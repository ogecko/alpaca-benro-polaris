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
#   MotorMove           a straight move in motor angles, closed form per motor from the current angles and speeds,
#                       with a dead-time-delayed reference: slews of more than 15 deg, flips past gimbal lock, M1 turns.
#   choose_end_solution the end solution of a straight move: tracking room (eq), no cable wrap on a flip (M1 and M3
#                       turning opposite ways), then the fastest (move_time).
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
    SAMPLES = 24                                             # at most (fewer for a short path, SAMPLE_DEG): step()
                                                             # walks the exact path and caps each axis's rate; the
                                                             # profile only shapes the speed (200 took ~25 ms a tick)
    SAMPLE_DEG = 0.5                                         # motor travel per sample
    MIN_SAMPLES = 6
    TURN_SHARE = 0.5
    BRANCH_JUMP_DEG = 30.0                                   # one sample step this large is an IK branch change

    def __init__(self, to_theta, max_rate, max_accel, dead_time_s=0.0, lag_s=0.0):
        self.to_theta = to_theta
        # the reference is the walk as the measurements should show it: dead_time_s late and through a first-order
        # lag of lag_s, as MotorMove's. Compared with the walk itself, the PID pushed each motor against its own lag
        # and a roll change (M1/M3 counter-rotating along a curve) left the pointing 80' off the path
        self.dead_time_s = np.broadcast_to(np.asarray(dead_time_s, dtype=float), (3,)).copy()   # per motor
        self.lag_s = float(lag_s)
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
        self._clock, self._history, self._lagged, self._goal_at = 0.0, [(0.0, self._theta.copy())], self._theta.copy(), None
        self.retarget(goal)

    def retarget(self, goal):
        """New goal: re-plan from the current reference position and speed."""
        self.goal = np.asarray(goal, dtype=float)
        # samples for the path's motor travel end to end (one conversion): each sample costs a sky -> motor
        # conversion, and 200 of them took ~1,400 kinematics calls in one tick for a 5 deg PA change (R4)
        end = self.to_theta(self.goal, self._theta)
        n = int(np.clip(math.ceil(float(np.max(np.abs(end - self._theta))) / self.SAMPLE_DEG), self.MIN_SAMPLES, self.SAMPLES))
        # plus samples packed near both ends, where the reference speeds up and brakes: read off a coarse profile
        # the start crept (0.21 deg/s takes 0.004 deg at 5 deg/s^2, the first uniform sample is 0.5 deg away)
        ends = np.array([1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2])
        ends = ends[ends < 1.0 / n]
        fracs = np.unique(np.concatenate([np.linspace(0.0, 1.0, n + 1), ends, 1.0 - ends]))
        thetas = [self._theta]
        ends_q = self._ends_q(self._alpha, self.goal)          # the slerp ends, once per plan (not per sample)
        for f in fracs[1:]:
            thetas.append(self.to_theta(self._interp(self._alpha, self.goal, f, ends_q), thetas[-1]))
        thetas = np.array(thetas)
        self.path_thetas = thetas                               # the sampled path in motor angles (limit checks)
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
        # the walk's time from here, off the profile (exact under constant acceleration): the goto timeout allows
        # for it, as for a MotorMove (a 30 deg roll change at 1 deg/s ran past the 45 s timeout)
        vm = (v[:-1] + v[1:]) / 2
        self.duration = float(np.sum(np.where(vm > 1e-9, ds / np.maximum(vm, 1e-9), 0.0)))
        self._pos = 0.0
        self._at_goal = s[-1] < 1e-9
        self.done = False

    def step(self, dt):
        """Returns (theta_ref, omega_ff): the reference (the walk dead_time_s ago through the lag), and the velocity
        that takes the walk to where it will be one dt later (where it then advances to)."""
        ref, rate = self._walk(dt)
        if not np.any(self.dead_time_s > 0) and self.lag_s <= 0:
            return ref, rate
        self._clock += dt
        self._history.append((self._clock, ref.copy()))
        while len(self._history) > 2 and self._history[1][0] <= self._clock - float(np.max(self.dead_time_s)):
            self._history.pop(0)                                # keep what the longest delay still needs
        ts = np.array([t for t, _ in self._history])
        hs = np.array([h for _, h in self._history])
        delayed = np.array([np.interp(self._clock - d, ts, hs[:, i]) for i, d in enumerate(self.dead_time_s)])
        self._lagged = (delayed if self.lag_s <= 0
                        else self._lagged + (delayed - self._lagged) * (1.0 - math.exp(-dt / self.lag_s)))
        if self.done:                                           # the walk is at the goal: done once its response is
            if self._goal_at is None:                           # through as well
                self._goal_at = self._clock
            self.done = self._clock - self._goal_at >= float(np.max(self.dead_time_s)) + 3 * self.lag_s - 1e-9
            if self.done:
                return ref, rate
        return self._lagged.copy(), rate

    def _walk(self, dt):
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
    def _ends_q(a, b):
        return azaltroll_to_q(a[0], a[1], 0.0), azaltroll_to_q(b[0], b[1], 0.0)

    @staticmethod
    def _interp(a, b, frac, ends_q=None):
        """Az/Alt along the great circle (slerp at roll 0) and roll linearly, like alpha_limit_step. ends_q: the
        two ends' quaternions, when already known."""
        q_a, q_b = ends_q if ends_q is not None else GotoTrajectory._ends_q(a, b)
        az, alt, _ = q_to_azaltroll(Quaternion.slerp(q_a, q_b, frac))
        return np.array([az, alt, a[2] + frac * wrap180(b[2] - a[2])])


def _axis_profile(d, v0, vmax, a):
    """Time-optimal segments [(duration, accel)] for one motor to move d (deg) and stop, starting at speed v0 (deg/s),
    within vmax and a: speed up (or slow to vmax), cruise, brake; when it can't stop in time, brake first and come
    back."""
    if d < 0 or (d == 0 and v0 < 0):
        return [(t, -acc) for t, acc in _axis_profile(-d, -v0, vmax, a)]
    if d == 0 and v0 == 0:
        return []
    stop = v0 * abs(v0) / (2 * a)                       # distance to a stop braking now (negative: moving away)
    if stop > d + 1e-12:                                # overshoots even braking now: brake, then come back
        return [(v0 / a, -a)] + _axis_profile(d - stop, 0.0, vmax, a)
    peak = math.sqrt(a * d + v0 * v0 / 2)               # triangle: speed up to peak, brake to the goal
    if peak <= vmax:
        return [(max(0.0, (peak - v0) / a), a), (peak / a, -a)]
    acc = a if vmax >= v0 else -a                       # up to vmax (or down to it from beyond)
    d1 = (vmax * vmax - v0 * v0) / (2 * acc)
    cruise = max(0.0, (d - d1 - vmax * vmax / (2 * a)) / vmax)
    return [(abs(vmax - v0) / a, acc), (cruise, 0.0), (vmax / a, -a)]


def move_time(theta_from, theta_to, omega, max_rate, max_accel):
    """Time (s) of a straight motor-angle move from theta_from at speeds omega to rest at theta_to: the slowest
    motor's time-optimal profile."""
    d = np.asarray(theta_to, dtype=float) - np.asarray(theta_from, dtype=float)
    v0 = np.broadcast_to(np.asarray(omega, dtype=float), d.shape)
    vmax = np.broadcast_to(np.asarray(max_rate, dtype=float), d.shape)
    return max(sum(t for t, _ in _axis_profile(float(d[i]), float(v0[i]), float(vmax[i]), float(max_accel)))
               for i in range(len(d)))


FLIP_DEG = 90.0                     # a move turning both M1 and M3 further than this is a flip (~180 deg each)


def is_flip(theta_from, theta_to):
    """A move to the other side: M1 and M3 both swinging round (~180 deg each)."""
    d = np.asarray(theta_to, dtype=float) - np.asarray(theta_from, dtype=float)
    return bool(abs(d[0]) > FLIP_DEG and abs(d[2]) > FLIP_DEG)


def wraps_cables(theta_from, theta_to):
    """A flip that turns M1 and M3 the same way: the cables wrap (they should turn in opposite directions)."""
    d = np.asarray(theta_to, dtype=float) - np.asarray(theta_from, dtype=float)
    return is_flip(theta_from, theta_to) and bool(d[0] * d[2] > 0)


CABLE_TWIST_MAX_DEG = 270.0      # net cable twist (raw M1 + M3 angles) an end solution may leave before a slower one wins:
                                 # above eq mode's tracking-room turn (+204 at the zenith; 180 unwound M1 282 deg there)
CABLE_TWIST_SLACK_DEG = 30.0     # ... up to this much past it is fine for a move winding them no more than this further:
                                 # below the horizon the flipped branch sits at +-270-287 (M3 near 180), and a 3 deg
                                 # goto there (+4-7) chose a 360 deg M3 unwind, 50-56 s slower, and timed out


def choose_end_solution(solutions, theta_now, omega_now, max_rate, max_accel, has_room=None, twist=None):
    """Index of the end solution to move to, in order: tracking room (has_room(theta) -> bool, eq mode), no cable wrap
    on a flip, the cables' net twist (twist(theta) -> deg) within CABLE_TWIST_MAX_DEG (else the least twisted), the
    fastest from the current angles and speeds. None if there are none.
    The twist: a move that turned M1 +274 (forced the long way round by its limit) also turned M3 +44 rather than
    -316, 6 s faster but leaving the cables wound +318 deg (field 2026-10-17, pano panel 41 -> 40); the flip check
    alone saw no wrap, as M3 hardly moved."""
    if len(solutions) == 0:
        return None
    times = [move_time(theta_now, s, omega_now, max_rate, max_accel) for s in solutions]
    room = [bool(has_room(s)) if has_room else True for s in solutions]
    wrap = [wraps_cables(theta_now, s) for s in solutions]
    over = [cable_twist_over(twist, s, theta_now) if twist else 0.0 for s in solutions]
    return min(range(len(solutions)), key=lambda i: (not room[i], wrap[i], over[i], times[i]))


def cable_twist_over(twist, theta, theta_now):
    """How far (deg) the cables' net twist at end solution theta is past CABLE_TWIST_MAX_DEG, 0 within it -- or within
    CABLE_TWIST_SLACK_DEG past it for a move that winds them no more than that further than they are now."""
    t, now = abs(float(twist(theta))), abs(float(twist(theta_now)))
    if t <= CABLE_TWIST_MAX_DEG or (t <= CABLE_TWIST_MAX_DEG + CABLE_TWIST_SLACK_DEG and t <= now + CABLE_TWIST_SLACK_DEG):
        return 0.0
    return t - CABLE_TWIST_MAX_DEG


class MotorMove:
    """A straight move in motor angles, closed form: each motor on its own time-optimal profile (speed up, cruise,
    brake within its max_rate and max_accel) from its current angle and speed to the goal, where it stops. Nothing
    is sampled, so planning costs microseconds (R4), and it starts from a moving mount as well as from rest (R2).

    The measurements show a motor's response to a speed command late and smoothed: dead_time_s late (the age of a
    measurement), and through a first-order lag of lag_s (the MCU easing each motor to a new speed). step() returns
    the commanded speed now as the feed-forward, and as the reference the plan passed through that delay and lag:
    what the measurements should show now. The PID then sees only real errors, not the lag, and doesn't push a motor
    on into an overshoot (study design item 3). Modelling the lag as a delay alone left a(lag_s^2)/2 of overshoot
    from every stop (0.3 deg at 5 deg/s^2 and 0.35 s)."""
    space = 'THETA'

    def __init__(self, max_rate, max_accel, dead_time_s=0.0, lag_s=0.0, drift=None):
        self.max_rate = np.broadcast_to(np.asarray(max_rate, dtype=float), (3,)).copy()
        # the goal's own motion (deg/s per motor), for a goto while tracking: the move is planned in a frame moving
        # with the target, so the reference and the commands carry the tracking on through it and arrive tracking
        self.drift = np.zeros(3) if drift is None else np.broadcast_to(np.asarray(drift, dtype=float), (3,)).copy()
        self._T0 = 0.0                                   # time since start() when the current plan began
        self.max_accel = float(max_accel)
        self.dead_time_s = float(dead_time_s)
        self.lag_s = float(lag_s)
        self._lagged = None                              # the reference: the delayed plan through the motor lag
        self.goal = None
        self.alpha_goal = None                           # the sky target, when a goto planned this move
        self.done = True
        self.branch_change = False

    def start(self, theta, goal, omega=None):
        """Plan from the measured angles theta and the speeds commanded now (omega): the motors are commanded to be
        a dead time ahead of where they are measured."""
        v0 = np.zeros(3) if omega is None else np.asarray(omega, dtype=float)
        self._T0 = 0.0
        self._plan(np.asarray(theta, dtype=float) + v0 * (self.dead_time_s + self.lag_s), v0 - self.drift, goal)
        self._lagged = np.asarray(theta, dtype=float).copy()

    def retarget(self, goal):
        """New goal (where it is now) mid-move: re-plan from where the plan has the motors now, at their speed now."""
        p, v = self._profile(self._t)
        self._T0 += self._t
        self._plan(p, v, np.asarray(goal, dtype=float) - self.drift * self._T0)

    def _plan(self, p0, v0, goal):
        """Plan the profile (in the frame moving with the drift) from p0 at v0 to goal."""
        self.goal = np.asarray(goal, dtype=float)
        self._p0, self._v0, self._t = p0.copy(), v0.copy(), 0.0
        self._segments = [_axis_profile(float(self.goal[i] - p0[i]), float(v0[i]), float(self.max_rate[i]),
                                        self.max_accel) for i in range(3)]
        self.duration = max((sum(t for t, _ in seg) for seg in self._segments), default=0.0)
        self.done = False

    def _state(self, t):
        """Commanded angles and speeds at time t into the plan: the profile plus the drift."""
        p, v = self._profile(t)
        return p + self.drift * (self._T0 + t), v + self.drift

    def _profile(self, t):
        """The profile's angles and speeds at time t into the plan (before it: carrying on at the start speed)."""
        p, v = self._p0.copy(), self._v0.copy()
        if t <= 0:
            return p + v * t, v
        for i, seg in enumerate(self._segments):
            left = t
            for dur, acc in seg:
                step = min(dur, left)
                p[i] += v[i] * step + 0.5 * acc * step * step
                v[i] += acc * step
                left -= step
                if left <= 0:
                    break
            if left > 0:                                 # finished: at rest on the goal
                p[i], v[i] = self.goal[i], 0.0
        return p, v

    def step(self, dt):
        """Returns (theta_ref, omega_ff): the plan dead_time_s ago through the motor lag, and its mean speeds over
        this tick."""
        self._t += dt
        delayed, _ = self._state(self._t - self.dead_time_s)
        if self.lag_s > 0:
            self._lagged += (delayed - self._lagged) * (1.0 - math.exp(-dt / self.lag_s))
        else:
            self._lagged = delayed
        ref = self._lagged.copy()
        # the command: the plan's mean speed over a tick centred on t (on a ramp, its speed at t, as the reference),
        # so a move shorter than a tick (a 0.02 deg dither lasts 0.13 s) is still commanded, not sampled as 0
        p_then, _ = self._state(self._t - dt / 2)
        p_next, _ = self._state(self._t + dt / 2)
        omega = (p_next - p_then) / dt
        if self._t - dt / 2 >= self.duration + self.dead_time_s + 3 * self.lag_s - 1e-9:   # its last command sent
            self.done = True
            ref = self.goal + self.drift * (self._T0 + self._t)
        return ref, omega
