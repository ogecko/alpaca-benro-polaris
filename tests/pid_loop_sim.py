"""
Offline closed-loop simulation of PID sidereal tracking: PID (mirror of PID_Controller's TRACK
law) -> motor speed controller (legacy or v2) -> MCU model (tests/mcu_model.py) -> position
measured at the 518 cadence -> PID.

Used by tests/test_speed_controller_tracking_sim.py to compare tracking RMS error between the
legacy MotorSpeedController and the v2 SpeedCoordinator without hardware.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

from control import CalibrationManager, MotorSpeedController, MoveAxisMessenger    # noqa: E402
from speed_controller import RateUnits, SpeedCoordinator                           # noqa: E402
from mcu_model import McuModel                                                     # noqa: E402

# PID gains as in driver/config.toml
KP, KI, KD, KE, KA = 1.0, 0.07, 0.5, 0.4, 5.0
PID_DT = 0.2                 # PID control loop period
MEASURE_DT = 0.2             # 518 position message cadence
SIM_DT = 0.01
NOISE_DEG = 1e-4             # observed traw noise


def calibration():
    cm = CalibrationManager(liveInstance=False)
    cm.createTestDataFromBaseline()
    cm.generateCalibrationFromBaselineAndTestData()
    cm.generateInterpolatorsFromCalibrationData()
    return cm


class Pid:
    """Mirror of PID_Controller.errintegral/pid/constrain for mode TRACK (per axis arrays)."""
    def __init__(self):
        self.omega_op = np.zeros(3)
        self.integral = np.zeros(3)

    def step(self, err, omega_ff):
        rate_limit = 1 / 60
        preloading = np.abs(err) > rate_limit
        self.integral = np.clip(self.integral + np.where(preloading, 0, err) * PID_DT, -rate_limit / KI, rate_limit / KI)
        tgt = KP * err + KI * self.integral - KD * (self.omega_op - omega_ff) + omega_ff
        ctl = self.omega_op + np.clip((tgt - self.omega_op) / PID_DT, -KA, KA) * PID_DT
        self.omega_op = ctl * (1 - KE) + KE * self.omega_op
        return self.omega_op


class V2Driver:
    def __init__(self, cm):
        self.core = SpeedCoordinator({a: RateUnits(cm.baseline_data[a]) for a in range(3)})

    def command(self, axis, dps, now):
        self.core.set_speed(axis, dps, now, hold=True, ramp_duration=PID_DT)

    def tick(self, now):
        return [msg for _a, msg in self.core.tick(now)]


class LegacyDriver:
    """Synchronous mirror of MotorSpeedController (control.py): its own _apply_pending_update, plus
    the body of its _dispatch_loop and MoveAxisMessenger de-duplication, on a simulated clock."""
    def __init__(self, cm):
        self.motors = []
        for axis in range(3):
            m = object.__new__(MotorSpeedController)
            m.axis, m._calibration_manager = axis, cm
            m.pending_update, m.rate_dps, m.rate_raw, m.mode = None, 0.0, 0.0, 'IDLE'
            m.ramp_start = m.ramp_target = 0.0
            m.ramp_duration, m.ramp_start_time, m.next_dispatch_time = None, 0.0, 0.0
            m.command, m.duty_cycle, m.pwm_phase, m.last_switch_time = None, 0.0, 'ON', 0.0
            m.msgr = MoveAxisMessenger(axis, None)
            self.motors.append(m)

    def command(self, axis, dps, now):
        m = self.motors[axis]
        raw = m._model.interpolate['DPS'].toRAW(dps)
        m.pending_update = (float(raw), PID_DT, True, True, now)

    def _slow(self, m, rate, out):
        r = int(np.clip(rate, -5, 5))
        if r != m.msgr.last_slow_raw_rate:
            m.msgr.last_slow_raw_rate = r
            out.append(f"1&{m.msgr.cmd_slow}&3&key:{0 if r > 0 else 1};state:{0 if r == 0 else 1};level:{abs(r)};#")

    def tick(self, now):
        out = []
        for m in self.motors:
            m._apply_pending_update(now)
            if now < m.next_dispatch_time:
                continue
            if m.mode in ("FAST", "FAST_RAMP"):
                out.append(f"1&{m.msgr.cmd_fast}&3&speed:{int(np.clip(m.command if m.mode == 'FAST' else m.ramp_target, -2500, 2500))};#")
                m.next_dispatch_time = now + 0.05
            elif m.mode == "SLOW":
                self._slow(m, m.command, out)
                m.next_dispatch_time = math.inf
                if m.command == 0:
                    m.mode = "IDLE"
            elif m.mode == "SLOW_PWM":
                base, next_up = m.command
                was_on = m.pwm_phase == "ON"
                self._slow(m, base if was_on else next_up, out)
                m.next_dispatch_time = now + 0.5 * (1 - m.duty_cycle if was_on else m.duty_cycle)
                m.pwm_phase = "OFF" if was_on else "ON"
            else:
                m.next_dispatch_time = now + 0.05
        return out


def track(driver, omega_ff, duration=180.0, settle=30.0, seed=0, pid_jitter=0.02):
    """Run PID tracking of a constant-rate reference; return RMS error per axis and total (arcsec).
    The PID period varies uniformly within ±pid_jitter seconds, as the asyncio loop does on hardware."""
    rng = np.random.default_rng(seed)
    mcu, pid = McuModel(), Pid()
    omega_ff = np.asarray(omega_ff, dtype=float)
    t, next_pid, next_meas = 0.0, 0.0, 0.0
    pv = np.zeros(3)
    errs = []
    while t < duration:
        if t >= next_meas - 1e-9:
            pv = mcu.position + rng.normal(0, NOISE_DEG, 3)
            next_meas += MEASURE_DT
        if t >= next_pid - 1e-9:
            err = omega_ff * t - pv
            if t >= settle:
                errs.append(err.copy())
            for axis, dps in enumerate(pid.step(err, omega_ff)):
                driver.command(axis, dps, t)
            next_pid += PID_DT + rng.uniform(-pid_jitter, pid_jitter)
        for msg in driver.tick(t):
            mcu.feed(t, msg)
        t = round(t + SIM_DT, 9)
        mcu.advance(t)
    e = np.array(errs) * 3600
    return np.sqrt(np.mean(e ** 2, axis=0)), float(np.sqrt(np.mean(np.sum(e ** 2, axis=1))))


def orientation_motor_rates(az, alt, roll, lat=-33.654651, dt=20.0):
    """Sidereal-tracking motor rates (deg/s) at an Az/Alt/Roll pose, holding position angle fixed."""
    from kinematics import azaltroll_to_theta_ik, calc_parallactic_angle
    A, h, phi = map(math.radians, (az, alt, lat))
    dec = math.asin(math.sin(h) * math.sin(phi) + math.cos(h) * math.cos(phi) * math.cos(A))
    H = math.atan2(-math.sin(A) * math.cos(h), math.sin(h) * math.cos(phi) - math.cos(h) * math.sin(phi) * math.cos(A))
    H1 = H + math.radians(360 / 86164.1 * dt)
    alt1 = math.asin(math.sin(dec) * math.sin(phi) + math.cos(dec) * math.cos(phi) * math.cos(H1))
    az1 = math.atan2(-math.cos(dec) * math.sin(H1), math.sin(dec) * math.cos(phi) - math.cos(dec) * math.sin(phi) * math.cos(H1))
    az1, alt1 = math.degrees(az1) % 360, math.degrees(alt1)
    q0, q1 = calc_parallactic_angle(az, alt, lat), calc_parallactic_angle(az1, alt1, lat)
    roll1 = roll - ((q1 - q0 + 180) % 360 - 180)
    t0 = np.array(azaltroll_to_theta_ik(az, alt, roll))
    t1 = np.array(azaltroll_to_theta_ik(az1, alt1, roll1))
    return ((t1 - t0 + 180) % 360 - 180) / dt
