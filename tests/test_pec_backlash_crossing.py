"""
PEC Drift Correction pauses its learning while a motor left uncompensated after a goto crosses its gear slack
(BacklashCompensator.crossing_slack, control_pec._pec_crossing_paused; switched with pec_reversal_pause).

Backlash Compensation leaves a motor alone after a goto when it has no settled tracking side (under
ENGAGE_RATE_ARCSEC_S, about to turn, at the edges of the mount's reach): corrections can outpace it, and pushing it
through its slack would fight them. But a motor engaged on its far flank must cross the slack before the output follows
it: the motor turns, the camera doesn't, and the guider sees the sky move. Learnt as drift, that fights the guiding.

nina01 2026-10-18 20:36, RA 21h31 Dec +12 3.5 min before transit: M2 tracking at 0.24"/s, engaged on its far flank by a
centering goto. With plate-solve syncs every 6 s, M2 turned 455" (its 432" slack) while the Dec residual grew to 38",
then collapsed; PEC learnt 50'/h in Dec from it, then pushed ~100" per 2-min sub that each sync took back, for 30 min.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

from config import Config
from control_backlash import BacklashCompensator, CROSSING_WATCH_SEC
from kinematics import azaltroll_to_theta_ik, q_to_azaltroll, theta_to_q
from sim_digital_twin import Twin
from sim_guider import SimPlateSolver, ARCSEC
from test_motion_outcomes import run_goto

SLACK = 0.12                                # M2's measured 432"
HALF = SLACK / 2
SLOW = np.array([10.0, 0.24, -18.0]) / ARCSEC       # M2 at 0.24"/s: uncompensated, no settled side (deg/s)
THETA = np.array([1.0, 44.0, 0.5])


# ── the compensator on its own ────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def comp(monkeypatch):
    for key, value in {'coordinated_speed_control': True, 'advanced_backlash': True, 'backlash_deg': [SLACK] * 3}.items():
        monkeypatch.setattr(Config, key, value, raising=False)
    return BacklashCompensator()


def after_a_goto(comp, m2_lead, now=0.0):
    """A goto ends with M2's output m2_lead (deg, +HALF: engaged the way it tracks, -HALF: its far flank) behind it."""
    comp.update(THETA, SLOW, True, True, now=now)
    comp.output[1] = THETA[1] - m2_lead
    comp.update(THETA, SLOW, True, False, now=now)


def m2_at(comp, d_deg, now):
    """M2 turned d_deg from where the goto left it."""
    comp.update(THETA + [0.0, d_deg, 0.0], SLOW, True, False, now=now)
    return bool(comp.crossing_slack()[1])


def test_a_slow_motor_engaged_on_its_far_flank_is_not_crossing_until_it_turns_into_its_slack(comp):
    after_a_goto(comp, -HALF)
    assert not comp.active[1] and not comp.crossing_slack()[1]      # left alone by BLC, and its output follows it
    assert m2_at(comp, 0.05, 10.0)                                    # tracking turns it into its slack: crossing
    assert m2_at(comp, 0.10, 20.0)
    assert not m2_at(comp, 0.12 + 0.001, 30.0)                        # engaged the way it tracks: done


def test_once_engaged_the_way_it_tracks_it_is_not_watched_again_until_the_next_goto(comp):
    after_a_goto(comp, -HALF)
    m2_at(comp, SLACK + 0.001, 10.0)
    assert not m2_at(comp, SLACK - 0.05, 20.0)                        # a correction backs it into the slack: guiding
    after_a_goto(comp, -HALF, now=30.0)                               # a new goto watches it again
    assert m2_at(comp, 0.05, 40.0)


def test_engaged_the_way_it_tracks_after_the_goto_it_is_never_crossing(comp):
    after_a_goto(comp, +HALF)
    assert not m2_at(comp, -0.05, 10.0)                               # backed into its slack later: ordinary guiding


def test_without_a_goto_a_motor_inside_its_slack_is_not_crossing(comp):
    comp.update(THETA, SLOW, True, False, now=0.0)
    comp.output[1] = THETA[1]                                         # mid-slack, as after hours of slow guiding
    assert not m2_at(comp, 0.01, 10.0) and not m2_at(comp, 0.02, 20.0)


def test_the_watch_ends_after_crossing_watch_sec(comp):
    after_a_goto(comp, -HALF)
    assert m2_at(comp, 0.05, CROSSING_WATCH_SEC - 1)
    assert not m2_at(comp, 0.05, CROSSING_WATCH_SEC + 1)


def test_a_motor_blc_compensates_is_not_reported(comp):
    fast = np.array([10.0, 5.0, -18.0]) / ARCSEC                      # M2 at 5"/s: compensated through the goto
    comp.update(THETA, fast, True, True, now=0.0)
    comp.output[1] = THETA[1]
    comp.update(THETA, fast, True, False, now=0.0)
    assert comp.active[1] and not comp.crossing_slack()[1]            # BLC takes it up and theta_pv allows for it


def test_switched_off_or_not_tracking_nothing_is_reported(comp, monkeypatch):
    after_a_goto(comp, -HALF)
    assert m2_at(comp, 0.05, 10.0)
    comp.update(THETA, SLOW, False, False, now=20.0)
    assert not comp.crossing_slack().any()


# ── on the twin ───────────────────────────────────────────────────────────────────────────────────────────────────
POSE = (1.07, 44.07, 0.5)                   # nina01 2026-10-18 20:36 (the path depends on the pose and the latitude)
CFG = {"coordinated_speed_control": True, "advanced_pec_drift": True, "advanced_sync_guiding": True,
       "advanced_alignment": True, 'advanced_backlash': True, 'backlash_deg': [SLACK] * 3}


class OutputSolver(SimPlateSolver):
    """Plate solves of the camera, which follows the output shafts, against an alignment learnt with each motor
    engaged on `flank`."""
    flank = None

    def encoder_radec(self):
        sm, p = self.tw.polaris._sm, self.tw.polaris
        az, alt, _ = q_to_azaltroll(sm.alignQ_B2T * theta_to_q(*(self.tw.true_theta + self.flank * self.tw.backlash / 2)))
        ra_h, dec = p.altaz2radec(alt, az)
        return ra_h * 15.0, dec


def far_flank_session(monkeypatch, pause=True, drift_dec_arcsec_s=0.0, fast_syncs=25, subs=4, far=True, config=None):
    """A centering goto leaves M2 (0.4"/s here) on its far flank (far) or engaged the way it tracks, where the
    alignment is taken; then syncs every 6 s, then every 2.2 min (subs). Returns (solver, PEC Dec rate after the 6 s
    syncs and its peak in '/h, how many 6 s syncs saw M2 crossing, the Dec error RMS over the subs in ")."""
    tw = Twin(monkeypatch, config={**CFG, 'pec_reversal_pause': pause, **(config or {})}, backlash_deg=SLACK, seed=0)
    tw.place(azaltroll_to_theta_ik(*POSE))
    tw.start_tracking()
    tw.run(30)
    done, _, _ = run_goto(tw, lambda: tw.slew_relative(dec=-2 / 60))
    assert done is not None
    tw.run(1.0)
    flank = np.sign(tw.pid.omega_ff)
    if far:
        flank[1] = -flank[1]
    tw.output = tw.theta - flank * tw.backlash / 2
    tw.pid.backlash.output = np.asarray(tw.polaris._theta_raw, float) - flank * SLACK / 2
    g = OutputSolver(tw, drift=lambda t: (0.0, drift_dec_arcsec_s * t / ARCSEC), interval_s=6.0,
                     solve_noise_arcsec=1.5, seed=0)
    g.flank = flank
    g.start()
    g.lock = (float(tw.pid.delta_sp[0]), float(tw.pid.delta_sp[1]))        # the goto's target
    sm = tw.polaris._sm
    rate = lambda: sm._pec_dec._applied_rate * 60 * 3600
    peak, crossing = 0.0, 0
    for _ in range(fast_syncs):
        g.guide(6.0)
        peak = max(peak, abs(rate()))
        crossing += bool(tw.pid.backlash.crossing_slack()[1])
    after_fast = rate()
    g.frame_s = 132.0
    g._next = tw.clock.t + g.frame_s
    t_subs = tw.clock.t - g.t0
    for _ in range(subs):
        g.guide(132.0)
        peak = max(peak, abs(rate()))
    rms = g.error_rms_arcsec(since_s=t_subs)[1]
    tw.close()
    return g, after_fast, peak, crossing, rms


def test_pec_does_not_learn_the_slack_of_a_motor_left_on_its_far_flank(monkeypatch):
    g, after_fast, peak, crossing, rms = far_flank_session(monkeypatch)
    dec = [f[2] * ARCSEC for f in g.frames]
    assert max(dec[:25]) > 30                                         # the slack shows, as on the night (38")
    assert crossing >= 5                                              # ... while M2 crossed it
    assert peak < 5.0, peak                                           # '/h: not learnt (paused off: ~50'/h)
    assert rms < 8.0, rms                                             # " (paused off: ~45")


@pytest.mark.slow
@pytest.mark.parametrize('drift', [0.0, 0.2, -0.2])
def test_the_pause_turns_the_nights_fight_into_a_learnt_drift(monkeypatch, drift):
    """Paused off this reproduces the night: ~50'/h learnt from the slack, then 100"-a-sub fights with the syncs.
    Paused on, a real drift (0.2"/s = 12'/h) is still learnt once the slack is crossed."""
    results = {}
    for pause in (False, True):
        mp = pytest.MonkeyPatch()
        try:
            _, after_fast, peak, _, rms = far_flank_session(mp, pause=pause, drift_dec_arcsec_s=drift, subs=14)
            results[pause] = (after_fast, peak, rms)
        finally:
            mp.undo()
    assert abs(results[False][0]) > 30, results                       # the bug: the slack learnt as drift
    assert results[True][1] < abs(drift) * 60 + 5, results            # no more than the real drift
    assert results[True][2] < 0.3 * results[False][2], results


def test_engaged_the_way_it_tracks_pec_learns_a_drift_as_before(monkeypatch):
    """The guard: after a goto that leaves every motor engaged the way it tracks, nothing pauses and PEC learns a real
    drift (0.3"/s = 18'/h) just as with the pause switched off."""
    rates = {}
    for pause in (False, True):
        mp = pytest.MonkeyPatch()
        try:
            g, after_fast, _, crossing, _ = far_flank_session(mp, pause=pause, drift_dec_arcsec_s=0.3, far=False)
            rates[pause] = after_fast
            assert crossing == 0
        finally:
            mp.undo()
    assert rates[True] == pytest.approx(rates[False], abs=0.5), rates
    assert abs(rates[True]) > 3.0, rates                               # learning: 150 s into pec_tau_sec's 450 s


def test_the_pause_is_logged_once_and_marked_in_peclog(monkeypatch, caplog):
    caplog.set_level('INFO')
    far_flank_session(monkeypatch, fast_syncs=25, subs=1, config={'log_pec': True})
    msgs = [r.getMessage() for r in caplog.records]
    assert sum('PEC drift learning paused while M2 crosses its gear backlash' in m for m in msgs) == 1, msgs
    assert sum('PEC drift learning resumed (M2 backlash taken up)' in m for m in msgs) == 1
    assert any("'paused': 'M2'" in m for m in msgs if m.startswith('PECLOG'))
