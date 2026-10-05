"""
Inventory of archived driver logs for drift / periodic-error (PEC) analysis.

Splits every session (rotated log parts joined in time order) into segments of steady tracking on one
target -- broken by gotos, slews, jogs, rotates, parks and tracking changes -- and records for each
what data it holds and at what pose, so the segments that can answer a modelling question can be
picked out (e.g. long, PEC off, one or two fast motors, records that give the motor angles).

    uv run python utility/catalog_logs.py                       # writes logs/archive/catalog_segments.csv
    uv run python utility/catalog_logs.py --md docs/x.md        # and a markdown summary

Per segment: start/end/duration, driver version, why it started/ended, target RA/Dec (last goto),
pose (az/alt/roll start/end/mean) and its source (KFLOG theta, SGLOG theta, or PECLOG az/alt/roll
through the inverse kinematics), each motor's rate and travel, record counts (PECLOG/SGLOG/KFLOG),
PEC state, worm gear correction (feed-forward) state, sync-guide count and median interval, pulse-guiding evidence,
battery, and the session's notes from the session registry (sessions.toml). The span of a worm gear test (Speed
Calibration M1-M2-M3-WORM-PROFILE, or the earlier per-motor M#-WORM-GEAR, which step the motors back and forth) is
left out.
"""
import argparse
import ast
import glob
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from kinematics import azaltroll_to_theta_ik                                          # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse_helpers import parse_peclog_legacy                                       # noqa: E402

MIN_SEGMENT_MIN = 45.0          # shorter segments can't show several cycles of a ~30-60 min signal
SETTLE_S = 60.0                 # skipped after the event that starts a segment
KFLOG_EVERY_S = 10.0            # KFLOG/SGLOG theta samples kept (KFLOG runs at 5 Hz)

_TS_RE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?)")
_VERSION_RE = re.compile(r"==STARTUP== ALPACA BENRO POLARIS DRIVER (v[\w.]+(?: \w+ [\w.]+)?)")
_GOTO_RADEC_RE = re.compile(r"GOTO Observed\s+RA (\d+)h(\d+)m([\d.]+)s\s+Dec ([+-])(\d+)d(\d+)'([\d.]+)\"")
_CONFIG_RE = re.compile(r"'Action': 'Polaris:ConfigUpdate', 'Parameters': (\{[^}]*\})")
_BATTERY_RE = re.compile(r"BATTERY status changed: 778 \{'capacity': '(\d+)'")
_ROTATE_RE = re.compile(r"Rotate Absolute Observed\s+RollAngle ([+-])(\d+)d(\d+)'([\d.]+)\"")
_WORM_TEST_RE = re.compile(r"WORM (?:PROFILE TEST|GEAR TEST M\d): (START|END)")      # current, and earlier logs
_SLEWABS_ROLL_RE = re.compile(r"Polaris:SlewAbsolute \{[^}]*'roll': (-?[\d.]+)")

_MOVES = ('slewtocoordinatesasync', 'slewtoaltazasync', 'Polaris:SlewAbsolute', 'Polaris:SlewRelative',
          'Polaris:PanoSlew', 'Polaris:MoveAxis', 'Polaris:MoveMotor', 'Rotate Absolute', 'Polaris:ResetAxes',
          '/telescope/0/abortslew', '/telescope/0/park ', '/telescope/0/findhome', 'Advanced Control: PARK')


def session_key(filename):
    """Session name of a log file: rotated parts (_a1, _a08, _d3 ...) share one key."""
    name = os.path.basename(filename)
    name = re.sub(r"\.log(\.\d+)?$", "", name)
    name = re.sub(r"_[a-z]?\*$", "", name)          # glob patterns from notebook lists (_a*.log)
    return re.sub(r"_[a-d]\d+$", "", name)              # rotated parts: _a1, _a08, _d3 (not _h2 etc.)


def _classify(line):
    """(kind, payload) for the lines that matter, else None."""
    if 'PECLOG {' in line:
        return 'peclog', line.split(' PECLOG ', 1)[1]
    if ' PECLOG ' in line:
        rec = parse_peclog_legacy(line)                 # pre-dict format: Pos,az,alt,roll; no resid
        return ('peclog', rec) if rec is not None else None
    if ' SGLOG {' in line:
        return 'sglog', line.split(' SGLOG ', 1)[1]
    if ' KFLOG {' in line:
        return 'kflog', line.split(' KFLOG ', 1)[1]
    if 'SYNC GUIDING' in line and 'Residuals' in line and 'too large' not in line:
        return 'sync_guide', None
    m = _GOTO_RADEC_RE.search(line)
    if m:
        ra = int(m[1]) + int(m[2]) / 60 + float(m[3]) / 3600
        dec = (1 if m[4] == '+' else -1) * (int(m[5]) + int(m[6]) / 60 + float(m[7]) / 3600)
        return 'goto', (ra, dec)
    m = _WORM_TEST_RE.search(line)
    if m:                                               # a worm gear test steps a motor: not steady tracking
        return ('worm_test_start' if m[1] == 'START' else 'worm_test_end'), None
    if 'Advanced Control: START tracking' in line:
        return 'tracking_on', None
    if 'Advanced Control: STOP' in line or ("/telescope/0/tracking {" in line and "'Tracking': 'false'" in line):
        return 'tracking_off', None
    m = _ROTATE_RE.search(line)
    if m:
        return 'move', (1 if m[1] == '+' else -1) * (int(m[2]) + int(m[3]) / 60 + float(m[4]) / 3600)
    m = _SLEWABS_ROLL_RE.search(line)
    if m:
        return 'move', float(m[1])
    if any(m in line for m in _MOVES):
        return 'move', None
    m = _CONFIG_RE.search(line)
    if m:
        try:
            return 'config', ast.literal_eval(m[1])
        except (ValueError, SyntaxError):
            return None
    m = _VERSION_RE.search(line)
    if m:
        return 'version', m[1].strip()
    m = _BATTERY_RE.search(line)
    if m:
        return 'battery', int(m[1])
    return None


def _read_session(paths):
    """Time-ordered (timestamp, kind, payload) events of a session's rotated parts."""
    events = []
    for p in paths:
        last_kf = None
        with open(p, encoding='utf-8', errors='replace') as f:
            for line in f:
                m = _TS_RE.match(line)
                if not m:
                    continue
                c = _classify(line)
                if c is None:
                    continue
                t = pd.Timestamp(m[1])
                if c[0] == 'kflog':
                    if last_kf is not None and (t - last_kf).total_seconds() < KFLOG_EVERY_S:
                        continue
                    last_kf = t
                events.append((t, c[0], c[1]))
    events.sort(key=lambda e: e[0])
    return events


def _payload(s):
    if isinstance(s, dict):
        return s
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return None


def _pose_and_theta(samples):
    """Pose and motor angles of a segment from the best record type available."""
    kf, sg, pec = samples['kflog'], samples['sglog'], samples['peclog']
    pose = [(t, d['az'], d['alt'], d['roll']) for t, d in sg + pec
            if all(isinstance(d.get(k), (int, float)) for k in ('az', 'alt', 'roll'))]
    pose.sort(key=lambda x: x[0])
    if kf:
        th = [(t, d['θ_meas_raw']) for t, d in kf if isinstance(d.get('θ_meas_raw'), list)]
        src = 'kflog'
    elif sg and any('theta_raw' in d for _, d in sg):
        th = [(t, d['theta_raw']) for t, d in sg if 'theta_raw' in d]
        src = 'sglog'
    elif pose:
        th = [(t, list(azaltroll_to_theta_ik(az, alt, roll))) for t, az, alt, roll in pose]
        src = 'peclog' if pec else 'sglog'
    else:
        th, src = [], 'none'
    return pose, th, src


def _pose_source(src, target):
    """No pose records, but a known target: the pose can be rebuilt from target, time, site and roll."""
    return 'target' if src == 'none' and not np.isnan(target[0]) else src


def _rates(th):
    """Per-motor mean rate (deg/hr, slope of a linear fit) and travel (deg) of unwrapped motor angles."""
    if len(th) < 3:
        return [np.nan] * 3, [np.nan] * 3
    t = np.array([(x[0] - th[0][0]).total_seconds() for x in th]) / 3600
    a = np.degrees(np.unwrap(np.radians(np.array([x[1] for x in th], dtype=float)), axis=0))
    rates = [abs(np.polyfit(t, a[:, i], 1)[0]) for i in range(3)]
    travel = [float(np.ptp(a[:, i])) for i in range(3)]
    return rates, travel


def catalog_session(paths, notes=None):
    """Segments (list of dicts) of one session given its rotated log parts (any order)."""
    events = _read_session(paths)
    key = session_key(paths[0])
    segs, cur = [], None
    state = dict(version=None, target=(np.nan, np.nan), pec=None, tracking=False, last_move=None, roll=np.nan,
                 worm_test=False)
    seg_idx = 0

    def open_seg(t, reason):
        return dict(start=t + pd.Timedelta(seconds=SETTLE_S), start_reason=reason,
                    samples={'peclog': [], 'sglog': [], 'kflog': []}, syncs=[], battery=[],
                    pec_events=[state['pec']], version=state['version'], target=state['target'], roll=state['roll'])

    def close_seg(t, reason):
        nonlocal seg_idx
        if cur is None:
            return
        end = t
        dur = (end - cur['start']).total_seconds() / 60
        if dur <= 0:
            return
        pose, th, src = _pose_and_theta(cur['samples'])
        src = _pose_source(src, cur['target'])
        rates, travel = _rates(th)
        syncs = [s for s in cur['syncs'] if cur['start'] <= s <= end]
        intervals = np.diff([s.value / 1e9 for s in syncs])
        pec_rows = cur['samples']['peclog']
        single_axis = sum(1 for _, d in pec_rows if isinstance(d.get('resid'), list)
                          and sum(v is not None for v in d['resid']) == 1)
        pec_known = [p for p in cur['pec_events'] if p is not None]
        pec = 'on' if pec_rows else ('off' if pec_known and not any(pec_known) else ('unknown' if not pec_known else 'off'))
        wff_on = any(isinstance(d.get('wff'), list) and any(isinstance(v, (int, float)) and v != 0 for v in d['wff'])
                     for _, d in pec_rows)
        rec = dict(session=key, segment=seg_idx, start=cur['start'], end=end, duration_min=round(dur, 1),
                   start_reason=cur['start_reason'], end_reason=reason, driver_version=cur['version'],
                   target_ra_h=cur['target'][0], target_dec=cur['target'][1], roll_set=cur['roll'], pose_source=src,
                   n_peclog=len(pec_rows), n_sglog=len(cur['samples']['sglog']), n_kflog=len(cur['samples']['kflog']),
                   pec=pec, worm_ff='on' if wff_on else 'off', n_sync_guide=len(syncs),
                   sync_interval_s=float(np.median(intervals)) if len(intervals) else np.nan,
                   pulse_guiding=single_axis > 0,
                   battery_start=cur['battery'][0] if cur['battery'] else np.nan,
                   battery_end=cur['battery'][-1] if cur['battery'] else np.nan)
        for name, idx in (('az', 1), ('alt', 2), ('roll', 3)):
            v = [p[idx] for p in pose]
            rec[f'{name}_start'] = v[0] if v else np.nan
            rec[f'{name}_end'] = v[-1] if v else np.nan
            rec[f'{name}_mean'] = float(np.mean(v)) if v else np.nan
        for i in range(3):
            rec[f'm{i+1}_dps_hr'] = rates[i]
            rec[f'm{i+1}_travel_deg'] = travel[i]
        rec['usable'] = bool(dur >= MIN_SEGMENT_MIN and src != 'none')
        rec['notes'] = (notes or {}).get(key, '')
        segs.append(rec)
        seg_idx += 1

    for t, kind, payload in events:
        if kind == 'version':
            state['version'] = payload
        elif kind == 'config':
            if 'advanced_pec' in payload:
                state['pec'] = bool(payload['advanced_pec'])
                if cur is not None:
                    cur['pec_events'].append(state['pec'])
        elif kind == 'battery':
            if cur is not None:
                cur['battery'].append(payload)
        elif kind == 'goto':
            state['target'] = payload
            state['last_move'] = (t, 'goto')
            close_seg(t, 'goto')
            cur = open_seg(t, 'goto') if state['tracking'] and not state['worm_test'] else None
        elif kind == 'move':
            if payload is not None:
                state['roll'] = payload
            state['last_move'] = (t, 'move')
            close_seg(t, 'move')
            cur = open_seg(t, 'move') if state['tracking'] and not state['worm_test'] else None
        elif kind == 'worm_test_start':
            close_seg(t, 'worm_gear_test')
            cur = None
            state['worm_test'] = True
            state['tracking'] = True                    # the test turns tracking on
        elif kind == 'worm_test_end':
            state['worm_test'] = False
            close_seg(t, 'worm_gear_test')
            cur = open_seg(t, 'worm_gear_test') if state['tracking'] else None
        elif kind == 'tracking_on':
            if not state['tracking']:
                state['tracking'] = True
                if cur is None and not state['worm_test']:
                    lm = state['last_move']             # goto/move then START tracking: credit the move
                    if lm is not None and (t - lm[0]).total_seconds() <= 30:
                        cur = open_seg(lm[0], lm[1])
                    else:
                        cur = open_seg(t, 'tracking_on')
        elif kind == 'tracking_off':
            state['tracking'] = False
            close_seg(t, 'tracking_off')
            cur = None
        elif kind == 'sync_guide':
            if cur is not None:
                cur['syncs'].append(t)
        elif kind in ('peclog', 'sglog', 'kflog'):
            if cur is not None and t >= cur['start']:
                d = _payload(payload)
                if isinstance(d, dict):
                    cur['samples'][kind].append((t, d))
                    if kind in ('peclog', 'sglog'):
                        state['tracking'] = True
            elif cur is None and kind == 'peclog' and not state['worm_test']:
                # PECLOG only exists while tracking: a log that starts mid-session is tracking already
                state['tracking'] = True
                cur = open_seg(t - pd.Timedelta(seconds=SETTLE_S), 'log_start')
                d = _payload(payload)
                if isinstance(d, dict):
                    cur['samples'][kind].append((t, d))
    if cur is not None and events:
        close_seg(events[-1][0], 'log_end')
    return segs


def catalog(log_dir, notes=None):
    """Every session in log_dir split into segments. notes: {session: text}, e.g. sessions.catalog_notes()."""
    files = [p for p in glob.glob(os.path.join(log_dir, 'alpaca.*.log')) if os.path.basename(p) != 'alpaca.log']
    by_session = {}
    for p in sorted(files):
        by_session.setdefault(session_key(p), []).append(p)
    notes = notes or {}
    rows = []
    for key, paths in sorted(by_session.items()):
        rows += catalog_session(paths, notes)
    return pd.DataFrame(rows)


def to_markdown(df):
    use = df[df['usable']].copy()
    cols = ['session', 'segment', 'start', 'duration_min', 'pec', 'worm_ff', 'n_sync_guide', 'sync_interval_s', 'pulse_guiding',
            'pose_source', 'alt_mean', 'roll_mean', 'm1_dps_hr', 'm2_dps_hr', 'm3_dps_hr', 'notes']
    use['start'] = use['start'].dt.strftime('%Y-%m-%d %H:%M')
    out = [f"# Usable tracking segments ({len(use)} of {len(df)}, >= {MIN_SEGMENT_MIN:.0f} min with a pose source)\n",
           "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in use.iterrows():
        out.append("| " + " | ".join(f"{r[c]:.1f}" if isinstance(r[c], float) else str(r[c]) for c in cols) + " |")
    return "\n".join(out) + "\n"


if __name__ == '__main__':
    from sessions import catalog_notes
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--log-dir', default=os.path.join(here, '..', 'logs', 'archive'))
    ap.add_argument('--csv', default=None, help='default: <log-dir>/catalog_segments.csv')
    ap.add_argument('--md', default=None, help='also write a markdown summary of the usable segments')
    a = ap.parse_args()
    df = catalog(a.log_dir, catalog_notes())
    csv = a.csv or os.path.join(a.log_dir, 'catalog_segments.csv')
    df.to_csv(csv, index=False)
    print(f"{len(df)} segments in {df['session'].nunique()} sessions, {int(df['usable'].sum())} usable -> {csv}")
    if a.md:
        open(a.md, 'w', encoding='utf-8').write(to_markdown(df))
        print(f"markdown summary -> {a.md}")
