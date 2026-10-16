"""
Goto planning (driver/control_plan.py): the digital twin sweep against the acceptance criteria of
docs/study_goto_response.md.

Random gotos in the digital twin, level and eq (wedge) mode, idle and while tracking. Per goto: the time to complete,
the theoretical best (the fastest end solution, each motor moving on its own at Kv / Ka from rest to rest:
kinematics.theta_solutions, control_plan.min_move_time), the end solution the driver chose, motor limits, mid-goto
remaps (UNWIND / FLIP / LOCK / EQ ROOM transitions), the tripod cone and rig tilt along the path, M1's tracking
room, and the kinematics work done per control tick (R4: counted calls, not wall time, so it is the same on any
machine).

The acceptance tests are xfail(strict=False) until the redesign lands: they record what today's planner does, and one
that starts passing shows as XPASS. A seeded subset runs in the suite; the full sweep (--runslow) prints the report
the study quotes:

    uv run pytest tests/test_control_plan.py --runslow -s -k report
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
from control_eq import rig_tilt_deg, THETA2_MIN                                  # noqa: E402
from control_plan import min_move_time                                           # noqa: E402
from kinematics import (theta_solutions, theta_to_q, azaltroll_to_q, q_to_azaltroll, vector_to_az_alt,  # noqa: E402
                        THETA2_MAX)
from sim_digital_twin import Twin                                                 # noqa: E402
from test_motion_outcomes import radec_sep_arcmin                                 # noqa: E402

CASES = {"level_idle": (False, False), "level_track": (False, True), "eq_idle": (True, False), "eq_track": (True, True)}
SUBSET, FULL = 10, 150             # gotos per case: in the suite / the full sweep (--runslow)
TIMEOUT_S = 120.0
ZETA_OFFSET = np.array([180.0, 45.0, 0.0])            # motor angle = raw zeta + this (sim_digital_twin)
TRIPOD_CONE_DEG = 8.5               # study R1
TRACK_ROOM_DEG = 120.0              # 8 h of M1 for tracking (control_eq.EQ_MIN_TRACK_ROOM_DEG)
KINEMATICS_PER_TICK = 40            # R4 budget, provisional: until a Pi Zero 2 W benchmark sets it in time
REMAP_WORDS = (" Transition", "EQ ROOM")
GOTO_TIMEOUT_S = 45.0               # PID_Controller.goto_timeout: the goto is marked complete wherever it is


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
        tw = Twin(mp, config={"coordinated_speed_control": True, "advanced_eq_mode": eq}, seed=seed)
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
    poses = [alignQ * theta_to_q(*t) for t in trace[::2]]
    bores = np.array([p.rotate([0.0, 0.0, -1.0]) for p in poses])
    return {
        "case": case, "seed": seed, "done_s": done, "miss_arcmin": miss_arcmin,
        "t_best_s": float(times.min()) if len(times) else np.nan,
        "t_chosen_s": float(times[chosen]) if chosen_ok else np.nan,
        "n_solutions": len(sols),
        "limit": bool((trace < lo - 1e-6).any() or (trace > hi + 1e-6).any() or "LIMIT" in modes),
        "remaps": [m for m in records.messages if any(w in m for w in REMAP_WORDS)],
        "min_nadir_deg": float(90 + np.degrees(np.arcsin(np.clip(bores[:, 2], -1, 1))).min()),
        "max_rig_tilt_deg": float(max(rig_tilt_deg(p) for p in poses)),
        "room_deg": room,
        "best_room_short": bool(track and len(sols) and _room_short(sols[int(np.argmin(times))], kv)),
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
            "entered tripod cone": int((g.min_nadir_deg < TRIPOD_CONE_DEG).sum()),
            "rig tilt > 100": int((g.max_rig_tilt_deg > 100).sum()),
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
def test_eq_paths_stay_out_of_the_tripod_cone(sweep):
    eq = sweep[sweep.case.str.startswith("eq")]
    bad = eq[eq.min_nadir_deg < TRIPOD_CONE_DEG]
    assert bad.empty, f"{len(bad)} eq gotos entered the tripod cone:\n{bad[['case', 'seed', 'min_nadir_deg']]}"


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
