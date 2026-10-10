"""
The worm profile test (driver/control_worm.py): all three motors stepped through their worms at once while sidereal
tracking holds the sky, each plate-solve sync recorded as a 2-D pointing error, and one joint fit for every motor.

  * the schedule: 51 positions (50 steps), each motor sweeping ~2.5 worm turns with its own step and reversal points
  * one sync per position once every motor has settled; syncs before settling, or whose error jumps (an exposure that
    caught the move), are discarded
  * the joint fit recovers every motor's worm (1st and 2nd harmonic) and backlash next to an offset, a drift and a
    pointing trend; a pose where M1 and M3 move the field the same way (Roll 0) is a POOR FIT, not a wrong answer;
    several tests pool into one profile
  * the tests are kept in worm_profile.json; approving applies the pooled profile (all motors, on MCU angles) and
    rejecting restores the previous one; the Speed Calibration table has one worm profile row, on M1
"""
import json
import logging
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

from control import CalibrationManager
from control_worm import (POSITIONS, PROFILE_TEST, CALIBRATION_HISTORY, POOL_TESTS, SETTLE_HOLD_S, JUMP_ARCSEC, BACKLASH_DEG,
                          APPROACH_RELEASE_ARCSEC,
                          WormProfileTest, WormFeedForward, fit_worm_profile, store_profile_test, pooled_profile,
                          apply_profile, revert_profile, profile_row_fields, row_status)

WORM = 6.0
TRUE = {'M1': [24.2, 25.3, 3.0, -2.0], 'M2': [-60.0, 0.3, -6.0, -6.0], 'M3': [-40.2, -29.7, 1.0, 1.5]}   # a1 b1 a2 b2
BACKLASH = [8.0, -12.0, 5.0]


def jacobian(separation_deg):
    """Each motor's 2-D effect on the pointing: M2 up, M1 sideways, M3 at separation_deg from M1."""
    s = np.radians(separation_deg)
    return np.array([[0.7, 0.0], [0.0, 1.0], [np.cos(s), np.sin(s)]])


def synthetic_test(seed=0, separation_deg=30.0, noise=2.0, start=(37.2, 21.5, 11.3), drift=(0.15, 0.02, 0.1),
                   true=TRUE, backlash=BACKLASH, offset=(30.0, -20.0)):
    """Samples as the test records them: the schedule plus tracking drift on each motor, res = sum of J_m x (worm +
    backlash moving forward) + offset + a slow drift in time + noise."""
    rng = np.random.default_rng(seed)
    J = jacobian(separation_deg)
    out = []
    for i, pos in enumerate(POSITIONS):
        zeta = np.array(start) + pos + np.array(drift) * i
        d = [0, 0, 0] if i == 0 else [int(x) for x in np.sign(POSITIONS[i] - POSITIONS[i - 1])]
        e = np.zeros(3)
        for m, M in enumerate(('M1', 'M2', 'M3')):
            a1, b1, a2, b2 = true[M]
            ph = 2 * np.pi * zeta[m] / WORM
            e[m] = a1 * np.sin(ph) + b1 * np.cos(ph) + a2 * np.sin(2 * ph) + b2 * np.cos(2 * ph) + backlash[m] * (d[m] > 0)
        res = J.T @ e + np.array(offset) + np.array([0.02, -0.01]) * i ** 1.5 + rng.normal(0, noise, 2)
        out.append({'t': 15.0 * i, 'zeta': zeta.tolist(), 'res': res.tolist(), 'J': J.tolist(),
                    'offset': pos.tolist(), 'direction': d})
    return out


def coef_error(fitted, true):
    return float(np.hypot(fitted[0] - true[0], fitted[1] - true[1]))


# ── schedule ──────────────────────────────────────────────────────────────────────────────────
def test_schedule_sweeps_each_motor_about_two_and_a_half_worm_turns_its_own_way():
    """Real mount 2026-10-06: over ~1.5 worm turns a linear pointing trend mimics much of a worm cycle (M2's terms
    correlated ~0.8 with it; two clean runs gave M2 41" and 100"). 51 positions (50 steps) sweeping ~2.5 turns each separate them."""
    assert POSITIONS.shape == (51, 3) and np.all(POSITIONS[0] == 0)
    assert np.abs(POSITIONS).max() <= 7.5 + 1e-9
    assert all(np.ptp(POSITIONS[:, m]) >= 2.2 * 6.0 for m in range(3))                    # >= ~2.2 worm turns each
    steps = np.abs(np.diff(POSITIONS, axis=0))
    rates = [round(float(steps[:, m].max()) * 60, 2) for m in range(3)]                     # worm phase deg per step
    assert rates == [45.0, 36.0, 33.75]
    assert not {2 * r for r in rates} & set(rates)                                          # no 2nd/1st harmonic alias
    turns = lambda m: set(np.flatnonzero(np.diff(np.sign(np.diff(POSITIONS[:, m])))) + 1)
    assert not (turns(0) & turns(1)) and not (turns(0) & turns(2)) and not (turns(1) & turns(2))


def settle(test, now):
    """The control ticks of a step that settles: every motor within SETTLE_ARCSEC from `now`, held for SETTLE_HOLD_S."""
    test.track_settle(50.0, now)
    test.track_settle(5.0, now + 1.0)
    test.track_settle(4.0, now + 1.0 + SETTLE_HOLD_S)


def test_a_sync_after_the_step_settles_is_kept_and_steps_all_motors_at_once():
    test = WormProfileTest(now=0.0)
    settle(test, 0.0)
    step = test.on_sync({'res': [1.0, 2.0]}, now=5.0)
    assert np.allclose(step, POSITIONS[1] - POSITIONS[0])
    assert test.samples[-1]['direction'] == [0, 0, 0] and test.samples[-1]['settle_s'] is None
    t = 5.0
    while not test.done:
        settle(test, t + 1.0)
        t += 10.0
        test.on_sync({'res': [0.0, 0.0]}, now=t)
        assert test.last_outcome == 'kept'
    assert len(test.samples) == len(POSITIONS) and test.samples[1]['direction'] == [1, -1, 1]
    assert test.samples[1]['settle_s'] == pytest.approx(2.0)
    assert test.on_sync({'res': [0, 0]}, now=t + 10.0) is None


def test_syncs_before_settling_or_jumping_are_discarded():
    test = WormProfileTest(now=0.0)
    settle(test, 0.0)
    test.on_sync({'res': [10.0, 0.0]}, now=5.0)
    assert test.on_sync({'res': [10.0, 0.0]}, now=8.0) is None and test.last_outcome == 'moving'
    settle(test, 9.0)
    assert test.on_sync({'res': [11.0 + JUMP_ARCSEC, 0.0]}, now=15.0) is None and test.last_outcome == 'jump'
    assert test.on_sync({'res': [11.0 + JUMP_ARCSEC, 0.0]}, now=25.0) is not None   # exposed after a settled sync
    assert test.discarded == {'moving': 1, 'jump': 1}



# ── backlash: every position is approached in each motor's tracking direction ────────────────────
TRACK = np.array([-1, -1, 1])                      # the tracking direction of each motor (sign of its rate)


def test_a_step_against_a_motors_tracking_direction_overshoots_then_approaches_with_tracking():
    """Tracking then keeps turning each motor the way it arrived: no backlash to take up after the step (on the real
    mount, ~350" of drift over 25 s after every step that reversed M3)."""
    test = WormProfileTest(now=0.0)
    settle(test, 0.0)
    step = np.asarray(test.on_sync({'res': [0.0, 0.0]}, now=5.0, track_dir=TRACK))
    want = POSITIONS[1] - POSITIONS[0]                                       # M1 +, M2 -, M3 +
    assert np.allclose(step, want + np.array([BACKLASH_DEG, 0.0, 0.0]))      # M1 steps against its tracking (-)
    assert test.settled_at is None
    approach = None
    for t in np.arange(6.0, 9.0, 0.2):                                       # the overshoot settles: approach
        approach = test.track_settle(0.0, now=t) if approach is None else approach
    assert np.allclose(approach, [-BACKLASH_DEG, 0.0, 0.0]) and test.settled_at is None
    for t in np.arange(9.0, 12.0, 0.2):
        assert test.track_settle(0.0, now=t) is None
    assert test.settled_at is not None                                       # settled only after the approach
    test.on_sync({'res': [0.0, 0.0]}, now=20.0, track_dir=TRACK)
    assert test.samples[-1]['direction'] == [-1, -1, 1]                      # every motor arrived as it tracks


def test_the_approach_starts_once_the_overshoot_is_past_the_backlash_without_waiting_to_settle():
    """The overshoot only has to take up the backlash: the approach starts as soon as every motor is within
    APPROACH_RELEASE_ARCSEC of the overshoot (no hold), well past the position by more than the backlash."""
    assert BACKLASH_DEG * 3600 - APPROACH_RELEASE_ARCSEC > 620                # the most backlash measured on the mount
    test = WormProfileTest(now=0.0)
    settle(test, 0.0)
    test.on_sync({'res': [0.0, 0.0]}, now=5.0, track_dir=TRACK)
    assert test.track_settle(APPROACH_RELEASE_ARCSEC + 1, now=6.0) is None    # still on its way to the overshoot
    approach = test.track_settle(APPROACH_RELEASE_ARCSEC - 1, now=6.1)        # close enough: approach at once
    assert np.allclose(approach, [-BACKLASH_DEG, 0.0, 0.0]) and test.settled_at is None
    assert test.track_settle(5.0, now=6.2) is None and test.settled_at is None  # the final position still holds
    test.track_settle(5.0, now=6.2 + SETTLE_HOLD_S)
    assert test.settled_at is not None


def test_with_every_step_along_the_tracking_direction_there_is_no_approach():
    test = WormProfileTest(now=0.0)
    settle(test, 0.0)
    step = test.on_sync({'res': [0.0, 0.0]}, now=5.0, track_dir=np.sign(POSITIONS[1] - POSITIONS[0]))
    assert np.allclose(step, POSITIONS[1] - POSITIONS[0])
    assert all(test.track_settle(0.0, now=t) is None for t in np.arange(6.0, 9.0, 0.2))
    assert test.settled_at is not None


def test_a_motor_that_is_not_tracking_needs_no_approach():
    test = WormProfileTest(now=0.0)
    settle(test, 0.0)
    step = test.on_sync({'res': [0.0, 0.0]}, now=5.0, track_dir=np.array([0, 0, 0]))
    assert np.allclose(step, POSITIONS[1] - POSITIONS[0])

def test_times_out_and_aborts():
    test = WormProfileTest(now=0.0)
    assert not test.timed_out(59.0) and test.timed_out(61.0)
    settle(test, 0.0)
    test.on_sync({'res': [0, 0]}, now=5.0)
    test.abort('goto')
    test.abort('jog')
    assert test.aborted and test.abort_reason == 'goto' and test.on_sync({'res': [0, 0]}, now=9.0) is None


# ── the fit ───────────────────────────────────────────────────────────────────────────────────
def test_fit_recovers_every_motors_worm_and_backlash():
    r = fit_worm_profile([synthetic_test()])
    assert r['status'] == 'COMPLETED', r['checks']
    for m, M in enumerate(('M1', 'M2', 'M3')):
        got = r['motors'][M]
        assert coef_error(got['coef'][:2], TRUE[M][:2]) < 4.0, (M, got)
        assert got['backlash'] == pytest.approx(BACKLASH[m], abs=12.0)     # loosely determined next to the quadratic
                                                                            # trend (reported only; real tests approach with tracking)
    assert coef_error(r['motors']['M2']['coef'][2:], TRUE['M2'][2:]) < 3.0     # a significant 2nd harmonic is applied
    assert r['checks']['positions'] == len(POSITIONS) - 1 and r['checks']['rms_arcsec'] == pytest.approx(2.0, abs=0.8)


def test_an_insignificant_2nd_harmonic_is_not_applied():
    true = {M: v[:2] + [0.0, 0.0] for M, v in TRUE.items()}
    r = fit_worm_profile([synthetic_test(true=true)])
    for M in ('M1', 'M2', 'M3'):
        if r['motors'][M]['h2_amplitude'] < 3.0 * r['motors'][M]['h2_se']:
            assert r['motors'][M]['coef'][2:] == [0.0, 0.0]


def test_where_m1_and_m3_move_the_field_the_same_way_the_result_is_less_certain_and_flagged():
    good = fit_worm_profile([synthetic_test(separation_deg=30.0)])
    same = fit_worm_profile([synthetic_test(separation_deg=0.0)])
    assert same['checks']['separation_deg'] == [0.0, 0.0] and good['checks']['separation_deg'][0] == pytest.approx(30.0)
    assert same['motors']['M1']['se'] > good['motors']['M1']['se']
    for M in ('M1', 'M3'):                                  # the staggered steps still separate them, less precisely
        assert coef_error(same['motors'][M]['coef'][:2], TRUE[M][:2]) < 8.0
    assert '⚠ low separation' in profile_row_fields(same, same, None)['test_change']
    assert 'low separation' not in profile_row_fields(good, good, None)['test_change']


def test_too_few_positions_is_no_data():
    assert fit_worm_profile([synthetic_test()[:10]])['status'] == 'NO DATA'
    assert fit_worm_profile([])['status'] == 'NO DATA'


def test_several_tests_pool_with_their_own_offset_and_drift():
    tests = [synthetic_test(seed=k, start=(37.2 + 7 * k, 21.5 - 3 * k, 11.3 + 2 * k), offset=(30.0 * k, -20.0 + 15 * k))
             for k in range(3)]
    one, pooled = fit_worm_profile(tests[:1]), fit_worm_profile(tests)
    assert pooled['checks']['tests'] == 3 and pooled['status'] == 'COMPLETED'
    for M in ('M1', 'M2', 'M3'):
        assert pooled['motors'][M]['se'] < one['motors'][M]['se']
        assert coef_error(pooled['motors'][M]['coef'][:2], TRUE[M][:2]) < 3.0


# ── the profile file ──────────────────────────────────────────────────────────────────────────
def stored(path, n, status='COMPLETED', noise=2.0):
    for k in range(n):
        s = synthetic_test(seed=k, noise=noise)
        r = fit_worm_profile([s])
        r['status'] = status
        store_profile_test(path, s, r, timing={'settle_median_s': 7.0})


def test_tests_are_kept_with_their_samples_up_to_the_history_limit(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    stored(p, CALIBRATION_HISTORY + 2)
    h = json.load(open(p))['calibration_history']
    assert len(h) == CALIBRATION_HISTORY and all(e['test'] == PROFILE_TEST for e in h)
    assert len(h[-1]['samples']) == len(POSITIONS) and h[-1]['status'] == 'COMPLETED' and h[-1]['timing']['settle_median_s'] == 7.0
    assert WormFeedForward.load(p).coef.sum() == 0                     # kept, not applied


def test_the_pooled_profile_uses_the_last_tests_with_a_clean_fit(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    stored(p, POOL_TESTS + 2)
    assert pooled_profile(p)['checks']['tests'] == POOL_TESTS


def test_tests_too_uncertain_on_their_own_pool_but_a_bad_fit_does_not(tmp_path):
    """Real mount 2026-10-06: a clean test (12" rms) was POOR FIT on significance alone (3.3 sigma) -- pooled with a
    few more it passes; tests spoiled by backlash take-up (33" rms) must stay out."""
    p = str(tmp_path / 'worm_profile.json')
    stored(p, 2, status='POOR FIT')                           # clean fits (synthetic, ~2" rms), each short of 4 sigma
    stored(p, 1, status='POOR FIT', noise=60.0)               # a bad fit: residual well above POOL_MAX_RMS_ARCSEC
    pooled = pooled_profile(p)
    assert pooled['checks']['tests'] == 2 and pooled['status'] == 'COMPLETED'


def test_the_row_shows_completed_when_the_pooled_profile_passes():
    assert row_status({'status': 'POOR FIT'}, {'status': 'COMPLETED', 'motors': {'M1': {}}}) == 'COMPLETED'
    assert row_status({'status': 'POOR FIT'}, {'status': 'NO DATA', 'motors': {}}) == 'POOR FIT'
    assert row_status({'status': 'COMPLETED'}, {'status': 'POOR FIT', 'motors': {'M1': {}}}) == 'COMPLETED'


def test_approve_applies_the_pooled_profile_on_mcu_angles_and_reject_restores(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=np.full((3, 2), 5.0), meta={'learnt_from': ['x']}).save(p)
    stored(p, 2)
    assert apply_profile(p)
    ff = WormFeedForward.load(p)
    assert ff.harmonics == (1, 2) and ff.angle_reference == {'M1': 'zeta', 'M2': 'zeta', 'M3': 'zeta'}
    assert coef_error(ff.coef[1][:2], TRUE['M2'][:2]) < 4.0 and ff.meta['applied_profile']['tests'] == 2
    assert apply_profile(p)                                            # approving again keeps the original to restore
    assert revert_profile(p)
    ff = WormFeedForward.load(p)
    assert ff.harmonics == (1,) and np.allclose(ff.coef, 5.0) and ff.angle_reference == {}
    assert ff.meta['learnt_from'] == ['x'] and len(ff.meta['calibration_history']) == 2
    assert not revert_profile(p)


def test_apply_without_a_clean_test_does_nothing(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    assert not apply_profile(p)
    stored(p, 1, status='POOR FIT', noise=60.0)              # a bad fit doesn't pool
    assert not apply_profile(p)


def test_zeta_referenced_motors_are_evaluated_on_mcu_angles():
    ff = WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=np.array([[36.0, 0.0], [0, 0], [0, 0]]),
                         angle_reference={'M1': 'zeta'})
    theta = np.array([100.0 + 1.5, 20.0, 30.0])                       # 518 angle = MCU angle 1.5 + offset 100
    assert ff.error_deg(theta, zeta_offset=[100.0, 0.0, 0.0])[0] * 3600 == pytest.approx(36.0)   # sin(90 deg)
    assert ff.error_deg(theta)[0] == 0.0                               # no offset known yet: left out


# ── the Speed Calibration row ─────────────────────────────────────────────────────────────────
def table():
    cm = CalibrationManager(False)
    cm.createTestDataFromBaseline()
    cm.ensureWormProfileRow()
    return cm


def test_one_worm_profile_row_on_m1_first_in_the_table():
    cm = table()
    assert list(cm.test_data)[0] == PROFILE_TEST and cm.test_data[PROFILE_TEST]['axis'] == 0
    assert cm.test_data[PROFILE_TEST]['raw'] == '50 steps, approx 15 min'      # Raw Command column
    assert not any(k.endswith('-WORM-GEAR') for k in cm.test_data)


def test_the_per_motor_rows_of_earlier_versions_are_dropped(tmp_path):
    cm = table()
    for a in range(3):
        cm.test_data[f'M{a + 1}-WORM-GEAR'] = dict(name=f'M{a + 1}-WORM-GEAR', axis=a, raw=0, ascom=0.0, dps=0.0,
                                                    test_result='', test_change='', test_stdev='', test_status='APPROVED')
    del cm.test_data[PROFILE_TEST]
    cm.saveTestDataToFile(tmp_path / 't.json')
    cm2 = CalibrationManager(False)
    cm2.loadTestDataFromFile(tmp_path / 't.json')
    cm2.ensureWormProfileRow()
    assert list(cm2.test_data)[0] == PROFILE_TEST and not any(k.endswith('-WORM-GEAR') for k in cm2.test_data)


def test_speed_runs_never_include_the_worm_profile_row():
    cm = table()
    assert 0 not in cm.pendingTests(0, []) and cm.test_data[PROFILE_TEST]['test_status'] == 'UNTESTED'
    assert not cm.pendingWormProfileTest([]) and not cm.pendingWormProfileTest(['M1-SLOW-1.0'])
    assert cm.pendingWormProfileTest([PROFILE_TEST]) and cm.test_data[PROFILE_TEST]['test_status'] == 'PENDING'


def test_approval_calls_back_and_is_left_out_of_the_speed_calibration():
    cm = table()
    calls = []
    cm.on_worm_profile_approval = lambda approved: calls.append(approved) or True
    cm.addWormProfileResult({'test_result': 'M1 36"@263 M2 63"@283 M3 116"@212', 'dps': 0.0}, 'COMPLETED')
    cm.toggleApproval(0, [PROFILE_TEST])
    assert cm.test_data[PROFILE_TEST]['test_status'] == 'APPROVED' and calls == [True]
    cm.generateCalibrationFromBaselineAndTestData()                  # text result: must not be parsed as a speed
    cm.toggleApproval(0, [PROFILE_TEST])
    assert cm.test_data[PROFILE_TEST]['test_status'] == 'REJECTED' and calls == [True, False]
    cm.on_worm_profile_approval = lambda approved: False
    cm.toggleApproval(0, [PROFILE_TEST])
    assert cm.test_data[PROFILE_TEST]['test_status'] == 'REJECTED'   # couldn't be applied: unchanged


def test_the_row_shows_the_pooled_profile_and_what_applying_it_changes():
    latest = fit_worm_profile([synthetic_test()])
    pooled = fit_worm_profile([synthetic_test(seed=k) for k in range(3)])
    f = profile_row_fields(latest, pooled, None)
    assert f['test_result'].startswith('M1 ') and ' M3 ' in f['test_result'] and '"@' in f['test_result']
    assert f['test_change'].startswith('pooled 3 tests:') and 'rms n50' in f['test_stdev']
    bad = dict(latest, status='POOR FIT')
    assert '⚠' in profile_row_fields(bad, pooled, None)['test_change']


def test_every_row_stays_in_the_last_150_messages_through_a_worm_profile_test(monkeypatch):
    """Pilot builds the Speed Calibration table from the last 150 'cm' messages (driver backlog and its own store), so
    every update publishes the whole table: the test's progress updates must not push the other rows out."""
    sent = []
    handler = logging.Handler()
    handler.emit = lambda record: sent.append(record.msg['name'])
    logger = logging.getLogger('cm')
    logger.addHandler(handler)
    monkeypatch.setattr(logger, 'level', logging.INFO)
    try:
        cm = table()
        cm.liveInstance = True                                  # publish on updates (not saved: no results added)
        cm.publishTestData()
        for done in range(100):
            cm.setWormProfileProgress(done % 33, 33)
    finally:
        logger.removeHandler(handler)
    assert set(sent[-150:]) == set(cm.test_data)
    assert sent[-len(cm.test_data):] == list(cm.test_data)      # in table order


def test_a_curved_pointing_error_across_the_test_does_not_leak_into_the_worms():
    """The pointing model's error changes across the test's +-7.5 deg, not only linearly: a quadratic trend absorbs it."""
    rng = np.random.default_rng(5)
    quad = rng.normal(0, 4.0, (2, 3, 3))                                       # "/deg^2: hundreds of " at +-7.5 deg
    s = synthetic_test(seed=3)
    for x in s:
        o = np.asarray(x['offset'])
        x['res'] = list(np.asarray(x['res']) + np.einsum('aij,i,j->a', quad, o, o))
    r = fit_worm_profile([s])
    for M in ('M1', 'M2', 'M3'):
        assert coef_error(r['motors'][M]['coef'][:2], TRUE[M][:2]) < 6.0, (M, r['motors'][M])


# ── per-motor acceptance ─────────────────────────────────────────────────────────────────────
SMALL_M1 = dict(TRUE, M1=[1.0, -1.0, 0.0, 0.0])         # a worm too small to measure on M1


def test_a_motor_too_small_to_measure_is_left_uncorrected_and_the_others_are_applied():
    """Real mount 2026-10-06: M2 and M3 at 15-19 sigma, M1 (~21") at 2.8-3.9: the whole test was POOR FIT. Each motor now
    stands on its own: a significant one is applied, the others are left uncorrected."""
    r = fit_worm_profile([synthetic_test(true=SMALL_M1, noise=8.0)])
    assert r['status'] == 'COMPLETED', r['checks']
    assert not r['motors']['M1']['applied'] and r['motors']['M1']['coef'] == [0.0, 0.0, 0.0, 0.0]
    for M in ('M2', 'M3'):
        assert r['motors'][M]['applied'] and coef_error(r['motors'][M]['coef'][:2], TRUE[M][:2]) < 8.0


def test_a_test_with_no_motor_measured_or_a_poor_residual_is_a_poor_fit():
    nothing = {M: [0.5, 0.5, 0.0, 0.0] for M in ('M1', 'M2', 'M3')}
    assert fit_worm_profile([synthetic_test(true=nothing)])['status'] == 'POOR FIT'
    noisy = fit_worm_profile([synthetic_test(noise=40.0)])                  # rms above POOL_MAX_RMS_ARCSEC
    assert noisy['checks']['rms_arcsec'] > 20.0 and noisy['status'] == 'POOR FIT'


def test_the_row_marks_the_motors_left_uncorrected():
    r = fit_worm_profile([synthetic_test(true=SMALL_M1, noise=8.0)])
    fields = profile_row_fields(r, r, None)
    assert 'M1 off' in fields['test_result'] and 'M2 ' in fields['test_result']


def test_unused_trend_columns_do_not_inflate_the_residual():
    """A narrow test (the 33-position schedule) carries the quadratic trend columns as zeros: they aren't parameters."""
    from control_worm import _legs
    narrow = np.array([_legs(0.6, [(+1, 8), (-1, 16), (+1, 8)]), _legs(0.45, [(-1, 12), (+1, 20)]),
                       _legs(0.375, [(+1, 16), (-1, 16)])]).T
    s = synthetic_test(noise=2.0)[:len(narrow)]
    for x, pos in zip(s, narrow):
        x['offset'] = list(pos)
    assert fit_worm_profile([s])['checks']['rms_arcsec'] == pytest.approx(2.0, abs=0.6)


# ── display: the angle where each motor's wobble peaks ──────────────────────────────────────────
def test_displayed_angle_is_the_worm_phase_of_the_peak():
    """e = a sin(phi) + b cos(phi) = A sin(phi + p): the stored phase p is a shift; users read the angle of the peak."""
    from control_worm import peak_deg
    for a, b in ((30.0, 0.0), (0.0, 30.0), (-20.0, -25.0), (5.0, -40.0)):
        peak = peak_deg(a, b)
        phi = np.radians(np.arange(0, 360, 0.5))
        e = a * np.sin(phi) + b * np.cos(phi)
        assert abs((np.degrees(phi[np.argmax(e)]) - peak + 180) % 360 - 180) < 0.6
        e2 = a * np.sin(2 * phi) + b * np.cos(2 * phi)                          # 2nd harmonic: its first peak
        assert abs((np.degrees(phi[np.argmax(e2[:360])]) - peak_deg(a, b, harmonic=2) + 90) % 180 - 90) < 0.6


def test_the_fit_and_the_row_show_the_peak():
    from control_worm import peak_deg
    r = fit_worm_profile([synthetic_test()])
    v = r['motors']['M3']
    assert v['peak'] == pytest.approx(peak_deg(*v['coef'][:2]), abs=0.1)
    assert f'M3 {v["amplitude"]:.0f}"@{v["peak"]:.0f}' in profile_row_fields(r, r, None)['test_result']


def test_the_profile_file_starts_with_the_profile_in_use_and_ends_with_the_test_history(tmp_path):
    """The applied profile is what a reader opens the file for: at the top, before the (long) test history."""
    p = str(tmp_path / 'worm_profile.json')
    stored(p, 3)
    assert apply_profile(p)
    keys = list(json.load(open(p)))
    assert keys[:6] == ['worm_theta', 'harmonics', 'motors', 'units', 'angle_reference', 'applied_profile']
    assert keys[-1] == 'calibration_history'


def test_the_row_shows_the_profile_in_use_as_its_baseline():
    """Like the speed rows (baseline, test result, change): Baseline = the profile in use, Test Result = the pooled
    profile, Change = how far approving it moves each motor."""
    from control_worm import profile_text
    r = fit_worm_profile([synthetic_test()])
    coef = np.array([r['motors'][M]['coef'] for M in ('M1', 'M2', 'M3')])
    ff = WormFeedForward(worm_theta=6.0, harmonics=(1, 2), coef=coef)
    fields = profile_row_fields(r, r, ff)
    assert fields['dps'] == profile_text(ff) == fields['test_result']        # the pooled profile is the one in use
    assert fields['test_change'].endswith('M1 +0" M2 +0" M3 +0"')
    assert profile_row_fields(r, r, None)['dps'] == 'none'
    off = WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=np.array([[0.0, 0.0], [0.0, -86.2], [-58.8, -61.5]]))
    assert profile_text(off) == 'M1 off M2 86"@180 M3 85"@224'


# ── pooled fits: a looser residual limit than one test ─────────────────────────────────────────

def test_a_pool_of_tests_is_judged_by_the_pooled_limit():
    """2026-10-09: tests 12-16 fitted at 12-18" each, but pooled at 20.2" (between-test differences: seeing, the gravity
    side) -- just over the single-test 20" limit, so Approve found nothing to apply. A pool is judged at 25"."""
    from control_worm import POOL_MAX_RMS_ARCSEC, POOLED_FIT_MAX_RMS_ARCSEC
    noisy = [synthetic_test(seed=s, noise=24.0) for s in (1, 2)]          # fits at ~21.5"
    single = fit_worm_profile([noisy[0]])
    pooled = fit_worm_profile(noisy)
    assert POOL_MAX_RMS_ARCSEC < single['checks']['rms_arcsec'] < POOLED_FIT_MAX_RMS_ARCSEC
    assert single['status'] == 'POOR FIT'
    assert pooled['checks']['rms_arcsec'] < POOLED_FIT_MAX_RMS_ARCSEC and pooled['status'] == 'COMPLETED'
