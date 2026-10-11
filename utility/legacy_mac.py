# -*- coding: utf-8 -*-
"""
Legacy Mechanical Alignment Correction (MAC) model, removed from the driver in October 2026 (replaced by the
alignment model in driver/align_model.py: M2/M3 zero offsets and an M2 scale fitted with QUEST -- see
docs/study_alignment_mac_v2.md). Kept here only for utility/fits_extract.py's older image-based analysis.
"""
import math
import sys
import os
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from quaternion import Q as Quaternion                                         # noqa: E402
from kinematics import *                                                       # noqa: E402,F401,F403


# ── Mechanical axis corrections ───────────────────────────────────────────────

@dataclass
class MountModelParams:
    """
    Mechanical axis correction parameters for the Benro Polaris mount.
    """
    m3_tilt_dm2:      float = 0.0   # arcmin    — M3 tilt altitude effect
    m3_tilt_dm1:      float = 0.0   # arcmin    — M3 tilt azimuth effect
    m3_tilt_dm3:      float = 0.0   # arcmin    — M3 tilt roll effect
    m2_tilt_dm2_amp:  float = 0.0   # arcmin    — M2 tilt amplitude
    m2_tilt_dm2_zero: float = 0.0   # degrees   — M2 tilt zero crossing
    m2_roll_coupling: float = 0.0   # arcmin    — M2 roll coupling (theta2-dependent roll error)
    m2_roll_zero:     float = 45.0  # degrees   — theta2 where M2 roll coupling is zero
    m1_offset:        float = 0.0   # arcmin    — Polar Alignment M1/Az offset
    m2_offset:        float = 0.0   # arcmin    — Polar Alignment M2/Alt offset
    m3_offset:        float = 0.0   # arcmin    — Polar Alignment M3 offset

    @classmethod
    def from_config(cls, config):
        get = (lambda k: config[k]) if isinstance(config, dict) else (lambda k: getattr(config, k))
        return cls(
            m3_tilt_dm2      = get('m3_tilt_dm2'),
            m3_tilt_dm1      = get('m3_tilt_dm1'),
            m3_tilt_dm3      = get('m3_tilt_dm3'),
            m2_tilt_dm2_amp  = get('m2_tilt_dm2_amp'),
            m2_tilt_dm2_zero = get('m2_tilt_dm2_zero'),
            m2_roll_coupling = get('m2_roll_coupling'),
            m2_roll_zero     = get('m2_roll_zero'),
            m1_offset        = get('m1_offset'),
            m2_offset        = get('m2_offset'),
            m3_offset        = get('m3_offset'),
        )

def get_mechanical_correction_q(q: Quaternion, params: MountModelParams):
    """
    Create a quaternion for FK mechanical axis corrections applied BEFORE QUEST.

    Architecture: corrections are applied to q_base before QUEST alignment.
    QUEST is then refitted on corrected sky-pointing pairs, absorbing the
    altitude-structured component of each correction into the frame alignment.

    Sign convention:
      All corrections use degrees=-dm* where dm* is the error in degrees.
      This applies the correction in the apparent 'wrong' motor-space direction,
      which after QUEST absorption produces the correct net correction.
      This is NOT the same as post-QUEST scalar corrections (which add the error
      directly to theta values). The two architectures have opposite sign conventions.

    Constraint on which corrections can be used here:
      Only corrections whose sky-space projection is altitude-structured (varies
      with theta2/sky-alt, not theta3/roll) can work before QUEST. QUEST can absorb
      altitude-varying sky-alt shifts as a frame-tilt adjustment.
      Roll-varying sky-alt shifts (e.g. m3_tilt_dm2: f*sin(t3)) CANNOT be corrected
      here — QUEST cannot absorb them, causing double application. Set m3_tilt_dm2=0.

    M3 tilt — theta1 effect [m3_tilt_dm1]
      Fitted error: dev_q_theta1 = m3_tilt_dm1 * (1 - cos(theta3))
      dm1 = (m3_tilt_dm1/60) * (1-cos(t3)) + m1_offset/60  [degrees]
      Applied: Quaternion(m1_axis, degrees=-dm1)

    M3 tilt — theta3 effect (geometrically coupled to theta1)
      dev_q_theta3 = -cos(theta2) * dev_q_theta1  (j ≈ -1 from FK geometry)
      dm3 = -cos(t2) * dm1 + m3_offset/60  [degrees]
      Applied: Quaternion(m3_axis, degrees=-dm3)

    M2 tilt [m2_tilt_dm2_amp, m2_tilt_dm2_zero]
      Fitted error: dev_q_theta2 = m2_tilt_dm2_amp * sin(theta2 - m2_tilt_dm2_zero)
      Works before QUEST: sky-alt shift is altitude-structured (sin(t2)).
      dm2 += (m2_tilt_dm2_amp/60) * sin(t2 - m2_tilt_dm2_zero) + m2_offset/60
      Applied: Quaternion(m2_axis, degrees=-dm2)

    M3 tilt — theta2 effect [m3_tilt_dm2]
      Fitted error: dev_q_theta2 = m3_tilt_dm2 * sin(theta3)
      CANNOT be applied here (roll-varying sky-alt, QUEST cannot absorb).
      Set m3_tilt_dm2 = 0 in config. Parameter retained for documentation only.

    Correction chain order (right-to-left application):
      q_corr = q_dm3 * q_dm1 * q_dm2
      q_fixed = (q_corr * q_base).normalised
    """
    t1, t2, t3 = q_to_theta(q)

    qtheta1 = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
    m2_axis        = qtheta1.rotate([0, 1, 0])
    m3_axis        = (qtheta1 * qtheta2).rotate([1, 0, 0])
    m1_axis        = [0.0, 0.0, 1.0]
    boresight_axis = q.rotate([0, 0, -1])

    # theta1 - M3 tilt effect (around m1_axis)
    dm1 = (params.m3_tilt_dm1 / 60.0) * (1.0 - math.cos(math.radians(t3)))
    # theta3 - M3 tilt effect (geometrically coupled to theta1, around m3_axis)
    dm3 = -math.cos(math.radians(t2)) * dm1
    # theta2 - M2 tilt effect (around m2_axis)
    dm2 = (params.m2_tilt_dm2_amp / 60.0) * math.sin(math.radians(t2 - params.m2_tilt_dm2_zero))  

    # Build correction quaternions
    q_dm2 = Quaternion(axis=m2_axis,  degrees=-dm2)
    q_dm1 = Quaternion(axis=m1_axis,  degrees=-dm1)
    q_dm3 = Quaternion(axis=m3_axis,  degrees=-dm3)  

    q_corr    = q_dm3 * q_dm1 * q_dm2
    magnitude = 2 * math.degrees(math.acos(min(1.0, abs(q_corr.w))))

    return q_corr, magnitude

def apply_mechanical_corrections(q: Quaternion, params: MountModelParams):
    """
    Apply mechanical axis corrections to motor/base quaternion.
    """
    q_corr, magnitude = get_mechanical_correction_q(q, params)
    q_fixed = (q_corr * q).normalised

    return q_fixed, magnitude


def autotune_mac(sync_history: list[dict], base_params: MountModelParams, worm_q=None) -> dict:
    """
    Numerically optimise three MAC parameters to minimise QUEST residuals.

    Optimises: m2_tilt_dm2_amp, m2_tilt_dm2_zero, m3_tilt_dm1
    All other MountModelParams are held fixed at base_params values.

    Parameters
    ----------
    sync_history : list of sync entry dicts from SyncManager.sync_history (only non-deleted AzAlt entries are used)
    base_params  : current MountModelParams (frozen — not mutated)
    worm_q       : entry -> the worm feed-forward rotation at that sync point (SyncManager.entry_worm_q), so each
                   prediction is built as at runtime: MAC(raw pose) * WFF * raw pose. None: no worm correction.

    Returns
    -------
    dict with keys:
        success          : bool
        m2_tilt_dm2_amp  : float (arcmin)
        m2_tilt_dm2_zero : float (degrees)
        m3_tilt_dm1      : float (arcmin)
        rms_before       : float (arcmin)
        rms_after        : float (arcmin)
        rms_improv       : float (% improvement, negative = worse)
        r2               : float (fraction of variance explained by MAC)
        n_points         : int   (number of sync points used)
        nit              : int   (number of optimiser iterations)
        message          : str
    """

    # ── Gather valid sync pairs ───────────────────────────────────────────
    entries = [
        e for e in sync_history
        if not e.get('deleted', False)
        and e.get('a_az')  is not None
        and e.get('a_alt') is not None
    ]
    n = len(entries)
    if n < 2:
        return {'success': False, 'message': f'Need ≥2 sync points, have {n}', 'n_points': n}

    # Pre-compute observed boresight vectors — fixed, roll-independent
    v_obs_list = [np.array(azalt_to_vector(e['a_az'], e['a_alt'])) for e in entries]

    def _davenport_quest(v_preds: list) -> 'Quaternion':
        """Solve Wahba's problem via Davenport K matrix, mirroring optimize_alignQ_B2T exactly."""
        B     = sum(np.outer(vp, vo) for vp, vo in zip(v_preds, v_obs_list))  # pred row, obs col — matches production
        S     = B + B.T
        sigma = np.trace(B)
        Z     = np.array([B[1,2]-B[2,1], B[2,0]-B[0,2], B[0,1]-B[1,0]])
        K        = np.zeros((4, 4))
        K[0, 0]  = sigma
        K[0, 1:] = K[1:, 0] = Z
        K[1:,1:] = S - sigma * np.eye(3)
        eigvals, eigvecs = np.linalg.eigh(K)
        q = eigvecs[:, np.argmax(eigvals)]
        return Quaternion(q[0], q[1], q[2], q[3])

    raw_q  = [azaltroll_to_q(e['p_az'], e['p_alt'], e['p_roll']) for e in entries]
    worm_q = [worm_q(e) if worm_q is not None else Quaternion() for e in entries]

    def residuals_ss(params: MountModelParams) -> float:
        v_preds = []
        for q, w in zip(raw_q, worm_q):
            corr, _    = get_mechanical_correction_q(q, params)      # MAC from the raw pose, as at runtime
            az, alt, _ = q_to_azaltroll((corr * w * q).normalised)
            v_preds.append(np.array(azalt_to_vector(az, alt)))

        alignQ = _davenport_quest(v_preds)

        ss = 0.0
        for vp, vo in zip(v_preds, v_obs_list):
            dot = np.clip(np.dot(np.array(alignQ.rotate(vp)), vo), -1.0, 1.0)
            ss += math.acos(dot) ** 2
        return ss

    def objective(x):
        amp, zero, dm1 = x
        return residuals_ss(dataclasses.replace(base_params,
            m2_tilt_dm2_amp=amp, m2_tilt_dm2_zero=zero, m3_tilt_dm1=dm1))

    # ── Optimise ─────────────────────────────────────────────────────────
    #              m2_tilt_dm2_amp  (arcmin)    m2_tilt_dm2_zero (degrees)    m3_tilt_dm1 (arcmin)
    x0        = [ base_params.m2_tilt_dm2_amp, base_params.m2_tilt_dm2_zero, base_params.m3_tilt_dm1 ]
    bounds    = [ (-300.0,  300.0),              (-360.0,  360.0),               (-400.0,  400.0) ]
    # Nelder-Mead's default first simplex steps each parameter by 5% of its value (0.00025 when it is 0), so from
    # zero (a mount whose MAC values were cleared) it stops at once: start from steps of a typical size instead
    steps     = [ 20.0, 30.0, 40.0 ]                                   # arcmin, degrees, arcmin
    simplex   = [ x0 ] + [ [x + (s if j == i else 0.0) for j, x in enumerate(x0)] for i, s in enumerate(steps) ]
    ss_before = objective(x0)
    result    = minimize(objective, x0, method='Nelder-Mead', bounds=bounds,
                         options={'xatol': 0.01, 'fatol': 1e-6, 'maxiter': 2000, 'initial_simplex': simplex})
    ss_after  = result.fun

    rms_before = math.degrees(math.sqrt(ss_before / n)) * 60   # arcmin
    rms_after  = math.degrees(math.sqrt(ss_after  / n)) * 60   # arcmin
    r2         = 1.0 - (ss_after / ss_before) if ss_before > 0 else 0.0

    return {
        'success':           result.success,
        'm2_tilt_dm2_amp':   result.x[0],
        'm2_tilt_dm2_zero':  result.x[1],
        'm3_tilt_dm1':       result.x[2],
        'rms_before':        rms_before,
        'rms_after':         rms_after,
        'rms_improv':        (1.0 - rms_after / rms_before) * 100 if rms_before > 0 else 0.0,
        'r2':                r2,
        'n_points':          n,
        'nit':               result.nit,
        'message':           result.message,
    }


