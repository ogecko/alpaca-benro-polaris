"""
Shared helpers for the utility/analyse_*.ipynb notebooks: resolving rotated driver log
files (optionally relative to a log_dir), and parsing the '<TAG> {dict}' log lines the
driver emits for PECLOG (control.py's _pec_log()) and KFLOG/PIDLOG (control.py's
observe()/errsignal() logging). analyse_pec.ipynb and analyse_kf_pid.ipynb both load off
the same underlying log files and payload convention -- analyse_pec.ipynb's outcome
overview even loads KFLOG as an optional secondary diagnostic -- so keeping this in one
place means a fix (e.g. to the None/bool handling below) only has to happen once.
"""
import os
import re
import ast
from glob import glob

import pandas as pd


def _has_glob_magic(s: str) -> bool:
    """True if a string contains glob wildcard characters (*, ?, [...])."""
    return any(ch in s for ch in "*?[")


def _join_log_dir(item, log_dir):
    """Join a bare filename/glob onto log_dir, but pass an absolute path through unchanged."""
    return item if os.path.isabs(item) else os.path.join(log_dir, item)


def resolve_log_files(pattern, log_dir='.'):
    """
    Expand a glob pattern (or accept an explicit list) into the set of rotated driver
    logs to load. A multi-hour capture routinely spans several rotated files regardless
    of the configured per-file size cap, so this is the normal path, not a special case.

    Accepts a bare glob string (e.g. 'alpaca.log*' -- filtered to just
    'alpaca.log'/'alpaca.log.<N>', excluding renamed/archived variants like
    'alpaca.mark_*.log' and stray ':Zone.Identifier' sidecar files), or a list where
    each entry is either a literal filename or itself a glob pattern, e.g.
    ['alpaca.soak_nopec_Beta4.3_08_29n*.log'] or a mix of explicit files and globs --
    useful when a soak run's files don't follow the default 'alpaca.log[.N]' rotation
    naming that the bare-glob form filters to. A literal entry with no wildcard is
    passed through unexpanded so a typo'd filename still surfaces as a clear
    FileNotFoundError downstream, rather than silently vanishing the way an unmatched
    glob would.

    Every entry is joined onto log_dir unless it's already absolute, so log_filenames can
    be shortened to bare filenames/globs by pointing log_dir at the session's log
    directory (e.g. log_dir='../logs/logs') instead of repeating it in every entry.
    """
    if isinstance(pattern, str):
        candidates = glob(_join_log_dir(pattern, log_dir))
        return sorted(p for p in candidates if re.search(r"alpaca\.log(\.\d+)?$", os.path.basename(p)))

    paths = []
    for item in pattern:
        full = _join_log_dir(item, log_dir)
        if _has_glob_magic(item):
            paths.extend(sorted(glob(full)))
        else:
            paths.append(full)
    return paths


def parse_val(v):
    v = v.strip()
    try:
        return float(v)
    except ValueError:
        return v


def parse_payload_line(line, tag):
    """
    Split 'TIMESTAMP INFO <TAG> {dict}' and literal_eval the trailing dict, flattening any
    list-valued field into '<key>_<i+1>' columns -- the shared axis-indexed convention used
    by PECLOG ('resid', 'ra_model'/'dec_model', ... -> 1=RA, 2=Dec) and KFLOG/PIDLOG
    ('θ_meas', ... -> 1=M1, 2=M2, 3=M3).
    """
    if f" {tag} " not in line:
        return None
    ts, _, body = line.partition(f" {tag} ")
    ts = ts.split(" INFO")[0].strip()
    try:
        payload = ast.literal_eval(body.strip())
    except (ValueError, SyntaxError):
        return None
    rec = {"timestamp": ts}
    for key, val in payload.items():
        if isinstance(val, list):
            for i, v in enumerate(val):
                # None (e.g. PECLOG's resid/guide fields on a cycle where only one axis
                # updated) must not be stringified to "None" first -- float("None") raises,
                # so parse_val would otherwise leave the literal string "None" sitting in a
                # numeric column.
                rec[f"{key}_{i+1}"] = float("nan") if v is None else parse_val(str(v))
        else:
            # val is already properly typed by ast.literal_eval() above (bool/int/float/str)
            # -- stringifying it first and re-parsing via parse_val() (as the list branch
            # above does) turns a real Python bool into the literal string "True"/"False",
            # which silently breaks any later boolean mask like peclog_df[peclog_df.pec_active]
            # (pandas treats a non-bool-dtype column used as an indexer as a list of column
            # names, not a row mask -- hence the confusing "None of [Index(['True', ...])] are
            # in the columns" KeyError instead of a type error).
            rec[key] = float("nan") if val is None else val
    return rec


_LEGACY_PECLOG_FIELD_MAP = {
    "R2": "r2", "rmse": "rmse", "Rate": "fit_rate", "Guide": "pec_accum",
    "Accum": "total_accum", "RA_model": "ra_model", "Dec_model": "dec_model", "lambda": "lambda",
}


def parse_peclog_legacy(line):
    """
    Parse the pre-dict PECLOG format used by older driver versions, e.g.:
    'PECLOG  n,2,TOO_FEW_OBS,TOO_FEW_OBS, | R2,-2.000,-2.000, | rmse,0.3365,0.7011, |
    Rate,-3.2267,+6.7222, | Guide,-0.86894,+1.81028, | Accum,-0.86894,+1.81028, |
    Pos,205.79,17.30,-0.68, | RA_model,-3.2267,0.0006,0.0012, | Dec_model,+6.7222,0.0013,0.0026, |
    lambda,0.98740,0.98740'

    Field names map onto the modern dict format's keys (see parse_payload_line()):
    R2->r2, rmse->rmse, Rate->fit_rate, Guide->pec_accum, Accum->total_accum, Pos->az/alt/roll,
    RA_model/Dec_model->ra_model/dec_model, lambda->lambda -- checked consistent across every
    old-format session in this project's logs, no field-name variants found. This format
    predates a logged 'resid' field entirely -- see parse_sync_guiding_residual_line(), which
    recovers it from a separate, always-present line and must be merged in by timestamp by the
    caller (load_pec() does this automatically).
    """
    if ' PECLOG ' not in line or ' PECLOG {' in line:
        return None
    ts, _, body = line.partition(' PECLOG ')
    ts = ts.split(' INFO')[0].strip()

    rec = {'timestamp': ts}
    for field in body.strip().split('|'):
        parts = [p.strip() for p in field.split(',') if p.strip() != '']
        if not parts:
            continue
        name, vals = parts[0], parts[1:]
        if name == 'n':
            if len(vals) < 3:
                return None
            rec['n'] = int(float(vals[0]))
            rec['inhibit_1'], rec['inhibit_2'] = vals[1], vals[2]
        elif name == 'Pos':
            if len(vals) < 3:
                return None
            rec['az'], rec['alt'], rec['roll'] = (parse_val(v) for v in vals[:3])
        elif name in _LEGACY_PECLOG_FIELD_MAP:
            key = _LEGACY_PECLOG_FIELD_MAP[name]
            for i, v in enumerate(vals, start=1):
                rec[f'{key}_{i}'] = parse_val(v)
    return rec if len(rec) > 1 else None


_SYNC_GUIDING_RESID_RE = re.compile(
    r'SYNC GUIDING\s+Ra\s+([+-]\d+)d(\d+)\'([\d.]+)"\s*,\s*Dec\s+([+-]\d+)d(\d+)\'([\d.]+)"\s+Residuals'
)


def _dms_to_deg(sign_deg, minutes, seconds):
    """Inverse of shr.py's deg2dms() -- sign_deg carries the sign (e.g. '-000')."""
    sign = -1.0 if sign_deg.strip().startswith('-') else 1.0
    return sign * (abs(int(sign_deg)) + int(minutes) / 60 + float(seconds) / 3600)


def parse_sync_guiding_residual_line(line):
    """
    Parse the always-present '->> Polaris: SYNC GUIDING Ra <dms>, Dec <dms> Residuals' line
    (control.py's process_guide_sync(), logged unconditionally regardless of Config.advanced_pec
    or PECLOG format/version) back into decimal-degree ra_resid_deg/dec_resid_deg -- the inverse
    of shr.py's deg2dms(). This is the only place a legacy (pre-dict-format) PECLOG session's
    'resid' survives; parse_peclog_legacy()'s own payload doesn't carry it.
    """
    if 'SYNC GUIDING' not in line or 'too large' in line:
        return None
    ts = line.split(' INFO')[0].strip()
    m = _SYNC_GUIDING_RESID_RE.search(line)
    if not m:
        return None
    return {
        'timestamp': ts,
        'ra_resid_deg': _dms_to_deg(m.group(1), m.group(2), m.group(3)),
        'dec_resid_deg': _dms_to_deg(m.group(4), m.group(5), m.group(6)),
    }


def parse_pecconfig(line):
    """Extract the PECCONFIG line emitted once per session, if present."""
    m = re.search(
        r'PECCONFIG mode,(\w+),n_harmonics,(\d+),T,([\d.]+),tau_sec,([\d.]+),min_dt_sec,([\d.]+)',
        line
    )
    if not m:
        return None
    mode, H, T, tau, min_dt = m.groups()
    return dict(mode=mode, H=int(H), T=float(T), tau=float(tau), min_dt=float(min_dt))


def _finalize_log_df(rows):
    """
    Common tail of every loader below: typed timestamp, full-row dedup, t_sec/gap_sec.
    Dedup is on the FULL row, not just timestamp -- a log tag can carry two genuinely
    distinct messages (e.g. a delayed one immediately followed by a fresh one) that round to
    the same millisecond string, and deduping on timestamp alone would silently discard one
    of them. A true duplicate (e.g. from overlapping rotated log segments) still has
    identical values in every column and is still caught here.
    """
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp", kind="stable").drop_duplicates().reset_index(drop=True)
    df["t_sec"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds()
    df["gap_sec"] = df["timestamp"].diff().dt.total_seconds()
    return df


def load_pec(log_filenames, log_dir='.'):
    """
    Parse PECCONFIG/PECLOG lines from one or more rotated driver logs into a single
    DataFrame, plus the session's pec_config dict. Accepts a single filename/path, a glob
    pattern (e.g. 'alpaca.log*'), or an explicit list of filenames/paths/globs -- all rows
    are concatenated and re-sorted by timestamp, so file order/naming doesn't matter. The
    first PECCONFIG line found (across all files, in resolution order) wins, since it's
    emitted once per session and shouldn't change across a session's rotated logs. See
    resolve_log_files() for how log_filenames is resolved against log_dir.

    Transparently handles both the modern 'PECLOG {dict}' format and the legacy
    comma-separated format used by older driver versions (see parse_peclog_legacy()) -- a
    session can even mix both if its rotated logs span a driver upgrade. The legacy format
    predates a logged 'resid' field, so for any row that comes back without one, resid_1/2 is
    backfilled from the separate, always-present 'SYNC GUIDING ... Residuals' line by
    nearest-timestamp match (within 2s; see parse_sync_guiding_residual_line()).

    Raises if no PECLOG lines are found at all -- PECLOG is the primary signal for whichever
    notebook calls this, so silently returning an empty result would hide a real problem
    (wrong log, wrong Config.log_pec) rather than surface it. A caller for whom PECLOG is
    only a secondary/optional signal (e.g. analyse_kf_pid.ipynb's exposure subgrouping)
    should catch ValueError itself.
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    if not paths:
        raise FileNotFoundError(f"No log files matched: {log_filenames!r} (log_dir={log_dir!r})")

    rows = []
    sync_resid_rows = []
    pec_config = None
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        if os.path.getsize(log_path) == 0:
            raise ValueError(f"log_path exists but is empty (0 bytes): {log_path!r}")
        # encoding='utf-8': the driver's RotatingFileHandler writes utf-8 explicitly (log.py), but
        # open() without an explicit encoding falls back to the OS default -- cp1252 on Windows --
        # which can silently corrupt any non-ASCII content instead of raising.
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                if 'PECCONFIG' in line:
                    if pec_config is None:
                        cfg = parse_pecconfig(line)
                        if cfg is not None:
                            pec_config = cfg
                    continue
                if ' PECLOG {' in line:
                    rec = parse_payload_line(line, "PECLOG")
                    if rec is not None:
                        rows.append(rec)
                    continue
                if ' PECLOG ' in line:
                    rec = parse_peclog_legacy(line)
                    if rec is not None:
                        rows.append(rec)
                    continue
                if 'SYNC GUIDING' in line:
                    sr = parse_sync_guiding_residual_line(line)
                    if sr is not None:
                        sync_resid_rows.append(sr)

    if not rows:
        raise ValueError(f"No PECLOG lines found in {paths!r}")

    df = _finalize_log_df(rows)

    if sync_resid_rows:
        resid_df = pd.DataFrame(sync_resid_rows)
        resid_df['timestamp'] = pd.to_datetime(resid_df['timestamp'])
        resid_df = resid_df.sort_values('timestamp', kind='stable').reset_index(drop=True)
        merged = pd.merge_asof(df[['timestamp']], resid_df, on='timestamp',
                                direction='nearest', tolerance=pd.Timedelta('2s'))
        # deg -> arcmin, matching the modern PECLOG payload's own resid convention
        legacy_resid_1 = merged['ra_resid_deg'] * 60
        legacy_resid_2 = merged['dec_resid_deg'] * 60
        if 'resid_1' in df.columns:
            df['resid_1'] = df['resid_1'].fillna(legacy_resid_1)
            df['resid_2'] = df['resid_2'].fillna(legacy_resid_2)
        else:
            df['resid_1'] = legacy_resid_1
            df['resid_2'] = legacy_resid_2

    return df, pec_config


_TRACKING_BOUNDARY_RE = re.compile(
    r"PUT /api/v1/telescope/0/(slewtocoordinatesasync|slewtoaltazasync|slewtocoordinates|"
    r"slewtoaltaz|tracking|park|unpark|findhome|abortslew)\b"
)


def find_tracking_segments(log_filenames, log_dir='.', min_duration_min=20):
    """
    Split one or more rotated driver logs into continuous-tracking segments, treating any
    slew/goto, tracking on/off, park/unpark, findhome, or abortslew REST call as a boundary --
    a real capture session routinely includes several of these (retargeting, dithering,
    meridian flips), and a segment spanning one would inject a large non-periodic-error
    discontinuity into any cumulative-motor-angle analysis (see
    docs/pec_theta_space_plan.md Phase 0.2). Returns a list of (start_ts, end_ts,
    duration_min) tuples for segments at least min_duration_min long, sorted chronologically;
    shorter segments are dropped rather than returned as noise.

    This only looks at REST-command timestamps, not driver behavior, so it can't tell a
    boundary event that actually changed the mount's target from one that didn't (e.g. a
    tracking-on call confirming an already-on state). In practice these cluster within
    seconds of the real retargeting event they're part of, so they don't meaningfully split
    an otherwise-clean segment on their own; only genuine gaps between clusters do.
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    if not paths:
        raise FileNotFoundError(f"No log files matched: {log_filenames!r} (log_dir={log_dir!r})")

    ts_re = re.compile(r'^(\S+)')
    boundaries = []
    first_ts = last_ts = None
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                m = ts_re.match(line)
                if not m:
                    continue
                ts = m.group(1)
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
                if _TRACKING_BOUNDARY_RE.search(line):
                    boundaries.append(ts)

    if first_ts is None:
        return []

    edges = pd.to_datetime(sorted(set([first_ts] + boundaries + [last_ts])))

    segments = []
    for start, end in zip(edges[:-1], edges[1:]):
        dur_min = (end - start).total_seconds() / 60
        if dur_min >= min_duration_min:
            segments.append((start, end, dur_min))
    return segments


def load_kf_pid(log_filenames, log_dir='.'):
    """
    Parse KFLOG and PIDLOG lines from one or more rotated driver logs (Config.log_position =
    true) into two DataFrames. Accepts a single filename/path, a glob pattern (e.g.
    'alpaca.log*'), or an explicit list of filenames/paths -- all rows are concatenated and
    re-sorted by timestamp, so file order/naming doesn't matter. See resolve_log_files() for
    how log_filenames is resolved against log_dir.

    Returns two empty DataFrames (never raises) when neither tag is found -- KFLOG/PIDLOG
    are gated together by the same Config.log_position flag and aren't present in every
    capture, so whether that's expected or a problem depends on the caller (it's optional in
    analyse_pec.ipynb's KFLOG diagnostic, but the primary signal in analyse_kf_pid.ipynb,
    which raises itself if both come back empty).
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    if not paths:
        raise FileNotFoundError(f"No log files matched: {log_filenames!r} (log_dir={log_dir!r})")
    kf_rows, pid_rows = [], []
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        # encoding='utf-8' is required: the driver writes θ/ω/Δ/α as UTF-8 (log.py's
        # RotatingFileHandler is pinned to utf-8), but open() without an explicit encoding
        # falls back to the OS default -- cp1252 on Windows -- which silently mangles those
        # keys instead of raising, so columns like "θ_sp_1" quietly never get created.
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                if " KFLOG " in line:
                    rec = parse_payload_line(line, "KFLOG")
                    if rec: kf_rows.append(rec)
                elif " PIDLOG " in line:
                    rec = parse_payload_line(line, "PIDLOG")
                    if rec: pid_rows.append(rec)

    kf_df  = _finalize_log_df(kf_rows)  if kf_rows  else pd.DataFrame()
    pid_df = _finalize_log_df(pid_rows) if pid_rows else pd.DataFrame()
    return kf_df, pid_df
