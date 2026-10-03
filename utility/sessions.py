"""
Single registry of captured log sessions for the analysis notebooks (utility/sessions.toml).

Every notebook selects what to analyse with one line:

    SESSION = "jdm_Beta7.1_09_29_pulseguide"
    S = get_session(SESSION)              # -> S.log_filenames, S.log_dir, S.phd2, S.t_from, S.t_to, S.notes, S.paths

and list_sessions() shows everything available (filter by records='kf', contains='nebula', ...).

Adding new logs: copy them into the log directory (logs/archive), then

    uv run python utility/sessions.py --add-new

which appends a stub for each new session (detected date, driver version, guiding mode, record types, and a PHD2
guide log found next to it) without touching existing entries, comments or notes. Edit the notes afterwards.

Entry fields (all optional except logs):
    logs     list of file names / globs, relative to [defaults].log_dir (rotated parts: "alpaca.x_a*.log")
    phd2     PHD2 guide log for the same night, relative to log_dir
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
_TS = re.compile(r"^(\d{4}-\d\d-\d\d)T")
_VERSION = re.compile(r"==STARTUP== ALPACA BENRO POLARIS DRIVER (v[\w.]+(?: \w+ [\w.]+)?)")
RECORD_TAGS = {'pec': ' PECLOG ', 'sg': ' SGLOG {', 'kf': ' KFLOG {', 'pid': ' PIDLOG {', 'sync': 'SYNC GUIDING'}


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
    info = {k: v for k, v in e.items() if k not in ('logs', 'phd2', 't_from', 't_to', 'notes')}
    return Session(key=key, log_filenames=list(e['logs']), log_dir=log_dir, phd2=phd2,
                   t_from=e.get('t_from'), t_to=e.get('t_to'), notes=e.get('notes', ''), info=info)


def list_sessions(registry=DEFAULT_REGISTRY, records=None, contains=None):
    """Table of sessions (index = key). records: only sessions holding that record type ('kf', 'pec', 'sg', 'pid',
    'sync'); contains: case-insensitive text to find in the key or notes."""
    log_dir, sessions = load_registry(registry)
    rows = {}
    for key, e in sessions.items():
        s = get_session(key, registry)
        rows[key] = {'date': e.get('date', ''), 'driver': e.get('driver', ''), 'guiding': e.get('guiding', ''),
                     'records': ','.join(e.get('records', [])), 'phd2': bool(s.phd2 and os.path.exists(s.phd2)),
                     'files': len(s.paths), 'window': f"{s.t_from or ''}..{s.t_to or ''}" if (s.t_from or s.t_to) else '',
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
    out = {}
    for key in load_registry(registry)[1]:
        s = get_session(key, registry)
        v = value(s)
        if v:
            for p in s.paths:
                out.setdefault('alpaca.' + _session_key(p), v)
    return out


def catalog_notes(registry=DEFAULT_REGISTRY):
    """{catalog session ('alpaca.<name>', rotated parts merged): notes} for catalog_logs.catalog()."""
    return _catalog_map(lambda s: s.notes, registry)


def catalog_phd2(registry=DEFAULT_REGISTRY):
    """{catalog session: PHD2 guide log path} for extract_segments.extract_all()."""
    return _catalog_map(lambda s: s.phd2 if s.phd2 and os.path.exists(s.phd2) else None, registry)


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


def _scan_files(paths):
    date, version, found = None, None, set()
    for p in paths:
        with open(p, encoding='utf-8', errors='replace') as f:
            for line in f:
                if date is None:
                    m = _TS.match(line)
                    if m:
                        date = m[1]
                if version is None and '==STARTUP==' in line:
                    m = _VERSION.search(line)
                    if m:
                        version = m[1].strip()
                for tag, needle in RECORD_TAGS.items():
                    if tag not in found and needle in line:
                        found.add(tag)
    return date, version, sorted(found)


def scan_new(registry=DEFAULT_REGISTRY):
    """Sessions in log_dir that the registry doesn't cover yet: {key: entry dict}."""
    log_dir, sessions = load_registry(registry)
    covered = set()
    for key in sessions:
        covered.update(get_session(key, registry).paths)
    groups = {}
    for p in sorted(glob.glob(os.path.join(log_dir, 'alpaca.*.log'))):
        if os.path.basename(p) == 'alpaca.log' or p in covered:
            continue
        groups.setdefault(_session_key(p), []).append(p)
    new = {}
    for key, paths in groups.items():
        base = os.path.basename(paths[0])
        stem = re.sub(r"\.log$", "", base)
        rotated = _ROTATED.search(stem)
        logs = [f"{stem[:rotated.start()]}_{rotated.group()[1]}*.log"] if rotated else [base]   # rotated parts -> one glob
        date, version, records = _scan_files(paths)
        phd2 = sorted(glob.glob(os.path.join(log_dir, f"alpaca.{key}*PHD2_GuideLog*.txt")))
        guiding = []
        if phd2 or ('pec' in records and _has_single_axis_resid(paths)):
            guiding.append('pulse (PHD2)')
        if 'sync' in records:
            guiding.append('sync')
        entry = {'logs': logs, 'date': date or '', 'driver': version or '', 'guiding': ' + '.join(guiding) or 'none',
                 'records': records}
        if phd2:
            entry['phd2'] = os.path.basename(phd2[0])
        new[key] = entry
    return new


def _has_single_axis_resid(paths):
    pat = re.compile(r"'resid': \[(None, [-\d.]+|[-\d.]+, None)\]")
    for p in paths:
        with open(p, encoding='utf-8', errors='replace') as f:
            for line in f:
                if ' PECLOG {' in line and pat.search(line):
                    return True
    return False


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
