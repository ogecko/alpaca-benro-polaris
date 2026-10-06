# -----------------------------------------------------------------------------
# control_pec.py - PEC: predictive drift correction for SyncManager
# -----------------------------------------------------------------------------
#
# PEC learns how fast the mount is drifting from the guide corrections it receives and applies that rate ahead of
# the guider, so the guider only has to correct what is left.
#
#   PecMixin      SyncManager's PEC methods (mixed into control.SyncManager)
#     learning      update_pec_model(): each sync guide residual (plate-solve sync), and ingest_pulse_for_pec(): each
#                   pulse guide when Config.advanced_pulse_pec_tuning -- per axis (RA, Dec), as a running total of drift
#     applying      step_pec_drift(), every control tick while tracking: the predicted rate becomes a feed-forward velocity
#                   for the PID (omega_pec_B) and the same correction is folded into the sync guide correction, so the
#                   PID treats the moved pointing as on target; each step is capped (pec_max_step_arcmin)
#     gating        nothing is applied until an axis's model has converged: pec_min_observations, rmse below
#                   pec_max_rmse_arcmin, R2 above pec_min_r2 (PecInhibit says why not); residuals above
#                   pec_max_resid_arcmin are ignored; gotos, pans, rolls, tracking off and settings changes reset the
#                   model (reset_pec_model)
#     logging       PECCONFIG once per session, PECLOG per update (drift totals, model, inhibit, motor angles) for
#                   utility/analyse_tracking.ipynb
#   PecAxis       one axis's drift model: the observed drift rate, exponentially smoothed (EMA, time constant
#                   pec_tau_sec). A recursive least squares model (linear drift + harmonics of a 34 min period) was
#                   removed in v2.2 Beta 7: on the archived logs it did no better than no PEC, while EMA with a
#                   5-10 min time constant did best (utility/analyse_sessions.ipynb).
#   GuiderCalibrationDetector
#                 recognises a guider's calibration (PHD2, CCDciel) in the pulses, so PEC doesn't learn its large
#                 deliberate moves as drift; what was learnt during it is rolled back (pec_ignore_guider_calibration)
#
# The worm gear correction (Config.advanced_pec_worm, with a profile from the worm profile test) is a separate,
# fixed correction: see control_worm.py.
# PEC keeps working on whatever drift that leaves.
# -----------------------------------------------------------------------------

import copy
import math
import time
from dataclasses import dataclass
from enum import IntEnum

import numpy as np

from config import Config


@dataclass(frozen=True)
class PulseVerdict:
    ingest: bool       # learn from this pulse
    run_start: bool    # this pulse starts a new run -- snapshot state before learning from it
    rollback: bool     # calibration recognised -- undo what was learnt since the run started


class GuiderCalibrationDetector:
    """
    When PEC learns from pulse guiding, every pulse is treated as a guide correction of drift.
    A guider's calibration (PHD2, CCDciel, ...) is not: it deliberately moves the mount tens of
    pixels in each direction, and PEC learning those pulses fits a large false drift rate
    (2026-09-29 session: RA fit -785 arcmin/hr after a PHD2 calibration, which guiding then had
    to fight at +363"/min).

    The driver only sees PulseGuide(direction, duration), so GuiderCalibrationDetector recognises
    calibration by its signature: ONE axis at a time, ONE direction, and either IDENTICAL durations
    (PHD2's steps, backlash clearing and recenters) or a RAMP where each pulse is exactly 1.5x the
    previous one (CCDciel's internal guider grows its East pulse from its "initial calibration step"
    until the star moves; cu_autoguider_internal.pas, durations rounded to whole ms). Guiding sends
    RA and Dec pulses in the same frame with durations computed from the measured error, so neither
    run of `run_length` (3) occurs while guiding: replaying 43,199 PHD2 guide pulses (2026-09-29)
    gave 0 identical runs of 3 (but 59 runs of 2) and one 1.5x ramp of short pulses (79, 118, 176 ms),
    so a ramp only triggers once its pulse reaches `ramp_min_ms` (300); CCDciel's 2,079 guide pulses
    (2026-09-12) gave none.

    Because the first run_length-1 calibration pulses are only recognised in hindsight, the
    verdict for the triggering pulse asks the caller to roll back what it learnt since the
    start of the run (run_start marks where to snapshot). Once active, nothing is learnt until
    no repeated (identical or ramp) pulse has been seen for `quiet_sec`. Recenter pulses, backlash
    clearing and the Dec steps all repeat, so the whole calibration stays suppressed (CCDciel's single
    West return pulse arrives a guide frame after the ramp); afterwards only the first `quiet_sec` of
    guiding is skipped.

    The detector only ever withholds learning: a missed calibration behaves as before, and a
    false trigger costs `quiet_sec` of PEC observations. Config.pec_ignore_guider_calibration.
    """
    RAMP_FACTOR = 1.5            # CCDciel: CalibrationDuration := round(CalibrationDuration * 1.5)

    def __init__(self, run_length=3, quiet_sec=20.0, ramp_min_ms=300):
        self.run_length  = run_length
        self.quiet_sec   = quiet_sec
        self.ramp_min_ms = ramp_min_ms
        self.reset()

    def reset(self):
        self.active       = False
        self._last_pulse  = None     # (axis, sign, duration_ms) of the previous pulse
        self._run         = 0        # length of the current run of identical pulses
        self._ramp        = 0        # length of the current run of 1.5x pulses
        self._last_repeat = None     # time of the last repeated pulse while active

    def _step(self, pulse):
        """'same' or 'ramp' if this pulse continues the previous one's run, else None."""
        last = self._last_pulse
        if last is None or last[:2] != pulse[:2]:
            return None
        if pulse[2] == last[2]:
            return 'same'
        if abs(pulse[2] - self.RAMP_FACTOR * last[2]) <= 0.5:   # whole-ms rounding of the 1.5x step
            return 'ramp'
        return None

    def observe(self, axis, sign, duration_ms, now):
        pulse = (axis, sign, int(duration_ms))
        step = self._step(pulse)
        repeat = step is not None
        self._run  = self._run + 1 if step == 'same' else 1
        self._ramp = self._ramp + 1 if step == 'ramp' else 1
        self._last_pulse = pulse

        if self.active:
            if repeat:
                self._last_repeat = now
                return PulseVerdict(ingest=False, run_start=False, rollback=False)
            if now - self._last_repeat <= self.quiet_sec:
                return PulseVerdict(ingest=False, run_start=True, rollback=False)
            self.active = False

        if self._run >= self.run_length or (self._ramp >= self.run_length and pulse[2] >= self.ramp_min_ms):
            self.active = True
            self._last_repeat = now
            return PulseVerdict(ingest=False, run_start=False, rollback=True)

        return PulseVerdict(ingest=True, run_start=not repeat, rollback=False)


class PecMixin:
    """PEC and drift modelling methods of SyncManager (see control.SyncManager)."""

    def init_pec(self):
        """Create the PEC state; called once from SyncManager.__init__."""
        self._guider_cal = GuiderCalibrationDetector()   # recognises PHD2/CCDciel calibration so PEC ignores it
        self._pec_run_snapshot = None           # PEC state before the current run of identical pulses (rollback point)
        self._pec_generation = 0                # bumped by reset_pec_model(), invalidates a snapshot across resets
        self._pec_ingest_seq = 0                # bumped on every PEC seed/ingest, invalidates a snapshot if anything else ingests
        self.init_pec_model()

    def init_pec_model(self):
        """Initialise (or reset) the recursive drift model. Safe to call after slew."""
        self._pec_n           = 0
        self._pec_t0          = None
        self._pec_last_apply  = None
        self._pec_guide_last_time  = None

        # Config-driven thresholds (read once so update/apply don't need getattr)
        self._pec_tau         = getattr(Config, 'pec_tau_sec',            7.5*60)           # EMA smoothing time constant (sec)
        self._pec_min_dt      = getattr(Config, 'pec_min_dt_sec',         0.05)           # ignore an axis update if it arrives sooner than this since that axis's own last update
        self._pec_min_obs     = getattr(Config, 'pec_min_observations',   3)              # inhibit until n > min_obs
        self._pec_max_resid   = getattr(Config, 'pec_max_resid_arcmin',   10.0)  / 60.0   # ignore guide update if resid > max_resid degrees
        self._pec_max_step    = getattr(Config, 'pec_max_step_arcmin',    0.5)   / 60.0   # clamp +/-correction step to max_step degrees every 200ms
        self._pec_max_rmse    = getattr(Config, 'pec_max_rmse_arcmin',    6.0)   / 60.0   # inhibit if rmse > max_rmse degrees
        self._pec_min_r2      = getattr(Config, 'pec_min_r2',             0.5)            # inhibit if bad R2 < 0.5

        self._pec_ra  = PecAxis(tau=self._pec_tau, min_dt=self._pec_min_dt)
        self._pec_dec = PecAxis(tau=self._pec_tau, min_dt=self._pec_min_dt)

        self._pec_var_alpha  = 0.05           # EMA factor for var estimate, more stable R2
        self._pec_sse_alpha  = 0.15           # EMA factor for sse estimate, faster tracking decay
        self._pec_active      = False

        if Config.log_pec and getattr(self, '_log_pec_config', True):
            self.logger.info(f"PECCONFIG drift,{bool(Config.advanced_pec_drift)},worm,{bool(Config.advanced_pec_worm)},"
                             f"tau_sec,{self._pec_tau},min_dt_sec,{self._pec_min_dt}")
            self._log_pec_config = False


    def reset_pec_model(self):
        """Call after slew, rotate, or QUEST reset."""
        self._pec_generation += 1               # a calibration rollback must not undo this reset
        self.init_pec_model()

    def ingest_pulse_for_pec(self, axis, sign, duration_ms, angle_deg):
        """
        Feed one pulse guide correction to the PEC model, ignoring a guider's calibration.
        GuiderCalibrationDetector recognises calibration only on its 3rd identical pulse, so the
        model is snapshotted at the start of every run of identical pulses and rolled back to
        that snapshot when the run turns out to be a calibration.
        """
        ra_resid  = angle_deg if axis == 0 else None
        dec_resid = angle_deg if axis == 1 else None
        if not getattr(Config, 'pec_ignore_guider_calibration', True):
            self.update_pec_model(ra_resid, dec_resid)
            return

        was_active = self._guider_cal.active
        verdict = self._guider_cal.observe(axis, sign, duration_ms, time.monotonic())
        if was_active and not self._guider_cal.active:
            self.logger.info("->> Polaris: PEC resumed learning from pulse guiding after guider calibration")
        if verdict.run_start:
            self._pec_run_snapshot = self._pec_snapshot(axis)
        if verdict.rollback:
            rolled_back = self._pec_rollback_run()
            self.logger.info(f"->> Polaris: PEC ignoring guider calibration pulses "
                             f"({'rolled back' if rolled_back else 'could not roll back'} the start of the calibration)")
        if not verdict.ingest:
            return

        seq_before = self._pec_ingest_seq
        ingested = self.update_pec_model(ra_resid, dec_resid)
        snap = self._pec_run_snapshot
        if snap is not None and self._pec_ingest_seq != seq_before:
            snap['ingests'] += 1
            if ingested:
                snap['resid_sum'] += float(angle_deg)

    def _pec_snapshot(self, axis):
        """PEC state for one axis (a run only ever moves one axis) plus the shared counters."""
        return {
            'axis': axis, 'generation': self._pec_generation, 'seq': self._pec_ingest_seq,
            'ingests': 0, 'resid_sum': 0.0,
            'n': self._pec_n, 't0': self._pec_t0, 'last_apply': self._pec_last_apply,
            'state': copy.deepcopy(self._pec_ra if axis == 0 else self._pec_dec),
        }

    def _pec_rollback_run(self):
        """
        Restore the PEC model to the snapshot taken before the current run, as if its pulses had
        never been seen. PEC correction applied by the control loop since the snapshot is kept:
        whatever ingest() folded into _accum (beyond the run's own residuals) and whatever is
        still pending in _applied_accum goes back into _applied_accum, to be folded at the next ingest.
        Returns False if the snapshot no longer applies (model reset, or another source ingested).
        """
        snap, self._pec_run_snapshot = self._pec_run_snapshot, None
        if snap is None or snap['generation'] != self._pec_generation:
            return False
        if self._pec_ingest_seq - snap['seq'] != snap['ingests']:
            return False

        name = '_pec_ra' if snap['axis'] == 0 else '_pec_dec'
        current, restored = getattr(self, name), snap['state']
        if snap['n'] > 0:
            restored._applied_accum = (current._accum - restored._accum - snap['resid_sum']) + current._applied_accum
            restored._applied_rate  = current._applied_rate
        else:
            self._pec_t0         = snap['t0']
            self._pec_last_apply = snap['last_apply']
        setattr(self, name, restored)
        self._pec_n = snap['n']
        self._pec_active = self._pec_ra.converged() or self._pec_dec.converged()
        return True

    def update_pec_model(self, ra_resid_deg, dec_resid_deg):
        """
        Ingest a guide correction into the PEC model.
        Either or both residuals may be None (pulse guiding sends one axis at a time).
        Returns True if the residuals were fitted (False if disabled, rejected or used as the seed).
        """
        if not Config.advanced_pec_drift:
            return False

        now = time.monotonic()
        ra_resid  = self._pec_validate_resid(ra_resid_deg)
        dec_resid = self._pec_validate_resid(dec_resid_deg)

        if ra_resid is None and dec_resid is None:
            return False

        self._pec_ingest_seq += 1
        if not self._pec_initialised(now, ra_resid, dec_resid):
            return False

        t = now - self._pec_t0
        # Snapshot the PEC-only accumulator *before* _pec_update_axes() -> ingest() folds it into
        # _accum (the total-drift reconstruction) and resets it to 0.0 -- read after that call,
        # it would always log as ~0 regardless of how much PEC actually applied since the
        # previous PECLOG entry.
        pec_accum_snapshot = (self._pec_ra._applied_accum, self._pec_dec._applied_accum)
        self._pec_update_axes(ra_resid, dec_resid, t)
        self._pec_log(ra_resid, dec_resid, pec_accum_snapshot)
        return True

    def _pec_validate_resid(self, resid):
        """Returns float residual if valid, None if missing or outlier."""
        if resid is None:
            return None
        resid = float(resid)
        if abs(resid) > self._pec_max_resid:
            return None
        return resid

    def _pec_initialised(self, now, ra_resid, dec_resid):
        """
        Ensures model is ready. Seeds axes on first valid observation.
        Returns False if this call should be consumed as the seed (no fit update yet).
        """
        if self._pec_t0 is None:
            self.init_pec_model()

        if self._pec_n == 0:
            self._pec_t0         = now
            self._pec_last_apply = now
            if ra_resid  is not None: self._pec_ra.reset_seed()
            if dec_resid is not None: self._pec_dec.reset_seed()
            self._pec_n = 1
            return False

        return True

    def _pec_update_axes(self, ra_resid, dec_resid, t):
        """Update each axis's fit and inhibit state. Each axis derives its own lambda/alpha from its own dt."""
        if ra_resid is not None:
            self._pec_ra.ingest(ra_resid,   t, self._pec_var_alpha, self._pec_sse_alpha)
        if dec_resid is not None:
            self._pec_dec.ingest(dec_resid, t, self._pec_var_alpha, self._pec_sse_alpha)

        self._pec_n += 1

        self._pec_ra.eval_inhibit( self._pec_n, self._pec_min_obs, self._pec_max_rmse, self._pec_min_r2)
        self._pec_dec.eval_inhibit(self._pec_n, self._pec_min_obs, self._pec_max_rmse, self._pec_min_r2)
        self._pec_active = self._pec_ra.converged() or self._pec_dec.converged()

    def _pec_log(self, ra_resid, dec_resid, pec_accum_snapshot):
        if not Config.log_pec:
            return
        ra, dec = self._pec_ra, self._pec_dec
        pv_deg = self.polaris._pid.alpha_pv
        theta_raw = getattr(self.polaris, '_theta_raw', None)
        zeta = getattr(self.polaris, '_zeta_meas', None)
        zeta_off = getattr(self.polaris, '_zeta_raw_offset', None)
        t517 = getattr(self.polaris, '_last_517_timesec', None)
        pec_accum_ra, pec_accum_dec = pec_accum_snapshot
        # float(): several values below (pv_deg elements, PecAxis floats) can be numpy scalars, whose
        # numpy-2.x repr (e.g. np.float64(1.23)) breaks ast.literal_eval() on readback.
        # Paired fields are [ra, dec] lists -- matching PIDLOG/KFLOG's axis-indexed convention
        # (there, 1/2/3 = M1/M2/M3; here, 1/2 = ra/dec via the standard "_i+1" flattening).
        # Rounded for readability -- re-derive from PecAxis state directly if you need full
        # precision.
        ARCMIN_PER_HOUR = 3600 * 60   # deg/sec -> arcmin/hr
        payload = {
            # guide-sync counter, resets after a goto
            "n": self._pec_n,

            # per-axis fit status: TOO_FEW_OBS -> LOW_R2/HIGH_RMSE -> VALID
            "inhibit": [ra.inhibit.name, dec.inhibit.name],

            # fit quality, 0-1, dimensionless
            "r2": [round(float(ra.r2), 4), round(float(dec.r2), 4)],

            # arcmin, fit residual noise
            "rmse": [round(float(ra.rmse_arcmin()), 4), round(float(dec.rmse_arcmin()), 4)],

            # arcmin, this sync's raw guide error -- should shrink as PEC improves.
            "resid": [
                round(float(ra_resid * 60), 4)  if ra_resid  is not None else None,
                round(float(dec_resid * 60), 4) if dec_resid is not None else None,
            ],
            # arcmin/hr, model's rate as of the last ingest (frozen between syncs)
            "fit_rate": [round(float(ra.theta*ARCMIN_PER_HOUR), 3), round(float(dec.theta*ARCMIN_PER_HOUR), 3)],

            # arcmin/hr, rate actually driving the motors as of the last successful control tick
            "applied_rate": [round(float(ra._applied_rate*ARCMIN_PER_HOUR), 3), round(float(dec._applied_rate*ARCMIN_PER_HOUR), 3)],

            # arcmin, PEC correction actually applied since the *previous* PECLOG entry only (resets every sync)
            # Euler-integration of the continuously-advancing predicted_rate(t)
            "pec_accum": [round(float(pec_accum_ra*60), 4), round(float(pec_accum_dec*60), 4)],

            # arcmin, (resid + pec_accum) accumulated across every sync since the PEC model was last reset (goto/rotate/jog/stop-tracking/config change), not since the last sync
            # The fit's training signal; deliberately doesn't shrink as PEC improves (see docs/control.md)
            "total_accum": [round(float(ra._accum*60), 4), round(float(dec._accum*60), 4)],

            # degrees, current topocentric position
            "az": round(float(pv_deg[0]), 3), "alt": round(float(pv_deg[1]), 3), "roll": round(float(pv_deg[2]), 3),

            # degrees, raw MCU motor angles [M1, M2, M3] as of the last 518 message (as SGLOG) -- per-motor
            # worm analysis needs these, not the pose (which includes the session's alignment)
            "theta_raw": [round(float(v), 5) for v in theta_raw] if theta_raw is not None else [None, None, None],

            # degrees, the MCU's own motor angles from the last 517 (polled about once a minute; no compass / SPA
            # heading), theta_raw - zeta at that 517, and its age in seconds -- theta_raw - zeta_offset is the motor
            # angle at every entry, comparable across sessions (per-motor worm phase)
            "zeta": [round(float(v), 5) for v in zeta] if zeta is not None else [None, None, None],
            "zeta_offset": [round(float(v), 5) for v in zeta_off] if zeta_off is not None else [None, None, None],
            "zeta_age": round(time.monotonic() - t517, 1) if (zeta is not None and t517 is not None) else None,

            # arcmin, the worm feed-forward currently applied (when there is a worm gear profile), split along the RA and Dec axes.
            # Guide corrections (and so total_accum) no longer include what it corrects: add it back for the drift.
            "wff": self._wff_radec_arcmin(),

            # EMA weight of the previous rate at the last ingest, exp(-dt / tau), dimensionless
            "lambda": [round(float(ra.lam), 5), round(float(dec.lam), 5)],

            # ra.converged() or dec.converged() -- gates step_pec_drift() as a
            # whole, but is not per-axis: check inhibit[0]/[1] for whether RA/Dec specifically
            # is actually being corrected (see docs/control.md)
            "pec_active": self._pec_active,

            # seconds since the last real 518 telemetry -- large value means this entry landed
            # in a telemetry gap
            "age_518": round(float(self.polaris._age_518_seconds), 3),
        }
        self.logger.info(f"PECLOG {payload}")


    def step_pec_drift(self):
        """
        Advance the PEC drift correction by one control tick (called every tick from the PID's control step). While
        tracking with PEC Drift Correction on (and no worm profile test), this tick's step of the drift rate is:
        1. folded into the present value (q_syncguide_B, via accumulate_sync_guiding_residuals), so the loop's
            notion of "on target" advances with the drift -- this is what stops Ki from seeing a sustained error and
            rejecting the correction over time;
        2. published as the feed-forward rate omega_pec_B, which feed_forward() solves through the Jacobian into
            motor rates, so the mount moves with the drift instead of waiting for the error.
        Otherwise omega_pec_B is zero: a step outside TRACK would move the PV with no motion to match.
        delta_sp/delta_ref are never touched — sidereal target identity is preserved.
        """
        self.omega_pec_B = np.zeros(3, dtype=float)   # deg/sec, Base frame — read by feed_forward()

        pid = getattr(self.polaris, '_pid', None)
        if not Config.advanced_pec_drift or getattr(pid, 'mode', None) != 'TRACK' or self.worm_test is not None:
            return
        if not getattr(self, '_pec_active', False):
            return
        if self.equatorial_axes_B[0] is None:
            return

        now = time.monotonic()
        if self._pec_last_apply is None or self._pec_t0 is None:
            self._pec_last_apply = now
            return
        t  = now - self._pec_t0
        dt = now - self._pec_last_apply
        self._pec_last_apply = now
        if dt <= 0 or dt > 5.0:
            return

        cap = self._pec_max_step
        d_ra,  ra_applied  = self._pec_ra.eval_correction(t, dt, cap)
        d_dec, dec_applied = self._pec_dec.eval_correction(t, dt, cap)

        if ra_applied or dec_applied:
            self._pec_guide_last_time = now
            # apply as correction to PV
            self.accumulate_sync_guiding_residuals(d_ra, d_dec)
            # apply as correction to omega_pec feed forward
            ra_axis_B, dec_axis_B, _ = self.equatorial_axes_B
            self.omega_pec_B = (d_ra/dt) * ra_axis_B + (d_dec/dt) * dec_axis_B


class PecInhibit(IntEnum):
    IDLE         = 0
    VALID        = 1
    TOO_FEW_OBS  = 2
    NOT_CONVERGED = 3
    HIGH_RMSE    = 4
    LOW_R2       = 5

class PecAxis:
    """
    One axis's drift model: an exponential moving average of the observed drift rate.

    Each guide update adds its residual to the running total of drift (y); the rate observed since the previous
    update, (y - y_last) / dt, is blended into the smoothed rate with weight alpha = 1 - exp(-dt / tau), computed
    from that axis's own dt, so RA and Dec (which may update on different schedules under pulse guiding) each track
    correctly. Fit quality (R2, rmse) compares each update with the rate predicted from the previous one.
    """

    def __init__(self, tau=7.5*60, min_dt=0.05):
        self.tau    = tau        # smoothing time constant, seconds
        self.min_dt = min_dt     # ignore updates arriving sooner than this since this axis's own last update

        self.rate    = 0.0       # deg/sec -- the smoothed drift rate
        self._y_last = None
        self.lam     = 1.0       # exp(-dt / tau) at the last ingest; alpha = 1 - lam

        # fit-quality state
        self.sse = 0.0
        self.var = 0.0
        self.r2  = 0.0
        self.inhibit = PecInhibit.IDLE

        self._t_last = 0.0
        self._ref    = 0.0
        self._accum  = 0.0
        self._applied_accum = 0.0
        self._applied_rate  = 0.0   # last applied instantaneous rate, deg/s -- for status reporting

    def reset(self):
        """Full reset -- preserves configuration (tau/min_dt), clears the rate and fit state."""
        self.__init__(tau=self.tau, min_dt=self.min_dt)

    def reset_seed(self, accum_deg=0.0):
        """Set the reference point at t=0."""
        self._accum  = accum_deg
        self._ref    = accum_deg
        self._applied_accum = 0.0
        self._y_last = None
        self._t_last = 0.0

    # ── primary methods ─────────────────────────────────────────────────────────
    def ingest(self, resid_deg, t, var_alpha, sse_alpha):
        """
        Ingest a new guide residual and update the model.
        resid_deg: guide residual for this axis in degrees.
        t: seconds since session start.
        """
        self._accum += resid_deg + self._applied_accum
        self._applied_accum = 0.0
        self._update(self._accum - self._ref, t, var_alpha, sse_alpha)

    def ingest_accum(self, accum_deg, t, var_alpha, sse_alpha):
        """Direct accum ingestion for notebook replay -- bypasses delta accounting."""
        self._accum = accum_deg
        self._update(self._accum - self._ref, t, var_alpha, sse_alpha)

    def _update(self, y, t, var_alpha, sse_alpha):
        dt = t - self._t_last
        if dt < self.min_dt:
            return    # too soon since this axis's own last update -- skip rather than corrupt the fit
        self.lam = math.exp(-dt / self.tau)

        y_pred = (self._y_last + self.rate * dt) if self._y_last is not None else y
        err    = y - y_pred
        self.var = var_alpha * y * y     + (1 - var_alpha) * self.var
        self.sse = sse_alpha * err * err + (1 - sse_alpha) * self.sse
        self.r2  = 1.0 - self.sse / self.var if self.var > 1e-10 else 0.0

        if self._y_last is not None:
            alpha    = 1.0 - self.lam
            rate_obs = (y - self._y_last) / dt
            self.rate = alpha * rate_obs + (1 - alpha) * self.rate
        self._y_last = y
        self._t_last = t

    # ── outputs ────────────────────────────────────────────────────────────────
    @property
    def theta(self):
        """Smoothed drift rate as of the most recent ingest, deg/sec -- for logging/reporting."""
        return self.rate

    def predicted_rate(self, t):
        """Rate to apply at time t, deg/sec (EMA: the smoothed rate, whatever t)."""
        return self.rate

    def predicted_accum(self, t):
        """Predicted cumulative correction at t -- for comparing against raw cumul."""
        if self._y_last is None:
            return self._ref
        return self._y_last + self.rate * (t - self._t_last) + self._ref

    def eval_correction(self, t, dt, cap):
        """
        Compute and accumulate a PEC correction step over time span dt.
        Returns (d, correction_was_applied). d is in degrees.
        """
        if not self.converged():
            return 0.0, False
        rate = self.predicted_rate(t)
        self._applied_rate = rate
        d = max(-cap, min(cap, rate * dt))
        if abs(d) < 1e-7:
            return 0.0, False
        self._applied_accum += d
        return d, True

    def eval_inhibit(self, n, min_obs, max_rmse, min_r2=0.5, var_floor=1e-8):
        if n < min_obs:
            self.inhibit = PecInhibit.TOO_FEW_OBS
        elif math.sqrt(self.sse) >= max_rmse:
            self.inhibit = PecInhibit.HIGH_RMSE
        elif self.r2 < min_r2 and self.var > var_floor:   # only trust R2 when there's real signal variance to judge against
            self.inhibit = PecInhibit.LOW_R2
        else:
            self.inhibit = PecInhibit.VALID

    def converged(self):
        return self.inhibit == PecInhibit.VALID

    def rmse_arcmin(self):
        return math.sqrt(self.sse) * 60