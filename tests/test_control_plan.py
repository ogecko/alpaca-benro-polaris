"""
Goto planning (driver/control_plan.py): the digital twin sweep against the acceptance criteria of
docs/study_goto_response.md.

Random gotos in the digital twin, level and eq (wedge) mode, idle and while tracking. Per goto: the time to complete,
the theoretical best (the fastest end solution, each motor moving on its own at Kv / Ka from rest to rest:
kinematics.theta_solutions, control_plan.min_move_time), the end solution the driver chose, motor limits, mid-goto
remaps (UNWIND / FLIP / LOCK / EQ ROOM transitions), M1's tracking
room, and the kinematics work done per control tick (R4: counted calls, not wall time, so it is the same on any
machine).

The acceptance tests are xfail(strict=False) until the redesign lands: they record what today's planner does, and one
that starts passing shows as XPASS. A seeded subset runs in the suite; the full sweep (--runslow) prints the report
the study quotes:

    uv run pytest tests/test_control_plan.py --runslow -s -k report

GOTO_SWEEP_CALIBRATED=1 gives the driver an approved FAST speed calibration of the twin's motors (which, like the
mount's, run faster than the baseline table: sim_digital_twin.twin_fast_calibration).
"""
import logging
import math
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
import control                                                                   # noqa: E402
import control_plan                                                              # noqa: E402
from config import Config                                                        # noqa: E402
from control_eq import THETA2_MIN                                               # noqa: E402
from control_plan import min_move_time, move_time, MotorMove, choose_end_solution, wraps_cables  # noqa: E402
from kinematics import (theta_solutions, theta_to_q, azaltroll_to_q, q_to_azaltroll, vector_to_az_alt,  # noqa: E402
                        THETA2_MAX)
from sim_digital_twin import Twin, MEASURE_DT                                     # noqa: E402
from test_motion_outcomes import radec_sep_arcmin                                 # noqa: E402

CASES = {"level_idle": (False, False), "level_track": (False, True), "eq_idle": (True, False), "eq_track": (True, True)}
SUBSET, FULL = 10, 150             # gotos per case: in the suite / the full sweep (--runslow)
TIMEOUT_S = 120.0
ZETA_OFFSET = np.array([180.0, 45.0, 0.0])            # motor angle = raw zeta + this (sim_digital_twin)
TRACK_ROOM_DEG = 120.0              # 8 h of M1 for tracking (control_eq.EQ_MIN_TRACK_ROOM_DEG)
KINEMATICS_PER_TICK = 40            # R4 budget, provisional: until a Pi Zero 2 W benchmark sets it in time
REMAP_WORDS = (" Transition", "EQ ROOM")
GOTO_TIMEOUT_S = 45.0               # PID_Controller.goto_timeout: the goto is marked complete wherever it is
CALIBRATED = os.environ.get("GOTO_SWEEP_CALIBRATED") == "1"     # the driver with an approved FAST speed calibration


def motor_limits(safety=0.0):
    """Motor-angle limits (deg) from the raw zeta limits, less a safety margin on M1/M3."""
    lo = np.array([Config.z1_min_limit, Config.z2_min_limit, Config.z3_min_limit], dtype=float) + ZETA_OFFSET
    hi = np.array([Config.z1_max_limit, Config.z2_max_limit, Config.z3_max_limit], dtype=float) + ZETA_OFFSET
    return lo + [safety, 0, safety], hi - [safety, 0, safety]


def end_solutions(motorQ):
    """The end solutions a planner may choose from: inside the limits less the safety margin, M2 in the
    reference range."""
    lo, hi = motor_limits(Config.zeta_safety_margin)
    lo[1], hi[1] = max(lo[1], THETA2_MIN), min(hi[1], THETA2_MAX)
    return theta_solutions(motorQ, lo, hi)


def solution_times(solutions, start, kv, ka):
    return np.array([float(np.max(min_move_time(s - start, kv, ka))) for s in solutions])


class _Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class _Counter:
    """Counts calls to the kinematics functions the control loop and the planner use."""
    NAMES = ((control, "q_to_theta"), (control, "azaltroll_to_q"), (control, "q_to_azaltroll"),
             (control_plan, "azaltroll_to_q"), (control_plan, "q_to_azaltroll"))

    def __init__(self, mp):
        self.n = 0
        for module, name in self.NAMES:
            fn = getattr(module, name)
            mp.setattr(module, name, self._wrap(fn))

    def _wrap(self, fn):
        def counted(*a, **k):
            self.n += 1
            return fn(*a, **k)
        return counted


def _random_pose(rng, alignQ, min_alt):
    """Random motor angles well inside the limits whose pointing is above min_alt."""
    lo, hi = motor_limits(Config.zeta_safety_margin + 20)
    while True:
        theta = np.array([rng.uniform(lo[0], hi[0]), rng.uniform(5.0, 75.0), rng.uniform(-150.0, 150.0)])
        bore = np.array((alignQ * theta_to_q(*theta)).rotate([0.0, 0.0, -1.0]))
        if math.degrees(math.asin(np.clip(bore[2], -1, 1))) > min_alt:
            return theta


def run_goto(case, seed):
    """One random goto of a case in a fresh twin. Returns a dict of what happened."""
    eq, track = CASES[case]
    rng = np.random.default_rng(seed)
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True, "advanced_eq_mode": eq}, seed=seed, calibrated=CALIBRATED)
        sm = tw.polaris._sm
        sm.optimize_alignQ_B2T()                       # eq: the ideal wedge (as on enabling eq mode)
        alignQ = sm.alignQ_B2T
        tw.place(_random_pose(rng, alignQ, 10.0))
        if track:
            tw.start_tracking()
            tw.run(5)
        records, counter = _Records(), _Counter(mp)
        tw.logger.addHandler(records)
        tw.logger.setLevel(logging.INFO)
        target = None
        while target is None:                          # a target above 15 deg
            v = rng.normal(size=3)
            az, alt = vector_to_az_alt(v / np.linalg.norm(v))
            if alt > 15.0:
                target = (az, alt, rng.uniform(-180, 180))
        start = tw.theta
        t0 = tw.clock.t
        if track:
            ra, dec = tw.polaris.altaz2radec(target[1], target[0])
            tw.goto_radec(ra, dec)
        else:
            tw.goto_altaz(*target)
        # what the driver aims for: the pose it resolves the target to, in the motors' frame
        reach = tw.pid._reachable_alpha(np.array(tw.pid.alpha_sp, dtype=float))
        motorQ = sm.topoQ_to_baseQ(azaltroll_to_q(*reach))
        trace, modes, work = [start.copy()], [], []

        def watch(t):
            trace.append(t.theta)
            modes.append(t.pid.mode)
            work.append(counter.n)
            counter.n = 0

        while tw.clock.t - t0 < TIMEOUT_S and tw.polaris.goto_complete_at is None:
            tw.run(0.2, on_measure=watch)
        done = None if tw.polaris.goto_complete_at is None else tw.polaris.goto_complete_at - t0
        final = tw.theta
        if track and done is not None:
            miss_arcmin = radec_sep_arcmin(ra, dec, tw.polaris.rightascension, tw.polaris.declination)
        else:
            q = alignQ * theta_to_q(*final)
            d = abs(float(np.dot(np.asarray(q.q), np.asarray(azaltroll_to_q(*reach).q))))
            miss_arcmin = math.degrees(2 * math.acos(min(1.0, d))) * 60
        room = np.nan
        if track and done is not None:                 # M1's room left in the direction tracking turns it
            before = tw.theta[0]
            tw.run(10)
            lo, hi = motor_limits(Config.zeta_safety_margin)
            room = hi[0] - tw.theta[0] if tw.theta[0] >= before else tw.theta[0] - lo[0]
        tw.close()
    finally:
        mp.undo()

    kv, ka = np.array(tw.pid.Kv, dtype=float), min(float(np.min(tw.pid.Ka)), tw.pid.GOTO_MAX_ACCEL)
    sols = end_solutions(motorQ)
    times = solution_times(sols, start, kv, ka) if len(sols) else np.array([])
    chosen = int(np.argmin(np.max(np.abs(sols - final), axis=1))) if len(sols) else None
    chosen_ok = chosen is not None and np.max(np.abs(sols[chosen] - final)) < 2.0
    trace = np.array(trace)
    lo, hi = motor_limits()
    return {
        "case": case, "seed": seed, "done_s": done, "miss_arcmin": miss_arcmin,
        "t_best_s": float(times.min()) if len(times) else np.nan,
        "t_chosen_s": float(times[chosen]) if chosen_ok else np.nan,
        "n_solutions": len(sols),
        "limit": bool((trace < lo - 1e-6).any() or (trace > hi + 1e-6).any() or "LIMIT" in modes),
        "remaps": [m for m in records.messages if any(w in m for w in REMAP_WORDS)],
        "room_deg": room,
        "best_room_short": bool((track or eq) and len(sols) and _room_short(sols[int(np.argmin(times))], kv)),
        "max_work_per_tick": int(max(work)) if work else 0,
        "travel_deg": float(np.abs(np.diff(trace, axis=0)).sum()),
    }


def _room_short(theta, kv):
    """Rough check: the best solution leaves M1 less than a night's room on either side."""
    lo, hi = motor_limits(Config.zeta_safety_margin)
    return min(hi[0] - theta[0], theta[0] - lo[0]) < TRACK_ROOM_DEG


def run_sweep(n, seed0=0):
    return pd.DataFrame([run_goto(case, seed0 + k) for case in CASES for k in range(n)])


def summarise(df):
    rows = []
    for case, g in df.groupby("case", sort=False):
        done = g[g.done_s.notna() & (g.miss_arcmin <= 2.0)]                  # arrived
        ratio = (done.done_s / done.t_best_s).replace([np.inf], np.nan)
        slower = (g.t_chosen_s - g.t_best_s) > 2.0
        rows.append({
            "case": case, "gotos": len(g), "arrived": f"{len(done)}/{len(g)}",
            "arrival/best (median)": round(float(ratio.median()), 2),
            "arrival-best s (median)": round(float((done.done_s - done.t_best_s).median()), 1),
            "chose slower by >2 s": int(slower.sum()),
            "...room excuses": int((slower & g.best_room_short).sum()),
            "LIMIT": int(g.limit.sum()), "remapped": int(g.remaps.map(bool).sum()),
            "kinematics/tick (max)": int(g.max_work_per_tick.max()),
            "missed > 2'": int((g.miss_arcmin > 2).sum()),
            "...at the 45 s timeout": int(((g.miss_arcmin > 2) & (g.done_s >= GOTO_TIMEOUT_S - 0.5)).sum()),
        })
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def sweep():
    return run_sweep(SUBSET)


# ---------------------------------------------------------------------------------------
# The harness itself (must pass)
# ---------------------------------------------------------------------------------------

def test_min_move_time_trapezoid_and_triangle():
    v, a = 8.0, 4.0                                       # reaches v after 2 s and 8 deg (16 deg to speed up and stop)
    assert min_move_time(24.0, v, a) == pytest.approx(5.0)                  # 2 s up, 1 s at v (8 deg), 2 s down
    assert min_move_time(16.0, v, a) == pytest.approx(4.0)                  # just reaches v
    assert min_move_time(4.0, v, a) == pytest.approx(2.0)                   # triangle: 1 s up to 4 deg/s, 1 s down
    assert min_move_time(0.0, v, a) == pytest.approx(0.0)
    assert min_move_time(-16.0, v, a) == pytest.approx(min_move_time(16.0, v, a))


@pytest.mark.parametrize("theta", [(30.0, 40.0, 50.0), (200.0, 5.0, -100.0), (10.0, -5.0, 0.0), (100.0, 81.0, 30.0)])
def test_theta_solutions_are_the_same_pose(theta):
    q = theta_to_q(*theta)
    lo, hi = np.array([-90.0, -10.0, -270.0]), np.array([450.0, 82.0, 270.0])
    sols = theta_solutions(q, lo, hi)
    assert any(np.allclose(s, theta, atol=1e-6) for s in sols)
    for s in sols:
        assert (s >= lo - 1e-9).all() and (s <= hi + 1e-9).all()
        assert abs(float(np.dot(np.asarray(theta_to_q(*s).q), np.asarray(q.q)))) == pytest.approx(1.0, abs=1e-9)
    if abs(theta[1]) <= 10.0:                             # both branches when the mirrored M2 is in range too
        assert len({round(float(s[1]), 6) for s in sols}) == 2


def test_out_of_reach_pose_has_no_solution():
    q = azaltroll_to_q(0.0, 89.0, 0.0)                    # level: the zenith zone is past M2's 81.5
    assert len(theta_solutions(q, [-90, -10, -270], [450, 82, 270])) == 0


def _run_move(move, dt=0.05, seconds=60.0):
    out = []
    for _ in range(int(seconds / dt)):
        out.append(move.step(dt))
        if move.done:
            break
    return np.array([r for r, _ in out]), np.array([w for _, w in out])


@pytest.mark.parametrize("goal, omega", [((30.0, -10.0, 90.0), (0.0, 0.0, 0.0)), ((2.0, 0.5, -1.0), (0.0, 0.0, 0.0)),
                                         ((30.0, 30.0, 30.0), (5.0, -5.0, 9.0)), ((1.0, -1.0, 0.0), (6.0, 6.0, -6.0))],
                         ids=["from_rest", "small", "moving", "overshooting"])
def test_motor_move_lands_on_the_goal_within_the_limits(goal, omega):
    rate, accel = np.array([8.0, 7.0, 8.0]), 5.0
    move = MotorMove(rate, accel)
    move.start(np.zeros(3), goal, omega)
    refs, speeds = _run_move(move)
    assert move.done and np.allclose(refs[-1], goal) and np.allclose(speeds[-1], 0.0)
    assert (np.abs(speeds[1:]) <= np.maximum(rate, np.abs(omega)) + 1e-9).all()                # never past max_rate
    assert (np.abs(np.diff(speeds, axis=0)) <= accel * 0.05 + 1e-6).all()                    # within max_accel
    assert move.duration == pytest.approx(move_time(np.zeros(3), goal, omega, rate, accel))


def test_motor_move_from_rest_is_time_optimal():
    rate, accel, goal = np.array([8.0, 7.0, 8.0]), 5.0, np.array([30.0, -10.0, 90.0])
    move = MotorMove(rate, accel)
    move.start(np.zeros(3), goal)
    assert move.duration == pytest.approx(float(np.max(min_move_time(goal, rate, accel))))


def test_motor_move_reference_lags_the_commands_by_the_dead_time():
    lagged, now = MotorMove(8.0, 5.0, dead_time_s=0.4), MotorMove(8.0, 5.0)
    for m in (lagged, now):
        m.start(np.zeros(3), (20.0, 0.0, 0.0))
    refs, speeds = _run_move(lagged, dt=0.1)
    refs_now, speeds_now = _run_move(now, dt=0.1)
    assert np.allclose(refs[4:len(refs_now) + 4, 0], refs_now[:, 0])         # the same plan, 0.4 s (4 steps) behind
    assert np.allclose(speeds[:len(speeds_now) - 1, 0], speeds_now[:-1, 0])  # the commands themselves aren't delayed
    assert len(refs) == len(refs_now) + 4


def test_motor_move_reference_follows_the_motor_lag():
    lag_s, dt = 0.4, 0.05
    move = MotorMove(8.0, 5.0, lag_s=lag_s)
    move.start(np.zeros(3), (20.0, 0.0, 0.0))
    refs, speeds = _run_move(move, dt=dt)
    ran = (np.cumsum(speeds[:, 0]) - speeds[:, 0] / 2) * dt                      # where the commands put the motor
    lagged = np.zeros(len(ran))
    for i in range(1, len(ran)):
        lagged[i] = lagged[i - 1] + (ran[i] - lagged[i - 1]) * (1 - math.exp(-dt / lag_s))
    assert np.max(np.abs(refs[:-1, 0] - lagged[:-1])) < 0.05                    # the reference is that lagged motor
    assert refs[-1][0] == pytest.approx(20.0) and len(refs) * dt >= move.duration + 3 * lag_s


@pytest.mark.parametrize("seed", [1000, 1004])
def test_guard_goto_completes_only_once_the_motors_settle(seed):
    """These two stopped 7' and 24' short (control.ARRIVED_MAX_RATE_DPS off): on target by measurements that lagged
    the motors, a KF estimate still converging on a motor it overshot braking or a motor still creeping on at a SLOW
    speed."""
    r = run_goto("level_idle", seed)
    assert r["done_s"] is not None and r["miss_arcmin"] < 2.0


@pytest.mark.parametrize("seed", [1047, 1084])
def test_guard_measurements_start_on_the_motors_ik_branch(seed):
    """From a start at low M2 the driver's LastPosition default (180, 45, 0) resolved theta_pv to the other IK branch
    (M1 -180, M2 negated, M3 +180), the planner's limits (from theta - zeta) were 180 deg off, and these eq gotos
    drove M3 into its limit. PID_Controller.seed_branch starts LastPosition at the raw motor angles."""
    r = run_goto("eq_idle", seed)
    assert not r["limit"] and r["done_s"] is not None and r["miss_arcmin"] < 2.0


def test_guard_redirect_at_speed_keeps_every_motor_speed_continuous():
    """R2: a controlled path (a goto of 15 deg or less) redirected at 7 deg/s carried its path speed onto the new path's
    direction in motor space, stepping each motor's speed (M1 4.9 -> 0.6 deg/s in one tick, 24 deg/s^2). It now
    continues straight in motor angles from the motors' current speeds."""
    seed = 1002
    rng = np.random.default_rng(seed)
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=seed)
        sm = tw.polaris._sm
        sm.optimize_alignQ_B2T()
        tw.place(_random_pose(rng, sm.alignQ_B2T, 20.0))
        while True:
            v = rng.normal(size=3)
            az, alt = vector_to_az_alt(v / np.linalg.norm(v))
            if alt > 20:
                break
        ops = []
        tw.goto_altaz(az, alt, 0.0)
        tw.run(3.0, on_measure=lambda t: ops.append(np.array(t.pid.omega_op)))
        a, b, _ = q_to_azaltroll(sm.alignQ_B2T * theta_to_q(*tw.theta))
        tw.polaris.goto_complete_at = None
        tw.goto_altaz(a + 8.0, min(80.0, b + 5.0), 0.0)                      # redirected while slewing
        t1 = tw.clock.t
        while tw.clock.t - t1 < 60 and tw.polaris.goto_complete_at is None:
            tw.run(0.2, on_measure=lambda t: ops.append(np.array(t.pid.omega_op)))
        done = tw.polaris.goto_complete_at
        tw.close()
    finally:
        mp.undo()
    step = np.max(np.abs(np.diff(np.array(ops), axis=0))) / MEASURE_DT
    assert done is not None and step < 10.0, f"command stepped {step:.1f} deg/s^2"


def test_guard_goto_to_alt_0_while_tracking_completes():
    """Field 2026-10-16: a goto to Alt 0 while tracking (level: M2 = 0, gimbal lock) timed out oscillating. Tracking's
    feed-forward demanded the roll the motors can't make there (M1/M3 counter-rotating at 2.4 deg/s), and the PID
    fought how the reference and the measurement split theta1 + theta3 (+1932" M1, -1802" M3)."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place((251.7, 42.4, 0.0))
        tw.start_tracking()
        tw.run(5)
        t0 = tw.clock.t
        tw.goto_altaz(251.76, 0.0)
        while tw.clock.t - t0 < 45 and tw.polaris.goto_complete_at is None:
            tw.run(0.2)
        done = tw.polaris.goto_complete_at
        tw.close()
    finally:
        mp.undo()
    assert done is not None and done - t0 < 30, f"done {done and done - t0}"


def test_guard_tracking_at_gimbal_lock_keeps_the_pointing():
    """Field 2026-10-16: tracking at Alt 0 Az 180 (level, M2 = 0) the goto and a rotate never completed (M2 17" behind)
    and the pointing sank 13"/s. Inside the gimbal lock q_to_theta held the M1/M3 split but kept M2 from the exact
    split: M2 followed the field rotation (roll it can't make there) and tilted the pointing instead. M2 is now solved
    for the boresight with the held split."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place((360.2, 30.0, -180.6))                                    # Alt -30 Az 180, as in the field
        tw.start_tracking()
        tw.run(5)
        t0 = tw.clock.t
        tw.goto_altaz(189.2, 0.0)
        tw.run(2.9)
        tw.goto_altaz(180.0, 0.0)
        target = tw.polaris.altaz2radec(0.0, 180.0)
        tw.run(1.0)
        tw.pid.set_alpha_target({"roll": 0.0})
        tw.pid.set_rotate_complete_callback(lambda: None)
        while tw.clock.t - t0 < 45 and tw.polaris.goto_complete_at is None:
            tw.run(0.2)
        done = tw.polaris.goto_complete_at
        tw.run(60.0)
        off = radec_sep_arcmin(*target, *tw.true_radec())
        tw.close()
    finally:
        mp.undo()
    assert done is not None and done - t0 < 30 and off < 1.0, f"done {done and done - t0}, pointing {off:.1f}' off"


def test_guard_roll_change_after_a_goto_keeps_the_pointing():
    """Field 2026-10-16: rotator moves (roll -30 etc.) straight after a goto went straight in motor angles (17 deg
    off the target mid-roll), and on the pointing-holding path at full speed still left it ~60' off. Roll changes are
    classed by a pointing change small next to the roll, and planned holding the pointing (at full speed since
    2026-10-17: 15' here with M3's FAST speeds calibrated; the previous controller left it 180-530' off)."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0, calibrated=True)
        tw.place((290.0, 50.0, 0.0))
        tw.start_tracking()
        tw.run(5)
        ra, dec = tw.polaris.altaz2radec(42.4, 251.9)
        tw.goto_radec(ra, dec)
        tw.run(16.0)                                                       # as in the field: before it has settled
        tw.pid.set_alpha_target({"roll": -30.0})
        tw.pid.set_rotate_complete_callback(lambda: None)
        worst = 0.0
        for _ in range(100):
            tw.run(0.2)
            worst = max(worst, radec_sep_arcmin(ra, dec, *tw.true_radec()))
        tw.close()
    finally:
        mp.undo()
    assert worst < 25.0, f"pointing {worst:.1f}' off the target during the roll"


def test_guard_roll_change_during_a_goto_completes_on_target():
    """Field 2026-10-16, eq mode over a level alignment: a goto to Alt 30 redirected to Alt -30 kept the PA (roll 60),
    and a rotator move to 0 asked for 23 s later (~78 s of roll change, M1 at the then 1 deg/s) ran past the 45 s goto
    timeout: TIMED OUT after 60.6 s, 227" off, still rolling. Controlled paths now extend the timeout by their
    planned time, as straight moves do."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place((89.5, 30.5, 0.0))
        mp.setattr(Config, "advanced_eq_mode", True)
        tw.start_tracking()
        tw.run(5)
        tw.goto_altaz(180.0, 30.5)
        tw.run(12.7)
        t0 = tw.clock.t
        tw.goto_altaz(180.0, -30.0)
        tw.run(23.0)
        tw.pid.set_alpha_target({"roll": 0.0})
        tw.pid.set_rotate_complete_callback(lambda: None)
        while tw.clock.t - t0 < 200 and tw.polaris.goto_complete_at is None:
            tw.run(0.2)
        done = tw.polaris.goto_complete_at
        err = np.abs(np.array(tw.pid.theta_pv) - np.array(tw.pid.theta_ref)) * 3600
        tw.close()
    finally:
        mp.undo()
    assert done is not None and float(np.max(err)) < 30.0, f"done {done and done - t0}, error {err.round(0)}\""


def test_guard_roll_past_the_reach_while_tracking_keeps_the_pointing():
    """2026-10-17: a +90 roll at Alt 15 is past the roll the motors reach there (81 deg). The path ran in PA towards
    the unreachable PA; once its samples passed the reach the clip switched to the frame nearer level (a 175 deg jump),
    so the planner left it to the PID, which drove M2 past its limit: LIMIT, 74' off. The path now runs to the
    reachable PA."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0, calibrated=True)
        tw.place((90.0, 15.0, 0.0))
        tw.start_tracking()
        tw.run(10)
        target = (tw.polaris.rightascension, tw.polaris.declination)
        t0 = tw.clock.t
        tw.slew_relative(roll=90.0)
        worst = 0.0
        while tw.clock.t - t0 < 120 and tw.polaris.goto_complete_at is None:
            tw.run(0.2)
            worst = max(worst, radec_sep_arcmin(*target, *tw.true_radec()))
        done, mode = tw.polaris.goto_complete_at, tw.pid.mode
        off = radec_sep_arcmin(*target, *tw.true_radec())
        tw.close()
    finally:
        mp.undo()
    assert done is not None and mode == "TRACK", f"done {done}, mode {mode}"
    assert off < 0.2 and worst < 30.0, f"{off:.1f}' off at the end, {worst:.1f}' during the roll"


def test_guard_goto_sent_during_a_small_correction_is_planned_afresh():
    """Field 2026-10-17 (pano panel 14 -> 12): a goto sent while the last one's final correction ran (a small move,
    capped at SMALL_MOVE_RATE) was retargeted onto it: 80 deg at 0.21 deg/s, timed out at Alt -31 of 35. A redirect
    further than a small move is planned afresh (here straight in motor angles)."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place((218.5, 72.6, -132.7))
        a = np.array(tw.pid.alpha_pv, dtype=float)
        tw.goto_altaz(a[0] + 0.05, a[1], a[2])
        tw.run(0.6)
        small = np.array(getattr(tw.pid.goto_traj, "axis_rates", [np.inf]))
        t0 = tw.clock.t
        tw.goto_altaz(141.48, 35.33, 68.55)
        while tw.clock.t - t0 < 60 and tw.polaris.goto_complete_at is None:
            tw.run(0.5)
        done = tw.polaris.goto_complete_at
        alt = float(tw.pid.alpha_pv[1])
        tw.close()
    finally:
        mp.undo()
    assert np.all(small <= control.PID_Controller.SMALL_MOVE_RATE), "the setup needs a small correction under way"
    assert done is not None and done - t0 < 30 and abs(alt - 35.33) < 0.05, f"done {done and done - t0}, alt {alt:.2f}"


@pytest.mark.parametrize("theta3", [-8.0, -30.0])
def test_guard_alt_jog_through_gimbal_lock_does_not_flip(caplog, theta3):
    """Field 2026-10-17: jogging Alt down at 9 deg/s through M2 = 0 (M3 -8) logged a FLIP and swung M1, with M2 at -3
    (inside the -8 overlap). The jog holds Az and Roll, and through Alt 0 with any roll that pose needs M3 to swing
    90 deg; the reference stepped over the lock zone and swung M1/M3 30-70 deg. Near the lock jogs now walk the
    pointing in motor angles."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place((15.7, 5.0, theta3))
        theta0 = np.array(tw.pid.theta_pv, dtype=float)
        swing = 0.0
        with caplog.at_level("INFO"):
            tw.pid.set_axis_velocities({"alt": -9.0})
            def on(t):
                nonlocal swing
                swing = max(swing, float(np.max(np.abs((np.array(t.pid.theta_ref) - theta0)[[0, 2]]))))
            tw.run(1.3, on_measure=on)
            tw.pid.set_axis_velocities({"alt": 0.0})
            tw.run(6.0, on_measure=on)
        theta2 = float(tw.pid.theta_pv[1])
        tw.close()
    finally:
        mp.undo()
    flips = [r.getMessage() for r in caplog.records if "Transition" in r.getMessage()]
    assert not flips, flips
    assert theta2 < -2.0 and swing < 3.0, f"M2 {theta2:.1f}, M1/M3 reference swung {swing:.1f} deg"


@pytest.mark.parametrize("axis, rate", [("ra", -1.0), ("ra", -9.0), ("b", -3.0)])
def test_guard_sky_axis_jog_finishes_where_it_got_to(axis, rate):
    """Field 2026-10-17: an RA jog while not tracking barely moved. A RA/Dec/PA or galactic jog runs the PID in TRACK,
    and releasing it went IDLE at once: the motors stopped wherever they were, 1-2.5 deg short of the jog's reference,
    which was left behind them. It now finishes in AUTO on the Az/Alt the reference got to."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place((17.0, 32.0, -38.5))
        theta0 = np.array(tw.theta)
        tw.pid.set_axis_velocities({axis: rate})
        tw.run(4.8)
        tw.pid.set_axis_velocities({axis: 0.0})
        t0 = tw.clock.t
        while tw.pid.mode != "IDLE" and tw.clock.t - t0 < 30:
            tw.run(0.2)
        mode, moved = tw.pid.mode, float(np.max(np.abs(np.array(tw.theta) - theta0)))
        err = np.abs(np.array(tw.pid.theta_ref) - np.array(tw.pid.theta_pv)) * 60
        tw.close()
    finally:
        mp.undo()
    assert mode == "IDLE" and float(np.max(err)) < 2.0 and moved > 1.0, f"{mode}, moved {moved:.1f}, err {err.round(1)}'"


@pytest.mark.parametrize("start", [(180.0, 45.0, 0.01), (180.0, 12.0, 0.3)], ids=["from_home", "short"])
def test_guard_goto_into_gimbal_lock_does_not_stutter(start, caplog):
    """Field 2026-10-17: Home, then a goto to Alt 0 (level: M2 = 0, gimbal lock) stuttered badly: M1/M3 driven back and
    forth at up to 1.8 deg/s as M2 came in. The target's roll (0.01, from the home pose) can't be made at the lock, so
    theta_solutions found no end solution and the goto took a sampled path into the lock, its M1/M3 split swinging.
    End solutions at the lock now match the boresight, and a goto ending in the lock goes straight in motor angles."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place(start)
        ops = []
        with caplog.at_level("INFO"):
            tw.goto_altaz(180.03, 0.0)
            t0 = tw.clock.t
            while tw.clock.t - t0 < 40 and tw.polaris.goto_complete_at is None:
                tw.run(0.2, on_measure=lambda t: ops.append(np.array(t.pid.omega_op)))
        done = tw.polaris.goto_complete_at
        tw.close()
    finally:
        mp.undo()
    ops = np.array(ops)
    m1 = np.where(np.abs(ops[:, 0]) > 0.05, ops[:, 0], 0.0)
    reversals = int((np.diff(np.sign(m1)) != 0).sum())
    assert done is not None and any("GOTO plan: fast in motor angles" in r.getMessage() for r in caplog.records)
    assert float(np.abs(ops[:, 0]).max()) < 0.3 and reversals <= 2, f"M1 up to {np.abs(ops[:, 0]).max():.2f} deg/s, {reversals} reversals"


def test_motor_move_retarget_keeps_the_speed():
    move = MotorMove(8.0, 5.0)
    move.start(np.zeros(3), (60.0, 0.0, 0.0))
    for _ in range(40):
        _, before = move.step(0.1)
    move.retarget((-20.0, 0.0, 0.0))                                             # reversed mid-flight
    _, after = move.step(0.1)
    assert before[0] > 7.0 and abs(after[0] - before[0]) <= 5.0 * 0.1 + 1e-9      # no step in the command
    refs, _ = _run_move(move)
    assert refs[-1][0] == pytest.approx(-20.0)


def test_choose_end_solution_room_then_no_cable_wrap_then_time():
    now, still, rate, accel = np.array([0.0, 30.0, 180.0]), np.zeros(3), 8.0, 5.0
    near_wrap = np.array([170.0, 30.0, 350.0])          # a flip turning M1 and M3 the same way: fastest
    far_ok = np.array([-190.0, 30.0, 350.0])            # the opposite turns: slower
    sols = np.array([near_wrap, far_ok])
    assert wraps_cables(now, near_wrap) and not wraps_cables(now, far_ok)
    assert choose_end_solution(sols, now, still, rate, accel) == 1
    assert choose_end_solution(sols, now, still, rate, accel, has_room=lambda t: t[0] > 0) == 0   # room first
    assert choose_end_solution(np.empty((0, 3)), now, still, rate, accel) is None


def test_choose_end_solution_keeps_the_cables_within_their_twist():
    now, still, rate, accel = np.array([0.0, 15.0, 180.0]), np.zeros(3), 7.1, 5.0
    wound = np.array([274.0, 21.1, 224.0])              # M3 +44: faster, net twist +318
    unwound = np.array([274.0, 21.1, -136.0])           # M3 -316: slower, net twist -42
    sols = np.array([wound, unwound])
    twist = lambda t: (t[0] - 180.0) + t[2]             # raw M1 (theta - 180) + raw M3
    assert choose_end_solution(sols, now, still, rate, accel) == 0
    assert choose_end_solution(sols, now, still, rate, accel, twist=twist) == 1
    both_wound = np.array([wound, wound + np.array([0.0, 0.0, 720.0])])
    assert choose_end_solution(both_wound, now, still, rate, accel, twist=twist) == 0    # else the least twisted


def test_guard_goto_does_not_wind_the_cables(caplog):
    """Field 2026-10-17 (pano panel 41 -> 40): after a flip left M1 at raw -180, a goto to Az 140 Alt -15 had to turn
    M1 +274 (the short way passed its limit), and turned M3 +44 with it rather than -316: 6 s faster, but the cables
    wound to +318. End solutions now keep the net twist (raw M1 + M3) within CABLE_TWIST_MAX_DEG."""
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place((0.0, 15.0, 180.0))                    # raw M1 -180, M3 +180: net 0, as panel 41 left it
        with caplog.at_level("INFO"):
            tw.goto_altaz(140.0, -15.0, 15.0)
            t0 = tw.clock.t
            while tw.clock.t - t0 < 90 and tw.polaris.goto_complete_at is None:
                tw.run(0.5)
        zeta = np.array(tw.pid.zeta_meas, dtype=float)
        done = tw.polaris.goto_complete_at
        tw.close()
    finally:
        mp.undo()
    assert done is not None and abs(zeta[0] + zeta[2]) <= control_plan.CABLE_TWIST_MAX_DEG + 1.0, \
        f"raw M1 {zeta[0]:+.0f} M3 {zeta[2]:+.0f}: twist {zeta[0] + zeta[2]:+.0f}"


def test_choose_end_solution_lets_a_small_move_near_the_twist_limit_go_the_fast_way():
    """Below the horizon the flipped branch sits at a twist of +-270-287 (M3 near 180): a 3 deg goto there (+4-7)
    chose a 360 deg M3 unwind, 50-56 s slower, and timed out. Within CABLE_TWIST_SLACK_DEG past the limit, a move
    winding the cables no more than that further goes the fast way; beyond it, or winding further, it doesn't."""
    still, rate, accel = np.zeros(3), 7.1, 5.0
    twist = lambda t: (t[0] - 180.0) + t[2]             # raw M1 (theta - 180) + raw M3
    lim, slack = control_plan.CABLE_TWIST_MAX_DEG, control_plan.CABLE_TWIST_SLACK_DEG

    def chosen(twist_now, twist_fast):
        now = np.array([180.0 + twist_now - 180.0, 5.0, 180.0])
        fast = np.array([now[0] + (twist_fast - twist_now), 5.0, 180.0])
        unwound = fast - [0.0, 0.0, 360.0]                # M3 the other way round: slower, twist - 360
        return choose_end_solution(np.array([fast, unwound]), now, still, rate, accel, twist=twist)

    assert chosen(270.0, 274.0) == 0                      # a 3 deg goto at the flipped branch: the fast way
    assert chosen(lim + slack - 10, lim + slack - 5) == 0
    assert chosen(lim + slack - 10, lim + slack + 5) == 1     # past the slack: unwound
    assert chosen(lim - 20, lim + slack - 5) == 1         # winding them more than the slack further: unwound


def test_guard_goto_while_tracking_at_the_m2_limit_ends_its_move():
    """A goto while tracking whose PA the motors can't reach (M2 at its 81.5 deg limit near the zenith) aims at the
    reachable PA: its move compared that with the PA asked for, 25 deg apart, re-planned every tick and never ended,
    so tracking's feed-forward never resumed and the goto timed out (a 3 deg goto at Alt 82)."""
    from kinematics import azaltroll_to_theta_ik, reachable_azaltroll
    mp = pytest.MonkeyPatch()
    try:
        tw = Twin(mp, config={"coordinated_speed_control": True}, seed=0)
        tw.place(azaltroll_to_theta_ik(*reachable_azaltroll(0.0, 82.0, 0.0)))
        tw.start_tracking()
        tw.run(30)
        cosd = math.cos(math.radians(tw.pid.delta_sp[1]))
        tw.slew_relative(ra=3.0 / max(cosd, 0.1) / 15, dec=-3.0)
        t0, ended = tw.clock.t, None
        while tw.clock.t - t0 < 20 and ended is None:
            tw.run(0.5)
            if tw.pid.goto_traj is None and np.any(tw.pid.omega_ff != 0):
                ended = tw.clock.t - t0
        tw.close()
    finally:
        mp.undo()
    assert ended is not None and ended < 12, f"the move never ended (re-planned every tick)" if ended is None else ended


def test_idle_gotos_end_on_an_enumerated_solution(sweep):
    idle = sweep[sweep.case.str.endswith("idle") & sweep.done_s.notna() & (sweep.miss_arcmin < 2.0)]   # arrived
    assert len(idle) > 0
    missing = idle[idle.t_chosen_s.isna()]
    assert missing.empty, f"final pose matched no end solution: seeds {missing.seed.tolist()} ({missing.case.tolist()})"


# ---------------------------------------------------------------------------------------
# Acceptance criteria (docs/study_goto_response.md): xfail until the redesign lands
# ---------------------------------------------------------------------------------------

BASELINE = pytest.mark.xfail(strict=False, reason="baseline: today's planner (study acceptance criteria)")


@BASELINE
def test_every_goto_completes_on_target(sweep):
    bad = sweep[sweep.done_s.isna() | (sweep.miss_arcmin > 2.0)]
    assert bad.empty, f"{len(bad)} gotos incomplete or > 2' off:\n{bad[['case', 'seed', 'done_s', 'miss_arcmin']]}"


@BASELINE
def test_no_motor_limit(sweep):
    bad = sweep[sweep.limit]
    assert bad.empty, f"{len(bad)} gotos reached a motor limit:\n{bad[['case', 'seed']]}"


@BASELINE
def test_no_mid_goto_remap(sweep):
    bad = sweep[sweep.remaps.map(bool)]
    assert bad.empty, f"{len(bad)} gotos remapped mid-goto:\n" + "\n".join(
        f"  {r.case} seed {r.seed}: {r.remaps[0]}" for r in bad.itertuples())


@BASELINE
def test_chosen_end_solution_within_2s_of_the_best(sweep):
    slower = sweep[((sweep.t_chosen_s - sweep.t_best_s) > 2.0) & ~sweep.best_room_short]
    assert slower.empty, f"{len(slower)} gotos chose an end solution > 2 s slower than the best:\n" \
                         f"{slower[['case', 'seed', 't_best_s', 't_chosen_s']]}"


@BASELINE
@pytest.mark.parametrize("case", CASES.keys())
def test_median_arrival_within_1_3x_the_best(sweep, case):
    g = sweep[(sweep.case == case) & sweep.done_s.notna() & (sweep.miss_arcmin <= 2.0)]
    ratio = float((g.done_s / g.t_best_s).median())
    assert ratio <= 1.3, f"{case}: median arrival {ratio:.2f}x the best"


@BASELINE
def test_planning_work_per_tick_within_budget(sweep):
    worst = int(sweep.max_work_per_tick.max())
    assert worst <= KINEMATICS_PER_TICK, f"a tick did {worst} kinematics calls (budget {KINEMATICS_PER_TICK})"


# ---------------------------------------------------------------------------------------
# The full sweep: the study's report
# ---------------------------------------------------------------------------------------

@pytest.mark.slow
def test_full_sweep_report():
    df = run_sweep(FULL, seed0=1000)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print("\n" + summarise(df).to_string(index=False))
    path = os.environ.get("GOTO_SWEEP_CSV")
    if path:
        df.drop(columns=["remaps"]).assign(remaps=df.remaps.map(len)).to_csv(path, index=False)
    assert len(df) == FULL * len(CASES)
