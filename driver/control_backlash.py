# -----------------------------------------------------------------------------
# control_backlash.py - Backlash Compensation for the PID controller
# -----------------------------------------------------------------------------
#
# The MCU measures each motor's angle before its gearbox, so when a motor reverses it turns through its gear backlash
# (measured 150-620" on the real mount) before the output shaft, and the camera, follows. A goto that finishes with a
# motor moving against its tracking direction leaves that slack open: tracking then takes it up and the image moves
# by up to the backlash after the plate solve (Slew & Center landing arcminutes off). A planned tracking reversal (M2
# near transit) stalls the output while the motor crosses the slack: a drift bump the guider has to chase.
#
#   BacklashCompensator   one dead band per motor (backlash_deg) estimates where the output shaft is: it moves only
#                         once the motor has crossed the slack. While compensating, the forward kinematics applies it
#                         as its first correction ([BLC], SyncManager.baseQ_to_topoQ), offset so a motor engaged the
#                         way it tracks reads its own angle (alignment and PEC are learnt engaged): theta_pv, the sky
#                         positions, ASCOM and syncs then describe the output shafts, and the PID controls them; the KF,
#                         the worm's MCU angles and the motor limits keep the motor angles. A sync point keeps the
#                         adjustment it was taken with. On a reversal the estimate stands still, the error stays, and a take-up push drives
#                         the motor through the slack (on top of the PID, slowing as it nears the far flank: the motor
#                         lags its speed command, and an overrun moves the output).
#     when                only where a reversal is known: while a goto or rotate completes (and until the motor is
#                         engaged again), and through a planned tracking reversal along the target's sidereal path
#                         (SyncManager.motor_turns), latched from just before the turning point until the next goto.
#                         Not during ordinary tracking and guiding: a motor barely moving under guide pulses reverses
#                         constantly, and pushing it through its slack each time becomes a limit cycle. Nor where a
#                         motor has no settled tracking side: under ENGAGE_RATE_ARCSEC_S, about to turn, or at the edges
#                         of the mount's reach (M2 near gimbal lock or its limit).
#     flank               the side a motor is engaged on: its tracking direction, held through a latched reversal --
#                         the alignment was learnt on the old flank, so the motor runs the backlash ahead of its old
#                         path afterwards instead of the camera falling behind by it.
#     one-way             a push only ever goes towards the tracking flank; an engaged motor that overran its target a
#                         little never reverses: its speed is held at zero against the flank until the sky catches up
#                         (as far as the sky closes in HOLD_MAX_SEC, up to HOLD_ARCSEC), and it counts as arrived. A push
#                         back across the slack overran in turn on the real mount (its speed lags the command by more
#                         than the twin's), and the two became a limit cycle.
#                         A motor that still crosses its slack more than MAX_CROSSINGS times in a goto is given up
#                         until the next goto or planned reversal (each gets its own MAX_CROSSINGS).
#     limits              the dead band follows the 518 motor angles, sampled every 0.2 s and M3's held ~0.6 s, so an
#                         overshoot reversing between samples can move the output further than the estimate sees: it
#                         can then end a goto up to ~1.5' off (M3 in the twin, about one Slew & Center correction in
#                         eight), still less than without compensation.
#
# Config.advanced_backlash switches it ("Backlash Compensation"), Config.backlash_deg is each motor's slack. An
# overestimate costs time, not accuracy: the controller still finishes with the motor engaged the way it tracks, where
# the adjustment is zero.
# -----------------------------------------------------------------------------

import numpy as np

from config import Config
from kinematics import THETA2_MAX

PUSH_DPS = 0.05                     # take-up push through the slack (deg/s); at 0.2 the motor's lag overran the flank
PUSH_SHARE = 0.15                   # ... and no more than this share of the slack left in one tick (0.3 overran the far
                                    # flank by up to 75" on the real M2: its speed lags the command)
PUSH_ENGAGE_ERR_ARCSEC = 3.0        # push (only ever towards the tracking flank) once the error reaches this
HOLD_ARCSEC = 120.0                 # an engaged motor up to this far ahead of its target holds (never reverses): the sky
                                    # catches up. The real mount overran a push by 35-45", and a push back across the slack
                                    # became a limit cycle (nina/nec06 2026-10-12, Az 176 Alt 43: +-144", +-432" every 1-2 s)
HOLD_MAX_SEC = 6.0                  # ... but only as far ahead as the sky closes in this long at the motor's tracking rate
                                    # (a slow M2 held 75" ahead for 30 s live and timed the goto out) ...
HOLD_MIN_ARCSEC = 15.0              # ... and at least this far (a motor near its turning point still holds an overrun)
HOLD_ARRIVED_ARCSEC = 15.0          # ... and counts as arrived within this (further ahead, the goto waits for the sky)
MAX_CROSSINGS = 2                   # full slack crossings per motor per goto before compensating it is given up
CROSSING_SHARE = 0.9                # ... a crossing starting with at least this share of the slack ahead
ENGAGE_RATE_ARCSEC_S = 0.5          # a motor tracking slower than this has no tracking direction (keeps its last)
ENGAGED_ARCSEC = 1.0                # within this of engaged the way it tracks: released after a goto
SLOW_TAKEUP_ARCSEC_S = 2.0          # a motor tracking slower than this doesn't hold a goto up while its slack is taken up
                                    # (taking_up), and has it pushed through even with a small error: tracking alone took
                                    # 30-40 s over the last 30" (worm test roll at Az 295 Alt 34, M1/M2 at 0.8"/s: 47 s,
                                    # timed out on the mount 2026-10-18 00:00)
TURN_LEAD_SEC = 10.0                # latch a planned reversal from this long before its turning point ...
TURN_LATE_SEC = 60.0                # ... until this long after it (not later: by then the camera has fallen behind)
LATCH_ENGAGED_ARCSEC = 5.0          # ... and only a motor engaged on its old flank (within this)
TURN_SOON_SEC = 300.0               # a goto doesn't compensate a motor turning within this from now: its tracking side
                                    # is about to change
GIMBAL_LOCK_DEG = 12.0              # ... nor any motor with M2 within this of gimbal lock (theta2 0): M1/M3's tracking
                                    # sides swap within seconds as the pointing moves (a 5' correction swings them by degrees)
M2_LIMIT_MARGIN_DEG = 1.0           # ... or within this of M2's limit (THETA2_MAX): the goto can't settle there anyway


def wrap180(x):
    return (np.asarray(x, float) + 180.0) % 360.0 - 180.0


class BacklashCompensator:
    def __init__(self, logger=None):
        self.logger = logger
        self.reset()

    def reset(self):
        self.output = None                           # estimated output shaft angles (deg, motor angle space)
        self.flank = np.zeros(3)                     # +1/-1: the side each motor is engaged on (its tracking way)
        self.latched = np.zeros(3, dtype=bool)       # through a planned tracking reversal, until the next goto
        self.active = np.zeros(3, dtype=bool)        # the adjustment applies to the error signal
        self.adjust = np.zeros(3)                    # motor angle - controlled angle (deg)
        self._pushing = np.zeros(3, dtype=bool)
        self._latched_turns = set()
        self._crossings = np.zeros(3, dtype=int)     # full slack crossings pushed this goto (or planned reversal)
        self.given_up = np.zeros(3, dtype=bool)      # ... too many: not compensated until the next goto (or reversal)
        self._was_pending = False
        self._heading = np.zeros(3)
        self._rate = np.zeros(3)
        self.hold = np.zeros(3, dtype=bool)          # holding while the sky catches up (update_hold)

    @staticmethod
    def slack():
        b = getattr(Config, 'backlash_deg', 0.0) or 0.0
        return np.broadcast_to(np.abs(np.asarray(b, float)), (3,)).copy()

    @staticmethod
    def enabled():
        """On, with some slack to take up, and with Coordinated Speed Control: only its controller pushes a motor
        through its slack and holds it while the sky catches up (push, clutch); the legacy controller can't, and with
        the hold still counting as arrived its gotos completed up to 15\" short (twin, 2026-10-18)."""
        return (bool(getattr(Config, 'advanced_backlash', False)) and bool(getattr(Config, 'coordinated_speed_control', False))
                and bool(np.any(BacklashCompensator.slack() > 0)))

    def update(self, theta_m, omega_ff, tracking, move_pending, turns=(), now=0.0):
        """Each control tick: the adjustment (deg, per motor) to take off the motor angles theta_m for the PID's error.
        omega_ff: the tracking feed-forward (deg/s); tracking: sidereal (or other) tracking under PID TRACK;
        move_pending: a goto/rotate under way; turns: the target's motor turning points [(motor, monotonic time, ...)]."""
        if not self.enabled() or not tracking:
            if self.output is not None:
                self.reset()
            return self.adjust
        theta_m = np.asarray(theta_m, float)
        half = self.slack() / 2
        w = np.asarray(omega_ff, float) * 3600
        self._heading = np.sign(w)                   # the way each motor tracks now (a latched one: its new way)
        self._rate = np.abs(w)                       # ... and how fast ("/s)
        if move_pending and not self._was_pending:  # a new goto: compensate every motor again
            self._crossings[:] = 0
            self.given_up[:] = False
        self._was_pending = move_pending
        if move_pending:
            self.latched[:] = False                  # a goto re-engages every motor the way it then tracks
        moving = np.abs(w) > ENGAGE_RATE_ARCSEC_S
        self.flank = np.where(moving & ~self.latched, np.sign(w), self.flank)
        if self.output is None:                                # engaged the way it moves (however slowly)
            self.output = theta_m - np.where(self.flank != 0, self.flank, np.sign(w)) * half
        lead = wrap180(theta_m - self.output)
        self.output = np.where(lead > half, theta_m - half, np.where(lead < -half, theta_m + half, self.output))
        lead = wrap180(theta_m - self.output)
        t2 = abs(wrap180(theta_m[1]))
        edge = t2 < GIMBAL_LOCK_DEG or t2 > THETA2_MAX - M2_LIMIT_MARGIN_DEG     # the edges of the mount's reach
        if edge:
            self.latched[:] = False                  # left alone at the edges, even through a reversal
        if not move_pending and not edge:
            for m, tc, *_ in turns:
                key = (m, round(tc))                 # each turn latches once (not again after a goto through it)
                if not (tc - TURN_LEAD_SEC <= now <= tc + TURN_LATE_SEC and w[m] != 0 and not self.latched[m]
                        and key not in self._latched_turns):
                    continue
                # the flank it was engaged on: the way it moved before the turn (slowing into it, it can be well
                # under ENGAGE_RATE_ARCSEC_S, e.g. the SMC's M2 at 0.17"/s 3 min before) -- only if it is engaged
                # there: a goto ending at the turn leaves no tracked flank to keep
                f = np.sign(w[m]) if now < tc else -np.sign(w[m])
                if abs(lead[m] - f * half[m]) * 3600 > LATCH_ENGAGED_ARCSEC:
                    continue
                self.flank[m] = f
                self.latched[m] = True
                self._latched_turns.add(key)
                # a reversal has its own crossing budget: a motor given up during the goto (often one with many
                # back-and-forth crossings, 2026-10-14 Tuc47) is otherwise left uncompensated through its reversal
                self._crossings[m] = 0
                self.given_up[m] = False
                if self.logger:
                    self.logger.info(f"->> Polaris: BACKLASH M{m + 1} reversing its tracking direction "
                                     f"{'in' if tc >= now else 'since'} {abs(tc - now):.0f} s: compensating its "
                                     f"{half[m] * 2 * 3600:.0f}\" slack until the next goto")
        adj = np.where(self.flank != 0, lead - self.flank * half, 0.0)     # 0 while engaged the way it tracks
        adj = np.where(np.abs(adj) < 1e-9, 0.0, adj)                        # (not wrap180's rounding)
        engaged = np.abs(adj) <= ENGAGED_ARCSEC / 3600
        # a motor tracking too slowly to load its gear either way (e.g. M2 at 0.01"/s) has no side to engage, and one
        # about to turn has no settled one: left alone
        turning = np.zeros(3, dtype=bool)
        for m, tc, *_ in turns:
            turning[m] |= 0.0 <= tc - now < TURN_SOON_SEC    # ahead: once past, its new side is settled
        settled = moving & ~turning & ~edge
        self.active = ((((move_pending | (self.active & ~engaged)) & settled) | self.latched) & (self.flank != 0)
                       & ~self.given_up)
        self.adjust = np.where(self.active, adj, 0.0)
        return self.adjust

    def taking_up(self):
        """A compensated motor is not yet engaged the way it tracks: its slack is still being taken up. A slow motor
        (under SLOW_TAKEUP_ARCSEC_S) doesn't hold a goto up: its slack stays modelled (the pointing allows for it) and is
        taken up by tracking and the push after the goto completes, as at a turning point. Waiting for it, a 2 deg roll
        took 47 s and timed out (worm test at Az 295 Alt 34, M1/M2 at 0.8"/s: an overshoot reversed M1 through its
        whole slack, then it waited for the sky)."""
        fast = np.abs(self._rate) >= SLOW_TAKEUP_ARCSEC_S
        return bool(np.any(self.active & fast & (np.abs(self.adjust) > ENGAGED_ARCSEC / 3600)))

    def update_hold(self, error):
        """Once per control tick, from the PID's error (deg): which compensated motors hold -- engaged the way they
        track and a little ahead of their target, they stand still (clutch()) while the sky catches up instead of
        reversing into their slack: up to HOLD_ARCSEC, and no further than the sky closes in HOLD_MAX_SEC at the motor's
        tracking rate (at least HOLD_MIN_ARCSEC). Returns the hold mask."""
        err = np.asarray(error, float)
        window = np.clip(self._rate * HOLD_MAX_SEC, HOLD_MIN_ARCSEC, HOLD_ARCSEC)
        ahead = (np.sign(err) == -self.flank) & (np.abs(err) * 3600 <= window)
        engaged = np.abs(self.adjust) <= ENGAGED_ARCSEC / 3600
        self.hold = self.active & ~self.latched & ahead & engaged
        return self.hold

    def holding(self, error=None, limit_arcsec=HOLD_ARCSEC):
        """The hold mask (update_hold), optionally only where the motor is within limit_arcsec of its target."""
        if error is None or limit_arcsec >= HOLD_ARCSEC:
            return self.hold.copy()
        return self.hold & (np.abs(np.asarray(error, float)) * 3600 <= limit_arcsec)

    def clutch(self, omega, error=None):
        """omega (deg/s, per motor) with a holding motor's speed against its tracking flank cut to zero: it waits for
        the target instead of reversing into its slack."""
        omega = np.asarray(omega, float)
        return np.where(self.hold, self.flank * np.maximum(self.flank * omega, 0.0), omega)

    def push(self, error, theta_m, dt):
        """The take-up push (deg/s, per motor) for the motors being compensated whose error wants them through the
        slack towards their tracking flank (never away from it): at PUSH_DPS and at most PUSH_SHARE of the distance
        left per tick."""
        if self.output is None or dt <= 0 or not np.any(self.active):
            self._pushing[:] = False
            return np.zeros(3)
        half = self.slack() / 2
        err = np.asarray(error, float)
        # only ever the way the motor keeps moving: its tracking flank, or for a latched reversal its new direction
        way = np.where(self.latched, self._heading, self.flank)
        s = np.sign(err)
        s = s * (s == way) * (np.abs(err) * 3600 >= PUSH_ENGAGE_ERR_ARCSEC) * self.active
        # a slow motor isn't left to take its slack up by tracking alone: push it its own way while its error doesn't
        # want the other way (pushing through the slack moves the motor, not the output, so not the pointing)
        slow = self.active & ~self.latched & (np.abs(self._rate) < SLOW_TAKEUP_ARCSEC_S) & \
            ((np.sign(err) == way) | (np.abs(err) * 3600 < PUSH_ENGAGE_ERR_ARCSEC))
        s = np.where(slow & (s == 0), way, s)
        rem = wrap180(self.output + s * half - np.asarray(theta_m, float))
        rem = np.where(s * rem > 1 / 3600, rem, 0.0)
        omega = np.sign(rem) * np.minimum(PUSH_DPS, PUSH_SHARE * np.abs(rem) / dt)
        starting = (omega != 0) & ~self._pushing
        # a fresh crossing: from the far flank, with (nearly) all the slack ahead -- not a push pausing part-way across
        crossing = starting & (np.abs(rem) > CROSSING_SHARE * 2 * half)
        self._crossings += crossing
        over = crossing & (self._crossings > MAX_CROSSINGS)
        if np.any(over):
            self.given_up |= over
            self.active &= ~over
            self.adjust = np.where(over, 0.0, self.adjust)
            omega = np.where(over, 0.0, omega)
            starting = starting & ~over
            if self.logger:
                self.logger.warning("->> Polaris: BACKLASH compensation stopped until the next goto or planned reversal "
                                    "for " + ", ".join(f"M{m + 1}" for m in np.flatnonzero(over))
                                    + f": crossed its slack more than {MAX_CROSSINGS} times")
        crossing = crossing & ~over
        if self.logger and np.any(crossing):                          # (not the small top-ups after it)
            self.logger.info("->> Polaris: BACKLASH taking up slack: " + ", ".join(
                f"M{m + 1} {rem[m] * 3600:+.0f}\"" for m in np.flatnonzero(crossing)))
        self._pushing = omega != 0
        return omega
