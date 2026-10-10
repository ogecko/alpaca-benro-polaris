"""
Requirements: equatorial (wedge) mode proof of concept.

On a wedge that tilts the M1 axis onto the visible celestial pole, tracking any star is M1-only at the sidereal rate
(M2 and M3 hold still, field rotation included), the reachable Dec follows sin(dec_p) = cos(theta3) sin(theta2), and
the far side of the equator needs |theta3| > 90. A level mount tracking the same star moves all three motors.

Sky positions come from ephem (refraction off), independent of the driver's own frames, so these also check that the
wedge really puts M1 on the axis the sky turns about. The motor angles come from the driver's own IK (q_to_theta)
with the wedge as alignQ_B2T. Pure kinematics, no hardware.
"""
import logging
import math
import os
import sys

import ephem
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from quaternion import Q as Quaternion
from kinematics import (theta_to_q, q_to_theta, q_to_azaltroll, azaltroll_to_q, LastPosition, vector_to_az_alt, azalt_to_vector,
                        wrap180, THETA2_MAX)
from control_eq import (celestial_pole_topo, wedge_alignQ_B2T, theta_to_pole_dec, min_abs_theta3_for_dec,
                        roll_keeping_theta3, goto_roll_for_eq, THETA2_MIN, SIDEREAL_RATE_ARCSEC_S)

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


# ---------------------------------------------------------------------------------------
# advanced_eq_mode in the driver: SyncManager alignment and the control loop (digital twin)
# ---------------------------------------------------------------------------------------
#
# Requirements with advanced_eq_mode on (Polaris on a wedge, M1 on the visible celestial pole):
#   * the setting exists in config.toml and is off by default
#   * before any sync the alignment is the ideal wedge for the site latitude (not identity), whether or not
#     advanced_alignment is on, so gotos are right from the start
#   * a single sync corrects the wedge's small setup error on top of the wedge (the level-mount fallback would
#     treat the 56 deg tilt as the error); two or more syncs let QUEST recover the true base orientation
#   * the control loop applies its reach limits in the mount's own (base) frame, not as if the base were level:
#     wedge poses whose sky alt/roll a level mount can't reach are tracked unchanged
#   * sidereal tracking is M1-only: M2 and M3 hold, M1 runs at the sidereal rate
#   * a goto while tracking completes on target, and keeps M3 where it is (framing) when it can, else the smallest
#     M3 change: M3 at 0 if M2 alone reaches the target, or past 90 deg for the far side of the equator
#   * the meridian is no event: tracking through hour angle 0 is M1-only with no flip or unwind
#   * switching advanced_eq_mode on or off while tracking re-bases the setpoints on the current position: the mount
#     does not slew, and keeps tracking
#   * with advanced_eq_mode off everything is as before (the rest of the test suite, plus the level goto below)


from config import Config, CONFIG_TOML_PATH
from control import SyncManager
from test_sync_manager import Polaris as MockPolaris, mock_config   # noqa: F401  (fixture)
from sim_digital_twin import Twin, LAT as TWIN_LAT
from test_motion_outcomes import tracking_rms, run_goto, radec_sep_arcmin

EQ_TWIN = {"advanced_eq_mode": True, "coordinated_speed_control": True}


def q_angle_arcsec(qa, qb):
    """Rotation angle between two quaternions (arcsec), either sign of the double cover."""
    w = abs(float(np.dot(np.asarray(qa.q), np.asarray(qb.q))))
    return math.degrees(2 * math.acos(min(1.0, w))) * 3600


@pytest.fixture
def eq_config(mock_config):
    mock_config.advanced_eq_mode = True
    mock_config.advanced_sync_guiding = False
    return mock_config


def eq_sync(sm, p, true_B2T, az_b, alt_b, roll_b=0.0):
    """Sync at the base-frame pose az_b/alt_b/roll_b (what the motors report) of a mount whose true base->topo
    rotation is true_B2T."""
    p.update(az_b, alt_b, roll_b)
    v_obs = true_B2T.rotate(azalt_to_vector(az_b, alt_b))
    a_az, a_alt = vector_to_az_alt(v_obs)
    lat = math.radians(p._sitelatitude)
    a_dec = math.degrees(math.asin(np.dot(v_obs, [0.0, math.cos(lat), math.sin(lat)])))
    sm.sync_az_alt(0.0, a_dec, a_az, a_alt)


class TestEqConfig:

    def test_setting_in_config_toml_off_by_default(self):
        Config.load(tomlpath=CONFIG_TOML_PATH, pilotpath="/nonexistent")
        assert Config.advanced_eq_mode is False


class TestEqAlignment:

    def test_level_mode_starts_at_identity(self, mock_config):
        mock_config.advanced_eq_mode = False
        sm = SyncManager(logging.getLogger(), MockPolaris())
        assert q_angle_arcsec(sm.alignQ_B2T, Quaternion(1, 0, 0, 0)) < 1e-6

    @pytest.mark.parametrize("advanced_alignment", [True, False])
    def test_eq_mode_starts_at_the_ideal_wedge(self, eq_config, advanced_alignment):
        eq_config.advanced_alignment = advanced_alignment
        p = MockPolaris()
        sm = SyncManager(logging.getLogger(), p)
        sm.optimize_alignQ_B2T()
        assert q_angle_arcsec(sm.alignQ_B2T, wedge_alignQ_B2T(p._sitelatitude)) < 1e-6
        assert q_angle_arcsec(sm.alignQ_B2T_inv, wedge_alignQ_B2T(p._sitelatitude).inverse) < 1e-6

    @pytest.mark.parametrize("error_axis", [[0, 0, 1], [1, 0, 0]], ids=["az", "lat"])
    def test_single_sync_corrects_on_top_of_the_wedge(self, eq_config, error_axis):
        p = MockPolaris()
        sm = SyncManager(logging.getLogger(), p)
        true_B2T = Quaternion(axis=error_axis, degrees=0.3) * wedge_alignQ_B2T(p._sitelatitude)
        eq_sync(sm, p, true_B2T, 150.0, 40.0)
        for az_b, alt_b in [(150.0, 40.0), (100.0, 30.0), (200.0, 60.0)]:     # the synced pose and two others
            v_true = true_B2T.rotate(azalt_to_vector(az_b, alt_b))
            v_pred = azalt_to_vector(*sm.azalt_polaris2ascom(az_b, alt_b))
            assert math.degrees(math.acos(np.clip(np.dot(v_true, v_pred), -1, 1))) < 0.35   # within the setup error

    def test_quest_recovers_the_true_wedge_orientation(self, eq_config):
        p = MockPolaris()
        sm = SyncManager(logging.getLogger(), p)
        true_B2T = Quaternion(axis=[0.3, 1.0, 0.4], degrees=0.5) * wedge_alignQ_B2T(p._sitelatitude)
        for az_b, alt_b in [(150.0, 40.0), (100.0, 30.0), (200.0, 60.0), (60.0, 20.0)]:
            eq_sync(sm, p, true_B2T, az_b, alt_b)
        assert q_angle_arcsec(sm.alignQ_B2T, true_B2T) < 1.0


def eq_twin(monkeypatch, theta0, seed=0):
    tw = Twin(monkeypatch, config=EQ_TWIN, seed=seed)
    tw.place(theta0)
    tw.start_tracking()
    tw.run(30)
    return tw


EQ_POSES = {                    # wedge motor poses (deg) and whether a level mount's sky-frame limits would clamp them
    "ha-4h_dec-36": (60.0, 36.0, 0.0),        # within the level limits
    "ha-2h_dec-36": (30.0, 36.0, 0.0),        # sky roll -87 beyond the level max roll 69 at alt 65
    "transit_dec-56": (0.0, 56.0, -0.5),      # sky alt 68, roll ~180: beyond the level max roll
    "m3_framing_dec-52": (30.0, 60.0, 25.0),  # M3 turned for framing: sky roll -115
}


class TestEqTracking:

    @pytest.mark.parametrize("pose", EQ_POSES.keys())
    def test_tracking_is_m1_only_and_on_target(self, monkeypatch, pose):
        tw = eq_twin(monkeypatch, EQ_POSES[pose])
        theta_start, ra0, dec0 = tw.theta, tw.polaris.rightascension, tw.polaris.declination
        rms = tracking_rms(tw, seconds=90.0)
        moved = (tw.theta - theta_start) * 3600
        drift = radec_sep_arcmin(ra0, dec0, tw.polaris.rightascension, tw.polaris.declination) * 60
        tw.close()
        assert abs(moved[1]) < 10 and abs(moved[2]) < 10, f"M2/M3 moved {moved[1]:.1f}\" / {moved[2]:.1f}\""
        assert abs(abs(moved[0]) / 90.0 - SIDEREAL_RATE_ARCSEC_S) < 0.02 * SIDEREAL_RATE_ARCSEC_S, \
            f"M1 ran at {abs(moved[0]) / 90.0:.2f}\"/s"
        assert rms < 3.0, f"tracking RMS {rms:.2f}\""
        assert drift < 5.0, f"RA/Dec drifted {drift:.1f}\""

    def test_goto_while_tracking_completes_on_target(self, monkeypatch):
        tw = eq_twin(monkeypatch, EQ_POSES["ha-4h_dec-36"])
        target = (tw.polaris.rightascension + 0.2, tw.polaris.declination - 3.0)    # 3 deg in RA and 3 deg south
        done, _, miss = run_goto(tw, lambda: tw.goto_radec(*target), target_radec=target)
        tw.close()
        assert done is not None and done < 40, f"goto did not complete ({done})"
        assert miss < 60, f"goto finished {miss:.1f}\" from target"


class TestEqGotoRoll:

    @pytest.mark.parametrize("theta", [(30.0, 36.0, 0.0), (-50.0, 60.0, 25.0), (100.0, 20.0, -40.0),
                                       (10.0, 75.0, 130.0), (200.0, -5.0, 0.0)])
    @pytest.mark.parametrize("alignQ", ["wedge", "level"])
    def test_roll_keeping_theta3_round_trips(self, theta, alignQ):
        q = WEDGE if alignQ == "wedge" else Quaternion(1, 0, 0, 0)
        az, alt, roll = q_to_azaltroll(q * theta_to_q(*theta))
        assert wrap180(roll_keeping_theta3(az, alt, theta[2], q) - roll) == pytest.approx(0.0, abs=1e-6)

    def test_roll_keeping_theta3_none_when_m3_cannot_reach(self):
        az, alt, _ = q_to_azaltroll(WEDGE * theta_to_q(30.0, 40.0, 0.0))      # dec_p 40
        assert roll_keeping_theta3(az, alt, 80.0, WEDGE) is None              # at theta3 80, |dec_p| <= 10

    @pytest.mark.parametrize("theta3_now, target, expected_theta3", [
        (25.0, (30.0, 40.0, 25.0), 25.0),        # reachable: M3 kept
        (80.0, (30.0, 40.0, 0.0), 0.0),          # dec_p 40 not reachable at 80: M2 alone, M3 at 0
        (0.0, (30.0, 81.5, 120.0), 120.0),       # far side (dec_p -30): the smallest |theta3| past 90 ...
        (-10.0, (30.0, 81.5, -120.0), -120.0),   # ... on the side M3 is already
    ])
    def test_goto_roll_for_eq_picks_theta3(self, theta3_now, target, expected_theta3):
        az, alt, _ = q_to_azaltroll(WEDGE * theta_to_q(*target))
        roll = goto_roll_for_eq(az, alt, theta3_now, WEDGE)
        _, _, theta3 = q_to_theta(WEDGE.inverse * azaltroll_to_q(az, alt, roll),
                                  LastPosition(target[0], target[1], expected_theta3))
        assert wrap180(theta3 - expected_theta3) == pytest.approx(0.0, abs=0.5)


def eq_toggle(monkeypatch, tw, on):
    """Polaris:ConfigUpdate advanced_eq_mode (as polaris.make_config_params_live applies it)."""
    monkeypatch.setattr(Config, "advanced_eq_mode", on)
    sm = tw.polaris._sm
    sm.clear_sync_guiding()
    sm.optimize_alignQ_B2T()
    sm.refresh_pid_setpoints_from_q1()


class TestEqGotos:

    @pytest.mark.parametrize("pose", ["ha-4h_dec-36", "m3_framing_dec-52"])
    def test_goto_while_tracking_keeps_m3(self, monkeypatch, pose):
        tw = eq_twin(monkeypatch, EQ_POSES[pose])
        theta3 = tw.theta[2]
        target = (tw.polaris.rightascension + 0.2, tw.polaris.declination - 3.0)
        done, _, miss = run_goto(tw, lambda: tw.goto_radec(*target), target_radec=target)
        tw.run(10)
        moved3 = tw.theta[2] - theta3
        tw.close()
        assert done is not None and miss < 60, f"goto done {done}, miss {miss}"
        assert abs(moved3) < 0.05, f"M3 moved {moved3:.3f} deg"

    def test_goto_across_dec_0_completes(self, monkeypatch):
        tw = eq_twin(monkeypatch, (60.0, 12.0, 0.0))                       # dec_p 12 (Dec -12)
        target = (tw.polaris.rightascension, tw.polaris.declination + 16.0)  # Dec +4: M2 through 0 (gimbal lock)
        done, _, miss = run_goto(tw, lambda: tw.goto_radec(*target), target_radec=target, max_s=90)
        tw.close()
        assert done is not None and miss < 60, f"goto done {done}, miss {miss}"

    def test_level_goto_keeps_sky_roll_as_before(self, monkeypatch):
        tw = Twin(monkeypatch, config={"coordinated_speed_control": True}, seed=0)
        tw.place((150.0, 40.0, 20.0))
        tw.start_tracking()
        tw.run(10)
        tw.goto_radec(tw.polaris.rightascension + 0.2, tw.polaris.declination - 3.0)
        roll_default = tw.pid.body2alpha()[2]
        assert tw.pid.alpha_sp[2] == pytest.approx(roll_default, abs=1e-9)
        tw.close()


class TestEqMeridianAndToggle:

    def test_tracking_through_the_meridian_is_m1_only(self, monkeypatch, caplog):
        tw = eq_twin(monkeypatch, (2.0, 56.0, -0.5))        # 8 min east of the meridian
        theta0 = tw.theta
        with caplog.at_level("INFO"):
            tw.run(16 * 60)
        moved = tw.theta - theta0
        tw.close()
        assert theta0[0] > 0 > tw.theta[0], f"M1 {theta0[0]:.2f} -> {tw.theta[0]:.2f} did not pass the meridian"
        assert abs(moved[1]) * 3600 < 10 and abs(moved[2]) * 3600 < 10
        assert not [r for r in caplog.records if "UNWIND" in r.getMessage() or "FLIP" in r.getMessage()]

    @pytest.mark.parametrize("start_eq", [False, True], ids=["level->eq", "eq->level"])
    def test_toggle_while_tracking_does_not_slew(self, monkeypatch, start_eq):
        config = {"coordinated_speed_control": True, "advanced_eq_mode": start_eq}
        tw = Twin(monkeypatch, config=config, seed=0)
        tw.place(EQ_POSES["ha-4h_dec-36"] if start_eq else (135.0, 45.0, 0.0))
        tw.start_tracking()
        tw.run(30)
        theta0 = tw.theta
        eq_toggle(monkeypatch, tw, not start_eq)
        mode = tw.pid.mode
        rms = tracking_rms(tw, seconds=30.0)
        moved = np.abs(tw.theta - theta0)
        tw.close()
        assert mode == "TRACK"
        assert np.all(moved < 0.2), f"motors moved {np.round(moved, 3)} deg in 30 s: a slew"
        assert rms < 5.0, f"tracking RMS {rms:.2f}\""
