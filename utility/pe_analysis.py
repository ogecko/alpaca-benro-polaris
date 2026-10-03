"""
Per-motor periodic-error analysis over the extracted segment datasets (utility/extract_segments.py).

The question: does the mount's periodic drift repeat with each MOTOR's angle (a worm on that motor,
period THETA degrees of its rotation), or with time? On an alt-az-roll mount each motor turns at a
pose-dependent rate, so a worm gives a different time period at every pose while a time-based source
does not.

time_scan()     -- the same at one fixed time period in every segment: the time-based hypothesis.
                   Compare the two on the same data; the pooled angle scan alone can show peaks for a
                   time-based signal too, because each segment hits some THETA = T x rate.
theta_scan()    -- for each motor and candidate THETA, the mean Lomb-Scargle power (RA and Dec, trend
                   removed) at the period that worm would give in each segment: THETA / motor rate.
                   A worm on motor i shows as one THETA where power peaks across segments whose time
                   periods all differ. exclude_session gives leave-one-session-out estimates.
forecast_skill() -- fit each candidate model on the first part of a segment and score how well it
                   predicts the rest (what PEC has to do): linear trend only, the current time-based
                   shape (34 + 17 min), and per-motor worm terms (1 or 2 harmonics) for each motor
                   turning at least min_rate deg/hr.

Theta-space PEC (worm profile on top of EMA, scored like analyse_pec_catalog):
fit_worm()              -- drift as sin/cos of each motor's worm phase, fitted on 1-min drift increments.
replay_worm_pec_rate()  -- PEC rate with a fixed profile: EMA on the drift minus the profile + the profile's rate.
causal_worm_pec_rate()  -- the same with the profile learnt only from the segment so far.
worm_benchmark()        -- hindsight / same-session / other-sessions / live tiers vs EMA; relative_to() pools them.
worm_angle_control()    -- hindsight gain by assumed worm angle: a real worm dips at its angle.
"""
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from analyse_helpers import lombscargle_periodogram

MOTORS = ('M1', 'M2', 'M3')
DUPLICATES = ('07_20_master', 'tarantula1b')     # same captures as 07_20_h2 / tarantula1


@dataclass
class Segment:
    name: str
    session: str
    t: np.ndarray          # s from segment start
    ra: np.ndarray         # drift, arcsec (driver correction convention)
    dec: np.ndarray
    theta: np.ndarray      # (n, 3) motor angles, deg, unwrapped
    _pg: dict = field(default_factory=dict, repr=False)

    @property
    def rates(self):
        """|mean rate| of each motor, deg/hr."""
        return np.abs(np.polyfit(self.t / 3600, self.theta, 1)[0])

    @property
    def hours(self):
        return float(self.t[-1] - self.t[0]) / 3600

    def periodograms(self, max_points=1200):
        """Lomb-Scargle of RA and Dec (quadratic trend removed), binned to <= max_points; cached."""
        if not self._pg:
            n = min(len(self.t), max_points)
            edges = np.linspace(self.t[0], self.t[-1], n + 1)
            b = np.clip(np.digitize(self.t, edges) - 1, 0, n - 1)
            g = pd.DataFrame({'b': b, 't': self.t, 'ra': self.ra, 'dec': self.dec}).groupby('b').mean()
            dt = float(np.median(np.diff(g['t'])))
            pmin, pmax = max(5 * 60, 4 * dt), min(90 * 60, (self.t[-1] - self.t[0]) / 2)
            self._pg['range'] = (pmin, pmax)
            for ax in ('ra', 'dec'):
                y = g[ax].values - np.polyval(np.polyfit(g['t'], g[ax].values, 2), g['t'])
                self._pg[ax] = lombscargle_periodogram(g['t'].values, y, min_period=pmin, max_period=pmax,
                                                       detrend=False, n_periods=3000)
        return self._pg


SETTLE_S = 120.0                 # s dropped after a rapid-solve burst (about one normal solve; see _clean_parts):
                                 # the drift rate right after a burst is no higher than later (2026-10-03 archive)


def _clean_parts(t, burst_interval_s=30.0, burst_min_run=3, settle_s=SETTLE_S):
    """Index arrays of the usable parts of a segment's samples. Sync-guided segments (median interval >= 10 s) often
    open with a burst of plate solves a few seconds apart, to seed PEC. Each sync re-anchors the model before the
    mount has carried out PEC's correction, so PECLOG's pec_accum there never happened; extract_segments now leaves it
    out (PHANTOM_GAP_S), so bursts are usable and kept by default -- drop_bursts=True removes them. Samples
    in a run of >= burst_min_run intervals under burst_interval_s (and under half the segment's median interval), and
    those within settle_s after it, are dropped;
    a burst inside a segment splits it, as the running total jumps across it. Pulse-guided segments are dense by
    nature and kept whole."""
    t = np.asarray(t, float)
    n = len(t)
    if n < 3 or np.median(np.diff(t)) < 10:
        return [np.arange(n)]
    fast = np.diff(t) < min(burst_interval_s, 0.5 * np.median(np.diff(t)))     # fast for this segment's cadence
    bad = np.zeros(n, bool)
    k = 0
    while k < len(fast):
        if not fast[k]:
            k += 1
            continue
        j = k
        while j < len(fast) and fast[j]:
            j += 1
        if j - k >= burst_min_run:                      # samples k..j are the burst
            bad[k:j + 1] = True
            bad[(t > t[j]) & (t < t[j] + settle_s)] = True
        k = j
    parts, cur = [], []
    for i in range(n):
        if bad[i]:
            if cur:
                parts.append(np.array(cur))
            cur = []
        else:
            cur.append(i)
    if cur:
        parts.append(np.array(cur))
    return parts


def load_segments(seg_dir, min_minutes=60, exclude=DUPLICATES, drop_bursts=False, burst_interval_s=30.0,
                  burst_min_run=3, settle_s=SETTLE_S, dedupe=True):
    """Segments (>= min_minutes) from the extracted datasets. drop_bursts: remove rapid plate-solve bursts and their
    settling (_clean_parts; off by default since extract_segments drops their phantom PEC correction), splitting a segment at a burst inside it (names '#k.1', '#k.2', ...). dedupe: load a
    capture archived under two names once (identical drift and timing)."""
    idx = pd.read_csv(os.path.join(seg_dir, 'index.csv'))
    out, seen = [], set()
    for _, r in idx.iterrows():
        if any(x in r['session'] for x in exclude):
            continue
        d = pd.read_csv(os.path.join(seg_dir, r['file']))
        if d[['theta1', 'theta2', 'theta3']].isna().all().any() or len(d) < 20:
            continue
        t = d['t_sec'].values.astype(float)
        ra, dec = d['drift_ra_arcsec'].values, d['drift_dec_arcsec'].values
        theta = d[['theta1', 'theta2', 'theta3']].values
        if dedupe:
            key = (len(t), round(float(t[-1] - t[0]), 3), round(float(np.nansum(ra)), 3), round(float(np.nansum(dec)), 3))
            if key in seen:
                continue
            seen.add(key)
        parts = _clean_parts(t, burst_interval_s, burst_min_run, settle_s) if drop_bursts else [np.arange(len(t))]
        parts = [p for p in parts if len(p) >= 20 and t[p[-1]] - t[p[0]] >= min_minutes * 60]
        base = f"{r['session']}#{int(r['segment'])}"
        for i, p in enumerate(parts):
            out.append(Segment(name=base if len(parts) == 1 else f'{base}.{i + 1}', session=r['session'],
                               t=t[p] - t[p[0]], ra=ra[p], dec=dec[p], theta=theta[p]))
    return out


def theta_scan(segs, thetas, exclude_session=None, min_rate=5.0):
    """Mean power at the worm-predicted period per motor and THETA (+ n segment-axes in range)."""
    use = [s for s in segs if s.session != exclude_session]
    rows = []
    for th in thetas:
        row = {'theta': th}
        for i, m in enumerate(MOTORS):
            v = []
            for s in use:
                r = s.rates[i]
                if r < min_rate:
                    continue
                pg = s.periodograms()
                pmin, pmax = pg['range']
                T = th / r * 3600
                if pmin <= T <= pmax:
                    for ax in ('ra', 'dec'):
                        per, pw = pg[ax]
                        v.append(np.interp(T, per, pw))
            row[m] = float(np.mean(v)) if v else np.nan
            row[f'n_{m}'] = len(v)
        rows.append(row)
    df = pd.DataFrame(rows).set_index('theta')
    df.attrs['n_segments'] = len(use)
    return df


def time_scan(segs, periods_s):
    """Mean power (RA and Dec) at the same fixed time period in every segment -- the time-based hypothesis."""
    rows = []
    for T in periods_s:
        v = []
        for s in segs:
            pg = s.periodograms()
            pmin, pmax = pg['range']
            if pmin <= T <= pmax:
                for ax in ('ra', 'dec'):
                    per, pw = pg[ax]
                    v.append(np.interp(T, per, pw))
        rows.append({'period_s': T, 'power': float(np.mean(v)) if v else np.nan, 'n': len(v)})
    return pd.DataFrame(rows).set_index('period_s')


def best_theta(scan):
    return {m: float(scan[m].idxmax()) for m in MOTORS if scan[m].notna().any()}


def _design(t, theta, kind, thetas, fast):
    cols = [np.ones_like(t), t / 3600]
    if kind == 'time_34_17':
        for T in (34 * 60, 17 * 60):
            cols += [np.sin(2 * np.pi * t / T), np.cos(2 * np.pi * t / T)]
    elif kind in ('worm', 'worm_h2'):
        for i in fast:
            for h in ((1,) if kind == 'worm' else (1, 2)):
                a = 2 * np.pi * h * theta[:, i] / thetas[MOTORS[i]]
                cols += [np.sin(a), np.cos(a)]
    return np.column_stack(cols)


def forecast_skill(seg, thetas, train_frac=0.6, min_rate=5.0):
    """Hold-out RMS (arcsec, RA and Dec pooled) of each model fitted on the first train_frac of the segment."""
    t = seg.t - seg.t[0]
    fast = [i for i in range(3) if seg.rates[i] >= min_rate]
    cut = t[-1] * train_frac
    tr, te = t <= cut, t > cut
    out = {'segment': seg.name, 'hours': round(seg.hours, 2), 'fast_motors': [MOTORS[i] for i in fast]}
    for kind in ('trend', 'time_34_17', 'worm', 'worm_h2'):
        X = _design(t, seg.theta, kind, thetas, fast)
        sq = []
        for y in (seg.ra, seg.dec):
            c, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
            sq.append((y[te] - X[te] @ c) ** 2)
        out[kind] = float(np.sqrt(np.mean(np.concatenate(sq))))
    return out


def rolling_forecast(seg, thetas, window_s=40 * 60, horizon_s=10 * 60, step_s=10 * 60, min_rate=5.0):
    """
    PEC's actual job: repeatedly fit the last window_s of drift and predict the next horizon_s.
    Returns the RMS forecast error (arcsec, RA and Dec pooled, error relative to the drift at the
    forecast origin) of each model over every window in the segment.
    """
    t = seg.t - seg.t[0]
    fast = [i for i in range(3) if seg.rates[i] >= min_rate]
    out = {'segment': seg.name, 'hours': round(seg.hours, 2), 'fast_motors': [MOTORS[i] for i in fast]}
    errs = {k: [] for k in ('trend', 'time_34_17', 'worm', 'worm_h2')}
    n = 0
    for t0 in np.arange(window_s, t[-1] - horizon_s + 1e-9, step_s):
        tr = (t > t0 - window_s) & (t <= t0)
        te = (t > t0) & (t <= t0 + horizon_s)
        if tr.sum() < 10 or te.sum() < 2:
            continue
        n += 1
        for kind in errs:
            X = _design(t, seg.theta, kind, thetas, fast)
            for y in (seg.ra, seg.dec):
                c, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
                errs[kind].append((y[te] - X[te] @ c) ** 2)
    for kind, e in errs.items():
        out[kind] = float(np.sqrt(np.mean(np.concatenate(e)))) if e else np.nan
    out['n_windows'] = n
    return out


# ── PEC rate benchmark ───────────────────────────────────────────────────────────────────
# PEC applies a RATE continuously and the guider removes what is left at each correction. So a PEC model
# is scored on (1) how well its causal rate estimate tracks the actual drift rate (a centred local slope
# of the drift, only computable afterwards) and (2) the drift left for the guider per correction interval,
# y(t + dt) - y(t) - rate(t) * dt, for realistic guide intervals. The model is the driver's own PecAxis
# replayed causally on the drift series (total_accum: the mount's drift with PEC's effect removed).

@dataclass
class PecModel:
    name: str
    mode: str = 'ema'            # 'ema' or 'rls' (the driver's PecAxis), or 'dema' (benchmark only, see below)
    n_harmonics: int = 0
    tau_s: float = 1260.0
    T: float = 2040.0
    k: float = 1.0               # 'dema' lag compensation: rate = e1 + k * (e1 - e2); 0 = plain EMA, 1 = DEMA


def true_rate(t, y, half_window_s=300.0):
    """Actual drift rate (arcsec/min): slope of a local line over t +/- half_window_s; NaN near the ends."""
    out = np.full(len(t), np.nan)
    lo = np.searchsorted(t, t - half_window_s, side='left')
    hi = np.searchsorted(t, t + half_window_s, side='right')
    for k in range(len(t)):
        if t[k] - half_window_s < t[0] or t[k] + half_window_s > t[-1] or hi[k] - lo[k] < 3:
            continue
        tt, yy = t[lo[k]:hi[k]], y[lo[k]:hi[k]]
        out[k] = np.polyfit(tt - t[k], yy, 1)[0] * 60
    return out


def _replay_dema(t, y, tau_s, k):
    """Lag-compensated EMA of the observed rate: e1 = EMA(rate), e2 = EMA(e1), rate = e1 + k (e1 - e2).
    Same per-sample smoothing as PecAxis's EMA mode (alpha = 1 - exp(-dt / tau)); with a steadily changing
    rate e1 lags by ~tau and e2 by ~2 tau, so k = 1 cancels the lag (at the cost of more noise and overshoot)."""
    out = np.zeros(len(t))
    e1 = e2 = 0.0
    for i in range(2, len(t)):                  # like PecAxis: the first ingest only sets the reference point
        dt = t[i] - t[i - 1]
        if dt <= 0:
            out[i] = out[i - 1]
            continue
        alpha = 1.0 - np.exp(-dt / tau_s)
        obs = (y[i] - y[i - 1]) / dt * 60
        e1 += alpha * (obs - e1)
        e2 += alpha * (e1 - e2)
        out[i] = e1 + k * (e1 - e2)
    return out


def replay_pec_rate(t, y, model, var_alpha=0.05, sse_alpha=0.15):
    """Rate (arcsec/min) the driver's PecAxis would apply after ingesting each sample of drift y (arcsec)."""
    if model.mode == 'dema':
        return _replay_dema(np.asarray(t, float), np.asarray(y, float), model.tau_s, model.k)
    from control_pec import PecAxis, PecMode
    ax = PecAxis(T=model.T, n_harmonics=model.n_harmonics, mode=PecMode(model.mode), tau=model.tau_s, min_dt=0.05)
    ax.reset_seed(y[0] / 3600)
    out = np.zeros(len(t))
    for k in range(1, len(t)):
        ax.ingest_accum(y[k] / 3600, t[k], var_alpha, sse_alpha)
        out[k] = ax.predicted_rate(t[k]) * 3600 * 60
    return out


def rate_scores(t, y, rates, guide_intervals_s=(30, 120, 300), ref_half_window_s=300.0, warmup_s=600.0):
    """{'rate_rms': {name: arcsec/min}, 'guide_rms': {dt: {name: arcsec}}}, each with a 'no_pec' baseline."""
    t = np.asarray(t, float) - t[0]
    rt = true_rate(t, y, ref_half_window_s)
    m = (t >= warmup_s) & ~np.isnan(rt)
    out = {'rate_rms': {'no_pec': float(np.sqrt(np.mean(rt[m] ** 2)))}, 'guide_rms': {}}
    for name, r in rates.items():
        out['rate_rms'][name] = float(np.sqrt(np.mean((r[m] - rt[m]) ** 2)))
    for dt in guide_intervals_s:
        g = (t >= warmup_s) & (t + dt <= t[-1])
        step = np.interp(t[g] + dt, t, y) - y[g]
        res = {'no_pec': float(np.sqrt(np.mean(step ** 2)))}
        for name, r in rates.items():
            res[name] = float(np.sqrt(np.mean((step - r[g] * dt / 60) ** 2)))
        out['guide_rms'][dt] = res
    return out


def benchmark_segments(segs, models, guide_intervals_s=(30, 120, 300), ref_half_windows_s=(150, 300),
                       thin_s=5.0, pulse_dt_s=10.0):
    """Long DataFrame (seg, kind, axis, metric, model, value) of rate_scores for every segment, axis and model.
    kind: 'pulse' if the drift is sampled faster than pulse_dt_s (pulse-guided PECLOG/PHD2), else 'sync'.
    Dense segments are thinned to one sample per thin_s (PecAxis uses each sample's own dt)."""
    rows = []
    for s in segs:
        t = s.t - s.t[0]
        keep = np.r_[True, np.diff(np.floor(t / thin_s)) > 0] if thin_s else np.ones(len(t), bool)
        t = t[keep]
        kind = 'pulse' if np.median(np.diff(t)) < pulse_dt_s else 'sync'
        for axis, y in (('ra', s.ra[keep]), ('dec', s.dec[keep])):
            rates = {m.name: replay_pec_rate(t, y, m) for m in models}
            for i, hw in enumerate(ref_half_windows_s):
                sc = rate_scores(t, y, rates, guide_intervals_s=guide_intervals_s, ref_half_window_s=hw)
                for name, v in sc['rate_rms'].items():
                    rows.append(dict(seg=s.name, kind=kind, axis=axis, metric=f'rate (ref +-{hw / 60:.1f} min)', model=name, value=v))
                if i == len(ref_half_windows_s) - 1:
                    for dt, d in sc['guide_rms'].items():
                        for name, v in d.items():
                            rows.append(dict(seg=s.name, kind=kind, axis=axis, metric=f'guide residual {dt}s', model=name, value=v))
    return pd.DataFrame(rows)


def pooled_relative(df):
    """Pooled RMS of each model relative to no PEC, per metric (rows: model, columns: metric)."""
    out = {}
    for metric, g in df.groupby('metric'):
        base = g[g['model'] == 'no_pec'].set_index(['seg', 'axis'])['value']
        out[metric] = {m: float(np.sqrt((gg.set_index(['seg', 'axis'])['value'] ** 2).sum() /
                                        (base.loc[gg.set_index(['seg', 'axis']).index] ** 2).sum()))
                       for m, gg in g.groupby('model')}
    return pd.DataFrame(out)


# ── theta-space PEC: a worm profile per motor, on top of EMA ─────────────────────────────────────
# A worm error is an error in one motor's output angle, e_i(theta_i) = sum over harmonics h of a sin + b cos of
# that motor's worm phase (360 deg per WORM_THETA of rotation). It is a small rotation about that motor's axis;
# split along the celestial pole, the Dec axis and the boresight (as the driver's equatorial axes), the first
# two parts are what the driver logs as RA and Dec correction (the boresight part is field rotation, which no
# guider sees). So RA/Dec drift = sky_weights(pose) . e(theta): the profile lives in motor space and holds at
# any pose. PEC with a profile: EMA follows the drift with the profile removed, and the profile adds its own
# rate from the current motor angles.

WORM_THETA = 360 / 60            # deg of output rotation per worm turn: 60-tooth wheel, 960:1 = 16 x 60 (the
                                 # MCU's ratio; the tooth count is not known -- see worm_angle_control)


def _rodrigues(axis, angle, v):
    """Rotate vectors v (n, 3) about unit axes (n, 3) by angles (n,) in radians (right-hand rule)."""
    c, s = np.cos(angle)[:, None], np.sin(angle)[:, None]
    return v * c + np.cross(axis, v) * s + axis * np.sum(axis * v, axis=1, keepdims=True) * (1 - c)


def sky_weights(theta, lat):
    """(n, 2, 3): arcsec of RA (row 0) and Dec (row 1) correction per arcsec of error in each motor's angle,
    at each pose (motor angles, deg) and site latitude. Same maths as kinematics.theta_to_jacobian and
    calc_equatorial_axes_B with an ideal (level, north-aligned) base."""
    return sky_matrix(theta, lat)[:, :2, :]


def sky_matrix(theta, lat):
    """(n, 3, 3): rotation about the RA (pole), Dec and boresight (field rotation) axes per unit of each motor's angle
    -- rows RA, Dec, field rotation; columns M1-M3. sky_weights is its first two rows."""
    th = np.radians(np.atleast_2d(np.asarray(theta, float)))
    n = len(th)
    z, y, x = (np.tile(e, (n, 1)) for e in np.eye(3)[::-1])
    a2 = _rodrigues(z, -th[:, 0] + np.pi / 2, y)
    a3 = _rodrigues(z, -th[:, 0] + np.pi / 2, _rodrigues(y, -th[:, 1] - np.pi / 2, x))
    J = -np.stack([z, a2, a3], axis=2)
    v = _rodrigues(z, -th[:, 0] + np.pi / 2, _rodrigues(y, -th[:, 1] - np.pi / 2, -z))
    v = _rodrigues(a3, -th[:, 2], v)
    lr = np.radians(lat)
    p = np.tile([0.0, np.cos(lr), np.sin(lr)], (n, 1))
    d = np.cross(p, v)
    nd = np.linalg.norm(d, axis=1, keepdims=True)
    d = np.where(nd > 1e-6, d / np.maximum(nd, 1e-12), [1.0, 0.0, 0.0])
    d *= np.where(np.sum(np.cross(d, v) * p, axis=1) < 0, -1.0, 1.0)[:, None]
    return np.linalg.solve(np.stack([p, d, v], axis=2), J)


def remove_corrections(theta, ra, dec, lat):
    """Motor angles from a pose-derived theta (PECLOG/SGLOG az/alt/roll through the inverse kinematics), with the
    corrections accumulated since the first sample taken back out. That pose is the driver's present value: the motor
    pose rotated by every guide and PEC correction (RA/Dec drift totals ra, dec in arcsec), which shifts the angles by
    up to ~1 deg over a night. A constant offset (the corrections before the first sample) is left in."""
    theta = np.atleast_2d(np.asarray(theta, float))
    c = np.column_stack([np.asarray(ra, float) - ra[0], np.asarray(dec, float) - dec[0], np.zeros(len(theta))]) / 3600.0
    return theta - np.linalg.solve(sky_matrix(theta, lat), c[:, :, None])[:, :, 0]


def motor_errors(ra, dec, theta, lat, min_theta2=5.0):
    """(n, 3) per-motor angle error (arcsec) that explains each RA/Dec drift sample with the least total motor
    error (field rotation is unobserved, so the split is a choice). NaN where |theta2| < min_theta2: M1 and M3
    are then nearly coaxial and their split is arbitrary."""
    W = sky_weights(theta, lat)
    r = np.column_stack([ra, dec])
    e = np.einsum('nji,nj->ni', W, np.linalg.solve(W @ np.transpose(W, (0, 2, 1)), r[:, :, None])[:, :, 0])
    e[np.abs(np.atleast_2d(theta)[:, 1]) < min_theta2] = np.nan
    return e


def detrend_per_minute(t, y, deg=2, grid_s=60.0):
    """y minus a polynomial trend fitted on a grid_s grid (each minute counts once), so a burst of dense samples
    can't pull the trend the way a per-sample fit would."""
    t, y = np.asarray(t, float), np.asarray(y, float)
    tg = np.arange(t[0], t[-1] + grid_s / 2, grid_s)
    if len(tg) <= deg:
        tg = t
    return y - np.polyval(np.polyfit(tg, np.interp(tg, t, y), deg), t)


def partial_motor_errors(t, ra, dec, theta, lat, profile, min_theta2=5.0, trend_degree=2):
    """(n, 3) per-motor partial residuals (arcsec): each motor's fitted profile + what the joint fit leaves
    unexplained (RA/Dec drift minus the whole mapped profile, quadratic trend removed, split with
    motor_errors). Unlike motor_errors on the raw drift, the other motors' fitted cycles don't leak in."""
    t = np.asarray(t, float)
    f_ra, f_dec = profile.drift(theta, lat)
    deg = auto_trend_degree(theta, profile.worm_theta, t=t) if trend_degree == 'auto' else int(trend_degree)
    detr = lambda y: detrend_per_minute(t, y, deg)
    r = motor_errors(detr(np.asarray(ra, float) - f_ra), detr(np.asarray(dec, float) - f_dec), theta, lat, min_theta2)
    return profile.motor_error(theta) + r


def worm_features(theta, worm_theta=WORM_THETA, harmonics=(1, 2)):
    """(n, 3 * 2 * len(harmonics)): per motor, per harmonic, sin and cos of the worm phase."""
    ph = 2 * np.pi * np.asarray(theta, float) / worm_theta
    cols = [f(h * ph[:, m]) for m in range(ph.shape[1]) for h in harmonics for f in (np.sin, np.cos)]
    return np.column_stack(cols)


@dataclass
class WormProfile:
    coef: np.ndarray                 # per motor, per harmonic: sin, cos (arcsec of that motor's angle)
    worm_theta: float = WORM_THETA
    harmonics: tuple = (1, 2)

    def motor_error(self, theta):
        """(n, 3) arcsec error of each motor's angle at these motor angles."""
        f = worm_features(theta, self.worm_theta, self.harmonics) * self.coef
        return f.reshape(len(f), 3, -1).sum(axis=2)

    def drift(self, theta, lat):
        """(ra, dec) arcsec of drift the profile predicts at these motor angles."""
        rd = np.einsum('nij,nj->ni', sky_weights(theta, lat), self.motor_error(theta))
        return rd[:, 0], rd[:, 1]


def _grid_turns(t, theta, worm_theta, grid_s=60.0):
    """Worm turns each motor travels (path length, so a reversal counts both ways), on a grid_s grid."""
    t = np.asarray(t, float)
    tg = np.arange(t[0], t[-1] + grid_s / 2, grid_s)
    g = np.column_stack([np.interp(tg, t, np.asarray(theta, float)[:, i]) for i in range(3)])
    return np.abs(np.diff(g, axis=0)).sum(axis=0) / worm_theta


def auto_trend_degree(theta, worm_theta=WORM_THETA, min_turns=2.0, max_degree=4, t=None):
    """Polynomial degree of the slow-drift trend a segment can support next to its worm: 2 (quadratic) when the slowest
    motor worth fitting (>= min_turns worm turns) makes ~2 turns, one more per extra turn, up to max_degree. With few
    turns a flexible trend and the worm can't be told apart; with many, the repeating worm pins itself down."""
    theta = np.asarray(theta, float)
    turns = (_grid_turns(t, theta, worm_theta) if t is not None
             else np.abs(np.diff(theta, axis=0)).sum(axis=0) / worm_theta)
    fitted = turns[turns >= min_turns]
    if not len(fitted):
        return 2
    return int(np.clip(2 + np.floor(fitted.min() - 2), 2, max_degree))


def motor_direction(t, theta, min_rate=1.0, smooth_s=600.0):
    """(n, 3): each motor's direction of travel (+1 / -1), 0 where it turns slower than min_rate deg/hr (rate over
    +/- smooth_s / 2). After a reversal the gear teeth bear on the other flank (backlash), and a nearly stationary
    motor's angle can't separate its worm from slow drift."""
    t = np.asarray(t, float)
    theta = np.asarray(theta, float)
    h = smooth_s / 2
    lo, hi = np.clip(t - h, t[0], t[-1]), np.clip(t + h, t[0], t[-1])
    rate = np.column_stack([(np.interp(hi, t, theta[:, i]) - np.interp(lo, t, theta[:, i])) for i in range(3)])
    rate = rate / np.maximum(hi - lo, 1e-9)[:, None] * 3600
    return np.where(np.abs(rate) < min_rate, 0, np.sign(rate)).astype(int)


def pass_turns(t, theta, worm_theta=WORM_THETA, min_rate=1.0, smooth_s=600.0):
    """(n, 3): for each sample and motor, the worm turns covered by the continuous same-direction pass it belongs to
    (0 while the motor is nearly stationary). A pass under ~2 turns can't separate that motor's worm from slow drift,
    e.g. M2's short climb after it reverses at the meridian."""
    theta = np.asarray(theta, float)
    d = motor_direction(t, theta, min_rate, smooth_s)
    out = np.zeros(theta.shape)
    for m in range(3):
        k = 0
        while k < len(t):
            j = k
            while j + 1 < len(t) and d[j + 1, m] == d[k, m]:
                j += 1
            if d[k, m] != 0:
                out[k:j + 1, m] = np.abs(np.diff(theta[k:j + 1, m])).sum() / worm_theta
            k = j + 1
    return out


def fit_worm(parts, worm_theta=WORM_THETA, harmonics=(1, 2), grid_s=60.0, ridge=1e-3, min_turns=2.0, trend_degree=2):
    """Fit a WormProfile to drift data. parts: list of (t, ra, dec, theta, lat). On a grid_s grid, each minute's
    RA and Dec drift increment = that part's own drift-rate trend per axis (not penalised) + the change of the
    mapped profile over that minute; RA and Dec share the motor coefficients (small ridge penalty). A motor's
    terms only count in parts where it turns at least min_turns worm turns (over less, a worm term is
    indistinguishable from the trend); a motor with no such part keeps zero coefficients."""
    per_motor = 2 * len(harmonics)
    n_coef = 3 * per_motor
    blocks = []
    for t, ra, dec, theta, lat in parts:
        t = np.asarray(t, float)
        if t[-1] - t[0] < 4 * grid_s:
            continue
        tg = np.arange(t[0], t[-1], grid_s)
        thg = np.column_stack([np.interp(tg, t, theta[:, i]) for i in range(3)])
        F = worm_features(thg, worm_theta, harmonics)
        turns = np.abs(np.diff(thg, axis=0)).sum(axis=0) / worm_theta
        for m in range(3):
            if turns[m] < min_turns:
                F[:, m * per_motor:(m + 1) * per_motor] = 0.0
        W = sky_weights(thg, lat)
        motor = np.repeat(np.arange(3), per_motor)
        deg = auto_trend_degree(thg, worm_theta, min_turns) if trend_degree == 'auto' else int(trend_degree)
        x = 2 * (tg[1:] - tg[1]) / max(tg[-1] - tg[1], 1e-9) - 1
        rate_basis = np.polynomial.legendre.legvander(x, deg - 1)              # drift rate: degree deg - 1
        for ax, y in enumerate((ra, dec)):
            G = W[:, ax, motor] * F                                     # profile -> this axis, per coefficient
            blocks.append((np.diff(G, axis=0), rate_basis, np.diff(np.interp(tg, t, y))))
    if not blocks:
        return WormProfile(np.zeros(n_coef), worm_theta, tuple(harmonics))
    X = np.zeros((sum(len(b[2]) for b in blocks), n_coef + sum(b[1].shape[1] for b in blocks)))
    Y = np.zeros(len(X))
    r, c = 0, n_coef
    for dG, trend, dy in blocks:
        X[r:r + len(dy), :n_coef] = dG
        X[r:r + len(dy), c:c + trend.shape[1]] = trend
        Y[r:r + len(dy)] = dy
        r += len(dy)
        c += trend.shape[1]
    A = X.T @ X
    pen = np.zeros(len(A))
    pen[:n_coef] = ridge * max(np.trace(A[:n_coef, :n_coef]) / n_coef, 1e-12) + 1e-9
    sol = np.linalg.lstsq(A + np.diag(pen), X.T @ Y, rcond=None)[0]
    return WormProfile(sol[:n_coef], worm_theta, tuple(harmonics))


def _profile_rate(t, f):
    """arcsec/min of a profile series f at each sample, from the change since the previous sample."""
    out = np.zeros(len(t))
    dt = np.diff(t)
    ok = dt > 0
    out[1:][ok] = np.diff(f)[ok] / dt[ok] * 60
    return out


def replay_worm_pec_rate(t, ra, dec, theta, lat, profile, model):
    """(rate_ra, rate_dec) arcsec/min with a fixed worm profile: `model` replayed on the drift minus the
    profile, plus the profile's own rate."""
    f_ra, f_dec = profile.drift(theta, lat)
    return tuple(replay_pec_rate(t, np.asarray(y, float) - f, model) + _profile_rate(t, f)
                 for y, f in ((ra, f_ra), (dec, f_dec)))


def causal_worm_pec_rate(t, ra, dec, theta, lat, model, refit_s=600.0, min_s=1800.0, **fit_kw):
    """As replay_worm_pec_rate, but the profile is learnt only from the segment so far: refitted every refit_s
    once min_s of data exists (plain `model` before that)."""
    t, ra, dec = (np.asarray(v, float) for v in (t, ra, dec))
    out = [replay_pec_rate(t, ra, model), replay_pec_rate(t, dec, model)]
    k0 = int(np.searchsorted(t, t[0] + min_s))
    edges = list(range(k0, len(t), max(1, int(np.searchsorted(t, t[0] + refit_s)))))
    for a, b in zip(edges, edges[1:] + [len(t)]):
        prof = fit_worm([(t[:a], ra[:a], dec[:a], theta[:a], lat)], **fit_kw)
        rates = replay_worm_pec_rate(t[:b], ra[:b], dec[:b], theta[:b], lat, prof, model)
        for ax in (0, 1):
            out[ax][a:b] = rates[ax][a:b]
    return tuple(out)


def _thinned(s, thin_s):
    t = s.t - s.t[0]
    k = np.r_[True, np.diff(np.floor(t / thin_s)) > 0] if thin_s else np.ones(len(t), bool)
    return t[k], s.ra[k], s.dec[k], s.theta[k]


def worm_benchmark(segs, model, lat_of, raw_theta=(), same_mount=lambda a, b: True, guide_intervals_s=(30, 120, 300),
                   thin_s=5.0, warmup_s=1800.0, **fit_kw):
    """Long DataFrame (seg, session, kind, axis, dt, model, rms) of the drift left for the guider by: no PEC,
    `model` (EMA), and `model` + a motor-space worm profile fitted
      'worm: hindsight'      on the scored segment itself -- an upper bound, not something PEC can do,
      'worm: same session'   on the session's other segments (would a profile survive a goto?),
      'worm: other sessions' on other sessions of the same mount (does the profile repeat night to night?);
                             only segments named in raw_theta (raw MCU motor angles), scored and used,
      'worm: live'           on the segment so far (what the driver could do).
    lat_of(session) -> site latitude; same_mount(session_a, session_b) -> bool."""
    rows = []
    raw = [o for o in segs if o.name in raw_theta]
    part_of = lambda o: (o.t, o.ra, o.dec, o.theta, lat_of(o.session))
    for s in segs:
        kind = 'pulse' if np.median(np.diff(s.t)) < 10 else 'sync'
        lat = lat_of(s.session)
        t, ra, dec, th = _thinned(s, thin_s)
        rates = {model.name: (replay_pec_rate(t, ra, model), replay_pec_rate(t, dec, model)),
                 'worm: hindsight': replay_worm_pec_rate(t, ra, dec, th, lat, fit_worm([(t, ra, dec, th, lat)], **fit_kw), model),
                 'worm: live': causal_worm_pec_rate(t, ra, dec, th, lat, model, **fit_kw)}
        same = [o for o in segs if o.session == s.session and o.name != s.name]
        other = [o for o in raw if o.session != s.session and same_mount(s.session, o.session)] if s.name in raw_theta else []
        for tier, src in (('worm: same session', same), ('worm: other sessions', other)):
            if src:
                rates[tier] = replay_worm_pec_rate(t, ra, dec, th, lat, fit_worm([part_of(o) for o in src], **fit_kw), model)
        for ax, y in ((0, ra), (1, dec)):
            sc = rate_scores(t, y, {m: r[ax] for m, r in rates.items()}, guide_intervals_s=guide_intervals_s,
                             warmup_s=warmup_s)
            for dt, res in sc['guide_rms'].items():
                rows += [dict(seg=s.name, session=s.session, kind=kind, axis=('ra', 'dec')[ax], dt=dt, model=m, rms=v)
                         for m, v in res.items()]
    return pd.DataFrame(rows)


def relative_to(df, ref):
    """Per model and interval: pooled RMS relative to `ref` and to no PEC, over exactly the segments/axes where
    that model was scored, and the number of segments ('n'). Columns: (dt, 'vs ref' | 'vs no PEC' | 'n')."""
    out = {}
    key = ['seg', 'axis', 'dt']
    base = {m: g.set_index(key)['rms'] for m, g in df[df['model'].isin([ref, 'no_pec'])].groupby('model')}
    for (m, dt), g in df.groupby(['model', 'dt']):
        v = g.set_index(key)['rms']
        out[(m, dt)] = {'vs ref': float(np.sqrt((v ** 2).sum() / (base[ref].loc[v.index] ** 2).sum())),
                        'vs no PEC': float(np.sqrt((v ** 2).sum() / (base['no_pec'].loc[v.index] ** 2).sum())),
                        'n': g['seg'].nunique()}
    return pd.DataFrame(out).T.unstack(level=1).swaplevel(axis=1).sort_index(axis=1)


def worm_angle_control(segs, thetas, model, lat_of, dt=120, thin_s=5.0, warmup_s=1800.0, **fit_kw):
    """Pooled RMS (RA and Dec) of `model` + a hindsight worm profile, relative to `model`, for each candidate
    worm angle. A real worm shows as a dip at its angle; a flat curve means the hindsight gain is just extra
    parameters."""
    num, den = dict.fromkeys(thetas, 0.0), 0.0
    for s in segs:
        lat = lat_of(s.session)
        t, ra, dec, th = _thinned(s, thin_s)
        fits = {W: replay_worm_pec_rate(t, ra, dec, th, lat, fit_worm([(t, ra, dec, th, lat)], worm_theta=W, **fit_kw), model)
                for W in thetas}
        for ax, y in ((0, ra), (1, dec)):
            rates = {W: r[ax] for W, r in fits.items()}
            rates['ref'] = replay_pec_rate(t, y, model)
            sc = rate_scores(t, y, rates, guide_intervals_s=(dt,), warmup_s=warmup_s)['guide_rms'][dt]
            den += sc['ref'] ** 2
            for W in thetas:
                num[W] += sc[W] ** 2
    return pd.Series({W: float(np.sqrt(num[W] / den)) for W in thetas}, name=f'hindsight worm / {model.name}')


def worm_phase_table(segs, lat_of, worm_theta=WORM_THETA, min_turns=2.0, **fit_kw):
    """One row per segment and motor turning at least min_turns worm turns: the 1st-harmonic amplitude (arcsec) and
    phase (deg, of e = A sin(worm phase + phase)) from a joint fit of that segment, and the phase difference
    between fits of its first and second halves (each needing a full worm turn) as a noise check."""
    harmonics = fit_kw.pop('harmonics', (1, 2))
    per_motor = 2 * len(harmonics)

    def h1(prof, m):
        a, b = prof.coef[m * per_motor], prof.coef[m * per_motor + 1]
        return float(np.hypot(a, b)), float(np.degrees(np.arctan2(b, a)) % 360)

    rows = []
    for s in segs:
        lat = lat_of(s.session)
        prof = fit_worm([(s.t, s.ra, s.dec, s.theta, lat)], worm_theta=worm_theta, harmonics=harmonics, **fit_kw)
        first = s.t <= s.t[0] + (s.t[-1] - s.t[0]) / 2
        halves = [fit_worm([(s.t[k], s.ra[k], s.dec[k], s.theta[k], lat)], worm_theta=worm_theta, harmonics=harmonics,
                           **fit_kw) if k.sum() > 20 else None for k in (first, ~first)]
        for m in range(3):
            turns = np.ptp(s.theta[:, m]) / worm_theta
            if turns < min_turns:
                continue
            amp, phase = h1(prof, m)
            ok = [h is not None and np.ptp(s.theta[k, m]) >= worm_theta for h, k in zip(halves, (first, ~first))]
            dh = ((h1(halves[0], m)[1] - h1(halves[1], m)[1] + 180) % 360 - 180) if all(ok) else np.nan
            rows.append(dict(seg=s.name, session=s.session, motor=f'M{m + 1}', turns=turns, amp=amp, phase=phase,
                             halves_diff=dh))
    return pd.DataFrame(rows, columns=['seg', 'session', 'motor', 'turns', 'amp', 'phase', 'halves_diff'])


def phase_consistency(phases_deg):
    """Circular clustering of phases: n, mean phase (deg), mean resultant length R (1 = identical, ~0 = random) and
    the Rayleigh test p-value (approx. exp(-n R^2): the chance of R this large from random phases)."""
    ph = np.radians(np.asarray(phases_deg, float))
    n = len(ph)
    if n == 0:
        return {'n': 0, 'mean': np.nan, 'R': np.nan, 'p': np.nan}
    z = np.exp(1j * ph).mean()
    R = float(abs(z))
    return {'n': n, 'mean': float(np.degrees(np.angle(z)) % 360), 'R': R, 'p': float(np.exp(-n * R ** 2))}
