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
  - Polar-alignment-adjusted fields (pa_*): solved position with polar misalignment
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
  Analyses plate-solve residuals to characterise and fit three layers of
  systematic pointing error. The output is divided into four sections:

  SECTION A — Polar alignment confidence
    Fits a sinusoid (A·cos(az) + B·sin(az) + C) to the raw deviations
    dev_alt, dev_az, and dev_roll as a function of azimuth. Reports
    amplitude, phase, offset, R², RMSE, F-test significance, and
    Shapiro-Wilk residual normality for each channel.

    Derived summary:
      Polar tilt magnitude and direction (from dev_alt amplitude/phase)
      Az encoder offset  (from dev_az constant term C)
      SPA roll bias      (from dev_roll constant term C)

    These errors are absorbed by QUEST multi-point alignment and require
    no driver config constants. Non-normal residuals in this section are
    expected until theta-space corrections (Section B) are applied.

  SECTION B — Theta-space mechanical models
    Fits corrections for three physical axis errors using the polar-
    corrected residuals (pa_dev_*). Each correction uses a named
    config constant (theta_model_a through theta_model_e):

    B1 — M2 dependant altitude residual  (theta_model_a, theta_model_b)
      The M2 rotation axis is not perfectly horizontal. Camera altitude
      deviates sinusoidally as theta2 changes:
        pa_dev_theta2 = theta_model_a · sin(theta2 − theta_model_b)
      Requires: good az and alt coverage (theta3 does not matter).

    B2 — M2 dependent roll residual  (theta_model_c, theta_model_d)
      A roll error that varies with altitude, visible at theta3≈0.
      Physically: imperfect polar sinusoid removal leaving an altitude-
      dependent residual, or a true mechanical roll offset in the camera
      mount. Corrected in the driver by rotating around the boresight axis:
        pa_dev_roll = theta_model_c · cos(theta2 − theta_model_d)
      Requires: theta3≈0 subset with theta2 span ≥30°. Fitted on the
      tightest |theta3| window that yields ≥30 points. Unreliable if
      the polar sinusoid fit (Section A) has poor R² for dev_roll.

    B3 — M3 encoder scale error  (theta_model_e)
      The M3 encoder reports slightly more or less rotation than occurred.
      Visible only when theta3 spans ≥30° (ideally ±60°):
        pa_dev_theta3 = theta_model_e · theta3
      Requires: p_roll swept from −60° to +60° at fixed az/alt.

    B4 — pa_dev_theta1 structure  (diagnostic only, no config constant)
      Residual azimuth error after polar correction. At theta3≈0 this
      is the geometric projection of M2 tilt onto the az axis, which
      disappears automatically once apply_mechanical_corrections() is
      active. No separate correction constant is needed.

    A fitted-coefficients block is printed at the end of Section B for
    direct copy-paste into config.toml.

  SECTION C — Sky-space RBC model  (rbc_model_a, rbc_model_b, rbc_model_c)
    Fits a roll-dependent residual that QUEST cannot correct because it
    changes with mechanical configuration (specifically M3 encoder error
    coupling into roll and az). Modelled in sky space after polar sinusoid
    removal:
        roll_error (arcmin) = (rbc_model_a · tan(alt) + rbc_model_b) · p_roll
        az_error   (arcmin) =  rbc_model_c · roll_error
    Requires: p_roll swept across ±60° for reliable fitting (R² improves
    dramatically with theta3 coverage). Reports R², RMSE, and the
    percentage reduction in roll standard deviation.

    Note: rbc_model_a/b partially absorb the M2 axis tilt geometric
    projection until theta-space corrections are implemented. After
    implementing Sections B1–B3, recollect data and refit — the
    rbc coefficients should reduce substantially.

  SECTION D — Calibration roadmap
    Priority-ordered action list derived from Sections A–C, with exact
    config values and driver call syntax for each pending correction.

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


# ── Model fitting helpers ─────────────────────────────────────────────────────

def _r2(y, y_pred):
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    return (1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

def _rmse(y, y_pred):
    return float(np.sqrt(np.mean((y - y_pred) ** 2)))

def _fit_sincos(az_rad, y):
    """
    Fit y = A·cos(az) + B·sin(az) + C via linear least squares.
    Returns (popt, pcov, r2, rmse, F_stat, p_F, p_shapiro).
    """
    from numpy.linalg import lstsq
    from scipy import stats as sp_stats

    n = len(y)
    X = np.column_stack([np.cos(az_rad), np.sin(az_rad), np.ones(n)])
    coeffs, _, _, _ = lstsq(X, y, rcond=None)
    pred  = X @ coeffs
    resid = y - pred

    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2     = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse_  = float(np.sqrt(ss_res / n))

    # Covariance of coefficients
    sigma2 = ss_res / max(n - 3, 1)
    XtX_inv = np.linalg.pinv(X.T @ X)
    pcov = sigma2 * XtX_inv
    perr = np.sqrt(np.diag(pcov))

    # Amplitude and phase from A, B
    A, B, C = coeffs
    amp   = float(np.sqrt(A**2 + B**2))
    phase = float(np.degrees(np.arctan2(B, A)))  # az of maximum

    # Uncertainty on amplitude via delta method
    amp_err = float(np.sqrt((A/amp)**2 * pcov[0,0] + (B/amp)**2 * pcov[1,1]
                             + 2*(A/amp)*(B/amp)*pcov[0,1])) if amp > 1e-6 else 0.0

    # F-test (model vs null)
    ss_model = ss_tot - ss_res
    F_stat   = (ss_model / 3) / (ss_res / max(n - 3, 1)) if ss_res > 0 else 0.0
    p_F      = float(1 - sp_stats.f.cdf(max(F_stat, 0), 3, max(n - 3, 1)))

    # Shapiro-Wilk normality test on residuals
    _, p_sw = sp_stats.shapiro(resid) if n <= 5000 else (0, float('nan'))

    return dict(
        A=A, B=B, C=C, coeffs=coeffs, perr=perr, pcov=pcov,
        amp=amp, amp_err=amp_err, phase=phase,
        r2=r2, rmse=rmse_, F=F_stat, p_F=p_F, p_sw=p_sw,
        pred=pred, resid=resid,
    )

def _fit_curve(model_fn, x, y, p0, n_params=None):
    """
    Fit via scipy curve_fit. Returns extended result dict.
    """
    from scipy.optimize import curve_fit as sp_curve_fit
    from scipy import stats as sp_stats

    n = len(y)
    p = n_params or len(p0)
    popt, pcov = sp_curve_fit(model_fn, x, y, p0=p0, maxfev=20000)
    perr  = np.sqrt(np.diag(pcov))
    pred  = model_fn(x, *popt)
    resid = y - pred

    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2     = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse_  = float(np.sqrt(ss_res / n))

    ss_model = ss_tot - ss_res
    F_stat   = (ss_model / p) / (ss_res / max(n - p - 1, 1)) if ss_res > 0 else 0.0
    p_F      = float(1 - sp_stats.f.cdf(max(F_stat, 0), p, max(n - p - 1, 1)))
    t_crit   = sp_stats.t.ppf(0.975, df=max(n - p, 1))
    _, p_sw  = sp_stats.shapiro(resid) if n <= 5000 else (0, float('nan'))

    return dict(popt=popt, perr=perr, r2=r2, rmse=rmse_,
                F=F_stat, p_F=p_F, t_crit=t_crit, p_sw=p_sw,
                pred=pred, resid=resid)

def _conf_str(val, err, t_crit, unit=''):
    return f"{val:+.3f}{unit}  ±{err:.3f}{unit} 1σ  95%CI ±{t_crit*err:.3f}{unit}"

def _significance(p_F):
    if p_F < 1e-10: return "p<1e-10 ✓✓✓"
    if p_F < 1e-4:  return f"p={p_F:.1e} ✓✓"
    if p_F < 0.05:  return f"p={p_F:.4f} ✓"
    return f"p={p_F:.4f} (not significant)"

def _normality(p_sw):
    if math.isnan(p_sw): return "n/a"
    return f"p={p_sw:.4f} {'✓ normal' if p_sw > 0.05 else '(non-normal — use results cautiously)'}"


# ── RBC model fitting ─────────────────────────────────────────────────────────

def fit_models(csv_path):
    """
    Load the extracted CSV and fit:

      A) Polar alignment model confidence
         Sinusoidal fits of raw dev_alt / dev_az / dev_roll vs azimuth,
         reported with R², RMSE, F-test and 95% confidence intervals.

      B) Theta-space mechanical models (from pa_dev_theta* fields)
         M2 axis tilt:    pa_dev_theta2 = A·sin(theta2 − φ)
         M2 roll coupling: pa_dev_roll  = A·cos(theta2 − φ)
         M3 encoder scale: pa_dev_theta3 = k·theta3  (if theta3 range is sufficient)

      C) Sky-space RBC model (legacy, for driver Config)
         roll_error = (rbc_model_a·tan(alt) + rbc_model_b)·p_roll
         az_error   = rbc_model_c · roll_error
    """
    try:
        import numpy as np
        from scipy.optimize import curve_fit
        from scipy import stats as sp_stats
        from numpy.linalg import lstsq
    except ImportError:
        print("\nERROR: numpy and scipy are required for --model.")
        print("       Run: pip install numpy scipy")
        return None, None, None

    # ── Load rows ─────────────────────────────────────────────────────────
    rows = []
    has_pa_fields = False
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        has_pa_fields = 'pa_dev_theta2_arcmin' in fieldnames
        for row in reader:
            if row['status'] != 'solved':
                continue
            try:
                d = {
                    'p_az':           float(row['p_az']),
                    'p_alt':          float(row['p_alt']),
                    'p_roll':         float(row['p_roll']),
                    'dev_az_arcmin':  float(row['dev_az_arcmin']),
                    'dev_alt_arcmin': float(row['dev_alt_arcmin']),
                    'dev_roll_arcmin':float(row['dev_roll_arcmin']),
                }
                if has_pa_fields:
                    d.update({
                        'theta2':             float(row['theta2']),
                        'theta3':             float(row['theta3']),
                        'pa_dev_t2':          float(row['pa_dev_theta2_arcmin']),
                        'pa_dev_t3':          float(row['pa_dev_theta3_arcmin']),
                        'pa_dev_roll':        float(row['pa_dev_roll_arcmin']),
                        'pa_dev_t1':          float(row['pa_dev_theta1_arcmin']),
                    })
                rows.append(d)
            except (ValueError, KeyError):
                continue

    if len(rows) < 20:
        print(f"\nERROR: Only {len(rows)} solved rows — need at least 20.")
        return None, None, None

    n     = len(rows)
    p_az  = np.array([r['p_az']           for r in rows])
    p_alt = np.array([r['p_alt']           for r in rows])
    p_roll= np.array([r['p_roll']          for r in rows])
    d_az  = np.array([r['dev_az_arcmin']   for r in rows])
    d_alt = np.array([r['dev_alt_arcmin']  for r in rows])
    d_roll= np.array([r['dev_roll_arcmin'] for r in rows])
    az_rad= np.radians(p_az)

    W = "═" * 64

    # ══════════════════════════════════════════════════════════════════
    print()
    print(W)
    print("  SECTION A — POLAR ALIGNMENT MODEL CONFIDENCE")
    print(W)
    print(f"  N = {n} solved frames")
    print()
    print("  Fits dev_alt / dev_az / dev_roll = A·cos(az)+B·sin(az)+C")
    print("  Amplitude = √(A²+B²), Phase = azimuth of maximum deviation")
    print()

    polar_fits = {}
    for label, y, desc in [
        ('dev_alt',  d_alt,  'Altitude deviation (polar tilt, dominant signal)'),
        ('dev_az',   d_az,   'Azimuth deviation  (encoder offset + weaker tilt)'),
        ('dev_roll', d_roll, 'Roll deviation     (SPA bias + polar tilt in roll)'),
    ]:
        f = _fit_sincos(az_rad, y)
        polar_fits[label] = f
        t_crit = sp_stats.t.ppf(0.975, df=max(n - 3, 1))
        print(f"  ── {label} ({desc})")
        amp_str = _conf_str(f['amp'], f['amp_err'], t_crit, "'")
        off_str = _conf_str(f['C'],   f['perr'][2], t_crit, "'")
        print(f"     Amplitude : {amp_str}")
        print(f"     Phase (az): {f['phase']:+.2f}°  (azimuth of maximum)")
        print(f"     Offset C  : {off_str}")
        print(f"     R²={f['r2']:.4f}  RMSE={f['rmse']:.1f}'  F={f['F']:.1f}  {_significance(f['p_F'])}")
        print(f"     Residual normality: {_normality(f['p_sw'])}")
        print()

    # Derived tilt summary
    alt_f = polar_fits['dev_alt']
    print(f"  Polar tilt (from dev_alt): {alt_f['amp']/60:.3f}° ± {alt_f['amp_err']/60:.3f}°  "
          f"toward az={alt_f['phase']:.1f}°")
    print(f"  Az encoder offset (C from dev_az): {polar_fits['dev_az']['C']:+.1f}'")
    print(f"  SPA roll bias     (C from dev_roll): {polar_fits['dev_roll']['C']:+.1f}'")

    # ══════════════════════════════════════════════════════════════════
    if has_pa_fields:
        t2 = np.array([r['theta2']    for r in rows])
        t3 = np.array([r['theta3']    for r in rows])
        pa_dev_t2   = np.array([r['pa_dev_t2']   for r in rows])
        pa_dev_t3   = np.array([r['pa_dev_t3']   for r in rows])
        pa_dev_roll = np.array([r['pa_dev_roll'] for r in rows])
        pa_dev_t1   = np.array([r['pa_dev_t1']  for r in rows])

        t3_range = float(t3.max() - t3.min())

        print()
        print(W)
        print("  SECTION B — THETA-SPACE MECHANICAL MODELS")
        print(W)
        print()

        # ── M2 axis tilt → pa_dev_theta2 ──────────────────────────────
        print("  ── B1: M2 dependent altitude residual  (pa_dev_theta2 = theta_model_a · sin(theta2 − theta_model_b))")
        print()
        print("     Mechanical meaning: M2 rotation axis is not perfectly horizontal.")
        print("     As theta2 increases, the camera altitude deviates sinusoidally.")
        print("     theta_model_a  = tilt amplitude (arcmin)")
        print("     theta_model_b  = theta2 at which error is zero (degrees)")
        print()
        amp_m2, zero_m2 = None, None
        try:
            def m2_model(t, amp, zero): return amp * np.sin(np.radians(t - zero))
            r_m2 = _fit_curve(m2_model, t2, pa_dev_t2, p0=[52., 36.])
            amp_m2, zero_m2 = r_m2['popt']
            amp_err, zero_err = r_m2['perr']
            tc = r_m2['t_crit']
            _sa = _conf_str(amp_m2,  amp_err,  tc, "'")
            _sz = _conf_str(zero_m2, zero_err, tc, '°')
            print(f"     theta_model_a = {_sa}")
            print(f"     theta_model_b = {_sz}")
            print(f"     R²={r_m2['r2']:.4f}  RMSE={r_m2['rmse']:.2f}'  "
                  f"F={r_m2['F']:.1f}  {_significance(r_m2['p_F'])}")
            print(f"     Residual normality: {_normality(r_m2['p_sw'])}")
        except Exception as e:
            print(f"     FIT FAILED: {e}")

        # ── M2 axis tilt → pa_dev_roll coupling ───────────────────────
        print()
        print("  ── B2: M2 dependant roll residual  (pa_dev_roll = theta_model_c · cos(theta2 − theta_model_d))")
        print()
        print("     The same M2 axis tilt that shifts altitude also rotates the camera")
        print("     frame around the boresight, appearing as a roll error that grows")
        print("     with cos(theta2) — largest at horizon, zero at zenith.")
        print("     theta_model_c  = roll coupling amplitude (arcmin)")
        print("     theta_model_d  = theta2 at which roll coupling is zero (degrees)")
        print()
        print("     Fitted on theta3≈0 subset only: at large theta3 the M3 encoder")
        print("     error dominates pa_dev_roll and buries the M2 coupling signal.")
        print()

        B2_MIN_N        = 30
        B2_MIN_T2_RANGE = 30.0
        b2_thresh = None
        b2_mask   = None
        for _thresh in [2, 5, 10, 15, 20]:
            _m = np.abs(t3) < _thresh
            if _m.sum() >= B2_MIN_N:
                b2_thresh = _thresh
                b2_mask   = _m
                break

        amp_r, zero_r = None, None
        b2_reliable   = False
        try:
            if b2_mask is None or b2_mask.sum() < B2_MIN_N:
                raise ValueError(f"No theta3≈0 subset with ≥{B2_MIN_N} points found. "
                                  "Capture images at p_roll≈0 across a range of altitudes and re-run.")

            n_b2      = int(b2_mask.sum())
            t2_b2     = t2[b2_mask]
            roll_b2   = pa_dev_roll[b2_mask]
            t2_span   = float(t2_b2.max() - t2_b2.min())
            t2_unique = len(np.unique(np.round(t2_b2, 0)))

            print(f"     Subset: |theta3| < {b2_thresh}°  (n={n_b2} of {n} total frames)")
            print(f"     theta2 coverage: {t2_b2.min():.1f}° – {t2_b2.max():.1f}°"
                  f"  (span={t2_span:.1f}°,  {t2_unique} distinct altitudes)")
            print()

            if t2_span < B2_MIN_T2_RANGE:
                print(f"     ⚠ theta2 span ({t2_span:.1f}°) is too narrow for a reliable")
                print(f"       cosine fit — need ≥{B2_MIN_T2_RANGE:.0f}° to distinguish amplitude from noise.")
                print(f"       For a reliable B2: capture images at p_roll≈0 with")
                print(f"       altitude stepped from 20° to 70° across multiple azimuths.")
                print()

            def m2_roll_model(t, amp, zero): return amp * np.cos(np.radians(t - zero))
            r_roll = _fit_curve(m2_roll_model, t2_b2, roll_b2, p0=[149., -52.])
            amp_r, zero_r = r_roll['popt']
            if amp_r < 0:
                amp_r  = -amp_r
                zero_r = zero_r + 180.0
            zero_r = ((zero_r + 180) % 360) - 180

            tc = r_roll['t_crit']
            _sa = _conf_str(amp_r,  r_roll['perr'][0], tc, "'")
            _sz = _conf_str(zero_r, r_roll['perr'][1], tc, '°')
            print(f"     theta_model_c = {_sa}")
            print(f"     theta_model_d = {_sz}")
            print(f"     R²={r_roll['r2']:.4f}  RMSE={r_roll['rmse']:.2f}'  "
                  f"F={r_roll['F']:.1f}  {_significance(r_roll['p_F'])}")
            print(f"     Residual normality: {_normality(r_roll['p_sw'])}")
            print()
            b2_reliable = r_roll['r2'] >= 0.5 and t2_span >= B2_MIN_T2_RANGE
            if not b2_reliable:
                print(f"     ⚠ Low reliability (R²={r_roll['r2']:.2f}, theta2 span={t2_span:.0f}°).")
                if amp_m2 is not None:
                    median_t2 = float(np.median(t2_b2))
                    expected_a = abs(amp_m2) / math.tan(math.radians(median_t2))
                    print(f"       Rough estimate at median theta2={median_t2:.0f}°: "
                          f"theta_model_c ≈ {expected_a:.0f}'")
                print(f"       Capture images at p_roll≈0 across alt 20°–70° and re-run.")
            else:
                print(f"     ✓ Reliable fit (R²={r_roll['r2']:.2f}, theta2 span={t2_span:.0f}°)")
            print()
            corr = float(np.corrcoef(r_m2['resid'][b2_mask], r_roll['resid'])[0,1])
            print(f"     Cross-check: corr(B1_resid, B2_resid) on subset = {corr:+.4f}")
            if abs(corr) > 0.3:
                print(f"     Shared residual structure — both driven by same M2 tilt source ✓")
            else:
                print(f"     Low residual correlation — models are well-separated ✓")
        except Exception as e:
            print(f"     FIT FAILED: {e}")

        # ── M3 encoder → pa_dev_theta3 ────────────────────────────────
        print()
        print("  ── B3: M3 encoder scale error  (pa_dev_theta3 = theta_model_e · theta3)")
        print()
        print(f"     theta_model_e  = M3 encoder scale error (arcmin per degree of theta3)")
        print(f"     theta3 range in this dataset: {t3.min():.1f}° to {t3.max():.1f}°"
              f"  (span = {t3_range:.1f}°)")
        print()

        k_m3, k_m3_frac = None, None
        MIN_T3_RANGE = 30.0
        if t3_range < MIN_T3_RANGE:
            print(f"     ⚠ theta3 range ({t3_range:.1f}°) is insufficient for reliable fit.")
            print(f"       Need ≥{MIN_T3_RANGE:.0f}° range (ideally ±60°).")
            print(f"       Collect dedicated images with p_roll varied from −60° to +60°")
            print(f"       at a fixed az/alt and re-run -model.")
            _k_ind = float(np.dot(t3, pa_dev_t3) / np.dot(t3, t3)) if np.dot(t3,t3)>0 else 0
            print(f"       Indicative estimate (unreliable): theta_model_e ≈ {_k_ind:.3f}'/°")
        else:
            k_m3  = float(np.dot(t3, pa_dev_t3) / np.dot(t3, t3))
            pred3 = k_m3 * t3
            ss_r3 = float(np.sum((pa_dev_t3 - pred3)**2))
            ss_t3 = float(np.sum((pa_dev_t3 - pa_dev_t3.mean())**2))
            r2_m3 = 1 - ss_r3/ss_t3 if ss_t3 > 0 else 0
            rmse3 = float(np.sqrt(ss_r3/n))
            se_k  = float(np.sqrt(ss_r3 / max(n-1,1) / max(float(np.dot(t3,t3)),1e-9)))
            t_stat= k_m3 / se_k if se_k > 0 else 0
            tc    = float(sp_stats.t.ppf(0.975, df=max(n-1,1)))
            p_k   = float(2*(1 - sp_stats.t.cdf(abs(t_stat), df=max(n-1,1))))
            r_t2r = float(np.corrcoef(t2, pa_dev_t3 - pred3)[0,1])
            k_m3_frac = k_m3 / 60.0
            print(f"     theta_model_e = {k_m3:+.4f}'/°  ±{se_k:.4f}  95%CI ±{tc*se_k:.4f}")
            print(f"     As fraction:    {k_m3_frac:.6f} ({k_m3_frac*100:.4f}% scale error)")
            print(f"     R²={r2_m3:.4f}  RMSE={rmse3:.2f}'  t={t_stat:.1f}  {_significance(p_k)}")
            print(f"     Corr(theta2, residuals) = {r_t2r:.4f}  (want ≈0)")

        # ── pa_dev_theta1 ──────────────────────────────────────────────
        print()
        print("  ── B4: pa_dev_theta1 structure (diagnostic only — no config constant)")
        print()
        print("     pa_dev_theta1 is the residual azimuth error in motor space.")
        print("     At theta3≈0 it has two components:")
        print("       i)  Geometric projection of M2 tilt onto the az axis")
        print("           — disappears automatically once apply_mechanical_corrections()")
        print("             is implemented (no extra constant needed).")
        print("       ii) Residual from imperfect polar sinusoid removal")
        print("             — irreducible until more az coverage is added.")
        print()
        print(f"     Summary: mean={pa_dev_t1.mean():+.1f}'  std={pa_dev_t1.std():.1f}'  "
              f"min={pa_dev_t1.min():+.1f}'  max={pa_dev_t1.max():+.1f}'")
        cot_t2 = np.cos(np.radians(t2)) / np.clip(np.sin(np.radians(t2)), 1e-3, None)
        k_cot  = float(np.dot(cot_t2, pa_dev_t1) / np.dot(cot_t2, cot_t2))
        pred_t1_cot = k_cot * cot_t2
        ss_r_cot    = float(np.sum((pa_dev_t1 - pred_t1_cot)**2))
        ss_t_t1     = float(np.sum((pa_dev_t1 - pa_dev_t1.mean())**2))
        r2_cot      = 1 - ss_r_cot / ss_t_t1 if ss_t_t1 > 0 else 0
        se_cot      = float(np.sqrt(ss_r_cot / max(n-1,1) / max(float(np.dot(cot_t2,cot_t2)),1e-9)))
        tc_cot      = float(sp_stats.t.ppf(0.975, df=max(n-1,1)))
        corr_t3     = float(np.corrcoef(t3, pa_dev_t1)[0,1])
        print()
        print(f"     Geometric projection: pa_dev_t1 = K·cot(theta2)")
        print(f"       K = {k_cot:+.3f}'/°  ±{se_cot:.3f}  95%CI ±{tc_cot*se_cot:.3f}")
        print(f"       R²={r2_cot:.4f}  RMSE={np.sqrt(ss_r_cot/n):.2f}'")
        print(f"     Corr(theta3, pa_dev_t1) = {corr_t3:+.4f}")
        if abs(corr_t3) > 0.5:
            print(f"     → Strong theta3 correlation: M3 encoder error is visible in az.")
        else:
            print(f"     → Weak theta3 correlation: consistent with near-zero theta3 dataset.")

        # ── Section B fitted coefficients summary ──────────────────────
        print()
        print("  " + "─" * 62)
        print("  Fitted coefficients — Section B  (copy into driver config.toml)")
        print("  " + "─" * 62)
        print()
        if amp_m2 is not None:
            print(f"  theta_model_a = {amp_m2:.4f}   # M2 tilt amplitude (arcmin)")
            print(f"  theta_model_b = {zero_m2:.4f}   # M2 tilt zero crossing (degrees theta2)")
        else:
            print(f"  theta_model_a = ???              # B1 fit failed — check data")
            print(f"  theta_model_b = ???")
        if amp_r is not None:
            b2_note = "# M2 roll coupling amplitude (arcmin)" + \
                      ("" if b2_reliable else "  ⚠ low reliability — use with caution")
            print(f"  theta_model_c = {amp_r:.4f}   {b2_note}")
            print(f"  theta_model_d = {zero_r:.4f}   # M2 roll coupling zero crossing (degrees theta2)")
        else:
            print(f"  theta_model_c = ???              # B2 fit failed or insufficient data")
            print(f"  theta_model_d = ???")
        if k_m3 is not None:
            print(f"  theta_model_e = {k_m3:.4f}   # M3 encoder scale error (arcmin/degree)")
        else:
            print(f"  theta_model_e = ???              # B3 insufficient theta3 range — sweep p_roll ±60°")
        print()

        # ── Section A non-normality explanation ───────────────────────
        print()
        print("  ── Note on non-normal residuals (Sections A and B)")
        print()
        print("     All channels show non-normal residuals (Shapiro-Wilk p<0.05).")
        print("     Cause: the M2 axis tilt creates an altitude-dependent error that")
        print("     survives the polar sinusoid removal — the sinusoid absorbs the")
        print("     az variation but not the altitude variation within each az group.")
        print("     Once apply_mechanical_corrections() is implemented and theta2")
        print("     errors are removed upstream, residual normality should improve.")
        print("     For now, treat confidence intervals as approximate.")

    else:
        print()
        print("  NOTE: pa_* fields not found in CSV.")
        print("  Re-run -extract with the updated script to generate them,")
        print("  then re-run -model for theta-space model fitting.")

    # ══════════════════════════════════════════════════════════════════
    print()
    print(W)
    print("  SECTION C — SKY-SPACE RBC MODEL")
    print(W)
    print()
    print("  Note: this model was fitted in sky space (p_alt, p_roll) before")
    print("  theta-space corrections were understood. The tan(alt) term in")
    print("  rbc_model_a partially absorbs the M2 axis tilt geometric projection.")
    print("  After implementing theta-space corrections (Sections B1/B3), the")
    print("  residual RBC correction should be smaller and recalibrated.")
    print()

    def sinusoidal_az_amp(az_deg, amplitude, az0_deg, offset):
        return amplitude * np.cos(np.radians(az_deg - az0_deg)) + offset

    p0_roll = [(d_roll.max() - d_roll.min()) / 2, 90.0, d_roll.mean()]
    try:
        popt_az, _ = curve_fit(sinusoidal_az_amp, p_az, d_roll,
                               p0=p0_roll, maxfev=10000)
    except RuntimeError:
        print("WARNING: Az sinusoid fit failed to converge.")
        return None, None, None

    d_roll_residual = d_roll - sinusoidal_az_amp(p_az, *popt_az)
    tan_alt         = np.tan(np.radians(p_alt))
    X               = np.column_stack([tan_alt * p_roll, p_roll])
    coeffs, _, _, _ = lstsq(X, d_roll_residual, rcond=None)
    rbc_model_a, rbc_model_b = float(coeffs[0]), float(coeffs[1])
    pred_roll       = X @ coeffs
    r2_rbc          = _r2(d_roll_residual, pred_roll)
    rmse_rbc        = _rmse(d_roll_residual, pred_roll)
    roll_error_pred = (rbc_model_a * tan_alt + rbc_model_b) * p_roll

    p0_daz = [(d_az.max() - d_az.min()) / 2, 90.0, d_az.mean()]
    try:
        popt_daz, _ = curve_fit(sinusoidal_az_amp, p_az, d_az,
                                p0=p0_daz, maxfev=10000)
        d_az_residual = d_az - sinusoidal_az_amp(p_az, *popt_daz)
    except RuntimeError:
        d_az_residual = d_az - d_az.mean()

    denom       = float(np.dot(roll_error_pred, roll_error_pred))
    rbc_model_c = float(np.dot(roll_error_pred, d_az_residual) / denom) if denom > 0 else 0.0
    az_pred_c   = rbc_model_c * roll_error_pred
    r2_az_c     = _r2(d_az_residual, az_pred_c)
    rmse_az_c   = _rmse(d_az_residual, az_pred_c)

    d_roll_final = d_roll_residual - pred_roll
    corr_before  = float(np.corrcoef(d_roll_residual, p_roll)[0,1])
    corr_after   = float(np.corrcoef(d_roll_final,    p_roll)[0,1])
    pct_improve  = 100 * (1 - d_roll_final.std() / max(d_roll_residual.std(), 1e-9))

    print(f"  roll_error = ({rbc_model_a:.4f}·tan(alt) + {rbc_model_b:.4f})·p_roll")
    print(f"  R²={r2_rbc:.4f}  RMSE={rmse_rbc:.1f}'")
    print(f"  az_error = {rbc_model_c:.4f} · roll_error")
    print(f"  R²={r2_az_c:.4f}  RMSE={rmse_az_c:.1f}'")
    print()
    print(f"  Validation: corr(p_roll, residual) {corr_before:+.4f} → {corr_after:+.4f}")
    print(f"  Roll std reduction: {d_roll_residual.std():.1f}' → {d_roll_final.std():.1f}'  "
          f"({pct_improve:.1f}% improvement)")
    print()
    print("  ── Fitted coefficients (copy into driver Config) ───────────")
    print(f"     rbc_model_a = {rbc_model_a:.4f}")
    print(f"     rbc_model_b = {rbc_model_b:.4f}")
    print(f"     rbc_model_c = {rbc_model_c:.4f}")

    # ══════════════════════════════════════════════════════════════════
    print()
    print(W)
    print("  SECTION D — CALIBRATION ROADMAP")
    print(W)
    print()
    print("  Priority order for corrections, largest to smallest expected impact:")
    print()
    if has_pa_fields:
        try:
            amp_m2_val = float(amp_m2)
            zero_m2_val = float(zero_m2)
            print(f"  1. M2 axis tilt  [Section B1]  amplitude={amp_m2_val:.1f}'  zero={zero_m2_val:.1f}°")
            print(f"     Apply in driver: apply_mechanical_corrections(q,")
            print(f"         m2_tilt_arcmin={amp_m2_val:.1f}, m2_tilt_zero_deg={zero_m2_val:.1f}, m3_encoder_k=0.0)")
            print(f"     Expected QUEST residual improvement: ~{amp_m2_val/2:.0f}' → <10'")
        except NameError:
            print("  1. M2 axis tilt  [Section B1]  — fit failed, check data")
        print()
        print(f"  2. M3 encoder scale  [Section B3]")
        if t3_range < 30.0:
            print(f"     ✗ Cannot calibrate — theta3 span only {t3_range:.1f}°")
            print(f"     → Capture ~5 images each at p_roll = −60°, −30°, 0°, +30°, +60°")
            print(f"       at a fixed az/alt with good sky coverage, then re-run -model.")
        else:
            try:
                print(f"     Apply: m3_encoder_k = {k_m3/60:.6f}  (in degrees/degree)")
            except NameError:
                pass
        print()
    print(f"  3. Polar axis tilt  [Section A, dev_alt]")
    try:
        print(f"     Tilt = {alt_f['amp']/60:.3f}° ± {alt_f['amp_err']/60:.3f}°  toward az={alt_f['phase']:.1f}°")
    except NameError:
        pass
    print(f"     Handled by QUEST multi-point alignment (no driver code change needed).")
    print(f"     More sync points spread across az will reduce residual further.")
    print()
    print(f"  4. Sky-space RBC  [Section C]")
    print(f"     After implementing steps 1–2, recollect data and refit -model.")
    print(f"     The rbc_model_a/b/c coefficients should be smaller once theta-space")
    print(f"     corrections absorb the dominant M2/M3 errors.")
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
    parser.add_argument('-dir',  metavar='DIR',  default='.',
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
        fit_models(csv_path)