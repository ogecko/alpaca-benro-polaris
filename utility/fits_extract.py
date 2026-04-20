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
  1. Disable ALL mechanical corrections in the driver config: QUEST off, RBC off, LGA off, PEC off
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
  m_*      Model prediction  (corrections + QUEST applied)
  dev_p_*  Raw deviation    = solved - polaris  (arcmin)
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
    from pyquaternion import Quaternion
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
    'site_lat', 'site_lon',
    'p_az', 'p_alt', 'p_roll', 'p_theta1', 'p_theta2', 'p_theta3',
    's_az', 's_alt', 's_roll', 's_theta1', 's_theta2', 's_theta3',
    'dev_p_az', 'dev_p_alt', 'dev_p_roll',
    'pixel_scale_arcsec',
]

_PREDICT_FIELDS = _EXTRACT_FIELDS + [
    'sync_point',
    'alignQ_w', 'alignQ_x', 'alignQ_y', 'alignQ_z',
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
    f4 = lambda v: round(v, 4) if v is not None else ''
    f2 = lambda v: round(v, 2) if v is not None else ''

    try:
        h = _read_header(path)
    except Exception as e:
        row['status'] = f'error: {e}'
        return row

    lat = _sf(h, 'SITELAT',  lat)
    lon = _sf(h, 'SITELONG', lon)
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
            m3_tilt_alt      = tm.get('m3_tilt_alt',      0.0),
            m3_tilt_az       = tm.get('m3_tilt_az',       0.0),
            m2_tilt_alt_amp  = tm.get('m2_tilt_alt_amp',  0.0),
            m2_tilt_alt_zero = tm.get('m2_tilt_alt_zero', 0.0),
            m3_encoder_scale = tm.get('m3_encoder_scale', 0.0),
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
    """Return model prediction dict for one row, or None on error."""
    try:
        p_az  = float(row['p_az']);     p_alt = float(row['p_alt']);    p_roll = float(row['p_roll'])
        p_t1  = float(row['p_theta1']); p_t2 = float(row['p_theta2']);  p_t3 = float(row['p_theta3'])
        s_az  = float(row['s_az']);     s_alt = float(row['s_alt']);    s_roll = float(row['s_roll'])
        s_t1  = float(row['s_theta1']); s_t2  = float(row['s_theta2']); s_t3 = float(row['s_theta3'])
    except (ValueError, TypeError):
        return None
    if not p_roll:
        return None

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
        'm_az':          m_az,
        'm_alt':         m_alt,
        'm_roll':        m_roll,
        'm_theta1':      m_t1,
        'm_theta2':      m_t2,
        'm_theta3':      m_t3,
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
        '_dev_m_theta2': wrap180(s_t2 - m_t2) * 60,
        '_dev_m_theta3': wrap180(s_t3 - m_t3) * 60,
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
        print(f"  m3_tilt_alt={tm.get('m3_tilt_alt',0):.4f}  "
              f"m3_tilt_az={tm.get('m3_tilt_az',0):.4f}  "
              f"m2_tilt_alt_amp={tm.get('m2_tilt_alt_amp',0):.4f}  "
              f"m2_tilt_alt_zero={tm.get('m2_tilt_alt_zero',0):.4f}  "
              f"m3_encoder_scale={tm.get('m3_encoder_scale',0):.4f}  "
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

        preds = [_predict_row(r, alignQ, roll_adj, mount_params) for r in rows]
        valid = [(r, p) for r, p in zip(rows, preds) if p is not None]
        if valid:
            dt2 = np.array([p['_dev_m_theta2'] for _, p in valid])
            print(f"  dev_m_theta2 (M3+M2 tilt residual): {_arr_stats(dt2)}")
        print()
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

    theta2   = _col('p_theta2')
    theta3   = _col('p_theta3')
    p_az     = _col('p_az')
    az_rad   = np.radians(p_az)
    t3_range = float(np.nanmax(theta3) - np.nanmin(theta3))
    n        = len(all_pred_rows)

    dev_m_t2  = _pcol('_dev_m_theta2')
    dev_m_t3  = _pcol('_dev_m_theta3')
    dev_m_az  = _pcol('dev_m_az')
    dev_p_az  = _col('dev_p_az')
    dev_p_alt = _col('dev_p_alt')

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
    print(f"  Baseline dev_m_theta2 RMS (current params): {rms_baseline:.1f}'")
    print()
    print(f"  theta3 range in data: {np.nanmin(theta3):.1f} to {np.nanmax(theta3):.1f} deg"
          f"  (span={t3_range:.1f})")
    print()

    r2_f = r2_g = r2_h = r2_e = None
    fitted_f = fitted_g = fitted_a = fitted_b = fitted_e = None
    fitted_h = fitted_z = None

    # M3 tilt correction — altitude component
    print("  -- M3 tilt correction — altitude/theta2 ----------")
    print("     Fitted error: dev_theta2 [arcmin] = f * theta3")
    corr_f = float(np.corrcoef(theta3[~np.isnan(dev_m_t2)],
                                dev_m_t2[~np.isnan(dev_m_t2)])[0,1])
    print(f"     corr(theta3, dev_m_theta2) = {corr_f:+.3f}")
    if t3_range >= 10:
        k_f, se_f, r2_f = _fit_linear_through_origin(theta3, dev_m_t2)
        if k_f is not None:
            fitted_f = k_f
            tc_f = float(sp_stats.t.ppf(0.975, df=max(n-1,1)))
            resid_f = dev_m_t2 - k_f*theta3
            rms_after_f = float(np.sqrt(np.nanmean(resid_f**2)))
            impr_f = (1 - rms_after_f/rms_baseline)*100 if rms_baseline > 0 else 0
            print(f"     f = m3_tilt_alt = {k_f:+.4f} arcmin/deg  +/-{se_f:.4f}        R2={r2_f:.3f}")
            print(f"     dev_m_theta2 RMS: {rms_baseline:.1f}' -> {rms_after_f:.1f}'                       ({impr_f:+.0f}% improvement)")
            print(f"     eg. Theta2 Deviation at +-40 deg roll: {abs(k_f*40):.0f}'")
    else:
        fitted_f = 0
        print(f"     Insufficient theta3 span ({t3_range:.0f} deg, need >= 10).")
    print()

    # M3 tilt correction — azimuth component
    print("  -- M3 tilt correction — azimuth/theta1 ----------")
    print("     Fitted error: dev_m_az [arcmin] = g * sin(theta2) * theta3")
    pred_g = np.sin(np.radians(theta2)) * theta3
    mask_g = ~np.isnan(dev_m_az) & ~np.isnan(pred_g) & (np.abs(theta3) > 5)
    if mask_g.sum() >= 10:
        k_g, se_g, r2_g = _fit_linear_through_origin(pred_g[mask_g], dev_m_az[mask_g])
        if k_g is not None:
            fitted_g = k_g
            tc_g = float(sp_stats.t.ppf(0.975, df=max(mask_g.sum()-1, 1)))
            resid_g = dev_m_az[mask_g] - k_g * pred_g[mask_g]
            rms_az_raw   = float(np.sqrt(np.nanmean(dev_m_az[mask_g]**2)))
            rms_az_after = float(np.sqrt(np.nanmean(resid_g**2)))
            impr_g = (1 - rms_az_after/rms_az_raw)*100 if rms_az_raw > 0 else 0
            corr_g = float(np.corrcoef(pred_g[mask_g], dev_m_az[mask_g])[0,1])
            print(f"     corr(sin(t2)*t3, dev_m_az) = {corr_g:+.3f}")
            print(f"     g = m3_tilt_az = {k_g:+.4f} arcmin/deg +/-{se_g:.4f}          R2={r2_g:.3f}  ")
            print(f"     dev_m_az RMS: {rms_az_raw:.1f}' -> {rms_az_after:.1f}'                           ({impr_g:+.0f}% improvement)")
            print(f"     eg. Azimuth Deviation at +40 deg roll and alt: {abs(k_g*np.sin(np.radians(40))*40):.0f}'")
        else:
            fitted_g = 0
            print("     FIT FAILED")
    else:
        print(f"     Insufficient data (N={mask_g.sum()}, need >= 10 with |theta3| > 5).")
    print()

    # M2 tilt correction
    print("  -- M2 tilt correction - altitude/theta2 ----------")
    print("     Fitted error: dev_theta2 [arcmin] = a * sin(theta2 - b)")
    r2_m2 = None
    mask_m2 = np.abs(theta3) < 4
    y_b1 = dev_m_t2 - (fitted_f * theta3 if fitted_f is not None else 0)
    p0a  = [mount_params.m2_tilt_alt_amp or 52., mount_params.m2_tilt_alt_zero or 36.]
    r_b1 = _fit_curve(lambda t, a, b: a * np.sin(np.radians(t - b)), theta2[mask_m2], y_b1[mask_m2], p0a)
    if r_b1 is not None:
        fitted_a, fitted_b = float(r_b1['popt'][0]), float(r_b1['popt'][1])
        resid_b1 = y_b1 - r_b1['popt'][0]*np.sin(np.radians(theta2 - r_b1['popt'][1]))
        rms_b1_before = float(np.sqrt(np.nanmean(y_b1**2)))
        rms_b1_after  = float(np.sqrt(np.nanmean(resid_b1**2)))
        impr_b1 = (1 - rms_b1_after/rms_b1_before)*100 if rms_b1_before > 0 else 0
        r2_m2 = r_b1['r2']
        print(f"     a = m2_tilt_alt_amp  = {fitted_a:+.2f}'  +/-{r_b1['perr'][0]:.2f}'               R2={r_b1['r2']:.3f}")
        print(f"     b = m2_tilt_alt_zero = {fitted_b:+.2f} deg  +/-{r_b1['perr'][1]:.2f} deg")
        print(f"     Residual RMS after M3+M2 tilt: {rms_b1_before:.1f}' -> {rms_b1_after:.1f}'          ({impr_b1:+.0f}% improvement)")
        print(f"     eg. Theta2 Deviation at +40 deg alt: {abs(fitted_a*np.sin(np.radians(40-fitted_b))):.0f}'")
        if abs(t3_range) < 30:
            fitted_a, fitted_b = 0, 0
            print("     NOTE: M2 tilt fit may be contaminated by M3 tilt if theta3 range is small.")
            print("           Fit M2 tilt from roll=0 data only for cleanest result.")
    else:
        print("     FIT FAILED -- insufficient theta2 variation or poor data coverage.")
    print()

    # M2 roll coupling correction 
    print("  -- M2 roll coupling - roll/theta2 ----------")
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
        print(f"     h = m2_roll_coupling = {fitted_h:+.4f} arcmin/deg  R2={r2_h:.3f}")
        print(f"     z = m2_roll_zero     = {fitted_z:+.2f} deg")
        print(f"     dev_m_roll RMS: {rms_roll_raw:.1f}' -> {rms_roll_after:.1f}'  ({impr_roll:+.0f}% improvement)")
        print(f"     eg. Roll deviation at theta2={eg_t2:.0f}: {abs(fitted_h*(eg_t2-fitted_z)):.0f}'")
    else:
        print(f"     Insufficient data (N={mask_roll.sum()}).")
    print()

    # M3 encoder correction
    print("  -- M3 encoder correction - roll/theta3 ----------")
    print("     Fitted error: dev_theta3 [arcmin] = e * theta3")
    if t3_range >= 30:
        k_e, se_e, r2_e = _fit_linear_through_origin(theta3, dev_m_t3)
        if k_e is not None:
            fitted_e = k_e
            tc_e = float(sp_stats.t.ppf(0.975, df=max(n-1,1)))
            print(f"     e = m3_encoder_scale = {k_e:+.4f} arcmin/deg  +/-{se_e:.4f}   R2={r2_e:.3f}")
            if r2_e < 0.3:
                fitted_e = 0
                print("     CAUTION: Low R2. dev_theta3 may be contaminated by SPA")
                print("     roll bias. Treat this value with caution.")
    else:
        print(f"     Skipped -- theta3 span {t3_range:.0f} deg < 30 deg minimum.")
        print("     Collect data with p_roll sweeping -60 to +60 at fixed az/alt.")
    print()

    # Offset correction

    # ---- Results summary ----------------------------------------------------
    def _use(fitted, fallback):
        return round(fitted, 6) if fitted is not None else round(fallback, 6)

    f_out = _use(fitted_f, mount_params.m3_tilt_alt)
    g_out = _use(fitted_g, mount_params.m3_tilt_az)
    a_out = _use(fitted_a, mount_params.m2_tilt_alt_amp)
    b_out = _use(fitted_b, mount_params.m2_tilt_alt_zero)
    e_out = _use(fitted_e, mount_params.m3_encoder_scale)
    h_out = _use(fitted_h, mount_params.m2_roll_coupling)
    z_out = round(fitted_z, 6) if fitted_z is not None else round(mount_params.m2_roll_zero, 6)

    y_final = dev_m_t2.copy()
    if fitted_f is not None:
        y_final = y_final - fitted_f * theta3
    if fitted_a is not None and fitted_b is not None:
        y_final = y_final - fitted_a * np.sin(np.radians(theta2 - fitted_b))
    rms_final  = float(np.sqrt(np.nanmean(y_final[~np.isnan(y_final)]**2)))
    impr_total = (1 - rms_final / rms_baseline) * 100 if rms_baseline > 0 else 0

    def _quality(r2):
        if r2 is None:   return "not fitted"
        if r2 > 0.7:     return "GOOD"
        if r2 > 0.4:     return "FAIR"
        if r2 > 0.1:     return "WEAK"
        return "POOR"

    print()
    print(W)
    print("  RESULTS SUMMARY")
    print(W)
    print()
    print("  dev_m_theta2 RMS progression (motor altitude error):")
    print(f"    After QUEST only    : {rms_baseline:7.1f}'  (baseline)")
    if fitted_f is not None:
        rms_after_f2 = float(np.sqrt(np.nanmean((dev_m_t2 - fitted_f * theta3)**2)))
        print(f"    After QUEST + M3 tilt       : {rms_after_f2:7.1f}'")
    print(f"    After QUEST + M3+M2 tilt    : {rms_final:7.1f}'  ({impr_total:+.0f}% total)")
    print()

    r2_f_val  = r2_f   if fitted_f is not None else None
    r2_g_val  = r2_g   if fitted_g is not None else None
    r2_b1_val = r_b1['r2'] if r_b1 is not None else None
    r2_h_val  = r2_h   if fitted_h is not None else None
    r2_e_val  = r2_e   if fitted_e is not None else None

    print("  Fitted parameters  (copy to config.toml):")
    print(f"    m3_tilt_alt      = {f_out:+8.4f}   [M3 tilt alt  arcmin/deg]   {_quality(r2_f_val)}"
          + (f"  R2={r2_f_val:.3f}" if r2_f_val is not None else ""))
    print(f"    m3_tilt_az       = {g_out:+8.4f}   [M3 tilt az   arcmin/deg]   {_quality(r2_g_val)}"
          + (f"  R2={r2_g_val:.3f}" if r2_g_val is not None else ""))
    print(f"    m2_tilt_alt_amp  = {a_out:+8.4f}   [M2 tilt amp  arcmin    ]   {_quality(r2_b1_val)}"
          + (f"  R2={r2_b1_val:.3f}" if r2_b1_val is not None else ""))
    print(f"    m2_tilt_alt_zero = {b_out:+8.4f}   [M2 tilt zero degrees   ]")
    print(f"    m3_encoder_scale = {e_out:+8.4f}   [M3 encoder   arcmin/deg]   {_quality(r2_e_val)}"
          + (f"  R2={r2_e_val:.3f}" if r2_e_val is not None else ""))
    print(f"    m2_roll_coupling = {h_out:+8.4f}   [M2 roll coupling arcmin/deg] {_quality(r2_h_val)}"
          + (f"  R2={r2_h_val:.3f}" if r2_h_val is not None else ""))
    print(f"    m2_roll_zero     = {z_out:+8.4f}   [M2 roll zero  degrees      ]")
    print()

    warnings = []
    if t3_range < 30:
        warnings.append(
            f"theta3 span only {t3_range:.0f} deg -- M3 tilt fit unreliable (need 60+ deg)")
    if r2_f_val is not None and r2_f_val < 0.4:
        warnings.append(
            f"M3 tilt alt R2={r2_f_val:.3f} is low -- check roll variation in data")
    if r2_b1_val is not None and r2_b1_val < 0.3:
        warnings.append(
            f"M2 tilt R2={r2_b1_val:.3f} is low -- fit M2 tilt from roll=0 data only")
    if r2_h_val is not None and r2_h_val < 0.3:
        warnings.append(
            f"M2 roll coupling R2={r2_h_val:.3f} is low -- check dev_m_roll variation in data")
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
        'm3_tilt_alt':      f_out,
        'm3_tilt_az':       g_out,
        'm2_tilt_alt_amp':  a_out,
        'm2_tilt_alt_zero': b_out,
        'm3_encoder_scale': e_out,
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
            'rms_baseline_arcmin':  round(rms_baseline, 2),
            'rms_final_arcmin':     round(rms_final, 2),
            'improvement_pct':      round(impr_total, 1),
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
    print(f"  m3_tilt_alt={tm.get('m3_tilt_alt',0):.4f}  "
          f"m3_tilt_az={tm.get('m3_tilt_az',0):.4f}  "
          f"m2_tilt_alt_amp={tm.get('m2_tilt_alt_amp',0):.4f}  "
          f"m2_tilt_alt_zero={tm.get('m2_tilt_alt_zero',0):.4f}  "
          f"m3_encoder_scale={tm.get('m3_encoder_scale',0):.4f}  "
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

        dev_p_2d_all  = []
        dev_m_2d_all  = []
        dev_p_2d_test = []
        dev_m_2d_test = []
        dev_p_t2_list = []
        dev_m_t2_list = []

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
                out['m_az']    = f4(pred['m_az'])
                out['m_alt']   = f4(pred['m_alt'])
                out['m_roll']  = f4(pred['m_roll'])
                out['m_theta1'] = f4(pred['m_theta1'])
                out['m_theta2'] = f4(pred['m_theta2'])
                out['m_theta3'] = f4(pred['m_theta3'])
                out['dev_m_az']   = f2(pred['dev_m_az'])
                out['dev_m_alt']  = f2(pred['dev_m_alt'])
                out['dev_m_roll'] = f2(pred['dev_m_roll'])
                for k in ('dev_p_theta2','dev_p_theta3','dev_m_theta2','dev_m_theta3'):
                    v = pred.get(k, float('nan'))
                    if not math.isnan(v): out[k] = f2(v)

                try:
                    dp = math.sqrt(float(row.get('dev_p_az',0))**2 +
                                   float(row.get('dev_p_alt',0))**2)
                    dm = math.sqrt(pred['dev_m_az']**2 + pred['dev_m_alt']**2)
                    dev_p_2d_all.append(dp)
                    dev_m_2d_all.append(dm)
                    if not is_sync:
                        dev_p_2d_test.append(dp)
                        dev_m_2d_test.append(dm)
                except Exception:
                    pass
                try:
                    pdt2 = pred.get('dev_p_theta2', float('nan'))
                    dmt2 = pred.get('dev_m_theta2', float('nan'))
                    if not math.isnan(pdt2):
                        dev_p_t2_list.append(pdt2)
                        dev_m_t2_list.append(dmt2)
                except Exception:
                    pass

                output_rows.append(out)

        dp_rms_all  = _rms(dev_p_2d_all)
        dm_rms_all  = _rms(dev_m_2d_all)
        dp_rms_test = _rms(dev_p_2d_test)
        dm_rms_test = _rms(dev_m_2d_test)
        imp_all     = (1 - dm_rms_all/dp_rms_all)*100   if dp_rms_all  > 0 else float('nan')
        imp_test    = (1 - dm_rms_test/dp_rms_test)*100 if dp_rms_test > 0 else float('nan')

        n_test = len(rows) - n_use_sync
        rms_p_t2 = _rms(dev_p_t2_list) if dev_p_t2_list else float('nan')
        rms_m_t2 = _rms(dev_m_t2_list) if dev_m_t2_list else float('nan')
        imp_t2   = (1 - rms_m_t2/rms_p_t2)*100 if rms_p_t2 > 0 else float('nan')

        print(f"  Results ({len(rows)} rows, {n_use_sync} sync):")
        print(f"  {'Metric':<32}  {'Raw':>8}  {'Model':>8}  {'Improv':>8}")
        print(f"  {'-'*32}  {'-'*8}  {'-'*8}  {'-'*8}")
        if not math.isnan(rms_p_t2):
            imp_t2_s = f"{imp_t2:>+7.1f}%" if not math.isnan(imp_t2) else "    N/A"
            good = "  <-- KEY" if not math.isnan(imp_t2) and abs(imp_t2) > 10 else ""
            print(f"  {'Motor theta2 RMS (dev_p/m_theta2)':<32}  "
                  f"{rms_p_t2:>7.1f}'  {rms_m_t2:>7.1f}'  {imp_t2_s}{good}")
        imp_all_s = f"{imp_all:>+7.1f}%" if not math.isnan(imp_all) else "    N/A"
        print(f"  {'Sky 2D RMS (az+alt, all rows)':<32}  "
              f"{dp_rms_all:>7.1f}'  {dm_rms_all:>7.1f}'  {imp_all_s}")
        if n_test > 0 and not math.isnan(dp_rms_test):
            imp_test_s = f"{imp_test:>+7.1f}%" if not math.isnan(imp_test) else "    N/A"
            print(f"  {'Sky 2D RMS (az+alt, test only)':<32}  "
                  f"{dp_rms_test:>7.1f}'  {dm_rms_test:>7.1f}'  {imp_test_s}")
        print()

        session_summary.append({
            'sid': sid, 'n': len(rows), 'n_sync': n_use_sync,
            'dp_all': dp_rms_all, 'dm_all': dm_rms_all, 'imp_all': imp_all,
            'dp_test': dp_rms_test, 'dm_test': dm_rms_test, 'imp_test': imp_test,
            'rms_p_t2': rms_p_t2, 'rms_m_t2': rms_m_t2, 'imp_t2': imp_t2,
        })

    output_csv = Path(output_csv)
    with open(output_csv, 'w', newline='') as f:
        w2 = csv.DictWriter(f, fieldnames=_PREDICT_FIELDS, extrasaction='ignore')
        w2.writeheader()
        w2.writerows(output_rows)
    print(f"Wrote {len(output_rows)} rows -> {output_csv}")
    print()

    print("=" * 66)
    print("  VALIDATION SUMMARY")
    print("=" * 66)
    print()

    has_t2 = any(not math.isnan(s.get('rms_p_t2', float('nan'))) for s in session_summary)
    if has_t2:
        print("  Motor theta2 (KEY metric -- directly measures correction quality):")
        print(f"  {'Session':<34}  {'N':>5}  {'Raw':>8}  {'Model':>8}  {'Improvement':>12}")
        print("  " + "-"*34 + "  " + "-"*5 + "  " + "-"*8 + "  " + "-"*8 + "  " + "-"*12)
        t2_dp = []; t2_dm = []
        for s in session_summary:
            rp = s.get('rms_p_t2', float('nan'))
            rm = s.get('rms_m_t2', float('nan'))
            ii = s.get('imp_t2',   float('nan'))
            if math.isnan(rp): continue
            imps = f"{ii:>+8.1f}%" if not math.isnan(ii) else "       N/A"
            flag = "  ***" if not math.isnan(ii) and ii > 30 else \
                   "  *"   if not math.isnan(ii) and ii > 10 else ""
            print(f"  {s['sid']:<34}  {s['n']:>5}  {rp:>7.1f}'  {rm:>7.1f}'  {imps}{flag}")
            t2_dp.append(rp); t2_dm.append(rm)
        if t2_dp:
            mean_rp = sum(t2_dp)/len(t2_dp)
            mean_rm = sum(t2_dm)/len(t2_dm)
            ov = (1 - mean_rm/mean_rp)*100 if mean_rp > 0 else float('nan')
            print("  " + "-"*34 + "  " + "-"*5 + "  " + "-"*8 + "  " + "-"*8 + "  " + "-"*12)
            ov_s = f"{ov:>+8.1f}%" if not math.isnan(ov) else "       N/A"
            print(f"  {'OVERALL':<34}  {'':>5}  {mean_rp:>7.1f}'  {mean_rm:>7.1f}'  {ov_s}")
            print()
            if not math.isnan(ov):
                if ov > 50:
                    print(f"  EXCELLENT: {ov:.0f}% improvement in motor theta2.")
                elif ov > 25:
                    print(f"  GOOD: {ov:.0f}% improvement in motor theta2.")
                elif ov > 10:
                    print(f"  MODERATE: {ov:.0f}% improvement. Consider refitting parameters.")
                elif ov > 0:
                    print(f"  MARGINAL: {ov:.0f}% improvement. Data quality or model may need review.")
                else:
                    print(f"  NO IMPROVEMENT ({ov:.0f}%). Check parameter signs and data quality.")
        print()

    print("  Sky 2D az+alt (secondary -- note: sky metric can be misleading")
    print("  at large roll due to motor-to-sky geometry coupling):")
    print(f"  {'Session':<34}  {'N':>5}  {'Raw':>8}  {'Model':>8}  {'Improvement':>12}")
    print("  " + "-"*34 + "  " + "-"*5 + "  " + "-"*8 + "  " + "-"*8 + "  " + "-"*12)
    all_dp = []; all_dm = []
    for s in session_summary:
        imp_s = f"{s['imp_all']:>+8.1f}%" if not math.isnan(s['imp_all']) else "       N/A"
        print(f"  {s['sid']:<34}  {s['n']:>5}  {s['dp_all']:>7.1f}'  {s['dm_all']:>7.1f}'  {imp_s}")
        if not math.isnan(s['dp_all']): all_dp.append(s['dp_all'])
        if not math.isnan(s['dm_all']): all_dm.append(s['dm_all'])
    if all_dp:
        mean_dp = sum(all_dp)/len(all_dp)
        mean_dm = sum(all_dm)/len(all_dm)
        ov_imp  = (1 - mean_dm/mean_dp)*100 if mean_dp > 0 else float('nan')
        print("  " + "-"*34 + "  " + "-"*5 + "  " + "-"*8 + "  " + "-"*8 + "  " + "-"*12)
        ov_s = f"{ov_imp:>+8.1f}%" if not math.isnan(ov_imp) else "       N/A"
        print(f"  {'OVERALL':<34}  {'':>5}  {mean_dp:>7.1f}'  {mean_dm:>7.1f}'  {ov_s}")
    print()


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