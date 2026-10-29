"""
Mechanical Alignment Correction (MAC) in the SyncManager (docs/study_alignment_mac_v2.md): with advanced_align_mac on,
each refit
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
from kinematics_mac import corrected_theta, boresights
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
    assert sm.mac_d2 == pytest.approx(D2, abs=1e-4) and sm.mac_d3 == pytest.approx(D3, abs=1e-4)
    assert residuals_arcmin(sm).max() < 0.1


def test_rotation_only_quest_is_the_ab_comparison(cfg):
    cfg.advanced_align_mac = False
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    assert sm.mac_d2 == 0 and sm.mac_d3 == 0
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
    assert sm.mac_d2 == 0 and sm.mac_d3 == 0
    sync_all(sm, p, POSES[2:])
    assert sm.mac_d2 == pytest.approx(D2, abs=1e-4)


def test_a_reset_clears_the_offsets_and_the_correction(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    sm.set_alignQ_to_identity()
    assert sm.mac_d2 == 0 and sm.mac_d3 == 0 and sm.corrQ_MAC.degrees == 0


def test_switching_the_model_off_drops_the_offsets(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    cfg.advanced_align_mac = False
    sm.optimize_alignQ_B2T()
    theta = np.array([200.0, 41.0, -25.0])
    cam, mpv = sm.baseQ_to_topoQ(theta_to_q(*theta), theta=theta)
    assert sm.mac_d2 == 0 and sm.mac_d3 == 0 and sm.corrQ_MAC.degrees == 0


@pytest.mark.parametrize('switch', ['advanced_alignment', 'advanced_control'])
def test_single_point_alignment_applies_no_mac_not_even_the_m2_scale(cfg, switch):
    """MAC is part of Multi-Point Alignment: in Single-Point Alignment the Polaris' own model points, and the M2 scale
    (from config, not the fit) would otherwise still bend it -- up to ~12' at 0.8%."""
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    setattr(cfg, switch, False)
    sm.optimize_alignQ_B2T()
    theta = np.array([200.0, 20.0, -25.0])
    sm.baseQ_to_topoQ(theta_to_q(*theta), theta=theta)
    assert sm.mac_terms() == (0.0, 0.0, 0.0)
    assert sm.corrQ_MAC.degrees == 0


def test_the_m2_scale_starts_from_config_until_a_fit_is_significantly_better(cfg):
    cfg.align_m2_scale = 0.0                                    # the default: no scale
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p, POSES[:5])                                  # 5 points: too few to refit the scale
    assert sm.mac_s2 is None and sm.m2_scale() == 0.0 and sm.mac_s2_status == 'default'
    sync_all(sm, p, POSES[5:])                                  # the 6th: the data's +1% is significantly better
    assert sm.mac_s2 == pytest.approx(S2, abs=5e-4) and sm.mac_s2_status == 'fitted'
    assert residuals_arcmin(sm).max() < 0.1
    sm.optimize_alignQ_B2T()                                    # refitted again: the same scale, now held
    assert sm.mac_s2_status == 'held' and sm.m2_scale() == pytest.approx(S2, abs=5e-4)


def test_the_model_logs_its_terms(cfg, caplog):
    cfg.log_quest_model = True
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    with caplog.at_level(logging.INFO, logger='test'):
        sync_all(sm, p)
    line = next(r.getMessage() for r in reversed(caplog.records) if 'MAC: ON' in r.getMessage())
    assert "d2 +000d50'" in line and "d3 -000d53'" in line and 'M2 scale +1.00%' in line


# ── the M2 scale refitted at each sync (no AutoTune), statuses and guidance for Pilot ─────────────────────────

def test_a_scale_that_isnt_significantly_better_is_not_taken(cfg):
    """The data has exactly the configured scale: freeing it can't do significantly better, so it stays the default."""
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    assert sm.mac_s2 is None and sm.mac_s2_status == 'default' and sm.m2_scale() == pytest.approx(S2)


def test_single_point_alignment_resets_the_scale_to_its_default(cfg):
    cfg.align_m2_scale = 0.0
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    assert sm.mac_s2 is not None
    cfg.advanced_alignment = False
    sm.optimize_alignQ_B2T()
    assert sm.mac_s2 is None and sm.mac_s2_status == 'default'


def test_the_taken_scale_is_kept_with_the_alignment(cfg, tmp_path):
    cfg.align_m2_scale = 0.0
    cfg.apply_changes = lambda changes: changes                 # (loading sets advanced_alignment through Config)
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    path = tmp_path / 'sync_points.json'
    sm.saveSyncDataToFile(path)
    sm2 = SyncManager(logging.getLogger('test'), Polaris())
    assert sm2.loadSyncDataFromFile(path)
    assert sm2.mac_s2 == pytest.approx(sm.mac_s2) and sm2.mac_s2_status == 'held'


@pytest.mark.parametrize('n, expected', [
    (2, "Add 3 or more plate-solve syncs spread across the sky."),
    (3, "Add additional sync points to improve mechanical alignment."),
    (5, "Add additional sync points to improve mechanical alignment."),
    (6, "Good alignment. Add more sync points to refine it further (up to 20)."),
])
def test_guidance_follows_the_points(cfg, n, expected):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p, POSES[:n])
    assert sm.align_guidance == expected
    assert sm.mac_offsets_status == ('fitted' if n >= 3 else 'default')


def test_guidance_asks_for_more_altitude_spread(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    bunched = [(az, alt, 0) for az, alt in ((100, 40), (140, 42), (180, 44), (220, 41), (260, 43), (300, 45))]
    sync_all(sm, p, bunched)
    g = sm.align_guidance
    assert g.startswith("Add sync points above ") and g.endswith("\N{DEGREE SIGN} altitude."), g
    above = int(g.split()[4].rstrip("\N{DEGREE SIGN}"))
    assert 60 <= above <= 66, g                                 # M2 40-45 deg at roll 0: 20 deg above the lowest


def test_with_mac_up_to_20_points_are_kept_dropping_the_oldest_but_never_the_m2_extremes(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    poses = [(10 + 17 * i, 30 + (i * 37) % 45, 0) for i in range(22)]       # spread, none within 1.5 deg
    sync_all(sm, p, poses)
    active = [e for e in sm.sync_history if not e['deleted']]
    assert len(active) == 20
    m2 = [float(sm.entry_theta(e)[1]) for e in active]
    all_m2 = [float(q_to_theta_pose(*pp)[1]) for pp in poses]
    assert min(m2) == pytest.approx(min(all_m2), abs=0.01) and max(m2) == pytest.approx(max(all_m2), abs=0.01)


def q_to_theta_pose(az, alt, roll):
    from kinematics import azaltroll_to_theta_ik
    return azaltroll_to_theta_ik(az, alt, roll)


def test_when_the_points_cant_fix_the_offsets_the_weighted_quest_rotation_is_kept(cfg):
    """Points bunched together (or along one roll and altitude) can't separate the offsets from the rotation: the
    alignment is then the existing weighted QUEST, whose proximity weighting fits best locally (A/B: greg 08-02)."""
    bunched = [(150, 45, 10), (154, 46, 10), (150, 50, 11), (146, 43, 9)]      # > 1.5 deg apart: all four kept
    cfg.align_m2_scale = 0.0                                    # the held model is then the identity: on == off
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p, bunched)
    q_on = sm.alignQ_B2T
    assert sm.aligned_count == 4 and sm.mac_d2 == 0 and sm.mac_d3 == 0
    cfg.advanced_align_mac = False
    sm.optimize_alignQ_B2T()
    assert abs(abs(float(np.dot(q_on.q, sm.alignQ_B2T.q))) - 1.0) < 1e-12


# ── roll sync (roll_adj) with MAC ─────────────────────────────────────────────────────────────
from kinematics import q_to_azaltroll, angular_difference          # noqa: E402

CAMERA_ROLL = 7.0                                                   # the camera turned in its clamp: a roll sync's job


def true_roll(theta):
    """The camera's true sky roll for raw motor angles, plus the camera's own turn in its clamp."""
    q = Q_TRUE * theta_to_q(*corrected_theta(np.asarray(theta, float), D2, D3, S2))
    return q_to_azaltroll(q)[2] + CAMERA_ROLL


def reported_roll(sm, theta):
    cam, _ = sm.baseQ_to_topoQ(theta_to_q(*theta), theta=np.asarray(theta, float))
    return q_to_azaltroll(cam)[2]


def test_a_roll_sync_after_a_mac_alignment_makes_the_reported_roll_true(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    p.update(200, 41, -25)
    sm.baseQ_to_topoQ(p._q1, theta=np.asarray(p._theta_raw))
    sm.sync_roll(true_roll(p._theta_raw))
    for th in ([200.0, 41.0, -25.0], [120.0, 55.0, 40.0], [250.0, 35.0, -60.0]):
        assert abs(angular_difference(reported_roll(sm, th), true_roll(th))) < 0.01


def test_roll_adj_follows_a_later_mac_refit(cfg):
    """A roll sync's prediction is rebuilt from its raw motor angles with the current MAC and QUEST rotation: an
    alignment sync after it (which refits the M2/M3 offsets) must not leave roll_adj on the old ones."""
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p, POSES[:2])                                     # 2 points: offsets held at 0
    assert sm.mac_d2 == 0 and sm.mac_d3 == 0
    p.update(200, 41, -25)
    sm.baseQ_to_topoQ(p._q1, theta=np.asarray(p._theta_raw))
    sm.sync_roll(true_roll(p._theta_raw))
    sync_all(sm, p, POSES[2:])                                     # refit with all six: the offsets change
    assert sm.mac_d2 == pytest.approx(D2, abs=1e-4)
    for th in ([200.0, 41.0, -25.0], [120.0, 55.0, 40.0]):
        assert abs(angular_difference(reported_roll(sm, th), true_roll(th))) < 0.01


def test_with_roll_adj_the_pointing_is_unchanged_and_the_inverse_round_trips(cfg):
    p = Polaris(); sm = SyncManager(logging.getLogger('test'), p)
    sync_all(sm, p)
    theta = np.array([200.0, 41.0, -25.0])
    cam0, _ = sm.baseQ_to_topoQ(theta_to_q(*theta), theta=theta)
    sm.roll_adj = 12.0
    cam, mpv = sm.baseQ_to_topoQ(theta_to_q(*theta), theta=theta)
    assert sep_arcmin(cam.rotate([0, 0, -1]), cam0.rotate([0, 0, -1])) < 1e-6          # turns about the boresight
    assert angular_difference(q_to_azaltroll(cam)[2], q_to_azaltroll(cam0)[2]) == pytest.approx(-12.0, abs=1e-6) \
        or angular_difference(q_to_azaltroll(cam)[2], q_to_azaltroll(cam0)[2]) == pytest.approx(12.0, abs=1e-6)
    back = sm.topoQ_to_baseQ(cam)                                   # the PID's corrected motor pose
    assert abs(abs(float(np.dot(back.q, mpv.q))) - 1.0) < 1e-12
