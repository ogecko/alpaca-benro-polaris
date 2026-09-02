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
    Alt/Az/theta delta via the parallactic angle -- see docs/pec_theta_space_plan.md Phase 0.1.
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


def load_sync_guiding_residuals(log_filenames, log_dir='.'):
    """
    Parse every '->> Polaris: SYNC GUIDING Ra <dms>, Dec <dms> Residuals' line into a
    DataFrame with timestamp/resid_1 (RA, arcmin)/resid_2 (Dec, arcmin) -- same convention as
    PECLOG's own resid_1/resid_2. Unlike load_pec(), this works with Config.advanced_pec off
    (a session with PEC disabled, sync-guiding enabled -- e.g. for a clean, uncontaminated
    ground-truth capture per docs/pec_theta_space_plan.md): process_guide_sync() logs this
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
    docs/pec_theta_space_plan.md Phase 0.1). For each row:
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
    at all it silently returns (None, None, None) for *every* row (its own default argument
    is passed through as a literal None to kinematics.q_to_theta(), which then fails on
    None.unwrap() and gets swallowed by azaltroll_to_theta()'s try/except; found by testing
    this function empirically, not from reading the signature). A single LastPosition is
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
         no-hidden-term reasoning for total_accum in docs/pec_theta_space_plan.md -- the same
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
    delta_guide_accum, see docs/pec_theta_space_plan.md) is already that cumulative sum,
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
    docs/pec_theta_space_plan.md Phase 0.2, so it needs to handle irregular spacing in either
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
    docs/pec_theta_space_plan.md): with the small sample sizes PECLOG-cadence segments give
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


def load_vitals(log_filenames, log_dir='.'):
    """
    Parse the driver's shr.system_vitals()-carrying WARNING lines into a DataFrame -- three
    distinct triggers, all sharing the same CPU/Mem/Swap/thread-count/network-counter
    snapshot format:
      - 'Polaris position update' -- polaris.py's 500ms watchdog (_every_500ms_watchdog_check),
        fires whenever 518 telemetry itself is running late (>0.5s).
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
                    timestamp=d["ts"], kind=d["kind"],
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
    investigating a real overnight dropout (docs/pec_theta_space_plan.md): the disconnect at
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
    the hard way while diagnosing a real overnight dropout (docs/pec_theta_space_plan.md): the
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
    outage (docs/pec_theta_space_plan.md) turned out to span two separate driver-restart
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
                      if k.startswith('param_') and pd.notna(ev[k])}
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
