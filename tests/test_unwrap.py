"""
test_unwrap_q_to_theta.py
=========================
Tests for the unwrap() method of LastPosition as used inside q_to_theta.

Background
----------
unwrap() restores the multi-turn winding of theta1 and theta3 after the
core IK (arctan2) strips them to the range (-180, 180].

  N1 = round((last_theta1 - theta1_A_raw) / 360)
  result = theta1_A_raw + N1 * 360

"""

import math
import pytest
import numpy as np
import sys, os

# Allow running from repo root or tests/ folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

from kinematics import  LastPosition, azaltroll_to_theta, theta_to_azaltroll, azaltroll_to_q, q_to_theta


# ─── helpers ──────────────────────────────────────────────────────────────────

def make_lp(t1, t2, t3, z3=None):
    lp = LastPosition(t1=t1, t2=t2, t3=t3, z3=z3)
    return lp


def az_alt_round_trip_ok(az, alt, roll, lp, tol_deg=0.1):
    """Return True when azaltroll → theta → azaltroll is within tol_deg."""
    t1, t2, t3 = azaltroll_to_theta(az, alt, roll, lp)
    if t1 is None:
        return False
    az2, alt2, roll2 = theta_to_azaltroll(t1, t2, t3)
    err_az   = abs((az2  - az  + 180) % 360 - 180)
    err_alt  = abs(alt2  - alt)
    err_roll = abs((roll2 - roll + 180) % 360 - 180)
    return err_az < tol_deg and err_alt < tol_deg and err_roll < tol_deg


def sequential_theta1(positions, start_lp):
    """
    Drive azaltroll_to_theta through a sequence of (az, alt, roll) positions,
    updating lastPos at each step.  Returns list of theta1 values.
    """
    lp = start_lp
    thetas = []
    for az, alt, roll in positions:
        t1, t2, t3 = azaltroll_to_theta(az, alt, roll, lp)
        thetas.append((t1, t2, t3))
        lp.update(t1, t2, t3)
    return thetas, lp


# ─── 1. Basic unwrap correctness ──────────────────────────────────────────────

class TestUnwrapBasicCorrectness:
    """The unwrapped result must be within 180° of last_theta1."""

    def test_zero_wind_no_change(self):
        """When last and raw are the same, unwrap must be a no-op."""
        lp = make_lp(45, 30, 10)
        t1, t2, t3 = lp.unwrap(45, 30, 10)
        assert t1 == pytest.approx(45)
        assert t2 == pytest.approx(30)
        assert t3 == pytest.approx(10)

    def test_t2_is_always_passed_through_unchanged(self):
        """unwrap() only touches t1 and t3 – t2 must come out identical."""
        lp = make_lp(0, 45, 0)
        for t2 in [-8, 0, 30, 60, 83]:
            _, out_t2, _ = lp.unwrap(0, t2, 0)
            assert out_t2 == t2

    @pytest.mark.parametrize("last_t1,t1_raw", [
        (0,     0),      # identity
        (90,    90),     # no-op
        (0,    -90),     # small negative raw
        (360,   0),      # one full positive wind
        (-360,  0),      # one full negative wind
        (720,   0),      # two full winds
        (-720,  0),      # two negative winds
        (45,  -315),     # same physical position, different representation
        (90,    90 - 360),  # equivalent raw
    ])
    def test_result_within_180_of_last(self, last_t1, t1_raw):
        lp = make_lp(last_t1, 45, 0)
        t1, _, _ = lp.unwrap(t1_raw, 45, 0)
        diff = abs(t1 - last_t1)
        assert diff <= 180, (
            f"last_t1={last_t1}, t1_raw={t1_raw} → unwrapped={t1}, "
            f"diff={diff:.1f}° > 180°"
        )


# ─── 2. Reported bug: home → az=0 → alt change ───────────────────────────────

class TestReportedBugScenario:
    """
    Exact sequence from the bug report:
      1. Mount starts at home: z1=0,z2=0,z3=0 → az=180, alt=45, roll=0 → theta1=180
      2. Mount moves to az=0, alt=45, roll=0   → theta1=0
      3. Alt changes (30, 20, …)               → theta1 must stay near 0
    """

    def _run_sequence(self, drift=0.0):
        """
        Run the home → az=0 → alt-sweep sequence.
        drift: simulates sidereal tracking adding drift to theta1 after step 2.
        Returns (theta1_after_step2, theta1_step3, theta1_step4).
        """
        lp = make_lp(t1=180, t2=45, t3=0)

        # Step 1 – home confirmed (no-op: just checks the start state is sane)
        t1_home, _, _ = azaltroll_to_theta(180, 45, 0, lp)
        assert t1_home == pytest.approx(180, abs=0.5), \
            f"Home should give theta1≈180, got {t1_home}"
        lp.update(t1_home, 45, 0)

        # Step 2 – goto az=0
        t1_az0, t2_az0, t3_az0 = azaltroll_to_theta(0, 45, 0, lp)
        lp.update(t1_az0, t2_az0, t3_az0)
        # apply optional simulated tracking drift
        lp.last_theta1 += drift

        # Step 3 – alt change to 30
        t1_alt30, t2_alt30, t3_alt30 = azaltroll_to_theta(0, 30, 0, lp)
        lp.update(t1_alt30, t2_alt30, t3_alt30)

        # Step 4 – alt change to 20
        t1_alt20, t2_alt20, t3_alt20 = azaltroll_to_theta(0, 20, 0, lp)

        return t1_az0, t1_alt30, t1_alt20

    def test_no_drift_alt_changes_keep_theta1_stable(self):
        t1_az0, t1_alt30, t1_alt20 = self._run_sequence(drift=0.0)
        assert t1_az0 == pytest.approx(0, abs=1.0)
        assert abs(t1_alt30 - t1_az0) < 5, \
            f"Alt change from 45→30 caused theta1 jump: {t1_az0:.1f}→{t1_alt30:.1f}"
        assert abs(t1_alt20 - t1_alt30) < 5, \
            f"Alt change from 30→20 caused theta1 jump: {t1_alt30:.1f}→{t1_alt20:.1f}"

    @pytest.mark.parametrize("drift", [0.5, 1.0, 2.0, 5.0])
    def test_small_positive_drift_alt_changes_stable(self, drift):
        """Small sidereal drift should not cause a 360° jump on the next alt change."""
        t1_az0, t1_alt30, t1_alt20 = self._run_sequence(drift=drift)
        assert abs(t1_alt30 - t1_az0 - drift) < 10, (
            f"drift={drift}: after alt change theta1 jumped from {t1_az0:.1f} "
            f"(+{drift}) to {t1_alt30:.1f}  (expected ≈{t1_az0 + drift:.1f})"
        )

    @pytest.mark.xfail(reason="Known bug: drift of ~181 deg triggers unwrap dead zone")
    def test_large_drift_181_triggers_known_bug(self):
        """
        drift=181 puts lastPos.t1 at 181 while the next IK gives t1_raw=0.
        round((181-0)/360) = round(0.503) = 1  →  theta1 = 360 instead of 181.
        This is the exact reported bug – marked xfail so the suite documents it.
        """
        t1_az0, t1_alt30, _ = self._run_sequence(drift=181)
        # With the bug, t1_alt30 = 360 instead of ≈181
        assert abs(t1_alt30 - (t1_az0 + 181)) < 10, \
            f"Expected theta1≈{t1_az0+181:.0f}, got {t1_alt30:.0f}  (bug: jumped to 360)"

    def test_round_trip_az0_alt_sweep(self):
        """FK round-trip must hold throughout the alt sweep."""
        lp = make_lp(180, 45, 0)
        t1, t2, t3 = azaltroll_to_theta(180, 45, 0, lp)
        lp.update(t1, t2, t3)
        t1, t2, t3 = azaltroll_to_theta(0, 45, 0, lp)
        lp.update(t1, t2, t3)
        for alt in [40, 30, 20, 15, 10]:
            assert az_alt_round_trip_ok(0, alt, 0, lp), \
                f"Round-trip failed at az=0, alt={alt}"
            t1, t2, t3 = azaltroll_to_theta(0, alt, 0, lp)
            lp.update(t1, t2, t3)


# ─── 3. Dead-zone boundary tests ──────────────────────────────────────────────

class TestUnwrapDeadZoneBoundary:
    """
    The dead zone is |last_theta1 - theta1_A_raw| mod 360 ≈ 170–190°.
    In this zone round() may select the wrong multiple of 360.
    Tests here document the exact boundary and which values are currently safe.
    """

    # theta1_A_raw is 0 (mount pointing at az=0); vary last_theta1
    @pytest.mark.parametrize("last_t1", list(range(160, 201)))
    def test_dead_zone_170_to_190(self, last_t1):
        """
        When last_theta1 is 170–190 and t1_raw=0, the unwrapped result
        should be within 180° of last_theta1.  
        """
        lp = make_lp(last_t1, 45, 0)
        t1, _, _ = lp.unwrap(0, 45, 0)
        diff = abs(t1 - last_t1)
        assert diff <= 180, (
            f"last_t1={last_t1}: unwrapped={t1:.0f}, diff={diff:.0f}° > 180°  "
            f"(round((last_t1-0)/360) = {round(last_t1/360)})"
        )

    @pytest.mark.parametrize("last_t1,t1_raw,expected_band", [
        (170,  0,   0),    # just outside dead zone, N=0 → unwrapped=0
        (190,  0, 360),    # just outside other side, N=1 → unwrapped=360
        (  0,  0,   0),    # trivial
        (360,  0, 360),    # one full wind
        (720,  0, 720),    # two full winds
        (-360, 0, -360),   # negative wind
    ])
    def test_safe_values_outside_dead_zone(self, last_t1, t1_raw, expected_band):
        """Values comfortably outside the dead zone should unwrap to expected_band."""
        lp = make_lp(last_t1, 45, 0)
        t1, _, _ = lp.unwrap(t1_raw, 45, 0)
        assert t1 == pytest.approx(expected_band, abs=1.0), \
            f"last_t1={last_t1}, t1_raw={t1_raw}: expected≈{expected_band}, got {t1:.1f}"

    @pytest.mark.parametrize("base", [0, 360, 720, -360])
    def test_dead_zone_repeats_every_360(self, base):
        """The dead zone repeats at every multiple of 360."""
        for dead_last in [base + 181, base + 185, base - 181, base - 185]:
            lp = make_lp(dead_last, 45, 0)
            # The closest valid raw is 0 (or base equivalent)
            t1_raw = base % 360 if base >= 0 else -(abs(base) % 360)
            t1, _, _ = lp.unwrap(t1_raw, 45, 0)
            diff = abs(t1 - dead_last)
            assert diff <= 180, (
                f"base={base}, dead_last={dead_last}: diff={diff:.0f}° > 180°"
            )


# ─── 4. Multi-turn accumulation ───────────────────────────────────────────────

class TestMultiTurnAccumulation:
    """
    A continuously tracking mount accumulates theta1.  unwrap() must
    faithfully reconstruct large absolute winding numbers.
    """

    @pytest.mark.parametrize("winds", [1, 2, 3, -1, -2])
    def test_full_rotation_recovers_winding(self, winds):
        """After N full CW/CCW rotations, theta1 must equal 360*N within tolerance."""
        # Start at az=180 (theta1=180) then wind through 360*|winds| degrees
        n_steps = 36  # 10° per step
        step_deg = 360 / n_steps * (1 if winds > 0 else -1)
        total_az_change = 360 * abs(winds)

        lp = make_lp(t1=0, t2=45, t3=0)
        az = 0.0
        for _ in range(n_steps * abs(winds)):
            az = (az + step_deg) % 360
            t1, t2, t3 = azaltroll_to_theta(az, 45, 0, lp)
            lp.update(t1, t2, t3)

        # Final theta1 should be ≈ 360*winds from the start (0)
        expected = 360 * winds
        assert abs(lp.last_theta1 - expected) < 5, (
            f"After {winds} full turns, theta1={lp.last_theta1:.1f}, expected≈{expected}"
        )

    def test_incremental_steps_no_large_jumps(self):
        """Each individual 1° step in az must produce a theta1 change < 2°."""
        lp = make_lp(t1=0, t2=45, t3=0)
        az = 0.0
        for i in range(720):   # two full CW sweeps
            az_new = (az + 1.0) % 360
            t1_old = lp.last_theta1
            t1, t2, t3 = azaltroll_to_theta(az_new, 45, 0, lp)
            lp.update(t1, t2, t3)
            delta = abs(t1 - t1_old)
            assert delta < 5, (
                f"step {i}: az {az:.1f}→{az_new:.1f}, theta1 {t1_old:.1f}→{t1:.1f}  "
                f"(jump={delta:.1f}°)"
            )
            az = az_new

    @pytest.mark.parametrize("start_t1", [350, 355, 359, 360, 361, 365])
    def test_crossing_360_boundary(self, start_t1):
        """Crossing the 0/360 boundary must not cause a ±360 jump in theta1."""
        lp = make_lp(t1=start_t1, t2=45, t3=0)
        # az = 0 corresponds to theta1_A_raw = 0
        t1, _, _ = azaltroll_to_theta(0, 45, 0, lp)
        jump = abs(t1 - start_t1)
        assert jump < 15 or abs(jump - 360) < 15, (
            f"start_t1={start_t1}: theta1 jumped to {t1:.1f} (Δ={t1-start_t1:+.1f}°)"
        )


# ─── 5. Negative winding ──────────────────────────────────────────────────────

class TestNegativeWinding:
    """The motor can wind negatively (CCW).  unwrap() must track negative N."""

    @pytest.mark.parametrize("last_t1", [-10, -90, -180, -350, -370])
    def test_negative_last_t1_small_step(self, last_t1):
        """
        With a negative winding, a small move must stay within 5° of last_t1.
        Use FK to find the az that corresponds to last_t1 (not a hand-derived formula).
        """
        lp = make_lp(t1=last_t1, t2=45, t3=0)
        # Use FK to find the az that matches last_t1 exactly
        az_at_last, _, _ = theta_to_azaltroll(last_t1, 45, 0)
        # Round-trip: q_to_theta from that same az must recover last_t1
        t1, _, _ = azaltroll_to_theta(az_at_last, 45, 0, lp)
        diff = abs(t1 - last_t1)
        diff = min(diff, 360 - diff)
        assert diff < 5, (
            f"last_t1={last_t1}: az={az_at_last:.1f} → theta1={t1:.1f}, diff={diff:.1f}°"
        )

    def test_negative_two_turn_accumulation(self):
        """After two full CCW turns from 0, theta1 should be near -720."""
        lp = make_lp(t1=0, t2=45, t3=0)
        az = 0.0
        for _ in range(720):
            az = (az - 1.0) % 360
            t1, t2, t3 = azaltroll_to_theta(az, 45, 0, lp)
            lp.update(t1, t2, t3)
        assert abs(lp.last_theta1 - (-720)) < 10, \
            f"Expected theta1≈-720 after 2 CCW turns, got {lp.last_theta1:.1f}"


# ─── 6. theta3 mirrors theta1 bugs ───────────────────────────────────────────

class TestTheta3UnwrapMirrorsTheta1:
    """
    theta3 is unwrapped with the same round() formula.
    It has the same dead zone around ±180.  Test the parallel behaviour.
    """

    @pytest.mark.parametrize("last_t3,t3_raw", [
        (0,     0),
        (90,   90),
        (360,   0),
        (-360,  0),
    ])
    def test_theta3_safe_cases(self, last_t3, t3_raw):
        lp = make_lp(t1=0, t2=45, t3=last_t3)
        _, _, t3 = lp.unwrap(0, 45, t3_raw)
        diff = abs(t3 - last_t3)
        diff = min(diff, 360 - diff)
        assert diff <= 180, \
            f"theta3: last={last_t3}, raw={t3_raw} → unwrapped={t3:.1f}, diff={diff:.1f}°"

    @pytest.mark.parametrize("last_t3", list(range(171, 190)))
    def test_theta3_dead_zone_documented(self, last_t3):
        """
        theta3 dead zone: last_t3=171..189, t3_raw=0.
        These are the same failure modes as theta1.
        """
        lp = make_lp(t1=0, t2=45, t3=last_t3)
        _, _, t3 = lp.unwrap(0, 45, 0)
        diff = abs(t3 - last_t3)
        diff = min(diff, 360 - diff)
        # Document: the dead zone exists for theta3 too
        assert diff <= 180, (
            f"theta3 dead zone: last_t3={last_t3} → unwrapped={t3:.0f}, diff={diff:.0f}°"
        )


# ─── 7. Sequential move continuity ───────────────────────────────────────────

class TestSequentialMoveContinuity:
    """
    Driving through a sequence of realistic sky positions should never
    produce a single-step theta1 jump larger than the physical step taken.
    """

    def test_az_sweep_no_jumps(self):
        """Full 360° az sweep at fixed alt, 5° steps."""
        lp = make_lp(t1=0, t2=45, t3=0)
        azs = list(range(0, 360, 5))
        thetas, _ = sequential_theta1([(az, 45, 0) for az in azs], lp)
        for i in range(1, len(thetas)):
            d1 = abs(thetas[i][0] - thetas[i-1][0])
            assert d1 < 15, (
                f"step {i}: az {azs[i-1]}→{azs[i]}, "
                f"theta1 {thetas[i-1][0]:.1f}→{thetas[i][0]:.1f}, Δ={d1:.1f}°"
            )

    def test_alt_sweep_fixed_az_no_jumps(self):
        """Alt sweep 10°→80° at fixed az, 5° steps; theta1 must be near-constant."""
        lp = make_lp(t1=0, t2=45, t3=0)
        alts = list(range(10, 81, 5))
        thetas, _ = sequential_theta1([(0, alt, 0) for alt in alts], lp)
        for i in range(1, len(thetas)):
            d1 = abs(thetas[i][0] - thetas[i-1][0])
            assert d1 < 5, (
                f"alt change {alts[i-1]}→{alts[i]}: "
                f"theta1 {thetas[i-1][0]:.1f}→{thetas[i][0]:.1f}, Δ={d1:.1f}°"
            )

    def test_home_to_north_to_south_no_jumps(self):
        """
        Typical observing arc: home (az=180) → north (az=0) → south (az=180 again).
        No step should produce a theta1 jump > 15°.
        """
        lp = make_lp(t1=180, t2=45, t3=0)
        # Sweep az 180→0 in 15° steps (going CCW: 180,165,…,15,0)
        positions = [(az, 45, 0) for az in range(180, -1, -15)]
        # Then back 0→180
        positions += [(az, 45, 0) for az in range(0, 181, 15)]
        thetas, _ = sequential_theta1(positions, lp)
        for i in range(1, len(thetas)):
            d1 = abs(thetas[i][0] - thetas[i-1][0])
            assert d1 < 20, (
                f"step {i}: theta1 {thetas[i-1][0]:.1f}→{thetas[i][0]:.1f}, Δ={d1:.1f}°"
            )

    @pytest.mark.parametrize("az", [0, 45, 90, 135, 180, 225, 270, 315])
    def test_single_alt_step_at_all_azimuths(self, az):
        """
        A single 5° alt change at any azimuth must not produce a theta1 jump > 10°.
        Catches the bug in the reported scenario at az=0.
        """
        lp = make_lp(t1=az, t2=45, t3=0)   # theta1 ~ az for roll=0
        t1_before, _, _ = azaltroll_to_theta(az, 45, 0, lp)
        lp.update(t1_before, 45, 0)
        t1_after, _, _ = azaltroll_to_theta(az, 40, 0, lp)
        d1 = abs(t1_after - t1_before)
        assert d1 < 10, (
            f"az={az}: alt 45→40 caused theta1 jump {t1_before:.1f}→{t1_after:.1f} "
            f"(Δ={d1:.1f}°)"
        )


# ─── 8. FK round-trip ─────────────────────────────────────────────────────────

class TestFKRoundTrip:
    """
    azaltroll → theta → azaltroll must recover the original coordinates
    for representative sky positions.
    """

    @pytest.mark.parametrize("az,alt,roll", [
        (0,   45, 0),    (90,  45, 0),   (180, 45, 0),   (270, 45, 0),
        (0,   10, 0),    (0,   70, 0),   (45,  30, 0),   (315, 60, 0),
        (0,   45, 20),   (0,   45, -20), (90,  45, 30),
    ])
    def test_round_trip_standard_positions(self, az, alt, roll):
        lp = make_lp(t1=az, t2=alt, t3=roll)
        assert az_alt_round_trip_ok(az, alt, roll, lp), \
            f"Round-trip failed for az={az}, alt={alt}, roll={roll}"

    def test_round_trip_after_az0_goto(self):
        """After goto to az=0 (from home at az=180), round-trip must still hold."""
        lp = make_lp(t1=180, t2=45, t3=0)
        t1, t2, t3 = azaltroll_to_theta(0, 45, 0, lp)
        lp.update(t1, t2, t3)
        assert az_alt_round_trip_ok(0, 45, 0, lp)
        assert az_alt_round_trip_ok(0, 30, 0, lp)
        assert az_alt_round_trip_ok(0, 20, 0, lp)

    def test_round_trip_sequential_alt_sweep(self):
        """Sequential alt changes from 45→10 after a home→az=0 goto."""
        lp = make_lp(t1=180, t2=45, t3=0)
        t1, t2, t3 = azaltroll_to_theta(180, 45, 0, lp)
        lp.update(t1, t2, t3)
        t1, t2, t3 = azaltroll_to_theta(0, 45, 0, lp)
        lp.update(t1, t2, t3)
        for alt in [40, 35, 30, 25, 20, 15, 10]:
            assert az_alt_round_trip_ok(0, alt, 0, lp), \
                f"Round-trip failed at az=0, alt={alt}"
            t1, t2, t3 = azaltroll_to_theta(0, alt, 0, lp)
            lp.update(t1, t2, t3)


# ─── 9. theta1 / theta3 consistency ──────────────────────────────────────────

class TestTheta1Theta3Consistency:
    """
    theta1 and theta3 are coupled through the FK equations.
    After an unwrap, FK(theta1, theta2, theta3) must reproduce the
    original azaltroll to within rounding.
    """

    @pytest.mark.parametrize("az,alt,roll", [
        (0, 45, 0), (90, 45, 0), (180, 45, 0), (270, 45, 0),
        (0, 45, 30), (90, 30, -15),
    ])
    def test_fk_ik_consistency(self, az, alt, roll):
        """IK then FK must recover the original az/alt/roll."""
        lp = make_lp(t1=az, t2=alt, t3=roll)
        t1, t2, t3 = azaltroll_to_theta(az, alt, roll, lp)
        assert t1 is not None
        az2, alt2, roll2 = theta_to_azaltroll(t1, t2, t3)
        assert abs((az2  - az  + 180) % 360 - 180) < 0.5
        assert abs(alt2  - alt)                      < 0.5
        assert abs((roll2 - roll + 180) % 360 - 180) < 0.5

    def test_theta1_theta3_sum_preserved_at_az0(self):
        """
        At az=0, roll=0, the sum theta1+theta3 should be constant regardless of alt
        (since changing alt at fixed az and roll=0 adjusts only theta2).
        """
        lp = make_lp(t1=0, t2=45, t3=0)
        t1_ref, t2_ref, t3_ref = azaltroll_to_theta(0, 45, 0, lp)
        lp.update(t1_ref, t2_ref, t3_ref)
        sum_ref = t1_ref + t3_ref
        for alt in [40, 30, 20, 10]:
            t1, t2, t3 = azaltroll_to_theta(0, alt, 0, lp)
            assert abs((t1 + t3) - sum_ref) < 2, (
                f"alt={alt}: theta1+theta3={t1+t3:.2f}, expected≈{sum_ref:.2f}"
            )
            lp.update(t1, t2, t3)



# ─── Run directly ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))