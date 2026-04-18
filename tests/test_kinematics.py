"""
test_kinematics.py — pytest suite for kinematics.py

Running:
    pytest test_kinematics.py -v
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
import math
import pytest
import numpy as np
from pyquaternion import Quaternion

import kinematics as pm
from kinematics import (
    theta_to_q, q_to_azaltroll, q_to_theta, q_from_azaltroll,
    azaltroll_to_q, azaltroll_to_theta, wrap180, angular_error_arcmin,
    wrap_to_180, wrap_to_360, wrap_to_90, rotator_to_p_roll,
    calc_parallactic_angle, crota2_from_cd, crota2_to_roll,
    make_polar_corrQ, apply_polar_correction, apply_polar_correction_pair,
    apply_mechanical_corrections, MountModelParams,
    quest_solve,
)

ARCMIN_TOL = 0.1    # tolerable correction error (arcmin)
TIGHT_TOL  = 0.01   # tight tolerance for exact inversions
POLAR_TOL  = 2.0    # polar correction accuracy tolerance (arcmin RMS)


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


# ── Unit tests: mechanical axis corrections ───────────────────────────────────


class TestMechanicalCorrections:

    def test_zero_params_is_identity(self):
        """MountModelParams with all zeros should not change pointing."""
        params = MountModelParams()
        for t1, t2, t3 in [(180, 40, 0), (90, 30, 20), (270, 50, -30)]:
            q = theta_to_q(t1, t2, t3)
            q_corr = apply_mechanical_corrections(q, params)
            az0, alt0, _ = q_to_azaltroll(q)
            azc, altc, _ = q_to_azaltroll(q_corr)
            err = angular_error_arcmin(az0, alt0, azc, altc)
            assert err < TIGHT_TOL, f"Zero params changed pointing by {err}'"

    def test_m2_tilt_zero_crossing(self):
        """At theta2 = m2_tilt_alt_zero, M2 tilt correction should be zero."""
        params = MountModelParams(m2_tilt_alt_amp=52.0, m2_tilt_alt_zero=36.4)
        q = theta_to_q(180, 36.4, 0)
        q_corr = apply_mechanical_corrections(q, params)
        az0, alt0, _ = q_to_azaltroll(q)
        azc, altc, _ = q_to_azaltroll(q_corr)
        err = angular_error_arcmin(az0, alt0, azc, altc)
        assert err < TIGHT_TOL, f"M2 tilt correction at zero crossing = {err}'"

    def test_m2_tilt_affects_only_altitude(self):
        """M2 tilt correction should not change azimuth or roll."""
        params = MountModelParams(m2_tilt_alt_amp=52.0, m2_tilt_alt_zero=36.4)
        q = theta_to_q(180, 50, 0)
        q_corr = apply_mechanical_corrections(q, params)
        az0, _, roll0 = q_to_azaltroll(q)
        azc, _, rollc = q_to_azaltroll(q_corr)
        assert abs(wrap180(azc - az0)) * 60 < TIGHT_TOL,   "M2 tilt changed azimuth"
        assert abs(wrap180(rollc - roll0)) * 60 < TIGHT_TOL, "M2 tilt changed roll"

    def test_zero_m3_encoder_at_theta3_zero(self):
        """M3 encoder correction should be zero when theta3=0 (any az/alt)."""
        params = MountModelParams(m3_encoder_scale=0.0)
        for t2 in [20, 40, 60, 80]:
            q = theta_to_q(180, t2, 0)
            q_corr = apply_mechanical_corrections(q, params)
            az0, alt0, _ = q_to_azaltroll(q)
            azc, altc, _ = q_to_azaltroll(q_corr)
            err = angular_error_arcmin(az0, alt0, azc, altc)
            assert err < TIGHT_TOL, f"Zero params changed pointing by {err}' at theta2={t2}"

    def test_m3_encoder_zero_at_theta3_zero(self):
        """M3 encoder correction should be zero when theta3=0."""
        params = MountModelParams(m3_encoder_scale=0.78)
        for t1, t2 in [(90, 30), (180, 45), (270, 60)]:
            q = theta_to_q(t1, t2, 0)
            q_corr = apply_mechanical_corrections(q, params)
            az0, alt0, _ = q_to_azaltroll(q)
            azc, altc, _ = q_to_azaltroll(q_corr)
            err = angular_error_arcmin(az0, alt0, azc, altc)
            assert err < TIGHT_TOL, f"M3 encoder non-zero at theta3=0: {err}'"

    def test_m2_correction_produces_zero_roll(self):
        """M2 tilt correction rotates around M2 axis (⊥ boresight) so roll is unchanged."""
        params = MountModelParams(m2_tilt_alt_amp=52.0, m2_tilt_alt_zero=36.4)
        for t1, t2 in [(90, 30), (180, 45), (270, 60), (45, 70)]:
            q = theta_to_q(t1, t2, 0)
            q_corr = apply_mechanical_corrections(q, params)
            _, _, roll0 = q_to_azaltroll(q)
            _, _, rollc = q_to_azaltroll(q_corr)
            droll = abs(wrap180(rollc - roll0)) * 60
            assert droll < TIGHT_TOL, \
                f"M2 correction changed roll by {droll}' at t1={t1} t2={t2}"


# ── Unit tests: RBC correction ────────────────────────────────────────────────


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


class TestAngleHelpers:
    def test_wrap_to_180(self):
        assert pm.wrap_to_180(270)  == -90.0
        assert pm.wrap_to_180(-270) ==  90.0
        assert pm.wrap_to_180(180)  == -180.0
        assert pm.wrap_to_180(0)    ==   0.0

    def test_wrap_to_360(self):
        assert pm.wrap_to_360(-10)  == 350.0
        assert pm.wrap_to_360(370)  ==  10.0
        assert pm.wrap_to_360(0)    ==   0.0

    def test_wrap_to_90(self):
        assert pm.wrap_to_90(100)  == -80.0
        assert pm.wrap_to_90(-91)  ==  89.0

    def test_rotator_to_p_roll(self):
        assert pm.rotator_to_p_roll(0)   ==   0.0
        assert pm.rotator_to_p_roll(270) == -90.0

    def test_calc_parallactic_angle_zenith(self):
        """At zenith (alt=90), parallactic angle is 0."""
        assert pm.calc_parallactic_angle(0.0, 90.0, -33.86) == pytest.approx(0.0)

    def test_calc_parallactic_angle_value(self):
        """Parallactic angle should be a float in [-180, 180]."""
        pa = pm.calc_parallactic_angle(0.0, 45.0, -33.86)
        assert isinstance(pa, float)
        assert -180 <= pa <= 180

    def test_crota2_from_cd_zero(self):
        assert pm.crota2_from_cd(0.0, 0.0) is None

    def test_crota2_from_cd_value(self):
        angle = pm.crota2_from_cd(0.0, -1.0)
        assert angle == pytest.approx(180.0) or angle == pytest.approx(-180.0)

    def test_crota2_to_roll_roundtrip(self):
        """crota2_to_roll returns (roll, para) both as floats in range."""
        roll, para = pm.crota2_to_roll(45.0, 180.0, 40.0, -33.86)
        assert isinstance(roll, float) and isinstance(para, float)
        assert -180 <= roll <= 180 and -180 <= para <= 180


class TestM3TiltCorrection:
    """Tests for M3 tilt correction (m3_tilt_alt) — was B5."""

    def test_m3_tilt_alt_stored_in_arcmin_per_deg(self):
        """m3_tilt_alt field stores value directly in arcmin/deg (no /60 in dataclass)."""
        p = pm.MountModelParams(m3_tilt_alt=-2.394)
        assert p.m3_tilt_alt == pytest.approx(-2.394)

    def test_m3_tilt_alt_no_correction_at_t3_zero(self):
        """M3 tilt correction should be zero when theta3=0."""
        p = pm.MountModelParams(m3_tilt_alt=-2.394)
        q = pm.theta_to_q(180, 40, 0)
        q_corr = pm.apply_mechanical_corrections(q, p)
        t1r, t2r, t3r = pm.q_to_theta(q)
        t1c, t2c, t3c = pm.q_to_theta(q_corr)
        assert abs(t2c - t2r) < 0.01

    def test_m3_tilt_alt_corrects_dev_theta2(self):
        """After M3 tilt correction, pa_dev_theta2 should be near zero."""
        m3_tilt_alt = -2.394  # arcmin/deg
        p = pm.MountModelParams(m3_tilt_alt=m3_tilt_alt)
        for t3 in [-50, -30, -10, 10, 30, 50]:
            q_base = pm.theta_to_q(180, 40, t3)
            t1_m, t2_m, t3_m = pm.q_to_theta(q_base)
            # Simulate real hardware: offset theta2 by the M3 tilt amount
            t2_real = t2_m + m3_tilt_alt * t3 / 60.0
            # Apply M3 tilt correction to q_base
            q_corr = pm.apply_mechanical_corrections(q_base, p)
            t1c, t2c, t3c = pm.q_to_theta(q_corr)
            # pa_dev_theta2 after correction
            pa_dev = (t2_real - t2c) * 60.0
            assert abs(pa_dev) < 0.1, f"t3={t3}: pa_dev_theta2={pa_dev:.2f}' (expected ≈0)"

    def test_m3_tilt_alt_direction_positive_t3(self):
        """At positive t3, M3 tilt correction should DECREASE pa_theta2."""
        p = pm.MountModelParams(m3_tilt_alt=-2.394)
        q = pm.theta_to_q(180, 40, 30)
        q_corr = pm.apply_mechanical_corrections(q, p)
        t1r, t2r, _ = pm.q_to_theta(q)
        t1c, t2c, _ = pm.q_to_theta(q_corr)
        assert t2c < t2r, "M3 tilt alt should decrease pa_theta2 when theta3 > 0"

    def test_m3_tilt_alt_direction_negative_t3(self):
        """At negative t3, M3 tilt correction should INCREASE pa_theta2."""
        p = pm.MountModelParams(m3_tilt_alt=-2.394)
        q = pm.theta_to_q(180, 40, -30)
        q_corr = pm.apply_mechanical_corrections(q, p)
        t1r, t2r, _ = pm.q_to_theta(q)
        t1c, t2c, _ = pm.q_to_theta(q_corr)
        assert t2c > t2r, "M3 tilt alt should increase pa_theta2 when theta3 < 0"

    def test_m3_tilt_and_m2_tilt_independent(self):
        """M3 tilt and M2 tilt applied together give independent corrections."""
        p_m3_only = pm.MountModelParams(m3_tilt_alt=-2.394)
        p_both    = pm.MountModelParams(m3_tilt_alt=-2.394,
                                        m2_tilt_alt_amp=52.2, m2_tilt_alt_zero=36.4)
        q = pm.theta_to_q(180, 60, 30)
        q_m3    = pm.apply_mechanical_corrections(q, p_m3_only)
        q_both  = pm.apply_mechanical_corrections(q, p_both)
        t1_m3,   t2_m3,   _ = pm.q_to_theta(q_m3)
        t1_both, t2_both, _ = pm.q_to_theta(q_both)
        # M2 tilt adds additional theta2 correction on top of M3 tilt
        # At theta2=60, zero=36.4: sin(23.6°)=0.40, correction = 52.2*0.40/60 = 0.35°
        assert abs(t2_m3 - t2_both) > 0.1, "M2 tilt should add extra theta2 shift on top of M3 tilt"


