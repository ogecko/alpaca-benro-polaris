"""
Tests for the worm feed-forward (control_worm.WormFeedForward): each motor's gear periodic error e_i(theta_i) -- the
true output angle is the MCU's motor angle + e_i, which the MCU can't see -- from a profile learnt offline
(utility/learn_worm.py), applied as a base-frame rotation so the driver's present value is the true pointing.
"""
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

from control_worm import WormFeedForward
from kinematics import theta_to_q

ARCSEC = 3600.0


def profile(m3=(20.0, -12.0, 6.0, 4.0), m2=(0.0, 0.0, 0.0, 0.0), theta=6.0):
    coef = np.zeros((3, 4))
    coef[1], coef[2] = m2, m3
    return WormFeedForward(worm_theta=theta, harmonics=(1, 2), coef=coef)


def test_error_is_each_motors_own_periodic_function_in_arcsec_of_that_motor():
    ff = profile()
    th = np.array([30.0, 40.0, 1.5])                       # M3 worm phase 90 deg
    e = ff.error_deg(th) * ARCSEC
    assert e[0] == 0.0 and e[1] == 0.0
    assert e[2] == pytest.approx(20.0 * 1 + -12.0 * 0 + 6.0 * 0 + 4.0 * -1, abs=1e-9)   # sin 90, cos 90, sin 180, cos 180
    assert np.allclose(ff.error_deg(th + [0, 0, 6.0]), ff.error_deg(th))


def test_correction_rotation_turns_the_measured_pose_into_the_true_one():
    ff = profile(m2=(15.0, 5.0, 0.0, 0.0))
    th = np.array([123.0, 37.0, -21.3])
    corr = ff.correction_q(th)
    true = theta_to_q(*(th + ff.error_deg(th)))
    got = corr * theta_to_q(*th)
    v_true, v_got = true.rotate([0, 0, -1]), got.rotate([0, 0, -1])
    assert np.degrees(np.arccos(np.clip(np.dot(v_true, v_got), -1, 1))) * ARCSEC < 0.01
    assert 5.0 < corr.degrees * ARCSEC < 60.0                  # a small rotation, about the size of the errors


def test_zero_profile_is_the_identity():
    ff = WormFeedForward(coef=np.zeros((3, 4)))
    assert abs(ff.correction_q(np.array([10.0, 20.0, 30.0])).degrees) < 1e-9


def test_profile_round_trips_through_json_with_its_provenance(tmp_path):
    ff = profile(m2=(1.0, 2.0, 3.0, 4.0))
    ff.meta = {'learnt_from': ['alpaca.soak_Beta4.4_09_08_sg_sglog'], 'angles': 'theta_raw (518)'}
    path = tmp_path / 'worm_profile.json'
    ff.save(path)
    d = json.loads(path.read_text())
    assert d['worm_theta'] == 6.0 and d['harmonics'] == [1, 2] and d['motors']['M2'] == [1.0, 2.0, 3.0, 4.0]
    back = WormFeedForward.load(path)
    assert np.allclose(back.coef, ff.coef) and back.worm_theta == 6.0 and back.meta['angles'] == 'theta_raw (518)'


def test_loading_a_missing_or_malformed_profile_gives_none(tmp_path):
    assert WormFeedForward.load(tmp_path / 'nope.json') is None
    bad = tmp_path / 'bad.json'
    bad.write_text('{"worm_theta": 6.0}')
    assert WormFeedForward.load(bad) is None


# ── in the driver: SyncManager.baseQ_to_topoQ applies it first ───────────

import ast
import logging
from control import SyncManager
import control_worm
from test_sync_manager import Polaris, mock_config          # noqa: F401  (fixture)


@pytest.fixture
def ff_config(mock_config, tmp_path, monkeypatch):
    profile(m2=(15.0, 5.0, 0.0, 0.0)).save(tmp_path / 'worm_profile.json')
    mock_config.pec_worm_ff = True
    monkeypatch.setattr(control_worm, 'WORM_PROFILE_PATH', tmp_path / 'worm_profile.json')
    return mock_config


def boresight(q):
    return np.asarray(q.rotate([0, 0, -1]))


def sep_arcsec(a, b):
    return np.degrees(np.arccos(np.clip(np.dot(a, b), -1, 1))) * ARCSEC


TH = np.array([123.0, 37.0, -21.3])


def test_present_value_is_the_true_pose_when_the_feed_forward_is_on(ff_config):
    sm = SyncManager(logging.getLogger('test'), Polaris())
    cam, _ = sm.baseQ_to_topoQ(theta_to_q(*TH), theta=TH)
    ff = WormFeedForward.load(control_worm.WORM_PROFILE_PATH)
    want = sm.alignQ_B2T * theta_to_q(*(TH + ff.error_deg(TH)))
    assert sep_arcsec(boresight(cam), boresight(want)) < 0.01
    plain = sm.alignQ_B2T * theta_to_q(*TH)
    assert sep_arcsec(boresight(cam), boresight(plain)) > 5.0


def test_calls_without_motor_angles_use_the_last_correction(ff_config):
    sm = SyncManager(logging.getLogger('test'), Polaris())
    a, _ = sm.baseQ_to_topoQ(theta_to_q(*TH), theta=TH)
    b, _ = sm.baseQ_to_topoQ(theta_to_q(*TH))
    assert sep_arcsec(boresight(a), boresight(b)) < 1e-6


def test_off_or_without_a_profile_the_present_value_is_unchanged(ff_config, tmp_path, caplog, monkeypatch):
    for setup in ('off', 'missing'):
        if setup == 'off':
            ff_config.pec_worm_ff = False
        else:
            ff_config.pec_worm_ff = True
            monkeypatch.setattr(control_worm, 'WORM_PROFILE_PATH', tmp_path / 'none.json')
        sm = SyncManager(logging.getLogger('test'), Polaris())
        with caplog.at_level(logging.WARNING, logger='test'):
            cam, _ = sm.baseQ_to_topoQ(theta_to_q(*TH), theta=TH)
        assert sep_arcsec(boresight(cam), boresight(sm.alignQ_B2T * theta_to_q(*TH))) < 1e-6
    assert any('worm' in r.getMessage().lower() for r in caplog.records)      # missing profile is reported


def test_switching_it_off_at_runtime_takes_effect_on_the_next_update(ff_config):
    sm = SyncManager(logging.getLogger('test'), Polaris())
    sm.baseQ_to_topoQ(theta_to_q(*TH), theta=TH)
    ff_config.pec_worm_ff = False
    cam, _ = sm.baseQ_to_topoQ(theta_to_q(*TH), theta=TH)
    assert sep_arcsec(boresight(cam), boresight(sm.alignQ_B2T * theta_to_q(*TH))) < 1e-6


def test_peclog_records_the_applied_correction_in_ra_and_dec(ff_config, caplog):
    ff_config.log_pec = True
    sm = SyncManager(logging.getLogger('test'), Polaris())
    sm.polaris._theta_raw = TH
    sm.baseQ_to_topoQ(theta_to_q(*TH), theta=TH)
    sm.cache_axes_B(sm.alignQ_B2T * theta_to_q(*TH))
    with caplog.at_level(logging.INFO, logger='test'):
        sm._pec_log(0.001, None, (0.0, 0.0))
    p = ast.literal_eval(next(r.getMessage() for r in caplog.records if r.getMessage().startswith('PECLOG '))[7:])
    assert len(p['wff']) == 2 and all(isinstance(v, float) for v in p['wff'])
    assert 0.05 < np.hypot(*p['wff']) * 60 < 60.0                  # arcsec, about the size of the profile's error


def test_logged_wff_is_the_worm_part_of_the_drift_the_analysis_model_predicts(ff_config, caplog):
    """On a feed-forward night the guide corrections (total_accum) lack exactly what PECLOG logs as wff, in the same
    convention as utility/pe_analysis (WormProfile.drift) -- so drift = total_accum + wff."""
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
    from pe_analysis import WormProfile
    ff_config.log_pec = True
    sm = SyncManager(logging.getLogger('test'), Polaris())
    lat = sm.polaris._sitelatitude
    ff = WormFeedForward.load(control_worm.WORM_PROFILE_PATH)
    for th in (TH, np.array([200.0, 55.0, 30.0]), np.array([40.0, 25.0, -60.0])):
        sm.polaris._theta_raw = th
        sm.baseQ_to_topoQ(theta_to_q(*th), theta=th)
        sm.cache_axes_B(theta_to_q(*th))                       # ideal (identity) alignment
        caplog.clear()
        with caplog.at_level(logging.INFO, logger='test'):
            sm._pec_log(0.001, None, (0.0, 0.0))
        wff = ast.literal_eval(next(r.getMessage() for r in caplog.records if r.getMessage().startswith('PECLOG '))[7:])['wff']
        ra, dec = WormProfile(ff.coef.ravel(), ff.worm_theta, ff.harmonics).drift(th[None, :], lat)
        assert wff[0] * 60 == pytest.approx(ra[0], abs=0.05) and wff[1] * 60 == pytest.approx(dec[0], abs=0.05)


def test_provenance_can_never_overwrite_the_coefficients(tmp_path):
    ff = profile(m2=(1.0, 2.0, 3.0, 4.0))
    ff.meta = {'motors': ['M2', 'M3'], 'worm_theta': 99, 'harmonics': [7]}       # clashing names
    ff.save(tmp_path / 'p.json')
    back = WormFeedForward.load(tmp_path / 'p.json')
    assert back is not None and np.allclose(back.coef, ff.coef)
    assert back.worm_theta == 6.0 and back.harmonics == (1, 2)
