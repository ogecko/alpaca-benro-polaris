"""
One standard drift dataset per catalogued tracking segment (utility/catalog_logs.py), for studying
the mount's drift / periodic error whatever records each log happens to hold.

Columns: timestamp, t_sec (from segment start), drift_ra_arcsec, drift_dec_arcsec, drift_source,
theta1-3 (motor angles, deg, unwrapped), theta_source, az, alt, roll.

Drift is the driver's own `total_accum` (guide corrections + PEC applied: the mount's drift with PEC's
effect removed), in the driver's correction convention, joined across PEC model resets; or, for a
segment with no PECLOG (PEC off), a PHD2 guide log's pulses where one is given, or the SYNC GUIDING residual lines. Motor angles come from KFLOG theta, SGLOG theta, PECLOG/SGLOG
az/alt/roll through the inverse kinematics, or the target rebuilt from time, site and roll (tracking
holds roll + parallactic angle), interpolated onto the drift samples.

    uv run python utility/extract_segments.py      # all usable segments -> logs/archive/segments/
"""
import glob
import math
import os
import sys

import ephem
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from catalog_logs import _read_session, _payload, session_key                     # noqa: E402
from kinematics import azaltroll_to_theta_ik                                       # noqa: E402

DEFAULT_SITE = (-33.654651, 151.12)        # Mount Colah, where most archived sessions were captured
DEFAULT_UTC_OFFSET_H = 10.0                # driver logs are in local time


def stitch_accum(values, reset):
    """Running total across model resets: after a reset the logged accumulator restarts from 0."""
    out, offset, prev = np.empty(len(values)), 0.0, 0.0
    for i, (v, r) in enumerate(zip(values, reset)):
        if r:
            offset += prev
        out[i] = offset + v
        prev = v
    return out


def target_pose(ra_h, dec, local_ts, lat, lon, utc_offset_h=DEFAULT_UTC_OFFSET_H):
    obs = ephem.Observer()
    obs.lat, obs.lon, obs.pressure = str(lat), str(lon), 0
    obs.date = ephem.Date((pd.Timestamp(local_ts) - pd.Timedelta(hours=utc_offset_h)).to_pydatetime())
    b = ephem.FixedBody()
    b._ra, b._dec, b._epoch = math.radians(ra_h * 15), math.radians(dec), obs.date
    b.compute(obs)
    return math.degrees(b.az), math.degrees(b.alt)


def _parallactic(az, alt, lat):
    a, h, phi = map(math.radians, (az, alt, lat))
    return math.degrees(math.atan2(math.sin(a), math.tan(phi) * math.cos(h) - math.sin(h) * math.cos(a)))


def _interp_theta(t_out, t_in, theta_in):
    a = np.degrees(np.unwrap(np.radians(np.asarray(theta_in, dtype=float)), axis=0))
    return np.column_stack([np.interp(t_out, t_in, a[:, i]) for i in range(3)])


def _drift_from_records(rows, has_n):
    """(times, ra_arcsec, dec_arcsec) from PECLOG/SGLOG rows carrying total_accum (arcmin)."""
    def accum(d):                       # modern dict: total_accum [ra, dec]; legacy (parse_peclog_legacy): _1/_2
        a = d.get('total_accum')
        if isinstance(a, list) and len(a) == 2:
            return a
        if 'total_accum_1' in d and 'total_accum_2' in d:
            return [d['total_accum_1'], d['total_accum_2']]
        return None
    rows = [(t, {**d, 'total_accum': accum(d)}) for t, d in rows]
    rows = [(t, d) for t, d in rows if d['total_accum'] is not None
            and all(isinstance(v, (int, float)) for v in d['total_accum'])]
    if not rows:
        return None
    t = np.array([r[0] for r in rows])
    acc = np.array([r[1]['total_accum'] for r in rows], dtype=float) * 60
    if has_n:
        n = np.array([r[1].get('n', 0) for r in rows], dtype=float)
        reset = np.r_[False, np.diff(n) < 0]
    else:   # SGLOG has no counter: a reset shows as the running total jumping back to (about) this row's resid
        reset = np.zeros(len(rows), bool)
        for i in range(1, len(rows)):
            r = rows[i][1].get('resid') or [0, 0]
            if all(abs(acc[i, k] - (r[k] or 0) * 60) < 1e-6 for k in range(2)) and np.any(np.abs(acc[i - 1]) > 1e-6):
                reset[i] = True
    return t, stitch_accum(acc[:, 0], reset), stitch_accum(acc[:, 1], reset)


def _drift_from_sync_lines(paths, start, end):
    from analyse_helpers import parse_sync_guiding_residual_line
    rows = []
    for p in paths:
        with open(p, encoding='utf-8', errors='replace') as f:
            for line in f:
                if 'SYNC GUIDING' in line:
                    r = parse_sync_guiding_residual_line(line)
                    if r is not None:
                        t = pd.Timestamp(r['timestamp'])
                        if start <= t <= end:
                            rows.append((t, r['ra_resid_deg'] * 3600, r['dec_resid_deg'] * 3600))
    if not rows:
        return None
    rows.sort()
    return (np.array([r[0] for r in rows]), np.cumsum([r[1] for r in rows]), np.cumsum([r[2] for r in rows]))


def extract_segment(paths, seg, phd2_frames=None, site=DEFAULT_SITE, utc_offset_h=DEFAULT_UTC_OFFSET_H):
    """Standard drift dataset (DataFrame, empty if the segment has no drift signal) for one catalog row."""
    start, end = pd.Timestamp(seg['start']), pd.Timestamp(seg['end'])
    rec = {'peclog': [], 'sglog': [], 'kflog': []}
    for t, kind, payload in _read_session(paths):
        if kind in rec and start <= t <= end:
            d = _payload(payload)
            if isinstance(d, dict):
                rec[kind].append((t, d))

    # ── drift ────────────────────────────────────────────────────────────────────────────
    drift, src = None, None
    if phd2_frames is not None and len(phd2_frames) and not rec['peclog']:   # with PEC on, PHD2 alone misses PEC's share
        f = phd2_frames[(phd2_frames['timestamp'] >= start) & (phd2_frames['timestamp'] <= end)]
        if len(f):
            drift = (f['timestamp'].values, f['ra_pulse_arcsec'].cumsum().values, f['dec_pulse_arcsec'].cumsum().values)
            src = 'phd2'
    if drift is None:
        drift = _drift_from_records(rec['peclog'], has_n=True)
        src = 'peclog'
    if drift is None:
        drift = _drift_from_records(rec['sglog'], has_n=False)
        src = 'sglog'
    if drift is None:                   # PEC off and no SGLOG: the always-logged SYNC GUIDING residual lines
        drift, src = _drift_from_sync_lines(paths, start, end), 'sync_lines'
    if drift is None:
        return pd.DataFrame()
    t_drift = pd.to_datetime(drift[0])
    out = pd.DataFrame({'timestamp': t_drift, 'drift_ra_arcsec': drift[1], 'drift_dec_arcsec': drift[2]})
    out['drift_source'] = src
    tsec = (t_drift - t_drift[0]).total_seconds().values
    out['t_sec'] = tsec

    # ── pose and motor angles ────────────────────────────────────────────────────────────
    pose = sorted([(t, d['az'], d['alt'], d['roll']) for t, d in rec['sglog'] + rec['peclog']
                   if all(isinstance(d.get(k), (int, float)) for k in ('az', 'alt', 'roll'))], key=lambda x: x[0])
    t0 = t_drift[0]
    sec = lambda ts_: np.array([(x - t0).total_seconds() for x in ts_])
    if pose:
        pt = sec([p[0] for p in pose])
        for i, name in enumerate(('az', 'alt', 'roll'), start=1):
            vals = np.array([p[i] for p in pose], dtype=float)
            if name == 'az':                                                   # unwrap through 0/360
                out[name] = np.interp(tsec, pt, np.degrees(np.unwrap(np.radians(vals)))) % 360
            else:
                out[name] = np.interp(tsec, pt, vals)
    kf = [(t, d['θ_meas_raw']) for t, d in rec['kflog'] if isinstance(d.get('θ_meas_raw'), list)]
    sg = [(t, d['theta_raw']) for t, d in rec['sglog'] if isinstance(d.get('theta_raw'), list)]
    if kf:
        th, tsrc = kf, 'kflog'
    elif sg:
        th, tsrc = sg, 'sglog'
    elif pose:
        th, tsrc = [(p[0], list(azaltroll_to_theta_ik(p[1], p[2], p[3]))) for p in pose], ('peclog' if rec['peclog'] else 'sglog')
    elif not np.isnan(seg.get('target_ra_h', np.nan)) and not np.isnan(seg.get('roll_set', np.nan)):
        lat, lon = site
        azalt = [target_pose(seg['target_ra_h'], seg['target_dec'], t, lat, lon, utc_offset_h) for t in t_drift]
        para = [_parallactic(az, alt, lat) for az, alt in azalt]
        roll = [seg['roll_set'] - (p - para[0]) for p in para]               # tracking holds roll + parallactic
        out['az'], out['alt'], out['roll'] = [a for a, _ in azalt], [h for _, h in azalt], roll
        th, tsrc = [(t, list(azaltroll_to_theta_ik(a, h, r))) for t, (a, h), r in zip(t_drift, azalt, roll)], 'target'
    else:
        th, tsrc = [], 'none'
    if th:
        theta = _interp_theta(tsec, sec([x[0] for x in th]), [x[1] for x in th])
        out['theta1'], out['theta2'], out['theta3'] = theta[:, 0], theta[:, 1], theta[:, 2]
    else:
        out['theta1'] = out['theta2'] = out['theta3'] = np.nan
    out['theta_source'] = tsrc
    return out


def extract_all(catalog_csv, log_dir, out_dir, phd2=None):
    """Write one CSV per usable segment with a drift signal, plus an index. phd2: {session key: guide log}."""
    from analyse_helpers import load_phd2_guidelog
    cat = pd.read_csv(catalog_csv, parse_dates=['start', 'end'])
    files = [p for p in glob.glob(os.path.join(log_dir, 'alpaca.*.log')) if os.path.basename(p) != 'alpaca.log']
    by_session = {}
    for p in sorted(files):
        by_session.setdefault(session_key(p), []).append(p)
    os.makedirs(out_dir, exist_ok=True)
    index = []
    for _, seg in cat[cat['usable']].iterrows():
        frames = None
        if phd2 and seg['session'] in phd2:
            frames, _ = load_phd2_guidelog(phd2[seg['session']])
        d = extract_segment(by_session[seg['session']], seg, phd2_frames=frames)
        if d.empty:
            continue
        name = f"{seg['session']}__seg{int(seg['segment'])}.csv"
        d.to_csv(os.path.join(out_dir, name), index=False)
        index.append({**seg.to_dict(), 'file': name, 'n_samples': len(d),
                      'drift_source': d['drift_source'].iloc[0], 'theta_source': d['theta_source'].iloc[0]})
    pd.DataFrame(index).to_csv(os.path.join(out_dir, 'index.csv'), index=False)
    return pd.DataFrame(index)


if __name__ == '__main__':
    from sessions import catalog_phd2
    here = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(here, '..', 'logs', 'archive')
    phd2 = catalog_phd2()                               # PHD2 guide logs registered in sessions.toml
    idx = extract_all(os.path.join(log_dir, 'catalog_segments.csv'), log_dir, os.path.join(log_dir, 'segments'), phd2)
    print(f"{len(idx)} segments with a drift signal -> {os.path.join(log_dir, 'segments')}")
