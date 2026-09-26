"""
Purpose tests for the shared-level motor speed controller (driver/speed_controller.py).

What a Polaris motor speed controller is for:
  1. Each motor's average velocity equals its commanded rate.
  2. Motors are independent: commanding one never changes another's velocity.
     (The MCU has ONE slow-jog level shared by all axes, A Polaris System Design.md §5.4.)
  3. A holding/tracking motor never drops torque (never sent state 0).
  4. A stopped motor is stopped (state 0, then silence).
  5. Position ripple from modulation is bounded and rate changes take effect promptly.
  6. Fast rates use FAST commands, refreshed before the MCU watchdog expires, with ramps.
  7. The message rate to the mount is bounded; unchanged commands are not resent.
  8. Rate units (DPS / RAW / ASCOM) keep their existing meaning for clients.

Behaviour is checked through tests/mcu_model.py, a model of the MCU verified on hardware.
"""
import asyncio
import math
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

from speed_controller import (RateUnits, SpeedCoordinator, SpeedControllerRuntime, SwitchableMotor,
                              SLOW_DPS, MAX_SLOW_DPS, BAND_DPS, MIN_SLOW_DWELL, REVERSING_CYCLE_S)
from control import CalibrationManager
from mcu_model import McuModel

SIDEREAL_DPS = 360 / 86164.1
TICK = 0.05


@pytest.fixture
def units():
    cm = CalibrationManager(liveInstance=False)
    return {axis: RateUnits(cm.baseline_data[axis]) for axis in range(3)}


@pytest.fixture
def ctrl(units):
    return SpeedCoordinator(units)


def run(ctrl, mcu, t0, duration):
    """Drive the coordinator and the MCU model with synthetic time; return end time."""
    t = t0
    end = t0 + duration
    while t < end - 1e-9:
        for _axis, msg in ctrl.tick(t):
            mcu.feed(t, msg)
        t = round(t + TICK, 9)
        mcu.advance(t)
    return t


MEASURE_S = 120.0


def mean_velocity(ctrl, mcu, rates, hold=False, warmup=2.0, duration=MEASURE_S):
    for axis, dps in enumerate(rates):
        ctrl.set_speed(axis, dps, now=0.0, hold=hold)
    t = run(ctrl, mcu, 0.0, warmup)
    p0 = mcu.position.copy()
    run(ctrl, mcu, t, duration)
    return (mcu.position - p0) / duration


def window_bound(ctrl, duration=MEASURE_S):
    """Largest average-rate error a finite window can show without drift: the modulation keeps
    position error within one slow period at the top speed of the level, at each window end."""
    return 2 * ctrl.period * SLOW_DPS[(ctrl.level or 1, 2)] / duration


def assert_rate(axis, measured, target, bound=0.0):
    tol = max(0.01 * abs(target), 1e-6) + bound
    assert abs(measured - target) <= tol, (
        f"M{axis + 1} average velocity {measured:+.6f} dps does not match commanded "
        f"{target:+.6f} dps (tolerance ±{tol:.6f})")


# ---------------------------------------------------------------------------------------
# 8. Rate units keep their meaning
# ---------------------------------------------------------------------------------------

def test_dps_is_passed_through(units):
    assert units[0].to_dps(0.0123, "DPS") == pytest.approx(0.0123), "DPS input must not be converted"


@pytest.mark.parametrize("raw,level", [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])
def test_raw_integer_rates_are_firmware_levels(units, raw, level):
    assert units[0].to_dps(raw, "RAW") == pytest.approx(SLOW_DPS[(level, 1)]), (
        f"RAW {raw} must mean SLOW level {level} (state 1) = {SLOW_DPS[(level, 1)]} dps")


@pytest.mark.parametrize("raw,expected", [(0.5, 0.5 * SLOW_DPS[(1, 1)]),
                                          (1.5, (SLOW_DPS[(1, 1)] + SLOW_DPS[(2, 1)]) / 2),
                                          (4.25, 0.75 * SLOW_DPS[(4, 1)] + 0.25 * SLOW_DPS[(5, 1)])])
def test_raw_fractions_are_linear_between_levels(units, raw, expected):
    assert units[0].to_dps(raw, "RAW") == pytest.approx(expected), (
        f"RAW {raw} must be a linear PWM mix of the neighbouring levels ({expected:.5f} dps)")


def test_raw_above_5_is_fast_speed_units(units):
    assert units[0].to_dps(1000, "RAW") == pytest.approx(1.7124653, rel=1e-3), (
        "RAW > 5 must be FAST speed units, converted with the FAST interpolator")


def test_ascom_matches_raw_up_to_5_and_is_fast_above(units):
    assert units[0].to_dps(3, "ASCOM") == pytest.approx(units[0].to_dps(3, "RAW")), "ASCOM 0-5 must equal RAW 0-5"
    assert units[0].to_dps(9, "ASCOM") == pytest.approx(8.9185931, rel=1e-3), "ASCOM 9 must be the fastest FAST speed"


@pytest.mark.parametrize("unit,rate", [("RAW", 2.5), ("ASCOM", 7), ("DPS", 0.3)])
def test_units_are_sign_symmetric(units, unit, rate):
    assert units[1].to_dps(-rate, unit) == pytest.approx(-units[1].to_dps(rate, unit)), (
        f"negative {unit} rates must mirror positive ones")


def test_fast_units_roundtrip(units):
    for dps in (0.3, 1.0, 4.0, 8.0):
        u = units[2].fast_units(dps)
        assert units[2].to_dps(u, "RAW") == pytest.approx(dps, rel=0.01), (
            f"fast_units({dps}) = {u} does not convert back to {dps} dps")


# ---------------------------------------------------------------------------------------
# 1. Average velocity equals commanded rate
# ---------------------------------------------------------------------------------------

SINGLE_RATES = [SIDEREAL_DPS, 0.001, 0.0059, 0.008, 0.0119, 0.015, 0.03, 0.05, 0.1, 0.2, 0.24]


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("target", SINGLE_RATES + [-r for r in SINGLE_RATES[:4]])
def test_single_axis_average_velocity_matches_command(ctrl, axis, target):
    rates = [0.0, 0.0, 0.0]
    rates[axis] = target
    v = mean_velocity(ctrl, McuModel(), rates)
    assert_rate(axis, v[axis], target, window_bound(ctrl))


# ---------------------------------------------------------------------------------------
# 2. Axes are independent despite the shared level
# ---------------------------------------------------------------------------------------

INDEPENDENT_CASES = {
    "tracking_mix": (0.0042, -0.0031, 0.0025),
    "m1_above_level1": (0.0073, 0.0035, -0.0020),
    "low_alt_low_roll": (0.0130, 0.0030, -0.0115),
    "guide_catchup_m1": (0.0200, 0.0040, 0.0010),
    "hardware_case_raw_0p8_vs_2p5": (0.8 * SLOW_DPS[(1, 1)], (SLOW_DPS[(2, 1)] + SLOW_DPS[(3, 1)]) / 2, 0.0),
    "jog_m3": (0.0030, -0.0020, 0.1500),
    "two_fast_axes_near_each_other": (0.0327, 0.0310, 0.0040),   # 2nd axis often above the period's level
}


@pytest.mark.parametrize("rates", INDEPENDENT_CASES.values(), ids=INDEPENDENT_CASES.keys())
def test_axes_are_independent(ctrl, rates):
    v = mean_velocity(ctrl, McuModel(), rates, hold=True)
    for axis in range(3):
        assert_rate(axis, v[axis], rates[axis], window_bound(ctrl))


def test_starting_another_axis_does_not_change_a_running_axis(ctrl):
    mcu = McuModel()
    target = 0.8 * SLOW_DPS[(1, 1)]
    ctrl.set_speed(1, target, now=0.0)
    t = run(ctrl, mcu, 0.0, 2.0)
    p = mcu.position.copy()
    t = run(ctrl, mcu, t, MEASURE_S)
    assert_rate(1, (mcu.position[1] - p[1]) / MEASURE_S, target, window_bound(ctrl))
    ctrl.set_speed(0, 0.1, now=t)                     # M1 now needs level 4
    t = run(ctrl, mcu, t, 2.0)
    assert ctrl.level == 4
    p = mcu.position.copy()
    run(ctrl, mcu, t, MEASURE_S)
    assert_rate(1, (mcu.position[1] - p[1]) / MEASURE_S, target, window_bound(ctrl))


def test_all_active_slow_axes_always_share_one_level(ctrl):
    mcu = McuModel()
    for axis, dps in enumerate((0.0073, 0.03, -0.002)):
        ctrl.set_speed(axis, dps, now=0.0, hold=True)
    t = 0.0
    while t < 20.0:
        for _a, msg in ctrl.tick(t):
            mcu.feed(t, msg)
        levels = {int(fields[2]) for (_t, a, kind, fields) in
                  [max((e for e in mcu.log if e[1] == ax and e[2] == "SLOW"), default=(0, ax, "NONE", None))
                   for ax in range(3)] if kind == "SLOW" and fields[1] in (1, 2)}
        assert len(levels) <= 1, f"at t={t:.2f}s active axes were last sent different levels {levels}"
        t = round(t + TICK, 9)
        mcu.advance(t)


def test_level_stays_1_while_all_rates_are_in_band(ctrl):
    mcu = McuModel()
    rates = (0.0118, -0.0100, 0.0060)                 # all within the level-1 band (<= 0.012)
    for axis, dps in enumerate(rates):
        ctrl.set_speed(axis, dps, now=0.0, hold=True)
    run(ctrl, mcu, 0.0, 20.0)
    sent_levels = {fields[2] for (_t, _a, kind, fields) in mcu.log if kind == "SLOW"}
    assert sent_levels == {1}, (
        f"all rates are within the level-1 band ({BAND_DPS} dps) but levels {sent_levels} were sent")


# ---------------------------------------------------------------------------------------
# 3 / 4. Holding never drops torque; stopping stops
# ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("target", [0.0, 0.0005, -0.003])
def test_holding_axis_never_releases_torque(ctrl, target):
    mcu = McuModel()
    ctrl.set_speed(0, target, now=0.0, hold=True)
    run(ctrl, mcu, 0.0, 20.0)
    stops = [e for e in mcu.log if e[1] == 0 and e[2] == "SLOW" and e[3][1] == 0]
    assert not stops, f"holding M1 at {target} dps was sent state 0 (torque release) {len(stops)} times"


def test_zero_rate_without_hold_stops_the_axis(ctrl):
    mcu = McuModel()
    ctrl.set_speed(0, 0.01, now=0.0)
    t = run(ctrl, mcu, 0.0, 2.0)
    ctrl.set_speed(0, 0.0, now=t)
    t = run(ctrl, mcu, t, 1.0)
    n = len(mcu.log)
    run(ctrl, mcu, t, 5.0)
    assert mcu.state[0] == 0, "M1 was not sent state 0 after being commanded to 0 without hold"
    assert len(mcu.log) == n, f"{len(mcu.log) - n} messages were sent to a stopped mount"


def test_hold_zero_averages_to_zero(ctrl):
    v = mean_velocity(ctrl, McuModel(), (0.0, 0.0, 0.0), hold=True)
    for axis in range(3):
        assert_rate(axis, v[axis], 0.0, window_bound(ctrl))


# ---------------------------------------------------------------------------------------
# 5. Ripple is bounded; changes are prompt
# ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("target", [SIDEREAL_DPS, 0.009, 0.02])
def test_position_ripple_is_bounded(ctrl, target):
    mcu = McuModel()
    ctrl.set_speed(0, target, now=0.0, hold=True)
    ctrl.set_speed(1, 0.004, now=0.0, hold=True)
    t = run(ctrl, mcu, 0.0, 2.0)
    p0, t0 = mcu.position[0], t
    worst = 0.0
    while t < t0 + 20.0:
        t = run(ctrl, mcu, t, TICK)
        worst = max(worst, abs(mcu.position[0] - p0 - target * (t - t0)))
    limit = 2 * ctrl.period * SLOW_DPS[(ctrl.level, 2)]
    assert worst <= limit, f"M1 position ripple {worst * 3600:.1f} arcsec exceeds {limit * 3600:.1f} arcsec"


def test_rate_change_takes_effect_within_one_slow_period(ctrl):
    mcu = McuModel()
    ctrl.set_speed(0, 0.0059, now=0.0, hold=True)
    t = run(ctrl, mcu, 0.0, 2.0)
    ctrl.set_speed(0, 0.0119, now=t)
    t = run(ctrl, mcu, t, ctrl.period + TICK)
    assert mcu.dps(0) == pytest.approx(0.0119, rel=0.01), (
        f"M1 still at {mcu.dps(0):.5f} dps one slow period after being commanded 0.0119 dps")


def test_reported_rate_is_the_commanded_rate(ctrl):
    ctrl.set_speed(0, 0.0073, now=0.0, hold=True)
    ctrl.set_speed(1, 1.5, now=0.0)
    assert ctrl.rate_dps(0) == pytest.approx(0.0073), "rate_dps must report the commanded average rate (used by the KF)"
    assert ctrl.rate_dps(1) == pytest.approx(1.5), "rate_dps must report the commanded FAST rate"


def test_slow_commands_respect_minimum_dwell(ctrl):
    """The MCU only picks up SLOW changes on its scheduler tick; on hardware 0.045-0.055 s dwells
    aliased to 0.28x-0.48x of the commanded rate. No SLOW command may be replaced sooner than
    MIN_SLOW_DWELL, even when targets change faster (the PID updates every 0.2 s)."""
    mcu = McuModel()
    t = 0.0
    for k in range(100):                                  # new targets every 0.2 s, like the PID
        ctrl.set_speed(0, 0.0073 + 0.002 * math.sin(k), now=t, hold=True)
        ctrl.set_speed(1, 0.0300 + 0.004 * math.cos(k), now=t, hold=True)
        t = run(ctrl, mcu, t, 0.2)
    for axis in (0, 1):
        # an axis's own direction/state changes; re-sends that only carry a new shared level don't count
        changes, last = [], None
        for (te, ax, kind, fields) in mcu.log:
            if ax == axis and kind == "SLOW" and fields[:2] != last:
                changes.append(te)
                last = fields[:2]
        shortest = min(np.diff(changes))
        assert shortest >= MIN_SLOW_DWELL - 1e-9, f"M{axis + 1} changed direction/state after only {shortest:.3f} s"


# ---------------------------------------------------------------------------------------
# 6. FAST
# ---------------------------------------------------------------------------------------

def test_fast_rates_use_fast_commands_refreshed_before_watchdog(ctrl):
    mcu = McuModel()
    ctrl.set_speed(0, 2.0, now=0.0)
    run(ctrl, mcu, 0.0, 3.0)
    fast = [e[0] for e in mcu.log if e[1] == 0 and e[2] == "FAST"]
    slow = [e for e in mcu.log if e[1] == 0 and e[2] == "SLOW"]
    assert fast and not slow, "a 2 dps rate must be sent as FAST (513) only"
    assert max(np.diff(fast)) <= 0.1 + 1e-9, "FAST must be refreshed at least every 0.1 s (MCU watchdog)"
    assert mcu.dps(0) == pytest.approx(2.0, rel=0.02), f"FAST velocity {mcu.dps(0):.3f} dps is not the commanded 2.0"


def test_fast_ramp_is_monotonic_and_reaches_target(ctrl, units):
    mcu = McuModel()
    ctrl.set_speed(0, 4.0, now=0.0, ramp_duration=1.0)
    run(ctrl, mcu, 0.0, 1.5)
    speeds = [e[3] for e in mcu.log if e[1] == 0 and e[2] == "FAST"]
    assert all(b >= a for a, b in zip(speeds, speeds[1:])), "FAST ramp must increase monotonically"
    assert speeds[-1] == pytest.approx(units[0].fast_units(4.0), abs=1), "FAST ramp must end at the target speed"
    assert len(set(speeds)) > 5, "a 1 s ramp must pass through intermediate speeds"


def test_fast_to_slow_to_stop(ctrl):
    mcu = McuModel()
    ctrl.set_speed(0, 2.0, now=0.0)
    t = run(ctrl, mcu, 0.0, 1.0)
    ctrl.set_speed(0, 0.0119, now=t)
    t = run(ctrl, mcu, t, 2.0)
    assert mcu.dps(0) == pytest.approx(0.0119, rel=0.01), "after FAST, a slow rate must run as SLOW"
    ctrl.set_speed(0, 0.0, now=t)
    run(ctrl, mcu, t, 1.0)
    assert mcu.dps(0) == 0.0, "after SLOW, a zero rate must stop the axis"


# ---------------------------------------------------------------------------------------
# 7. Message budget
# ---------------------------------------------------------------------------------------

def test_message_rate_is_bounded(ctrl):
    mcu = McuModel()
    for axis, dps in enumerate((0.0073, -0.0031, 0.0025)):
        ctrl.set_speed(axis, dps, now=0.0, hold=True)
    run(ctrl, mcu, 0.0, 30.0)
    per_s = len(mcu.log) / 30.0
    limit = 3 * 2 / REVERSING_CYCLE_S          # two switches per reversing cycle per axis (legacy: 12/s)
    assert per_s <= limit, f"{per_s:.1f} SLOW messages/s exceeds {limit:.1f}/s for three modulating axes"


@pytest.mark.parametrize("target", [SLOW_DPS[(1, 1)], SLOW_DPS[(1, 2)]])
def test_steady_rung_rate_sends_one_message(ctrl, target):
    mcu = McuModel()
    ctrl.set_speed(0, target, now=0.0)
    run(ctrl, mcu, 0.0, 10.0)
    assert len(mcu.log) == 1, f"a rate exactly on a firmware speed should be one message, got {len(mcu.log)}"


def test_allow_pwm_false_uses_nearest_speed_without_modulation(ctrl):
    mcu = McuModel()
    ctrl.set_speed(0, 0.010, now=0.0, allow_pwm=False)
    run(ctrl, mcu, 0.0, 5.0)
    assert len(mcu.log) == 1 and mcu.dps(0) == pytest.approx(SLOW_DPS[(1, 2)]), (
        "allow_PWM=False must pick the nearest firmware speed and hold it")


# ---------------------------------------------------------------------------------------
# Runtime and hot swap
# ---------------------------------------------------------------------------------------

def test_runtime_sends_messages_and_stops_cleanly(units):
    sent = []

    async def send(msg):
        sent.append(msg)

    async def scenario():
        rt = SpeedControllerRuntime(units, send)
        await rt.axis(0).set_motor_speed(0.0119, "DPS")
        await asyncio.sleep(0.3)
        await rt.axis(0).set_motor_speed(0, "DPS")
        await asyncio.sleep(0.1)
        await rt.stop()
        return rt

    rt = asyncio.run(scenario())
    assert sent[0] == "1&532&3&key:0;state:2;level:1;#", f"first message was {sent[0]!r}"
    assert sent[-1].startswith("1&532&3&key:0;state:0;"), f"last message was {sent[-1]!r}, expected a stop"
    assert rt.axis(0).get_cmdstr().strip() == "IDLE"


class FakeMotor:
    def __init__(self, name):
        self.name, self.calls, self.rate_dps, self.rate_raw = name, [], 0.0, 0.0

    async def set_motor_speed(self, rate, rate_unit="DPS", **kw):
        self.calls.append((rate, rate_unit))

    def get_cmdstr(self):
        return self.name

    def to_dps(self, rate, units):
        return rate * (2 if self.name == "new" else 1)

    async def stop_disspatch_loop_task(self):
        self.calls.append("stopped")


def test_switchable_motor_routes_and_swaps():
    old, new = FakeMotor("old"), FakeMotor("new")
    m = SwitchableMotor(old, new, use_new=False)

    async def scenario():
        await m.set_motor_speed(0.01, "DPS")
        assert m.get_cmdstr() == "old" and m.to_dps(1, "RAW") == 1
        await m.select(use_new=True)
        await m.set_motor_speed(0.02, "DPS")
        await m.stop_disspatch_loop_task()

    asyncio.run(scenario())
    assert old.calls[:2] == [(0.01, "DPS"), (0, "DPS")], "swap must first stop the outgoing controller"
    assert (0.02, "DPS") in new.calls and (0.02, "DPS") not in old.calls, "after swap, commands go to the new controller"
    assert m.get_cmdstr() == "new" and m.to_dps(1, "RAW") == 2
    assert "stopped" in old.calls and "stopped" in new.calls, "shutdown must stop both controllers"


DRIVER_INTERFACE = ("set_motor_speed", "rate_dps", "rate_raw", "get_cmdstr", "to_dps", "max_dps",
                    "stop_disspatch_loop_task")


@pytest.mark.parametrize("use_new", [False, True], ids=["legacy", "v2"])
def test_switchable_motor_provides_the_driver_interface(use_new):
    """Everything polaris.py / PID_Controller / telescope.py use on self._motors[axis]."""
    import logging
    from control import MotorSpeedController
    cm = CalibrationManager(liveInstance=False)
    cm.createTestDataFromBaseline()
    cm.generateCalibrationFromBaselineAndTestData()
    cm.generateInterpolatorsFromCalibrationData()
    sent = []

    async def send(msg):
        sent.append(msg)

    async def scenario():
        rt = SpeedControllerRuntime({a: RateUnits(cm.baseline_data[a]) for a in range(3)}, send)
        m = SwitchableMotor(MotorSpeedController(logging.getLogger("t"), cm, 0, send), rt.axis(0), use_new=use_new)
        missing = [name for name in DRIVER_INTERFACE if not hasattr(m, name)]
        assert not missing, f"SwitchableMotor is missing driver interface members {missing}"
        await m.set_motor_speed(3, "RAW", ramp_duration=0.2, allow_PWM=True, tracking=False)
        await asyncio.sleep(0.2)
        assert m.rate_dps == pytest.approx(m.to_dps(3, "RAW"), rel=0.05), "rate_dps must follow the command"
        assert m.max_dps == pytest.approx(8.9185931, rel=1e-3), "max_dps must be the fastest FAST speed"
        assert isinstance(m.get_cmdstr(), str) and isinstance(m.rate_raw, float | np.floating)
        await m.set_motor_speed(0, "DPS")
        await asyncio.sleep(0.2)
        await m.stop_disspatch_loop_task()

    asyncio.run(scenario())
    assert any("&532&" in msg for msg in sent), "no SLOW message was sent for a RAW 3 command"
