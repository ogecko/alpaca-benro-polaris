"""
Tests for driver/kinematics_mac.py: Mechanical Alignment Correction (MAC) fitted with QUEST's rotation -- M2/M3 zero offsets (d2, d3) per
alignment and an M2 scale (s2, a mount constant), applied to the motor angles before the forward kinematics:
    theta' = theta + (0, d2 + s2 * (theta2 - 45), d3)
docs/study_alignment_mac_v2.md: on 1,300 archived sync points these take residuals from 36-95' to 2-8'.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest
from quaternion import Q as Quaternion

from kinematics_mac import corrected_theta, boresights, fit_alignment, M2_SCALE_REF_DEG
from kinematics import theta_to_q, q_to_theta, azaltroll_to_q

ARCMIN = 1 / 60.0

# the standard 6-point Multi-Point Alignment poses (az, alt, roll), and 4 more spread ones
POSES = [(105, 50, 45), (135, 35, 65), (155, 69, 1), (225, 52, -65), (252, 62, -44), (180, 33, -2),
         (60, 40, -50), (300, 55, 30), (20, 65, 10), (330, 30, -30)]


def thetas(poses):
    return np.array([np.asarray(q_to_theta(azaltroll_to_q(*p)), float) for p in poses])


def observe(theta_raw, q_true, d2, d3, s2, noise_arcmin=0.0, seed=0):
    """Plate-solved directions for raw motor angles: the true pose is the corrected angles, turned by q_true."""
    b = boresights(corrected_theta(theta_raw, d2, d3, s2))
    v = np.array([q_true.rotate(x) for x in b])
    if noise_arcmin:
        rng = np.random.default_rng(seed)
        v = v + rng.normal(0, np.radians(noise_arcmin / 60), v.shape)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


Q_TRUE = Quaternion(axis=[0.3, -0.2, 1.0], degrees=4.3)          # a tripod 4 deg off north, slightly tilted


def angle_deg(q1, q2):
    return np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(q1.q, q2.q))))))


# ── the model ────────────────────────────────────────────────────────────────────────────────

def test_boresights_are_the_drivers_forward_kinematics():
    rng = np.random.default_rng(1)
    th = np.column_stack([rng.uniform(0, 360, 50), rng.uniform(-8, 81, 50), rng.uniform(-170, 170, 50)])
    want = np.array([np.asarray(theta_to_q(*t).rotate([0, 0, -1]), float) for t in th])
    assert np.allclose(boresights(th), want, atol=1e-12)


def test_corrected_theta_adds_the_offsets_and_the_m2_scale_about_45_deg():
    th = np.array([[100.0, 45.0, -20.0], [200.0, 65.0, 30.0]])
    c = corrected_theta(th, d2=0.5, d3=-0.8, s2=0.01)
    assert np.allclose(c[:, 0], th[:, 0])                                      # M1 untouched
    assert np.allclose(c[:, 1], th[:, 1] + 0.5 + 0.01 * (th[:, 1] - M2_SCALE_REF_DEG))
    assert np.allclose(c[:, 2], th[:, 2] - 0.8)
    assert np.allclose(corrected_theta(th, 0.0, 0.0, 0.0), th)


# ── the fit ──────────────────────────────────────────────────────────────────────────────────

def test_recovers_the_rotation_and_offsets_from_six_points():
    th = thetas(POSES[:6])
    obs = observe(th, Q_TRUE, d2=50 * ARCMIN, d3=-53 * ARCMIN, s2=0.01)
    f = fit_alignment(th, obs, s2=0.01)
    assert f.offsets_fitted
    assert f.d2 == pytest.approx(50 * ARCMIN, abs=1e-6) and f.d3 == pytest.approx(-53 * ARCMIN, abs=1e-6)
    assert angle_deg(f.q, Q_TRUE) < 1e-6 and f.rms_arcmin < 1e-4


def test_with_plate_solve_noise_the_rms_is_the_noise():
    th = thetas(POSES)
    obs = observe(th, Q_TRUE, d2=1.1, d3=-0.9, s2=0.015, noise_arcmin=2.0, seed=3)
    f = fit_alignment(th, obs, s2=0.015)
    assert abs(f.d2 - 1.1) < 5 * ARCMIN and abs(f.d3 + 0.9) < 5 * ARCMIN
    assert 0.8 < f.rms_arcmin < 3.0


def test_rotation_only_fit_is_quest_for_unweighted_points():
    """Without offsets it is the least-squares rotation, the one QUEST finds with equal weights."""
    th = thetas(POSES[:6])
    obs = observe(th, Q_TRUE, d2=0.0, d3=0.0, s2=0.0, noise_arcmin=1.0, seed=5)
    f = fit_alignment(th, obs, fit_offsets=False)
    assert not f.offsets_fitted and f.d2 == 0 and f.d3 == 0
    B = boresights(th).T @ obs                                                 # QUEST with equal weights
    S, sigma = B + B.T, np.trace(B)
    Z = np.array([B[1, 2] - B[2, 1], B[2, 0] - B[0, 2], B[0, 1] - B[1, 0]])
    K = np.zeros((4, 4)); K[0, 0] = sigma; K[0, 1:] = Z; K[1:, 0] = Z; K[1:, 1:] = S - sigma * np.eye(3)
    w, v = np.linalg.eigh(K)
    assert angle_deg(f.q, Quaternion(*v[:, np.argmax(w)])) < 1e-6


def test_two_points_cannot_fix_the_offsets_so_they_are_held():
    th = thetas(POSES[:2])
    obs = observe(th, Q_TRUE, d2=0.8, d3=-0.7, s2=0.01)
    f = fit_alignment(th, obs, s2=0.01, d_init=(0.6, -0.5))
    assert not f.offsets_fitted and (f.d2, f.d3) == (0.6, -0.5)


def test_points_bunched_together_cannot_separate_the_offsets_so_they_are_held():
    th = thetas([(150, 45, 10), (151, 45.5, 10), (150.5, 46, 11), (149.5, 44.5, 9)])
    obs = observe(th, Q_TRUE, d2=0.8, d3=-0.7, s2=0.0)
    f = fit_alignment(th, obs, d_init=(0.0, 0.0))
    assert not f.offsets_fitted and f.d2 == 0.0 and f.d3 == 0.0


def test_points_at_one_roll_spread_in_az_and_alt_still_fix_both_offsets():
    th = thetas([(100, 30, 0), (140, 45, 0), (180, 60, 0), (220, 40, 0)])
    obs = observe(th, Q_TRUE, d2=0.8, d3=-0.7, s2=0.0)
    f = fit_alignment(th, obs)
    assert f.offsets_fitted and f.d2 == pytest.approx(0.8, abs=1e-6) and f.d3 == pytest.approx(-0.7, abs=1e-6)


def test_the_m2_scale_can_be_calibrated_from_well_spread_points():
    th = thetas(POSES)
    obs = observe(th, Q_TRUE, d2=0.9, d3=-0.8, s2=0.013, noise_arcmin=0.5, seed=7)
    f = fit_alignment(th, obs, s2=0.0, fit_s2=True)
    assert f.s2_fitted and f.s2 == pytest.approx(0.013, abs=0.002)
    assert f.rms_arcmin < 1.0


def test_residuals_are_per_point_in_arcmin():
    th = thetas(POSES[:6])
    obs = observe(th, Q_TRUE, d2=0.0, d3=0.0, s2=0.0)
    obs[2] = Quaternion(axis=[1, 0, 0], degrees=0.5).rotate(obs[2])          # one point 30' off
    f = fit_alignment(th, obs, fit_offsets=False)
    assert f.residuals_arcmin.shape == (6,) and np.argmax(f.residuals_arcmin) == 2
    assert f.rms_arcmin == pytest.approx(np.sqrt(np.mean(f.residuals_arcmin ** 2)))


def test_correction_rotation_closed_form_matches_the_forward_kinematics():
    """kinematics_mac.correction_q(theta, d2, d3, s2) = q(theta') q(theta)^-1, computed directly for the control tick."""
    from kinematics_mac import correction_q
    rng = np.random.default_rng(4)
    for _ in range(50):
        th = np.array([rng.uniform(0, 360), rng.uniform(-8, 81), rng.uniform(-170, 170)])
        d2, d3, s2 = rng.uniform(-2, 2), rng.uniform(-6, 6), rng.uniform(-0.03, 0.03)
        want = theta_to_q(*corrected_theta(th, d2, d3, s2)) * theta_to_q(*th).inverse
        got = correction_q(th, d2, d3, s2)
        assert angle_deg(got, want) < 1e-5                                     # arccos near 1: ~0.01" precision
        b = boresights(th[None])[0]
        assert np.allclose(got.rotate(b), boresights(corrected_theta(th[None], d2, d3, s2))[0], atol=1e-12)


def test_six_standard_points_with_3_arcmin_errors_recover_the_terms_without_bias():
    """How well the standard 6-point alignment determines the terms when each sync point is ~3' off (the typical
    residual after the model): 300 runs. Offsets to ~4' (1 sigma), the M2 scale to ~0.16% -- no bias. One
    alignment's AutoTune is therefore good to about +-0.3% (2 sigma); repeat it, or use more points spread in
    altitude, to tighten it."""
    th = thetas(POSES[:6])
    d2s, d3s, s2s = [], [], []
    for seed in range(300):
        obs = observe(th, Q_TRUE, d2=50 * ARCMIN, d3=-53 * ARCMIN, s2=0.01, noise_arcmin=3.0, seed=seed)
        f = fit_alignment(th, obs, s2=0.01)
        d2s.append(f.d2 * 60); d3s.append(f.d3 * 60)
        s2s.append(fit_alignment(th, obs, fit_s2=True).s2 * 100)
    assert abs(np.mean(d2s) - 50) < 1.0 and abs(np.mean(d3s) + 53) < 1.0 and abs(np.mean(s2s) - 1.0) < 0.05
    assert np.std(d2s) < 5.0 and np.std(d3s) < 5.0 and np.std(s2s) < 0.22
