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
  worm_gains             per motor, how much of its profile's worm the mount really had (gain and phase against the
                         profile), from the drift rates with the slow drift taken out

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


def _centred_slope(t, y, half, piece):
    """Least-squares slope of y over t within +-half seconds of each row, inside its piece (NaN with under 5 rows)."""
    out = np.full(len(t), np.nan)
    for g in np.unique(piece):
        k = np.flatnonzero(piece == g)
        tt, yy = t[k], y[k]
        c = lambda v: np.r_[0.0, np.cumsum(v)]
        S1, St, Sy, Stt, Sty = c(np.ones_like(tt)), c(tt), c(yy), c(tt * tt), c(tt * yy)
        lo, hi = np.searchsorted(tt, tt - half, 'left'), np.searchsorted(tt, tt + half, 'right')
        n, st, sy, stt, sty = (S[hi] - S[lo] for S in (S1, St, Sy, Stt, Sty))
        den = n * stt - st * st
        ok = (n >= 5) & (den > 0)
        out[k[ok]] = (n * sty - st * sy)[ok] / den[ok]
    return out


def _highpass(t, y, window):
    """y minus its centred running mean over window seconds (NaNs left out of the mean)."""
    ok = np.isfinite(y)
    c = lambda v: np.r_[0.0, np.cumsum(v)]
    s, n = c(np.where(ok, y, 0.0)), c(ok.astype(float))
    lo, hi = np.searchsorted(t, t - window / 2, 'left'), np.searchsorted(t, t + window / 2, 'right')
    return y - (s[hi] - s[lo]) / np.maximum(n[hi] - n[lo], 1)


def worm_gains(df, C, coef, y, harmonics=HARMONICS, worm_theta=WORM_THETA, rate_half_window_s=60.0,
               highpass_s=1800.0):
    """
    Per motor: how much of its profile's worm the mount really had. y ((n, 2) arcmin RA/Dec) is what all the
    corrections removed -- the guide corrections plus the worm feed-forward (total_accum + pec_accum + wff, section 7's
    "needed"). Its drift rate (a +-rate_half_window_s slope, inside each piece between PEC resets) is fitted, RA and
    Dec together, to each motor's profile worm rate (predicted_wff with that motor only) and to the same worm advanced
    90 deg in its own phase, after taking the slow drift out of every series (a highpass_s running mean).
    gain 1 and quadrature 0: the profile is exact; ratio = true / profile amplitude, phase_deg = how far the true worm
    leads the profile (in each harmonic's own phase). se is approximate (the rows' slopes overlap; scaled for it).
    Returns (DataFrame per motor: gain, quadrature, ratio, phase_deg, se, worm_rate (the motor's profile worm rate,
    std "/min), turns, reliable), and the std ("/min) of: left_now (what the profile left for the guider and PEC),
    left_fitted (had it the fitted gains), worm_profile and worm_fitted (the worm rates).
    """
    coef = np.asarray(coef, float)
    t = df['t_sec'].to_numpy(float)
    piece = np.cumsum(np.r_[0, np.diff(df['n'].to_numpy()) < 0])
    quad = coef.copy()                                   # each harmonic advanced 90 deg: a sin + b cos -> -b sin + a cos
    for j in range(len(harmonics)):
        quad[:, 2 * j], quad[:, 2 * j + 1] = -coef[:, 2 * j + 1], coef[:, 2 * j]
    rate = lambda v: _highpass(t, _centred_slope(t, v, rate_half_window_s, piece) * 3600, highpass_s)   # "/min
    y = np.asarray(y, float)
    Y = np.concatenate([rate(y[:, k]) for k in range(2)])
    cols = []
    for c in (coef, quad):
        for m in range(3):
            one = np.zeros_like(c)
            one[m] = c[m]
            w = predicted_wff(df, C, one, harmonics, worm_theta)
            cols.append(np.concatenate([rate(w[:, k]) for k in range(2)]))
    X = np.column_stack(cols)
    ok = np.isfinite(Y) & np.isfinite(X).all(axis=1)
    X, Y = X[ok], Y[ok]
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    r = Y - X @ beta
    s2 = float(r @ r) / max(len(Y) - X.shape[1], 1)
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0
    se = np.sqrt(np.maximum(np.diag(s2 * np.linalg.pinv(X.T @ X)), 0)) * np.sqrt(max(2 * rate_half_window_s / dt, 1.0))
    turns = np.ptp(motor_angles(df), axis=0) / worm_theta
    sep = separation_deg(C)
    rows = []
    for m in range(3):
        g, q = beta[m], beta[3 + m]
        rows.append(dict(motor=MOTORS[m], gain=float(g), quadrature=float(q), ratio=float(np.hypot(g, q)),
                         phase_deg=float(np.degrees(np.arctan2(q, g))), se=float(max(se[m], se[3 + m])),
                         worm_rate=float(np.std(X[:, m])), turns=round(float(turns[m]), 1),
                         reliable=bool(turns[m] >= MIN_TURNS and (m == 1 or np.percentile(sep, 10) >= MIN_SEPARATION_DEG))))
    ideal = np.r_[1.0, 1.0, 1.0, 0.0, 0.0, 0.0]
    summary = {'left_now': float(np.std(Y - X @ ideal)), 'left_fitted': float(np.std(r)),
               'worm_profile': float(np.std(X @ ideal)), 'worm_fitted': float(np.std(X @ beta))}
    return pd.DataFrame(rows), summary


# ── the worm feed-forward rebuilt between PECLOG rows ─────────────────────────────────────────────
# PECLOG is written at each guide update: dense while pulse guiding, but once per plate-solve sync while only sync
# guiding, so its logged wff misses the worm between syncs. The feed-forward runs every control tick from each
# motor's MCU angle; while tracking those angles change smoothly, so the feed-forward can be rebuilt on a fine grid
# from the angles interpolated between rows and the profile the session ran with (its WORMPROFILE log line).

def logged_worm_profiles(log_paths):
    """[(timestamp, profile dict)] from the WORMPROFILE {...} lines of the driver logs (the profile the feed-forward
    ran with, from each time it was read: start, Approve/Reject, a lens change), oldest first."""
    import ast
    out = []
    for path in log_paths:
        with open(path, errors='replace') as f:
            for line in f:
                k = line.find('WORMPROFILE {')
                if k < 0:
                    continue
                try:
                    prof = ast.literal_eval(line[k + len('WORMPROFILE '):].strip())
                except (ValueError, SyntaxError):
                    continue
                out.append((pd.Timestamp(line[:23]), prof))
    return sorted(out, key=lambda p: p[0])


def _profile_coef(prof, direction):
    """(3, 2 x len(harmonics)) arcsec: a logged profile's coefficients per motor, its forward / reverse ones for a
    motor split by direction (direction: per motor +1 / -1 / 0)."""
    coef = np.array([prof['motors'][M] for M in MOTORS], float)
    for m, M in enumerate(MOTORS):
        split = (prof.get('direction_motors') or {}).get(M)
        if split and direction[m]:
            coef[m] = split['forward' if direction[m] > 0 else 'reverse']
    return coef


def rebuilt_wff(df, site_lat, profiles, step_s=10.0, max_gap_s=900.0, max_rate_dps=0.02):
    """The worm feed-forward (RA/Dec arcmin) on a step_s grid between PECLOG rows: each motor's MCU angle and the pose
    interpolated linearly between rows no more than max_gap_s apart (a longer gap is left out, and so is one where a
    motor turned faster than max_rate_dps: a goto or jog, not tracking -- ~5x the fastest sidereal motor rate), and the profile in use then (profiles: logged_worm_profiles), forward or reverse by each motor's direction
    of travel. Returns (DataFrame timestamp, wff_1, wff_2, rebuilt at the rows' own times as a check: the rms of
    rebuilt - logged in arcsec, or None)."""
    cols = ['theta_raw_1', 'theta_raw_2', 'theta_raw_3', 'az', 'alt', 'roll']
    d = df.dropna(subset=cols).sort_values('timestamp').reset_index(drop=True)
    if len(d) < 2 or not profiles:
        return pd.DataFrame(columns=['timestamp', 'wff_1', 'wff_2']), None
    off = d[['zeta_offset_1', 'zeta_offset_2', 'zeta_offset_3']].astype(float).ffill().bfill() \
        if 'zeta_offset_1' in d else pd.DataFrame(np.zeros((len(d), 3)))
    t = (d['timestamp'] - d['timestamp'].iloc[0]).dt.total_seconds().to_numpy()
    unwrap = {c: np.degrees(np.unwrap(np.radians(d[c].to_numpy(float)))) for c in ('theta_raw_1', 'theta_raw_3', 'az')}
    vals = {c: unwrap.get(c, d[c].to_numpy(float)) for c in cols}
    rows = []
    for i in range(len(d) - 1):
        dt = t[i + 1] - t[i]
        if dt <= 0 or dt > max_gap_s:
            continue
        jump = max(abs(vals[c][i + 1] - vals[c][i]) for c in ('theta_raw_1', 'theta_raw_2', 'theta_raw_3'))
        if jump > max_rate_dps * dt + 0.05:             # a goto or jog between the rows: not tracking
            continue
        for tt in np.arange(t[i], t[i + 1], step_s):
            f = (tt - t[i]) / dt
            r = {c: vals[c][i] + f * (vals[c][i + 1] - vals[c][i]) for c in cols}
            r.update({f'zeta_offset_{m + 1}': off.iloc[i, m] for m in range(3)})
            r['t'] = tt
            r['dir'] = [int(np.sign(vals[c][i + 1] - vals[c][i])) for c in ('theta_raw_1', 'theta_raw_2', 'theta_raw_3')]
            rows.append(r)
    if not rows:
        return pd.DataFrame(columns=['timestamp', 'wff_1', 'wff_2']), None
    g = pd.DataFrame(rows)
    g['timestamp'] = d['timestamp'].iloc[0] + pd.to_timedelta(g['t'], unit='s')
    for c in ('theta_raw_1', 'theta_raw_3', 'az'):
        g[c] = g[c] % 360
    C, _ = wff_coupling(g, site_lat)
    ang = motor_angles(g)
    times = [p[0] for p in profiles]
    out = np.zeros((len(g), 2))
    for k in range(len(g)):
        j = np.searchsorted(times, g['timestamp'].iloc[k], side='right') - 1
        prof = profiles[max(j, 0)][1]
        coef = _profile_coef(prof, g['dir'].iloc[k])
        harmonics = prof.get('harmonics', HARMONICS)
        phi = 2 * np.pi * ang[k] / float(prof.get('worm_theta', WORM_THETA))
        e = np.zeros(3)
        for h_i, h in enumerate(harmonics):
            e += coef[:, 2 * h_i] * np.sin(h * phi) + coef[:, 2 * h_i + 1] * np.cos(h * phi)
        out[k] = np.einsum('m,mk->k', e / 3600, C[k])
    res = pd.DataFrame({'timestamp': g['timestamp'], 'wff_1': out[:, 0], 'wff_2': out[:, 1]})
    check = None
    if 'wff_1' in d:
        logged = d[['timestamp', 'wff_1', 'wff_2']].rename(columns={'wff_1': 'l1', 'wff_2': 'l2'})
        logged['timestamp'] = logged['timestamp'].astype('datetime64[ns]')
        logged[['l1', 'l2']] = logged[['l1', 'l2']].astype(float)
        left = res.sort_values('timestamp').copy()
        left['timestamp'] = left['timestamp'].astype('datetime64[ns]')
        near = pd.merge_asof(left, logged.sort_values('timestamp'), on='timestamp', direction='nearest',
                             tolerance=pd.Timedelta(seconds=step_s / 2))
        ok = near.dropna(subset=['l1'])
        if len(ok):
            check = float(np.sqrt(np.mean((ok[['wff_1', 'wff_2']].to_numpy() - ok[['l1', 'l2']].to_numpy()) ** 2)) * 60)
    return res, check
