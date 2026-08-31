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
