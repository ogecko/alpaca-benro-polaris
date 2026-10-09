"""
The worm profile test keeps every motor's sweep where the motor can go, and ends when a position can't be reached.

2026-10-09 (roll ladder, 200 mm): the test started with M2 at 79.85 (motor frame), about 1.6 deg below where the
Alt/Roll envelope (reachable_azaltroll, THETA2_MAX 81.5) caps it. The sweep takes M2 +-7.2 deg, so position 35 asked
for more: the target was clamped, M2 held at its limit, the position never settled, and the plate-solves arriving
every ~23 s kept the test waiting (it only ends when solves stop). The user shouldn't have to check the motors' room
before a test: the driver fits the sweep inside what each motor can reach, and ends a test whose position never settles.
"""
import logging
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

import control_worm
from control import SyncManager
from control_worm import (POSITIONS, SYNC_CYCLE_S, REACH_MARGIN_DEG, SETTLE_TIMEOUT_S, WormProfileTest, fit_sweep)
from kinematics import q_to_azaltroll, reachable_azaltroll, theta_to_q
from test_sync_manager import Polaris, mock_config          # noqa: F401  (fixture)

TONIGHT_THETA = np.array([173.63441, 79.84956, 31.16695])    # theta_pv at position 34 (log 19:48:41)
TONIGHT_ZETA = np.array([353.64755, 34.89121, 31.26323])
DURATION_S = len(POSITIONS) * SYNC_CYCLE_S


# ── fit_sweep ──────────────────────────────────────────────────────────────────────────────────

class TestFitSweep:

    def test_room_for_the_whole_sweep_leaves_it_alone(self):
        p, scale = fit_sweep(POSITIONS, np.full(3, -20.0), np.full(3, 20.0))
        assert np.array_equal(p, POSITIONS) and np.all(scale == 1)

    def test_a_low_ceiling_moves_the_sweep_down_keeping_its_shape(self):
        lo, hi = np.full(3, -20.0), np.array([20.0, 1.5, 20.0])
        p, scale = fit_sweep(POSITIONS, lo, hi)
        assert p[:, 1].max() == pytest.approx(hi[1] - REACH_MARGIN_DEG)
        assert np.allclose(np.diff(p[:, 1]), np.diff(POSITIONS[:, 1]))      # same steps: the same worm phases visited
        assert np.array_equal(p[:, [0, 2]], POSITIONS[:, [0, 2]]) and scale[1] == 1

    def test_a_high_floor_moves_the_sweep_up(self):
        lo, hi = np.array([-20.0, -20.0, -2.0]), np.full(3, 20.0)
        p, _ = fit_sweep(POSITIONS, lo, hi)
        assert p[:, 2].min() == pytest.approx(lo[2] + REACH_MARGIN_DEG)

    def test_a_range_narrower_than_the_sweep_shrinks_it_onto_the_range(self):
        lo, hi = np.full(3, -20.0), np.array([20.0, 20.0, 20.0])
        lo[0], hi[0] = -3.0, 3.0
        p, scale = fit_sweep(POSITIONS, lo, hi)
        assert p[:, 0].min() == pytest.approx(lo[0] + REACH_MARGIN_DEG)
        assert p[:, 0].max() == pytest.approx(hi[0] - REACH_MARGIN_DEG)
        assert 0 < scale[0] < 1

    def test_no_room_holds_the_motor_still(self):
        lo, hi = np.full(3, -20.0), np.full(3, 20.0)
        lo[1], hi[1] = -0.2, 0.2
        p, scale = fit_sweep(POSITIONS, lo, hi)
        assert np.ptp(p[:, 1]) == 0 and lo[1] <= p[0, 1] <= hi[1] and scale[1] == 0


# ── the settle timeout ────────────────────────────────────────────────────────────────────────

class TestSettleTimeout:

    def test_a_step_that_never_settles_is_overdue(self):
        t = WormProfileTest(now=0.0)
        t.step_at = 100.0
        assert not t.settle_overdue(100.0 + SETTLE_TIMEOUT_S - 1)
        assert t.settle_overdue(100.0 + SETTLE_TIMEOUT_S + 1)

    def test_settled_and_waiting_for_a_solve_is_not_overdue(self):
        t = WormProfileTest(now=0.0)
        t.step_at = 100.0
        t.track_settle(0.0, now=101.0)
        t.track_settle(0.0, now=102.5)
        assert t.settled_at is not None and not t.settle_overdue(100.0 + 10 * SETTLE_TIMEOUT_S)

    def test_the_start_is_timed_from_when_the_test_began(self):
        t = WormProfileTest(now=50.0)
        assert not t.settle_overdue(50.0 + SETTLE_TIMEOUT_S - 1) and t.settle_overdue(50.0 + SETTLE_TIMEOUT_S + 1)


# ── the reach, on the real kinematics ─────────────────────────────────────────────────────────

def reachable_pose(sm, theta):
    az, alt, roll = q_to_azaltroll(sm.alignQ_B2T * theta_to_q(*theta))
    r = reachable_azaltroll(az, alt, roll)
    return abs(r[1] - alt) < 1e-3 and abs((r[2] - roll + 180) % 360 - 180) < 1e-3


@pytest.fixture
def sm(mock_config, monkeypatch):
    for k, v in dict(z1_min_limit=-270, z1_max_limit=270, z2_min_limit=-55, z2_max_limit=37,
                     z3_min_limit=-270, z3_max_limit=270, zeta_safety_margin=10).items():
        monkeypatch.setattr(control_worm.Config, k, v, raising=False)
    return SyncManager(logging.getLogger('test'), Polaris())


class TestReach:

    def test_tonight_m2_has_little_room_up_and_the_fitted_sweep_stays_reachable(self, sm):
        lo, hi = sm.worm_test_reach(TONIGHT_THETA, TONIGHT_ZETA, np.zeros(3), DURATION_S)
        assert 0.5 < hi[1] < 2.2                                 # ~1.6 deg to the envelope, ~2.1 to z2 max
        p, _ = fit_sweep(POSITIONS, lo, hi)
        for off in p:
            assert reachable_pose(sm, TONIGHT_THETA + off), f"offset {off} unreachable"

    def test_the_standard_sweep_reproduces_tonight_s_stall(self, sm):
        """Without the fit, some positions are outside the envelope (the one the test stuck on among them)."""
        bad = [i for i, off in enumerate(POSITIONS) if not reachable_pose(sm, TONIGHT_THETA + off)]
        assert bad and 35 in bad

    def test_a_comfortable_pose_keeps_the_full_sweep(self, sm):
        theta = np.array([180.0, 45.0, 10.0])
        lo, hi = sm.worm_test_reach(theta, np.array([0.0, 0.0, 10.0]), np.zeros(3), DURATION_S)
        p, scale = fit_sweep(POSITIONS, lo, hi)
        assert np.array_equal(p, POSITIONS) and np.all(scale == 1)

    def test_the_motor_limits_count_with_the_unwind_margin_for_m1_m3(self, sm):
        theta = np.array([180.0, 45.0, 10.0])
        zeta = np.array([258.0, 0.0, 0.0])                       # M1 2 deg inside its unwind margin (270 - 10)
        lo, hi = sm.worm_test_reach(theta, zeta, np.zeros(3), DURATION_S)
        assert hi[0] == pytest.approx(2.0)

    def test_tracking_travel_during_the_test_is_kept_clear(self, sm):
        theta = np.array([180.0, 45.0, 10.0])
        zeta = np.array([0.0, 30.0, 0.0])                        # M2 7 deg below z2 max ...
        still, _ = sm.worm_test_reach(theta, zeta, np.zeros(3), DURATION_S)[1], None
        rising = sm.worm_test_reach(theta, zeta, np.array([0.0, 2.0 / DURATION_S, 0.0]), DURATION_S)[1]
        assert rising[1] == pytest.approx(still[1] - 2.0)         # ... and it rises 2 deg while the test runs
