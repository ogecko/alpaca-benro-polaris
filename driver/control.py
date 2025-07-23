import numpy as np
import datetime
from pyquaternion import Quaternion
from config import Config
from scipy.interpolate import PchipInterpolator
import time
import asyncio
from typing import Optional

# ************* TODO LIST *****************

# Control Algorithm Features
# [X] Quaternion-based kinematics and inverse solutions
# [X] Angular Rate Interpolation Framework
# [X] PWM Driven Speed Control
# [X] Real-time Angular Position and Velocity Measurement
# [X] Control Input Normalisation
# [X] Orientation Estimation via Kalman Filtering
# [X] Speed Calibration & Response Profiling
# [ ] Model Predicture Control trajectory shaping
# [ ] Rate Derivative Estimation (Jerk Monitoring)
# [ ] Feedforward Control Integration (minimise overshoot)
# [ ] Constraint-Aware Rate Limiting
# [ ] Control Mode Switching
# [ ] Time-Differentiated Tracking Profiles
#
# Position Calculation Features
# [X] Accurate Orbital Positioning of Earth and Target Body
# [X] Light Travel Time Compensation for Apparent Position
# [X] Epoch-Based Coordinate Precession Alignment
# [X] Relativistic Light Deflection near Solar Limb
# [x] Earth Nutation Correction (Polar Axis Wobble)
# [x] Aberration of Light Due to Earth’s Orbital Velocity
# [x] Atmospheric Refraction Modeling (Pressure & Temperature Based)
# [x] Observer-Based Parallax Offset Correction
# [x] Astrometric Geocentric Coordinate Generation
# [x] Apparent Geocentric Position Refinement
# [x] Topocentric Apparent Coordinate Output (RA, Dec, PA | Alt, Az, Roll)
#
# Precision Slew Control
# [ ] Kinematically Optimised Mount Trajectory
# [ ] Real-Time Interruptible Path Planning
# [ ] Dynamically Smooth Motion and Acceleration
# [ ] Predictive Anti-Backlash Correction
# [ ] Expanded Target Catalog
# [ ] Auto-fetch Target Catalog updates
# [ ] Auto-fetch orbital elements
#
# Precision Tracking
# [ ] Target position and velocity tracking with adaptive error correction
# [ ] Seamless Axis Override During Tracking
# [ ] Deep-Sky Object Tracking
# [ ] Selenographic Lunar Tracking
# [ ] Planetary and Orbital Moons Tracking
# [ ] Commet and Asteroid Tracking
# [ ] Satelite Tracking via TLE (Two Line Element)
# [ ] Solar Tracking
# [ ] Transiting Exoplanet Support

#
# Rotator Control Features
# [ ] Parallactic and Roll Angle Targeting
# [ ] ASCOM Rotator Driver Integration
# [ ] Direct Slew to Defined Angular Pose
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




# ************* Quaternion Kinematics *************

def is_angle_same(a, b, tolerance=1e-4):
    """Returns True if angles a and b are equivalent within tolerance, accounting for wrapping."""
    return abs((a - b + 180) % 360 - 180) < tolerance


def is_same_quaternion_rotation(q1, q2, tolerance=1e-6):
    """Check if two quaternions represent the same rotation"""
    t1, t2, t3, a1, a2, a3 = quaternion_to_angles(q1)
    s1, s2, s3, b1, b2, b3 = quaternion_to_angles(q2)
    return (t1-s1)**2+(t2-s2)**2+(t3-s3)**2+(a1-b1)**2+(a2-b2)**2+(a3-b3)**2 < tolerance


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
    if alignment < -epsilon:
        return roll_raw
    else:
        return -roll_raw



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
    
    return -q1.normalised



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
    qtheta3 = Quaternion(axis=(qtheta1*qtheta2).rotate([1, 0, 0]), degrees= theta3)
    q1 = qtheta3 * qtheta1 * qtheta2   # Reconstructed q1 quaternion from theta2 then theta1 then theta3

    return -q1.normalised



def quaternion_to_angles(q1):
    """
    Convert a quaternion to theta1, theta2, theta3, altitude, azimuth, and roll angles.
    
    Args:
        q1: Quaternion that rotates from camera frame to topocentric frame
            Camera frame: -z = boresight, +x = up, +y = left
            Topocentric frame: +z = Zenith, +y = North, +x = East
    
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
    q4 = q1 * Quaternion(axis=cUp, degrees=180)                     # since axis3 is last rotation ZYX in q1, we can simply read its Euler angle X after we flip it
    theta3 = np.degrees(np.arctan2(2 * (q4[0]*q4[1] + q4[2]*q4[3]), q4[0]**2 - q4[1]**2 - q4[2]**2 + q4[3]**2))
    
    # --- Theta1 and Theta2: rotation around corrected bore vector ie Polaris Axis 1 and 2, without effect of Axis 3
    unroll = Quaternion(axis=tUp, degrees=theta3).inverse               # Undo Theta3 rotation to get cleaned bore vector 
    mBore = unroll.rotate(tBore)                                        # mBore is the Camera optical axis if we removed the Astro Module on the polaris
    theta1 = (np.degrees(np.arctan2(mBore[0], mBore[1])) + 360) % 360
    theta2 = np.degrees(np.arcsin(np.clip(mBore[2], -1.0, 1.0)))


    return theta1, theta2, theta3, az, alt, roll



# ************* Kalman Filter *************


class KalmanFilter:
    def __init__(self, logger, dt, initial_state):
        self._logger = logger
        self.dt = dt

        # State: [theta1, theta2, theta3, omega1, omega2, omega3]
        self.x = initial_state.reshape(6, 1)

        # State transition matrix (A): position + dt * velocity
        self.A = np.block([
            [np.eye(3), dt * np.eye(3)],
            [np.zeros((3, 3)), np.eye(3)]
        ])

        # Control matrix (B): acceleration nudging velocity
        self.B = np.block([
            [np.zeros((3, 3))],
            [np.eye(3)]
        ])

        # Measurement matrix (H): measures both position and velocity
        self.H = np.eye(6)

        # Noise models
        self.Q = np.eye(6) * 1e-4           # Process noise
        self.R = np.eye(6) * 1.45e-4        # Measurement noise
        self.P = np.eye(6)                  # Initial estimate covariance
        self.I = np.eye(6)

    def predict(self, control_input):
        control_input = np.array(control_input).reshape(3, 1)
        omega_est = self.x[3:]                       # Estimated velocity
        u = control_input - omega_est                # Acceleration signal
        self.x = self.A @ self.x + self.B @ u
        self.P = self.A @ self.P @ self.A.T + self.Q

    def observe(self, theta, omega):
        theta = np.array(theta).reshape(3, 1)
        omega = np.array(omega).reshape(3, 1)
        z = np.vstack((theta, omega))               # Measurement: position + velocity

        y = z - self.H @ self.x                     # Measurement residual
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (self.I - K @ self.H) @ self.P

    def get_state(self):
        return self.x.flatten()

    def set_state(self, x):
        self.x = np.array(x).reshape(6, 1)



# ************* MoveAxis Rate Interpolation *************

move_axis_data = {
    0: {  # Axis 0
        'RAW':   [0, 1, 2, 3, 4, 5, 370, 770, 1179, 1589, 2000],
        'ASCOM': [0, 1, 2, 3, 4, 5, 5.001, 6, 7, 8, 9],
        'DPS':   [0.0, 0.006003545, 0.01783035, 0.04750983, 0.089358299, 0.208111366, 0.2082, 1.086256628, 2.068490002, 3.491413677, 5.358685096]
    },
    1: {  # Axis 1
        'RAW':   [0, 1, 2, 3, 4, 5, 370, 770, 1179, 1589, 2000],
        'ASCOM': [0, 1, 2, 3, 4, 5, 5.001, 6, 7, 8, 9],
        'DPS':   [0.0, 0.006003545, 0.01783035, 0.04750983, 0.089358299, 0.208111366, 0.2082, 1.086256628, 2.068490002, 3.491413677, 5.358685096]
    },
    2: {  # Axis 2
        'RAW':   [0, 1, 2, 3, 4, 5, 370, 770, 1179, 1589, 2000],
        'ASCOM': [0, 1, 2, 3, 4, 5, 5.001, 6, 7, 8, 9],
        'DPS':   [0.0, 0.006003545, 0.01783035, 0.04750983, 0.089358299, 0.208111366, 0.2082, 1.086256628, 2.068490002, 3.491413677, 5.358685096]
    },
}

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
    def __init__(self, logger, axis: int, send_msg):
        self.axis = axis
        self._logger = logger
        self._model = MoveAxisRateInterpolator(move_axis_data[axis])
        self._messenger = MoveAxisMessenger(axis, send_msg)
        self._stop_flag = asyncio.Event()
        self._lock = asyncio.Lock()
        self._strategy: Optional[AxisControlStrategy] = None

        self.rate = 0.0            # last set_motor_speed rate +/-
        self.rate_unit = "DPS"     # units of the last set_motor_speed rate ('DPS', 'ASCOM', or 'RAW')
        self.rate_raw = 0.0        # rate in raw units (command rate +/-0.0 to 5.0 SLOW, >5 to 2000 FAST)
        self.rate_dps = 0.0        # rate in dps units (Degrees per second)

        # Kick off the dispatch loop as an asyncio task
        asyncio.create_task(self._dispatch_loop())

    @property
    def motor_mode(self):
        return self._strategy.mode if self._strategy else "IDLE"

    def set_motor_speed(self, rate: float, rate_unit="DPS"):
        async def _update():
            async with self._lock:
                previous = self._strategy
                self.rate = rate
                self.rate_unit = rate_unit
                self.rate_raw = float(self._model.interpolate[rate_unit].toRAW(rate))
                self.rate_dps = float(self._model.interpolate['RAW'].toDPS(self.rate_raw))
                self._strategy = AxisControlStrategy(self.rate_raw, previous)
        asyncio.create_task(_update())

    async def stop(self):
        async with self._lock:
            self._stop_flag.set()
            await self._messenger.send_slow_move_msg(0)

    async def _dispatch_loop(self):
        while not self._stop_flag.is_set():
            async with self._lock:
                strategy = self._strategy

            if strategy:
                cmd = strategy.get_command_if_due()
                if cmd:
                    # self._logger.info(f"[Axis {self.axis}] Mode: {self.motor_mode}, DPS: {self.rate_dps:.4f}, RAW: {self.rate_raw:.4f}, Cmd: {cmd}, Duration: {strategy.next_dispatch_time - time.monotonic():.2f}s")
                    raw_rate = cmd["raw_rate"]
                    typ = cmd["type"]
                    # Fire-and-forget async messages
                    if typ in ("SLOW", "PWM_SLOW"): 
                        asyncio.create_task(self._messenger.send_slow_move_msg(raw_rate)) 
                    else:
                        asyncio.create_task(self._messenger.send_fast_move_msg(raw_rate))

            # Non-blocking sleep until next dispatch
            next_time = strategy.next_dispatch_time if strategy else time.monotonic() + 0.05
            sleep_sec = float(np.clip(next_time - time.monotonic(), 0.001, 0.05))
            await asyncio.sleep(sleep_sec)

class AxisControlStrategy:
    def __init__(self, raw_rate: float, previous: Optional['AxisControlStrategy'], pwm_cycle_ms=5000, fast_cycle_ms=50):
        self.raw_rate = raw_rate
        self.mode = 'IDLE'
        self.pwm_cycle_ms = pwm_cycle_ms
        self.fast_cycle_ms = fast_cycle_ms
        self.next_dispatch_time = time.monotonic()
        self._analyze(previous)

    def _analyze(self, previous_strategy: Optional['AxisControlStrategy']):
        interp = abs(self.raw_rate)
        direction = 1 if self.raw_rate >= 0 else -1
        now = time.monotonic()

        # if a FAST rate
        if interp > 5:
            self.mode = 'FAST'
            self.command = int(np.clip(round(interp), 300, 2000)) * direction

        # if we are stopping this axis
        elif interp == 0:
            self.mode = 'SLOW'
            self.command = 0

        # if a SLOW or PWM_SLOW rate
        else:
            base = int(np.floor(interp)) * direction
            next_up = int(np.ceil(interp)) * direction
            duty = interp - np.floor(interp)

            # if a integer SLOW rate
            if duty == 0 or base == next_up:
                self.mode = 'SLOW'
                self.command = base

            # if a PWM_SLOW rate is needed
            else:
                self.mode = 'PWM_SLOW'
                self.command = (base, next_up)
                self.duty_cycle = duty
                self.pwm_phase = 'ON'
                self.last_switch_time = now
                self.next_dispatch_time = now  # Start immediately

                if previous_strategy and previous_strategy.mode == 'PWM_SLOW':
                    # Preserve PWM state and calculate adjusted next_dispatch_time
                    elapsed = time.monotonic() - previous_strategy.last_switch_time
                    last_phase = previous_strategy.pwm_phase
                    new_duration = self.pwm_cycle_ms * (1 - self.duty_cycle if last_phase == 'ON' else self.duty_cycle)

                    if elapsed < new_duration:
                        self.pwm_phase = last_phase
                        self.next_dispatch_time = time.monotonic() + (new_duration - elapsed) / 1000.0
                        self.last_switch_time = time.monotonic()

    def get_command_if_due(self):
        now = time.monotonic()
        if now < self.next_dispatch_time:
            return None

        if self.mode == 'SLOW':
            self.next_dispatch_time = time.monotonic() + float('inf')
            return {"type": "SLOW", "raw_rate": self.command}

        elif self.mode == 'FAST':
            self.next_dispatch_time = now + self.fast_cycle_ms / 1000.0
            return {"type": "FAST", "raw_rate": self.command}

        elif self.mode == 'PWM_SLOW':
            base, next_up = self.command
            duration = self.pwm_cycle_ms * (1 - self.duty_cycle if self.pwm_phase == 'ON' else self.duty_cycle)
            self.next_dispatch_time = now + duration / 1000.0
            cmd = base if self.pwm_phase == 'ON' else next_up
            self.pwm_phase = 'OFF' if self.pwm_phase == 'ON' else 'ON'
            return {"type": "PWM_SLOW", "raw_rate": cmd}

class MoveAxisMessenger:
    def __init__(self, axis: int, send_msg):
        if axis not in (0, 1, 2):
            raise ValueError("Invalid axis.")
        self.axis = axis
        self.send_msg = send_msg
        self.cmd_slow = ['532', '533', '534'][axis]     # Pick right cmd based on axis passed in on initialisation
        self.cmd_fast = ['513', '514', '521'][axis]     # Pick right cmd based on axis passed in on initialisation

    async def send_slow_move_msg(self, slow_raw_rate: int) -> str:
        if not isinstance(slow_raw_rate, int) or not (-5 <= slow_raw_rate <= 5):
            raise ValueError("SLOW rate must be an integer between 0 and 5.")
        key = 0 if slow_raw_rate > 0 else 1
        state = 0 if slow_raw_rate == 0 else 1
        msg = f"1&{self.cmd_slow}&3&key:{key};state:{state};level:{abs(slow_raw_rate)};#"
        await self.send_msg(msg)
        return msg

    async def send_fast_move_msg(self, fast_raw_rate: int) -> str:
        if abs(fast_raw_rate) > 2000:
            raise ValueError("FAST rate must be within ±2000.")
        msg = f"1&{self.cmd_fast}&3&speed:{int(fast_raw_rate)};#"
        await self.send_msg(msg)
        return msg
