#!/usr/bin/env python3
"""
fits_extract.py

Reads all FITS files in a directory and extracts data into a CSV for analysis.
Includes both solved and unsolved files — solved files get ASTAP WCS fields,
unsolved files get only the Polaris/Nina predicted values.

ASTAP batch solve writes the WCS solution back into the original FITS
file headers (CRVAL1/2, CROTA2, CD matrix, PLTSOLVD=T). The companion
.wcs files written by batch solve are minimal stubs (NAXIS=0 only) and
are ignored -- all data comes from the .fits files.

The script extracts:
  - Polaris predicted values: CENTAZ, CENTALT, ROTATOR (Nina writes at capture)
  - ASTAP solved values: CRVAL1/2, CROTA2, CD matrix (if solved)
  - Derived: theta1/2/3 (from inverse kinematics on p_az/p_alt/p_roll)
  - Derived: observed Az/Alt/Roll, Az/Alt/Roll deviation (if solved)

Usage:
    python fits_extract.py <fits_directory> [output.csv]

Example:
    python fits_extract.py . D:/Astro/Images/plate_solve_data.csv

Dependencies:
    pip install astropy ephem pyquaternion
"""

import sys
import csv
import math
from pathlib import Path
from collections import Counter

try:
    from astropy.io import fits as astropy_fits
except ImportError:
    print("ERROR: astropy not installed. Run: pip install astropy")
    sys.exit(1)

try:
    import numpy as np
    from pyquaternion import Quaternion
    HAS_QUATERNION = True
except ImportError:
    HAS_QUATERNION = False
    print("WARNING: pyquaternion/numpy not available — theta1/2/3 won't be computed.")
    print("         Run: pip install pyquaternion numpy")

try:
    import ephem
    HAS_EPHEM = True
except ImportError:
    HAS_EPHEM = False
    print("WARNING: ephem not available — solved Az/Alt won't be computed.")
    print("         Run: pip install ephem")

# ── Configuration ─────────────────────────────────────────────────────────────

ROTATOR_OFFSET = 0.0


# ── Angle helpers ─────────────────────────────────────────────────────────────

def wrap_to_180(angle):
    return (angle + 180.0) % 360.0 - 180.0

def wrap_to_360(angle):
    wrapped = angle % 360.0
    return 0.0 if abs(wrapped - 360) < 1e-10 else wrapped

def wrap_to_90(angle):
    return (angle + 90.0) % 180.0 - 90.0

def rotator_to_p_roll(rotator_deg):
    return wrap_to_180(rotator_deg - ROTATOR_OFFSET)

def calc_parallactic_angle(az_deg, alt_deg, lat_deg):
    """Matches driver's calc_parallactic_angle()."""
    if abs(alt_deg - 90.0) < 1e-6:
        return 0.0
    az  = math.radians(az_deg)
    alt = math.radians(alt_deg)
    lat = math.radians(lat_deg)
    num = math.sin(az)
    den = math.tan(lat) * math.cos(alt) - math.sin(alt) * math.cos(az)
    return wrap_to_180(-math.degrees(math.atan2(num, den)))

def radec_to_altaz(ra_deg, dec_deg, lat_deg, lon_deg, date_obs_utc):
    """Convert J2000 RA/Dec to topocentric Alt/Az using ephem."""
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
    """
    Derive field position angle from ASTAP CD matrix.
    ASTAP convention: CD1_1 = -scale*sin(rot), CD2_1 = -scale*cos(rot)
    => position_angle = atan2(-CD1_1, -CD2_1)
    """
    if abs(cd1_2) < 1e-15 and abs(cd2_2) < 1e-15:
        return None, 'none'
    return wrap_to_180(math.degrees(math.atan2(-cd1_2, cd2_2))), 'CD_matrix'

def crota2_to_roll(crota2_deg, az_deg, alt_deg, lat_deg):
    """
    Convert ASTAP CROTA2 to camera roll angle.
    Empirically verified: roll = wrap_to_180(180 - parallactic_angle - CROTA2)
    Returns (roll_deg, parallactic_angle_deg).
    """
    para = calc_parallactic_angle(az_deg, alt_deg, lat_deg)
    position_angle = wrap_to_360(180 - crota2_deg)
    roll = wrap_to_180(position_angle - para)
    return roll, position_angle, para


# ── Inverse kinematics ────────────────────────────────────────────────────────
# Ported directly from control.py — derives theta1/2/3 from p_az/p_alt/p_roll

class LastPosition:
    def __init__(self, t1=180, t2=45, t3=0):
        self.last_theta1 = t1
        self.last_theta2 = t2
        self.last_theta3 = t3
        self.in_gimbal_lock = False

    def calcMechanicalAngularDiff(self, t1, t2, t3):
        def ad(a, b): return ((b - a + 180) % 360) - 180
        return ad(t1, self.last_theta1)**2 + ad(t2, self.last_theta2)**2 + ad(t3, self.last_theta3)**2

    def check_for_gimbal_lock(self, theta2=None):
        if theta2 is None:
            theta2 = self.last_theta2
        if not self.in_gimbal_lock and abs(theta2) < 1:
            self.in_gimbal_lock = True
        elif self.in_gimbal_lock and abs(theta2) > 3:
            self.in_gimbal_lock = False
        return self.in_gimbal_lock

def alpha_to_cameraQ_C2T(az, alt, roll):
    """Matches driver's alpha_to_cameraQ_C2T()."""
    qaz   = Quaternion(axis=[0, 0, 1], degrees=-az + 90)
    qalt  = Quaternion(axis=[0, 1, 0], degrees=-alt - 90)
    qroll = Quaternion(axis=[0, 0, 1], degrees=roll)
    q1 = qaz * qalt * qroll
    return -(q1.normalised) if roll < 0 else q1.normalised

def motorQ_C2B_to_theta(motorQ_C2B, lastPos=None):
    """Matches driver's motorQ_C2B_to_theta()."""
    if lastPos is None:
        lastPos = LastPosition()
    q1     = motorQ_C2B
    tUp    = q1.rotate(np.array([1, 0, 0]))
    tRight = q1.rotate(np.array([0, 1, 0]))

    theta1_A = wrap_to_360(np.degrees(np.arctan2(-tUp[0], -tUp[1])))
    t1r_A    = np.radians(theta1_A)
    sin_t2_A = -(tUp[0] * np.sin(t1r_A) + tUp[1] * np.cos(t1r_A))
    theta2_A = wrap_to_90(np.degrees(np.arctan2(sin_t2_A, tUp[2])))
    theta1_B = wrap_to_360(theta1_A + 180)
    theta2_B = -theta2_A

    theta2_min, theta2_max = -8, 83
    validA = theta2_min <= theta2_A <= theta2_max
    validB = theta2_min <= theta2_B <= theta2_max

    def calc_theta3(theta1, theta2):
        qt1 = Quaternion(axis=[0, 0, 1], degrees=-theta1 + 90)
        qt2 = Quaternion(axis=[0, 1, 0], degrees=-theta2 - 90)
        tRight_no_M3 = (qt1 * qt2).rotate([0, 1, 0])
        r1 = tRight_no_M3 - np.dot(tRight_no_M3, tUp) * tUp
        r2 = tRight        - np.dot(tRight,        tUp) * tUp
        n1, n2 = np.linalg.norm(r1), np.linalg.norm(r2)
        if n1 < 1e-9 or n2 < 1e-9:
            return lastPos.last_theta3
        r1n, r2n = r1 / n1, r2 / n2
        cos_t3 = np.clip(np.dot(r1n, r2n), -1, 1)
        sin_t3 = np.dot(np.cross(r1n, r2n), tUp)
        return wrap_to_180(-np.degrees(np.arctan2(sin_t3, cos_t3)))

    if validA and not validB:
        theta1, theta2 = theta1_A, theta2_A
        theta3 = calc_theta3(theta1, theta2)
    elif validB and not validA:
        theta1, theta2 = theta1_B, theta2_B
        theta3 = calc_theta3(theta1, theta2)
    elif validA and validB:
        theta3_A = calc_theta3(theta1_A, theta2_A)
        theta3_B = calc_theta3(theta1_B, theta2_B)
        diffA = lastPos.calcMechanicalAngularDiff(theta1_A, theta2_A, theta3_A)
        diffB = lastPos.calcMechanicalAngularDiff(theta1_B, theta2_B, theta3_B)
        if diffA <= diffB:
            theta1, theta2, theta3 = theta1_A, theta2_A, theta3_A
        else:
            theta1, theta2, theta3 = theta1_B, theta2_B, theta3_B
    else:
        def dist(t2):
            if t2 < theta2_min: return theta2_min - t2
            if t2 > theta2_max: return t2 - theta2_max
            return 0.0
        if dist(theta2_B) < dist(theta2_A):
            theta1, theta2 = theta1_B, np.clip(theta2_B, theta2_min, theta2_max)
        else:
            theta1, theta2 = theta1_A, np.clip(theta2_A, theta2_min, theta2_max)
        theta3 = calc_theta3(theta1, theta2)

    if lastPos.check_for_gimbal_lock(theta2):
        locked_sum = wrap_to_360(theta1 + theta3)
        theta3 = 0
        theta1 = locked_sum

    return theta1, theta2, theta3

def azaltroll_to_theta(p_az, p_alt, p_roll):
    """
    Derive theta1, theta2, theta3 from p_az, p_alt, p_roll using the same
    inverse kinematics as the driver. When QUEST is off, motorQ == cameraQ
    so alpha_to_cameraQ_C2T gives us motorQ_C2B directly.
    """
    if not HAS_QUATERNION:
        return None, None, None
    try:
        motorQ = alpha_to_cameraQ_C2T(p_az, p_alt, p_roll)
        t1, t2, t3 = motorQ_C2B_to_theta(motorQ)
        return t1, t2, t3
    except Exception:
        return None, None, None


# ── FITS reading ──────────────────────────────────────────────────────────────

def safe_float(header, key, default=None):
    try:
        v = header.get(key, default)
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default

def safe_str(header, key, default=''):
    v = header.get(key, default)
    return str(v).strip() if v is not None else default

def read_header(fits_path):
    with astropy_fits.open(fits_path, memmap=False,
                           ignore_missing_simple=True) as hdul:
        return dict(hdul[0].header)


# ── CSV field order ───────────────────────────────────────────────────────────

_ALL_FIELDS = [
    'filename', 'status', 'date_obs', 'object', 'filter', 'exptime_s',
    'site_lat', 'site_lon',
    # Polaris predicted
    'p_ra', 'p_dec', 'p_az', 'p_alt', 'p_roll', 
    # Derived motor angles
    'theta1', 'theta2', 'theta3',
    # ASTAP solved
    'solved_ra', 'solved_dec', 'solved_pa', 'solved_az', 'solved_alt', 'solved_roll',
    # Deviations
    'dev_az_arcmin', 'dev_alt_arcmin', 'dev_roll_arcmin',
    # WCS metrics
    'crota2', 'cd1_1', 'cd1_2', 'cd2_1', 'cd2_2',
    'pa_source', 'parallactic_angle', 'pixel_scale_arcsec',
]


# ── Per-file processing ───────────────────────────────────────────────────────

def process_fits(fits_path):
    """
    Returns (row_dict, status_str).
    All files included — unsolved files have empty solved/deviation fields.
    """
    # Start with all fields empty
    row = {'filename': fits_path.name, **{k: '' for k in _ALL_FIELDS if k != 'filename'}}

    try:
        h = read_header(fits_path)
    except Exception as e:
        row['status'] = f'error: {e}'
        return row, row['status']

    # ── Polaris/Nina values written at capture time ────────────────────────
    centaz   = safe_float(h, 'CENTAZ')
    centalt  = safe_float(h, 'CENTALT')
    rotator  = safe_float(h, 'ROTATOR')
    nina_ra  = safe_float(h, 'RA')
    nina_dec = safe_float(h, 'DEC')
    lat      = safe_float(h, 'SITELAT',  -33.86)
    lon      = safe_float(h, 'SITELONG', 151.12)
    date_obs = safe_str(h, 'DATE-OBS')

    p_az   = centaz
    p_alt  = centalt
    p_roll = rotator_to_p_roll(rotator) if rotator is not None else None

    def f(v, dp=4):
        return round(v, dp) if v is not None else ''

    # Populate base fields
    row.update({
        'date_obs':    date_obs,
        'object':      safe_str(h, 'OBJECT'),
        'filter':      safe_str(h, 'FILTER'),
        'exptime_s':   safe_float(h, 'EXPTIME'),
        'site_lat':    f(lat),
        'site_lon':    f(lon),
        'p_ra':        f(nina_ra,  6),
        'p_dec':       f(nina_dec, 6),
        'p_az':        f(p_az),
        'p_alt':       f(p_alt),
        'p_roll':      f(p_roll),
    })

    # ── Derive theta1/2/3 from p_az/p_alt/p_roll ──────────────────────────
    if None not in (p_az, p_alt, p_roll):
        t1, t2, t3 = azaltroll_to_theta(p_az, p_alt, p_roll)
        row.update({
            'theta1': f(t1),
            'theta2': f(t2),
            'theta3': f(t3),
        })

    # ── Check solve status ─────────────────────────────────────────────────
    solved_flag = h.get('PLTSOLVD', False)
    is_solved = (solved_flag is True or str(solved_flag).strip().upper() == 'T')

    if not is_solved:
        row['status'] = 'unsolved'
        return row, 'unsolved'

    # ── ASTAP solved values ────────────────────────────────────────────────
    solved_ra  = safe_float(h, 'CRVAL1')
    solved_dec = safe_float(h, 'CRVAL2')
    crota2     = safe_float(h, 'CROTA2')
    cd1_1      = safe_float(h, 'CD1_1', 0.0)
    cd1_2      = safe_float(h, 'CD1_2', 0.0)
    cd2_1      = safe_float(h, 'CD2_1', 0.0)
    cd2_2      = safe_float(h, 'CD2_2', 0.0)
    cdelt2     = safe_float(h, 'CDELT2', 0.0)

    if solved_ra is None or solved_dec is None:
        row['status'] = 'solved-no-wcs'
        return row, 'solved-no-wcs'

    # Use CROTA2 directly if present, fall back to CD matrix derivation
    if crota2 is not None:
        pa_source = 'CROTA2'
    else:
        crota2 = crota2_from_cd(cd1_2, cd2_2)
    if crota2 is None:
        pa_source = 'CD1CD2'
        row['status'] = 'solved-no-rotation'
        return row, 'solved-no-rotation'

    # Convert solved RA/Dec → Alt/Az
    solved_az, solved_alt = radec_to_altaz(solved_ra, solved_dec, lat, lon, date_obs)

    # Use solved az/alt for roll derivation where available
    ref_az  = solved_az  if solved_az  is not None else p_az
    ref_alt = solved_alt if solved_alt is not None else p_alt

    # Observed roll from ASTAP position angle
    solved_roll, solved_pa, parallactic_angle = crota2_to_roll(crota2, ref_az, ref_alt, lat)

    # Deviations (observed - Polaris predicted)
    az_dev   = wrap_to_180(solved_az  - p_az)  if (solved_az  is not None and p_az  is not None) else None
    alt_dev  = (solved_alt - p_alt)             if (solved_alt is not None and p_alt is not None) else None
    roll_dev = wrap_to_180(solved_roll - p_roll)     if p_roll is not None else None

    row.update({
        'status':             'solved',
        'solved_ra':          f(solved_ra,  6),
        'solved_dec':         f(solved_dec, 6),
        'solved_pa':          f(solved_pa),
        'solved_az':          f(solved_az),
        'solved_alt':         f(solved_alt),
        'solved_roll':        f(solved_roll),
        'dev_az_arcmin':      f(az_dev  * 60, 2) if az_dev  is not None else '',
        'dev_alt_arcmin':     f(alt_dev * 60, 2) if alt_dev is not None else '',
        'dev_roll_arcmin':    f(roll_dev * 60, 2) if roll_dev is not None else '',
        'pa_source':          pa_source,
        'crota2':             f(crota2),
        'cd1_1':              f(cd1_1, 8),
        'cd1_2':              f(cd1_2, 8),
        'cd2_1':              f(cd2_1, 8),
        'cd2_2':              f(cd2_2, 8),
        'parallactic_angle':  f(parallactic_angle),
        'pixel_scale_arcsec': f(abs(cdelt2) * 3600 if cdelt2 else None),
    })

    return row, 'solved'


# ── Main ──────────────────────────────────────────────────────────────────────

def process_directory(fits_dir, output_csv):
    fits_dir   = Path(fits_dir)
    output_csv = Path(output_csv)

    fits_files = sorted(
        list(fits_dir.rglob('*.fits')) + list(fits_dir.rglob('*.fit')),
        key=lambda f: f.stat().st_mtime
    )

    if not fits_files:
        print(f"No FITS files found in {fits_dir}")
        return

    print('==== FITS PLATE-SOLVE SOLUTION EXTRACTOR ====')
    print()
    print(f"ephem: {HAS_EPHEM}  |  quaternion: {HAS_QUATERNION}  |  "
          f"Found {len(fits_files)} FITS files")
    print()

    rows = []
    status_counts = Counter()

    for fp in fits_files:
        row, status = process_fits(fp)
        rows.append(row)
        status_counts[status] += 1

        t_str = (f"  t1={row['theta1']:>7}  t2={row['theta2']:>6}  t3={row['theta3']:>7}"
                 if row['theta1'] != '' else '')

        if status == 'solved':
            print(f"  OK      {fp.name:<44s}  "
                  f"p_alt={row['p_alt']:>6}  p_roll={row['p_roll']:>7}"
                  f"{t_str}  "
                  f"roll_err={row['dev_roll_arcmin']:>+7}'"
                  f"  az_err={row['dev_az_arcmin']:>+7}'")
        elif status == 'unsolved':
            print(f"  UNSOLVED {fp.name:<44s}  "
                  f"p_alt={row['p_alt']:>6}  p_roll={row['p_roll']:>7}"
                  f"{t_str}")
        else:
            print(f"  {status.upper():<10} {fp.name}")

    print()

    try:
        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=_ALL_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} rows → {output_csv}")
    except PermissionError:
        alt_csv = output_csv.with_stem(output_csv.stem + '_1')
        print(f"ERROR: Permission denied writing {output_csv} (Is it open in Excel?)")
        print(f"       Trying: {alt_csv}")
        try:
            with open(alt_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=_ALL_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            print(f"Wrote {len(rows)} rows → {alt_csv}")
        except PermissionError as e:
            print(f"ERROR: Could not write to {alt_csv} either: {e}")
            return

    # Status summary
    print()
    print(f"── Status summary ──────────────────────────────────────────────────")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<22s}: {count}")

    # Statistics for solved files only
    solved_rows = [r for r in rows if r['status'] == 'solved']
    if solved_rows:
        def stats(vals):
            vals = [float(v) for v in vals if v != '']
            if not vals: return 'N/A'
            return (f"mean={sum(vals)/len(vals):+6.1f}  "
                    f"min={min(vals):+6.1f}  max={max(vals):+6.1f}")

        print()
        print(f"── Solved file statistics (arc-minutes) ────────────────────────────")
        print(f"  Roll dev:  {stats([r['dev_roll_arcmin'] for r in solved_rows])}")
        print(f"  Az dev:    {stats([r['dev_az_arcmin']   for r in solved_rows])}")
        print(f"  Alt dev:   {stats([r['dev_alt_arcmin']  for r in solved_rows])}")

        p_rolls  = [float(r['p_roll'])  for r in solved_rows if r['p_roll']  != '']
        p_alts   = [float(r['p_alt'])   for r in solved_rows if r['p_alt']   != '']
        t2s      = [float(r['theta2'])  for r in solved_rows if r['theta2']  != '']
        t3s      = [float(r['theta3'])  for r in solved_rows if r['theta3']  != '']

        if p_rolls: print(f"  p_roll (°): {min(p_rolls):.1f} → {max(p_rolls):.1f}")
        if p_alts:  print(f"  p_alt  (°): {min(p_alts):.1f}  → {max(p_alts):.1f}")
        if t2s:     print(f"  theta2 (°): {min(t2s):.1f} → {max(t2s):.1f}")
        if t3s:     print(f"  theta3 (°): {min(t3s):.1f} → {max(t3s):.1f}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    process_directory(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else 'fits_extract.csv'
    )