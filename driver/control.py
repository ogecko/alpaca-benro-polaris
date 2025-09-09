import numpy as np
import datetime
from pyquaternion import Quaternion
from config import Config
from scipy.interpolate import PchipInterpolator
import time
import asyncio
from typing import Optional
import ephem
import math
from shr import rad2deg, deg2rad, rad2hms, deg2dms

# ************* TODO LIST *****************
#
# Technical next steps
# [X] Implement TRACK mode
# [X] Allow first SLOW speed 0 through (dont assume it was 0)
# [X] Stop PID and Motor controllers on shutdown
# [X] Enabling tracking mid GOTO should use SP as target, not current pos
# [X] Fix bug tracking on, off, on - rotates at a faster rate
# [X] Fix delta_ref3 should represent equatorial angle (no change when tracking), alpha_ref desired camera roll angle +ve CCW, 0=horz (changes when tracking)
# [X] Add DATA6 for PID debugging
# [X] Introduce a Low-Pass Filter on Omega Output (aready doing this I think)
# [x] Overlay the expected tracking velocity on the omega plot
# [X] Improve responsiveness of manual slewing, incorporate desired velocity into omega_op
# [X] Fix quaternian maths when alt is negative and zero
# [X] Implement Rotator
# [X] Proper task cleanup in polaris.restart(), especially to fix no position updates for over 2s. Restarting AHRS
# [X] Implement Alpaca Pilot App
# [X] Setup Dialog in Alpaca Pilot
# [X] Alpaca Pilot Action ConfigUpdate pass through to live polaris and pickup from live Polaris eg lat/lon Nina changes
# [X] Alpaca Pilot Log file viewer and streaming of data
# [X] Alpaca Pilot Radial Indicators and home dashboard
# [X] Alpaca pilot current position main display, is parked, is tracking, is slewing, is gotoing, is PID active, is Pulse Guiding
# Alpaca Features
# [X] Alpaca pilot commands for Eq-Az toggle, park, unpark, abort, track, tracking rate
# [X] Alpaca pilot goto Az, Alt, Roll with click on Radial Indicators
# [X] Alpaca pilot floating action buttons for quick axis settings (az, alt, roll)
# [X] Alpaca pilot goto RA, Dec, PA with click on Radial Indicators
# [X] Alpaca pilot radial scales to show warning limits on angles
# [X] Implement slewing state monitoring
# [X] Implement gotoing state monitoring
# [X] Alpaca pilot to restrict pid max velocity and accel in real time
# [X] Explicit pid mode changes, add a 'PARK' mode, ensure no pid activity while parked.
# [X] Ensure polaris tracking is off when enabling advanced tracked
# [X] Indicate speed on Alpaca Dashboard
# [X] Indicate motor activity on Alpaca Dashboard
# [X] Alpaca pilot manual slew AltAzRoll, slew rate
# [X] Alpaca pilot manual slew RADecPA
# [ ] Alpaca pilot Sync
# [ ] Alpaca Pilot SP pointer is removed around +/- 90 degrees too early
# [ ] Alpaca Pilot Radial Scale PVtoSP can arc the wrong way when around 360/0 wraparound
# [ ] Alpaca pilot feature degredation when not in Advanced Control
# [ ] Alpaca pilot feature degredation when no Rotator
# [ ] Alpaca pilot feature degredation when not ABP Driver
# [ ] Alpaca Pilot memory and logevity tests
# [ ] Fix Position Angle dashboard and interaction
# [ ] Fix 340-360 Control Kinematics

# Connection
# [ ] Alpaca pilot work outside of Astro Mode
# [ ] Implement Benro Polaris Connection process and diagnostics
# [ ] Implement Benro Polaris Wifi On 
# Performance
# [ ] Improve responsiveness of manual slewing, stop immediately, faster accel?
# [ ] Move performance tests to actions
# [ ] Rationalise performance data capture and analysis
# [ ] PID tuning to use velocity error as well as position error
# [ ] Improve fine grained tracking precision
# [ ] Improve Kalman Filter tuning
# [ ] Store Motor Calibration data to a file
# [ ] Improve tracking performance beyond BP implementation
# Rotator
# [ ] Rotator Halt, Sync, Reverse, Move(relative), MoveAbs, MoveMech, Position(PA), TargetPosition(PA)
# [ ] Pass ConformU test on Rotator
# Catalog
# [ ] Favorite Targets to Search Home page
# [ ] Alpaca pilot catalog of targets, search, select, goto, display current target
# Orbitals
# [ ] Implement Lunar Tracking rate
# [ ] Implement Solar Tracking rate
# [ ] Implement King Tracking rate
# [ ] Implement Pulse Guiding API ITelescope Pulse 
# [ ] Check Astro head hardware connection
# [ ] Integral Anti-Windup dontaccumulate when output is saturated or quantized
# 
# Features 
#
# Precision Tracking
# [ ] Seamless Axis Override During Tracking
# [ ] Deep-Sky Object Tracking 
# [ ] Selenographic Lunar Tracking 
# [ ] Planetary and Orbital Moons Tracking
# [ ] Commet and Asteroid Tracking
# [ ] Satelite Tracking via TLE (Two Line Element)
# [ ] Solar Tracking 
# [ ] Transiting Exoplanet Support
#
#
# Pulse Guiding Features
# [ ] Guide Camera Support via PHD2
# [ ] PHD2 Support via ASCOM/Alpaca
# [ ] ASCOM Telescope Pulse Guide API Support
# [ ] Pulse Guiding Tracking correction 
#
# Imaging and User Experience Enhancements
# [ ] Long Exposure Tracking Stabilization
# [ ] Drift supression and Auto-Centering
# [ ] Automated Leveling Compensation
# [ ] Dithering support
# [ ] Zenith Imaging Support (18° Circle)
# [ ] Mosaic imaging support through Nina

# Candidate future enhancements
# [ ] Rate Derivative Estimation (Jerk Monitoring)
# [ ] Feedforward Control Integration (minimise overshoot)
# [ ] Control Mode Switching
# [ ] Time-Differentiated Tracking Profiles
# [ ] Predictive Anti-Backlash Correction
# [ ] Expanded Target Catalog
# [ ] Auto-fetch Target Catalog updates
# [ ] Auto-fetch orbital elements
#



# ************* Quaternion Kinematics *************

def is_angle_same(a, b, tolerance=1e-4):
    """Returns True if angles a and b are equivalent within tolerance, accounting for wrapping."""
    return abs((a - b + 180) % 360 - 180) < tolerance


def is_same_quaternion_rotation(q1, q2, tolerance=1e-6):
    """Check if two quaternions represent the same rotation"""
    t1, t2, t3, a1, a2, a3 = quaternion_to_angles(q1)
    s1, s2, s3, b1, b2, b3 = quaternion_to_angles(q2)
    return (t1-s1)**2+(t2-s2)**2+(t3-s3)**2+(a1-b1)**2+(a2-b2)**2+(a3-b3)**2 < tolerance

def wrap_to_360(angle):
    """Wraps angle to [0, 360) degrees"""
    return angle % 360.0

def wrap_to_180(angle):
    """Wraps angle to [-180, +180) degrees"""
    return (angle + 180.0) % 360.0 - 180.0

def wrap_to_90(angle):
    """Wraps angle to [-90, +90) degrees"""
    return (angle + 90.0) % 180.0 - 90.0

def wrap_angle_residual(measured_theta, predicted_theta):
    return np.vectorize(wrap_to_180)(measured_theta - predicted_theta)

def wrap_state_angles(x):
    x_wrapped = x.copy()
    x_wrapped[0, 0] = wrap_to_360(x[0, 0])    # theta1
    x_wrapped[1, 0] = wrap_to_180(x[1, 0])    # theta2
    x_wrapped[2, 0] = wrap_to_180(x[2, 0])    # theta3 
    return x_wrapped

def polar_rotation_angle(latitude_rad, az_rad, alt_rad):
    """
    Compute the roll angle (in degrees) needed to rotate a camera pointed at (az, alt)
    so that the top of the image points toward the celestial pole.
    Positive angle means clockwise rotation when looking through the camera.
    """
    # Convert alt-az to Cartesian unit vector
    def altaz_to_vector(az, alt):
        x = math.cos(alt) * math.sin(az)
        y = math.cos(alt) * math.cos(az)
        z = math.sin(alt)
        return [x, y, z]

    # Step 1: Camera pointing vector
    cam_vec = altaz_to_vector(az_rad, alt_rad)

    # Step 2: Construct orthonormal tangent basis
    # Up vector: derivative of cam_vec w.r.t altitude; Right vector: derivative of cam_vec w.r.t azimuth
    up_vec = [ -math.sin(alt_rad) * math.sin(az_rad), -math.sin(alt_rad) * math.cos(az_rad), math.cos(alt_rad) ]
    right_vec = [ math.cos(alt_rad) * math.cos(az_rad), -math.cos(alt_rad) * math.sin(az_rad), 0 ]

    # Normalize basis vectors
    def normalize(v):
        mag = math.sqrt(sum(c**2 for c in v))
        return [c / mag for c in v]
    up_vec = normalize(up_vec)
    right_vec = normalize(right_vec)

    # Step 3: Celestial pole vector
    pole_az = 0.0 if latitude_rad >= 0 else math.pi
    pole_alt = abs(latitude_rad)
    pole_vec = altaz_to_vector(pole_az, pole_alt)

    # Step 4: Project pole vector into tangent plane
    # Subtract component along cam_vec
    dot = sum(p * c for p, c in zip(pole_vec, cam_vec))
    proj_vec = [p - dot * c for p, c in zip(pole_vec, cam_vec)]

    # Step 5: Compute angle in tangent plane
    proj_up = sum(p * u for p, u in zip(proj_vec, up_vec))
    proj_right = sum(p * r for p, r in zip(proj_vec, right_vec))

    angle_rad = math.atan2(proj_right, proj_up)
    angle_deg = math.degrees(angle_rad)

    return angle_deg

def polar_rotation_angle_wrapped(latitude_rad, az_rad, alt_rad):
    """ Compute the polar rotation angle [-90 to +90) degrees, turn your images upside down. """
    angle_deg = polar_rotation_angle(latitude_rad, az_rad, alt_rad)
    return wrap_to_90(angle_deg)


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
    - Polar Angle ∈ [-180, 180)
    """
    clamped = np.empty_like(delta)
    clamped[0] = delta[0] % 360
    clamped[1] = np.clip(delta[1], -90, 90)
    clamped[2] = ((delta[2] + 180) % 360) - 180
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

def clamp_error(theta_ref, theta_meas):
    """
    Calculates angular error considering wrap-around using modular arithmetic.
    Each error is normalized to [-180, 180) range.
    """
    return ((theta_ref - theta_meas + 180) % 360) - 180

def fmt3(theta):
    return ','.join([ f"{x:.4f}" for x in theta ])

def fmt4(delta):
    return f'{rad2hms(delta[0]/180*math.pi)[:8]}, {deg2dms(delta[1])[:8]}, {deg2dms(delta[2])[:8]}'


def calculate_angular_velocity(history):
    """
    Computes angular velocity from the first and last entries in a history buffer.
    Each entry must be a list or tuple: [timestamp, theta1, theta2, theta3]

    Returns omega : ndarray
        Angular velocity vector [ω₁, ω₂, ω₃] in degrees per second.
        Returns [0.0, 0.0, 0.0] if input is insufficient or invalid.
    """
    try:
        if history is None or len(history) < 2:
            return np.zeros(3)

        # Use first and last entries
        t_start, *theta_start = history[0]
        t_end,   *theta_end   = history[-1]

        if not isinstance(t_start, datetime.datetime) or not isinstance(t_end, datetime.datetime):
            return np.zeros(3)

        dt = (t_end - t_start).total_seconds()
        if dt <= 0:
            return np.zeros(3)

        # Wrap-safe angular velocity
        omega = np.array([
            angular_difference(start, end) / dt
            for start, end in zip(theta_start, theta_end)
        ])
        return omega

    except Exception:
        return np.zeros(3)



def extract_roll_from_quaternion(q3, reference_axis=np.array([0, 0, 1]), epsilon=1e-6):
    """
    Determines roll angle from quaternion q3, corrected for axis direction.
    
    Args:
        q3: Quaternion representing rotation around boresight, with alt and az rotations removed
        reference_axis: Expected boresight direction (default +z)
        epsilon: Threshold for floating-point comparison
    
    Returns:
        float: Corrected roll angle in degrees
    """
    axis_norm = np.linalg.norm(q3.axis)
    if axis_norm < epsilon:
        return 0.0  # No rotation → roll is zero

    actual_axis = q3.axis / axis_norm
    roll_raw = np.float64(q3.degrees)
    alignment = np.dot(actual_axis, reference_axis)

    # Flip sign if axis is pointing in the opposite direction
    # if alignment < -epsilon:
    #     return roll_raw
    # else:
    #     return -roll_raw

    return roll_raw




def angles_to_quaternion(az, alt, roll):
    """
    Convert altitude, azimuth, and roll angles to a quaternion using simple rotation composition.
    
    Args:
        az: Azimuth angle in degrees (0-360)
        alt: Altitude angle in degrees (-90 to +90)
        roll: Roll angle around boresight in degrees
    
    Returns:
        Quaternion: q1 that rotates from camera frame to topocentric frame
    """
    # Reconstructing q1 from az, alt, roll
    qaz = Quaternion(axis=[0, 0, 1], degrees= -az + 90)
    qalt = Quaternion(axis=[0, 1, 0], degrees= -alt - 90)
    qroll = Quaternion(axis=[0, 0, 1], degrees= roll)
    q1 = qaz * qalt * qroll  # Reconstructed q1 quaternion from roll, then alt, then az
    
    return -(q1.normalised) if roll < 0 else q1.normalised



def motors_to_quaternion(theta1, theta2, theta3):
    """
    Convert theta1, theta2, theta3 angles to a quaternion using simple rotation composition.
    
    Args:
        theta1: Polaris Axis 1 angle in degrees (0-360)
        theta2: Polaris Axis 2 angle in degrees (-90 to +90)
        theta3: Polaris Axis 3 angle in degrees (-90 to +90)
    
    Returns:
        Quaternion: q1 that rotates from camera frame to topocentric frame
    """
    
    # Reconstructing q1 from theta1, theta2, theta3
    qtheta1 = Quaternion(axis=[0, 0, 1], degrees= -theta1 + 90)
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees= -theta2 - 90)
    qtheta3 = Quaternion(axis=(qtheta1*qtheta2).rotate([1, 0, 0]), degrees= -theta3)
    q1 = qtheta3 * qtheta1 * qtheta2   # Reconstructed q1 quaternion from theta2 then theta1 then theta3

    return q1.normalised if theta3 < 0 else -q1.normalised



def quaternion_to_angles(q1, azhint = -1):
    """
    Convert a quaternion to theta1, theta2, theta3, altitude, azimuth, and roll angles.
    
    Args:
        q1: Quaternion that rotates from camera frame to topocentric frame
            Camera frame: -z = boresight, +x = up, +y = left
            Topocentric frame: +z = Zenith, +y = North, +x = East
        azhint: Azimuth hint in case we have a gimbal lock at alt=0
    
    Returns:
        tuple: (theta1, theta2, theta3, alt, az, roll)
            - theta1: Rotation around Polaris Axis 1 (degrees, 0-360)
            - theta2: Rotation around Polaris Axis 2 (degrees, -90 to +90)
            - theta3: Rotation around Polaris Axis 3 (degrees)
            - alt: Altitude angle (degrees, -90 to +90)
            - az: Azimuth angle (degrees, 0-360)
            - roll: Roll angle around boresight (degrees)
    """
    
    # Reference Unit Vectors
    cBore =   np.array([0, 0,-1])     # Camera Pointing Unit Vector (same as optical axis) in the Camera Reference Frame
    cUp =     np.array([1, 0, 0])     # Camera Up Unit Vector (same as Polaris Axis 3) in the Camera Reference Frame
    cRight =  np.array([0,-1, 0])     # Camera Right Unit Vector in the Camera Reference Frame


    # q1 rotates from camera frame (-z = boresight, +x = up, +y = left) to topocentric frame (+z = Zenith, +y = North, +x = East)
    # Rotate Camera Reference Unit Vectors to Topocentric Reference Frame
    [tBore, tUp, tRight] = np.array([q1.rotate(p) for p in [cBore, cUp, cRight]])    

    # --- Azimuth and Altitude: rotation around unadjusted bore vector ie Topocentric co-ordinates including effect of Axis 3
    az = (np.degrees(np.arctan2(tBore[0], tBore[1])) + 360) % 360       # Azimuth = Boresight axis projected on N/E plane
    alt = np.degrees(np.arcsin(np.clip(tBore[2], -1.0, 1.0)))           # Altitude = Angle from N/E plane, vertically to the Boresight axis

    # --- Roll angle: rotation around boresight ---
    if abs(abs(alt) - 90) < 1e-3:                                       # if altitude is +90 = pointing straight up or -90 = straight down
        roll = 0.0  
    else:
        qalt = Quaternion(axis=cRight, degrees= alt + 90)
        qaz = Quaternion(axis=cBore, degrees= az - 90)
        q3 = q1 * (qaz * qalt).inverse                                  # remove alt and az rotations, leaving only the residual roll about the boresight
        roll = extract_roll_from_quaternion(q3)
        
    # --- Theta3: rotation around Camera up axis in topocentric frame (Polaris Axis 3) ---
    q4 = q1 if alt < 0 else q1 * Quaternion(axis=cUp, degrees=180)      # since axis3 is last rotation ZYX in q1, we can simply read its Euler angle X after we flip it
    theta3 = -np.degrees(np.arctan2(2 * (q4[0]*q4[1] + q4[2]*q4[3]), q4[0]**2 - q4[1]**2 - q4[2]**2 + q4[3]**2))
    
    # --- Theta1 and Theta2: rotation around corrected bore vector ie Polaris Axis 1 and 2, without effect of Axis 3
    unroll = Quaternion(axis=tUp, degrees= -theta3).inverse               # Undo Theta3 rotation to get cleaned bore vector 
    mBore = unroll.rotate(tBore)                                        # mBore is the Camera optical axis if we removed the Astro Module on the polaris
    theta1 = (np.degrees(np.arctan2(mBore[0], mBore[1])) + 360) % 360
    theta2 = np.degrees(np.arcsin(np.clip(mBore[2], -1.0, 1.0)))

    # --- Handle a weird rounding problem for tests, ensure 359.9999999994 is 0.0 
    if abs(theta1 - 360) < 1e-10:
        theta1 = 0.0

    # --- Handle the case where we have a gimbal lock at alt = 0
    if abs(alt) < 1e-10 and azhint != -1:
        roll = angular_difference(azhint, az)
        az = wrap_to_360(azhint)
        theta3 = roll
        theta1 = az

    return theta1, theta2, theta3, az, alt, roll



# ************* Kalman Filter *************


class KalmanFilter:
    def __init__(self, logger, initial_state):
        self._logger = logger
        self._time = time.monotonic()
        self._need_first_measurement = True

        # State: [theta1, theta2, theta3, omega1, omega2, omega3]
        self.x = initial_state.reshape(6, 1)
        self.set_state_transition_matrix_A()    # State transition matrix (A): position + dt * velocity 
        self.set_control_matrix_B()             # Control matrix (B): nudge state velocity by acceleration (omega_ref - omega_state)
        self.H = np.eye(6)                      # Measurement matrix (H): measures both position and velocity
        self.set_process_noise_model_Q()        # Process noise models matrix (Q) 
        self.set_measurement_noise_model_R()    # Measurement noise model matrix (R)
        self.P = np.eye(6)                      # Initial estimate covariance
        self.I = np.eye(6)

    def set_state_transition_matrix_A(self):
        # recalc State transition matrix (A): position + dt * velocity
        # use time interval since last call as dt
        new_time = time.monotonic()
        dt = new_time - self._time
        self._time = new_time
        self.A = np.block([
            [np.eye(3), dt * np.eye(3)],
            [np.zeros((3, 3)), np.eye(3)]
        ])

    def set_control_matrix_B(self, accel_nudge_vel=0.5):
        # Control matrix (B): acceleration nudging velocity
        self.B = np.block([
            [np.zeros((3, 3))],
            [accel_nudge_vel * np.eye(3)]
        ])

    def set_process_noise_model_Q(self, pos=1e-5, vel=1e-4):
        self.Q = np.diag([ pos, pos, pos, vel, vel, vel ])

    def set_measurement_noise_model_R(self, pos=1e-5, vel=1e-4):
        # The Astro axis2 (theta3 and omega3) tend to have more noisy measurements
        self.R = np.diag([ pos, pos, pos*10, vel, vel, vel*10 ])

    def predict(self, control_input):
        self.Q = np.diag(Config.kf_process_noise)
        self.set_state_transition_matrix_A()
        control_input = np.array(control_input).reshape(3, 1)
        omega_state = self.x[3:]                    # stateimated velocity
        u = control_input - omega_state             # Acceleration signal
        self.x = self.A @ self.x + self.B @ u
        self.P = self.A @ self.P @ self.A.T + self.Q
        self.x = wrap_state_angles(self.x)


    def observe(self, theta, omega):
        self.R = np.diag(Config.kf_measure_noise)
        if self._need_first_measurement:
            self._need_first_measurement = False
            self.set_state([*theta, *omega])

        theta_meas = np.array(theta).reshape(3, 1)
        omega_meas = np.array(omega).reshape(3, 1)
        z = np.vstack((theta_meas, omega_meas))               # Measurement: position + velocity

        # Measurement residual
        theta_residual = wrap_angle_residual(theta_meas, self.x[:3])
        omega_residual = omega_meas - self.x[3:]
        y = np.vstack((theta_residual, omega_residual))
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (self.I - K @ self.H) @ self.P
        self.x = wrap_state_angles(self.x)

        self._logger.debug(f"KF Gain:{K} | Residual y:{y}")


    def get_state(self):
        state = self.x.flatten()
        theta = state[0:3]
        omega = state[3:]
        return theta, omega

    def set_state(self, x):
        self.x = np.array(x).reshape(6, 1)



# ************* MoveAxis Rate Interpolation *************

# MoveAxis Rate Interpolation Data from PERFORMANCE TEST 3
move_axis_data = {
0: {
    "RAW":   [        0.0,        1.0,        2.0,        3.0,        4.0,        5.0,        0.0,      200.0,      300.0,      400.0,      500.0,      750.0,     1000.0,     1250.0,     1500.0,     1750.0,     2000.0,     2250.0,     2500.0 ],
    "DPS":   [  0.0000000,  0.0059018,  0.0175906,  0.0478282,  0.0892742,  0.2079884,  0.0000000,  0.0826508,  0.1884720,  0.3499597,  0.5431475,  1.1070739,  1.6431014,  2.4638719,  3.4226340,  4.5138057,  5.7638248,  7.1917616,  8.4718999 ],
    "ASCOM": [  0.0000000,  1.0000000,  2.0000000,  3.0000000,  4.0000000,  5.0000000,  0.0000000,  2.5202957,  4.8908095,  5.2406800,  5.4834616,  5.8336443,  6.0594102,  6.3969944,  6.7087436,  7.1151553,  7.6606850,  8.3396806,  9.0000000 ],
    "STDEV": [  0.0000710,  0.0000910,  0.0003617,  0.0004860,  0.0003016,  0.0004048,  0.0002092,  0.0079668,  0.0057629,  0.0132442,  0.0072990,  0.0135596,  0.0065439,  0.0196820,  0.0048385,  0.0070419,  0.0219490,  0.0090652,  0.0054845 ],
    "BAD":   [       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK' ]
},
1: {
    "RAW":   [        0.0,        1.0,        2.0,        3.0,        4.0,        5.0,        0.0,      200.0,      300.0,      400.0,      500.0,      750.0,     1000.0,     1250.0,     1500.0,     1750.0,     2000.0,     2250.0,     2500.0 ],
    "DPS":   [  0.0000000,  0.0058962,  0.0178883,  0.0475348,  0.0891956,  0.2081685,  0.0000000,  0.0746553,  0.1555750,  0.2881311,  0.4348639,  0.9816407,  1.5581530,  2.1773055,  2.9791471,  3.8844374,  5.0558151,  6.1462419,  7.5407644 ],
    "ASCOM": [  0.0000000,  1.0000000,  2.0000000,  3.0000000,  4.0000000,  5.0000000,  0.0000000,  2.2778847,  4.4147319,  5.1589071,  5.3928647,  5.8263561,  6.1114718,  6.3925436,  6.6853189,  7.0528322,  7.6227352,  8.1985778,  9.0000000 ],
    "STDEV": [  0.0000521,  0.0001222,  0.0001968,  0.0001482,  0.0002402,  0.0002164,  0.0001024,  0.0069683,  0.0057544,  0.0092193,  0.0141372,  0.0142809,  0.0250686,  0.0201466,  0.0176632,  0.0342234,  1.1317187,  0.0185269,  0.0105715 ],
    "BAD":   [       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK', 'UNSTABLE',       'OK',       'OK' ]
},
2: {
    "RAW":   [        0.0,        1.0,        2.0,        3.0,        4.0,        5.0,        0.0,      200.0,      300.0,      400.0,      500.0,      750.0,     1000.0,     1250.0,     1500.0,     1750.0,     2000.0,     2250.0,     2500.0 ],
    "DPS":   [  0.0000000,  0.0061072,  0.0178865,  0.0475870,  0.0893458,  0.2093503,  0.0000000,  0.0700289,  0.1421763,  0.2879616,  0.4680061,  1.0217304,  1.5638822,  2.2193762,  3.0904376,  4.0124070,  5.1367704,  6.4164300,  7.8230214 ],
    "ASCOM": [  0.0000000,  1.0000000,  2.0000000,  3.0000000,  4.0000000,  5.0000000,  0.0000000,  2.1189787,  4.1218697,  5.1511917,  5.4230129,  5.8293670,  6.0842764,  6.3768690,  6.6849994,  7.0450211,  7.5699184,  8.2198180,  9.0000000 ],
    "STDEV": [  0.0001545,  0.0002600,  0.0002692,  0.0004644,  0.0001037,  0.0004251,  0.0000689,  0.0012950,  0.0086627,  0.0097931,  0.0042968,  0.0093393,  0.0188401,  0.0072625,  0.0125140,  0.0075252,  0.0040023,  0.0035787,  0.0064637 ],
    "BAD":   [       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK',       'OK' ]
},
}


def format_move_axis_data(data, col_width=10):
    output_lines = []
    for axis, axis_data in data.items():
        output_lines.append(f"{axis}: {{")
        keys = list(axis_data.keys())
        for i, key in enumerate(keys):
            values = axis_data[key]
            if key in ["DPS", "ASCOM", "STDEV"] :
                formatted = [f"{v:.7f}".rjust(col_width) for v in values]
            elif key == "BAD":
                formatted = [f"'{v}'".rjust(col_width) for v in values]
            else:
                formatted = [str(v).rjust(col_width) for v in values]
            value_str = ', '.join(formatted)
            comma = ',' if i < len(keys) - 1 else ''
            output_lines.append(f'    "{key+'":':7s} [ {value_str} ]{comma}')
        output_lines.append("},")  # End of axis block with trailing comma
    return '\n'.join(output_lines)

class MoveAxisRateInterpolator:
    """
    Interpolation manager for MoveAxis rates across multiple units.

    Provides:
    - interpolate['ASCOM'].toRAW(x): Interpolates ASCOM rate to RAW step command rate
    - interpolate['DPS'].toRAW(x): Interpolates degrees/sec to RAW step command rate
    - interpolate['RAW'].toRAW(x): Pass-through (input is already RAW)
    - interpolate['RAW'].toDPS(x): Converts RAW step command to degrees/sec
    """

    def __init__(self, data):
        self.RAW = MoveAxisRateUnitInterpolator(data, 'RAW')
        self.ASCOM = MoveAxisRateUnitInterpolator(data, 'ASCOM')
        self.DPS = MoveAxisRateUnitInterpolator(data, 'DPS')
        self.maxDPS = data['DPS'][-1]
        self.interpolate = { 'RAW': self.RAW, 'ASCOM': self.ASCOM, 'DPS': self.DPS }

class MoveAxisRateUnitInterpolator:
    def __init__(self, data, unit):
        # any data point with raw > 5 is a FAST command
        idx = data['RAW'].index(5) + 1
        self.threshold = data[unit][idx - 1]

        # unit → RAW interpolation
        self.SLOW = PchipInterpolator(data[unit][0:idx], data['RAW'][0:idx], extrapolate=True)
        self.FAST = PchipInterpolator(data[unit][idx:], data['RAW'][idx:], extrapolate=True)
        self.toRAW = lambda x: self._signed_raw(np.array(x))

        # RAW → DPS interpolation
        if unit == 'RAW':
            self.SLOW_INV = PchipInterpolator(data['RAW'][0:idx], data['DPS'][0:idx], extrapolate=True)
            self.FAST_INV = PchipInterpolator(data['RAW'][idx:], data['DPS'][idx:], extrapolate=True)
            self.toDPS = lambda x: self._signed_dps(np.array(x))

    def _signed_raw(self, x):
        direction = np.sign(x)
        abs_x = np.abs(x)
        raw_val = np.where(abs_x > self.threshold, self.FAST(abs_x), self.SLOW(abs_x))
        return raw_val * direction

    def _signed_dps(self, x):
        direction = np.sign(x)
        abs_x = np.abs(x)
        dps_val = np.where(abs_x > 5, self.FAST_INV(abs_x), self.SLOW_INV(abs_x))
        return dps_val * direction


# ************* MoveAxis Speed Controller *************
class MotorSpeedController:
    def __init__(self, logger, axis, send_msg):
        self.axis = axis
        self._logger = logger
        self._model = MoveAxisRateInterpolator(move_axis_data[axis])
        self._messenger = MoveAxisMessenger(axis, send_msg)
        self._stop_flag = asyncio.Event()
        self._lock = asyncio.Lock()

        # Core state
        self.pending_update = None  # Stores update tuple (raw, ramp_duration, timestamp)
        self.rate_dps = 0.0         # dps rate of current requested speed
        self.rate_raw = 0.0         # raw rate of current requested speed
        self.mode = 'IDLE'          # Modes: IDLE, SLOW, SLOW_PWM, FAST_RAMP, FAST
        self.ramp_start = 0.0       # raw rate at start of ramp
        self.ramp_target = 0.0      # raw rate at end of ramp
        self.ramp_duration = None   # duration of ramp in seconds
        self.ramp_start_time = time.monotonic()     # Time the ramp started
        self.next_dispatch_time = time.monotonic()  # Next time to dispatch a command
        self.command = None         # for SLOW_PWM hols (base, next); for all other modes holds Current command to send to the motor

        # PWM tracking
        self.duty_cycle = 0.0
        self.pwm_phase = 'ON'
        self.last_switch_time = time.monotonic()

        asyncio.create_task(self._dispatch_loop())

    async def set_motor_speed(self, rate, rate_unit="DPS", ramp_duration=None, allow_PWM=True):
        async with self._lock:
            raw = self._model.interpolate[rate_unit].toRAW(rate)
            now = time.monotonic()
            # if we get too many updates before they are applied, just overwrite the last one
            self.pending_update = (float(raw), ramp_duration, allow_PWM, now)

    def _apply_pending_update(self, now):
        if not self.pending_update:
            return
        
        if self.mode == "SLOW_PWM" and now < self.next_dispatch_time:
            return
        

        # Apply new rate and update state for dispatch to take over
        new_raw, ramp_duration, allow_PWM, update_time = self.pending_update
        self.pending_update = None
        prior_raw = self.rate_raw
        self.rate_raw = new_raw
        self.rate_dps = self._model.interpolate['RAW'].toDPS(new_raw)
        interp = abs(new_raw)
        direction = 1 if new_raw >= 0 else -1
        self.next_dispatch_time = now

        if interp == 0:
            self.mode = "SLOW"
            self.command = 0

        elif interp > 5 and ramp_duration:
            self.mode = "FAST_RAMP"
            self.ramp_start = prior_raw
            self.ramp_target = new_raw
            self.ramp_duration = ramp_duration
            self.ramp_start_time = time.monotonic()
            # work out command on the fly with FAST_RAMP

        elif interp > 5:
            self.mode = "FAST"
            self.command = int(np.clip(round(interp), 100, 2500)) * direction

        else:
            base = int(np.floor(interp)) * direction
            next_up = int(np.ceil(interp)) * direction
            duty = interp - np.floor(interp)

            if not allow_PWM:
                self.mode = "SLOW"
                self.command = int(round(interp,0)) * direction
                self.rate_dps = self._model.interpolate['RAW'].toDPS(self.command)
            elif duty == 0 or base == next_up:
                self.mode = "SLOW"
                self.command = base
            else:
                self.mode = "SLOW_PWM"
                self.command = (base, next_up)
                self.duty_cycle = duty

    async def _dispatch_loop(self):
        while not self._stop_flag.is_set():
            async with self._lock:
                now = time.monotonic()
                self._apply_pending_update(now)

                if now < self.next_dispatch_time:
                    await asyncio.sleep(0.001)
                    continue

                if self.mode == "FAST":
                    await self._messenger.send_fast_move_msg(self.command)
                    self.next_dispatch_time = now + 0.05

                elif self.mode == "FAST_RAMP":
                    elapsed = now - self.ramp_start_time
                    if elapsed >= self.ramp_duration:
                        self.mode = "FAST"
                    blend = max(0.0, min(1.0, elapsed / self.ramp_duration))
                    self.command = self.ramp_start + blend * (self.ramp_target - self.ramp_start)
                    await self._messenger.send_fast_move_msg(self.command)
                    # self._logger.info(f"Motor {self.axis} FAST_RAMP: rate {self.command}, blend {blend:.2f}, start {self.ramp_start:.2f}, target {self.ramp_target:.2f}")
                    self.next_dispatch_time = now + 0.05

                elif self.mode == "SLOW":
                    await self._messenger.send_slow_move_msg(self.command)
                    self.next_dispatch_time = now + float('inf')
                    if self.command == 0:
                        self.mode = "IDLE"

                elif self.mode == "SLOW_PWM":
                    base, next_up = self.command
                    pwm_rate = base if self.pwm_phase == "ON" else next_up
                    duration = 1.2 * (1 - self.duty_cycle if self.pwm_phase == "ON" else self.duty_cycle)
                    await self._messenger.send_slow_move_msg(pwm_rate)
                    # self._logger.info(f"Motor {self.axis} PWM phase: {self.pwm_phase}, rate: {pwm_rate}, duration: {duration:.2f}s")
                    self.pwm_phase = "OFF" if self.pwm_phase == "ON" else "ON"
                    self.last_switch_time = now
                    self.next_dispatch_time = now + duration

            await asyncio.sleep(0.001)

    async def stop_disspatch_loop_task(self):
        async with self._lock:
            # dont bother trying to stop motors as some structures have been lost already
            # await self._messenger.send_slow_move_msg(0)
            # await asyncio.sleep(0.2)
            self._stop_flag.set()

class MoveAxisMessenger:
    def __init__(self, axis: int, send_msg):
        if axis not in (0, 1, 2):
            raise ValueError("Invalid axis.")
        self.axis = axis
        self.send_msg = send_msg
        self.cmd_slow = ['532', '533', '534'][axis]     # Pick right cmd based on axis passed in on initialisation
        self.cmd_fast = ['513', '514', '521'][axis]     # Pick right cmd based on axis passed in on initialisation
        self.last_slow_raw_rate = None

    async def send_slow_move_msg(self, slow_raw_rate: int) -> str:
        clamped_raw_rate = int(np.clip(slow_raw_rate, -5, +5))
        if clamped_raw_rate == self.last_slow_raw_rate:
            return
        self.last_slow_raw_rate = clamped_raw_rate
        key = 0 if clamped_raw_rate > 0 else 1
        state = 0 if clamped_raw_rate == 0 else 1
        msg = f"1&{self.cmd_slow}&3&key:{key};state:{state};level:{abs(clamped_raw_rate)};#"
        await self.send_msg(msg)
        return msg

    async def send_fast_move_msg(self, fast_raw_rate: int) -> str:
        clamped_fast_rate = int(np.clip(fast_raw_rate, -2500, +2500))
        msg = f"1&{self.cmd_fast}&3&speed:{int(clamped_fast_rate)};#"
        await self.send_msg(msg)
        return msg

########################## 
#  PID CONTROL STRATEGY  #
########################## 


class PID_Controller():
    def __init__(self, logger, controllers, observer, dt=0.2, Kp=0.8, Ki=0.0, Kd=0.8, Ke=0.4, Kc=1.0, loop=None):
        self._stop_flag = asyncio.Event()                    # Used to flag control loop to stop
        self._lock = asyncio.Lock()                          # Used to ensure no threading issues
        self.logger = logger                                 # Logging utility
        self.controllers = controllers                       # Motor speed controllers[0,1,2]
        self.observer = observer                             # Observing object from ephem
        self.body = ephem.FixedBody()                        # Target body
        self.body._epoch = ephem.J2000                       # default to J2000 epoch
        self.body_pa_offset = 0                              # used to store body pa to oconvert back to roll
        self.control_loop_duration = loop                    # PID Control Loop duration in seconds
        self.mode = 'IDLE'                                   # PID Controller mode: PARK, IDLE, AUTO, TRACK
        self.target_type = 'NONE'                            # target body we are tracking
        self.delta_sp = np.array([0,0,0], dtype=float)       # Setpoint for ra, dec, polar anglular positions
        self.alpha_sp = np.array([0,0,0], dtype=float)       # Setpoint for az, alt, roll angular positions
        self.delta_meas = np.array([0,0,0], dtype=float)     # ra, dec, polar measured angular position
        self.alpha_meas = np.array([0,0,0], dtype=float)     # az, alt, roll measured angular position
        self.theta_meas = np.array([0,0,0], dtype=float)     # theta1-3 motor measured angular position
        self.delta_ref = np.array([0,0,0], dtype=float)      # ra, dec, polar angular reference position
        self.alpha_ref = np.array([0,0,0], dtype=float)      # az, alt, roll angular reference position
        self.theta_ref = np.array([0,0,0], dtype=float)      # theta1-3 motor reference angular position
        self.error_signal = np.array([0,0,0], dtype=float)   # theta1-3 error btw theta_ref and theta_meas
        self.error_integral = np.array([0,0,0], dtype=float) # theta1-3 error btw theta_ref and theta_meas
        self.goto_complete_callback = None                    # callback function when no longer deviating
        self.is_deviating = False                            # cost signal is > Kc Arc Minutes²
        self.is_slewing = False                              # a velicity_sp is non-zero
        self.is_tracking = False                             # tracking target body
        self.is_moving = False                               # mount is deviating, slewing or tracking
        self.was_moving = False                              # previous control step movement flag
        self.omega_ref = np.array([0,0,0], dtype=float)      # omega1-3 reference tracking angular velocity
        self.omega_tgt = np.array([0,0,0], dtype=float)      # omega1-3 motor angular velocity raw pid output
        self.omega_ctl = np.array([0,0,0], dtype=float)      # omega1-3 motor angular velocity constrained output
        self.omega_op = np.array([0,0,0], dtype=float)       # omega1-3 motor angular velocity control output
        self.reset_offsets()
        self.reset_theta()
        self.time_meas = None                # Time of measurement
        self.time_sp = None                  # Time that target was set
        self.time_step = time.monotonic()    # Time that control step was done
        self.dt = dt    # Time interval since last control step in seconds

        # Tunable gains and constraints
        self.Kp = Kp    # Proportional Gain - control speed correlated with error_signal
        self.Ki = Ki    # Integral Gain - reduce cumulative error when reference is ramping
        self.Kd = Kd    # Derivative Gain - reduce control when angular velocity higher (damping)
        self.Ke = Ke    # Expotential Smoothing - how much of current value to mix (0=None)
        self.Kc = Kc    # Number of Arc-Minutes error to accept as not deviating
        self.set_Ka_array(Config.max_accel_rate) # Maximum acceleration (float: degrees per seconds² or array(3): degrees per seconds²
        self.set_Kv_array(Config.max_slew_rate)  # Maximum velocity (float: degrees per second or array(3): degrees per seconds or None: (maxDSP from controller)
        
        if Config.advanced_control and self.control_loop_duration:
            asyncio.create_task(self._control_loop())

    #------- Helper functions ---------
    def set_Ka_array(self, Ka):
        if isinstance(Ka, (list, tuple)):
            self.Ka = np.array(Ka, dtype=float)
        elif isinstance(Ka, float) and Ka>0 and Ka<10:
            self.Ka = np.array([Ka, Ka, Ka], dtype=float)
        else:
            self.Ka = np.array([3,3,3], dtype=float)

    def set_Kv_array(self, Kv):
        if  isinstance(Kv, (list, tuple)):
            self.Kv = np.array(Kv, dtype=float)
        elif isinstance(Kv, float) and Kv>0 and Kv<10:
            self.Kv = np.array([Kv, Kv, Kv], dtype=float) 
        else:
            self.Kv = np.array([ self.controllers[axis]._model.maxDPS for axis in range(3) ], dtype=float)

    def reset_offsets(self):
        self.reset_delta_offsets()
        self.reset_alpha_offsets()

    def reset_delta_offsets(self):
        self.delta_v_sp = np.array([0,0,0], dtype=float)     # Setpoint for ra, dec, polar anglular velocities
        self.delta_offst = np.array([0,0,0], dtype=float)    # ra, dec, polar anglular offsets
        self.delta_ref_last = np.array([0,0,0], dtype=float) # ra, dec, polar angular reference position of last control step

    def reset_alpha_offsets(self):
        self.alpha_v_sp = np.array([0,0,0], dtype=float)     # Setpoint for az, alt, roll angular velocities
        self.alpha_offst = np.array([0,0,0], dtype=float)    # az, alt, roll angular offsets

    def reset_theta(self):
        self.theta_ref = np.array([0,0,0], dtype=float)      # theta1-3 motor angular reference position
        self.theta_ref_last = np.array([0,0,0], dtype=float) # theta1-3 motor angular reference position of last control step

    def body_pa(self):
        return wrap_to_180(0.0 - rad2deg(self.body.parallactic_angle()))
    
    def body2alpha(self):
        self.observer.date = datetime.datetime.now(tz=datetime.timezone.utc)
        self.body.compute(self.observer)
        alt = rad2deg(self.body.alt)
        az = rad2deg(self.body.az)
        roll = self.body_pa() + self.body_pa_offset
        return np.array([az, alt, roll], dtype=float)

    def alpha2body(self, alpha):
        self.observer.date = datetime.datetime.now(tz=datetime.timezone.utc)
        ra_rad, dec_rad = self.observer.radec_of(deg2rad(alpha[0]), deg2rad(alpha[1]))
        self.body._ra = ra_rad
        self.body._dec = dec_rad
        self.body.compute(self.observer)
        self.body_pa_offset = alpha[2] - self.body_pa()

    def body2delta(self):
        self.observer.date = datetime.datetime.now(tz=datetime.timezone.utc)
        self.body.compute(self.observer)
        ra_deg = rad2deg(self.body._ra)
        dec_deg = rad2deg(self.body._dec)
        pa_deg = self.body_pa_offset
        return np.array([ra_deg, dec_deg, pa_deg], dtype=float)
    

    def delta2body(self, delta):
        self.observer.date = datetime.datetime.now(tz=datetime.timezone.utc)
        self.body._ra = deg2rad(delta[0])
        self.body._dec = deg2rad(delta[1])
        self.body_pa_offset = delta[2] 

    #------- Functions to change SP, Targets and Mode ---------

    def set_tracking_on(self):
        if self.mode=="PARK":
            return
        if self.mode=="AUTO":
            track_target = self.alpha_ref.copy()
        else:
            track_target = self.alpha_meas.copy()
        self.reset_offsets()
        self.alpha_sp = track_target
        self.alpha2body(track_target)
        self.delta_sp = self.body2delta()
        self.set_pid_mode('TRACK')
    
    def set_tracking_off(self):
        if self.mode=="PARK":
            return
        if self.mode == 'TRACK':
            self.set_pid_mode('AUTO')

    def set_pid_mode(self, newMode):
        if newMode in ['PARK', 'IDLE', 'AUTO', 'TRACK']:
            self.mode = newMode

    def set_no_target(self):
        self.target_type = "NONE"
        self.reset_offsets()

    def set_alpha_target(self, sp: dict[str, float]):
        if self.mode=="PARK":
            return
        self.reset_offsets()
        self.target_type = "ALPHA"
        # Safely update alpha_sp components if provided
        self.alpha_sp[0] = sp.get("az", self.alpha_sp[0])
        self.alpha_sp[1] = sp.get("alt", self.alpha_sp[1])
        self.alpha_sp[2] = sp.get("roll", self.alpha_sp[2])
        self.alpha2body(self.alpha_sp)
        self.delta_sp = self.body2delta()
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_alpha_axis_velocity(self, axis, sp=0.0):
        if self.mode=="PARK":
            return
        self.alpha_v_sp[axis] = sp
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_delta_target(self, delta):
        if self.mode=="PARK":
            return
        self.reset_offsets()
        self.target_type = "DELTA"
        self.delta_sp = delta
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_delta_axis_position(self, axis, sp=0.0):
        if self.mode=="PARK":
            return
        self.delta_sp[axis] = sp
        self.delta_v_sp[axis] = 0
        self.delta_offst[axis] = 0
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')
        
    def set_delta_axis_position_relative(self, axis, sp=0.0):
        if self.mode=="PARK":
            return
        self.delta_sp[axis] = self.delta_sp[axis] + sp
        self.delta_v_sp[axis] = 0
        self.delta_offst[axis] = 0
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_delta_axis_velocity(self, axis, sp=0.0):
        if self.mode=="PARK":
            return
        self.delta_v_sp[axis] = sp
        if self.mode in ['IDLE','AUTO']:
            self.set_pid_mode('TRACK')
    
    def pulse_delta_axis(self, axis, duration, direction=1, sp=0.0020833):
        if self.mode!="TRACK":
            return
        # default guide rate is 0.50x sidereal rate (in the positive direction)
        pulse = np.array([0,0,0], dtype=float)
        pulse[axis] = direction * sp
        self.delta_offst = clamp_delta(self.delta_offst + duration * pulse)

    def set_TLE_target(self, line1, line2, line3):
        if self.mode=="PARK":
            return
        self.reset_offsets()
        self.target_type = "TLE"
        self.target['lines'] = [line1, line2, line3]
        self.reset_offsets()
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')
    
    def set_XEphem_target(self, line):
        if self.mode=="PARK":
            return
        self.reset_offsets()
        self.target_type = "XEPHEM"
        self.target['line'] = line
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def rotator_move_relative(self, sp=0.0):
        if self.mode=="PARK":
            return
        axis=2
        self.alpha_sp[axis] = self.alpha_sp[axis] + sp
        self.alpha_v_sp[axis] = 0
        self.alpha_offst[axis] = 0
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_goto_complete_callback(self, fn):
        self.is_deviating = True
        self.goto_complete_callback = fn
              

    #------- Control step functions ---------

    def track_target(self):
        # Update alpha_ref based on current mode
        if self.mode in ['IDLE', 'PARK']:
            self.alpha2body(self.alpha_meas)
            self.delta_ref = self.body2delta()           
            self.delta_sp = self.body2delta()            
            self.alpha_ref = self.alpha_meas
            self.alpha_sp = self.alpha_meas                  # in case we switch to AUTO
            self.alpha_offst = np.array([0,0,0],dtype=float) # in case we switch to AUTO
        
        elif self.mode == 'AUTO':
            self.delta_offst = clamp_delta(self.delta_offst + self.dt * self.delta_v_sp)
            self.delta_ref = clamp_delta(self.delta_sp + self.delta_offst)
            self.delta2body(self.delta_ref)
            # when in AUTO ignore body, and use the alpha_sp + alpha_offset
            self.alpha_offst = clamp_alpha(self.alpha_offst + self.dt * self.alpha_v_sp)
            self.alpha_ref = clamp_alpha(self.alpha_sp + self.alpha_offst)

        elif self.mode == 'TRACK':
            self.delta_offst = clamp_delta(self.delta_offst + self.dt * self.delta_v_sp)
            self.delta_ref_last = self.delta_ref
            self.delta_ref = clamp_delta(self.delta_sp + self.delta_offst)
            self.delta2body(self.delta_ref)
            self.alpha_ref = self.body2alpha()
            self.alpha_sp = self.alpha_meas             # in case we switch to AUTO

        # Convert alpha_ref to theta_ref
        q1 = angles_to_quaternion(*self.alpha_ref)
        theta1,theta2,theta3,_,_,_ = quaternion_to_angles(q1)
        self.theta_ref_last = self.theta_ref
        self.theta_ref = np.array([theta1,theta2,theta3])
    
    def measure(self, alpha_meas, theta_meas):
        now = ephem.now()
        # if not self.time_meas:
        #     self.alpha_sp = alpha_meas     # initialise alpha_sp with first measurement
        self.alpha_meas = alpha_meas
        self.theta_meas = theta_meas
        self.time_meas = now

    def predict(self):
        self.theta_meas = clamp_theta(self.theta_meas + self.dt * self.omega_op)
        self.time_meas = self.time_meas + self.dt

    def errsignal(self):
        old_error_signal = self.error_signal
        self.error_signal = clamp_error(self.theta_ref, self.theta_meas)
        self.error_integral = old_error_signal + self.error_signal
        self.cost_signal = np.sum(self.error_signal ** 2)
        self.is_deviating = self.cost_signal > (self.Kc / 60) ** 2
        self.is_slewing = np.any(self.alpha_v_sp != 0) or np.any(self.delta_v_sp != 0)
        self.was_moving = self.is_moving
        self.is_moving = self.is_deviating or self.is_slewing or self.mode=="TRACK"
        if not self.is_moving and self.mode=='AUTO':
            self.set_pid_mode('IDLE')
    
    def pid(self):
        self.omega_tgt = self.Kp * self.error_signal + self.Ki * self.error_integral - self.Kd * self.omega_op

    def feed_forward(self):
        # Feed forward tracking velocities (when in track mode and no delta_ref change)
        self.omega_ref = np.array([0,0,0], dtype=float)
        if self.mode == "TRACK":
            delta_ref_change = self.delta_ref - self.delta_ref_last
            delta_ref_nochange = np.sum(delta_ref_change ** 2) < 1e-3
            if delta_ref_nochange and self.dt > 0:
                tracking_vel = clamp_error(self.theta_ref, self.theta_ref_last) / self.dt
                self.omega_ref = tracking_vel
        # Feed forward slew velocities when in auto mode
        elif self.mode == "AUTO":
            self.omega_ref = self.alpha_v_sp
        self.omega_tgt += self.omega_ref

    def constrain(self):
        # Compute constrained acceleration
        accel_clipped = np.array([0, 0, 0], dtype=float)
        if self.dt > 0:
            delta_omega = self.omega_tgt - self.omega_op
            accel = delta_omega / self.dt
            accel_clipped = np.clip(accel, -self.Ka, self.Ka)
        # Apply clipped acceleration, expotential smoothing, and clip velocity
        self.omega_ctl = self.omega_op + accel_clipped * self.dt
        self.omega_ctl = self.omega_ctl * (1.0 - self.Ke) + self.Ke * self.omega_op
        self.omega_ctl = np.clip(self.omega_ctl, -self.Kv, self.Kv)

    async def control(self):
        self.omega_op = np.array([0,0,0], dtype=float)
        # [0.0, 0.0059018, 0.0175906, 0.0478282, 0.0892742, 0.2079884]
        for axis in range(3):
            self.omega_op[axis] = self.omega_ctl[axis]
            raw = self.controllers[axis]._model.DPS.toRAW(self.omega_ctl[axis])
            if abs(raw) < 5.5:
                raw = round(raw,0)  # no fractional SLOW commands
                self.omega_op[axis] = self.controllers[axis]._model.RAW.toDPS(raw)
        # send control to motor when moving
        if self.is_moving and self.mode in ['AUTO', 'TRACK']:
            for axis in range(3):
                await self.controllers[axis].set_motor_speed(self.omega_op[axis], rate_unit='DPS', ramp_duration=self.dt, allow_PWM=False)
        # Stop motors when transitioning from moving to stopped
        if self.was_moving and not self.is_moving:
            for axis in range(3):
                await self.controllers[axis].set_motor_speed(0)

    def notify(self):
        if not self.is_deviating and self.goto_complete_callback:
            self.goto_complete_callback()
            self.goto_complete_callback = None

    async def control_step(self):
        now = time.monotonic()
        if self.control_loop_duration:
            self.dt = now - self.time_step
        self.time_step = now
        if self.time_meas:      # Only process if we have a measurement
            self.track_target() # Update theta_ref with target's new position
            self.errsignal()    # Update error_signal/integral with deviation from theta_ref
            self.pid()          # Update omega_tgt, calculate raw PID control target
            self.feed_forward() # Feed forward tracking velocities when in TRACK mode
            self.constrain()    # Update omega_ctl, constrain velocity and acceleration
            await self.control()      # Update omega_op, constrain with valid op control values
            self.notify()       # Notify any callback of no longer deviating
            if Config.log_performance_data==6:
                self.logger.info(f',"DATA6", "{self.mode}",  { fmt3(self.delta_ref)},  {fmt3(self.alpha_ref)},  {fmt3(self.theta_ref)},  {fmt3(self.theta_meas)},  {fmt3(self.omega_ref)},  {fmt3(self.omega_op)}')


    async def _control_loop(self):
        while not self._stop_flag.is_set():
            # self.measure() is done at processing 518 message
            await self.control_step()
            await asyncio.sleep(self.control_loop_duration)

    async def stop_control_loop_task(self):
        async with self._lock:
            self._stop_flag.set()

