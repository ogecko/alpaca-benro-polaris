"""
Purpose tests for goto trajectory planning and jog shaping (driver/control.py GotoTrajectory,
ramp_rates).

What goto planning is for:
  1. While the target changes only in roll, the telescope keeps pointing at the same Az/Alt.
     (Today the PID chases a reference recomputed from the current pose, so the mount follows a
     pursuit curve in motor space that cuts across the constant-Az/Alt path: 50'-750' off.)
  2. Every goto reaches its target and settles, in a time close to what the motors allow.
  3. The motor reference moves no faster, and accelerates no harder (per axis, including the
     path's curvature), than the motors can follow.
  4. The feed-forward velocity handed to the PID is the reference's own velocity.
  5. A new target mid-move continues smoothly from where the reference is.

What jog shaping is for:
  6. Pressing or releasing a jog never asks the motors for more than their acceleration.
  7. After a jog is released the mount stops close to where the reference stopped (small
     overshoot) and settles quickly. (Today: ~107' overshoot, 8 s to settle.)

Closed loop: planner/jog -> PID -> motors (ideal integrators), identity alignment so motor angles
and Az/Alt/Roll are related by IK/FK. The PID mirrors PID_Controller's law with the new structure
these features rely on: the feedback part (Kp, Kd damping, output smoothing, acceleration clamp)
is smoothed and clamped; the planner/jog feed-forward, already shaped within the motor limits, is
added after. The error is taken against the reference at the current time.
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

from kinematics import azaltroll_to_theta_ik, theta_to_azaltroll_fk        # noqa: E402
from control import GotoTrajectory, ramp_rates                              # noqa: E402

KP, KD, KE = 1.0, 0.5, 0.4        # driver/config.toml pid_Kp, pid_Kd, pid_Ke
KV, KA = 8.9, 5.0                 # max motor speed (deg/s, calibrated max) and acceleration (deg/s^2)
PLAN_RATE = 0.8 * KV              # planner speed limit (headroom for the feedback part)
DT, SUB = 0.2, 20                 # PID period, motor integration sub-steps per period
ARCMIN = 60.0


def wrap180(x):
    return (np.asarray(x) + 180.0) % 360.0 - 180.0


def to_theta(alpha, theta_near):
    """Az/Alt/Roll -> motor angles on the branch nearest theta_near (identity alignment)."""
    t = np.array(azaltroll_to_theta_ik(*alpha), dtype=float)
    return theta_near + wrap180(t - theta_near)


def pointing_error_arcmin(theta, az, alt):
    a, h, _ = theta_to_azaltroll_fk(*theta)
    a1, h1, a2, h2 = map(math.radians, (az, alt, a, h))
    c = math.sin(h1) * math.sin(h2) + math.cos(h1) * math.cos(h2) * math.cos(a1 - a2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c)))) * ARCMIN


class Pid:
    """PID_Controller law, feedback smoothed/clamped, shaped feed-forward added after."""
    def __init__(self):
        self.fb = np.zeros(3)
        self.op = np.zeros(3)

    def step(self, err, ff):
        tgt = KP * err - KD * self.fb
        ctl = self.fb + np.clip((tgt - self.fb) / DT, -KA, KA) * DT
        self.fb = ctl * (1 - KE) + KE * self.fb
        self.op = np.clip(self.fb + ff, -KV, KV)
        return self.op


def goto(start, goal, max_time=120.0, retarget=None):
    """Run a goto from alpha `start` to alpha `goal`. Returns a dict of what happened."""
    theta = to_theta(start, np.array([180.0, 45.0, 0.0]))
    traj = GotoTrajectory(to_theta, max_rate=PLAN_RATE, max_accel=KA)
    traj.start(np.asarray(start, float), theta.copy(), np.asarray(goal, float))
    pid = Pid()
    roll_only = np.allclose(goal[:2], start[:2])
    worst_pointing, refs, ffs, ops, t = 0.0, [], [], [], 0.0
    while t < max_time:
        if retarget and abs(t - retarget[0]) < DT / 2:
            traj.retarget(np.asarray(retarget[1], float))
            goal = retarget[1]
        theta_ref, omega_ff = traj.step(DT)            # reference now, and its velocity over the next DT
        refs.append(theta_ref.copy())
        ffs.append(omega_ff.copy())
        op = pid.step(theta_ref - theta, omega_ff)
        ops.append(op.copy())
        for _ in range(SUB):
            theta = theta + op * DT / SUB
            if roll_only:
                worst_pointing = max(worst_pointing, pointing_error_arcmin(theta, goal[0], goal[1]))
        t += DT
        a, h, r = theta_to_azaltroll_fk(*theta)
        if traj.done and pointing_error_arcmin(theta, goal[0], goal[1]) < 1.0 and abs(wrap180(r - goal[2])) < 0.05 \
                and np.max(np.abs(op)) < 0.01:
            break
    return {"time": t, "theta": theta, "worst_pointing": worst_pointing, "refs": np.array(refs),
            "ffs": np.array(ffs), "ops": np.array(ops), "settled": t < max_time}


ROLL_MOVES = {
    "alt20_roll_0_to_45": ((180.0, 20.0, 0.0), (180.0, 20.0, 45.0)),
    "alt20_roll_30_to_75": ((180.0, 20.0, 30.0), (180.0, 20.0, 75.0)),
    "alt45_roll_0_to_45": ((180.0, 45.0, 0.0), (180.0, 45.0, 45.0)),
    "alt45_roll_-30_to_20": ((180.0, 45.0, -30.0), (180.0, 45.0, 20.0)),
    "alt70_roll_0_to_45": ((0.0, 70.0, 0.0), (0.0, 70.0, 45.0)),
}


@pytest.mark.parametrize("start,goal", ROLL_MOVES.values(), ids=ROLL_MOVES.keys())
def test_roll_only_goto_keeps_pointing(start, goal):
    r = goto(start, goal)
    assert r["worst_pointing"] <= 10.0, (
        f"roll {start[2]:+.0f} -> {goal[2]:+.0f} at Az {goal[0]:.0f} Alt {goal[1]:.0f}: pointing wandered "
        f"{r['worst_pointing']:.1f}' from the target Az/Alt (limit 10')")


GOTOS = dict(ROLL_MOVES, **{
    "az_alt_roll_all_change": ((150.0, 30.0, 0.0), (200.0, 55.0, 20.0)),
    "az_only": ((100.0, 40.0, 10.0), (130.0, 40.0, 10.0)),
})


@pytest.mark.parametrize("start,goal", GOTOS.values(), ids=GOTOS.keys())
def test_goto_reaches_target_in_time_the_motors_allow(start, goal):
    r = goto(start, goal)
    theta_goal = to_theta(goal, to_theta(start, np.array([180.0, 45.0, 0.0])))
    travel = np.max(np.abs(r["refs"][-1] - r["refs"][0]))
    allowed = 2.0 * travel / PLAN_RATE + 6.0
    assert r["settled"], f"goto {start} -> {goal} did not settle within 120 s"
    assert np.max(np.abs(wrap180(r["theta"] - theta_goal))) < 0.1, "goto ended away from the target motor angles"
    assert r["time"] <= allowed, (
        f"goto {start} -> {goal} took {r['time']:.1f} s; {travel:.0f} deg of motor travel should take <= {allowed:.1f} s")


@pytest.mark.parametrize("start,goal", GOTOS.values(), ids=GOTOS.keys())
def test_reference_stays_within_motor_limits(start, goal):
    """Every axis of the reference moves no faster than the planner rate and accelerates no harder than
    max_accel - including the acceleration that comes from the path curving in motor space."""
    refs = goto(start, goal)["refs"]
    rate = np.diff(refs, axis=0) / DT
    accel = np.diff(rate, axis=0) / DT
    assert np.max(np.abs(rate)) <= PLAN_RATE + 1e-6, f"reference moved at {np.max(np.abs(rate)):.2f} deg/s (limit {PLAN_RATE:.2f})"
    assert np.max(np.abs(accel)) <= 1.1 * KA, f"reference accelerated at {np.max(np.abs(accel)):.2f} deg/s^2 on one axis (limit {KA})"


@pytest.mark.parametrize("move,rate", [("az_only", PLAN_RATE), ("az_only", 0.21), ("az_alt_roll_all_change", PLAN_RATE)],
                         ids=["az_only_fast", "az_only_small_move_rate", "az_alt_roll_all_change"])
def test_reference_starts_moving_at_once(move, rate):
    """From rest the reference speeds up at max_accel from the first step (no dead time before it moves).
    Was: the speed profile read near its sqrt(2as) start grew the speed exponentially from ~0, so the
    reference crept for ~1.6 s before moving (3-4 s on the mount with FAST lag)."""
    start, goal = GOTOS[move]
    theta = to_theta(start, np.array([180.0, 45.0, 0.0]))
    traj = GotoTrajectory(to_theta, max_rate=rate, max_accel=KA)
    traj.start(np.asarray(start, float), theta, np.asarray(goal, float))
    speeds = [float(np.max(np.abs(traj.step(DT)[1]))) for _ in range(5)]
    expected = [min(KA * DT * (k + 1), rate) for k in range(5)]
    assert all(s >= 0.9 * e for s, e in zip(speeds, expected)), (
        f"{move} at up to {rate:.2f} deg/s: reference speed over the first 1 s was {np.round(speeds, 3).tolist()} deg/s, "
        f"expected to follow max_accel {KA} deg/s^2: {np.round(expected, 3).tolist()}")


def test_branch_change_on_the_path_is_flagged():
    """A path the motors can only follow by switching IK branch (M1/M3 +-180, M2 mirrored - e.g. below
    theta2 -8 on the way to a negative altitude) can't be walked by the reference: it is flagged so the
    goto is left to the PID and its FLIP handling. Was: the reference stalled at the jump (near alt 0 on
    the mount) for ~20 s, then leapt 180 deg."""
    def to_theta_with_branch(alpha, theta_near):
        t = to_theta(alpha, theta_near)
        if alpha[1] < -8:                                          # only the other branch is valid down here
            t = np.array([t[0] + 180.0, -t[1], t[2] - 180.0])
        return t
    start, goal = (130.0, 30.0, 0.0), (130.0, -30.0, 0.0)
    theta = to_theta(start, np.array([180.0, 45.0, 0.0]))
    traj = GotoTrajectory(to_theta_with_branch, max_rate=PLAN_RATE, max_accel=KA)
    traj.start(np.asarray(start, float), theta, np.asarray(goal, float))
    assert traj.branch_change, "a 180 deg IK branch change on the planned path must be flagged"
    traj = GotoTrajectory(to_theta, max_rate=PLAN_RATE, max_accel=KA)
    traj.start(np.asarray(start, float), theta, np.asarray((200.0, 60.0, 30.0), float))
    assert not traj.branch_change, "a continuous path must not be flagged as a branch change"


def test_feed_forward_is_the_reference_velocity():
    r = goto(*ROLL_MOVES["alt45_roll_0_to_45"])
    assert np.allclose(r["ffs"][:-1], np.diff(r["refs"], axis=0) / DT, atol=1e-9), (
        "omega_ff must be the velocity that takes the reference to its next position")


def test_new_target_mid_move_continues_smoothly():
    start, goal = ROLL_MOVES["alt45_roll_0_to_45"]
    r = goto(start, goal, retarget=(2.0, (180.0, 45.0, -20.0)))
    step = np.max(np.abs(np.diff(r["refs"], axis=0)))
    assert r["settled"], "goto did not settle after being retargeted mid-move"
    assert step <= PLAN_RATE * DT + 1e-6, f"reference jumped {step:.2f} deg in one tick when retargeted"
    _, _, roll = theta_to_azaltroll_fk(*r["theta"])
    assert abs(wrap180(roll + 20.0)) < 0.05, f"ended at roll {roll:.2f}, not the new target -20"


# ---------------------------------------------------------------------------------------
# Jogs
# ---------------------------------------------------------------------------------------

def jog(rate, on_s=5.0, total_s=15.0):
    """Jog motor axis 0 at `rate` for on_s seconds, then release. The jog rate is shaped by ramp_rates;
    the reference moves at the shaped rate, which is also the feed-forward."""
    theta, ref, v = np.zeros(3), np.zeros(3), np.zeros(3)
    pid, t, peak_accel, prev_op = Pid(), 0.0, 0.0, np.zeros(3)
    overshoot, settle, lag = 0.0, None, 0.0
    while t < total_s:
        want = np.array([rate if t < on_s else 0.0, 0.0, 0.0])
        v = ramp_rates(v, want, KA * DT)
        op = pid.step(ref - theta, v)
        peak_accel = max(peak_accel, float(np.max(np.abs(op - prev_op))) / DT)
        prev_op = op.copy()
        ref = ref + v * DT
        theta = theta + op * DT
        t += DT
        if 2.0 < t < on_s:
            lag = max(lag, abs(ref[0] - theta[0]))
        if t >= on_s:
            overshoot = max(overshoot, float((theta[0] - ref[0]) * np.sign(rate)))
            if settle is None and v[0] == 0 and abs(ref[0] - theta[0]) < 1 / 60 and abs(op[0]) < 0.01:
                settle = t - on_s
    return {"peak_accel": peak_accel, "overshoot": overshoot * ARCMIN, "settle": settle, "lag": lag * ARCMIN}


@pytest.mark.parametrize("rate", [0.5, 3.0, -6.0])
def test_jog_press_and_release_stay_within_motor_acceleration(rate):
    r = jog(rate)
    assert r["peak_accel"] <= 1.1 * KA, f"a {rate} deg/s jog commanded {r['peak_accel']:.1f} deg/s^2 (limit {KA})"


@pytest.mark.parametrize("rate", [0.5, 3.0, -6.0])
def test_jog_release_stops_close_and_settles(rate):
    r = jog(rate)
    assert r["overshoot"] <= 10.0, f"after a {rate} deg/s jog the mount overshot by {r['overshoot']:.1f}' (limit 10')"
    assert r["settle"] is not None and r["settle"] <= 3.0, f"after a {rate} deg/s jog it took {r['settle']} s to settle (limit 3 s)"


def test_ramp_rates_moves_each_axis_toward_target_by_at_most_max_step():
    v = ramp_rates(np.array([0.0, 2.0, -1.0]), np.array([3.0, 2.0, 1.0]), 1.0)
    assert np.allclose(v, [1.0, 2.0, 0.0]), f"ramp_rates gave {v}"
