"""
Hardware test: each motor's measured velocity matches the commanded rate (Polaris:MoveMotor, DPS).

Covers the tracking band (sidereal .. 0.012 deg/s, all level 1), the level 2-4 SLOW range and one
FAST rate. Runs only against a live driver whose Polaris is connected and idle; otherwise the whole
module is skipped. All motors are stopped after each test. Takes ~4 minutes.
"""
import time

import pytest

from polaris_hw import MOTOR_NAMES, direction, idle_reason, measure_velocity, move_motor, speed_controller, stop_all

SIDEREAL_DPS = 360 / 86164.1
SLOW_RATES = [SIDEREAL_DPS, 0.008, 0.0119, 0.02, 0.05, 0.1]
SETTLE_S = 2.0
MEASURE_S = 8.0
REL_TOLERANCE = 0.05


@pytest.fixture(scope="module", autouse=True)
def polaris_idle():
    reason = idle_reason()
    if reason:
        pytest.skip(f"Hardware test skipped: {reason}")
    print(f"\nspeed controller under test: {speed_controller()}")
    yield
    stop_all()


@pytest.fixture(autouse=True)
def stopped_motors():
    stop_all()
    time.sleep(1.0)
    yield
    stop_all()


@pytest.mark.parametrize("axis", [0, 1, 2], ids=["M1", "M2", "M3"])
@pytest.mark.parametrize("rate", SLOW_RATES, ids=[f"{r:.4f}dps" for r in SLOW_RATES])
def test_slow_rate_accuracy(axis, rate):
    d = direction(axis)
    move_motor(axis, d * rate, "DPS")
    time.sleep(SETTLE_S)
    measured = d * measure_velocity(MEASURE_S)[axis]
    assert abs(measured - rate) <= REL_TOLERANCE * rate, (
        f"{MOTOR_NAMES[axis]} measured {measured:.5f} dps for a commanded {rate:.5f} dps "
        f"({(measured / rate - 1):+.1%}, tolerance ±{REL_TOLERANCE:.0%})")


@pytest.mark.parametrize("axis", [0, 2], ids=["M1", "M3"])
def test_fast_rate_runs_in_the_commanded_direction(axis):
    """FAST accuracy depends on battery and load (§5.4.7), so only direction and rough speed are checked."""
    move_motor(axis, 1.0, "DPS")
    time.sleep(1.5)
    measured = measure_velocity(2.0)[axis]
    assert 0.5 <= measured <= 1.5, f"{MOTOR_NAMES[axis]} measured {measured:.3f} dps for a commanded 1.0 dps FAST rate"
