"""
Requirements: tracking a target through the unreachable zenith zone (alt above THETA2_MAX = 81.5).

M2 cannot raise the camera above 81.5 deg, so a target that culminates higher passes through a zone the mount can't
reach. While it is there the mount must track at its limit, directly below the target: same azimuth, alt 81.5. That
is the nearest reachable pointing (the error is the target's altitude minus 81.5), and it keeps M1 following the
target's own azimuth, which sweeps the short way through the meridian on the side the target transits (south of the
zenith for Dec < latitude, north for Dec > latitude). Only a pose that has really gone over the top (alt > 90, which
a jog can produce) maps to the opposite azimuth.

Seen 2026-10-09 (NGC1365, Dec -36, site -33.66, culminating at alt 87.7): reachable_azaltroll treated every alt above
81.5 as over the top and flipped the target to az + 180. The mount whipped 180 deg to the north side at 02:42,
followed the mirror image through north (az 288 -> 0 -> 72) instead of through south, whipped back at 04:03 when the
target dropped below 81.5 and ran into M1's anti-windup limit: ~514 deg of M1 travel instead of ~150.

Pure kinematics (reachable_azaltroll on the target's az/alt from ephem), no hardware.
"""
import datetime
import math
import os
import sys

import ephem
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from kinematics import reachable_azaltroll, altitude_to_maxroll, calc_parallactic_angle, THETA2_MAX

SITE_LAT, SITE_LON = -33.655, 151.2          # the 2026-10-08 session's site
NGC1365 = (3.5776912 * 15, -36.0461)         # RA, Dec deg (as the client sent it)
STEP_S = 20


def boresight(az, alt):
    """Unit pointing vector (East, North, Up); valid for any alt, including over the top."""
    az, alt = math.radians(az), math.radians(alt)
    return np.array([math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt)])


def separation(a, b):
    """Great-circle angle (deg) between two (az, alt) pointings."""
    return math.degrees(math.acos(float(np.clip(boresight(*a) @ boresight(*b), -1.0, 1.0))))


def az_step(a, b):
    return abs((b - a + 180.0) % 360.0 - 180.0)


def footprint_error(want, got):
    """Roll difference (deg) between two camera rolls modulo 180: an upside-down frame has the same footprint."""
    return abs((want - got + 90.0) % 180.0 - 90.0)


def best_footprint_error(roll, alt):
    """The least footprint error any reachable roll at alt can have: the requested roll's nearest 180-equivalent to
    level, less the roll range there."""
    return max(0.0, footprint_error(roll, 0.0) - altitude_to_maxroll(alt))


def transit(ra_deg, dec_deg, start=datetime.datetime(2026, 10, 8, 14, 30), hours=4.0, pa=None):
    """The target's (az, alt, requested roll) every STEP_S seconds, and the mount's reachable pose for it. Roll 0, or
    with pa the roll that holds that position angle on the sky (PA - parallactic angle), as celestial tracking does."""
    obs = ephem.Observer()
    obs.lat, obs.lon, obs.pressure = str(SITE_LAT), str(SITE_LON), 0
    body = ephem.FixedBody()
    body._ra, body._dec, body._epoch = math.radians(ra_deg), math.radians(dec_deg), ephem.J2000
    target, mount = [], []
    for s in range(0, int(hours * 3600), STEP_S):
        obs.date = start + datetime.timedelta(seconds=s)
        body.compute(obs)
        az, alt = math.degrees(body.az), math.degrees(body.alt)
        roll = 0.0 if pa is None else (pa - calc_parallactic_angle(az, alt, SITE_LAT) + 180.0) % 360.0 - 180.0
        target.append((az, alt, roll))
        mount.append(reachable_azaltroll(az, alt, roll))
    return np.array(target), np.array(mount)


# ── the reachable pose for a target in the zone ─────────────────────────────────────────────────

class TestZenithZonePose:

    @pytest.mark.parametrize("az", [0.0, 45.0, 108.5, 180.0, 252.7, 359.0])
    @pytest.mark.parametrize("alt", [THETA2_MAX + 0.01, 82.7, 85.0, 87.65, 89.9, 90.0])
    def test_tracks_at_the_limit_directly_below_the_target(self, az, alt):
        """A target between 81.5 and 90: same az, alt 81.5 (not the opposite side of the zenith)."""
        out_az, out_alt, _ = reachable_azaltroll(az, alt, 0.0)
        assert out_alt == pytest.approx(THETA2_MAX, abs=1e-9)
        assert az_step(out_az, az) == pytest.approx(0.0, abs=1e-9)

    @pytest.mark.parametrize("alt", [82.0, 84.0, 86.0, 88.0, 89.5])
    def test_pointing_error_is_only_the_altitude_above_the_limit(self, alt):
        """Nearest reachable pointing: off the target by alt - 81.5, no more."""
        out_az, out_alt, _ = reachable_azaltroll(120.0, alt, 0.0)
        assert separation((out_az, out_alt), (120.0, alt)) == pytest.approx(alt - THETA2_MAX, abs=1e-6)

    @pytest.mark.parametrize("alt, az, expected", [
        (95.0, 100.0, (280.0, 81.5)),      # just over the top: nearest reachable is at the limit, opposite az
        (98.5, 100.0, (280.0, 81.5)),
        (120.0, 100.0, (280.0, 60.0)),
        (170.0, 100.0, (280.0, 10.0)),
    ])
    def test_over_the_top_maps_to_the_opposite_azimuth(self, alt, az, expected):
        """Only alt > 90 is over the top: az + 180, alt 180 - alt (clamped to the limit)."""
        out_az, out_alt, _ = reachable_azaltroll(az, alt, 0.0)
        assert out_az == pytest.approx(expected[0], abs=1e-9)
        assert out_alt == pytest.approx(expected[1], abs=1e-9)

    @pytest.mark.parametrize("roll", [-30.0, 0.0, 30.0])
    def test_roll_is_level_at_the_limit(self, roll):
        """At alt 81.5 the only reachable roll is 0 (both for the zone and for a pose just below it)."""
        _, _, out_roll = reachable_azaltroll(150.0, 86.0, roll)
        assert out_roll == pytest.approx(0.0, abs=1e-6)


# ── a sidereal target through the zone ──────────────────────────────────────────────────────────

class TestZenithTransit:

    def test_ngc1365_2026_10_08_tracks_through_south(self):
        """The night the mount spun: az should trace ~108 -> 180 -> ~252 through south, never via north."""
        target, mount = transit(*NGC1365)
        zone = target[:, 1] > THETA2_MAX
        assert zone.any(), "the target must reach the zone for this test to mean anything"
        entry, exit_ = np.flatnonzero(zone)[[0, -1]]
        assert 100.0 < mount[entry, 0] < 115.0, f"entered the zone at az {mount[entry, 0]:.1f}, expected ~108"
        assert 245.0 < mount[exit_, 0] < 260.0, f"left the zone at az {mount[exit_, 0]:.1f}, expected ~252"
        in_zone = mount[zone]
        assert np.all((in_zone[:, 0] > 90.0) & (in_zone[:, 0] < 270.0)), "the mount went round the north side"
        assert np.any(np.abs(in_zone[:, 0] - 180.0) < 2.0), "never crossed the meridian at south"

    @pytest.mark.parametrize("dec, side", [
        (-36.0461, 'south'),       # NGC1365: culminates at 87.7, 2.4 deg south of the zenith
        (-34.5, 'south'),          # 0.8 deg south of the zenith
        (-31.0, 'north'),          # Dec above the latitude: culminates north of the zenith, az passes 0
        (-29.0, 'north'),
    ])
    def test_az_follows_the_target_the_short_way(self, dec, side):
        """M1 turns no more than the target's own azimuth sweep (well under a full turn) without jumps."""
        target, mount = transit(NGC1365[0], dec)
        steps = np.array([az_step(a, b) for a, b in zip(mount[:-1, 0], mount[1:, 0])])
        target_steps = np.array([az_step(a, b) for a, b in zip(target[:-1, 0], target[1:, 0])])
        assert steps.sum() == pytest.approx(target_steps.sum(), abs=1.0), \
            f"M1 az travel {steps.sum():.0f} deg vs the target's {target_steps.sum():.0f} deg"
        assert steps.sum() < 200.0
        assert steps.max() < 10.0, f"az jumped {steps.max():.0f} deg in {STEP_S} s"
        meridian = 180.0 if side == 'south' else 0.0
        culmination = mount[np.argmax(target[:, 1])]
        assert az_step(culmination[0], meridian) < 5.0, f"culminated at az {culmination[0]:.1f}, expected {side}"

    @pytest.mark.parametrize("dec", [-36.0461, -34.5, -33.7, -31.0])
    def test_never_further_from_the_target_than_the_zone_allows(self, dec):
        """Every step: pointing error = max(0, target alt - 81.5)."""
        target, mount = transit(NGC1365[0], dec)
        for (t_az, t_alt, _), (m_az, m_alt, _) in zip(target, mount):
            allowed = max(0.0, t_alt - THETA2_MAX)
            assert separation((m_az, m_alt), (t_az, t_alt)) <= allowed + 1e-6, \
                f"target ({t_az:.1f}, {t_alt:.2f}) -> mount ({m_az:.1f}, {m_alt:.2f})"

    def test_leaving_the_zone_does_not_jump(self):
        """The 04:03 whip: the step where the target drops back below 81.5 must be as small as its neighbours."""
        target, mount = transit(*NGC1365)
        zone = target[:, 1] > THETA2_MAX
        for edge in (np.flatnonzero(zone)[0], np.flatnonzero(zone)[-1] + 1):
            assert az_step(mount[edge - 1, 0], mount[edge, 0]) < 2.0


# ── holding a position angle (roll != 0) through the zone ───────────────────────────────────────

class TestZenithTransitWithRoll:
    """Celestial tracking holds a PA, so the requested roll (PA - parallactic angle) swings ~180 deg across transit.
    The roll range shrinks to 0 at the limit: the mount must keep the frame as close to the requested footprint as
    the range allows (any 180-equivalent), without flipping the camera back and forth."""

    PAS = [0.0, 30.0, 75.0, 120.0, -60.0]

    @pytest.mark.parametrize("pa", PAS)
    @pytest.mark.parametrize("dec", [-36.0461, -31.0])
    def test_roll_stays_within_the_range_at_its_altitude(self, dec, pa):
        _, mount = transit(NGC1365[0], dec, pa=pa)
        for az, alt, roll in mount:
            assert abs(roll) <= altitude_to_maxroll(alt) + 1e-6, f"roll {roll:.2f} at alt {alt:.2f}"

    @pytest.mark.parametrize("pa", PAS)
    @pytest.mark.parametrize("dec", [-36.0461, -31.0])
    def test_footprint_as_close_as_the_roll_range_allows(self, dec, pa):
        """Each step: the frame's footprint is off the requested one by no more than the roll range forces."""
        target, mount = transit(NGC1365[0], dec, pa=pa)
        for (_, _, want), (_, alt, got) in zip(target, mount):
            assert footprint_error(want, got) <= best_footprint_error(want, alt) + 1e-6, \
                f"requested roll {want:.1f} at alt {alt:.2f}: got {got:.1f}"

    # PA 0 at this target asks for roll -90 (frame perpendicular to level) at alt ~71, where +-max_roll (63) are equally
    # near: a rule that sees only the requested roll must jump between them. Needs the mount's current roll (hysteresis).
    TIE = pytest.mark.xfail(strict=True, reason="requested roll crosses +-90: stateless choice flips the camera; "
                                                "needs the current roll (hysteresis) to keep its side")

    @pytest.mark.parametrize("pa", [pytest.param(0.0, marks=TIE), 30.0, 75.0, 120.0, -60.0])
    def test_roll_moves_smoothly_through_the_zone(self, pa):
        """No camera flips while entering, crossing or leaving the zone: roll steps stay small."""
        target, mount = transit(*NGC1365, pa=pa)
        steps = np.abs(np.diff(mount[:, 2]))
        worst = int(np.argmax(steps))
        assert steps.max() < 10.0, (f"roll jumped {mount[worst, 2]:.1f} -> {mount[worst + 1, 2]:.1f} at target alt "
                                    f"{target[worst + 1, 1]:.2f} (requested {target[worst + 1, 2]:.1f})")

    @pytest.mark.parametrize("pa", PAS)
    def test_az_path_does_not_depend_on_roll(self, pa):
        """Roll never changes where the mount points: same az/alt path as at roll 0."""
        _, level = transit(*NGC1365)
        _, rolled = transit(*NGC1365, pa=pa)
        assert np.allclose(rolled[:, :2], level[:, :2], atol=1e-9)
