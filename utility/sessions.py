"""
Single registry of captured log sessions for the analysis notebooks (utility/sessions.toml).

Every notebook selects what to analyse with one line:

    SESSION = "jdm_Beta7.1_09_29_pulseguide"
    S = get_session(SESSION)              # -> S.log_filenames, S.log_dir, S.phd2, S.t_from, S.t_to, S.notes, S.paths

and list_sessions() shows everything available (filter by records='kf', contains='nebula', ...).

Adding new logs: copy them into the log directory (logs/archive), then

    uv run python utility/sessions.py --add-new

which appends a stub for each new session (detected date, driver version, guiding mode, record types, and the PHD2
guide log and N.I.N.A. logs of the same night) without touching existing entries, comments or notes. Edit the notes
afterwards.

A session is one observing night (local time shifted back 12 h, so a night past midnight stays one session). A driver
log that ran over several nights -- the host slept with the driver running, logged on waking as "Event loop lag
detected: slept N s" -- is split into one session per night, each windowed with t_from / t_to onto the shared log,
leaving out the nights without any records (or, in a log without records, without any client requests). Companion
logs are named after the driver log ("alpaca.<owner>_aN_PHD2_GuideLog_...txt", "alpaca.<owner>_aN_Nina_...log", owner
being the name before its _aN part), and are linked to the session of that owner on the night they started.

Entry fields (all optional except logs):
    logs     list of file names / globs, relative to [defaults].log_dir (rotated parts: "alpaca.x_a*.log")
    phd2     PHD2 guide log for the same night, relative to log_dir
    nina     list of N.I.N.A. logs for the same night, relative to log_dir
    t_from, t_to   default analysis window (local time as in the log)
    date, driver, guiding, records, notes   descriptive
"""
import argparse
import difflib
import glob
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REGISTRY = os.path.join(HERE, 'sessions.toml')
_ROTATED = re.compile(r"_[a-d]\d+$")
_TS = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?) ")
_VERSION = re.compile(r"==STARTUP== ALPACA BENRO POLARIS DRIVER (v[\w.]+(?: \w+ [\w.]+)?)")
RECORD_TAGS = {'pec': ' PECLOG ', 'sg': ' SGLOG {', 'kf': ' KFLOG {', 'pid': ' PIDLOG {', 'sync': 'SYNC GUIDING'}
_SLEPT = re.compile(r"(?:Event loop lag detected: +slept|Heartbeat lag detected: +pulse) ([\d.]+)s")   # on waking
HOST_SLEEP_S = 300              # an event loop "lag" this long is the host sleeping, not load: a session boundary
NIGHT_SHIFT = pd.Timedelta(hours=12)
_COMPANION = re.compile(r"(_[a-d]\d+)?(_(alpaca|PHD2_GuideLog.*|nina.*))?$", re.IGNORECASE)
_PHD2_START = re.compile(r"PHD2_GuideLog_(\d{4}-\d\d-\d\d)_(\d\d)(\d\d)(\d\d)")
_ANY_TS = re.compile(r"^(\d{4}-\d\d-\d\d)[T ](\d\d:\d\d:\d\d)")


@dataclass
class Session:
    key: str
    log_filenames: list
    log_dir: str
    phd2: str = None
    t_from: str = None
    t_to: str = None
    notes: str = ''
    info: dict = field(default_factory=dict)
    nina: list = field(default_factory=list)

    @property
    def paths(self):
        out = []
        for pat in self.log_filenames:
            out += sorted(glob.glob(os.path.join(self.log_dir, pat)))
        return out


def load_registry(registry=DEFAULT_REGISTRY):
    with open(registry, 'rb') as f:
        data = tomllib.load(f)
    log_dir = data.get('defaults', {}).get('log_dir', '../logs/archive')
    if not os.path.isabs(log_dir):
        log_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(registry)), log_dir))
    return log_dir, data.get('sessions', {})


def get_session(key, registry=DEFAULT_REGISTRY):
    log_dir, sessions = load_registry(registry)
    if key not in sessions:
        close = difflib.get_close_matches(key, list(sessions), n=5, cutoff=0.4)
        raise KeyError(f"No session {key!r} in {registry}. Close matches: {close}. See list_sessions().")
    e = sessions[key]
    phd2 = os.path.join(log_dir, e['phd2']) if e.get('phd2') else None
    info = {k: v for k, v in e.items() if k not in ('logs', 'phd2', 'nina', 't_from', 't_to', 'notes')}
    return Session(key=key, log_filenames=list(e['logs']), log_dir=log_dir, phd2=phd2,
                   t_from=e.get('t_from'), t_to=e.get('t_to'), notes=e.get('notes', ''), info=info,
                   nina=[os.path.join(log_dir, n) for n in e.get('nina', [])])


def list_sessions(registry=DEFAULT_REGISTRY, records=None, contains=None):
    """Table of sessions (index = key). records: only sessions holding that record type ('kf', 'pec', 'sg', 'pid',
    'sync'); contains: case-insensitive text to find in the key or notes."""
    log_dir, sessions = load_registry(registry)
    rows = {}
    for key, e in sessions.items():
        s = get_session(key, registry)
        rows[key] = {'date': e.get('date', ''), 'driver': e.get('driver', ''), 'guiding': e.get('guiding', ''),
                     'records': ','.join(e.get('records', [])), 'phd2': bool(s.phd2 and os.path.exists(s.phd2)),
                     'nina': sum(os.path.exists(n) for n in s.nina), 'files': len(s.paths), 'window': f"{s.t_from or ''}..{s.t_to or ''}" if (s.t_from or s.t_to) else '',
                     'notes': e.get('notes', '')}
    t = pd.DataFrame.from_dict(rows, orient='index')
    if t.empty:
        return t
    if records:
        t = t[t['records'].str.split(',').apply(lambda r: records in r)]
    if contains:
        c = contains.lower()
        t = t[t.index.str.lower().str.contains(c, regex=False) | t['notes'].str.lower().str.contains(c, regex=False)]
    return t.sort_values('date', kind='stable')


def _catalog_map(value, registry):
    """{catalog session: value}; where several windowed entries share a log (one per night), the value is instead a
    list of (t_from, t_to, value) for value_at() to pick from by time."""
    found = {}
    for key in load_registry(registry)[1]:
        s = get_session(key, registry)
        v = value(s)
        if v:
            for p in s.paths:
                found.setdefault('alpaca.' + _session_key(p), []).append((s.t_from, s.t_to, v))
    out = {}
    for k, entries in found.items():
        windowed = [e for e in entries if e[0] or e[1]]
        out[k] = windowed if len(windowed) > 1 else entries[0][2]
    return out


def value_at(value, t):
    """A catalog map value at time t (pd.Timestamp or str): the value itself, or from a list of (t_from, t_to, value)
    the one whose window holds t (None if none does)."""
    if not isinstance(value, list):
        return value
    t = pd.Timestamp(t)
    for t_from, t_to, v in value:
        if (t_from is None or t >= pd.Timestamp(t_from)) and (t_to is None or t <= pd.Timestamp(t_to)):
            return v
    return None


def catalog_notes(registry=DEFAULT_REGISTRY):
    """{catalog session ('alpaca.<name>', rotated parts merged): notes} for catalog_logs.catalog()."""
    return _catalog_map(lambda s: s.notes, registry)


def catalog_phd2(registry=DEFAULT_REGISTRY):
    """{catalog session: PHD2 guide log path} for extract_segments.extract_all()."""
    return _catalog_map(lambda s: s.phd2 if s.phd2 and os.path.exists(s.phd2) else None, registry)


def is_nina_log(path):
    """A N.I.N.A. log (kept next to the driver logs as alpaca.<owner>_aN_Nina_...log), not a driver log."""
    if re.search(r"_nina_", os.path.basename(path), re.IGNORECASE):
        return True
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return 'N.I.N.A.' in f.read(512)
    except OSError:
        return False


def driver_logs(log_dir):
    """The archived driver logs in log_dir (alpaca.*.log, less the live alpaca.log and N.I.N.A. logs)."""
    return [p for p in sorted(glob.glob(os.path.join(log_dir, 'alpaca.*.log')))
            if os.path.basename(p) != 'alpaca.log' and not is_nina_log(p)]


_LATITUDE = re.compile(r"'SiteLatitude': '(-?[\d.]+)'")


def site_latitude(key, registry=DEFAULT_REGISTRY, default=None):
    """Site latitude (deg) a client set during the session (its last SiteLatitude in the logs), else `default`.
    key: registry key, with or without the 'alpaca.' prefix of catalog session names."""
    key = key[len('alpaca.'):] if key.startswith('alpaca.') else key
    try:
        paths = get_session(key, registry).paths
    except KeyError:
        return default
    found = []
    for p in paths:
        with open(p, encoding='utf-8', errors='replace') as f:
            found += _LATITUDE.findall(f.read())
    return float(found[-1]) if found else default


def _session_key(path):
    name = re.sub(r"\.log(\.\d+)?$", "", os.path.basename(path))
    name = _ROTATED.sub('', name)
    return name[len('alpaca.'):] if name.startswith('alpaca.') else name


_SINGLE_AXIS_RESID = re.compile(r"'resid': \[(None, [-\d.]+|[-\d.]+, None)\]")


def _owner(path):
    """Name shared by a driver log and its PHD2 / N.I.N.A. companions: the part before _aN (and _alpaca, _PHD2_..., _Nina_...)."""
    stem = re.sub(r"\.(log|txt)$", "", os.path.basename(path))
    stem = stem[len('alpaca.'):] if stem.startswith('alpaca.') else stem
    return stem[:_COMPANION.search(stem).start()]


def _night(t):
    """Observing night of a local time: the date of the evening it began."""
    return (pd.Timestamp(t) - NIGHT_SHIFT).date()


def _scan_pieces(paths):
    """Runs of a driver log broken at each driver start and host sleep: [{start, end, version, records, requests,
    single_axis_resid}] in time order. A run's start is its first line; after a sleep that is the wake-up line."""
    pieces, cur, version = [], None, None
    for p in paths:
        with open(p, encoding='utf-8', errors='replace') as f:
            for line in f:
                m = _TS.match(line)
                if not m:
                    continue
                t = pd.Timestamp(m[1])
                if '==STARTUP==' in line and (v := _VERSION.search(line)):
                    version, cur = v[1].strip(), None
                elif (s := _SLEPT.search(line)) and float(s[1]) >= HOST_SLEEP_S:
                    cur = None
                if cur is None:
                    cur = {'start': t, 'end': t, 'version': version, 'records': set(), 'requests': 0,
                           'single_axis_resid': False}
                    pieces.append(cur)
                cur['end'], cur['version'] = t, cur['version'] or version
                for tag, needle in RECORD_TAGS.items():
                    if needle in line:
                        cur['records'].add(tag)
                if ' -> PUT ' in line or ' -> GET ' in line:
                    cur['requests'] += 1
                if ' PECLOG {' in line and _SINGLE_AXIS_RESID.search(line):
                    cur['single_axis_resid'] = True
    return pieces


def _nights(paths):
    """The log's sessions, one per observing night: [{t_from, t_to, night, version, records, single_axis_resid}],
    and whether they cover the whole log (no night or run left out, so no window is needed)."""
    pieces = _scan_pieces(paths)
    kept = ([p for p in pieces if p['records']] or [p for p in pieces if p['requests']] or pieces)
    out = []
    for p in kept:
        n = _night(p['start'])
        if out and out[-1]['night'] == n:
            o = out[-1]
            o['t_to'], o['records'] = p['end'], o['records'] | p['records']
            o['single_axis_resid'] |= p['single_axis_resid']
            o['version'] = o['version'] or p['version']
        else:
            out.append({'t_from': p['start'], 't_to': p['end'], 'night': n, 'version': p['version'],
                        'records': set(p['records']), 'single_axis_resid': p['single_axis_resid']})
    return out, len(out) == 1 and len(kept) == len(pieces)


def _companion_start(path):
    """When a PHD2 guide log (from its name) or a N.I.N.A. log (its first timestamped line) began."""
    m = _PHD2_START.search(os.path.basename(path))
    if m:
        return pd.Timestamp(f"{m[1]} {m[2]}:{m[3]}:{m[4]}")
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = _ANY_TS.match(line)
            if m:
                return pd.Timestamp(f"{m[1]} {m[2]}")
    return None


def scan_new(registry=DEFAULT_REGISTRY):
    """Sessions in log_dir that the registry doesn't cover yet: {key: entry dict}."""
    log_dir, sessions = load_registry(registry)
    covered, companions_used = set(), set()
    for key in sessions:
        s = get_session(key, registry)
        covered.update(s.paths)
        companions_used.update([s.phd2] if s.phd2 else [])
        companions_used.update(s.nina)
    groups = {}
    for p in driver_logs(log_dir):
        if p not in covered:
            groups.setdefault(_session_key(p), []).append(p)
    phd2_logs = sorted(glob.glob(os.path.join(log_dir, 'alpaca.*PHD2_GuideLog*.txt')))
    nina_logs = [p for p in sorted(glob.glob(os.path.join(log_dir, 'alpaca.*.log'))) if is_nina_log(p)]

    def companions(candidates, owner, night, whole):
        return [p for p in candidates if p not in companions_used and _owner(p) == owner
                and (whole or ((t := _companion_start(p)) is not None and _night(t) == night))]

    new = {}
    for key, paths in groups.items():
        base = os.path.basename(paths[0])
        stem = re.sub(r"\.log$", "", base)
        rotated = _ROTATED.search(stem)
        logs = [f"{stem[:rotated.start()]}_{rotated.group()[1]}*.log"] if rotated else [base]   # rotated parts -> one glob
        owner = _owner(paths[0])
        nights, whole = _nights(paths)
        for n in nights:
            phd2 = companions(phd2_logs, owner, n['night'], whole)
            nina = companions(nina_logs, owner, n['night'], whole)
            records = sorted(n['records'])
            guiding = []
            if phd2 or ('pec' in records and n['single_axis_resid']):
                guiding.append('pulse (PHD2)')
            if 'sync' in records:
                guiding.append('sync')
            entry = {'logs': logs, 'date': str(n['night']), 'driver': n['version'] or '',
                     'guiding': ' + '.join(guiding) or 'none', 'records': records}
            if not whole:       # one of several nights in the log, or a night with idle runs left out: window it
                entry['t_from'] = n['t_from'].floor('min').strftime('%Y-%m-%d %H:%M')
                entry['t_to'] = n['t_to'].ceil('min').strftime('%Y-%m-%d %H:%M')
            if phd2:
                entry['phd2'] = os.path.basename(phd2[0])
            if nina:
                entry['nina'] = [os.path.basename(p) for p in nina]
            companions_used.update(phd2[:1] + nina)
            k = key if whole else _night_key(owner, n['night'])
            while k in new or k in sessions:
                k += '_'
            new[k] = entry
    return new


def _night_key(owner, night):
    """Session key of one night of a multi-night log: the owner with its _MM_DD date (if any) set to the night's."""
    mm_dd = night.strftime('%m_%d')
    key, n = re.subn(r"_\d\d_\d\d(?=_|$)", f"_{mm_dd}", owner, count=1)
    return key if n else f"{owner}_{mm_dd}"


def _toml_str(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def add_new(registry=DEFAULT_REGISTRY, notes=None):
    """Append stubs for new sessions to the registry (existing text untouched). notes: {session key or
    'alpaca.<key>': note} to pre-fill. Returns the keys added."""
    new = scan_new(registry)
    notes = notes or {}
    blocks = []
    for key, e in new.items():
        note = notes.get(key) or notes.get(f'alpaca.{key}', '')
        lines = [f'\n[sessions.{_toml_str(key)}]',
                 f"logs = [{', '.join(_toml_str(x) for x in e['logs'])}]"]
        if e.get('phd2'):
            lines.append(f"phd2 = {_toml_str(e['phd2'])}")
        if e.get('nina'):
            lines.append(f"nina = [{', '.join(_toml_str(x) for x in e['nina'])}]")
        for w in ('t_from', 't_to'):
            if e.get(w):
                lines.append(f"{w} = {_toml_str(e[w])}")
        lines += [f"date = {_toml_str(e['date'])}", f"driver = {_toml_str(e['driver'])}",
                  f"guiding = {_toml_str(e['guiding'])}",
                  f"records = [{', '.join(_toml_str(r) for r in e['records'])}]",
                  f"notes = {_toml_str(note)}"]
        blocks.append('\n'.join(lines) + '\n')
    if blocks:
        with open(registry, 'a', encoding='utf-8') as f:
            f.write(''.join(blocks))
    return list(new)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Registry of captured log sessions (utility/sessions.toml).')
    ap.add_argument('--add-new', action='store_true', help='append stubs for sessions in log_dir not yet registered')
    ap.add_argument('--list', action='store_true', help='print the registry as a table')
    ap.add_argument('--registry', default=DEFAULT_REGISTRY)
    a = ap.parse_args()
    if a.add_new:
        added = add_new(a.registry)
        print(f"added {len(added)} session(s) to {a.registry}: " + ', '.join(added) if added else 'nothing new')
    if a.list or not a.add_new:
        with pd.option_context('display.width', 250, 'display.max_colwidth', 70, 'display.max_rows', 500):
            print(list_sessions(a.registry))
