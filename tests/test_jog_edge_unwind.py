"""
Jogs past the M2 range and UNWIND (field 2026-10-29 13:58, and 2026-10-28 20:42-20:43): an Alt jog to -8 put the
jog reference on the other IK branch; the FLIP that followed was read by UNWIND as a -181 deg M1 change past z1's
limit, and UNWIND sent M1 to theta +637 (zeta +457), a 540 deg run-away twist.

  * a jog whose reference would change IK branch stops at the edge, holding there: no FLIP, no M1/M3 swing
  * UNWIND does not turn M1 on its own while the mount holds (idle, after an abort, during a jog)
  * a goto that needs it still unwinds, to the turn within both motor limits
"""
import logging
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

from config import Config                                               # noqa: E402
from control_eq import THETA2_MIN                                       # noqa: E402
from sim_digital_twin import Twin                                       # noqa: E402

FIELD = {"coordinated_speed_control": True, "advanced_backlash": True}  # nina01


@pytest.fixture
def messages():
    out = []

    class H(logging.Handler):
        def emit(self, r):
            out.append(r.getMessage())
    lg = logging.getLogger('twin')
    h = H()
    lg.addHandler(h)
    lg.setLevel(logging.INFO)
    yield out
    lg.removeHandler(h)


def _zeta(tw):
    return np.array(tw.polaris._zeta_meas, dtype=float)


@pytest.mark.parametrize("coordinated", [True, False])
def test_alt_jog_below_the_m2_range_stops_without_a_flip(monkeypatch, messages, coordinated):
    tw = Twin(monkeypatch, config={**FIELD, "coordinated_speed_control": coordinated}, calibrated=coordinated)
    try:
        tw.place([98.2, 5.5, 10.9])                       # the field: Az ~112 Alt 5, M1 at zeta -82
        tw.goto_altaz(98.0, 2.15, -1.35)
        tw.run(15)
        z0 = _zeta(tw)
        path = []
        tw.pid.set_axis_velocities({'alt': -0.345})       # down past the horizon, as the field's jogs did
        tw.run(40, on_measure=lambda t: path.append(np.array(t.theta)))
        tw.pid.set_axis_velocities({'az': 0.345})         # then Az, when the field's UNWIND fired
        tw.run(1.2, on_measure=lambda t: path.append(np.array(t.theta)))
        tw.pid.set_axis_velocities({'az': 0.0, 'alt': 0.0})
        tw.run(20, on_measure=lambda t: path.append(np.array(t.theta)))
        path = np.array(path)
        assert any('JOG stopped' in m for m in messages)
        assert not any('FLIP' in m or 'UNWIND' in m for m in messages)
        # M1/M3 never swung round (field: 300+ deg); through gimbal lock (M2 0) they counter-rotate up to ~50 deg,
        # which leaves the cable twist (M1 + M3) as it was
        assert np.max(np.abs(path[:, 0] - (z0[0] + 180))) < 90
        assert np.max(np.abs(path[:, 0] + path[:, 2] - (z0[0] + 180 + z0[2]))) < 15
        assert path[-1, 1] > THETA2_MIN - 1.0                       # M2 held at its edge
    finally:
        tw.close()


def test_no_unwind_while_holding_near_the_m1_limit(monkeypatch, messages):
    tw = Twin(monkeypatch, config=FIELD, calibrated=True)
    try:
        z1 = Config.z1_min_limit + Config.zeta_safety_margin / 2     # inside the limit, past its safety margin
        tw.place([z1 + 180.0, 30.0, 0.0])
        tw.run(30)
        assert not any('UNWIND' in m for m in messages)
        assert abs(_zeta(tw)[0] - z1) < 1.0
    finally:
        tw.close()


@pytest.mark.parametrize("coordinated", [True, False])
def test_a_goto_past_the_m1_limit_unwinds_within_the_limits(monkeypatch, coordinated):
    tw = Twin(monkeypatch, config={**FIELD, "coordinated_speed_control": coordinated}, calibrated=coordinated)
    try:
        tw.place([-70.0, 30.0, 0.0])                      # zeta1 -250, 10 deg inside the safety margin
        tw.goto_altaz(260.0, 30.0, 0.0)                   # 30 deg further on M1 the short way: past the limit
        tw.run(120)
        z = _zeta(tw)
        assert Config.z1_min_limit <= z[0] <= Config.z1_max_limit
        assert abs(z[0] - 80.0) < 1.0                     # the same pointing a turn round (theta +260)
        assert tw.pid.mode != 'LIMIT'
    finally:
        tw.close()
