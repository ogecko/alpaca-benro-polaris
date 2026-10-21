"""
Requirements: PanoGrid panel centres that run past the zenith or a celestial/galactic pole land on the right sky.

A grid's panels are offsets from the anchor in its reference frame (Az/Alt, RA/Dec or Glon/Glat: Polaris
get_panel_azaltroll). A tall grid -- a vertorama, or a galactic pano across the Milky Way -- gives panel centres past
90 in the second coordinate: Alt + 170 is Alt 10 at the opposite azimuth, Glat 100 is Glat 80 at Glon + 180, Dec -100
is Dec -80 at RA + 180. Each panel must end up where its centre really is on the sky, and with the frame on the same
footprint (the camera upside down over the top is the same rectangle: roll is equivalent modulo 180).

The mount stage is modelled as the driver does it: SlewToAltAz goes through RA/Dec (altaz2radec), the tracking
target comes back as Az/Alt (radec2altaz) and reachable_azaltroll maps it onto the mount. Panels whose centre is
above THETA2_MAX (81.5) can only be reached at the limit: the nearest pointing is directly below them.

Driven on a stand-in Polaris (the real pano methods, Config patched, an ephem observer), no hardware.
"""
import math
import os
import sys
from types import MethodType, SimpleNamespace

import ephem
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from config import Config
from polaris import Polaris
from control import SyncManager
from kinematics import reachable_azaltroll, azaltroll_to_q, gamma_to_delta, altitude_to_maxroll, calc_parallactic_angle, THETA2_MAX

SITE_LAT, SITE_LON = -33.86, 151.2
WHEN = '2026/10/8 14:00'                     # UTC; the galactic centre region is up in the west
TOL_DEG = 0.05


# ── stand-in Polaris ────────────────────────────────────────────────────────────────────────────

def stand_in():
    obs = ephem.Observer()
    obs.lat, obs.lon, obs.pressure, obs.date = str(SITE_LAT), str(SITE_LON), 0, WHEN
    obs.epoch = obs.date                       # RA/Dec of date both ways, as the driver's round trip
    p = SimpleNamespace(_observer=obs, _sitelatitude=SITE_LAT)
    for name in ('get_number_of_panels', 'validate_target_panel', 'panel_to_rc', 'get_ref_anchor_position',
                 'get_ref_azaltroll_position', 'get_panel_azaltroll'):
        setattr(p, name, MethodType(getattr(Polaris, name), p))
    # the observer stays at WHEN (Polaris resets it to utcnow on every conversion)
    def radec2altaz(ra_hr, dec):
        body = ephem.FixedBody()
        body._ra, body._dec, body._epoch = math.radians(ra_hr * 15), math.radians(dec), obs.date
        body.compute(obs)
        return math.degrees(body.alt), math.degrees(body.az)
    def altaz2radec(alt, az):
        ra, dec = obs.radec_of(math.radians(az), math.radians(alt))
        return math.degrees(ra) / 15, math.degrees(dec)
    p.radec2altaz, p.altaz2radec = radec2altaz, altaz2radec
    sm = SimpleNamespace(polaris=p)
    sm.pa2roll = MethodType(SyncManager.pa2roll, sm)
    sm.roll2pa = MethodType(SyncManager.roll2pa, sm)
    p._sm = sm
    return p


@pytest.fixture
def grid(monkeypatch):
    """Set up a PanoGrid: grid(rows=, cols=, hstep=, vstep=, ref=, track=, r=(r1, r2, r3)) -> stand-in Polaris."""
    def make(rows, cols, hstep, vstep, ref, track, r, anchor=0, first=2, order=0):
        for k, v in dict(rows=rows, cols=cols, hstep=hstep, vstep=vstep, ref=ref, track=track, anchor=anchor,
                         first=first, order=order, r1=r[0], r2=r[1], r3=r[2]).items():
            monkeypatch.setattr(Config, k, v, raising=False)
        return stand_in()
    return make


def mount_pose(p, az, alt, roll):
    """What the slew ends at: through RA/Dec and back, then onto the mount's reachable range."""
    ra, dec = p.altaz2radec(alt, az)
    alt2, az2 = p.radec2altaz(ra, dec)
    return reachable_azaltroll(az2, alt2, roll)


# ── geometry helpers ────────────────────────────────────────────────────────────────────────────

def frame(az, alt, roll):
    """Camera boresight and up vectors (East, North, Up) for any az/alt/roll, including over the top."""
    q = azaltroll_to_q(az, alt, roll)
    return np.asarray(q.rotate([0, 0, -1]), float), np.asarray(q.rotate([1, 0, 0]), float)


def angle(u, v):
    return math.degrees(math.acos(float(np.clip(u @ v / np.linalg.norm(u) / np.linalg.norm(v), -1, 1))))


def elevation(az, alt):
    return math.degrees(math.asin(frame(az, alt, 0)[0][2]))


def footprint_roll_error(want, got):
    """Rotation about the boresight between two frames, modulo 180 (an upside-down camera has the same footprint)."""
    b, up_w = frame(*want)
    _, up_g = frame(*got)
    ang = angle(up_w - (up_w @ b) * b, up_g - (up_g @ b) * b)
    return min(ang, 180.0 - ang)


def allowed_footprint_error(roll, mount_alt):
    """The least footprint error any reachable roll can have at the mount's alt (roll range shrinks with alt)."""
    d = abs((roll + 90.0) % 180.0 - 90.0)          # the requested roll's nearest 180-equivalent to level
    return max(0.0, d - altitude_to_maxroll(mount_alt))


def expected_pose(az, alt, roll):
    """The panel's own sky pose with alt wrapped over the top: alt 170 at az -> alt 10 at az + 180, roll + 180."""
    a = (alt + 180.0) % 360.0 - 180.0
    if a > 90.0:
        return (az + 180.0) % 360.0, 180.0 - a, roll + 180.0
    if a < -90.0:
        return (az + 180.0) % 360.0, -180.0 - a, roll + 180.0
    return az % 360.0, a, roll


# ── 1. topocentric vertorama ────────────────────────────────────────────────────────────────────

class TestVertoramaOverTheTop:
    """ref 0 (Az/Alt/Roll), Horizon-Locked: one column from the horizon up over the zenith and down the far side."""

    ROWS, VSTEP = 8, 25.0
    ANCHOR_ALT = 10.0 + (ROWS - 1) / 2 * VSTEP          # bottom panel at alt 10, top at 185

    def panels(self, grid, az=100.0):
        p = grid(rows=self.ROWS, cols=1, hstep=40.0, vstep=self.VSTEP, ref=0, track=1, r=(az, self.ANCHOR_ALT, 0.0))
        return [p.get_panel_azaltroll(n) for n in range(1, self.ROWS + 1)], p

    def test_panel_centres_climb_straight_up_the_column(self, grid):
        """Bottom-left first, one column: the grid alts are 10, 35, ... 185 on the anchor's azimuth."""
        poses, _ = self.panels(grid)
        assert [round(alt, 6) for _, alt, _ in poses] == [10.0 + k * self.VSTEP for k in range(self.ROWS)]
        assert all(az == pytest.approx(100.0) for az, _, _ in poses)

    @pytest.mark.parametrize("n", range(1, ROWS + 1))
    def test_reachable_panels_point_at_their_own_sky(self, grid, n):
        """Alt + 135 is Alt 45 at az + 180, Alt 185 is Alt -5 at az + 180: the mount points exactly there."""
        poses, p = self.panels(grid)
        az, alt, roll = poses[n - 1]
        want = expected_pose(az, alt, roll)
        if abs(want[1]) > THETA2_MAX:
            pytest.skip(f"panel {n} (grid alt {alt:.0f}) is in the zenith zone: see the next test")
        got = mount_pose(p, az, alt, roll)
        assert angle(frame(*want)[0], frame(*got)[0]) < TOL_DEG, f"panel {n}: wanted {want}, got {got}"
        assert footprint_roll_error(want, got) < TOL_DEG

    @pytest.mark.parametrize("alt", [85.0, 88.0, 92.0, 95.0])
    def test_panel_in_the_zenith_zone_is_shot_from_the_nearest_reachable_pointing(self, grid, alt):
        """A panel centre above 81.5 (either side of the zenith): mount at the limit directly below it."""
        p = grid(rows=1, cols=1, hstep=40.0, vstep=25.0, ref=0, track=1, r=(100.0, alt, 0.0))
        az, a, roll = p.get_panel_azaltroll(1)
        got = mount_pose(p, az, a, roll)
        elev = elevation(az, a)
        assert got[1] == pytest.approx(THETA2_MAX, abs=TOL_DEG)
        assert angle(frame(az, a, 0)[0], frame(*got)[0]) == pytest.approx(elev - THETA2_MAX, abs=TOL_DEG)

    @pytest.mark.parametrize("roll", [25.0, -40.0, 70.0, 135.0])
    @pytest.mark.parametrize("n", range(1, ROWS + 1))
    def test_rolled_panels_keep_their_footprint_as_far_as_the_roll_range_allows(self, grid, roll, n):
        """Horizon-Locked with a roll: over the top the camera is upside down (same footprint); high panels get the
        reachable roll nearest the requested footprint."""
        p = grid(rows=self.ROWS, cols=1, hstep=40.0, vstep=self.VSTEP, ref=0, track=1,
                 r=(100.0, self.ANCHOR_ALT, roll))
        az, alt, r = p.get_panel_azaltroll(n)
        assert r == pytest.approx(roll)
        want = expected_pose(az, alt, r)
        got = mount_pose(p, az, alt, r)
        if abs(want[1]) <= THETA2_MAX:
            assert angle(frame(*want)[0], frame(*got)[0]) < TOL_DEG
        assert footprint_roll_error(want, (got[0], got[1], got[2])) <= allowed_footprint_error(roll, got[1]) + TOL_DEG, \
            f"panel {n} grid alt {alt:.0f} roll {roll}: mount {got}"


# ── 2. galactic pano across the galactic pole ───────────────────────────────────────────────────

class TestGalacticPanoOverThePole:
    """ref 2 (Glon/Glat/GPA), Milky Way: a column in galactic latitude past b = 90."""

    @pytest.mark.parametrize("l, b, gpa", [
        (20.0, 100.0, 0.0),
        (20.0, 135.0, 15.0),
        (200.0, -110.0, 0.0),
    ])
    def test_glat_past_the_pole_is_the_same_sky_as_glon_plus_180(self, l, b, gpa):
        """(l, 100) and (l + 180, 80) are the same direction, and the frame differs only by 180 deg about it."""
        b2 = 180.0 - b if b > 90 else -180.0 - b
        d1, d2 = gamma_to_delta([l, b, gpa]), gamma_to_delta([(l + 180.0) % 360.0, b2, gpa + 180.0])
        assert angle(boresight_radec(*d1[:2]), boresight_radec(*d2[:2])) < 1e-3
        assert abs((d1[2] - d2[2] + 90.0) % 180.0 - 90.0) < 0.01

    def test_panels_past_the_pole_point_at_their_own_sky(self, grid):
        """A 1 x 5 column from b = 40 in steps of 30 (b 40 ... 160) around l = 0: every panel's mount pointing is the
        panel centre's own direction (or, in the zenith zone, directly below it)."""
        p = grid(rows=5, cols=1, hstep=30.0, vstep=30.0, ref=2, track=3, r=(0.0, 100.0, 0.0))
        for n in range(1, 6):
            az, alt, roll = p.get_panel_azaltroll(n)
            r, c = p.panel_to_rc(n)
            b = 100.0 + (r - 2) * 30.0
            ra, dec, _ = gamma_to_delta([0.0, b, 0.0])
            want_alt, want_az = p.radec2altaz(ra / 15, dec)
            got = mount_pose(p, az, alt, roll)
            err = angle(frame(want_az, want_alt, 0)[0], frame(*got)[0])
            assert err <= max(0.0, want_alt - THETA2_MAX) + TOL_DEG, \
                f"panel {n} (b {b:.0f}): sky ({want_az:.1f}, {want_alt:.1f}) mount ({got[0]:.1f}, {got[1]:.1f})"


# ── 3. equatorial grid across the celestial pole ────────────────────────────────────────────────

class TestGalacticPanoWithGpa:
    """ref 2, Milky Way, with a galactic position angle: the frame keeps the GPA's footprint across b = 90."""

    @pytest.mark.parametrize("gpa", [30.0, -60.0, 100.0])
    def test_panels_keep_the_gpa_footprint(self, grid, gpa):
        p = grid(rows=5, cols=1, hstep=30.0, vstep=30.0, ref=2, track=3, r=(0.0, 100.0, gpa))
        for n in range(1, 6):
            az, alt, roll = p.get_panel_azaltroll(n)
            r, _ = p.panel_to_rc(n)
            b = 100.0 + (r - 2) * 30.0
            l2, b2, g2 = (0.0, b, gpa) if b <= 90.0 else (180.0, 180.0 - b, gpa + 180.0)   # same sky, b <= 90
            ra, dec, pa = gamma_to_delta([l2, b2, g2])
            want_alt, want_az = p.radec2altaz(ra / 15, dec)
            want_roll = pa - calc_parallactic_angle(want_az, want_alt, SITE_LAT)
            got = mount_pose(p, az, alt, roll)
            want = (want_az, want_alt, want_roll)
            assert footprint_roll_error(want, got) <= allowed_footprint_error(want_roll, got[1]) + TOL_DEG, \
                f"panel {n} (b {b:.0f}, gpa {gpa}): wanted roll {want_roll:.1f}, mount {got}"


class TestEquatorialPanoOverThePole:
    """ref 1 (RA/Dec/PA), Celestial: a column in Dec past the south celestial pole (up at this site)."""

    def test_panels_past_the_pole_point_at_their_own_sky(self, grid):
        p = grid(rows=5, cols=1, hstep=20.0, vstep=20.0, ref=1, track=2, r=(5.0, -90.0, 0.0))
        for n in range(1, 6):
            az, alt, roll = p.get_panel_azaltroll(n)
            r, _ = p.panel_to_rc(n)
            dec = -90.0 + (r - 2) * 20.0
            ra_deg, dec_w = (75.0, dec) if dec >= -90.0 else (255.0, -180.0 - dec)
            want_alt, want_az = p.radec2altaz(ra_deg / 15, dec_w)
            got = mount_pose(p, az, alt, roll)
            assert angle(frame(want_az, want_alt, 0)[0], frame(*got)[0]) < TOL_DEG, \
                f"panel {n} (Dec {dec:.0f}): sky ({want_az:.1f}, {want_alt:.1f}) mount ({got[0]:.1f}, {got[1]:.1f})"


def boresight_radec(ra_deg, dec_deg):
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    return np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
