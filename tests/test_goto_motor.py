"""
Goto raw motor angles (Polaris:SlewAbsolute / SlewRelative m1/m2/m3 -> Polaris.slew_axis -> PID_Controller.
set_theta_target): m1/m2/m3 are zeta (the 517 angles StatusMotors shows), and each motor is driven straight to its
angle, so M1 goes the long way round when that is where the zeta is (an Az/Alt goto takes the short way). It ends
held at the pose -- or, while tracking, tracking from there.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

from sim_digital_twin import Twin                                       # noqa: E402

ZETA_TOL_DEG = 0.1
TWIN_ZETA_THETA = np.array([180.0, 45.0, 0.0])      # the twin: theta = zeta + (180, 45, 0), no alignment


def _zeta(tw):
    return np.array(tw.polaris._zeta_meas, dtype=float)


def _slew_motor(tw, zeta_goal):
    """What Polaris.slew_axis does for m1/m2/m3 (absolute)."""
    done = []
    tw.polaris._tracking = tw.pid.mode == 'TRACK'
    tw.pid.set_goto_complete_callback(lambda: done.append(tw.clock.monotonic()))
    tw.pid.set_theta_target(np.asarray(zeta_goal, dtype=float) + TWIN_ZETA_THETA)
    return done


@pytest.mark.parametrize("coordinated", [True, False])
@pytest.mark.parametrize("start, goal", [
    ([200.0, 60.0, 10.0], [-60.0, -10.0, 40.0]),     # an ordinary move on all three motors
    ([330.0, 60.0, 0.0], [-150.0, 15.0, 0.0]),       # M1 +150 -> -150: 300 deg back, not 60 on over the top
])
def test_motor_angle_goto_reaches_the_zeta(monkeypatch, coordinated, start, goal):
    tw = Twin(monkeypatch, config={"coordinated_speed_control": coordinated}, calibrated=coordinated)
    try:
        tw.place(start)
        z0 = _zeta(tw)
        done = _slew_motor(tw, goal)
        path = []
        tw.run(90.0, on_measure=lambda t: path.append(_zeta(t)[0]))
        assert done, "the goto never completed"
        assert np.max(np.abs(_zeta(tw) - goal)) < ZETA_TOL_DEG
        # M1 went straight there: never outside the start..goal range (no turn the other way)
        lo, hi = sorted([z0[0], goal[0]])
        assert min(path) > lo - 5.0 and max(path) < hi + 5.0
    finally:
        tw.close()


def test_motor_angle_goto_while_tracking_tracks_from_there(monkeypatch):
    tw = Twin(monkeypatch, config={"coordinated_speed_control": True}, calibrated=True)
    try:
        tw.place([200.0, 50.0, 0.0])
        tw.start_tracking()
        tw.run(5.0)
        goal = [-100.0, 10.0, 20.0]
        done = _slew_motor(tw, goal)
        tw.run(90.0)
        assert done, "the goto never completed"
        assert tw.pid.mode == 'TRACK'
        z_arrived = _zeta(tw)
        assert abs(z_arrived[0] - goal[0]) < 1.0         # the same turn of M1 (the sky moves on while it settles)
        ra0, dec0 = tw.true_radec()
        tw.run(60.0)
        ra1, dec1 = tw.true_radec()
        assert abs(dec1 - dec0) * 3600 < 30 and abs(ra1 - ra0) * 15 * 3600 < 30    # tracking holds the sky position
    finally:
        tw.close()
