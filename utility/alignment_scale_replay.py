"""
Should the M2 scale be fitted at every sync (instead of Pilot's AutoTune)? Replays the archived alignments in the order
their points were synced: after each sync the alignment is refitted as the driver would (rotation + M2/M3 offsets with
the M2 scale of the mode), and scored on the goto to the next point -- what a per-sync scale fit has to get right.

Modes (the M2 scale each refit uses):
    fixed_1.0      align_m2_scale's default, +1.0%
    carried        the scale AutoTune would have given on that mount's previous alignment (the current workflow; +1.0%
                   for a mount's first)
    auto           refitted at each sync when the points determine it (MIN_POINTS, M2 spread MIN_SPAN_DEG, separable,
                   within S2_RANGE), else the last value (starting from carried)
    auto_ftest     as auto, but a new value is taken only when freeing the scale cuts the misfit significantly (F-test
                   at P_ACCEPT against the current value)
    in_sample      AutoTune on all of the alignment's points (not available during a session: the best case)

    uv run python utility/alignment_scale_replay.py [log glob] [--log-dir DIR] [--offsets]

--offsets compares refitting the M2/M3 offsets at every sync (the driver) with taking new ones only when significantly
better (F-test), from zero or carried from the mount's previous alignment. 2026-10-13 on the archive: gating is worse
(median 14.3' free, 19.5' / 16.1' gated): the offsets change with the setup between sessions. The M2 scale gated by the
F-test is the safest (never more than 3' worse than AutoTune carried over, 14' better at best).
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))
from kinematics_mac import fit_alignment, corrected_theta, boresights          # noqa: E402
from kinematics import q_to_theta, azaltroll_to_q, azalt_to_vector          # noqa: E402
from alignment_ab import parse_sync_tables, LOG_DIR                         # noqa: E402

DEFAULT_S2 = 0.01
MIN_POINTS = 6
MIN_SPAN_DEG = 20.0
S2_RANGE = (0.0, 0.04)
P_ACCEPT = 0.05
MODES = ('fixed_1.0', 'carried', 'auto', 'auto_ftest', 'in_sample')


def owner(log):
    name = log.replace('alpaca.', '')
    for o in ('mark', 'greg', 'vyskocil'):
        if name.startswith(o):
            return o
    return 'jdm'                                    # jdm, soak, pec, rpi: jdm's mount


def alignments(tables, min_points=MIN_POINTS):
    """As alignment_ab.alignments, in session order, with the mount and the full table time."""
    out, seen = [], set()
    for log, g in tables.groupby('log', sort=True):
        times = sorted(g['table_time'].unique())
        sizes = [int((g['table_time'] == t).sum()) for t in times]
        for i, t in enumerate(times):
            if not (i == len(times) - 1 or sizes[i + 1] < sizes[i]) or sizes[i] < min_points:
                continue
            x = g[g['table_time'] == t].sort_values('no')
            x = x[[(r.point_time, r.ra, r.dec) not in seen for r in x.itertuples()]]
            if len(x) < min_points:
                continue
            seen.update((r.point_time, r.ra, r.dec) for r in x.itertuples())
            theta = np.array([np.asarray(q_to_theta(azaltroll_to_q(a, b, c)), float)
                              for a, b, c in zip(x['p_az'], x['p_alt'], x['p_roll'])])
            out.append(dict(name=f"{log.replace('alpaca.', '').replace('.log', '')}@{t[5:16]}", time=t, mount=owner(log),
                            theta=theta, obs=np.array([azalt_to_vector(a, b) for a, b in zip(x['obs_az'], x['obs_alt'])])))
    return sorted(out, key=lambda a: (a['mount'], a['time']))


def autotune(theta, obs, s2_now):
    """AutoTune (SyncManager.calibrate_m2_scale): (s2 or None, the fit with s2 held, the fit with s2 free)."""
    if len(theta) < MIN_POINTS or np.ptp(theta[:, 1]) < MIN_SPAN_DEG:
        return None, None, None
    held = fit_alignment(theta, obs, s2=s2_now)
    free = fit_alignment(theta, obs, s2=s2_now, d_init=(held.d2, held.d3), fit_s2=True)
    if not free.s2_fitted or not (S2_RANGE[0] <= free.s2 <= S2_RANGE[1]):
        return None, held, free
    return float(free.s2), held, free


def significant(held, free, n):
    """F-test: does freeing the M2 scale (1 parameter) cut the residual sum of squares by more than chance?
    2 residual components per point; 6 parameters (rotation 3, d2, d3, s2)."""
    rss0 = float(np.sum(held.residuals_arcmin ** 2))
    rss1 = float(np.sum(free.residuals_arcmin ** 2))
    dof = 2 * n - 6
    if dof <= 0 or rss1 <= 0 or rss0 <= rss1:
        return False
    f = (rss0 - rss1) / (rss1 / dof)
    return stats.f.sf(f, 1, dof) < P_ACCEPT


def goto_error(theta, obs, k, s2):
    """Fit points 0..k-1 with the M2 scale s2 as the driver does, and return the error (arcmin) predicting point k."""
    f = fit_alignment(theta[:k], obs[:k], s2=s2)
    target = boresights(corrected_theta(theta[k:k + 1], f.d2, f.d3, s2))[0]
    p = np.asarray(f.q.rotate(target), float)
    return float(np.degrees(np.arctan2(np.linalg.norm(np.cross(p, obs[k])), np.dot(p, obs[k]))) * 60)


def replay(als):
    rows, carried = [], {}
    for al in als:
        theta, obs, n = al['theta'], al['obs'], len(al['obs'])
        start = carried.get(al['mount'], DEFAULT_S2)
        s2_in = autotune(theta, obs, start)[0]
        state = {'auto': start, 'auto_ftest': start}
        for k in range(MIN_POINTS, n):                  # each sync from the 6th: refit, then the goto to point k
            for mode in ('auto', 'auto_ftest'):
                s2_new, held, free = autotune(theta[:k], obs[:k], state[mode])
                if s2_new is not None and (mode == 'auto' or significant(held, free, k)):
                    state[mode] = s2_new
            s2 = {'fixed_1.0': DEFAULT_S2, 'carried': start, 'auto': state['auto'], 'auto_ftest': state['auto_ftest'],
                  'in_sample': s2_in if s2_in is not None else start}
            for mode in MODES:
                rows.append(dict(alignment=al['name'], mount=al['mount'], n=n, k=k, mode=mode, s2=s2[mode] * 100,
                                 err=goto_error(theta, obs, k, s2[mode])))
        if s2_in is not None:
            carried[al['mount']] = s2_in                 # what AutoTune would leave for the mount's next alignment
    return pd.DataFrame(rows)


# ── the M2/M3 offsets: refitted at every sync (the driver) or only when significantly better ───────────────────────
OFFSET_MODES = ('free', 'gated_from_0', 'gated_carried')


def offsets_significant(held, free, n):
    """F-test: does freeing the M2/M3 offsets (2 parameters) cut the misfit by more than chance? 2 components per point,
    5 parameters (rotation 3, d2, d3)."""
    rss0, rss1 = float(np.sum(held.residuals_arcmin ** 2)), float(np.sum(free.residuals_arcmin ** 2))
    dof = 2 * n - 5
    if dof <= 0 or rss1 <= 0 or rss0 <= rss1:
        return False
    return stats.f.sf(((rss0 - rss1) / 2) / (rss1 / dof), 2, dof) < P_ACCEPT


def goto_error_offsets(theta, obs, k, s2, d, fit):
    """Fit points 0..k-1 (offsets fitted, or held at d) and return the error (arcmin) predicting point k."""
    f = fit_alignment(theta[:k], obs[:k], s2=s2, d_init=d, fit_offsets=fit)
    target = boresights(corrected_theta(theta[k:k + 1], f.d2, f.d3, s2))[0]
    p = np.asarray(f.q.rotate(target), float)
    return float(np.degrees(np.arctan2(np.linalg.norm(np.cross(p, obs[k])), np.dot(p, obs[k]))) * 60), f


def replay_offsets(als, first_k=3):
    """Each alignment in session order with the carried M2 scale; the goto to point k after each sync from the 3rd."""
    rows, carried_s2, carried_d = [], {}, {}
    for al in als:
        theta, obs, n = al['theta'], al['obs'], len(al['obs'])
        s2 = carried_s2.get(al['mount'], DEFAULT_S2)
        d_state = {'gated_from_0': (0.0, 0.0), 'gated_carried': carried_d.get(al['mount'], (0.0, 0.0))}
        for k in range(first_k, n):
            for mode in ('gated_from_0', 'gated_carried'):         # this sync's refit decides the held offsets
                held = fit_alignment(theta[:k], obs[:k], s2=s2, d_init=d_state[mode], fit_offsets=False)
                free = fit_alignment(theta[:k], obs[:k], s2=s2, d_init=d_state[mode])
                if free.offsets_fitted and offsets_significant(held, free, k):
                    d_state[mode] = (free.d2, free.d3)
            for mode in OFFSET_MODES:
                if mode == 'free':
                    err, f = goto_error_offsets(theta, obs, k, s2, (0.0, 0.0), True)
                    d = (f.d2, f.d3)
                else:
                    err, _ = goto_error_offsets(theta, obs, k, s2, d_state[mode], False)
                    d = d_state[mode]
                rows.append(dict(alignment=al['name'], mount=al['mount'], k=k, mode=mode, err=err,
                                 d2=d[0] * 60, d3=d[1] * 60))
        s2_in = autotune(theta, obs, s2)[0]
        if s2_in is not None:
            carried_s2[al['mount']] = s2_in
        f_all = fit_alignment(theta, obs, s2=s2)
        if f_all.offsets_fitted:
            carried_d[al['mount']] = (f_all.d2, f_all.d3)
    return pd.DataFrame(rows)


def offsets_report(als):
    df = replay_offsets(als)
    per = df.groupby(['alignment', 'mode'])['err'].apply(lambda e: float(np.sqrt(np.mean(e ** 2)))).unstack()[list(OFFSET_MODES)]
    early = df[df['k'] < 6].groupby(['alignment', 'mode'])['err'].apply(lambda e: float(np.sqrt(np.mean(e ** 2)))).unstack()
    print(f"\nM2/M3 offsets: goto to the next point after each sync from the 3rd, {len(per)} alignments, "
          f"{len(df) // len(OFFSET_MODES)} gotos")
    print("median RMS:", {m: round(float(per[m].median()), 2) for m in OFFSET_MODES},
          " mean RMS:", {m: round(float(per[m].mean()), 2) for m in OFFSET_MODES})
    print("syncs 3-5 only, median RMS:", {m: round(float(early[m].median()), 2) for m in OFFSET_MODES if m in early})
    for m in ('gated_from_0', 'gated_carried'):
        dd = per[m] - per['free']
        print(f"{m:14s} vs free: better on {int((dd < -0.5).sum())}, worse on {int((dd > 0.5).sum())}, "
              f"within 0.5' on {int((dd.abs() <= 0.5).sum())}; worst {dd.max():+.1f}', best {dd.min():+.1f}'")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('pattern', nargs='?', default='*.log')
    ap.add_argument('--log-dir', default=LOG_DIR)
    ap.add_argument('--offsets', action='store_true', help='compare gating the M2/M3 offsets instead')
    a = ap.parse_args()
    paths = sorted(glob.glob(os.path.join(a.log_dir, a.pattern if a.pattern.endswith('.log') else a.pattern + '.log')))
    als = alignments(parse_sync_tables(paths))
    if a.offsets:
        offsets_report(als)
        sys.exit(0)
    df = replay(als)
    per = df.groupby(['alignment', 'mount', 'mode'])['err'].apply(lambda e: float(np.sqrt(np.mean(e ** 2)))).unstack()
    per = per[list(MODES)]
    pd.set_option('display.width', 220)
    print(f"Goto to the next point after each sync (RMS arcmin per alignment), {len(per)} alignments, "
          f"{len(df) // len(MODES)} gotos:\n")
    print(per.round(1).to_string())
    print("\nmedian RMS per mode:", {m: round(float(per[m].median()), 2) for m in MODES})
    print("mean RMS per mode:  ", {m: round(float(per[m].mean()), 2) for m in MODES})
    base = per['carried']
    for m in ('fixed_1.0', 'auto', 'auto_ftest', 'in_sample'):
        d = per[m] - base
        print(f"{m:10s} vs carried: better on {int((d < -0.5).sum())}, worse on {int((d > 0.5).sum())}, "
              f"within 0.5' on {int((d.abs() <= 0.5).sum())}; worst {d.max():+.1f}'")
    final = df.sort_values('k').groupby(['alignment', 'mode'])['s2'].last().unstack()[['carried', 'auto', 'auto_ftest', 'in_sample']]
    print("\nM2 scale (%) at the end of each alignment, by mount:")
    print(final.join(per['mount'].to_frame() if 'mount' in per else df.groupby('alignment')['mount'].first()).groupby('mount').agg(['median', 'min', 'max']).round(2).to_string())
