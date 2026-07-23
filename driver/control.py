import numpy as np
import datetime
import json, os, re
import logging
from pathlib import Path
from quaternion import Q as Quaternion
from config import Config
from scipy.interpolate import PchipInterpolator
import time
import asyncio
import ephem
import math
import copy
from shr import rad2deg, deg2rad, deg2dms, format_timestamp, ratio_string
from threading import Lock
from orbitals import orbital_data, create_tle_orbital_celestrak, create_xephem_orbital_jpl, ensure_data_dir_exists
from kinematics import wrap360, wrap180, calc_parallactic_angle, wrap_angle_residual, wrap_state_angles
from kinematics import get_mechanical_correction_q, apply_mechanical_corrections, MountModelParams, calc_equatorial_axes_B
from kinematics import azalt_to_vector, vector_to_az_alt, v_angular_distance, calculate_angular_velocity_vector 
from kinematics import angular_difference, clamp_alpha, clamp_delta, clamp_theta, clamp_offset, clamp_error
from kinematics import q_to_theta, q_to_azaltroll, quaternion_difference, reachable_azaltroll
from kinematics import azaltroll_to_q, theta_to_jacobian, LastPosition, delta_to_gamma

DRIVER_DIR = Path(__file__).resolve().parent      # Get the path to the current script (control.py)
DATA_DIR = DRIVER_DIR.parent / 'data'             # Default data directory: ../data 
CALIBRATION_PATH = DATA_DIR / 'speed_calibration.json'
TESTDATA_PATH = DATA_DIR / 'speed_testdata.json'
SYNC_POINTS_PATH = DATA_DIR / 'sync_points.json'



# ************* Kalman Filter *************


class KalmanFilter:
    def __init__(self, logger, initial_state):
        self._logger = logger
        self._time = time.monotonic()
        self._need_first_measurement = True

        self.z = np.zeros((6,1))
        self.x = initial_state.reshape(6, 1)    # State: [theta1, theta2, theta3, omega1, omega2, omega3]
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
        if dt < 0.05:
            return

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
        self.z = np.vstack((theta_meas, omega_meas))               # Measurement: position + velocity

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
        meas = self.z.flatten()
        theta = state[0:3] if Config.advanced_kf else meas[0:3]
        omega = state[3:] if Config.advanced_kf else meas[3:]
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


    def saveCalibrationDataToFile(self, path = CALIBRATION_PATH):
        ensure_data_dir_exists()
        with open(path, 'w') as f:
            f.write(self.formatCalibrationData())

    def saveTestDataToFile(self, path = TESTDATA_PATH):
        ensure_data_dir_exists()
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
        self._condition = asyncio.Condition()
        self._stopping = False

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
        async with self._condition:
            if not rate_unit in ['RAW', 'DPS', 'ASCOM']:
                self._logger.info(f'Set Motor Speed - Invalid units {rate_unit}')
                return
            raw = self._model.interpolate[rate_unit].toRAW(rate)
            now = time.monotonic()
            # if we get too many updates before they are applied, just overwrite the last one
            self.pending_update = (float(raw), ramp_duration, allow_PWM, tracking, now)
            self._condition.notify()

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
        while True:
            async with self._condition:
                if self._stopping:
                    return
                
                now = time.monotonic()
                self._apply_pending_update(now)

                # Determine when we need to wake next
                if now < self.next_dispatch_time:
                    timeout = self.next_dispatch_time - now
                    try:
                        await asyncio.wait_for( self._condition.wait(), timeout=timeout )
                    except asyncio.TimeoutError:
                        # Expected: timeout means it's time to wake and dispatch on schedule.
                        pass
                    continue

                # Dispatch the relevant commands
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
                    # self._logger.info(f"Motor {self.axis+1} RateDPS: {self.rate_dps:.4f}, PWM phase: {self.pwm_phase}, rate: {pwm_rate}, duration: {duration:.2f}s")
                    self.pwm_phase = "OFF" if was_on else "ON"
                    self.last_switch_time = now
                    self.next_dispatch_time = now + duration
                
                else:
                    self.next_dispatch_time = now + 0.05

    def get_cmdstr(self):
        if self.mode=="IDLE":
            return f" IDLE      "
        elif self.mode=="FAST_RAMP":
            return f" RAMP {self.command:+05.0f}"
        elif self.mode=="FAST":
            return f" FAST {self.command:+05.0f}"
        elif self.mode=="SLOW":
            return f" SLOW {self.command:+05.0f}"
        elif self.mode=="SLOW_PWM":
            return f"{self.command[0]:+2.0f} {ratio_string(self.duty_cycle)} {self.command[1]:+2.0f}"
        else:
            return f"       "

    async def stop_disspatch_loop_task(self):
        async with self._condition:
            # dont bother trying to stop motors as some structures have been lost already
            # await self._messenger.send_slow_move_msg(0)
            # await asyncio.sleep(0.2)
            self._stopping = True
            self._condition.notify()            

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
            return ""
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
    def __init__(self, logger, polaris, dt=0.2, loop=None):
        self._stop_flag = asyncio.Event()                    # Used to flag control loop to stop
        self._lock = Lock()                                  # Used to ensure no threading issues
        self._lp = LastPosition()                            # Used to remember last theta position for gimbal lock
        self.logger = logger                                 # Logging utility
        self.polaris = polaris                               # Only used for guiding clacs and flaging
        self.controllers = polaris._motors                   # Motor speed controllers[0,1,2]
        self.observer = polaris._observer                    # Observing object from ephem
        self.body = ephem.FixedBody()                        # Target body
        self.body._epoch = ephem.now()                       # default to J2000 epoch
        self.body_pa_offset = 0                              # used to store body pa to oconvert back to roll
        self.control_loop_duration = loop                    # PID Control Loop duration in seconds
        self.mode = 'PRESETUP'                               # PID Controller mode: HOMING, PARKING, PARK, IDLE, AUTO, TRACK, PRESETUP, LIMIT
        self.ack_limit_timestamp = None                      # Timestamp of last ACK of PID LIMIT ALARM
        self.target_type = 'NONE'                            # target body we are tracking
        self.orbital_sp_name = None                    # name of pyephem body tracking for Lunar, Solar, Custom rates
        self.orbital_sp_fetchmsg  = None               # result msg from last http fetch of orbital parameters
        self.orbital_sp_status = [0, 0, 0]             # status of orbital tracking [is_orb_trackable (0=N/A, 1=toolow, 2=ok), orb_az, orb_alt]
        self.gamma_sp = np.zeros(3, dtype=float)       # Setpoint for l,  b,   gpa  - user set target galactic co-ordinates
        self.delta_sp = np.zeros(3, dtype=float)       # Setpoint for ra, dec, pa   - user set target equatorial co-ordinates
        self.alpha_sp = np.zeros(3, dtype=float)       # Setpoint for az, alt, roll - user set target topocentric co-ordinates
        self.gamma_pv = np.zeros(3, dtype=float)       # l,  b,   gpa  - measured galactic co-ordinates
        self.delta_pv = np.zeros(3, dtype=float)       # ra, dec, pa   - measured equatorial co-ordinates
        self.alpha_pv = np.zeros(3, dtype=float)       # az, alt, roll - measured topocentric co-ordinates
        self.theta_pv = np.zeros(3, dtype=float)       # theta1-3      - measured motor angular position (kf and pec corrected)
        self.zeta_meas = np.zeros(3, dtype=float)      # zeta1-3       - measured raw motor angular position (no alignment effect)
        self.delta_ref = np.zeros(3, dtype=float)      # ra, dec, pa    - control target equatorial co-ordinates
        self.alpha_ref = np.zeros(3, dtype=float)      # az, alt, roll  - control target topocentric co-ordinates
        self.theta_ref = np.zeros(3, dtype=float)      # theta1-3 motor - control target motor co-ordinates
        self.theta_ref_cache = None                    # theta1-3       - cached when mount needs to do large slews
        self.theta_ref_cache_cause = None              # theta1-3       - string cause of cached theta_ref either 'FLIP CW', 'FLIP CCW' or 'UNWIND'
        self.zeta_ref = np.zeros(3, dtype=float)       # zeta1-3        - control target motor reference (used in PARKING, HOMING)
        self.error_signal = np.zeros(3, dtype=float)   # theta1-3 error btw theta_ref and theta_meas
        self.error_integral = np.zeros(3, dtype=float) # theta1-3 error btw theta_ref and theta_meas
        self.cameraQ_ref = None
        self.cameraQ_ref_last = None
        self.goto_complete_callback = None                   # callback function when no longer deviating
        self.rotate_complete_callback = None                 # callback function when no longer deviating
        self.slew_complete_callback = None                   # callback function when no longer slewing
        self.parking_complete_callback = None                # callback function when reached parking position
        self.homing_complete_callback = None                 # callback function when reached homing position
        self.is_deviating = False                            # cost signal is > Kc Arc Minutes²
        self.is_slewing = False                              # a velicity_sp is non-zero
        self.is_moving = False                               # mount is deviating, slewing or tracking
        self.was_moving = False                              # previous control step movement flag
        self.ff_inhibit_ticks = 0                            # number of ticks to supress FF after any SP change
        self.omega_kp = np.zeros(3, dtype=float)       # omega1-3 due to proportional error
        self.omega_ki = np.zeros(3, dtype=float)       # omega1-3 due to integrated error
        self.omega_kd = np.zeros(3, dtype=float)       # omega1-3 due to velocity damping (derivative of position)
        self.omega_ff = np.zeros(3, dtype=float)       # omega1-3 due to requested velocity feed forward (slew, tracking)
        self.omega_pec = np.zeros(3, dtype=float)
        self.omega_min = np.zeros(3, dtype=float)      # omega1-3 min allowable angular velocity (0=axis at limit, no more -ve)
        self.omega_max = np.zeros(3, dtype=float)      # omega1-3 max allowable angular velocity (0=axis at limit, no more +ve)
        self.omega_tgt = np.zeros(3, dtype=float)      # omega1-3 motor angular velocity raw pid output
        self.omega_ctl = np.zeros(3, dtype=float)      # omega1-3 motor angular velocity constrained output
        self.omega_op = np.zeros(3, dtype=float)       # omega1-3 motor angular velocity control output
        self.reset_offsets()
        self.reset_theta()
        self.time_meas = None                # Time of measurement
        self.time_goto = None                # Time that goto callback was set
        self.time_step = time.monotonic()    # Time that control step was done
        self.dt = dt    # Time interval since last control step in seconds
        if self.control_loop_duration:
            asyncio.create_task(self._control_loop())

    #------- Helper functions ---------
    def set_Ka_array(self, Ka):
        if isinstance(Ka, (list, tuple)):
            self.Ka = np.array(Ka, dtype=float)
        elif isinstance(Ka, float) and Ka>0 and Ka<10:
            self.Ka = np.array([Ka, Ka, Ka], dtype=float)
        else:
            self.Ka = np.array([5,5,5], dtype=float)

    def set_Kv_array(self, Kv):
        if  isinstance(Kv, (list, tuple)):
            self.Kv = np.array(Kv, dtype=float)
        elif isinstance(Kv, float) and Kv>0 and Kv<10:
            self.Kv = np.array([Kv, Kv, Kv], dtype=float) 
        else:
            self.Kv = np.array([ self.controllers[axis]._model.maxDPS for axis in range(3) ], dtype=float)

    def reset_offsets(self, axes=None):
        """Reset alpha/delta_v_sp, _offset, _ref_last for each axes. 
           Where axes is a list from ["ra", "dec", "pa", "alt", "az", "roll"], and defaults to all"""
        self.reset_delta_offsets(axes)
        self.reset_alpha_offsets(axes)
        self.clear_theta_ref_cache()

    def reset_delta_offsets(self, axes):
        if axes is None:
            self.delta_v_sp = np.zeros(3, dtype=float)     # Setpoint for ra, dec, polar anglular velocities
            self.delta_offst = np.zeros(3, dtype=float)    # ra, dec, polar anglular offsets
            self.delta_ref_last = np.zeros(3, dtype=float) # ra, dec, polar angular reference position of last control step
            return
        DELTA_MAP = {'ra': 0, 'dec': 1, 'pa': 2}    
        for key, idx in DELTA_MAP.items():
            if key in axes:
                self.delta_v_sp[idx] = 0.0
                self.delta_offst[idx] = 0.0
                self.delta_ref_last[idx] = 0.0

    def reset_alpha_offsets(self, axes):
        if axes is None:
            self.alpha_v_sp = np.zeros(3, dtype=float)     # Setpoint for az, alt, roll angular velocities
            self.alpha_offst = np.zeros(3, dtype=float)    # az, alt, roll angular offsets
            return
        ALPHA_MAP = {'az': 0, 'alt': 1, 'roll': 2}
        for key, idx in ALPHA_MAP.items():
            if key in axes:
                self.alpha_v_sp[idx] = 0.0
                self.alpha_offst[idx] = 0.0

    def reset_theta(self):
        self.theta_ref = np.zeros(3, dtype=float)      # theta1-3 motor angular reference position
        self.theta_ref_last = np.zeros(3, dtype=float) # theta1-3 motor angular reference position of last control step

    def reset_sp(self, alpha_pv=None):               # align all SP with alpha_meas (defaults to current pid measured position)
        if alpha_pv is not None:
            self.alpha_pv = alpha_pv
        self.alpha2body(self.alpha_pv)
        self.delta_ref = self.body2delta()           
        self.delta_sp = self.delta_ref            
        self.alpha_ref = self.alpha_pv
        self.alpha_sp = self.alpha_pv                  
        self.reset_offsets() 
        self.ff_inhibit_ticks = 2  # suppress FF for 2 ticks after any SP change

    def body_pa(self):
        return wrap180(0.0 - rad2deg(self.body.parallactic_angle()))
    
    def body2alpha(self):
        self.observer.date = ephem.Date(datetime.datetime.utcnow())
        self.observer.epoch = ephem.now()
        self.body.compute(self.observer)
        alt = rad2deg(self.body.alt)
        az = rad2deg(self.body.az)
        roll = self.body_pa_offset
        return np.array([az, alt, roll], dtype=float)

    def alpha2body(self, alpha):
        self.observer.date = ephem.Date(datetime.datetime.utcnow())
        self.observer.epoch = ephem.now()
        ra_rad, dec_rad = self.observer.radec_of(deg2rad(alpha[0]), deg2rad(alpha[1]))
        self.body._ra = ra_rad
        self.body._dec = dec_rad
        self.body.compute(self.observer)
        self.body_pa_offset = alpha[2]

    def body2delta(self):
        self.observer.date = ephem.Date(datetime.datetime.utcnow())
        self.observer.epoch = ephem.now()
        self.body.compute(self.observer)
        ra_deg = rad2deg(self.body._ra)
        dec_deg = rad2deg(self.body._dec)
        alt = rad2deg(self.body.alt)
        az = rad2deg(self.body.az)
        parallactic_angle = calc_parallactic_angle(az, alt, self.polaris._sitelatitude)
        pa_deg = wrap360(self.body_pa_offset + parallactic_angle)
        return np.array([ra_deg, dec_deg, pa_deg], dtype=float)
    

    def delta2body(self, delta):
        self.observer.date = ephem.Date(datetime.datetime.utcnow())
        self.observer.epoch = ephem.now()
        self.body._ra = deg2rad(delta[0])
        self.body._dec = deg2rad(delta[1])
        self.body.compute(self.observer)
        alt = rad2deg(self.body.alt)
        az = rad2deg(self.body.az)
        if self.polaris._trackingrate == 0:   # only update roll when sidereal tracking
            parallactic_angle = calc_parallactic_angle(az, alt, self.polaris._sitelatitude)
            self.body_pa_offset = wrap360(delta[2] - parallactic_angle)

    def orbital2delta(self):
        orbital = None
        self.orbital_sp_status = [0, 0, 0]
        if self.polaris._trackingrate == 1:   # 1=Lunar
            orbital = orbital_data["Moon"]["body"]
        elif self.polaris._trackingrate == 2: # 2=Solar
            orbital = orbital_data["Sun"]["body"]
        elif self.polaris._trackingrate == 3: # 3=Custom
            if self.orbital_sp_name in orbital_data:
                orbital = orbital_data[self.orbital_sp_name]["body"]

        if orbital and self.polaris._trackingrate in [1,2,3]:
            self.observer.date = ephem.Date(datetime.datetime.utcnow()) + ephem.second * 2.5    # 2.5 seconds in the future
            self.observer.epoch = ephem.now()
            orbital.compute(self.observer)
            # self.logger.info(f"Tracking - Alt: {rad2deg(orbital.alt):.2f} Az: {rad2deg(orbital.az):.2f}")    
            orb_alt = rad2deg(orbital.alt)
            orb_az = rad2deg(orbital.az)
            orb_ra = rad2deg(orbital.ra)
            orb_dec = rad2deg(orbital.dec)
            ra_change = abs(orb_ra - self.delta_sp[0])
            dec_change = abs(orb_dec - self.delta_sp[1])
            is_keep_roll_angle = True
            is_orbital_trackable = 1 if orb_alt < 10 else 2
            if is_orbital_trackable == 2:
                self.delta_sp[0] = orb_ra
                self.delta_sp[1] = orb_dec
                parallactic_angle = calc_parallactic_angle(orb_az, orb_alt, self.polaris._sitelatitude)
                self.delta_sp[2] = self.body_pa_offset + parallactic_angle  # keep roll angle stable
            self.orbital_sp_status = [is_orbital_trackable, orb_az, orb_alt]
        else:
            # switch back to sidereal if no orbital found
            self.polaris._trackingrate = 0

    #------- Functions to change SP, Targets and Mode ---------

    def set_tracking_on(self):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        if self.mode=='AUTO':
            track_target = self.alpha_ref.copy()
        else:
            track_target = self.alpha_pv.copy()
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
            self.ff_inhibit_ticks = 2  # suppress FF for 2 ticks after any SP change
            self.clear_theta_ref_cache()


    def set_no_target(self):
        self.target_type = 'NONE'
        self.reset_offsets()

    def set_alpha_target(self, sp: dict[str, float]):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.reset_offsets()      
        self.target_type = 'ALPHA'
        # Safely update alpha_sp components if provided
        default = self.body2alpha() if self.mode == 'TRACK' else self.alpha_sp
        alpha = [
            sp.get("az",   default[0]),
            sp.get("alt",  default[1]),
            sp.get("roll", default[2]),
        ]
        self.alpha_sp[:] = alpha
        self.alpha2body(alpha)
        self.delta_sp[:] = self.body2delta()
        self.ff_inhibit_ticks = 2  # suppress FF for 2 ticks after any SP change
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_alpha_axis_velocity(self, axis, sp=0.0):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.alpha_v_sp[axis] = sp
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_delta_target(self, sp: dict[str, float]):
        """" Beware ra parameter is in hours, ra/dec changes keep pa constant """
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.reset_offsets()
        self.target_type = 'DELTA'
        default = self.delta_sp
        delta = [
            sp.get("ra",  default[0] / 15) * 15,   # accept ra in hours, store as deg
            sp.get("dec", default[1]),
            sp.get("pa",  default[2]),
        ]
        self.delta_sp[:] = delta
        self.delta2body(delta)
        self.alpha_sp[:] = self.body2alpha()
        self.ff_inhibit_ticks = 2
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def set_delta_axis_velocity(self, axis, sp=0.0):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        self.delta_v_sp[axis] = sp
        if self.mode in ['IDLE','AUTO']:
            self.set_pid_mode('TRACK')
    
    def set_pano_offset(self, offsets):
        dictmap = {
            'ra': (self.delta_offst, 0),
            'dec': (self.delta_offst, 1),
            'pa': (self.delta_offst, 2),
            'az': (self.alpha_offst, 0),
            'alt': (self.alpha_offst, 1),
            'roll': (self.alpha_offst, 2),
        }
        for key, val in offsets.items():
            if key in dictmap:
                arr, idx = dictmap[key]
                arr[idx] = 0.0 if val == 0 else arr[idx] + val
            else:
                self.logger.info(f'PanoOffset key "{key}":{val} is invalid')
        if self.mode=="IDLE":
            self.set_pid_mode("AUTO")

    def set_zeta_ref_to_home(self):
        if self.mode in ['PRESETUP']:
            return
        self.reset_offsets()
        self.target_type = "ZETA"
        self.zeta_ref = np.zeros(3, dtype=float)

    def set_zeta_ref_to_park(self):
        if self.mode in ['PRESETUP']:
            return
        self.reset_offsets()
        self.target_type = "ZETA"
        self.zeta_ref = np.array([Config.m1_park, Config.m2_park, Config.m3_park], dtype=float)

    async def set_tle_orbital_target(self, name):
        self.reset_offsets()
        orbname, msg = await create_tle_orbital_celestrak(self.logger, name)
        self.target_type = "ORBITAL"
        self.orbital_sp_name = orbname
        self.orbital_sp_fetchmsg = msg

    async def set_xephem_orbital_target(self, name):
        self.reset_offsets()
        orbname, msg = await create_xephem_orbital_jpl(self.logger, name)
        self.target_type = "ORBITAL"
        self.orbital_sp_name = orbname
        self.orbital_sp_fetchmsg = msg

    async def set_orbital_target(self, name):
        self.reset_offsets()
        self.target_type = "ORBITAL"
        if name in orbital_data:
            self.orbital_sp_name = name
            self.orbital_sp_fetchmsg = None
        else:
            self.orbital_sp_name = None
            self.orbital_sp_fetchmsg = f'Cannot find orbital with name "{name}"'

    def rotator_move_relative(self, sp=0.0):
        if self.mode in ['PRESETUP', 'PARK', 'LIMIT']:
            return
        axis=2
        self.alpha_sp[axis] = self.alpha_sp[axis] + sp
        self.alpha_v_sp[axis] = 0
        self.alpha_offst[axis] = 0
        if self.mode == 'IDLE':
            self.set_pid_mode('AUTO')

    def goto_timeout(self):
        return self.time_goto and (ephem.now() - self.time_goto) * 24 * 3600 > 45
    
    def set_goto_complete_callback(self, fn):
        self.is_deviating = True
        self.time_goto = ephem.now()
        self.goto_complete_callback = fn
              
    def set_rotate_complete_callback(self, fn):
        self.is_deviating = True
        self.rotate_complete_callback = fn
              
    def set_slew_complete_callback(self, fn):
        self.is_slewing = True
        self.slew_complete_callback = fn
              
    def set_parking_complete_callback(self, fn):
        self.parking_complete_callback = fn
              
    def set_homing_complete_callback(self, fn):
        self.homing_complete_callback = fn
              
    def ack_limit_alarm(self):
        self.ack_limit_timestamp = datetime.datetime.now()
        self.set_pid_mode('IDLE')

    def set_theta_ref_cache(self, cause, theta):
        self.theta_ref = theta
        self.theta_ref_cache = theta
        self.theta_ref_cache_cause = cause

    def clear_theta_ref_cache(self):
        self.theta_ref_cache = None
        self.theta_ref_cache_cause = None
        

    #------- Control step functions ---------
    def alpha_limit_step(self, alpha_pv, alpha_ref, max_step_deg=12, min_frac=0.01):
        """
        Step toward alpha_ref from alpha_pv.
        Az/alt are stepped in SO(3) (geodesic, well-behaved near zenith).
        Roll is stepped independently in angle space (preserves az/alt during roll-only moves).
        """
        # ── Az/alt component: step in SO(3) using boresight vectors ──────────
        # Build quaternions with roll=0 for both pv and ref
        # This isolates the az/alt motion from roll
        q_pv_noroll  = azaltroll_to_q(alpha_pv[0],  alpha_pv[1],  0.0)
        q_ref_noroll = azaltroll_to_q(alpha_ref[0], alpha_ref[1], 0.0)

        azalt_angle, _, _ = quaternion_difference(q_pv_noroll, q_ref_noroll)
        roll_delta = wrap180(alpha_ref[2] - alpha_pv[2])
        total_travel = max(azalt_angle, abs(roll_delta))

        if total_travel < 1e-6:
            return alpha_ref

        frac = np.clip(max_step_deg / total_travel, min_frac, 1.0)

        # Step az/alt via slerp (geodesic, singularity-safe)
        q_step_noroll = Quaternion.slerp(q_pv_noroll, q_ref_noroll, frac)
        az_step, alt_step, _ = q_to_azaltroll(q_step_noroll)

        # Step roll linearly (independent axis, preserves az/alt)
        roll_step = alpha_pv[2] + frac * roll_delta

        return np.array([az_step, alt_step, roll_step])
    
    
    def track_target(self):
        # Update alpha_ref based on current mode
        if self.mode in ['PRESETUP', 'PARKING', 'HOMING', 'PARK', 'LIMIT']:
            self.reset_sp()
        
        elif self.mode in ['IDLE']:
            if (self.alpha_ref[0]==0):                       # only reset sp in special case
                self.reset_sp()
            self.alpha_offst = np.zeros(3, dtype=float)      # in case we switch to AUTO

        elif self.mode == 'AUTO':
            self.delta_offst = clamp_offset(self.delta_offst + self.dt * self.delta_v_sp)
            self.delta_ref = clamp_delta(self.delta_sp + self.delta_offst)
            self.delta2body(self.delta_ref)
            # when in AUTO ignore body, and use the alpha_sp + alpha_offset
            self.alpha_offst = clamp_offset(self.alpha_offst + self.dt * self.alpha_v_sp)
            self.alpha_ref = clamp_alpha(self.alpha_sp + self.alpha_offst)

        elif self.mode == 'TRACK':
            # update delta_sp based on any non-sidereal tracking (Lunar, Solar, Other)
            self.orbital2delta()

            # Apply relevant delta slew velocities
            self.delta_offst = clamp_offset(self.delta_offst + self.dt * self.delta_v_sp)
            self.delta_ref_last = self.delta_ref
            self.delta_ref = clamp_delta(self.delta_sp + self.delta_offst)
            self.delta2body(self.delta_ref)
            self.alpha_ref = clamp_alpha(self.body2alpha())
            self.alpha_sp = self.alpha_pv             # in case we switch to AUTO

        
        # Remember cameraQ_ref and last cameraQ_ref for calculating FF
        self.alpha_ref = np.array(reachable_azaltroll(*self.alpha_ref, roll_adj=self.polaris._sm.roll_adj))
        self.gamma_sp = delta_to_gamma(self.delta_ref)
        cameraQ_ref = azaltroll_to_q(*self.alpha_ref)
        if self.cameraQ_ref is None:
            # first run — no previous reference
            self.cameraQ_ref = cameraQ_ref
            self.cameraQ_ref_last = cameraQ_ref
        else:
            self.cameraQ_ref_last = self.cameraQ_ref
            self.cameraQ_ref = cameraQ_ref

        # Step in alpha space with az/alt locked during roll changes
        alpha_step = self.alpha_limit_step(self.alpha_pv, self.alpha_ref)
        cameraQ_step = azaltroll_to_q(*alpha_step)  
        
        # IK from the stepped alpha
        motorQ_ref   = self.polaris._sm.topoQ_to_baseQ(cameraQ_step)
        self.theta_ref = np.array(q_to_theta(motorQ_ref, self._lp))


    def measure(self, delta_pv, alpha_pv, theta_pv, zeta_meas):
        now = ephem.now()
        # if not self.time_meas:
        #     self.alpha_sp = alpha_meas     # initialise alpha_sp with first measurement
        self.delta_pv = delta_pv
        self.alpha_pv = alpha_pv
        self.theta_pv = theta_pv
        self.zeta_meas = zeta_meas
        self.time_meas = now
        self._lp.update(*theta_pv)
        self._lp.update_zeta(zeta_meas)
        self._lp.check_for_gimbal_lock()
        self.gamma_pv = delta_to_gamma(delta_pv)

    def predict(self):          # This is not used in the PID Control Loop
        self.theta_pv = clamp_theta(self.theta_pv + self.dt * self.omega_op)
        self.time_meas = self.time_meas + self.dt

    def feed_forward(self):
        # inhibit FF after any step SP change.
        if self.ff_inhibit_ticks > 0:
            self.ff_inhibit_ticks -= 1
            return
        self.omega_ff = np.zeros(3, dtype=float)
        if self.mode == "TRACK":
            if self.dt > 0 and self.polaris._tracking:
                # Desired angular velocity vector based on change in cameraQ_ref
                motorQ_now  = self.polaris._sm.topoQ_to_baseQ(self.cameraQ_ref)
                motorQ_last = self.polaris._sm.topoQ_to_baseQ(self.cameraQ_ref_last)
                omega_base = calculate_angular_velocity_vector(motorQ_last, motorQ_now, self.dt)
                # Compute Jacobian (converts joint rates into physical motion) ie ω = J(θ) · θ_dot
                J = theta_to_jacobian(*self.theta_pv)
                # Solve inverse Jacobian to calc joint rates for given physical motion ie omega_ff = θ_dot = J⁻¹ ω
                theta_dot = np.linalg.solve(J, omega_base)
                self.omega_ff = np.degrees(theta_dot)
                # for non sidereal tracking,  ensure M3 ff is zero
                if self.polaris._trackingrate != 0: 
                    self.omega_ff[2] = 0                                 
        # Feed forward slew velocities when in auto mode
        elif self.mode == "AUTO":
            self.omega_ff = self.alpha_v_sp

        # PEC contribution — independent of ff_inhibit gating (that's for setpoint-
        # change transients, unrelated to PEC), added as its own velocity term.
        self.omega_pec = np.zeros(3, dtype=float)
        if Config.advanced_pec and self.mode == "TRACK":
            omega_pec_B = getattr(self.polaris._sm, 'omega_pec_B', None)
            if omega_pec_B is not None and np.any(omega_pec_B):
                J = theta_to_jacobian(*self.theta_pv)
                theta_dot_pec = np.linalg.solve(J, np.radians(omega_pec_B))
                self.omega_pec = np.degrees(theta_dot_pec)
                if self.polaris._trackingrate != 0:
                    self.omega_pec[2] = 0            

    def prevent_windup(self):
        if self.theta_ref_cache is not None or self.zeta_meas is None or self.mode == 'LIMIT':
            return
        zeta = np.array(self.zeta_meas)
        d1 = max(angular_difference(self.alpha_pv[0],self.alpha_ref[0]), angular_difference(self.theta_pv[0],self.theta_ref[0]), key=abs)
        d3 = max(angular_difference(self.alpha_pv[2],self.alpha_ref[2]), angular_difference(self.theta_pv[2],self.theta_ref[2]), key=abs)
        z1_implied = zeta[0] + d1
        z3_implied = zeta[2] + d3
        safety = Config.zeta_safety_margin
        t1_fix = 360 if z1_implied < Config.z1_min_limit+safety else -360 if z1_implied > Config.z1_max_limit-safety else 0
        t3_fix = 360 if z3_implied < Config.z3_min_limit+safety else -360 if z3_implied > Config.z3_max_limit-safety else 0
        if t1_fix != 0 or t3_fix != 0:
            # UNWIND: if we need to unwind then adjust target and cahce
            motorQ_final = self.polaris._sm.topoQ_to_baseQ(azaltroll_to_q(*self.alpha_ref))
            theta_final = np.array(q_to_theta(motorQ_final, self._lp))
            theta_final[0] += t1_fix
            theta_final[2] += t3_fix
            cause = 'UNWIND'
            msg = f'{cause} Transition'
            if t1_fix!=0: msg+= f' | Implied z1 {z1_implied:+.1f} Remap t1 {theta_final[0]-t1_fix:+.1f} to {theta_final[0]:+.1f}'
            if t3_fix!=0: msg+= f' | Implied z3 {z3_implied:+.1f} Remap t3 {theta_final[2]-t3_fix:+.1f} to {theta_final[2]:+.1f}'
            self.logger.info(msg)
            self.set_theta_ref_cache(cause, theta_final)
        else:
            # FLIP: if far away from target (in M1 or M3) then cache the target
            distance = self.theta_ref - self.theta_pv
            if abs(distance[0])>30 or abs(distance[2])>30:
                cause = 'FLIP CW' if self._lp.flipCW else 'FLIP CCW'
                self.logger.info(f'{cause} Transition | theta_ref_cache: {self.theta_ref[0]:+.1f},{self.theta_ref[1]:+.1f},{self.theta_ref[2]:+.1f}')
                self.set_theta_ref_cache(cause, self.theta_ref.copy())
                self._lp.flipCW = not self._lp.flipCW

    def errsignal(self):
        # calc the error signal off theta (aligned motor angles) or zeta (raw motor angles)
        if self.mode in ['HOMING', 'PARKING']:
            self.error_signal = self.zeta_ref - self.zeta_meas
        else:        
            if self.theta_ref_cache is None:
                self.prevent_windup()
                self.error_signal = self.theta_ref - self.theta_pv
            else:
                self.theta_ref = self.theta_ref_cache
                self.error_signal = self.theta_ref_cache - self.theta_pv
                # if close to cached target then reset the cache
                if abs(self.error_signal[0])<10 and abs(self.error_signal[2])<10:
                    self.clear_theta_ref_cache()
        # Log every position for debugging
        if Config.log_position:
            now = time.monotonic()
            every_Xs = not hasattr(self, '_last_log_time') or now - self._last_log_time > Config.log_position_rate
            if every_Xs:
                self._last_log_time = now
                self.logger.info(f"POSLOG"
                    f", | alpha_ref: ,{self.alpha_ref[0]:+.1f},{self.alpha_ref[1]:+.1f},{self.alpha_ref[2]:+.1f}"
                    f", | alpha_pv: ,{self.alpha_pv[0]:+.1f},{self.alpha_pv[1]:+.1f},{self.alpha_pv[2]:+.1f}"
                    f", | theta_ref: ,{self.theta_ref[0]:+.1f},{self.theta_ref[1]:+.1f},{self.theta_ref[2]:+.1f}"
                    f", | theta_pv: ,{self.theta_pv[0]:+.1f},{self.theta_pv[1]:+.1f},{self.theta_pv[2]:+.1f}"
                    f", | zeta_pv: ,{self.zeta_meas[0]:+.1f},{self.zeta_meas[1]:+.1f},{self.zeta_meas[2]:+.1f}"
                    f", | motors: ,{[motor.get_cmdstr() for motor in self.polaris._motors.values()]}"
                )
        # Per-axis deviation flags
        tollerance = Config.pid_Kc / 60 / 20  if self.mode=="TRACK" else Config.pid_Kc / 60
        self.is_axis_deviating = np.abs(self.error_signal) > tollerance
        # calc cost signal and flags
        self.is_deviating = np.any(self.is_axis_deviating)
        self.cost_signal = np.sum(self.error_signal ** 2)
        self.is_slewing = np.any(self.alpha_v_sp != 0) or np.any(self.delta_v_sp != 0)
        self.was_moving = self.is_moving
        self.is_moving = self.is_deviating or self.is_slewing or self.mode=="TRACK"

    def errintegral(self):
        # setup some constants for calcs below
        Ki = np.array(Config.pid_Ki, dtype=float) 
        Kd = np.array(Config.pid_Kd, dtype=float)
        integration_rate_limit = 1/60                                                            # max deg per sec for the integration component
        self.is_axis_preloading = np.abs(self.error_signal) > integration_rate_limit * 1      # preload when greater than integration limit over 1 sec
        i_limit = np.where(Ki != 0, integration_rate_limit / Ki, 0)    # limit integral rate / Ki

        # calc the integral error if tracking or slewing
        if self.mode=='TRACK' or self.is_slewing:
            # Preload to cancel derivative term: omega_kd = -Kd * omega_op, or use last integral value
            preload = np.where(Ki != 0, (Kd * self.omega_ff) / Ki, 0)
            preload_masked = np.where(self.is_axis_preloading, preload, self.error_integral)
            # Conditional integration mask ie not pulse guiding and not exceeding omega speed limits
            can_integrate = np.logical_or(
                np.logical_and(self.omega_tgt >= self.omega_min, self.omega_tgt <= self.omega_max),
                np.sign(self.error_signal) != np.sign(self.omega_tgt)
            ) & (~self.polaris._ispulseguiding)
            delta_integral = np.where(~self.is_axis_preloading & can_integrate, self.error_signal, 0)
            updated_integral = preload_masked + delta_integral * self.dt
            self.error_integral = np.clip(updated_integral, -i_limit, +i_limit)
            if self.polaris._trackingrate != 0: 
                self.error_integral[2] = 0                                 # for non sidereal tracking,  ensure M3 integral is zero
        else:
            self.error_integral = np.zeros(3, dtype=float)

   
    def pid(self):
        self.omega_kp = np.array(Config.pid_Kp, dtype=float) * self.error_signal    # increase control proportional to error
        self.omega_ki = np.array(Config.pid_Ki, dtype=float) * self.error_integral  # increase control when integral error is high
        self.omega_kd = - np.array(Config.pid_Kd, dtype=float) * self.omega_op      # dampen control when velocity high
        self.omega_tgt = self.omega_kp + self.omega_ki + self.omega_kd + self.omega_ff + self.omega_pec

    def constrain(self):
        self.set_Ka_array(Config.pid_Ka) 
        self.set_Kv_array(Config.pid_Kv) 
        # Compute constrained acceleration
        accel_clipped = np.array([0, 0, 0], dtype=float)
        if self.dt > 0:
            delta_omega = self.omega_tgt - self.omega_op
            accel = delta_omega / self.dt
            accel_clipped = np.clip(accel, -self.Ka, self.Ka)
        # Apply clipped acceleration, expotential smoothing, and clip velocity
        self.omega_ctl = self.omega_op + accel_clipped * self.dt
        self.omega_ctl = self.omega_ctl * (1.0 - Config.pid_Ke) + Config.pid_Ke * self.omega_op
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
            isnotPARKorHOMEorPRESETUP = self.mode not in ['PRESETUP', 'PARK', 'HOME']
            if isLimited and isUnAcked and isnotPARKorHOMEorPRESETUP:
                self.set_pid_mode('LIMIT')
                self.parking_complete_callback = None  # Cancel any parking underway
                self.homing_complete_callback = None  # Cancel any homeing underway
                self.clear_theta_ref_cache()

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
        self.omega_op = np.zeros(3, dtype=float)
        # [0.0, 0.0059018, 0.0175906, 0.0478282, 0.0892742, 0.2079884]
        for axis in range(3):
            self.omega_op[axis] = self.omega_ctl[axis]
        # send control to motor when moving
        if self.is_moving and self.mode in ['AUTO', 'TRACK', 'HOMING', 'PARKING']:
            for axis in range(3):
                # if Config.log_polaris_ble and axis==1:
                #     q = self.polaris._q1
                #     self.logger.info(f"Motor 2 omega_meas1-3: {self.polaris._omega_raw[0]:+.5f} {self.polaris._omega_raw[1]:+.5f} {self.polaris._omega_raw[2]:+.5f}, t_meas: {self.theta_meas[1]:.4f}, t_ref: {self.theta_ref[1]:.4f}, kp: {self.omega_kp[1]:.4f}, ki: {self.omega_ki[1]:.4f}, kd: {self.omega_kd[1]:.4f}, ff: {self.omega_ff[1]:.4f}, op: {self.omega_op[1]:.4f}")
                await self.controllers[axis].set_motor_speed(self.omega_op[axis], rate_unit='DPS', ramp_duration=self.dt, allow_PWM=True, tracking=(self.mode=="TRACK"))
        # If we have goto timeout or stopped moving; while  in AUTO, HOMING or PARKING, go to IDLE
        if (self.goto_timeout() or not self.is_moving) and self.mode in ['AUTO', 'HOMING', 'PARKING']:
            self.set_pid_mode('IDLE')
            self.was_moving = True
            self.is_moving = False
            self.time_goto = None
        # Stop motors when transitioning from moving to stopped
        if self.was_moving and not self.is_moving:
            for axis in range(3):
                await self.controllers[axis].set_motor_speed(0)

    def control_step_calculate(self):
        now = time.monotonic()
        if self.control_loop_duration:
            self.dt = now - self.time_step
            if self.dt < 0.05:
                return
        self.time_step = now
        if Config.advanced_pec:
            self.polaris._sm.apply_pec_drift_correction()
        if self.time_meas:      # Only process if we have a measurement
            self.track_target() # Update theta_ref with target's new position
            self.feed_forward() # Feed forward tracking velocities when in TRACK mode
            self.errsignal()    # Update error_signal with deviation from theta_ref
            self.errintegral()  # Update error_integral with accumulation of err_signal
            self.pid()          # Update omega_tgt, calculate raw PID control target
            self.constrain()    # Update omega_ctl, constrain velocity and acceleration
            self.notify()       # Notify any callback of no longer deviating
            self.telemetry()    # send to Alpaca Pilot

    async def control_step_execute(self):
        """Async part - motor commands only."""
        if self.time_meas:
            await self.control()      # Update omega_op, constrain with valid op control values

    async def control_step(self):
        self.control_step_calculate()
        await self.control_step_execute()

    async def _control_loop(self):
        while not self._stop_flag.is_set():
            # Only run if 518 messages have stopped flowing
            # ie device disconnected or not sending position updates
            if self.polaris._age_518_seconds > 0.5:
                self.control_step_calculate()      
                await self.control_step_execute()      
            delay = self.control_loop_duration if self.polaris._connected else 2.0
            await asyncio.sleep(delay)

    def notify(self):
        if ((not self.is_deviating) or self.goto_timeout()) and self.goto_complete_callback:
            self.goto_complete_callback()
            self.goto_complete_callback = None
            self.time_goto = None
        if not self.is_deviating and self.rotate_complete_callback:
            self.rotate_complete_callback()
            self.rotate_complete_callback = None
        if not self.is_deviating and self.parking_complete_callback:
            self.parking_complete_callback()
            self.parking_complete_callback = None
        if not self.is_deviating and self.homing_complete_callback:
            self.homing_complete_callback()
            self.homing_complete_callback = None
        if not self.is_slewing and self.slew_complete_callback:
            self.slew_complete_callback()
            self.slew_complete_callback = None

    def telemetry(self):
        # Log meas, state and ref for websocket streaming
        payload = { 
            "Δ_sp": self.delta_ref.tolist(),
            "Δ_pv": self.delta_pv.tolist(),
            "α_sp": self.alpha_ref.tolist(),
            "α_pv": self.alpha_pv.tolist(),
            "θ_sp": self.theta_ref.tolist(), 
            "θ_pv": self.theta_pv.tolist(), 
            "ω_kp": self.omega_kp.tolist(), 
            "ω_ki": self.omega_ki.tolist(),  
            "ω_kd": self.omega_kd.tolist(), 
            "ω_ff": self.omega_ff.tolist(), 
            "ω_op": self.omega_op.tolist(), 
        }
        pidlogger = logging.getLogger('pid') 
        pidlogger.info(payload)

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
        self.set_alignQ_to_identity()

    def set_alignQ_to_identity(self):
        self.sync_history = []                  # list of sync events, both AzAlt and Roll
        self.last_sync_time = None              # timestamp used to fade LGA to zero as time passes
        self.corrQ_LGA = Quaternion(1,0,0,0)    # cache of LGA stored in forward Kinematics path, used in forward and inverse paths (None if no adj remaining)
        self.corrQ_RBC = Quaternion(1,0,0,0)    # cache of MAC stored in forward Kinematics path, used in forward and inverse paths (None if no adj remaining)
        self.params_RBC = MountModelParams.from_config(Config)
        self.scc_error = 0                      # cache of Slew & Center Correction error magnitude, either LGA or ZRC (for Kinematics page)
        self.rbc_error = 0                      # cache of Rotation Bias Correction  error magnitude, (for Kinematics page)
        self.mpa_error = 0                      # cache of Multi Point Alignment RMS Residual error, (for Alignment page)
        self.aligned_count = 0                  # number of AzAlt syncs used in last optimisation
        self.alignQ_B2T = Quaternion(1,0,0,0)       # cached adjustment quaternion for azalt syncing, initially identity
        self.alignQ_B2T_inv = Quaternion(1,0,0,0)   # cached inverse adjustment quaternion for azalt syncing, initially identity
        self.alignQ_B2T_message = ""                # message from last optimisation
        self.q_guide_B = Quaternion(1,0,0,0)        # accumulation of pulse guide corrections
        self.q_syncguide_B = Quaternion(1,0,0,0)    # accumulation of sync guide corrections
        self.valid_sync_guide = False               # flag to indicate pure sidereal tracking since last sync
        self.delta_guide_accum = np.zeros(3, dtype=float) 
        self.delta_guide_pulse = np.zeros(3, dtype=float) 
        self.equatorial_axes_B = (None, None, None)
        self.tilt_adj_az = 0                    # alignQ_B2T Tilt azimuth (°): direction of steepest upward inclination (info only)    
        self.tilt_adj_mag = 0                   # alignQ_B2T Tilt magnitude (°): angle of inclination from horizontal plane (info only)
        self.az_adj = 0                         # alignQ_B2T Azimuth correction (°): azimuth axis correction to apply (info only)
        self.roll_adj = 0                       # Roll axis correction (°): optimised adjustment offset from roll syncing 
        self.refresh_pid_setpoints_from_q1()
        self.streamSyncDataReset()
        self.init_pec_model()

    def standard_entry(self):
        entry = {
            "timestamp": format_timestamp(),
            "deleted": False,
            "p_az": self.polaris._p_azimuth,    # store raw motorQ_state Az
            "p_alt": self.polaris._p_altitude,  # store raw motorQ_state Alt
            "p_roll": self.polaris._p_roll,     # store raw motorQ_state Roll
            "a_ra": None,
            "a_dec": None,
            "a_az": None,
            "a_alt": None,
            "a_roll": None,
            "p_roll_pv": None,                  # store MAC + QUEST Roll
        }
        return entry

    def entry_to_pred_vector(self, entry):
        """
        Convert a sync history entry's raw stored p_az/p_alt/p_roll into a predicted unit vector.
        Only apply [MAC] as its the only static theta frame correction. Do not apply [SGC], [PGC] or [LGA] 
        """
        if Config.advanced_align_mac:
            motorQ_entry = azaltroll_to_q(entry["p_az"], entry["p_alt"], entry["p_roll"])
            motorQ_adj, _   = apply_mechanical_corrections(motorQ_entry, self.params_RBC)
            eff_az, eff_alt, _ = q_to_azaltroll(motorQ_adj)
        else:
            eff_az  = entry["p_az"]
            eff_alt = entry["p_alt"]
        return azalt_to_vector(eff_az, eff_alt), eff_az, eff_alt



    def baseQ_to_topoQ(self, motorQ_C2B_state):
        """
        Forward kinematics: Base frame → Topocentric frame.
        motorQ → [MAC] → [SGC] → [PGC] → [QUEST] → [LGA] → [roll_adj] → cameraQ
        """
        motorQ_C2B_pv = motorQ_C2B_state

        # Apply Mechanical Corrections (MAC)
        if Config.advanced_align_mac:
            self.corrQ_RBC, self.rbc_error = get_mechanical_correction_q(motorQ_C2B_state, self.params_RBC)
            motorQ_C2B_pv = self.corrQ_RBC * motorQ_C2B_state

        # Apply Sync Guide Corrections (SGC)
        motorQ_C2B_pv = self.get_sync_guiding_correction_q() * motorQ_C2B_pv

        # Apply Pulse Guide Corrections (PGC)
        motorQ_C2B_pv = self.q_guide_B * motorQ_C2B_pv

        # Apply alignQ_B2T model (QUEST)
        cameraQ_C2T_pv = self.alignQ_B2T * motorQ_C2B_pv

        # Apply Local Gaussian Adjustment (LGA)
        if Config.advanced_scc_enabled and Config.advanced_scc_choice==1:
            self.corrQ_LGA, self.scc_error = self.get_local_guassian_adjustment_q(cameraQ_C2T_pv)
            cameraQ_C2T_pv = self.corrQ_LGA * cameraQ_C2T_pv

        # Apply roll sync adj (roll_adj)
        if self.roll_adj != 0:
            boresight_T = cameraQ_C2T_pv.rotate([0, 0, -1])
            corrQ_roll = Quaternion(axis=boresight_T, degrees=-self.roll_adj)
            cameraQ_C2T_pv = corrQ_roll * cameraQ_C2T_pv

        return cameraQ_C2T_pv, motorQ_C2B_pv



    def topoQ_to_baseQ(self, cameraQ_C2T):
        """
        Inverse kinematics: Topocentric frame → Base frame.
        cameraQ → undo[roll_adj] → undo[LGA] → undo[QUEST] → motorQ (in corrected theta space)
        """
        # Undo roll sync adj (roll_adj)
        if self.roll_adj != 0:
            boresight_T = cameraQ_C2T.rotate([0, 0, -1])
            corrQ_roll_undo = Quaternion(axis=boresight_T, degrees=self.roll_adj)
            cameraQ_C2T = corrQ_roll_undo * cameraQ_C2T

        # Undo Local Guassian Adjustment (LGA) 
        if Config.advanced_scc_enabled and Config.advanced_scc_choice==1:
            if self.corrQ_LGA is not None:
                cameraQ_C2T = self.corrQ_LGA.inverse * cameraQ_C2T

        # Undo alignQ_B2T model (QUEST)
        motorQ_C2B = self.alignQ_B2T_inv * cameraQ_C2T

        # Do not undo the following as PID theta works in corrected theta space
        # no undo Mechanical Corrections (MAC)
        # no undo Pulse Guiding Corrections (PGC)
        # no undo Sync Guiding Corrections (SGC)

        return motorQ_C2B

    def refresh_pid_setpoints_from_q1(self):
        """
        Called after any sync reset, delete, or alignment model update.
        Re-derives all PID setpoints from current motor quaternion + new alignment model,
        """   
        if self.polaris._q1 is None:
            return
        if not hasattr(self.polaris, '_pid') or self.polaris._pid is None:
            return
        cameraQ, _ = self.baseQ_to_topoQ(self.polaris._q1)     
        az, alt, roll = q_to_azaltroll(cameraQ)
        self.polaris._pid.reset_sp(np.array([az,alt,roll], dtype=float))
                                   
    def sync_az_alt(self, a_ra, a_dec, a_az, a_alt):
        if not Config.advanced_alignment:
            return
    
        if Config.advanced_sync_guiding:
            # return if a valid sync guide update occurs
            if self.process_guide_sync(a_ra, a_dec, a_az, a_alt):
                return   

        # otherwise process it as a quest update
        self.process_quest_sync(a_ra, a_dec, a_az, a_alt)


    def process_quest_sync(self, a_ra, a_dec, a_az, a_alt):
        # Remove old nearby sync points
        new_pred_vec = azalt_to_vector(self.polaris._p_azimuth, self.polaris._p_altitude)
        new_obs_vec  = azalt_to_vector(a_az, a_alt)
        threshold_rad = math.radians(1.5)   # 1.5 degrees
        for entry in self.sync_history:
            if entry.get("deleted", False):
                continue
            if entry["a_az"] is None or entry["a_alt"] is None:
                continue
            existing_pred_vec = azalt_to_vector(entry["p_az"], entry["p_alt"])
            existing_obs_vec  = azalt_to_vector(entry["a_az"], entry["a_alt"])
            if (v_angular_distance(new_pred_vec, existing_pred_vec) < threshold_rad or
                v_angular_distance(new_obs_vec,  existing_obs_vec)  < threshold_rad):
                self.sync_remove(entry["timestamp"], optimise=False)

        # If limit reached, remove the lowest-weighted entry
        active_entries = [e for e in self.sync_history if not e.get("deleted", False)]
        if len(active_entries) >= 10:
            # Find entry with lowest weight
            lowest_entry = min(active_entries, key=lambda e: e.get("w_total", 0.0))
            timestamp_to_remove = lowest_entry.get("timestamp")
            self.sync_remove(timestamp_to_remove, optimise=False)

        # Create and add the new entry
        entry = self.standard_entry()
        entry["a_ra"] = a_ra
        entry["a_dec"] = a_dec
        entry["a_az"] = a_az
        entry["a_alt"] = a_alt
        self.sync_history.append(entry)
        self.last_sync_time = time.monotonic()

        # Recalculate QUEST based on the new data
        self.optimize_alignQ_B2T()
        self.refresh_pid_setpoints_from_q1()
        self.streamSyncData()
        self.enable_sync_guiding()

    def sync_roll(self, a_roll):
        if not Config.advanced_alignment:
            return
        entry = self.standard_entry()
        entry["a_roll"] = a_roll
        if Config.advanced_alignment and Config.advanced_control:
            _, _, p_roll_pv = q_to_azaltroll(self.alignQ_B2T * self.corrQ_RBC * self.polaris._motorQ_state)
            entry["p_roll_pv"] = p_roll_pv   # MAC+QUEST corrected roll in T Frame for roll_adj computation
        self.sync_history.append(entry)
        self.optimize_roll_adj()
        self.refresh_pid_setpoints_from_q1()
        self.streamSyncData()

    def sync_remove(self, timestamp, optimise=True):
        found = False
        for entry in self.sync_history:
            if entry.get("timestamp") == timestamp:
                entry["deleted"] = True
                found = True
                break
        if found:
            if Config.log_quest_model:
                self.logger.info(f"Cleared sync data for timestamp: {timestamp}")
            if optimise:
                self.optimize_alignQ_B2T()
                self.optimize_roll_adj()
                self.refresh_pid_setpoints_from_q1()
            self.streamSyncData()
        else:
            self.logger.warning(f"No sync entry found with timestamp: {timestamp}")


    def azalt_polaris2ascom(self, p_az, p_alt):
        if self.alignQ_B2T is None:
            return p_az, p_alt
        v_pred = azalt_to_vector(p_az, p_alt)
        v_obs = self.alignQ_B2T.rotate(v_pred)
        c_az, c_alt = vector_to_az_alt(v_obs) 
        return c_az, c_alt

    def azalt_ascom2polaris(self, a_az, a_alt):
        if self.alignQ_B2T is None:
            return a_az, a_alt
        v_obs = azalt_to_vector(a_az, a_alt)
        v_pred = self.alignQ_B2T.inverse.rotate(v_obs)
        p_az, p_alt = vector_to_az_alt(v_pred)
        return p_az, p_alt

    def optimize_alignQ_B2T(self, persist=True):
        """
        Implement the QUEST algorithm to find the optimal rotation quaternion
        that minimizes the misalignment between predicted (Polaris) and observed (Plate Solved/ASCOM) vectors.
        Based on: 
        Markley, F. L. (2000). "Quaternion Attitude Estimation Using Vector Observations." https://tinyurl.com/ymk5xd7z
        Markley, F. L. (2003). "Attitude Estimation or Quaternion Estimation?" https://ntrs.nasa.gov/citations/20030093641
        """
        if Config.advanced_alignment == False:
            self.set_alignQ_to_identity()
            return

        pairs = []
        weights = []
        self.params_RBC = MountModelParams.from_config(Config)
        self.clear_guide_pulses(persist=persist)

        v_current = azalt_to_vector(self.polaris._p_azimuth, self.polaris._p_altitude)

        for i, entry in enumerate(self.sync_history):
            if entry["deleted"] or entry["a_az"] is None or entry["a_alt"] is None:
                continue

            v_obs = azalt_to_vector(entry["a_az"], entry["a_alt"])            # Observed vector from sync
            v_pred, _, _ = self.entry_to_pred_vector(entry)                   # Predicted vector from q1/alpha_state
            proximity_angle = v_angular_distance(v_pred, v_current)           # in Polaris space

            w_recency = 0.5 * np.exp(-0.1 * (len(self.sync_history) - i))                 # Recent syncs weighted more heavily: ~0.6–1.0
            w_proximity = 1.0 * np.exp(-(proximity_angle**2) / (2 * np.radians(10)**2))   # Higher weight for syncs near current pointing orientation: #  guassian σ=10°
            w_polar = 1.0 * np.exp(-((abs(entry['a_dec']) - 90)**2) / (2 * 10**2))        # Gaussian peak at ±90°, σ=10°
            
            # Combine weights additively to ensure no single factor can zero out the weight
            w_total = w_proximity + w_polar + w_recency + 0.01  
            entry["w_recency"] = w_recency
            entry["w_proximity"] = w_proximity
            entry["w_polar"] = w_polar
            entry["w_total"] = w_total

            pairs.append((v_pred, v_obs))
            weights.append(w_total)


        self.aligned_count = len(pairs)
        if len(pairs) < 2:
            self.alignQ_B2T = self.optimise_alignQ_B2T_fallback_single_sync(pairs)
            self.alignQ_B2T_inv = self.alignQ_B2T.inverse
            self.alignQ_B2T_message = "Fallback rotation from single sync"
        else:
            # Normalize weights
            weights = np.array(weights)
            weights /= np.sum(weights)

            # Build the B matrix: sum of weighted outer products between predicted and observed vectors
            # Each term aligns a predicted direction (from Polaris) to an observed direction (from sync)
            # This builds the core rotation alignment matrix
            B = sum(w * np.outer(v_pred, v_obs) for (v_pred, v_obs), w in zip(pairs, weights))

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

            self.alignQ_B2T = Quaternion(q_opt[0], q_opt[1], q_opt[2], q_opt[3])
            self.alignQ_B2T_inv = self.alignQ_B2T.inverse

            # If not optimal sidereal tracking then tweak QUEST model to zero our residual on final syncpoint
            if Config.advanced_scc_enabled and Config.advanced_scc_choice==0:
                self.clear_sync_guiding()
                self.apply_zero_last_residual_to_model()
                
            self.alignQ_B2T_message = "QUEST solution applied"


        # Now compute the residuals and tilt correction
        self.compute_azalt_residuals()   # Compute and store residuals
        self.compute_tilt()              # Compute tilt correction
        self.logSyncDataToConsole()
        if Config.advanced_scc_enabled and Config.advanced_scc_choice==2:
            self.seed_sync_guide_from_quest_residual()

        return


    def get_last_syncpoint_residual(self):
        """
        Returns the residual of the most recent valid AzAlt sync point as
        (az_err_deg, alt_err_deg, v_pred_rot, v_obs), or (0, 0, None, None)
        if no valid sync exists.

        Residual is defined as: observed - model_predicted.
        v_pred_rot is the model-rotated predicted vector (used for quaternion correction).
        v_obs is the observed vector (used for quaternion correction).
        """
        last_valid = next(
            (e for e in reversed(self.sync_history)
            if not e.get('deleted', False)
            and e.get('a_az') is not None
            and e.get('a_alt') is not None),
            None
        )
        if last_valid is None:
            return 0.0, 0.0, None, None

        v_pred, _, _ = self.entry_to_pred_vector(last_valid)
        v_obs  = azalt_to_vector(last_valid['a_az'], last_valid['a_alt'])
        v_pred_rot = self.alignQ_B2T.rotate(v_pred)

        az_corr, alt_corr = vector_to_az_alt(v_pred_rot)
        az_err  = angular_difference(az_corr, last_valid['a_az'])
        alt_err = angular_difference(alt_corr, last_valid['a_alt'])

        return az_err, alt_err, v_pred_rot, v_obs
    

    def get_local_guassian_adjustment_q(self, cameraQ_C2T, sigma_deg=10.0, sigma_sec=60*60):
        """
        Returns a spatially and temporally weighted correction quaternion based on the
        last sync point residual.
        Spatial:  Gaussian over angular distance from last sync point (sigma_deg).
        Temporal: Gaussian over time since last sync (sigma_sec).
                LGA fades to identity after a slew-and-centre completes so that
                sidereal tracking is not continuously nudged by a stale correction.

        Returns (QIdentity, 0) if no valid sync, weight too small, or correction negligible.
        """
        identity = (Quaternion(1,0,0,0), 0)

        # ---- Temporal fade --------------------------------------------------
        if self.last_sync_time is None:
            return identity
        
        # Disable Temporal weight
        temporal_weight = 1
        # dt = time.monotonic() - self.last_sync_time
        # temporal_weight = math.exp(-(dt ** 2) / (2 * sigma_sec ** 2))
        # if temporal_weight < 1e-3:                   # effectively zero after ~3 sigma
        #     return identity
        
        # ---- Spatial Gaussian -----------------------------------------------
        az_err, alt_err, v_pred_rot, v_obs = self.get_last_syncpoint_residual()
        if v_pred_rot is None:
            return identity

        # Angular distance from current boresight to last sync point (in observed space)
        boresight_T = cameraQ_C2T.rotate([0, 0, -1])
        angular_dist_rad = v_angular_distance(boresight_T, v_obs)

        # Gaussian weight: 1.0 at sync point, fades toward 0 beyond sigma_deg
        sigma_rad = math.radians(sigma_deg)
        spatial_weight = math.exp(-(angular_dist_rad ** 2) / (2 * sigma_rad ** 2))
        if spatial_weight < 1e-4:
            return identity

        # Build the full residual correction quaternion (v_pred_rot → v_obs)
        axis = np.cross(v_pred_rot, v_obs)
        norm_axis = np.linalg.norm(axis)
        if norm_axis < 1e-8:
            return identity
        axis /= norm_axis
        angle = np.arccos(np.clip(np.dot(v_pred_rot, v_obs), -1.0, 1.0))
        q_full = Quaternion(axis=axis, radians=angle)

        # Slerp between identity and full correction by weight
        weight = spatial_weight * temporal_weight
        q_weighted = Quaternion.slerp(Quaternion(1, 0, 0, 0), q_full, amount=weight)
        scc_error = np.degrees(-angle*weight)
        return (q_weighted, scc_error)

    def apply_zero_last_residual_to_model(self):
        self.scc_error = 0
        az_err, alt_err, v_pred_rot, v_obs = self.get_last_syncpoint_residual()
        if v_pred_rot is None:
            self.alignQ_B2T_message += " | No valid sync for final alignment"
            return

        axis = np.cross(v_pred_rot, v_obs)
        norm_axis = np.linalg.norm(axis)
        if norm_axis < 1e-8:
            self.alignQ_B2T_message += " | Final sync already aligned"
            return

        axis /= norm_axis
        angle = np.arccos(np.clip(np.dot(v_pred_rot, v_obs), -1.0, 1.0))
        q_correction = Quaternion(axis=axis, radians=angle)
        self.alignQ_B2T = q_correction * self.alignQ_B2T
        self.alignQ_B2T_inv = self.alignQ_B2T.inverse
        self.scc_error = np.degrees(-angle)


    def optimise_alignQ_B2T_fallback_single_sync(self, pairs):
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
            _, eff_az, eff_alt = self.entry_to_pred_vector(entry)
            az_corr, alt_corr  = self.azalt_polaris2ascom(eff_az, eff_alt)            
            az_err = angular_difference(az_corr, entry["a_az"])
            alt_err = angular_difference(alt_corr, entry["a_alt"])
            # Project az error onto the sky before combining with alt error.
            # Raw az degrees overstate separation at high altitudes.
            ref_alt = math.radians((alt_corr + entry["a_alt"]) / 2.0)
            az_err_projected = az_err * math.cos(ref_alt)
            magnitude = math.sqrt(az_err_projected**2 + alt_err**2)
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
        self.az_adj = wrap180(north_az)


    def roll2pa(self, az_deg, alt_deg, roll_deg):
        """Convert camera-frame roll to sky-frame position angle and parallactic angle at ascom azalt."""
        parallactic_angle = calc_parallactic_angle(az_deg, alt_deg, self.polaris._sitelatitude)
        position_angle = wrap360(roll_deg + parallactic_angle)
        return position_angle, parallactic_angle

    def pa2roll(self, az_deg, alt_deg, position_angle_deg):
        """Convert sky-frame position angle to camera-fram roll using parallactic angle at ascom azalt."""
        parallactic_angle = calc_parallactic_angle(az_deg, alt_deg, self.polaris._sitelatitude)
        return wrap360(position_angle_deg - parallactic_angle)

    def roll_polaris2ascom(self, polaris_roll_deg):
        """Convert Polaris roll angle to ASCOM roll angle (mechanical angle), applying roll sync adjustment correction."""
        return wrap360(polaris_roll_deg + self.roll_adj)

    def roll_ascom2polaris(self, ascom_roll_deg):
        """Convert ASCOM roll angle (mechanical angle) to Polaris roll angle, applying roll sync adjustment."""
        return wrap360(ascom_roll_deg - self.roll_adj)

    def optimize_roll_adj(self):
        deltas = []

        for entry in self.sync_history:
            if entry["deleted"] or entry["a_roll"] is None:
                continue
            # Use MAC+QUEST corrected p_roll_pv if available, else raw
            p_roll = entry.get("p_roll_pv", entry["p_roll"])
            # Compute delta: how much Polaris roll differs from expected PA
            delta = angular_difference(p_roll, entry["a_roll"])
            deltas.append(delta)

        if deltas:
            # circular mean to handle wrap-around near ±180°
            sin_sum = sum(math.sin(math.radians(d)) for d in deltas)
            cos_sum = sum(math.cos(math.radians(d)) for d in deltas)
            self.roll_adj = math.degrees(math.atan2(sin_sum, cos_sum))
        else:
            self.roll_adj = 0
        self.compute_roll_residuals()


    def logSyncDataToConsole(self):
        if Config.log_quest_model:
            # --- Model summary line ---
            active = [e for e in self.sync_history if not e.get("deleted") and e.get("a_az") is not None]
            residuals = [e["residual_magnitude"] for e in active if "residual_magnitude" in e]
            rms = math.sqrt(sum(r**2 for r in residuals) / len(residuals)) if residuals else 0
            max_res = max(residuals) if residuals else 0
            max_entry = active[residuals.index(max_res)] if residuals else None
            self.mpa_error = rms

            self.logger.info(
                f"QUEST Model  | Points: {len(active)} | "
                f"w: {self.alignQ_B2T[0]:+9.7f} | " 
                f"x: {self.alignQ_B2T[1]:+9.7f} | " 
                f"y: {self.alignQ_B2T[2]:+9.7f} | " 
                f"z: {self.alignQ_B2T[3]:+9.7f} " 
            )
            en = Config.advanced_scc_enabled
            ch = Config.advanced_scc_choice
            self.logger.info(
                f"  MAC: {'ON ' if Config.advanced_align_mac else 'OFF'}   | " 
                f"{'SCC: OFF  | ' if not en else 'ZLR: ON   | ' if ch==0 else 'LGA: ON   | ' if ch==1 else 'SGA: ON   | ' }"
                f"RMS Residual: {deg2dms(rms)}  | "
                f"Az Correction: {deg2dms(self.az_adj)} | "
                f"Tilt: {deg2dms(self.tilt_adj_mag)} @ {deg2dms(self.tilt_adj_az)} | "
                f"Roll Adj: {deg2dms(self.roll_adj)}"
            )

            # --- Per-point table, compact format ---
            # Header
            self.logger.info(
                f"  {'No':>2} {'Timestamp':>10} {'Age h':>5} "
                f"{'Obs RA':>8} {'Obs Dec':>8} {'Obs Az':>8} {'Obs Alt':>8} "
                f"{'p_az':>8} {'p_alt':>8} {'p_roll':>8} "
                f"{'Weight':>7} {'ResAz':>8} {'ResAlt':>8} {'ResMag':>8} "
            )
            for i, entry in enumerate(self.sync_history):
                if entry.get("deleted") or entry.get("a_az") is None:
                    continue
                az_err, alt_err = entry.get("residual_vector", (0, 0))
                mag = entry.get("residual_magnitude", 0)
                w = entry.get("w_total", 0)
                # Timestamp short form eg 12:24:04
                ts_utc = datetime.datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                ts_local = ts_utc.astimezone()
                ts = ts_local.strftime('%H:%M:%S')
                age_h = (datetime.datetime.now(datetime.timezone.utc) - ts_utc).total_seconds() / 3600
                self.logger.info(
                    f" #{i:02d} {ts:>10} {age_h:>5.1f} "
                    f"{entry['a_ra']:>8.2f} {entry['a_dec']:>8.2f} {entry['a_az']:>8.2f} {entry['a_alt']:>8.2f} "
                    f"{entry['p_az']:>8.2f} {entry['p_alt']:>8.2f} {entry['p_roll']:>8.2f} "
                    f"{w:>7.4f} {az_err*60:>+8.2f}' {alt_err*60:>+8.2f}' {deg2dms(mag):>8}"
                )
            # --- Point pair separation ---
            if len(active) >= 2:
                self.logger.info("Point separations (degrees):")
                for i in range(len(active)):
                    parts = []
                    for j in range(i+1, len(active)):
                        v1 = azalt_to_vector(active[i]['a_az'], active[i]['a_alt'])
                        v2 = azalt_to_vector(active[j]['a_az'], active[j]['a_alt'])
                        sep = math.degrees(v_angular_distance(v1, v2))
                        parts.append(f"#{j:02d}: {sep:5.2f}")
                    if parts:
                        self.logger.info(f" #{i:02d}   <->  {';  '.join(parts)}")

    def streamSyncData(self, persist=True):
        self.streamSyncDataReset()
        sm_logger = logging.getLogger('sm')
        for entry in self.sync_history:
            sm_logger.info(entry)
        if persist:
            self.saveSyncDataToFile()

    def streamSyncDataReset(self):
        sm_logger = logging.getLogger('sm')
        first_entry = self.standard_entry()
        first_entry["timestamp"] = 'reset'    # flag clients to clear alignment history
        first_entry["a_alt"] = 0
        first_entry["a_az"] = 0 
        first_entry["a_roll"] = 0 
        sm_logger.info(first_entry)

    def saveSyncDataToFile(self, path=SYNC_POINTS_PATH):
        ensure_data_dir_exists()
        entries_to_save = [
            {k: v for k, v in entry.items() if k not in ('w_recency', 'w_proximity', 'w_polar', 'w_total', 'residual_vector', 'residual_magnitude')}
            for entry in self.sync_history
            if not entry.get('deleted', False)
        ]
        guide_state = {
            "q_guide_B":          list(self.q_guide_B.q),
            "q_syncguide_B":      list(self.q_syncguide_B.q),
            "valid_sync_guide":   bool(self.valid_sync_guide),
        }
        data = {"sync_points": entries_to_save, "guide_state": guide_state}
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def loadSyncDataFromFile(self, path=SYNC_POINTS_PATH):
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r') as f:
                loaded = json.load(f)

            # Backward compatibility: old files are a bare list (sync points only, no guide state). New files are a dict with both.
            if isinstance(loaded, list):
                entries, guide_state = loaded, None
            elif isinstance(loaded, dict):
                entries = loaded.get('sync_points', [])
                guide_state = loaded.get('guide_state')
            else:
                self.logger.warning("sync_points.json: unexpected format, ignoring.")
                return False

            if not isinstance(entries, list):
                self.logger.warning("sync_points.json: expected a list of sync points, ignoring.")
                return False

            self.sync_history = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                if entry.get('timestamp') == 'reset':
                    continue
                clean = {
                    'timestamp':  entry.get('timestamp', format_timestamp()),
                    'deleted':    False,
                    'p_az':       float(entry['p_az']),
                    'p_alt':      float(entry['p_alt']),
                    'p_roll':     float(entry['p_roll']),
                    'p_roll_pv':  float(entry['p_roll_pv']) if entry.get('p_roll_pv') is not None else None,
                    'a_ra':       float(entry['a_ra'])   if entry.get('a_ra')   is not None else None,
                    'a_dec':      float(entry['a_dec'])  if entry.get('a_dec')  is not None else None,
                    'a_az':       float(entry['a_az'])   if entry.get('a_az')   is not None else None,
                    'a_alt':      float(entry['a_alt'])  if entry.get('a_alt')  is not None else None,
                    'a_roll':     float(entry['a_roll']) if entry.get('a_roll') is not None else None,
                }
                self.sync_history.append(clean)

            payload = {'advanced_alignment': True if len(self.sync_history) > 0 else False}
            Config.apply_changes(payload)
            self.logger.info(f"==STARTUP== Loading Alignment Model ({len(self.sync_history)} sync points{', and guide state' if guide_state else ''}).")
            self.optimize_alignQ_B2T(persist=False)
            self.optimize_roll_adj()
            self.refresh_pid_setpoints_from_q1()
            self.last_sync_time = time.monotonic()

            # Restore guide correction state, if present (older files won't have it —
            # q_guide_B/q_syncguide_B simply stay at identity, same as before this change).
            if guide_state:
                try:
                    self.q_guide_B     = Quaternion(*guide_state['q_guide_B']).normalised
                    self.q_syncguide_B = Quaternion(*guide_state['q_syncguide_B']).normalised
                    self.valid_sync_guide  = guide_state.get('valid_sync_guide', False)
                except Exception as e:
                    self.logger.warning(f"Failed to restore guide state, continuing at identity: {e}")

            self.streamSyncData(persist=False)
            return True
        except Exception as e:
            self.logger.warning(f"Failed to load sync_points.json: {e}")
            return False

    def _request_persist_guide_state(self, throttle_sec=60):
        """
        Throttled save of guide correction state (q_guide_B, q_syncguide_B).
        Called from every guide/PEC accumulation point, which can fire many times
        per second (PEC ticks every ~200ms) — so this must not write to disk on
        every call. Saves immediately if throttle_sec has elapsed since the last
        save; otherwise defers a single trailing save so the final state is never
        more than throttle_sec stale, without hammering the filesystem.
        """
        now = time.monotonic()
        last = getattr(self, '_last_persist_time', None)
        if last is None or (now - last) >= throttle_sec:
            self._last_persist_time = now
            self._persist_pending = False
            self.saveSyncDataToFile()
        elif not getattr(self, '_persist_pending', False):
            self._persist_pending = True
            remaining = throttle_sec - (now - last)
            asyncio.create_task(self._deferred_persist_guide_state(remaining))

    async def _deferred_persist_guide_state(self, delay):
        await asyncio.sleep(delay)
        if getattr(self, '_persist_pending', False):
            self._last_persist_time = time.monotonic()
            self._persist_pending = False
            self.saveSyncDataToFile()

# ── Pulse Guiding ──────────────────────────────────────────────────────────

    def process_pulse_guide_axis(self, direction, duration):
        axis = None
        sign = 0
        if direction == 0: axis, sign = 1, +1    # North DEC +ve
        elif direction == 1: axis, sign = 1, -1  # South DEC -ve
        elif direction == 2: axis, sign = 0, +1  # East RA +ve
        elif direction == 3: axis, sign = 0, -1  # West RA -ve
        else:
            self.logger.warning(f"Invalid pulse guide direction: {direction}")
            return

        # accumulate the pulse guide durations into q_guide_B for baseQ_to_topoQ to apply as a correction
        step_sec = abs(duration)/1000
        velocity = sign * (self.polaris._guideraterightascension if axis == 0 else self.polaris._guideratedeclination)
        self.accumulate_guide_pulses(axis, step_sec, velocity)
        
        # update the drift and PEC model
        angle_deg = velocity*step_sec
        ra_resid = angle_deg if axis==0 else None
        dec_resid = angle_deg if axis==1 else None
        self.update_pec_model(ra_resid, dec_resid)

        # make immediate update to ra and dec for conformU tests
        cameraQ_pv, _ = self.polaris._sm.baseQ_to_topoQ(self.polaris._motorQ_state)
        az, alt, _ = q_to_azaltroll(cameraQ_pv)
        ra, dec = self.polaris.altaz2radec(alt, az)
        self.polaris._rightascension = float(ra)
        self.polaris._declination = float(dec)
        self.polaris._ispulseguiding = True

    def cache_equatorial_axes_B(self, cameraQ_pv, lat):
        """ cache equatorial axes in B Frame, when ever PV changes, ie called from 518 handler """
        alignQ_B2T_inv = self.alignQ_B2T_inv
        self.equatorial_axes_B = calc_equatorial_axes_B(cameraQ_pv, alignQ_B2T_inv, lat)

    def accumulate_guide_pulses(self, axis, step_sec, velocity):
        axis_base = self.equatorial_axes_B[axis]
        if axis_base is None:
            return Quaternion()
        angle_deg = velocity * step_sec
        if abs(angle_deg) < 1e-9:
            return Quaternion()
        q_pulse = Quaternion(axis=axis_base, degrees=angle_deg)
        self.q_guide_B = (q_pulse * self.q_guide_B).normalised
        self.delta_guide_accum[axis] += angle_deg
        self.delta_guide_pulse[axis] = angle_deg
        self._request_persist_guide_state()
    
    def clear_guide_pulses(self, persist=True):
        self.delta_guide_accum = np.zeros(3, dtype=float)
        self.q_guide_B = Quaternion(1,0,0,0)
        self.delta_guide_pulse = np.zeros(3, dtype=float)
        if persist:
            self._request_persist_guide_state()


# ── Sync Guiding ──────────────────────────────────────────────────────────

    def process_guide_sync(self, a_ra, a_dec, a_az, a_alt):
        if not self.valid_sync_guide:
            return False
        
        MAX_SYNC_GUIDE_DEG = 3.0
        ra_resid = clamp_error(a_ra*15, self.polaris.rightascension*15)
        dec_resid = clamp_error(a_dec, self.polaris.declination)
        if (abs(ra_resid) > MAX_SYNC_GUIDE_DEG or abs(dec_resid) > MAX_SYNC_GUIDE_DEG):
            return False

        self.logger.info(f"->> Polaris: SYNC GUIDING    Ra {deg2dms(ra_resid)}, Dec {deg2dms(dec_resid)} Residuals")
        self.accumulate_sync_guiding_residuals(ra_resid, dec_resid)

        # update the drift and PEC model
        self.update_pec_model(ra_resid,dec_resid)

        return True

    def invalidate_sync_guiding(self):
        """ Next sync is not to be used for sync guiding, but keep q_syncguide_B """
        self.reset_pec_model()
        self.valid_sync_guide = False

    def clear_sync_guiding(self):
        """ Cleared whenever Tracking disabled, Panning, Rolling 
            Although Gotos only invalidate, as the q_syncguide_B is used for scc """
        self.reset_pec_model()
        self.valid_sync_guide = False
        self.q_syncguide_B = Quaternion(1,0,0,0)
        self.delta_guide_accum = np.zeros(3, dtype=float) 
        if Config.advanced_scc_enabled and Config.advanced_scc_choice==2:
            self.scc_error = 0
        self._request_persist_guide_state()

    def enable_sync_guiding(self):
        """ Enabled from a valid QUEST sync and sidereal tracking enabled """
        self.valid_sync_guide = True

    def accumulate_sync_guiding_residuals(self, ra_resid, dec_resid):
        """ Accumulate residuals in decimal degrees, as well as a corresponding corection quaternion """
        ra_axis_B, dec_axis_B, _ = self.equatorial_axes_B
        q_ra_corr  = Quaternion(axis=ra_axis_B,  degrees= ra_resid)
        q_dec_corr = Quaternion(axis=dec_axis_B, degrees= dec_resid)
        q_adj = (q_ra_corr * q_dec_corr).normalised
        self.q_syncguide_B = (q_adj * self.q_syncguide_B).normalised

        self.delta_guide_accum[0] += ra_resid
        self.delta_guide_accum[1] += dec_resid
        self.delta_guide_pulse[0] = ra_resid
        self.delta_guide_pulse[1] = dec_resid
        self._request_persist_guide_state()
        
    def get_sync_guiding_correction_q(self):
        return self.q_syncguide_B
        
    def seed_sync_guide_from_quest_residual(self):
        if self.last_sync_time is None:
            return
        if self.polaris._motorQ_state is None:
            return
        
        # Update cameraQ_pv based on recalculated QUEST model
        cameraQ_pv, _ = self.baseQ_to_topoQ(self.polaris._motorQ_state)
        self.cache_equatorial_axes_B(cameraQ_pv, self.polaris._sitelatitude)

        az_err, alt_err, v_pred_rot, v_obs = self.get_last_syncpoint_residual()
        if v_pred_rot is None:
            return

        axis = np.cross(v_pred_rot, v_obs)
        norm_axis = np.linalg.norm(axis)
        if norm_axis < 1e-8:
            return
        axis /= norm_axis
        angle = np.arccos(np.clip(np.dot(v_pred_rot, v_obs), -1.0, 1.0))
        self.scc_error = np.degrees(-angle)

        # Build exact residual correction in Topocentric frame, rotate to Base frame
        q_corr_topo = Quaternion(axis=axis, radians=angle)
        q_corr_B = self.alignQ_B2T_inv * q_corr_topo * self.alignQ_B2T

        self.logger.info(
            f"Sync Guide seeded from QUEST residual: "
            f"Az {deg2dms(az_err)}, Alt {deg2dms(alt_err)}, angle {deg2dms(np.degrees(angle))}"
        )

        self.q_syncguide_B = q_corr_B.normalised
        self.delta_guide_accum[0] = 0
        self.delta_guide_accum[1] = 0
        self._request_persist_guide_state()




# ── PEC and Drift Modelling ───────────────────────────────────────────────

    def init_pec_model(self):
        """Initialise (or reset) the recursive drift model. Safe to call after slew."""
        self._pec_n           = 0
        self._pec_t0          = None
        self._pec_last_apply  = None

        # Config-driven thresholds (read once so update/apply don't need getattr)
        self._pec_mode        = PecMode(getattr(Config, 'pec_mode', 'rls'))               # 'rls' or 'ema'
        self._pec_tau         = getattr(Config, 'pec_tau_sec',            21*60)         # single smoothing time constant (sec), both modes
        self._pec_min_dt      = getattr(Config, 'pec_min_dt_sec',         0.05)          # ignore an axis update if it arrives sooner than this since that axis's own last update
        self._pec_min_obs     = getattr(Config, 'pec_min_observations',   3)              # inhibit until n > min_obs
        self._pec_max_resid   = getattr(Config, 'pec_max_resid_arcmin',   10.0)  / 60.0   # ignore guide update if resid > max_resid degrees
        self._pec_max_step    = getattr(Config, 'pec_max_step_arcmin',    0.5)   / 60.0   # clamp +/-correction step to max_step degrees every 200ms
        self._pec_max_rmse    = getattr(Config, 'pec_max_rmse_arcmin',    6.0)   / 60.0   # inhibit if rmse > max_rmse degrees
        self._pec_min_r2      = getattr(Config, 'pec_min_r2',             0.5)            # inhibit if bad R2 < 0.5
        self._pec_T_sec       = getattr(Config, 'pec_T_sec',              34*60)          # T: worm period in seconds (default 34 min = 2040s)
        self._pec_n_harmonics = getattr(Config, 'pec_n_harmonics',        2)              # n_harmonics: 0, 1, or 2 (0 = pure linear, RLS mode only)

        self._pec_ra  = PecAxis(T=self._pec_T_sec, n_harmonics=self._pec_n_harmonics,
                                 mode=self._pec_mode, tau=self._pec_tau, min_dt=self._pec_min_dt)
        self._pec_dec = PecAxis(T=self._pec_T_sec, n_harmonics=self._pec_n_harmonics,
                                 mode=self._pec_mode, tau=self._pec_tau, min_dt=self._pec_min_dt)

        self._pec_var_alpha  = 0.05           # EMA factor for var estimate, more stable R2
        self._pec_sse_alpha  = 0.15           # EMA factor for sse estimate, faster tracking decay
        self._pec_active      = False

        if Config.log_pec and getattr(self, '_log_pec_config', True):
            self.logger.info(
                f"PECCONFIG mode,{self._pec_mode.value},n_harmonics,{self._pec_n_harmonics},"
                f"T,{self._pec_T_sec},tau_sec,{self._pec_tau},min_dt_sec,{self._pec_min_dt}"
            )
            self._log_pec_config = False


    def reset_pec_model(self):
        """Call after slew, rotate, or QUEST reset."""
        self.init_pec_model()

    def update_pec_model(self, ra_resid_deg, dec_resid_deg):
        """
        Ingest a guide correction into the PEC model.
        Either or both residuals may be None (pulse guiding sends one axis at a time).
        """
        if not Config.advanced_pec:
            return

        now = time.monotonic()
        ra_resid  = self._pec_validate_resid(ra_resid_deg)
        dec_resid = self._pec_validate_resid(dec_resid_deg)

        if ra_resid is None and dec_resid is None:
            return

        if not self._pec_initialised(now, ra_resid, dec_resid):
            return

        t = now - self._pec_t0
        self._pec_update_axes(ra_resid, dec_resid, t)
        self._pec_log(ra_resid, dec_resid)

    def _pec_validate_resid(self, resid):
        """Returns float residual if valid, None if missing or outlier."""
        if resid is None:
            return None
        resid = float(resid)
        if abs(resid) > self._pec_max_resid:
            return None
        return resid

    def _pec_initialised(self, now, ra_resid, dec_resid):
        """
        Ensures model is ready. Seeds axes on first valid observation.
        Returns False if this call should be consumed as the seed (no fit update yet).
        """
        if self._pec_t0 is None:
            self.init_pec_model()

        if self._pec_n == 0:
            self._pec_t0         = now
            self._pec_last_apply = now
            if ra_resid  is not None: self._pec_ra.reset_seed()
            if dec_resid is not None: self._pec_dec.reset_seed()
            self._pec_n = 1
            return False

        return True

    def _pec_update_axes(self, ra_resid, dec_resid, t):
        """Update each axis's fit and inhibit state. Each axis derives its own lambda/alpha from its own dt."""
        if ra_resid is not None:
            self._pec_ra.ingest(ra_resid,   t, self._pec_var_alpha, self._pec_sse_alpha)
        if dec_resid is not None:
            self._pec_dec.ingest(dec_resid, t, self._pec_var_alpha, self._pec_sse_alpha)

        self._pec_n += 1

        self._pec_ra.eval_inhibit( self._pec_n, self._pec_min_obs, self._pec_max_rmse, self._pec_min_r2)
        self._pec_dec.eval_inhibit(self._pec_n, self._pec_min_obs, self._pec_max_rmse, self._pec_min_r2)
        self._pec_active = self._pec_ra.converged() or self._pec_dec.converged()

    def _pec_log(self, ra_resid, dec_resid):
        if not Config.log_pec:
            return
        ra, dec = self._pec_ra, self._pec_dec
        pv_deg = self.polaris._pid.alpha_pv
        ra_accum_arcmin = ra._accum*60
        dec_accum_arcmin = dec._accum*60
        ra_guide_arcmin  = ra_resid*60 if ra_resid is not None else float('nan')
        dec_guide_arcmin = dec_resid*60 if dec_resid is not None else float('nan')
        ra_fit  = f"{ra.dc_rate()*3600:+.4f}"
        dec_fit = f"{dec.dc_rate()*3600:+.4f}"
        for h in range(1, ra.n_harmonics + 1):
            ra_fit  += f",{ra.harmonic_rate(h)*3600:.4f}"
            dec_fit += f",{dec.harmonic_rate(h)*3600:.4f}"
        self.logger.info(
            f"PECLOG  n,{self._pec_n},{ra.inhibit.name},{dec.inhibit.name}"
            f", | R2,{ra.r2:.3f},{dec.r2:.3f}"
            f", | rmse,{ra.rmse_arcmin():.4f},{dec.rmse_arcmin():.4f}"
            f", | Rate,{ra.theta*3600:+.4f},{dec.theta*3600:+.4f}"
            f", | Guide,{ra_guide_arcmin:+.5f},{dec_guide_arcmin:+.5f}"
            f", | Accum,{ra_accum_arcmin:+.5f},{dec_accum_arcmin:+.5f}"
            f", | Pos,{pv_deg[0]:.2f},{pv_deg[1]:.2f},{pv_deg[2]:+.2f}"
            f", | RA_model,{ra_fit}"
            f", | Dec_model,{dec_fit}"
            f", | lambda,{ra.lam:.5f},{dec.lam:.5f}"
        )


    def apply_pec_drift_correction(self):
        """
        Called every control tick. Computes the current PEC rate once, then:
        1. Publishes it as omega_pec_B for feed_forward() to solve through the
            Jacobian and add proactively to omega_tgt (minimizes transient/lag).
        2. Injects the same rate into the measurement chain via
            accumulate_sync_guiding_residuals (original design) so the loop's
            notion of "on target" advances in lockstep with the FF-induced
            motion — this is what stops Ki from seeing a sustained error and
            rejecting the correction over time.
        delta_sp/delta_ref are never touched — sidereal target identity is
        preserved exactly as before.
        """
        self.omega_pec_B = np.zeros(3, dtype=float)   # deg/sec, Base frame — read by feed_forward()

        if not getattr(self, '_pec_active', False):
            return
        if self.equatorial_axes_B[0] is None:
            return

        now = time.monotonic()
        if self._pec_last_apply is None:
            self._pec_last_apply = now
            return
        t  = now - self._pec_t0
        dt = now - self._pec_last_apply
        self._pec_last_apply = now
        if dt <= 0 or dt > 5.0:
            return

        cap = self._pec_max_step
        d_ra,  ra_applied  = self._pec_ra.eval_correction(t, dt, cap)
        d_dec, dec_applied = self._pec_dec.eval_correction(t, dt, cap)

        if ra_applied or dec_applied:
            # apply as correction to PV
            self.accumulate_sync_guiding_residuals(d_ra, d_dec)
            # apply as correction to omega_pec feed forward
            ra_axis_B, dec_axis_B, _ = self.equatorial_axes_B
            self.omega_pec_B = (d_ra/dt) * ra_axis_B + (d_dec/dt) * dec_axis_B


from enum import IntEnum, Enum
class PecInhibit(IntEnum):
    IDLE         = 0
    VALID        = 1
    TOO_FEW_OBS  = 2
    NOT_CONVERGED = 3
    HIGH_RMSE    = 4
    LOW_R2       = 5

class PecMode(str, Enum):
    RLS = "rls"
    EMA = "ema"


class PecAxis:
    """
    Two interchangeable drift estimators behind one interface:
      RLS mode: multi-harmonic recursive least squares (n_harmonics=0 -> pure linear)
                Fits: y(t)  = a*t + b1*sin(wt)   + c1*cos(wt)   + b2*sin(2wt)    + c2*cos(2wt) + ...
                      dy/dt = a   + b1*w*cos(wt) - c1*w*sin(wt) + b2*2w*cos(2wt) - c2*2w*sin(2wt) ...
                T: worm period in seconds (default 34 min = 2040s)
      EMA mode: exponential moving average of the observed instantaneous rate, no phase/harmonics

    Both modes share a single smoothing time constant `tau` (seconds):
      lam   = exp(-dt/tau)   — RLS forgetting factor
      alpha = 1 - lam        — EMA smoothing weight
    computed fresh at each ingest from that axis's own dt, so RA and Dec (which may
    update on different schedules under pulse guiding) each track correctly.

    theta            : rate as of the most recent ingest — for logging/reporting.
    predicted_rate(t): rate evaluated at an arbitrary/current time — used by
                        eval_correction() so harmonic phase advances continuously
                        between sparse ingests rather than freezing.
    """

    def __init__(self, T=34*60, n_harmonics=2, mode=PecMode.RLS, tau=21*60, min_dt=0.05):
        self.T           = T
        self.mode        = mode
        self.n_harmonics = n_harmonics if mode == PecMode.RLS else 0   # EMA never uses harmonics
        self.n_params    = 1 + 2 * self.n_harmonics                    # only meaningful in RLS mode

        self.tau    = tau        # single smoothing time constant, seconds — used by both modes
        self.min_dt = min_dt     # ignore updates arriving sooner than this since this axis's own last update

        # RLS state (unused but harmless in EMA mode)
        self._theta = np.zeros(self.n_params)
        self.P      = np.eye(self.n_params)

        # EMA state
        self.rate    = 0.0       # deg/sec — the EMA-tracked rate
        self._y_last = None

        self.lam = 1.0           # last-used lambda; alpha = 1 - lam when needed

        # shared fit-quality state
        self.sse = 0.0
        self.var = 0.0
        self.r2  = 0.0
        self.inhibit = PecInhibit.IDLE

        self._t_last = 0.0
        self._ref    = 0.0
        self._accum  = 0.0
        self._applied_accum = 0.0
        self._applied_rate  = 0.0   # last applied instantaneous rate, deg/s — for status reporting

    def reset(self):
        """Full reset — preserves configuration (mode/tau/min_dt), clears fit/EMA state."""
        self.__init__(T=self.T, n_harmonics=self.n_harmonics, mode=self.mode,
                      tau=self.tau, min_dt=self.min_dt)

    def reset_fit(self):
        """Reset fit statistics but preserve parameter estimates as warm start."""
        self.P   = np.eye(self.n_params)
        self.sse = 0.0
        self.var = 0.0
        self.r2  = 0.0

    def reset_seed(self, accum_deg=0.0):
        """Set the reference point at t=0."""
        self._accum  = accum_deg
        self._ref    = accum_deg
        self._applied_accum = 0.0
        self._y_last = None
        self._t_last = 0.0

    # ── primary methods ─────────────────────────────────────────────────────────
    def ingest(self, resid_deg, t, var_alpha, sse_alpha):
        """
        Ingest a new guide residual and update the model.
        resid_deg: guide residual for this axis in degrees.
        t: seconds since session start.
        """
        self._accum += resid_deg + self._applied_accum
        self._applied_accum = 0.0
        y  = self._accum - self._ref
        dt = t - self._t_last
        if dt < self.min_dt:
            return    # too soon since this axis's own last update — skip rather than corrupt the fit

        self.lam = math.exp(-dt / self.tau)
        if self.mode == PecMode.RLS:
            self._update_rls(var_alpha, sse_alpha, t, y)
        else:
            self._update_ema(var_alpha, sse_alpha, dt, y)
        self._t_last = t

    def ingest_accum(self, accum_deg, t, var_alpha, sse_alpha):
        """Direct accum ingestion for notebook replay — bypasses delta accounting."""
        self._accum = accum_deg
        y  = self._accum - self._ref
        dt = t - self._t_last
        if dt < self.min_dt:
            return

        self.lam = math.exp(-dt / self.tau)
        if self.mode == PecMode.RLS:
            self._update_rls(var_alpha, sse_alpha, t, y)
        else:
            self._update_ema(var_alpha, sse_alpha, dt, y)
        self._t_last = t

    # ── EMA internals ────────────────────────────────────────────────────────
    def _update_ema(self, var_alpha, sse_alpha, dt, y):
        y_pred = (self._y_last + self.rate * dt) if self._y_last is not None else y
        err    = y - y_pred

        self.var = var_alpha * y * y     + (1 - var_alpha) * self.var
        self.sse = sse_alpha * err * err + (1 - sse_alpha) * self.sse
        self.r2  = 1.0 - self.sse / self.var if self.var > 1e-10 else 0.0

        if self._y_last is not None:
            alpha    = 1.0 - self.lam
            rate_obs = (y - self._y_last) / dt
            self.rate = alpha * rate_obs + (1 - alpha) * self.rate

        self._y_last = y

    # ── RLS internals ────────────────────────────────────────────────────────
    def _update_rls(self, var_alpha, sse_alpha, t, y):
        phi = self._phi(t)
        err = y - float(phi @ self._theta)

        self.var = var_alpha * y * y     + (1 - var_alpha) * self.var
        self.sse = sse_alpha * err * err + (1 - sse_alpha) * self.sse

        Pp = self.P @ phi
        S  = self.lam + float(phi @ Pp)
        K  = Pp / S

        self._theta += K * err
        self.P       = (self.P - np.outer(K, phi @ self.P)) / self.lam
        self.r2      = 1.0 - self.sse / self.var if self.var > 1e-10 else 0.0

    def _phi(self, t):
        w   = 2 * math.pi / self.T
        phi = np.zeros(self.n_params)
        phi[0] = t
        for h in range(1, self.n_harmonics + 1):
            phi[1 + 2*(h-1)] = math.sin(h * w * t)
            phi[2 + 2*(h-1)] = math.cos(h * w * t)
        return phi

    def _drift_rate(self, t):
        """dy/dt of the full model at time t, in deg/sec."""
        w    = 2 * math.pi / self.T
        rate = self._theta[0]
        for h in range(1, self.n_harmonics + 1):
            i     = 1 + 2 * (h - 1)
            b     = self._theta[i]
            c     = self._theta[i + 1]
            hw    = h * w
            rate += b * hw * math.cos(hw * t) - c * hw * math.sin(hw * t)
        return rate

    # ── primary output ─────────────────────────────────────────────────────────
    @property
    def theta(self):
        """Fitted drift rate as of the most recent ingest, deg/sec — for logging/reporting.
        For real-time application between sparse updates, use predicted_rate(t) instead."""
        return self._drift_rate(self._t_last) if self.mode == PecMode.RLS else self.rate

    # ── secondary outputs ──────────────────────────────────────────────────────
    def dc_rate(self):
        """Steady-state drift rate in deg/sec (linear component, excluding harmonics)."""
        return self._theta[0] if self.mode == PecMode.RLS else self.rate

    def harmonic_rate(self, harmonic=1):
        """Amplitude/Peak contribution rate in deg/sec of the given harmonic (1-indexed)."""
        if self.mode != PecMode.RLS or harmonic < 1 or harmonic > self.n_harmonics:
            return 0.0
        i  = 1 + 2 * (harmonic - 1)
        hw = harmonic * 2 * math.pi / self.T
        return hw * math.sqrt(self._theta[i]**2 + self._theta[i+1]**2)

    def phase(self, harmonic=1):
        """PEC phase in radians of the given harmonic."""
        if self.mode != PecMode.RLS or harmonic < 1 or harmonic > self.n_harmonics:
            return 0.0
        i = 1 + 2 * (harmonic - 1)
        return math.atan2(self._theta[i+1], self._theta[i])

    def predicted_rate(self, t):
        """Instantaneous rate at arbitrary/current t — real-time correction and plotting."""
        return self._drift_rate(t) if self.mode == PecMode.RLS else self.rate

    def predicted_accum(self, t):
        """Predicted cumulative correction at t — for comparing against raw cumul."""
        if self.mode == PecMode.RLS:
            return float(self._phi(t) @ self._theta) + self._ref
        if self._y_last is None:
            return self._ref
        return self._y_last + self.rate * (t - self._t_last) + self._ref

    def eval_correction(self, t, dt, cap):
        """
        Compute and accumulate a PEC correction step over time span dt.
        Evaluated at the actual current time t (via predicted_rate) so harmonic
        phase keeps advancing between sparse guide updates rather than freezing
        at the last ingest.
        Returns (d, correction_was_applied). d is in degrees.
        """
        if not self.converged():
            return 0.0, False
        rate = self.predicted_rate(t)
        self._applied_rate = rate
        d = max(-cap, min(cap, rate * dt))
        if abs(d) < 1e-7:
            return 0.0, False
        self._applied_accum += d
        return d, True

    def eval_inhibit(self, n, min_obs, max_rmse, min_r2=0.5):
        if n < min_obs:
            self.inhibit = PecInhibit.TOO_FEW_OBS
        elif math.sqrt(self.sse) >= max_rmse:
            self.inhibit = PecInhibit.HIGH_RMSE
        elif self.r2 < min_r2 and self.var > self.sse:  # skip R² check if signal variance too small
            self.inhibit = PecInhibit.LOW_R2
        else:
            self.inhibit = PecInhibit.VALID

    def converged(self):
        return self.inhibit == PecInhibit.VALID

    def rmse_arcmin(self):
        return math.sqrt(self.sse) * 60