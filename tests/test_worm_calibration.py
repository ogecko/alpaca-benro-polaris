"""
Tests for the M1-WORM / M2-WORM / M3-WORM calibration (driver/control_worm.py): step one motor through its worm
while sidereal tracking holds the sky, record each plate-solve sync as that motor's angle error, and fit the worm.

  * the schedule: 0.5 deg steps over 2 worm turns forward and back, centred on the starting pointing (+/- 6 deg),
    one step per kept sync: a sync is kept once the step has settled (and its error didn't jump from the last sample:
    an exposure that caught the move), and the motor steps at once
  * the fit recovers amplitude and phase (the shared model: a pure 6 deg sine) next to a slow trend, a per-direction
    offset (backlash) and noise, and reports the checks: 2nd harmonic, best period, phase per direction, backlash
  * the result goes into worm_profile.json for review; approval puts that motor's coefficients into the profile (on
    MCU angles), rejection restores the previous ones
"""
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

from control_worm import (WormCalibration, fit_worm_calibration, store_calibration, apply_calibration,
                              revert_calibration, CALIBRATION_HISTORY, SETTLE_HOLD_S, JUMP_ARCSEC)
from control_worm import WormFeedForward

ARCSEC = 3600.0


# ── schedule ──────────────────────────────────────────────────────────────────────────────────
def test_schedule_steps_two_worm_turns_each_way_centred_on_the_start():
    wc = WormCalibration(axis=1)
    pos = np.array(wc.positions)
    assert pos[0] == 0.0 and pos.max() == pytest.approx(6.0) and pos.min() == pytest.approx(-6.0) and pos[-1] == 0.0
    assert np.allclose(np.abs(np.diff(pos)), 0.5)
    assert len(pos) == 49                                       # 0 -> 6 -> -6 -> 0
    d = np.sign(np.diff(pos))
    assert (d > 0).sum() * 0.5 == pytest.approx(12.0) and (d < 0).sum() * 0.5 == pytest.approx(12.0)


def settle(wc, now):
    """The control ticks of a step that settles: within SETTLE_ARCSEC from `now`, held for SETTLE_HOLD_S."""
    wc.track_settle(50.0, now)
    wc.track_settle(5.0, now + 1.0)
    wc.track_settle(4.0, now + 1.0 + SETTLE_HOLD_S)


def test_a_sync_after_the_step_settles_is_kept_and_steps_at_once():
    wc = WormCalibration(axis=2, step_deg=0.5, turns=1 / 3, now=0.0)     # 0, .5, 1, .5, 0, -.5, -1, -.5, 0
    settle(wc, 0.0)
    assert wc.on_sync({'k': 0}, now=5.0) == pytest.approx(0.5)            # kept, step +0.5
    assert wc.samples[-1]['k'] == 0 and wc.samples[-1]['position'] == 0.0
    assert wc.samples[-1]['settle_s'] is None and wc.samples[-1]['since_settle_s'] == pytest.approx(4.0)
    t = 5.0
    steps = []
    while not wc.done:
        settle(wc, t + 1.0)                                               # settled 2 s after the step
        t += 10.0
        steps.append(wc.on_sync({}, now=t))
        assert wc.last_outcome == 'kept'
    assert len(wc.samples) == len(wc.positions)                          # one sync per position
    assert steps[-1] is None                                             # no step after the last position
    assert [s['direction'] for s in wc.samples] == [0, 1, 1, -1, -1, -1, -1, 1, 1]
    assert wc.samples[1]['settle_s'] == pytest.approx(2.0) and wc.samples[1]['since_settle_s'] == pytest.approx(8.0)
    assert wc.on_sync({}, now=t + 10.0) is None                          # finished: nothing more recorded
    assert len(wc.samples) == len(wc.positions)
    assert wc.timing() == {'settle_median_s': 2.0, 'settle_max_s': 2.0, 'discarded': {'moving': 0, 'jump': 0}}


def test_a_sync_before_the_step_settles_is_discarded():
    wc = WormCalibration(axis=1, now=0.0)
    settle(wc, 0.0)
    assert wc.on_sync({}, now=5.0) == pytest.approx(0.5)
    assert wc.on_sync({}, now=8.0) is None and wc.last_outcome == 'moving'     # still moving: no settle yet
    wc.track_settle(5.0, 9.0)
    assert wc.on_sync({}, now=9.5) is None and wc.last_outcome == 'moving'     # within, but not held long enough
    wc.track_settle(30.0, 9.6)                                           # overshoot: start again
    wc.track_settle(5.0, 10.0)
    wc.track_settle(5.0, 10.0 + SETTLE_HOLD_S)
    assert wc.on_sync({}, now=15.0) == pytest.approx(0.5) and wc.last_outcome == 'kept'
    assert wc.samples[-1]['settle_s'] == pytest.approx(5.0)              # settled at 10.0, stepped at 5.0
    assert wc.discarded == {'moving': 2, 'jump': 0}
    assert len(wc.samples) == 2


def test_a_jump_from_the_last_sample_is_discarded_once_then_the_next_sync_is_kept():
    wc = WormCalibration(axis=1, now=0.0)
    settle(wc, 0.0)
    wc.on_sync({'err_arcsec': 40.0}, now=5.0)
    settle(wc, 6.0)
    assert wc.on_sync({'err_arcsec': 40.0 + JUMP_ARCSEC + 1}, now=12.0) is None and wc.last_outcome == 'jump'
    assert wc.on_sync({'err_arcsec': 40.0 + JUMP_ARCSEC + 1}, now=22.0) == pytest.approx(0.5)   # exposed after a
    assert wc.last_outcome == 'kept' and len(wc.samples) == 2                                    # settled sync: real
    settle(wc, 23.0)
    assert wc.on_sync({'err_arcsec': 380.0}, now=30.0) == pytest.approx(0.5)     # within JUMP_ARCSEC: kept
    assert wc.discarded == {'moving': 0, 'jump': 1}


# ── fit ───────────────────────────────────────────────────────────────────────────────────────
def sweep(A=60.0, phase=100.0, noise=3.0, backlash=0.0, trend=(0.0, 0.0), h2=0.0, worm=6.0, seed=0, start=37.2):
    """Samples of a calibration sweep: MCU angle, error (arcsec), time (s), direction."""
    rng = np.random.default_rng(seed)
    wc = WormCalibration(axis=1)
    pos = np.array(wc.positions)
    angle = start + pos
    t = np.arange(len(pos)) * 20.0
    d = np.r_[0, np.sign(np.diff(pos))]
    phi = 2 * np.pi * angle / worm + np.radians(phase)
    tt = t / t[-1]
    err = (A * np.sin(phi) + A * h2 * np.sin(2 * phi + 1.0) + trend[0] * tt + trend[1] * tt ** 2
           + backlash / 2 * d + rng.normal(0, noise, len(t)))
    return angle, err, t, d


def test_fit_recovers_amplitude_and_phase_with_trend_and_backlash():
    r = fit_worm_calibration(*sweep(A=60.0, phase=100.0, noise=3.0, backlash=20.0, trend=(40.0, -25.0)))
    assert r['amplitude_arcsec'] == pytest.approx(60.0, abs=4.0)
    assert r['phase_deg'] == pytest.approx(100.0, abs=5.0)
    a, b = r['coef']                                            # A sin(phi + p) = a sin phi + b cos phi
    assert np.hypot(a, b) == pytest.approx(r['amplitude_arcsec'], abs=0.01)
    assert np.degrees(np.arctan2(b, a)) % 360 == pytest.approx(r['phase_deg'], abs=0.1)
    c = r['checks']
    assert c['backlash_arcsec'] == pytest.approx(20.0, abs=6.0)
    assert c['rms_arcsec'] == pytest.approx(3.0, abs=1.5)
    assert c['turns'] == pytest.approx(2.0)
    assert c['n'] == 48                                         # the start position (no direction yet) is left out
    assert r['status'] == 'COMPLETED'


def test_checks_confirm_pure_sine_and_six_degree_period():
    c = fit_worm_calibration(*sweep(noise=2.0))['checks']
    assert c['harmonic2_ratio'] < 0.1
    assert c['best_worm_theta'] == pytest.approx(6.0, abs=0.1)
    assert abs(c['phase_split_deg']) < 10                       # forward and reverse passes agree


def test_checks_flag_a_second_harmonic_and_a_different_period():
    c = fit_worm_calibration(*sweep(noise=2.0, h2=0.4))['checks']
    assert c['harmonic2_ratio'] == pytest.approx(0.4, abs=0.08)
    c = fit_worm_calibration(*sweep(noise=2.0, worm=6.67))['checks']
    assert c['best_worm_theta'] == pytest.approx(6.67, abs=0.15)


def test_fit_with_no_worm_or_too_little_data_is_not_completed():
    r = fit_worm_calibration(*sweep(A=0.0, noise=5.0))
    assert r['status'] == 'POOR FIT'
    angle, err, t, d = sweep()
    r = fit_worm_calibration(angle[:6], err[:6], t[:6], d[:6])
    assert r['status'] == 'NO DATA'


# ── storage, approval ─────────────────────────────────────────────────────────────────────────
def shared_profile(path):
    coef = np.zeros((3, 2))
    coef[1], coef[2] = [-12.99, 62.74], [-3.35, -63.99]
    WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=coef, meta={'learnt_from': ['x']}).save(path)


def result(a=10.0, b=50.0):
    return {'status': 'COMPLETED', 'coef': [a, b], 'amplitude_arcsec': float(np.hypot(a, b)),
            'phase_deg': float(np.degrees(np.arctan2(b, a)) % 360), 'checks': {'n': 49},
            'samples': [{'t': 0.0, 'angle': 1.0, 'err_arcsec': 2.0}]}


def test_store_keeps_the_result_for_review_without_changing_the_profile(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    shared_profile(p)
    store_calibration(p, 2, result())
    d = json.load(open(p))
    assert d['calibration']['M3']['coef'] == [10.0, 50.0]
    assert d['calibration']['M3']['samples'][0]['err_arcsec'] == 2.0
    assert d['motors']['M3'] == [-3.35, -63.99]                 # not applied until approved
    assert d['learnt_from'] == ['x']


def test_store_creates_the_profile_file_when_missing(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store_calibration(p, 0, result())
    ff = WormFeedForward.load(p)
    assert ff is not None and np.all(ff.coef == 0)
    assert ff.meta['calibration']['M1']['status'] == 'COMPLETED'


def test_store_keeps_a_history_of_reruns_across_motors(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store_calibration(p, 0, result(1.0, 2.0))
    store_calibration(p, 0, result(3.0, 4.0))
    store_calibration(p, 2, result(5.0, 6.0))
    d = json.load(open(p))
    assert [(h['motor'], h['coef']) for h in d['calibration_history']] == [('M1', [1.0, 2.0]), ('M1', [3.0, 4.0]),
                                                                          ('M3', [5.0, 6.0])]
    assert d['calibration_history'][0]['samples'][0]['err_arcsec'] == 2.0
    assert d['calibration']['M1']['coef'] == [3.0, 4.0]             # the latest per motor is still the one to review


def test_history_keeps_the_last_fifteen_results(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    for i in range(CALIBRATION_HISTORY + 3):
        store_calibration(p, i % 3, result(float(i), 1.0))
    h = json.load(open(p))['calibration_history']
    assert len(h) == CALIBRATION_HISTORY == 15
    assert [x['coef'][0] for x in h] == [float(i) for i in range(3, CALIBRATION_HISTORY + 3)]


def test_history_survives_approval_and_rejection(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    shared_profile(p)
    store_calibration(p, 2, result())
    assert apply_calibration(p, 2) and revert_calibration(p, 2)
    h = WormFeedForward.load(p).meta['calibration_history']
    assert len(h) == 1 and h[0]['motor'] == 'M3' and 'applied' not in h[0]


def test_approve_applies_the_motor_on_mcu_angles_and_reject_restores(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    shared_profile(p)
    store_calibration(p, 2, result(10.0, 50.0))
    assert apply_calibration(p, 2)
    ff = WormFeedForward.load(p)
    assert list(ff.coef[2]) == [10.0, 50.0]
    assert list(ff.coef[1]) == [-12.99, 62.74]
    assert ff.angle_reference == {'M3': 'zeta'}
    assert ff.meta['calibration']['M3']['applied']
    assert revert_calibration(p, 2)
    ff = WormFeedForward.load(p)
    assert list(ff.coef[2]) == [-3.35, -63.99]
    assert ff.angle_reference == {}
    assert not ff.meta['calibration']['M3']['applied']


def test_apply_widens_a_two_harmonic_profile(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    WormFeedForward(worm_theta=6.0, harmonics=(1, 2), coef=np.ones((3, 4))).save(p)
    store_calibration(p, 0, result(3.0, 4.0))
    assert apply_calibration(p, 0)
    ff = WormFeedForward.load(p)
    assert list(ff.coef[0]) == [3.0, 4.0, 0.0, 0.0]
    assert list(ff.coef[1]) == [1.0, 1.0, 1.0, 1.0]


def test_apply_without_a_stored_result_does_nothing(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    shared_profile(p)
    assert not apply_calibration(p, 0)
    assert not revert_calibration(p, 0)


# ── feed-forward on MCU angles ────────────────────────────────────────────────────────────────
def test_zeta_referenced_motor_is_evaluated_on_mcu_angles():
    coef = np.zeros((3, 2))
    coef[0] = [36.0, 0.0]
    ff = WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=coef, angle_reference={'M1': 'zeta'})
    theta = np.array([181.5, 40.0, 0.0])                        # 518 angle carries the session heading (+180)
    offset = [180.0, 0.0, 0.0]                                  # theta_raw - zeta
    assert ff.error_deg(theta, zeta_offset=offset)[0] * ARCSEC == pytest.approx(36.0)    # MCU angle 1.5: sin 90
    assert ff.error_deg(theta)[0] == 0.0                        # offset unknown: not applied
    got = ff.correction_q(theta, zeta_offset=offset)
    from kinematics import theta_to_q
    want = theta_to_q(*(theta + [36.0 / ARCSEC, 0, 0])) * theta_to_q(*theta).inverse
    assert abs(abs((got.inverse * want).normalised.w) - 1) < 1e-12


# ── Speed Calibration rows: M1-WORM-GEAR .. M3-WORM-GEAR ─────────────────────────────────────
from control import CalibrationManager
from control_worm import gear_row_fields, fit_worm_samples, WormCalibration as _WC


def test_every_row_stays_in_the_last_150_messages_through_a_worm_gear_test(monkeypatch):
    """Pilot builds the Speed Calibration table from the last 150 'cm' messages (driver backlog and its own store), so
    every update publishes the whole table: a worm gear test's ~50 progress updates must not push the other rows out
    (M3-WORM-GEAR went missing after the M1 and M2 tests when only the changed row was sent)."""
    import logging
    sent = []
    handler = logging.Handler()
    handler.emit = lambda record: sent.append(record.msg['name'])
    logger = logging.getLogger('cm')
    logger.addHandler(handler)
    monkeypatch.setattr(logger, 'level', logging.INFO)
    try:
        cm = CalibrationManager(False)
        cm.createTestDataFromBaseline()
        cm.liveInstance = True                                  # publish on updates (not saved: no results added)
        cm.publishTestData()
        for axis in (0, 1):
            for done in range(50):
                cm.setWormGearProgress(axis, done, 49)
    finally:
        logger.removeHandler(handler)
    assert set(sent[-150:]) == set(cm.test_data)                # every row, M3-WORM-GEAR included
    assert sent[-len(cm.test_data):] == list(cm.test_data)      # in table order


def test_gear_rows_exist_alongside_the_speed_rows():
    cm = CalibrationManager(False)
    cm.createTestDataFromBaseline()
    for a in range(3):
        row = cm.test_data[f'M{a + 1}-WORM-GEAR']
        assert row['axis'] == a and row['test_status'] == 'UNTESTED' and row['raw'] == 0
    assert list(cm.test_data)[:3] == ['M1-WORM-GEAR', 'M2-WORM-GEAR', 'M3-WORM-GEAR']


def test_gear_rows_are_added_to_test_data_saved_before_they_existed(tmp_path):
    cm = CalibrationManager(False)
    cm.createTestDataFromBaseline()
    for a in range(3):
        del cm.test_data[f'M{a + 1}-WORM-GEAR']
    cm.saveTestDataToFile(tmp_path / 't.json')
    cm2 = CalibrationManager(False)
    cm2.loadTestDataFromFile(tmp_path / 't.json')
    cm2.ensureWormGearRows()
    assert list(cm2.test_data)[:3] == ['M1-WORM-GEAR', 'M2-WORM-GEAR', 'M3-WORM-GEAR']   # top of the table


def test_speed_runs_never_include_the_gear_rows():
    cm = CalibrationManager(False)
    cm.createTestDataFromBaseline()
    rates = cm.pendingTests(1, [])                                   # "all" on M2
    assert 0 not in rates and cm.test_data['M2-WORM-GEAR']['test_status'] == 'UNTESTED'
    rates = cm.pendingTests(1, ['M2-WORM-GEAR', 'M2-SLOW-1.0'])
    assert rates == [1.0] and cm.test_data['M2-WORM-GEAR']['test_status'] == 'UNTESTED'


def test_a_gear_test_is_pending_only_when_its_row_is_selected():
    cm = CalibrationManager(False)
    cm.createTestDataFromBaseline()
    assert not cm.pendingWormGearTest(1, [])
    assert not cm.pendingWormGearTest(1, ['M3-WORM-GEAR', 'M2-SLOW-1.0'])
    assert cm.pendingWormGearTest(1, ['M2-WORM-GEAR', 'M2-SLOW-1.0'])
    assert cm.test_data['M2-WORM-GEAR']['test_status'] == 'PENDING'
    cm.setWormGearProgress(1, 12, 49)
    assert cm.test_data['M2-WORM-GEAR']['test_status'] == 'PENDING 12/49'
    cm.stopTests()
    assert cm.test_data['M2-WORM-GEAR']['test_status'] == 'STOPPED'


def test_gear_result_shows_amplitude_phase_change_and_rms():
    cur = WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=np.array([[0, 0], [-12.99, 62.74], [0, 0]], float))
    r = fit_worm_calibration(*sweep(A=62.0, phase=104.0, noise=3.0))
    r['checks']['sensitivity'] = 0.9
    f = gear_row_fields(r, cur, 1)
    assert f['dps'] == pytest.approx(64.07, abs=0.01)                # baseline: the profile's amplitude now
    assert f['test_result'].startswith(f"{r['amplitude_arcsec']:.1f}\" @ {r['phase_deg']:.1f}")
    assert '/' in f['test_change'] and '⚠' not in f['test_change']
    assert f['test_stdev'].startswith(f"{r['checks']['rms_arcsec']:.1f}\" rms n48")
    assert gear_row_fields(r, None, 1)['test_change'] == 'new'
    assert gear_row_fields(r, cur, 0)['test_change'] == 'new'        # the profile has nothing for M1


def test_gear_result_warns_on_failed_checks():
    r = fit_worm_calibration(*sweep(noise=2.0, h2=0.4))
    r['checks']['sensitivity'] = 0.2
    f = gear_row_fields(r, None, 1)
    assert '⚠' in f['test_change'] and '2nd harm' in f['test_change'] and 'sensitivity' in f['test_change']
    nd = gear_row_fields({'status': 'NO DATA', 'checks': {'n': 3}}, None, 1)
    assert nd['test_result'] == '' and nd['test_stdev'] == 'n3'


def test_gear_approval_calls_back_and_is_left_out_of_the_speed_calibration():
    cm = CalibrationManager(False)
    cm.createTestDataFromBaseline()
    calls = []
    cm.on_worm_gear_approval = lambda axis, approved: calls.append((axis, approved)) or True
    cm.addWormGearResult(1, {'test_result': '62.0" @ 104.0°', 'test_change': 'new', 'test_stdev': '3.0" rms n48',
                             'dps': 0.0}, 'COMPLETED')
    cm.toggleApproval(1, ['M2-WORM-GEAR'])
    assert cm.test_data['M2-WORM-GEAR']['test_status'] == 'APPROVED' and calls == [(1, True)]
    cm.generateCalibrationFromBaselineAndTestData()                  # text result: must not be parsed as a speed
    cm.toggleApproval(1, ['M2-WORM-GEAR'])
    assert cm.test_data['M2-WORM-GEAR']['test_status'] == 'REJECTED' and calls == [(1, True), (1, False)]


def test_gear_approval_that_cannot_be_applied_stays_unapproved():
    cm = CalibrationManager(False)
    cm.createTestDataFromBaseline()
    cm.on_worm_gear_approval = lambda axis, approved: False
    cm.addWormGearResult(0, {'test_result': 'x', 'test_change': '', 'test_stdev': '', 'dps': 0.0}, 'COMPLETED')
    cm.toggleApproval(0, ['M1-WORM-GEAR'])
    assert cm.test_data['M1-WORM-GEAR']['test_status'] == 'COMPLETED'


def test_fit_worm_samples_adds_sensitivity_and_keeps_the_samples():
    angle, err, t, d = sweep()
    samples = [{'angle': a, 'err_arcsec': e, 't': tt, 'direction': int(dd), 'sensitivity': 0.8}
               for a, e, tt, dd in zip(angle, err, t, d)]
    r = fit_worm_samples(samples)
    assert r['status'] == 'COMPLETED' and r['checks']['sensitivity'] == pytest.approx(0.8)
    assert r['samples'] is samples
    assert fit_worm_samples([])['status'] == 'NO DATA'


# ── no syncs, interference ────────────────────────────────────────────────────────────────────
def test_times_out_without_syncs():
    wc = WormCalibration(1, now=0.0)
    assert wc.no_sync_timeout_s == 60.0                         # solves every 10-15 s: a minute without one is none
    assert not wc.timed_out(59.0) and wc.timed_out(61.0)
    wc.on_sync({}, now=100.0)                                   # any sync, kept or discarded, counts as activity
    assert not wc.timed_out(159.0) and wc.timed_out(161.0)


def test_an_aborted_test_records_and_steps_no_more():
    wc = WormCalibration(1, now=0.0)
    settle(wc, 0.0)
    assert wc.on_sync({}, now=5.0) == pytest.approx(0.5)
    wc.abort('goto')
    assert wc.aborted and wc.abort_reason == 'goto'
    settle(wc, 6.0)
    assert wc.on_sync({}, now=10.0) is None and len(wc.samples) == 1
    wc.abort('jog')
    assert wc.abort_reason == 'goto'                            # the first reason is kept
