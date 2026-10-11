"""
A/B of the alignment model (Mechanical Alignment Correction on: rotation + M2/M3 offsets, M2 scale, fitted
unweighted -- driver/align_model.py) against the existing alignment (off: the driver's weighted rotation-only QUEST),
replayed on the sync tables that every QUEST refit writes to the driver log.

Scored by goto accuracy: each sync point is held out in turn and predicted from a model fitted on the others -- for
QUEST with the driver's weights as if pointing at the held-out point (proximity), as at a goto to a new target.

    uv run python alignment_ab.py                      # every log in logs/archive
    uv run python alignment_ab.py "alpaca.jdm_*"       # a glob

The logged p_az/p_alt/p_roll are the raw motor pose (no worm gear correction), so both sides are compared without it.
docs/study_alignment_mac_v2.md has the study this replays.
"""
import glob
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from align_model import fit_alignment, corrected_theta, boresights          # noqa: E402
from kinematics import q_to_theta, azaltroll_to_q, azalt_to_vector          # noqa: E402
from quaternion import Q as Quaternion                                       # noqa: E402

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs', 'archive'))
DEFAULT_M2_SCALE = 0.01

_TS = re.compile(r'^(\d{4}-\d\d-\d\dT[\d:.]+) ')
_ROW = re.compile(r"INFO\s+#(\d+)\s+(\d\d:\d\d:\d\d)\s+([\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+"
                  r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([-+\d.]+)'\s+([-+\d.]+)'")
_MAC = re.compile(r'MAC: (\w+)')


def parse_sync_tables(paths):
    """Every QUEST table row in the logs: log, table_time, mac, no, point_time, age_h, ra, dec, obs_az, obs_alt,
    p_az, p_alt, p_roll, weight (degrees, hours for ra)."""
    rows = []
    for path in paths:
        name, table_time, mac = os.path.basename(str(path)), None, None
        with open(path, errors='replace') as fh:
            for line in fh:
                if 'QUEST Model' in line:
                    m = _TS.match(line)
                    table_time = m.group(1) if m else None
                elif 'RMS Residual' in line and 'MAC: ' in line:
                    m = _MAC.search(line)
                    mac = m.group(1) if m else None
                elif table_time and ' #' in line:
                    m = _ROW.search(line)
                    if m:
                        g = m.groups()
                        rows.append(dict(log=name, table_time=table_time, mac=mac, no=int(g[0]), point_time=g[1],
                                         age_h=float(g[2]), ra=float(g[3]), dec=float(g[4]), obs_az=float(g[5]),
                                         obs_alt=float(g[6]), p_az=float(g[7]), p_alt=float(g[8]), p_roll=float(g[9]),
                                         weight=float(g[10])))
    return pd.DataFrame(rows)


def alignments(tables, min_points=6):
    """Sets of points fitted together: each log's tables that are the largest before its point count drops (or its
    last), without points already in an earlier set. Each: name, theta (raw motor angles), pred (raw boresights),
    obs (observed directions), dec."""
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
            out.append(dict(name=f"{log.replace('alpaca.', '').replace('.log', '')}@{t[5:16]}", theta=theta,
                            pred=np.array([azalt_to_vector(a, b) for a, b in zip(x['p_az'], x['p_alt'])]),
                            obs=np.array([azalt_to_vector(a, b) for a, b in zip(x['obs_az'], x['obs_alt'])]),
                            dec=x['dec'].to_numpy(float)))
    return out


def quest_weighted_q(pred, obs, w):
    """The driver's QUEST (SyncManager.optimize_alignQ_B2T): the Davenport eigenvector for weighted vector pairs."""
    w = np.asarray(w, float) / np.sum(w)
    B = (pred * w[:, None]).T @ obs
    S, sigma = B + B.T, np.trace(B)
    Z = np.array([B[1, 2] - B[2, 1], B[2, 0] - B[0, 2], B[0, 1] - B[1, 0]])
    K = np.zeros((4, 4))
    K[0, 0], K[0, 1:], K[1:, 0], K[1:, 1:] = sigma, Z, Z, S - sigma * np.eye(3)
    vals, vecs = np.linalg.eigh(K)
    return Quaternion(*vecs[:, np.argmax(vals)])


def driver_weights(pred, dec, v_current):
    """SyncManager.optimize_alignQ_B2T's weights: recency + proximity to the current pointing (sigma 10 deg) + polar."""
    n = len(pred)
    i = np.arange(n)
    w_recency = 0.5 * np.exp(-0.1 * (n - i))
    ang = np.arccos(np.clip(pred @ v_current, -1, 1))
    w_proximity = np.exp(-ang ** 2 / (2 * np.radians(10) ** 2))
    w_polar = np.exp(-((np.abs(dec) - 90) ** 2) / (2 * 10 ** 2))
    return w_proximity + w_polar + w_recency + 0.01


def _sep_arcmin(a, b):
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b)), np.dot(a, b))) * 60


def loo_errors_arcmin(al, s2=DEFAULT_M2_SCALE):
    """Leave-one-out goto errors (arcmin) per point: 'quest' (the driver's weighted rotation-only QUEST, MAC off),
    'model' (the alignment model with the M2 scale s2; the weighted QUEST when its points can't fix the offsets)."""
    n = len(al['obs'])
    quest, model = np.zeros(n), np.zeros(n)
    for k in range(n):
        m = np.arange(n) != k
        q = quest_weighted_q(al['pred'][m], al['obs'][m], driver_weights(al['pred'][m], al['dec'][m], al['pred'][k]))
        quest[k] = _sep_arcmin(np.asarray(q.rotate(al['pred'][k]), float), al['obs'][k])
        f = fit_alignment(al['theta'][m], al['obs'][m], s2=s2)
        target = boresights(corrected_theta(al['theta'][k:k + 1], f.d2, f.d3, s2))[0]
        if f.offsets_fitted:
            q = f.q
        else:                   # as the driver: offsets held, the weighted QUEST on the model's predictions
            pred = boresights(corrected_theta(al['theta'][m], f.d2, f.d3, s2))
            q = quest_weighted_q(pred, al['obs'][m], driver_weights(pred, al['dec'][m], target))
        model[k] = _sep_arcmin(np.asarray(q.rotate(target), float), al['obs'][k])
    return {'quest': quest, 'model': model}


def ab_table(pattern='*.log', log_dir=LOG_DIR, s2=DEFAULT_M2_SCALE, min_points=6):
    """One row per alignment: n, goto RMS for QUEST (MAC off) and the model (on), and the change."""
    paths = sorted(glob.glob(os.path.join(log_dir, pattern if pattern.endswith('.log') else pattern + '.log')))
    rows = []
    for al in alignments(parse_sync_tables(paths), min_points=min_points):
        e = loo_errors_arcmin(al, s2=s2)
        rq, rm = (float(np.sqrt(np.mean(e[k] ** 2))) for k in ('quest', 'model'))
        rows.append(dict(alignment=al['name'], n=len(al['obs']), quest_rms=rq, model_rms=rm,
                         improvement_pct=(1 - rm / rq) * 100 if rq else np.nan))
    return pd.DataFrame(rows)


if __name__ == '__main__':
    t = ab_table(sys.argv[1] if len(sys.argv) > 1 else '*.log')
    pd.set_option('display.width', 200)
    print("Goto accuracy, leave-one-out RMS (arcmin): QUEST = MAC off (weighted rotation), model = MAC on")
    print(t.round(1).to_string(index=False))
    if len(t):
        print(f"\nmedian: QUEST {t['quest_rms'].median():.1f}'  model {t['model_rms'].median():.1f}'  "
              f"({len(t)} alignments; model better on {int((t['model_rms'] < t['quest_rms']).sum())})")
