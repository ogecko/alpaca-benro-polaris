"""
Worm gear correction analysis for the notebooks (analyse_worm_profile.ipynb, analyse_tracking.ipynb).

  profile_tests          the worm profile tests kept in a worm_profile.json (driver/control_worm.py)
  test_fit_details       one test's fit, sample by sample: the fit, each motor's worm on its own, the residual
  wff_coupling           how much each motor's angle error moves RA and Dec (arcmin per deg), as the driver splits the
                         worm feed-forward for PECLOG's wff (control_worm.WormMixin._wff_radec_arcmin)
  wff_matches_profile    is the logged worm feed-forward the profile in use? (direct check of the driver, no fit)
  worm_terms             each motor's worm (a sin + b cos per harmonic, arcsec of motor angle) in a PECLOG RA/Dec series:
                         the logged wff (returns the profile in use), the guide corrections (what the profile left), or
                         both (what the mount needed)

The worm is on the MCU's own motor angles (517 zeta = theta_raw - zeta_offset), the same every session.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from kinematics import theta_to_q, azaltroll_to_q, calc_equatorial_axes_B          # noqa: E402
from quaternion import Q as Quaternion                                               # noqa: E402
from control_worm import (PROFILE_TEST, HARMONICS, MOTORS, profile_design, fit_worm_profile, peak_deg,   # noqa: E402
                          N_NUISANCE)

WORM_THETA = 6.0


# ── worm profile tests ────────────────────────────────────────────────────────────────────────
def profile_tests(path):
    """The worm profile tests in a worm_profile.json, oldest first: dicts with created, status, result, timing and
    samples (per-motor tests of earlier versions are left out)."""
    with open(path) as f:
        d = json.load(f)
    return [e for e in d.get('calibration_history', []) if e.get('test') == PROFILE_TEST and e.get('samples')]


def test_fit_details(samples, worm_theta=WORM_THETA, harmonics=HARMONICS):
    """One test's joint fit, per kept sample and tangent axis: DataFrame with position, axis (0 horizontal, 1 up), the
    measured error, the fitted error, each motor's worm alone (projected on that axis, arcsec of sky), the rest of the
    fit (offset, drift, trend, backlash) and the residual. Also the motor angles and directions, for plotting."""
    X, y, tests = profile_design([samples], worm_theta, harmonics)
    if not tests:
        return pd.DataFrame()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    nh = 2 * len(harmonics)
    rows = []
    for i, s in enumerate(tests[0]):
        for a in range(2):
            k = 2 * i + a
            worm = [float(X[k, m * nh:(m + 1) * nh] @ beta[m * nh:(m + 1) * nh]) for m in range(3)]
            rows.append(dict(position=i + 1, axis=a, measured=y[k], fitted=float(X[k] @ beta), worm_M1=worm[0],
                             worm_M2=worm[1], worm_M3=worm[2], nuisance=float(X[k, 3 * nh:] @ beta[3 * nh:]),
                             residual=float(y[k] - X[k] @ beta),
                             **{f'zeta_M{m + 1}': s['zeta'][m] for m in range(3)},
                             **{f'dir_M{m + 1}': s['direction'][m] for m in range(3)},
                             **{f'J_M{m + 1}': float(np.asarray(s['J'])[m, a]) for m in range(3)}))
    return pd.DataFrame(rows)


# ── the worm feed-forward in PECLOG ───────────────────────────────────────────────────────────
def _qavg(qs):
    ref = np.asarray(qs[0].q, float)
    acc = np.zeros(4)
    for q in qs:
        v = np.asarray(q.q, float)
        acc += v if v @ ref >= 0 else -v
    return Quaternion(*(acc / np.linalg.norm(acc)))


def wff_coupling(df, site_lat):
    """(n, 3, 2): for each PECLOG row, how much each motor's angle error moves the pointing along the RA and Dec axes,
    in arcmin per degree -- the driver's split of the worm feed-forward (rotation per motor, decomposed on its
    equatorial axes), with the alignment taken as the rigid rotation from the motor angles (theta_raw) to the pose
    (az/alt/roll), averaged over the rows. Also returns that alignment fit's median error (arcmin)."""
    theta = df[['theta_raw_1', 'theta_raw_2', 'theta_raw_3']].to_numpy(float)
    pose = df[['az', 'alt', 'roll']].to_numpy(float)
    cam = [azaltroll_to_q(*p) for p in pose]
    mot = [theta_to_q(*th) for th in theta]
    align = _qavg([c * m.inverse for c, m in zip(cam, mot)])
    fit_err = float(np.median([(c * (align * m).inverse).normalised.degrees * 60 for c, m in zip(cam, mot)]))
    align_inv = align.inverse
    C = np.zeros((len(df), 3, 2))
    for i, (th, cq) in enumerate(zip(theta, cam)):
        A = np.column_stack(calc_equatorial_axes_B(cq, align_inv, site_lat))
        for m in range(3):
            e = np.zeros(3)
            e[m] = 1e-3
            dq = (theta_to_q(*(th + e)) * theta_to_q(*th).inverse).normalised
            rv = np.asarray(dq.axis) * dq.degrees / 1e-3
            C[i, m] = np.linalg.solve(A, rv)[:2] * 60
    return C, fit_err


def motor_angles(df):
    """(n, 3) each motor's MCU angle (deg): theta_raw - zeta_offset (the offset carried forward from the last 517)."""
    off = df[['zeta_offset_1', 'zeta_offset_2', 'zeta_offset_3']].astype(float).ffill().bfill().to_numpy()
    return df[['theta_raw_1', 'theta_raw_2', 'theta_raw_3']].to_numpy(float) - off


def predicted_wff(df, C, coef, harmonics=HARMONICS, worm_theta=WORM_THETA):
    """(n, 2) RA/Dec arcmin: the worm feed-forward a profile (coef (3, 2 x harmonics), arcsec, on MCU angles) gives."""
    phi = 2 * np.pi * motor_angles(df) / worm_theta
    e = np.zeros(phi.shape)
    for j, h in enumerate(harmonics):
        e += coef[:, 2 * j] * np.sin(h * phi) + coef[:, 2 * j + 1] * np.cos(h * phi)
    return np.einsum('nm,nmk->nk', e / 3600, C)


MIN_TURNS = 2.0                 # a motor turning fewer worm turns in the series can't be told from the drift
MIN_SEPARATION_DEG = 10.0       # M1 and M3 moving the sky within this angle (Roll ~0) trade their worms


def worm_terms(df, y, C, harmonics=HARMONICS, worm_theta=WORM_THETA, trend_degree=3):
    """Fit each motor's worm in an RA/Dec series y ((n, 2) arcmin: e.g. the logged wff, the guide corrections
    total_accum + pec_accum, or both) next to a polynomial drift per axis and an offset per piece between PEC resets
    (the totals restart there). Both harmonics by default, as the driver applies them: fitting only the 1st to a profile
    with a 2nd harmonic leaks it into the other motors. Use a series with one profile in use (not across a restart).
    Returns (DataFrame per motor and harmonic: a, b, amplitude, phase (the shift), peak (the worm phase of the peak, as
    shown to users), se -- arcsec of motor angle, the profile's
    convention -- turns (worm turns in the series), reliable (enough turns, and for M1/M3 enough separation), and the
    residual rms in arcmin)."""
    phi = 2 * np.pi * motor_angles(df) / worm_theta
    n = len(df)
    t = df['t_sec'].to_numpy(float)
    ts = (t - t[0]) / max(np.ptp(t), 1e-9)
    piece = np.cumsum(np.r_[0, np.diff(df['n'].to_numpy()) < 0])
    cols, names = [], []
    for m in range(3):
        for h in harmonics:
            for f in (np.sin, np.cos):
                cols.append(np.concatenate([f(h * phi[:, m]) * C[:, m, k] / 3600 for k in range(2)]))
            names.append((MOTORS[m], h))
    nw = len(cols)
    for k in range(2):
        for p in range(1, trend_degree + 1):
            c = np.zeros(2 * n)
            c[k * n:(k + 1) * n] = ts ** p
            cols.append(c)
        for g in range(piece.max() + 1):
            c = np.zeros(2 * n)
            c[k * n:(k + 1) * n] = piece == g
            cols.append(c)
    X = np.column_stack(cols)
    Y = np.concatenate([np.asarray(y, float)[:, 0], np.asarray(y, float)[:, 1]])
    ok = np.isfinite(Y)
    beta, *_ = np.linalg.lstsq(X[ok], Y[ok], rcond=None)
    r = Y[ok] - X[ok] @ beta
    s2 = float(r @ r) / max(ok.sum() - X.shape[1], 1)
    cov = s2 * np.linalg.pinv(X[ok].T @ X[ok])
    turns = np.ptp(motor_angles(df), axis=0) / worm_theta
    sep = separation_deg(C)
    rows = []
    for i, (M, h) in enumerate(names):
        a, b = beta[2 * i], beta[2 * i + 1]
        m = MOTORS.index(M)
        reliable = bool(turns[m] >= MIN_TURNS and (M == 'M2' or np.percentile(sep, 10) >= MIN_SEPARATION_DEG))
        rows.append(dict(motor=M, harmonic=h, a=a, b=b, amplitude=float(np.hypot(a, b)),
                         phase=float(np.degrees(np.arctan2(b, a)) % 360), peak=peak_deg(a, b, harmonic=h),
                         se=float(np.sqrt(max((cov[2 * i, 2 * i] + cov[2 * i + 1, 2 * i + 1]) / 2, 0))),
                         turns=round(float(turns[m]), 1), reliable=reliable))
    return pd.DataFrame(rows), float(np.sqrt(s2))


def separation_deg(C):
    """(n,) the angle (deg) between the directions M1 and M3 move RA/Dec at each row (C from wff_coupling)."""
    c = np.abs(np.sum(C[:, 0] * C[:, 2], axis=1)) / np.maximum(np.linalg.norm(C[:, 0], axis=1) *
                                                             np.linalg.norm(C[:, 2], axis=1), 1e-12)
    return np.degrees(np.arccos(np.clip(c, 0.0, 1.0)))


def wff_matches_profile(df, C, coef, harmonics=HARMONICS, worm_theta=WORM_THETA):
    """Is the logged worm feed-forward (wff) the profile `coef` ((3, 2 x harmonics) arcsec, on MCU angles)? The direct
    check of the driver, no fit: {'corr': per axis (min), 'rms_diff_arcsec': rms of logged - predicted}."""
    pred = predicted_wff(df, C, np.asarray(coef, float), harmonics, worm_theta)
    wff = df[['wff_1', 'wff_2']].to_numpy(float)
    corr = min(float(np.corrcoef(wff[:, k], pred[:, k])[0, 1]) for k in range(2))
    return {'corr': corr, 'rms_diff_arcsec': float(np.sqrt(np.mean((wff - pred) ** 2)) * 60)}
