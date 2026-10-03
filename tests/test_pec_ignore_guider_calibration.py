"""
PEC must not learn a guider's calibration pulses (Config.pec_ignore_guider_calibration).

SyncManager.ingest_pulse_for_pec() runs every pulse through GuiderCalibrationDetector. The
first two calibration pulses are learnt before the run is recognised, so on the third the
PEC model is rolled back to the state before the run -- keeping any PEC correction applied
by the control loop in the meantime. The reference for "no trace" is a SyncManager that was
never shown the calibration pulses (nor the quiet period after it).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import logging
from unittest.mock import patch

import numpy as np
import pytest

from control import SyncManager
from test_sync_manager import Polaris, mock_config          # noqa: F401  (fixture)
from test_pec_detect_guider_calibration import phd2_calibration, ccdciel_calibration, guiding, DIRECTION

GUIDE_RATE_DEG_S = 15.0 / 3600                              # 1x sidereal, as PHD2 is set up


@pytest.fixture
def cfg(mock_config):
    mock_config.advanced_pulse_pec_tuning = True
    mock_config.pec_ignore_guider_calibration = True
    return mock_config


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    c = Clock()
    with patch('control.time.monotonic', c):
        yield c


def new_sm():
    return SyncManager(logging.getLogger('test'), Polaris())


def pulse(sm, clock, t, d, ms):
    clock.t = t
    axis, sign = DIRECTION[d]
    sm.ingest_pulse_for_pec(axis, sign, ms, sign * GUIDE_RATE_DEG_S * ms / 1000)


def feed(sm, clock, pulses):
    for t, d, ms in pulses:
        pulse(sm, clock, t, d, ms)


def pec_state(sm):
    def axis(a):
        return dict(theta=a._theta.copy(), P=a.P.copy(), accum=a._accum, applied=a._applied_accum,
                    ref=a._ref, sse=a.sse, var=a.var, r2=a.r2, t_last=a._t_last, inhibit=a.inhibit)
    return dict(n=sm._pec_n, t0=sm._pec_t0, ra=axis(sm._pec_ra), dec=axis(sm._pec_dec))


def assert_same_pec(a, b):
    sa, sb = pec_state(a), pec_state(b)
    assert sa['n'] == sb['n']
    assert sa['t0'] == sb['t0']
    for ax in ('ra', 'dec'):
        for k in sa[ax]:
            np.testing.assert_allclose(sa[ax][k], sb[ax][k], rtol=1e-9, atol=1e-15, err_msg=f'{ax}.{k}')


def after_quiet(cal, pulses, quiet_sec=20.0):
    """Guide pulses the detector lets through after `cal` (last repeated pulse + quiet_sec)."""
    t_last_repeat = cal[-2][0]
    return [p for p in pulses if p[0] - t_last_repeat > quiet_sec]


# ── behaviour while guiding ──────────────────────────────────────────────

def test_guard_is_transparent_while_guiding(cfg, clock):
    guarded, plain = new_sm(), new_sm()
    pulses = guiding(1000.0, 300)
    feed(guarded, clock, pulses)
    cfg.pec_ignore_guider_calibration = False
    feed(plain, clock, pulses)
    assert guarded._pec_n > 500
    assert_same_pec(guarded, plain)


# ── calibration leaves no trace ──────────────────────────────────────────

@pytest.mark.parametrize("calibration, last_repeat", [(phd2_calibration, -2),       # ends S2500 S2500 S1500
                                                     (ccdciel_calibration, -1)],   # ends with 2 identical S measures
                         ids=['phd2', 'ccdciel'])
def test_calibration_leaves_no_trace_in_the_pec_model(cfg, clock, calibration, last_repeat):
    before = guiding(1000.0, 150)
    cal = calibration(before[-1][0] + 3.0)
    after = guiding(cal[-1][0] + 2.0, 150)

    guarded, reference = new_sm(), new_sm()
    feed(guarded, clock, before + cal + after)
    t_last_repeat = cal[last_repeat][0]
    feed(reference, clock, before + [p for p in after if p[0] - t_last_repeat > 20.0])
    assert_same_pec(guarded, reference)


@pytest.mark.parametrize("model, min_shift", [({'pec_mode': 'rls', 'pec_n_harmonics': 2, 'pec_tau_sec': 1260}, 50),
                                              ({'pec_mode': 'ema', 'pec_n_harmonics': 0, 'pec_tau_sec': 450}, 5)],
                         ids=['rls_h2_as_on_2026-09-29', 'ema_default'])
def test_without_the_guard_the_calibration_steps_are_learnt_as_drift(cfg, clock, model, min_shift):
    for k, v in model.items():
        setattr(cfg, k, v)
    # documents the 2026-09-29 18:55 failure: by the end of PHD2's West steps PEC had fitted
    # them as RA drift (-785 arcmin/hr) and was applying it while guiding resumed.
    # PEC is reset by the goto, so calibration usually follows only a short guiding history.
    before = guiding(1000.0, 20)
    west_steps = [p for p in phd2_calibration(before[-1][0] + 3.0) if p[1] == 'W']
    guarded, unguarded, reference = new_sm(), new_sm(), new_sm()
    feed(guarded, clock, before + west_steps)
    feed(reference, clock, before)
    cfg.pec_ignore_guider_calibration = False
    feed(unguarded, clock, before + west_steps)

    ARCMIN_PER_HOUR = 3600 * 60
    shift = (unguarded._pec_ra.dc_rate() - reference._pec_ra.dc_rate()) * ARCMIN_PER_HOUR
    assert shift < -min_shift                # West steps pull the RA rate negative (RLS+H2 ~-100, EMA ~-14 arcmin/hr)
    assert guarded._pec_ra.dc_rate() == reference._pec_ra.dc_rate()


def test_rollback_keeps_pec_correction_applied_during_the_run(cfg, clock):
    # apply_pec_drift_correction() adds to _applied_accum every control tick, also between
    # the calibration pulses; the rollback must not lose those amounts
    before = guiding(1000.0, 150)
    t = before[-1][0]
    guarded, reference = new_sm(), new_sm()
    feed(guarded, clock, before)
    feed(reference, clock, before)

    applied = [1.5e-5, -0.7e-5, 2.2e-5]
    for i, a in enumerate(applied):
        pulse(guarded, clock, t + 1.4 * (i + 1), 'W', 500)
        guarded._pec_ra._applied_accum += a
    reference._pec_ra._applied_accum += sum(applied)

    clock.t = t + 30.0
    assert_same_pec(guarded, reference)


def test_calibration_before_pec_is_seeded_leaves_pec_unseeded(cfg, clock):
    cal = phd2_calibration(1000.0)
    after = guiding(cal[-1][0] + 2.0, 100)
    guarded, reference = new_sm(), new_sm()

    feed(guarded, clock, cal)
    assert guarded._pec_n == 0
    assert guarded._pec_t0 is None

    feed(guarded, clock, after)
    feed(reference, clock, after_quiet(cal, after))
    assert_same_pec(guarded, reference)


# ── snapshot invalidation ────────────────────────────────────────────────

def test_pec_reset_during_a_run_is_not_undone_by_the_rollback(cfg, clock):
    before = guiding(1000.0, 100)
    t = before[-1][0]
    sm = new_sm()
    feed(sm, clock, before)
    pulse(sm, clock, t + 1.4, 'W', 500)
    pulse(sm, clock, t + 2.8, 'W', 500)
    sm.reset_pec_model()                         # e.g. goto: the old model must stay discarded
    after_reset = pec_state(sm)
    pulse(sm, clock, t + 4.2, 'W', 500)          # triggers detection
    assert pec_state(sm)['n'] == after_reset['n'] == 0
    assert sm._pec_t0 is None


def test_other_pec_ingest_during_a_run_skips_the_rollback_but_still_suppresses(cfg, clock):
    before = guiding(1000.0, 100)
    t = before[-1][0]
    sm = new_sm()
    feed(sm, clock, before)
    pulse(sm, clock, t + 1.4, 'W', 500)
    clock.t = t + 2.0
    sm.update_pec_model(1e-5, -1e-5)             # sync-guide ingest: the snapshot no longer applies
    pulse(sm, clock, t + 2.8, 'W', 500)
    n_before_trigger = sm._pec_n
    pulse(sm, clock, t + 4.2, 'W', 500)          # triggers detection
    assert sm._pec_n == n_before_trigger         # not rolled back ...
    pulse(sm, clock, t + 5.6, 'W', 500)
    assert sm._pec_n == n_before_trigger         # ... but further calibration pulses are ignored


# ── wiring ───────────────────────────────────────────────────────────────

def test_process_pulse_guide_axis_feeds_pec_through_the_guard(cfg, clock):
    p = Polaris()
    p._guideraterightascension = GUIDE_RATE_DEG_S
    p._guideratedeclination = GUIDE_RATE_DEG_S
    p.altaz2radec = lambda alt, az: (0.0, 0.0)
    sm = SyncManager(logging.getLogger('test'), p)
    p._sm = sm
    with patch.object(sm, 'ingest_pulse_for_pec') as ingest:
        clock.t = 1000.0
        sm.process_pulse_guide_axis(3, 500)      # ASCOM West
    ingest.assert_called_once()
    axis, sign, ms, angle = ingest.call_args.args
    assert (axis, sign, ms) == (0, -1, 500)
    assert angle == pytest.approx(-GUIDE_RATE_DEG_S * 0.5)


def test_pulse_pec_tuning_off_learns_nothing(cfg, clock):
    cfg.advanced_pulse_pec_tuning = False
    p = Polaris()
    p._guideraterightascension = GUIDE_RATE_DEG_S
    p._guideratedeclination = GUIDE_RATE_DEG_S
    p.altaz2radec = lambda alt, az: (0.0, 0.0)
    sm = SyncManager(logging.getLogger('test'), p)
    p._sm = sm
    with patch.object(sm, 'ingest_pulse_for_pec') as ingest:
        sm.process_pulse_guide_axis(3, 500)
    ingest.assert_not_called()
