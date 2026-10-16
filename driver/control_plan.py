# -----------------------------------------------------------------------------
# control_plan.py - Goto planning for the PID controller
# -----------------------------------------------------------------------------
#
# The reference trajectories the PID follows during a goto (coordinated_speed_control) and the jog shaping:
#
#   GotoTrajectory      a controlled pointing path: the pointing on a great circle from start to target (Az/Alt, or
#                       RA/Dec while tracking), roll/PA in proportion, sampled in motor space and walked at the fastest
#                       speed the motors allow, with the velocity as feed-forward; re-plans from the current speed when
#                       the target moves.
#   MotorTrajectory     the same profile along a straight line in motor angles (a flip past gimbal lock).
#   ramp_rates          jog shaping: each axis rate toward its target within the acceleration limit.
#   min_move_time       the shortest rest-to-rest time of one motor's move within its speed and acceleration.
#
# PID_Controller.plan_goto (control.py) decides when a goto is planned and steps the trajectory every tick. The goto
# redesign (docs/study_goto_response.md: end solution chosen once, controlled paths for moves of 15 deg or less,
# closed-form straight motor moves above, planning that never blocks the tick) builds here.
# -----------------------------------------------------------------------------
import math

import numpy as np

from quaternion import Q as Quaternion
from kinematics import wrap180, azaltroll_to_q, q_to_azaltroll


def min_move_time(distance, max_rate, max_accel):
    """Shortest time (s) for one motor to move distance (deg) from rest to rest within max_rate (deg/s) and max_accel
    (deg/s^2): accelerate, cruise, decelerate, or a triangle when it never reaches max_rate. Works on arrays."""
    d, v, a = np.abs(np.asarray(distance, dtype=float)), np.asarray(max_rate, dtype=float), float(max_accel)
    return np.where(d >= v * v / a, d / v + v / a, 2.0 * np.sqrt(d / a))


def ramp_rates(current, target, max_step):
    """Move each axis rate toward its target by at most max_step (max_accel * dt): jog shaping, so a
    jog's reference motion and feed-forward never ask the motors for more than their acceleration."""
    current = np.asarray(current, dtype=float)
    return current + np.clip(np.asarray(target, dtype=float) - current, -max_step, max_step)


class GotoTrajectory:
    """Reference trajectory for a goto, with velocity feed-forward.

    The PID reaches a far-away reference by chasing it from wherever the mount is, which moves the
    motors in near-straight lines in motor space. Paths that hold Az/Alt while roll changes are
    strongly curved in motor space (at low alt/low roll M1 and M3 counter-rotate), so chasing cuts
    across them (50'-750' off in simulation). Instead, this moves the reference itself along the
    planned path - Az/Alt on a great circle and roll linearly, as alpha_limit_step plans it - no
    faster than the motors can follow, and gives the reference velocity as feed-forward, so the PID
    only corrects small errors.

    On start/retarget the path is sampled in motor space and given a speed profile: the path speed
    (fastest axis) keeps every axis within its max_rate (a limit per axis, or one for all), slows where the path curves so that per-axis acceleration
    from turning stays within half of max_accel, and speeds up / slows down within the acceleration
    that turning leaves over, from the
    current speed to a stop at the goal. step() then walks the profile.

    to_theta(alpha, theta_near) converts Az/Alt/Roll to motor angles on the branch nearest theta_near.
    """
    SAMPLES = 200
    TURN_SHARE = 0.5
    BRANCH_JUMP_DEG = 30.0                                   # one sample step this large is an IK branch change

    def __init__(self, to_theta, max_rate, max_accel):
        self.to_theta = to_theta
        self.axis_rates = np.broadcast_to(np.asarray(max_rate, dtype=float), (3,)).copy()   # per-axis limits
        self.max_rate = float(np.max(self.axis_rates))
        self.max_accel = float(max_accel)
        self.done = True
        self._at_goal = True
        self.branch_change = False

    def start(self, alpha, theta, goal):
        self._alpha = np.asarray(alpha, dtype=float)
        self._theta = np.asarray(theta, dtype=float)
        self._speed = 0.0
        self.retarget(goal)

    def retarget(self, goal):
        """New goal: re-plan from the current reference position and speed."""
        self.goal = np.asarray(goal, dtype=float)
        fracs = np.linspace(0.0, 1.0, self.SAMPLES + 1)
        thetas = [self._theta]
        for f in fracs[1:]:
            thetas.append(self.to_theta(self._interp(self._alpha, self.goal, f), thetas[-1]))
        thetas = np.array(thetas)
        seg = np.diff(thetas, axis=0)
        ds = np.max(np.abs(seg), axis=1)                       # path length in fastest-axis degrees
        # the path switches IK branch (M1/M3 +-180, M2 mirrored, e.g. to reach a negative altitude): the
        # reference can't be walked across the jump - the caller leaves such a goto to the PID/FLIP
        self.branch_change = bool(np.max(ds, initial=0.0) > self.BRANCH_JUMP_DEG)
        s = np.concatenate([[0.0], np.cumsum(ds)])
        u = seg / np.maximum(ds, 1e-12)[:, None]              # per-axis rate per unit path speed
        # path speed cap: each axis within its own limit (axis rate = path speed * |u|)
        seg_cap = np.min(self.axis_rates[None, :] / np.maximum(np.abs(u), 1e-12), axis=1)
        cap = np.concatenate([[seg_cap[0]], np.minimum(seg_cap[:-1], seg_cap[1:]), [seg_cap[-1]]])
        v = cap.copy()
        kappa = np.max(np.abs(np.diff(u, axis=0)), axis=1) / np.maximum((ds[:-1] + ds[1:]) / 2, 1e-12)
        # turning takes at most half of max_accel, leaving the rest for speeding up / slowing down
        v[1:-1] = np.minimum(v[1:-1], np.sqrt(self.TURN_SHARE * self.max_accel / np.maximum(kappa, 1e-12)))
        v[0], v[-1] = min(self._speed, v[0]), 0.0
        k = np.concatenate([[0.0], kappa, [0.0]])               # curvature at every sample

        def spare(i, vi):                                       # acceleration left once turning takes its share
            return max(self.max_accel - vi * vi * k[i], 0.1 * self.max_accel)

        for i in range(1, len(s)):                              # forward: speed up within what's left
            v[i] = min(v[i], math.sqrt(v[i - 1] ** 2 + 2 * spare(i - 1, v[i - 1]) * ds[i - 1]))
        for i in range(len(s) - 2, -1, -1):                     # backward: be able to stop at the goal
            v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2 * spare(i + 1, v[i + 1]) * ds[i]))
        self._start_alpha, self._fracs, self._s, self._v, self._k, self._cap = self._alpha.copy(), fracs, s, v, k, cap
        self._pos = 0.0
        self._at_goal = s[-1] < 1e-9
        self.done = False

    def step(self, dt):
        """Returns (theta_ref, omega_ff): the reference now, and the velocity that takes it to where
        it will be one dt later (where it then advances to)."""
        now = self._theta.copy()
        if self._at_goal:                                       # the reference is at the goal: done once it
            self.done = True                                    # has been handed out as theta_ref
            self._speed = 0.0
            return now, np.zeros(3)
        a_dt = self.max_accel * dt
        remaining = self._s[-1] - self._pos
        k = float(np.interp(self._pos, self._s, self._k))      # speed up only within what turning leaves over
        up_dt = max(self.max_accel - self._speed ** 2 * k, 0.1 * self.max_accel) * dt
        # read the profile where the reference would be after speeding up for this step, interpolating v^2
        # (exact under constant acceleration): reading v at the current position, near a sqrt(2as) start,
        # made the speed grow exponentially from ~0 - the reference crept for ~1.6 s before moving
        probe = self._pos + (self._speed + up_dt) * dt
        target = math.sqrt(float(np.interp(probe, self._s, self._v ** 2)))
        rate_cap = min(float(np.interp(self._pos, self._s, self._cap)), float(np.interp(probe, self._s, self._cap)))
        speed = min(max(target, self._speed - a_dt), self._speed + up_dt, rate_cap)
        if remaining <= max(speed, a_dt) * dt:
            pos = self._s[-1]                                   # last step lands on the goal
        else:
            pos = self._pos + max(speed, 1e-6) * dt
        cap = min(max(speed, a_dt), rate_cap) * dt
        for _ in range(4):                                      # the exact step may be a little longer than
            frac = float(np.interp(pos, self._s, self._fracs))  # the sampled profile says: shorten it to cap
            alpha = self._interp(self._start_alpha, self.goal, frac)
            theta = self.to_theta(alpha, now)
            moved = float(np.max(np.abs(theta - now)))
            if moved <= cap * (1 + 1e-9):
                break
            pos = self._pos + (pos - self._pos) * cap / moved * 0.999
        rate = (theta - now) / dt
        self._alpha, self._theta, self._pos = alpha, theta, pos
        self._speed = float(np.max(np.abs(rate)))
        if pos >= self._s[-1]:
            self._at_goal = True
        return now, rate

    @staticmethod
    def _interp(a, b, frac):
        """Az/Alt along the great circle (slerp at roll 0) and roll linearly, like alpha_limit_step."""
        q_a, q_b = azaltroll_to_q(a[0], a[1], 0.0), azaltroll_to_q(b[0], b[1], 0.0)
        az, alt, _ = q_to_azaltroll(Quaternion.slerp(q_a, q_b, frac))
        return np.array([az, alt, a[2] + frac * wrap180(b[2] - a[2])])


class MotorTrajectory(GotoTrajectory):
    """A GotoTrajectory along a straight line in motor angles (its 'alpha' is theta): for a move that must go
    straight to the target's motor angles, e.g. a flip past gimbal lock, with the same speed/acceleration
    profile (no PID overshoot at the end)."""
    def __init__(self, max_rate, max_accel):
        super().__init__(lambda theta, theta_near: np.asarray(theta, dtype=float), max_rate, max_accel)
        self.space = 'THETA'

    @staticmethod
    def _interp(a, b, frac):
        return np.asarray(a, dtype=float) + frac * (np.asarray(b, dtype=float) - np.asarray(a, dtype=float))
