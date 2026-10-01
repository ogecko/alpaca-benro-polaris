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


def load_segments(seg_dir, min_minutes=60, exclude=DUPLICATES):
    idx = pd.read_csv(os.path.join(seg_dir, 'index.csv'))
    out = []
    for _, r in idx.iterrows():
        if any(x in r['session'] for x in exclude):
            continue
        d = pd.read_csv(os.path.join(seg_dir, r['file']))
        if d[['theta1', 'theta2', 'theta3']].isna().all().any() or len(d) < 20:
            continue
        if d['t_sec'].iloc[-1] - d['t_sec'].iloc[0] < min_minutes * 60:
            continue
        out.append(Segment(name=f"{r['session']}#{int(r['segment'])}", session=r['session'], t=d['t_sec'].values,
                           ra=d['drift_ra_arcsec'].values, dec=d['drift_dec_arcsec'].values,
                           theta=d[['theta1', 'theta2', 'theta3']].values))
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
