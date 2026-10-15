"""
A/B of Mechanical Alignment Correction (MAC on: rotation + M2/M3 offsets, M2 scale, fitted
unweighted -- driver/kinematics_mac.py) against the existing alignment (off: the driver's weighted rotation-only QUEST),
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
from kinematics_mac import fit_alignment, corrected_theta, boresights          # noqa: E402
from kinematics import q_to_theta, azaltroll_to_q, azalt_to_vector, vector_to_az_alt          # noqa: E402
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
    obs (observed directions), dec; and log, table_time, mac (as logged with that table) and points (the table rows,
    in sync order)."""
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
                            dec=x['dec'].to_numpy(float), log=log, table_time=t,
                            mac=x['mac'].iloc[0] if 'mac' in x else None,
                            points=x.reset_index(drop=True)))
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


def predict(al, m, k, s2=DEFAULT_M2_SCALE):
    """Where each alignment points for point k when fitted on the points in mask m: (QUEST's direction, the model's
    direction, the model's AlignFit). QUEST = the driver's weighted rotation-only QUEST (MAC off); the model = QUEST +
    MAC with the M2 scale s2 (the weighted QUEST on the model's predictions when its points can't fix the offsets)."""
    q = quest_weighted_q(al['pred'][m], al['obs'][m], driver_weights(al['pred'][m], al['dec'][m], al['pred'][k]))
    v_quest = np.asarray(q.rotate(al['pred'][k]), float)
    f = fit_alignment(al['theta'][m], al['obs'][m], s2=s2)
    target = boresights(corrected_theta(al['theta'][k:k + 1], f.d2, f.d3, s2))[0]
    if f.offsets_fitted:
        q = f.q
    else:                       # as the driver: offsets held, the weighted QUEST on the model's predictions
        pred = boresights(corrected_theta(al['theta'][m], f.d2, f.d3, s2))
        q = quest_weighted_q(pred, al['obs'][m], driver_weights(pred, al['dec'][m], target))
    return v_quest, np.asarray(q.rotate(target), float), f


def loo_errors_arcmin(al, s2=DEFAULT_M2_SCALE):
    """Leave-one-out goto errors (arcmin) per point: 'quest' (the driver's weighted rotation-only QUEST, MAC off),
    'model' (QUEST + MAC with the M2 scale s2; the weighted QUEST when its points can't fix the offsets)."""
    n = len(al['obs'])
    quest, model = np.zeros(n), np.zeros(n)
    for k in range(n):
        vq, vm, _ = predict(al, np.arange(n) != k, k, s2)
        quest[k], model[k] = _sep_arcmin(vq, al['obs'][k]), _sep_arcmin(vm, al['obs'][k])
    return {'quest': quest, 'model': model}


def _azalt_error_arcmin(v_pred, v_obs):
    """(horizontal, vertical) arcmin from where the alignment pointed to where the star was: dAz x cos(Alt), dAlt."""
    az_p, alt_p = vector_to_az_alt(v_pred)
    az_o, alt_o = vector_to_az_alt(v_obs)
    return ((az_o - az_p + 180) % 360 - 180) * np.cos(np.radians(alt_o)) * 60, (alt_o - alt_p) * 60


def point_errors(al, s2=DEFAULT_M2_SCALE, min_fit=3):
    """Per point, in sync order: its pose, and each alignment's goto error (arcmin, total and horizontal/vertical
    components) predicting it two ways -- 'loo' (fitted on every other point: the alignment's accuracy once complete)
    and 'next' (fitted only on the points synced before it, from min_fit on: the goto to a new target as the
    alignment grows; NaN before) -- plus the model's d2, d3 (deg) on the 'next' fit and whether it could fit them."""
    n = len(al['obs'])
    rows = []
    for k in range(n):
        p = al['points'].iloc[k] if 'points' in al else None
        r = dict(k=k, point_time=None if p is None else p['point_time'], az=None if p is None else p['obs_az'],
                 alt=None if p is None else p['obs_alt'], roll=None if p is None else p['p_roll'],
                 theta2=al['theta'][k, 1], theta3=al['theta'][k, 2])
        fits = [('loo', np.arange(n) != k)]
        if k >= min_fit:
            fits.append(('next', np.arange(n) < k))
        for tag, m in fits:
            vq, vm, f = predict(al, m, k, s2)
            for side, v in (('quest', vq), ('model', vm)):
                r[f'{tag}_{side}'] = _sep_arcmin(v, al['obs'][k])
                r[f'{tag}_{side}_h'], r[f'{tag}_{side}_v'] = _azalt_error_arcmin(v, al['obs'][k])
            if tag == 'next':
                r.update(next_d2=f.d2, next_d3=f.d3, next_offsets_fitted=f.offsets_fitted)
        rows.append(r)
    return pd.DataFrame(rows)


_BLC_TAKEUP = re.compile(r'BACKLASH taking up slack: (.*)')
_BLC_GIVEUP = re.compile(r'BACKLASH compensation stopped until .*?for (M[\d, M]+)')
_MOVE = ('slewtocoordinatesasync', 'slewtocoordinates ', 'J2000Goto {', 'SlewAbsolute {', 'movemechanical', 'moveabsolute')


def _point_timestamp(point_time, table_time):
    """A sync table's HH:MM:SS as a full ISO time: the latest such time not after the table (a point is always
    synced before the table that lists it, possibly the day before)."""
    t = pd.Timestamp(f'{table_time[:10]}T{point_time}')
    if t > pd.Timestamp(table_time) + pd.Timedelta(seconds=1):
        t -= pd.Timedelta(days=1)
    return t.isoformat(timespec='milliseconds')


def blc_at_points(path, point_times, table_time):
    """How Backlash Compensation ended the move before each sync point (HH:MM:SS, as in the sync table written at
    table_time): the last goto / slew / rotate request before it, and the BLC lines between that and the point:
    'compensated' (slack taken up), 'given up' (compensation stopped for a motor), 'no slack' (BLC lines elsewhere in
    the log, none here), or 'off' (no BLC lines in the log: switched off, or a driver without it)."""
    events, blc_seen = [], False
    with open(path, errors='replace') as fh:
        for line in fh:
            m = _TS.match(line)
            if not m:
                continue
            t = m.group(1)
            if any(k in line for k in _MOVE):
                events.append((t, 'move', None))
            elif (g := _BLC_TAKEUP.search(line)):
                events.append((t, 'takeup', g.group(1).strip()))
                blc_seen = True
            elif (g := _BLC_GIVEUP.search(line)):
                events.append((t, 'giveup', g.group(1)))
                blc_seen = True
    rows = []
    for pt in point_times:
        ts = _point_timestamp(pt, table_time)
        moves = [i for i, e in enumerate(events) if e[1] == 'move' and e[0] <= ts]
        if not moves:
            rows.append(dict(point_time=pt, move_time=None, takeups=0, giveups='', blc='off' if not blc_seen else 'no move'))
            continue
        seg = [e for e in events[moves[-1] + 1:] if e[0] <= ts]
        tu = [e[2] for e in seg if e[1] == 'takeup']
        gu = [e[2] for e in seg if e[1] == 'giveup']
        state = 'off' if not blc_seen else 'given up' if gu else 'compensated' if tu else 'no slack'
        rows.append(dict(point_time=pt, move_time=events[moves[-1]][0], takeups=len(tu), giveups=';'.join(gu), blc=state))
    return pd.DataFrame(rows)


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
