"""
Outcome tests for motion control, run on the digital twin (tests/twin.py: the driver's real
PID_Controller, SyncManager, KalmanFilter and v2 speed controller against a hardware-matched model of
the mount, on a simulated clock). Twin baselines match the mount closely (tracking RMS within ~25%,
goto-while-tracking settle times and roll-step drift in the hardware range).

Guards - must hold for every change (no going backwards):
  * sidereal tracking RMS at five poses stays within 10% of the recorded baseline, for each
    coordinated_speed_control setting (off = legacy speed controller, on = coordinated)
Goals - the improvements being worked on (fail until done):
  * tracking right after a goto is no worse than before it (baseline: 2.21" after vs 1.87" before,
    from the integral disturbed by the goto)
  * a 3' corrective goto while tracking completes (2.25" on all motors) within 3 s   [baseline ~6.3 s]
  * a 5 deg goto while tracking completes within 15 s                                 [baseline ~27.7 s]
  * the PID integral winds up no more than 10" during a goto                          [baseline 26-100"]
  * a 30 deg roll step while tracking keeps RA/Dec within 30'                          [baseline ~325']
  * a 45 deg roll goto while not tracking keeps Az/Alt within 30'
The completion tolerance is the driver's own (pid_Kc/60/20 = 2.25"); it is not loosened.
"""
import math

import numpy as np
import pytest

from twin import Twin
from kinematics import azaltroll_to_theta_ik
from test_speed_controller_hw_tracking import ORIENTATIONS

SEEDS = (0, 1, 2)
TOL_DEG = 0.75 / 60 / 20
ARCSEC = 3600.0

# twin tracking RMS baselines (arcsec, mean of SEEDS), 2026-09-27, per coordinated_speed_control setting,
# with the hardware M3 sample-and-hold (0.6 s) in the twin
BASELINE_TRACKING_RMS = {
    "legacy": {"pole_alt15_roll0": 84.08, "pole_alt20_roll0": 13.51, "pole_alt20_roll45": 2.29,
               "north_alt15_roll0": 12.09, "mid_alt_meridian": 2.37},
    "coordinated": {"pole_alt15_roll0": 7.15, "pole_alt20_roll0": 3.33, "pole_alt20_roll45": 1.91,
                    "north_alt15_roll0": 5.89, "mid_alt_meridian": 2.4},
}
GUARD = 1.10
TRACK_POSE = (135.0, 45.0, 0.0)
CANDIDATE = {"coordinated_speed_control": True}           # the configuration the goals are for
# Goals not yet met are expected failures (non-strict): they show as XFAIL until achieved, then XPASS.
goal = pytest.mark.xfail(strict=False, reason="motion-control goal not yet met (see module docstring)")


def radec_sep_arcmin(ra1, dec1, ra2, dec2):
    a1, d1, a2, d2 = math.radians(ra1 * 15), math.radians(dec1), math.radians(ra2 * 15), math.radians(dec2)
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(a1 - a2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 60


def azalt_sep_arcmin(az1, alt1, az2, alt2):
    a1, h1, a2, h2 = map(math.radians, (az1, alt1, az2, alt2))
    c = math.sin(h1) * math.sin(h2) + math.cos(h1) * math.cos(h2) * math.cos(a1 - a2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * 60


def tracking_rms(tw, seconds=60.0):
    errs = []
    tw.run(seconds, on_measure=lambda t: errs.append(t.pid.error_signal.copy()))
    e = np.array(errs) * ARCSEC
    return float(np.sqrt(np.mean(np.sum(e ** 2, axis=1))))


def tracking_twin(monkeypatch, config, seed, pose=TRACK_POSE):
    tw = Twin(monkeypatch, config=config, seed=seed)
    tw.place(azaltroll_to_theta_ik(*pose))
    tw.start_tracking()
    tw.run(30)
    return tw


def run_goto(tw, start, target_radec=None, max_s=60.0):
    """Start a goto and run until it reports complete. Returns (seconds to complete or None, integral wind-up
    arcsec, RA/Dec distance from target_radec at completion in arcsec or None)."""
    t0, i0, wind = tw.clock.t, tw.pid.error_integral.copy(), [0.0]

    def watch(t):
        wind[0] = max(wind[0], float(np.max(np.abs(t.pid.error_integral - i0))) * ARCSEC)

    start()
    while tw.clock.t - t0 < max_s and tw.polaris.goto_complete_at is None:
        tw.run(0.2, on_measure=watch)
    done = None if tw.polaris.goto_complete_at is None else tw.polaris.goto_complete_at - t0
    miss = None
    if target_radec is not None and done is not None:
        miss = radec_sep_arcmin(*target_radec, tw.polaris.rightascension, tw.polaris.declination) * 60
    return done, wind[0], miss


def fmt(xs):
    return "[" + ", ".join("-" if x is None else f"{x:.1f}" for x in xs) + "]"


# ---------------------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("setting", ["legacy", "coordinated"])
@pytest.mark.parametrize("pose", ORIENTATIONS.keys())
def test_guard_tracking_rms_not_worse_than_baseline(monkeypatch, setting, pose):
    config = CANDIDATE if setting == "coordinated" else {}
    rms = []
    for seed in SEEDS:
        tw = tracking_twin(monkeypatch, config, seed, ORIENTATIONS[pose])
        rms.append(tracking_rms(tw))
        tw.close()
    baseline = BASELINE_TRACKING_RMS[setting][pose]
    assert np.mean(rms) <= GUARD * baseline, (
        f"{setting} sidereal tracking RMS at {pose} is {np.mean(rms):.2f}\" (seeds {np.round(rms, 2)}), worse than "
        f"its baseline {baseline:.2f}\" + 10% = {GUARD * baseline:.2f}\"")


@goal
@pytest.mark.parametrize("config", [{}, CANDIDATE], ids=["legacy", "coordinated"])
def test_goal_tracking_after_goto_is_no_worse_than_before(monkeypatch, config):
    before, after = [], []
    for seed in SEEDS:
        tw = tracking_twin(monkeypatch, config, seed)
        before.append(tracking_rms(tw, 40))
        ra, dec = tw.polaris.rightascension, tw.polaris.declination
        run_goto(tw, lambda: tw.goto_radec(ra, dec + 3 / 60))
        after.append(tracking_rms(tw, 40))
        tw.close()
    assert np.mean(after) <= 1.15 * np.mean(before), (
        f"tracking RMS after a corrective goto {np.mean(after):.2f}\" (seeds {np.round(after, 2)}) is worse than "
        f"before it {np.mean(before):.2f}\" + 15% - goto/integral handling is disturbing tracking")


@pytest.mark.parametrize("config", [{}, CANDIDATE], ids=["legacy", "coordinated"])
@pytest.mark.parametrize("step", ["corrective_3arcmin", "large_5deg"])
def test_guard_goto_completes_only_on_target(monkeypatch, config, step):
    """Plate solving follows completion: when a goto while tracking reports complete, the mount must be on
    the requested RA/Dec (within 5\"), not still moving towards it."""
    misses = []
    for seed in SEEDS:
        tw = tracking_twin(monkeypatch, config, seed)
        ra, dec = tw.polaris.rightascension, tw.polaris.declination
        target = (ra, dec + 3 / 60) if step == "corrective_3arcmin" else ((ra + 5 / 15) % 24, dec)
        done, _, miss = run_goto(tw, lambda: tw.goto_radec(*target), target_radec=target)
        misses.append(miss if done is not None else 1e9)
        tw.close()
    assert max(misses) <= 5.0, f"{step} goto reported complete {fmt(misses)}\" away from the requested RA/Dec (limit 5\")"


# ---------------------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------------------

@goal
def test_goal_corrective_goto_while_tracking_completes_within_3s(monkeypatch):
    times = []
    for seed in SEEDS:
        tw = tracking_twin(monkeypatch, CANDIDATE, seed)
        ra, dec = tw.polaris.rightascension, tw.polaris.declination
        times.append(run_goto(tw, lambda: tw.goto_radec(ra, dec + 3 / 60))[0])
        tw.close()
    assert all(t is not None and t <= 3.0 for t in times), (
        f"a 3' corrective goto while tracking took {fmt(times)} s to reach 2.25\" and complete (goal <= 3 s)")


@goal
def test_goal_large_goto_while_tracking_completes_within_15s(monkeypatch):
    times = []
    for seed in SEEDS:
        tw = tracking_twin(monkeypatch, CANDIDATE, seed)
        ra, dec = tw.polaris.rightascension, tw.polaris.declination
        times.append(run_goto(tw, lambda: tw.goto_radec((ra + 5 / 15) % 24, dec))[0])
        tw.close()
    assert all(t is not None and t <= 15.0 for t in times), (
        f"a 5 deg goto while tracking took {fmt(times)} s to reach 2.25\" and complete (goal <= 15 s)")


@pytest.mark.parametrize("step", ["corrective_3arcmin", "large_5deg"])
def test_goal_integral_does_not_wind_up_during_goto(monkeypatch, step):
    winds = []
    for seed in SEEDS:
        tw = tracking_twin(monkeypatch, CANDIDATE, seed)
        ra, dec = tw.polaris.rightascension, tw.polaris.declination
        target = (ra, dec + 3 / 60) if step == "corrective_3arcmin" else ((ra + 5 / 15) % 24, dec)
        winds.append(run_goto(tw, lambda: tw.goto_radec(*target))[1])
        tw.close()
    assert max(winds) <= 10.0, f"during a {step} goto the PID integral wound up by {fmt(winds)}\" (goal <= 10\")"


@goal
def test_goal_roll_step_while_tracking_holds_radec(monkeypatch):
    drifts = []
    for seed in SEEDS:
        tw = tracking_twin(monkeypatch, CANDIDATE, seed)
        ra0, dec0, worst = tw.polaris.rightascension, tw.polaris.declination, [0.0]

        def watch(t):
            worst[0] = max(worst[0], radec_sep_arcmin(ra0, dec0, t.polaris.rightascension, t.polaris.declination))

        t0 = tw.clock.t
        tw.slew_relative(roll=30.0)
        while tw.clock.t - t0 < 60 and tw.polaris.goto_complete_at is None:
            tw.run(0.2, on_measure=watch)
        drifts.append(worst[0])
        tw.close()
    assert max(drifts) <= 30.0, f"a 30 deg roll step while tracking moved RA/Dec by {fmt(drifts)}' (goal <= 30')"


@goal
def test_goal_roll_goto_not_tracking_holds_azalt(monkeypatch):
    drifts = []
    for seed in SEEDS:
        tw = Twin(monkeypatch, config=CANDIDATE, seed=seed)
        tw.place(azaltroll_to_theta_ik(180.0, 20.0, 0.0))
        az0, alt0, worst = tw.polaris._p_azimuth, tw.polaris._p_altitude, [0.0]

        def watch(t):
            worst[0] = max(worst[0], azalt_sep_arcmin(az0, alt0, t.polaris._p_azimuth, t.polaris._p_altitude))

        t0 = tw.clock.t
        tw.goto_altaz(az0, alt0, 45.0)
        while tw.clock.t - t0 < 60 and tw.polaris.goto_complete_at is None:
            tw.run(0.2, on_measure=watch)
        drifts.append(worst[0])
        tw.close()
    assert max(drifts) <= 30.0, f"a 45 deg roll goto at alt 20 moved Az/Alt by {fmt(drifts)}' (goal <= 30')"


@pytest.mark.parametrize("config", [{}, CANDIDATE], ids=["legacy", "coordinated"])
def test_guard_unwind_goto_does_not_overshoot(monkeypatch, config):
    """A goto that must unwind M1 (the short way would pass its motor limit) goes the long way round and
    stops at the target: M1 overshoots its final angle by at most 5 deg and the goto completes.
    Was (coordinated): the planner took over from the unwind at full speed with a trajectory planned
    from rest - 93 deg past, back, past again (seen on the mount going Altair -> Alnair)."""
    overs, times = [], []
    for seed in SEEDS:
        tw = Twin(monkeypatch, config=config, seed=seed)
        theta = np.array(azaltroll_to_theta_ik(50.0, 40.0, 0.0), dtype=float)
        theta[0] += 360.0                                   # M1 wound to zeta1 ~ +230 (limit 270, margin 10)
        tw.place(theta)
        t0, path = tw.clock.t, []
        tw.goto_altaz(120.0, 40.0)                          # short way would take zeta1 to ~ +300
        while tw.clock.t - t0 < 120 and tw.polaris.goto_complete_at is None:
            tw.run(0.2, on_measure=lambda t: path.append(t.theta[0]))
        tw.run(5, on_measure=lambda t: path.append(t.theta[0]))
        path = np.array(path)
        direction = np.sign(path[-1] - path[0])
        overs.append(float(max(0.0, np.max((path - path[-1]) * direction))))
        times.append(None if tw.polaris.goto_complete_at is None else tw.polaris.goto_complete_at - t0)
        tw.close()
    assert all(t is not None for t in times), f"unwind goto did not complete within 120 s: {fmt(times)} s"
    assert max(overs) <= 5.0, f"unwind goto: M1 overshot its final angle by {fmt(overs)} deg (limit 5 deg)"


def test_guard_goto_needing_a_flip_is_left_to_the_pid(monkeypatch, caplog):
    """A goto to a negative altitude needs the other IK branch (theta2 < -8 is invalid): the Az/Alt planner
    can't walk the reference across the 180 deg jump, so it must not plan it; the goto flips once, straight to
    the target, and arrives. Was: the planned reference stalled at the jump - on the mount the goto fought
    near alt 0 for ~20 s before flipping."""
    import logging
    caplog.set_level(logging.INFO)
    tw = Twin(monkeypatch, config=CANDIDATE, seed=0)
    tw.place(azaltroll_to_theta_ik(130.8, 30.0, 0.0))
    theta0 = tw.theta
    caplog.clear()
    t0 = tw.clock.t
    tw.goto_altaz(130.8, -30.0)
    tw.run(0.4)
    azalt_planned = tw.pid.goto_traj is not None and tw.pid.goto_traj.space != 'THETA'
    while tw.clock.t - t0 < 90 and tw.polaris.goto_complete_at is None:
        tw.run(0.2)
    flips = [r.message[:60] for r in caplog.records if "FLIP" in r.message]
    sep = azalt_sep_arcmin(130.8, -30.0, tw.polaris._p_azimuth, tw.polaris._p_altitude)
    d1, d3 = tw.theta[0] - theta0[0], tw.theta[2] - theta0[2]
    tw.close()
    assert d1 * d3 < 0, f"goto to alt -30 turned M1 {d1:+.0f} and M3 {d3:+.0f} deg: a flip must turn them in opposite directions (cable wrap)"
    assert not azalt_planned, "a goto across an IK branch change (to alt -30) was planned in Az/Alt"
    assert len(flips) == 1, f"goto to alt -30 flipped {len(flips)} times: {flips} (expected once)"
    assert sep < 1.5, f"goto to alt -30 ended {sep:.1f}' from the target"


@pytest.mark.parametrize("roll", [0.0, 0.6, 3.0])
@pytest.mark.parametrize("config", [{}, CANDIDATE], ids=["legacy", "coordinated"])
def test_guard_flip_goes_straight_to_the_target(monkeypatch, config, roll, caplog):
    """A goto from a negative altitude (other IK branch: theta2 mirrored, M1/M3 +-180) up to a positive one
    flips once, straight to the target. Was: the FLIP cached the 12 deg stepped reference, which landed near
    theta2 ~ 0 (M1/M3 aligned - gimbal lock), so M1/M3 counter-rotated there with the altitude stuck near 0,
    then a second FLIP the other way (seen on the mount 16:16:30 CCW / 16:16:34 CW). With roll != 0 the twin also
    stalled (alt ~10, or LIMIT). Now the flip is decided at the start of the goto (the path passes near gimbal
    lock) and goes straight to the target's motor angles."""
    import logging
    caplog.set_level(logging.INFO)
    tw = Twin(monkeypatch, config=config, seed=0)
    tw.place(azaltroll_to_theta_ik(180.0, -30.0, roll))   # alt -30 is only reachable on the flipped branch (theta2 +30)
    theta0 = tw.theta
    caplog.clear()
    t0 = tw.clock.t
    tw.goto_altaz(180.0, 30.0, roll)
    while tw.clock.t - t0 < 90 and tw.polaris.goto_complete_at is None:
        tw.run(0.2)
    flips = [r.message[:60] for r in caplog.records if "FLIP" in r.message]
    alt, done = tw.polaris._p_altitude, tw.polaris.goto_complete_at is not None
    d1, d3 = tw.theta[0] - theta0[0], tw.theta[2] - theta0[2]
    tw.close()
    assert d1 * d3 < 0, f"goto alt -30 -> +30 (roll {roll}) turned M1 {d1:+.0f} and M3 {d3:+.0f} deg: a flip must turn them in opposite directions (cable wrap)"
    assert done, f"goto alt -30 -> +30 (roll {roll}) did not complete within 90 s (at alt {alt:.2f}, flips {flips})"
    assert len(flips) <= 1, f"goto alt -30 -> +30 (roll {roll}) flipped {len(flips)} times: {flips} (expected one flip, straight to the target)"
    assert abs(alt - 30.0) < 0.1, f"goto alt -30 -> +30 ended at alt {alt:.2f}"


@pytest.mark.parametrize("move", [((100.0, 40.0), (190.0, 40.0)), ((150.0, 20.0), (200.0, 70.0))], ids=["az_90", "az_alt"])
@pytest.mark.parametrize("config", [{}, CANDIDATE], ids=["legacy", "coordinated"])
def test_guard_goto_clear_of_gimbal_lock_does_not_flip(monkeypatch, config, move, caplog):
    """A large goto whose path stays clear of theta2 ~ 0 needs no FLIP, and arrives."""
    import logging
    caplog.set_level(logging.INFO)
    (az0, alt0), (az1, alt1) = move
    tw = Twin(monkeypatch, config=config, seed=0)
    tw.place(azaltroll_to_theta_ik(az0, alt0, 0.0))
    caplog.clear()
    t0 = tw.clock.t
    tw.goto_altaz(az1, alt1)
    while tw.clock.t - t0 < 90 and tw.polaris.goto_complete_at is None:
        tw.run(0.2)
    flips = [r.message[:60] for r in caplog.records if "FLIP" in r.message]
    sep = azalt_sep_arcmin(az1, alt1, tw.polaris._p_azimuth, tw.polaris._p_altitude)
    tw.close()
    assert not flips, f"goto {move} flipped: {flips}"
    assert sep < 1.5, f"goto {move} ended {sep:.1f}' from the target (completion tolerance 0.75' per motor)"


@pytest.mark.parametrize("roll", [0.0, 3.0])
@pytest.mark.parametrize("move", [(30.0, -5.0), (-30.0, 5.0)], ids=["alt30_to_-5", "alt-30_to_5"])
@pytest.mark.parametrize("config", [{}, CANDIDATE], ids=["legacy", "coordinated"])
def test_guard_goto_within_the_overlap_does_not_flip(monkeypatch, config, move, roll, caplog):
    """The two sides overlap for |theta2| <= 8 (theta2 is valid from -8): from positive altitudes a target
    down to ~-8 alt is reached without flipping, and from negative altitudes one up to ~+8."""
    import logging
    caplog.set_level(logging.INFO)
    alt0, alt1 = move
    tw = Twin(monkeypatch, config=config, seed=0)
    tw.place(azaltroll_to_theta_ik(180.0, alt0, roll))
    theta0 = tw.theta
    caplog.clear()
    t0 = tw.clock.t
    tw.goto_altaz(180.0, alt1, roll)
    while tw.clock.t - t0 < 90 and tw.polaris.goto_complete_at is None:
        tw.run(0.2)
    flips = [r.message[:60] for r in caplog.records if "FLIP" in r.message]
    sep = azalt_sep_arcmin(180.0, alt1, tw.polaris._p_azimuth, tw.polaris._p_altitude)
    m1_turn = abs(tw.theta[0] - theta0[0])
    tw.close()
    assert not flips, f"goto alt {alt0} -> {alt1} (roll {roll}) flipped: {flips}"
    assert m1_turn < 90, f"goto alt {alt0} -> {alt1} (roll {roll}) turned M1 {m1_turn:.0f} deg (a flip)"
    assert sep < 1.5, f"goto alt {alt0} -> {alt1} (roll {roll}) ended {sep:.1f}' from the target (completion tolerance 0.75' per motor)"


@pytest.mark.parametrize("wind", [(0, 0), (360, 0), (0, -360), (360, -360)], ids=["m1_0_m3_0", "m1_+360", "m3_-360", "m1_+360_m3_-360"])
@pytest.mark.parametrize("config", [{}, CANDIDATE], ids=["legacy", "coordinated"])
def test_guard_flip_turns_m1_and_m3_in_opposite_directions(monkeypatch, config, wind, caplog):
    """A flip turns M1 and M3 by ~180 deg each: they must turn in opposite directions (else the cables wrap)
    whenever that fits within the motor limits (z +-270, 10 deg margin). From z1, z3 both ~+180 (or both ~-180)
    it can't (an unwind first would take ~1.5 min): then the flip stays within the limits and a warning is logged."""
    import logging
    caplog.set_level(logging.INFO)
    tw = Twin(monkeypatch, config=config, seed=0)
    theta = np.array(azaltroll_to_theta_ik(180.0, -30.0, 0.0), dtype=float) + np.array([wind[0], 0.0, wind[1]])
    tw.place(theta)                                          # alt -30: flipped branch, theta ~ (0+w1, 30, 180+w3)
    theta0 = tw.theta
    caplog.clear()
    t0, zmax, same = tw.clock.t, [0.0, 0.0], [0.0]
    prev = [tw.theta]
    tw.goto_altaz(180.0, 30.0)

    def watch(t):
        z = t.polaris._zeta_meas
        zmax[0], zmax[1] = max(zmax[0], abs(z[0])), max(zmax[1], abs(z[2]))
        d = t.theta - prev[0]
        prev[0] = t.theta
        if d[0] * d[2] > 0:                                  # M1 and M3 turning the same way this sample
            same[0] += min(abs(d[0]), abs(d[2]))

    while tw.clock.t - t0 < 90 and tw.polaris.goto_complete_at is None:
        tw.run(0.2, on_measure=watch)
    alt = tw.polaris._p_altitude
    warned = any("same direction" in r.message for r in caplog.records)
    tw.close()
    z1, z3 = theta0[0] - 180.0, theta0[2]
    opposite_fits = any(abs(z1 + s1 * 180) <= 260 and abs(z3 - s1 * 180) <= 260 for s1 in (1, -1))
    assert abs(alt - 30.0) < 0.1, f"flip from wind {wind} ended at alt {alt:.2f}"
    assert zmax[0] <= 270 and zmax[1] <= 270, f"flip from wind {wind} reached |z1| {zmax[0]:.0f} / |z3| {zmax[1]:.0f} (limit 270)"
    if opposite_fits:
        assert same[0] < 5.0, f"flip from wind {wind} turned M1 and M3 in the same direction together by {same[0]:.0f} deg (cable wrap)"
    else:
        assert warned, f"flip from wind {wind} (z1 {z1:+.0f}, z3 {z3:+.0f}) can't turn M1/M3 opposite within the limits: expected a warning"
    assert zmax[0] <= 270 and zmax[1] <= 270, f"flip from wind {wind} reached |z1| {zmax[0]:.0f} / |z3| {zmax[1]:.0f} (limit 270)"
