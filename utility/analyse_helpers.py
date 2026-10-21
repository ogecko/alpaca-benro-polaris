"""
Shared helpers for the utility/analyse_*.ipynb notebooks: resolving rotated driver log
files (optionally relative to a log_dir), and parsing the '<TAG> {dict}' log lines the
driver emits for PECLOG (control.py's _pec_log()) and KFLOG/PIDLOG (control.py's
observe()/errsignal() logging). analyse_pec.ipynb and analyse_kf_pid.ipynb both load off
the same underlying log files and payload convention -- analyse_pec.ipynb's outcome
overview even loads KFLOG as an optional secondary diagnostic -- so keeping this in one
place means a fix (e.g. to the None/bool handling below) only has to happen once.
Also the goto response analysis (utility/goto_response.py runs) for analyse_goto_response.ipynb.
"""
import os
import re
import ast
import math
import datetime
from glob import glob

import numpy as np
import pandas as pd
from scipy import signal as _scipy_signal


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
    ('θ_meas', ... -> 1=M1, 2=M2, 3=M3). A dict-valued field (PIDLOG's 'blc') is flattened the same way under
    '<key>_<subkey>' (e.g. 'blc_adj_1'): left as a dict, the column is unhashable and the loaders' dedup fails.
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
    items = list(payload.items())
    while items:
        key, val = items.pop(0)
        if isinstance(val, dict):
            items[:0] = [(f"{key}_{k}", v) for k, v in val.items()]
        elif isinstance(val, list):
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
    (control.py's process_guide_sync(), logged unconditionally regardless of Config.advanced_pec_drift
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


_SITE_LOCATION_RE = re.compile(
    r"Site lat = (-?[\d.]+) \([^)]*\) \| lon = (-?[\d.]+) \([^)]*\)\."
)


def parse_site_location(line):
    """Extract site lat/lon (decimal degrees) from the driver's startup 'Site lat = ... |
    lon = ...' log line, if present on this line."""
    m = _SITE_LOCATION_RE.search(line)
    if not m:
        return None
    return dict(lat_deg=float(m.group(1)), lon_deg=float(m.group(2)))


def find_site_location(log_filenames, log_dir='.'):
    """
    Scan one or more rotated driver logs for the first 'Site lat = ... | lon = ...' line and
    return {'lat_deg':..., 'lon_deg':...}, or None if not present (this line isn't written by
    every driver version/config, e.g. it's absent when the site is left at its default and
    never explicitly set for that session). Needed to convert a PECLOG resid (RA/Dec) into an
    Alt/Az/theta delta via the parallactic angle -- see docs/study_pec_motor_space_v2.md Phase 0.1.
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    if not paths:
        raise FileNotFoundError(f"No log files matched: {log_filenames!r} (log_dir={log_dir!r})")
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                loc = parse_site_location(line)
                if loc is not None:
                    return loc
    return None


def parse_pecconfig(line):
    """The PECCONFIG line emitted once per session: {'drift', 'worm'} (the PEC Drift / Worm Gear Correction switches,
    None in logs before they were split), {'tau', 'min_dt'} (seconds), or None. Logs from before v2.2 Beta 7 also
    name the model ('mode' rls/ema, harmonics, period); RLS has since been removed, so only EMA sessions replay as
    they ran."""
    m = re.search(r'PECCONFIG (?:drift,(True|False),worm,(True|False),)?(?:mode,(\w+),n_harmonics,\d+,T,[\d.]+,)?'
                  r'tau_sec,([\d.]+),min_dt_sec,([\d.]+)', line)
    if not m:
        return None
    drift, worm, mode, tau, min_dt = m.groups()
    flag = lambda v: None if v is None else v == 'True'
    return dict(drift=flag(drift), worm=flag(worm), mode=mode or 'ema', tau=float(tau), min_dt=float(min_dt))


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
    predates a logged 'resid' field, so for every legacy-format row resid_1/2 is
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
        # which can silently corrupt any non-ASCII content instead of raising. errors='replace':
        # some old logs carry an occasional genuinely non-UTF-8 byte (e.g. a '°' written as
        # Latin-1 by an older tool/version) -- one bad byte shouldn't abort parsing an otherwise
        # good multi-hour file, and the replacement char only ever lands in free-text content,
        # never in a field this module actually extracts.
        with open(log_path, encoding="utf-8", errors="replace") as f:
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
                        rec['_legacy'] = True
                        rows.append(rec)
                    continue
                if 'SYNC GUIDING' in line:
                    sr = parse_sync_guiding_residual_line(line)
                    if sr is not None:
                        sync_resid_rows.append(sr)

    if not rows:
        raise ValueError(f"No PECLOG lines found in {paths!r}")

    df = _finalize_log_df(rows)
    legacy = df.pop('_legacy').fillna(False).astype(bool) if '_legacy' in df.columns else None

    # Only legacy rows lack a logged resid; on a modern row a None resid means the pulse was on
    # the other axis, and filling it from a nearby sync would count that sync again.
    if sync_resid_rows and legacy is not None and legacy.any():
        resid_df = pd.DataFrame(sync_resid_rows)
        resid_df['timestamp'] = pd.to_datetime(resid_df['timestamp'])
        resid_df = resid_df.sort_values('timestamp', kind='stable').reset_index(drop=True)
        merged = pd.merge_asof(df[['timestamp']], resid_df, on='timestamp',
                                direction='nearest', tolerance=pd.Timedelta('2s'))
        # deg -> arcmin, matching the modern PECLOG payload's own resid convention
        legacy_resid_1 = merged['ra_resid_deg'] * 60
        legacy_resid_2 = merged['dec_resid_deg'] * 60
        if 'resid_1' in df.columns:
            df.loc[legacy, 'resid_1'] = df.loc[legacy, 'resid_1'].fillna(legacy_resid_1[legacy])
            df.loc[legacy, 'resid_2'] = df.loc[legacy, 'resid_2'].fillna(legacy_resid_2[legacy])
        else:
            df['resid_1'] = legacy_resid_1.where(legacy)
            df['resid_2'] = legacy_resid_2.where(legacy)

    return df, pec_config


def load_sync_guiding_residuals(log_filenames, log_dir='.'):
    """
    Parse every '->> Polaris: SYNC GUIDING Ra <dms>, Dec <dms> Residuals' line into a
    DataFrame with timestamp/resid_1 (RA, arcmin)/resid_2 (Dec, arcmin) -- same convention as
    PECLOG's own resid_1/resid_2. Unlike load_pec(), this works with Config.advanced_pec_drift off
    (a session with PEC disabled, sync-guiding enabled -- e.g. for a clean, uncontaminated
    ground-truth capture per docs/study_pec_motor_space_v2.md): process_guide_sync() logs this
    line unconditionally, whether or not PECLOG exists at all for the session.

    Raises if no such lines are found -- if you have PECLOG for this session, use load_pec()
    instead, which already backfills resid this same way for legacy-format logs and carries
    the rest of PECLOG's fields too; this is for when there's no PECLOG at all to load.
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    if not paths:
        raise FileNotFoundError(f"No log files matched: {log_filenames!r} (log_dir={log_dir!r})")
    rows = []
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if 'SYNC GUIDING' not in line:
                    continue
                sr = parse_sync_guiding_residual_line(line)
                if sr is not None:
                    rows.append(sr)
    if not rows:
        raise ValueError(f"No 'SYNC GUIDING ... Residuals' lines found in {paths!r}")
    df = pd.DataFrame(rows)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp', kind='stable').drop_duplicates().reset_index(drop=True)
    df['resid_1'] = df.pop('ra_resid_deg') * 60
    df['resid_2'] = df.pop('dec_resid_deg') * 60
    df['t_sec'] = (df['timestamp'] - df['timestamp'].iloc[0]).dt.total_seconds()
    return df


def load_sglog(log_filenames, log_dir='.'):
    """
    Parse 'SGLOG {dict}' lines (control.py's process_guide_sync(), added specifically so a
    session with PEC -- and hence PECLOG -- off, and log_position off to avoid KFLOG/PIDLOG's
    much higher control-tick-rate log volume, still carries enough for theta-space analysis)
    into a DataFrame with az/alt/roll, resid_1/2, total_accum_1/2, and theta_raw_1/2/3 (the
    real motor position at the moment of each sync -- no nearest-KFLOG-sample matching needed,
    unlike load_sync_guiding_residuals() + derive_theta_from_sync_residuals() for logs that
    predate SGLOG). Use derive_theta_from_sglog() on the result, not
    derive_theta_from_total_accum() -- SGLOG carries no 'n' PEC-model-reset counter for that
    function's internal segment splitting to key off.

    Raises if no SGLOG lines are found -- for an older log without it, use
    load_sync_guiding_residuals() + derive_theta_from_sync_residuals() instead.
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    if not paths:
        raise FileNotFoundError(f"No log files matched: {log_filenames!r} (log_dir={log_dir!r})")
    rows = []
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if ' SGLOG {' not in line:
                    continue
                rec = parse_payload_line(line, "SGLOG")
                if rec is not None:
                    rows.append(rec)
    if not rows:
        raise ValueError(f"No SGLOG lines found in {paths!r}")
    return _finalize_log_df(rows)


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
    docs/study_pec_motor_space_v2.md Phase 0.2). Returns a list of (start_ts, end_ts,
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
        with open(log_path, encoding="utf-8", errors="replace") as f:
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


def derive_theta_ground_truth(df, lat_deg, lon_deg, theta2_exclude_above=80.0):
    """
    Per-motor pointing-error ground truth for each PECLOG guide-sync cycle, derived from the
    plate-solve's true observed sky position rather than the RA/Dec resid alone (see
    docs/study_pec_motor_space_v2.md Phase 0.1). For each row:
      1. predicted_ra/dec = this row's az/alt/roll (the PID's PV) -> ra/dec, via
         kinematics.azalt_to_radec() -- the same conversion the driver itself uses.
      2. observed_ra/dec = predicted_ra/dec + resid (resid_1=RA, resid_2=Dec, both arcmin of
         degrees -- PECLOG's own convention: control.py's process_guide_sync() computes
         ra_resid = clamp_error(a_ra*15, rightascension*15), already in degrees before the
         *60-to-arcmin the PECLOG payload applies, so resid_i/60 recovers degrees directly).
      3. observed_az/alt = observed_ra/dec -> az/alt, via kinematics.radec_to_altaz().
      4. theta_pred = azaltroll_to_theta(az, alt, roll); theta_obs =
         azaltroll_to_theta(observed_az, observed_alt, roll) -- roll held fixed, since a small
         RA/Dec offset doesn't meaningfully change field rotation.

    Adds theta_pred_1/2/3, theta_obs_1/2/3, and theta_resid_1/2/3 (= obs - pred, degrees) to a
    copy of df. A row missing az/alt/roll/resid_1/resid_2, or where the kinematics solve fails
    (returns None -- e.g. an unreachable geometry), comes back NaN rather than raising, since a
    handful of bad rows in a multi-hour session shouldn't abort the whole derivation.

    theta2_exclude_above: rows with theta_pred_2 beyond this (degrees) get NaN'd out too, not
    just missing/failed ones. kinematics.py's own THETA2_MAX=81.5 is a real, hard mechanical
    near-singularity -- confirmed empirically (not assumed) against real sessions: every large
    theta_resid_1 outlier found while validating this function (up to ~345 degrees before this
    guard existed) had theta_pred_2 clustered at 81.49-81.52. Right at that boundary, the IK's
    branch selection (kinematics.q_to_theta()'s validA/validB) can differ between the predicted
    and observed pose even though the true positional difference is tiny (a few arcmin), since
    theta_pred and theta_obs are unwrapped independently -- see the LastPosition note below.
    The default (80.0) sits ~1.5deg clear of the observed instability zone.

    Requires driver/kinematics.py importable -- adds '<repo>/driver' to sys.path if not
    already present, matching the notebooks' own convention. lat_deg/lon_deg: see
    find_site_location(), which recovers these from the log itself where present.

    kinematics.azaltroll_to_theta()'s IK is multi-valued (two mechanically-distinct motor
    poses can point at the same sky position) and needs a LastPosition to pick the branch
    continuous with the previous row and to unwrap through +/-360 -- called with no lastPos
    it uses a fresh LastPosition per call, so rows aren't continuous with each other (before
    2026-10-17 it silently returned (None, None, None) for every row instead). A single LastPosition is
    carried across rows here, advanced by theta_pred only (the real trajectory) after both
    theta_pred and theta_obs are computed against it -- mirroring how the driver carries one
    persistent self._pid._lp across a session, and keeping theta_obs from ever nudging the
    continuity anchor on its own.
    """
    import sys
    driver_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver'))
    if driver_dir not in sys.path:
        sys.path.insert(0, driver_dir)
    from kinematics import azalt_to_radec, radec_to_altaz, azaltroll_to_theta, LastPosition

    out = df.copy()
    theta_pred = {1: [], 2: [], 3: []}
    theta_obs = {1: [], 2: [], 3: []}
    last_pos = LastPosition()

    def _isnan(v):
        return v is None or (isinstance(v, float) and pd.isna(v))

    for row in out.itertuples(index=False):
        az, alt, roll = getattr(row, 'az', None), getattr(row, 'alt', None), getattr(row, 'roll', None)
        resid_1, resid_2 = getattr(row, 'resid_1', None), getattr(row, 'resid_2', None)
        ts = row.timestamp

        if any(_isnan(v) for v in (az, alt, roll, resid_1, resid_2)):
            for i in (1, 2, 3):
                theta_pred[i].append(float('nan'))
                theta_obs[i].append(float('nan'))
            continue

        date_obs_utc = ts.strftime('%Y-%m-%dT%H:%M:%S.%f')
        ra_deg, dec_deg = azalt_to_radec(az, alt, lat_deg, lon_deg, date_obs_utc)
        t_pred = azaltroll_to_theta(az, alt, roll, last_pos)

        if ra_deg is None or t_pred[0] is None:
            for i in (1, 2, 3):
                theta_pred[i].append(float('nan'))
                theta_obs[i].append(float('nan'))
            continue

        obs_ra_deg = ra_deg + resid_1 / 60
        obs_dec_deg = dec_deg + resid_2 / 60
        obs_az, obs_alt = radec_to_altaz(obs_ra_deg, obs_dec_deg, lat_deg, lon_deg, date_obs_utc)
        t_obs = azaltroll_to_theta(obs_az, obs_alt, roll, last_pos) if obs_az is not None else (None, None, None)

        # last_pos still advances here even when the row gets excluded below -- continuity for
        # *later* rows shouldn't depend on whether this one was near the singularity.
        last_pos.update(*t_pred)

        if t_pred[1] > theta2_exclude_above or (t_obs[1] is not None and t_obs[1] > theta2_exclude_above):
            for i in (1, 2, 3):
                theta_pred[i].append(float('nan'))
                theta_obs[i].append(float('nan'))
            continue

        for i in (1, 2, 3):
            theta_pred[i].append(t_pred[i - 1] if t_pred[i - 1] is not None else float('nan'))
            theta_obs[i].append(t_obs[i - 1] if t_obs[i - 1] is not None else float('nan'))

    for i in (1, 2, 3):
        out[f'theta_pred_{i}'] = theta_pred[i]
        out[f'theta_obs_{i}'] = theta_obs[i]
        # theta_pred/theta_obs are unwrapped independently (each call resolves its own IK
        # branch against the shared last_pos), so near a +/-360 boundary they can occasionally
        # land a whole revolution apart even though the true difference is tiny -- resid is at
        # most a few arcmin, so theta_resid can never legitimately approach even a few degrees.
        # Wrap the raw difference into (-180, 180] rather than subtracting directly, to remove
        # that artifact instead of letting it dominate any later mean/std over the session.
        raw_diff = out[f'theta_obs_{i}'] - out[f'theta_pred_{i}']
        out[f'theta_resid_{i}'] = (raw_diff + 180) % 360 - 180

    return out


def derive_theta_from_total_accum(df, lat_deg, lon_deg, theta2_exclude_above=80.0):
    """
    PEC-correction-independent per-motor drift trajectory, reconstructed from PECLOG's
    total_accum -- NOT resid. This exists because of a real gap found in derive_theta_
    ground_truth(): resid/theta_resid measures whatever pointing error remains AFTER PEC's own
    RA/Dec-space correction has already been applied to the logged az/alt/roll (checked
    empirically: `inhibit_1` was VALID, i.e. PEC actively correcting, for 95%+ of the rows in
    the session this was validated against) -- so it's not a clean measurement of the true,
    uncorrected mechanical periodic error, it's contaminated by however well or badly the
    current (wrong-domain) RA/Dec model happens to be doing at each moment. total_accum is the
    field the driver's own code deliberately keeps free of this: "The fit's training signal;
    deliberately doesn't shrink as PEC improves" (control.py's _pec_log() docstring). This
    mirrors what analyse_pec.ipynb's own existing "Right Ascension/Declination Period" cells
    already do -- periodogram total_accum directly, not resid, for exactly this reason -- just
    projected into theta-space instead of staying in RA/Dec.

    For each PEC-model segment (split at every 'n' counter reset -- goto/rotate/jog/stop-
    tracking/config change, the same reset detection used by the reset-aware cells elsewhere
    in analyse_pec.ipynb):
      1. Anchor ra0/dec0 at the segment's first usable row (az/alt/roll -> ra/dec, same
         kinematics.azalt_to_radec() conversion as derive_theta_ground_truth()).
      2. true_ra/dec(t) = ra0/dec0 + total_accum_1/2(t)/60 (arcmin -> degrees) -- the sky
         position the mount would be pointing at if it had run open-loop with zero correction
         since this segment's reset.
      3. true_az/alt(t) = true_ra/dec(t) -> az/alt via kinematics.radec_to_altaz(), combined
         with this row's own logged roll.
      4. theta_true_1/2/3(t) = azaltroll_to_theta(true_az, true_alt, roll, lastPos) -- one
         running LastPosition per segment (a fresh one at each reset), same reasoning as
         derive_theta_ground_truth()'s single running instance.

    theta_true_i(t) is dominated by the same real tracking motion theta_pred_i was (total_accum
    is a small arcmin-scale perturbation on top of the much larger intentional slew/track
    motion baked into az/alt/roll), so it can be used the same way theta_pred_i was: as its own
    angle-domain x-axis (paired with itself as the y-signal, `lombscargle_periodogram()`'s
    built-in detrend removes the large-scale tracking trend, leaving the periodic wobble).

    Adds theta_true_1/2/3 (degrees) to a copy of df; NaN for rows missing az/alt/roll/
    total_accum_1/2, where the kinematics solve fails, or (same guard as
    derive_theta_ground_truth(), same justification) near the theta2 near-singularity.
    """
    import sys
    driver_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver'))
    if driver_dir not in sys.path:
        sys.path.insert(0, driver_dir)
    from kinematics import azalt_to_radec, radec_to_altaz, azaltroll_to_theta, LastPosition

    out = df.copy().reset_index(drop=True)
    theta_true = {i: [float('nan')] * len(out) for i in (1, 2, 3)}

    def _isnan(v):
        return v is None or (isinstance(v, float) and pd.isna(v))

    n_col = out['n'].values
    seg_starts = [0] + [i for i in range(1, len(out)) if n_col[i] < n_col[i - 1]]
    seg_bounds = list(zip(seg_starts, seg_starts[1:] + [len(out)]))

    for seg_start, seg_end in seg_bounds:
        anchor_ra = anchor_dec = None
        last_pos = LastPosition()
        for idx in range(seg_start, seg_end):
            row = out.iloc[idx]
            az, alt, roll = row.get('az'), row.get('alt'), row.get('roll')
            ta1, ta2 = row.get('total_accum_1'), row.get('total_accum_2')
            ts = row['timestamp']

            if any(_isnan(v) for v in (az, alt, roll, ta1, ta2)):
                continue

            date_obs_utc = ts.strftime('%Y-%m-%dT%H:%M:%S.%f')

            if anchor_ra is None:
                anchor_ra, anchor_dec = azalt_to_radec(az, alt, lat_deg, lon_deg, date_obs_utc)
                if anchor_ra is None:
                    continue

            true_ra = anchor_ra + ta1 / 60
            true_dec = anchor_dec + ta2 / 60
            true_az, true_alt = radec_to_altaz(true_ra, true_dec, lat_deg, lon_deg, date_obs_utc)
            if true_az is None:
                continue

            t_true = azaltroll_to_theta(true_az, true_alt, roll, last_pos)
            if t_true[0] is None or t_true[1] > theta2_exclude_above:
                continue

            last_pos.update(*t_true)
            for i in (1, 2, 3):
                theta_true[i][idx] = t_true[i - 1]

    for i in (1, 2, 3):
        out[f'theta_true_{i}'] = theta_true[i]

    return out


def derive_theta_from_sync_residuals(resid_df, kf_df, lat_deg, lon_deg, theta2_exclude_above=80.0,
                                      match_tolerance='2s'):
    """
    PEC-independent per-motor drift trajectory for a session with NO PECLOG at all (PEC
    disabled, sync-guiding enabled -- see load_sync_guiding_residuals()) -- the
    load_pec()/total_accum-based derive_theta_from_total_accum() can't be used here since
    there's no az/alt/roll or total_accum logged anywhere without PECLOG. Sourced instead
    from raw KFLOG telemetry:
      1. For each sync-guiding residual event (resid_df, from load_sync_guiding_residuals()),
         find the nearest KFLOG sample (within match_tolerance) and take its θ_meas_raw_1/2/3
         -- the real, physical motor position at that moment.
      2. Convert θ_meas_raw -> az/alt/roll via kinematics.theta_to_azaltroll() (the forward
         counterpart of azaltroll_to_theta()), then az/alt -> ra/dec via azalt_to_radec().
      3. Anchor ra0/dec0 at the first usable event, then true_ra/dec(t) = ra0/dec0 +
         cumsum(resid_1/2)(t)/60 (arcmin -> degrees) -- note this has no separate PEC term to
         add back (PEC is off, cumsum(resid) alone is the true uncorrected drift; see the
         no-hidden-term reasoning for total_accum in docs/study_pec_motor_space_v2.md -- the same
         applies here even more directly, since resid is the *only* correction mechanism
         active).
      4. true_az/alt(t) = true_ra/dec(t) -> az/alt via radec_to_altaz(), combined with this
         event's own roll (from step 2).
      5. theta_true_1/2/3(t) = azaltroll_to_theta(true_az, true_alt, roll, lastPos) -- one
         running LastPosition across the whole df (caller should pre-split by tracking
         segment/reset first -- unlike derive_theta_from_total_accum(), this doesn't split on
         PECLOG's 'n' counter, since there is none; a goto/reslew mid-session, e.g. after a
         reconnection, would need excluding by the caller beforehand).

    Also adds theta_meas_1/2/3 -- θ_meas_raw converted straight to theta via the matched
    KFLOG row, no resid/cumsum involved -- for use as an angle-domain x-axis (dominated by
    real tracking motion, same role theta_pred_i played for the PECLOG-based derivation).

    Returns a copy of resid_df with these columns added; NaN for events with no KFLOG match
    within tolerance, a failed kinematics solve, or near the theta2 near-singularity (same
    guard and justification as derive_theta_ground_truth()).
    """
    import sys
    driver_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver'))
    if driver_dir not in sys.path:
        sys.path.insert(0, driver_dir)
    from kinematics import azalt_to_radec, radec_to_altaz, azaltroll_to_theta, theta_to_azaltroll, LastPosition

    out = resid_df.copy().reset_index(drop=True)
    kf_cols = ['timestamp'] + [f'θ_meas_raw_{i}' for i in (1, 2, 3)]
    kf_sub = kf_df.dropna(subset=[f'θ_meas_raw_{i}' for i in (1, 2, 3)])[kf_cols].sort_values('timestamp')
    matched = pd.merge_asof(out[['timestamp']], kf_sub, on='timestamp',
                             direction='nearest', tolerance=pd.Timedelta(match_tolerance))

    theta_meas = {i: [] for i in (1, 2, 3)}
    theta_true = {i: [] for i in (1, 2, 3)}
    anchor_ra = anchor_dec = None
    last_pos = LastPosition()

    def _isnan(v):
        return v is None or (isinstance(v, float) and pd.isna(v))

    cum_resid_1 = cum_resid_2 = 0.0
    for idx in range(len(out)):
        m1, m2, m3 = matched.loc[idx, 'θ_meas_raw_1'], matched.loc[idx, 'θ_meas_raw_2'], matched.loc[idx, 'θ_meas_raw_3']
        r1, r2 = out.loc[idx, 'resid_1'], out.loc[idx, 'resid_2']
        cum_resid_1 += 0.0 if _isnan(r1) else r1
        cum_resid_2 += 0.0 if _isnan(r2) else r2

        if any(_isnan(v) for v in (m1, m2, m3)):
            for i in (1, 2, 3):
                theta_meas[i].append(float('nan'))
                theta_true[i].append(float('nan'))
            continue

        az, alt, roll = theta_to_azaltroll(m1, m2, m3)
        if az is None:
            for i in (1, 2, 3):
                theta_meas[i].append(float('nan'))
                theta_true[i].append(float('nan'))
            continue

        ts = out.loc[idx, 'timestamp']
        date_obs_utc = ts.strftime('%Y-%m-%dT%H:%M:%S.%f')
        if anchor_ra is None:
            anchor_ra, anchor_dec = azalt_to_radec(az, alt, lat_deg, lon_deg, date_obs_utc)
            if anchor_ra is None:
                for i in (1, 2, 3):
                    theta_meas[i].append(float('nan'))
                    theta_true[i].append(float('nan'))
                continue

        true_ra = anchor_ra + cum_resid_1 / 60
        true_dec = anchor_dec + cum_resid_2 / 60
        true_az, true_alt = radec_to_altaz(true_ra, true_dec, lat_deg, lon_deg, date_obs_utc)
        t_true = azaltroll_to_theta(true_az, true_alt, roll, last_pos) if true_az is not None else (None, None, None)

        if t_true[0] is None or t_true[1] > theta2_exclude_above:
            for i in (1, 2, 3):
                theta_meas[i].append(float('nan'))
                theta_true[i].append(float('nan'))
            continue

        last_pos.update(*t_true)
        for i, v in zip((1, 2, 3), (m1, m2, m3)):
            theta_meas[i].append(v)
        for i in (1, 2, 3):
            theta_true[i].append(t_true[i - 1])

    for i in (1, 2, 3):
        out[f'theta_meas_{i}'] = theta_meas[i]
        out[f'theta_true_{i}'] = theta_true[i]

    return out


def derive_theta_from_sglog(df, lat_deg, lon_deg, theta2_exclude_above=80.0):
    """
    PEC-independent per-motor drift trajectory from SGLOG alone (load_sglog()) -- no KFLOG or
    PECLOG needed. Simpler than derive_theta_from_sync_residuals(): SGLOG already carries
    theta_raw_1/2/3 (the real motor position at the moment of each sync) and az/alt/roll (the
    PID's PV) directly on every row, so there's no nearest-sample matching to do, and no
    separate cumsum(resid) bookkeeping either -- total_accum_1/2 (backed by the driver's own
    delta_guide_accum, see docs/study_pec_motor_space_v2.md) is already that cumulative sum,
    tracked live in the driver.

    For each row:
      1. theta_meas_1/2/3 = theta_raw_1/2/3 directly -- already in motor space, no conversion
         needed. Use as the angle-domain x-axis (dominated by real tracking motion), the same
         role theta_pred_i/theta_meas_i play in the PECLOG/sync-residual derivations.
      2. Anchor ra0/dec0 at the first usable row: this row's logged az/alt (PV) -> ra/dec via
         kinematics.azalt_to_radec().
      3. true_ra/dec(t) = ra0/dec0 + total_accum_1/2(t)/60 (arcmin -> degrees) -- the sky
         position the mount would be pointing at if it had run open-loop with zero correction
         since total_accum's last reset.
      4. true_az/alt(t) = true_ra/dec(t) -> az/alt via kinematics.radec_to_altaz(), combined
         with this row's own logged roll.
      5. theta_true_1/2/3(t) = azaltroll_to_theta(true_az, true_alt, roll, lastPos) -- one
         running LastPosition across the whole df.

    Unlike derive_theta_from_total_accum(), this does NOT split internally on any reset
    counter -- SGLOG carries no 'n' field (there's no PEC model here to reset against).
    total_accum can still jump discontinuously within a session (clear_sync_guiding(), or any
    optimize_alignQ_B2T() realignment -- see load_sglog()); if this session spans a
    goto/reslew/reconnection, pre-split the df yourself first (e.g. one find_tracking_segments()
    segment at a time), the same convention derive_theta_from_sync_residuals() documents.

    Adds theta_meas_1/2/3 and theta_true_1/2/3 (degrees) to a copy of df; NaN for rows missing
    az/alt/roll/total_accum_1/2/theta_raw_1/2/3, where the kinematics solve fails, or near the
    theta2 near-singularity (same guard and justification as derive_theta_ground_truth()).
    """
    import sys
    driver_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver'))
    if driver_dir not in sys.path:
        sys.path.insert(0, driver_dir)
    from kinematics import azalt_to_radec, radec_to_altaz, azaltroll_to_theta, LastPosition

    out = df.copy().reset_index(drop=True)
    theta_meas = {i: [] for i in (1, 2, 3)}
    theta_true = {i: [] for i in (1, 2, 3)}
    anchor_ra = anchor_dec = None
    last_pos = LastPosition()

    def _isnan(v):
        return v is None or (isinstance(v, float) and pd.isna(v))

    for idx in range(len(out)):
        row = out.iloc[idx]
        az, alt, roll = row.get('az'), row.get('alt'), row.get('roll')
        ta1, ta2 = row.get('total_accum_1'), row.get('total_accum_2')
        m1, m2, m3 = row.get('theta_raw_1'), row.get('theta_raw_2'), row.get('theta_raw_3')
        ts = row['timestamp']

        if any(_isnan(v) for v in (az, alt, roll, ta1, ta2, m1, m2, m3)):
            for i in (1, 2, 3):
                theta_meas[i].append(float('nan'))
                theta_true[i].append(float('nan'))
            continue

        date_obs_utc = ts.strftime('%Y-%m-%dT%H:%M:%S.%f')
        if anchor_ra is None:
            anchor_ra, anchor_dec = azalt_to_radec(az, alt, lat_deg, lon_deg, date_obs_utc)
            if anchor_ra is None:
                for i in (1, 2, 3):
                    theta_meas[i].append(float('nan'))
                    theta_true[i].append(float('nan'))
                continue

        true_ra = anchor_ra + ta1 / 60
        true_dec = anchor_dec + ta2 / 60
        true_az, true_alt = radec_to_altaz(true_ra, true_dec, lat_deg, lon_deg, date_obs_utc)
        t_true = azaltroll_to_theta(true_az, true_alt, roll, last_pos) if true_az is not None else (None, None, None)

        if t_true[0] is None or t_true[1] > theta2_exclude_above:
            for i in (1, 2, 3):
                theta_meas[i].append(float('nan'))
                theta_true[i].append(float('nan'))
            continue

        last_pos.update(*t_true)
        for i, v in zip((1, 2, 3), (m1, m2, m3)):
            theta_meas[i].append(v)
        for i in (1, 2, 3):
            theta_true[i].append(t_true[i - 1])

    for i in (1, 2, 3):
        out[f'theta_meas_{i}'] = theta_meas[i]
        out[f'theta_true_{i}'] = theta_true[i]

    return out


def lombscargle_periodogram(x, y, min_period=None, max_period=None, n_periods=2000, detrend=True):
    """
    Lomb-Scargle periodogram of y against x, for irregularly-sampled data -- PECLOG's own
    guide-sync cadence isn't uniform, and this is used for both the time-domain (x=t_sec) and
    angle-domain (x=cumulative motor rotation, e.g. theta_pred_i) periodicity tests in
    docs/study_pec_motor_space_v2.md Phase 0.2, so it needs to handle irregular spacing in either
    axis without resampling artifacts. Returns (periods, power) with `periods` in the same
    units as `x` (minutes if x is t_sec/60, degrees if x is a theta_pred_i column) and `power`
    scipy's normalized Lomb-Scargle power at each period -- comparable in shape to (though not
    numerically identical to) the scipy.signal.periodogram plots already used elsewhere in
    analyse_pec.ipynb.

    detrend=True (default) removes a linear fit of y against x before the periodogram, same
    convention as those existing cells (`ra_detrended = ra - polyval(polyfit(t, ra, 1), t)`)
    -- confirmed empirically to matter, not just for consistency: theta_resid does carry a
    real linear trend against theta_pred, and without removing it the periodogram's power
    rises monotonically all the way to max_period with no local peak at all (a textbook
    slow-trend signature), which read as a spurious "period == exactly half the data span"
    for almost every motor/segment tried before this was added.

    min_period/max_period default to [4x the median sample spacing, half the x-span]: a period
    under ~4 samples isn't reliably resolvable, and one over half the available span is really
    just a trend within the data, not a repeating period.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]
    order = np.argsort(x)
    x, y = x[order], y[order]
    if len(x) < 8:
        raise ValueError(f"Not enough points for a periodogram: {len(x)}")
    if detrend:
        y = y - np.polyval(np.polyfit(x, y, 1), x)
    y = y - np.mean(y)

    dx = np.diff(x)
    dx = dx[dx > 0]
    median_dx = np.median(dx) if len(dx) else 1.0
    span = x[-1] - x[0]

    if min_period is None:
        min_period = 4 * median_dx
    if max_period is None:
        max_period = span / 2
    if not (0 < min_period < max_period):
        raise ValueError(f"Invalid period range: min={min_period}, max={max_period} (span={span}, median spacing={median_dx})")

    periods = np.linspace(min_period, max_period, n_periods)
    ang_freqs = 2 * np.pi / periods
    power = _scipy_signal.lombscargle(x, y, ang_freqs, normalize=True)
    return periods, power


def periodogram_peak(periods, power):
    """(peak_period, peak_power) -- the strongest periodicity found by lombscargle_periodogram()."""
    idx = int(np.argmax(power))
    return periods[idx], power[idx]


def periodogram_false_alarm_probability(x, y, n_shuffles=200, rng=None, **periodogram_kwargs):
    """
    False-alarm probability (FAP) for the strongest peak in lombscargle_periodogram(x, y): the
    fraction of random shufflings of y (x held fixed, so the same sampling/detrending/search
    range is reused) whose own strongest peak power meets or beats the real data's. A low FAP
    means the real peak is unusually strong for this sample size/spacing; a high one means
    noise alone regularly produces a peak just as strong, i.e. the "peak" isn't trustworthy.

    This exists because of a real failure mode found while validating Phase 0.2 (see
    docs/study_pec_motor_space_v2.md): with the small sample sizes PECLOG-cadence segments give
    (tens to a few hundred points), the raw peak period/power alone kept landing near
    suspiciously round numbers of cycles across unrelated motors/segments even after
    detrending -- a classic small-sample periodogram bias (a long period has more freedom to
    fit noise relative to how few independent cycles are actually observed), not evidence of
    real periodicity. A permutation test is the direct way to tell the difference: it directly
    answers "how easily does noise alone produce a peak this strong here," rather than relying
    on power alone, which isn't comparable in meaning across different sample sizes/spans.

    Returns (fap, real_peak_period, real_peak_power). rng: a numpy Generator, or None to use
    a fresh default_rng() (results then vary run to run -- pass one explicitly to reproduce).
    """
    if rng is None:
        rng = np.random.default_rng()
    periods, power = lombscargle_periodogram(x, y, **periodogram_kwargs)
    real_peak_period, real_peak_power = periodogram_peak(periods, power)

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    x, y = x[mask], y[mask]

    n_meets_or_beats = 0
    for _ in range(n_shuffles):
        y_shuffled = rng.permutation(y)
        _, shuffled_power = lombscargle_periodogram(x, y_shuffled, **periodogram_kwargs)
        if shuffled_power.max() >= real_peak_power:
            n_meets_or_beats += 1

    fap = n_meets_or_beats / n_shuffles
    return fap, real_peak_period, real_peak_power


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
        with open(log_path, encoding="utf-8", errors="replace") as f:
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


# ── Comms / dropout / restart diagnostics ───────────────────────────────────────────────────

_VITALS_RE = re.compile(
    r"^(?P<ts>\S+) WARNING ->> (?P<kind>Polaris position update|Heartbeat lag detected|"
    r"Event loop lag detected):\s+"
    r"(?:lag|pulse|slept) (?P<lag>[\d.]+)s \(expected [\d.]+s\) "
    r"CPU:\s*(?P<cpu>[\d.]+)% Mem:\s*(?P<mem>[\d.]+)% \((?P<mem_mb>\d+)MB\) "
    r"Swap:\s*(?P<swap>[\d.]+)% Threads: (?P<threads>\d+) "
    r"NetDrops: (?P<dropin>\d+)/(?P<dropout>\d+) NetErr: (?P<errin>\d+)/(?P<errout>\d+)"
)

# Display name shown downstream for each raw 'kind' matched above -- keyed by the literal
# text the driver actually logs (unchanged there), so renaming a label here never breaks
# _VITALS_RE's ability to match real log lines.
_VITALS_KIND_DISPLAY_NAMES = {"Polaris position update": "518 lag detected"}


def load_vitals(log_filenames, log_dir='.'):
    """
    Parse the driver's shr.system_vitals()-carrying WARNING lines into a DataFrame -- three
    distinct triggers, all sharing the same CPU/Mem/Swap/thread-count/network-counter
    snapshot format:
      - '518 lag detected' (raw log text: 'Polaris position update') -- polaris.py's 500ms
        watchdog (_every_500ms_watchdog_check), fires whenever 518 telemetry itself is
        running late (>0.5s).
      - 'Heartbeat lag detected' -- main.py's asyncio event-loop watchdog thread, fires when
        the event loop's own heartbeat coroutine hasn't pulsed recently -- a sign the loop is
        stalled on something CPU-bound, not a network symptom.
      - 'Event loop lag detected' -- polaris.py's own watchdog-cycle sleep overrun check
        (expected to sleep 0.5s between cycles; fires when it actually took meaningfully
        longer) -- same root cause as heartbeat lag, different call site.

    Each is a genuine discrete event with its own system snapshot at the moment it fired --
    exactly the context needed to tell a real network/Polaris-side problem apart from local
    system resource pressure on the machine running the driver. NetDrops/NetErr are
    psutil.net_io_counters() system-wide cumulative counters (interface-level hard drops/
    errors) -- they won't catch WiFi RSSI degradation, TCP-level retransmission, or CPU
    contention from another process, only a hard interface-level drop, so 0/0 here doesn't by
    itself rule out a real problem; see load_high_cpu_events() for the CPU-contention case
    specifically (system_vitals() triggers a one-shot top-5-process probe whenever it
    observes CPU > 95%, logged separately as its own 'HIGH CPU LOAD breakdown' line).

    Returns an empty DataFrame, not an error, when none are found.
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    rows = []
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _VITALS_RE.match(line)
                if not m:
                    continue
                d = m.groupdict()
                rows.append(dict(
                    timestamp=d["ts"], kind=_VITALS_KIND_DISPLAY_NAMES.get(d["kind"], d["kind"]),
                    lag_s=float(d["lag"]), cpu_pct=float(d["cpu"]),
                    mem_pct=float(d["mem"]), mem_mb=int(d["mem_mb"]),
                    swap_pct=float(d["swap"]), threads=int(d["threads"]),
                    net_dropin=int(d["dropin"]), net_dropout=int(d["dropout"]),
                    net_errin=int(d["errin"]), net_errout=int(d["errout"]),
                ))
    df = pd.DataFrame(rows)
    if len(df):
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp", kind="stable").drop_duplicates().reset_index(drop=True)
    return df


_HIGH_CPU_RE = re.compile(r"^(?P<ts>\S+) WARNING ->> HIGH CPU LOAD breakdown:\s+(?P<procs>.*)$")
_HIGH_CPU_PROC_RE = re.compile(r"^(?P<name>.+?)\s+(?P<pct>[\d.]+)%$")


def load_high_cpu_events(log_filenames, log_dir='.'):
    """
    Parse 'HIGH CPU LOAD breakdown: <Name X.X%, Name X.X%, ...>' WARNING lines (main.py's
    heartbeat-monitor thread, via shr.system_cpu(): a one-shot top-5-process-by-CPU% probe,
    triggered whenever a system_vitals() call -- i.e. any of load_vitals()'s three warning
    kinds -- observes CPU > 95%). This is the single most direct signal for "was this dropout
    caused by CPU contention on the machine running the driver" -- found essential while
    investigating a real overnight dropout (docs/study_pec_motor_space_v2.md): the disconnect at
    2026-09-01T00:21:52 was preceded by NINA.exe (imaging software) and the driver's own
    python.exe pushing CPU to 100%, starving the driver's asyncio event loop long enough that
    the connection was forcibly closed.

    Returns a long-form DataFrame (one row per ranked process per event: timestamp, rank
    (1=highest), process, cpu_pct) -- easier to plot/filter/join than the raw comma-joined
    string. Empty DataFrame, not an error, when none are found (a session with no CPU
    contention has none, and that's the expected/good case).
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    rows = []
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _HIGH_CPU_RE.match(line)
                if not m:
                    continue
                procs = m.group("procs").strip()
                if not procs:
                    continue
                for rank, part in enumerate(procs.split(", "), start=1):
                    pm = _HIGH_CPU_PROC_RE.match(part.strip())
                    if pm:
                        rows.append(dict(timestamp=m.group("ts"), rank=rank,
                                          process=pm.group("name"), cpu_pct=float(pm.group("pct"))))
    df = pd.DataFrame(rows)
    if len(df):
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values(["timestamp", "rank"], kind="stable").drop_duplicates().reset_index(drop=True)
    return df


_CONN_EVENT_PATTERNS = [
    ('driver_start', re.compile(r"^(?P<ts>\S+) INFO ==STARTUP== ALPACA BENRO POLARIS DRIVER (?P<detail>.+?)\s*=+"), None),
    ('disconnect', re.compile(r"^(?P<ts>\S+) ERROR ==DISCONNECT== Polaris socket error: (?P<detail>.*)$"), None),
    ('disconnect', re.compile(r"^(?P<ts>\S+) WARNING ==DISCONNECT== Polaris socket closed\.$"),
        lambda m: {'detail': 'socket closed (no data)'}),
    ('reconnect_error', re.compile(r"^(?P<ts>\S+) ERROR ==STARTUP== Connection error: (?P<detail>.*)$"), None),
    # read_msgs()'s own except block -- the canonical "an established connection died"
    # trigger. Covers three distinct root causes sharing this one log format: the 5s-no-
    # 518 watchdog (WatchdogError, detail startswith '==ERROR==: No position update...'),
    # a cmd-response timeout re-raised from _await_cmd_response, and a raw send/receive
    # failure -- see _CONNECTION_ERROR_TAXONOMY below for telling them apart via `detail`.
    ('reconnect_error', re.compile(r"^(?P<ts>\S+) ERROR ==ERROR== read_msgs failed: (?P<detail>.*)$"), None),
    # ==TIMEOUT==/==SEND== both set the same _task_exception that read_msgs() picks up and
    # re-logs (with identical detail text) as the 'reconnect_error' above one loop tick
    # later -- kept as their own non-triggering kinds (reconstruct_outages() only treats
    # 'disconnect'/'reconnect_error' as outage starts) purely for taxonomy/context, so a
    # real outage isn't double-counted just because both lines appear for it.
    ('cmd_timeout', re.compile(r"^(?P<ts>\S+) ERROR ==TIMEOUT== (?P<detail>.*)$"), None),
    ('send_error', re.compile(r"^(?P<ts>\S+) ERROR ==SEND== Failed to send message: (?P<detail>.*)$"), None),
    ('connect_attempt_failed', re.compile(
        r"^(?P<ts>\S+) ERROR (?!==)(?P<detail>Connect timed out\..*|Connection .*|"
        r"Check (?:Network|Hostname).*|Polaris not .*|Unexpected error:.*)$"), None),
    ('init_start', re.compile(r"^(?P<ts>\S+) INFO Polaris communication init\.\.\.$"),
        lambda m: {'detail': None}),
    ('init_done', re.compile(r"^(?P<ts>\S+) INFO Polaris communication init\.\.\. done$"),
        lambda m: {'detail': None}),
    ('wifi_join_failed', re.compile(r"^(?P<ts>\S+) WARNING Failed to join WiFi network '(?P<ssid>[^']+)': (?P<detail>.*)$"), None),
    # BLE-mediated Wi-Fi-radio-enable failures (Polaris:bleEnableWifi) -- a distinct WiFi
    # lifecycle event from wifi_join_failed above (that one is the *host's* netsh join to
    # the Polaris hotspot; this one is telling the Polaris itself, over Bluetooth, to turn
    # its Wi-Fi radio on in the first place).
    ('ble_wifi_failed', re.compile(r"^(?P<ts>\S+) ERROR (?P<detail>BLE failed to enable Wi-Fi after \d+ attempts for \S+)$"), None),
    ('ble_error', re.compile(r"^(?P<ts>\S+) ERROR (?P<detail>Unexpected BLE error on attempt \d+:.*)$"), None),
    ('wifi_interface', re.compile(r"^(?P<ts>\S+) INFO Using WiFi interface: (?P<detail>.*)$"), None),
    ('sync_observed', re.compile(r"^(?P<ts>\S+) INFO ->> Polaris: SYNC Observed\s+(?P<detail>.*)$"), None),
]


# ── Connection-error taxonomy ───────────────────────────────────────────────────────────
#
# Maps the free-text `detail` captured by the patterns above to a short, stable
# `error_code` + one-line `error_meaning` + broader `error_category` (for grouping/
# charting). Built by grepping every capture in logs/archive for its unique connect_
# attempt_failed/reconnect_error/disconnect/wifi_join_failed/ble_* detail strings, then
# cross-referencing driver/polaris.py's own `_format_connection_error()` (the only place
# that turns a raw exception into the text that ends up in these log lines) and
# docs/troubleshooting.md's C0/C1/C3 sections (written from field reports of the same
# failures) for what each one actually means and how to chase it down.
#
# Deliberately keyed on regexes matched against the *rendered* message, not the exception
# class -- that's all a log line gives us to go on, and it's what `detail` already is.
# Ordered most-specific first; first match wins. Entries: (code, meaning, category, regex).
_CONNECTION_ERROR_TAXONOMY = [
    ('WATCHDOG_NO_TELEMETRY',
     "Driver's 5s-no-518-telemetry watchdog fired on an already-established connection -- "
     "Polaris stopped sending position updates even though the socket itself looked fine.",
     'watchdog', re.compile(r'No position update for over 5s')),

    ('CMD_RESPONSE_TIMEOUT',
     'A specific command (usually cmd 284, the current-mode query during init) got no reply '
     'within its timeout and the link was declared dead.',
     'watchdog', re.compile(r'No response to Polaris cmd \d+')),

    ('CONNECTION_LOST',
     'The socket reported the connection already gone when the driver next tried to use it '
     '(send or read) -- same underlying loss as a disconnect/reset, just observed on the '
     'send/receive path rather than the raw socket-error handler.',
     'peer_reset', re.compile(r'^Connection lost\b')),

    ('SOCKET_CLOSED_CLEAN',
     'Peer closed the TCP connection cleanly (zero-byte read, no error) -- Polaris or the '
     'app-side ended the session outright rather than the link failing underneath it.',
     'closed_clean', re.compile(r'socket closed \(no data\)|Polaris socket closed')),

    ('WSAECONNRESET',
     'Peer forcibly reset an established connection (WSAECONNRESET/WinError 10054) -- often '
     'the OS/network stack timing out the socket after the event loop was starved too long '
     'to service it. See docs/troubleshooting.md C3-1 (CPU/resource starvation).',
     'peer_reset', re.compile(r'WinError\s*10054|winerror=10054')),

    ('NETNAME_DELETED',
     'The network adapter/name disappeared out from under the socket (WinError 64) -- '
     'typically a Wi-Fi adapter reset or driver crash. See docs/troubleshooting.md C3-6.',
     'adapter_reset', re.compile(r'WinError\s*64\b')),

    ('CONN_ABORTED_LOCAL',
     'Windows tore the TCP connection down locally (WinError 1236) -- most often a DHCP '
     'lease rejection (DHCPNACK) or an adapter/IP change. See docs/troubleshooting.md C3-2.',
     'local_abort', re.compile(r'WinError\s*1236|winerror=1236')),

    ('CONN_REFUSED',
     'Polaris actively refused the connection attempt (WinError 1225) -- nothing was '
     'listening on the expected port (Astro Mode not active, or Polaris still booting).',
     'refused', re.compile(r'WinError\s*1225|winerror=1225')),

    ('SEM_TIMEOUT',
     'A network operation timed out mid-flight (winerror=121, ERROR_SEM_TIMEOUT) -- usually '
     'a degraded/weak Wi-Fi link rather than a hard disconnect. See docs/troubleshooting.md '
     'C3-5 (RF interference/signal strength).',
     'link_degraded', re.compile(r'winerror=121\b|WinError\s*121\b')),

    ('NET_UNREACHABLE',
     'No route to the Polaris subnet at all -- the Wi-Fi adapter is not associated to the '
     'Polaris hotspot. See docs/troubleshooting.md C1a.',
     'unreachable', re.compile(r'WinError\s*1231|errno=51\b')),

    ('HOST_UNREACHABLE',
     'Associated to the Polaris Wi-Fi but no IP route to the Polaris host -- wrong IP '
     'config, IPv6-only association, or DHCP failure. See docs/troubleshooting.md C1b/C1c.',
     'unreachable', re.compile(r'WinError\s*1232|errno=(?:60|64)\b')),

    ('CONNECT_TIMEOUT',
     "Fresh TCP connect() itself never completed within the 5s attempt window -- Polaris is "
     "off, not yet booted, or the host hasn't joined the polaris_XXXXXX hotspot yet.",
     'connect_timeout', re.compile(r'^Connect timed out\.')),

    ('CONN_ABORTED_GENERIC',
     'Local OS aborted the connection (bare ConnectionAbortedError, no specific winerror).',
     'local_abort', re.compile(r'network connection was aborted')),

    ('NOT_ASTRO_MODE',
     "Polaris isn't in Astro Mode -- a mount-config state, not a network failure. Use the "
     'Polaris App to change mode.',
     'config_state', re.compile(r'not in Astro Mode')),

    ('NOT_ALIGNED',
     "Polaris alignment isn't complete -- a mount-config state, not a network failure. "
     'Complete alignment in the Polaris App.',
     'config_state', re.compile(r'not aligned')),

    ('BLE_WIFI_ENABLE_FAILED',
     "bleEnableWifi couldn't turn the Polaris's Wi-Fi radio on via Bluetooth after repeated "
     'attempts -- phone/app still holding the BLE connection, out of range, or the Polaris '
     'BLE stack wedged.',
     'ble', re.compile(r'BLE failed to enable Wi-Fi')),

    ('BLE_ERROR',
     'An unclassified error occurred talking to the Polaris over Bluetooth.',
     'ble', re.compile(r'Unexpected BLE error')),
]

# Generic fallback for a WinError/winerror/errno number this taxonomy hasn't seen yet --
# keeps it groupable by code instead of silently collapsing into 'UNCLASSIFIED'.
_WINCODE_FALLBACK_RE = re.compile(r'WinError\s*(-?\d+)|winerror=(-?\d+)|errno=(-?\d+)')


def _param_present(v):
    """
    True if a config_update 'param_<key>' value should be treated as present.
    Plain pd.notna(v)/pd.isna(v) raises ValueError on a list/array value (e.g. the
    kf_measure_noise/kf_process_noise arrays Polaris:ConfigUpdate can carry) since
    those compare elementwise. Non-scalars are never NaN, so only scalars need the
    notna check.
    """
    return not np.isscalar(v) or pd.notna(v)


def classify_connection_error(detail, kind=None):
    """
    Map one load_connection_events() row's `detail` (+ its `kind`, for the wifi_join_failed
    special case below) to (error_code, error_meaning, error_category) via
    _CONNECTION_ERROR_TAXONOMY. Returns (None, None, None) for a missing/empty detail --
    e.g. driver_start/init_start/init_done/sync_observed/config_update rows, which carry no
    error to classify.

    Falls back to extracting a bare WinError/winerror/errno number for anything not
    explicitly enumerated in the taxonomy (a 'WINERR_<n>'/'ERRNO_<n>' code with a generic
    meaning), and to ('UNCLASSIFIED', None, 'other') when even that fails -- so a brand new
    error string this taxonomy hasn't been taught yet still lands in the table with *some*
    code, rather than crashing or vanishing.
    """
    if not detail:
        return (None, None, None)
    if kind == 'wifi_join_failed':
        return ('WIFI_JOIN_FAILED',
                "The host's own Wi-Fi join to the Polaris hotspot (netsh) failed -- see "
                'docs/troubleshooting.md C0 (adapter compatibility) / C3-4 (adapter hardware).',
                'wifi_join')
    for code, meaning, category, pattern in _CONNECTION_ERROR_TAXONOMY:
        if pattern.search(detail):
            return (code, meaning, category)
    m = _WINCODE_FALLBACK_RE.search(detail)
    if m:
        n = next(g for g in m.groups() if g is not None)
        return (f'WINERR_{n}',
                f'Windows/OS error code {n} -- not yet in the taxonomy, see the raw detail text.',
                'other')
    return ('UNCLASSIFIED', None, 'other')


# kinds from _CONN_EVENT_PATTERNS that represent an actual failure worth classifying --
# everything else (driver_start, init_start/done, wifi_interface, sync_observed,
# config_update, client_action) carries no error in its `detail`.
_CLASSIFIABLE_ERROR_KINDS = {
    'disconnect', 'reconnect_error', 'connect_attempt_failed', 'wifi_join_failed',
    'cmd_timeout', 'send_error', 'ble_wifi_failed', 'ble_error',
}

_CLIENT_ACTION_RE = re.compile(
    r"^(?P<ts>\S+) INFO (?P<client_ip>\S+) -> PUT /api/v1/telescope/0/action (?P<body>\{.*\})\s*$"
)
_INTERESTING_ACTIONS = {
    'Polaris:ConnectPolaris', 'Polaris:DeviceConnect', 'Polaris:DeviceDisconnect',
    'Polaris:bleEnableWifi', 'Polaris:ConfigUpdate', 'Polaris:RestartDriver', 'Polaris:StopDriver',
}


def load_connection_events(log_filenames, log_dir='.'):
    """
    Parse the driver's connection-lifecycle log lines -- process (re)starts, socket
    disconnects, reconnect attempts (both flavors -- see below), successful re-inits, WiFi
    interface/join events, and the client REST actions that drive/observe reconnection
    (Polaris:ConnectPolaris, ConfigUpdate, etc.) -- into a single DataFrame, sorted by the
    timestamp *embedded in each line*, not by which file it came from.

    That sort is not optional: rotated log files are numbered by *reverse* recency (a fresh
    'alpaca.log' plus '.1', '.2', ... or an equivalent NN-suffixed archive naming), so
    concatenating them in filename order silently interleaves events backwards -- confirmed
    the hard way while diagnosing a real overnight dropout (docs/study_pec_motor_space_v2.md): the
    file holding the disconnect (...a12.log) chronologically *precedes* the file holding the
    successful reconnect (...a11.log), the opposite of their filename order.

    Two distinct connect-failure 'kind's, both surfaced by control.py/polaris.py's own
    error-formatting (_format_connection_error), worth telling apart:
      - 'connect_attempt_failed' -- a fresh TCP connect attempt itself failed/timed out
        (attempt_polaris_connect()) -- there was no established connection to lose, so this
        repeats every ~15s during the retry backoff with no driver restart in between.
      - 'reconnect_error' -- an *established* connection broke, from read_msgs()'s own
        except-Exception block (`==ERROR== read_msgs failed: ...`). This includes the
        5s-no-518-telemetry watchdog specifically (detail starts with '==ERROR==: No
        position update for over 5s...', from polaris.py's _every_500ms_watchdog_check()
        raising WatchdogError) as well as any other send/receive failure on an
        already-open socket -- see _CONNECTION_ERROR_TAXONOMY / the error_code column for
        telling them apart.
    'disconnect' is the raw socket-level event itself (read_msgs()'s own read-loop except
    block, carrying the raw OS/Python exception text, e.g. a WinError) -- usually
    immediately followed by a run of 'connect_attempt_failed' events as the retry loop
    tries to re-establish a fresh connection. Note a hard 'disconnect' can happen *before*
    the 5s watchdog ever gets a chance to fire -- distinguish the two from trigger_kind/
    trigger_detail, don't assume every outage is the 5s-watchdog case.

    Two more non-outage-triggering kinds exist purely for context/taxonomy, because
    read_msgs() re-logs (and reconstruct_outages() re-counts) the same failure a moment
    later as 'reconnect_error': 'cmd_timeout' (a _await_cmd_response() timeout, usually
    cmd 284 during init) and 'send_error' (a failed socket write). 'ble_wifi_failed'/
    'ble_error' cover Polaris:bleEnableWifi failing to turn the Polaris's own Wi-Fi radio
    on over Bluetooth -- distinct from 'wifi_join_failed', which is the *host's* netsh
    join to the Polaris hotspot failing.

    Every row whose kind represents an actual failure (disconnect, reconnect_error,
    connect_attempt_failed, wifi_join_failed, cmd_timeout, send_error, ble_wifi_failed,
    ble_error) gets three extra columns via classify_connection_error() applied to its
    `detail`: 'error_code' (a short stable id, e.g. 'WSAECONNRESET'), 'error_meaning' (a
    one-line human explanation, with a docs/troubleshooting.md section reference where one
    exists), and 'error_category' (a coarser grouping for charting -- 'watchdog',
    'peer_reset', 'link_degraded', 'unreachable', 'wifi_join', 'ble', 'config_state',
    'other', ...). NaN for every other kind (driver_start, init_start/done, sync_observed,
    config_update, client_action) -- there's no error to classify on those.

    'config_update' rows additionally carry every key of the REST call's own Parameters dict
    as a 'param_<key>' column (e.g. param_log_position) -- added because a config toggle
    mid-outage (e.g. log_position turned off while troubleshooting, then back on later) can
    otherwise look exactly like a real KFLOG/PIDLOG data gap to another notebook; cross-check
    against this table (or use reconstruct_outages(), which does this automatically) before
    treating a coincident gap as itself evidence of an outage's true start/end.

    Returns an empty DataFrame, not an error, when none are found.
    """
    paths = resolve_log_files(log_filenames, log_dir=log_dir)
    rows = []
    for log_path in paths:
        if not os.path.exists(log_path):
            raise FileNotFoundError(f"log_path does not exist: {log_path!r}")
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _CLIENT_ACTION_RE.match(line)
                if m:
                    try:
                        body = ast.literal_eval(m.group("body"))
                    except (ValueError, SyntaxError):
                        body = None
                    action = body.get('Action') if isinstance(body, dict) else None
                    if action in _INTERESTING_ACTIONS:
                        kind = 'config_update' if action == 'Polaris:ConfigUpdate' else 'client_action'
                        row = dict(timestamp=m.group("ts"), kind=kind, action=action,
                                   client=body.get('ClientID'), detail=action)
                        if kind == 'config_update':
                            params = body.get('Parameters')
                            if isinstance(params, dict):
                                for k, v in params.items():
                                    row[f'param_{k}'] = v
                        rows.append(row)
                    continue
                for kind, pattern, extractor in _CONN_EVENT_PATTERNS:
                    pm = pattern.match(line)
                    if not pm:
                        continue
                    row = dict(timestamp=pm.group("ts"), kind=kind)
                    row.update(extractor(pm) if extractor else
                               {k: v for k, v in pm.groupdict().items() if k != 'ts'})
                    rows.append(row)
                    break

    df = pd.DataFrame(rows)
    if len(df):
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
        # Plain drop_duplicates() fails outright on a config_update row whose param_<key>
        # value is a list (e.g. Polaris:ConfigUpdate's kf_measure_noise/kf_process_noise
        # arrays) -- pandas can't hash a list to dedupe on it. Dedupe on the stringified
        # row instead; harmless for every other row, whose values are already scalar.
        df = df.loc[~df.astype(str).duplicated()].reset_index(drop=True)
        df["t_sec"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds()

        # A plain index loop, not df.apply(axis=1) -- apply() collapses to a DataFrame
        # instead of a Series of tuples whenever exactly one row is classifiable (a common
        # case for a single short capture), silently breaking the zip-into-columns below.
        idx = df.index[df["kind"].isin(_CLASSIFIABLE_ERROR_KINDS)]
        codes, meanings, categories = [], [], []
        for i in idx:
            code, meaning, category = classify_connection_error(df.at[i, "detail"], df.at[i, "kind"])
            codes.append(code); meanings.append(meaning); categories.append(category)
        df["error_code"] = pd.Series(codes, index=idx, dtype="object")
        df["error_meaning"] = pd.Series(meanings, index=idx, dtype="object")
        df["error_category"] = pd.Series(categories, index=idx, dtype="object")
    return df


def reconstruct_outages(connection_events_df):
    """
    Walk load_connection_events()'s chronological event stream and collapse it into discrete
    outage spans -- a 'disconnect'/'reconnect_error' event through to the next 'init_done' --
    with full context on what happened in between. Exists because a real multi-file overnight
    outage (docs/study_pec_motor_space_v2.md) turned out to span two separate driver-restart
    attempts and a client config change (log_position toggled off, then back on, mid-outage),
    none of which is obvious from any single line. It also matters for a subtler reason: a
    naive KFLOG-gap-based estimate of "how long was the outage" can undershoot badly -- in
    that same incident, the driver's KF/PID control loop kept ticking and being logged for
    roughly 20 more minutes on dead-reckoned predictions alone after the real connection had
    already died, only actually stopping when a client happened to also toggle
    Config.log_position off mid-outage -- so the true connection-level outage (~30 min) was
    nearly double what the KFLOG-visible gap alone suggested (~15 min). Always prefer this
    reconstruction's outage_start/outage_end over a raw telemetry-gap boundary when the two
    disagree.

    For each outage: trigger_kind/trigger_detail (what broke it -- see load_connection_events()
    for the 'disconnect' vs 'reconnect_error' vs 'connect_attempt_failed' distinction),
    n_connect_attempts_failed (retry count during the outage), driver_restarted (whether a
    fresh ==STARTUP== happened mid-outage -- a real process/OS restart, not just a retry),
    n_driver_restarts, wifi_join_failed (whether a WiFi rejoin was attempted and failed during
    it), config_changes (list of {timestamp, params} for any Polaris:ConfigUpdate seen
    mid-outage). An outage still open when the event stream ends (no 'init_done' after the
    last trigger) gets outage_end=NaT, ongoing=True -- e.g. the capture was stopped, or the
    log files loaded don't extend far enough to see the eventual recovery.
    """
    if not len(connection_events_df):
        return pd.DataFrame()

    events = connection_events_df.sort_values('timestamp', kind='stable').reset_index(drop=True)
    outages = []
    down = False
    cur = None

    def _new_outage(ev):
        return dict(
            outage_start=ev.timestamp, trigger_kind=ev.kind,
            trigger_detail=ev.get('detail'),
            n_connect_attempts_failed=0, driver_restarted=False, n_driver_restarts=0,
            wifi_join_failed=False, config_changes=[],
        )

    for _, ev in events.iterrows():
        if ev.kind in ('disconnect', 'reconnect_error'):
            if not down:
                cur = _new_outage(ev)
                down = True
        elif ev.kind == 'connect_attempt_failed' and down:
            cur['n_connect_attempts_failed'] += 1
        elif ev.kind == 'driver_start' and down:
            cur['driver_restarted'] = True
            cur['n_driver_restarts'] += 1
        elif ev.kind == 'wifi_join_failed' and down:
            cur['wifi_join_failed'] = True
        elif ev.kind == 'config_update' and down:
            params = {k[len('param_'):]: ev[k] for k in ev.index
                      if k.startswith('param_') and _param_present(ev[k])}
            cur['config_changes'].append(dict(timestamp=ev.timestamp, params=params))
        elif ev.kind == 'init_done' and down:
            cur['outage_end'] = ev.timestamp
            cur['ongoing'] = False
            outages.append(cur)
            down = False
            cur = None

    if down and cur is not None:
        cur['outage_end'] = pd.NaT
        cur['ongoing'] = True
        outages.append(cur)

    out = pd.DataFrame(outages)
    if len(out):
        out['duration_min'] = (out['outage_end'] - out['outage_start']).dt.total_seconds() / 60
    return out


def window_df(df, t_from=None, t_to=None):
    """
    Rows of df whose 'timestamp' lies in [t_from, t_to] (either may be None for open-ended,
    both None returns df unchanged). If df has a t_sec column it is restarted from 0 at the
    first kept row, so plots of a windowed multi-target night start at the window. Lets a
    notebook cut a session to one PEC run (e.g. between gotos).
    """
    if df is None or df.empty or (t_from is None and t_to is None):
        return df
    keep = pd.Series(True, index=df.index)
    if t_from is not None:
        keep &= df['timestamp'] >= pd.Timestamp(t_from)
    if t_to is not None:
        keep &= df['timestamp'] <= pd.Timestamp(t_to)
    out = df[keep].reset_index(drop=True)
    if 't_sec' in out.columns and len(out):
        out['t_sec'] = (out['timestamp'] - out['timestamp'].iloc[0]).dt.total_seconds()
    return out


_PHD2_GUIDING_BEGINS_RE = re.compile(r"^Guiding Begins at (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
_PHD2_GUIDING_ENDS_RE   = re.compile(r"^Guiding Ends at (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
_PHD2_CAL_BEGINS_RE     = re.compile(r"^Calibration Begins at (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
_PHD2_PIXEL_SCALE_RE    = re.compile(r"^Pixel scale = ([\d.]+) arc-sec/px")
_PHD2_GUIDE_SPEED_RE    = re.compile(r"^RA Guide Speed = ([\d.]+) a-s/s, Dec Guide Speed = ([\d.]+) a-s/s")
_PHD2_FRAME_RE          = re.compile(r"^\d+,[\d.]+,\"")


def load_phd2_guidelog(path):
    """
    Parse a PHD2 guide log (PHD2_GuideLog_*.txt) into (frames, events) DataFrames, so a
    notebook can compare PEC with what the guider actually saw and did.

    frames: one row per guided frame ("Mount" rows; DROP/star-lost frames are events instead)
        timestamp, segment (0-based guiding segment), frame,
        ra_arcsec / dec_arcsec   raw guide error, using that segment's pixel scale
        ra_ms / dec_ms           pulse duration, signed like the driver's pulse residuals:
                                 East/North positive, West/South negative
        ra_pulse_arcsec / dec_pulse_arcsec   ms x that segment's RA/Dec guide speed
    events: timestamp, kind, detail -- kind is calibration, guiding_start, guiding_end,
        dither or star_lost. INFO lines carry no time of their own, so a dither is stamped
        with the frame before it.

    PHD2 writes local times, the same clock as the driver log, so the two line up directly.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"PHD2 guide log does not exist: {path!r}")

    frames, events = [], []
    seg, seg_start = -1, None
    pixel_scale, ra_speed, dec_speed = 1.0, 15.0, 15.0
    last_ts = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip('\n')
            m = _PHD2_CAL_BEGINS_RE.match(line)
            if m:
                last_ts = pd.Timestamp(m.group(1))
                events.append(dict(timestamp=last_ts, kind='calibration', detail=''))
                continue
            m = _PHD2_GUIDING_BEGINS_RE.match(line)
            if m:
                seg += 1
                seg_start = last_ts = pd.Timestamp(m.group(1))
                events.append(dict(timestamp=seg_start, kind='guiding_start', detail=''))
                continue
            m = _PHD2_GUIDING_ENDS_RE.match(line)
            if m:
                events.append(dict(timestamp=pd.Timestamp(m.group(1)), kind='guiding_end', detail=''))
                seg_start = None
                continue
            m = _PHD2_PIXEL_SCALE_RE.match(line)
            if m:
                pixel_scale = float(m.group(1))
                continue
            m = _PHD2_GUIDE_SPEED_RE.match(line)
            if m:
                ra_speed, dec_speed = float(m.group(1)), float(m.group(2))
                continue
            if line.startswith('INFO: DITHER') and seg_start is not None:
                events.append(dict(timestamp=last_ts, kind='dither', detail=line[6:]))
                continue
            if seg_start is None or not _PHD2_FRAME_RE.match(line):
                continue
            p = line.split(',')
            ts = seg_start + pd.Timedelta(seconds=float(p[1]))
            last_ts = ts
            if p[2] != '"Mount"':
                events.append(dict(timestamp=ts, kind='star_lost', detail=p[-1].strip('"')))
                continue
            ra_ms  = int(float(p[9] or 0))  * {'E': 1, 'W': -1}.get(p[10], 0)
            dec_ms = int(float(p[11] or 0)) * {'N': 1, 'S': -1}.get(p[12], 0)
            frames.append(dict(
                timestamp=ts, segment=seg, frame=int(p[0]),
                ra_arcsec=float(p[5] or 0) * pixel_scale, dec_arcsec=float(p[6] or 0) * pixel_scale,
                ra_ms=ra_ms, dec_ms=dec_ms,
                ra_pulse_arcsec=ra_ms / 1000 * ra_speed, dec_pulse_arcsec=dec_ms / 1000 * dec_speed,
            ))

    frames = pd.DataFrame(frames, columns=['timestamp', 'segment', 'frame', 'ra_arcsec', 'dec_arcsec',
                                           'ra_ms', 'dec_ms', 'ra_pulse_arcsec', 'dec_pulse_arcsec'])
    events = pd.DataFrame(events, columns=['timestamp', 'kind', 'detail'])
    return frames, events


def frame_shift_components(kf_df, sync_times, step_before_s=(25, 2), step_after_s=(10, 35), ripple_window_s=60.0,
                           break_arcsec=600.0, settle_s=60.0):
    """
    KFLOG's per-motor frame shift, theta_meas_raw - theta_ref_raw (arcsec): the raw motor angle minus the PID's
    target in corrected motor space, i.e. minus every correction applied so far (MAC + sync guide + pulse guide +
    PEC) expressed as motor angles, plus the PID's own tracking error. Split into:
      staircase -- the step at each sync (median shift 10-35 s after minus 2-25 s before), accumulated
      smooth    -- what's left after removing the staircase, smoothed over ripple_window_s (change between syncs:
                   PEC's continuous correction, MAC changing with pose, slow tracking error)
      ripple    -- shift minus its ripple_window_s rolling median (PID error, speed-controller dither, M3 hold)
    Gotos/slews while tracking make the shift jump by degrees between consecutive samples (> break_arcsec on any
    motor): each jump is removed from the series (the offset is subtracted from what follows) and the settle_s
    after it is left out of the ripple, so they don't count as divergence; summary.attrs['breaks'] counts them.
    Returns (components DataFrame, per-motor summary DataFrame). summary.attrs['m1_m3_amplification'] is
    1 / sin(median theta2): when M2 is near 0 the M1 and M3 axes line up, and a small correction on the sky
    needs large, opposite M1/M3 rotations -- mirror-image M1/M3 shifts there are geometry, not mount error.
    """
    kf = kf_df.sort_values('timestamp').reset_index(drop=True)
    t = (kf['timestamp'] - kf['timestamp'].iloc[0]).dt.total_seconds().values
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0
    win = max(3, int(round(ripple_window_s / dt)) | 1)
    syncs = [(pd.Timestamp(s) - kf['timestamp'].iloc[0]).total_seconds() for s in sync_times]
    syncs = [s for s in syncs if t[0] <= s <= t[-1]]
    comp = pd.DataFrame({'timestamp': kf['timestamp'], 't_min': t / 60})
    raw = {i: (((kf[f'θ_meas_raw_{i}'] - kf[f'θ_ref_raw_{i}'] + 180) % 360) - 180).values * 3600 for i in (1, 2, 3)}
    jumps = np.zeros(len(t), bool)
    for i in (1, 2, 3):
        jumps[1:] |= np.abs(np.diff(raw[i])) > break_arcsec
    brk = np.where(jumps)[0]
    settling = np.zeros(len(t), bool)
    for b in brk:
        settling |= (t >= t[b]) & (t < t[b] + settle_s)
    rows = {}
    for i in (1, 2, 3):
        m = f'M{i}'
        shift = raw[i].copy()
        for b in brk:                                       # remove each goto jump from what follows
            shift[b:] -= shift[b] - shift[b - 1]
        stair = np.zeros(len(t))
        steps = []
        for s in syncs:
            a = shift[(t > s - step_before_s[0]) & (t < s - step_before_s[1])]
            b = shift[(t > s + step_after_s[0]) & (t < s + step_after_s[1])]
            if len(a) > 3 and len(b) > 3:
                step = float(np.median(b) - np.median(a))
                steps.append(step)
                stair += np.where(t >= s, step, 0.0)
        rolling = pd.Series(shift).rolling(win, center=True, min_periods=max(3, win // 5)).median().values
        smooth = pd.Series(shift - stair).rolling(win, center=True, min_periods=max(3, win // 5)).median().values
        ripple = np.where(settling, np.nan, shift - rolling)
        comp[f'{m} shift'], comp[f'{m} staircase'], comp[f'{m} smooth'], comp[f'{m} ripple'] = shift, stair, smooth, ripple
        k = max(1, min(len(t) // 20, int(round(30 / dt))))
        net = float(np.mean(shift[-k:]) - np.mean(shift[:k]))
        rows[m] = {'net change "': net, 'range "': float(np.ptp(shift)), 'syncs': len(steps),
                   'sync steps sum "': float(np.sum(steps)) if steps else 0.0,
                   'median |step| "': float(np.median(np.abs(steps))) if steps else 0.0,
                   'between syncs "': net - (float(np.sum(steps)) if steps else 0.0),
                   'ripple rms "': float(np.nanstd(ripple))}
    summary = pd.DataFrame(rows).T
    theta2 = float(np.median(np.abs(kf['θ_ref_raw_2'])))
    summary.attrs['m1_m3_amplification'] = 1.0 / max(np.sin(np.radians(theta2)), 1e-3)
    summary.attrs['breaks'] = int(len(brk))
    summary.attrs['theta2_deg'] = theta2
    return comp, summary


def ramp_vs_next_step(comp, sync_times, before_s=(25, 2), after_s=(10, 35)):
    """
    For each interval between syncs: the frame shift's change over the interval (the "ramp": PEC's continuous
    correction, MAC changing with pose) vs the step at the next sync (the plate-solve correction). Per motor:
    ramp/step RMS, their correlation, and the share of the ramp the next sync undoes (-sum(ramp*step)/sum(ramp^2)).
    A working PEC ramps WITH the drift, so the next step is small and not opposed (share ~0). Correlation near -1
    with share ~1 means each sync reverses what PEC applied in between: PEC and the sync guiding are fighting.
    """
    t = comp['t_min'].values * 60
    t0 = comp['timestamp'].iloc[0]
    st = [(pd.Timestamp(s) - t0).total_seconds() for s in sync_times]
    st = [s for s in st if t[0] <= s <= t[-1]]
    rows = {}
    for i in (1, 2, 3):
        sh = comp[f'M{i} shift'].values
        R, S = [], []
        for a, b in zip(st[:-1], st[1:]):
            p = sh[(t > a + after_s[0]) & (t < a + after_s[1])]
            q = sh[(t > b - before_s[0]) & (t < b - before_s[1])]
            r = sh[(t > b + after_s[0]) & (t < b + after_s[1])]
            if len(p) > 3 and len(q) > 3 and len(r) > 3:
                R.append(np.median(q) - np.median(p))
                S.append(np.median(r) - np.median(q))
        R, S = np.array(R), np.array(S)
        ok = len(R) >= 5 and np.sum(R * R) > 0
        rows[f'M{i}'] = {'intervals': len(R), 'ramp rms "': float(np.sqrt(np.mean(R ** 2))) if len(R) else np.nan,
                         'step rms "': float(np.sqrt(np.mean(S ** 2))) if len(S) else np.nan,
                         'corr': float(np.corrcoef(R, S)[0, 1]) if ok and np.std(S) > 0 else np.nan,
                         'share undone': float(-np.sum(R * S) / np.sum(R * R)) if ok else np.nan}
    return pd.DataFrame(rows).T


def _centred_slope_per_min(t_sec, y, half_window_s, segment=None):
    """Slope of y (per minute) over +-half_window_s around each row. With `segment` (an id per row, e.g. the PEC run
    between resets), a window never crosses into another segment: near a boundary it is clipped to its own side, so a
    step at a reset (worm feed-forward switched off, a goto) doesn't smear into the rates before and after it. A
    window shorter than half_window_s in all (the very ends) gives NaN."""
    t_sec = np.asarray(t_sec, float)
    seg = np.zeros(len(t_sec), int) if segment is None else np.asarray(segment)
    out = np.full(len(t_sec), np.nan)
    for s_id in np.unique(seg):
        idx = np.flatnonzero(seg == s_id)
        ts, ys = t_sec[idx], np.asarray(y, float)[idx]
        lo = np.searchsorted(ts, ts - half_window_s, side='left')
        hi = np.searchsorted(ts, ts + half_window_s, side='right')
        for k in range(len(ts)):
            span = min(ts[k] + half_window_s, ts[-1]) - max(ts[k] - half_window_s, ts[0])
            if hi[k] - lo[k] < 3 or span < half_window_s:
                continue
            out[idx[k]] = np.polyfit(ts[lo[k]:hi[k]] - ts[k], ys[lo[k]:hi[k]], 1)[0] * 60
    return out


def correction_breakdown(df, rate_half_window_s=300.0):
    """
    Who corrected the mount's drift, per axis, from PECLOG (one PEC run or a windowed session):
      mount_drift  = pulse_guide + sync_guide + pec_applied + worm_ff   running totals in arcsec (driver correction
                     convention), joined across PEC model resets (total_accum restarts at each reset; these don't)
      worm_ff      = the worm feed-forward's correction (PECLOG wff, Config.pec_worm_ff) since the first row: on those
                     nights the guide corrections lack what it corrected, so mount drift adds it back (0 when off)
      drift_for_pec = mount_drift - worm_ff: the drift PEC drift correction is there to follow (the worm feed-forward
                     handles the rest)
      *_rate       = centred slope of each over +-rate_half_window_s, arcsec/min, within each PEC run (a window never
                     crosses a reset, e.g. the worm feed-forward switched on or off); drift_rate = sum of the others
      pec_model_rate   = the rate the driver's PEC model gave (fit_rate), arcsec/min (= arcmin/hr)
      pec_applied_logged_rate = the rate PEC actually applied (0 while inhibited); pec_active = inhibit == VALID
    A sync-guide row carries both axes' residuals, a pulse-guide row only one; pec_accum is counted only on that
    axis's own rows (it is logged on every row but folded into the model only when that axis is ingested).
    Returns {'ra': DataFrame, 'dec': DataFrame, 'resets': Series of reset timestamps}.
    """
    d = df.sort_values('timestamp').reset_index(drop=True)
    is_sync = d['resid_1'].notna() & d['resid_2'].notna()
    resets = d.loc[np.r_[False, np.diff(d['n'].values) < 0], 'timestamp'].reset_index(drop=True)
    out = {'resets': resets}
    for ax, i in (('ra', 1), ('dec', 2)):
        own = d[f'resid_{i}'].notna()
        x = d.loc[own, ['timestamp', 't_sec']].copy()
        resid = d.loc[own, f'resid_{i}'] * 60
        sync = is_sync[own]
        x['pulse_guide'] = resid.where(~sync, 0.0).cumsum().values
        x['sync_guide'] = resid.where(sync, 0.0).cumsum().values
        x['pec_applied'] = (d.loc[own, f'pec_accum_{i}'].fillna(0) * 60).cumsum().values
        if f'wff_{i}' in d:
            w = (pd.to_numeric(d[f'wff_{i}'], errors='coerce').ffill().fillna(0.0) * 60)[own].values  # level, arcsec
            x['worm_ff'] = w - w[0] if len(w) else w
        else:
            x['worm_ff'] = 0.0
        x['mount_drift'] = x['pulse_guide'] + x['sync_guide'] + x['pec_applied'] + x['worm_ff']
        x['drift_for_pec'] = x['mount_drift'] - x['worm_ff']
        t = x['t_sec'].values
        run = np.searchsorted(resets.values, x['timestamp'].values, side='right')      # PEC run: 0 before the 1st reset
        for col in ('mount_drift', 'pulse_guide', 'sync_guide', 'pec_applied', 'worm_ff', 'drift_for_pec'):
            name = 'drift_rate' if col == 'mount_drift' else f'{col}_rate'
            x[name] = _centred_slope_per_min(t, x[col].values, rate_half_window_s, segment=run)
        x['pec_model_rate'] = d.loc[own, f'fit_rate_{i}'].values if f'fit_rate_{i}' in d else np.nan
        x['pec_applied_logged_rate'] = d.loc[own, f'applied_rate_{i}'].values if f'applied_rate_{i}' in d else np.nan
        x['pec_active'] = (d.loc[own, f'inhibit_{i}'] == 'VALID').values if f'inhibit_{i}' in d else True
        out[ax] = x.reset_index(drop=True)
    return out


_BLC_RE = re.compile(r'^(?P<ts>\S+) \S+ ->> Polaris: BACKLASH (?P<msg>.*)$')
_BLC_MOTORS_RE = re.compile(r'M[123]')


def load_blc_events(log_filenames, log_dir='.'):
    """
    Backlash Compensation's events, from the driver log's '->> Polaris: BACKLASH ...' lines (control_backlash.py):
      latch      a planned tracking reversal latched ('M3 reversing its tracking direction in 10 s: ...')
      take_up    a push through a motor's slack ('taking up slack: M3 +288"'), after a goto or through a reversal
      given_up   compensation stopped for a motor that crossed its slack more than MAX_CROSSINGS times
    Its per-tick state (adjustment, push, hold) is only in PIDLOG's blc (log_position), so these mark where BLC acted,
    not how far it moved the sky. Returns DataFrame: timestamp, kind, motors (e.g. 'M1,M3'), detail; empty if none.
    """
    rows = []
    for log_path in resolve_log_files(log_filenames, log_dir=log_dir):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if 'BACKLASH' not in line:
                    continue
                m = _BLC_RE.match(line.rstrip('\n'))
                if not m:
                    continue
                msg = m.group('msg')
                if msg.startswith('taking up slack:'):
                    kind, detail = 'take_up', msg.split(':', 1)[1].strip()
                elif msg.startswith('compensation stopped'):
                    kind, detail = 'given_up', msg
                elif 'reversing its tracking direction' in msg:
                    kind, detail = 'latch', msg
                else:
                    continue
                motors = ','.join(dict.fromkeys(_BLC_MOTORS_RE.findall(msg.split(':')[0] if kind != 'take_up' else detail)))
                rows.append(dict(timestamp=pd.Timestamp(m.group('ts')), kind=kind, motors=motors, detail=detail))
    out = pd.DataFrame(rows, columns=['timestamp', 'kind', 'motors', 'detail'])
    return out.sort_values('timestamp', kind='stable').reset_index(drop=True)


SLIP_ARCSEC = 8.0                                     # M2 stepping back more than this against its motion in one step
SLIP_SPEED_BINS = (0, 2, 5, 8, 11, 15, 25, 60)         # M2 speed bins ("/s) for m2_slip_summary


def m2_slips(df, slip_arcsec=SLIP_ARCSEC, max_step_s=3.0, window=61, max_rate=60.0, still_rate=0.3, pose_every=30):
    """
    M2 slips while tracking: with a heavy payload M2 can creep ahead and then slip back 10-30" at once, which the
    guider sees as a kick (seen with a 300 mm f/2.8 while M2 lifted it, 8 Oct 2026). Found in PECLOG's motor angles
    (theta_raw), ~1 s apart while pulse guiding.

    Per step between consecutive rows (no more than max_step_s apart, M2 under max_rate "/s): M2's local speed (the
    median over `window` steps), the step's departure from it, and whether it slipped (stepped back more than
    slip_arcsec against its motion; either way when M2 is still). direction: whether M2's motion lifts or lowers
    the lens (its altitude), or 'still' (under still_rate "/s), from the pose every `pose_every` steps.
    Returns DataFrame: timestamp, dt, rate ("/s), resid ("), size (" back), slip, direction.
    """
    from kinematics import theta_to_q, q_to_azaltroll
    cols = ['timestamp', 'dt', 'rate', 'resid', 'size', 'slip', 'direction']
    d = df.dropna(subset=['theta_raw_2']).sort_values('t_sec').reset_index(drop=True)
    if len(d) < 3:
        return pd.DataFrame(columns=cols)
    t = d['t_sec'].to_numpy(float)
    th = d[['theta_raw_1', 'theta_raw_2', 'theta_raw_3']].to_numpy(float)
    dt = np.diff(t)
    step = np.diff(th[:, 1]) * 3600
    ok = (dt > 0.2) & (dt <= max_step_s)
    rate = pd.Series(np.where(ok, step / np.where(dt > 0, dt, 1), np.nan)).rolling(
        window, center=True, min_periods=window // 3).median().to_numpy()
    resid = step - rate * dt
    keep = ok & np.isfinite(rate) & (np.abs(rate) < max_rate)
    size = np.where(np.abs(rate) > still_rate, -np.sign(rate) * resid, np.abs(resid))
    # does M2 turning up raise the lens? the altitude's change with M2, at a pose every pose_every steps
    rows = np.arange(0, len(dt), pose_every)
    up = []
    for i in rows:
        alt = [q_to_azaltroll(theta_to_q(*(th[i] + [0, s, 0])))[1] for s in (-0.01, 0.01)]
        up.append(np.sign(alt[1] - alt[0]))
    up = np.asarray(up)[np.minimum(np.round(np.arange(len(dt)) / pose_every).astype(int), len(rows) - 1)]
    direction = np.where(np.abs(rate) < still_rate, 'still', np.where(up * rate > 0, 'lifting', 'lowering'))
    out = pd.DataFrame({'timestamp': d['timestamp'].iloc[1:].to_numpy(), 'dt': dt, 'rate': rate, 'resid': resid,
                        'size': size, 'slip': (size > slip_arcsec) & (np.abs(resid) < 120), 'direction': direction})
    return out[keep].reset_index(drop=True)


def m2_slip_summary(steps, frames=None, speed_bins=SLIP_SPEED_BINS, sky_jump_arcsec=6.0, sky_within_s=4.0):
    """
    Slips per hour of tracking by direction (lifting, lowering, still) and M2 speed ("/s), from m2_slips(). With PHD2
    frames (load_phd2_guidelog), also the share of slips the guider saw: a frame-to-frame jump of the guide star
    over sky_jump_arcsec within sky_within_s after the slip.
    """
    s = steps.copy()
    labels = [f'{a}-{b}' for a, b in zip(speed_bins[:-1], speed_bins[1:])]
    s['speed'] = pd.cut(s['rate'].abs(), speed_bins, labels=labels, include_lowest=True)
    if frames is not None and len(frames):
        f = frames.sort_values('timestamp')
        jumps = f.loc[np.hypot(f['ra_arcsec'].diff(), f['dec_arcsec'].diff()) > sky_jump_arcsec, 'timestamp'].to_numpy()
        ts = s['timestamp'].to_numpy()
        i = np.searchsorted(jumps, ts)
        nxt = jumps[np.minimum(i, len(jumps) - 1)] if len(jumps) else np.full(len(ts), np.datetime64('NaT'))
        s['seen'] = (i < len(jumps)) & ((nxt - ts) <= np.timedelta64(int(sky_within_s * 1000), 'ms'))
    rows = []
    for (direction, speed), g in s.groupby(['direction', 'speed'], observed=True):
        hours = g['dt'].sum() / 3600
        slips = g[g['slip']]
        row = {'direction': direction, 'speed': speed, 'hours': round(hours, 2), 'slips': len(slips),
               'slips per hour': len(slips) / hours if hours else np.nan,
               'median size "': round(float(slips['size'].median()), 1) if len(slips) else np.nan}
        if 'seen' in s:
            row['seen by guider %'] = round(100 * slips['seen'].mean()) if len(slips) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


# ── Goto response (utility/goto_response.py runs, utility/analyse_goto_response.ipynb) ─────────
# Analysis of utility/goto_response.py runs, from a driver log with log_position on (used by
# utility/analyse_goto_response.ipynb). Each run is split from the log by its REPLAYLOG 'begin' marker and each
# leg by its 'start'/'end' markers; PIDLOG (every control tick, ~0.2 s) gives the planned motor angles (θ_sp),
# the measured ones (θ_pv), the speed commanded to each motor (ω_op) and the PID terms.
#
# Per leg and moving motor: the theoretical minimum time of an independent-motor move (each motor accelerating,
# cruising, decelerating within its limits, the slowest deciding), the arrival (within 1' from then on; tracking:
# of the tracked setpoint, and also the time to the tracking tolerance pid_Kc/20), the commanded vs measured
# speed, the response delay, how far the motor fell behind its reference, overshoot and the final error. See
# docs/study_goto_response.md.

GR_GOTO_RATE_SHARE = 0.8                      # the planner moves at this share of Kv (control.PID_Controller)
GR_KV_DEFAULT = (8.92, 7.66, 7.99)            # the motors' max speeds, deg/s (the FAST 2500 calibration)
GR_KA_DEFAULT = 5.0                           # acceleration, deg/s^2 (pid_Ka 0 -> 5)
GR_KP_DEFAULT = (1.0, 1.0, 1.0)               # config.toml pid_Kp
GR_KD_DEFAULT = (0.5, 0.5, 0.8)               # config.toml pid_Kd
GR_ARRIVE_DEG = 1.0 / 60                      # arrival: within 1'
GR_TIGHT_DEG = 0.75 / 60 / 20                 # the tracking completion tolerance: pid_Kc / 20
GR_REF_SETTLED_DEG = 0.2                      # tracking: the setpoint has reached the target (sky motion aside)
GR_SIDEREAL_DEG_S = 0.0042
GR_MOVING_DEG = 0.2                           # a motor moves in a leg if its target is this far away

def load_goto_response(path):
    """(pid ticks [(t, θ_sp, θ_pv, ω_op, terms, mode)], goto_response markers [(t, dict)], battery [(t, %, charging)])."""
    pid, marks, battery = [], [], []
    for line in open(path, encoding="utf-8", errors="replace"):
        if " PIDLOG " in line:
            r = parse_payload_line(line, "PIDLOG")
            if r is None:
                continue
            v = lambda k: np.array([r[f"{k}_{i}"] for i in (1, 2, 3)], dtype=float)
            pid.append((pd.Timestamp(r["timestamp"]).timestamp(), v("θ_sp"), v("θ_pv"), v("ω_op"),
                        {k: v(k) for k in ("ω_kp", "ω_ki", "ω_kd", "ω_ff")}, r["mode"]))
        elif " REPLAYLOG " in line or "BATTERY status changed: 778" in line:
            ts, _, body = line.partition(" INFO ")
            t = pd.Timestamp(ts.strip()).timestamp()
            d = ast.literal_eval(body[body.index("{"):].strip())
            if "REPLAYLOG" in body:
                if d.get("test") == "goto_response":
                    marks.append((t, d))
            else:
                battery.append((t, int(d["capacity"]), d["charge"] == "1"))
    return pid, marks, battery


def goto_response_runs(marks):
    """One run per 'begin' marker: [(t_begin, t_end, tracking, markers)]."""
    out = []
    for t, d in marks:
        if d.get("event") == "begin":
            out.append([t, None, bool(d.get("tracking")), []])
        elif out:
            out[-1][3].append((t, d))
            if d.get("event") == "finish":
                out[-1][1] = t
    return [(a, b if b is not None else (m[-1][0] if m else a), tr, m) for a, b, tr, m in out]


def goto_response_legs(run_marks):
    """[(name, t_start, t_end, target θ, seconds the script waited for completion)]."""
    out, start = [], {}
    for t, d in run_marks:
        if d.get("event") == "start":
            start[d["leg"]] = (t, np.array(d["target"]))
        elif d.get("event") == "end" and d["leg"] in start:
            t0, target = start.pop(d["leg"])
            out.append((d["leg"], t0, t, target, d["seconds"]))
    return out


def _gr_axis_time(d, v, a):
    """Minimum time for one motor to move d deg from rest to rest at max speed v and acceleration a."""
    d = abs(d)
    return d / v + v / a if d >= v * v / a else 2.0 * math.sqrt(d / a)


def _gr_arrival(t, err, ok=None, tol=GR_ARRIVE_DEG):
    """First time from which every motor stays within tol (and ok holds), or None."""
    good = np.all(np.abs(err) < tol, axis=1)
    if ok is not None:
        good &= ok
    bad = np.where(~good)[0]
    if not len(bad):
        return float(t[0])
    return float(t[bad[-1] + 1]) if bad[-1] + 1 < len(t) else None


def _gr_lag_s(cmd, vel, dt):
    """Delay (s) of the measured speed behind the commanded, by cross-correlation (0 to 1.5 s)."""
    best, best_k = -np.inf, 0
    for k in range(0, int(1.5 / dt) + 1):
        a, b = cmd[:len(cmd) - k], vel[k:]
        if len(a) < 5 or np.std(a) < 1e-6 or np.std(b) < 1e-6:
            continue
        c = np.corrcoef(a, b)[0, 1]
        if c > best:
            best, best_k = c, k
    return best_k * dt


def goto_response_leg_series(pid, t0, t1):
    """One leg's PIDLOG ticks as a DataFrame (t from the leg's start), per motor: sp, pv, op, measured speed vel,
    and the PID terms kp/ki/kd/ff."""
    sel = [p for p in pid if t0 <= p[0] <= t1]
    if len(sel) < 2:
        return pd.DataFrame()
    t = np.array([p[0] for p in sel]) - t0
    sp, pv, op = (np.array([p[i] for p in sel]) for i in (1, 2, 3))
    vel = np.gradient(pv, t, axis=0)
    cols = {"t": t, "mode": [p[5] for p in sel]}
    for a in range(3):
        m = f"m{a + 1}"
        cols.update({f"{m}_sp": sp[:, a], f"{m}_pv": pv[:, a], f"{m}_op": op[:, a], f"{m}_vel": vel[:, a]})
        for k in ("ω_kp", "ω_ki", "ω_kd", "ω_ff"):
            cols[f"{m}_{k[2:]}"] = [p[4][k][a] for p in sel]
    return pd.DataFrame(cols)


def goto_response_leg_table(pid, run_marks, track, kv=GR_KV_DEFAULT, ka=GR_KA_DEFAULT):
    """One row per leg and moving motor."""
    rate = np.array(kv, dtype=float) * GR_GOTO_RATE_SHARE
    rows = []
    for case, (name, t0, t1, target, done) in enumerate(goto_response_legs(run_marks)):
        s = goto_response_leg_series(pid, t0, t1)
        if len(s) < 5:
            continue
        t = s["t"].to_numpy()
        sp = s[["m1_sp", "m2_sp", "m3_sp"]].to_numpy()
        pv = s[["m1_pv", "m2_pv", "m3_pv"]].to_numpy()
        op = s[["m1_op", "m2_op", "m3_op"]].to_numpy()
        vel = s[["m1_vel", "m2_vel", "m3_vel"]].to_numpy()
        delta = target - pv[0]
        moving = [a for a in range(3) if abs(delta[a]) > GR_MOVING_DEG]
        if not moving:
            continue
        t_min = max(_gr_axis_time(delta[a], rate[a], ka) for a in range(3))
        dt = float(np.median(np.diff(t)))
        if track:
            # tracking: the setpoint steps to the target and then moves on with the sky
            err = pv - sp
            ref_done = np.all(np.abs(sp - sp[-1]) < GR_REF_SETTLED_DEG + np.abs(t - t[-1])[:, None] * GR_SIDEREAL_DEG_S, axis=1)
            t_arr, t_tight = _gr_arrival(t, err, ref_done), _gr_arrival(t, err, ref_done, GR_TIGHT_DEG)
        else:
            err, ref_done = pv - target, np.ones(len(t), dtype=bool)
            t_arr, t_tight = _gr_arrival(t, err), None
        during = t <= (t_arr if t_arr is not None else t[-1])
        for a in moving:
            sgn = np.sign(delta[a])
            cruise = np.abs(op[:, a]) > 0.5 * np.max(np.abs(op[:, a]))
            ratio = np.median(np.abs(vel[cruise, a])) / np.median(np.abs(op[cruise, a])) if cruise.sum() >= 3 else np.nan
            rows.append({
                "case": case, "leg": name, "motor": f"M{a + 1}", "move_deg": delta[a], "t_min_s": t_min,
                "t_arrive_s": t_arr, "t_tight_s": t_tight, "done_s": done,
                "cmd_peak_dps": float(np.max(np.abs(op[:, a]))), "meas_peak_dps": float(np.max(np.abs(vel[:, a]))),
                "meas_per_cmd": ratio, "lag_s": _gr_lag_s(np.abs(op[:, a]), np.abs(vel[:, a]), dt),
                "behind_ref_arcmin": float(np.max(np.abs(sp[during, a] - pv[during, a]))) * 60,
                "overshoot_arcmin": max(0.0, float(np.max(sgn * err[ref_done, a]))) * 60 if ref_done.any() else np.nan,
                "final_arcmin": float(err[-1, a]) * 60,
            })
    df = pd.DataFrame(rows)
    if len(df):
        df["late_s"] = df["t_arrive_s"] - df["t_min_s"]
        df["tight_after_s"] = df["t_tight_s"] - df["t_arrive_s"]
    return df


def goto_response_summary(pid, marks, battery, kv=GR_KV_DEFAULT, ka=GR_KA_DEFAULT, exclude=()):
    """(runs table, {run: leg table}). exclude: (run, case) pairs to leave out of the summary, e.g. a leg stopped by hand."""
    out, tables = [], {}
    for i, (t0, t1, track, run_marks) in enumerate(goto_response_runs(marks), 1):
        df = goto_response_leg_table(pid, run_marks, track, kv, ka)
        tables[i] = df
        bat = [b for b in battery if t0 - 120 <= b[0] <= t1]
        keep = df[~df["case"].isin([c for r, c in exclude if r == i])] if len(df) else df
        big = keep[keep["move_deg"].abs() >= 25] if len(keep) else keep
        row = {"run": i, "start": datetime.datetime.fromtimestamp(t0).strftime("%H:%M"),
               "tracking": track, "battery": f"{bat[0][1]}->{bat[-1][1]}%" if bat else "not reported",
               "charging_reports": f"{sum(b[2] for b in bat)}/{len(bat)}" if bat else "",
               "legs": len(goto_response_legs(run_marks)),
               "late_median_s": keep["late_s"].median() if len(keep) else np.nan,
               "overshoot_median_arcmin": keep["overshoot_arcmin"].median() if len(keep) else np.nan,
               "tight_after_median_s": keep["tight_after_s"].median() if track and len(keep) else np.nan}
        for m in ("M1", "M2", "M3"):
            b = big[big["motor"] == m] if len(big) else big
            row[f"{m}_meas_per_cmd"] = b["meas_per_cmd"].median() if len(b) else np.nan
            row[f"{m}_peak_dps"] = b["meas_peak_dps"].max() if len(b) else np.nan
        out.append(row)
    return pd.DataFrame(out), tables


def goto_response_kd_effect(pid, run_marks, legs_axes, kp=GR_KP_DEFAULT, kd=GR_KD_DEFAULT):
    """The Kd term with coordinated speed control damps the PID's own feedback command toward the feed-forward
    (ω_kd = -Kd (ω_fb - ω_ff)), so a sustained error e gets ω_fb = Kp e / (1 + Kd): the effective gain is
    1/(1 + Kd) and the error closes as a first-order decay with time constant (1 + Kd) / Kp, before the
    response delay and Ke smoothing slow it further. Per (leg, motor): the measured gain ratio and decay time
    constant against those predictions."""
    by_name = {name: (t0, t1) for name, t0, t1, _, _ in goto_response_legs(run_marks)}
    rows = []
    for name, a in legs_axes:
        if name not in by_name:
            continue
        s = goto_response_leg_series(pid, *by_name[name])
        m = f"m{a + 1}"
        t, k_p, op, ff = s["t"].to_numpy(), s[f"{m}_kp"].to_numpy(), s[f"{m}_op"].to_numpy(), s[f"{m}_ff"].to_numpy()
        e = (s[f"{m}_sp"] - s[f"{m}_pv"]).to_numpy()
        chase = (np.abs(k_p) > 0.5) & (np.abs(k_p) < 0.9 * np.abs(k_p).max())
        ratio = float(np.median((op[chase] - ff[chase]) / k_p[chase])) if chase.sum() > 3 else np.nan
        tail = (np.abs(e) < 3) & (np.abs(e) > 0.05) & (t > t[np.argmax(np.abs(e))])
        tau = float(-1 / np.polyfit(t[tail], np.log(np.abs(e[tail])), 1)[0]) if tail.sum() > 4 else np.nan
        rows.append({"leg": name, "motor": f"M{a + 1}", "gain_ratio": ratio, "predicted_ratio": 1 / (1 + kd[a]),
                     "decay_tau_s": tau, "predicted_tau_s": (1 + kd[a]) / kp[a],
                     "close_5deg_to_1arcmin_s": tau * math.log(300) if not np.isnan(tau) else np.nan})
    return pd.DataFrame(rows)


# ── Eq mode reachability (utility/analyse_span.ipynb) ──────────────────────────────────────────────────────────
# Which poses (pointing + position angle) a Polaris on an ideal wedge can reach, what the tripod cone and the rig
# tilt limit take away, and how a straight motor-angle goto between two reachable poses can pass through the tripod
# cone. Frames as the driver's: topocentric x East, y North, z Up; camera -z boresight, +x camera-up; PA the angle of
# camera-up from the direction of the north celestial pole (the driver's delta[2] = roll + parallactic angle,
# checked by eq_check_against_driver()). Motor reach is the driver's rule: camera-up (the M3 axis) within
# THETA2_MAX of the M1 axis, which the wedge points at the visible celestial pole (control_eq.wedge_alignQ_B2T). The
# vector maths is vectorised here for whole-sky grids; eq_check_against_driver() compares it with the driver's own
# kinematics (reachable_azaltroll, theta_to_q, q_to_theta). See docs/study_goto_response.md (R1).

EQ_THETA2_MAX = 81.5            # kinematics.THETA2_MAX
EQ_TRIPOD_CONE_DEG = 8.5        # the tripod: pointings within this of the nadir (altitude below -81.5)
EQ_RIG_TILT_OFF = 180.0         # config.toml eq_rig_tilt_limit default: off


def _eq_rot(q):
    """3x3 rotation matrix of a driver Quaternion (its action on the basis vectors)."""
    return np.column_stack([q.rotate(np.array(v, dtype=float)) for v in ([1, 0, 0], [0, 1, 0], [0, 0, 1])])


def eq_m1_axis(lat_deg):
    """The M1 axis (topocentric unit vector) of an ideal wedge at this latitude: the visible celestial pole."""
    from control_eq import celestial_pole_topo
    return celestial_pole_topo(lat_deg)


def eq_azalt_vec(az, alt):
    """Unit vectors (..., 3) for azimuth (from North through East) and altitude, degrees."""
    a, e = np.radians(az), np.radians(alt)
    return np.stack([np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), np.sin(e)], axis=-1)


def eq_vec_azalt(v):
    """Azimuth (0-360) and altitude (deg) of unit vectors (..., 3)."""
    v = np.asarray(v, dtype=float)
    return np.degrees(np.arctan2(v[..., 0], v[..., 1])) % 360, np.degrees(np.arcsin(np.clip(v[..., 2], -1, 1)))


def eq_hadec_to_azalt(ha, dec, lat_deg):
    """Hour angle (deg, + west) and declination to azimuth / altitude at this latitude."""
    h, d, L = np.radians(ha), np.radians(dec), math.radians(lat_deg)
    alt = np.degrees(np.arcsin(np.clip(np.sin(d) * math.sin(L) + np.cos(d) * math.cos(L) * np.cos(h), -1, 1)))
    az = np.degrees(np.arctan2(-np.cos(d) * np.sin(h), np.sin(d) * math.cos(L) - np.cos(d) * math.sin(L) * np.cos(h)))
    return az % 360, alt


def eq_pose_vectors(az, alt, pa, lat_deg):
    """Boresight and camera-up (..., 3) for pointings (az, alt) at position angle pa (deg, all broadcast together)."""
    L = math.radians(lat_deg)
    ncp = np.array([0.0, math.cos(L), math.sin(L)])
    az, alt, pa = np.broadcast_arrays(*(np.asarray(x, dtype=float) for x in (az, alt, pa)))
    b = eq_azalt_vec(az, alt)
    n = ncp - np.sum(b * ncp, axis=-1, keepdims=True) * b              # celestial north on the sky at b
    nn = np.linalg.norm(n, axis=-1, keepdims=True)
    n = np.where(nn > 1e-9, n / np.maximum(nn, 1e-12), np.array([0.0, 0.0, 1.0]))   # at the poles: any reference
    e = np.cross(n, b)
    p = np.radians(pa)[..., None]
    return b, np.cos(p) * n + np.sin(p) * e


def eq_constraints(bore, up, lat_deg, rig_tilt_limit=EQ_RIG_TILT_OFF, tripod_cone_deg=EQ_TRIPOD_CONE_DEG, level=False):
    """Boolean arrays for poses given by boresight / camera-up vectors: 'motor' (camera-up within THETA2_MAX of the
    M1 axis: the zenith when level, the pole on the wedge), 'rig' (camera-up within rig_tilt_limit of the zenith),
    'tripod' (boresight outside the tripod cone round the nadir), 'above' (boresight above the horizon), and
    'ok' (motor, rig and tripod all allow it)."""
    m1 = np.array([0.0, 0.0, 1.0]) if level else eq_m1_axis(lat_deg)
    motor = up @ m1 >= math.cos(math.radians(EQ_THETA2_MAX)) - 1e-12
    rig = up[..., 2] >= math.cos(math.radians(min(rig_tilt_limit, 180.0))) - 1e-12
    tripod = bore[..., 2] > -math.cos(math.radians(tripod_cone_deg))
    return {"motor": motor, "rig": rig, "tripod": tripod, "above": bore[..., 2] > 0, "ok": motor & rig & tripod}


def eq_sky_grid(lat_deg, az_step=2.0, alt_step=2.0, pa_step=5.0, rig_tilt_limit=EQ_RIG_TILT_OFF,
                tripod_cone_deg=EQ_TRIPOD_CONE_DEG, level=False):
    """Over an Az x Alt grid of pointings, the share (0-1) of position angles each constraint allows:
    {'az', 'alt', 'motor', 'motor_rig', 'ok', 'tripod' (0/1, the same at every PA), 'rig_tilt_min' (the least
    rig tilt any motor-reachable PA has: what a rig tilt limit must allow for the pointing to stay reachable)}, and
    'motor_either', 'motor_rig_either', 'ok_either': the same allowing an upside-down frame (PA or PA + 180).
    pa_step must divide 180."""
    az = np.arange(0, 360 + 1e-9, az_step)
    alt = np.arange(-90, 90 + 1e-9, alt_step)
    pa = np.arange(-180, 180, pa_step)
    AZ, ALT = np.meshgrid(az, alt)
    bore, up = eq_pose_vectors(AZ[..., None], ALT[..., None], pa, lat_deg)
    c = eq_constraints(bore, up, lat_deg, rig_tilt_limit, tripod_cone_deg, level)
    tilt = np.degrees(np.arccos(np.clip(up[..., 2], -1, 1)))
    tilt_min = np.where(c["motor"], tilt, np.nan)
    with np.errstate(all="ignore"):
        tilt_min = np.nanmin(np.where(np.isnan(tilt_min), np.inf, tilt_min), axis=-1)
    tilt_min[np.isinf(tilt_min)] = np.nan
    half = int(round(180 / pa_step))
    assert abs(half * pa_step - 180) < 1e-9, "pa_step must divide 180"
    either = lambda m: (m | np.roll(m, half, axis=-1)).mean(-1)          # PA or PA + 180 (upside down)
    motor_rig = c["motor"] & c["rig"]
    return {"az": az, "alt": alt, "pa": pa, "motor": c["motor"].mean(-1), "motor_rig": motor_rig.mean(-1),
            "ok": c["ok"].mean(-1), "tripod": c["tripod"].all(-1).astype(float), "rig_tilt_min": tilt_min,
            "motor_either": either(c["motor"]), "motor_rig_either": either(motor_rig), "ok_either": either(c["ok"])}


def eq_pa_grid(lat_deg, dec, ha_step=2.0, pa_step=2.0, rig_tilt_limit=EQ_RIG_TILT_OFF, tripod_cone_deg=EQ_TRIPOD_CONE_DEG):
    """For one declination, over hour angle x PA: what limits each pose, as codes 0 reachable, 1 motor reach,
    2 rig tilt, 3 tripod cone (first that applies, in the order tripod, motor, rig), plus the altitude per HA.
    'code_flip' is the same for the upside-down frame (PA + 180)."""
    ha = np.arange(-180, 180 + 1e-9, ha_step)
    pa = np.arange(-180, 180 + 1e-9, pa_step)
    az, alt = eq_hadec_to_azalt(ha, np.full_like(ha, dec), lat_deg)

    def codes(pa_):
        bore, up = eq_pose_vectors(az[:, None], alt[:, None], pa_[None, :], lat_deg)
        c = eq_constraints(bore, up, lat_deg, rig_tilt_limit, tripod_cone_deg)
        code = np.zeros(up.shape[:-1], dtype=int)
        code[~c["rig"]] = 2
        code[~c["motor"]] = 1
        code[~c["tripod"]] = 3
        return code.T                                                   # [pa, ha]

    return {"ha": ha, "pa": pa, "alt": alt, "code": codes(pa), "code_flip": codes(pa + 180.0)}


def eq_motor_pa_by_dec(lat_deg, decs, pas):
    """Motor reach alone over declination x PA (it doesn't depend on hour angle: tracking turns M1 about the pole):
    codes[dec, pa] 2 reachable, 1 reachable only upside down (PA + 180 is), 0 neither."""
    decs, pas = np.asarray(decs, float), np.asarray(pas, float)
    az, alt = eq_hadec_to_azalt(np.zeros_like(decs), decs, lat_deg)
    reach = [eq_constraints(*eq_pose_vectors(az[:, None], alt[:, None], (pas + k)[None, :], lat_deg), lat_deg)["motor"]
             for k in (0.0, 180.0)]
    return np.where(reach[0], 2, np.where(reach[1], 1, 0))


def eq_fk_vectors(theta, alignQ_B2T):
    """Boresight and camera-up (..., 3), topocentric, for motor angles theta (..., 3): the driver's theta_to_q
    (camera-up = the M3 axis, set by M1/M2; M3 turns the boresight about it) followed by the base->topo rotation."""
    t1, t2, t3 = (np.radians(np.asarray(theta, float)[..., i]) for i in range(3))
    up = np.stack([-np.sin(t2) * np.sin(t1), -np.sin(t2) * np.cos(t1), np.cos(t2)], axis=-1)
    b0 = np.stack([np.cos(t2) * np.sin(t1), np.cos(t2) * np.cos(t1), np.sin(t2)], axis=-1)
    bore = b0 * np.cos(t3)[..., None] - np.cross(up, b0) * np.sin(t3)[..., None]
    R = _eq_rot(alignQ_B2T)
    return bore @ R.T, up @ R.T


def eq_check_against_driver(lat_deg, n=2000, seed=0):
    """Compare this section's vector maths with the driver's kinematics on random poses: PA convention (deg),
    boresight, motor reach (count of disagreements: poses on the boundary can differ), and FK (deg)."""
    from kinematics import azaltroll_to_q, calc_parallactic_angle, q_to_azaltroll, reachable_azaltroll, theta_to_q
    from control_eq import wedge_alignQ_B2T
    rng = np.random.default_rng(seed)
    A = wedge_alignQ_B2T(lat_deg)
    Ai = A.inverse
    pa_err, bore_err, fk_err, reach_diff = [], [], [], 0
    for _ in range(n):
        az, alt, pa = rng.uniform(0, 360), rng.uniform(-85, 85), rng.uniform(-180, 180)
        q = azaltroll_to_q(az, alt, (pa - calc_parallactic_angle(az, alt, lat_deg) + 180) % 360 - 180)
        b_d, u_d = np.array(q.rotate([0, 0, -1.0])), np.array(q.rotate([1.0, 0, 0]))
        b, u = eq_pose_vectors(az, alt, pa, lat_deg)
        pa_err.append(math.degrees(math.acos(np.clip(u @ u_d, -1, 1))))
        bore_err.append(math.degrees(math.acos(np.clip(b @ b_d, -1, 1))))
        mine = bool(eq_constraints(b, u, lat_deg)["motor"])
        a_B = q_to_azaltroll(Ai * q)
        r_B = reachable_azaltroll(*a_B)
        drv = math.degrees(math.acos(np.clip(eq_azalt_vec(r_B[0], r_B[1]) @ eq_azalt_vec(a_B[0], a_B[1]), -1, 1))) < 0.05 \
            and abs((r_B[2] - a_B[2] + 180) % 360 - 180) < 0.05
        reach_diff += mine != drv
        th = rng.uniform([-180, -10, -180], [180, 82, 180])
        qt = A * theta_to_q(*th)
        bf, uf = eq_fk_vectors(th, A)
        fk_err.append(max(math.degrees(math.acos(np.clip(bf @ np.array(qt.rotate([0, 0, -1.0])), -1, 1))),
                          math.degrees(math.acos(np.clip(uf @ np.array(qt.rotate([1.0, 0, 0])), -1, 1)))))
    return {"poses": n, "pa_max_err_deg": max(pa_err), "bore_max_err_deg": max(bore_err),
            "reach_disagreements": reach_diff, "fk_max_err_deg": max(fk_err)}


def eq_random_poses(lat_deg, n, rng, min_alt=10.0, rig_tilt_limit=EQ_RIG_TILT_OFF):
    """n random reachable poses (az, alt, pa) above min_alt, uniform over the sky, PA uniform over the reachable
    ones (motor reach, and the rig tilt limit if set)."""
    out = []
    while len(out) < n:
        v = rng.normal(size=3)
        v /= np.linalg.norm(v)
        if v[2] < math.sin(math.radians(min_alt)):
            continue
        az, alt = eq_vec_azalt(v)
        pa = rng.uniform(-180, 180)
        b, u = eq_pose_vectors(az, alt, pa, lat_deg)
        if eq_constraints(b, u, lat_deg, rig_tilt_limit)["ok"]:
            out.append((float(az), float(alt), float(pa)))
    return np.array(out)


def eq_straight_gotos(lat_deg, n_pairs=1000, samples=61, min_alt=10.0, rig_tilt_limit=EQ_RIG_TILT_OFF,
                      tripod_cone_deg=EQ_TRIPOD_CONE_DEG, seed=0):
    """Gotos between random reachable poses above min_alt, moved straight in motor angles (the end angles from the
    driver's q_to_theta; M1 and M3 the shorter way round): per goto the least boresight nadir distance and the
    largest rig tilt along the path, and whether it enters the tripod cone / passes the rig tilt limit. Returns
    (DataFrame, paths) with paths[i] the (samples, 3) motor angles and the path's boresight az/alt."""
    from kinematics import azaltroll_to_q, calc_parallactic_angle, q_to_theta
    from control_eq import wedge_alignQ_B2T
    rng = np.random.default_rng(seed)
    A = wedge_alignQ_B2T(lat_deg)
    Ai = A.inverse
    poses = eq_random_poses(lat_deg, 2 * n_pairs, rng, min_alt, rig_tilt_limit)

    def ik(p):
        az, alt, pa = p
        q = azaltroll_to_q(az, alt, (pa - calc_parallactic_angle(az, alt, lat_deg) + 180) % 360 - 180)
        return np.array(q_to_theta(Ai * q)[:3], dtype=float)

    f = np.linspace(0, 1, samples)[:, None]
    rows, paths = [], []
    for i in range(n_pairs):
        p0, p1 = poses[2 * i], poses[2 * i + 1]
        t0, t1 = ik(p0), ik(p1)
        d = t1 - t0
        d[[0, 2]] = (d[[0, 2]] + 180) % 360 - 180
        th = t0 + f * d
        bore, up = eq_fk_vectors(th, A)
        nadir = 90 + np.degrees(np.arcsin(np.clip(bore[:, 2], -1, 1)))
        tilt = np.degrees(np.arccos(np.clip(up[:, 2], -1, 1)))
        az, alt = eq_vec_azalt(bore)
        rows.append({"az0": p0[0], "alt0": p0[1], "pa0": p0[2], "az1": p1[0], "alt1": p1[1], "pa1": p1[2],
                     "m1_0": t0[0], "m2_0": t0[1], "m3_0": t0[2], "m1_1": t1[0], "m2_1": t1[1], "m3_1": t1[2],
                     "min_nadir_deg": nadir.min(), "max_rig_tilt_deg": tilt.max(),
                     "enters_cone": bool(nadir.min() < tripod_cone_deg), "passes_tilt": bool(tilt.max() > rig_tilt_limit)})
        paths.append({"theta": th, "az": az, "alt": alt})
    return pd.DataFrame(rows), paths


def eq_cone_motor_map(lat_deg, step=2.5, tripod_cone_deg=EQ_TRIPOD_CONE_DEG):
    """Motor angles (M1, M3 over -180..180, M2 over -10..82 in step) and the boresight's topocentric altitude at
    each, to show where in motor space the tripod cone lies. Returns (m1, m2, m3, alt[m2, m3, m1])."""
    from control_eq import wedge_alignQ_B2T
    m1 = np.arange(-180, 180 + 1e-9, step)
    m2 = np.arange(-10, 82 + 1e-9, step)
    m3 = np.arange(-180, 180 + 1e-9, step)
    T2, T3, T1 = np.meshgrid(m2, m3, m1, indexing="ij")
    bore, _ = eq_fk_vectors(np.stack([T1, T2, T3], axis=-1), wedge_alignQ_B2T(lat_deg))
    return m1, m2, m3, np.degrees(np.arcsin(np.clip(bore[..., 2], -1, 1)))


# ── Tripod collision: the M3 disk (utility/analyse_span.ipynb) ──────────────────────────────────────────────────
# The camera and OTA sit square to the M3 axis, so spinning M3 sweeps the OTA - front and rear - round a disk at
# right angles to that axis. The disk's orientation is set by M1 and M2 alone (the M3 axis is camera-up, eq_fk_vectors);
# M3 only moves the OTA round it. The tripod is modelled, as seen from the M3 pivot, as a cone of half-angle
# tripod_deg round the nadir (the legs, allowing for the OTA's length). The disk reaches within asin(|up_z|) of the
# nadir: a steep M3 axis keeps it clear, a near-horizontal one sweeps it down into the tripod. On a wedge at M2 = 0
# the M3 axis is the polar axis (elevation |latitude|); M2 tilts it, and M1 decides which way: down towards the
# horizon (worst) or sideways, the disk then passing down the side of the tripod.

EQ_TRIPOD_DISK_DEG = 25.0       # the tripod's half-angle round the nadir seen from the M3 pivot (a guess: measure it)


def eq_disk_nadir_gap(up):
    """How close (deg) the M3 disk - the plane square to the M3 axis `up` (..., 3) - comes to the nadir."""
    return np.degrees(np.arcsin(np.clip(np.abs(np.asarray(up, dtype=float)[..., 2]), 0.0, 1.0)))


def eq_ota_nadir_gap(bore):
    """How close (deg) the OTA comes to the nadir, front or rear: 90 - |boresight altitude| (pointing near the zenith
    puts the rear end near the nadir)."""
    return 90.0 - np.degrees(np.arcsin(np.clip(np.abs(np.asarray(bore, dtype=float)[..., 2]), 0.0, 1.0)))


def eq_disk_map(lat_deg, step=2.0):
    """The M3 disk's nadir gap over M1 (-180..180) x M2 (-10..82): (m1, m2, gap[m2, m1]). M3 doesn't change it."""
    from control_eq import wedge_alignQ_B2T
    m1 = np.arange(-180, 180 + 1e-9, step)
    m2 = np.arange(-10, 82 + 1e-9, step)
    T2, T1 = np.meshgrid(m2, m1, indexing="ij")
    _, up = eq_fk_vectors(np.stack([T1, T2, np.zeros_like(T1)], axis=-1), wedge_alignQ_B2T(lat_deg))
    return m1, m2, eq_disk_nadir_gap(up)


def eq_disk_critical_m2(m1, m2, gap, tripod_deg=EQ_TRIPOD_DISK_DEG):
    """For each M1, the least M2 at which the disk reaches into the tripod (NaN: never, within M2's range)."""
    hit = gap < tripod_deg
    return np.array([m2[np.argmax(hit[:, j])] if hit[:, j].any() else np.nan for j in range(len(m1))])


def eq_ota_m3_map(lat_deg, m1, step=2.0):
    """At one M1: the OTA's nadir gap (front or rear) over M3 (-180..180) x M2 (-10..82): (m2, m3, gap[m2, m3]) -
    which M3 angles actually reach the tripod once the disk does."""
    from control_eq import wedge_alignQ_B2T
    m2 = np.arange(-10, 82 + 1e-9, step)
    m3 = np.arange(-180, 180 + 1e-9, step)
    T2, T3 = np.meshgrid(m2, m3, indexing="ij")
    bore, _ = eq_fk_vectors(np.stack([np.full_like(T2, float(m1)), T2, T3], axis=-1), wedge_alignQ_B2T(lat_deg))
    return m2, m3, eq_ota_nadir_gap(bore)


def eq_disk_scene(lat_deg, theta, tripod_deg=EQ_TRIPOD_DISK_DEG, n=73):
    """Geometry for a 3D view, M3 pivot at the origin, topocentric (x East, y North, z Up), unit OTA half-length:
    'pole' (polar axis), 'up' (M3 axis), 'disk' (n, 3) circle swept by the OTA ends, 'front'/'rear' OTA ends at this
    M3, 'tripod' (legs: 3 lines down the cone round the nadir), 'cone' (the cone's rim at unit distance), 'gap'."""
    from control_eq import wedge_alignQ_B2T
    bore, up = eq_fk_vectors(np.asarray(theta, dtype=float), wedge_alignQ_B2T(lat_deg))
    a = np.cross(up, [0.0, 0.0, 1.0])
    a = a / np.linalg.norm(a) if np.linalg.norm(a) > 1e-9 else np.array([1.0, 0.0, 0.0])
    b = np.cross(up, a)
    t = np.linspace(0, 2 * np.pi, n)
    disk = np.outer(np.cos(t), a) + np.outer(np.sin(t), b)
    r, h = math.sin(math.radians(tripod_deg)), math.cos(math.radians(tripod_deg))
    legs = [np.array([[0, 0, 0], [r * math.cos(k) * 1.4, r * math.sin(k) * 1.4, -h * 1.4]]) for k in np.radians([90, 210, 330])]
    cone = np.stack([r * np.cos(t), r * np.sin(t), -h * np.ones_like(t)], axis=-1)
    return {"pole": eq_m1_axis(lat_deg), "up": up, "disk": disk, "front": bore, "rear": -bore, "tripod": legs,
            "cone": cone, "gap": float(eq_disk_nadir_gap(up)), "ota_gap": float(eq_ota_nadir_gap(bore))}


def eq_segment_distance(p0, p1, q0, q1):
    """Least distance between the segments p0-p1 and q0-q1 (3-vectors)."""
    u, v, w = p1 - p0, q1 - q0, p0 - q0
    a, b, c, d, e = u @ u, u @ v, v @ v, u @ w, v @ w
    den = a * c - b * b
    s = np.clip((b * e - c * d) / den, 0.0, 1.0) if den > 1e-12 else 0.0
    t = np.clip((b * s + e) / c, 0.0, 1.0) if c > 1e-12 else 0.0
    s = np.clip((b * t - d) / a, 0.0, 1.0) if a > 1e-12 else 0.0       # re-solve s for the clamped t
    return float(np.linalg.norm((p0 + s * u) - (q0 + t * v)))


def eq_tripod_clearance(pts, leg_spread_deg, depth):
    """Signed distance (units of the OTA's front length) from points (n, 3) to the tripod, modelled as a solid cone:
    apex at the wedge (origin), axis to the nadir, half-angle the legs' splay, down to `depth` below the apex. The legs
    stand on its surface and the space between them (spreader, tray, head) counts as tripod. Negative: inside."""
    p = np.atleast_2d(np.asarray(pts, dtype=float))
    r = np.linalg.norm(p, axis=1)
    down = -p[:, 2]                                          # depth below the apex, along the axis
    radial = np.hypot(p[:, 0], p[:, 1])
    half = math.radians(leg_spread_deg)
    # distance to the slanted surface, signed (+ outside): the point's offset across the cone's side
    side = radial * math.cos(half) - down * math.sin(half)
    out = np.where(down <= 0.0, r, side)                     # above the apex: its distance to the apex
    below = down - depth                                     # past the legs' feet: outside by that much
    return np.where(below > 0.0, np.maximum(out, below), out)


def eq_rig_scene(lat_deg, theta, front=1.0, rear=0.5, leg_spread_deg=20.0, leg_len=1.5, ota_r=0.05, leg_r=0.02,
                 joint=0.1, n=145):
    """The rig on an ideal wedge for a 3D view and a collision check, topocentric (x East, y North, z Up), units of
    the OTA's front length: the tripod's legs splay leg_spread_deg from the vertical below the wedge (origin, one leg
    towards the pole); M1 sits joint above the wedge along the polar axis, M2 joint above M1, M3 joint above M2 along
    the M3 axis; the OTA runs front ahead of M3 along the boresight and rear behind it. The tripod is the solid cone
    the legs span (eq_tripod_clearance). Returns the joints, axes, the OTA ends, the legs, the disks the front and
    rear sweep as M3 turns, and 'clearance' (the OTA's least distance to the tripod less its radius and the legs': < 0
    is a hit), 'disk_clearance' (the same over every M3 angle: < 0 means some M3 angle hits)."""
    from control_eq import wedge_alignQ_B2T
    theta = np.asarray(theta, dtype=float)
    bore, up = eq_fk_vectors(theta, wedge_alignQ_B2T(lat_deg))
    t1, t2 = np.radians(theta[0]), np.radians(theta[1])
    b0 = np.array([np.cos(t2) * np.sin(t1), np.cos(t2) * np.cos(t1), np.sin(t2)])
    u0 = np.array([-np.sin(t2) * np.sin(t1), -np.sin(t2) * np.cos(t1), np.cos(t2)])
    m2_axis = _eq_rot(wedge_alignQ_B2T(lat_deg)) @ np.cross(b0, u0)       # M2's axis (base frame -> topocentric)
    pole = eq_m1_axis(lat_deg)
    p1 = joint * pole
    p2 = p1 + joint * pole
    p3 = p2 + joint * up
    tip, tail = p3 + front * bore, p3 - rear * bore
    paz = math.atan2(pole[0], pole[1])
    sp = math.radians(leg_spread_deg)
    legs = [np.array([[0.0, 0.0, 0.0], leg_len * np.array([math.sin(sp) * math.sin(paz + k), math.sin(sp) * math.cos(paz + k),
                                                            -math.cos(sp)])]) for k in np.radians([0.0, 120.0, 240.0])]
    # the boresight's directions as M3 turns, from a direction fixed by M1/M2 alone: sampled from the current
    # boresight, the samples moved with M3 and the disk's colour flickered as M3 turned (the disk itself doesn't move)
    ref = np.cross(up, [0.0, 0.0, 1.0])
    ref = ref / np.linalg.norm(ref) if np.linalg.norm(ref) > 1e-9 else np.cross(up, [1.0, 0.0, 0.0]) / np.linalg.norm(np.cross(up, [1.0, 0.0, 0.0]))
    tt = np.linspace(0, 2 * np.pi, n)
    ring = np.outer(np.cos(tt), ref) + np.outer(np.sin(tt), np.cross(up, ref))
    disk_front, disk_rear = p3 + front * ring, p3 - rear * ring
    s_ = np.linspace(-rear, front, 61)
    depth = leg_len * math.cos(sp)
    margin = ota_r + leg_r
    gap = float(eq_tripod_clearance(p3 + np.outer(s_, bore), leg_spread_deg, depth).min()) - margin
    sweep = p3 + s_[None, :, None] * ring[:, None, :]                    # every OTA point at every M3 angle
    disk_gap = float(eq_tripod_clearance(sweep.reshape(-1, 3), leg_spread_deg, depth).min()) - margin
    return {"pole": pole, "up": up, "m2_axis": m2_axis, "bore": bore, "joints": np.array([p1, p2, p3]), "front": tip,
            "rear": tail, "legs": legs, "disk_front": disk_front, "disk_rear": disk_rear,
            "clearance": gap, "disk_clearance": disk_gap}


def eq_tripod_sky_map(lat_deg, front=1.0, rear=0.5, leg_spread_deg=20.0, leg_len=1.5, ota_r=0.05, leg_r=0.02,
                      joint=0.1, step=(4.0, 2.0, 4.0), az_step=15.0, alt_step=7.5, roll_step=10.0):
    """What the tripod takes from the sky, by pointing: every motor pose on a grid (M1, M2, M3 steps `step`; M2 over
    its reference range) is put through the rig (eq_rig_scene's geometry, the tripod as its legs' solid cone) and
    binned by the OTA's Az / Alt / roll (roll: camera-up from the vertical plane through the boresight). Returns
    (az_edges, alt_edges, reach, taken): reach[alt, az] the share of rolls the motors reach there, taken[alt, az] the
    share of those the tripod blocks (NaN where nothing is reachable)."""
    from control_eq import wedge_alignQ_B2T
    t1 = np.arange(0.0, 360.0, step[0])
    t2 = np.arange(-8.0, EQ_THETA2_MAX + 1e-9, step[1])
    t3 = np.arange(0.0, 360.0, step[2])
    th = np.stack(np.meshgrid(t1, t2, t3, indexing="ij"), axis=-1).reshape(-1, 3)
    bore, up = eq_fk_vectors(th, wedge_alignQ_B2T(lat_deg))
    p3 = 2 * joint * eq_m1_axis(lat_deg) + joint * up
    depth = leg_len * math.cos(math.radians(leg_spread_deg))
    gap = np.full(len(th), np.inf)
    for s_ in np.linspace(-rear, front, 13):
        gap = np.minimum(gap, eq_tripod_clearance(p3 + s_ * bore, leg_spread_deg, depth))
    hit = gap - ota_r - leg_r < 0
    az, alt = eq_vec_azalt(bore)
    z = np.array([0.0, 0.0, 1.0])
    u0 = z - (bore @ z)[:, None] * bore
    u0 /= np.maximum(np.linalg.norm(u0, axis=1, keepdims=True), 1e-9)
    roll = np.degrees(np.arctan2(np.einsum("ij,ij->i", np.cross(u0, up), bore), np.einsum("ij,ij->i", u0, up))) % 360
    az_edges = np.arange(0.0, 360.0 + 1e-9, az_step)
    alt_edges = np.arange(-90.0, 90.0 + 1e-9, alt_step)
    nr = int(round(360.0 / roll_step))
    ia = np.clip(np.digitize(alt, alt_edges) - 1, 0, len(alt_edges) - 2)
    iz = np.clip(np.digitize(az, az_edges) - 1, 0, len(az_edges) - 2)
    ir = np.clip((roll // roll_step).astype(int), 0, nr - 1)
    reach = np.zeros((len(alt_edges) - 1, len(az_edges) - 1, nr), bool)
    clear = np.zeros_like(reach)
    np.logical_or.at(reach, (ia, iz, ir), True)
    np.logical_or.at(clear, (ia, iz, ir), ~hit)
    n_reach = reach.sum(-1)
    taken = np.where(n_reach > 0, 1.0 - clear.sum(-1) / np.maximum(n_reach, 1), np.nan)
    return az_edges, alt_edges, n_reach / nr, taken


def eq_latitude_summary(lats, rig_tilt_limits=(EQ_RIG_TILT_OFF, 100.0, EQ_THETA2_MAX), n_pairs=400,
                        tripod_cone_deg=EQ_TRIPOD_CONE_DEG, seed=0):
    """Per latitude: the mean share of PA reachable over the sky above the horizon (motor reach alone, and with
    each rig tilt limit; '_either' also allowing an upside-down frame), the share of that sky not reachable at any PA, and the share of straight motor-angle
    gotos (between poses above 10 deg) that enter the tripod cone."""
    rows = []
    for lat in lats:
        g = {lim: eq_sky_grid(lat, 4, 4, 10, rig_tilt_limit=lim, tripod_cone_deg=tripod_cone_deg) for lim in rig_tilt_limits}
        first = g[rig_tilt_limits[0]]
        above = first["alt"][:, None] > 0
        w = np.cos(np.radians(first["alt"]))[:, None] * np.ones_like(first["motor"])     # area weights
        w = np.where(above, w, 0)
        row = {"lat": lat, "pa_share_motor": float((first["motor"] * w).sum() / w.sum()),
               "sky_unreachable": float(((first["motor"] == 0) * w).sum() / w.sum())}
        for lim in rig_tilt_limits:
            row[f"pa_share_tilt_{lim:g}"] = float((g[lim]["motor_rig"] * w).sum() / w.sum())
            row[f"pa_share_tilt_{lim:g}_either"] = float((g[lim]["motor_rig_either"] * w).sum() / w.sum())
        df, _ = eq_straight_gotos(lat, n_pairs, 41, tripod_cone_deg=tripod_cone_deg, seed=seed)
        row["gotos_enter_cone"] = float(df["enters_cone"].mean())
        row["gotos_min_nadir_p01"] = float(df["min_nadir_deg"].quantile(0.01))
        rows.append(row)
    return pd.DataFrame(rows)
