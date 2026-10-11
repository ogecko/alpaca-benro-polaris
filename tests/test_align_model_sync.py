"""
The alignment model in the SyncManager (docs/study_alignment_mac_v2.md): with advanced_align_mac on (the
Mechanical Alignment Correction switch, reused for the new model), each refit
fits QUEST's rotation together with the M2/M3 zero offsets (d2, d3), with the M2 scale from config
(align_m2_scale, %), and the forward path corrects the motor angles the same way. Off is the previous rotation-only
QUEST (A/B).
"""
import logging
import math
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

from control import SyncManager
from kinematics import theta_to_q, azalt_to_vector
from align_model import corrected_theta, boresights
from quaternion import Q as Quaternion
from test_sync_manager import Polaris, mock_config          # noqa: F401  (fixture)

POSES = [(105, 50, 45), (135, 35, 65), (155, 69, 1), (225, 52, -65), (252, 62, -44), (180, 33, -2)]
Q_TRUE = Quaternion(axis=[0.3, -0.2, 1.0], degrees=4.3)
D2, D3, S2 = 50 / 60, -53 / 60, 0.01


@pytest.fixture
def cfg(mock_config):
    mock_config.advanced_align_mac = True
    mock_config.align_m2_scale = S2 * 100
    mock_config.advanced_scc_enabled = False
    return mock_config


def vec_to_azalt(v):
    return math.degrees(math.atan2(v[0], v[1])) % 360, math.degrees(math.asin(max(-1.0, min(1.0, v[2]))))


def true_direction(theta):
    """Where the camera really points for raw motor angles theta: the corrected angles, turned by Q_TRUE."""
    return Q_TRUE.rotate(boresights(corrected_theta(np.atleast_2d(theta), D2, D3, S2))[0])


def sync_all(sm, p, poses=POSES):
    for az, alt, roll in poses:
        p.update(az, alt, roll)
        a_az, a_alt = vec_to_azalt(true_direction(p._theta_raw))
        sm.process_quest_sync(0.0, -40.0, a_az, a_alt)


def residuals_arcmin(sm):
    return np.array([e['residual_magnitude'] * 60 for e in sm.sync_history if not e['deleted'] and e.get('a_az') is not None])


def sep_arcmin(a, b):
    return math.degrees(math.atan2(np.linalg.norm(np.cross(a, b)), np.dot(a, b))) * 60


def test_the_refit_finds_the_offsets_and_leaves_no_residual(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    assert sm.align_d2 == pytest.approx(D2, abs=1e-4) and sm.align_d3 == pytest.approx(D3, abs=1e-4)
    assert residuals_arcmin(sm).max() < 0.1


def test_rotation_only_quest_is_the_ab_comparison(cfg):
    cfg.advanced_align_mac = False
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    assert sm.align_d2 == 0 and sm.align_d3 == 0
    assert residuals_arcmin(sm).max() > 20                    # the offsets the rotation can't absorb


def test_the_live_pose_is_corrected_with_the_model(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    theta = np.array([200.0, 41.0, -25.0])                     # a pose away from the sync points
    cam, _ = sm.baseQ_to_topoQ(theta_to_q(*theta), theta=theta)
    assert sep_arcmin(cam.rotate([0, 0, -1]), true_direction(theta)) < 0.1


def test_a_refit_updates_the_current_pose_without_motor_angles(cfg):
    """refresh_pid_setpoints_from_q1 and the guide paths call the forward path without motor angles: the current
    pose's correction must follow a refit, not keep the model from before it."""
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    p.update(200, 41, -25)
    sm.baseQ_to_topoQ(p._q1, theta=np.asarray(p._theta_raw))   # a control tick at the current pose
    sync_all(sm, p, POSES)
    p.update(200, 41, -25)
    sm.baseQ_to_topoQ(p._q1, theta=np.asarray(p._theta_raw))
    cam, _ = sm.baseQ_to_topoQ(p._q1)
    assert sep_arcmin(cam.rotate([0, 0, -1]), true_direction(p._theta_raw)) < 0.1


def test_with_fewer_than_three_points_the_offsets_are_held(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p, POSES[:2])
    assert sm.align_d2 == 0 and sm.align_d3 == 0
    sync_all(sm, p, POSES[2:])
    assert sm.align_d2 == pytest.approx(D2, abs=1e-4)


def test_a_reset_clears_the_offsets_and_the_correction(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    sm.set_alignQ_to_identity()
    assert sm.align_d2 == 0 and sm.align_d3 == 0 and sm.corrQ_MODEL.degrees == 0


def test_switching_the_model_off_drops_the_offsets(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    cfg.advanced_align_mac = False
    sm.optimize_alignQ_B2T()
    theta = np.array([200.0, 41.0, -25.0])
    cam, mpv = sm.baseQ_to_topoQ(theta_to_q(*theta), theta=theta)
    assert sm.align_d2 == 0 and sm.align_d3 == 0 and sm.corrQ_MODEL.degrees == 0


def test_the_m2_scale_comes_from_config(cfg):
    cfg.align_m2_scale = 0.0                                    # the model without the scale
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    assert residuals_arcmin(sm).max() > 0.5                    # the data has a 1% scale the model now lacks
    cfg.align_m2_scale = S2 * 100
    sm.optimize_alignQ_B2T()
    assert residuals_arcmin(sm).max() < 0.1


def test_the_model_logs_its_terms(cfg, caplog):
    cfg.log_quest_model = True
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    with caplog.at_level(logging.INFO, logger='test'):
        sync_all(sm, p)
    line = next(r.getMessage() for r in reversed(caplog.records) if 'Model:' in r.getMessage())
    assert "d2 +000d50'" in line and "d3 -000d53'" in line and 'M2 scale +1.00%' in line


# ── M2 scale calibration (Pilot's AutoTune, Polaris:AutotuneMAC) ──────────────────────────────

def test_calibration_fits_the_m2_scale_from_the_current_points(cfg):
    cfg.align_m2_scale = 0.0                                    # not yet calibrated
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    r = sm.calibrate_m2_scale()
    assert r['success'] and r['n_points'] == 6
    assert r['m2_scale'] == pytest.approx(S2 * 100, abs=0.05)           # %
    assert r['rms_after'] < 0.1 < r['rms_before'] and r['rms_improv'] > 90
    assert cfg.align_m2_scale == 0.0                                    # reported, not applied: Pilot's Apply saves it


def test_calibration_needs_enough_well_spread_points(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p, POSES[:3])
    r = sm.calibrate_m2_scale()
    assert not r['success'] and 'points' in r['message']


def test_another_pose_uses_its_own_correction_not_the_current_poses(cfg):
    """polaris.theta_to_alpha converts motor angles that aren't the current pose: model_theta gives their own
    correction, without changing the current pose's (used by callers without motor angles)."""
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    current = np.array([200.0, 41.0, -25.0])
    sm.baseQ_to_topoQ(theta_to_q(*current), theta=current)
    other = np.array([90.0, 65.0, 50.0])
    cam, _ = sm.baseQ_to_topoQ(theta_to_q(*other), model_theta=other)
    assert sep_arcmin(cam.rotate([0, 0, -1]), true_direction(other)) < 0.1
    cam, _ = sm.baseQ_to_topoQ(theta_to_q(*current))
    assert sep_arcmin(cam.rotate([0, 0, -1]), true_direction(current)) < 0.1
