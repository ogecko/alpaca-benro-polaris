"""
Hardware test: slow-jog (532/533/534) speed of each motor is independent of the others.

For each ordered pair (running motor A, disturbing motor B): run A alone at RAW 0.8
(SLOW_PWM, dithers -1<->+1), measure its speed, start B at RAW 2.5 (SLOW_PWM, dithers
+2<->+3), and check A's speed is unchanged. Motors are driven with Polaris:MoveMotor
and velocity is a linear fit of `traw` polled from Polaris:StatusFetch.

Runs only against a live driver whose Polaris is connected and idle (tracking off,
PID idle, not slewing); otherwise the whole module is skipped. All motors are stopped
after each test. Takes ~6 minutes.

Driver address: POLARIS_HOST / POLARIS_PORT env vars (default localhost:5555); see tests/polaris_hw.py.
"""
import time

import pytest

from polaris_hw import MOTOR_NAMES, direction, idle_reason, measure_velocity, move_motor, speed_controller, stop_all

RATE_A = 0.8            # RAW rate of the running motor
RATE_B = 2.5            # RAW rate of the disturbing motor
SETTLE_S = 3.0          # wait after a speed change before measuring
MEASURE_S = 24.0        # measurement window: long enough to average out modulation ripple at levels 2-3
MIN_SPEED_DPS = 0.002   # below this the motor is considered not moving
REL_TOLERANCE = 0.20    # allowed change in A's speed when B starts


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
    time.sleep(SETTLE_S)
    yield
    stop_all()


PAIRS = [(a, b) for a in range(3) for b in range(3) if a != b]


@pytest.mark.parametrize("a,b", PAIRS, ids=[f"M{b+1}_disturbs_M{a+1}" for a, b in PAIRS])
def test_motor_speed_unaffected_by_other_motor(a, b):
    na, nb = MOTOR_NAMES[a], MOTOR_NAMES[b]

    move_motor(a, RATE_A * direction(a))
    time.sleep(SETTLE_S)
    before = abs(measure_velocity(MEASURE_S)[a])
    assert before > MIN_SPEED_DPS, (
        f"Test setup failed: {na} did not move at RAW {RATE_A} on its own "
        f"(measured {before:.5f} dps)")

    move_motor(b, RATE_B * direction(b))
    time.sleep(SETTLE_S)
    v = measure_velocity(MEASURE_S)
    after, b_speed = abs(v[a]), abs(v[b])
    assert b_speed > MIN_SPEED_DPS, (
        f"Test setup failed: {nb} did not move at RAW {RATE_B} (measured {b_speed:.5f} dps)")

    ratio = after / before
    assert abs(ratio - 1) <= REL_TOLERANCE, (
        f"Axes not independent: {na} speed changed from {before:.5f} to {after:.5f} dps "
        f"(x{ratio:.2f}) when {nb} started at RAW {RATE_B}; expected within "
        f"±{REL_TOLERANCE:.0%}. The slow-jog level appears to be shared between motors.")
