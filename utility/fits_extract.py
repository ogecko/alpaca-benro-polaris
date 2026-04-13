#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
"""
fits_extract.py - Calibration utility for the Alpaca Benro Polaris Driver.

Pipeline
--------
  -extract    FITS files -> fits_extract.csv  (run once per session, then archive FITS)
  -model      CSV(s) -> fit theta model + per-session QUEST -> fits_params.json
  -validate   CSV(s) + fits_params.json -> fits_predict.csv

Workflow
--------
  1. Capture calibration images in NINA across az/alt/roll grid.
  2. Plate-solve with ASTAP (writes WCS back into FITS headers).
  3. Run -extract to produce a permanent CSV of raw observations.
  4. Run -model to fit the pointing model. Inspect residuals.
     Re-run -model to refine (reads fits_params.json as initial guess).
  5. Run -validate on held-out data to get honest out-of-sample errors.
     Inspect fits_predict.csv in Excel/Python to analyse each correction.

CSV field naming
----------------
  p_*      Polaris raw prediction (what the driver commanded)
  s_*      Solved truth  (plate-solve result)
  m_*      Model prediction  (theta corrections + QUEST)
  dev_p_*  Raw deviation  = solved - polaris  (arcmin)
  dev_m_*  Model residual = solved - model    (arcmin)


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
    import pointing_model as _pm
    HAS_PM = True
except ImportError:
    HAS_PM = False
    print("WARNING: pointing_model.py not found.")

try:
    import ephem
    HAS_EPHEM = True
except ImportError:
    HAS_EPHEM = False
    print("WARNING: ephem not available - solved az/alt won't be computed.")


# ---- Logging (tee to file when -log is given) ---------------------------

import builtins as _builtins

_log_file = None   # set to open file handle when -log is given

def _print(*args, **kwargs):
    """Replacement for print() that also writes to the log file."""
    _builtins.print(*args, **kwargs)
    if _log_file is not None:
        # replicate to log file with same args but no flush control
        end = kwargs.get('end', '\n')
        sep = kwargs.get('sep', ' ')
        line = sep.join(str(a) for a in args) + end
        _log_file.write(line)
        _log_file.flush()

# Shadow the built-in print for all code below this point
print = _print


# ---- Constants -----------------------------------------------------------

DEFAULT_LAT    = -33.86
DEFAULT_LON    = 151.12
ROTATOR_OFFSET = 0.0


# ---- Angle helpers -------------------------------------------------------

def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0

def wrap360(a):
    w = a % 360.0
    return 0.0 if abs(w - 360) < 1e-10 else w

def wrap90(a):
    return (a + 90.0) % 180.0 - 90.0

def rotator_to_p_roll(rotator_deg):
    return wrap180(rotator_deg - ROTATOR_OFFSET)

def calc_parallactic_angle(az_deg, alt_deg, lat_deg):
    if abs(alt_deg - 90.0) < 1e-6:
        return 0.0
    az  = math.radians(az_deg)
    alt = math.radians(alt_deg)
    lat = math.radians(lat_deg)
    return wrap180(-math.degrees(math.atan2(
        math.sin(az),
        math.tan(lat) * math.cos(alt) - math.sin(alt) * math.cos(az))))

def radec_to_altaz(ra_deg, dec_deg, lat_deg, lon_deg, date_obs_utc):
    if not HAS_EPHEM:
        return None, None
    try:
        obs = ephem.Observer()
        obs.lat   = math.radians(lat_deg)
        obs.long  = math.radians(lon_deg)
        obs.date  = ephem.Date(date_obs_utc.split('.')[0].replace('T', ' '))
        obs.epoch = ephem.J2000
        body = ephem.FixedBody()
        body._ra    = math.radians(ra_deg)
        body._dec   = math.radians(dec_deg)
        body._epoch = ephem.J2000
        body.compute(obs)
        return math.degrees(float(body.az)), math.degrees(float(body.alt))
    except Exception:
        return None, None

def crota2_from_cd(cd1_2, cd2_2):
    if abs(cd1_2) < 1e-15 and abs(cd2_2) < 1e-15:
        return None
    return wrap180(math.degrees(math.atan2(-cd1_2, cd2_2)))

def crota2_to_roll(crota2_deg, az_deg, alt_deg, lat_deg):
    para           = calc_parallactic_angle(az_deg, alt_deg, lat_deg)
    position_angle = wrap360(180.0 - crota2_deg)
    return wrap180(position_angle - para), para


# ---- Driver-matching IK --------------------------------------------------

def _azaltroll_to_q(az, alt, roll):
    qaz   = Quaternion(axis=[0, 0, 1], degrees=-az + 90)
    qalt  = Quaternion(axis=[0, 1, 0], degrees=-alt - 90)
    qroll = Quaternion(axis=[0, 0, 1], degrees=roll)
    q1    = qaz * qalt * qroll
    return -(q1.normalised) if roll < 0 else q1.normalised

def _q_to_theta(q):
    """Driver-matching IK. Returns (theta1, theta2, theta3)."""
    tUp    = q.rotate(np.array([1, 0, 0]))
    tRight = q.rotate(np.array([0, 1, 0]))
    th1A   = wrap360(np.degrees(np.arctan2(-tUp[0], -tUp[1])))
    t1rA   = np.radians(th1A)
    s2A    = -(tUp[0] * np.sin(t1rA) + tUp[1] * np.cos(t1rA))
    th2A   = wrap90(np.degrees(np.arctan2(s2A, tUp[2])))
    th1B   = wrap360(th1A + 180)
    th2B   = -th2A
    lo, hi = -8, 83
    okA    = lo <= th2A <= hi
    okB    = lo <= th2B <= hi

    def t3_from(t1, t2):
        qt1 = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
        qt2 = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
        rNM = (qt1 * qt2).rotate([0, 1, 0])
        r1  = rNM    - np.dot(rNM,    tUp) * tUp
        r2  = tRight - np.dot(tRight, tUp) * tUp
        n1, n2 = np.linalg.norm(r1), np.linalg.norm(r2)
        if n1 < 1e-9 or n2 < 1e-9:
            return 0.0
        r1n, r2n = r1 / n1, r2 / n2
        return wrap180(-np.degrees(np.arctan2(
            np.dot(np.cross(r1n, r2n), tUp),
            np.clip(np.dot(r1n, r2n), -1, 1))))

    if okA and not okB:
        return th1A, th2A, t3_from(th1A, th2A)
    if okB and not okA:
        return th1B, th2B, t3_from(th1B, th2B)
    if okA and okB:
        t3A = t3_from(th1A, th2A)
        t3B = t3_from(th1B, th2B)
        return (th1A, th2A, t3A) if abs(th2A - 45) <= abs(th2B - 45) else (th1B, th2B, t3B)
    # both out of range - clamp nearest
    pick = th2A if abs(th2A - 45) <= abs(th2B - 45) else th2B
    t1p  = th1A if pick == th2A else th1B
    t2p  = float(np.clip(pick, lo, hi))
    return t1p, t2p, t3_from(t1p, t2p)

def azaltroll_to_theta(az, alt, roll):
    if not HAS_NUMPY:
        return None, None, None
    try:
        return _q_to_theta(_azaltroll_to_q(az, alt, roll))
    except Exception:
        return None, None, None


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
    rotator = _sf(h, 'ROTATOR')
    p_roll  = rotator_to_p_roll(rotator) if rotator is not None else None

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
        # Overwriting progress line on stderr (not captured by -log)
        prog = f"  ({idx:04d} of {n_total:04d})  {fp.name:<48s}"
        sys.stderr.write('\r' + prog)
        sys.stderr.flush()

        row = _process_fits(fp, '', lat, lon)
        rows.append(row)
        status_counts[row['status']] += 1

    # Clear the progress line before printing the summary
    sys.stderr.write('\r' + ' ' * 80 + '\r')
    sys.stderr.flush()

    n_solved   = status_counts.get('solved', 0)
    ts         = datetime.now().strftime('%Y-%m-%d %H:%M')
    session_id = f"{ts} N={n_solved}"
    for row in rows:
        row['session_id'] = session_id

    for row in rows:
        st     = row['status']
        p_az_s = f"{float(row['p_az']):>7.2f}" if row['p_az']  != '' else '    N/A'
        p_al_s = f"{float(row['p_alt']):>6.2f}" if row['p_alt'] != '' else '   N/A'
        p_ro_s = f"{float(row['p_roll']):>7.2f}" if row['p_roll'] != '' else '    N/A'
        t_s    = (f"  t2={row['p_theta2']:>6.2f}  t3={row['p_theta3']:>7.2f}"
                  if row['p_theta2'] != '' else '')
        if st == 'solved':
            da_s = f"{float(row['dev_p_az']):>+7.1f}'"   if row['dev_p_az']   != '' else '    N/A'
            dl_s = f"{float(row['dev_p_alt']):>+7.1f}'"  if row['dev_p_alt']  != '' else '    N/A'
            dr_s = f"{float(row['dev_p_roll']):>+7.1f}'" if row['dev_p_roll'] != '' else '    N/A'
            print(f"  OK       {row['filename']:<42s}"
                  f"  p_az={p_az_s}  p_alt={p_al_s}  p_roll={p_ro_s}{t_s}"
                  f"  daz={da_s}  dalt={dl_s}  droll={dr_s}")
        elif st == 'unsolved':
            print(f"  UNSOLVED {row['filename']:<42s}"
                  f"  p_az={p_az_s}  p_alt={p_al_s}  p_roll={p_ro_s}{t_s}")
        else:
            print(f"  {st.upper():<10} {row['filename']}")

    print()
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
        def _st(vals):
            v = [float(x) for x in vals if x != '']
            if not v: return 'N/A'
            a = np.array(v)
            return (f"mean={np.mean(a):+7.1f}'  std={np.std(a):5.1f}'"
                    f"  min={np.min(a):+7.1f}'  max={np.max(a):+7.1f}'")
        print()
        print("---- Raw deviations (arcmin) ----")
        print(f"  dev_p_az  : {_st([r['dev_p_az']   for r in solved])}")
        print(f"  dev_p_alt : {_st([r['dev_p_alt']  for r in solved])}")
        print(f"  dev_p_roll: {_st([r['dev_p_roll'] for r in solved])}")
        t1s    = [float(r['p_theta1']) for r in solved if r['p_theta1'] != '']
        t2s    = [float(r['p_theta2']) for r in solved if r['p_theta2'] != '']
        t3s    = [float(r['p_theta3']) for r in solved if r['p_theta3'] != '']
        azs    = [float(r['p_az'])     for r in solved if r['p_az']     != '']
        alts   = [float(r['p_alt'])    for r in solved if r['p_alt']    != '']
        rolls  = [float(r['p_roll'])   for r in solved if r['p_roll']   != '']
        print()
        print("---- Data coverage ----")
        if t1s:   print(f"  p_theta1 (az)  : {min(t1s):+6.1f} -> {max(t1s):+6.1f} deg | span={max(t1s)-min(t1s):6.1f}")
        if t2s:   print(f"  p_theta2 (alt) : {min(t2s):+6.1f} -> {max(t2s):+6.1f} deg | span={max(t2s)-min(t2s):6.1f}")
        if t3s:   print(f"  p_theta3 (roll): {min(t3s):+6.1f} -> {max(t3s):+6.1f} deg | span={max(t3s)-min(t3s):6.1f}")
        if rolls: print(f"  p_az           : {min(azs):+6.1f} -> {max(azs):+6.1f} deg | span={max(azs)-min(azs):6.1f}")
        if rolls: print(f"  p_alt          : {min(alts):+6.1f} -> {max(alts):+6.1f} deg | span={max(alts)-min(alts):6.1f}")
        if rolls: print(f"  p_roll         : {min(rolls):+6.1f} -> {max(rolls):+6.1f} deg | span={max(rolls)-min(rolls):6.1f}")
    print()


# ---- Load CSV helpers ----------------------------------------------------

# Mapping from old column names (pre-redesign CSVs) to new names
# Mapping from old column names (pre-redesign CSVs) to new names
_OLD_COL_MAP = {
    'theta1':          'p_theta1',
    'theta2':          'p_theta2',
    'theta3':          'p_theta3',
    'solved_az':       's_az',
    'solved_alt':      's_alt',
    'solved_roll':     's_roll',
    'dev_az_arcmin':   'dev_p_az',
    'dev_alt_arcmin':  'dev_p_alt',
    'dev_roll_arcmin': 'dev_p_roll',
    # Note: pa_theta* NOT mapped - s_theta* always recomputed from IK(s_az/alt/roll)
}

def _normalise_row(row):
    """Rename old column names to new schema in-place."""
    for old, new in _OLD_COL_MAP.items():
        if old in row and new not in row:
            row[new] = row[old]
    # Always recompute s_theta* from IK(s_az, s_alt, s_roll).
    # Do NOT use pa_theta* - those were QUEST-corrected predictions, not ground truth.
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

def _load_theta_params(params_path):
    """Load ThetaModelParams from fits_params.json. Returns defaults if absent."""
    p = Path(params_path)
    if p.exists():
        with open(p) as f:
            saved = json.load(f)
        tm = saved.get('theta_model', {})
        return _pm.ThetaModelParams.from_config_values(
            theta_model_a=tm.get('theta_model_a', 0.0),
            theta_model_b=tm.get('theta_model_b', 0.0),
            theta_model_e=tm.get('theta_model_e', 0.0),
            theta_model_f=tm.get('theta_model_f', 0.0),
        ), saved
    return _pm.ThetaModelParams(), {}


def _build_quest_pairs(rows, theta_params):
    """Build (q_base_corrected, q_solved) pairs for QUEST.
    q_solved uses p_roll (not s_roll) so QUEST absorbs frame tilt only,
    not SPA roll bias."""
    pairs = []
    for r in rows:
        try:
            t1     = float(r['p_theta1']); t2 = float(r['p_theta2']); t3 = float(r['p_theta3'])
            s_az   = float(r['s_az']);    s_alt = float(r['s_alt'])
            p_roll = float(r['p_roll'])
        except (ValueError, TypeError):
            continue
        q_base = _pm.theta_to_q(t1, t2, t3)
        if theta_params is not None:
            q_base = _pm.apply_theta_corrections(q_base, theta_params)
        q_sol = _pm.q_from_azaltroll(s_az, s_alt, p_roll)
        pairs.append((q_base, q_sol))
    return pairs


def _fit_alignQ_from_rows(rows, theta_params):
    pairs = _build_quest_pairs(rows, theta_params)
    if len(pairs) < 3:
        return None
    return _pm.quest_solve(pairs)


def _predict_row(row, alignQ, theta_params):
    """Return model prediction dict for one row, or None on error."""
    try:
        t1    = float(row['p_theta1']); t2 = float(row['p_theta2']); t3 = float(row['p_theta3'])
        s_az  = float(row['s_az']);   s_alt = float(row['s_alt']);  s_roll = float(row['s_roll'])
        s_t2  = float(row['s_theta2']); s_t3 = float(row['s_theta3'])
    except (ValueError, TypeError):
        return None

    q_base = _pm.theta_to_q(t1, t2, t3)
    if theta_params is not None:
        q_base = _pm.apply_theta_corrections(q_base, theta_params)
    pa_q = (alignQ * q_base).normalised

    m_az, m_alt, m_roll_raw = _pm.q_to_azaltroll(pa_q)
    m_roll = wrap180(m_roll_raw)
    m_t1, m_t2, m_t3 = _q_to_theta(pa_q)

    try:
        p_t2 = float(row.get('p_theta2', ''))
        p_t3 = float(row.get('p_theta3', ''))
        dev_p_t2 = (s_t2 - p_t2) * 60
        dev_p_t3 = wrap180(s_t3 - p_t3) * 60
    except (ValueError, TypeError):
        dev_p_t2 = float('nan')
        dev_p_t3 = float('nan')

    return {
        'm_az':          m_az,
        'm_alt':         m_alt,
        'm_roll':        m_roll,
        'm_theta1':      m_t1,
        'm_theta2':      m_t2,
        'm_theta3':      m_t3,
        'dev_m_az':      wrap180(s_az  - m_az)  * 60,
        'dev_m_alt':     (s_alt - m_alt)         * 60,
        'dev_m_roll':    wrap180(s_roll - m_roll) * 60,
        'dev_p_theta2':  dev_p_t2,
        'dev_p_theta3':  dev_p_t3,
        'dev_m_theta2':  (s_t2 - m_t2) * 60,
        'dev_m_theta3':  wrap180(s_t3 - m_t3) * 60,
        # aliases for -model fitting
        '_dev_m_theta2': (s_t2 - m_t2) * 60,
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
    if not HAS_PM or not HAS_SCIPY:
        print("ERROR: pointing_model.py and scipy are required for -model.")
        return
    missing = [p for p in csv_paths if not Path(p).exists()]
    if missing:
        for p in missing:
            print(f"ERROR: Input CSV not found: {p}")
        print("       Run -extract first to create the CSV.")
        return

    params_path = Path(params_path)
    theta_params, saved_json = _load_theta_params(params_path)

    if saved_json:
        tm = saved_json.get('theta_model', {})
        print(f"Loaded initial params from {params_path}:")
        print(f"  theta_model_f={tm.get('theta_model_f',0):.4f}  "
              f"theta_model_a={tm.get('theta_model_a',0):.4f}  "
              f"theta_model_b={tm.get('theta_model_b',0):.4f}  "
              f"theta_model_e={tm.get('theta_model_e',0):.4f}")
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

    W = "=" * 66
    print()
    print(W)
    print("  MODEL FITTING")
    print(W)
    print(f"  Sessions  : {n_sessions}")
    print(f"  Total obs : {n_total}")
    print()

    # ---- Fit per-session QUEST ------------------------------------------
    print("---- QUEST alignment (per session, all rows used) ----")
    print()
    session_alignQ   = {}
    all_pred_rows    = []   # (row, pred_dict) for all sessions

    for sid, rows in sorted(sessions.items()):
        alignQ = _fit_alignQ_from_rows(rows, theta_params)
        if alignQ is None:
            print(f"  SKIP {sid}: insufficient data for QUEST (<3 valid rows)")
            continue
        session_alignQ[sid] = alignQ
        w, x, y, z = alignQ.w, alignQ.x, alignQ.y, alignQ.z
        az_ax = alignQ.rotate([0, 0, 1])
        tilt  = math.degrees(math.acos(max(-1.0, min(1.0, az_ax[2]))))
        taz   = math.degrees(math.atan2(az_ax[0], az_ax[1])) % 360
        print(f"  Session : {sid}")
        print(f"  alignQ  w={w:.7f}  x={x:.7f}  y={y:.7f}  z={z:.7f}")
        print(f"  Frame tilt: {tilt*60:.2f}' toward az={taz:.1f} deg"
              f"  (N={len(rows)})")

        preds = [_predict_row(r, alignQ, theta_params) for r in rows]
        valid = [(r, p) for r, p in zip(rows, preds) if p is not None]
        if valid:
            dt2 = np.array([p['_dev_m_theta2'] for _, p in valid])
            da  = np.array([p['dev_m_alt']      for _, p in valid])
            print(f"  dev_m_theta2: {_arr_stats(dt2)}")
            print(f"  dev_m_alt   : {_arr_stats(da)}")
        print()
        all_pred_rows.extend(valid)

    if not all_pred_rows:
        print("ERROR: No valid predictions to fit model from.")
        return

    # Build arrays for fitting
    def _col(key):
        out = []
        for r, p in all_pred_rows:
            try: out.append(float(r[key]))
            except (ValueError, TypeError): out.append(float('nan'))
        return np.array(out)

    def _pcol(key):
        return np.array([float(p[key]) if p and not math.isnan(p[key]) else float('nan')
                         for _, p in all_pred_rows])

    theta2    = _col('p_theta2')
    theta3    = _col('p_theta3')
    p_az      = _col('p_az')
    p_roll    = _col('p_roll')
    az_rad    = np.radians(p_az)
    t3_range  = float(np.nanmax(theta3) - np.nanmin(theta3))
    n         = len(all_pred_rows)

    dev_m_t2  = _pcol('_dev_m_theta2')
    dev_m_t3  = _pcol('_dev_m_theta3')
    dev_m_az  = _pcol('dev_m_az')
    dev_m_alt = _pcol('dev_m_alt')

    dev_p_az   = _col('dev_p_az')
    dev_p_alt  = _col('dev_p_alt')
    dev_p_roll = _col('dev_p_roll')

    # ---- Section A ------------------------------------------------------
    print()
    print(W)
    print("  SECTION A -- POLAR ALIGNMENT (sinusoid vs azimuth)")
    print(W)
    print(f"  N = {n} observations across {n_sessions} session(s)")
    print()
    print("  Fits raw dev_p_* = A*cos(az) + B*sin(az) + C")
    print()

    for label, y in [('dev_p_alt', dev_p_alt), ('dev_p_az', dev_p_az),
                     ('dev_p_roll', dev_p_roll)]:
        res = _fit_sincos(az_rad, y)
        if res is None:
            print(f"  -- {label}: insufficient data"); continue
        print(f"  -- {label}")
        print(f"     Amplitude: {res['amp']:+.2f}'  Phase: {res['phase']:+.1f} deg"
              f"  Offset C: {res['C']:+.2f}'")
        print(f"     R2={res['r2']:.4f}  RMSE={res['rmse']:.2f}'  {_sig(res['pF'])}")
        print()

    # ---- Section B ------------------------------------------------------
    print()
    print(W)
    print("  SECTION B -- THETA-SPACE MECHANICAL MODELS")
    print(W)
    print()

    fitted_f = fitted_a = fitted_b = fitted_e = None

    # B5: theta_model_f  (M3 axis tilt -> altitude, dominant)
    print("  -- B5: M3 axis tilt -> altitude  (theta_model_f)")
    print(f"     Model: dev_m_theta2 = F * theta3")
    print(f"     theta3 range: {np.nanmin(theta3):.1f} -> {np.nanmax(theta3):.1f} deg"
          f"  span={t3_range:.1f}")
    print(f"     corr(theta3, dev_m_theta2) = "
          f"{np.corrcoef(theta3[~np.isnan(dev_m_t2)], dev_m_t2[~np.isnan(dev_m_t2)])[0,1]:+.3f}")
    print()
    if t3_range >= 10:
        k_f, se_f, r2_f = _fit_linear_through_origin(theta3, dev_m_t2)
        if k_f is not None:
            fitted_f = k_f
            tc_f = float(sp_stats.t.ppf(0.975, df=max(n-1,1)))
            print(f"     theta_model_f = {_conf(k_f, se_f, tc_f, ' arcmin/deg')}")
            print(f"     R2={r2_f:.4f}")
            print(f"     At +-50 deg roll: {abs(k_f*50):.1f}' altitude error")
    else:
        print(f"     theta3 span too small for reliable fit (need >= 10 deg).")
    print()

    # B1: theta_model_a/b  (M2 axis tilt -> altitude)
    print("  -- B1: M2 axis tilt -> altitude  (theta_model_a, theta_model_b)")
    print(f"     Model: dev_m_theta2 = A * sin(theta2 - B)  [after removing B5]")
    print()
    y_b1 = dev_m_t2 - (fitted_f * theta3 if fitted_f is not None else 0)
    p0a  = [theta_params.m2_tilt_arcmin or 52., theta_params.m2_tilt_zero_deg or 36.]
    r_b1 = _fit_curve(lambda t, a, b: a * np.sin(np.radians(t - b)), theta2, y_b1, p0a)
    if r_b1 is not None:
        fitted_a, fitted_b = float(r_b1['popt'][0]), float(r_b1['popt'][1])
        print("     theta_model_a = " + _conf(fitted_a, r_b1['perr'][0], r_b1['tc'], "'"))
        print(f"     theta_model_b = {_conf(fitted_b, r_b1['perr'][1], r_b1['tc'], ' deg')}")
        print(f"     R2={r_b1['r2']:.4f}  RMSE={r_b1['rmse']:.2f}'  {_sig(r_b1['pF'])}")
    else:
        print("     FIT FAILED")
    print()

    # B3: theta_model_e  (M3 encoder scale)
    print("  -- B3: M3 encoder scale  (theta_model_e)")
    print(f"     Model: dev_m_theta3 = E * theta3")
    print(f"     theta3 span: {t3_range:.1f} deg  (need >= 30 for reliable fit)")
    print()
    if t3_range >= 30:
        k_e, se_e, r2_e = _fit_linear_through_origin(theta3, dev_m_t3)
        if k_e is not None:
            fitted_e = k_e
            tc_e = float(sp_stats.t.ppf(0.975, df=max(n-1,1)))
            print(f"     theta_model_e = {_conf(k_e, se_e, tc_e, ' arcmin/deg')}")
            print(f"     R2={r2_e:.4f}")
            print()
            print("     NOTE: dev_m_theta3 may be contaminated by SPA roll bias.")
            print("     Collect roll-sweep dataset at fixed az/alt to verify.")
    else:
        print("     Skipped - insufficient theta3 range.")
        print("     Collect images with p_roll from -60 to +60 deg at fixed az/alt.")
    print()

    # ---- Coefficient summary --------------------------------------------
    print()
    print("  " + "-" * 62)
    print("  Fitted coefficients  -->  fits_params.json")
    print("  " + "-" * 62)
    print()
    print(f"  theta_model_f = {fitted_f:.6f}"  if fitted_f is not None
          else "  theta_model_f = 0.000000  (not fitted)")
    print(f"  theta_model_a = {fitted_a:.6f}"  if fitted_a is not None
          else "  theta_model_a = 0.000000  (not fitted)")
    print(f"  theta_model_b = {fitted_b:.6f}"  if fitted_b is not None
          else "  theta_model_b = 0.000000  (not fitted)")
    print(f"  theta_model_e = {fitted_e:.6f}"  if fitted_e is not None
          else "  theta_model_e = 0.000000  (not fitted)")
    print()

    # ---- Section C: RBC diagnostics (read-only) -------------------------
    print()
    print(W)
    print("  SECTION C -- RBC DIAGNOSTICS  (decommissioned)")
    print(W)
    print()
    print("  RBC is decommissioned. theta_model_f corrects the same error")
    print("  in the correct axis. Shown here for reference.")
    print()
    c1 = np.corrcoef(p_roll[~np.isnan(dev_p_alt)],
                     dev_p_alt[~np.isnan(dev_p_alt)])[0,1]
    c2 = np.corrcoef(theta3[~np.isnan(dev_m_alt)],
                     dev_m_alt[~np.isnan(dev_m_alt)])[0,1]
    print(f"  corr(p_roll,  dev_p_alt)  = {c1:+.3f}  (signal RBC tried to model)")
    print(f"  corr(theta3,  dev_m_alt)  = {c2:+.3f}  (residual after QUEST)")
    print()
    if abs(c2) > 0.3:
        print("  >> theta_model_f is not yet applied or insufficient.")
    else:
        print("  >> theta3 -> altitude coupling is well-corrected.")
    print()

    # ---- Section D: roadmap ---------------------------------------------
    print()
    print(W)
    print("  SECTION D -- ROADMAP")
    print(W)
    print()
    print("  1. theta_model_f  [B5 - M3 axis tilt - DOMINANT]")
    if fitted_f is not None:
        print(f"     -> {fitted_f:.4f} arcmin/deg"
              f"  (+-{abs(fitted_f*50):.0f}' at +-50 deg roll)")
        print("     Implement in driver before refitting B1.")
    print()
    print("  2. theta_model_a/b  [B1 - M2 axis tilt]")
    if fitted_a is not None:
        print(f"     -> a={fitted_a:.4f}'  b={fitted_b:.4f} deg")
        print("     Refit after B5 is live in the driver.")
    print()
    print("  3. alignQ per session - already fitted above.")
    print("     Production: 3-6 sync points spread in az, low roll.")
    print()
    print("  4. theta_model_e  [B3 - M3 encoder] - dedicated roll sweep needed.")
    print()
    print("  Re-run -model after implementing corrections to see convergence.")
    print()

    # ---- Save fits_params.json ------------------------------------------
    def _use(fitted, fallback):
        return round(fitted, 6) if fitted is not None else round(fallback, 6)

    theta_model_out = {
        'theta_model_a': _use(fitted_a, theta_params.m2_tilt_arcmin),
        'theta_model_b': _use(fitted_b, theta_params.m2_tilt_zero_deg),
        'theta_model_e': _use(fitted_e, theta_params.m3_encoder_k * 60),
        'theta_model_f': _use(fitted_f, theta_params.m3_axis_tilt_k * 60),
    }
    sessions_out = {}
    for sid, alignQ in session_alignQ.items():
        sessions_out[sid] = {
            'alignQ': [round(alignQ.w, 7), round(alignQ.x, 7),
                       round(alignQ.y, 7), round(alignQ.z, 7)],
            'n_obs':  len(sessions[sid]),
        }
    output = {
        'theta_model':  theta_model_out,
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
    if not HAS_PM:
        print("ERROR: pointing_model.py required for -validate.")
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

    theta_params, saved_json = _load_theta_params(params_path)
    tm = saved_json.get('theta_model', {})
    print("==== VALIDATE ====")
    print(f"Params: {params_path}")
    print(f"  theta_model_f={tm.get('theta_model_f',0):.4f}  "
          f"theta_model_a={tm.get('theta_model_a',0):.4f}  "
          f"theta_model_b={tm.get('theta_model_b',0):.4f}  "
          f"theta_model_e={tm.get('theta_model_e',0):.4f}")
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

        alignQ = _fit_alignQ_from_rows(sync_rows, theta_params)
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
        print(f"  Sync rows used: {n_use_sync} / {len(rows)}")
        print()

        dev_p_2d_all  = []
        dev_m_2d_all  = []
        dev_p_2d_test = []
        dev_m_2d_test = []
        dev_p_t2_list = []
        dev_m_t2_list = []

        for i, row in enumerate(rows):
            pred = _predict_row(row, alignQ, theta_params)
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

        print(f"  Results (all {len(rows)} rows):")
        print(f"    Sky  2D  RMS raw  (dev_p az+alt):  {dp_rms_all:7.2f}'")
        print(f"    Sky  2D  RMS model(dev_m az+alt):  {dm_rms_all:7.2f}'  ({imp_all:+.1f}%)")
        if not math.isnan(rms_p_t2):
            print(f"    Motor t2 RMS raw  (dev_p_theta2): {rms_p_t2:7.2f}'")
            print(f"    Motor t2 RMS model(dev_m_theta2): {rms_m_t2:7.2f}'  ({imp_t2:+.1f}%)")
        if n_test > 0:
            print(f"  Results ({n_test} non-sync rows only):")
            print(f"    Sky 2D raw  : {dp_rms_test:7.2f}'")
            print(f"    Sky 2D model: {dm_rms_test:7.2f}'  ({imp_test:+.1f}%)")
        print()

        session_summary.append({
            'sid': sid, 'n': len(rows), 'n_sync': n_use_sync,
            'dp_all': dp_rms_all, 'dm_all': dm_rms_all, 'imp_all': imp_all,
            'dp_test': dp_rms_test, 'dm_test': dm_rms_test, 'imp_test': imp_test,
        })

    # Write CSV
    output_csv = Path(output_csv)
    with open(output_csv, 'w', newline='') as f:
        w2 = csv.DictWriter(f, fieldnames=_PREDICT_FIELDS, extrasaction='ignore')
        w2.writeheader()
        w2.writerows(output_rows)
    print(f"Wrote {len(output_rows)} rows -> {output_csv}")
    print()

    # Summary table
    print("==== SUMMARY ====")
    print()
    hdr = f"  {'Session':<36}  {'N':>5}  {'Sync':>5}  {'Raw RMS':>8}  {'Mdl RMS':>8}  {'Improv':>7}"
    print(hdr)
    print("  " + "-"*36 + "  " + "-"*5 + "  " + "-"*5 + "  " + "-"*8 + "  " + "-"*8 + "  " + "-"*7)
    all_dp = []; all_dm = []
    for s in session_summary:
        imp_s = f"{s['imp_all']:+.1f}%" if not math.isnan(s['imp_all']) else '   N/A'
        print(f"  {s['sid']:<36}  {s['n']:>5}  {s['n_sync']:>5}"
              f"  {s['dp_all']:>7.2f}'  {s['dm_all']:>7.2f}'  {imp_s:>7}")
        if not math.isnan(s['dp_all']): all_dp.append(s['dp_all'])
        if not math.isnan(s['dm_all']): all_dm.append(s['dm_all'])
    if all_dp:
        mean_dp = sum(all_dp)/len(all_dp)
        mean_dm = sum(all_dm)/len(all_dm)
        ov_imp  = (1 - mean_dm/mean_dp)*100 if mean_dp > 0 else float('nan')
        print("  " + "-"*36 + "  " + "-"*5 + "  " + "-"*5 + "  " + "-"*8 + "  " + "-"*8 + "  " + "-"*7)
        print(f"  {'OVERALL':<36}  {'':>5}  {'':>5}"
              f"  {mean_dp:>7.2f}'  {mean_dm:>7.2f}'  {ov_imp:>+6.1f}%")
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

    # Determine which txt file to open for logging
    if args.extract:  log_path = extract_txt
    elif args.model:  log_path = model_txt
    else:             log_path = validate_txt

    try:
        _log_file_handle = open(log_path, 'w', encoding='utf-8')
        # Inject into this module's namespace so _print() picks it up
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
