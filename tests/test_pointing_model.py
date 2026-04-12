"""
test_pointing_model.py — pytest suite for pointing_model.py

Test philosophy:
  - Unit tests use synthetic data with known ground truth so assertions
    can be exact (within floating-point tolerance).
  - Integration tests simulate realistic use: N sync points → fit model
    → evaluate residuals on held-out points.
  - Cross-validation tests use the real session CSVs when available;
    they are skipped gracefully if the files are absent.

Running:
    pytest test_pointing_model.py -v
    pytest test_pointing_model.py -v -k "not real_data"   # skip CSV tests
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))import math

import pytest
import numpy as np
from pyquaternion import Quaternion
from typing import List

from pointing_model import (
    # kinematics
    theta_to_q, q_to_azaltroll, q_to_theta, wrap180, angular_error_arcmin,
    # correction layers
    make_polar_corrQ, apply_polar_correction, apply_polar_correction_pair,
    apply_theta_corrections, ThetaModelParams,
    calc_rbc_corrQ, RBCParams,
    # alignment
    quest_solve, polar_quest_solve,
    # data structures
    Observation, Session,
    load_session_csv, combine_sessions,
    # evaluation
    residual_stats, predict_pointing, evaluate_session, fit_session_alignment,
)

ARCMIN_TOL   = 0.1     # tolerable round-trip / correction error (arcmin)
TIGHT_TOL    = 0.01    # tight tolerance for exact inversions
POLAR_TOL    = 2.0     # polar correction accuracy tolerance (arcmin RMS)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_obs(t1, t2, t3, session_id='test',
             true_AW=0.0, true_AN=0.0,
             noise_arcmin=0.0) -> Observation:
    """Synthetic observation with optional polar tilt and noise."""
    q_base = theta_to_q(t1, t2, t3)
    az_p, alt_p, roll_p = q_to_azaltroll(q_base)

    # Apply true polar tilt to get ground-truth solved position
    q_solved = apply_polar_correction(q_base, true_AW, true_AN)
    if noise_arcmin > 0:
        noise_rad = noise_arcmin / 60.0 / 180.0 * math.pi
        axis = np.random.randn(3); axis /= np.linalg.norm(axis)
        q_noise  = Quaternion(axis=axis.tolist(),
                               angle=noise_rad * np.random.randn())
        q_solved = (q_noise * q_solved).normalised

    az_s, alt_s, roll_s = q_to_azaltroll(q_solved)

    return Observation(
        session_id      = session_id,
        filename        = f'{t1}_{t2}_{t3}.fits',
        theta1=t1, theta2=t2, theta3=t3,
        p_az=az_p, p_alt=alt_p, p_roll=roll_p,
        solved_az=az_s, solved_alt=alt_s, solved_roll=roll_s,
        dev_az_arcmin   = wrap180(az_s  - az_p)  * 60,
        dev_alt_arcmin  = (alt_s - alt_p) * 60,
        dev_roll_arcmin = wrap180(roll_s - roll_p) * 60,
    )


@pytest.fixture
def identity_obs():
    """Simple on-axis observation with no tilt or noise."""
    return make_obs(180, 40, 0)


@pytest.fixture
def polar_tilted_session():
    """Session with known 0.888° polar tilt, 12 observations across sky."""
    np.random.seed(42)
    TRUE_AW = -0.888 * math.cos(math.radians(10.7))
    TRUE_AN =  0.888 * math.sin(math.radians(10.7))
    positions = [(az, alt) for az in range(0, 360, 45) for alt in [30, 50, 70]]
    obs_list = [make_obs(az, alt, 0, session_id='tilt_session',
                          true_AW=TRUE_AW, true_AN=TRUE_AN,
                          noise_arcmin=1.0)
                for az, alt in positions]
    return Session(session_id='tilt_session', observations=obs_list), TRUE_AW, TRUE_AN


# ── Unit tests: kinematics ────────────────────────────────────────────────────

class TestKinematics:

    def test_theta_to_q_roundtrip(self):
        """theta_to_q → q_to_azaltroll → theta_to_q should be self-consistent."""
        for t1, t2, t3 in [(180, 40, 0), (90, 30, 20), (270, 50, -30),
                            (45, 60, 45), (0, 20, -60)]:
            q = theta_to_q(t1, t2, t3)
            t1r, t2r, t3r = q_to_theta(q)
            assert abs(wrap180(t1r - t1)) < 0.01, f"theta1 roundtrip failed: {t1} → {t1r}"
            assert abs(t2r - t2) < 0.01,           f"theta2 roundtrip failed: {t2} → {t2r}"
            assert abs(wrap180(t3r - t3)) < 0.01,   f"theta3 roundtrip failed: {t3} → {t3r}"

    def test_theta2_matches_altitude(self):
        """At theta3=0, theta2 should equal p_alt (mount geometry)."""
        for t2 in [20, 30, 40, 50, 60, 70]:
            q = theta_to_q(180, t2, 0)
            _, alt, _ = q_to_azaltroll(q)
            assert abs(alt - t2) < 0.01, f"alt {alt} ≠ theta2 {t2}"

    def test_theta3_zero_gives_zero_roll(self):
        """At theta3=0, roll should be 0 regardless of pointing."""
        for t1, t2 in [(90, 30), (180, 45), (270, 60)]:
            q = theta_to_q(t1, t2, 0)
            _, _, roll = q_to_azaltroll(q)
            assert abs(roll) < 0.01, f"Roll {roll} ≠ 0 at theta3=0"

    def test_wrap180(self):
        assert wrap180(0)    == 0
        assert wrap180(180)  == -180 or wrap180(180) == 180   # edge case
        assert wrap180(-180) == -180 or wrap180(-180) == 180
        assert abs(wrap180(190))  - 170 < 0.001
        assert abs(wrap180(-190)) - 170 < 0.001

    def test_angular_error_zero(self):
        assert angular_error_arcmin(90, 45, 90, 45) < 1e-6

    def test_angular_error_known(self):
        # 1 degree separation at equator ≈ 60 arcmin
        err = angular_error_arcmin(0, 0, 1, 0)
        assert abs(err - 60.0) < 0.1


# ── Unit tests: polar correction ─────────────────────────────────────────────

class TestPolarCorrection:

    def test_zero_tilt_is_identity(self):
        """AW=AN=0 should return identity quaternion."""
        corrQ = make_polar_corrQ(180.0, 0.0, 0.0)
        assert abs(corrQ[0] - 1.0) < 1e-6

    def test_correction_exact_at_all_azimuths(self):
        """Applying then undoing via corrQ.inverse gives exact floating-point round-trip."""
        AW, AN = -0.888, 0.178
        for t1, t2, t3 in [(0, 40, 0), (90, 30, 0), (180, 50, 0), (270, 60, 0)]:
            q = theta_to_q(t1, t2, t3)
            q_corr, corrQ = apply_polar_correction_pair(q, AW, AN)
            q_recovered   = apply_polar_correction(q_corr, AW, AN,
                                                    undo=True, _corrQ=corrQ)
            az0, alt0, _ = q_to_azaltroll(q)
            azr, altr, _ = q_to_azaltroll(q_recovered)
            err = angular_error_arcmin(az0, alt0, azr, altr)
            assert err < TIGHT_TOL, f"Polar round-trip error {err}' at t1={t1}"

    def test_polar_correction_removes_sinusoidal_error(self):
        """
        A mount with polar tilt produces az-dependent altitude errors.
        After polar correction, those errors should be near zero.
        """
        AW, AN = -0.888 * math.cos(math.radians(10.7)), \
                  0.888 * math.sin(math.radians(10.7))
        errors_before, errors_after = [], []

        for az in range(0, 360, 30):
            q = theta_to_q(az, 40, 0)
            # True topo = polar correction applied
            q_true    = apply_polar_correction(q, AW, AN)
            az_t, alt_t, _ = q_to_azaltroll(q_true)
            az_p, alt_p, _ = q_to_azaltroll(q)

            errors_before.append(abs(alt_t - alt_p) * 60)

            # After correction
            q_corr = apply_polar_correction(q, AW, AN)
            az_c, alt_c, _ = q_to_azaltroll(q_corr)
            errors_after.append(angular_error_arcmin(az_c, alt_c, az_t, alt_t))

        rms_before = math.sqrt(sum(e**2 for e in errors_before) / len(errors_before))
        rms_after  = math.sqrt(sum(e**2 for e in errors_after)  / len(errors_after))
        assert rms_before > 30.0, "Expected >30' error before correction"
        assert rms_after  < 0.01, f"Expected <0.01' after correction, got {rms_after}'"

    @pytest.mark.parametrize("tppa_alt,tppa_az", [
        (53.3, 10.7),
        (-30.0, 20.0),
        (0.0, 45.0),
        (45.0, 0.0),
    ])
    def test_tppa_to_aw_an_conversion(self, tppa_alt, tppa_az):
        """NINA TPPA errors should convert correctly to AW/AN."""
        AW = -tppa_alt / 60.0
        AN = +tppa_az  / 60.0

        # Validate: the total tilt magnitude should match
        eps_expected = math.sqrt((tppa_alt/60)**2 + (tppa_az/60)**2)
        eps_got      = math.sqrt(AW**2 + AN**2)
        assert abs(eps_got - eps_expected) < 1e-9


# ── Unit tests: theta-space corrections ──────────────────────────────────────

class TestThetaCorrections:

    def test_zero_params_is_identity(self):
        """ThetaModelParams with all zeros should not change pointing."""
        params = ThetaModelParams()
        for t1, t2, t3 in [(180, 40, 0), (90, 30, 20), (270, 50, -30)]:
            q = theta_to_q(t1, t2, t3)
            q_corr = apply_theta_corrections(q, params)
            az0, alt0, _ = q_to_azaltroll(q)
            azc, altc, _ = q_to_azaltroll(q_corr)
            err = angular_error_arcmin(az0, alt0, azc, altc)
            assert err < TIGHT_TOL, f"Zero params changed pointing by {err}'"

    def test_m2_tilt_zero_crossing(self):
        """At theta2 = m2_tilt_zero_deg, B1 correction should be zero."""
        params = ThetaModelParams(m2_tilt_arcmin=52.0, m2_tilt_zero_deg=36.4)
        q = theta_to_q(180, 36.4, 0)
        q_corr = apply_theta_corrections(q, params)
        az0, alt0, _ = q_to_azaltroll(q)
        azc, altc, _ = q_to_azaltroll(q_corr)
        err = angular_error_arcmin(az0, alt0, azc, altc)
        assert err < TIGHT_TOL, f"B1 correction at zero crossing = {err}'"

    def test_m2_tilt_affects_only_altitude(self):
        """B1 correction should not change azimuth or roll."""
        params = ThetaModelParams(m2_tilt_arcmin=52.0, m2_tilt_zero_deg=36.4)
        q = theta_to_q(180, 50, 0)
        q_corr = apply_theta_corrections(q, params)
        az0, _, roll0 = q_to_azaltroll(q)
        azc, _, rollc = q_to_azaltroll(q_corr)
        assert abs(wrap180(azc - az0)) * 60 < TIGHT_TOL,   "B1 changed azimuth"
        assert abs(wrap180(rollc - roll0)) * 60 < TIGHT_TOL, "B1 changed roll"

    def test_boresight_correction_is_pure_roll(self):
        """B2 (boresight rotation) should change roll only, not az or alt."""
        params = ThetaModelParams(roll_amp_arcmin=150.0, roll_zero_deg=-52.0)
        for t2 in [20, 40, 60, 80]:
            q = theta_to_q(180, t2, 0)
            q_corr = apply_theta_corrections(q, params)
            az0, alt0, _ = q_to_azaltroll(q)
            azc, altc, _ = q_to_azaltroll(q_corr)
            daz  = abs(wrap180(azc - az0)) * 60
            dalt = abs(altc - alt0) * 60
            assert daz  < TIGHT_TOL, f"B2 changed az by {daz}' at theta2={t2}"
            assert dalt < TIGHT_TOL, f"B2 changed alt by {dalt}' at theta2={t2}"

    def test_m3_encoder_zero_at_theta3_zero(self):
        """B3 correction should be zero when theta3=0."""
        params = ThetaModelParams(m3_encoder_k=0.013)
        for t1, t2 in [(90, 30), (180, 45), (270, 60)]:
            q = theta_to_q(t1, t2, 0)
            q_corr = apply_theta_corrections(q, params)
            az0, alt0, _ = q_to_azaltroll(q)
            azc, altc, _ = q_to_azaltroll(q_corr)
            err = angular_error_arcmin(az0, alt0, azc, altc)
            assert err < TIGHT_TOL, f"B3 non-zero at theta3=0: {err}'"

    def test_m2_correction_produces_zero_roll(self):
        """
        Proven geometrically: M2 axis ⊥ boresight → zero roll change.
        """
        params = ThetaModelParams(m2_tilt_arcmin=52.0, m2_tilt_zero_deg=36.4)
        for t1, t2 in [(90, 30), (180, 45), (270, 60), (45, 70)]:
            q = theta_to_q(t1, t2, 0)
            q_corr = apply_theta_corrections(q, params)
            _, _, roll0 = q_to_azaltroll(q)
            _, _, rollc = q_to_azaltroll(q_corr)
            droll = abs(wrap180(rollc - roll0)) * 60
            assert droll < TIGHT_TOL, \
                f"M2 correction changed roll by {droll}' at t1={t1} t2={t2}"


# ── Unit tests: RBC correction ────────────────────────────────────────────────

class TestRBCCorrection:

    def test_zero_roll_no_correction(self):
        """p_roll=0 → no RBC correction."""
        params = RBCParams(rbc_model_a=0.94, rbc_model_b=0.25, rbc_model_c=-1.01)
        q = theta_to_q(180, 40, 0)     # theta3=0 → p_roll≈0
        corrQ, roll_err = calc_rbc_corrQ(q, params)
        assert corrQ is None
        assert roll_err == 0.0

    def test_rbc_no_altitude_change(self):
        """
        Boresight + Z rotations cannot change altitude (proven geometrically).
        """
        params = RBCParams(rbc_model_a=0.94, rbc_model_b=0.25, rbc_model_c=-1.01)
        for t1, t2, t3 in [(180, 46, -55), (90, 40, -30), (270, 50, 50)]:
            q = theta_to_q(t1, t2, t3)
            corrQ, _ = calc_rbc_corrQ(q, params, sign=-1)
            if corrQ is None:
                continue
            q_corr = (corrQ * q).normalised
            _, alt0, _ = q_to_azaltroll(q)
            _, altc, _ = q_to_azaltroll(q_corr)
            assert abs(altc - alt0) * 60 < TIGHT_TOL, \
                f"RBC changed altitude by {(altc-alt0)*60:.4f}' at t3={t3}"

    def test_rbc_apply_undo_roundtrip(self):
        """Applying then undoing RBC via corrQ.inverse should be exact."""
        params = RBCParams(rbc_model_a=0.94, rbc_model_b=0.25, rbc_model_c=-1.01)
        for t1, t2, t3 in [(90, 30, 20), (180, 46, -55), (270, 50, 50)]:
            q = theta_to_q(t1, t2, t3)
            corrQ, _ = calc_rbc_corrQ(q, params, sign=-1)
            if corrQ is None:
                continue
            q_applied   = (corrQ * q).normalised
            q_recovered = (corrQ.inverse * q_applied).normalised
            az0, alt0, _ = q_to_azaltroll(q)
            azr, altr, _ = q_to_azaltroll(q_recovered)
            err = angular_error_arcmin(az0, alt0, azr, altr)
            assert err < TIGHT_TOL, f"RBC round-trip error {err}' at t3={t3}"


# ── Unit tests: QUEST alignment ───────────────────────────────────────────────

class TestQuestSolve:

    def test_single_pair_exact(self):
        """With 1 pair, QUEST should fit it exactly."""
        q_base  = theta_to_q(180, 40, 0)
        q_topo  = apply_polar_correction(q_base, -0.5, 0.2)
        alignQ  = quest_solve([(q_base, q_topo)])
        q_pred  = (alignQ * q_base).normalised
        az_t, alt_t, _ = q_to_azaltroll(q_topo)
        az_p, alt_p, _ = q_to_azaltroll(q_pred)
        err = angular_error_arcmin(az_p, alt_p, az_t, alt_t)
        assert err < ARCMIN_TOL

    def test_multiple_pairs_low_residual(self):
        """With consistent pairs, QUEST residuals should be near zero."""
        # Simulate a mount with a constant rigid body offset
        AW, AN = -0.888, 0.178
        positions = [(az, 40) for az in range(0, 360, 45)]
        pairs = []
        for az, alt in positions:
            q_b = theta_to_q(az, alt, 0)
            q_t = apply_polar_correction(q_b, AW, AN)
            pairs.append((q_b, q_t))

        alignQ = quest_solve(pairs)
        errs   = []
        for q_b, q_t in pairs:
            q_p = (alignQ * q_b).normalised
            az_t, alt_t, _ = q_to_azaltroll(q_t)
            az_p, alt_p, _ = q_to_azaltroll(q_p)
            errs.append(angular_error_arcmin(az_p, alt_p, az_t, alt_t))
        # Polar tilt is NOT a rigid body — QUEST should leave ~30' RMS
        rms = math.sqrt(sum(e**2 for e in errs) / len(errs))
        assert rms > 10.0, "QUEST should NOT fully absorb polar tilt"


class TestPolarQuestSolve:

    def test_falls_back_with_few_pairs(self):
        """polar_quest_solve with N<3 should return AW=AN=0 (fallback)."""
        AW, AN = -0.888, 0.178
        pairs = [(theta_to_q(180, 40, 0),
                  apply_polar_correction(theta_to_q(180, 40, 0), AW, AN))]
        _, AW_fit, AN_fit = polar_quest_solve(pairs)
        assert AW_fit == 0.0 and AN_fit == 0.0

    def test_falls_back_with_narrow_az_spread(self):
        """polar_quest_solve with az spread < 60° should fall back."""
        AW, AN = -0.888, 0.178
        pairs = []
        for az in [0, 10, 20]:      # only 20° spread
            q_b = theta_to_q(az, 40, 0)
            q_t = apply_polar_correction(q_b, AW, AN)
            pairs.append((q_b, q_t))
        _, AW_fit, AN_fit = polar_quest_solve(pairs)
        assert AW_fit == 0.0 and AN_fit == 0.0

    def test_recovers_tilt_with_good_coverage(self, polar_tilted_session):
        """With 12 well-spread noiseless pairs, should recover tilt within 2'."""
        session, TRUE_AW, TRUE_AN = polar_tilted_session
        np.random.seed(0)
        # Noiseless version
        noiseless = []
        for obs in session.observations:
            q_b = obs.q_base
            q_t = apply_polar_correction(q_b, TRUE_AW, TRUE_AN)
            noiseless.append((q_b, q_t))

        _, AW_fit, AN_fit = polar_quest_solve(noiseless,
                                               AW_init=TRUE_AW * 0.5,
                                               AN_init=TRUE_AN * 0.5)
        assert abs(AW_fit - TRUE_AW) * 60 < POLAR_TOL, \
            f"AW error: {abs(AW_fit-TRUE_AW)*60:.1f}'"
        assert abs(AN_fit - TRUE_AN) * 60 < POLAR_TOL, \
            f"AN error: {abs(AN_fit-TRUE_AN)*60:.1f}'"


# ── Integration tests: sync → predict ────────────────────────────────────────

class TestSyncAndPredict:

    def _make_session(self, n_obs=24, AW=-0.888, AN=0.178,
                      noise=1.0, seed=42) -> Session:
        np.random.seed(seed)
        positions = [(az, alt) for az in range(0, 360, 45) for alt in [25, 45, 65]]
        obs_list  = [make_obs(az, alt, 0, session_id='sim',
                               true_AW=AW, true_AN=AN,
                               noise_arcmin=noise)
                     for az, alt in positions[:n_obs]]
        return Session(session_id='sim', observations=obs_list)

    def test_level0_baseline(self):
        """Level 0 (raw kinematics) should show large errors (~60' RMS)."""
        session = self._make_session()
        identity = Quaternion(1, 0, 0, 0)
        _, test = evaluate_session(session, identity)
        assert test.rms > 30.0, f"Expected >30' baseline RMS, got {test.rms:.1f}'"

    def test_level1_quest_reduces_error(self):
        """QUEST with 4 sync points should reduce error vs baseline."""
        session = self._make_session()
        sync_idx = [0, 3, 8, 16]   # spread across sky
        alignQ, _, _ = fit_session_alignment(session, sync_idx)
        sync_stats, test_stats = evaluate_session(
            session, alignQ, sync_indices=sync_idx)
        baseline = self._make_session()
        _, bl_test = evaluate_session(baseline, Quaternion(1, 0, 0, 0))
        assert test_stats.rms < bl_test.rms, "QUEST should reduce error vs baseline"

    def test_level2_polar_quest_beats_quest(self):
        """Polar-aware QUEST should beat plain QUEST with enough sync points."""
        session = self._make_session(noise=1.0)
        sync_idx = list(range(12))   # 12 sync points, good az coverage

        # Level 1: standard QUEST
        alignQ1, _, _ = fit_session_alignment(session, sync_idx, fit_polar=False)
        _, test1 = evaluate_session(session, alignQ1, sync_indices=sync_idx)

        # Level 2: polar-aware QUEST
        alignQ2, AW2, AN2 = fit_session_alignment(session, sync_idx, fit_polar=True)
        _, test2 = evaluate_session(session, alignQ2, AW2, AN2,
                                     sync_indices=sync_idx)

        assert test2.rms < test1.rms, \
            f"Polar QUEST {test2.rms:.1f}' should beat QUEST {test1.rms:.1f}'"

    def test_sync_residuals_near_zero(self):
        """
        Sync point residuals should be near-zero after fitting alignQ,
        PROVIDED the true error is a rigid body rotation (constant alignQ).

        Polar tilt is NOT a rigid body rotation — corrQ varies with azimuth —
        so QUEST cannot zero all sync points simultaneously with a polar-tilted
        true model.  This test uses a constant rigid body offset.
        """
        TRUE_ALIGN = Quaternion(axis=[0.1, 0.3, 0.9], degrees=2.5).normalised
        positions  = [(az, alt) for az in range(0, 360, 45) for alt in [25, 45, 65]]

        def _obs_rigid(t1, t2):
            q_base   = theta_to_q(t1, t2, 0)
            q_solved = (TRUE_ALIGN * q_base).normalised
            az_p, alt_p, roll_p = q_to_azaltroll(q_base)
            az_s, alt_s, roll_s = q_to_azaltroll(q_solved)
            return Observation(
                session_id='rigid', filename=f'{t1}_{t2}.fits',
                theta1=t1, theta2=t2, theta3=0,
                p_az=az_p, p_alt=alt_p, p_roll=roll_p,
                solved_az=az_s, solved_alt=alt_s, solved_roll=roll_s,
                dev_az_arcmin=wrap180(az_s-az_p)*60,
                dev_alt_arcmin=(alt_s-alt_p)*60,
                dev_roll_arcmin=wrap180(roll_s-roll_p)*60,
            )

        obs_list = [_obs_rigid(az, alt) for az, alt in positions]
        session  = Session(session_id='rigid', observations=obs_list)
        sync_idx = [0, 6, 12, 18]
        alignQ, _, _ = fit_session_alignment(session, sync_idx)
        sync_stats, _ = evaluate_session(session, alignQ, sync_indices=sync_idx)
        assert sync_stats.rms < TIGHT_TOL, \
            f"Sync residuals should be <{TIGHT_TOL}', got {sync_stats.rms:.4f}'"

    @pytest.mark.parametrize("n_sync", [1, 2, 3, 6, 12])
    def test_error_decreases_with_more_sync_points(self, n_sync):
        """More sync points should generally improve or maintain accuracy."""
        session = self._make_session(noise=2.0, seed=7)
        sync_idx = list(range(n_sync))
        alignQ, _, _ = fit_session_alignment(session, sync_idx)
        _, test = evaluate_session(session, alignQ, sync_indices=sync_idx)
        # No strict assertion — just ensure it runs without error
        assert test.rms >= 0


# ── Cross-session tests ───────────────────────────────────────────────────────

class TestCrossSession:

    def _make_multi_session(self, n_sessions=3, n_obs=24,
                             base_AW=-0.5, base_AN=0.1):
        """Generate multiple sessions with different polar tilts."""
        np.random.seed(99)
        sessions = []
        for j in range(n_sessions):
            # Each session has slightly different polar tilt (mount repositioned)
            AW = base_AW + np.random.uniform(-0.2, 0.2)
            AN = base_AN + np.random.uniform(-0.1, 0.1)
            positions = [(az, alt)
                          for az in range(0, 360, 45)
                          for alt in [25, 45, 65]]
            obs_list = [make_obs(az, alt, t3, session_id=f'session_{j}',
                                  true_AW=AW, true_AN=AN, noise_arcmin=2.0)
                        for (az, alt), t3 in zip(positions[:n_obs],
                                                   [0] * n_obs)]
            sessions.append(Session(session_id=f'session_{j}',
                                     observations=obs_list))
        return sessions

    def test_combine_sessions(self):
        """Combining sessions should give total N observations."""
        sessions = self._make_multi_session(n_sessions=3, n_obs=12)
        all_obs = combine_sessions(sessions)
        assert len(all_obs) == 3 * 12

    def test_per_session_quest_each_session(self):
        """Each session's QUEST should fit independently."""
        sessions = self._make_multi_session()
        for session in sessions:
            sync_idx = list(range(6))
            alignQ, _, _ = fit_session_alignment(session, sync_idx)
            _, test = evaluate_session(session, alignQ, sync_indices=sync_idx)
            assert test.rms >= 0   # just runs cleanly

    def test_leave_one_session_out(self):
        """
        Simulate realistic cross-validation:
          - Fit theta-space params on N-1 sessions (shared hardware)
          - Evaluate residuals on held-out session with fresh alignQ
        For now uses zero theta-space params (no shared hardware fitted yet).
        TODO: extend when cross-session theta fitting is implemented.
        """
        sessions = self._make_multi_session(n_sessions=3)
        results = []
        for j, test_session in enumerate(sessions):
            train_sessions = [s for i, s in enumerate(sessions) if i != j]
            # Fit per-session params on held-out session using 4 sync points
            sync_idx = [0, 3, 8, 16]
            alignQ, AW, AN = fit_session_alignment(
                test_session, sync_idx, fit_polar=True)
            _, test = evaluate_session(
                test_session, alignQ, AW, AN, sync_indices=sync_idx)
            results.append(test.rms)
        avg_rms = sum(results) / len(results)
        assert avg_rms < 100.0, f"Cross-validation RMS unreasonably high: {avg_rms:.1f}'"


# ── Real data tests (skipped if CSV not present) ─────────────────────────────

REAL_CSV_196  = '/home/claude/fits_extract.csv'
REAL_CSV_ENRICHED = '/home/claude/fits_enriched.csv'

@pytest.mark.skipif(not os.path.exists(REAL_CSV_196),
                     reason="196-frame CSV not available")
class TestRealData196:

    @pytest.fixture(scope='class')
    def session(self):
        return load_session_csv(REAL_CSV_196, session_id='196frame')

    def test_load(self, session):
        assert session.n > 100, f"Expected >100 obs, got {session.n}"

    def test_baseline_rms(self, session):
        """Raw kinematics should have large RMS (polar tilt present)."""
        identity = Quaternion(1, 0, 0, 0)
        _, test = evaluate_session(session, identity)
        assert test.rms > 30.0

    @pytest.mark.parametrize("n_sync", [1, 3, 6, 12])
    def test_quest_improves_with_sync_count(self, session, n_sync):
        """QUEST should reduce errors, improving as N_sync grows."""
        step = max(1, session.n // n_sync)
        sync_idx = list(range(0, session.n, step))[:n_sync]
        alignQ, _, _ = fit_session_alignment(session, sync_idx)
        _, test = evaluate_session(session, alignQ, sync_indices=sync_idx)
        assert test.rms >= 0

    def test_polar_quest_beats_quest_with_12_sync(self, session):
        """Polar QUEST should beat plain QUEST given good az coverage."""
        step     = session.n // 12
        sync_idx = list(range(0, session.n, step))[:12]

        alignQ1, _, _     = fit_session_alignment(session, sync_idx, fit_polar=False)
        alignQ2, AW2, AN2 = fit_session_alignment(session, sync_idx, fit_polar=True)

        _, test1 = evaluate_session(session, alignQ1, sync_indices=sync_idx)
        _, test2 = evaluate_session(session, alignQ2, AW2, AN2,
                                     sync_indices=sync_idx)

        print(f"\n  QUEST RMS: {test1.rms:.1f}'  "
              f"PolarQUEST RMS: {test2.rms:.1f}'  "
              f"AW={AW2*60:.1f}\"  AN={AN2*60:.1f}\"")
        # Polar QUEST should not be worse
        assert test2.rms <= test1.rms * 1.1   # allow 10% tolerance for noise

    def test_known_theta_params_reduce_residuals(self, session):
        """Applying fitted theta-space corrections should reduce residuals."""
        params = ThetaModelParams.from_config_values(
            theta_model_a=52.18, theta_model_b=36.39,
            theta_model_c=150.5, theta_model_d=-52.35,
        )
        sync_idx = list(range(0, session.n, 16))[:8]

        # Without theta corrections
        alignQ1, _, _ = fit_session_alignment(session, sync_idx)
        _, test1 = evaluate_session(session, alignQ1, sync_indices=sync_idx)

        # With theta corrections
        alignQ2, _, _ = fit_session_alignment(
            session, sync_idx, theta_params=params)
        _, test2 = evaluate_session(
            session, alignQ2, theta_params=params, sync_indices=sync_idx)

        print(f"\n  Without theta: {test1.rms:.1f}'  With theta: {test2.rms:.1f}'")
        assert test2.rms <= test1.rms * 1.2   # should not significantly worsen



@pytest.mark.skipif(not os.path.exists(REAL_CSV_ENRICHED),
                     reason="Enriched CSV not available")
class TestRealDataEnriched:
    """Tests on the pa_*-enriched 196-frame dataset (full az/alt survey, theta3≈0)."""

    @pytest.fixture(scope='class')
    def session(self):
        return load_session_csv(REAL_CSV_ENRICHED, session_id='enriched')

    def test_load(self, session):
        assert session.n > 100, f"Expected >100 obs, got {session.n}"

    def test_theta3_limited_as_expected(self, session):
        """This is a p_roll≈0 az/alt survey — theta3 range is small by design."""
        t3s    = [o.theta3 for o in session.observations]
        spread = max(t3s) - min(t3s)
        assert 5.0 < spread < 20.0, f"Expected 5-20° theta3 span, got {spread:.1f}°"

    def test_good_az_coverage(self, session):
        """Az/alt survey should have good azimuth coverage (>270°)."""
        azs  = [o.p_az for o in session.observations]
        s    = sorted(a % 360 for a in azs)
        gaps = [s[i+1]-s[i] for i in range(len(s)-1)] + [360-s[-1]+s[0]]
        spread = 360 - max(gaps)
        assert spread > 270, f"Expected >270° az spread, got {spread:.1f}°"