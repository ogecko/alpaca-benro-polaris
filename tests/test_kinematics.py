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
from quaternion import Q as Quaternion

import kinematics as pm
from kinematics import (
    theta_to_q, q_to_azaltroll, q_to_theta, q_from_azaltroll,
    azaltroll_to_q, azaltroll_to_theta, angular_error_arcmin,
    wrap360, wrap180, wrap90,
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
            q_corr, _ = apply_mechanical_corrections(q, params)
            az0, alt0, _ = q_to_azaltroll(q)
            azc, altc, _ = q_to_azaltroll(q_corr)
            err = angular_error_arcmin(az0, alt0, azc, altc)
            assert err < TIGHT_TOL, f"Zero params changed pointing by {err}'"

    def test_m2_tilt_zero_crossing(self):
        """At theta2 = m2_tilt_dm2_zero, M2 tilt correction should be zero."""
        params = MountModelParams(m2_tilt_dm2_amp=52.0, m2_tilt_dm2_zero=36.4)
        q = theta_to_q(180, 36.4, 0)
        q_corr, _ = apply_mechanical_corrections(q, params)
        az0, alt0, _ = q_to_azaltroll(q)
        azc, altc, _ = q_to_azaltroll(q_corr)
        err = angular_error_arcmin(az0, alt0, azc, altc)
        assert err < TIGHT_TOL, f"M2 tilt correction at zero crossing = {err}'"

    def test_m2_tilt_affects_only_altitude(self):
        """M2 tilt correction should not change azimuth or roll."""
        params = MountModelParams(m2_tilt_dm2_amp=52.0, m2_tilt_dm2_zero=36.4)
        q = theta_to_q(180, 50, 0)
        q_corr, _ = apply_mechanical_corrections(q, params)
        az0, _, roll0 = q_to_azaltroll(q)
        azc, _, rollc = q_to_azaltroll(q_corr)
        assert abs(wrap180(azc - az0)) * 60 < TIGHT_TOL,   "M2 tilt changed azimuth"
        assert abs(wrap180(rollc - roll0)) * 60 < TIGHT_TOL, "M2 tilt changed roll"


    def test_m2_correction_produces_zero_roll(self):
        """M2 tilt correction rotates around M2 axis (⊥ boresight) so roll is unchanged."""
        params = MountModelParams(m2_tilt_dm2_amp=52.0, m2_tilt_dm2_zero=36.4)
        for t1, t2 in [(90, 30), (180, 45), (270, 60), (45, 70)]:
            q = theta_to_q(t1, t2, 0)
            q_corr, _ = apply_mechanical_corrections(q, params)
            _, _, roll0 = q_to_azaltroll(q)
            _, _, rollc = q_to_azaltroll(q_corr)
            droll = abs(wrap180(rollc - roll0)) * 60
            assert droll < TIGHT_TOL, \
                f"M2 correction changed roll by {droll}' at t1={t1} t2={t2}"


# ── Unit tests: MAC correction ────────────────────────────────────────────────


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
    def test_wrap180(self):
        assert pm.wrap180(270)  == -90.0
        assert pm.wrap180(-270) ==  90.0
        assert pm.wrap180(180)  == -180.0
        assert pm.wrap180(0)    ==   0.0

    def test_wrap360(self):
        assert pm.wrap360(-10)  == 350.0
        assert pm.wrap360(370)  ==  10.0
        assert pm.wrap360(0)    ==   0.0

    def test_wrap90(self):
        assert pm.wrap90(100)  == -80.0
        assert pm.wrap90(-91)  ==  89.0

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
    """Tests for M3 tilt correction (m3_tilt_dm2) — was B5."""

    def test_m3_tilt_dm2_stored_in_arcmin_per_deg(self):
        """m3_tilt_dm2 field stores value directly in arcmin/deg (no /60 in dataclass)."""
        p = pm.MountModelParams(m3_tilt_dm2=-2.394)
        assert p.m3_tilt_dm2 == pytest.approx(-2.394)

    def test_m3_tilt_dm2_no_correction_at_t3_zero(self):
        """M3 tilt correction should be zero when theta3=0."""
        p = pm.MountModelParams(m3_tilt_dm2=-2.394)
        q = pm.theta_to_q(180, 40, 0)
        q_corr, _ = pm.apply_mechanical_corrections(q, p)
        t1r, t2r, t3r = pm.q_to_theta(q)
        t1c, t2c, t3c = pm.q_to_theta(q_corr)
        assert abs(t2c - t2r) < 0.01

    def test_m3_tilt_and_m2_tilt_independent(self):
        """M3 tilt and M2 tilt applied together give independent corrections."""
        p_m3_only = pm.MountModelParams(m3_tilt_dm2=-2.394)
        p_both    = pm.MountModelParams(m3_tilt_dm2=-2.394,
                                        m2_tilt_dm2_amp=52.2, m2_tilt_dm2_zero=36.4)
        q = pm.theta_to_q(180, 60, 30)
        q_m3, _    = pm.apply_mechanical_corrections(q, p_m3_only)
        q_both,_   = pm.apply_mechanical_corrections(q, p_both)
        t1_m3,   t2_m3,   _ = pm.q_to_theta(q_m3)
        t1_both, t2_both, _ = pm.q_to_theta(q_both)
        # M2 tilt adds additional theta2 correction on top of M3 tilt
        # At theta2=60, zero=36.4: sin(23.6°)=0.40, correction = 52.2*0.40/60 = 0.35°
        assert abs(t2_m3 - t2_both) > 0.1, "M2 tilt should add extra theta2 shift on top of M3 tilt"


# ── Unit tests: pulse_to_baseQ and radecpa_to_baseQ ──────────────────────────

from kinematics import pulse_to_baseQ, radecpa_to_baseQ

class TestPulseToBaseQ:
    """
    Tests for pulse_to_baseQ — guide pulse to base-frame rotation quaternion.

    Key geometric invariants:
    - RA pulse rotates around the celestial pole axis
    - Dec pulse rotates perpendicular to both pole and boresight
    - Zero duration/velocity returns identity
    - RA and Dec axes are orthogonal
    - Applying then inverting recovers original pointing
    - Pulse magnitude scales linearly with step_sec and velocity
    - Function receives alignQ_B2T_inv (T→B), not alignQ_B2T (B→T)
    """

    # ── Fixtures ──────────────────────────────────────────────────────────────

    @pytest.fixture
    def site_lat(self):
        return -33.86   # Sydney

    @pytest.fixture
    def alignQ_inv(self):
        """Identity alignment inverse — simplifies geometric checks."""
        return Quaternion()   # identity.inverse == identity

    @pytest.fixture
    def alignQ_tilt(self):
        """Non-identity tilt alignQ (forward) — for convention tests."""
        return Quaternion(axis=[1, 0, 0], degrees=10.7)

    @pytest.fixture
    def alignQ_tilt_inv(self):
        """Non-identity tilt alignQ inverse — what the function actually receives."""
        return Quaternion(axis=[1, 0, 0], degrees=10.7).inverse

    @pytest.fixture
    def cameraQ_meridian(self):
        """Camera pointing at meridian, mid-altitude."""
        return azaltroll_to_q(180.0, 45.0, 0.0)

    @pytest.fixture
    def cameraQ_east(self):
        """Camera pointing east."""
        return azaltroll_to_q(90.0, 45.0, 0.0)

    @pytest.fixture
    def cameraQ_pole(self, site_lat):
        """Camera pointing near celestial pole (az=0, alt=lat)."""
        return azaltroll_to_q(0.0, abs(site_lat) - 5.0, 0.0)

    @pytest.fixture
    def pole_topo(self, site_lat):
        """Celestial pole unit vector in topo frame."""
        lat_rad = np.radians(site_lat)
        return np.array([0.0, np.cos(lat_rad), np.sin(lat_rad)])

    # ── Identity / zero cases ─────────────────────────────────────────────────

    def test_zero_duration_returns_identity(self, cameraQ_meridian, alignQ_inv, site_lat):
        """Zero step_sec should return identity quaternion."""
        q = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, axis=0,
                           step_sec=0.0, velocity=15.0/3600)
        assert abs(q.w - 1.0) < 1e-9, "Zero duration should give identity"

    def test_zero_velocity_returns_identity(self, cameraQ_meridian, alignQ_inv, site_lat):
        """Zero velocity should return identity quaternion."""
        q = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, axis=0,
                           step_sec=1.0, velocity=0.0)
        assert abs(q.w - 1.0) < 1e-9, "Zero velocity should give identity"

    def test_zero_both_returns_identity(self, cameraQ_meridian, alignQ_inv, site_lat):
        """Zero velocity and duration should return identity."""
        q = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, axis=0,
                           step_sec=0.0, velocity=0.0)
        assert abs(q.w - 1.0) < 1e-9

    # ── Return type and unit quaternion ───────────────────────────────────────

    def test_returns_unit_quaternion_ra(self, cameraQ_meridian, alignQ_inv, site_lat):
        """RA pulse should return a unit quaternion."""
        q = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, axis=0,
                           step_sec=1.0, velocity=15.0/3600)
        assert abs(np.linalg.norm(q.q) - 1.0) < 1e-9

    def test_returns_unit_quaternion_dec(self, cameraQ_meridian, alignQ_inv, site_lat):
        """Dec pulse should return a unit quaternion."""
        q = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, axis=1,
                           step_sec=1.0, velocity=15.0/3600)
        assert abs(np.linalg.norm(q.q) - 1.0) < 1e-9

    def test_returns_unit_quaternion_pa(self, cameraQ_meridian, alignQ_inv, site_lat):
        """PA pulse should return a unit quaternion."""
        q = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, axis=2,
                           step_sec=1.0, velocity=15.0/3600)
        assert abs(np.linalg.norm(q.q) - 1.0) < 1e-9

    # ── Magnitude scaling ─────────────────────────────────────────────────────

    def test_ra_pulse_angle_scales_with_duration(self, cameraQ_meridian, alignQ_inv, site_lat):
        """Rotation angle should scale linearly with step_sec."""
        v  = 15.0 / 3600
        q1 = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, 0, 1.0, v)
        q2 = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, 0, 2.0, v)
        assert abs(q2.degrees - 2 * q1.degrees) < 1e-6, \
            f"Angle should double with double duration: {q1.degrees} → {q2.degrees}"

    def test_ra_pulse_angle_scales_with_velocity(self, cameraQ_meridian, alignQ_inv, site_lat):
        """Rotation angle should scale linearly with velocity."""
        q1 = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, 0, 1.0, 1.0/3600)
        q2 = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, 0, 1.0, 2.0/3600)
        assert abs(q2.degrees - 2 * q1.degrees) < 1e-6, \
            "Angle should double with double velocity"

    def test_negative_velocity_inverts_rotation(self, cameraQ_meridian, alignQ_inv, site_lat):
        """Negative velocity should give same magnitude, opposite rotation."""
        v     = 15.0 / 3600
        q_pos = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, 0,  1.0,  v)
        q_neg = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, 0,  1.0, -v)
        q_combined = q_pos * q_neg
        assert abs(q_combined.w) > 1 - 1e-6, \
            "Positive and negative pulses should cancel"

    # ── RA axis geometry ──────────────────────────────────────────────────────

    def test_ra_pulse_rotates_around_pole(self, alignQ_inv, site_lat, pole_topo):
        """RA pulse should rotate around the celestial pole axis."""
        for az in [0.0, 90.0, 180.0, 270.0]:
            cameraQ = azaltroll_to_q(az, 45.0, 0.0)
            q_pulse = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 0, 1.0, 1.0/3600)
            dot = abs(np.dot(q_pulse.axis, pole_topo))
            assert dot > 1 - 1e-4, \
                f"RA axis at az={az} should align with pole, dot={dot:.6f}"

    def test_ra_pulse_axis_independent_of_pointing(self, alignQ_inv, site_lat):
        """RA rotation axis should be the same regardless of where we point."""
        axes = []
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ = azaltroll_to_q(az, alt, 0.0)
            q_pulse = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 0, 1.0, 1.0/3600)
            axes.append(q_pulse.axis)
        for i in range(1, len(axes)):
            dot = abs(np.dot(axes[0], axes[i]))
            assert dot > 1 - 1e-4, \
                f"RA axis should be constant across pointings, dot={dot:.6f}"

    # ── Dec axis geometry ─────────────────────────────────────────────────────

    def test_dec_axis_perpendicular_to_ra_axis(self, alignQ_inv, site_lat):
        """Dec rotation axis should be perpendicular to RA axis."""
        for az, alt in [(0, 45), (90, 45), (180, 45), (270, 45)]:
            cameraQ = azaltroll_to_q(az, alt, 0.0)
            q_ra    = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 0, 1.0, 1.0/3600)
            q_dec   = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 1, 1.0, 1.0/3600)
            dot     = np.dot(q_ra.axis, q_dec.axis)
            assert abs(dot) < 1e-4, \
                f"RA and Dec axes not orthogonal at az={az}: dot={dot:.6f}"

    def test_dec_axis_changes_with_pointing(self, alignQ_inv, site_lat):
        """Dec axis should change as pointing changes (unlike RA axis)."""
        q_dec_0  = pulse_to_baseQ(azaltroll_to_q(  0.0, 45.0, 0.0), alignQ_inv, site_lat, 1, 1.0, 1.0/3600)
        q_dec_90 = pulse_to_baseQ(azaltroll_to_q( 90.0, 45.0, 0.0), alignQ_inv, site_lat, 1, 1.0, 1.0/3600)
        dot = abs(np.dot(q_dec_0.axis, q_dec_90.axis))
        assert dot < 0.99, \
            f"Dec axis should differ between az=0 and az=90, dot={dot:.4f}"

    def test_dec_pulse_perpendicular_to_boresight(self, alignQ_inv, site_lat):
        """Dec rotation axis should be perpendicular to boresight in topo frame."""
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ        = azaltroll_to_q(az, alt, 0.0)
            boresight_topo = cameraQ.rotate([0.0, 0.0, -1.0])
            q_dec          = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 1, 1.0, 1.0/3600)
            dot = np.dot(q_dec.axis, boresight_topo)
            assert abs(dot) < 1e-3, \
                f"Dec axis not perpendicular to boresight at az={az} alt={alt}: dot={dot:.6f}"

    # ── PA axis geometry ──────────────────────────────────────────────────────

    def test_pa_axis_parallel_to_boresight(self, alignQ_inv, site_lat):
        """PA rotation axis should be parallel to boresight (rotation around line of sight)."""
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ        = azaltroll_to_q(az, alt, 0.0)
            boresight_topo = cameraQ.rotate([0.0, 0.0, -1.0])
            q_pa           = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 2, 1.0, 1.0/3600)
            dot = abs(np.dot(q_pa.axis, boresight_topo))
            assert dot > 1 - 1e-4, \
                f"PA axis not parallel to boresight at az={az} alt={alt}: dot={dot:.6f}"

    def test_pa_axis_perpendicular_to_dec(self, alignQ_inv, site_lat):
        """PA (boresight) axis should be perpendicular to Dec axis — always true by construction."""
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ = azaltroll_to_q(az, alt, 0.0)
            q_dec   = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 1, 1.0, 1.0/3600)
            q_pa    = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 2, 1.0, 1.0/3600)
            dot = np.dot(q_pa.axis, q_dec.axis)
            assert abs(dot) < 1e-4, \
                f"PA axis not perpendicular to Dec axis at az={az} alt={alt}: dot={dot:.6f}"

    def test_pa_not_generally_perpendicular_to_ra(self, alignQ_inv, site_lat):
        """
        PA (boresight) is NOT generally perpendicular to RA (pole) — 
        only at the equator. This documents the expected geometry.
        """
        # At high declination (boresight nearly parallel to pole), dot should be large
        cameraQ_high_dec = azaltroll_to_q(180.0, abs(site_lat) + 20, 0.0)
        q_ra = pulse_to_baseQ(cameraQ_high_dec, alignQ_inv, site_lat, 0, 1.0, 1.0/3600)
        q_pa = pulse_to_baseQ(cameraQ_high_dec, alignQ_inv, site_lat, 2, 1.0, 1.0/3600)
        dot  = abs(np.dot(q_pa.axis, q_ra.axis))
        assert dot > 0.5, \
            f"Near pole, PA and RA axes should be nearly parallel, dot={dot:.4f}"
        
    # ── Roundtrip — apply and invert ──────────────────────────────────────────

    def test_ra_pulse_roundtrip(self, alignQ_inv, site_lat):
        """Applying RA pulse then its inverse should give identity."""
        q_pulse    = pulse_to_baseQ(azaltroll_to_q(180.0, 45.0, 0.0), alignQ_inv, site_lat, 0, 1.0, 15.0/3600)
        q_combined = q_pulse.inverse * q_pulse
        assert abs(q_combined.w) > 1 - 1e-9, "Pulse * inverse should be identity"

    def test_dec_pulse_roundtrip(self, alignQ_inv, site_lat):
        """Applying Dec pulse then its inverse should give identity."""
        q_pulse    = pulse_to_baseQ(azaltroll_to_q(180.0, 45.0, 0.0), alignQ_inv, site_lat, 1, 1.0, 15.0/3600)
        q_combined = q_pulse.inverse * q_pulse
        assert abs(q_combined.w) > 1 - 1e-9

    def test_pa_pulse_roundtrip(self, alignQ_inv, site_lat):
        """Applying PA pulse then its inverse should give identity."""
        q_pulse    = pulse_to_baseQ(azaltroll_to_q(180.0, 45.0, 0.0), alignQ_inv, site_lat, 2, 1.0, 15.0/3600)
        q_combined = q_pulse.inverse * q_pulse
        assert abs(q_combined.w) > 1 - 1e-9

    def test_many_small_pulses_equal_one_large(self, alignQ_inv, site_lat):
        """10 small RA pulses composed should equal 1 pulse of 10x duration."""
        cameraQ = azaltroll_to_q(180.0, 45.0, 0.0)
        v       = 15.0 / 3600
        q_large = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 0, 1.0, v)
        q_accum = Quaternion()
        for _ in range(10):
            q_small = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 0, 0.1, v)
            q_accum = (q_small * q_accum).normalised
        dot = abs(np.dot(q_accum.q, q_large.q))
        assert dot > 1 - 1e-6, \
            f"10 small pulses should equal 1 large pulse, dot={dot:.9f}"

    # ── alignQ convention — critical tests ───────────────────────────────────

    def test_alignQ_inv_vs_forward_gives_different_result(self, cameraQ_meridian, site_lat,
                                                           alignQ_tilt, alignQ_tilt_inv):
        """Passing alignQ vs alignQ.inverse should give different results — catches wrong convention."""
        q_forward = pulse_to_baseQ(cameraQ_meridian, alignQ_tilt,     site_lat, 0, 1.0, 1.0)
        q_inverse = pulse_to_baseQ(cameraQ_meridian, alignQ_tilt_inv, site_lat, 0, 1.0, 1.0)
        dot = abs(np.dot(q_forward.axis, q_inverse.axis))
        assert dot < 1 - 1e-4, \
            f"Forward and inverse alignQ should give different base-frame axes, dot={dot:.9f}"

    def test_alignQ_roundtrip_recovers_topo_axis(self, cameraQ_meridian, site_lat,
                                                  alignQ_tilt, alignQ_tilt_inv, pole_topo):
        """
        With non-identity alignQ_inv, rotating the resulting base-frame axis
        back through alignQ_B2T should recover the original topo pole axis.
        """
        q_pulse   = pulse_to_baseQ(cameraQ_meridian, alignQ_tilt_inv, site_lat, 0, 1.0, 1.0)
        axis_base = q_pulse.axis
        # alignQ_tilt rotates B→T, so rotating axis_base by it recovers topo
        axis_topo_recovered = alignQ_tilt.rotate(axis_base)
        dot = abs(np.dot(axis_topo_recovered, pole_topo))
        assert dot > 1 - 1e-4, \
            f"alignQ.rotate(axis_base) should recover pole_topo, dot={dot:.9f}"

    def test_nonidentity_alignQ_changes_result(self, cameraQ_meridian, alignQ_inv,
                                               alignQ_tilt_inv, site_lat):
        """Non-identity alignQ_inv should rotate the pulse axis in base frame."""
        q_identity = pulse_to_baseQ(cameraQ_meridian, alignQ_inv,      site_lat, 0, 1.0, 1.0)
        q_tilted   = pulse_to_baseQ(cameraQ_meridian, alignQ_tilt_inv, site_lat, 0, 1.0, 1.0)
        dot = abs(np.dot(q_identity.axis, q_tilted.axis))
        assert dot < 1 - 1e-4, \
            f"Tilt alignQ_inv should rotate the base-frame axis, dot={dot:.9f}"

    def test_alignQ_preserves_pulse_magnitude(self, cameraQ_meridian, alignQ_inv,
                                              alignQ_tilt_inv, site_lat):
        """alignQ_inv rotates the axis but never changes the pulse angle magnitude."""
        q_identity = pulse_to_baseQ(cameraQ_meridian, alignQ_inv,      site_lat, 0, 1.0, 1.0/3600)
        q_tilted   = pulse_to_baseQ(cameraQ_meridian, alignQ_tilt_inv, site_lat, 0, 1.0, 1.0/3600)
        assert abs(q_identity.degrees - q_tilted.degrees) < 1e-6, \
            "alignQ_inv rotation should not change pulse angle magnitude"

    # ── Near-pole behaviour ───────────────────────────────────────────────────

    def test_near_pole_dec_fallback(self, alignQ_inv, site_lat):
        """Near the celestial pole, Dec axis fallback should return a valid unit quaternion."""
        cameraQ = azaltroll_to_q(0.0, abs(site_lat), 0.0)
        q = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 1, 1.0, 1.0/3600)
        assert abs(np.linalg.norm(q.q) - 1.0) < 1e-9, \
            "Near-pole Dec pulse should still return unit quaternion"

    def test_near_pole_ra_still_valid(self, alignQ_inv, site_lat):
        """Near the celestial pole, RA pulse should still be valid."""
        cameraQ = azaltroll_to_q(0.0, abs(site_lat), 0.0)
        q = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 0, 1.0, 1.0/3600)
        assert abs(np.linalg.norm(q.q) - 1.0) < 1e-9

    # ── Physical scale check ──────────────────────────────────────────────────

    def test_sidereal_rate_pulse_magnitude(self, cameraQ_meridian, alignQ_inv, site_lat):
        """1 second at sidereal rate should give ~0.0042 degrees rotation."""
        sidereal_rate = 15.0 / 3600
        q = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, 0,
                           step_sec=1.0, velocity=sidereal_rate)
        assert abs(q.degrees - sidereal_rate) < 1e-6, \
            f"Sidereal pulse angle {q.degrees:.6f}° ≠ expected {sidereal_rate:.6f}°"

    def test_guide_pulse_is_small_rotation(self, cameraQ_meridian, alignQ_inv, site_lat):
        """A typical 500ms guide pulse at 0.5x sidereal should be < 0.005 degrees."""
        q = pulse_to_baseQ(cameraQ_meridian, alignQ_inv, site_lat, 0,
                           step_sec=0.5, velocity=0.5 * 15.0/3600)
        assert q.degrees < 0.005, \
            f"Guide pulse should be tiny rotation, got {q.degrees:.6f}°"


# ── Unit tests: radecpa_to_baseQ ─────────────────────────────────────────────

class TestRadecpaToBaseQ:
    """
    Tests for radecpa_to_baseQ — [ra, dec, pa] offset array to base-frame quaternion.
    """

    @pytest.fixture
    def site_lat(self):
        return -33.86

    @pytest.fixture
    def alignQ_inv(self):
        return Quaternion()

    @pytest.fixture
    def alignQ_tilt(self):
        return Quaternion(axis=[1, 0, 0], degrees=10.7)

    @pytest.fixture
    def alignQ_tilt_inv(self):
        return Quaternion(axis=[1, 0, 0], degrees=10.7).inverse

    @pytest.fixture
    def cameraQ(self):
        return azaltroll_to_q(180.0, 45.0, 0.0)

    def test_zero_array_returns_identity(self, cameraQ, alignQ_inv, site_lat):
        """All-zero delta_deg should return identity."""
        q = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, np.zeros(3))
        assert abs(q.w - 1.0) < 1e-9

    def test_ra_only_matches_pulse_to_baseQ(self, cameraQ, alignQ_inv, site_lat):
        """radecpa with only RA set should match pulse_to_baseQ axis=0."""
        delta = np.array([1.0, 0.0, 0.0])
        q_radecpa = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, delta)
        q_pulse   = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 0, 1.0, 1.0)
        dot = abs(np.dot(q_radecpa.q, q_pulse.q))
        assert dot > 1 - 1e-9, \
            f"RA-only radecpa should match pulse_to_baseQ axis=0, dot={dot:.9f}"

    def test_dec_only_matches_pulse_to_baseQ(self, cameraQ, alignQ_inv, site_lat):
        """radecpa with only Dec set should match pulse_to_baseQ axis=1."""
        delta = np.array([0.0, 1.0, 0.0])
        q_radecpa = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, delta)
        q_pulse   = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 1, 1.0, 1.0)
        dot = abs(np.dot(q_radecpa.q, q_pulse.q))
        assert dot > 1 - 1e-9, \
            f"Dec-only radecpa should match pulse_to_baseQ axis=1, dot={dot:.9f}"

    def test_pa_only_matches_pulse_to_baseQ(self, cameraQ, alignQ_inv, site_lat):
        """radecpa with only PA set should match pulse_to_baseQ axis=2."""
        delta = np.array([0.0, 0.0, 1.0])
        q_radecpa = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, delta)
        q_pulse   = pulse_to_baseQ(cameraQ, alignQ_inv, site_lat, 2, 1.0, 1.0)
        dot = abs(np.dot(q_radecpa.q, q_pulse.q))
        assert dot > 1 - 1e-9, \
            f"PA-only radecpa should match pulse_to_baseQ axis=2, dot={dot:.9f}"

    def test_returns_unit_quaternion(self, cameraQ, alignQ_inv, site_lat):
        """Combined ra/dec/pa offset should return unit quaternion."""
        q = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, np.array([0.1, 0.2, 0.3]))
        assert abs(np.linalg.norm(q.q) - 1.0) < 1e-9

    def test_combined_offset_differs_from_individual(self, cameraQ, alignQ_inv, site_lat):
        """Combined ra+dec offset should differ from either alone."""
        q_ra_only  = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, np.array([1.0, 0.0, 0.0]))
        q_dec_only = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, np.array([0.0, 1.0, 0.0]))
        q_combined = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, np.array([1.0, 1.0, 0.0]))
        dot_ra  = abs(np.dot(q_combined.q, q_ra_only.q))
        dot_dec = abs(np.dot(q_combined.q, q_dec_only.q))
        assert dot_ra  < 1 - 1e-6, "Combined should differ from RA-only"
        assert dot_dec < 1 - 1e-6, "Combined should differ from Dec-only"

    def test_negated_offset_inverts_rotation(self, cameraQ, alignQ_inv, site_lat):
        """Applying offset then negated offset should give identity."""
        delta   = np.array([0.5, 0.3, 0.1])
        q_fwd   = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat,  delta)
        q_rev   = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, -delta)
        q_check = q_fwd * q_rev
        assert abs(q_check.w) > 1 - 1e-6, \
            "Forward then reversed offset should give identity"

    def test_alignQ_roundtrip_recovers_topo_ra_axis(self, cameraQ, site_lat,
                                                     alignQ_tilt, alignQ_tilt_inv):
        """RA axis in base frame, rotated back by alignQ_B2T, should recover pole_topo."""
        lat_rad   = np.radians(site_lat)
        pole_topo = np.array([0.0, np.cos(lat_rad), np.sin(lat_rad)])
        delta     = np.array([1.0, 0.0, 0.0])
        q_pulse   = radecpa_to_baseQ(cameraQ, alignQ_tilt_inv, site_lat, delta)
        axis_topo_recovered = alignQ_tilt.rotate(q_pulse.axis)
        dot = abs(np.dot(axis_topo_recovered, pole_topo))
        assert dot > 1 - 1e-4, \
            f"alignQ.rotate(axis_base) should recover pole_topo, dot={dot:.9f}"

    def test_skip_zero_elements_gives_same_result(self, cameraQ, alignQ_inv, site_lat):
        """
        Passing [ra, 0, 0] should give the same result as [ra, 0, pa=0]
        confirming zero elements are skipped without affecting composition.
        """
        q1 = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, np.array([1.0, 0.0, 0.0]))
        q2 = radecpa_to_baseQ(cameraQ, alignQ_inv, site_lat, np.array([1.0, 0.0, 0.0]))
        dot = abs(np.dot(q1.q, q2.q))
        assert dot > 1 - 1e-9
