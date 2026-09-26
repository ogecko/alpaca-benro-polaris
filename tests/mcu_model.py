"""
Test double for the Benro Polaris gimbal MCU's motor speed behaviour, as reverse engineered
from polaris413_2.0.0.22.bin (A Polaris System Design.md §5.4) and verified on hardware.

It consumes the driver's 53x (SLOW) and 51x/521 (FAST) messages with timestamps and integrates
each motor's angle, so tests can check what the mount would actually do:

- SLOW 532/533/534 'key:k;state:s;level:l': ONE level shared by M1 and M2. A 53x for any axis,
  including 534, sets it (level 1..5; 0 or >5 keeps the previous speed pair). Direction and
  state (1 = start, 2 = continue) are per axis. state 0 stops the axis; state > 2 counts as 0.
- M3 (534) is driven by the astro module, which keeps its own copy of the level from each 534.
- FAST 513/514/521 'speed:n' overrides SLOW on that axis while refreshed (watchdog).
- SLOW commands are only picked up on the MCU scheduler tick (MCU_TICK_S). Hardware shows
  commands changing every 0.1 s alias badly (0.28x-0.48x) while >= 0.25 s is accurate;
  dwells of 0.045-0.055 s aliased and >= 0.067 s were fine, so the tick is modelled as 0.05 s.
"""
import math
import re

import numpy as np
from scipy.interpolate import PchipInterpolator

# Measured SLOW speeds (deg/s) by (level, state), utility/state2_test.py 2026-09-26.
SLOW_DPS = {
    (1, 1): 0.0059, (2, 1): 0.0179, (3, 1): 0.0474, (4, 1): 0.0896, (5, 1): 0.2088,
    (1, 2): 0.0119, (2, 2): 0.0295, (3, 2): 0.0593, (4, 2): 0.1193, (5, 2): 0.2402,
}
SLOW_CMD_AXIS = {"532": 0, "533": 1, "534": 2}
FAST_CMD_AXIS = {"513": 0, "514": 1, "521": 2}
FAST_WATCHDOG_S = 0.5
MCU_TICK_S = 0.05

# FAST speed units -> deg/s (baseline calibration, axis 0), good enough for a model.
_FAST_UNITS = [200, 300, 400, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500]
_FAST_DPS = [0.0856, 0.1956, 0.3489, 0.5494, 1.0888, 1.7125, 2.5597, 3.4889, 4.6249, 5.8938, 7.3678, 8.9186]
_fast_to_dps = PchipInterpolator(_FAST_UNITS, _FAST_DPS, extrapolate=True)

_SLOW_RE = re.compile(r"^1&(53[234])&3&key:(\d+);state:(\d+);level:(\d+);#$")
_FAST_RE = re.compile(r"^1&(51[34]|521)&3&speed:(-?\d+);#$")


class McuModel:
    def __init__(self):
        self.t = 0.0
        self.shared_level = None                 # K[3] as seen by M1/M2 (last valid level)
        self.astro_level = None                  # astro module's own level for M3
        self.dir = [0, 0, 0]                     # +1 / -1 per axis
        self.state = [0, 0, 0]                   # 0, 1, 2 per axis
        self.fast_speed = [0, 0, 0]
        self.fast_until = [-1.0, -1.0, -1.0]
        self.position = np.zeros(3)
        self.log = []                            # (t, axis, kind, fields)
        self._latched = (None, None, (0, 0, 0), (0, 0, 0))   # SLOW state as last sampled on a tick

    # ---- speeds -----------------------------------------------------------------
    def slow_dps(self, axis):
        shared, astro, dirs, states = self._latched
        level = astro if axis == 2 else shared
        if states[axis] not in (1, 2) or level is None:
            return 0.0
        return dirs[axis] * SLOW_DPS[(level, states[axis])]

    def _latch(self):
        self._latched = (self.shared_level, self.astro_level, tuple(self.dir), tuple(self.state))

    def dps(self, axis):
        if self.t < self.fast_until[axis]:
            s = self.fast_speed[axis]
            return float(np.sign(s) * _fast_to_dps(abs(s))) if s else 0.0
        return self.slow_dps(axis)

    def velocity(self):
        return np.array([self.dps(a) for a in range(3)])

    # ---- time and messages -----------------------------------------------------
    def advance(self, t):
        """Integrate positions up to time t, honouring FAST watchdog expiry on the way."""
        while self.t < t:
            tick = (math.floor(self.t / MCU_TICK_S + 1e-9) + 1) * MCU_TICK_S
            nxt = min([t, tick] + [u for u in self.fast_until if self.t < u < t])
            self.position += self.velocity() * (nxt - self.t)
            self.t = nxt
            if abs(self.t - tick) < 1e-9:
                self._latch()

    def feed(self, t, msg):
        self.advance(t)
        m = _SLOW_RE.match(msg)
        if m:
            axis = SLOW_CMD_AXIS[m.group(1)]
            key, state, level = int(m.group(2)), int(m.group(3)), int(m.group(4))
            self.dir[axis] = +1 if key == 0 else -1
            self.state[axis] = state if state <= 2 else 0
            if 1 <= level <= 5:
                self.shared_level = level
                if axis == 2:
                    self.astro_level = level
            self.log.append((t, axis, "SLOW", (key, state, level)))
            return
        m = _FAST_RE.match(msg)
        if m:
            axis = FAST_CMD_AXIS[m.group(1)]
            self.fast_speed[axis] = int(m.group(2))
            self.fast_until[axis] = t + FAST_WATCHDOG_S
            self.log.append((t, axis, "FAST", int(m.group(2))))
            return
        raise ValueError(f"McuModel: unrecognised message {msg!r}")
