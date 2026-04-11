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


# ── Basic quaternion / kinematics ─────────────────────────────────────────────

def theta_to_q(t1: float, t2: float, t3: float) -> Quaternion:
    """Motor angles (degrees) → camera quaternion in base frame."""
    qtheta1 = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
    m3_axis = np.array((qtheta1 * qtheta2).rotate([1, 0, 0]))
    qtheta3 = Quaternion(axis=m3_axis.tolist(), degrees=-t3)
    q = (qtheta3 * qtheta1 * qtheta2).normalised
    return q if t3 >= 0 else (-q).normalised

def q_from_azaltroll(az: float, alt: float, roll: float) -> Quaternion:
    """Build quaternion from (az, alt, roll) in degrees."""
    qaz  = Quaternion(axis=[0, 0, 1], degrees=-az + 90)
    qalt = Quaternion(axis=[0, 1, 0], degrees=-alt - 90)
    qnr  = qaz * qalt
    bore = np.array(qnr.rotate([0, 0, -1]))
    qroll = Quaternion(axis=bore.tolist(), degrees=-roll)
    return (qroll * qnr).normalised

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
    """Hardware-stable mechanical axis correction parameters."""
    m2_tilt_arcmin:   float = 0.0   # theta_model_a: M2 tilt amplitude (arcmin)
    m2_tilt_zero_deg: float = 0.0   # theta_model_b: zero crossing (degrees theta2)
    roll_amp_arcmin:  float = 0.0   # theta_model_c: boresight roll amplitude (arcmin)
    roll_zero_deg:    float = 0.0   # theta_model_d: roll zero crossing (degrees theta2)
    m3_encoder_k:     float = 0.0   # theta_model_e/60: M3 scale error (degrees/degree)

    @classmethod
    def from_config_values(cls,
                           theta_model_a: float = 0.0,
                           theta_model_b: float = 0.0,
                           theta_model_c: float = 0.0,
                           theta_model_d: float = 0.0,
                           theta_model_e: float = 0.0) -> 'ThetaModelParams':
        """Construct from config.toml theta_model_* values."""
        return cls(
            m2_tilt_arcmin   = theta_model_a,
            m2_tilt_zero_deg = theta_model_b,
            roll_amp_arcmin  = theta_model_c,
            roll_zero_deg    = theta_model_d,
            m3_encoder_k     = theta_model_e / 60.0,
        )


def apply_theta_corrections(q: Quaternion,
                             params: ThetaModelParams) -> Quaternion:
    """
    Apply B1 (M2 tilt), B2 (boresight roll), B3 (M3 encoder) corrections.

    B2 uses the boresight axis — not M2 — because M2 rotation is geometrically
    perpendicular to the boresight and cannot produce roll change.
    """
    t1, t2, t3 = q_to_theta(q)

    qtheta1   = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
    qtheta2   = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
    m2_axis   = np.array(qtheta1.rotate([0, 1, 0]))
    m3_axis   = np.array((qtheta1 * qtheta2).rotate([1, 0, 0]))
    boresight = np.array(q.rotate([0, 0, -1]))

    # B1: M2 axis tilt → altitude correction
    delta_t2 = -(params.m2_tilt_arcmin / 60.0) * math.sin(
        math.radians(t2 - params.m2_tilt_zero_deg))
    q_m2 = Quaternion(axis=m2_axis.tolist(), degrees=delta_t2)

    # B2: altitude-dependent roll offset → boresight rotation
    delta_roll = -(params.roll_amp_arcmin / 60.0) * math.cos(
        math.radians(t2 - params.roll_zero_deg))
    q_b2 = Quaternion(axis=boresight.tolist(), degrees=delta_roll)

    # B3: M3 encoder scale error
    delta_t3 = params.m3_encoder_k * t3
    q_m3 = Quaternion(axis=m3_axis.tolist(), degrees=delta_t3)

    return (q_m3 * q_b2 * q_m2 * q).normalised


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
