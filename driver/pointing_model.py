"""
pointing_model.py — Reusable pointing model functions.

All functions are pure (no global state, no Config references) so they
can be called identically from tests, cross-validation, and production.

Architecture:
  - Raw kinematics:    theta → q → az/alt/roll
  - Correction layers: polar_correction, theta_space_correction, rbc_correction
  - Alignment:         quest_solve (rigid body), polar_quest_solve (AW/AN + rigid)
  - Evaluation:        angular_error, residual_stats

Each correction layer is independent and composable.  The production
driver applies them in chain; the test suite can apply them selectively.
"""

import math
import numpy as np
from pyquaternion import Quaternion
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# -- Angle helpers (also used by fits_extract.py) --------------------------------

ROTATOR_OFFSET = 0.0   # Override if camera mounting introduces a roll bias


def wrap_to_180(angle: float) -> float:
    """Wrap angle to [-180, +180)."""
    return (angle + 180.0) % 360.0 - 180.0


def wrap_to_360(angle: float) -> float:
    """Wrap angle to [0, 360)."""
    wrapped = angle % 360.0
    return 0.0 if abs(wrapped - 360) < 1e-10 else wrapped


def wrap_to_90(angle: float) -> float:
    """Wrap angle to [-90, +90)."""
    return (angle + 90.0) % 180.0 - 90.0


def rotator_to_p_roll(rotator_deg: float) -> float:
    """Convert raw rotator angle to predicted roll, applying ROTATOR_OFFSET."""
    return wrap_to_180(rotator_deg - ROTATOR_OFFSET)


# -- Astronomy helpers -----------------------------------------------------------


def calc_parallactic_angle(az_deg: float, alt_deg: float, lat_deg: float) -> float:
    """
    Parallactic angle at (az, alt) for observer latitude lat_deg.
    Matches driver's calc_parallactic_angle().
    """
    if abs(alt_deg - 90.0) < 1e-6:
        return 0.0
    az  = math.radians(az_deg)
    alt = math.radians(alt_deg)
    lat = math.radians(lat_deg)
    num = math.sin(az)
    den = math.tan(lat) * math.cos(alt) - math.sin(alt) * math.cos(az)
    return wrap_to_180(-math.degrees(math.atan2(num, den)))


def radec_to_altaz(ra_deg: float, dec_deg: float,
                   lat_deg: float, lon_deg: float,
                   date_obs_utc: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Convert J2000 RA/Dec to topocentric Alt/Az using ephem.
    Returns (az_deg, alt_deg) or (None, None) if ephem unavailable.
    """
    try:
        import ephem
        obs = ephem.Observer()
        obs.lat   = math.radians(lat_deg)
        obs.long  = math.radians(lon_deg)
        obs.date  = ephem.Date(date_obs_utc.split('.')[0].replace('T', ' '))
        obs.epoch = ephem.J2000
        body = ephem.FixedBody()
        body._ra    = math.radians(ra_deg)
        body._dec   = math.radians(dec_deg)
        body._epoch = ephem.J2000
        body.compute(obs)
        return math.degrees(float(body.az)), math.degrees(float(body.alt))
    except Exception:
        return None, None


def crota2_from_cd(cd1_2: float, cd2_2: float) -> Tuple[Optional[float], str]:
    """Extract CROTA2 rotation angle from CD matrix elements."""
    if abs(cd1_2) < 1e-15 and abs(cd2_2) < 1e-15:
        return None, 'none'
    return wrap_to_180(math.degrees(math.atan2(-cd1_2, cd2_2))), 'CD_matrix'


def crota2_to_roll(crota2_deg: float,
                   az_deg: float, alt_deg: float,
                   lat_deg: float) -> Tuple[float, float, float]:
    """
    Convert CROTA2 WCS rotation to camera roll, position angle, parallactic angle.
    Returns (roll_deg, position_angle_deg, parallactic_angle_deg).
    """
    para           = calc_parallactic_angle(az_deg, alt_deg, lat_deg)
    position_angle = wrap_to_360(180 - crota2_deg)
    roll           = wrap_to_180(position_angle - para)
    return roll, position_angle, para


# -- Driver-matching IK (azaltroll_to_q / q_to_theta / azaltroll_to_theta) ------

class LastPosition:
    """Tracks previous motor position for IK disambiguation and gimbal lock."""
    def __init__(self, t1=180.0, t2=45.0, t3=0.0):
        self.last_theta1 = t1
        self.last_theta2 = t2
        self.last_theta3 = t3
        self.in_gimbal_lock = False

    def calcMechanicalAngularDiff(self, t1, t2, t3):
        def ad(a, b): return ((b - a + 180) % 360) - 180
        return ad(t1, self.last_theta1)**2 + ad(t2, self.last_theta2)**2 + ad(t3, self.last_theta3)**2

    def check_for_gimbal_lock(self, theta2=None):
        if theta2 is None:
            theta2 = self.last_theta2
        if not self.in_gimbal_lock and abs(theta2) < 1:
            self.in_gimbal_lock = True
        elif self.in_gimbal_lock and abs(theta2) > 3:
            self.in_gimbal_lock = False
        return self.in_gimbal_lock


def azaltroll_to_q(az: float, alt: float, roll: float) -> Quaternion:
    """Az/alt/roll (degrees) -> camera quaternion. Matches driver azaltroll_to_q()."""
    qaz   = Quaternion(axis=[0, 0, 1], degrees=-az + 90)
    qalt  = Quaternion(axis=[0, 1, 0], degrees=-alt - 90)
    qroll = Quaternion(axis=[0, 0, 1], degrees=roll)
    q1    = qaz * qalt * qroll
    return -(q1.normalised) if roll < 0 else q1.normalised


def q_to_theta_driver(motorQ_C2B: Quaternion,
                      lastPos: Optional['LastPosition'] = None,
                      ) -> Tuple[float, float, float]:
    """
    Camera quaternion -> (theta1, theta2, theta3) motor angles.
    Matches driver q_to_theta() exactly, including gimbal-lock handling.
    Use this when pa_* motor-space residuals need to match the driver's IK.
    """
    if lastPos is None:
        lastPos = LastPosition()
    q1     = motorQ_C2B
    tUp    = q1.rotate(np.array([1, 0, 0]))
    tRight = q1.rotate(np.array([0, 1, 0]))

    theta1_A = wrap_to_360(np.degrees(np.arctan2(-tUp[0], -tUp[1])))
    t1r_A    = np.radians(theta1_A)
    sin_t2_A = -(tUp[0] * np.sin(t1r_A) + tUp[1] * np.cos(t1r_A))
    theta2_A = wrap_to_90(np.degrees(np.arctan2(sin_t2_A, tUp[2])))
    theta1_B = wrap_to_360(theta1_A + 180)
    theta2_B = -theta2_A

    theta2_min, theta2_max = -8, 83
    validA = theta2_min <= theta2_A <= theta2_max
    validB = theta2_min <= theta2_B <= theta2_max

    def calc_theta3(theta1, theta2):
        qt1 = Quaternion(axis=[0, 0, 1], degrees=-theta1 + 90)
        qt2 = Quaternion(axis=[0, 1, 0], degrees=-theta2 - 90)
        tRight_no_M3 = (qt1 * qt2).rotate([0, 1, 0])
        r1 = tRight_no_M3 - np.dot(tRight_no_M3, tUp) * tUp
        r2 = tRight        - np.dot(tRight,        tUp) * tUp
        n1, n2 = np.linalg.norm(r1), np.linalg.norm(r2)
        if n1 < 1e-9 or n2 < 1e-9:
            return lastPos.last_theta3
        r1n, r2n = r1 / n1, r2 / n2
        cos_t3 = np.clip(np.dot(r1n, r2n), -1, 1)
        sin_t3 = np.dot(np.cross(r1n, r2n), tUp)
        return wrap_to_180(-np.degrees(np.arctan2(sin_t3, cos_t3)))

    if validA and not validB:
        theta1, theta2 = theta1_A, theta2_A
        theta3 = calc_theta3(theta1, theta2)
    elif validB and not validA:
        theta1, theta2 = theta1_B, theta2_B
        theta3 = calc_theta3(theta1, theta2)
    elif validA and validB:
        theta3_A = calc_theta3(theta1_A, theta2_A)
        theta3_B = calc_theta3(theta1_B, theta2_B)
        diffA = lastPos.calcMechanicalAngularDiff(theta1_A, theta2_A, theta3_A)
        diffB = lastPos.calcMechanicalAngularDiff(theta1_B, theta2_B, theta3_B)
        if diffA <= diffB:
            theta1, theta2, theta3 = theta1_A, theta2_A, theta3_A
        else:
            theta1, theta2, theta3 = theta1_B, theta2_B, theta3_B
    else:
        def dist(t2):
            if t2 < theta2_min: return theta2_min - t2
            if t2 > theta2_max: return t2 - theta2_max
            return 0.0
        if dist(theta2_B) < dist(theta2_A):
            theta1, theta2 = theta1_B, np.clip(theta2_B, theta2_min, theta2_max)
        else:
            theta1, theta2 = theta1_A, np.clip(theta2_A, theta2_min, theta2_max)
        theta3 = calc_theta3(theta1, theta2)

    if lastPos.check_for_gimbal_lock(theta2):
        locked_sum = wrap_to_360(theta1 + theta3)
        theta3 = 0.0
        theta1 = locked_sum

    return float(theta1), float(theta2), float(theta3)


def azaltroll_to_theta(p_az: float, p_alt: float, p_roll: float,
                       lastPos: Optional[LastPosition] = None,
                       ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Az/alt/roll (degrees) -> (theta1, theta2, theta3) via IK. Returns (None,None,None) on error."""
    try:
        motorQ = azaltroll_to_q(p_az, p_alt, p_roll)
        return q_to_theta_driver(motorQ, lastPos)
    except Exception:
        return None, None, None


# ── Basic quaternion / kinematics ─────────────────────────────────────────────

def theta_to_q(t1: float, t2: float, t3: float) -> Quaternion:
    """Motor angles (degrees) → camera quaternion in base frame."""
    qtheta1 = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
    m3_axis = np.array((qtheta1 * qtheta2).rotate([1, 0, 0]))
    qtheta3 = Quaternion(axis=m3_axis.tolist(), degrees=-t3)
    q = (qtheta3 * qtheta1 * qtheta2).normalised
    return q if t3 >= 0 else (-q).normalised


def q_to_azaltroll(q: Quaternion) -> Tuple[float, float, float]:
    """Camera quaternion → (az, alt, roll) in degrees.  az in [0,360)."""
    bore = q.rotate([0, 0, -1])
    az   = math.degrees(math.atan2(bore[0], bore[1])) % 360
    alt  = math.degrees(math.asin(max(-1.0, min(1.0, bore[2]))))
    qaz  = Quaternion(axis=[0, 0, 1], degrees=-az + 90)
    qalt = Quaternion(axis=[0, 1, 0], degrees=-alt - 90)
    qnr  = qaz * qalt
    qa   = q if (qnr * q.inverse).scalar >= 0 else -q
    qr   = qnr.inverse * qa
    roll = math.degrees(2 * math.atan2(
        math.sqrt(qr[1]**2 + qr[2]**2 + qr[3]**2), qr[0]))
    if qr[3] < 0:
        roll = -roll
    return az, alt, roll


def q_to_theta(q: Quaternion) -> Tuple[float, float, float]:
    """Camera quaternion → (theta1, theta2, theta3) in degrees."""
    tUp    = np.array(q.rotate([1, 0, 0]))
    tRight = np.array(q.rotate([0, 1, 0]))

    theta1_A = float(math.degrees(math.atan2(-tUp[0], -tUp[1])) % 360)
    t1r      = math.radians(theta1_A)
    sin_t2   = -(tUp[0] * math.sin(t1r) + tUp[1] * math.cos(t1r))
    theta2_A = float(max(-90.0, min(90.0,
                   math.degrees(math.atan2(sin_t2, tUp[2])))))
    theta1_B = (theta1_A + 180) % 360
    theta2_B = -theta2_A

    def _theta3(t1, t2):
        qt1  = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
        qt2  = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
        tR0  = np.array((qt1 * qt2).rotate([0, 1, 0]))
        r1   = tR0    - np.dot(tR0,    tUp) * tUp
        r2   = tRight - np.dot(tRight, tUp) * tUp
        n1, n2 = np.linalg.norm(r1), np.linalg.norm(r2)
        if n1 < 1e-9 or n2 < 1e-9:
            return 0.0
        r1n, r2n = r1 / n1, r2 / n2
        cross_z = float(np.dot(np.cross(r1n, r2n), tUp))
        dot     = float(np.clip(np.dot(r1n, r2n), -1.0, 1.0))
        return float(((-(math.degrees(math.atan2(cross_z, dot))) + 180) % 360) - 180)

    if -8 <= theta2_A <= 83:
        return theta1_A, theta2_A, _theta3(theta1_A, theta2_A)
    return theta1_B, theta2_B, _theta3(theta1_B, theta2_B)


def wrap180(x: float) -> float:
    return ((x + 180) % 360) - 180


def angular_error_arcmin(
        az_pred: float, alt_pred: float,
        az_true: float, alt_true: float) -> float:
    """Great-circle angular separation in arcminutes."""
    az1, az2 = math.radians(az_pred), math.radians(az_true)
    al1, al2 = math.radians(alt_pred), math.radians(alt_true)
    cos_sep = (math.sin(al1) * math.sin(al2) +
               math.cos(al1) * math.cos(al2) * math.cos(az1 - az2))
    cos_sep = max(-1.0, min(1.0, cos_sep))
    return math.degrees(math.acos(cos_sep)) * 60.0


# ── Polar correction (TPoint AW/AN, or NINA TPPA output) ─────────────────────

def make_polar_corrQ(theta1_deg: float,
                     AW_deg: float, AN_deg: float) -> Quaternion:
    """
    Quaternion that corrects the base frame for polar axis tilt.

    Parameters
    ----------
    theta1_deg : current mount azimuth (theta1 / M1 angle)
    AW_deg     : N-S tilt of az axis (degrees).  TPoint AW.
                 Positive = axis tilts North (pole too HIGH).
    AN_deg     : E-W tilt of az axis (degrees).  TPoint AN.
                 Positive = axis tilts East.

    From NINA TPPA output:
        AW_deg = -tppa_alt_error_arcmin / 60   (pole too low → neg AW)
        AN_deg = +tppa_az_error_arcmin  / 60   (pole too far east → pos AN)

    Returns
    -------
    Quaternion such that  q_corrected = corrQ * q_base
    """
    tilt = math.sqrt(AW_deg**2 + AN_deg**2)
    if tilt < 1e-6:
        return Quaternion(1, 0, 0, 0)

    # n_polar: the true az axis direction in the base frame
    eps = math.radians(tilt)
    # AW is N-S (cos component), AN is E-W (sin component)
    phi = math.atan2(AN_deg, AW_deg)      # direction the axis tilts toward
    n_polar = [
        math.sin(eps) * math.sin(phi),
        math.sin(eps) * math.cos(phi),
        math.cos(eps),
    ]
    q_real  = Quaternion(axis=n_polar,  degrees=-theta1_deg + 90)
    q_ideal = Quaternion(axis=[0, 0, 1], degrees=-theta1_deg + 90)
    return (q_real * q_ideal.inverse).normalised


def q_from_azaltroll(az: float, alt: float, roll: float) -> Quaternion:
    """Build quaternion from (az, alt, roll) in degrees."""
    qaz  = Quaternion(axis=[0, 0, 1], degrees=-az + 90)
    qalt = Quaternion(axis=[0, 1, 0], degrees=-alt - 90)
    qnr  = qaz * qalt
    bore = np.array(qnr.rotate([0, 0, -1]))
    qroll = Quaternion(axis=bore.tolist(), degrees=-roll)
    return (qroll * qnr).normalised


def apply_polar_correction(q: Quaternion,
                           AW_deg: float, AN_deg: float,
                           undo: bool = False,
                           _corrQ: Optional[Quaternion] = None,
                           ) -> Quaternion:
    """
    Apply (or undo) polar correction to q_base.

    For apply:  returns q_corrected = corrQ * q
    For undo:   pass the corrQ returned from the apply step as _corrQ,
                then returns corrQ.inverse * q_corrected (exact round-trip).

    Usage:
        q_corr, corrQ = apply_polar_correction_pair(q, AW, AN)
        q_undo        = apply_polar_correction(q_corr, AW, AN,
                                               undo=True, _corrQ=corrQ)
    """
    if undo:
        if _corrQ is None:
            # Fallback: recompute corrQ from q — NOT exact if theta1 changed
            t1, _, _ = q_to_theta(q)
            _corrQ = make_polar_corrQ(t1, AW_deg, AN_deg)
        return (_corrQ.inverse * q).normalised
    t1, _, _ = q_to_theta(q)
    corrQ = make_polar_corrQ(t1, AW_deg, AN_deg)
    return (corrQ * q).normalised


def apply_polar_correction_pair(q: Quaternion,
                                 AW_deg: float,
                                 AN_deg: float,
                                 ) -> Tuple[Quaternion, Quaternion]:
    """
    Apply polar correction, returning (q_corrected, corrQ).
    Use corrQ.inverse to undo exactly: q_orig = corrQ.inverse * q_corrected.
    """
    t1, _, _ = q_to_theta(q)
    corrQ = make_polar_corrQ(t1, AW_deg, AN_deg)
    return (corrQ * q).normalised, corrQ


# ── Theta-space mechanical corrections ───────────────────────────────────────

@dataclass
class ThetaModelParams:
    """
    Hardware-stable mechanical axis correction parameters.

    Applied in order B5 → B1 → B3 by apply_theta_corrections().

    Parameters
    ----------
    m2_tilt_arcmin   : theta_model_a  M2 axis tilt amplitude (arcmin).
                       pa_dev_theta2 = a * sin(theta2 - b)
    m2_tilt_zero_deg : theta_model_b  theta2 at which B1 error is zero (degrees).
    roll_amp_arcmin  : theta_model_c  Altitude-dependent roll residual amplitude.
                       DIAGNOSTIC ONLY — not applied in corrections.
    roll_zero_deg    : theta_model_d  theta2 at which roll residual is zero.
                       DIAGNOSTIC ONLY — not applied in corrections.
    m3_encoder_k     : theta_model_e / 60.  M3 scale error (degrees/degree).
                       pa_dev_theta3 = e * theta3
    m3_axis_tilt_k   : theta_model_f / 60.  M3 axis tilt → altitude (degrees/degree).
                       delta_theta2 = -(f/60) * theta3
                       Dominant error at large roll; ~2.4 arcmin/degree.
                       Best estimate: theta_model_f = -2.394 arcmin/degree.
    """
    m2_tilt_arcmin:   float = 0.0   # theta_model_a
    m2_tilt_zero_deg: float = 0.0   # theta_model_b
    roll_amp_arcmin:  float = 0.0   # theta_model_c  [diagnostic only]
    roll_zero_deg:    float = 0.0   # theta_model_d  [diagnostic only]
    m3_encoder_k:     float = 0.0   # theta_model_e / 60
    m3_axis_tilt_k:   float = 0.0   # theta_model_f / 60  (M3 axis tilt → altitude)

    @classmethod
    def from_config_values(cls,
                           theta_model_a: float = 0.0,
                           theta_model_b: float = 0.0,
                           theta_model_c: float = 0.0,
                           theta_model_d: float = 0.0,
                           theta_model_e: float = 0.0,
                           theta_model_f: float = 0.0) -> 'ThetaModelParams':
        """Construct from config.toml theta_model_* values."""
        return cls(
            m2_tilt_arcmin   = theta_model_a,
            m2_tilt_zero_deg = theta_model_b,
            roll_amp_arcmin  = theta_model_c,
            roll_zero_deg    = theta_model_d,
            m3_encoder_k     = theta_model_e / 60.0,
            m3_axis_tilt_k   = theta_model_f / 60.0,
        )


def apply_theta_corrections(q: Quaternion,
                             params: ThetaModelParams) -> Quaternion:
    """
    Apply mechanical axis corrections to camera quaternion.

    Correction order (applied left-to-right, outermost first):
      B5 first: removes dominant M3-axis-tilt error so B1 residuals are clean.
      B1 next:  removes M2-axis-tilt altitude error.
      B3 last:  removes M3 encoder scale error.

    B5 — M3 axis tilt -> altitude (theta_model_f)  [DOMINANT, apply first]
      Physical cause: M3 rotation axis is not exactly camera UP.
      Rotating M3 sweeps the boresight vertically.
      Correction: rotate around M2 axis (altitude axis) by -(f/60)*theta3 degrees.
      Formula:  delta_theta2 = -(theta_model_f / 60) * theta3

    B1 — M2 axis tilt -> altitude (theta_model_a, theta_model_b)
      Physical cause: M2 rotation axis not perpendicular to M1.
      Correction: rotate around M2 axis by -(a/60)*sin(theta2-b) degrees.
      Formula:  delta_theta2 = -(theta_model_a / 60) * sin(theta2 - theta_model_b)

    B3 — M3 encoder scale error (theta_model_e)
      Physical cause: M3 encoder reads more/less rotation than occurred.
      Correction: rotate around M3 axis by (e/60)*theta3 degrees.
      Formula:  delta_theta3 = (theta_model_e / 60) * theta3

    B2 (theta_model_c/d) is NOT applied here — it is diagnostic only.
    M2 rotation is perpendicular to the boresight and cannot produce roll change,
    so the cos(theta2) roll signal has a different origin (QUEST residual artefact).

    RBC (rbc_model_a/b/c) is DECOMMISSIONED.
    It was modelling the B5 M3-axis-tilt error in the wrong axis (roll/az),
    causing divergence in slew-and-centre at large roll angles.
    """
    t1, t2, t3 = q_to_theta(q)

    qtheta1 = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
    m2_axis = np.array(qtheta1.rotate([0, 1, 0]))
    m3_axis = np.array((qtheta1 * qtheta2).rotate([1, 0, 0]))

    # B5: M3 axis tilt -> altitude (apply first — dominant error)
    # Rotates around M2 axis (altitude) by -(theta_model_f/60)*theta3 degrees
    delta_t2_b5 = -params.m3_axis_tilt_k * t3
    q_b5 = Quaternion(axis=m2_axis.tolist(), degrees=delta_t2_b5)

    # B1: M2 axis tilt -> altitude
    delta_t2_b1 = -(params.m2_tilt_arcmin / 60.0) * math.sin(
        math.radians(t2 - params.m2_tilt_zero_deg))
    q_b1 = Quaternion(axis=m2_axis.tolist(), degrees=delta_t2_b1)

    # B3: M3 encoder scale error
    delta_t3 = params.m3_encoder_k * t3
    q_b3 = Quaternion(axis=m3_axis.tolist(), degrees=delta_t3)

    return (q_b3 * q_b1 * q_b5 * q).normalised


# ── RBC correction ────────────────────────────────────────────────────────────

@dataclass
class RBCParams:
    """Sky-space rotation bias correction parameters."""
    rbc_model_a: float = 0.0
    rbc_model_b: float = 0.0
    rbc_model_c: float = 0.0
    alt_clamp:   float = 75.0


def calc_rbc_corrQ(q: Quaternion,
                   params: RBCParams,
                   sign: float = -1.0) -> Tuple[Optional[Quaternion], float]:
    """
    Compute RBC correction quaternion and roll error.

    sign = -1 for apply (forward), +1 for undo (inverse).
    Returns (corrQ, roll_error_deg).  corrQ is None if correction is negligible.

    Boresight and Z-axis rotations are both perpendicular to altitude,
    so no altitude residual is introduced — corrQ_alt is not needed.
    """
    _, p_alt, p_roll = q_to_azaltroll(q)
    p_alt_clamped    = min(p_alt, params.alt_clamp)
    slope            = (params.rbc_model_a * math.tan(math.radians(p_alt_clamped))
                        + params.rbc_model_b)
    roll_error_deg   = slope * p_roll / 60.0

    if abs(roll_error_deg) < 1e-6:
        return None, 0.0

    boresight_B = np.array(q.rotate([0, 0, -1]))
    corrQ_roll  = Quaternion(axis=boresight_B.tolist(),
                              degrees=sign * roll_error_deg)
    az_error_deg = params.rbc_model_c * roll_error_deg
    corrQ_az     = Quaternion(axis=[0, 0, 1],
                               degrees=sign * az_error_deg)
    return (corrQ_az * corrQ_roll).normalised, roll_error_deg


# ── QUEST alignment ───────────────────────────────────────────────────────────

def quest_solve(sync_pairs: List[Tuple[Quaternion, Quaternion]]) -> Quaternion:
    """
    Standard QUEST: find alignQ minimising sum of angular errors.
    alignQ such that alignQ * q_base ≈ q_topo for all (q_base, q_topo) pairs.
    Requires >= 1 pair.
    """
    B = np.zeros((3, 3))
    ref_vecs = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    for q_base, q_topo in sync_pairs:
        for v in ref_vecs:
            b = np.array(q_base.rotate(v))
            r = np.array(q_topo.rotate(v))
            B += np.outer(r, b)
    U, _, Vt = np.linalg.svd(B)
    d = np.linalg.det(U @ Vt)
    D = np.diag([1.0, 1.0, d])
    R = U @ D @ Vt
    return Quaternion(matrix=R)


def polar_quest_solve(
        sync_pairs: List[Tuple[Quaternion, Quaternion]],
        AW_init: float = 0.0,
        AN_init: float = 0.0,
        min_pairs: int = 3,
        min_az_spread_deg: float = 60.0,
) -> Tuple[Quaternion, float, float]:
    """
    Polar-aware QUEST: jointly fit AW, AN (polar tilt) and alignQ.

    Uses TPoint AW/AN parameterisation — linear in corrections, so we
    solve via linear least squares rather than nonlinear optimisation:

        Δaz  = (AW·sin(az) − AN·cos(az)) / cos(alt)
        Δalt =  AW·cos(az) + AN·sin(az)

    With these applied to q_base before QUEST, the residual alignQ
    absorbs only the constant rigid-body offset.

    Falls back to standard QUEST if:
    - fewer than min_pairs sync points
    - az spread across sync points < min_az_spread_deg

    Returns
    -------
    (alignQ, AW_deg, AN_deg)
    """
    from scipy.optimize import minimize

    azimuths = []
    for q_base, _ in sync_pairs:
        az, _, _ = q_to_azaltroll(q_base)
        azimuths.append(az)

    def _circular_spread(azs):
        s = sorted(a % 360 for a in azs)
        if len(s) <= 1: return 0.0
        gaps = [s[i+1] - s[i] for i in range(len(s)-1)]
        gaps.append(360 - s[-1] + s[0])
        return 360.0 - max(gaps)

    az_spread = _circular_spread(azimuths)

    if len(sync_pairs) < min_pairs or az_spread < min_az_spread_deg:
        return quest_solve(sync_pairs), 0.0, 0.0

    def residual_rms(params):
        AW, AN = params
        corrected = []
        for q_base, q_topo in sync_pairs:
            az, _, _ = q_to_azaltroll(q_base)
            q_corr   = apply_polar_correction(q_base, AW, AN)
            corrected.append((q_corr, q_topo))
        aQ  = quest_solve(corrected)
        errs = []
        for q_corr, q_topo in corrected:
            dq  = q_topo * (aQ * q_corr).inverse
            imag_norm = math.sqrt(dq[1]**2 + dq[2]**2 + dq[3]**2)
            err = math.degrees(2 * math.asin(min(1.0, imag_norm))) * 60
            errs.append(err)
        return float(np.sqrt(np.mean(np.array(errs)**2)))

    result = minimize(
        residual_rms, [AW_init, AN_init],
        method='Nelder-Mead',
        options={'xatol': 0.001, 'fatol': 0.05, 'maxiter': 5000},
    )
    AW_fit, AN_fit = float(result.x[0]), float(result.x[1])

    corrected = []
    for q_base, q_topo in sync_pairs:
        q_corr = apply_polar_correction(q_base, AW_fit, AN_fit)
        corrected.append((q_corr, q_topo))
    alignQ = quest_solve(corrected)
    return alignQ, AW_fit, AN_fit


# ── Session and observation data structures ───────────────────────────────────

@dataclass
class Observation:
    """One plate-solved frame — the atomic unit of truth data."""
    session_id:  str
    filename:    str
    # Motor state
    theta1:      float
    theta2:      float
    theta3:      float
    p_az:        float
    p_alt:       float
    p_roll:      float
    # Ground truth
    solved_az:   float
    solved_alt:  float
    solved_roll: float
    # Raw deviations (arcmin) — computed from the above, session-independent
    dev_az_arcmin:   float
    dev_alt_arcmin:  float
    dev_roll_arcmin: float

    @property
    def q_base(self) -> Quaternion:
        return theta_to_q(self.theta1, self.theta2, self.theta3)

    @property
    def q_solved(self) -> Quaternion:
        """Quaternion that points at the plate-solved position (az, alt, roll)."""
        return q_from_azaltroll(self.solved_az, self.solved_alt, self.solved_roll)

    def angular_error_arcmin(self, az_pred: float, alt_pred: float) -> float:
        return angular_error_arcmin(az_pred, alt_pred,
                                    self.solved_az, self.solved_alt)


@dataclass
class Session:
    """All observations from one imaging night."""
    session_id:   str
    observations: List[Observation] = field(default_factory=list)

    # Per-session model parameters (fitted during evaluation)
    alignQ:  Optional[Quaternion] = None
    AW_deg:  float = 0.0    # TPoint AW: N-S polar axis tilt
    AN_deg:  float = 0.0    # TPoint AN: E-W polar axis tilt

    @property
    def n(self) -> int:
        return len(self.observations)

    def az_spread_deg(self) -> float:
        """Azimuth spread of observations — governs polar fit reliability."""
        if not self.observations:
            return 0.0
        azimuths = [o.p_az for o in self.observations]
        spread = max(azimuths) - min(azimuths)
        return min(spread, 360 - spread)


# ── CSV I/O ───────────────────────────────────────────────────────────────────

import csv
import os


def load_session_csv(path: str,
                     session_id: Optional[str] = None) -> Session:
    """
    Load a fits_extract CSV as a Session.

    session_id defaults to the stem of the file path (e.g. '2024-01-15').
    Only solved rows are loaded.  pa_* fields are ignored — they are
    session-specific and not portable across sessions.
    """
    if session_id is None:
        session_id = os.path.splitext(os.path.basename(path))[0]

    obs_list = []
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            if row.get('status') != 'solved':
                continue
            try:
                obs = Observation(
                    session_id      = session_id,
                    filename        = row.get('filename', ''),
                    theta1          = float(row['theta1']),
                    theta2          = float(row['theta2']),
                    theta3          = float(row['theta3']),
                    p_az            = float(row['p_az']),
                    p_alt           = float(row['p_alt']),
                    p_roll          = float(row['p_roll']),
                    solved_az       = float(row['solved_az']),
                    solved_alt      = float(row['solved_alt']),
                    solved_roll     = float(row['solved_roll']),
                    dev_az_arcmin   = float(row['dev_az_arcmin']),
                    dev_alt_arcmin  = float(row['dev_alt_arcmin']),
                    dev_roll_arcmin = float(row['dev_roll_arcmin']),
                )
                obs_list.append(obs)
            except (ValueError, KeyError):
                continue

    return Session(session_id=session_id, observations=obs_list)


def combine_sessions(sessions: List[Session]) -> List[Observation]:
    """Flatten multiple sessions into a single observation list."""
    return [obs for s in sessions for obs in s.observations]


# ── Evaluation helpers ────────────────────────────────────────────────────────

@dataclass
class ResidualStats:
    """Summary statistics for a set of pointing residuals."""
    n:        int
    rms:      float   # arcmin
    median:   float   # arcmin
    p95:      float   # arcmin (95th percentile)
    std:      float   # arcmin


def residual_stats(errors_arcmin: List[float]) -> ResidualStats:
    arr = np.array(errors_arcmin)
    return ResidualStats(
        n      = len(arr),
        rms    = float(np.sqrt(np.mean(arr**2))),
        median = float(np.median(arr)),
        p95    = float(np.percentile(arr, 95)),
        std    = float(np.std(arr)),
    )


def predict_pointing(obs: Observation,
                     alignQ: Quaternion,
                     AW_deg: float = 0.0,
                     AN_deg: float = 0.0,
                     theta_params: Optional[ThetaModelParams] = None,
                     rbc_params:   Optional[RBCParams] = None,
                     ) -> Tuple[float, float, float]:
    """
    Apply the full correction chain and return predicted (az, alt, roll).

    Chain (order matters):
      1. theta-space corrections (hardware, applied to raw motor q)
      2. polar correction (session-level)
      3. QUEST alignment (session-level rigid body)
      4. RBC correction (hardware, applied after alignment)
    """
    q = obs.q_base

    if theta_params is not None:
        q = apply_theta_corrections(q, theta_params)

    if AW_deg != 0.0 or AN_deg != 0.0:
        q = apply_polar_correction(q, AW_deg, AN_deg)

    if alignQ is not None:
        q = (alignQ * q).normalised

    if rbc_params is not None:
        corrQ, _ = calc_rbc_corrQ(q, rbc_params, sign=-1)
        if corrQ is not None:
            q = (corrQ * q).normalised

    return q_to_azaltroll(q)


def evaluate_session(session: Session,
                     alignQ: Quaternion,
                     AW_deg: float = 0.0,
                     AN_deg: float = 0.0,
                     theta_params: Optional[ThetaModelParams] = None,
                     rbc_params:   Optional[RBCParams] = None,
                     sync_indices: Optional[List[int]] = None,
                     ) -> Tuple[ResidualStats, ResidualStats]:
    """
    Evaluate pointing residuals for a session.

    Returns (sync_stats, test_stats) where:
      sync_stats = residuals on the sync subset (should be near zero for QUEST)
      test_stats = residuals on the held-out non-sync observations

    If sync_indices is None, all observations are treated as test points.
    """
    sync_set = set(sync_indices or [])
    sync_errs, test_errs = [], []

    for i, obs in enumerate(session.observations):
        az_pred, alt_pred, _ = predict_pointing(
            obs, alignQ, AW_deg, AN_deg, theta_params, rbc_params)
        err = obs.angular_error_arcmin(az_pred, alt_pred)
        if i in sync_set:
            sync_errs.append(err)
        else:
            test_errs.append(err)

    sync_stats = residual_stats(sync_errs) if sync_errs else residual_stats([0.0])
    test_stats = residual_stats(test_errs) if test_errs else residual_stats([0.0])
    return sync_stats, test_stats


def fit_session_alignment(session: Session,
                          sync_indices: List[int],
                          AW_deg: float = 0.0,
                          AN_deg: float = 0.0,
                          theta_params: Optional[ThetaModelParams] = None,
                          fit_polar: bool = False,
                          ) -> Tuple[Quaternion, float, float]:
    """
    Fit alignQ (and optionally AW/AN) from a subset of sync observations.

    theta_params corrections are applied before building sync pairs,
    so alignQ absorbs only the residual after hardware corrections.
    """
    pairs = []
    for i in sync_indices:
        obs = session.observations[i]
        q   = obs.q_base
        if theta_params is not None:
            q = apply_theta_corrections(q, theta_params)
        pairs.append((q, obs.q_solved))

    if fit_polar:
        return polar_quest_solve(pairs, AW_init=AW_deg, AN_init=AN_deg)
    else:
        alignQ = quest_solve(pairs)
        return alignQ, AW_deg, AN_deg
