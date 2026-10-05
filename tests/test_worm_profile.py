"""
The worm profile test (driver/control_worm.py): all three motors stepped through their worms at once while sidereal
tracking holds the sky, each plate-solve sync recorded as a 2-D pointing error, and one joint fit for every motor.

  * the schedule: 33 positions, each motor its own step and reversal points, within +-6 deg of the start
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
from control_worm import (POSITIONS, PROFILE_TEST, CALIBRATION_HISTORY, POOL_TESTS, SETTLE_HOLD_S, JUMP_ARCSEC,
                          WormProfileTest, WormFeedForward, fit_worm_profile, store_profile_test, pooled_profile,
                          apply_profile, revert_profile, profile_row_fields)

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
def test_schedule_steps_each_motor_its_own_way_within_six_degrees():
    assert POSITIONS.shape == (33, 3) and np.all(POSITIONS[0] == 0)
    assert np.abs(POSITIONS).max() <= 6.0
    steps = np.abs(np.diff(POSITIONS, axis=0))
    assert [round(float(steps[:, m].max()), 3) for m in range(3)] == [0.6, 0.45, 0.375]    # phase rates 36/27/22.5 deg
    turns = lambda m: np.flatnonzero(np.diff(np.sign(np.diff(POSITIONS[:, m])))) + 1
    assert list(turns(0)) == [8, 24] and list(turns(1)) == [12] and list(turns(2)) == [16]  # reversals don't coincide


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
    assert len(test.samples) == 33 and test.samples[1]['direction'] == [1, -1, 1]
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
        assert got['backlash'] == pytest.approx(BACKLASH[m], abs=8.0)      # only loosely determined (not applied)
    assert coef_error(r['motors']['M2']['coef'][2:], TRUE['M2'][2:]) < 3.0     # a significant 2nd harmonic is applied
    assert r['checks']['positions'] == 32 and r['checks']['rms_arcsec'] == pytest.approx(2.0, abs=0.8)


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
def stored(path, n, status='COMPLETED'):
    for k in range(n):
        s = synthetic_test(seed=k)
        r = fit_worm_profile([s])
        r['status'] = status
        store_profile_test(path, s, r, timing={'settle_median_s': 7.0})


def test_tests_are_kept_with_their_samples_up_to_the_history_limit(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    stored(p, CALIBRATION_HISTORY + 2)
    h = json.load(open(p))['calibration_history']
    assert len(h) == CALIBRATION_HISTORY and all(e['test'] == PROFILE_TEST for e in h)
    assert len(h[-1]['samples']) == 33 and h[-1]['status'] == 'COMPLETED' and h[-1]['timing']['settle_median_s'] == 7.0
    assert WormFeedForward.load(p).coef.sum() == 0                     # kept, not applied


def test_the_pooled_profile_uses_the_last_completed_tests(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    stored(p, POOL_TESTS + 2)
    stored(p, 1, status='POOR FIT')
    assert pooled_profile(p)['checks']['tests'] == POOL_TESTS


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


def test_apply_without_a_completed_test_does_nothing(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    assert not apply_profile(p)
    stored(p, 1, status='POOR FIT')
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
    assert f['test_change'].startswith('pooled 3 tests:') and 'rms n32' in f['test_stdev']
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
