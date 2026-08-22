"""
kinematics.py — Production kinematics and correction models for the Benro Polaris driver.

Provides the kinematics, mechanical corrections, and QUEST alignment used
in the real-time driver.  No file I/O, no CSV reading, no analysis helpers.

Contents
--------
  Angle helpers       wrap360/180/90, is_angle_same, angular_error_arcmin, 
                      angular_separation, angular_difference, is_angle_between
  Angle clampers      clamp_arcsec,  clamp_alpha/delta/theta/error/offset/error, 
                      altitude_to_maxroll, wrap_to_nearest, reachable_azaltroll
  3D Vectors          wrap_angle_residual, wrap_state_angles
                      azalt_to_vector, vector_to_az_alt, v_angular_distance
                      calculate_angular_velocity_vector
  Astronomy helpers   calc_parallactic_angle, radec_to_altaz, crota2_from_cd,
                      crota2_to_roll  (used by fits_extract)
  IK / FK             theta_to_q, q_to_theta, q_to_azaltroll, azaltroll_to_q
                      azaltroll_to_theta, azaltroll_to_q, LastPosition
  Mechanical corr.    MountModelParams, apply_mechanical_corrections
  QUEST alignment     quest_solve
"""

import math
import numpy as np
import dataclasses
from quaternion import Q as Quaternion
from dataclasses import dataclass
from typing import List, Optional, Tuple
from scipy.optimize import minimize
import ephem

# ── Angle helpers ─────────────────────────────────────────────────────────────

def wrap360(angle: float) -> float:
    """Wrap angle to [0, 360)."""
    wrapped = angle % 360.0
    # --- Handle a weird rounding problem for tests, ensure 359.9999999994 is 0.0 and not 360
    return 0.0 if abs(wrapped - 360) < 1e-10 else wrapped

def wrap180(angle: float) -> float:
    """Wrap angle to [-180, +180)."""
    return (angle + 180.0) % 360.0 - 180.0

def wrap90(angle: float) -> float:
    """Wrap angle to [-90, +90)."""
    return (angle + 90.0) % 180.0 - 90.0

def is_angle_same(a, b, tolerance=1e-4):
    """Returns True if angles a and b are equivalent within tolerance, accounting for wrapping."""
    return abs((a - b + 180) % 360 - 180) < tolerance

def angular_error_arcmin(az_pred: float, alt_pred: float, az_true: float, alt_true: float) -> float:
    """Great-circle angular separation in arcminutes."""
    az1, az2 = math.radians(az_pred), math.radians(az_true)
    al1, al2 = math.radians(alt_pred), math.radians(alt_true)
    cos_sep = (math.sin(al1) * math.sin(al2) +
               math.cos(al1) * math.cos(al2) * math.cos(az1 - az2))
    cos_sep = max(-1.0, min(1.0, cos_sep))
    return math.degrees(math.acos(cos_sep)) * 60.0

def angular_separation(ra1_hr, dec1_deg, ra2_hr, dec2_deg):
    """
    Computes angular separation between two celestial coordinates using the spherical law of cosines.
    
    Parameters:
        ra1_hr, dec1_deg: RA and Dec of first object (RA in hours, Dec in degrees)
        ra2_hr, dec2_deg: RA and Dec of second object (RA in hours, Dec in degrees)
    
    Returns:
        Angular separation in degrees
    """
    # Convert RA from hours to degrees
    ra1_deg = ra1_hr * 15.0
    ra2_deg = ra2_hr * 15.0

    # Convert all angles to radians
    ra1_rad = math.radians(ra1_deg)
    dec1_rad = math.radians(dec1_deg)
    ra2_rad = math.radians(ra2_deg)
    dec2_rad = math.radians(dec2_deg)

    # Spherical law of cosines
    cos_angle = (math.sin(dec1_rad) * math.sin(dec2_rad) +
                 math.cos(dec1_rad) * math.cos(dec2_rad) * math.cos(ra1_rad - ra2_rad))

    # Clamp to valid range to avoid rounding errors
    cos_angle = min(1.0, max(-1.0, cos_angle))

    # Compute angle in radians and convert to degrees
    angle_rad = math.acos(cos_angle)
    angle_deg = math.degrees(angle_rad)

    return angle_deg

def angular_difference(a, b):
    """
    Compute shortest angular difference from a to b, in degrees.
    Wraps output to [-180°, +180°].
    angular_difference(359, 1)   # → +2
    angular_difference(1, 359)   # → -2
    angular_difference(0, 180)   # → +180
    angular_difference(180, 0)   # → -180

    """
    return ((b - a + 180) % 360) - 180

def is_angle_between(angle: float, min_angle: float, max_angle: float) -> bool:
    diff_to_min = angle - min_angle
    diff_to_max = angle - max_angle
    return diff_to_min >= 0 and diff_to_max <= 0


def calculate_angular_velocity(history, nominal_dt=None, catchup_max_dt=None):
    """
    Computes angular velocity from the first and last entries in a history buffer.
    Each entry must be a list or tuple: [timemonotonic, coalesced, theta1, theta2, theta3],
    where `coalesced` is the number of stale hardware samples collapsed away immediately
    before this entry was dispatched (see Polaris.read_msgs / KalmanFilter.predict) --
    i.e. how many *extra* nominal_dt intervals this entry's own transition actually spans,
    beyond the usual one.

    nominal_dt: if given, the fixed real hardware sample interval (e.g. Polaris' 200ms
    cadence). The dt used is the total number of nominal intervals spanned by the whole
    window -- one per consecutive pair, plus each entry's own coalesced count -- rather
    than the raw wall-clock span between the first and last entries. Wall-clock time
    between entries reflects how the read loop happened to batch/pace its reads, not
    the real per-measurement interval, so a backlog-draining burst that lands some
    entries only ms apart in wall-clock time would otherwise dilute/inflate this
    average (the window's total span shrinks or stretches for reasons unrelated to how
    much the target actually moved). None (default) falls back to the raw wall-clock
    span, e.g. for callers without a known fixed sample cadence or per-entry coalesced
    counts.
    catchup_max_dt: above this raw wall-clock span, assume a genuine outage rather than
    ordinary backlog draining (nothing to attribute to catch-up, since the gap is too
    large to be explained by it) and use the real wall-clock span instead. Ignored if
    nominal_dt is None.

    Returns omega : ndarray
        Angular velocity vector [ω₁, ω₂, ω₃] in degrees per second.
        Returns [0.0, 0.0, 0.0] if input is insufficient or invalid.
    """
    try:
        if history is None or len(history) < 2:
            return np.zeros(3)

        hist_list = list(history)

        # Use first and last entries
        t_start, _, *theta_start = hist_list[0]
        t_end,   _, *theta_end   = hist_list[-1]

        raw_dt = (t_end - t_start)
        if raw_dt <= 0:
            return np.zeros(3)

        if nominal_dt is not None and not (catchup_max_dt is not None and raw_dt > catchup_max_dt):
            # One nominal interval per consecutive pair, plus each entry's own coalesced count.
            intervals = (len(hist_list) - 1) + sum(entry[1] for entry in hist_list[1:])
            dt = intervals * nominal_dt
        else:
            dt = raw_dt

        # Wrap-safe angular velocity
        omega = np.array([
            angular_difference(start, end) / dt
            for start, end in zip(theta_start, theta_end)
        ])
        return omega

    except Exception:
        return np.zeros(3)



# ── Angle clampers ─────────────────────────────────────────────────────────────

def clamparcsec(x):
    try:
        value = float(x) % (360 * 3600)  # Normalize to 0-360 degrees in arc-seconds
        if value > 180 * 3600:
            value -= 360 * 3600  # Adjust to -180 to 180 degrees in arc-seconds
        elif value < -180 * 3600:
            value += 360 * 3600  # Adjust to -180 to 180 degrees in arc-seconds
        return value
    except ValueError:
        return float('nan')

def clamp_alpha(alpha):
    """
    Apply custom bounds to Topo-centric angles alpha[0], alpha[1], alpha[2]:
    - Azimuth ∈ [0, 360)
    - Altitude ∈ [-90, 90)
    - Roll ∈ [-180, 180)
    """
    clamped = np.empty_like(alpha)
    clamped[0] = alpha[0] % 360
    clamped[1] = np.clip(alpha[1], -90, 90)
    clamped[2] = ((alpha[2] + 180) % 360) - 180
    return clamped

def clamp_delta(delta):
    """
    Apply custom bounds to Equatorial angles delta[0], delta[1], delta[2]:
    - Right Ascention ∈ [0, 360)
    - Declination ∈ [-90, 90)
    - Polar Angle ∈ [0, 360)
    """
    clamped = np.empty_like(delta)
    clamped[0] = delta[0] % 360
    clamped[1] = np.clip(delta[1], -90, 90)
    clamped[2] = delta[2] % 360
    return clamped

def clamp_theta(theta):
    """
    Apply custom bounds to Motor Angles theta[0], theta[1], theta[2]:
    - Theta1 ∈ [0, 360)
    - Theta2 ∈ [-90, 90)
    - Theta3 ∈ [-180, 180)
    """
    clamped = np.empty_like(theta)
    clamped[0] = theta[0] % 360
    clamped[1] = np.clip(theta[1], -90, 90)
    clamped[2] = ((theta[2] + 180) % 360) - 180
    return clamped

def clamp_offset(offset):
    """
    Apply custom bounds to Offset Angles offset[0], offset[1], offset[2]:
    - Offset1 ∈ [-180, 180)
    - Offset2 ∈ [-180, 180)
    - Offset3 ∈ [-180, 180)
    """
    clamped = np.empty_like(offset)
    clamped[0] = ((offset[0] + 180) % 360) - 180
    clamped[1] = ((offset[1] + 180) % 360) - 180
    clamped[2] = ((offset[2] + 180) % 360) - 180
    return clamped


def clamp_error(ref, meas):
    """
    Calculates angular error considering wrap-around using modular arithmetic.
    Each error is normalized to [-180, 180) range.
    """
    return ((ref - meas + 180) % 360) - 180

# ── 3D Vector helpers ─────────────────────────────────────────────────────────

def wrap_angle_residual(measured_theta, predicted_theta):
    return np.vectorize(wrap180)(measured_theta - predicted_theta)

def wrap_state_angles(x):
    x_wrapped = x.copy()
    x_wrapped[0, 0] = wrap360(x[0, 0])    # theta1
    x_wrapped[1, 0] = wrap180(x[1, 0])    # theta2
    x_wrapped[2, 0] = wrap180(x[2, 0])    # theta3 
    return x_wrapped

def azalt_to_vector(az_deg, alt_deg):
    az = math.radians(az_deg)
    alt = math.radians(alt_deg)
    x = math.cos(alt) * math.sin(az)
    y = math.cos(alt) * math.cos(az)
    z = math.sin(alt)
    return np.array([x, y, z])

def vector_to_az_alt(vec):
    x, y, z = vec
    az = math.degrees(math.atan2(x, y)) % 360
    alt = math.degrees(math.asin(z / np.linalg.norm(vec)))
    return az, alt

def v_angular_distance(v1, v2):
    """Compute angular separation between two unit vectors in radians."""
    return np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))


def calculate_angular_velocity_vector(q0: Quaternion, q1: Quaternion, dt: float):
    """
    Compute angular velocity vector (rad/sec) from two quaternions over a time interval.
    Args:
        q0 : Quaternion - Initial orientation.
        q1 : Quaternion - Final orientation.
        dt : float - Time interval in seconds.
    Returns:
        omega : np.ndarray, shape (3,) - Angular velocity vector in the frame of q0.
    """
    # Check for no duration
    if dt <= 0:
        return np.zeros(3, dtype=float)

    # Rotation from q0 → q1
    q_delta = q1 * q0.inverse

    # Ensure shortest path
    if q_delta.w < 0:
        q_delta = Quaternion(array=-q_delta.q)

    # Decompose q_delta
    angle_rad = np.radians(q_delta.degrees)
    axis = np.array(q_delta.axis)
    axis_norm = np.linalg.norm(axis)

    # Check for no rotation → zero angular velocity
    if axis_norm < 1e-12 or angle_rad == 0.0:
        return np.zeros(3, dtype=float)

    # Angular velocity ω = axis * (angle / dt)
    omega = axis / axis_norm * (angle_rad / dt)
    return omega


# ── Quaternion helpers ─────────────────────────────────────────────────────────

def quaternion_difference(q_from, q_to):
    """
    Returns:
        angle_deg     : total SO(3) rotation angle (degrees)
        axis          : unit rotation axis (in q_from frame)
        q_delta       : shortest-path relative quaternion
    """
    if np.dot(q_from.q, q_to.q) < 0:     # Enforce shortest path
        q_to = -q_to
    q_delta = (q_from.inverse * q_to).normalised       # Relative rotation
    w = np.clip(q_delta[0], -1.0, 1.0)
    angle_rad = 2.0 * np.arccos(w)
    if angle_rad < 1e-12:
        return 0.0, np.zeros(3), q_delta
    sin_half = np.sqrt(1.0 - w*w)
    axis = q_delta.vector / sin_half
    return np.degrees(angle_rad), axis, q_delta

# ── Astronomy helpers ─────────────────────────────────────────────────────────

def calc_parallactic_angle(az_deg: float, alt_deg: float, lat_deg: float) -> float:
    """Parallactic angle at (az, alt) for observer latitude lat_deg (degrees)."""
    if abs(alt_deg - 90.0) < 1e-6:
        return 0.0
    az  = math.radians(az_deg)
    alt = math.radians(alt_deg)
    lat = math.radians(lat_deg)
    numerator = math.sin(az)
    denominator = math.tan(lat) * math.cos(alt) - math.sin(alt) * math.cos(az)
    angle = math.degrees(math.atan2(numerator, denominator))
    return wrap180(-angle)


def radec_to_altaz(ra_deg: float, dec_deg: float, lat_deg: float, lon_deg: float, date_obs_utc: str):
    """
    Convert J2000 RA/Dec to topocentric Alt/Az using ephem.
    Returns (az_deg, alt_deg) or (None, None) if ephem unavailable or on error.
    """
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

def azalt_to_radec(az_deg: float, alt_deg: float, lat_deg: float, lon_deg: float, date_obs_utc: str):
    """
    Convert topocentric Alt/Az to J2000 RA/Dec using ephem.
    Returns (ra_deg, dec_deg) or (None, None) if ephem unavailable or on error.
    """
    try:
        obs = ephem.Observer()
        obs.lat   = math.radians(lat_deg)
        obs.long  = math.radians(lon_deg)
        obs.epoch = ephem.J2000
        obs.date = ephem.Date(date_obs_utc.split('.')[0].replace('T', ' '))
        ra_rad, dec_rad = obs.radec_of(np.radians(az_deg), np.radians(alt_deg))
        ra_deg = np.degrees(ra_rad)  
        dec_deg = np.degrees(dec_rad)
        return ra_deg, dec_deg
    except Exception:
        return None, None

def delta_to_gamma(delta: np.ndarray) -> np.ndarray:
    """Convert equatorial JNow (ra, dec, pa) to galactic (l, b, gpa)."""

    ra_deg, dec_deg, pa_deg = delta[0], delta[1], delta[2]
    try:
        # Step 1: JNow → J2000
        eq_now = ephem.Equatorial(math.radians(ra_deg), math.radians(dec_deg), epoch=ephem.now())
        eq_j2000 = ephem.Equatorial(eq_now, epoch=ephem.J2000)

        # Step 2: J2000 RA/Dec → Galactic (l, b)
        gal = ephem.Galactic(eq_j2000)
        l_deg = math.degrees(float(gal.lon))
        b_deg = math.degrees(float(gal.lat))

        # Step 3: PA (equatorial) → GPA (galactic)
        # Nudge along galactic latitude to find where galactic north points
        # in equatorial coords, then measure its bearing from our target.
        eps = 1e-4  # degrees
        gal_n     = ephem.Galactic(math.radians(l_deg), math.radians(b_deg + eps), epoch=ephem.J2000)
        eq_n      = ephem.Equatorial(gal_n, epoch=ephem.J2000)
        ra_n_deg  = math.degrees(float(eq_n.ra))
        dec_n_deg = math.degrees(float(eq_n.dec))

        # Bearing of galactic north in the equatorial tangent plane
        d_ra  = wrap180(ra_n_deg - math.degrees(float(eq_j2000.ra))) * math.cos(math.radians(dec_deg))
        d_dec = dec_n_deg - math.degrees(float(eq_j2000.dec))
        gal_north_pa = math.degrees(math.atan2(d_ra, d_dec))
        gpa_deg = wrap180(pa_deg - gal_north_pa)

        return np.array([l_deg, b_deg, gpa_deg])
    except Exception:
        return np.array([None, None, None])

def gamma_to_delta(gamma: np.ndarray) -> np.ndarray:
    """Convert galactic (l, b, gpa) in degrees to equatorial JNow (ra, dec, pa) in degrees."""
    l_deg, b_deg, gpa_deg = gamma[0], gamma[1], gamma[2]
    try:
        # Step 1: Galactic (l, b) → J2000 RA/Dec
        gal = ephem.Galactic(math.radians(l_deg), math.radians(b_deg), epoch=ephem.J2000)
        eq_j2000 = ephem.Equatorial(gal, epoch=ephem.J2000)

        # Step 2: J2000 → JNow
        eq_now = ephem.Equatorial(eq_j2000, epoch=ephem.now())
        ra_deg  = math.degrees(float(eq_now.ra))
        dec_deg = math.degrees(float(eq_now.dec))

        # Step 3: GPA → equatorial PA
        # Nudge along galactic latitude to find galactic north bearing in equatorial frame
        eps = 1e-4
        gal_n    = ephem.Galactic(math.radians(l_deg), math.radians(b_deg + eps), epoch=ephem.J2000)
        eq_n     = ephem.Equatorial(gal_n, epoch=ephem.J2000)
        ra_n_deg  = math.degrees(float(eq_n.ra))
        dec_n_deg = math.degrees(float(eq_n.dec))

        d_ra  = wrap180(ra_n_deg - math.degrees(float(eq_j2000.ra))) * math.cos(math.radians(dec_deg))
        d_dec = dec_n_deg - math.degrees(float(eq_j2000.dec))
        gal_north_pa = math.degrees(math.atan2(d_ra, d_dec))
        pa_deg = wrap180(gpa_deg + gal_north_pa)

        return np.array([ra_deg, dec_deg, pa_deg])
    except Exception:
        return None


def crota2_from_cd(cd1_2: float, cd2_2: float):
    """
    Extract CROTA2 rotation angle (degrees) from WCS CD matrix elements.
    Returns None if both elements are effectively zero.
    """
    if abs(cd1_2) < 1e-15 and abs(cd2_2) < 1e-15:
        return None
    return wrap180(math.degrees(math.atan2(-cd1_2, cd2_2)))


def crota2_to_roll(crota2_deg: float,
                   az_deg: float, alt_deg: float,
                   lat_deg: float):
    """
    Convert CROTA2 WCS rotation to camera roll and parallactic angle.
    Returns (roll_deg, parallactic_angle_deg).
    """
    para           = calc_parallactic_angle(az_deg, alt_deg, lat_deg)
    position_angle = wrap360(180.0 - crota2_deg)
    return wrap180(position_angle - para), para


# ── IK / FK (inverse and forward kinematics) ─────────────────────────────────


def azaltroll_to_q(az, alt, roll):
    """
    Convert altitude, azimuth, and roll angles to a camera quaternion using simple rotation composition.
    Args:
        az: Azimuth angle in degrees (0-360)
        alt: Altitude angle in degrees (-90 to +90)
        roll: Roll angle around boresight (degrees),  (+ve=camera rotates ccw when view from rear, image rotates cw)
    Returns:
        Quaternion: q1 that rotates from camera frame to topocentric frame
    """
    # Reconstructing q1 from az, alt, roll
    qaz = Quaternion(axis=[0, 0, 1], degrees= -az + 90)
    qalt = Quaternion(axis=[0, 1, 0], degrees= -alt - 90)
    qroll = Quaternion(axis=[0, 0, 1], degrees= roll)
    q1 = qaz * qalt * qroll  # Reconstructed quaternion from roll, then alt, then az
    return -(q1.normalised) if roll < 0 else q1.normalised


def theta_to_q(theta1, theta2, theta3):
    """
    Convert theta1, theta2, theta3 angles to a base quaternion using simple rotation composition.
    Args:
        theta1: Polaris Axis 1 angle in degrees [0-360) +ve=cw (looking down towards mount, 0=North)
        theta2: Polaris Axis 2 angle in degrees (-90 to +90) +ve=upwards (looking side on to mount, 0=Horizontal)
        theta3: Polaris Axis 3 angle in degrees (-180 to +180) +ve=cw (looking down towards mount. 0=Level)
    Returns:
        # q1 represents the orientation of the camera in topocentric 3D World space SO(3)
        # there may be multiple motor angle solutions that give rise to this orientation cf elbow up or down.
        # q1 rotates from camera frame (-z = boresight, +x = up, +y = left) to topocentric frame (+z = Zenith, +y = North, +x = East)
    """
    # Reconstructing q1 from theta1, theta2, theta3
    qtheta1 = Quaternion(axis=[0, 0, 1], degrees= -theta1 + 90)                      # Spin camera around vertical
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees= -theta2 - 90)                      # Tilt camera up/down
    qtheta3 = Quaternion(axis=(qtheta1*qtheta2).rotate([1, 0, 0]), degrees= -theta3) # Pan camera left/right
    q = (qtheta3 * qtheta1 * qtheta2).normalised
    noflip = theta3 < 0
    return q if noflip else -q


def theta_to_jacobian(theta1, theta2, theta3):
    """
    Compute the 3x3 Jacobian matrix at the given base frame orientation theta.
    Args:
        theta1: Polaris Axis 1 angle in degrees [0-360) +ve=cw (looking down towards mount, 0=North)
        theta2: Polaris Axis 2 angle in degrees (-90 to +90) +ve=upwards (looking side on to mount, 0=Horizontal)
        theta3: Polaris Axis 3 angle in degrees (-180 to +180) +ve=cw (looking down towards mount. 0=Level)
    Returns
        J : (3,3) ndarray - Jacobian matrix such that ω = J(θ) · θ_dot
    """
    # Rotation quaternions for first two joints
    qtheta1 = Quaternion(axis=[0, 0, 1], degrees=-theta1 + 90)
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees=-theta2 - 90)
    # Joint axes expressed in base frame
    a1 = np.array([0, 0, 1])                      # Joint 1 axis (Z, fixed in base)
    a2 = qtheta1.rotate([0, 1, 0])                # Joint 2 axis (Y after θ1)
    a3 = (qtheta1 * qtheta2).rotate([1, 0, 0])    # Joint 3 axis (X after θ1, θ2)
    # Assemble Jacobian
    J = np.column_stack((a1, a2, a3))
    return -J

class LastPosition:
    def __init__(self, t1=180, t2=45, t3=0, z3=None):
        self.last_theta1 = t1
        self.last_theta2 = t2
        self.last_theta3 = t3
        self.last_zeta3 = z3
        self.in_gimbal_lock = False
        self.flipCW = False             # Alternate solution based on CW: t1+180, t2 -ve, t3-180 or CCW: t1-180, t2 -ve, t3+180
    def update(self,t1,t2,t3):
        self.last_theta1 = t1
        self.last_theta2 = t2
        self.last_theta3 = t3
    def update_zeta(self,zeta):
        if zeta is not None:
            self.last_zeta3 = zeta[2]
    def calcMechanicalAngularDiff(self,t1,t2,t3):
        dt1 = t1 - self.last_theta1
        dt2 = t2 - self.last_theta2
        dt3 = t3 - self.last_theta3
        return dt1*dt1 + dt2*dt2 + dt3*dt3
    def check_for_gimbal_lock(self, theta2=None):
        if theta2 is None:
            theta2 = self.last_theta2
        # check new theta2 for potential gimbal lock, with hysteresis to eliminate chatter at boundary
        GIMBAL_ENTER = 1  
        GIMBAL_EXIT  = 3          
        if not self.in_gimbal_lock and abs(theta2) < GIMBAL_ENTER:
            self.in_gimbal_lock = True
        elif self.in_gimbal_lock and abs(theta2) > GIMBAL_EXIT:
            self.in_gimbal_lock = False
        return self.in_gimbal_lock
    def get_fallback_theta3(self):
        if self.last_zeta3 is not None:
            return self.last_zeta3  # more reliable that theta3, not subject to gimbal lock
        return self.last_theta3     # fallback if no zeta3
    def unwrap(self,t1,t2,t3):
        N1 = round((self.last_theta1 - t1) / 360)
        N3 = round((self.last_theta3 - t3) / 360)
        return t1 + N1 * 360, t2, t3 + N3 * 360

def q_to_theta(motorQ_C2B, lastPos=LastPosition()):
    """Convert a motor quaternion (C2B frame) into joint angles (θ), using the previous
       position as a reference to resolve ambiguity and ensure continuity."""
    q1 = motorQ_C2B
    
    # tUp invariant under theta3
    tUp = q1.rotate(np.array([1, 0, 0]))
    tRight = q1.rotate(np.array([0, 1, 0]))

    def calc_theta3(theta1, theta2):
        qt1 = Quaternion(axis=[0,0,1], degrees=-theta1+90)
        qt2 = Quaternion(axis=[0,1,0], degrees=-theta2-90)
        tRight_no_M3 = (qt1 * qt2).rotate([0, 1, 0])
        r1 = tRight_no_M3 - np.dot(tRight_no_M3, tUp) * tUp
        r2 = tRight       - np.dot(tRight,       tUp) * tUp
        n1, n2 = np.linalg.norm(r1), np.linalg.norm(r2)
        if n1 < 1e-9 or n2 < 1e-9:  # hard lock, t3 and t1 axis parallel
            return lastPos.get_fallback_theta3()
        r1n, r2n = r1/n1, r2/n2
        cos_t3 = np.clip(np.dot(r1n, r2n), -1, 1)
        sin_t3 = np.dot(np.cross(r1n, r2n), tUp)
        return -np.degrees(np.arctan2(sin_t3, cos_t3))

    # Primary solution
    t1r_A = np.arctan2(-tUp[0], -tUp[1])
    sin_t2_A = -(tUp[0]*np.sin(t1r_A) + tUp[1]*np.cos(t1r_A))
    cos_t2_A = tUp[2]
    t2r_A = np.arctan2(sin_t2_A, cos_t2_A)
    theta1_A, theta2_A = np.degrees(t1r_A), np.degrees(t2r_A)
    theta3_A = calc_theta3(theta1_A, theta2_A)
    thetaA = lastPos.unwrap(theta1_A, theta2_A, theta3_A)

    # Alternative solution with M1/M3 fliped 180, and M2 -ve
    if lastPos.flipCW:
        theta1_B, theta2_B, theta3_B = theta1_A + 180, -theta2_A, theta3_A - 180
    else:
        theta1_B, theta2_B, theta3_B = theta1_A - 180, -theta2_A, theta3_A + 180
    thetaB = lastPos.unwrap(theta1_B, theta2_B, theta3_B)

    # Validity
    theta2_min, theta2_max = -8, 83
    validA = theta2_min <= theta2_A <= theta2_max
    validB = theta2_min <= theta2_B <= theta2_max

    if validA and not validB:
        theta1, theta2, theta3 = thetaA

    elif validB and not validA:
        theta1, theta2, theta3 = thetaB

    elif validA and validB:
        # Both valid — compute theta3 for each and use full 3D lastPos comparison
        diffA = lastPos.calcMechanicalAngularDiff(*thetaA)
        diffB = lastPos.calcMechanicalAngularDiff(*thetaB)
        if diffA <= diffB:
            theta1, theta2, theta3 = thetaA
        else:
            theta1, theta2, theta3 = thetaB

    else:
        # Neither valid — clamp closest
        def dist(t2):
            if t2 < theta2_min: return theta2_min - t2
            if t2 > theta2_max: return t2 - theta2_max
            return 0.0
        if dist(theta2_B) < dist(theta2_A):
            theta1, theta2 = theta1_B, np.clip(theta2_B, theta2_min, theta2_max)
        else:
            theta1, theta2 = theta1_A, np.clip(theta2_A, theta2_min, theta2_max)
        theta1, theta2, theta3 = lastPos.unwrap(theta1, theta2, calc_theta3(theta1, theta2))

    # Gimbal lock
    in_gimbal_lock = lastPos.check_for_gimbal_lock(theta2)
    if in_gimbal_lock:
        locked_sum = theta1 + theta3
        theta3 = lastPos.get_fallback_theta3()
        theta1 = locked_sum - theta3

    return float(theta1), float(theta2), float(theta3)



def q_to_azaltroll(cameraQ_C2T):
    """Convert a camera quaternion (C2T frame) into azimuth, altitude, and roll angles."""
    # Rotate Camera Boresight Unit Vector to Topocentric Reference Frame
    tBore = cameraQ_C2T.rotate([0, 0, -1])

    # Azimuth and Altitude: rotation around unadjusted bore vector ie Topocentric co-ordinates including effect of Axis 3
    az = np.degrees(np.arctan2(tBore[0], tBore[1]))                     # Azimuth = Boresight axis projected on N/E plane
    alt = np.degrees(np.arcsin(np.clip(tBore[2], -1, 1)))               # Altitude = Angle from N/E plane, vertically to the Boresight axis

    # Roll Angle: Reconstruct the zero-roll quaternion using the same forward chain (roll=0)
    qaz   = Quaternion(axis=[0, 0, 1], degrees=-az + 90)
    qalt  = Quaternion(axis=[0, 1, 0], degrees=-alt - 90)
    q_no_roll = qaz * qalt          # What the quaternion would be with roll=0

    # The roll is the residual rotation between q_no_roll and the actual quaternion.
    # q_no_roll * qroll = cameraQ_C2T  =>  qroll = q_no_roll.inverse * cameraQ_C2T
    # But we must account for the double-cover sign ambiguity first, to ensure both q's are in same 4D hemisphere.
    q_actual = cameraQ_C2T
    if (q_no_roll * q_actual.inverse).scalar < 0:
        q_actual = -q_actual
    q_roll_residual = q_no_roll.inverse * q_actual

    # Extract the roll angle from the residual quaternion (axis should be ≈ [0,0,1])
    roll = np.degrees(2 * np.arctan2(
        np.linalg.norm([q_roll_residual[1], q_roll_residual[2], q_roll_residual[3]]),
        q_roll_residual[0]
    ))

    # Determine sign: if residual axis points in -Z direction, negate the angle
    if q_roll_residual[3] < 0:
        roll = -roll

    return wrap360(az), wrap180(alt), wrap180(roll)

def azaltroll_to_theta(p_az: float, p_alt: float, p_roll: float,
                       lastPos: Optional[LastPosition] = None):
    """Az/alt/roll (degrees) -> (theta1, theta2, theta3) via IK. Returns (None,None,None) on error."""
    try:
        motorQ = azaltroll_to_q(p_az, p_alt, p_roll)
        return q_to_theta(motorQ, lastPos)
    except Exception:
        return None, None, None


def theta_to_azaltroll(theta1: float, theta2: float, theta3: float):
    """theta1, theta2, theta3 (degrees) -> (az,alt,roll) via FK. Returns (None,None,None) on error."""
    try:
        motorQ = theta_to_q(theta1, theta2, theta3)
        return q_to_azaltroll(motorQ)
    except Exception:
        return None, None, None

def altitude_to_maxroll(alt_deg, theta2_max=81.5):
    """
    Maximum achievable camera roll at a given sky altitude.
    
    Derived from spherical geometry: as t3 varies at fixed t2_max,
    the boresight traces a great circle. At the point where altitude
    equals alt_deg, the roll satisfies:
    
        cos(roll) = cos(t2_max) / cos(alt)
    
    Returns 0 if altitude is outside the reachable range.
    """
    cos_ratio = np.cos(np.radians(theta2_max)) / np.cos(np.radians(alt_deg))
    if abs(cos_ratio) > 1:
        return 0.0
    return np.degrees(np.arccos(cos_ratio))

THETA2_MAX = 81.5  # hard mechanical limit for both alt and roll axes

def wrap_to_nearest(angle: float, target: float = 0.0) -> float:
    """Wrap angle to the value nearest to target, in steps of 360."""
    diff = angle - target
    diff = diff - 360 * round(diff / 360)
    return target + diff


def reachable_azaltroll(az: float, alt: float, roll: float, roll_adj: float = 0.0) -> tuple[float, float, float]:
    """
    Map any (az, alt, roll) to a mechanically reachable (az, alt, roll).

    Priority: reach the requested Az/Alt first, then best-effort on Roll.

    Alt handling
    ------------
    Normalise alt to the range (-180, 180] via wrap_to_nearest.
    If the result is in (-90, 90) it is directly reachable.
    If |alt| > 90 the boresight has gone 'over the top'; flip to the
    equivalent pointing: alt' = 180 - alt (or -180 - alt), az' = az + 180,
    and accumulate a 180° roll flip.

    Roll handling
    -------------
    Normalise roll (including any flip from the alt stage) to (-180, 180].
    The maximum achievable roll at the resolved altitude is altitude_to_maxroll(alt').
    If |roll| <= max_roll  → use roll as-is.
    If |roll| >  max_roll  → try the 180° equivalent (roll - 180 or roll + 180);
                             if still unreachable, clamp to ±max_roll.

    Returns
    -------
    az  : float  0 – 360
    alt : float  -THETA2_MAX – +THETA2_MAX
    roll: float  -max_roll   – +max_roll
    """

    # Normalise alt to (-180, 180] 
    alt_norm = wrap_to_nearest(alt, target=0.0)   # brings to (-180, 180]

    # Resolve over-the-top alt by flipping through the pole 
    roll_flip = 0.0

    if alt_norm > THETA2_MAX:
        # e.g. alt=120 → alt'=60, az+=180, roll+=180
        alt_resolved = 180.0 - alt_norm
        az += 180.0
        roll_flip += 180.0
    elif alt_norm < -THETA2_MAX:
        # e.g. alt=-120 → alt'=-60, az+=180, roll+=180
        alt_resolved = -180.0 - alt_norm
        az += 180.0
        roll_flip += 180.0
    else:
        alt_resolved = alt_norm

    # Safety clamp — should not be needed after the flip, but be defensive
    alt_resolved = float(np.clip(alt_resolved, -THETA2_MAX, THETA2_MAX))

    # Normalise az to [0, 360)
    az_resolved = az % 360.0

    # Compute the roll limit at the resolved altitude
    max_roll = altitude_to_maxroll(alt_resolved, THETA2_MAX)

    # Resolve mechanical roll angle
    roll_total = wrap_to_nearest(roll + roll_flip - roll_adj, target=0.0)

    if abs(roll_total) <= max_roll:
        roll_resolved_mech = roll_total
    else:
        # Try the upside-down equivalent: rotate 180° around boresight
        sign = 1.0 if roll_total >= 0 else -1.0
        roll_flipped = roll_total - sign * 180.0
        if abs(roll_flipped) <= max_roll:
            roll_resolved_mech = roll_flipped
        else:
            # Neither orientation reaches the target — clamp to nearest limit
            roll_resolved_mech = float(np.clip(roll_total, -max_roll, max_roll))

    # shift back to ASCOM roll angle (not mechanical roll angle)
    roll_resolved = wrap180(roll_resolved_mech + roll_adj)

    return az_resolved, alt_resolved, roll_resolved






"""
Revised FK/IK closed form trig solutions - Jun2026.
The three relationships are:
    alt       = arcsin(cos(t3) · sin(t2))
    roll_mag  = arcos(cos(t2) / cos(alt))        
    az        = t1 + arctan2(sin(t3), cos(t3)·cos(t2))

With sign conventions: 
    roll_sign = -sign(sin(t3)) · sign(t2)   in FK, and 
    t3_sign   = -sign(roll)                 in IK (since IK always returns t2 ≥ 0).
"""

def theta_to_azaltroll_fk(t1, t2, t3):
    t2r, t3r = np.radians(t2), np.radians(t3)

    # Altitude: boresight Z as t3 rotates it around tUp
    alt = np.degrees(np.arcsin(np.clip(np.cos(t3r) * np.sin(t2r), -1, 1)))
    cos_alt = np.cos(np.radians(alt))

    # Roll magnitude: from cos(roll) * cos(alt) = cos(t2)
    roll_mag = np.degrees(np.arccos(np.clip(np.cos(t2r) / cos_alt, -1, 1))) if cos_alt > 1e-9 else 0.0
    # Roll sign: -sign(sin(t3)) * sign(t2)
    sin_t3 = np.sin(t3r)
    roll_sign = -np.sign(sin_t3) * np.sign(t2) if abs(sin_t3) > 1e-9 else 1.0
    roll = roll_mag * roll_sign

    # Azimuth: t1 plus az offset from t3
    az = (t1 + np.degrees(np.arctan2(np.sin(t3r), np.cos(t3r) * np.cos(t2r)))) % 360

    return az, alt, roll


def azaltroll_to_theta_ik(az, alt, roll):
    altr, rollr = np.radians(alt), np.radians(roll)

    # t2: from cos(t2) = cos(roll) * cos(alt)
    t2 = np.degrees(np.arccos(np.clip(np.cos(rollr) * np.cos(altr), -1, 1)))
    t2r = np.radians(t2)
    sin_t2 = np.sin(t2r)

    # t3 magnitude: from cos(t3) = sin(alt) / sin(t2)
    t3_mag = np.degrees(np.arccos(np.clip(np.sin(altr) / sin_t2, -1, 1)))  if sin_t2 > 1e-9 else 0.0
    # t3 sign: IK always gives t2>=0, so sign(t2)=+1, giving t3_sign = -sign(roll)
    t3_sign = -np.sign(roll) if abs(roll) > 1e-9 else 1.0
    t3 = t3_mag * t3_sign
    t3r = np.radians(t3)

    # t1: az minus az offset from t3
    az_offset = np.degrees(np.arctan2(np.sin(t3r), np.cos(t3r) * np.cos(t2r)))
    t1 = (az - az_offset) % 360

    return t1, t2, t3


def quaternion_to_angles(q1, lastPos = LastPosition()):
    """
    Decomissioned - do not use this fn
    Convert a quaternion to theta1, theta2, theta3, altitude, azimuth, and roll angles.
    Args:
        q1: Quaternion that rotates from camera frame to topocentric frame
            Camera frame: -z = boresight, +x = up, +y = left
            Topocentric frame: +z = Zenith, +y = North, +x = East
        lastPos: last mechanical position (LastPosition object)
    Returns:
        tuple: (theta1, theta2, theta3, alt, az, roll)
            - theta1: Rotation around Polaris Axis 1 (degrees, 0-360)
            - theta2: Rotation around Polaris Axis 2 (degrees, -90 to +90)
            - theta3: Rotation around Polaris Axis 3 (degrees)
            - alt: Altitude angle (degrees, -90 to +90)
            - az: Azimuth angle (degrees, 0-360)
            - roll: Roll angle around boresight (degrees),  (+ve=camera rotates ccw when view from rear, image rotates cw)
    """
    # q1 rotates from camera frame (-z = boresight, +x = up, +y = left) to topocentric frame (+z = Zenith, +y = North, +x = East)
    # calculate the motor angles from the base quaternion
    theta1, theta2, theta3 = q_to_theta(q1, lastPos=lastPos)
    # Rotate Camera Boresight Unit Vector to Topocentric Reference Frame
    tBore = q1.rotate(np.array([0, 0,-1]))   
    # --- Azimuth and Altitude: rotation around unadjusted bore vector ie Topocentric co-ordinates including effect of Axis 3
    az = (np.degrees(np.arctan2(tBore[0], tBore[1])) + 360) % 360       # Azimuth = Boresight axis projected on N/E plane
    alt = np.degrees(np.arcsin(np.clip(tBore[2], -1.0, 1.0)))           # Altitude = Angle from N/E plane, vertically to the Boresight axis
    # --- Roll angle: rotation around boresight ---
    if abs(abs(alt) - 90) < 1e-3:                                       # if altitude is +90 = pointing straight up or -90 = straight down
        roll = 0.0  
    else:
        qalt = Quaternion(axis=np.array([0,-1, 0]), degrees= alt + 90)  # Rotate Alt around cRight
        qaz = Quaternion(axis=np.array([0, 0,-1]), degrees= az - 90)    # Rotate Az around cBore
        q3 = q1 * (qaz * qalt).inverse                                  # remove alt and az rotations, leaving only the residual roll about the boresight
        roll = abs(q3.degrees)
        aDiff = angular_difference(theta1, az)                          # anglular distance from theta1 to az (-ve diff is a positive ccw roll)
        flip = (roll<90 and aDiff>0) or (roll>=90 and aDiff<=0)
        roll = -roll if flip else roll
    return theta1, theta2, theta3, az, alt, roll




# ── Mechanical axis corrections ───────────────────────────────────────────────

@dataclass
class MountModelParams:
    """
    Mechanical axis correction parameters for the Benro Polaris mount.
    """
    m3_tilt_dm2:      float = 0.0   # arcmin    — M3 tilt altitude effect
    m3_tilt_dm1:      float = 0.0   # arcmin    — M3 tilt azimuth effect
    m3_tilt_dm3:      float = 0.0   # arcmin    — M3 tilt roll effect
    m2_tilt_dm2_amp:  float = 0.0   # arcmin    — M2 tilt amplitude
    m2_tilt_dm2_zero: float = 0.0   # degrees   — M2 tilt zero crossing
    m2_roll_coupling: float = 0.0   # arcmin    — M2 roll coupling (theta2-dependent roll error)
    m2_roll_zero:     float = 45.0  # degrees   — theta2 where M2 roll coupling is zero
    m1_offset:        float = 0.0   # arcmin    — Polar Alignment M1/Az offset
    m2_offset:        float = 0.0   # arcmin    — Polar Alignment M2/Alt offset
    m3_offset:        float = 0.0   # arcmin    — Polar Alignment M3 offset

    @classmethod
    def from_config(cls, config):
        get = (lambda k: config[k]) if isinstance(config, dict) else (lambda k: getattr(config, k))
        return cls(
            m3_tilt_dm2      = get('m3_tilt_dm2'),
            m3_tilt_dm1      = get('m3_tilt_dm1'),
            m3_tilt_dm3      = get('m3_tilt_dm3'),
            m2_tilt_dm2_amp  = get('m2_tilt_dm2_amp'),
            m2_tilt_dm2_zero = get('m2_tilt_dm2_zero'),
            m2_roll_coupling = get('m2_roll_coupling'),
            m2_roll_zero     = get('m2_roll_zero'),
            m1_offset        = get('m1_offset'),
            m2_offset        = get('m2_offset'),
            m3_offset        = get('m3_offset'),
        )

def get_mechanical_correction_q(q: Quaternion, params: MountModelParams):
    """
    Create a quaternion for FK mechanical axis corrections applied BEFORE QUEST.

    Architecture: corrections are applied to q_base before QUEST alignment.
    QUEST is then refitted on corrected sky-pointing pairs, absorbing the
    altitude-structured component of each correction into the frame alignment.

    Sign convention:
      All corrections use degrees=-dm* where dm* is the error in degrees.
      This applies the correction in the apparent 'wrong' motor-space direction,
      which after QUEST absorption produces the correct net correction.
      This is NOT the same as post-QUEST scalar corrections (which add the error
      directly to theta values). The two architectures have opposite sign conventions.

    Constraint on which corrections can be used here:
      Only corrections whose sky-space projection is altitude-structured (varies
      with theta2/sky-alt, not theta3/roll) can work before QUEST. QUEST can absorb
      altitude-varying sky-alt shifts as a frame-tilt adjustment.
      Roll-varying sky-alt shifts (e.g. m3_tilt_dm2: f*sin(t3)) CANNOT be corrected
      here — QUEST cannot absorb them, causing double application. Set m3_tilt_dm2=0.

    M3 tilt — theta1 effect [m3_tilt_dm1]
      Fitted error: dev_q_theta1 = m3_tilt_dm1 * (1 - cos(theta3))
      dm1 = (m3_tilt_dm1/60) * (1-cos(t3)) + m1_offset/60  [degrees]
      Applied: Quaternion(m1_axis, degrees=-dm1)

    M3 tilt — theta3 effect (geometrically coupled to theta1)
      dev_q_theta3 = -cos(theta2) * dev_q_theta1  (j ≈ -1 from FK geometry)
      dm3 = -cos(t2) * dm1 + m3_offset/60  [degrees]
      Applied: Quaternion(m3_axis, degrees=-dm3)

    M2 tilt [m2_tilt_dm2_amp, m2_tilt_dm2_zero]
      Fitted error: dev_q_theta2 = m2_tilt_dm2_amp * sin(theta2 - m2_tilt_dm2_zero)
      Works before QUEST: sky-alt shift is altitude-structured (sin(t2)).
      dm2 += (m2_tilt_dm2_amp/60) * sin(t2 - m2_tilt_dm2_zero) + m2_offset/60
      Applied: Quaternion(m2_axis, degrees=-dm2)

    M3 tilt — theta2 effect [m3_tilt_dm2]
      Fitted error: dev_q_theta2 = m3_tilt_dm2 * sin(theta3)
      CANNOT be applied here (roll-varying sky-alt, QUEST cannot absorb).
      Set m3_tilt_dm2 = 0 in config. Parameter retained for documentation only.

    Correction chain order (right-to-left application):
      q_corr = q_dm3 * q_dm1 * q_dm2
      q_fixed = (q_corr * q_base).normalised
    """
    t1, t2, t3 = q_to_theta(q)

    qtheta1 = Quaternion(axis=[0, 0, 1], degrees=-t1 + 90)
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees=-t2 - 90)
    m2_axis        = qtheta1.rotate([0, 1, 0])
    m3_axis        = (qtheta1 * qtheta2).rotate([1, 0, 0])
    m1_axis        = [0.0, 0.0, 1.0]
    boresight_axis = q.rotate([0, 0, -1])

    # theta1 - M3 tilt effect (around m1_axis)
    dm1 = (params.m3_tilt_dm1 / 60.0) * (1.0 - math.cos(math.radians(t3)))
    # theta3 - M3 tilt effect (geometrically coupled to theta1, around m3_axis)
    dm3 = -math.cos(math.radians(t2)) * dm1
    # theta2 - M2 tilt effect (around m2_axis)
    dm2 = (params.m2_tilt_dm2_amp / 60.0) * math.sin(math.radians(t2 - params.m2_tilt_dm2_zero))  

    # Build correction quaternions
    q_dm2 = Quaternion(axis=m2_axis,  degrees=-dm2)
    q_dm1 = Quaternion(axis=m1_axis,  degrees=-dm1)
    q_dm3 = Quaternion(axis=m3_axis,  degrees=-dm3)  

    q_corr    = q_dm3 * q_dm1 * q_dm2
    magnitude = 2 * math.degrees(math.acos(min(1.0, abs(q_corr.w))))

    return q_corr, magnitude

def apply_mechanical_corrections(q: Quaternion, params: MountModelParams):
    """
    Apply mechanical axis corrections to motor/base quaternion.
    """
    q_corr, magnitude = get_mechanical_correction_q(q, params)
    q_fixed = (q_corr * q).normalised

    return q_fixed, magnitude


def autotune_mac(sync_history: list[dict], base_params: MountModelParams) -> dict:
    """
    Numerically optimise three MAC parameters to minimise QUEST residuals.

    Optimises: m2_tilt_dm2_amp, m2_tilt_dm2_zero, m3_tilt_dm1
    All other MountModelParams are held fixed at base_params values.

    Parameters
    ----------
    sync_history : list of sync entry dicts from SyncManager.sync_history (only non-deleted AzAlt entries are used)
    base_params  : current MountModelParams (frozen — not mutated)

    Returns
    -------
    dict with keys:
        success          : bool
        m2_tilt_dm2_amp  : float (arcmin)
        m2_tilt_dm2_zero : float (degrees)
        m3_tilt_dm1      : float (arcmin)
        rms_before       : float (arcmin)
        rms_after        : float (arcmin)
        rms_improv       : float (% improvement, negative = worse)
        r2               : float (fraction of variance explained by MAC)
        n_points         : int   (number of sync points used)
        nit              : int   (number of optimiser iterations)
        message          : str
    """

    # ── Gather valid sync pairs ───────────────────────────────────────────
    entries = [
        e for e in sync_history
        if not e.get('deleted', False)
        and e.get('a_az')  is not None
        and e.get('a_alt') is not None
    ]
    n = len(entries)
    if n < 2:
        return {'success': False, 'message': f'Need ≥2 sync points, have {n}', 'n_points': n}

    # Pre-compute observed boresight vectors — fixed, roll-independent
    v_obs_list = [np.array(azalt_to_vector(e['a_az'], e['a_alt'])) for e in entries]

    def _davenport_quest(v_preds: list) -> 'Quaternion':
        """Solve Wahba's problem via Davenport K matrix, mirroring optimize_alignQ_B2T exactly."""
        B     = sum(np.outer(vp, vo) for vp, vo in zip(v_preds, v_obs_list))  # pred row, obs col — matches production
        S     = B + B.T
        sigma = np.trace(B)
        Z     = np.array([B[1,2]-B[2,1], B[2,0]-B[0,2], B[0,1]-B[1,0]])
        K        = np.zeros((4, 4))
        K[0, 0]  = sigma
        K[0, 1:] = K[1:, 0] = Z
        K[1:,1:] = S - sigma * np.eye(3)
        eigvals, eigvecs = np.linalg.eigh(K)
        q = eigvecs[:, np.argmax(eigvals)]
        return Quaternion(q[0], q[1], q[2], q[3])

    def residuals_ss(params: MountModelParams) -> float:
        v_preds = []
        for e in entries:
            motorQ_adj, _ = apply_mechanical_corrections(
                azaltroll_to_q(e['p_az'], e['p_alt'], e['p_roll']), params)
            az, alt, _    = q_to_azaltroll(motorQ_adj)
            v_preds.append(np.array(azalt_to_vector(az, alt)))

        alignQ = _davenport_quest(v_preds)

        ss = 0.0
        for vp, vo in zip(v_preds, v_obs_list):
            dot = np.clip(np.dot(np.array(alignQ.rotate(vp)), vo), -1.0, 1.0)
            ss += math.acos(dot) ** 2
        return ss

    def objective(x):
        amp, zero, dm1 = x
        return residuals_ss(dataclasses.replace(base_params,
            m2_tilt_dm2_amp=amp, m2_tilt_dm2_zero=zero, m3_tilt_dm1=dm1))

    # ── Optimise ─────────────────────────────────────────────────────────
    #              m2_tilt_dm2_amp  (arcmin)    m2_tilt_dm2_zero (degrees)    m3_tilt_dm1 (arcmin)
    x0        = [ base_params.m2_tilt_dm2_amp, base_params.m2_tilt_dm2_zero, base_params.m3_tilt_dm1 ]
    bounds    = [ (-300.0,  300.0),              (-360.0,  360.0),               (-400.0,  400.0) ]
    ss_before = objective(x0)
    result    = minimize(objective, x0, method='Nelder-Mead', bounds=bounds,
                         options={'xatol': 0.01, 'fatol': 1e-6, 'maxiter': 2000})
    ss_after  = result.fun

    rms_before = math.degrees(math.sqrt(ss_before / n)) * 60   # arcmin
    rms_after  = math.degrees(math.sqrt(ss_after  / n)) * 60   # arcmin
    r2         = 1.0 - (ss_after / ss_before) if ss_before > 0 else 0.0

    return {
        'success':           result.success,
        'm2_tilt_dm2_amp':   result.x[0],
        'm2_tilt_dm2_zero':  result.x[1],
        'm3_tilt_dm1':       result.x[2],
        'rms_before':        rms_before,
        'rms_after':         rms_after,
        'rms_improv':        (1.0 - rms_after / rms_before) * 100 if rms_before > 0 else 0.0,
        'r2':                r2,
        'n_points':          n,
        'nit':               result.nit,
        'message':           result.message,
    }


# ── QUEST alignment ──────────────────────────────────────────────────────────

def quest_solve(sync_pairs: List[Tuple[Quaternion, Quaternion]]) -> Quaternion:
    """
    Standard QUEST: find alignQ minimising sum of angular errors.
    alignQ such that alignQ * q_base ≈ q_topo for all (q_base, q_topo) pairs.
    Requires >= 1 pair.
    """
    B = np.zeros((3, 3))
    ref_vecs = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    for q_base, q_topo in sync_pairs:
        for v in ref_vecs:
            b = np.array(q_base.rotate(v))
            r = np.array(q_topo.rotate(v))
            B += np.outer(r, b)
    U, _, Vt = np.linalg.svd(B)
    d = np.linalg.det(U @ Vt)
    D = np.diag([1.0, 1.0, d])
    R = U @ D @ Vt
    return Quaternion(matrix=R)

# ── Pulse Guiding ──────────────────────────────────────────────────────────

def calc_equatorial_axes_B(cameraQ_C2T: Quaternion, alignQ_B2T_inv: Quaternion, site_lat: float):
    lat_rad = np.radians(site_lat)

    # ── RA axis — celestial north pole in topo frame ────────────────────────────
    ra_axis_topo = np.array([0.0, np.cos(lat_rad), np.sin(lat_rad)])
   
    # ── PA axis — boresight in topo frame ───────────────────────────────────────
    pa_axis_topo = np.array(cameraQ_C2T.rotate([0.0, 0.0, -1.0]))

    # ── Dec axis — cross(pole, boresight), sign fixed for +Dec = northward ─────
    dec_axis_topo = np.cross(ra_axis_topo, pa_axis_topo)
    n = np.linalg.norm(dec_axis_topo)
    if n < 1e-6:
        dec_axis_topo = np.array([1.0, 0.0, 0.0])
    else:
        dec_axis_topo /= n

    # Check Dec sign. Simulate a small positive rotation around the candidate dec axis
    # Rodrigues' formula: rotate boresight (pa_axis_topo) around dec_axis_topo by angle
    angle = 1e-3  # radians
    c, s = np.cos(angle), np.sin(angle)
    nudged = (c * pa_axis_topo
            + s * np.cross(dec_axis_topo, pa_axis_topo)
            + (1 - c) * np.dot(dec_axis_topo, pa_axis_topo) * dec_axis_topo)
    if np.dot(nudged, ra_axis_topo) < np.dot(pa_axis_topo, ra_axis_topo):
        dec_axis_topo = -dec_axis_topo

    # ── Rotate all axes to base (B) frame ────────────────────────────────
    ra_axis_B  = alignQ_B2T_inv.rotate(ra_axis_topo)
    dec_axis_B = alignQ_B2T_inv.rotate(dec_axis_topo)
    pa_axis_B  = alignQ_B2T_inv.rotate(pa_axis_topo)

    return (
        ra_axis_B  / np.linalg.norm(ra_axis_B),
        dec_axis_B / np.linalg.norm(dec_axis_B),
        pa_axis_B  / np.linalg.norm(pa_axis_B),
    )


def calc_pole_axes_B(pole_topo: np.ndarray, cameraQ_C2T: Quaternion, alignQ_B2T_inv: Quaternion):
    """
    Generalisation of calc_equatorial_axes_B's geometry to any 'pole' direction.

    Given a pole vector in the topocentric frame (celestial pole, zenith, galactic
    pole, ...) and the camera's current orientation, returns three orthogonal axes
    expressed in the Base (motor) frame:
        pole_axis : rotation that changes 'longitude' about the pole (RA / Az / Gal-l)
        perp_axis : rotation that changes 'latitude' from the pole   (Dec / Alt / Gal-b)
        bore_axis : rotation about the boresight itself              (Roll / PA / GPA)

    perp_axis is NOT ambiguous despite depending on only one 'pole' input: it is
    derived from pole x boresight, i.e. it's the axis that moves the CURRENT
    boresight directly toward/away from the pole -- identical in spirit to how
    calc_equatorial_axes_B already derives Dec from the current pointing, not a
    fixed direction in the sky. Degenerates (returns [1,0,0]) only when the
    boresight is pointing exactly at the pole, same as the original function.
    """
    pole_topo = np.asarray(pole_topo, dtype=float)
    pole_topo = pole_topo / np.linalg.norm(pole_topo)

    bore_topo = np.array(cameraQ_C2T.rotate([0.0, 0.0, -1.0]))

    perp_topo = np.cross(pole_topo, bore_topo)
    n = np.linalg.norm(perp_topo)
    if n < 1e-6:
        perp_topo = np.array([1.0, 0.0, 0.0])
    else:
        perp_topo /= n

    angle = 1e-3
    c, s = np.cos(angle), np.sin(angle)
    nudged = (c * bore_topo
              + s * np.cross(perp_topo, bore_topo)
              + (1 - c) * np.dot(perp_topo, bore_topo) * perp_topo)
    if np.dot(nudged, pole_topo) < np.dot(bore_topo, pole_topo):
        perp_topo = -perp_topo

    pole_B = alignQ_B2T_inv.rotate(pole_topo)
    perp_B = alignQ_B2T_inv.rotate(perp_topo)
    bore_B = alignQ_B2T_inv.rotate(bore_topo)

    return (pole_B / np.linalg.norm(pole_B),
            perp_B / np.linalg.norm(perp_B),
            bore_B / np.linalg.norm(bore_B))

GALACTIC_POLE_RA_J2000  = 192.85948   # degrees, North Galactic Pole (J2000)
GALACTIC_POLE_DEC_J2000 = 27.12825    # degrees, North Galactic Pole (J2000)

def calc_galactic_pole_topo(observer_date, lat_deg, lon_deg):
    """Topocentric unit vector toward the North Galactic Pole. Unlike the
    celestial pole, this moves through Alt/Az as sidereal time advances
    (fixed RA/Dec, rotating local frame), so it needs an ephem lookup."""
    obs = ephem.Observer()
    obs.lat, obs.long = math.radians(lat_deg), math.radians(lon_deg)
    obs.date = observer_date
    body = ephem.FixedBody()
    body._ra    = math.radians(GALACTIC_POLE_RA_J2000)
    body._dec   = math.radians(GALACTIC_POLE_DEC_J2000)
    body._epoch = ephem.J2000
    body.compute(obs)
    return azalt_to_vector(math.degrees(float(body.az)), math.degrees(float(body.alt)))


def calc_galactic_axes_B(cameraQ_C2T, alignQ_B2T_inv, lat_deg, lon_deg, observer_date):
    """
    L/B/GPA axes in Base frame. 'Pole' = North Galactic Pole.

    Sign convention (proven against ephem.Galactic -- see test_pole_axes.py):
      +l   -> +rotation about l_axis    (same prograde sense as RA -- no negation)
      +b   -> +rotation about b_axis    (same sense as Dec -- no negation)
      +gpa -> -rotation about gpa_axis  (same underlying boresight axis as roll/PA;
                                          gpa_axis is pole-independent and identical
                                          to roll_axis/pa_axis for the same cameraQ,
                                          so it inherits their negation -- negation needed)
    """
    pole_topo = calc_galactic_pole_topo(observer_date, lat_deg, lon_deg)
    return calc_pole_axes_B(pole_topo, cameraQ_C2T, alignQ_B2T_inv)



def calc_topocentric_axes_B(cameraQ_C2T, alignQ_B2T_inv):
    """
    Az/Alt/Roll axes in Base frame. 'Pole' = local zenith (time-invariant).
    Sign convention (proven in tests/test_pole_axes.py):
        +az   -> -rotation about az_axis    (Az is clockwise; opposite handedness to RA)
        +alt  -> +rotation about alt_axis
        +roll -> -rotation about roll_axis  (same vector as pa_axis/gpa_axis)
    """
    return calc_pole_axes_B([0.0, 0.0, 1.0], cameraQ_C2T, alignQ_B2T_inv)