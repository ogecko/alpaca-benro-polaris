import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import pytest
import numpy as np
import math
import ephem
from quaternion import Q as Quaternion
from kinematics import (
    calc_equatorial_axes_B, calc_pole_axes_B, calc_galactic_axes_B, calc_galactic_pole_topo,
    azaltroll_to_q, azalt_to_vector,
    GALACTIC_POLE_RA_J2000, GALACTIC_POLE_DEC_J2000,
)

"""
Sign convention reference (each proven exact -- not approximate -- against ephem
or algebraically; see individual test docstrings below):

    axis   pole              negation needed?
    ----   ----------------  -----------------
    ra     celestial pole    no   (+RA at fixed time == +rotation about pole_axis)
    dec    celestial pole    no
    pa     (boresight)       YES  (+PA == -rotation about bore_axis)
    az     zenith            YES  (+Az == -rotation about pole_axis; Az is clockwise,
                                    RA is prograde -- opposite handedness)
    alt    zenith            no
    roll   (boresight)       YES  (same underlying vector as pa/gpa -- pole independent)
    l      galactic pole     no   (same prograde sense as RA)
    b      galactic pole     no
    gpa    (boresight)       YES  (identical vector to roll/pa -- see
                                    test_bore_axis_is_pole_independent)

    SEPARATELY: sidereal TIME advance (not "+RA jog") needs negation about ra_axis
    too, because advancing time at fixed RA/Dec increases Hour Angle, which is
    the OPPOSITE sense to increasing RA. See test_ra_axis_sidereal_time_advance.
"""

FIXED_DATE = '2026/08/10 10:00:00'
SIDEREAL_RATE_RAD_S = 7.292115855e-5


def make_observer(lat_deg, lon_deg, date=FIXED_DATE):
    obs = ephem.Observer()
    obs.lat, obs.long = math.radians(lat_deg), math.radians(lon_deg)
    obs.date = ephem.Date(date)
    return obs


def radec_to_azalt(obs, ra_hr, dec_deg, epoch=None):
    b = ephem.FixedBody()
    b._ra = math.radians(ra_hr * 15)
    b._dec = math.radians(dec_deg)
    b._epoch = epoch if epoch is not None else obs.date
    b.compute(obs)
    return math.degrees(b.az), math.degrees(b.alt)


def lb_to_azalt(obs, l_deg, b_deg):
    gal = ephem.Galactic(math.radians(l_deg), math.radians(b_deg), epoch=ephem.J2000)
    eq = ephem.Equatorial(gal, epoch=ephem.J2000)
    body = ephem.FixedBody()
    body._ra, body._dec, body._epoch = eq.ra, eq.dec, ephem.J2000
    body.compute(obs)
    return math.degrees(body.az), math.degrees(body.alt)


def rodrigues(v, axis, theta):
    axis = axis / np.linalg.norm(axis)
    return (v * math.cos(theta) + np.cross(axis, v) * math.sin(theta)
            + axis * np.dot(axis, v) * (1 - math.cos(theta)))


def qmatch(qa: Quaternion, qb: Quaternion, tol=1e-9):
    return np.allclose(qa.q, qb.q, atol=tol) or np.allclose(qa.q, -qb.q, atol=tol)


LAT, LON = -33.86, 151.20


# ═══════════════════════════════════════════════════════════════════════════
# 1. calc_pole_axes_B must be a bit-exact drop-in for calc_equatorial_axes_B
# ═══════════════════════════════════════════════════════════════════════════

EQUATORIAL_CASES = [
    (-33.86,  90.0,  45.0,   0.0, [0, 0, 1],  0.0),
    (-33.86, 180.0,  10.0, -20.0, [0, 0, 1],  0.0),
    ( 51.5,   45.0,  60.0,  15.0, [0, 0, 1],  0.0),
    ( 51.5,  270.0,   5.0, -90.0, [0, 0, 1],  0.0),
    (  0.0,    0.0,  30.0,   0.0, [0, 0, 1],  0.0),
    (-33.86,  90.0,  45.0,  10.0, [1, 0, 0],  3.5),
    (-33.86, 200.0,  70.0, -45.0, [0, 1, 0], -2.0),
    ( 51.5,  310.0,  85.0,   5.0, [1, 1, 0],  1.0),
    (-33.86, 350.0, -5.0,    0.0, [0, 0, 1],  0.0),
    ( 80.0,   30.0,  75.0,   0.0, [0, 0, 1],  0.0),
    (-80.0,  30.0,   75.0,   0.0, [0, 0, 1],  0.0),
]

@pytest.mark.parametrize("lat, az, alt, roll, align_axis, align_deg", EQUATORIAL_CASES)
def test_pole_axes_matches_equatorial_axes(lat, az, alt, roll, align_axis, align_deg):
    cameraQ = azaltroll_to_q(az, alt, roll)
    alignQ_inv = Quaternion(axis=align_axis, degrees=align_deg)

    ra_old, dec_old, pa_old = calc_equatorial_axes_B(cameraQ, alignQ_inv, lat)
    lat_rad = math.radians(lat)
    ra_new, dec_new, pa_new = calc_pole_axes_B(
        [0.0, math.cos(lat_rad), math.sin(lat_rad)], cameraQ, alignQ_inv)

    assert np.allclose(ra_old, ra_new, atol=1e-9)
    assert np.allclose(dec_old, dec_new, atol=1e-9)
    assert np.allclose(pa_old, pa_new, atol=1e-9)


def test_pole_axes_matches_equatorial_axes_degenerate():
    """Boresight pointing exactly at the celestial pole -- both fns must hit the
    same [1,0,0] fallback identically."""
    for lat in [-45.0, 0.0, 33.86, 80.0]:
        cameraQ = azaltroll_to_q(0.0, lat, 0.0)
        alignQ_inv = Quaternion()
        ra_old, dec_old, pa_old = calc_equatorial_axes_B(cameraQ, alignQ_inv, lat)
        lat_rad = math.radians(lat)
        ra_new, dec_new, pa_new = calc_pole_axes_B(
            [0.0, math.cos(lat_rad), math.sin(lat_rad)], cameraQ, alignQ_inv)
        assert np.allclose(dec_old, [-1.0, 0.0, 0.0], atol=1e-9)
        assert np.allclose(dec_new, [-1.0, 0.0, 0.0], atol=1e-9)
        assert np.allclose(ra_old, ra_new, atol=1e-9)
        assert np.allclose(pa_old, pa_new, atol=1e-9)


@pytest.mark.parametrize("seed", range(20))
def test_pole_axes_matches_equatorial_axes_random(seed):
    rng = np.random.default_rng(seed)
    lat, az, alt, roll = rng.uniform(-80, 80), rng.uniform(0, 360), rng.uniform(-89, 89), rng.uniform(-180, 180)
    align_axis, align_deg = rng.normal(size=3), rng.uniform(-10, 10)

    cameraQ = azaltroll_to_q(az, alt, roll)
    alignQ_inv = Quaternion(axis=align_axis, degrees=align_deg)

    ra_old, dec_old, pa_old = calc_equatorial_axes_B(cameraQ, alignQ_inv, lat)
    lat_rad = math.radians(lat)
    ra_new, dec_new, pa_new = calc_pole_axes_B(
        [0.0, math.cos(lat_rad), math.sin(lat_rad)], cameraQ, alignQ_inv)

    assert np.allclose(ra_old, ra_new, atol=1e-9)
    assert np.allclose(dec_old, dec_new, atol=1e-9)
    assert np.allclose(pa_old, pa_new, atol=1e-9)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Alpha (Az/Alt/Roll) sign convention -- EXACT identity, holds at any step size
# ═══════════════════════════════════════════════════════════════════════════

ALPHA_SIGN_CASES = [
    (90.0,  45.0,   0.0,  0.001),
    (90.0,  45.0,   0.0,  1.0),
    (90.0,  45.0,   0.0, 30.0),
    (200.0, 10.0, -20.0,  0.5),
    (350.0, 70.0,  90.0,  2.0),
    (10.0, -60.0, -170.0, 0.25),
]

@pytest.mark.parametrize("az, alt, roll, eps", ALPHA_SIGN_CASES)
def test_az_axis_sign_is_negated(az, alt, roll, eps):
    """Increasing az by eps == rotating cameraQ by -eps about az_axis. Exact
    identity (azaltroll_to_q's qaz factor is a pure global rotation about
    zenith), holds for any eps -- not just infinitesimal."""
    cameraQ = azaltroll_to_q(az, alt, roll)
    az_axis, _, _ = calc_pole_axes_B([0, 0, 1.0], cameraQ, Quaternion())
    q_pred = Quaternion(axis=az_axis, degrees=-eps) * cameraQ
    assert qmatch(q_pred, azaltroll_to_q(az + eps, alt, roll))


@pytest.mark.parametrize("az, alt, roll, eps", ALPHA_SIGN_CASES)
def test_alt_axis_sign_is_direct(az, alt, roll, eps):
    if alt + eps >= 89:
        pytest.skip("alt+eps too close to zenith")
    cameraQ = azaltroll_to_q(az, alt, roll)
    _, alt_axis, _ = calc_pole_axes_B([0, 0, 1.0], cameraQ, Quaternion())
    q_pred = Quaternion(axis=alt_axis, degrees=+eps) * cameraQ
    assert qmatch(q_pred, azaltroll_to_q(az, alt + eps, roll))


@pytest.mark.parametrize("az, alt, roll, eps", ALPHA_SIGN_CASES)
def test_roll_axis_sign_is_negated(az, alt, roll, eps):
    cameraQ = azaltroll_to_q(az, alt, roll)
    _, _, roll_axis = calc_pole_axes_B([0, 0, 1.0], cameraQ, Quaternion())
    q_pred = Quaternion(axis=roll_axis, degrees=-eps) * cameraQ
    assert qmatch(q_pred, azaltroll_to_q(az, alt, roll + eps))


@pytest.mark.parametrize("seed", range(30))
def test_alpha_axis_signs_random_sweep(seed):
    rng = np.random.default_rng(seed)
    az, alt, roll = rng.uniform(0, 360), rng.uniform(-85, 85), rng.uniform(-170, 170)
    eps = rng.choice([0.001, 0.1, 1.0, 10.0, 45.0])

    cameraQ = azaltroll_to_q(az, alt, roll)
    az_axis, alt_axis, roll_axis = calc_pole_axes_B([0, 0, 1.0], cameraQ, Quaternion())

    assert qmatch(Quaternion(axis=az_axis, degrees=-eps) * cameraQ, azaltroll_to_q(az + eps, alt, roll))
    if alt + eps < 89:
        assert qmatch(Quaternion(axis=alt_axis, degrees=+eps) * cameraQ, azaltroll_to_q(az, alt + eps, roll))
    assert qmatch(Quaternion(axis=roll_axis, degrees=-eps) * cameraQ, azaltroll_to_q(az, alt, roll + eps))


# ═══════════════════════════════════════════════════════════════════════════
# 3. RA/Dec sign convention -- against ephem, at FIXED time
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("ra0, dec0, dRA_deg", [
    (3.85, -9.8, 0.5), (10.0, 31.6, 0.5), (18.0, -60.0, 0.5),
    (0.5, 76.1, 0.05), (12.3, 45.8, 0.05), (21.0, -43.6, 0.05),
])
def test_ra_axis_matches_increasing_ra_at_fixed_time(ra0, dec0, dRA_deg):
    """+eps hours of RA at FIXED TIME == +rotation by eps about ra_axis. NOT the
    same relationship as sidereal time-advance -- see next test."""
    obs = make_observer(LAT, LON)
    az0, alt0 = radec_to_azalt(obs, ra0, dec0)
    v0 = azalt_to_vector(az0, alt0)
    pole_topo = np.array([0.0, math.cos(math.radians(LAT)), math.sin(math.radians(LAT))])

    az1, alt1 = radec_to_azalt(obs, ra0 + dRA_deg / 15.0, dec0)
    v1_true = azalt_to_vector(az1, alt1)
    v1_pred = rodrigues(v0, pole_topo, math.radians(dRA_deg))
    assert np.linalg.norm(v1_pred - v1_true) < 1e-3


@pytest.mark.parametrize("ra0, dec0", [(3.85, -20.0), (10.0, 40.0), (18.0, -60.0), (0.5, 70.0)])
def test_ra_axis_matches_sidereal_time_advance(ra0, dec0):
    """Advancing TIME by dt (RA/Dec FIXED) == rotating by -SIDEREAL_RATE*dt about
    ra_axis. Opposite sign to the previous test: advancing time increases Hour
    Angle, which is the OPPOSITE sense to increasing RA (RA = LST - HA). This is
    the relationship used by PID_Controller.feed_forward's sidereal tracking."""
    obs = make_observer(LAT, LON)
    az0, alt0 = radec_to_azalt(obs, ra0, dec0)
    v0 = azalt_to_vector(az0, alt0)
    pole_topo = np.array([0.0, math.cos(math.radians(LAT)), math.sin(math.radians(LAT))])

    dt = 20.0
    obs.date = ephem.Date(FIXED_DATE) + dt * ephem.second
    az1, alt1 = radec_to_azalt(obs, ra0, dec0, epoch=ephem.Date(FIXED_DATE))
    v1_true = azalt_to_vector(az1, alt1)

    theta = SIDEREAL_RATE_RAD_S * dt
    v1_pred = rodrigues(v0, pole_topo, -theta)
    assert np.linalg.norm(v1_pred - v1_true) < 1e-3


@pytest.mark.parametrize("ra0, dec0, dDec_deg", [
    (12.1, -61.1, 0.5), (5.0, 18.4, 0.5), (19.0, -20.4, 0.5),
    (1.0, 55.0, 0.05), (8.5, -42.8, 0.05), (14.0, 65.5, 0.05),
])
def test_dec_axis_matches_increasing_dec_at_fixed_time(ra0, dec0, dDec_deg):
    """+eps degrees of Dec at fixed time == +rotation by eps about dec_axis."""
    obs = make_observer(LAT, LON)
    az0, alt0 = radec_to_azalt(obs, ra0, dec0)
    v0 = azalt_to_vector(az0, alt0)
    pole_topo = np.array([0.0, math.cos(math.radians(LAT)), math.sin(math.radians(LAT))])

    _, dec_axis, _ = calc_pole_axes_B(pole_topo, azaltroll_to_q(az0, alt0, 0.0), Quaternion())
    az1, alt1 = radec_to_azalt(obs, ra0, dec0 + dDec_deg)
    v1_true = azalt_to_vector(az1, alt1)
    v1_pred = rodrigues(v0, dec_axis, math.radians(dDec_deg))
    assert np.linalg.norm(v1_pred - v1_true) < 1e-3


# ═══════════════════════════════════════════════════════════════════════════
# 4. Galactic (l/b/gpa) sign convention -- against ephem.Galactic
# ═══════════════════════════════════════════════════════════════════════════

def test_galactic_pole_matches_ngp_definition():
    """ephem.Galactic(l=0,b=90) must resolve to the standard NGP: RA 12h51.4m Dec +27.13."""
    gal = ephem.Galactic(0.0, math.radians(90), epoch=ephem.J2000)
    eq = ephem.Equatorial(gal, epoch=ephem.J2000)
    assert abs(math.degrees(eq.ra) - GALACTIC_POLE_RA_J2000) < 0.01
    assert abs(math.degrees(eq.dec) - GALACTIC_POLE_DEC_J2000) < 0.01


@pytest.mark.parametrize("l0, b0, dl_deg", [
    (225.0, 55.6, 0.05), (279.2, -38.5, 0.05), (108.1, 52.3, 1.0),
    (1.9, 45.0, 1.0), (286.9, -4.5, 0.05), (109.1, -31.0, 1.0),
])
def test_l_axis_matches_increasing_l(l0, b0, dl_deg):
    """+eps degrees of galactic longitude == +rotation by eps about l_axis.
    Same prograde sense as RA -- no negation, unlike Az."""
    obs = make_observer(LAT, LON)
    pole_topo = calc_galactic_pole_topo(obs.date, LAT, LON)
    az0, alt0 = lb_to_azalt(obs, l0, b0)
    v0 = azalt_to_vector(az0, alt0)

    az1, alt1 = lb_to_azalt(obs, l0 + dl_deg, b0)
    v1_true = azalt_to_vector(az1, alt1)
    v1_pred = rodrigues(v0, pole_topo, math.radians(dl_deg))
    assert np.linalg.norm(v1_pred - v1_true) < 2e-3


@pytest.mark.parametrize("l0, b0, db_deg", [
    (91.8, -6.6, 0.05), (181.6, 6.4, 0.05), (358.4, 35.1, 1.0),
    (224.0, 58.7, 1.0), (77.5, -40.8, 0.05), (220.5, -54.7, 1.0),
])
def test_b_axis_matches_increasing_b(l0, b0, db_deg):
    """+eps degrees of galactic latitude == +rotation by eps about b_axis."""
    obs = make_observer(LAT, LON)
    pole_topo = calc_galactic_pole_topo(obs.date, LAT, LON)
    az0, alt0 = lb_to_azalt(obs, l0, b0)
    v0 = azalt_to_vector(az0, alt0)
    cameraQ = azaltroll_to_q(az0, alt0, 0.0)
    _, b_axis, _ = calc_pole_axes_B(pole_topo, cameraQ, Quaternion())

    az1, alt1 = lb_to_azalt(obs, l0, b0 + db_deg)
    v1_true = azalt_to_vector(az1, alt1)
    v1_pred = rodrigues(v0, b_axis, math.radians(db_deg))
    assert np.linalg.norm(v1_pred - v1_true) < 2e-3


@pytest.mark.parametrize("seed", range(20))
def test_bore_axis_is_pole_independent(seed):
    """roll_axis / pa_axis / gpa_axis are all the SAME vector (bore_topo is
    computed purely from the boresight, never from pole/perp), so the roll/PA
    negation proof (test_roll_axis_sign_is_negated) covers gpa too -- no
    separate ephem round-trip needed for gpa's sign."""
    rng = np.random.default_rng(seed)
    az, alt, roll = rng.uniform(0, 360), rng.uniform(-85, 85), rng.uniform(-170, 170)
    align_axis, align_deg = rng.normal(size=3), rng.uniform(-5, 5)
    cameraQ = azaltroll_to_q(az, alt, roll)
    alignQ_inv = Quaternion(axis=align_axis, degrees=align_deg)

    obs = make_observer(LAT, LON)
    pole_zenith = np.array([0.0, 0.0, 1.0])
    pole_celestial = np.array([0.0, math.cos(math.radians(LAT)), math.sin(math.radians(LAT))])
    pole_galactic = calc_galactic_pole_topo(obs.date, LAT, LON)

    _, _, bore_alpha = calc_pole_axes_B(pole_zenith, cameraQ, alignQ_inv)
    _, _, bore_equatorial = calc_pole_axes_B(pole_celestial, cameraQ, alignQ_inv)
    _, _, bore_galactic = calc_pole_axes_B(pole_galactic, cameraQ, alignQ_inv)

    assert np.allclose(bore_alpha, bore_equatorial, atol=1e-9)
    assert np.allclose(bore_alpha, bore_galactic, atol=1e-9)