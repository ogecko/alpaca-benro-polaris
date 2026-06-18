"""
Tests for reachable_azaltroll() and supporting helpers in kinematics.py

Convention
----------
- Az  : 0–360 (North=0, East=90)
- Alt : -81.5 to +81.5 (horizon=0, zenith=90 nominal but clamped)
- Roll: -81.5 to +81.5 (level=0), range shrinks at high alt
- THETA2_MAX = 81.5°  (hard mechanical limit for both alt and roll axes)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
import math
import pytest
import numpy as np
from kinematics import reachable_azaltroll, altitude_to_maxroll, wrap_to_nearest

THETA2_MAX = 81.5
ABS_TOL    = 1e-6       # degrees, used throughout


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def max_roll(alt):
    return altitude_to_maxroll(abs(alt), THETA2_MAX)

def assert_valid(az, alt, roll, label=""):
    """Assert that a (az, alt, roll) triple satisfies all hard constraints."""
    mr = max_roll(alt)
    assert 0.0 <= az < 360.0,                   f"{label} az={az:.4f} not in [0,360)"
    assert -THETA2_MAX <= alt <= THETA2_MAX,     f"{label} alt={alt:.4f} outside ±{THETA2_MAX}"
    assert -mr - ABS_TOL <= roll <= mr + ABS_TOL, f"{label} roll={roll:.4f} outside ±{mr:.4f} at alt={alt:.4f}"


# ═══════════════════════════════════════════════════════════════════════════════
# altitude_to_maxroll — unit tests for the helper itself
# ═══════════════════════════════════════════════════════════════════════════════

class TestAltitudeToMaxRoll:

    def test_zero_altitude_gives_full_range(self):
        """At alt=0 max roll should equal THETA2_MAX."""
        assert altitude_to_maxroll(0.0) == pytest.approx(THETA2_MAX, abs=ABS_TOL)

    def test_at_theta2_max_alt_roll_is_zero(self):
        """At alt==THETA2_MAX the only reachable roll is 0."""
        assert altitude_to_maxroll(THETA2_MAX) == pytest.approx(0.0, abs=ABS_TOL)

    def test_monotonically_decreasing(self):
        """max_roll should decrease as altitude increases."""
        alts = np.linspace(0, THETA2_MAX, 20)
        rolls = [altitude_to_maxroll(a) for a in alts]
        for i in range(len(rolls) - 1):
            assert rolls[i] >= rolls[i+1] - ABS_TOL, \
                f"Not monotone at alt={alts[i]:.2f}: {rolls[i]:.4f} -> {rolls[i+1]:.4f}"

    def test_negative_alt_treated_symmetrically(self):
        """altitude_to_maxroll is symmetric in alt."""
        for alt in [10, 30, 50, 70]:
            assert altitude_to_maxroll(alt) == pytest.approx(altitude_to_maxroll(-alt), abs=ABS_TOL)

    def test_beyond_theta2_max_returns_zero(self):
        """Alt outside reachable range returns 0."""
        assert altitude_to_maxroll(90.0) == 0.0
        assert altitude_to_maxroll(THETA2_MAX + 1) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# wrap_to_nearest — unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestWrapToNearest:

    @pytest.mark.parametrize("angle, target, expected", [
        (  0,    0,    0),
        (360,    0,    0),
        (-360,   0,    0),
        ( 90,    0,   90),
        (270,    0,  -90),
        (181,    0, -179),
        (-181,   0,  179),
        (370,    0,   10),
        (-370,   0,  -10),
        ( 10,  360,  370),   # nearest to 360 is 370 not 10
        (350,  360,  350),   # already nearest
    ])
    def test_wrap(self, angle, target, expected):
        result = wrap_to_nearest(angle, target)
        assert result == pytest.approx(expected, abs=ABS_TOL), \
            f"wrap_to_nearest({angle}, {target}) = {result:.4f}, expected {expected}"


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — output constraints always hold
# ═══════════════════════════════════════════════════════════════════════════════

class TestOutputConstraints:
    """For any input the output must satisfy the hard mechanical constraints."""

    @pytest.mark.parametrize("az, alt, roll", [
        (  0,    0,   0),
        (359,   45,  30),
        ( 90,  -45, -30),
        (180,   81,   0),
        (270,  -81,   0),
        # Over-range alts
        (  0,  120,   0),
        (  0, -120,   0),
        (  0,  180,   0),
        (  0, -180,   0),
        (  0,  360,   0),
        # Over-range rolls
        ( 90,   30,  120),
        ( 90,   30, -120),
        ( 90,   30,  200),
        # Over-range az
        (400,   30,  20),
        (-90,   30,  20),
        (720,   30,  20),
        # Combined extremes
        (400,  120,  200),
        (-90, -120, -200),
    ])
    def test_output_always_in_range(self, az, alt, roll):
        out_az, out_alt, out_roll = reachable_azaltroll(az, alt, roll)
        assert_valid(out_az, out_alt, out_roll, label=f"in=({az},{alt},{roll})")


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — passthrough for already-valid inputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestPassthrough:
    """Inputs already within mechanical limits should pass through unchanged."""

    @pytest.mark.parametrize("az, alt, roll", [
        (  0,    0,    0),
        ( 90,   45,   30),
        (270,  -45,  -30),
        (180,   60,    0),
        (  0,    0,   81),
        (  0,    0,  -81),
        (359.9, 0,    0),
    ])
    def test_valid_input_unchanged(self, az, alt, roll):
        out_az, out_alt, out_roll = reachable_azaltroll(az, alt, roll)
        assert out_az   == pytest.approx(az,   abs=ABS_TOL), f"az changed: {az} -> {out_az}"
        assert out_alt  == pytest.approx(alt,  abs=ABS_TOL), f"alt changed: {alt} -> {out_alt}"
        assert out_roll == pytest.approx(roll, abs=ABS_TOL), f"roll changed: {roll} -> {out_roll}"


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — alt wrapping / over-the-top flip
# ═══════════════════════════════════════════════════════════════════════════════

class TestAltitudeFlip:
    """Altitudes outside ±81.5 should be mapped to the equivalent pointing."""

    def test_alt_90_plus_30_maps_to_alt_60_opposite_az(self):
        """alt=120 (=90+30) → alt=60, az+=180."""
        az, alt, roll = reachable_azaltroll(90, 120, 0)
        assert alt  == pytest.approx(60.0,  abs=ABS_TOL)
        assert az   == pytest.approx(270.0, abs=ABS_TOL)

    def test_alt_minus_120_maps_to_minus_60_opposite_az(self):
        """alt=-120 → alt=-60, az+=180."""
        az, alt, roll = reachable_azaltroll(90, -120, 0)
        assert alt == pytest.approx(-60.0,  abs=ABS_TOL)
        assert az  == pytest.approx(270.0,  abs=ABS_TOL)

    def test_alt_180_maps_to_zero_opposite_az(self):
        """alt=180 (straight back) → alt=0, az+=180."""
        az, alt, roll = reachable_azaltroll(0, 180, 0)
        assert alt == pytest.approx(0.0,   abs=ABS_TOL)
        assert az  == pytest.approx(180.0, abs=ABS_TOL)

    def test_alt_360_maps_back_to_zero_same_az(self):
        """alt=360 → full rotation, alt=0, az unchanged."""
        az, alt, roll = reachable_azaltroll(45, 360, 0)
        assert alt == pytest.approx(0.0,  abs=ABS_TOL)
        assert az  == pytest.approx(45.0, abs=ABS_TOL)

    def test_alt_flip_carries_roll_flip_of_180(self):
        """
        Flipping over the top accumulates a 180° roll flip,
        so roll=0 in → roll=180 mod ±180 → 0 after normalisation only
        if that 180 is itself reachable. At alt=60 max_roll≈57°, so
        the 180° flip should be further resolved to ~0°.
        """
        az, alt, roll = reachable_azaltroll(0, 120, 0)
        # alt=60 at az=180. The 180° roll flip is not reachable → resolved.
        mr = max_roll(alt)
        assert abs(roll) <= mr + ABS_TOL

    def test_alt_just_above_limit_clamps(self):
        """alt = THETA2_MAX + 0.1 should be handled, not crash."""
        az, alt, roll = reachable_azaltroll(0, THETA2_MAX + 0.1, 0)
        assert -THETA2_MAX <= alt <= THETA2_MAX

    def test_alt_minus_just_below_limit_clamps(self):
        az, alt, roll = reachable_azaltroll(0, -(THETA2_MAX + 0.1), 0)
        assert -THETA2_MAX <= alt <= THETA2_MAX

    @pytest.mark.parametrize("az_in, az_expected", [
        (  0, 180),
        ( 90, 270),
        (180,   0),
        (270,  90),
        (350, 170),
    ])
    def test_az_flip_wraps_correctly(self, az_in, az_expected):
        """az+180 should always land in [0,360)."""
        az, alt, roll = reachable_azaltroll(az_in, 120, 0)
        assert az == pytest.approx(az_expected, abs=ABS_TOL)


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — roll handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestRollHandling:

    def test_roll_90_plus_30_maps_to_minus_60(self):
        """roll=120 (=90+30) → upside-down equivalent roll=-60."""
        az, alt, roll = reachable_azaltroll(0, 30, 120)
        assert roll == pytest.approx(-60.0, abs=ABS_TOL)

    def test_roll_minus_120_maps_to_plus_60(self):
        """roll=-120 → upside-down equivalent roll=+60."""
        az, alt, roll = reachable_azaltroll(0, 30, -120)
        assert roll == pytest.approx(60.0, abs=ABS_TOL)

    def test_roll_180_maps_to_zero(self):
        """roll=180 upside-down → roll=0."""
        az, alt, roll = reachable_azaltroll(0, 0, 180)
        assert roll == pytest.approx(0.0, abs=ABS_TOL)

    def test_roll_minus_180_maps_to_zero(self):
        az, alt, roll = reachable_azaltroll(0, 0, -180)
        assert roll == pytest.approx(0.0, abs=ABS_TOL)

    def test_roll_360_maps_to_zero(self):
        az, alt, roll = reachable_azaltroll(0, 0, 360)
        assert roll == pytest.approx(0.0, abs=ABS_TOL)

    def test_roll_270_maps_to_minus_90_then_clamped(self):
        """roll=270 → nearest is -90, which exceeds max_roll at low alt → clamped."""
        az, alt, roll = reachable_azaltroll(0, 0, 270)
        # -90 is not reachable (max=81.5), upside-down equivalent is +90 also not reachable
        assert abs(roll) <= THETA2_MAX + ABS_TOL

    def test_roll_clamped_when_both_orientations_unreachable(self):
        """Near-90° roll at high alt — neither orientation reachable, clamp expected."""
        az, alt, roll = reachable_azaltroll(0, 75, 89)
        mr = max_roll(75)
        assert abs(roll) <= mr + ABS_TOL

    def test_roll_shrinks_at_high_alt(self):
        """At alt=81 max_roll≈0, so any nonzero roll gets clamped near 0."""
        az, alt, roll = reachable_azaltroll(0, 81, 45)
        mr = max_roll(81)
        assert abs(roll) <= mr + ABS_TOL

    @pytest.mark.parametrize("roll_in, roll_expected", [
        (  0,    0),
        ( 40,   40),
        (-40,  -40),
        ( 81,   81),
        (-81,  -81),
    ])
    def test_small_roll_passthrough_at_zero_alt(self, roll_in, roll_expected):
        """Rolls within ±THETA2_MAX at alt=0 pass through unchanged."""
        az, alt, roll = reachable_azaltroll(90, 0, roll_in)
        assert roll == pytest.approx(roll_expected, abs=ABS_TOL)


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — az normalisation
# ═══════════════════════════════════════════════════════════════════════════════

class TestAzNormalisation:

    @pytest.mark.parametrize("az_in, az_expected", [
        (  0,    0),
        (360,    0),
        (720,    0),
        (-90,  270),
        (400,   40),
        (-400, 320),
        (359.9, 359.9),
    ])
    def test_az_normalised_to_0_360(self, az_in, az_expected):
        az, alt, roll = reachable_azaltroll(az_in, 30, 0)
        assert az == pytest.approx(az_expected, abs=ABS_TOL)


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — boresight equivalence (az priority)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoresightEquivalence:
    """
    When an alt flip occurs the output (az', alt') should point the same
    direction as the input (az, alt) in 3-D space.
    """

    def _boresight(self, az_deg, alt_deg):
        """Unit vector of boresight in topocentric frame (N/E/Up)."""
        az  = math.radians(az_deg)
        alt = math.radians(alt_deg)
        x = math.sin(az) * math.cos(alt)   # East
        y = math.cos(az) * math.cos(alt)   # North
        z = math.sin(alt)                  # Up
        return np.array([x, y, z])

    @pytest.mark.parametrize("az, alt, roll", [
        (  0,  120,  0),
        ( 90,  120,  0),
        (180, -120,  0),
        ( 45,  180,  0),
        (270,  200,  0),
    ])
    def test_boresight_preserved_after_flip(self, az, alt, roll):
        out_az, out_alt, out_roll = reachable_azaltroll(az, alt, roll)
        b_in  = self._boresight(az,     alt)
        b_out = self._boresight(out_az, out_alt)
        dot = np.dot(b_in / np.linalg.norm(b_in), b_out / np.linalg.norm(b_out))
        assert dot == pytest.approx(1.0, abs=1e-4), \
            f"Boresight changed: in=({az},{alt}) out=({out_az:.2f},{out_alt:.2f}) dot={dot:.6f}"


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — combined alt+roll flip scenarios
# ═══════════════════════════════════════════════════════════════════════════════

class TestCombinedFlips:

    def test_alt_flip_and_large_roll(self):
        """
        alt=120, roll=120 — alt flips (alt'=60, az+=180, roll_flip+=180),
        roll_total = 120+180 = 300 → nearest to 0 is -60, which at alt=60
        (max_roll≈57°) is not reachable → upside-down -60-180=-240→+120>57
        → clamp.
        """
        az, alt, roll = reachable_azaltroll(0, 120, 120)
        assert_valid(az, alt, roll, label="alt=120,roll=120")

    def test_no_flip_needed_near_limit(self):
        """alt=81, roll=5 — both within limits, no change."""
        az, alt, roll = reachable_azaltroll(45, 81, 5)
        assert alt  == pytest.approx(81.0, abs=ABS_TOL)
        assert roll == pytest.approx(5.0,  abs=ABS_TOL)

    def test_negative_alt_and_negative_roll(self):
        az, alt, roll = reachable_azaltroll(180, -120, -40)
        assert_valid(az, alt, roll, label="alt=-120,roll=-40")
        assert alt == pytest.approx(-60.0, abs=ABS_TOL)

    def test_az_over_360_and_alt_flip(self):
        """az=450=90, alt=120 → az_after_flip=270, alt=60."""
        az, alt, roll = reachable_azaltroll(450, 120, 0)
        assert az  == pytest.approx(270.0, abs=ABS_TOL)
        assert alt == pytest.approx(60.0,  abs=ABS_TOL)


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — idempotence
# ═══════════════════════════════════════════════════════════════════════════════

class TestIdempotence:
    """Calling reachable_azaltroll twice should give the same result as calling it once."""

    @pytest.mark.parametrize("az, alt, roll", [
        (  0,  120,    0),
        ( 90,  -30,  150),
        (400,   81,   45),
        (  0,  360,    0),
        (270, -120, -120),
    ])
    def test_idempotent(self, az, alt, roll):
        az1, alt1, roll1 = reachable_azaltroll(az, alt, roll)
        az2, alt2, roll2 = reachable_azaltroll(az1, alt1, roll1)
        assert az2   == pytest.approx(az1,   abs=ABS_TOL), f"az not idempotent"
        assert alt2  == pytest.approx(alt1,  abs=ABS_TOL), f"alt not idempotent"
        assert roll2 == pytest.approx(roll1, abs=ABS_TOL), f"roll not idempotent"


# ═══════════════════════════════════════════════════════════════════════════════
# reachable_azaltroll — galactic pano regression cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestGalacticPanoRegressions:
    """
    Representative panel positions from a galactic panorama that originally
    produced unreachable orientations.
    """

    @pytest.mark.parametrize("az, alt, roll, label", [
        ( 45,  70,  60, "high-alt panel"),
        (315,  70, -60, "high-alt symmetric panel"),
        (180,  82,   5, "near-zenith panel"),
        ( 90, -70,  55, "low-alt south panel"),
        (  0,  30, 100, "wide-roll panel"),
    ])
    def test_pano_panel_reachable(self, az, alt, roll, label):
        out_az, out_alt, out_roll = reachable_azaltroll(az, alt, roll)
        assert_valid(out_az, out_alt, out_roll, label=label)