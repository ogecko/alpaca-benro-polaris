# -----------------------------------------------------------------------------
# speed_controller.py - Shared-level motor speed controller for the Benro Polaris (BETA)
# -----------------------------------------------------------------------------
#
# The Polaris gimbal MCU runs SLOW jogs (532/533/534) as a position ramp whose step comes
# from ONE level byte shared by every axis; direction and state (1 = start, 2 = continue)
# are per axis (A Polaris System Design.md §5.4). Controlling each motor separately, as the
# legacy MotorSpeedController does, lets one axis's level change the speed of the others.
#
# This controller owns that shared level:
#   * every SLOW period (0.25 s) it picks ONE level for all SLOW axes and every 53x it sends
#     carries that level, so no axis can disturb another. The level is set by the fastest axis
#     (the pacer) from the full 10-speed ladder (levels 1-5 x states 1-2); when its rate lies
#     between two levels it alternates whole periods between them, so the level only rises as
#     far, and as often, as the pacer needs;
#   * every axis delta-modulates between the two speeds either side of its target at the current
#     level (-s2, -s1, +s1, +s2; never level/state 0 while moving, which releases torque): it keeps
#     one speed until its accumulated position error crosses a band, then switches. The band is
#     the ripple of a PWM at that duty over the shortest allowed cycle (0.25 s, 0.4 s when the pair
#     reverses direction, longer if the minority speed would run under MIN_SLOW_DWELL), so ripple
#     is below legacy at every duty; the average is exact, and PID target updates just change the slope. (Slot-per-period sigma-delta and fixed-period PWM both had
#     more ripple than legacy and made PID tracking worse at low rates.)
#   * no axis changes direction/state sooner than MIN_SLOW_DWELL, because the MCU only samples
#     SLOW changes on its scheduler tick;
#   * rates above the fastest SLOW speed use FAST (513/514/521), refreshed every 50 ms and
#     optionally ramped. The FAST speed-unit interpolator is the only use of calibration data.
#
# SpeedCoordinator is a pure, deterministic core (tick(now) -> messages) so it can be tested
# against tests/mcu_model.py; SpeedControllerRuntime runs it on asyncio, and
# AxisSpeedController / SwitchableMotor present the legacy per-axis interface so the new
# controller can be swapped in live via Config.speed_controller_v2.
# -----------------------------------------------------------------------------

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.interpolate import PchipInterpolator

# SLOW speeds (deg/s) by (level, state), measured on hardware (utility/state2_test.py,
# mean of M1-M3, 2026-09-26); firmware steps are 60 x 0.0001..0.004.
SLOW_DPS = {
    (1, 1): 0.0059, (2, 1): 0.0179, (3, 1): 0.0474, (4, 1): 0.0896, (5, 1): 0.2088,
    (1, 2): 0.0119, (2, 2): 0.0295, (3, 2): 0.0593, (4, 2): 0.1193, (5, 2): 0.2402,
}
LEVELS = (1, 2, 3, 4, 5)
BAND_DPS = SLOW_DPS[(1, 2)]           # fastest rate that keeps every axis on level 1
MAX_SLOW_DPS = SLOW_DPS[(5, 2)]       # above this, FAST is used
SLOW_CMD = ('532', '533', '534')
FAST_CMD = ('513', '514', '521')
FAST_UNITS_MIN, FAST_UNITS_MAX = 100, 2500
CYCLE_S = 0.25                        # shortest modulation cycle between same-direction speeds...
REVERSING_CYCLE_S = 0.4               # ...and between opposite directions (reversals cost more; legacy 0.5)
MIN_SLOW_DWELL = 0.005                # shortest time any SLOW command may run: the MCU only picks up
                                      # SLOW changes on its scheduler tick; on hardware 0.045-0.055 s
                                      # dwells aliased (0.28x-0.48x) while >= 0.067 s were accurate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------------------
# Rate units
# ---------------------------------------------------------------------------------------
class RateUnits:
    """Client rate units -> deg/s for one axis.

    DPS is passed through. RAW and ASCOM 0..5 are SLOW levels (fractions are a linear PWM mix
    of the neighbouring levels, matching the legacy meaning). RAW > 5 is FAST speed units and
    ASCOM > 5 maps onto them, via the baseline FAST calibration points.
    """
    _SLOW_RAW = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    _SLOW_DPS = [0.0] + [SLOW_DPS[(level, 1)] for level in LEVELS]

    def __init__(self, baseline: dict):
        i = baseline['RAW'].index(5) + 1          # FAST points follow RAW 5 (starting at the 0 separator)
        raw, dps, ascom = baseline['RAW'][i:], baseline['DPS'][i:], baseline['ASCOM'][i:]
        self._units_to_dps = PchipInterpolator(raw, dps, extrapolate=True)
        self._dps_to_units = PchipInterpolator(dps, raw, extrapolate=True)
        self._ascom_to_units = PchipInterpolator(ascom, raw, extrapolate=True)
        self.max_dps = float(dps[-1])            # fastest FAST speed

    def to_dps(self, rate: float, unit: str) -> float:
        x = abs(float(rate))
        if unit == 'DPS':
            dps = x
        elif unit in ('RAW', 'ASCOM') and x <= 5:
            dps = float(np.interp(x, self._SLOW_RAW, self._SLOW_DPS))
        elif unit == 'RAW':
            dps = float(self._units_to_dps(x))
        elif unit == 'ASCOM':
            dps = float(self._units_to_dps(self._ascom_to_units(x)))
        else:
            raise ValueError(f"unknown rate unit {unit!r}")
        return math.copysign(dps, rate) if dps else 0.0

    def fast_units(self, dps: float) -> float:
        units = float(np.clip(self._dps_to_units(abs(dps)), FAST_UNITS_MIN, FAST_UNITS_MAX))
        return math.copysign(units, dps)

    def to_raw(self, dps: float) -> float:
        """Legacy RAW equivalent of a rate, for reporting only."""
        x = abs(dps)
        raw = float(np.interp(x, self._SLOW_DPS, self._SLOW_RAW)) if x <= self._SLOW_DPS[-1] else abs(self.fast_units(x))
        return math.copysign(raw, dps) if raw else 0.0


# ---------------------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------------------
def _speeds_at(level):
    """The four SLOW speeds any axis can run at a level, ascending: (dps, key, state, level)."""
    s1, s2 = SLOW_DPS[(level, 1)], SLOW_DPS[(level, 2)]
    return ((-s2, 1, 2, level), (-s1, 1, 1, level), (s1, 0, 1, level), (s2, 0, 2, level))


# Every SLOW speed at every level, ascending: the pacer's choices.
LADDER = tuple(sorted({s for level in LEVELS for s in _speeds_at(level)}, key=lambda s: s[0]))


@dataclass
class _Axis:
    target: float = 0.0          # commanded rate, deg/s
    hold: bool = False           # keep torque at zero rate (tracking)
    allow_pwm: bool = True
    mode: str = 'IDLE'           # IDLE, STOP (stop pending), SLOW, FAST
    dirty: bool = False          # target changed since it was last planned
    active: Optional[tuple] = None   # SLOW speed (dps, key, state, level) the MCU is running now
    changed_at: float = -1e9     # when the running SLOW command was sent
    acc: float = 0.0             # position error (deg) of the actual speeds vs the target
    t_acc: float = 0.0           # time up to which acc has been accrued
    pair: tuple = ()             # the two speeds being mixed this period (for display)
    sent: Optional[tuple] = None  # last SLOW (key, state, level) sent
    fast_from: float = 0.0       # FAST ramp start / end (speed units)
    fast_to: float = 0.0
    ramp_start: float = 0.0
    ramp_s: float = 0.0
    fast_now: float = 0.0        # last FAST speed sent
    next_fast: float = 0.0

    @property
    def active_dps(self):
        return self.active[0] if self.active else 0.0


class SpeedCoordinator:
    """Deterministic shared-level speed controller for the three Polaris motors.

    Each period (slow_period) the pacer (fastest SLOW axis) sets the one level for all SLOW axes
    (sooner if it needs a higher one). Every SLOW axis then delta-modulates between the two speeds
    either side of its target at that level, switching when its accumulated position error crosses
    a fixed band, so the error stays bounded and the average is exact however often targets change.
    """

    def __init__(self, units: dict, slow_period: float = 0.25, fast_period: float = 0.05):
        self.units = units
        self.slow_period = slow_period
        self.fast_period = fast_period
        self.level: Optional[int] = None
        self._axes = {axis: _Axis() for axis in range(3)}
        self._period_start: Optional[float] = None
        self._pacer: Optional[int] = None

    # ---- commands -----------------------------------------------------------------
    def set_speed(self, axis: int, dps: float, now: float, hold: bool = False,
                  ramp_duration: Optional[float] = None, allow_pwm: bool = True):
        a = self._axes[axis]
        dps = float(dps)
        a.hold, a.allow_pwm = hold, allow_pwm
        if abs(dps) > MAX_SLOW_DPS:
            if a.mode == 'FAST':
                a.fast_from = a.fast_now
            else:
                a.fast_from = self.units[axis].fast_units(a.target) if a.target else 0.0
                a.sent, a.active = None, None            # resend SLOW after FAST ends
            a.fast_to = self.units[axis].fast_units(dps)
            a.ramp_start, a.ramp_s = now, (ramp_duration or 0.0)
            a.next_fast = now
            a.mode = 'FAST'
        elif dps == 0.0 and not hold:
            if a.mode != 'IDLE':
                a.mode = 'STOP'
        else:
            if a.mode == 'SLOW':
                self._accrue(a, now)                 # error so far belongs to the old target
            else:
                a.acc, a.t_acc, a.active = 0.0, now, None
            a.mode, a.dirty = 'SLOW', True
        a.target = dps

    def forget_sent(self, axis: int):
        """Force the next command for this axis to be sent (e.g. after a controller swap)."""
        self._axes[axis].sent = None

    @property
    def period(self) -> float:
        return self.slow_period

    # ---- reporting ------------------------------------------------------------------
    def rate_dps(self, axis: int) -> float:
        a = self._axes[axis]
        return 0.0 if a.mode in ('IDLE', 'STOP') else a.target

    def rate_raw(self, axis: int) -> float:
        return self.units[axis].to_raw(self.rate_dps(axis))

    def cmdstr(self, axis: int) -> str:
        a = self._axes[axis]
        if a.mode == 'FAST':
            label = 'RAMP' if a.fast_now != a.fast_to else 'FAST'
            return f" {label} {a.fast_now:+05.0f}"
        if a.mode == 'SLOW' and a.pair:
            # each speed as direction + level.state, e.g. '-1.1/+1.1' (tracking dither) or '+2.2'
            sym = lambda s: f"{'+' if s[0] > 0 else '-'}{s[3]}.{s[2]}"
            body = sym(a.pair[0]) if a.pair[0] == a.pair[1] else f"{sym(a.pair[0])}/{sym(a.pair[1])}"
            return f" {body}".ljust(11)
        return " IDLE      "

    # ---- scheduling -----------------------------------------------------------------
    def next_wakeup(self, now: float) -> float:
        times = [now + 1.0]
        slow = [axis for axis, a in self._axes.items() if a.mode == 'SLOW']
        for a in self._axes.values():
            if a.mode == 'STOP' or (a.mode == 'SLOW' and a.dirty):
                return now
            if a.mode == 'FAST':
                times.append(a.next_fast)
        if slow:
            times.append(now if self._period_start is None else self._period_start + self.period)
            times += [self._switch_time(self._axes[axis], now) for axis in slow]
        return min(times)

    def tick(self, now: float) -> list:
        """Advance to `now`; return the (axis, message) pairs to send, in order."""
        out = []
        for axis, a in self._axes.items():
            if a.mode == 'STOP':
                out.append((axis, self._slow_msg(axis, 0, 0, self.level or 1)))
                a.mode, a.active, a.acc, a.pair = 'IDLE', None, 0.0, ()
                a.sent = (0, 0, self.level or 1)
        slow = [axis for axis, a in self._axes.items() if a.mode == 'SLOW']
        if not slow:
            self._period_start = None
        else:
            for axis in slow:
                self._accrue(self._axes[axis], now)
            if self._level_due(slow, now):
                self._choose_level(slow, now)
            order = [self._pacer] + [axis for axis in slow if axis != self._pacer]
            for axis in order:
                out += self._modulate(axis, now)
        for axis, a in self._axes.items():
            if a.mode == 'FAST' and now >= a.next_fast - 1e-9:
                out.append((axis, self._fast_msg(axis, a, now)))
        return out

    # ---- SLOW -----------------------------------------------------------------------
    @staticmethod
    def _accrue(a: _Axis, now):
        """Add the position error built up since t_acc: commanded target vs speed actually running."""
        a.acc += (a.target - a.active_dps) * (now - a.t_acc)
        a.t_acc = now

    def _level_due(self, slow_axes, now):
        """Re-choose the level each period, or at once if the fastest axis now needs a higher one."""
        if self._period_start is None or self._pacer not in slow_axes or now >= self._period_start + self.period - 1e-9:
            return True
        return max(abs(self._axes[axis].target) for axis in slow_axes) > SLOW_DPS[(self.level, 2)] + 1e-12

    def _choose_level(self, slow_axes, now):
        """The pacer (fastest SLOW axis) sets the one level for all axes for the next period."""
        self._period_start = now
        fastest = max(abs(self._axes[axis].target) for axis in slow_axes)
        if self._pacer not in slow_axes or abs(self._axes[self._pacer].target) < fastest - 1e-12:
            self._pacer = max(slow_axes, key=lambda axis: abs(self._axes[axis].target))
        pacer = self._axes[self._pacer]
        lo, hi = self._bracket(pacer.target, LADDER)
        if lo[3] != hi[3]:
            # between two levels: run this period on the one that leaves the smaller position error
            self.level = min((lo, hi), key=lambda s: abs(pacer.acc + (pacer.target - s[0]) * self.period))[3]
        else:
            self.level = hi[3]

    def _modulate(self, axis, now):
        """Hysteretic delta modulation between the two speeds either side of the target at the current
        level: keep running one speed until the accumulated position error crosses ±h/2 (and it has
        run MIN_SLOW_DWELL), then switch. Error stays within a fixed band; the average is exact."""
        a = self._axes[axis]
        a.dirty = False
        speeds = _speeds_at(self.level)
        lo, hi = self._bracket(a.target, speeds)
        if not a.allow_pwm:
            lo = hi = min(speeds, key=lambda s: abs(s[0] - a.target))
        a.pair = (lo, hi)
        limit = 2 * MAX_SLOW_DPS * self.period                   # windup limit only
        a.acc = float(np.clip(a.acc, -limit, limit))
        if lo is hi:
            if abs(a.target - hi[0]) < 1e-12 or not a.allow_pwm:
                a.acc = 0.0                                      # on a speed: nothing to correct
            return self._run(axis, hi, now)
        dwelling = now < a.changed_at + MIN_SLOW_DWELL - 1e-9
        if a.active not in (lo, hi):
            if dwelling and a.active:
                # the level changed under this axis: carry the shared level, keep its direction/state
                same = next((s for s in speeds if s[1:3] == a.active[1:3]), None)
                if same:
                    return self._run(axis, same, now, restart_dwell=False)
            return self._run(axis, hi if a.acc >= 0 else lo, now)   # start on the speed that reduces the error
        if dwelling:
            return []
        half = self._band(lo, hi, a.target) / 2
        if a.active == hi and a.acc <= -half:
            return self._run(axis, lo, now)
        if a.active == lo and a.acc >= half:
            return self._run(axis, hi, now)
        return []

    @staticmethod
    def _band(lo, hi, target):
        """Peak-to-peak position error band: the ripple of a PWM mixing lo and hi at this duty over the
        shortest cycle allowed - no faster than CYCLE_S / REVERSING_CYCLE_S, and long enough that the
        minority speed still runs MIN_SLOW_DWELL. Ripple scales with duty*(1-duty), like a PWM."""
        gap = hi[0] - lo[0]
        duty = min(max((target - lo[0]) / gap, 1e-3), 1 - 1e-3)
        cycle = max(REVERSING_CYCLE_S if lo[1] != hi[1] else CYCLE_S, MIN_SLOW_DWELL / min(duty, 1 - duty))
        return gap * duty * (1 - duty) * cycle

    def _switch_time(self, a: _Axis, now):
        """When this axis's error will next cross its switching threshold (for scheduling)."""
        if not a.pair or a.pair[0] is a.pair[1] or a.active not in a.pair:
            return now + self.period
        lo, hi = a.pair
        half, slope = self._band(lo, hi, a.target) / 2, a.target - a.active_dps
        edge = -half if a.active == hi else half
        t = now + (edge - a.acc) / slope if slope * (edge - a.acc) > 0 else now
        return max(t, a.changed_at + MIN_SLOW_DWELL)

    def _run(self, axis, speed, now, restart_dwell=True):
        a = self._axes[axis]
        if speed != a.active:
            if restart_dwell or not a.active or speed[1:3] != a.active[1:3]:
                a.changed_at = now
            a.active = speed
        cmd = (speed[1], speed[2], speed[3])
        if cmd != a.sent:
            a.sent = cmd
            return [(axis, self._slow_msg(axis, *cmd))]
        return []

    @staticmethod
    def _bracket(target, speeds):
        """The two adjacent speeds either side of the target (the same speed twice if on or beyond one)."""
        v = float(np.clip(target, speeds[0][0], speeds[-1][0]))
        hi_i = next(i for i, s in enumerate(speeds) if s[0] >= v - 1e-12)
        hi = speeds[hi_i]
        lo = hi if abs(hi[0] - v) < 1e-12 or hi_i == 0 else speeds[hi_i - 1]
        return lo, hi

    def _slow_msg(self, axis, key, state, level):
        return f"1&{SLOW_CMD[axis]}&3&key:{key};state:{state};level:{level};#"

    # ---- FAST -----------------------------------------------------------------------
    def _fast_msg(self, axis, a: _Axis, now):
        if a.ramp_s > 0:
            blend = min(1.0, (now - a.ramp_start) / a.ramp_s)
            speed = a.fast_from + blend * (a.fast_to - a.fast_from)
        else:
            speed = a.fast_to
        a.fast_now = float(np.clip(round(speed), -FAST_UNITS_MAX, FAST_UNITS_MAX))
        a.next_fast = now + self.fast_period
        return f"1&{FAST_CMD[axis]}&3&speed:{int(a.fast_now)};#"


# ---------------------------------------------------------------------------------------
# asyncio runtime and legacy-compatible per-axis interface
# ---------------------------------------------------------------------------------------
class SpeedControllerRuntime:
    """Runs a SpeedCoordinator on the event loop and sends its messages."""

    def __init__(self, units: dict, send_msg, slow_period: float = 0.25, fast_period: float = 0.05,
                 log: Optional[logging.Logger] = None):
        self.core = SpeedCoordinator(units, slow_period, fast_period)
        self.units = units
        self._send = send_msg
        self._log = log or logger
        self._wake = asyncio.Event()
        self._stopping = False
        self._handles = {axis: AxisSpeedController(self, axis) for axis in range(3)}
        self._task = asyncio.create_task(self._loop(), name="SpeedControllerV2")

    def axis(self, axis: int) -> "AxisSpeedController":
        return self._handles[axis]

    def command(self, axis, dps, **kwargs):
        self.core.set_speed(axis, dps, time.monotonic(), **kwargs)
        self._wake.set()

    async def _loop(self):
        while not self._stopping:
            self._wake.clear()
            now = time.monotonic()
            for _axis, msg in self.core.tick(now):
                try:
                    await self._send(msg)
                except Exception as e:                       # never let a send error kill the loop
                    self._log.warning(f"SpeedControllerV2 send failed: {e}")
            timeout = max(0.0, self.core.next_wakeup(now) - time.monotonic())
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass

    async def stop(self):
        if not self._stopping:
            self._stopping = True
            self._wake.set()
            await self._task


class AxisSpeedController:
    """Per-axis view of the runtime with the legacy MotorSpeedController interface."""

    def __init__(self, runtime: SpeedControllerRuntime, axis: int):
        self._rt, self.axis = runtime, axis

    async def set_motor_speed(self, rate, rate_unit="DPS", ramp_duration=None, allow_PWM=True, tracking=False):
        if rate_unit not in ('RAW', 'DPS', 'ASCOM'):
            self._rt._log.info(f'Set Motor Speed - Invalid units {rate_unit}')
            return
        dps = self._rt.units[self.axis].to_dps(rate, rate_unit)
        self._rt.command(self.axis, dps, hold=tracking, ramp_duration=ramp_duration, allow_pwm=allow_PWM)

    @property
    def rate_dps(self) -> float:
        return self._rt.core.rate_dps(self.axis)

    @property
    def rate_raw(self) -> float:
        return self._rt.core.rate_raw(self.axis)

    def get_cmdstr(self) -> str:
        return self._rt.core.cmdstr(self.axis)

    def to_dps(self, rate, units) -> float:
        return self._rt.units[self.axis].to_dps(rate, units)

    @property
    def max_dps(self) -> float:
        return self._rt.units[self.axis].max_dps

    def resync(self):
        self._rt.core.forget_sent(self.axis)

    async def stop_disspatch_loop_task(self):
        await self._rt.stop()


class SwitchableMotor:
    """Hot-swappable facade over the legacy and v2 controllers for one axis (beta phase)."""

    def __init__(self, legacy, v2, use_new: bool = False):
        self._legacy, self._v2, self.use_new = legacy, v2, bool(use_new)

    @property
    def active(self):
        return self._v2 if self.use_new else self._legacy

    async def set_motor_speed(self, *args, **kwargs):
        await self.active.set_motor_speed(*args, **kwargs)

    @property
    def rate_dps(self):
        return self.active.rate_dps

    @property
    def rate_raw(self):
        return self.active.rate_raw

    def get_cmdstr(self):
        return self.active.get_cmdstr()

    def to_dps(self, rate, units) -> float:
        m = self.active
        if hasattr(m, 'to_dps'):
            return float(m.to_dps(rate, units))
        return float(m._model.interpolate['RAW'].toDPS(m._model.interpolate[units].toRAW(rate)))

    @property
    def max_dps(self) -> float:
        m = self.active
        return float(m.max_dps if hasattr(m, 'max_dps') else m._model.maxDPS)

    async def select(self, use_new: bool):
        """Stop the outgoing controller on this axis, then route commands to the other one."""
        use_new = bool(use_new)
        if use_new == self.use_new:
            return
        await self.active.set_motor_speed(0, "DPS")
        self.use_new = use_new
        if hasattr(self.active, 'resync'):
            self.active.resync()

    async def stop_disspatch_loop_task(self):
        await self._legacy.stop_disspatch_loop_task()
        await self._v2.stop_disspatch_loop_task()
