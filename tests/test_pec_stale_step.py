"""
PEC drift (driver/control_pec.PecAxis) when guide updates stop, and when one residual is far outside the prediction:

  * no update for longer than PEC_STALE_FACTOR x the recent interval (at least PEC_STALE_MIN_S): the rate stops being
    applied until the next one (2026-10-17: PHD2 stopped, -12.8"/min applied for 12.6 min, -161" on RA)
  * a residual far outside the prediction is a step, folded in without moving the rate (2026-10-17 23:27: a +165" Dec
    sync then -185", the rate driven to +22"/min); a run of them is a real change of drift, learned
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import pytest

from control_pec import PecAxis, PEC_STALE_MIN_S, PEC_STALE_FACTOR, PEC_STEP_MAX_RUN

AS = 1 / 3600.0                   # deg per arcsec
RATE = 3.0 / 60 * AS              # 3"/min, deg/s
SYNC_S = 130.0                    # a sync after each 2 min sub


def synced(n=12, noise=(0.4, -0.3, 0.2, -0.5, 0.3, -0.2)):
    """An axis fed n syncs SYNC_S apart of a 3"/min drift (plus a little scatter), converged."""
    ax = PecAxis(tau=450.0)
    ax.reset_seed()
    t = 0.0
    for k in range(n):
        t += SYNC_S
        ax.ingest(RATE * SYNC_S + noise[k % len(noise)] * AS, t, 0.05, 0.15)
        ax.eval_inhibit(k + 2, 3, 6.0 / 60)
    assert ax.converged()
    return ax, t


def test_the_rate_stops_being_applied_once_updates_have_stopped_for_too_long():
    ax, t = synced()
    assert ax.stale_after() == max(PEC_STALE_MIN_S, PEC_STALE_FACTOR * SYNC_S)
    d, applied = ax.eval_correction(t + 200, 0.2, 1.0)                 # a missed sync or two: still applied
    assert applied and d > 0 and not ax.stale
    d, applied = ax.eval_correction(t + ax.stale_after() + 1, 0.2, 1.0)
    assert not applied and d == 0 and ax.stale and ax._applied_rate == 0
    rate = ax.rate
    ax.ingest(RATE * 900 + 0.3 * AS, t + 900, 0.05, 0.15)               # the next update: the gap's drift is real
    assert not ax.last_step and ax.rate == pytest.approx(rate, rel=0.2)  # learned (still ~3"/min), not a step
    assert ax.eval_correction(t + 901, 0.2, 1.0)[1] and not ax.stale


def test_a_residual_far_outside_the_prediction_is_a_step_not_drift():
    ax, t = synced()
    rate = ax.rate
    ax.ingest(RATE * SYNC_S + 165 * AS, t + SYNC_S, 0.05, 0.15)         # a bad solve: +165"
    assert ax.last_step and ax.rate == rate
    ax.ingest(RATE * SYNC_S - 160 * AS, t + 2 * SYNC_S, 0.05, 0.15)     # ... and back
    assert ax.last_step and ax.rate == rate
    ax.ingest(RATE * SYNC_S + 0.2 * AS, t + 3 * SYNC_S, 0.05, 0.15)     # normal again: learned as before
    assert not ax.last_step and ax.rate == pytest.approx(rate, rel=0.05)


def test_a_run_of_large_residuals_is_a_real_change_of_drift_and_learned():
    ax, t = synced()
    rate = ax.rate
    for k in range(PEC_STEP_MAX_RUN + 1):
        ax.ingest(RATE * SYNC_S + 60 * AS, t + (k + 1) * SYNC_S, 0.05, 0.15)   # the drift now ~30"/min faster
    assert not ax.last_step and ax.rate > rate                          # the run's last one is learned


def test_pulse_guiding_scatter_is_not_a_step():
    ax = PecAxis(tau=450.0)
    ax.reset_seed()
    t = 0.0
    for k in range(300):
        t += 2.0
        ax.ingest(RATE * 2 + (0.8 if k % 2 else -0.8) * AS, t, 0.05, 0.15)
        assert not ax.last_step
