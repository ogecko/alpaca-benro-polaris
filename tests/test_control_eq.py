"""
Requirements: equatorial (wedge) mode proof of concept.

On a wedge that tilts the M1 axis onto the visible celestial pole, tracking any star is M1-only at the sidereal rate
(M2 and M3 hold still, field rotation included), the reachable Dec follows sin(dec_p) = cos(theta3) sin(theta2), and
the far side of the equator needs |theta3| > 90. A level mount tracking the same star moves all three motors.

Sky positions come from ephem (refraction off), independent of the driver's own frames, so these also check that the
wedge really puts M1 on the axis the sky turns about. The motor angles come from the driver's own IK (q_to_theta)
with the wedge as alignQ_B2T. Pure kinematics, no hardware.
"""
import math
import os
import sys

import ephem
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from quaternion import Q as Quaternion
from kinematics import theta_to_q, q_to_theta, LastPosition, vector_to_az_alt, azalt_to_vector, THETA2_MAX
from control_eq import (celestial_pole_topo, wedge_alignQ_B2T, theta_to_pole_dec, min_abs_theta3_for_dec,
                        THETA2_MIN, SIDEREAL_RATE_ARCSEC_S)

SITE_LAT, SITE_LON = -33.655, 151.2          # the 2026-10-08 session's site
START = ephem.Date('2026/10/09 14:00:00')    # UTC, ~midnight local
HOURS, STEP_MIN = 4, 15
ARCSEC = 1 / 3600


def observer(date):
    obs = ephem.Observer()
    obs.lat, obs.long = math.radians(SITE_LAT), math.radians(SITE_LON)
    obs.pressure = 0                         # no refraction: pure geometry
    obs.epoch = ephem.J2000
    obs.date = date
    return obs


def topo_vector(radec, date):
    body = ephem.FixedBody()
    body._ra, body._dec, body._epoch = radec[0], radec[1], ephem.J2000
    body.compute(observer(date))
    return azalt_to_vector(math.degrees(body.az), math.degrees(body.alt))


def camera_q(bore, up_point):
    """Camera->topocentric quaternion from the boresight and a second sky point above it (camera -z = boresight,
    +x = up, +y = left)."""
    z = -bore
    x = up_point - np.dot(up_point, bore) * bore
    x /= np.linalg.norm(x)
    return Quaternion(matrix=np.column_stack([x, np.cross(z, x), z]))


def sky_points(theta, alignQ, date):
    """J2000 RA/Dec of the boresight and of a point 5 deg above it, for the motor pose theta at date: fixes a
    star field (pointing and orientation) to track. The 5 deg lever keeps ephem's ~0.01" position rounding from
    showing up as arcseconds of field rotation."""
    q = alignQ * theta_to_q(*theta)
    bore, up = np.array(q.rotate([0, 0, -1])), np.array(q.rotate([1, 0, 0]))
    obs = observer(date)
    points = []
    for v in (bore, bore + math.tan(math.radians(5.0)) * up):
        az, alt = vector_to_az_alt(v)
        points.append(obs.radec_of(math.radians(az), math.radians(alt)))
    return points


def track(points, alignQ, theta0):
    """Motor angles (deg) from the driver's IK every STEP_MIN while the star field drifts for HOURS."""
    lp = LastPosition(*theta0)
    thetas = []
    for k in range(HOURS * 60 // STEP_MIN + 1):
        date = ephem.Date(START + k * STEP_MIN * ephem.minute)
        q = camera_q(*(topo_vector(p, date) for p in points))
        theta = q_to_theta(alignQ.inverse * q, lp)
        lp.update(*theta)
        thetas.append(theta)
    return np.array(thetas)


WEDGE = wedge_alignQ_B2T(SITE_LAT)


class TestWedge:

    @pytest.mark.parametrize("lat, pole_az", [(-33.655, 180.0), (51.5, 0.0)])
    def test_m1_axis_points_at_visible_pole(self, lat, pole_az):
        az, alt = vector_to_az_alt(wedge_alignQ_B2T(lat).rotate([0, 0, 1]))
        assert alt == pytest.approx(abs(lat), abs=1e-9)
        assert az == pytest.approx(pole_az, abs=1e-9)

    @pytest.mark.parametrize("theta0", [
        (30.0, 36.0, 0.0),        # NGC1365-like, Dec -36: M2 sets Dec, M3 at 0
        (-40.0, 60.0, 25.0),      # M3 off 0 for framing: still M1-only
        (10.0, 75.0, 130.0),      # far side of the equator, Dec ~ +38: camera swung past the M2 arm
    ])
    def test_tracking_is_m1_only_at_sidereal_rate(self, theta0):
        thetas = track(sky_points(theta0, WEDGE, START), WEDGE, theta0)
        assert np.ptp(thetas[:, 1]) < 1 * ARCSEC
        assert np.ptp(thetas[:, 2]) < 2 * ARCSEC
        rate = np.abs(np.diff(thetas[:, 0])) * 3600 / (STEP_MIN * 60)
        assert rate == pytest.approx(SIDEREAL_RATE_ARCSEC_S, rel=1e-4)

    @pytest.mark.parametrize("theta0", [(30.0, 36.0, 0.0), (10.0, 75.0, 130.0)])
    def test_tracked_dec_matches_formula(self, theta0):
        (_, dec), _ = sky_points(theta0, WEDGE, START)
        assert -math.degrees(dec) == pytest.approx(theta_to_pole_dec(theta0[1], theta0[2]), abs=0.2)  # J2000 vs pole of date

    def test_level_mount_moves_all_three_motors(self):
        level, theta0 = Quaternion(1, 0, 0, 0), (150.0, 40.0, 0.0)  # SSE, alt 40, roll 0: a Dec ~ -70 star field
        thetas = track(sky_points(theta0, level, START), level, theta0)
        assert all(np.ptp(thetas[:, i]) > 1.0 for i in range(3))


class TestReach:

    @pytest.mark.parametrize("theta2", [-8.0, 10.0, 36.0, 60.0, THETA2_MAX])
    @pytest.mark.parametrize("theta3", [-170.0, -95.0, -30.0, 0.0, 45.0, 120.0, 180.0])
    def test_pole_dec_formula(self, theta2, theta3):
        bore = (WEDGE * theta_to_q(0.0, theta2, theta3)).rotate([0, 0, -1])
        dec_p = math.degrees(math.asin(np.dot(bore, celestial_pole_topo(SITE_LAT))))
        assert dec_p == pytest.approx(theta_to_pole_dec(theta2, theta3), abs=1e-9)

    @pytest.mark.parametrize("dec, expected", [
        (-36.0, 0.0), (-81.5, 0.0), (5.0, 0.0), (8.0, 0.0),    # pole side, and just over the equator with theta2 >= -8
        (-85.0, None), (85.0, None),                           # polar caps
    ])
    def test_min_theta3_south(self, dec, expected):
        assert min_abs_theta3_for_dec(dec, SITE_LAT) == expected

    @pytest.mark.parametrize("dec", [10.0, 20.0, 45.0, 80.0])
    def test_far_side_needs_theta3_past_90(self, dec):
        t3 = min_abs_theta3_for_dec(dec, SITE_LAT)
        assert 90.0 < t3 <= 180.0
        assert theta_to_pole_dec(THETA2_MAX, t3) == pytest.approx(-dec, abs=1e-9)

    def test_theta2_limits(self):
        assert (THETA2_MIN, THETA2_MAX) == (-8.0, 81.5)
