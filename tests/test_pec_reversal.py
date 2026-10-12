"""
PEC Drift Correction pauses its learning while a motor reverses its tracking direction (pec_reversal_pause).

When a motor's tracking rate changes sign, it turns through its gear backlash before the output shaft follows: the
driver measures the motor, so the image drifts by up to the backlash (150-620" measured) while the guider pulls it
back. Learning that as drift spreads it over the next tau (nina01 2026-10-11, SMC: M2 reversed at 21:19, the guide
drift peaked at 134"/min and PEC was still applying 40-60"/min at 21:40, the guider pushing back).

The reversal is found along the target's own sidereal path (the motor angles the tracking reference will pass
through, and has passed through), not from measured rates: deterministic, unaffected by noise, guide pulses or a
driver restart. Learning pauses from pec_reversal_lead_sec before a motor's turning point until the motor has turned
pec_reversal_backlash_deg past it; PEC keeps applying the rate it had learned.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

from config import Config
from control_pec import motor_turning_points, reversal_pauses
from kinematics import azaltroll_to_theta_ik
from sim_digital_twin import Twin

LEAD = 120.0
BACKLASH = 0.2
TIMES = np.arange(-1800.0, LEAD + 300.0 + 1e-9, 30.0)


def path(m2):
    """A sampled path: M1 and M3 turning steadily, M2 given (deg) as a function of t (s)."""
    return np.column_stack([180.0 - 0.005 * TIMES, m2(TIMES), 10.0 + 0.004 * TIMES])


def turning(tc, a=2e-6):
    """M2 turning at tc: a parabola, a deg/s^2 / 2 (the SMC's M2 on 2026-10-11 accelerated ~7e-3 "/s^2 = 2e-6 deg/s^2)."""
    return lambda t: 45.0 + 0.5 * a * (t - tc) ** 2


# ── the turning points ───────────────────────────────────────────────────────────────────────────────────────────
def test_a_turning_point_is_found_where_the_motor_reverses():
    tps = motor_turning_points(TIMES, path(turning(47.0)))
    assert [tp[0] for tp in tps] == [1]
    _, tc, theta_c, accel = tps[0]
    assert abs(tc - 47.0) < 1.0 and abs(theta_c - 45.0) < 1e-6
    assert abs(accel - 2e-6) < 1e-8                           # deg/s^2 at the turn: how fast the slack is crossed


def test_motors_that_keep_turning_one_way_have_no_turning_point():
    assert motor_turning_points(TIMES, path(lambda t: 45.0 + 0.003 * t)) == []


def test_a_stationary_motor_or_numerical_noise_is_not_a_reversal():
    rng = np.random.default_rng(1)
    assert motor_turning_points(TIMES, path(lambda t: 45.0 + 0 * t)) == []
    assert motor_turning_points(TIMES, path(lambda t: 45.0 + rng.normal(0, 1e-8, t.shape))) == []
    # wiggles far below an arcsecond either side are not gear reversals
    assert motor_turning_points(TIMES, path(lambda t: 45.0 + 1e-5 * np.sin(t / 200))) == []


def test_two_motors_reversing_together_are_both_found():
    th = path(turning(-200.0))
    th[:, 0] = 180.0 + 0.5 * 3e-6 * (TIMES - 60.0) ** 2
    assert sorted(tp[0] for tp in motor_turning_points(TIMES, th)) == [0, 1]


def test_motor_angles_are_unwrapped_across_360():
    th = path(lambda t: 45.0 + 0.003 * t)
    th[:, 0] = np.mod(359.9 + 0.005 * TIMES, 360.0)            # M1 crossing 0/360 while turning one way
    assert motor_turning_points(TIMES, th) == []


# ── when learning pauses ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('tc, paused', [
    (600.0, False),     # turns in 10 min: not yet
    (LEAD + 30, False),
    (LEAD - 30, True),  # turns within the lead: the gear is already unloading
    (0.0, True),
    (-60.0, True),      # turned a minute ago: 13" of travel, the slack is not taken up
    (-420.0, True),     # 0.18 deg of travel: almost
    (-480.0, False),    # 0.23 deg past the turning point: the backlash is taken up
])
def test_learning_pauses_from_the_lead_until_the_backlash_is_taken_up(tc, paused):
    pauses = reversal_pauses(TIMES, path(turning(tc)), LEAD, BACKLASH)
    assert bool(pauses) == paused
    if paused:
        assert pauses[0]['motor'] == 1


def test_a_slow_reversal_is_learned_as_drift_not_paused():
    """Taking the slack up over hours (e.g. after a ZM2 roll, chosen to keep M2 nearly still) is a sustained drift
    that PEC should follow; only a reversal that takes it up within REVERSAL_MAX_SEC is a transient to pause for."""
    slow = 2e-9                                               # 0.2 deg in ~4 h
    assert motor_turning_points(TIMES, path(turning(-300.0, slow)))           # still a reversal ...
    assert reversal_pauses(TIMES, path(turning(-300.0, slow)), LEAD, BACKLASH) == []   # ... but not paused for
    assert reversal_pauses(TIMES, path(turning(-300.0, 2e-6)), LEAD, BACKLASH)       # the SMC's took 7.5 min


def test_the_pause_reports_how_far_the_motor_has_turned():
    p = reversal_pauses(TIMES, path(turning(-300.0)), LEAD, BACKLASH)[0]
    assert abs(p['t_turn'] + 300.0) < 1.0
    assert abs(p['travel_deg'] - 0.5 * 2e-6 * 300.0 ** 2) < 1e-3


# ── the driver ───────────────────────────────────────────────────────────────────────────────────────────────────
SMC_TURN = (162.0, 44.0, 12.4)      # the SMC from Sydney on 2026-10-11 at 21:19, when M2 turned (the path depends on the
                                    # pose and the latitude, not the date)
EAST = (100.0, 30.0, 0.0)           # rising in the east: every motor turning one way for hours


def tracking_twin(monkeypatch, pose=SMC_TURN):
    tw = Twin(monkeypatch, config={'advanced_pec_drift': True, 'pec_reversal_pause': True,
                                   'pec_reversal_lead_sec': LEAD, 'pec_reversal_backlash_deg': BACKLASH})
    tw.place(azaltroll_to_theta_ik(*pose))
    tw.start_tracking()
    tw.run(5)
    return tw


def sidereal_path(tw):
    return tw.polaris._sm.pec_sidereal_path(TIMES)


def test_the_tracked_targets_motor_path_matches_where_the_mount_goes(monkeypatch):
    tw = tracking_twin(monkeypatch)
    th = sidereal_path(tw)
    i0 = int(np.argmin(np.abs(TIMES)))
    start = tw.theta.copy()
    tw.run(60)
    predicted = th[i0] + (th[i0 + 2] - th[i0]) * 60 / 60       # 60 s = 2 samples
    assert np.all(np.abs((tw.theta - start) - (predicted - th[i0])) < 3 / 3600), (tw.theta - start, predicted - th[i0])


def test_the_driver_finds_the_m2_reversal_of_the_smc_night(monkeypatch):
    tw = tracking_twin(monkeypatch)
    tps = motor_turning_points(TIMES, sidereal_path(tw))
    assert [tp[0] for tp in tps] == [1], tps
    assert abs(tps[0][1]) < 180                               # within a few minutes of 21:19, as on the night
    assert [p['motor'] for p in tw.polaris._sm.pec_reversal_check(tw.clock.monotonic())] == [1]


def test_tracking_in_the_east_never_pauses(monkeypatch):
    tw = tracking_twin(monkeypatch, EAST)
    assert motor_turning_points(TIMES, sidereal_path(tw)) == []
    assert tw.polaris._sm.pec_reversal_check(tw.clock.monotonic()) == []


def test_the_motor_the_twin_turns_matches_the_path(monkeypatch):
    """Run the twin through the SMC's M2 reversal: the motor really turns where the path said."""
    tw = tracking_twin(monkeypatch, (161.7, 43.7, 13.8))     # about 5 min earlier
    tps = motor_turning_points(TIMES, sidereal_path(tw))
    assert [tp[0] for tp in tps] == [1]
    t_turn = tps[0][1]
    assert 0 < t_turn < LEAD + 300, t_turn
    t0, m2 = tw.clock.t, []
    tw.run(t_turn + 240, on_measure=lambda w: m2.append((w.clock.t - t0, w.theta[1])))
    t, x = np.array(m2).T
    k = np.argmin(x) if x[0] > x[len(x) // 2] else np.argmax(x)
    assert abs(t[k] - t_turn) < 60, (t[k], t_turn)


def test_paused_learning_keeps_the_rate_and_does_not_learn_the_backlash(monkeypatch):
    tw = tracking_twin(monkeypatch, EAST)
    sm = tw.polaris._sm
    for _ in range(10):                                       # learn a steady drift of 6"/min in RA
        sm.update_pec_model(6 / 3600 / 60 * 2, 0.0)
        tw.run(2)
    rate = sm._pec_ra.rate
    assert rate != 0
    monkeypatch.setattr(sm, 'pec_reversal_check', lambda now: [{'motor': 1, 't_turn': -30.0, 'travel_deg': 0.01}])
    sm._pec_reversal_next = 0.0
    for _ in range(10):                                       # the backlash: 2' a minute of guide corrections
        sm.update_pec_model(120 / 3600 / 60 * 2, 0.0)
        tw.run(2)
    assert sm._pec_ra.rate == rate                            # nothing learned
    assert sm._pec_active                                     # and still applied
    monkeypatch.setattr(sm, 'pec_reversal_check', lambda now: [])
    sm._pec_reversal_next = 0.0
    sm.update_pec_model(6 / 3600 / 60 * 2, 0.0)               # resumes: the first residual restarts the differencing
    tw.run(2)
    sm.update_pec_model(6 / 3600 / 60 * 2, 0.0)
    assert abs(sm._pec_ra.rate - rate) < abs(rate) * 0.5      # the 2'/min never reached the rate


def test_the_pause_is_logged_once_with_the_motor(monkeypatch, caplog):
    tw = tracking_twin(monkeypatch, EAST)
    sm = tw.polaris._sm
    monkeypatch.setattr(Config, 'log_pec', True)
    monkeypatch.setattr(sm, 'pec_reversal_check', lambda now: [{'motor': 1, 't_turn': 45.0, 'travel_deg': 0.0}])
    caplog.set_level('INFO')
    for _ in range(5):
        sm._pec_reversal_next = 0.0
        sm.update_pec_model(1e-4, None)
        tw.run(1)
    msgs = [r.getMessage() for r in caplog.records]
    assert sum('PEC drift learning paused' in m and 'M2' in m for m in msgs) == 1
    assert any("'paused': 'M2'" in m for m in msgs if 'PECLOG' in m)
    monkeypatch.setattr(sm, 'pec_reversal_check', lambda now: [])
    sm._pec_reversal_next = 0.0
    sm.update_pec_model(1e-4, None)
    assert any('PEC drift learning resumed' in r.getMessage() for r in caplog.records)


def test_switched_off_it_never_pauses(monkeypatch):
    tw = tracking_twin(monkeypatch)
    monkeypatch.setattr(Config, 'pec_reversal_pause', False)
    sm = tw.polaris._sm
    assert sm.pec_reversal_check(tw.clock.monotonic()) == []


def test_a_new_target_recomputes_the_turning_points(monkeypatch):
    tw = tracking_twin(monkeypatch)
    sm = tw.polaris._sm
    assert [p['motor'] for p in sm.pec_reversal_check(tw.clock.monotonic())] == [1]
    tw.goto_altaz(*EAST[:2])                                  # a goto resets the PEC model, so the cache with it
    for _ in range(300):
        tw.run(1)
        if tw.polaris.goto_complete_at is not None:
            break
    tw.run(5)
    sm.reset_pec_model()
    assert sm.pec_reversal_check(tw.clock.monotonic()) == []


# ── announcing a reversal in the log (whether or not PEC drift or guiding is on) ─────────────────────────────────
def reversal_lines(caplog):
    return [r.getMessage() for r in caplog.records if 'reverses its tracking direction' in r.getMessage()]


def test_an_upcoming_reversal_is_logged_once_with_its_motor(monkeypatch, caplog):
    caplog.set_level('INFO')
    tw = tracking_twin(monkeypatch, (161.7, 43.7, 13.8))     # the SMC, about 5 min before M2 turned
    tw.run(30)
    lines = reversal_lines(caplog)
    assert len(lines) == 1 and 'M2' in lines[0], lines
    tw.polaris._sm._pec_turns = None                          # a refresh moves the estimate a little: still once
    tw.run(60)
    assert len(reversal_lines(caplog)) == 1


def test_a_reversal_is_announced_without_pec_drift(monkeypatch, caplog):
    caplog.set_level('INFO')
    monkeypatch.setattr(Config, 'advanced_pec_drift', False, raising=False)
    tw = Twin(monkeypatch, config={'advanced_pec_drift': False})
    tw.place(azaltroll_to_theta_ik(161.7, 43.7, 13.8))
    tw.start_tracking()
    tw.run(30)
    assert len(reversal_lines(caplog)) == 1


def test_a_reversal_first_seen_after_it_says_how_much_is_left(monkeypatch, caplog):
    """E.g. after a goto onto a target whose motor turned 15 min ago: past tense, and the take-up time left, not the
    whole take-up from the turn (2026-10-12: "reverses its tracking direction 15 min ago ... drift for about 17 min")."""
    caplog.set_level('INFO')
    tw = tracking_twin(monkeypatch, (161.7, 43.7, 13.8))
    sm = tw.polaris._sm
    now = tw.clock.monotonic()
    accel = 2 * BACKLASH / (17 * 60) ** 2                     # takes 17 min to take up the backlash
    monkeypatch.setattr(sm, 'motor_turns', lambda t: [(1, now - 15 * 60, 45.0, accel)])
    sm._reversals_announced, sm._reversal_announce_next = [], 0.0
    sm.announce_motor_reversals(now)
    lines = [r.getMessage() for r in caplog.records if 'tracking direction' in r.getMessage()]
    assert lines and 'M2 reversed its tracking direction 15 min ago' in lines[-1], lines
    assert 'for about 2 more min' in lines[-1], lines


def test_no_reversal_is_announced_tracking_in_the_east(monkeypatch, caplog):
    caplog.set_level('INFO')
    tw = tracking_twin(monkeypatch, EAST)
    tw.run(30)
    assert reversal_lines(caplog) == []


def test_a_new_target_refreshes_the_turning_points(monkeypatch):
    tw = tracking_twin(monkeypatch)                           # the SMC at its M2 turn
    sm = tw.polaris._sm
    assert [t[0] for t in sm.motor_turns(tw.clock.monotonic())] == [1]
    tw.pid.set_alpha_target({'az': EAST[0], 'alt': EAST[1], 'roll': EAST[2]})   # a new target, PEC not reset
    tw.run(0.4)                                               # the tracking reference moves to it
    assert sm.motor_turns(tw.clock.monotonic()) == []
