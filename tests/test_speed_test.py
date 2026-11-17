"""
Motor speed calibration test (polaris.moveaxis_speed_test / moveaxis_speed_measurement) on a fake mount: M1/M3 run
towards the limit with room for the measurement, stop at the limit margin, a run in the negative direction can be
stable, and log_position logs KFLOG while the test runs.
"""
import asyncio
import logging
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
import polaris as polaris_mod                                                       # noqa: E402
from polaris import Polaris                                                         # noqa: E402

DT = 0.25


class FakeMotor:
    def __init__(self, mount, axis):
        self.mount, self.axis, self.rate_raw, self.rate_dps = mount, axis, 0.0, 0.0

    def to_dps(self, rate, units):
        return float(rate) * 0.004                       # 2500 -> 10 deg/s, a little faster than the mount

    async def set_motor_speed(self, rate, units):
        self.rate_raw, self.rate_dps = rate, self.to_dps(rate, units)
        self.mount.commands.append(rate)
        self.mount.modes_at_command.append(self.mount._pid.mode)


class FakeMount:
    """Polaris's attributes the speed test reads; asyncio.sleep advances the motor at its commanded speed."""
    def __init__(self, axis, zeta):
        self.logger = logging.getLogger('test')
        self.lifecycle = SimpleNamespace(start=lambda: None, reset=lambda: None, should_stop=lambda: False)
        self._kf = SimpleNamespace(log_untracked=False)
        self._pid = SimpleNamespace(mode='IDLE')
        self.commands, self.results, self.kf_logging, self.modes_at_command = [], [], [], []
        self._motors = {a: FakeMotor(self, a) for a in range(3)}
        self._zeta_meas = list(zeta)
        self._theta_raw = np.array([zeta[0] + 180.0, zeta[1] + 45.0, zeta[2]])
        self._omega_meas = np.zeros(3)
        self._cm = SimpleNamespace(addTestResult=lambda *a: self.results.append(a))
        self.axis = axis

    async def findHome(self):
        pass

    def advance(self, dt):
        dps = self._motors[self.axis].rate_dps
        self._zeta_meas[self.axis] += dps * dt
        self._omega_meas = np.zeros(3)
        self._omega_meas[self.axis] = dps
        self.kf_logging.append(self._kf.log_untracked)


SPEED_TEST_LIMITS = Polaris._speed_test_limits
SPEED_TEST_MAX_S = Polaris.SPEED_TEST_MAX_S


@pytest.fixture
def run(monkeypatch):
    def go(axis, zeta, rates, overrides=(), pid_mode='IDLE'):
        m = FakeMount(axis, zeta)
        m._pid.mode = pid_mode
        m._speed_test_limits = lambda a: SPEED_TEST_LIMITS(m, a)
        m.SPEED_TEST_MAX_S = SPEED_TEST_MAX_S
        m.moveaxis_speed_measurement = lambda a, r: Polaris.moveaxis_speed_measurement(m, a, r)
        monkeypatch.setattr(polaris_mod.Config, 'advanced_control', True, raising=False)
        for key, value in {'zeta_safety_margin': 10, 'z1_min_limit': -270, 'z1_max_limit': 270,
                           'z3_min_limit': -270, 'z3_max_limit': 270}.items():
            if key not in overrides:
                monkeypatch.setattr(polaris_mod.Config, key, value, raising=False)
        real_sleep = asyncio.sleep

        async def sleep(s):
            m.advance(s)
            await real_sleep(0)
        monkeypatch.setattr(asyncio, 'sleep', sleep)
        asyncio.run(Polaris.moveaxis_speed_test(m, axis, rates))
        return m
    return go


def test_m3_near_its_upper_limit_runs_the_other_way(run):
    lo, hi = -260.0, 260.0
    m = run(2, (0.0, 0.0, hi - 50.0), [2500])               # 10 deg/s for 16 s needs 160 deg: only 50 above
    assert m.commands[0] == 0 and m.commands[1] == -2500, m.commands
    assert m.results[0][4] == 'COMPLETED' and m.results[0][2] == pytest.approx(10.0)
    assert lo <= m._zeta_meas[2] <= hi


def test_m1_with_room_keeps_its_direction(run):
    m = run(0, (0.0, 0.0, 0.0), [500, 1000])
    assert m.commands[:2] == [500, 1000]                    # no stop and reversal between speeds
    assert [r[4] for r in m.results] == ['COMPLETED', 'COMPLETED']


def test_stops_at_the_limit_margin(run, monkeypatch):
    # no room either way for a full measurement: it goes the roomier way and stops at the margin
    for key, value in {'z3_min_limit': -40, 'z3_max_limit': 40, 'zeta_safety_margin': 10}.items():
        monkeypatch.setattr(polaris_mod.Config, key, value, raising=False)
    m = run(2, (0.0, 0.0, 5.0), [2500], overrides=('z3_min_limit', 'z3_max_limit', 'zeta_safety_margin'))
    assert m.results[0][4] == 'LIMIT'
    assert m._zeta_meas[2] <= 30.0 + 10.0 * DT + 1e-9          # stopped within a sample of the margin


def test_kflog_is_on_only_while_the_test_runs(run):
    m = run(0, (0.0, 0.0, 0.0), [500])
    assert any(m.kf_logging) and m._kf.log_untracked is False


def test_waits_for_the_last_return_home_before_measuring(run, monkeypatch):
    """A test started while the previous one's return home ran measured the PID's settling (field 2026-10-17)."""
    real = FakeMount.advance

    def advance(self, dt):
        self.homing_left = getattr(self, 'homing_left', 5.0) - dt
        if self.homing_left <= 0:
            self._pid.mode = 'IDLE'
        real(self, dt)
    monkeypatch.setattr(FakeMount, 'advance', advance)
    m = run(0, (0.0, 0.0, 0.0), [500], pid_mode='HOMING')
    assert m.modes_at_command[0] == 'IDLE' and m.results[0][4] == 'COMPLETED', m.modes_at_command
