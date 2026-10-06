"""
Digital twin of the driver's motion control loop, for outcome-based regression tests.

Runs the driver's REAL control code - PID_Controller, SyncManager, KalmanFilter and the v2
SpeedCoordinator - against a model of the mount (tests/sim_polaris_mcu.py: shared SLOW level, per-axis
state, SLOW sampled on the MCU tick, FAST lag), on a simulated clock. Every 0.2 s a 518-style
measurement goes through the same pipeline as polaris.py (KF -> theta_to_q -> baseQ_to_topoQ ->
sky positions -> pid.measure -> control_step_calculate -> control()).

Only the small Polaris facade below is written for the twin (site, observer, flags, sky position
extraction, goto completion). Alignment is single-point (identity), no MAC/LGA/PEC/sync guiding.
Config coordinated_speed_control selects the motors as in the driver: on = v2 SpeedCoordinator,
off = the legacy MotorSpeedController (synchronous mirror, tests/sim_pid_loop.py).
"""
import asyncio
import datetime as _dt
import logging
import math
import os
import sys
import time as _time
import types

import ephem
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import control                                                           # noqa: E402
import control_worm                                                      # noqa: E402
from config import Config, CONFIG_TOML_PATH                             # noqa: E402
from control import PID_Controller, SyncManager, KalmanFilter           # noqa: E402
from kinematics import theta_to_q, q_to_theta, q_to_azaltroll, calc_parallactic_angle, wrap360, THETA2_MIN_MEAS  # noqa: E402
from speed_controller import RateUnits, SpeedCoordinator                # noqa: E402
from sim_polaris_mcu import McuModel                                          # noqa: E402
from shr import deg2rad, rad2deg, rad2hr                                # noqa: E402

LAT, LON = -33.654651, 151.12
MEASURE_DT = 0.2
M3_HOLD_S = 0.6            # hardware: 518 messages arrive every 0.2 s but M3's value only changes every ~0.55-0.6 s
SIM_DT = 0.01
NOISE_DEG = 1e-4
START_UTC = _dt.datetime(2026, 9, 27, 11, 0, 0)

TWIN_CONFIG = {
    "advanced_control": True, "advanced_kf": True, "advanced_slewing": True, "advanced_goto": True,
    "advanced_tracking": True, "advanced_alignment": False, "advanced_scc_enabled": False,
    "advanced_align_mac": False, "advanced_pec_drift": False, "advanced_pec_worm": False, "advanced_sync_guiding": False,
    "advanced_pulse_guiding": True, "advanced_orbitals": False, "coordinated_speed_control": False,
    "log_position": False, "log_pec": False, "log_quest_model": False,
    "site_latitude": LAT, "site_longitude": LON, "pid_Ka": 0.0, "pid_Kv": 0.0,
}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def utc(self):
        return START_UTC + _dt.timedelta(seconds=self.t - 1000.0)


class _Datetime(_dt.datetime):
    clock = None

    @classmethod
    def utcnow(cls):
        return cls.clock.utc()

    @classmethod
    def now(cls, tz=None):
        return cls.clock.utc()


class MotorShim:
    """Legacy per-axis motor interface over one SpeedCoordinator, on the simulated clock."""
    def __init__(self, core, units, axis, clock):
        self.core, self.units, self.axis, self.clock = core, units, axis, clock

    async def set_motor_speed(self, rate, rate_unit="DPS", ramp_duration=None, allow_PWM=True, tracking=False):
        dps = self.units[self.axis].to_dps(rate, rate_unit)
        self.core.set_speed(self.axis, dps, self.clock.monotonic(), hold=tracking, ramp_duration=ramp_duration,
                            allow_pwm=allow_PWM)

    async def stop(self):
        self.core.stop(self.axis)

    @property
    def rate_dps(self):
        return self.core.rate_dps(self.axis)

    @property
    def rate_raw(self):
        return self.core.rate_raw(self.axis)

    @property
    def max_dps(self):
        return self.units[self.axis].max_dps

    def get_cmdstr(self):
        return self.core.cmdstr(self.axis)

    def to_dps(self, rate, units):
        return self.units[self.axis].to_dps(rate, units)


class LegacyMotorShim:
    """Legacy per-axis MotorSpeedController, via the synchronous mirror of its dispatch loop in
    tests/sim_pid_loop.py (LegacyDriver), on the simulated clock."""
    def __init__(self, legacy, axis, clock):
        self.m, self.legacy, self.axis, self.clock = legacy.motors[axis], legacy, axis, clock

    async def set_motor_speed(self, rate, rate_unit="DPS", ramp_duration=None, allow_PWM=True, tracking=False):
        raw = self.m._model.interpolate[rate_unit].toRAW(rate)
        self.m.pending_update = (float(raw), ramp_duration, allow_PWM, tracking, self.clock.monotonic())

    async def stop(self):
        self.m.msgr.last_slow_raw_rate = None          # the mirror's MoveAxisMessenger (sim_pid_loop.LegacyDriver)
        await self.set_motor_speed(0, "RAW")

    @property
    def rate_dps(self):
        return self.m.rate_dps

    @property
    def rate_raw(self):
        return self.m.rate_raw

    @property
    def max_dps(self):
        return self.m._model.maxDPS

    def get_cmdstr(self):
        return self.m.get_cmdstr() if self.m.command is not None else " IDLE      "

    def to_dps(self, rate, units):
        return float(self.m._model.interpolate['RAW'].toDPS(self.m._model.interpolate[units].toRAW(rate)))


class TwinPolaris:
    """The parts of Polaris the control code reads, backed by the twin."""
    def __init__(self, twin):
        self.twin = twin
        self._sitelatitude, self._sitelongitude = LAT, LON
        self._observer = ephem.Observer()
        self._observer.lat, self._observer.lon = str(LAT), str(LON)
        self._observer.pressure = 0
        self._tracking = False
        self._trackingrate = 0
        self._connected = True
        self._age_518_seconds = 0.0
        self._zeta_meas = None
        self._ispulseguiding = False
        self._guideraterightascension = 15.0 / 3600 * 0.5
        self._guideratedeclination = 15.0 / 3600 * 0.5
        self._motorQ_state = theta_to_q(180, 45, 0)
        self._q1 = self._motorQ_state
        self._theta_raw = np.array([180.0, 45.0, 0.0])
        self._p_azimuth, self._p_altitude, self._p_roll = 180.0, 45.0, 0.0
        self._rightascension = self._declination = 0.0
        self.rightascension = self.declination = 0.0
        self.goto_complete_at = None

    def altaz2radec(self, alt, az):
        self._observer.date = ephem.Date(self.twin.clock.utc())
        ra, dec = self._observer.radec_of(deg2rad(az), deg2rad(alt))
        return rad2hr(ra), rad2deg(dec)

    def markGotoAsComplete(self):
        self.goto_complete_at = self.twin.clock.monotonic()


class Twin:
    def __init__(self, monkeypatch, config=None, fast_lag_s=0.35, seed=0, m3_hold_s=M3_HOLD_S):
        Config.load(tomlpath=CONFIG_TOML_PATH, pilotpath="/nonexistent")
        for key, value in {**TWIN_CONFIG, **(config or {})}.items():
            monkeypatch.setattr(Config, key, value, raising=False)
        self.clock = Clock()
        _Datetime.clock = self.clock
        shim = types.SimpleNamespace(datetime=_Datetime, timedelta=_dt.timedelta)
        monkeypatch.setattr(control, "datetime", shim)
        monkeypatch.setattr(control.time, "monotonic", self.clock.monotonic)
        if control_worm.WORM_PROFILE_PATH == control_worm.DATA_DIR / 'worm_profile.json':
            # the worm gear correction uses data/worm_profile.json when it is switched on: a developer's own must not
            # change the twin (a test that wants a profile sets control_worm.WORM_PROFILE_PATH before creating the twin)
            monkeypatch.setattr(control_worm, "WORM_PROFILE_PATH", control_worm.DATA_DIR / 'twin_has_no_worm_profile.json')
        monkeypatch.setattr(ephem, "now", lambda: ephem.Date(self.clock.utc()))
        self.rng = np.random.default_rng(seed)
        self.logger = logging.getLogger("twin")
        self.polaris = TwinPolaris(self)
        if Config.coordinated_speed_control:
            units = {a: RateUnits(control.CalibrationManager(liveInstance=False).baseline_data[a]) for a in range(3)}
            self.core = SpeedCoordinator(units)
            self.polaris._motors = {a: MotorShim(self.core, units, a, self.clock) for a in range(3)}
            self._motor_tick = lambda t: [msg for _a, msg in self.core.tick(t)]
        else:
            import sim_pid_loop
            self.core = sim_pid_loop.LegacyDriver(sim_pid_loop.calibration())
            self.polaris._motors = {a: LegacyMotorShim(self.core, a, self.clock) for a in range(3)}
            self._motor_tick = self.core.tick
        self.polaris._sm = SyncManager(self.logger, self.polaris)
        self.pid = PID_Controller(self.logger, self.polaris, loop=None)
        self.polaris._pid = self.pid
        self.kf = KalmanFilter(self.logger, np.zeros(6))
        self.mcu = McuModel(fast_lag_s=fast_lag_s)
        self.loop = asyncio.new_event_loop()
        self._next_meas = self.clock.t
        self._last_raw = None
        self.m3_hold_s = m3_hold_s
        self._m3_held, self._m3_next = None, self.clock.t
        self.pid.check_latlon_configured()

    # ---- mount state -----------------------------------------------------------------
    def place(self, theta):
        """Put the mount at motor angles theta (deg) and let the loop settle idle."""
        self.mcu.position = np.array(theta, dtype=float)
        self.kf = KalmanFilter(self.logger, np.concatenate([self.mcu.position, np.zeros(3)]))
        self._last_raw = None
        self._m3_held = None
        self.run(2.0)
        self.pid.reset_sp()

    @property
    def theta(self):
        return self.mcu.position.copy()

    # ---- the control loop --------------------------------------------------------------
    def _measure_and_control(self):
        p = self.polaris
        theta_raw = self.mcu.position + self.rng.normal(0, NOISE_DEG, 3)
        if self.m3_hold_s:                                  # M3 in 518 is sample-and-hold, refreshed every m3_hold_s
            if self._m3_held is None or self.clock.t >= self._m3_next - 1e-9:
                self._m3_held, self._m3_next = theta_raw[2], self.clock.t + self.m3_hold_s
            theta_raw[2] = self._m3_held + self.rng.normal(0, NOISE_DEG)
        omega_ref = np.array([p._motors[a].rate_dps for a in range(3)])
        omega_meas = omega_ref if self._last_raw is None else (theta_raw - self._last_raw) / MEASURE_DT
        self._last_raw = theta_raw
        p._theta_raw = theta_raw
        p._zeta_meas = [theta_raw[0] - 180.0, theta_raw[1] - 45.0, theta_raw[2]]   # "517" raw motor angles (hardware: zeta = theta - (180, 45, 0))
        self.kf.predict(omega_ref)
        is_tracking = self.pid.mode == 'TRACK'
        self.kf.observe(theta_raw, omega_meas, omega_ref, theta_ref=(self.pid.theta_ref if is_tracking else None))
        theta_state, _ = self.kf.get_state()
        motorQ_state = theta_to_q(*theta_state)
        cameraQ_pv, motorQ_pv = p._sm.baseQ_to_topoQ(motorQ_state, theta=theta_state)
        theta_pv = np.array(q_to_theta(motorQ_pv, self.pid._lp, theta2_min=THETA2_MIN_MEAS))
        p._sm.cache_axes_B(cameraQ_pv if self.pid.cameraQ_ref is None else self.pid.cameraQ_ref)
        p._motorQ_state = motorQ_state
        az, alt, roll = q_to_azaltroll(cameraQ_pv)
        ra, dec = p.altaz2radec(alt, az)
        para = calc_parallactic_angle(az, alt, LAT)
        p._rightascension = p.rightascension = ra
        p._declination = p.declination = dec
        p._p_azimuth, p._p_altitude, p._p_roll = az, alt, roll
        delta_pv = np.array([ra * 15, dec, wrap360(roll + para)])
        alpha_pv = np.array([az, alt, roll])
        self.pid.measure(delta_pv, alpha_pv, theta_pv, p._zeta_meas, measurement_lag_s=0.0)
        self.pid.control_step_calculate()
        self.loop.run_until_complete(self.pid.control_step_execute())

    def run(self, seconds, on_measure=None):
        end = self.clock.t + seconds
        while self.clock.t < end - 1e-9:
            if self.clock.t >= self._next_meas - 1e-9:
                self._measure_and_control()
                self._next_meas += MEASURE_DT
                if on_measure:
                    on_measure(self)
            for msg in self._motor_tick(self.clock.t):
                self.mcu.feed(self.clock.t, msg)
            self.clock.t = round(self.clock.t + SIM_DT, 9)
            self.mcu.advance(self.clock.t)

    # ---- driver-level actions (mirror the thin glue in polaris.py) ---------------------
    def start_tracking(self):
        self.polaris._tracking = True
        self.pid.set_tracking_on()

    def goto_altaz(self, az, alt, roll=None):
        target = {"az": az, "alt": alt} if roll is None else {"az": az, "alt": alt, "roll": roll}
        self.polaris.goto_complete_at = None
        self.pid.set_alpha_target(target)
        self.pid.set_goto_complete_callback(self.polaris.markGotoAsComplete)

    def goto_radec(self, ra_h, dec):
        """SlewToCoordinates while tracking (polaris.SlewToCoordinates): target given as its Az/Alt now."""
        self.polaris._observer.date = ephem.Date(self.clock.utc())
        body = ephem.FixedBody()
        body._ra, body._dec, body._epoch = math.radians(ra_h * 15), math.radians(dec), ephem.Date(self.clock.utc())
        body.compute(self.polaris._observer)
        self.goto_altaz(math.degrees(body.az), math.degrees(body.alt))

    def slew_relative(self, **coords):
        """Polaris:SlewRelative for az/alt/roll/ra/dec/pa keys (relative to the PID setpoint)."""
        alpha = {k: v for k, v in coords.items() if k in ("az", "alt", "roll")}
        delta = {k: v for k, v in coords.items() if k in ("ra", "dec", "pa")}
        self.polaris.goto_complete_at = None
        if alpha:
            idx = {"az": 0, "alt": 1, "roll": 2}
            self.pid.set_alpha_target({k: self.pid.alpha_sp[idx[k]] + v for k, v in alpha.items()})
        if delta:
            idx, scale = {"ra": 0, "dec": 1, "pa": 2}, {"ra": 15, "dec": 1, "pa": 1}
            self.pid.set_delta_target({k: self.pid.delta_sp[idx[k]] / scale[k] + v for k, v in delta.items()})
        self.pid.set_goto_complete_callback(self.polaris.markGotoAsComplete)

    def close(self):
        self.loop.close()
