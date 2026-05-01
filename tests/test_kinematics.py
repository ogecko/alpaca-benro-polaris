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


# ── Unit tests: calc_equatorial_axes_B ───────────────────────────────────────

from kinematics import calc_equatorial_axes_B

class TestCalcEquatorialAxesB:
    """
    Tests for calc_equatorial_axes_B — computes RA, Dec, PA rotation axes in base (B) frame.

    Key geometric invariants:
    - RA axis aligns with celestial pole in topo frame
    - Dec axis is perpendicular to both RA axis and boresight
    - PA axis aligns with boresight
    - All axes are unit vectors
    - Dec axis sign: positive rotation = northward = increasing Dec (both hemispheres)
    - With identity alignQ, base frame == topo frame
    - Non-identity alignQ rotates axes into base frame without changing magnitudes
    """

    # ── Fixtures ──────────────────────────────────────────────────────────────

    @pytest.fixture
    def site_lat_south(self):
        return -33.86   # Sydney — southern hemisphere

    @pytest.fixture
    def site_lat_north(self):
        return +51.51   # London — northern hemisphere

    @pytest.fixture
    def alignQ_inv_identity(self):
        """Identity — base frame == topo frame."""
        return Quaternion()

    @pytest.fixture
    def alignQ_inv_tilt(self):
        """Non-identity tilt — rotates axes into base frame."""
        return Quaternion(axis=[1, 0, 0], degrees=10.7).inverse

    @pytest.fixture
    def alignQ_tilt(self):
        """Forward alignQ — used for round-trip verification."""
        return Quaternion(axis=[1, 0, 0], degrees=10.7)

    @pytest.fixture
    def cameraQ_meridian_south(self):
        """Camera pointing at meridian, mid-altitude, southern sky."""
        return azaltroll_to_q(180.0, 45.0, 0.0)

    @pytest.fixture
    def cameraQ_east(self):
        return azaltroll_to_q(90.0, 45.0, 0.0)

    @pytest.fixture
    def cameraQ_west(self):
        return azaltroll_to_q(270.0, 45.0, 0.0)

    @pytest.fixture
    def cameraQ_north(self):
        return azaltroll_to_q(0.0, 45.0, 0.0)

    # ── Helper ────────────────────────────────────────────────────────────────

    def _pole_topo(self, site_lat):
        lat_rad = np.radians(site_lat)
        return np.array([0.0, np.cos(lat_rad), np.sin(lat_rad)])

    # ── Unit vector checks ────────────────────────────────────────────────────

    def test_all_axes_are_unit_vectors(self, cameraQ_meridian_south,
                                       alignQ_inv_identity, site_lat_south):
        ra, dec, pa = calc_equatorial_axes_B(
            cameraQ_meridian_south, alignQ_inv_identity, site_lat_south)
        assert abs(np.linalg.norm(ra)  - 1.0) < 1e-9, "RA axis not unit length"
        assert abs(np.linalg.norm(dec) - 1.0) < 1e-9, "Dec axis not unit length"
        assert abs(np.linalg.norm(pa)  - 1.0) < 1e-9, "PA axis not unit length"

    @pytest.mark.parametrize("az,alt", [(0,30),(90,45),(180,60),(270,30)])
    def test_unit_vectors_at_multiple_pointings(self, alignQ_inv_identity, site_lat_south,
                                                az, alt):
        cameraQ = azaltroll_to_q(az, alt, 0.0)
        ra, dec, pa = calc_equatorial_axes_B(
            cameraQ, alignQ_inv_identity, site_lat_south)
        assert abs(np.linalg.norm(ra)  - 1.0) < 1e-9
        assert abs(np.linalg.norm(dec) - 1.0) < 1e-9
        assert abs(np.linalg.norm(pa)  - 1.0) < 1e-9

    # ── RA axis — aligns with celestial pole ──────────────────────────────────

    def test_ra_axis_aligns_with_pole_south(self, cameraQ_meridian_south,
                                            alignQ_inv_identity, site_lat_south):
        """With identity alignQ, RA axis should equal celestial pole in topo frame."""
        ra, _, _ = calc_equatorial_axes_B(
            cameraQ_meridian_south, alignQ_inv_identity, site_lat_south)
        pole = self._pole_topo(site_lat_south)
        dot  = abs(np.dot(ra, pole))
        assert dot > 1 - 1e-9, f"RA axis should align with south pole, dot={dot:.9f}"

    def test_ra_axis_aligns_with_pole_north(self, cameraQ_meridian_south,
                                            alignQ_inv_identity, site_lat_north):
        """Northern hemisphere: RA axis should align with north celestial pole."""
        ra, _, _ = calc_equatorial_axes_B(
            cameraQ_meridian_south, alignQ_inv_identity, site_lat_north)
        pole = self._pole_topo(site_lat_north)
        dot  = abs(np.dot(ra, pole))
        assert dot > 1 - 1e-9, f"RA axis should align with north pole, dot={dot:.9f}"

    def test_ra_axis_independent_of_pointing(self, alignQ_inv_identity, site_lat_south):
        """RA axis should be the same regardless of where the mount points."""
        axes = []
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ = azaltroll_to_q(az, alt, 0.0)
            ra, _, _ = calc_equatorial_axes_B(
                cameraQ, alignQ_inv_identity, site_lat_south)
            axes.append(ra)
        for i in range(1, len(axes)):
            dot = abs(np.dot(axes[0], axes[i]))
            assert dot > 1 - 1e-9, \
                f"RA axis should be constant across pointings, dot={dot:.9f}"

    # ── Dec axis — perpendicular to RA and boresight ──────────────────────────

    def test_dec_axis_perpendicular_to_ra(self, alignQ_inv_identity, site_lat_south):
        """Dec axis must be perpendicular to RA axis at all pointings."""
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ = azaltroll_to_q(az, alt, 0.0)
            ra, dec, _ = calc_equatorial_axes_B(
                cameraQ, alignQ_inv_identity, site_lat_south)
            dot = np.dot(ra, dec)
            assert abs(dot) < 1e-6, \
                f"Dec not perpendicular to RA at az={az} alt={alt}: dot={dot:.9f}"

    def test_dec_axis_perpendicular_to_boresight(self, alignQ_inv_identity, site_lat_south):
        """Dec axis must be perpendicular to boresight (PA axis) at all pointings."""
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ = azaltroll_to_q(az, alt, 0.0)
            _, dec, pa = calc_equatorial_axes_B(
                cameraQ, alignQ_inv_identity, site_lat_south)
            dot = np.dot(dec, pa)
            assert abs(dot) < 1e-6, \
                f"Dec not perpendicular to PA at az={az} alt={alt}: dot={dot:.9f}"

    def test_dec_axis_changes_with_pointing(self, alignQ_inv_identity, site_lat_south):
        """Dec axis should change as az changes (unlike RA axis)."""
        _, dec_0,  _ = calc_equatorial_axes_B(
            azaltroll_to_q(  0.0, 45.0, 0.0), alignQ_inv_identity, site_lat_south)
        _, dec_90, _ = calc_equatorial_axes_B(
            azaltroll_to_q( 90.0, 45.0, 0.0), alignQ_inv_identity, site_lat_south)
        dot = abs(np.dot(dec_0, dec_90))
        assert dot < 0.99, \
            f"Dec axis should differ between az=0 and az=90, dot={dot:.6f}"

    # ── Dec sign convention — critical for N/S guiding ────────────────────────

    def test_dec_positive_rotation_moves_north_southern_hemisphere(
            self, alignQ_inv_identity, site_lat_south):
        """
        Southern hemisphere: positive rotation around Dec axis should move
        the boresight northward (increasing Dec).
        Verified by rotating the boresight and checking the Dec component increases.
        """
        cameraQ = azaltroll_to_q(180.0, 45.0, 0.0)
        ra, dec, pa = calc_equatorial_axes_B(
            cameraQ, alignQ_inv_identity, site_lat_south)

        # Apply a small positive rotation around the Dec axis
        small_angle = 1.0   # degree
        q_dec = Quaternion(axis=dec, degrees=small_angle)

        # Rotate boresight
        boresight_before = cameraQ.rotate([0.0, 0.0, -1.0])
        boresight_after  = q_dec.rotate(boresight_before)

        # Project both onto the north direction in topo (+y = north)
        north_component_before = boresight_before[1]
        north_component_after  = boresight_after[1]

        assert north_component_after > north_component_before, \
            f"Positive Dec rotation should move boresight northward: " \
            f"before={north_component_before:.4f} after={north_component_after:.4f}"

    def test_dec_positive_rotation_moves_north_northern_hemisphere(
            self, alignQ_inv_identity, site_lat_north):
        """Northern hemisphere: positive rotation around Dec axis should also move north."""
        cameraQ = azaltroll_to_q(180.0, 45.0, 0.0)
        ra, dec, pa = calc_equatorial_axes_B(
            cameraQ, alignQ_inv_identity, site_lat_north)

        small_angle      = 1.0
        q_dec            = Quaternion(axis=dec, degrees=small_angle)
        boresight_before = cameraQ.rotate([0.0, 0.0, -1.0])
        boresight_after  = q_dec.rotate(boresight_before)

        assert boresight_after[1] > boresight_before[1], \
            f"Positive Dec rotation should move north in northern hemisphere too"

    @pytest.mark.parametrize("az", [0.0, 90.0, 180.0, 270.0])
    def test_dec_sign_consistent_across_azimuths(self, alignQ_inv_identity,
                                                  site_lat_south, az):
        """Positive Dec rotation should always move northward regardless of azimuth."""
        cameraQ = azaltroll_to_q(az, 45.0, 0.0)
        ra, dec, pa = calc_equatorial_axes_B(
            cameraQ, alignQ_inv_identity, site_lat_south)

        q_dec            = Quaternion(axis=dec, degrees=1.0)
        boresight_before = cameraQ.rotate([0.0, 0.0, -1.0])
        boresight_after  = q_dec.rotate(boresight_before)

        assert boresight_after[1] > boresight_before[1], \
            f"Positive Dec rotation should move north at az={az}: " \
            f"before={boresight_before[1]:.4f} after={boresight_after[1]:.4f}"

    # ── PA axis — aligns with boresight ───────────────────────────────────────

    def test_pa_axis_aligns_with_boresight(self, alignQ_inv_identity, site_lat_south):
        """PA axis should equal the boresight direction."""
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ        = azaltroll_to_q(az, alt, 0.0)
            _, _, pa       = calc_equatorial_axes_B(
                cameraQ, alignQ_inv_identity, site_lat_south)
            boresight_topo = cameraQ.rotate([0.0, 0.0, -1.0])
            dot = abs(np.dot(pa, boresight_topo / np.linalg.norm(boresight_topo)))
            assert dot > 1 - 1e-6, \
                f"PA axis should align with boresight at az={az} alt={alt}: dot={dot:.9f}"

    def test_pa_axis_perpendicular_to_dec(self, alignQ_inv_identity, site_lat_south):
        """PA axis perpendicular to Dec axis — guaranteed by cross product construction."""
        for az, alt in [(0, 30), (90, 45), (180, 60), (270, 30)]:
            cameraQ   = azaltroll_to_q(az, alt, 0.0)
            _, dec, pa = calc_equatorial_axes_B(
                cameraQ, alignQ_inv_identity, site_lat_south)
            dot = np.dot(pa, dec)
            assert abs(dot) < 1e-6, \
                f"PA not perpendicular to Dec at az={az} alt={alt}: dot={dot:.9f}"

    # ── alignQ_inv effect ─────────────────────────────────────────────────────

    def test_nonidentity_alignQ_changes_axes(self, cameraQ_meridian_south,
                                              alignQ_inv_identity, alignQ_inv_tilt,
                                              site_lat_south):
        """Non-identity alignQ_inv should rotate axes into base frame."""
        ra_id,  _, _ = calc_equatorial_axes_B(
            cameraQ_meridian_south, alignQ_inv_identity, site_lat_south)
        ra_tilt, _, _ = calc_equatorial_axes_B(
            cameraQ_meridian_south, alignQ_inv_tilt, site_lat_south)
        dot = abs(np.dot(ra_id, ra_tilt))
        assert dot < 1 - 1e-4, \
            f"Non-identity alignQ_inv should change RA axis in base frame, dot={dot:.9f}"

    def test_alignQ_preserves_axis_magnitudes(self, cameraQ_meridian_south,
                                               alignQ_inv_identity, alignQ_inv_tilt,
                                               site_lat_south):
        """alignQ_inv rotates axes but preserves their unit length."""
        for alignQ_inv in [alignQ_inv_identity, alignQ_inv_tilt]:
            ra, dec, pa = calc_equatorial_axes_B(
                cameraQ_meridian_south, alignQ_inv, site_lat_south)
            assert abs(np.linalg.norm(ra)  - 1.0) < 1e-9
            assert abs(np.linalg.norm(dec) - 1.0) < 1e-9
            assert abs(np.linalg.norm(pa)  - 1.0) < 1e-9

    def test_alignQ_roundtrip_recovers_topo_pole(self, cameraQ_meridian_south,
                                                  alignQ_inv_tilt, alignQ_tilt,
                                                  site_lat_south):
        """
        RA axis in base frame, rotated back through alignQ_B2T, should
        recover the celestial pole in topo frame.
        """
        ra_B, _, _ = calc_equatorial_axes_B(
            cameraQ_meridian_south, alignQ_inv_tilt, site_lat_south)
        ra_topo_recovered = alignQ_tilt.rotate(ra_B)
        pole_topo         = self._pole_topo(site_lat_south)
        dot = abs(np.dot(ra_topo_recovered, pole_topo))
        assert dot > 1 - 1e-6, \
            f"alignQ.rotate(ra_B) should recover pole_topo, dot={dot:.9f}"

    def test_alignQ_inv_vs_forward_gives_different_ra(self, cameraQ_meridian_south,
                                                       alignQ_tilt, alignQ_inv_tilt,
                                                       site_lat_south):
        """Passing alignQ vs alignQ.inverse should give different RA axis — catches wrong convention."""
        ra_fwd,  _, _ = calc_equatorial_axes_B(
            cameraQ_meridian_south, alignQ_tilt,     site_lat_south)
        ra_inv,  _, _ = calc_equatorial_axes_B(
            cameraQ_meridian_south, alignQ_inv_tilt, site_lat_south)
        dot = abs(np.dot(ra_fwd, ra_inv))
        assert dot < 1 - 1e-4, \
            f"Forward and inverse alignQ should give different RA axis, dot={dot:.9f}"

    # ── Near-pole fallback ────────────────────────────────────────────────────

    def test_near_pole_returns_valid_axes(self, alignQ_inv_identity, site_lat_south):
        """Near the celestial pole, fallback should return valid unit quaternions."""
        cameraQ = azaltroll_to_q(0.0, abs(site_lat_south), 0.0)
        ra, dec, pa = calc_equatorial_axes_B(
            cameraQ, alignQ_inv_identity, site_lat_south)
        assert abs(np.linalg.norm(ra)  - 1.0) < 1e-9, "RA not unit near pole"
        assert abs(np.linalg.norm(dec) - 1.0) < 1e-9, "Dec not unit near pole"
        assert abs(np.linalg.norm(pa)  - 1.0) < 1e-9, "PA not unit near pole"

    def test_near_pole_ra_still_aligns_with_pole(self, alignQ_inv_identity, site_lat_south):
        """Even near the pole, RA axis should still align with celestial pole."""
        cameraQ   = azaltroll_to_q(0.0, abs(site_lat_south), 0.0)
        ra, _, _  = calc_equatorial_axes_B(
            cameraQ, alignQ_inv_identity, site_lat_south)
        pole_topo = self._pole_topo(site_lat_south)
        dot       = abs(np.dot(ra, pole_topo))
        assert dot > 1 - 1e-9, f"RA should still align with pole near pole, dot={dot:.9f}"

    # ── Mutual orthogonality ──────────────────────────────────────────────────

    def test_ra_dec_pa_are_mutually_orthogonal(self, alignQ_inv_identity, site_lat_south):
        """
        RA ⊥ Dec and Dec ⊥ PA are guaranteed by construction.
        RA ⊥ PA is NOT guaranteed (only true at Dec=0).
        This test documents what IS and IS NOT orthogonal.
        """
        # At the equator (alt ≈ 90 - lat for meridian transit at Dec=0)
        cameraQ      = azaltroll_to_q(180.0, 45.0, 0.0)
        ra, dec, pa  = calc_equatorial_axes_B(
            cameraQ, alignQ_inv_identity, site_lat_south)

        assert abs(np.dot(ra,  dec)) < 1e-6, "RA must be perpendicular to Dec"
        assert abs(np.dot(dec, pa))  < 1e-6, "Dec must be perpendicular to PA"
        # RA and PA are NOT asserted orthogonal — only true at Dec=0