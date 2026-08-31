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
                if ' PECLOG ' not in line:
                    continue
                rec = parse_payload_line(line, "PECLOG")
                if rec is None:
                    continue
                rows.append(rec)

    if not rows:
        raise ValueError(f"No PECLOG lines found in {paths!r}")

    return _finalize_log_df(rows), pec_config


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
