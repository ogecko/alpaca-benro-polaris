# -----------------------------------------------------------------------------
# control_pec.py - PEC and drift modelling for SyncManager
# -----------------------------------------------------------------------------
#
# PecMixin holds SyncManager's PEC methods: guide corrections (sync guiding, or pulse guiding
# when Config.advanced_pulse_pec_tuning) are ingested into a per-axis PecAxis drift model,
# and apply_pec_drift_correction() feeds the predicted rate back every control tick.
#
# Guider calibration
# ------------------
# When PEC learns from pulse guiding, every pulse is treated as a guide correction of drift.
# A guider's calibration (PHD2, CCDciel, ...) is not: it deliberately moves the mount tens of
# pixels in each direction, and PEC learning those pulses fits a large false drift rate
# (2026-09-29 session: RA fit -785 arcmin/hr after a PHD2 calibration, which guiding then had
# to fight at +363"/min).
#
# The driver only sees PulseGuide(direction, duration), so GuiderCalibrationDetector recognises
# calibration by its signature: ONE axis at a time, ONE direction, and either IDENTICAL durations
# (PHD2's steps, backlash clearing and recenters) or a RAMP where each pulse is exactly 1.5x the
# previous one (CCDciel's internal guider grows its East pulse from its "initial calibration step"
# until the star moves; cu_autoguider_internal.pas, durations rounded to whole ms). Guiding sends
# RA and Dec pulses in the same frame with durations computed from the measured error, so neither
# run of `run_length` (3) occurs while guiding: replaying 43,199 PHD2 guide pulses (2026-09-29)
# gave 0 identical runs of 3 (but 59 runs of 2) and one 1.5x ramp of short pulses (79, 118, 176 ms),
# so a ramp only triggers once its pulse reaches `ramp_min_ms` (300); CCDciel's 2,079 guide pulses
# (2026-09-12) gave none.
#
# Because the first run_length-1 calibration pulses are only recognised in hindsight, the
# verdict for the triggering pulse asks the caller to roll back what it learnt since the
# start of the run (run_start marks where to snapshot). Once active, nothing is learnt until
# no repeated (identical or ramp) pulse has been seen for `quiet_sec`. Recenter pulses, backlash
# clearing and the Dec steps all repeat, so the whole calibration stays suppressed (CCDciel's single
# West return pulse arrives a guide frame after the ramp); afterwards only the first `quiet_sec` of
# guiding is skipped.
#
# The detector only ever withholds learning: a missed calibration behaves as before, and a
# false trigger costs `quiet_sec` of PEC observations. Config.pec_ignore_guider_calibration.
# -----------------------------------------------------------------------------

import copy
import math
import time
from dataclasses import dataclass
from enum import IntEnum, Enum

import numpy as np

from config import Config


@dataclass(frozen=True)
class PulseVerdict:
    ingest: bool       # learn from this pulse
    run_start: bool    # this pulse starts a new run -- snapshot state before learning from it
    rollback: bool     # calibration recognised -- undo what was learnt since the run started


class GuiderCalibrationDetector:
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
        self._pec_mode        = PecMode(getattr(Config, 'pec_mode', 'ema'))               # 'ema' (default) or 'rls'
        self._pec_tau         = getattr(Config, 'pec_tau_sec',            7.5*60)           # single smoothing time constant (sec), both modes
        self._pec_min_dt      = getattr(Config, 'pec_min_dt_sec',         0.05)           # ignore an axis update if it arrives sooner than this since that axis's own last update
        self._pec_min_obs     = getattr(Config, 'pec_min_observations',   3)              # inhibit until n > min_obs
        self._pec_max_resid   = getattr(Config, 'pec_max_resid_arcmin',   10.0)  / 60.0   # ignore guide update if resid > max_resid degrees
        self._pec_max_step    = getattr(Config, 'pec_max_step_arcmin',    0.5)   / 60.0   # clamp +/-correction step to max_step degrees every 200ms
        self._pec_max_rmse    = getattr(Config, 'pec_max_rmse_arcmin',    6.0)   / 60.0   # inhibit if rmse > max_rmse degrees
        self._pec_min_r2      = getattr(Config, 'pec_min_r2',             0.5)            # inhibit if bad R2 < 0.5
        self._pec_T_sec       = getattr(Config, 'pec_T_sec',              34*60)          # T: worm period in seconds (default 34 min = 2040s)
        self._pec_n_harmonics = getattr(Config, 'pec_n_harmonics',        0)              # n_harmonics: 0, 1, or 2 (0 = pure linear, RLS mode only)

        self._pec_ra  = PecAxis(T=self._pec_T_sec, n_harmonics=self._pec_n_harmonics,
                                 mode=self._pec_mode, tau=self._pec_tau, min_dt=self._pec_min_dt)
        self._pec_dec = PecAxis(T=self._pec_T_sec, n_harmonics=self._pec_n_harmonics,
                                 mode=self._pec_mode, tau=self._pec_tau, min_dt=self._pec_min_dt)

        self._pec_var_alpha  = 0.05           # EMA factor for var estimate, more stable R2
        self._pec_sse_alpha  = 0.15           # EMA factor for sse estimate, faster tracking decay
        self._pec_active      = False

        if Config.log_pec and getattr(self, '_log_pec_config', True):
            self.logger.info(
                f"PECCONFIG mode,{self._pec_mode.value},n_harmonics,{self._pec_n_harmonics},"
                f"T,{self._pec_T_sec},tau_sec,{self._pec_tau},min_dt_sec,{self._pec_min_dt}"
            )
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
        if not Config.advanced_pec:
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
        pec_accum_ra, pec_accum_dec = pec_accum_snapshot
        # float(): several values below (pv_deg elements, dc_rate()) are numpy scalars, whose
        # numpy-2.x repr (e.g. np.float64(1.23)) breaks ast.literal_eval() on readback.
        # Paired fields are [ra, dec] lists -- matching PIDLOG/KFLOG's axis-indexed convention
        # (there, 1/2/3 = M1/M2/M3; here, 1/2 = ra/dec via the standard "_i+1" flattening).
        # Rounded for readability -- re-derive from PecAxis state directly if you need full
        # precision (e.g. via analyse_pec.ipynb).
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

            # arcmin/hr, PEC Model parameters [DC, harmonic 1, 2, ...]
            "ra_model": [round(float(ra.dc_rate()*ARCMIN_PER_HOUR), 3)] + [round(float(ra.harmonic_rate(h)*ARCMIN_PER_HOUR), 3) for h in range(1, ra.n_harmonics + 1)],
            "dec_model": [round(float(dec.dc_rate()*ARCMIN_PER_HOUR), 3)] + [round(float(dec.harmonic_rate(h)*ARCMIN_PER_HOUR), 3) for h in range(1, dec.n_harmonics + 1)],

            # degrees, current topocentric position
            "az": round(float(pv_deg[0]), 3), "alt": round(float(pv_deg[1]), 3), "roll": round(float(pv_deg[2]), 3),

            # RLS forgetting factor, dimensionless
            "lambda": [round(float(ra.lam), 5), round(float(dec.lam), 5)],

            # ra.converged() or dec.converged() -- gates apply_pec_drift_correction() as a
            # whole, but is not per-axis: check inhibit[0]/[1] for whether RA/Dec specifically
            # is actually being corrected (see docs/control.md)
            "pec_active": self._pec_active,

            # seconds since the last real 518 telemetry -- large value means this entry landed
            # in a telemetry gap
            "age_518": round(float(self.polaris._age_518_seconds), 3),
        }
        self.logger.info(f"PECLOG {payload}")


    def apply_pec_drift_correction(self):
        """
        Called every control tick. Computes the current PEC rate once, then:
        1. Publishes it as omega_pec_B for feed_forward() to solve through the
            Jacobian and add proactively to omega_tgt (minimizes transient/lag).
        2. Injects the same rate into the measurement chain via
            accumulate_sync_guiding_residuals (original design) so the loop's
            notion of "on target" advances in lockstep with the FF-induced
            motion — this is what stops Ki from seeing a sustained error and
            rejecting the correction over time.
        delta_sp/delta_ref are never touched — sidereal target identity is
        preserved exactly as before.
        """
        self.omega_pec_B = np.zeros(3, dtype=float)   # deg/sec, Base frame — read by feed_forward()

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

class PecMode(str, Enum):
    RLS = "rls"
    EMA = "ema"


class PecAxis:
    """
    Two interchangeable drift estimators behind one interface:
      RLS mode: multi-harmonic recursive least squares (n_harmonics=0 -> pure linear)
                Fits: y(t)  = a*t + b1*sin(wt)   + c1*cos(wt)   + b2*sin(2wt)    + c2*cos(2wt) + ...
                      dy/dt = a   + b1*w*cos(wt) - c1*w*sin(wt) + b2*2w*cos(2wt) - c2*2w*sin(2wt) ...
                T: worm period in seconds (default 34 min = 2040s)
      EMA mode: exponential moving average of the observed instantaneous rate, no phase/harmonics

    Both modes share a single smoothing time constant `tau` (seconds):
      lam   = exp(-dt/tau)   — RLS forgetting factor
      alpha = 1 - lam        — EMA smoothing weight
    computed fresh at each ingest from that axis's own dt, so RA and Dec (which may
    update on different schedules under pulse guiding) each track correctly.

    theta            : rate as of the most recent ingest — for logging/reporting.
    predicted_rate(t): rate evaluated at an arbitrary/current time — used by
                        eval_correction() so harmonic phase advances continuously
                        between sparse ingests rather than freezing.
    """

    def __init__(self, T=34*60, n_harmonics=2, mode=PecMode.RLS, tau=21*60, min_dt=0.05):
        self.T           = T
        self.mode        = mode
        self.n_harmonics = n_harmonics if mode == PecMode.RLS else 0   # EMA never uses harmonics
        self.n_params    = 1 + 2 * self.n_harmonics                    # only meaningful in RLS mode

        self.tau    = tau        # single smoothing time constant, seconds — used by both modes
        self.min_dt = min_dt     # ignore updates arriving sooner than this since this axis's own last update

        # RLS state (unused but harmless in EMA mode)
        self._theta = np.zeros(self.n_params)
        self.P      = np.eye(self.n_params)

        # EMA state
        self.rate    = 0.0       # deg/sec — the EMA-tracked rate
        self._y_last = None

        self.lam = 1.0           # last-used lambda; alpha = 1 - lam when needed

        # shared fit-quality state
        self.sse = 0.0
        self.var = 0.0
        self.r2  = 0.0
        self.inhibit = PecInhibit.IDLE

        self._t_last = 0.0
        self._ref    = 0.0
        self._accum  = 0.0
        self._applied_accum = 0.0
        self._applied_rate  = 0.0   # last applied instantaneous rate, deg/s — for status reporting

    def reset(self):
        """Full reset — preserves configuration (mode/tau/min_dt), clears fit/EMA state."""
        self.__init__(T=self.T, n_harmonics=self.n_harmonics, mode=self.mode,
                      tau=self.tau, min_dt=self.min_dt)

    def reset_fit(self):
        """Reset fit statistics but preserve parameter estimates as warm start."""
        self.P   = np.eye(self.n_params)
        self.sse = 0.0
        self.var = 0.0
        self.r2  = 0.0

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
        y  = self._accum - self._ref
        dt = t - self._t_last
        if dt < self.min_dt:
            return    # too soon since this axis's own last update — skip rather than corrupt the fit

        self.lam = math.exp(-dt / self.tau)
        if self.mode == PecMode.RLS:
            self._update_rls(var_alpha, sse_alpha, t, y)
        else:
            self._update_ema(var_alpha, sse_alpha, dt, y)
        self._t_last = t

    def ingest_accum(self, accum_deg, t, var_alpha, sse_alpha):
        """Direct accum ingestion for notebook replay — bypasses delta accounting."""
        self._accum = accum_deg
        y  = self._accum - self._ref
        dt = t - self._t_last
        if dt < self.min_dt:
            return

        self.lam = math.exp(-dt / self.tau)
        if self.mode == PecMode.RLS:
            self._update_rls(var_alpha, sse_alpha, t, y)
        else:
            self._update_ema(var_alpha, sse_alpha, dt, y)
        self._t_last = t

    # ── EMA internals ────────────────────────────────────────────────────────
    def _update_ema(self, var_alpha, sse_alpha, dt, y):
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

    # ── RLS internals ────────────────────────────────────────────────────────
    def _update_rls(self, var_alpha, sse_alpha, t, y):
        phi = self._phi(t)
        err = y - float(phi @ self._theta)

        self.var = var_alpha * y * y     + (1 - var_alpha) * self.var
        self.sse = sse_alpha * err * err + (1 - sse_alpha) * self.sse

        Pp = self.P @ phi
        S  = self.lam + float(phi @ Pp)
        K  = Pp / S

        self._theta += K * err
        self.P       = (self.P - np.outer(K, phi @ self.P)) / self.lam
        self.r2      = 1.0 - self.sse / self.var if self.var > 1e-10 else 0.0

    def _phi(self, t):
        w   = 2 * math.pi / self.T
        phi = np.zeros(self.n_params)
        phi[0] = t
        for h in range(1, self.n_harmonics + 1):
            phi[1 + 2*(h-1)] = math.sin(h * w * t)
            phi[2 + 2*(h-1)] = math.cos(h * w * t)
        return phi

    def _drift_rate(self, t):
        """dy/dt of the full model at time t, in deg/sec."""
        w    = 2 * math.pi / self.T
        rate = self._theta[0]
        for h in range(1, self.n_harmonics + 1):
            i     = 1 + 2 * (h - 1)
            b     = self._theta[i]
            c     = self._theta[i + 1]
            hw    = h * w
            rate += b * hw * math.cos(hw * t) - c * hw * math.sin(hw * t)
        return rate

    # ── primary output ─────────────────────────────────────────────────────────
    @property
    def theta(self):
        """Fitted drift rate as of the most recent ingest, deg/sec — for logging/reporting.
        For real-time application between sparse updates, use predicted_rate(t) instead."""
        return self._drift_rate(self._t_last) if self.mode == PecMode.RLS else self.rate

    # ── secondary outputs ──────────────────────────────────────────────────────
    def dc_rate(self):
        """Steady-state drift rate in deg/sec (linear component, excluding harmonics)."""
        return self._theta[0] if self.mode == PecMode.RLS else self.rate

    def harmonic_rate(self, harmonic=1):
        """Amplitude/Peak contribution rate in deg/sec of the given harmonic (1-indexed)."""
        if self.mode != PecMode.RLS or harmonic < 1 or harmonic > self.n_harmonics:
            return 0.0
        i  = 1 + 2 * (harmonic - 1)
        hw = harmonic * 2 * math.pi / self.T
        return hw * math.sqrt(self._theta[i]**2 + self._theta[i+1]**2)

    def phase(self, harmonic=1):
        """PEC phase in radians of the given harmonic."""
        if self.mode != PecMode.RLS or harmonic < 1 or harmonic > self.n_harmonics:
            return 0.0
        i = 1 + 2 * (harmonic - 1)
        return math.atan2(self._theta[i+1], self._theta[i])

    def predicted_rate(self, t):
        """Instantaneous rate at arbitrary/current t — real-time correction and plotting."""
        return self._drift_rate(t) if self.mode == PecMode.RLS else self.rate

    def predicted_accum(self, t):
        """Predicted cumulative correction at t — for comparing against raw cumul."""
        if self.mode == PecMode.RLS:
            return float(self._phi(t) @ self._theta) + self._ref
        if self._y_last is None:
            return self._ref
        return self._y_last + self.rate * (t - self._t_last) + self._ref

    def eval_correction(self, t, dt, cap):
        """
        Compute and accumulate a PEC correction step over time span dt.
        Evaluated at the actual current time t (via predicted_rate) so harmonic
        phase keeps advancing between sparse guide updates rather than freezing
        at the last ingest.
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