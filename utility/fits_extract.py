#!/usr/bin/env python3
"""
fits_extract.py

Calibration utility for the Rotation Bias Correction model in the Alpaca Benro Polaris Driver.

To collect calibration data:
  1. Using Single Point Alignment, capture images across a grid of Alt, Az and
     rotation (roll) positions. Aim for good coverage of the full roll range at
     each Alt/Az combination.
  2. Run ASTAP in batch mode to plate-solve all captured images. ASTAP writes the
     WCS solution back into each FITS header (CRVAL1/2, CROTA2, CD matrix,
     PLTSOLVD=T). The companion .wcs stub files are not used.
  3. Run this script with -extract to read all FITS files and build a CSV, then
     -model to fit the correction coefficients from that CSV.

The script extracts (-extract):
  - Polaris predicted values: CENTAZ, CENTALT, ROTATOR (written by Nina at capture)
  - ASTAP plate-solve values: CRVAL1/2, CROTA2, CD matrix (solved frames only)
  - Derived motor angles: theta1/2/3 (via inverse kinematics from p_az/p_alt/p_roll)
  - Derived deviations: solved − predicted Az/Alt/Roll (solved frames only)
  - Polar-alignment-adjusted fields (pa_*): predicted position with polar misalignment
    and global SPA bias removed, plus residual deviations and motor angles
    expressed in that corrected frame

The polar alignment model fitted during -extract:
  dev_alt  = A·cos(az) + B·sin(az) + C   (polar tilt in altitude + constant offset)
  dev_az   = D·cos(az) + E·sin(az) + F   (polar tilt in azimuth  + encoder offset)
  dev_roll = G·cos(az) + H·sin(az) + I   (polar tilt in roll     + SPA bias)

  Tilt magnitude = sqrt(A²+B²)/60  degrees
  Tilt azimuth   = atan2(B,A)      degrees  (direction of polar axis lean)
  Az encoder offset  = F  arcmin (constant pointing offset in azimuth)
  SPA roll bias      = I  arcmin (global roll offset from Single Point Alignment)

  pa_az / pa_alt / pa_roll  = solved position with polar model subtracted
  pa_dev_az/alt/roll        = pa_* minus p_* (residual after polar correction)
  pa_theta1/2/3             = motor angles derived from pa_az/alt/roll via IK
  pa_dev_theta1/2/3         = pa_theta* minus raw theta* (motor-space residual)

The script models  (-model):
  Fits a Rotation Bias Correction (RBC) model to the plate-solved data. The IMU
  systematically mis-reports camera rotation angle depending on the mechanical
  configuration of the three motor axes. Because the same Az/Alt pointing can
  be reached at different rotation angles (requiring different motor positions),
  this error is configuration-dependent and cannot be corrected by QUEST's
  single rigid-body alignment. The model decomposes the observed pointing error
  into three components:

    [1] Global SPA bias     — a constant roll offset from Single Point Alignment,
                              present uniformly across all positions. Absorbed by
                              QUEST with any sync point.

    [2] Polar misalignment  — an Az-dependent sinusoidal variation caused by the
                              mount's azimuth axis not being perfectly vertical.
                              Absorbed by QUEST with sync points spread across Az.

    [3] Rotation bias       — a roll-dependent residual that QUEST cannot correct
                              because it changes with mechanical configuration.
                              Modelled as:
                                roll_error (arcmin) = (a · tan(alt) + b) · p_roll
                                az_error   (arcmin) =  c · roll_error (arcmin)

  Fitted coefficients:

    rbc_model_a — the geometric projection coefficient for roll error.
    rbc_model_b — the residual roll bias at zero altitude.
    rbc_model_c — the az-coupling coefficient.

Usage:
    python fits_extract.py -extract|-model [-dir DIR] [-csv FILE]

Options:
    -extract         Scan -dir for FITS files and write results to -csv.
    -model           Fit the RBC model from -csv and print coefficients.
    -dir DIR         Directory to scan for FITS files. Default: current directory.
    -csv FILE        CSV file — written by -extract, read by -model.
                     Default: fits_extract.csv

Examples:
    python fits_extract.py -extract
    python fits_extract.py -extract -dir /path/to/fits -csv my_data.csv
    python fits_extract.py -extract -model -csv my_data.csv
    python fits_extract.py -model -csv fits_extract.csv

Dependencies:
    pip install astropy ephem pyquaternion
    pip install numpy scipy          # required for --model and pa_* fields
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
    print("WARNING: pyquaternion/numpy not available — theta1/2/3 and pa_* won't be computed.")
    print("         Run: pip install pyquaternion numpy")

try:
    from scipy.optimize import curve_fit
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("WARNING: scipy not available — pa_* polar-alignment fields won't be computed.")
    print("         Run: pip install scipy")

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
    if abs(cd1_2) < 1e-15 and abs(cd2_2) < 1e-15:
        return None, 'none'
    return wrap_to_180(math.degrees(math.atan2(-cd1_2, cd2_2))), 'CD_matrix'

def crota2_to_roll(crota2_deg, az_deg, alt_deg, lat_deg):
    para = calc_parallactic_angle(az_deg, alt_deg, lat_deg)
    position_angle = wrap_to_360(180 - crota2_deg)
    roll = wrap_to_180(position_angle - para)
    return roll, position_angle, para


# ── Inverse kinematics ────────────────────────────────────────────────────────

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

def azaltroll_to_q(az, alt, roll):
    """Matches driver's azaltroll_to_q()."""
    qaz   = Quaternion(axis=[0, 0, 1], degrees=-az + 90)
    qalt  = Quaternion(axis=[0, 1, 0], degrees=-alt - 90)
    qroll = Quaternion(axis=[0, 0, 1], degrees=roll)
    q1 = qaz * qalt * qroll
    return -(q1.normalised) if roll < 0 else q1.normalised

def q_to_theta(motorQ_C2B, lastPos=None):
    """Matches driver's q_to_theta()."""
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
    if not HAS_QUATERNION:
        return None, None, None
    try:
        motorQ = azaltroll_to_q(p_az, p_alt, p_roll)
        t1, t2, t3 = q_to_theta(motorQ)
        return t1, t2, t3
    except Exception:
        return None, None, None


# ── Polar alignment model ─────────────────────────────────────────────────────

class PolarAlignmentModel:
    """
    Fits and evaluates the sinusoidal polar misalignment + SPA bias model.

    For each of dev_az, dev_alt, dev_roll, the model is:
        dev(az) = A·cos(az) + B·sin(az) + C

    where:
        sqrt(A²+B²) = sinusoidal amplitude (polar tilt projected onto that axis)
        atan2(B,A)  = azimuth of maximum deviation
        C           = constant offset (az encoder error / SPA roll bias)

    After subtracting this model from the solved position, the residuals
    (pa_dev_*) reflect only mechanical errors not captured by a rigid rotation —
    primarily M2 axis tilt and M3 encoder error.
    """

    def __init__(self):
        self.fitted  = False
        self.n_points = 0
        # Sinusoid coefficients [A, B, C] for each channel
        self.coeffs_alt  = None   # dev_alt  = A·cos(az)+B·sin(az)+C  (arcmin)
        self.coeffs_az   = None   # dev_az   = D·cos(az)+E·sin(az)+F  (arcmin)
        self.coeffs_roll = None   # dev_roll = G·cos(az)+H·sin(az)+I  (arcmin)
        # Derived summary values
        self.tilt_magnitude_arcmin = 0.0  # from alt channel
        self.tilt_azimuth_deg      = 0.0  # from alt channel
        self.az_offset_arcmin      = 0.0  # constant az encoder offset (F)
        self.spa_roll_arcmin       = 0.0  # global SPA roll bias (I)

    @staticmethod
    def _sincos(az_rad, A, B, C):
        return A * np.cos(az_rad) + B * np.sin(az_rad) + C

    def fit(self, solved_rows):
        """
        Fit from a list of dicts with keys:
            p_az, dev_az_arcmin, dev_alt_arcmin, dev_roll_arcmin
        Returns True if fit succeeded.
        """
        if not HAS_SCIPY or not HAS_QUATERNION:
            return False
        if len(solved_rows) < 10:
            print(f"  WARNING: Only {len(solved_rows)} solved points — polar model unreliable (need ≥10).")
            return False

        p_az    = np.array([r['p_az']            for r in solved_rows])
        d_alt   = np.array([r['dev_alt_arcmin']   for r in solved_rows])
        d_az    = np.array([r['dev_az_arcmin']    for r in solved_rows])
        d_roll  = np.array([r['dev_roll_arcmin']  for r in solved_rows])
        az_rad  = np.radians(p_az)

        try:
            self.coeffs_alt,  _ = curve_fit(self._sincos, az_rad, d_alt,  maxfev=10000)
            self.coeffs_az,   _ = curve_fit(self._sincos, az_rad, d_az,   maxfev=10000)
            self.coeffs_roll, _ = curve_fit(self._sincos, az_rad, d_roll, maxfev=10000)
        except RuntimeError as e:
            print(f"  WARNING: Polar model fit failed — {e}")
            return False

        A, B, C = self.coeffs_alt
        D, E, F = self.coeffs_az
        G, H, I = self.coeffs_roll

        self.tilt_magnitude_arcmin = math.sqrt(A**2 + B**2)
        self.tilt_azimuth_deg      = math.degrees(math.atan2(B, A))
        self.az_offset_arcmin      = F
        self.spa_roll_arcmin       = I
        self.n_points              = len(solved_rows)
        self.fitted                = True
        return True

    def predict(self, p_az_deg):
        """
        Returns (daz_arcmin, dalt_arcmin, droll_arcmin) — the polar model
        prediction at the given azimuth. These are subtracted from the solved
        position to get the pa_* corrected values.
        """
        if not self.fitted:
            return 0.0, 0.0, 0.0
        az_r = math.radians(p_az_deg)
        dalt  = self._sincos(az_r, *self.coeffs_alt)
        daz   = self._sincos(az_r, *self.coeffs_az)
        droll = self._sincos(az_r, *self.coeffs_roll)
        return daz, dalt, droll

    def print_summary(self):
        if not self.fitted:
            print("  Polar alignment model: NOT FITTED")
            return
        A,B,C = self.coeffs_alt
        D,E,F = self.coeffs_az
        G,H,I = self.coeffs_roll
        print(f"  Polar tilt:     {self.tilt_magnitude_arcmin:>6.1f}'  @ az={self.tilt_azimuth_deg:>6.1f}°"
              f"  (from alt sinusoid, {self.n_points} points)")
        print(f"  Az enc offset:  {self.az_offset_arcmin:>+6.1f}'  (constant az encoder zero error)")
        print(f"  SPA roll bias:  {self.spa_roll_arcmin:>+6.1f}'  (global Single Point Alignment roll offset)")
        print(f"  Alt  sinusoid:  {A:>+7.2f}·cos(az) + {B:>+7.2f}·sin(az) + {C:>+7.2f}  (arcmin)")
        print(f"  Az   sinusoid:  {D:>+7.2f}·cos(az) + {E:>+7.2f}·sin(az) + {F:>+7.2f}  (arcmin)")
        print(f"  Roll sinusoid:  {G:>+7.2f}·cos(az) + {H:>+7.2f}·sin(az) + {I:>+7.2f}  (arcmin)")


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
    # Derived motor angles (from p_az/p_alt/p_roll)
    'theta1', 'theta2', 'theta3',
    # ASTAP solved
    'solved_ra', 'solved_dec', 'solved_pa', 'solved_az', 'solved_alt', 'solved_roll',
    # Raw deviations (solved − predicted)
    'dev_az_arcmin', 'dev_alt_arcmin', 'dev_roll_arcmin',
    # WCS metrics
    'crota2', 'cd1_1', 'cd1_2', 'cd2_1', 'cd2_2',
    'pa_source', 'parallactic_angle', 'pixel_scale_arcsec',
    # Corrected predicted position: p_* + polar model (where mount should point)
    'pa_az', 'pa_alt', 'pa_roll',
    # Residuals: solved_* minus pa_* (ground truth minus corrected prediction)
    'pa_dev_az_arcmin', 'pa_dev_alt_arcmin', 'pa_dev_roll_arcmin',
    # Motor angles from IK(pa_az, pa_alt, pa_roll)
    'pa_theta1', 'pa_theta2', 'pa_theta3',
    # Motor-space residuals: solved_theta* minus pa_theta*
    'pa_dev_theta1_arcmin', 'pa_dev_theta2_arcmin', 'pa_dev_theta3_arcmin',
]


# ── Per-file processing ───────────────────────────────────────────────────────

def process_fits(fits_path):
    """
    Returns (row_dict, status_str).
    pa_* fields are left empty here; they are filled in a second pass
    once the polar model has been fitted to all solved rows.
    """
    row = {'filename': fits_path.name, **{k: '' for k in _ALL_FIELDS if k != 'filename'}}

    try:
        h = read_header(fits_path)
    except Exception as e:
        row['status'] = f'error: {e}'
        return row, row['status']

    # ── Polaris/Nina values ────────────────────────────────────────────────
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

    # ── Theta1/2/3 from p_az/p_alt/p_roll ────────────────────────────────
    if None not in (p_az, p_alt, p_roll):
        t1, t2, t3 = azaltroll_to_theta(p_az, p_alt, p_roll)
        row.update({
            'theta1': f(t1),
            'theta2': f(t2),
            'theta3': f(t3),
        })

    # ── Check solve status ────────────────────────────────────────────────
    solved_flag = h.get('PLTSOLVD', False)
    is_solved = (solved_flag is True or str(solved_flag).strip().upper() == 'T')

    if not is_solved:
        row['status'] = 'unsolved'
        return row, 'unsolved'

    # ── ASTAP solved values ───────────────────────────────────────────────
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

    if crota2 is not None:
        pa_source = 'CROTA2'
    else:
        crota2, pa_source = crota2_from_cd(cd1_2, cd2_2)
    if crota2 is None:
        row['status'] = 'solved-no-rotation'
        return row, 'solved-no-rotation'

    solved_az, solved_alt = radec_to_altaz(solved_ra, solved_dec, lat, lon, date_obs)

    ref_az  = solved_az  if solved_az  is not None else p_az
    ref_alt = solved_alt if solved_alt is not None else p_alt

    solved_roll, solved_pa, parallactic_angle = crota2_to_roll(crota2, ref_az, ref_alt, lat)

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
        # Store the raw solved values for the second-pass pa_* computation
        '_solved_az':   solved_az,
        '_solved_alt':  solved_alt,
        '_solved_roll': solved_roll,
        '_p_az':        p_az,
        '_p_alt':       p_alt,
        '_p_roll':      p_roll,
    })

    return row, 'solved'


def apply_polar_correction(row, polar_model):
    """
    Second pass: fill pa_* fields for a single solved row using the fitted
    polar alignment model.

    The polar model is applied to the PREDICTED position (p_*) to produce a
    corrected prediction (pa_*) that accounts for polar misalignment and SPA bias:

        pa_az/alt/roll  = p_* + polar_model(p_az)
                          i.e. where the mount would point if polar alignment
                          were perfect and SPA bias were zero

        pa_theta1/2/3   = IK(pa_az, pa_alt, pa_roll)
                          motor angles corresponding to the corrected prediction

        pa_dev_*        = solved_* − pa_*
                          residual between plate-solve ground truth and the
                          corrected prediction; reveals mechanical errors
                          (M2 axis tilt, M3 encoder) not captured by polar model

        pa_dev_theta*   = solved_theta* − pa_theta*
                          same residual expressed in motor-angle space
    """
    if not polar_model.fitted:
        return

    solved_az   = row.get('_solved_az')
    solved_alt  = row.get('_solved_alt')
    solved_roll = row.get('_solved_roll')
    p_az        = row.get('_p_az')
    p_alt       = row.get('_p_alt')
    p_roll      = row.get('_p_roll')

    if None in (solved_az, solved_alt, solved_roll, p_az, p_alt, p_roll):
        return

    def f(v, dp=4):
        return round(v, dp) if v is not None else ''

    # Polar model correction (arcmin) at the predicted azimuth
    model_daz, model_dalt, model_droll = polar_model.predict(p_az)

    # Apply polar correction to PREDICTED position → corrected prediction pa_*
    pa_az   = wrap_to_360(p_az   + model_daz   / 60.0)
    pa_alt  =             p_alt  + model_dalt  / 60.0
    pa_roll = wrap_to_180(p_roll + model_droll / 60.0)

    # Residual deviations: solved ground truth minus corrected prediction
    pa_dev_az   = wrap_to_180(solved_az   - pa_az)   * 60.0
    pa_dev_alt  =            (solved_alt  - pa_alt)  * 60.0
    pa_dev_roll = wrap_to_180(solved_roll - pa_roll) * 60.0

    row.update({
        'pa_az':              f(pa_az),
        'pa_alt':             f(pa_alt),
        'pa_roll':            f(pa_roll),
        'pa_dev_az_arcmin':   f(pa_dev_az,   2),
        'pa_dev_alt_arcmin':  f(pa_dev_alt,  2),
        'pa_dev_roll_arcmin': f(pa_dev_roll, 2),
    })

    # IK from corrected prediction → pa_theta*
    if HAS_QUATERNION:
        try:
            pa_t1, pa_t2, pa_t3 = azaltroll_to_theta(pa_az, pa_alt, pa_roll)
            row.update({
                'pa_theta1': f(pa_t1),
                'pa_theta2': f(pa_t2),
                'pa_theta3': f(pa_t3),
            })

            # Motor-space residuals: solved_theta - pa_theta
            # Derive solved motor angles from solved_az/alt/roll
            s_t1, s_t2, s_t3 = azaltroll_to_theta(solved_az, solved_alt, solved_roll)
            if None not in (pa_t1, pa_t2, pa_t3, s_t1, s_t2, s_t3):
                pa_dev_t1 = wrap_to_180(s_t1 - pa_t1) * 60.0
                pa_dev_t2 =            (s_t2 - pa_t2) * 60.0
                pa_dev_t3 = wrap_to_180(s_t3 - pa_t3) * 60.0
                row.update({
                    'pa_dev_theta1_arcmin': f(pa_dev_t1, 2),
                    'pa_dev_theta2_arcmin': f(pa_dev_t2, 2),
                    'pa_dev_theta3_arcmin': f(pa_dev_t3, 2),
                })
        except Exception:
            pass


# ── RBC model fitting ─────────────────────────────────────────────────────────

def fit_rbc_model(csv_path):
    """
    Load the extracted CSV and fit the three-coefficient RBC model.
    """
    try:
        import numpy as np
        from scipy.optimize import curve_fit
        from numpy.linalg import lstsq
    except ImportError:
        print("\nERROR: numpy and scipy are required for --model.")
        print("       Run: pip install numpy scipy")
        return None, None, None

    rows = []
    with open(csv_path, newline='') as f:
        for row in csv.DictReader(f):
            if row['status'] != 'solved':
                continue
            try:
                rows.append({
                    'p_az':           float(row['p_az']),
                    'p_alt':          float(row['p_alt']),
                    'p_roll':         float(row['p_roll']),
                    'dev_az_arcmin':  float(row['dev_az_arcmin']),
                    'dev_alt_arcmin': float(row['dev_alt_arcmin']),
                    'dev_roll_arcmin':float(row['dev_roll_arcmin']),
                })
            except (ValueError, KeyError):
                continue

    if len(rows) < 20:
        print(f"\nERROR: Only {len(rows)} solved rows — need at least 20 for a reliable fit.")
        return None, None, None

    p_az  = np.array([r['p_az']           for r in rows])
    p_alt = np.array([r['p_alt']           for r in rows])
    p_roll= np.array([r['p_roll']          for r in rows])
    d_az  = np.array([r['dev_az_arcmin']   for r in rows])
    d_alt = np.array([r['dev_alt_arcmin']  for r in rows])
    d_roll= np.array([r['dev_roll_arcmin'] for r in rows])
    n     = len(rows)

    def sinusoidal_az(az_deg, amplitude, az0_deg, offset):
        return amplitude * np.cos(np.radians(az_deg - az0_deg)) + offset

    def r_squared(y_actual, y_predicted):
        ss_res = np.sum((y_actual - y_predicted) ** 2)
        ss_tot = np.sum((y_actual - y_actual.mean()) ** 2)
        return 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    print()
    print("═" * 60)
    print("  ROTATION BIAS CORRECTION MODEL FIT")
    print("═" * 60)

    global_mean = d_roll.mean()
    global_std  = d_roll.std()

    print()
    print("── Component 1: Global alignment offset (SPA bias) ─────────")
    print(f"   Mean dev_roll  : {global_mean:+.1f} arcmin  ({global_mean/60:+.3f}°)")
    print(f"   Std  dev_roll  : {global_std:.1f} arcmin")
    print(f"   N (solved)     : {n}")
    print(f"   Interpretation : ~{global_mean/60:.2f}° global roll bias under SPA-only")
    print(f"                    QUEST absorbs this with any sync point")

    p0_roll = [(d_roll.max() - d_roll.min()) / 2, 90.0, d_roll.mean()]
    try:
        popt_az, _ = curve_fit(sinusoidal_az, p_az, d_roll, p0=p0_roll, maxfev=10000)
    except RuntimeError:
        print("\nWARNING: Az sinusoid fit failed to converge.")
        return None, None, None

    roll_az_amplitude, roll_az_az0, roll_az_offset = popt_az
    az_r2 = r_squared(d_roll, sinusoidal_az(p_az, *popt_az))

    p0_alt = [(d_alt.max() - d_alt.min()) / 2, 10.0, d_alt.mean()]
    try:
        popt_alt, _ = curve_fit(sinusoidal_az, p_az, d_alt, p0=p0_alt, maxfev=10000)
        alt_r2 = r_squared(d_alt, sinusoidal_az(p_az, *popt_alt))
        alt_fit_ok = True
    except RuntimeError:
        popt_alt = [0, 0, 0]
        alt_r2 = 0.0
        alt_fit_ok = False

    print()
    print("── Component 2: Az-dependent offset (polar misalignment) ───")
    print(f"   dev_roll sinusoid amplitude : {roll_az_amplitude:+.1f} arcmin  R²={az_r2:.4f}")
    print(f"   dev_roll Az of maximum      : {roll_az_az0:.1f}°")
    if alt_fit_ok:
        print(f"   dev_alt  sinusoid amplitude : {popt_alt[0]:+.1f} arcmin  R²={alt_r2:.4f}")
        print(f"   dev_alt  Az of maximum      : {popt_alt[1]:.1f}°")
        print(f"   Implied polar tilt          : ~{abs(popt_alt[0])/60:.2f}° toward Az≈{popt_alt[1]:.0f}°")
    print(f"   Interpretation              : QUEST absorbs this with multi-point sync")

    d_roll_residual = d_roll - sinusoidal_az(p_az, *popt_az)

    tan_alt     = np.tan(np.radians(p_alt))
    feature_tan = tan_alt * p_roll
    feature_p   = p_roll

    X = np.column_stack([feature_tan, feature_p])
    y = d_roll_residual

    coeffs, _, _, _ = lstsq(X, y, rcond=None)
    rbc_model_a, rbc_model_b = coeffs

    pred_roll = X @ coeffs
    r2_roll   = r_squared(y, pred_roll)
    rmse_roll = np.sqrt(np.mean((y - pred_roll) ** 2))

    print()
    print("── Component 3a: Roll error model (rbc_model_a, rbc_model_b) ──")
    print(f"   Fit on {n} points  R²={r2_roll:.4f}  RMSE={rmse_roll:.1f} arcmin")
    print(f"   roll_error = ({rbc_model_a:.4f}·tan(alt) + {rbc_model_b:.4f}) · p_roll")

    roll_error_pred = (rbc_model_a * tan_alt + rbc_model_b) * p_roll

    p0_daz = [(d_az.max() - d_az.min()) / 2, 90.0, d_az.mean()]
    try:
        popt_daz, _ = curve_fit(sinusoidal_az, p_az, d_az, p0=p0_daz, maxfev=10000)
        d_az_residual = d_az - sinusoidal_az(p_az, *popt_daz)
    except RuntimeError:
        d_az_residual = d_az - d_az.mean()

    rbc_model_c = float(np.dot(roll_error_pred, d_az_residual) /
                        np.dot(roll_error_pred, roll_error_pred))

    az_pred_c = rbc_model_c * roll_error_pred
    r2_az     = r_squared(d_az_residual, az_pred_c)
    rmse_az   = np.sqrt(np.mean((d_az_residual - az_pred_c) ** 2))
    raw_slope, raw_intercept = np.polyfit(d_roll, d_az, 1)

    print()
    print("── Component 3b: Az coupling coefficient (rbc_model_c) ────")
    print(f"   Raw linear fit dev_az vs dev_roll: slope={raw_slope:.4f}  intercept={raw_intercept:.1f}'")
    print(f"   Slope-only fit vs roll_error_pred: rbc_model_c={rbc_model_c:.4f}  R²={r2_az:.4f}  RMSE={rmse_az:.1f}'")

    d_roll_final = d_roll_residual - roll_error_pred
    before_std  = d_roll_residual.std()
    after_std   = d_roll_final.std()
    improvement = 100 * (1 - after_std / before_std)
    corr_before = float(np.corrcoef(d_roll_residual, p_roll)[0, 1])
    corr_after  = float(np.corrcoef(d_roll_final,    p_roll)[0, 1])

    print()
    print("── Validation ───────────────────────────────────────────────")
    print(f"   Correlation p_roll before: {corr_before:+.4f}  →  after: {corr_after:+.4f}")
    print(f"   Std before: {before_std:.1f}'  →  after: {after_std:.1f}'  ({improvement:.1f}% reduction)")

    print()
    print("── Fitted coefficients (copy into driver Config) ────────────")
    print(f"   rbc_model_a = {rbc_model_a:.4f}")
    print(f"   rbc_model_b = {rbc_model_b:.4f}")
    print(f"   rbc_model_c = {rbc_model_c:.4f}")
    print()

    return rbc_model_a, rbc_model_b, rbc_model_c


# ── Main processing ───────────────────────────────────────────────────────────

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
    print(f"ephem: {HAS_EPHEM}  |  quaternion: {HAS_QUATERNION}  |  scipy: {HAS_SCIPY}  |  "
          f"Found {len(fits_files)} FITS files")
    print()

    # ── Pass 1: read every FITS file ──────────────────────────────────────
    rows = []
    status_counts = Counter()
    solved_for_model = []

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
            # Collect data for polar model fit
            try:
                solved_for_model.append({
                    'p_az':            float(row['p_az']),
                    'p_alt':           float(row['p_alt']),
                    'dev_az_arcmin':   float(row['dev_az_arcmin']),
                    'dev_alt_arcmin':  float(row['dev_alt_arcmin']),
                    'dev_roll_arcmin': float(row['dev_roll_arcmin']),
                })
            except (ValueError, TypeError):
                pass
        elif status == 'unsolved':
            print(f"  UNSOLVED {fp.name:<44s}  "
                  f"p_alt={row['p_alt']:>6}  p_roll={row['p_roll']:>7}"
                  f"{t_str}")
        else:
            print(f"  {status.upper():<10} {fp.name}")

    print()

    # ── Pass 2: fit polar model and compute pa_* fields ───────────────────
    polar_model = PolarAlignmentModel()

    if HAS_SCIPY and HAS_QUATERNION and solved_for_model:
        print("── Polar alignment model ─────────────────────────────────────────────")
        fitted = polar_model.fit(solved_for_model)
        if fitted:
            polar_model.print_summary()
            print()
            # Apply pa_* correction to every solved row
            n_pa = 0
            for row in rows:
                if row['status'] == 'solved' and row.get('_solved_az') is not None:
                    apply_polar_correction(row, polar_model)
                    n_pa += 1
            print(f"  Applied pa_* correction to {n_pa} solved rows.")
            print()
    elif not HAS_SCIPY:
        print("  Skipping pa_* fields (scipy not available).")
    elif not solved_for_model:
        print("  Skipping pa_* fields (no solved rows).")

    # Strip internal scratch keys before writing
    _SCRATCH_KEYS = {'_solved_az', '_solved_alt', '_solved_roll', '_p_az', '_p_alt', '_p_roll'}
    clean_rows = [{k: v for k, v in r.items() if k not in _SCRATCH_KEYS} for r in rows]

    # ── Write CSV ─────────────────────────────────────────────────────────
    try:
        with open(output_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=_ALL_FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(clean_rows)
        print(f"Wrote {len(clean_rows)} rows → {output_csv}")
    except PermissionError:
        alt_csv = output_csv.with_stem(output_csv.stem + '_1')
        print(f"ERROR: Permission denied on {output_csv}. Trying: {alt_csv}")
        try:
            with open(alt_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=_ALL_FIELDS, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(clean_rows)
            print(f"Wrote {len(clean_rows)} rows → {alt_csv}")
            output_csv = alt_csv
        except PermissionError as e:
            print(f"ERROR: Could not write to {alt_csv} either: {e}")
            return

    # ── Status summary ────────────────────────────────────────────────────
    print()
    print(f"── Status summary ──────────────────────────────────────────────────")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<22s}: {count}")

    # ── Statistics for solved files ───────────────────────────────────────
    solved_rows = [r for r in clean_rows if r['status'] == 'solved']
    if solved_rows:
        def stats(vals):
            vals = [float(v) for v in vals if v != '']
            if not vals: return 'N/A'
            return (f"mean={sum(vals)/len(vals):+6.1f}  "
                    f"min={min(vals):+6.1f}  max={max(vals):+6.1f}")

        print()
        print(f"── Solved file statistics (arc-minutes) ────────────────────────────")
        print(f"  Raw deviations:")
        print(f"    Roll:       {stats([r['dev_roll_arcmin'] for r in solved_rows])}")
        print(f"    Az:         {stats([r['dev_az_arcmin']   for r in solved_rows])}")
        print(f"    Alt:        {stats([r['dev_alt_arcmin']  for r in solved_rows])}")
        if polar_model.fitted:
            print(f"  Residuals after polar correction, solved_* − pa_* (pa_dev_*):")
            print(f"    Roll:       {stats([r['pa_dev_roll_arcmin'] for r in solved_rows])}")
            print(f"    Az:         {stats([r['pa_dev_az_arcmin']   for r in solved_rows])}")
            print(f"    Alt:        {stats([r['pa_dev_alt_arcmin']  for r in solved_rows])}")
            print(f"  Motor-space residuals, solved_theta − pa_theta (pa_dev_theta*):")
            print(f"    Theta1:     {stats([r['pa_dev_theta1_arcmin'] for r in solved_rows])}")
            print(f"    Theta2:     {stats([r['pa_dev_theta2_arcmin'] for r in solved_rows])}")
            print(f"    Theta3:     {stats([r['pa_dev_theta3_arcmin'] for r in solved_rows])}")

        p_azs   = [float(r['p_az'])    for r in solved_rows if r['p_az']    != '']
        p_alts  = [float(r['p_alt'])   for r in solved_rows if r['p_alt']   != '']
        p_rolls = [float(r['p_roll'])  for r in solved_rows if r['p_roll']  != '']
        t3s     = [float(r['theta3'])  for r in solved_rows if r['theta3']  != '']
        print()
        if p_azs:   print(f"  p_az   (°): {min(p_azs):.1f} → {max(p_azs):.1f}")
        if p_alts:  print(f"  p_alt  (°): {min(p_alts):.1f} → {max(p_alts):.1f}")
        if p_rolls: print(f"  p_roll (°): {min(p_rolls):.1f} → {max(p_rolls):.1f}")
        if t3s:     print(f"  theta3 (°): {min(t3s):.1f} → {max(t3s):.1f}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        prog='fits_extract.py',
        description='Calibration utility for the Alpaca Benro Polaris Driver.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('-extract', action='store_true',
                        help='Scan --dir for FITS files and write results to --csv.')
    parser.add_argument('-model',   action='store_true',
                        help='Fit the RBC model from --csv and print calibration coefficients.')
    parser.add_argument('-dir',  metavar='DIR',  default='../../../images/DSO Lights/Test Data Sky Survey/L/lights',
                        help='Directory to scan recursively for FITS files.')
    parser.add_argument('-csv',  metavar='FILE', default='fits_extract.csv',
                        help='CSV file path.')

    args = parser.parse_args()

    if not args.extract and not args.model:
        parser.error('At least one of -extract or -model is required.')

    if args.extract:
        process_directory(args.dir, args.csv)

    if args.model:
        csv_path = Path(args.csv)
        if not csv_path.is_file():
            parser.error(f'CSV file not found: {csv_path}')
        fit_rbc_model(csv_path)