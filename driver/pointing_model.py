"""
pointing_model.py — Production pointing model for the Benro Polaris driver.

Provides the kinematics, mechanical corrections, and QUEST alignment used
in the real-time driver.  No file I/O, no CSV reading, no analysis helpers.

Contents
--------
  Angle helpers       wrap_to_180/360/90, wrap180, rotator_to_p_roll
  Astronomy helpers   calc_parallactic_angle, radec_to_altaz, crota2_from_cd,
                      crota2_to_roll  (used by driver and fits_extract)
  IK / FK             theta_to_q, q_to_theta, q_to_azaltroll, azaltroll_to_q
                      azaltroll_to_theta, q_from_azaltroll, LastPosition
  Polar correction    make_polar_corrQ, apply_polar_correction[_pair]
  Mechanical corr.    MountModelParams, apply_mechanical_corrections
  QUEST alignment     quest_solve
  Misc                angular_error_arcmin
"""

import math
import numpy as np
from pyquaternion import Quaternion
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ── Angle helpers ─────────────────────────────────────────────────────────────

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


def wrap180(x: float) -> float:
    """Wrap angle to [-180, +180).  Alias for wrap_to_180."""
    return ((x + 180) % 360) - 180


def rotator_to_p_roll(rotator_deg: float) -> float:
    """Convert raw rotator angle to predicted roll, applying ROTATOR_OFFSET."""
    return wrap_to_180(rotator_deg - ROTATOR_OFFSET)


# ── Astronomy helpers ─────────────────────────────────────────────────────────

def calc_parallactic_angle(az_deg: float, alt_deg: float, lat_deg: float) -> float:
    """Parallactic angle at (az, alt) for observer latitude lat_deg (degrees)."""
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
    Returns (az_deg, alt_deg) or (None, None) if ephem unavailable or on error.
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


def crota2_from_cd(cd1_2: float, cd2_2: float) -> Optional[float]:
    """
    Extract CROTA2 rotation angle (degrees) from WCS CD matrix elements.
    Returns None if both elements are effectively zero.
    """
    if abs(cd1_2) < 1e-15 and abs(cd2_2) < 1e-15:
        return None
    return wrap_to_180(math.degrees(math.atan2(-cd1_2, cd2_2)))


def crota2_to_roll(crota2_deg: float,
                   az_deg: float, alt_deg: float,
                   lat_deg: float) -> Tuple[float, float]:
    """
    Convert CROTA2 WCS rotation to camera roll and parallactic angle.
    Returns (roll_deg, parallactic_angle_deg).
    """
    para           = calc_parallactic_angle(az_deg, alt_deg, lat_deg)
    position_angle = wrap_to_360(180.0 - crota2_deg)
    return wrap_to_180(position_angle - para), para


# ── IK / FK (inverse and forward kinematics) ─────────────────────────────────

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


# ── Mechanical axis corrections ───────────────────────────────────────────────

@dataclass
class MountModelParams:
    """
    Mechanical axis correction parameters for the Benro Polaris mount.

    Field names match config.toml exactly — no translation layer.
    All angular parameters are stored in arcmin or arcmin/deg as noted;
    the /60 conversion to degrees happens explicitly in apply_mechanical_corrections.

    Correction groups (in order of importance):

    M3 tilt correction  — M3 rotation axis is physically tilted.
      When M3 rotates (changing roll), the boresight sweeps an arc rather than
      staying fixed. The tilt projects onto both the altitude (M2) and azimuth (M1)
      axes, with the azimuth component growing with altitude.

      m3_tilt_alt   arcmin/deg  altitude effect of M3 tilt
                                Fitted error: dev_theta2 [arcmin] = m3_tilt_alt * theta3
                                Typical: -4.0

      m3_tilt_az    arcmin/deg  azimuth effect of M3 tilt (altitude-dependent)
                                Fitted error: dev_theta1 [arcmin] = m3_tilt_az * sin(theta2) * theta3
                                Typical: +2.56

    M2 tilt correction  — M2 rotation axis not perpendicular to M1.
      Rotating M2 (altitude) doesn't track a true vertical arc. Error varies
      sinusoidally with altitude angle theta2, affecting only theta2.

      m2_tilt_alt_amp   arcmin    amplitude of altitude error
                                  Fitted error: dev_theta2 [arcmin] = m2_tilt_alt_amp * sin(theta2 - m2_tilt_alt_zero)
                                  Typical: 52.2

      m2_tilt_alt_zero  degrees   theta2 at which M2 tilt error is zero
                                  Typical: 36.4

    M3 encoder correction  — M3 encoder reads more/less than actual rotation.
      Produces a proportional error in theta3. Treat with caution until SPA
      roll bias is resolved.

      m3_encoder_scale  arcmin/deg  encoder scale error
                                    Fitted error: dev_theta3 [arcmin] = m3_encoder_scale * theta3
                                    Typical: 0.0
    """
    m3_tilt_alt:      float = 0.0   # arcmin/deg — M3 tilt altitude effect
    m3_tilt_az:       float = 0.0   # arcmin/deg — M3 tilt azimuth effect
    m2_tilt_alt_amp:  float = 0.0   # arcmin     — M2 tilt amplitude
    m2_tilt_alt_zero: float = 0.0   # degrees    — M2 tilt zero crossing
    m3_encoder_scale: float = 0.0   # arcmin/deg — M3 encoder scale error

    @classmethod
    def from_config(cls, config) -> 'MountModelParams':
        """Construct from a Config object. Field names must match config attributes."""
        return cls(
            m3_tilt_alt      = config.m3_tilt_alt,
            m3_tilt_az       = config.m3_tilt_az,
            m2_tilt_alt_amp  = config.m2_tilt_alt_amp,
            m2_tilt_alt_zero = config.m2_tilt_alt_zero,
            m3_encoder_scale = config.m3_encoder_scale,
        )


def apply_mechanical_corrections(q: Quaternion, params: MountModelParams) -> Quaternion:
    """
    Apply mechanical axis corrections to camera quaternion.

    Correction order (applied right-to-left in return expression):
      M3 tilt az  (innermost): azimuth component of M3 axis tilt.
      M3 tilt alt (next):      altitude component of M3 axis tilt (dominant).
      M2 tilt     (next):      M2 axis tilt altitude error.
      M3 encoder  (outermost): M3 encoder scale error.

    M3 tilt correction [m3_tilt_alt, m3_tilt_az]
      Physical cause: M3 rotation axis tilted from ideal boresight direction.
      Altitude effect:
        Fitted error:   dev_theta2 [arcmin] = m3_tilt_alt * theta3
        Correction:     rotate around M2 axis by -(m3_tilt_alt/60) * theta3 degrees.
      Azimuth effect (altitude-dependent):
        Fitted error:   dev_theta1 [arcmin] = m3_tilt_az * sin(theta2) * theta3
        Correction:     rotate around M1 axis by +(m3_tilt_az/60) * sin(theta2) * theta3 degrees.

    M2 tilt correction [m2_tilt_alt_amp, m2_tilt_alt_zero]
      Physical cause: M2 rotation axis not perpendicular to M1.
      Fitted error:   dev_theta2 [arcmin] = m2_tilt_alt_amp * sin(theta2 - m2_tilt_alt_zero)
      Correction:     rotate around M2 axis by -(m2_tilt_alt_amp/60) * sin(theta2 - m2_tilt_alt_zero) degrees.

    M3 encoder correction [m3_encoder_scale]
      Physical cause: M3 encoder reads more/less rotation than occurred.
      Fitted error:   dev_theta3 [arcmin] = m3_encoder_scale * theta3
      Correction:     rotate around M3 axis by (m3_encoder_scale/60) * theta3 degrees.
    """
    t1, t2, t3 = q_to_theta(q)

    qtheta1 = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
    m2_axis = qtheta1.rotate([0, 1, 0])
    m3_axis = (qtheta1 * qtheta2).rotate([1, 0, 0])

    # M3 tilt correction — altitude component (dominant)
    q_m3_tilt_alt = Quaternion(axis=m2_axis,
                               degrees=-(params.m3_tilt_alt / 60.0) * t3)

    # M3 tilt correction — azimuth component (altitude-dependent)
    q_m3_tilt_az = Quaternion(axis=[0.0, 0.0, 1.0],
                              degrees=(params.m3_tilt_az / 60.0) * math.sin(math.radians(t2)) * t3)

    # M2 tilt correction — altitude error
    q_m2_tilt = Quaternion(axis=m2_axis,
                           degrees=-(params.m2_tilt_alt_amp / 60.0) * math.sin(
                               math.radians(t2 - params.m2_tilt_alt_zero)))

    # M3 encoder correction — roll scale error
    q_m3_encoder = Quaternion(axis=m3_axis,
                              degrees=(params.m3_encoder_scale / 60.0) * t3)

    # Applied right-to-left: M3_tilt_az, M3_tilt_alt, M2_tilt, M3_encoder
    return (q_m3_encoder * q_m2_tilt * q_m3_tilt_alt * q_m3_tilt_az * q).normalised

# ── QUEST alignment ──────────────────────────────────────────────────────────

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