"""
A simple PHD2-like guider for the digital twin (tests/sim_digital_twin.py).

The twin knows where the mount really points (the MCU model's motor angles through the alignment
model, with no guide/PEC corrections). This guider adds an injected drift the driver cannot see -- the
stand-in for periodic error or model error -- measures the true pointing against its lock position
every frame, and corrects it with the driver's real PulseGuide path (SyncManager.process_pulse_guide_axis).

Like PHD2 it does not assume which way a pulse moves the mount: calibrate() pulses each axis and
records the measured direction, and guiding then uses that, so the sign of the driver's corrections is
measured rather than assumed.

Angles are RA-coordinate and Dec degrees throughout (RA in degrees, i.e. hours x 15), matching the
driver's pulse residuals: a pulse of d ms at guide rate g deg/s is a correction of d/1000 x g degrees.
"""
import numpy as np

from kinematics import theta_to_q, q_to_azaltroll

ASCOM_NORTH, ASCOM_SOUTH, ASCOM_EAST, ASCOM_WEST = 0, 1, 2, 3
ARCSEC = 3600.0


def wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


class SimGuider:
    def __init__(self, twin, drift=None, guide_rate_deg_s=15.0 / ARCSEC, frame_s=2.0, aggression=0.7,
                 min_move_arcsec=0.3, max_pulse_ms=2500, seeing_arcsec=0.0, seed=0):
        """drift(t_sec) -> (ra_deg, dec_deg): extra pointing error the driver cannot see, t from guider start."""
        self.tw = twin
        self.drift = drift or (lambda t: (0.0, 0.0))
        self.rate = guide_rate_deg_s
        self.frame_s, self.aggression = frame_s, aggression
        self.min_move = min_move_arcsec / ARCSEC
        self.max_ms = max_pulse_ms
        self.seeing = seeing_arcsec / ARCSEC
        self.rng = np.random.default_rng(seed)
        twin.polaris._guideraterightascension = guide_rate_deg_s
        twin.polaris._guideratedeclination = guide_rate_deg_s
        self.t0 = twin.clock.t
        self.lock = None
        self.east_sign = self.north_sign = None     # +1: an East/North pulse increases true RA/Dec
        self.frames = []                            # (t, ra_err_deg, dec_err_deg)
        self.corrections = []                       # (t, axis, driver-signed correction deg) -- as PEC sees it

    # ── where the mount really points ──────────────────────────────────────────────────
    def encoder_radec(self):
        sm, p = self.tw.polaris._sm, self.tw.polaris
        cameraQ = sm.alignQ_B2T * theta_to_q(*self.tw.mcu.position)
        az, alt, _ = q_to_azaltroll(cameraQ)
        ra_h, dec = p.altaz2radec(alt, az)
        return ra_h * 15.0, dec

    def true_radec(self):
        ra, dec = self.encoder_radec()
        d_ra, d_dec = self.drift(self.tw.clock.t - self.t0)
        return ra + d_ra, dec + d_dec

    # ── pulses through the driver ────────────────────────────────────────────────────────
    def pulse(self, direction, ms):
        ms = int(min(self.max_ms, round(ms)))
        if ms <= 0:
            return
        self.tw.polaris._sm.process_pulse_guide_axis(direction, ms)
        axis = 0 if direction in (ASCOM_EAST, ASCOM_WEST) else 1
        sign = +1 if direction in (ASCOM_EAST, ASCOM_NORTH) else -1
        self.corrections.append((self.tw.clock.t, axis, sign * ms / 1000 * self.rate))

    def calibrate(self, ms=2000, settle_s=6.0):
        """Measure which way an East and a North pulse move the true pointing, then pulse back."""
        for direction, back, attr, idx in ((ASCOM_EAST, ASCOM_WEST, 'east_sign', 0),
                                           (ASCOM_NORTH, ASCOM_SOUTH, 'north_sign', 1)):
            before = np.array(self.encoder_radec())
            self.pulse(direction, ms)
            self.tw.run(settle_s)
            moved = np.array(self.encoder_radec()) - before
            moved[0] = wrap180(moved[0])
            setattr(self, attr, 1 if moved[idx] > 0 else -1)
            self.pulse(back, ms)
            self.tw.run(settle_s)
        self.corrections.clear()

    # ── guiding ──────────────────────────────────────────────────────────────────────────
    def start(self):
        if self.east_sign is None:
            self.calibrate()
        self.t0 = self.tw.clock.t
        self.lock = self.true_radec()
        self._next = self.tw.clock.t

    def _frame(self, tw):
        if tw.clock.t < self._next - 1e-9:
            return
        self._next += self.frame_s
        ra, dec = self.true_radec()
        e_ra = wrap180(ra - self.lock[0]) + self.rng.normal(0, self.seeing)
        e_dec = dec - self.lock[1] + self.rng.normal(0, self.seeing)
        self.frames.append((tw.clock.t, e_ra, e_dec))
        for err, plus, minus, sign in ((e_ra, ASCOM_EAST, ASCOM_WEST, self.east_sign),
                                       (e_dec, ASCOM_NORTH, ASCOM_SOUTH, self.north_sign)):
            if abs(err) < self.min_move:
                continue
            # move against the error: the direction whose measured effect has the opposite sign
            direction = minus if err * sign > 0 else plus
            self.pulse(direction, self.aggression * abs(err) / self.rate * 1000)

    def guide(self, seconds):
        self.tw.run(seconds, on_measure=self._frame)

    # ── results ──────────────────────────────────────────────────────────────────────────
    def error_rms_arcsec(self, since_s=0.0):
        f = np.array([fr for fr in self.frames if fr[0] - self.t0 >= since_s])
        return float(np.sqrt(np.mean(f[:, 1] ** 2))) * ARCSEC, float(np.sqrt(np.mean(f[:, 2] ** 2))) * ARCSEC

    def correction_rate_arcsec_min(self, axis, since_s=0.0):
        """Net driver-signed guide correction per minute on an axis -- what PEC is trained on."""
        c = [d for t, a, d in self.corrections if a == axis and t - self.t0 >= since_s]
        span = (self.tw.clock.t - self.t0 - since_s) / 60.0
        return sum(c) * ARCSEC / span if span > 0 else 0.0


class SimPlateSolver(SimGuider):
    """
    Sync guiding without a guide scope (NINA/ASIAIR plate-solve + sync after each exposure): every
    `interval_s` the true pointing (with the injected drift and solve noise) is passed to the driver's
    real SyncManager.process_guide_sync(), which corrects by the whole residual and trains PEC on it.
    The error measured is the true pointing against the target held when start() was called.
    """
    def __init__(self, twin, drift=None, interval_s=120.0, solve_noise_arcsec=0.0, seed=0):
        super().__init__(twin, drift=drift, frame_s=interval_s, seeing_arcsec=solve_noise_arcsec, seed=seed)
        self.samples = []                           # (t, ra_err_deg, dec_err_deg) every control tick

    def start(self):
        sm = self.tw.polaris._sm
        sm.enable_sync_guiding()
        self.t0 = self.tw.clock.t
        self.lock = self.true_radec()
        self._next = self.tw.clock.t + self.frame_s

    def _sample(self, tw):
        ra, dec = self.true_radec()
        self.samples.append((tw.clock.t, wrap180(ra - self.lock[0]), dec - self.lock[1]))
        if tw.clock.t < self._next - 1e-9:
            return
        self._next += self.frame_s
        p = tw.polaris
        ra_obs = ra + self.rng.normal(0, self.seeing)
        dec_obs = dec + self.rng.normal(0, self.seeing)
        e = self.frames.append
        e((tw.clock.t, wrap180(ra - self.lock[0]), dec - self.lock[1]))
        before = (p.rightascension * 15.0, p.declination)
        p._sm.process_guide_sync(ra_obs / 15.0, dec_obs, p._p_azimuth, p._p_altitude)
        self.corrections.append((tw.clock.t, 0, wrap180(ra_obs - before[0])))
        self.corrections.append((tw.clock.t, 1, dec_obs - before[1]))

    def guide(self, seconds):
        self.tw.run(seconds, on_measure=self._sample)

    def error_rms_arcsec(self, since_s=0.0):
        """RMS of the true pointing error at every control tick (not just at solves)."""
        s = np.array([x for x in self.samples if x[0] - self.t0 >= since_s])
        return float(np.sqrt(np.mean(s[:, 1] ** 2))) * ARCSEC, float(np.sqrt(np.mean(s[:, 2] ** 2))) * ARCSEC
