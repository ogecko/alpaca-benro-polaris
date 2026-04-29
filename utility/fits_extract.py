#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
"""
fits_extract.py - Calibration utility for the Alpaca Benro Polaris Driver.

Pipeline
--------
  -extract    FITS files -> CSV  (run once per session, then archive FITS)
  -model      CSV(s) -> fit mechanical corrections + QUEST -> {prefix}model.json
  -validate   CSV(s) + {prefix}model.json -> {prefix}validate.csv + summary

Recommended workflow
--------------------
  1. Disable ALL mechanical corrections in the driver config: QUEST off, MAC off, LGA off, PEC off
  2. Capture a full calibration grid in NINA using a 12 x 4 PanoGrid, 30 hstep, 10 vstep, starting panel 1 at az 30, alt 25, roll 0
  3. Repeat capture for roll -45 and roll +45
  4. Plate-solve with ASTAP (writes WCS back into FITS headers).
  5. Run -extract to produce a permanent CSV of raw observations.
  6. Run -model to fit all parameters. Inspect the Results Summary.
  7. Run -validate -sync 6 to confirm out-of-sample improvement.
  8. Copy the fitted parameters to config.toml.

The same CSV works forever. Corrections are applied inside -model as fit
variables, so you can try different models without recapturing data.

CSV field naming
----------------
  p_*      Polaris raw prediction (derived from qC2B_raw, includes SPA)
  s_*      Solved truth  (plate-solve result)
  q_*      Quest-only prediction (QUEST applied, mechanical corrections NOT applied)
  m_*      Model prediction  (corrections + QUEST applied)
  dev_p_*  Raw deviation    = solved - polaris  (arcmin)
  dev_q_*  Quest deviations = solved - quest    (arcmin)
  dev_m_*  Model deviations = solved - model    (arcmin)

Note on SPA
-----------
  The Polaris firmware performs a Single Point Alignment (SPA) before use.
  This bakes the firmware's full initial alignment (not just a rotator offset)
  into qC2B_raw, which is the source of all p_* values.
  QUEST corrects any residual frame tilt per session on top of SPA.

All output uses ASCII only so stdout can be redirected to a text file.

Dependencies
------------
  pip install astropy ephem pyquaternion numpy scipy
"""

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from astropy.io import fits as astropy_fits
except ImportError:
    print("ERROR: astropy not installed.  Run: pip install astropy")
    sys.exit(1)

try:
    import numpy as np
    from quaternion import Q as Quaternion
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("WARNING: numpy/pyquaternion not available.")

try:
    from scipy.optimize import curve_fit
    from scipy import stats as sp_stats
    from numpy.linalg import lstsq
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("WARNING: scipy not available - model fitting won't work.")

try:
    import kinematics as _km
    from kinematics import (
        wrap360, wrap180, wrap90,
        calc_parallactic_angle,
        radec_to_altaz,
        azaltroll_to_q   as _azaltroll_to_q,
        q_to_theta       as _q_to_theta_km,
        azaltroll_to_theta,
        crota2_from_cd,
        crota2_to_roll,
    )
    HAS_KM = True
except ImportError as e:
    print(e)
    HAS_KM = False
    print("WARNING: kinematics.py not found.")
    def wrap180(a):    return (a + 180.0) % 360.0 - 180.0
    def wrap360(a):
        w = a % 360.0; return 0.0 if abs(w - 360) < 1e-10 else w
    def wrap90(a):     return (a + 90.0) % 180.0 - 90.0
    def calc_parallactic_angle(az, alt, lat): return 0.0
    def radec_to_altaz(*a, **kw): return None, None
    def azaltroll_to_theta(*a): return None, None, None
    def _azaltroll_to_q(*a): return None
    def _q_to_theta_km(*a): return None, None, None

try:
    import ephem
    HAS_EPHEM = True
except ImportError:
    HAS_EPHEM = False
    print("WARNING: ephem not available - solved az/alt won't be computed.")


# ---- Logging (tee to file when -log is given) ---------------------------

import builtins as _builtins

_log_file = None

def _print(*args, **kwargs):
    """Replacement for print() that also writes to the log file."""
    _builtins.print(*args, **kwargs)
    if _log_file is not None:
        end = kwargs.get('end', '\n')
        sep = kwargs.get('sep', ' ')
        line = sep.join(str(a) for a in args) + end
        _log_file.write(line)
        _log_file.flush()

print = _print


# ---- Constants -----------------------------------------------------------

DEFAULT_LAT    = -33.86
DEFAULT_LON    = 151.12


# ---- CSV schemas ---------------------------------------------------------

_EXTRACT_FIELDS = [
    'session_id', 'filename', 'status', 'date_obs',
    'ra', 'dec', 'site_lat', 'site_lon',
    'p_az', 'p_alt', 'p_roll', 'p_theta1', 'p_theta2', 'p_theta3',
    's_az', 's_alt', 's_roll', 's_theta1', 's_theta2', 's_theta3',
    'dev_p_az', 'dev_p_alt', 'dev_p_roll',
    'pixel_scale_arcsec',
]

_PREDICT_FIELDS = _EXTRACT_FIELDS + [
    'sync_point',
    'alignQ_w', 'alignQ_x', 'alignQ_y', 'alignQ_z',
    # Quest-only prediction (QUEST applied, no mechanical corrections)
    'q_az', 'q_alt', 'q_roll', 'q_theta1', 'q_theta2', 'q_theta3',
    'dev_q_az', 'dev_q_alt', 'dev_q_roll',
    # Full model prediction (QUEST + mechanical corrections)
    'm_az', 'm_alt', 'm_roll', 'm_theta1', 'm_theta2', 'm_theta3',
    'dev_m_az', 'dev_m_alt', 'dev_m_roll',
]


# ---- FITS header helpers -------------------------------------------------

def _sf(h, key, default=None):
    try:
        v = h.get(key, default)
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default

def _ss(h, key, default=''):
    v = h.get(key, default)
    return str(v).strip() if v is not None else default

def _read_header(path):
    with astropy_fits.open(path, memmap=False, ignore_missing_simple=True) as hdul:
        return dict(hdul[0].header)


# ---- Per-FITS processing -------------------------------------------------

def _process_fits(path, session_id, lat, lon):
    row = {k: '' for k in _EXTRACT_FIELDS}
    row['session_id'] = session_id
    row['filename']   = path.name
    f8 = lambda v: round(v, 8) if v is not None else ''
    f4 = lambda v: round(v, 4) if v is not None else ''
    f2 = lambda v: round(v, 2) if v is not None else ''

    try:
        h = _read_header(path)
    except Exception as e:
        row['status'] = f'error: {e}'
        return row
    
    ra  = _sf(h, 'RA')
    dec = _sf(h, 'DEC')
    lat = _sf(h, 'SITELAT',  lat)
    lon = _sf(h, 'SITELONG', lon)
    row['ra'] = f2(ra)
    row['dec'] = f2(dec)
    row['site_lat'] = f4(lat)
    row['site_lon'] = f4(lon)
    row['date_obs'] = _ss(h, 'DATE-OBS')

    p_az   = _sf(h, 'CENTAZ')
    p_alt  = _sf(h, 'CENTALT')
    p_roll = _sf(h, 'ROTATOR')

    row['p_az']   = f4(p_az)
    row['p_alt']  = f4(p_alt)
    row['p_roll'] = f4(p_roll)

    if None not in (p_az, p_alt, p_roll) and HAS_NUMPY:
        t1, t2, t3 = azaltroll_to_theta(p_az, p_alt, p_roll)
        row['p_theta1'] = f4(t1)
        row['p_theta2'] = f4(t2)
        row['p_theta3'] = f4(t3)

    solved_flag = h.get('PLTSOLVD', False)
    is_solved   = solved_flag is True or str(solved_flag).strip().upper() == 'T'
    if not is_solved:
        row['status'] = 'unsolved'
        return row

    s_ra  = _sf(h, 'CRVAL1')
    s_dec = _sf(h, 'CRVAL2')
    if s_ra is None or s_dec is None:
        row['status'] = 'solved-no-wcs'
        return row

    crota2 = _sf(h, 'CROTA2')
    if crota2 is None:
        crota2 = crota2_from_cd(_sf(h, 'CD1_2', 0.0), _sf(h, 'CD2_2', 0.0))
    if crota2 is None:
        row['status'] = 'solved-no-rotation'
        return row

    s_az, s_alt = radec_to_altaz(s_ra, s_dec, lat, lon, row['date_obs'])
    if s_az is None:
        row['status'] = 'solved-no-altaz'
        return row

    s_roll, _ = crota2_to_roll(crota2, s_az, s_alt, lat)

    row['s_az']   = f4(s_az)
    row['s_alt']  = f4(s_alt)
    row['s_roll'] = f4(s_roll)

    if HAS_NUMPY:
        st1, st2, st3 = azaltroll_to_theta(s_az, s_alt, s_roll)
        row['s_theta1'] = f4(st1)
        row['s_theta2'] = f4(st2)
        row['s_theta3'] = f4(st3)

    if p_az is not None:
        row['dev_p_az']  = f2(wrap180(s_az  - p_az)  * 60)
        row['dev_p_alt'] = f2((s_alt - p_alt)         * 60)
    if p_roll is not None:
        row['dev_p_roll'] = f2(wrap180(s_roll - p_roll) * 60)

    cdelt2 = _sf(h, 'CDELT2', 0.0)
    if cdelt2:
        row['pixel_scale_arcsec'] = f4(abs(cdelt2) * 3600)

    row['status'] = 'solved'
    return row


# ---- -extract -----------------------------------------------------------

def cmd_extract(fits_dir, output_csv, lat, lon):
    fits_dir   = Path(fits_dir)
    output_csv = Path(output_csv)
    fits_files = sorted(
        list(fits_dir.rglob('*.fits')) + list(fits_dir.rglob('*.fit')),
        key=lambda f: f.stat().st_mtime)

    if not fits_files:
        print(f"No FITS files found in {fits_dir}")
        return

    print("==== FITS EXTRACTOR ====")
    print(f"Found {len(fits_files)} FITS files in {fits_dir}")
    print(f"ephem={HAS_EPHEM}  numpy={HAS_NUMPY}")
    print()

    rows = []
    status_counts = Counter()
    n_total = len(fits_files)
    for idx, fp in enumerate(fits_files, 1):
        row = _process_fits(fp, '', lat, lon)
        rows.append(row)
        status_counts[row['status']] += 1
        prog = f"  ({idx} of {n_total})  {fp.name:<48s}"
        prog += f" | Az " + f"{float(row['p_az']):+7.2f}" if row['p_az']  != ''    else '    N/A'
        prog += f" | Alt " + f"{float(row['p_alt']):+7.2f}" if row['p_alt'] != ''   else '    N/A'
        prog += f" | Roll " + f"{float(row['p_roll']):+7.2f}" if row['p_roll'] != '' else '    N/A'
        prog += f" | {row['status']:<8s}"
        sys.stderr.write('\r' + prog)
        sys.stderr.flush()

    sys.stderr.write('\r' + ' ' * 120 + '\r')
    sys.stderr.flush()

    n_solved   = status_counts.get('solved', 0)
    ts         = datetime.now().strftime('%Y-%m-%d %H:%M')
    session_id = f"{ts} N={n_solved}"
    for row in rows:
        row['session_id'] = session_id
    print(f"Session ID: {session_id}")
    print()

    try:
        with open(output_csv, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=_EXTRACT_FIELDS, extrasaction='ignore')
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {len(rows)} rows -> {output_csv}")
    except PermissionError as e:
        print(f"ERROR: {e}")
        return

    print()
    print("---- Status summary ----")
    for st, n in sorted(status_counts.items()):
        print(f"  {st:<24s}: {n}")

    solved = [r for r in rows if r['status'] == 'solved']
    if solved and HAS_NUMPY:
        def _st1(field):
            vals = [float(r[field]) for r in solved if r[field] != '']
            return f"min={min(vals):+7.1f} deg | max={max(vals):+6.1f} deg | span={max(vals)-min(vals):6.1f}" if vals else "N/A"
        def _st2(field):
            vals = [float(r[field]) for r in solved if r[field] != '']
            if not vals: return "N/A"
            a = np.array(vals)
            return f"min={np.min(a):+7.1f}'    | max={np.max(a):+7.1f}'   | mean={np.mean(a):+7.1f}' | median={np.median(a):+7.1f}' | std={np.std(a):5.1f}'"
        print()
        print("---- Data coverage ----")
        print(f"  p_az            : {_st1('p_az')}")
        print(f"  p_alt           : {_st1('p_alt')}")
        print(f"  p_roll          : {_st1('p_roll')}")
        print()
        print(f"  p_theta1 (az)   : {_st1('p_theta1')}")
        print(f"  p_theta2 (alt)  : {_st1('p_theta2')}")
        print(f"  p_theta3 (roll) : {_st1('p_theta3')}")
        print()
        print("---- Raw deviations from plate-solved solution (arcmin) ----")
        print(f"  dev_p_az        : {_st2('dev_p_az')}")
        print(f"  dev_p_alt       : {_st2('dev_p_alt')}")
        print(f"  dev_p_roll      : {_st2('dev_p_roll')}")
    print()


# ---- Load CSV helpers ----------------------------------------------------


def _normalise_row(row):
    if row.get('s_az', '') != '' and HAS_NUMPY:
        try:
            t1, t2, t3 = azaltroll_to_theta(
                float(row['s_az']), float(row['s_alt']), float(row['s_roll']))
            row['s_theta1'] = round(t1, 4) if t1 is not None else ''
            row['s_theta2'] = round(t2, 4) if t2 is not None else ''
            row['s_theta3'] = round(t3, 4) if t3 is not None else ''
        except Exception:
            pass
    return row


def _load_csvs(csv_paths):
    """Load one or more extract CSVs (old or new schema). Returns solved rows only."""
    rows = []
    for path in csv_paths:
        path = Path(path)
        with open(path, newline='') as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            has_sid = 'session_id' in fields
            for row in reader:
                if row.get('status', '') != 'solved':
                    continue
                if not has_sid or not row.get('session_id', '').strip():
                    row['session_id'] = path.stem
                _normalise_row(row)
                rows.append(row)
    return rows


# ---- QUEST helpers -------------------------------------------------------

def _load_mount_params(params_path):
    """Load MountModelParams from fits_params.json. Returns defaults if absent."""
    p = Path(params_path)
    if p.exists():
        with open(p) as f:
            saved = json.load(f)
        tm = saved.get('mount_model', saved.get('theta_model', {}))
        # MODIFICATION 1: added m2_roll_coupling and m2_roll_zero
        return _km.MountModelParams(
            m3_tilt_dm2      = tm.get('m3_tilt_dm2',      0.0),
            m3_tilt_dm1       = tm.get('m3_tilt_dm1',       0.0),
            m3_tilt_dm3     = tm.get('m3_tilt_dm3',     0.0),
            m2_tilt_dm2_amp  = tm.get('m2_tilt_dm2_amp',  0.0),
            m2_tilt_dm2_zero = tm.get('m2_tilt_dm2_zero', 0.0),
            m2_roll_coupling = tm.get('m2_roll_coupling', 0.0),
            m2_roll_zero     = tm.get('m2_roll_zero',     45.0),
            m1_offset        = tm.get('m1_offset',        0.0),
            m2_offset        = tm.get('m2_offset',        0.0),
            m3_offset        = tm.get('m3_offset',        0.0),
        ), saved
    return _km.MountModelParams(), {}


def _build_quest_pairs(rows, mount_params):
    """Build (q_base_corrected, q_solved) pairs for QUEST."""
    pairs = []
    for r in rows:
        try:
            t1     = float(r['p_theta1']); t2 = float(r['p_theta2']); t3 = float(r['p_theta3'])
            s_az   = float(r['s_az']);    s_alt = float(r['s_alt'])
            p_az   = float(r['p_az']);    p_alt = float(r['p_alt'])
        except (ValueError, TypeError):
            continue
        q_base = _km.theta_to_q(t1, t2, t3)
        if mount_params is not None:
            q_base, _ = _km.apply_mechanical_corrections(q_base, mount_params)
        p_az_corr, p_alt_corr, _ = _km.q_to_azaltroll(q_base)
        q_pred   = _km.q_from_azaltroll(p_az_corr, p_alt_corr, 0.0)
        q_solved = _km.q_from_azaltroll(s_az, s_alt, 0.0)
        pairs.append((q_pred, q_solved))
    return pairs

def _fit_roll_adj_from_rows(rows):
    roll_deltas = []
    for r in rows:
        try:
            s_roll = float(r['s_roll'])
            p_roll = float(r['p_roll'])
            roll_deltas.append(wrap180(s_roll - p_roll))
        except: pass

    if not roll_deltas:
        return None
    else:
        return np.mean(roll_deltas)


def _fit_alignQ_from_rows(rows, mount_params):
    pairs = _build_quest_pairs(rows, mount_params)
    if len(pairs) < 3:
        return None
    return _km.quest_solve(pairs)


def _predict_row(row, alignQ, roll_adj, mount_params):
    """Return model prediction dict for one row, or None on error.

    Returns predictions at three levels:
      q_*     QUEST only  — alignQ applied, no mechanical corrections
      m_*     Full model  — mechanical corrections applied before QUEST
    """
    try:
        p_az  = float(row['p_az']);     p_alt = float(row['p_alt']);    p_roll = float(row['p_roll'])
        p_t1  = float(row['p_theta1']); p_t2 = float(row['p_theta2']);  p_t3 = float(row['p_theta3'])
        s_az  = float(row['s_az']);     s_alt = float(row['s_alt']);    s_roll = float(row['s_roll'])
        s_t1  = float(row['s_theta1']); s_t2  = float(row['s_theta2']); s_t3 = float(row['s_theta3'])
    except (ValueError, TypeError):
        return None
    if not p_roll:
        return None

    # ---- Quest-only prediction (no mechanical corrections) ---------------
    q_base_raw = _km.theta_to_q(p_t1, p_t2, p_t3)
    qa_q = (alignQ * q_base_raw).normalised
    q_az, q_alt, q_roll_raw = _km.q_to_azaltroll(qa_q)
    q_roll = wrap180(q_roll_raw + roll_adj)
    q_t1, q_t2, q_t3 = _km.q_to_theta(qa_q)
    # Apply roll_adj scalar corrections to quest-only thetas too
    q_t1_adj = wrap360(q_t1 + roll_adj / math.sin(math.radians(q_t2)))
    q_t3_adj = wrap180(q_t3 - roll_adj / math.tan(math.radians(q_t2)))

    # ---- Full model prediction (mechanical corrections + QUEST) ----------
    q_base = _km.theta_to_q(p_t1, p_t2, p_t3)
    if mount_params is not None:
        q_base, _ = _km.apply_mechanical_corrections(q_base, mount_params)
    pa_q = (alignQ * q_base).normalised

    m_az, m_alt, m_roll_raw = _km.q_to_azaltroll(pa_q)
    m_roll = wrap180(m_roll_raw + roll_adj)
    m_t1, m_t2, m_t3 = _km.q_to_theta(pa_q)
    m_t1   = wrap360(m_t1 + roll_adj / math.sin(math.radians(m_t2)))
    m_t2   = wrap180(m_t2 - roll_adj * math.sin(math.radians(m_t3)))
    m_t3   = wrap180(m_t3 - roll_adj / math.tan(math.radians(m_t2)))

    return {
        # Quest-only
        'q_az':          q_az,
        'q_alt':         q_alt,
        'q_roll':        q_roll,
        'q_theta1':      q_t1_adj,
        'q_theta2':      q_t2,
        'q_theta3':      q_t3_adj,
        'dev_q_az':      wrap180(s_az   - q_az)   * 60,
        'dev_q_alt':     wrap180(s_alt  - q_alt)  * 60,
        'dev_q_roll':    wrap180(s_roll - q_roll) * 60,
        # Full model
        'm_az':          m_az,
        'm_alt':         m_alt,
        'm_roll':        m_roll,
        'm_theta1':      m_t1,
        'm_theta2':      m_t2,
        'm_theta3':      m_t3,
        # Raw deviations (recomputed here for completeness)
        'dev_p_az':      wrap180(s_az  - p_az)    * 60,
        'dev_p_alt':     wrap180(s_alt - p_alt)   * 60,
        'dev_p_roll':    wrap180(s_roll - p_roll) * 60,
        'dev_m_az':      wrap180(s_az  - m_az)    * 60,
        'dev_m_alt':     wrap180(s_alt - m_alt)   * 60,
        'dev_m_roll':    wrap180(s_roll - m_roll) * 60,
        'dev_p_theta1':  wrap180(s_t1 - p_t1) * 60,
        'dev_p_theta2':  wrap180(s_t2 - p_t2) * 60,
        'dev_p_theta3':  wrap180(s_t3 - p_t3) * 60,
        'dev_m_theta1':  wrap180(s_t1 - m_t1) * 60,
        'dev_m_theta2':  wrap180(s_t2 - m_t2) * 60,
        'dev_m_theta3':  wrap180(s_t3 - m_t3) * 60,
        'dev_q_theta1':  wrap180(s_t1 - q_t1_adj) * 60,
        'dev_q_theta2':  wrap180(s_t2 - q_t2) * 60,
        'dev_q_theta3':  wrap180(s_t3 - q_t3_adj) * 60,
        # NOTE: use q_t2/q_t3 (not m_t2/m_t3) so that roll_adj*sin(theta3)
        # contamination is absent from the M3/M2 tilt fitting targets in cmd_model.
        # m_t2 has roll_adj*sin(m_t3) subtracted which introduces a spurious slope
        # vs theta3 that swamps the real M3 tilt signal (~1 arcmin/deg per deg of
        # roll_adj). q_t2/q_t3 are the raw QUEST-aligned angles with no roll_adj term.
        '_dev_m_theta2': wrap180(s_t2 - q_t2) * 60,
        '_dev_m_theta3': wrap180(s_t3 - q_t3_adj) * 60,
    }


# ---- Stat helpers --------------------------------------------------------

def _rms(v):
    v2 = [x for x in v if not math.isnan(x)]
    return math.sqrt(sum(x**2 for x in v2) / len(v2)) if v2 else float('nan')

def _arr_stats(arr):
    v = arr[~np.isnan(arr)]
    if not len(v): return 'N/A'
    return (f"mean={np.mean(v):+7.2f}'  std={np.std(v):6.2f}'"
            f"  rms={math.sqrt(float(np.mean(v**2))):6.2f}'"
            f"  min={np.min(v):+7.1f}'  max={np.max(v):+7.1f}'")

def _sig(pF):
    if pF < 1e-10: return "p<1e-10 ***"
    if pF < 1e-4:  return f"p={pF:.1e} **"
    if pF < 0.05:  return f"p={pF:.4f} *"
    return f"p={pF:.4f} (not significant)"

def _conf(val, err, tc, unit=''):
    return f"{val:+.4f}{unit}  +/-{err:.4f}{unit}  95%CI +/-{tc*err:.4f}{unit}"

def _fit_sincos(az_rad, y):
    mask = ~np.isnan(y)
    ar, yr = az_rad[mask], y[mask]
    n = len(yr)
    if n < 6: return None
    X = np.column_stack([np.cos(ar), np.sin(ar), np.ones(n)])
    c, _, _, _ = lstsq(X, yr, rcond=None)
    pred = X @ c; resid = yr - pred
    ss_r = float(np.sum(resid**2)); ss_t = float(np.sum((yr - yr.mean())**2))
    r2   = 1 - ss_r/ss_t if ss_t > 0 else 0
    rmse = float(np.sqrt(ss_r/n))
    A, B, C = c
    amp   = float(np.sqrt(A**2 + B**2))
    phase = float(np.degrees(np.arctan2(B, A)))
    F_    = (ss_t-ss_r)/3 / (ss_r/max(n-3,1)) if ss_r > 0 else 0
    pF    = float(1 - sp_stats.f.cdf(max(F_,0), 3, max(n-3,1)))
    return dict(A=A, B=B, C=C, amp=amp, phase=phase, r2=r2, rmse=rmse, F=F_, pF=pF)

def _fit_linear_through_origin(x, y):
    """Fit y = k*x, return (k, se_k, r2)."""
    mask = ~np.isnan(y)
    x_, y_ = x[mask], y[mask]
    n = len(x_)
    if n < 5: return None, None, None
    denom = float(np.dot(x_, x_))
    if denom == 0: return None, None, None
    k     = float(np.dot(x_, y_) / denom)
    pred  = k * x_; resid = y_ - pred
    ss_r  = float(np.sum(resid**2)); ss_t = float(np.sum((y_ - y_.mean())**2))
    r2    = 1 - ss_r/ss_t if ss_t > 0 else 0
    se_k  = float(np.sqrt(ss_r / max(n-1,1) / max(denom,1e-9)))
    return k, se_k, r2

def _fit_linear_with_intercept(x, y):
    """
    Fit y = a + b*x
    Returns dict with a (intercept), b (slope), se_a, se_b, r2, rmse, F, pF
    """
    mask = ~np.isnan(y)
    x_, y_ = x[mask], y[mask]
    n = len(x_)
    if n < 5:
        return None

    # Design matrix: [1, x]
    X = np.column_stack([np.ones(n), x_])

    # Least squares solution
    c, _, _, _ = lstsq(X, y_, rcond=None)
    a, b = c

    # Predictions and residuals
    pred = X @ c
    resid = y_ - pred
    ss_r = float(np.sum(resid**2))
    ss_t = float(np.sum((y_ - y_.mean())**2))
    r2 = 1 - ss_r/ss_t if ss_t > 0 else 0
    rmse = float(np.sqrt(ss_r / n))

    # --- Standard errors ---
    dof = max(n - 2, 1)
    sigma2 = ss_r / dof
    XtX_inv = np.linalg.inv(X.T @ X)
    cov = sigma2 * XtX_inv
    se_a = float(np.sqrt(cov[0, 0]))
    se_b = float(np.sqrt(cov[1, 1]))

    # --- F-statistic ---
    F_ = (ss_t - ss_r) / 2 / (ss_r / dof) if ss_r > 0 else 0
    pF = float(1 - sp_stats.f.cdf(max(F_, 0), 2, dof))

    return dict(a=float(a), b=float(b), se_a=se_a, se_b=se_b, r2=r2, rmse=rmse, F=F_, pF=pF)


def _fit_curve(fn, x, y, p0):
    mask = ~np.isnan(y)
    x_, y_ = x[mask], y[mask]
    n = len(y_)
    if n < len(p0) + 2: return None
    try:
        popt, pcov = curve_fit(fn, x_, y_, p0=p0, maxfev=20000)
    except RuntimeError:
        return None
    perr = np.sqrt(np.diag(pcov))
    pred = fn(x_, *popt); resid = y_ - pred
    ss_r = float(np.sum(resid**2)); ss_t = float(np.sum((y_ - y_.mean())**2))
    r2   = 1 - ss_r/ss_t if ss_t > 0 else 0
    p    = len(p0)
    F_   = (ss_t-ss_r)/p / (ss_r/max(n-p-1,1)) if ss_r > 0 else 0
    pF   = float(1 - sp_stats.f.cdf(max(F_,0), p, max(n-p-1,1)))
    tc   = float(sp_stats.t.ppf(0.975, df=max(n-p,1)))
    return dict(popt=popt, perr=perr, r2=r2, rmse=float(np.sqrt(ss_r/n)),
                F=F_, pF=pF, tc=tc)


# ---- -model --------------------------------------------------------------

def cmd_model(csv_paths, params_path):
    if not HAS_KM or not HAS_SCIPY:
        print("ERROR: kinematics.py and scipy are required for -model.")
        return
    missing = [p for p in csv_paths if not Path(p).exists()]
    if missing:
        for p in missing:
            print(f"ERROR: Input CSV not found: {p}")
        print("       Run -extract first to create the CSV.")
        return

    params_path = Path(params_path)
    mount_params, saved_json = _load_mount_params(params_path)
    # Always start with zero parameters for -model
    mount_params, saved_json = _km.MountModelParams(), {}

    if saved_json:
        tm = saved_json.get('mount_model', saved_json.get('theta_model', {}))
        print(f"Loaded initial params from {params_path}:")
        print(f"  m3_tilt_dm2={tm.get('m3_tilt_dm2',0):.4f}  "
              f"m3_tilt_dm1={tm.get('m3_tilt_dm1',0):.4f}  "
              f"m3_tilt_dm3={tm.get('m3_tilt_dm3',0):.4f}  "
              f"m2_tilt_dm2_amp={tm.get('m2_tilt_dm2_amp',0):.4f}  "
              f"m2_tilt_dm2_zero={tm.get('m2_tilt_dm2_zero',0):.4f}  "
              f"m2_roll_coupling={tm.get('m2_roll_coupling',0):.4f}  "
              f"m2_roll_zero={tm.get('m2_roll_zero',45.0):.4f} "
              f"m1_offset={tm.get('m1_offset',0.0):.4f} "
              f"m2_offset={tm.get('m2_offset',0.0):.4f} "
              f"m3_offset={tm.get('m3_offset',0.0):.4f} "
              )
        print()

    all_rows = _load_csvs(csv_paths)
    if not all_rows:
        print("ERROR: No solved rows found.")
        return

    sessions = defaultdict(list)
    for r in all_rows:
        sessions[r['session_id']].append(r)

    n_sessions = len(sessions)
    n_total    = len(all_rows)

    W  = "=" * 66
    W2 = "-" * 66
    print()
    print(W)
    print("  MODEL FITTING")
    print(W)
    print(f"  Sessions     : {n_sessions}")
    print(f"  Observations : {n_total}")
    print(f"  CSV inputs   : {[str(p) for p in csv_paths]}")
    print()

    # ---- QUEST per session --------------------------------------------------
    print(W2)
    print("  QUEST FRAME ALIGNMENT  (fitted per session from all rows)")
    print(W2)
    print()

    session_alignQ = {}
    session_roll_adj = {}
    all_pred_rows  = []

    for sid, rows in sorted(sessions.items()):
        alignQ = _fit_alignQ_from_rows(rows, mount_params)
        roll_adj = _fit_roll_adj_from_rows(rows)
        if alignQ is None:
            print(f"  SKIP {sid}: insufficient data for QUEST (<3 valid rows)")
            continue
        session_alignQ[sid] = alignQ
        session_roll_adj[sid] = roll_adj
        w, x, y, z = alignQ.w, alignQ.x, alignQ.y, alignQ.z
        az_ax = alignQ.rotate([0, 0, 1])
        tilt  = math.degrees(math.acos(max(-1.0, min(1.0, az_ax[2]))))
        taz   = math.degrees(math.atan2(az_ax[0], az_ax[1])) % 360
        print(f"  Session : {sid}  (N={len(rows)})")
        print(f"  alignQ  w={w:.7f}  x={x:.7f}  y={y:.7f}  z={z:.7f}")
        print(f"  Frame tilt: {tilt*60:.1f}' toward az={taz:.1f} deg")
        print(f"  Roll Adj:   {roll_adj:.5f} deg")
        print()

        preds = [_predict_row(r, alignQ, roll_adj, mount_params) for r in rows]
        valid = [(r, p) for r, p in zip(rows, preds) if p is not None]
        all_pred_rows.extend(valid)

    if not all_pred_rows:
        print("ERROR: No valid predictions to fit model from.")
        return

    # ---- Build arrays -------------------------------------------------------
    def _col(key):
        out = []
        for r, p in all_pred_rows:
            try: out.append(float(r[key]))
            except (ValueError, TypeError): out.append(float('nan'))
        return np.array(out)

    def _pcol(key):
        return np.array([float(p[key]) if p and not math.isnan(p[key]) else float('nan')
                         for _, p in all_pred_rows])

    n        = len(all_pred_rows)
    theta2   = _col('p_theta2')
    theta3   = _col('p_theta3')
    p_az     = _col('p_az')
    az_rad   = np.radians(p_az)
    t3_range = float(np.nanmax(theta3) - np.nanmin(theta3))
    t2_range = float(np.nanmax(theta2) - np.nanmin(theta2))

    dev_m_t2  = _pcol('_dev_m_theta2')
    dev_m_t3  = _pcol('_dev_m_theta3')
    dev_m_az  = _pcol('dev_m_az')
    dev_p_az  = _col('dev_p_az')
    dev_p_alt = _col('dev_p_alt')

    sin_theta3 = np.sin(np.radians(theta3))

    rms_baseline = float(np.sqrt(np.nanmean(dev_m_t2**2)))

    # ---- Section A: SPA / Frame tilt diagnostics ----------------------------
    print()
    print(W)
    print("  SECTION A -- SPA / FRAME TILT  (diagnostic, handled by QUEST)")
    print(W)
    print()
    print("  The SPA (Single Point Alignment) bakes the Polaris firmware's")
    print("  initial alignment into qC2B_raw.  QUEST corrects any residual")
    print("  frame tilt per session.  Sinusoid amplitude should be small")
    print("  after QUEST is applied.  Large values indicate poor SPA or")
    print("  that not enough az-spread sync points were used.")
    print()
    print("  Raw dev_p_alt = A*cos(az) + B*sin(az) + C  (pre-QUEST):")
    res_ft = _fit_sincos(az_rad, dev_p_alt)
    if res_ft:
        print(f"    Amplitude : {res_ft['amp']:+.1f}'   Phase: {res_ft['phase']:+.1f} deg  "
              f"Offset C: {res_ft['C']:+.1f}'")
        print(f"    R2={res_ft['r2']:.3f}  RMSE={res_ft['rmse']:.1f}'  {_sig(res_ft['pF'])}")
        if res_ft['amp'] > 60:
            print(f"    WARNING: Large frame tilt ({res_ft['amp']:.0f}'). Check SPA and use")
            print(f"    6+ sync points spread across the full az circle.")
        elif res_ft['amp'] > 20:
            print(f"    CAUTION: Moderate frame tilt ({res_ft['amp']:.0f}'). Consider more")
            print(f"    sync points spread across az=N/E/S/W.")
        else:
            print(f"    OK: Frame tilt is small ({res_ft['amp']:.0f}').")
    print()

    # ---- Section B: Mechanical corrections ----------------------------------
    print()
    print(W)
    print("  SECTION B -- MECHANICAL CORRECTIONS  (motor-space fitting)")
    print(W)
    print()
    print(f"  Fitting residuals after QUEST.  N={n} observations.")
    print()
    print(f"  -- M3 tilt correction ----------------------------------------------")
    print(f"  The M3 axis may be physically tilted by a small angle ε from the true camera-up direction.")
    print(f"  This may include a tilt towards the boresight or M2 axis and effects residuals on all axes.")
    print(f"  Theta3 range in data: {np.nanmin(theta3):.1f} to {np.nanmax(theta3):.1f} deg"
          f"  (span={t3_range:.1f})")
    print()

    r2_f = r2_g = r2_h = r2_e = r2_bore = None
    fitted_f = fitted_g = fitted_a = fitted_b = fitted_e = None
    fitted_h = fitted_z = fitted_bore = None

    print(f"  -- M3 tilt correction — theta3 effect on theta1 residuals ----------")
    y_field, x_field  = 'dev_q_theta1',   'q_theta3',      
    y_vals, x_vals    = _pcol(y_field),   _pcol(x_field)
    fnx = lambda x: 1 - np.cos(np.radians(x))
    fnx_vals = fnx(x_vals)
    rms_baseline = float(np.sqrt(np.nanmean(y_vals**2)))
    print(f"     Fitted error: {y_field} [arcmin] = g * (1 - cos({x_field})) + c")
    mask_g = ~np.isnan(y_vals) & ~np.isnan(fnx_vals) 
    if mask_g.sum() >= 10:
        soln = _fit_linear_with_intercept(fnx_vals, y_vals)
        if soln is not None:
            fitted_g, se_g, r2_g = soln['b'], soln['se_b'], soln['r2']
            resid_g = y_vals[mask_g] - fitted_g * fnx_vals[mask_g]
            rms_before   = float(np.sqrt(np.nanmean(y_vals[mask_g]**2)))
            rms_after    = float(np.sqrt(np.nanmean(resid_g**2)))
            impr_g = (1 - rms_after/rms_before)*100 if rms_before > 0 else 0
            corr_g = float(np.corrcoef(fnx_vals[mask_g], y_vals[mask_g])[0,1])
            print(f"     where: g = m3_tilt_dm1 = {fitted_g:+6.2f} arcmin  +/-{se_g:4.2f}              R2={r2_g:5.3f}")
            print(f"            c = intercept   = {soln["a"]:+6.4f} arcmin  +/-{soln["se_a"]:4.2f}")
            print(f"     Baseline RMS Error: {rms_before:5.1f}' Residual RMS Error {rms_after:5.1f}'         ({impr_g:+3.0f}% improvement)")
            print(f"     Corr(fn({x_field}), {y_field}) = {corr_g:+5.3f}")
            print(f"     eg. {y_field} at +40 deg roll: {abs(fitted_g*fnx(40)):.1f}'")
            print(f"     Summary: Important parameter for mechanical alignment correction.")
        else:
            fitted_g = 0
            print("     FIT FAILED")
    else:
        print(f"     Insufficient data (N={mask_g.sum()}, need >= 10 with |theta3| > 5).")
    print()

    print(f"  -- M3 tilt correction — theta3 effect on theta2 residuals ----------")
    y_field, x_field  = 'dev_q_theta2',   'q_theta3',      
    y_vals, x_vals    = _pcol(y_field),   _pcol(x_field)
    fnx = lambda x: np.sin(np.radians(x))
    fnx_vals = fnx(x_vals)
    rms_baseline = float(np.sqrt(np.nanmean(y_vals**2)))
    corr_f = float(np.corrcoef(fnx_vals[~np.isnan(y_vals)], y_vals[~np.isnan(y_vals)])[0,1])
    print(f"     Fitted error: {y_field} [arcmin] = f * sin({x_field}) + c")
    if t3_range >= 10:
        soln = _fit_linear_with_intercept(fnx_vals, y_vals)
        if soln is not None:
            fitted_f, se_f, r2_f = soln['b'], soln['se_b'], soln['r2']
            resid_f = y_vals - fitted_f * fnx_vals
            rms_after_f = float(np.sqrt(np.nanmean(resid_f**2)))
            impr_f = (1 - rms_after_f/rms_baseline)*100 if rms_baseline > 0 else 0
            print(f"     where: f = m3_tilt_dm2 = {fitted_f:+6.2f} arcmin/deg_M3  +/-{se_f:4.2f}       R2={r2_f:5.3f}")
            print(f"            c = intercept   = {soln["a"]:+6.4f} arcmin/deg_M3  +/-{soln["se_a"]:4.2f}")
            print(f"     Baseline RMS Error: {rms_baseline:5.1f}' Residual RMS Error: {rms_after_f:5.1f}'         ({impr_f:+3.0f}% improvement)")
            print(f"     Corr(fn({y_field}), {x_field}) = {corr_f:+.3f}")
            print(f"     eg. {y_field} at +-40 deg roll: {abs(fitted_f*fnx(40)):5.1f}'")
            print(f"     eg. {y_field} at +-60 deg roll: {abs(fitted_f*fnx(60)):5.1f}'")
            print(f"     Summary: Theta1/Theta3 corrections make this parameter redundant.")
    else:
        fitted_f = 0
        print(f"     Insufficient theta3 span ({t3_range:.0f} deg, need >= 10).")
    print()

    print(f"  -- M3 tilt correction — theta3 effect on theta3 residuals ----------")
    y_field, x_field, x2_field = 'dev_q_theta3',   'q_theta3',  'q_theta2'      
    y_vals, x_vals, x2_vals    = _pcol(y_field),   _pcol(x_field),  _pcol(x2_field)
    fnx = lambda x3,x2: np.cos(np.radians(x2)) * (1 - np.cos(np.radians(x3)))
    fnx_vals = fnx(x_vals,x2_vals)
    rms_baseline = float(np.sqrt(np.nanmean(y_vals**2)))
    print(f"     Fitted error: {y_field} [arcmin] = k * cos({x2_field}) * (1 - cos({x_field})) + c")
    mask_k = ~np.isnan(y_vals) & ~np.isnan(fnx_vals) 
    if mask_k.sum() >= 10:
        soln = _fit_linear_with_intercept(fnx_vals, y_vals)
        if soln is not None:
            fitted_k, se_k, r2_k = soln['b'], soln['se_b'], soln['r2']
            resid_k = y_vals[mask_k] - fitted_k * fnx_vals[mask_k]
            rms_before   = float(np.sqrt(np.nanmean(y_vals[mask_k]**2)))
            rms_after    = float(np.sqrt(np.nanmean(resid_k**2)))
            impr_k = (1 - rms_after/rms_before)*100 if rms_before > 0 else 0
            corr_k = float(np.corrcoef(fnx_vals[mask_k], y_vals[mask_k])[0,1])
            print(f"     where: k = m3_tilt_dm3 = {fitted_k:+6.2f} arcmin  +/-{se_k:4.2f}              R2={r2_k:5.3f}")
            print(f"            c = intercept   = {soln["a"]:+6.4f} arcmin  +/-{soln["se_a"]:4.2f}")
            print(f"     Baseline RMS Error: {rms_before:5.1f}' Residual RMS Error {rms_after:5.1f}'         ({impr_k:+3.0f}% improvement)")
            print(f"     Corr(fn({x2_field}), {y_field}) = {corr_k:+5.3f}")
            print(f"     eg. {y_field} at +45 deg roll, t2=60: {abs(fitted_k*fnx(45,60)):.1f}'")
            print(f"     Expect lower R2 for this model: {r2_k<r2_g} = {r2_k:5.3f} <{r2_g:5.3f}")
            print(f"     Parameter should NOT be applied, Driver relies on theta3/theta1 geometry.")
            print(f"     Summary: Rely on Theta3/Theta1 geometry instead of this parameter.")
        else:
            fitted_k = 0
            print("     FIT FAILED")
    else:
        print(f"     Insufficient data (N={mask_k.sum()}, need >= 10 with |theta3| > 5).")
    print()

    print(f"  -- M3 tilt correction — theta3/theta1 geometric relationship ----------")
    y_field, x_field, x2_field = 'dev_q_theta3',   'dev_q_theta1',  'q_theta2'      
    y_vals, x_vals, x2_vals    = _pcol(y_field),   _pcol(x_field),  _pcol(x2_field)
    fnx = lambda x3,x2: np.cos(np.radians(x2)) * x3
    fnx_vals = fnx(x_vals, x2_vals)
    rms_baseline = float(np.sqrt(np.nanmean(y_vals**2)))
    print(f"     Fitted error: {y_field} [arcmin] = j * cos({x2_field}) * {x_field} + c")
    mask_j = ~np.isnan(y_vals) & ~np.isnan(fnx_vals) 
    if mask_j.sum() >= 10:
        soln = _fit_linear_with_intercept(fnx_vals, y_vals)
        if soln is not None:
            fitted_j, se_j, r2_j = soln['b'], soln['se_b'], soln['r2']
            resid_j = y_vals[mask_j] - fitted_j * fnx_vals[mask_j]
            rms_before   = float(np.sqrt(np.nanmean(y_vals[mask_j]**2)))
            rms_after    = float(np.sqrt(np.nanmean(resid_j**2)))
            impr_j = (1 - rms_after/rms_before)*100 if rms_before > 0 else 0
            corr_j = float(np.corrcoef(fnx_vals[mask_j], y_vals[mask_j])[0,1])
            print(f"     where: j = m3_tilt_dm31 = {fitted_j:+5.3f} arcmin  +/-{se_j:4.2f}              R2={r2_j:5.3f}")
            print(f"            c = intercept    = {soln["a"]:+6.4f} arcmin  +/-{soln["se_a"]:4.2f}")
            print(f"     Baseline RMS Error: {rms_before:5.1f}' Residual RMS Error {rms_after:5.1f}'         ({impr_j:+3.0f}% improvement)")
            print(f"     Corr(fn({x_field}), {y_field}) = {corr_j:+5.3f}")
            print(f"     Expect geometric relationship: {abs(fitted_j+1)<0.10} = {fitted_j:+5.3f} approx -1")
            print(f"     Summary: Important relationship for mechanical alignment correction.")
        else:
            fitted_j = 0
            print("     FIT FAILED")
    else:
        print(f"     Insufficient data (N={mask_j.sum()}, need >= 10 with |theta3| > 5).")
    print()

    print(f"  -- M2 tilt correction ----------------------------------------------")
    print(f"  The M2 axis may be physically tilted by a small angle ε from being perpendicular to M1.")
    print(f"  This may include a tilt towards the vertical or boresight axis and effects residuals on Az and Alt axes.")
    print(f"  Theta2 range in data: {np.nanmin(theta2):.1f} to {np.nanmax(theta2):.1f} deg"
          f"  (span={t2_range:.1f})")
    print()

    print(f"  -- M2 tilt correction - theta2 effect on remaining theta2 residuals ----------")
    y_field, x_field, t3_field= 'dev_q_theta2',  'q_theta2',     'q_theta3'      
    y_vals,  x_vals,  t3_vals  = _pcol(y_field),  _pcol(x_field), _pcol(t3_field)
    y_vals = y_vals - (fitted_f * np.sin(np.radians(t3_vals)) if fitted_f is not None else 0)
    mask_m2 = np.abs(t3_vals) < 4
    p0a  = [52.0, 1.0]
    print(f"     Fitted error: {y_field}^ [arcmin] = a * sin({x_field} - b)")
    fnx = lambda x, a, b: a * np.sin(np.radians(x - b))
    soln = _fit_curve(fnx, x_vals[mask_m2], y_vals[mask_m2], p0a)
    if soln is not None:
        fitted_a, fitted_b, r2_a = float(soln['popt'][0]), float(soln['popt'][1]), soln['r2']
        resid_b1 = y_vals - fnx(x_vals, fitted_a, fitted_b)
        rms_b1_before = float(np.sqrt(np.nanmean(y_vals[mask_m2]**2)))
        rms_b1_after  = float(np.sqrt(np.nanmean(resid_b1[mask_m2]**2)))
        impr_b1 = (1 - rms_b1_after/rms_b1_before)*100 if rms_b1_before > 0 else 0
        print(f"     where: a = m2_tilt_dm2_amp  = {fitted_a:+5.2f}'  +/-{soln['perr'][0]:4.2f}'               R2={r2_a:5.3f}")
        print(f"            b = m2_tilt_dm2_zero = {fitted_b:+5.2f} deg  +/-{soln['perr'][1]:4.2f} deg")
        print(f"            {y_field}^ = {y_field} after applying M3 tilt correction.")
        print(f"     Baseline RMS Error: {rms_b1_before:.1f}' Residual RMS Error {rms_b1_after:.1f}'            ({impr_b1:+3.0f}% improvement)")
        print(f"     eg. {y_field}^ at +40 deg alt: {abs(fnx(40,fitted_a,fitted_b)):.0f}'")
        if abs(t3_range) < 30:
            fitted_a, fitted_b = 0, 0
            print("     NOTE: M2 tilt fit may be contaminated by M3 tilt if theta3 range is small.")
            print("           Fit M2 tilt from roll=0 data only for cleanest result.")
    else:
        print("     FIT FAILED -- insufficient theta2 variation or poor data coverage.")
    print()

    # M2 roll coupling correction
    print("  -- M2 roll coupling - theta2 effect on boresight roll residuals ----------")
    print("     Fitted error: dev_m_roll [arcmin] = h * (theta2 - m2_roll_zero)")
    print("     Physical cause: M2 motor introduces roll error proportional to")
    print("     displacement from mechanical zero (theta2 = m2_roll_zero).")
    dev_m_roll_arr = np.array(
        [p.get('dev_m_roll', float('nan')) for _, p in all_pred_rows], dtype=float)
    mask_roll = ~np.isnan(dev_m_roll_arr)
    if mask_roll.sum() >= 10:
        # Linear fit: dev_m_roll = h*theta2 + c  =>  zero crossing at z = -c/h
        X_roll = np.column_stack([theta2[mask_roll], np.ones(mask_roll.sum())])
        coeffs_r, _, _, _ = lstsq(X_roll, dev_m_roll_arr[mask_roll], rcond=None)
        h_fit, c_fit = float(coeffs_r[0]), float(coeffs_r[1])
        z_fit = -c_fit / h_fit if abs(h_fit) > 1e-6 else 45.0
        fitted_roll_pred = h_fit * theta2 + c_fit
        ss_r = float(np.nansum((dev_m_roll_arr - fitted_roll_pred) ** 2))
        ss_t = float(np.nansum((dev_m_roll_arr[mask_roll] - dev_m_roll_arr[mask_roll].mean()) ** 2))
        r2_h = 1.0 - ss_r / ss_t if ss_t > 0 else 0.0
        rms_roll_raw   = float(np.sqrt(np.nanmean(dev_m_roll_arr ** 2)))
        rms_roll_after = float(np.sqrt(np.nanmean(
            (dev_m_roll_arr - fitted_roll_pred) ** 2)))
        impr_roll = (1.0 - rms_roll_after / rms_roll_raw) * 100 if rms_roll_raw > 0 else 0
        fitted_h = h_fit
        fitted_z = z_fit
        eg_t2 = 25.0
        print(f"     h = m2_roll_coupling = {fitted_h:+.4f} arcmin/deg             R2={r2_h:.3f}")
        print(f"     z = m2_roll_zero     = {fitted_z:+.2f} deg")
        print(f"     dev_m_roll RMS: {rms_roll_raw:.1f}' -> {rms_roll_after:.1f}'                        ({impr_roll:+.0f}% improvement)")
        print(f"     eg. Roll deviation at theta2={eg_t2:.0f}: {abs(fitted_h*(eg_t2-fitted_z)):.0f}'")
    else:
        print(f"     Insufficient data (N={mask_roll.sum()}).")
    print()


    # ---- Results summary ----------------------------------------------------
    def _quality(fitted, r2):
        rating = "not fitted" if r2 is None else \
                  "GOOD" if r2>0.7 else \
                  "FAIR" if r2>0.4 else \
                  "WEAK" if r2>0.1 else \
                  "POOR"
        quality = f"{rating}" + f"  R2={r2:.3f}" if r2 is not None else ""
        out = fitted if rating in ["GOOD","FAIR"] else 0
        return round(out,6), quality

    f_out, f_quality    = _quality(fitted_f, r2_f)
    g_out, g_quality    = _quality(fitted_g, r2_g)
    k_out, k_quality    = _quality(fitted_k, r2_k)
    a_out, a_quality    = _quality(fitted_a, r2_a)
    b_out, b_quality    = _quality(fitted_b, r2_a)
    h_out, h_quality    = _quality(fitted_h, r2_h)
    z_out, z_quality    = _quality(fitted_z, r2_h)

    print()
    print(W)
    print("  RESULTS SUMMARY")
    print(W)
    print()
    print("# Fitted parameters generated by fits_extract.py (copy to config.toml):")
    print(f"m3_tilt_dm1       = {g_out:+8.2f}                # [arcmin/fn_M3]  {g_quality}")
    print(f"m3_tilt_dm2       = {f_out:+8.2f}                # [arcmin/fn_M3]  {f_quality}")
    print(f"m3_tilt_dm3       = {k_out:+8.2f}                # [arcmin/fn_M3]  {k_quality}")
    print(f"m2_tilt_dm2_amp   = {a_out:+8.2f}                # [arcmin/fn_M2]  {a_quality}")
    print(f"m2_tilt_dm2_zero  = {b_out:+8.2f}                # [degrees     ]  {b_quality}")
    print(f"m2_roll_coupling  = {h_out:+8.2f}                # [arcmin/fn_M2]  {h_quality}")
    print(f"m2_roll_zero      = {z_out:+8.2f}                # [degrees     ]  {z_quality}")
    print(f"m1_offset         =     0.0                 # [arcmin      ]")
    print(f"m2_offset         =     0.0                 # [arcmin      ]")
    print(f"m3_offset         =     0.0                 # [arcmin      ]")
    print()

    warnings = []
    if t3_range < 30:
        warnings.append(
            f"theta3 span only {t3_range:.0f} deg -- M3 tilt fit unreliable (need 60+ deg)")
    if r2_f is not None and r2_f < 0.4:
        warnings.append(
            f"M3 tilt alt R2={r2_f:.3f} is low -- check roll variation in data")
    if r2_a is not None and r2_a < 0.3:
        warnings.append(
            f"M2 tilt R2={r2_a:.3f} is low -- fit M2 tilt from roll=0 data only")
    if r2_k is not None and r2_k < 0.2:
        warnings.append(
            f"M3 boresight R2={r2_k:.3f} is low -- need wider theta3 span for reliable fit")
    if r2_h is not None and r2_h < 0.3:
        warnings.append(
            f"M2 roll coupling R2={r2_h:.3f} is low -- check dev_m_roll variation in data")
    if n_sessions == 1 and n_total < 100:
        warnings.append(
            f"Only {n_total} observations -- more data improves reliability")
    if res_ft and res_ft['amp'] > 60:
        warnings.append(
            f"Frame tilt amplitude {res_ft['amp']:.0f}' is large -- "
            f"check SPA and use 6+ sync points spread across the full az circle")

    if warnings:
        print("  DATA QUALITY WARNINGS:")
        for w_msg in warnings:
            print(f"    !  {w_msg}")
        print()

    print("  Run -validate to confirm improvement on held-out data.")
    print()

    # ---- Save JSON ----------------------------------------------------------
    model_params_out = {
        'm3_tilt_dm2':      f_out,
        'm3_tilt_dm1':      g_out,
        'm3_tilt_dm3':      k_out,
        'm2_tilt_dm2_amp':  a_out,
        'm2_tilt_dm2_zero': b_out,
        'm2_roll_coupling': h_out,
        'm2_roll_zero':     z_out,
        'm1_offset':        0.0,
        'm2_offset':        0.0,
        'm3_offset':        0.0,
    }
    sessions_out = {}
    for sid, alignQ in session_alignQ.items():
        sessions_out[sid] = {
            'alignQ': [round(alignQ.w, 7), round(alignQ.x, 7), round(alignQ.y, 7), round(alignQ.z, 7)],
            'roll_adj': session_roll_adj[sid],
            'n_obs':  len(sessions[sid]),
        }
    output = {
        'mount_model':  model_params_out,
        'sessions':     sessions_out,
        'fit_metadata': {
            'date_fitted':    datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'n_sessions':     n_sessions,
            'n_observations': n_total,
            'csv_inputs':     [str(p) for p in csv_paths],
        }
    }
    with open(params_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"Saved -> {params_path}")
    print()


# ---- -validate -----------------------------------------------------------

def cmd_validate(csv_paths, params_path, output_csv, n_sync):
    if not HAS_KM:
        print("ERROR: kinematics.py required for -validate.")
        return
    missing = [p for p in csv_paths if not Path(p).exists()]
    if missing:
        for p in missing:
            print(f"ERROR: Input CSV not found: {p}")
        print("       Run -extract first to create the CSV.")
        return

    params_path = Path(params_path)
    if not params_path.exists():
        print(f"ERROR: {params_path} not found.  Run -model first.")
        return

    mount_params, saved_json = _load_mount_params(params_path)
    tm = saved_json.get('mount_model', saved_json.get('theta_model', {}))
    print("==== VALIDATE ====")
    print(f"Params: {params_path}")
    print(f"  m3_tilt_dm2={tm.get('m3_tilt_dm2',0):.4f}  "
          f"m3_tilt_dm1={tm.get('m3_tilt_dm1',0):.4f}  "
          f"m2_tilt_dm2_amp={tm.get('m2_tilt_dm2_amp',0):.4f}  "
          f"m2_tilt_dm2_zero={tm.get('m2_tilt_dm2_zero',0):.4f}  "
          f"m3_tilt_dm3={tm.get('m3_tilt_dm3',0):.4f}  "
          f"m2_roll_coupling={tm.get('m2_roll_coupling',0):.4f}  "
          f"m2_roll_zero={tm.get('m2_roll_zero',45.0):.4f} "
          f"m1_offset={tm.get('m1_offset',0.0):.4f} "
          f"m2_offset={tm.get('m2_offset',0.0):.4f} "
          f"m3_offset={tm.get('m3_offset',0.0):.4f} "
          )
    sync_label = 'ALL rows' if n_sync is None else f'first {n_sync} rows'
    print(f"Sync points  : {sync_label} per session")
    print()

    all_rows = _load_csvs(csv_paths)
    if not all_rows:
        print("ERROR: No solved rows found.")
        return

    sessions = defaultdict(list)
    for r in all_rows:
        sessions[r['session_id']].append(r)

    output_rows     = []
    session_summary = []

    for sid, rows in sorted(sessions.items()):
        n_use_sync = len(rows) if n_sync is None else min(n_sync, len(rows))
        sync_set   = set(range(n_use_sync))
        sync_rows  = [rows[i] for i in range(n_use_sync)]

        print(f"---- Session: {sid}  (N={len(rows)}) ----")

        alignQ = _fit_alignQ_from_rows(sync_rows, mount_params)
        roll_adj = _fit_roll_adj_from_rows(sync_rows)
        if alignQ is None:
            print(f"  ERROR: Could not fit alignQ from {len(sync_rows)} sync rows.")
            print()
            continue

        w, x, y, z = alignQ.w, alignQ.x, alignQ.y, alignQ.z
        az_ax = alignQ.rotate([0, 0, 1])
        tilt  = math.degrees(math.acos(max(-1.0, min(1.0, az_ax[2]))))
        taz   = math.degrees(math.atan2(az_ax[0], az_ax[1])) % 360
        print(f"  alignQ  w={w:.7f}  x={x:.7f}  y={y:.7f}  z={z:.7f}")
        print(f"  Frame tilt: {tilt*60:.2f}' toward az={taz:.1f} deg")
        print(f"  Roll Adj: {roll_adj:.5f} deg")
        print(f"  Sync rows used: {n_use_sync} / {len(rows)}")
        print()

        # Per-row accumulators — theta space and sky space, each 3 axes × 3 levels
        # Keys: axes t1/t2/t3 and az/alt/roll; levels p/q/m
        _TAXES = ['t1', 't2', 't3']
        _SAXES = ['az', 'alt', 'roll']
        acc = {ax: {'p': [], 'q': [], 'm': []} for ax in _TAXES + _SAXES}

        for i, row in enumerate(rows):
            pred = _predict_row(row, alignQ, roll_adj, mount_params)
            is_sync = i in sync_set

            out = {k: row.get(k, '') for k in _EXTRACT_FIELDS}
            out['sync_point'] = 'Y' if is_sync else ''
            out['alignQ_w']   = f"{w:.7f}"
            out['alignQ_x']   = f"{x:.7f}"
            out['alignQ_y']   = f"{y:.7f}"
            out['alignQ_z']   = f"{z:.7f}"

            if pred is not None:
                f4 = lambda v: round(v, 4)
                f2 = lambda v: round(v, 2)

                # Quest-only fields
                out['q_az']       = f4(pred['q_az'])
                out['q_alt']      = f4(pred['q_alt'])
                out['q_roll']     = f4(pred['q_roll'])
                out['q_theta1']   = f4(pred['q_theta1'])
                out['q_theta2']   = f4(pred['q_theta2'])
                out['q_theta3']   = f4(pred['q_theta3'])
                out['dev_q_az']   = f2(pred['dev_q_az'])
                out['dev_q_alt']  = f2(pred['dev_q_alt'])
                out['dev_q_roll'] = f2(pred['dev_q_roll'])

                # Full model fields
                out['m_az']       = f4(pred['m_az'])
                out['m_alt']      = f4(pred['m_alt'])
                out['m_roll']     = f4(pred['m_roll'])
                out['m_theta1']   = f4(pred['m_theta1'])
                out['m_theta2']   = f4(pred['m_theta2'])
                out['m_theta3']   = f4(pred['m_theta3'])
                out['dev_m_az']   = f2(pred['dev_m_az'])
                out['dev_m_alt']  = f2(pred['dev_m_alt'])
                out['dev_m_roll'] = f2(pred['dev_m_roll'])

                for k in ('dev_p_theta1', 'dev_p_theta2', 'dev_p_theta3',
                          'dev_q_theta1', 'dev_q_theta2', 'dev_q_theta3',
                          'dev_m_theta1', 'dev_m_theta2', 'dev_m_theta3'):
                    v = pred.get(k, float('nan'))
                    if not math.isnan(v):
                        out[k] = f2(v)

                # Accumulate per-axis residuals for RMS
                _pmap = {
                    't1':   ('dev_p_theta1', 'dev_q_theta1', 'dev_m_theta1'),
                    't2':   ('dev_p_theta2', 'dev_q_theta2', 'dev_m_theta2'),
                    't3':   ('dev_p_theta3', 'dev_q_theta3', 'dev_m_theta3'),
                    'az':   ('dev_p_az',     'dev_q_az',     'dev_m_az'),
                    'alt':  ('dev_p_alt',    'dev_q_alt',    'dev_m_alt'),
                    'roll': ('dev_p_roll',   'dev_q_roll',   'dev_m_roll'),
                }
                for ax, (pk, qk, mk) in _pmap.items():
                    try:
                        vp = pred.get(pk, float('nan'))
                        vq = pred.get(qk, float('nan'))
                        vm = pred.get(mk, float('nan'))
                        # raw p values come from the row for sky axes
                        if ax in _SAXES:
                            vp = float(row.get(pk, 'nan') or 'nan')
                        if not math.isnan(vp):
                            acc[ax]['p'].append(vp)
                            acc[ax]['q'].append(vq)
                            acc[ax]['m'].append(vm)
                    except Exception:
                        pass

                output_rows.append(out)

        # ---- Per-session RMS computation ------------------------------------
        def _impr(after, before):
            return (1 - after/before)*100 if before > 0 and not math.isnan(after) else float('nan')

        def _rms3(ax_list):
            """Combined 3D RMS across a list of axes (each a list of residuals)."""
            combined = []
            for vals in ax_list:
                combined.extend(vals)
            return _rms(combined)

        rms = {ax: {lvl: _rms(acc[ax][lvl]) for lvl in ('p', 'q', 'm')}
               for ax in _TAXES + _SAXES}

        # 3D combined RMS
        rms3_theta = {lvl: _rms3([acc[ax][lvl] for ax in _TAXES]) for lvl in ('p', 'q', 'm')}
        rms3_sky   = {lvl: _rms3([acc[ax][lvl] for ax in _SAXES]) for lvl in ('p', 'q', 'm')}

        # ---- Per-session results table --------------------------------------
        W_MET = 18; W_VAL = 8; W_IMP = 9
        hdr_sess = (f"  {'Metric':<{W_MET}}  {'Raw':>{W_VAL}}  {'Quest':>{W_VAL}}"
                    f"  {'Model':>{W_VAL}}  {'Q-Impr':>{W_IMP}}  {'M-Impr':>{W_IMP}}")
        sep_sess  = ("  " + "-"*W_MET + "  " + "-"*W_VAL + "  " + "-"*W_VAL
                     + "  " + "-"*W_VAL + "  " + "-"*W_IMP + "  " + "-"*W_IMP)

        def _sess_row(label, rp, rq, rm, flag=''):
            iq = _impr(rq, rp); im = _impr(rm, rp)
            iqs = f"{iq:>+8.1f}%" if not math.isnan(iq) else "      N/A"
            ims = f"{im:>+8.1f}%" if not math.isnan(im) else "      N/A"
            rps = f"{rp:>7.1f}'" if not math.isnan(rp) else "     N/A"
            rqs = f"{rq:>7.1f}'" if not math.isnan(rq) else "     N/A"
            rms_s = f"{rm:>7.1f}'" if not math.isnan(rm) else "     N/A"
            return f"  {label:<{W_MET}}  {rps}  {rqs}  {rms_s}  {iqs}  {ims}{flag}"

        print(f"  Results ({len(rows)} rows, {n_use_sync} sync):")
        print()
        print("  -- Theta space (motor angles) --")
        print(hdr_sess)
        print(sep_sess)
        for ax, label in [('t1', 'theta1 (azimuth)'),
                           ('t2', 'theta2 (altitude)'),
                           ('t3', 'theta3 (roll)')]:
            print(_sess_row(label, rms[ax]['p'], rms[ax]['q'], rms[ax]['m']))
        print(sep_sess)
        print(_sess_row('3D combined RMS',
                        rms3_theta['p'], rms3_theta['q'], rms3_theta['m']))
        print()
        print("  -- Sky space (az/alt/roll) --")
        print(hdr_sess)
        print(sep_sess)
        for ax, label in [('az',   'az'),
                           ('alt',  'alt'),
                           ('roll', 'roll')]:
            print(_sess_row(label, rms[ax]['p'], rms[ax]['q'], rms[ax]['m']))
        print(sep_sess)
        print(_sess_row('3D combined RMS',
                        rms3_sky['p'], rms3_sky['q'], rms3_sky['m']))
        print()

        session_summary.append({
            'sid': sid, 'n': len(rows), 'n_sync': n_use_sync,
            'rms': rms,
            'rms3_theta': rms3_theta,
            'rms3_sky':   rms3_sky,
        })

    # ---- Write CSV ----------------------------------------------------------
    output_csv = Path(output_csv)
    with open(output_csv, 'w', newline='') as f:
        w2 = csv.DictWriter(f, fieldnames=_PREDICT_FIELDS, extrasaction='ignore')
        w2.writeheader()
        w2.writerows(output_rows)
    print(f"Wrote {len(output_rows)} rows -> {output_csv}")
    print()

    # ---- Validation summary -------------------------------------------------
    W    = "=" * 82
    W2   = "-" * 82
    W_SID = 28; W_VAL = 8; W_IMP = 9

    def _impr(after, before):
        return (1 - after/before)*100 if before > 0 and not math.isnan(after) else float('nan')

    # Build per-axis overall means (mean of per-session RMS values)
    _TAXES = ['t1', 't2', 't3']
    _SAXES = ['az', 'alt', 'roll']

    def _mean_across_sessions(ax, lvl):
        vals = [s['rms'][ax][lvl] for s in session_summary
                if not math.isnan(s['rms'][ax][lvl])]
        return sum(vals)/len(vals) if vals else float('nan')

    def _mean_rms3(space, lvl):
        """Mean of per-session 3D combined RMS."""
        key = 'rms3_theta' if space == 'theta' else 'rms3_sky'
        vals = [s[key][lvl] for s in session_summary if not math.isnan(s[key][lvl])]
        return sum(vals)/len(vals) if vals else float('nan')

    hdr_sum = (f"  {'Session':<{W_SID}}  {'N':>5}  {'Raw':>{W_VAL}}  {'Quest':>{W_VAL}}"
               f"  {'Model':>{W_VAL}}  {'Q-Impr':>{W_IMP}}  {'M-Impr':>{W_IMP}}")
    sep_sum  = ("  " + "-"*W_SID + "  " + "-"*5 + "  " + "-"*W_VAL + "  " + "-"*W_VAL
                + "  " + "-"*W_VAL + "  " + "-"*W_IMP + "  " + "-"*W_IMP)

    def _sum_row(label, n, rp, rq, rm, flag=''):
        iq = _impr(rq, rp); im = _impr(rm, rp)
        iqs = f"{iq:>+8.1f}%" if not math.isnan(iq) else "      N/A"
        ims = f"{im:>+8.1f}%" if not math.isnan(im) else "      N/A"
        rps = f"{rp:>7.1f}'" if not math.isnan(rp) else "     N/A"
        rqs = f"{rq:>7.1f}'" if not math.isnan(rq) else "     N/A"
        rms_s = f"{rm:>7.1f}'" if not math.isnan(rm) else "     N/A"
        ns    = f"{n:>5}" if n is not None else "     "
        return f"  {label:<{W_SID}}  {ns}  {rps}  {rqs}  {rms_s}  {iqs}  {ims}{flag}"

    def _print_axis_table(title, note, axes_labels, rms3_key):
        """Print a per-session × per-axis block, then an OVERALL row."""
        print(f"  {title}")
        if note:
            print(f"  {note}")
        print()
        for ax, ax_label in axes_labels:
            print(f"  {ax_label}:")
            print(hdr_sum)
            print(sep_sum)
            col_p = []; col_q = []; col_m = []
            for s in session_summary:
                rp = s['rms'][ax]['p']
                rq = s['rms'][ax]['q']
                rm = s['rms'][ax]['m']
                im = _impr(rm, rp)
                flag = "  ***" if not math.isnan(im) and im > 30 else \
                       "  *"   if not math.isnan(im) and im > 10 else ""
                print(_sum_row(s['sid'], s['n'], rp, rq, rm, flag))
                if not math.isnan(rp): col_p.append(rp)
                if not math.isnan(rq): col_q.append(rq)
                if not math.isnan(rm): col_m.append(rm)
            if col_p:
                ov_p = sum(col_p)/len(col_p)
                ov_q = sum(col_q)/len(col_q) if col_q else float('nan')
                ov_m = sum(col_m)/len(col_m) if col_m else float('nan')
                print(sep_sum)
                print(_sum_row('OVERALL', None, ov_p, ov_q, ov_m))
            print()

        # 3D combined RMS across all axes in this space
        print(f"  3D combined RMS ({', '.join(lbl for _, lbl in axes_labels)}):")
        print(hdr_sum)
        print(sep_sum)
        col_p = []; col_q = []; col_m = []
        for s in session_summary:
            rp = s[rms3_key]['p']; rq = s[rms3_key]['q']; rm = s[rms3_key]['m']
            im = _impr(rm, rp)
            flag = "  ***" if not math.isnan(im) and im > 30 else \
                   "  *"   if not math.isnan(im) and im > 10 else ""
            print(_sum_row(s['sid'], s['n'], rp, rq, rm, flag))
            if not math.isnan(rp): col_p.append(rp)
            if not math.isnan(rq): col_q.append(rq)
            if not math.isnan(rm): col_m.append(rm)
        if col_p:
            ov_p = sum(col_p)/len(col_p)
            ov_q = sum(col_q)/len(col_q) if col_q else float('nan')
            ov_m = sum(col_m)/len(col_m) if col_m else float('nan')
            print(sep_sum)
            print(_sum_row('OVERALL', None, ov_p, ov_q, ov_m))
            ov_qi = _impr(ov_q, ov_p); ov_mi = _impr(ov_m, ov_p)
            if not math.isnan(ov_mi):
                if ov_mi > 50:   verdict = f"EXCELLENT: {ov_mi:.0f}% total improvement."
                elif ov_mi > 25: verdict = f"GOOD: {ov_mi:.0f}% total improvement."
                elif ov_mi > 10: verdict = f"MODERATE: {ov_mi:.0f}% improvement."
                elif ov_mi > 0:  verdict = f"MARGINAL: {ov_mi:.0f}% improvement."
                else:            verdict = f"NO IMPROVEMENT ({ov_mi:.0f}%)."
                print()
                print(f"  {verdict}")
            if not math.isnan(ov_qi) and not math.isnan(ov_mi):
                print(f"  Improvement breakdown: QUEST={ov_qi:+.1f}%  Mechanical={ov_mi-ov_qi:+.1f}%")
        print()

    print(W)
    print("  VALIDATION SUMMARY")
    print(W)
    print()
    print("  Quest column = QUEST only (no mechanical corrections).")
    print("  Model column = full pipeline (QUEST + mechanical corrections).")
    print("  Q-Impr/M-Impr = improvement vs Raw.")
    print()

    _print_axis_table(
        "THETA SPACE  (motor angles — primary metric for correction quality)",
        "theta2 is the direct observable for M2/M3 tilt corrections.",
        [('t1', 'theta1 (azimuth motor)'),
         ('t2', 'theta2 (altitude motor)  <-- KEY'),
         ('t3', 'theta3 (roll motor)')],
        'rms3_theta',
    )

    _print_axis_table(
        "SKY SPACE  (az / alt / roll — observer-frame residuals)",
        "Roll included. Sky errors at large roll are partly motor-geometry coupling.",
        [('az',   'az'),
         ('alt',  'alt'),
         ('roll', 'roll')],
        'rms3_sky',
    )


# ---- Entry point ---------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        prog='fits_extract.py',
        description='Calibration utility for the Alpaca Benro Polaris Driver.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('-extract',  action='store_true',
                        help='Read FITS files -> {prefix}extract.csv + {prefix}extract.txt')
    parser.add_argument('-model',    action='store_true',
                        help='Fit model -> {prefix}model.json + {prefix}model.txt')
    parser.add_argument('-validate', action='store_true',
                        help='Validate -> {prefix}validate.csv + {prefix}validate.txt')
    parser.add_argument('-prefix', metavar='PFX', default='fits_',
                        help='Filename prefix for all outputs. Default: fits_')
    parser.add_argument('-dir',    metavar='DIR',  default='.',
                        help='FITS directory for -extract. Default: current dir')
    parser.add_argument('-sync',   metavar='N', type=int, default=None,
                        help='Sync points per session for -validate (default: ALL).')
    parser.add_argument('-lat',    metavar='DEG', type=float, default=DEFAULT_LAT,
                        help=f'Site latitude.  Default: {DEFAULT_LAT}')
    parser.add_argument('-lon',    metavar='DEG', type=float, default=DEFAULT_LON,
                        help=f'Site longitude. Default: {DEFAULT_LON}')

    args = parser.parse_args()

    if not any([args.extract, args.model, args.validate]):
        parser.error('Specify one of -extract, -model, or -validate.')

    pfx = args.prefix
    extract_csv  = f'{pfx}extract.csv'
    extract_txt  = f'{pfx}extract.txt'
    model_json   = f'{pfx}model.json'
    model_txt    = f'{pfx}model.txt'
    validate_csv = f'{pfx}validate.csv'
    validate_txt = f'{pfx}validate.txt'

    if args.extract:  log_path = extract_txt
    elif args.model:  log_path = model_txt
    else:             log_path = validate_txt

    try:
        _log_file_handle = open(log_path, 'w', encoding='utf-8')
        sys.modules[__name__].__dict__['_log_file'] = _log_file_handle
    except OSError as e:
        _builtins.print(f"WARNING: Cannot open log file {log_path}: {e}")
        _log_file_handle = None

    try:
        if args.extract:
            cmd_extract(args.dir, extract_csv, args.lat, args.lon)

        if args.model:
            cmd_model([extract_csv], model_json)

        if args.validate:
            cmd_validate([extract_csv], model_json, validate_csv, args.sync)

    except KeyboardInterrupt:
        sys.stderr.write('\r' + ' ' * 80 + '\r')
        sys.stderr.flush()
        print()
        print("Interrupted by user.")
    finally:
        lf = sys.modules[__name__].__dict__.get('_log_file')
        if lf is not None:
            lf.close()