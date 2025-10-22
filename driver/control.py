import numpy as np
import datetime
import json, os
import logging
from pathlib import Path
from pyquaternion import Quaternion
from config import Config
from scipy.interpolate import PchipInterpolator
from scipy.optimize import minimize
import time
import asyncio
from typing import Optional
import ephem
import math
import copy
from shr import rad2deg, deg2rad, rad2hms, deg2dms, format_timestamp
from threading import Lock

# ************* TODO LIST *****************
#
# Alpaca Pilot App
# [X] Implement Alpaca Pilot App Framework
# [X] Implement Alpaca Pilot sidebar menu and toolbar menu
# [X] Implment Alpaca Pilot routing
#
# Alpaca Pilot Connection, Bluetooth LE
# [X] Implement Benro Polaris Connection process and diagnostics
# [X] Connect to Benro Polaris without the Benro App
# [X] Use BT Low Energey to Discover nearby Benro Polaris devices
# [X] Use BT Low Energey to enable Wifi on selected Benro Polaris device
# [X] Show Benro Polaris hardware and firmware versions
# [X] Allow change Polaris Mode to Astro
# [X] Allow goto Park position from Connection page
# [X] Allow skip Compass and Single Star Alignment using default values
# [X] Alpaca pilot works outside of Astro Mode eg in Photo Mode
#
# Alpaca Pilot Configuration/Setup 
# [X] Setup Dialog in Alpaca Pilot
# [X] Foolproof and Simple observing site lat/lon configuration
# [x] Ability to enable various advanced conrtol features and standard control features
# [X] Ability to save and restore configuration modifications
# [X] Alpaca Pilot Action ConfigUpdate pass through to live polaris and pickup from live Polaris eg lat/lon Nina changes
# [X] Alpaca pilot to restrict pid max velocity and accel in real time
# [X] Remove Alpaca Performance Recording Settings
#
# Alpaca Pilot Log 
# [X] Alpaca Pilot Log file viewer and streaming of data over Sockets
# [X] Ability to change Log Level and Log Settings
# [X] Rationalise loggin across alpaca, polaris, discovery, synscan, bluetooth protocols
# [X] Fix sizing of log scrolling window
#
# Alpaca Pilot Dashboard Features
# [X] Alpaca Pilot Radial Indicators
# [X] Alpaca pilot goto Az, Alt, Roll with click on Radial Scale or Radial Labels
# [X] Alpaca pilot goto RA, Dec, PA with click on Radial Scale or Radial Labels
# [X] Alpaca pilot floating action buttons for quick axis settings (az, alt, roll)
# [X] Alpaca pilot radial scales to show warning limits on angles
# [X] Alpaca Pilot SP pointer is removed around +/- 90 degrees too early
# [X] Alpaca Pilot Radial Scale PVtoSP can arc the wrong way when around 360/0 wraparound
# [X] Alpaca Pilot Home dashboard
# [X] Alpaca pilot current position main display
# [X] Alpaca Pilot is parked, is tracking, is slewing, is gotoing, is PID active, is Pulse Guiding
# [X] Alpaca pilot commands for Eq-Az toggle, park, unpark, abort, track, tracking rate
# [X] Indicate speed on Alpaca Dashboard
# [X] Indicate motor activity on Alpaca Dashboard
# [X] Alpaca pilot manual slew AltAzRoll, slew rate
# [X] Alpaca pilot manual slew RADecPA
# [X] Fix Position Angle dashboard
# [X] Fix Position Angle interaction
# [ ] Fix Az/Alt/Roll interaction while tracking
#
# Alpaca Pilot Tuning
# [X] Alpaca Pilot KF Tuning page
# [X] Alpaca Pilot PWM Testing page
# [X] Alpaca Improved PWM_SLOW with (-1, +1) rate instead of 0
# [X] Alpaca Pilot Speed Calibration Test Management and Actions
# [X] Alpaca Pilot Speed Calibration hookup and cancel test
# [X] Alpaca Pilot Position Diagnostics Page
# [ ] Alpaca Pilot PID Tuning page
# [ ] Fix chart sizing when screen resized
#
# Alpaca Single-Point and Multi-Point Alignment
# [X] Alpaca pilot Single-Point Alignment using Polaris internal model
# [X] Alpaca pilot Multi-Point Alignment using QUEST modeling
# [X] Alpaca pilot SYNC with RA/Dec and Az/Alt co-ordinates
# [X] Alpaca pilot SYNC with landmark on map
# [X] Alpaca pilot Sync Analysis and Residual display
# [X] Alpaca pilot Sync editing and removal
# [X] Alpaca pilot Tripod Level Correction
# [x] Alpaca near Zenith (18° circle) tracking and gotoing by tilting mount  
# [ ] Fix Reduce number of Nina plate-solve and sync to get to target
# [ ] Fix SYNC events are not cleared in client after driver restart
#
# Alpaca Speed Control
# [X] Refactor low level SLOW and FAST speed controler
# [X] Implement reliable PWM control over +1 to -1 SLOW Speed
# [X] Allow first SLOW speed 0 through (dont assume it was 0)
# 
# Alpaca Kinematics
# [X] Build comprehensive test suite for Kinematics calculations
# [X] Fix quaternian maths when alt is negative and zero
# [X] Fix 340-360 Control Kinematics, note roll flips sign near N when KF enabled
# [X] Fix Alt 0 Control Kinematics, theta1/theta3 spin at 180, maintain mechnical position
# [X] Add Anti-Windup Motor Angle Limits
# [ ] Fix zero Altitude movement
# [ ] Improve motor limits indication and safety protection (including with tilts)
#
# Alpaca Kalman Filter
# [X] Implment Kalman Filter to improve reliabilty of state assessment
# [X] Alpaca pilot Ability to optionally use KF
# [X] Introduce a Low-Pass Filter on Omega Output (aready doing this I think)
#
# Alpaca PID Control
# [X] Implement PID control loop
# [X] Stop PID and Motor controllers on shutdown
# [X] Implement TRACK mode
# [X] Implement slewing and gotoing state monitoring
# [X] Ensure polaris tracking is off when enabling advanced tracked
# [X] Alpaca Pilot Speed control for 0 while tracking should remain in PWM_SLOW not SLOW
# [X] Enabling tracking mid GOTO should use SP as target, not current pos
# [X] Fix bug tracking on, off, on - rotates at a faster rate
# [X] Fix delta_ref3 should represent equatorial angle (no change when tracking), alpha_ref desired camera roll angle +ve CCW, 0=horz (changes when tracking)
# [X] Add DATA6 for PID debugging
# [x] Overlay the expected tracking velocity on the omega plot
# [X] Improve responsiveness of manual slewing, incorporate desired velocity into omega_op
# [X] Explicit pid mode changes, add a 'PARK' mode, ensure no pid activity while parked.
#
# Reliability and degrdation
# [X] Proper task cleanup in polaris.restart(), especially to fix no position updates for over 2s. Restarting AHRS
# [X] Fix when Pilot left behind other window, and Chrome hangs
# [X] Alpaca Pilot close inactive websocket clients
# [X] Alpaca pilot feature degredation when not in Advanced Control
# [X] Alpaca pilot feature degredation when no Multi-Point Alignment
# [X] Alpaca pilot feature degredation when no Rotator
# [X] Alpaca pilot feature degredation when no Bluetooth
# [ ] Alpaca pilot feature degredation when not ABP Driver
# [ ] Alpaca pilot works without the third axis Astro Module Hardware (adjust Az/Alt)
# [ ] Alpaca Pilot memory and logevity tests
# 
# Documentation
# [ ] Documentation on new features Topocentric tracking
# [ ] Youtube training videos
# [ ] Kickstarter project
#
# Performance
# [X] Improve fine grained tracking precision
# [X] Improve Kalman Filter tuning
# [X] Store Motor Calibration data to a file
# [X] Improve tracking performance beyond BP implementation
# [ ] Move performance tests to actions
# [ ] Rationalise performance data capture and analysis
# [ ] Move image culling to Alpaca Pilot
#
# ASCOM Rotator
# [X] Implement Rotator
# [X] Rotator Halt, Sync, Reverse, Move(relative), MoveAbs, MoveMech, Position(PA), TargetPosition(PA)
# [X] Pass ConformU test on Rotator
# [X] Pass ConformU test on Telescope
#
# ASCOM Park and Home
# [X] Add ASCOM FindHome command, and expose in Alpaca Pilot, use true Home co-ord from zeta
# [X] Add Park and Home to Dashboard
# [ ] Change ASCOM Park to true custom Park position, persisted in settings
# [ ] Add ASCOM SetPark command, and expose in Alpaca Pilot 
#
# Catalog
# [X] Expanded Target Catalog (Stars, Nebula, Galaxies, Clusters)
# [X] Alpaca pilot catalog of targets, search, filter, pagination
# [X] Data cleaning and creation pipeline
# [X] Fix RA hrs vs deg, qnotify of goto
# [X] GOTO from catalog
# [X] Sync from catalog
# [X] Calc current Azimuth, Altitude of dso and categorise it for filtering
# [X] Fix filter clear to only clear when filter is already open
# [ ] Add South and North Celestrial Pole
# [ ] Add images of each target
# [ ] Add a details page for each target
# [ ] Tonights Altitude, Proximity
# [ ] Calc Sunset, Sunrise, Naut Set, Naut Rise, Moonrise, MoonSet
# [ ] Catalog Target Info on Dashboard
# [ ] Ability to switch catalogs from settings, revise grouping/sizing of each one
# [ ] Favorite Targets to Search Home page
# [ ] Auto-fetch orbital elements
#
# Orbitals
# [ ] Implement Lunar Tracking rate
# [ ] Implement Solar Tracking rate
# [ ] Implement King Tracking rate
# [ ] Implement Pulse Guiding API ITelescope Pulse 
# [ ] Check Astro head hardware connection
# [ ] Integral Anti-Windup dontaccumulate when output is saturated or quantized
# 
# Precision Tracking
# [X] Deep-Sky Object Tracking 
# [X] Seamless Axis Override During Tracking
# [ ] Selenographic Lunar Tracking 
# [ ] Planetary and Orbital Moons Tracking
# [ ] Commet and Asteroid Tracking
# [ ] Satelite Tracking via TLE (Two Line Element)
# [ ] Solar Tracking 
# [ ] Transiting Exoplanet Support
#
# Pulse Guiding Features
# [X] ASCOM Telescope Pulse Guide API Support
# [X] Pulse Guiding Tracking correction 
# [X] Enable Nina Dithering via Nina Direct Guider and Advanced Schedule (uses Pulse Guide API)
# [X] Guide Camera Support via PHD2
# [X] PHD2 Support via ASCOM/Alpaca
# [ ] Allow setting of guiderates 0.5x 1.0x 1.5x 2.0x in Settings of Alpaca Pilot
#
# Imaging and User Experience Enhancements
# [X] Long Exposure Tracking Stabilization
# [X] Automated Leveling Compensation
# [X] Zenith Imaging Support (18° Circle)
# [X] Drift supression and Auto-Centering
# [X] Dithering support
# [X] Mosaic imaging support through Nina

# Candidate future enhancements
# [X] Feedforward Control Integration (minimise overshoot)
# [ ] Rate Derivative Estimation (Jerk Monitoring)
# [ ] Control Mode Switching
# [ ] Time-Differentiated Tracking Profiles
# [ ] Predictive Anti-Backlash Correction
#

DRIVER_DIR = Path(__file__).resolve().parent      # Get the path to the current script (control.py)
DATA_DIR = DRIVER_DIR.parent / 'data'             # Default data directory: ../data 
CALIBRATION_PATH = DATA_DIR / 'speed_calibration.json'
TESTDATA_PATH = DATA_DIR / 'speed_testdata.json'


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
    wrapped = angle % 360.0
    # --- Handle a weird rounding problem for tests, ensure 359.9999999994 is 0.0 and not 360
    return 0.0 if abs(wrapped - 360) < 1e-10 else wrapped

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

def calc_parallactic_angle(az_deg, alt_deg, lat_deg):
    if abs(alt_deg - 90.0) < 1e-6:
        return 0.0  # Zenith has no parallactic angle

    az = math.radians(az_deg)
    alt = math.radians(alt_deg)
    lat = math.radians(lat_deg)

    numerator = math.sin(az)
    denominator = math.tan(lat) * math.cos(alt) - math.sin(alt) * math.cos(az)
    angle = math.degrees(math.atan2(numerator, denominator))
    return wrap_to_180(-angle)


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



def angles_to_quaternion(az, alt, roll):
    """
    Convert altitude, azimuth, and roll angles to a quaternion using simple rotation composition.
    
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
    q1 = qaz * qalt * qroll  # Reconstructed q1 quaternion from roll, then alt, then az
    
    return -(q1.normalised) if roll < 0 else q1.normalised



def motors_to_quaternion(theta1, theta2, theta3):
    """
    Convert theta1, theta2, theta3 angles to a quaternion using simple rotation composition.
    
    Args:
        theta1: Polaris Axis 1 angle in degrees [0-360) +ve=cw (looking down towards mount, 0=North)
        theta2: Polaris Axis 2 angle in degrees (-90 to +90) +ve=upwards (looking side on to mount, 0=Horizontal)
        theta3: Polaris Axis 3 angle in degrees (-180 to +180) +ve=cw (looking down towards mount. 0=Level)
    
    Returns:
        # q1 rotates from camera frame (-z = boresight, +x = up, +y = left) to topocentric frame (+z = Zenith, +y = North, +x = East)
    """
    # Reconstructing q1 from theta1, theta2, theta3
    qtheta1 = Quaternion(axis=[0, 0, 1], degrees= -theta1 + 90)                      # Spin camera around vertical
    qtheta2 = Quaternion(axis=[0, 1, 0], degrees= -theta2 - 90)                      # Tilt camera up/down
    qtheta3 = Quaternion(axis=(qtheta1*qtheta2).rotate([1, 0, 0]), degrees= -theta3) # Pan camera left/right
    q1 = qtheta3 * qtheta1 * qtheta2   # Reconstructed q1 quaternion from tilt then pan then spin
    noflip = theta3 < 0
    q1n = q1.normalised if noflip else -q1.normalised
    return q1n

def extract_theta_given_theta3(tUp, tBore, theta3):
    """ Calc Theta1 and Theta2 based on removing Theta3 pan """
    unTheta3Pan = Quaternion(axis=tUp, degrees= -theta3).inverse             # Undo Theta3 rotation to get cleaned bore vector 
    mBore = unTheta3Pan.rotate(tBore)                                        # mBore is the Camera optical axis if we removed the Astro Module effect
    theta1 = wrap_to_360(np.degrees(np.arctan2(mBore[0], mBore[1])))
    theta2 = wrap_to_90(np.degrees(np.arcsin(np.clip(mBore[2], -1.0, 1.0))))
    return theta1, theta2, wrap_to_180(theta3)

class LastPosition:
    def __init__(self, t1=180, t2=45, t3=0):
        self.last_theta1 = t1
        self.last_theta2 = t2
        self.last_theta3 = t3
    def update(self,t1,t2,t3):
        self.last_theta1 = t1
        self.last_theta2 = t2
        self.last_theta3 = t3
    def calcMechanicalAngularDiff(self,t1,t2,t3):
        dt1 = angular_difference(t1, self.last_theta1)
        dt2 = angular_difference(t2, self.last_theta2)
        dt3 = angular_difference(t3, self.last_theta3)
        return dt1*dt1 + dt2*dt2 + dt3*dt3
_lp = LastPosition()

def quaternion_to_motors(q1, theta1Hint=None, lastPos=None):
    """ Convert quaternion to Theta1, Theta2, Theta3 motor positions using quaternion decomposition """
    global _lp
    if lastPos is None:
        lastPos = _lp

    # --- Camera Up and Boresight vector in topo frame
    tUp = q1.rotate(np.array([1, 0, 0]))
    tBore = q1.rotate(np.array([0, 0, -1]))

    # --- Theta3: rotation around Camera up axis in topocentric frame (Polaris Axis 3) ---
    q4 = q1 * Quaternion(axis=np.array([1, 0, 0]), degrees=180) 
    theta3 = -np.degrees(np.arctan2(2 * (q4[0]*q4[1] + q4[2]*q4[3]), q4[0]**2 - q4[1]**2 - q4[2]**2 + q4[3]**2))

    # --- Find the two solutions based on theta3 being pointing one way or the opposite
    theta1_A, theta2_A, theta3_A = extract_theta_given_theta3(tUp, tBore, theta3)
    theta1_B, theta2_B, theta3_B = extract_theta_given_theta3(tUp, tBore, theta3 - 180)

    # Choose the best mechnical solution
    if theta2_A < -8:           # Rules out Solution A
        [theta1, theta2, theta3] = [theta1_B, theta2_B, theta3_B]
    elif theta2_B < -8:         # Rules out Solution B
        [theta1, theta2, theta3] = [theta1_A, theta2_A, theta3_A]
    else:                       # --- Choose the solution closest to the last mechnical position
        diffA = lastPos.calcMechanicalAngularDiff(theta1_A, theta2_A, theta3_A,)
        diffB = lastPos.calcMechanicalAngularDiff(theta1_B, theta2_B, theta3_B,)
        [theta1, theta2, theta3] = [theta1_A, theta2_A, theta3_A] if diffA<diffB else [theta1_B, theta2_B, theta3_B]
    lastPos.update(theta1, theta2, theta3)

    # --- Handle the case where we have a gimbal lock at Alt = 0, ie t1/t3 in gimbal lock
    alt = np.degrees(np.arcsin(np.clip(tBore[2], -1.0, 1.0)))           # Altitude = Angle from N/E plane, vertically to the Boresight axis
    if abs(alt) < 1e-10 and theta1Hint is not None:
        diffC = angular_difference(theta1, theta1Hint)
        theta1 = wrap_to_360(theta1Hint)
        theta3 = wrap_to_180(theta3 - diffC)

    return theta1, theta2, theta3


def quaternion_to_angles(q1, azhint=None, lastPos = None):
    """
    Convert a quaternion to theta1, theta2, theta3, altitude, azimuth, and roll angles.
    
    Args:
        q1: Quaternion that rotates from camera frame to topocentric frame
            Camera frame: -z = boresight, +x = up, +y = left
            Topocentric frame: +z = Zenith, +y = North, +x = East
        lastPos: last mechnical position (LastPosition object)
    
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

    # calculate the motor angles from the quaternion
    theta1, theta2, theta3 = quaternion_to_motors(q1, lastPos=lastPos)

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
        self.K = np.zeros((6, 6))

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


    def observe(self, theta, omega, omega_ref):
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
        self.K = self.P @ self.H.T @ np.linalg.inv(S)

        self.x = self.x + self.K @ y
        self.P = (self.I - self.K @ self.H) @ self.P
        self.x = wrap_state_angles(self.x)

        # Log meas, state and ref for websocket streaming
        payload = { 
            "θ_meas":  theta_meas.flatten().tolist(), 
            "θ_state": self.x[:3].flatten().tolist(), 
            "K_gain":  np.diag(self.K).tolist(),
            "ω_meas":  omega_meas.flatten().tolist(), 
            "ω_state": self.x[3:].flatten().tolist(), 
            "ω_ref":   omega_ref.tolist(),  
        }
        kflogger = logging.getLogger('kf') 
        kflogger.info(payload)


    def get_state(self):
        state = self.x.flatten()
        theta = state[0:3]
        omega = state[3:]
        return theta, omega

    def set_state(self, x):
        self.x = np.array(x).reshape(6, 1)

    def set_theta_state(self, theta_state):
        theta_state = np.array(theta_state).reshape(3, 1)
        if self.x is None or self.x.shape != (6, 1):
            self.x = np.zeros((6, 1))
        self.x[:3] = theta_state


# ************* Calibration Manager ************
class CalibrationManager:
    def __init__(self, liveInstance=True):
        self.liveInstance = liveInstance        # False = used for unit testing purposes
        self.raw_rates = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0] 
        self.raw_rates += [0.0] + [x for x in range(200,500,100)] + [x for x in range(500,2500+250,250)]
        self.baseline_data = {
            0: {
                "RAW":   [        0.0,        0.5,        1.0,        1.5,        2.0,        2.5,        3.0,        3.5,        4.0,        4.5,        5.0,        0.0,      200.0,      300.0,      400.0,      500.0,      750.0,     1000.0,     1250.0,     1500.0,     1750.0,     2000.0,     2250.0,     2500.0 ],
                "DPS":   [  0.0000000,  0.0028021,  0.0060228,  0.0118625,  0.0178193,  0.0325911,  0.0475504,  0.0682790,  0.0890018,  0.1494888,  0.2081359,  0.0000000,  0.0856123,  0.1956495,  0.3488612,  0.5493848,  1.0887906,  1.7124653,  2.5596667,  3.4889146,  4.6249466,  5.8937798,  7.3677819,  8.9185931 ],
                "ASCOM": [  0.0000000,  0.5000000,  1.0000000,  1.5000000,  2.0000000,  2.5000000,  3.0000000,  3.5000000,  4.0000000,  4.5000000,  5.0000000,  0.0000000,  5.1284937,  5.3007042,  5.5095365,  5.6867827,  5.8739240,  6.1311617,  6.4341598,  6.7568192,  7.2206272,  7.8160615,  8.5247481,  9.0000000 ]
            },
            1: {
                "RAW":   [        0.0,        0.5,        1.0,        1.5,        2.0,        2.5,        3.0,        3.5,        4.0,        4.5,        5.0,        0.0,      200.0,      300.0,      400.0,      500.0,      750.0,     1000.0,     1250.0,     1500.0,     1750.0,     2000.0,     2250.0,     2500.0 ],
                "DPS":   [  0.0000000,  0.0027828,  0.0061134,  0.0118115,  0.0179306,  0.0329477,  0.0474911,  0.0678652,  0.0892049,  0.1490858,  0.2079325,  0.0000000,  0.0624035,  0.1550967,  0.2818549,  0.4429422,  0.9865743,  1.5764286,  2.2335193,  3.0316268,  3.9409350,  5.0398936,  6.2998655,  7.6626160 ],
                "ASCOM": [  0.0000000,  0.5000000,  1.0000000,  1.5000000,  2.0000000,  2.5000000,  3.0000000,  3.5000000,  4.0000000,  4.5000000,  5.0000000,  0.0000000,  5.0701129,  5.2593430,  5.4397258,  5.6204410,  5.8704272,  6.0775486,  6.3777151,  6.6626556,  7.0344015,  7.7582774,  8.1985778,  9.0000000 ]
            },
            2: {
                "RAW":   [        0.0,        0.5,        1.0,        1.5,        2.0,        2.5,        3.0,        3.5,        4.0,        4.5,        5.0,        0.0,      200.0,      300.0,      400.0,      500.0,      750.0,     1000.0,     1250.0,     1500.0,     1750.0,     2000.0,     2250.0,     2500.0 ],
                "DPS":   [  0.0000000,  0.0025771,  0.0060485,  0.0116477,  0.0178566,  0.0331094,  0.0477487,  0.0681221,  0.0896771,  0.1484604,  0.2090765,  0.0000000,  0.0710666,  0.1906350,  0.2917780,  0.4614574,  1.0211624,  1.6094697,  2.2771888,  3.1632519,  4.1730833,  5.3294800,  6.5653307,  7.9927540 ],
                "ASCOM": [  0.0000000,  0.5000000,  1.0000000,  1.5000000,  2.0000000,  2.5000000,  3.0000000,  3.5000000,  4.0000000,  4.5000000,  5.0000000,  0.0000000,  5.1059046,  5.2953173,  5.4563247,  5.6045402,  5.8719654,  6.0894325,  6.3677080,  6.6855091,  7.0802587,  7.5992287,  8.2492810,  9.0000000 ]
            },
        }
        self.test_data = {}
        self.calibration_data = {}
        self.interpolator_data = {0:{}, 1:{}, 2:{}}
        if self.liveInstance:
            self.initialiseCalibrationData()

    def initialiseCalibrationData(self):
        if not self.loadTestDataFromFile():
            self.createTestDataFromBaseline()
        self.updateCalibrationAndInterpolators()

    def createTestDataFromBaseline(self):
        self.test_data = {}
        for axis, axisData in self.baseline_data.items():
            for i in range(len(axisData['RAW'])):
                raw = axisData['RAW'][i]
                ascom = axisData['ASCOM'][i]
                dps = axisData['DPS'][i]
                cmd = 'SLOW' if raw<=5 else 'FAST'
                name = f'M{axis+1}-{cmd}-{raw}'
                if not raw==0:
                    self.test_data[name] = dict(
                        name=name, axis=axis, raw=raw, ascom=ascom, dps=dps, 
                        test_result= '', test_change= '', test_stdev= '', test_status= 'UNTESTED')

    def addTestResult(self, axis, raw, result, stdev, status):
        cmd = 'SLOW' if raw<=5 else 'FAST'
        name = f'M{axis+1}-{cmd}-{raw}'
        idxSlow5 = self.baseline_data[axis]['RAW'].index(5) 
        mid = self.baseline_data[axis]['DPS'][idxSlow5]
        max = self.baseline_data[axis]['DPS'][-1]
        interpToASCOM = PchipInterpolator([0, mid, 0.18*max, 0.5*max, max], [0,5,6,7,9], extrapolate=True)
        interpToBaseline = MoveAxisRateUnitInterpolator(self.baseline_data[axis], 'RAW')
        ascom = float(interpToASCOM(result) if raw > 5 else raw)
        dps = float(interpToBaseline.toDPS(raw))
        change = (result/dps - 1) * 100
        status = 'HIGH CHANGE' if abs(change)>25 and status in ['COMPLETED'] else status
        bad_test = status in ['HIGH STDEV', 'HIGH CHANGE', 'NO DATA', 'STOPPED']
        test_result = f'{result:.7f}' if not bad_test else ''
        test_change = f'{change:.2f}%'
        test_stdev = f'{stdev:.7f}'
        test_status = status
        self.test_data[name] = dict(
            name=name, axis=axis, raw=raw, ascom=ascom, dps=dps, 
            test_result= test_result, test_change= test_change, test_stdev= test_stdev, test_status= test_status)
        if self.liveInstance:
            self.logTestData([name])
            self.saveTestDataToFile()

    def stopTests(self):
        testNameList = self.test_data.keys()
        for testName in testNameList:
            testData = self.test_data.get(testName, {})
            if testData and testData.get('test_status')=='PENDING':
                self.test_data[testName]['test_status'] = 'STOPPED'
                self.test_data[testName]['test_result'] = ''
                self.test_data[testName]['test_change'] = ''
                self.test_data[testName]['test_stdev'] = ''
        if self.liveInstance:
            self.logTestData(testNameList)


    def pendingTests(self, axis, testNameList):
        if not testNameList:
            testNameList = self.test_data.keys()
        tests=[]
        for testName in testNameList:
            testData = self.test_data.get(testName, {})
            if testData and testData.get('axis')==axis:
                self.test_data[testName]['test_status'] = 'PENDING'
                self.test_data[testName]['test_result'] = ''
                self.test_data[testName]['test_change'] = ''
                self.test_data[testName]['test_stdev'] = ''
                raw = testData.get('raw',0)
                tests.append(raw)
        if self.liveInstance:
            self.logTestData(testNameList)
        return tests

    def approveTests(self, testNameList):
        if not testNameList:
            testNameList = self.test_data.keys()
        for testName in testNameList:
            testData = self.test_data.get(testName, {})
            status = testData.get('test_status','')
            if status in ['COMPLETED', 'REJECTED']:
                self.test_data[testName]['test_status'] = 'APPROVED'
        if self.liveInstance:
            self.logTestData(testNameList)
            self.updateCalibrationAndInterpolators()

    def rejectTests(self, testNameList):
        if not testNameList:
            testNameList = self.test_data.keys()
        for testName in testNameList:
            testData = self.test_data.get(testName, {})
            status = testData.get('test_status','')
            if status in ['COMPLETED', 'APPROVED']:
                self.test_data[testName]['test_status'] = 'REJECTED'
        if self.liveInstance:
            self.logTestData(testNameList)
            self.updateCalibrationAndInterpolators()

    def toggleApproval(self, axis, testNameList):
        if not testNameList:
            testNameList = self.test_data.keys()
        for testName in testNameList:
            testData = self.test_data.get(testName, {})
            if testData and testData.get('axis')==axis:
                status = testData.get('test_status','')
                if status in ['COMPLETED', 'REJECTED']:
                    self.test_data[testName]['test_status'] = 'APPROVED'
                elif status in ['APPROVED']:
                    self.test_data[testName]['test_status'] = 'REJECTED'
        if self.liveInstance:
            self.logTestData(testNameList)
            self.updateCalibrationAndInterpolators()

    def logTestData(self, testNameList):
        cm_logger = logging.getLogger('cm')
        if not testNameList:
            testNameList = self.test_data.keys()
        for testName in testNameList:
            testData = self.test_data.get(testName, {})
            cm_logger.info(testData)

    def updateCalibrationAndInterpolators(self):
        self.generateCalibrationFromBaselineAndTestData()
        self.generateInterpolatorsFromCalibrationData()
        self.saveCalibrationDataToFile()
        self.saveTestDataToFile()

    def generateCalibrationFromBaselineAndTestData(self):
        self.calibration_data = copy.deepcopy(self.baseline_data)
        for testName in self.test_data.keys():
            if self.test_data[testName].get('test_status','')=='APPROVED':
                axis = self.test_data[testName].get('axis',0)
                raw = self.test_data[testName].get('raw',0)
                dps = float(self.test_data[testName].get('test_result',0))
                try:
                    idx = self.calibration_data[axis]['RAW'].index(raw)
                    self.calibration_data[axis]['DPS'][idx] = dps
                except ValueError:
                    continue

    def generateInterpolatorsFromCalibrationData(self):
        self.interpolator_data = {
            axis: MoveAxisRateInterpolator(self.calibration_data[axis])
            for axis in range(3)
        }

    def formatCalibrationData(self, col_width=10):
        begin = '{\n"_comment": "Copy of consolidated calibration data overriden with approved test data."\n'
        output_lines = []
        for axis, axis_data in self.calibration_data.items():
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
                formatted_key = f'{key:7s}'
                output_lines.append(f'    "{formatted_key}": [ {value_str} ]{comma}')
            output_lines.append("},")  # End of axis block with trailing comma
        return begin + '\n'.join(output_lines) + '\n}\n'

    def ensure_data_dir_exists(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def saveCalibrationDataToFile(self, path = CALIBRATION_PATH):
        self.ensure_data_dir_exists()
        with open(path, 'w') as f:
            f.write(self.formatCalibrationData())

    def saveTestDataToFile(self, path = TESTDATA_PATH):
        self.ensure_data_dir_exists()
        with open(path, 'w') as f:
            json.dump(self.test_data, f, indent=2)

    def loadTestDataFromFile(self, path = TESTDATA_PATH):
        if os.path.exists(path):
            with open(path, 'r') as f:
                self.test_data = json.load(f)
            return True
        else:
            return False



# ************* MoveAxis Rate Interpolation *************

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
    def __init__(self, logger, cm:CalibrationManager, axis:int, send_msg):
        self.axis = axis
        self._logger = logger
        self._calibration_manager = cm
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

    @property
    def _model(self):
        return self._calibration_manager.interpolator_data[self.axis]

    async def set_motor_speed(self, rate, rate_unit="DPS", ramp_duration=None, allow_PWM=True, tracking=False):
        async with self._lock:
            if not rate_unit in ['RAW', 'DPS', 'ASCOM']:
                self._logger.info(f'Set Motor Speed - Invalid units {rate_unit}')
                return
            raw = self._model.interpolate[rate_unit].toRAW(rate)
            now = time.monotonic()
            # if we get too many updates before they are applied, just overwrite the last one
            self.pending_update = (float(raw), ramp_duration, allow_PWM, tracking, now)

    def _apply_pending_update(self, now):
        if not self.pending_update:
            return
        
        if self.mode == "SLOW_PWM" and now < self.next_dispatch_time:
            return

        # Apply new rate and update state for dispatch to take over
        new_raw, ramp_duration, allow_PWM, tracking, update_time = self.pending_update
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
            elif (duty == 0 or base == next_up) and not (base==0 and tracking):
                self.mode = "SLOW"
                self.command = base
            elif interp > 1:
                self.mode = "SLOW_PWM"
                self.command = (base, next_up)
                self.duty_cycle = duty
            else:
                self.mode = "SLOW_PWM"
                self.command = (-1, +1)               # dont use 0 as it disengages torque
                self.duty_cycle = (new_raw + 1.0)/2   # -1=>0, -0.5=>0.25 0=>0.5, +0.5=>0.75 +1=>1.0
            # self._logger.info(f'apply {self.mode}, {self.rate_dps}, {self.command}, {self.duty_cycle}  ')


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
                    was_on = self.pwm_phase == "ON"
                    pwm_rate = base if was_on else next_up
                    duration = 0.5 * (1 - self.duty_cycle if was_on else self.duty_cycle)
                    await self._messenger.send_slow_move_msg(pwm_rate)
                    # self._logger.info(f"Motor {self.axis} PWM phase: {self.pwm_phase}, rate: {pwm_rate}, duration: {duration:.2f}s")
                    self.pwm_phase = "OFF" if was_on else "ON"
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
    def __init__(self, logger, polaris, dt=0.2, Kp=0.8, Ki=0.0, Kd=0.8, Ke=0.4, Kc=1.0, loop=None):
        self._stop_flag = asyncio.Event()                    # Used to flag control loop to stop
        self._lock = Lock()                                  # Used to ensure no threading issues
        self.logger = logger                                 # Logging utility
        self.polaris = polaris                               # Only used for guiding clacs and flaging
        self.controllers = polaris._motors                   # Motor speed controllers[0,1,2]
        self.observer = polaris._observer                    # Observing object from ephem
        self.body = ephem.FixedBody()                        # Target body
        self.body._epoch = ephem.J2000                       # default to J2000 epoch
        self.body_pa_offset = 0                              # used to store body pa to oconvert back to roll
        self.control_loop_duration = loop                    # PID Control Loop duration in seconds
        self.mode = 'PRESETUP'                               # PID Controller mode: PARK, IDLE, AUTO, TRACK, PRESETUP, LIMIT
        self.ack_limit_timestamp = None                      # Timestamp of last ACK of PID LIMIT ALARM
        self.target_type = 'NONE'                            # target body we are tracking
        self.delta_sp = np.array([0,0,0], dtype=float)       # Setpoint for ra, dec, polar anglular positions
        self.alpha_sp = np.array([0,0,0], dtype=float)       # Setpoint for az, alt, roll angular positions
        self.delta_meas = np.array([0,0,0], dtype=float)     # ra, dec, polar measured angular position
        self.alpha_meas = np.array([0,0,0], dtype=float)     # az, alt, roll measured angular position
        self.theta_meas = np.array([0,0,0], dtype=float)     # theta1-3 motor measured angular position
        self.zeta_meas = np.array([0,0,0], dtype=float)      # zeta1-3 motor raw measured angular position (no alignment effect)
        self.delta_ref = np.array([0,0,0], dtype=float)      # ra, dec, polar angular reference position
        self.alpha_ref = np.array([0,0,0], dtype=float)      # az, alt, roll angular reference position
        self.theta_ref = np.array([0,0,0], dtype=float)      # theta1-3 motor reference angular position
        self.zeta_ref = np.array([0,0,0], dtype=float)       # zeta1-3 motor reference angular position (used in PARKING, HOMING)
        self.error_signal = np.array([0,0,0], dtype=float)   # theta1-3 error btw theta_ref and theta_meas
        self.error_integral = np.array([0,0,0], dtype=float) # theta1-3 error btw theta_ref and theta_meas
        self.goto_complete_callback = None                   # callback function when no longer deviating
        self.rotate_complete_callback = None                 # callback function when no longer deviating
        self.slew_complete_callback = None                   # callback function when no longer slewing
        self.parking_complete_callback = None                # callback function when reached parking position
        self.is_deviating = False                            # cost signal is > Kc Arc Minutes²
        self.is_slewing = False                              # a velicity_sp is non-zero
        self.is_tracking = False                             # tracking target body
        self.is_moving = False                               # mount is deviating, slewing or tracking
        self.was_moving = False                              # previous control step movement flag
        self.omega_kp = np.array([0,0,0], dtype=float)       # omega1-3 due to proportional error
        self.omega_ki = np.array([0,0,0], dtype=float)       # omega1-3 due to integrated error
        self.omega_kd = np.array([0,0,0], dtype=float)       # omega1-3 due to velocity damping (derivative of position)
        self.omega_ref = np.array([0,0,0], dtype=float)      # omega1-3 due to requested velocity feed forward (slew, tracking)
        self.omega_min = np.array([0,0,0], dtype=float)      # omega1-3 min allowable angular velocity (0=axis at limit, no more -ve)
        self.omega_max = np.array([0,0,0], dtype=float)      # omega1-3 max allowable angular velocity (0=axis at limit, no more +ve)
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
        
        if self.control_loop_duration:
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
        self.delta_g_sp = np.array([0,0,0], dtype=float)     # Guiderate duration in +/- ms for ra, dec, polar anglular velocities
        self.delta_offst = np.array([0,0,0], dtype=float)    # ra, dec, polar anglular offsets
        self.delta_ref_last = np.array([0,0,0], dtype=float) # ra, dec, polar angular reference position of last control step

    def reset_alpha_offsets(self):
        self.alpha_v_sp = np.array([0,0,0], dtype=float)     # Setpoint for az, alt, roll angular velocities
        self.alpha_offst = np.array([0,0,0], dtype=float)    # az, alt, roll angular offsets

    def reset_theta(self):
        self.theta_ref = np.array([0,0,0], dtype=float)      # theta1-3 motor angular reference position
        self.theta_ref_last = np.array([0,0,0], dtype=float) # theta1-3 motor angular reference position of last control step

    def reset_sp(self):                                      # align all SP with alpha_meas current position
        self.alpha2body(self.alpha_meas)
        self.delta_ref = self.body2delta()           
        self.delta_sp = self.delta_ref            
        self.alpha_ref = self.alpha_meas
        self.alpha_sp = self.alpha_meas                  
        self.reset_offsets() 

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
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        if self.mode=='AUTO':
            track_target = self.alpha_ref.copy()
        else:
            track_target = self.alpha_meas.copy()
        self.reset_offsets()
        self.alpha_sp = track_target
        self.alpha2body(track_target)
        self.delta_sp = self.body2delta()
        self.set_pid_mode('TRACK')
    
    def set_tracking_off(self):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        if self.mode == 'TRACK':
            self.set_pid_mode('AUTO')

    def set_pid_mode(self, newMode):
        if newMode in ['PRESETUP', 'HOMING', 'PARKING', 'PARK', 'IDLE', 'AUTO', 'TRACK', 'LIMIT', ]:
            self.mode = newMode

    def set_no_target(self):
        self.target_type = 'NONE'
        self.reset_offsets()

    def set_alpha_target(self, sp: dict[str, float]):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.reset_offsets()
        self.target_type = 'ALPHA'
        # Safely update alpha_sp components if provided
        self.alpha_sp[0] = sp.get("az", self.alpha_sp[0])
        self.alpha_sp[1] = sp.get("alt", self.alpha_sp[1])
        self.alpha_sp[2] = sp.get("roll", self.alpha_sp[2])
        self.alpha2body(self.alpha_sp)
        self.delta_sp = self.body2delta()
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_alpha_axis_velocity(self, axis, sp=0.0):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.alpha_v_sp[axis] = sp
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_delta_target(self, delta):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.reset_offsets()
        self.target_type = "DELTA"
        self.delta_sp = delta
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_delta_axis_position(self, axis, sp=0.0):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.delta_sp[axis] = sp
        self.delta_v_sp[axis] = 0
        self.delta_offst[axis] = 0
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')
        
    def set_delta_axis_position_relative(self, axis, sp=0.0):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.delta_sp[axis] = self.delta_sp[axis] + sp
        self.delta_v_sp[axis] = 0
        self.delta_offst[axis] = 0
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_delta_axis_velocity(self, axis, sp=0.0):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.delta_v_sp[axis] = sp
        if self.mode in ['IDLE','AUTO']:
            self.set_pid_mode('TRACK')
    
    def pulse_delta_axis(self, direction, duration):
        if self.mode!="TRACK":
            return
        axis = None
        sign = 0
        if direction == 0: axis, sign = 1, +1    # North
        elif direction == 1: axis, sign = 1, -1  # South
        elif direction == 2: axis, sign = 0, +1  # East
        elif direction == 3: axis, sign = 0, -1  # West
        else:
            self.logger.warning(f"Invalid pulse guide direction: {direction}")
            return
        # accumulate the pulse guide durations on the relevant axis
        with self._lock:
            current = self.delta_g_sp[axis]
            proposed = current + sign * duration
            clamped = max(-10_000, min(10_000, proposed))
            self.delta_g_sp[axis] = clamped

    def set_zeta_ref_to_home(self):
        if self.mode in ['PRESETUP']:
            return
        self.reset_offsets()
        self.target_type = "ZETA"
        self.zeta_ref = np.array([0,0,0], dtype=float)

    def set_zeta_ref_to_park(self):
        if self.mode in ['PRESETUP']:
            return
        self.reset_offsets()
        self.target_type = "ZETA"
        self.zeta_ref = np.array([Config.m1_park, Config.m2_park, Config.m3_park], dtype=float)

    def set_TLE_target(self, line1, line2, line3):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.reset_offsets()
        self.target_type = "TLE"
        self.target['lines'] = [line1, line2, line3]
        self.reset_offsets()
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')
    
    def set_XEphem_target(self, line):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.reset_offsets()
        self.target_type = "XEPHEM"
        self.target['line'] = line
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def rotator_move_relative(self, sp=0.0):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
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
              
    def set_rotate_complete_callback(self, fn):
        self.is_deviating = True
        self.rotate_complete_callback = fn
              
    def set_slew_complete_callback(self, fn):
        self.is_slewing = True
        self.slew_complete_callback = fn
              
    def set_parking_complete_callback(self, fn):
        self.parking_complete_callback = fn
              
    def ack_limit_alarm(self):
        self.ack_limit_timestamp = datetime.datetime.now()
        self.set_pid_mode('IDLE')

    #------- Control step functions ---------

    def track_target(self):
        # Update alpha_ref based on current mode
        if self.mode in ['PRESETUP', 'PARKING', 'HOMING', 'PARK', 'LIMIT']:
            self.reset_sp()
        
        elif self.mode in ['IDLE']:
            if (self.alpha_ref[0]==0):                       # only reset sp in special case
                self.reset_sp()
            self.alpha_offst = np.array([0,0,0],dtype=float) # in case we switch to AUTO

        elif self.mode == 'AUTO':
            self.delta_offst = clamp_delta(self.delta_offst + self.dt * self.delta_v_sp)
            self.delta_ref = clamp_delta(self.delta_sp + self.delta_offst)
            self.delta2body(self.delta_ref)
            # when in AUTO ignore body, and use the alpha_sp + alpha_offset
            self.alpha_offst = clamp_alpha(self.alpha_offst + self.dt * self.alpha_v_sp)
            self.alpha_ref = clamp_alpha(self.alpha_sp + self.alpha_offst)

        elif self.mode == 'TRACK':
            # Apply relevant guiderate if delta_g_sp duration is non-zero
            for axis in [0, 1]:  # RA, Dec
                with self._lock:
                    duration = self.delta_g_sp[axis]        # remaining pulse guide duration in ms
                    if duration != 0:
                        sign = np.sign(duration)
                        remaining_ms = abs(duration)
                        step_ms = min(remaining_ms, self.dt * 1000)  # apply only up to what's left
                        step_sec = step_ms / 1000.0
                        velocity = sign * (self.polaris._guideraterightascension if axis == 0 else self.polaris._guideratedeclination)
                        self.delta_offst[axis] += step_sec * velocity
                        self.delta_g_sp[axis] -= sign * step_ms
                        self.delta_g_sp[axis] = int(self.delta_g_sp[axis])  # ensure it's cleanly integral
            if np.all(self.delta_g_sp[:2] == 0):
                with self.polaris._lock:
                    self.polaris._ispulseguiding = False
            # Apply relevant delta slew velocities
            self.delta_offst = clamp_delta(self.delta_offst + self.dt * self.delta_v_sp)
            self.delta_ref_last = self.delta_ref
            self.delta_ref = clamp_delta(self.delta_sp + self.delta_offst)
            self.delta2body(self.delta_ref)
            self.alpha_ref = self.body2alpha()
            self.alpha_sp = self.alpha_meas             # in case we switch to AUTO

        # Convert alpha_ref to theta_ref
        a_az, a_alt, a_roll = self.alpha_ref
        if Config.advanced_rotator and Config.advanced_control:
            a_roll = self.polaris._sm.roll_ascom2polaris(a_roll)

        q1 = angles_to_quaternion(a_az, a_alt, a_roll)

        if Config.advanced_rotator and Config.advanced_control:
            q1 = self.polaris._sm.q1_adj.inverse * q1

        theta1,theta2,theta3,_,_,_ = quaternion_to_angles(q1, azhint=self.alpha_ref[0])
        self.theta_ref_last = self.theta_ref
        self.theta_ref = np.array([theta1,theta2,theta3])
    
    def measure(self, alpha_meas, theta_meas, zeta_meas):
        now = ephem.now()
        # if not self.time_meas:
        #     self.alpha_sp = alpha_meas     # initialise alpha_sp with first measurement
        self.alpha_meas = alpha_meas
        self.theta_meas = theta_meas
        self.zeta_meas = zeta_meas
        self.time_meas = now

    def predict(self):
        self.theta_meas = clamp_theta(self.theta_meas + self.dt * self.omega_op)
        self.time_meas = self.time_meas + self.dt

    def errsignal(self):
        # calc the error signal off theta (1 star aligned motor angles) or zeta (raw motor angles)
        if self.mode in ['HOMING', 'PARKING']:
            self.error_signal = self.zeta_ref - self.zeta_meas
        else:            
            self.error_signal = clamp_error(self.theta_ref, self.theta_meas)
        # calc the integral error
        if self.Ki != 0: 
            i_limit = 5 / self.Ki      # Clamp integral term with anti-windup limit of 5 degrees/s
            can_integrate = (          # Conditional integration
                (self.omega_min <= self.omega_tgt <= self.omega_max) or     # when not saturated
                (np.sign(self.error_signal) != np.sign(self.omega_tgt))     # or when reduces saturation
            )
            if can_integrate:            
                self.error_integral = np.clip(self.error_integral + self.error_signal, -i_limit, +i_limit) 
        # calc cost signal and flags
        self.cost_signal = np.sum(self.error_signal ** 2)
        self.is_deviating = self.cost_signal > (self.Kc / 60) ** 2
        self.is_slewing = np.any(self.alpha_v_sp != 0) or np.any(self.delta_v_sp != 0)
        self.was_moving = self.is_moving
        self.is_moving = self.is_deviating or self.is_slewing or self.mode=="TRACK"
        if not self.is_moving and self.mode in ['AUTO', 'HOMING', 'PARKING']:
            self.set_pid_mode('IDLE')
   
    def pid(self):
        self.omega_kp = self.Kp * self.error_signal    # increase control proportional to error
        self.omega_ki = self.Ki * self.error_integral  # increase control when integral error is high
        self.omega_kd = - self.Kd * self.omega_op      # dampen control when velocity high
        self.omega_tgt = self.omega_kp + self.omega_ki + self.omega_kd

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
        # Check zeta motor limits and constrain omega further if past limits
        if self.polaris._zeta_meas is None:
            self.omega_min = -self.Kv
            self.omega_max = +self.Kv
        else:
            zeta = np.array(self.polaris._zeta_meas)
            zeta_min = np.array([Config.z1_min_limit, Config.z2_min_limit, Config.z3_min_limit])
            zeta_max = np.array([Config.z1_max_limit, Config.z2_max_limit, Config.z3_max_limit])
            self.omega_min = np.where(zeta < zeta_min, np.array([0,0,0]), -self.Kv) 
            self.omega_max = np.where(zeta > zeta_max, np.array([0,0,0]), +self.Kv) 
            isLimited = np.any(self.omega_min == 0) or np.any(self.omega_max == 0)
            isUnAcked = self.ack_limit_timestamp is None or (datetime.datetime.now() - self.ack_limit_timestamp).total_seconds() > 60
            isnotPARKorPRESETUP = not self.set_pid_mode in ['PRESETUP', 'PARK']
            if isLimited and isUnAcked and isnotPARKorPRESETUP:
                self.set_pid_mode('LIMIT')
                self.parking_complete_callback = None  # Cancel any parking underway

        # Check that lat/lon has been set
        lat_unchanged = abs(rad2deg(float(self.observer.lat)) - -33.8598874) <= 0.00001
        lon_unchanged = abs(rad2deg(float(self.observer.lon)) - 151.2021771) <= 0.00001
        if lat_unchanged and lon_unchanged:
            self.set_pid_mode('PRESETUP')
        else:
            if self.mode=='PRESETUP':
                self.set_pid_mode('IDLE')

        self.omega_ctl = np.clip(self.omega_ctl, self.omega_min, self.omega_max)

    async def control(self):
        self.omega_op = np.array([0,0,0], dtype=float)
        # [0.0, 0.0059018, 0.0175906, 0.0478282, 0.0892742, 0.2079884]
        for axis in range(3):
            self.omega_op[axis] = self.omega_ctl[axis]
            raw = self.controllers[axis]._model.DPS.toRAW(self.omega_ctl[axis])
        # send control to motor when moving
        if self.is_moving and self.mode in ['AUTO', 'TRACK', 'HOMING', 'PARKING']:
            for axis in range(3):
                await self.controllers[axis].set_motor_speed(self.omega_op[axis], rate_unit='DPS', ramp_duration=self.dt, allow_PWM=True, tracking=(self.mode=="TRACK"))
        # Stop motors when transitioning from moving to stopped
        if self.was_moving and not self.is_moving:
            for axis in range(3):
                await self.controllers[axis].set_motor_speed(0)

    def notify(self):
        if not self.is_deviating and self.goto_complete_callback:
            self.goto_complete_callback()
            self.goto_complete_callback = None
        if not self.is_deviating and self.rotate_complete_callback:
            self.rotate_complete_callback()
            self.rotate_complete_callback = None
        if not self.is_deviating and self.parking_complete_callback:
            self.parking_complete_callback()
            self.parking_complete_callback = None
        if not self.is_slewing and self.slew_complete_callback:
            self.slew_complete_callback()
            self.slew_complete_callback = None

    def telemetry(self):
        # Log meas, state and ref for websocket streaming
        payload = { 
            "θ_sp":  self.theta_ref.tolist(), 
            "θ_pv":  self.theta_meas.tolist(), 
            "ω_kp":  self.omega_kp.tolist(), 
            "ω_ki":  self.omega_ki.tolist(),  
            "ω_kd":  self.omega_kd.tolist(), 
            "ω_ff":  self.omega_ref.tolist(), 
            "ω_op":  self.omega_op.tolist(), 
        }
        pidlogger = logging.getLogger('pid') 
        pidlogger.info(payload)


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
        with self._lock:
            self._stop_flag.set()



########################## 
#  SYNC MANAGER          #
########################## 

class SyncManager:
    def __init__(self, logger, polaris):
        self.logger = logger
        self.polaris = polaris
        self.sync_history = []                  # list of sync events, both AzAlt and Roll
        self.aligned_count = 0                  # number of AzAlt syncs used in last optimisation
        self.q1_adj = Quaternion(1,0,0,0)       # optimised adjustment quaternion for azalt syncing, initially identity
        self.q1_adj_message = ""                # message from last optimisation
        self.tilt_adj_az = 0                    # q1_adj Tilt azimuth (°): direction of steepest upward inclination (info only)     
        self.tilt_adj_mag = 0                   # q1_adj Tilt magnitude (°): angle of inclination from horizontal plane (info only)
        self.az_adj = 0                         # q1_adj Azimuth correction (°): azimuth axis correction to apply (info only)
        self.roll_adj = 0                       # Roll axis correction (°): optimised adjustment offset from roll syncing 

    def standard_entry(self):
        entry = {
            "timestamp": format_timestamp(),
            "deleted": False,
            "p_az": self.polaris._p_azimuth,
            "p_alt": self.polaris._p_altitude,
            "p_roll": self.polaris._p_roll,
            "a_az": None,
            "a_alt": None,
            "a_roll": None,
        }
        return entry

    def sync_az_alt(self, a_az, a_alt):
        entry = self.standard_entry()
        entry["a_az"] = a_az
        entry["a_alt"] = a_alt
        self.sync_history.append(entry)
        self.optimize_q1_adj()
        self.logSyncData()

    def sync_roll(self, a_roll):
        entry = self.standard_entry()
        entry["a_roll"] = a_roll
        if (Config.advanced_alignment and Config.advanced_control):
            _,_,_,_,_,p_roll = quaternion_to_angles(self.q1_adj * self.polaris._q1, azhint=self.polaris.azimuth)
            entry["p_roll"] = p_roll         # The polaris roll needs to be adjusted for tilt using q1_adj
        self.sync_history.append(entry)
        self.optimize_roll_adj()
        self.logSyncData()

    def sync_remove(self, timestamp):
        found = False
        for entry in self.sync_history:
            if entry.get("timestamp") == timestamp:
                entry["deleted"] = True
                found = True
                break
        if found:
            self.logger.info(f"Cleared sync data for timestamp: {timestamp}")
            self.optimize_q1_adj()
            self.optimize_roll_adj()
            self.logSyncData()
        else:
            self.logger.warning(f"No sync entry found with timestamp: {timestamp}")

    def az_alt_to_vector(self, az_deg, alt_deg):
        az = math.radians(az_deg)
        alt = math.radians(alt_deg)
        x = math.cos(alt) * math.sin(az)
        y = math.cos(alt) * math.cos(az)
        z = math.sin(alt)
        return np.array([x, y, z])

    def vector_to_az_alt(self, vec):
        x, y, z = vec
        az = math.degrees(math.atan2(x, y)) % 360
        alt = math.degrees(math.asin(z / np.linalg.norm(vec)))
        return az, alt

    def azalt_polaris2ascom(self, p_az, p_alt):
        if self.q1_adj is None:
            return p_az, p_alt
        v_pred = self.az_alt_to_vector(p_az, p_alt)
        v_obs = self.q1_adj.rotate(v_pred)
        c_az, c_alt = self.vector_to_az_alt(v_obs) 
        return c_az, c_alt

    def azalt_ascom2polaris(self, a_az, a_alt):
        if self.q1_adj is None:
            return a_az, a_alt
        v_obs = self.az_alt_to_vector(a_az, a_alt)
        v_pred = self.q1_adj.inverse.rotate(v_obs)
        p_az, p_alt = self.vector_to_az_alt(v_pred)
        return p_az, p_alt

    def optimize_q1_adj(self):
        """
        Implement the QUEST algorithm to find the optimal rotation quaternion
        that minimizes the misalignment between predicted (Polaris) and observed (Plate Solved/ASCOM) vectors.
        Based on: 
        Markley, F. L. (2000). "Quaternion Attitude Estimation Using Vector Observations." https://tinyurl.com/ymk5xd7z
        Markley, F. L. (2003). "Attitude Estimation or Quaternion Estimation?" https://ntrs.nasa.gov/citations/20030093641
        """
        pairs = []
        for entry in self.sync_history:
            if entry["deleted"] or entry["a_az"] is None or entry["a_alt"] is None:
                continue
            # Observed vector from sync
            v_obs = self.az_alt_to_vector(entry["a_az"], entry["a_alt"])
            # Predicted vector from mount
            v_pred = self.az_alt_to_vector(entry["p_az"], entry["p_alt"])
            pairs.append((v_pred, v_obs))

        self.aligned_count = len(pairs)
        if len(pairs) < 2:
            self.q1_adj = self.optimise_q1_adj_fallback_single_sync(pairs)
            self.q1_adj_message = "Fallback rotation from single sync"
        else:
            # Build the B matrix: sum of weighted outer products between predicted and observed vectors
            # Each term aligns a predicted direction (from Polaris) to an observed direction (from sync)
            # This builds the core rotation alignment matrix
            B = sum(np.outer(v_pred, v_obs) for v_pred, v_obs in pairs)

            # Construct the Davenport matrix K, which encodes the optimal rotation in quaternion form
            # This is based on the method from Markley's QUEST algorithm
            S = B + B.T             # Symmetric part of B
            sigma = np.trace(B)     # Scalar part: trace of B (sum of diagonal elements)

            # Anti-symmetric part: used to build the vector Z
            # Z encodes the cross-product-like skew between predicted and observed vectors
            Z = np.array([
                B[1,2] - B[2,1],    # YZ - ZY
                B[2,0] - B[0,2],    # ZX - XZ
                B[0,1] - B[1,0]     # XY - YX
            ])
            # Initialize the 4x4 Davenport matrix K
            # K is structured to find the quaternion that best rotates predicted vectors to observed ones
            K = np.zeros((4,4))
            K[0,0] = sigma
            K[0,1:] = Z
            K[1:,0] = Z
            K[1:,1:] = S - sigma * np.eye(3)

            # Solve the eigenvalue problem: find the eigenvector of K with the largest eigenvalue
            # This eigenvector represents the optimal quaternion [w, x, y, z]
            eigvals, eigvecs = np.linalg.eigh(K)
            q_opt = eigvecs[:, np.argmax(eigvals)]  # [w, x, y, z]

            self.q1_adj = Quaternion(q_opt[0], q_opt[1], q_opt[2], q_opt[3])
            self.q1_adj_message = "QUEST solution applied"

        # Now compute the residuals and tilt correction
        self.compute_azalt_residuals()   # Compute and store residuals
        self.compute_tilt()              # Compute tilt correction

        return


    def optimise_q1_adj_fallback_single_sync(self, pairs):
        if len(pairs) == 0:
            return Quaternion(1,0,0,0)  # identity quaternion
        
        v_pred, v_obs = pairs[0]
        v_pred /= np.linalg.norm(v_pred)
        v_obs /= np.linalg.norm(v_obs)

        # Horizontal projection
        v_pred_h = np.array([v_pred[0], v_pred[1], 0])
        v_obs_h = np.array([v_obs[0], v_obs[1], 0])

        # Azimuth correction
        q_az = Quaternion(1, 0, 0, 0)
        if np.linalg.norm(v_pred_h - v_obs_h) > 1e-6:
            az_pred = math.atan2(v_pred[1], v_pred[0])
            az_obs = math.atan2(v_obs[1], v_obs[0])
            d_az = az_obs - az_pred
            q_az = Quaternion(axis=[0, 0, 1], radians=d_az)
            v_pred = q_az.rotate(v_pred)

        # Tilt correction
        dot = np.dot(v_pred, v_obs)
        angle = math.acos(np.clip(dot, -1.0, 1.0))
        axis = np.cross(v_pred, v_obs)
        axis = np.array([axis[0], axis[1], 0])  # project to horizontal

        if np.linalg.norm(axis) < 1e-6:
            return q_az  # only azimuth correction needed

        axis /= np.linalg.norm(axis)
        q_tilt = Quaternion(axis=axis, radians=angle)
        return q_tilt * q_az

    def compute_azalt_residuals(self):
        for entry in self.sync_history:
            if entry["deleted"] or entry["a_az"] is None or entry["a_alt"] is None:
                continue
            az_corr, alt_corr = self.azalt_polaris2ascom(entry["p_az"], entry["p_alt"])
            az_err = angular_difference(az_corr, entry["a_az"])
            alt_err = angular_difference(alt_corr, entry["a_alt"])
            magnitude = math.sqrt(az_err**2 + alt_err**2)
            entry["residual_vector"] = (az_err, alt_err)
            entry["residual_magnitude"] = magnitude

    def compute_roll_residuals(self):
        for entry in self.sync_history:
            if entry["a_roll"] is None:
                continue
            p_roll = entry["p_roll"]
            p_corr = self.roll_polaris2ascom(p_roll)
            entry["residual_magnitude"] = angular_difference(p_corr, entry["a_roll"])


    def compute_tilt(self):
        # Sample altitudes at cardinal azimuths
        north_az, north_alt = self.azalt_polaris2ascom(0, 0)
        _, east_alt  = self.azalt_polaris2ascom(90, 0)
        _, south_alt = self.azalt_polaris2ascom(180, 0)

        # Build vectors: each points in azimuth direction with altitude as Z
        v_north = np.array([0, 1, math.tan(math.radians(north_alt))])
        v_east  = np.array([1, 0, math.tan(math.radians(east_alt))])
        v_south = np.array([0, -1, math.tan(math.radians(south_alt))])

        # Fit a plane to these three points
        A = np.vstack([v_north, v_east, v_south])
        centroid = np.mean(A, axis=0)
        A_centered = A - centroid
        _, _, vh = np.linalg.svd(A_centered)
        normal = vh[-1]  # normal to best-fit plane
        if normal[2] < 0:
            normal = -normal


        # Tilt magnitude: angle between normal and vertical
        tilt_angle_rad = math.acos(np.clip(normal[2], -1.0, 1.0))
        tilt_magnitude_deg = math.degrees(tilt_angle_rad)

        # Tilt azimuth: direction of tilt projected onto horizontal plane
        v_downhill = np.array([-normal[0], -normal[1], 0]) # invert to get "downhill" direction
        tilt_az_polaris = math.degrees(math.atan2(v_downhill[0], v_downhill[1])) % 360
        tilt_az_observed, _ = self.azalt_polaris2ascom(tilt_az_polaris, 0)

        self.tilt_adj_az = tilt_az_observed
        self.tilt_adj_mag = tilt_magnitude_deg
        self.az_adj = wrap_to_180(north_az)


    def roll2pa(self, az_deg, alt_deg, roll_deg):
        """Convert camera-frame roll to sky-frame position angle and parallactic angle at ascom azalt."""
        parallactic_angle = calc_parallactic_angle(az_deg, alt_deg, self.polaris._sitelatitude)
        position_angle = wrap_to_360(roll_deg + parallactic_angle)
        return position_angle, parallactic_angle

    def pa2roll(self, az_deg, alt_deg, position_angle_deg):
        """Convert sky-frame position angle to camera-fram roll using parallactic angle at ascom azalt."""
        parallactic_angle = calc_parallactic_angle(az_deg, alt_deg, self.polaris._sitelatitude)
        return wrap_to_360(position_angle_deg - parallactic_angle)

    def roll_polaris2ascom(self, polaris_roll_deg):
        """Convert Polaris roll angle to ASCOM roll angle (mechanical angle), applying roll sync adjustment correction."""
        return wrap_to_360(polaris_roll_deg + self.roll_adj)

    def roll_ascom2polaris(self, ascom_roll_deg):
        """Convert ASCOM roll angle (mechanical angle) to Polaris roll angle, applying roll sync adjustment."""
        return wrap_to_360(ascom_roll_deg - self.roll_adj)

    def optimize_roll_adj(self):
        deltas = []

        for entry in self.sync_history:
            if entry["deleted"] or entry["a_roll"] is None:
                continue

            # Compute delta: how much Polaris roll differs from expected PA
            delta = angular_difference(entry["p_roll"], entry["a_roll"])
            deltas.append(delta)

        self.roll_adj = sum(deltas) / len(deltas) if deltas else 0
        self.compute_roll_residuals()

    def logSyncData(self):
        sm_logger = logging.getLogger('sm')
        for entry in self.sync_history:
            sm_logger.info(entry)


