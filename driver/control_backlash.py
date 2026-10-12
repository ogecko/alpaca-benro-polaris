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
#                         once the motor has crossed the slack. The PID's error signal uses that estimate instead of
#                         the motor angle, offset so a motor engaged the way it tracks reads its own angle (alignment
#                         and PEC are learnt engaged); theta_pv, the alignment, the KF, PEC and the logs keep the motor
#                         angles. On a reversal the estimate stands still, the error stays, and a take-up push drives
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
#     hysteresis          a push away from the tracking flank starts only for an error of PUSH_MIN_ERR_ARCSEC: the
#                         PID's normal few arcseconds would otherwise push the motor back and forth across the slack.
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
PUSH_SHARE = 0.3                    # ... and no more than this share of the slack left in one tick
PUSH_MIN_ERR_ARCSEC = 30.0          # push away from the tracking flank only for an error at least this (hysteresis
                                    # against the PID's few arcseconds pushing it back and forth across the slack)
PUSH_ENGAGE_ERR_ARCSEC = 3.0        # ... towards the tracking flank: one-way, it can't chatter
ENGAGE_RATE_ARCSEC_S = 0.5          # a motor tracking slower than this has no tracking direction (keeps its last)
ENGAGED_ARCSEC = 1.0                # within this of engaged the way it tracks: released after a goto
TURN_LEAD_SEC = 10.0                # latch a planned reversal from this long before its turning point ...
TURN_LATE_SEC = 60.0                # ... until this long after it (not later: by then the camera has fallen behind)
LATCH_ENGAGED_ARCSEC = 5.0          # ... and only a motor engaged on its old flank (within this)
TURN_SOON_SEC = 300.0               # a goto doesn't compensate a motor turning within this of now: its tracking side is
                                    # about to change
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

    @staticmethod
    def slack():
        b = getattr(Config, 'backlash_deg', 0.0) or 0.0
        return np.broadcast_to(np.abs(np.asarray(b, float)), (3,)).copy()

    @staticmethod
    def enabled():
        return bool(getattr(Config, 'advanced_backlash', False)) and bool(np.any(BacklashCompensator.slack() > 0))

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
            turning[m] |= abs(tc - now) < TURN_SOON_SEC
        settled = moving & ~turning & ~edge
        self.active = (((move_pending | (self.active & ~engaged)) & settled) | self.latched) & (self.flank != 0)
        self.adjust = np.where(self.active, adj, 0.0)
        return self.adjust

    def push(self, error, theta_m, dt):
        """The take-up push (deg/s, per motor) for the motors being compensated whose error wants them through the
        slack: towards the far flank, at PUSH_DPS and at most PUSH_SHARE of the distance left per tick."""
        if self.output is None or dt <= 0 or not np.any(self.active):
            self._pushing[:] = False
            return np.zeros(3)
        half = self.slack() / 2
        err = np.asarray(error, float)
        s = np.sign(err)
        threshold = np.where(s == self.flank, PUSH_ENGAGE_ERR_ARCSEC, PUSH_MIN_ERR_ARCSEC)
        s = s * (np.abs(err) * 3600 >= threshold) * self.active
        rem = wrap180(self.output + s * half - np.asarray(theta_m, float))
        rem = np.where(s * rem > 1 / 3600, rem, 0.0)
        omega = np.sign(rem) * np.minimum(PUSH_DPS, PUSH_SHARE * np.abs(rem) / dt)
        starting = (omega != 0) & ~self._pushing
        if self.logger and np.any(starting):
            self.logger.info("->> Polaris: BACKLASH taking up slack: " + ", ".join(
                f"M{m + 1} {rem[m] * 3600:+.0f}\"" for m in np.flatnonzero(starting)))
        self._pushing = omega != 0
        return omega
