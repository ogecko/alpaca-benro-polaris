"""
The two PEC switches: Config.advanced_pec_drift (the drift correction, an EMA of the guide corrections) and
Config.advanced_pec_worm (the worm gear correction from the measured profile), each on or off on its own, for A/B tests.

  * the worm gear correction applies only when it is switched on and a profile exists (a warning when it is on and there
    is none); the drift correction only learns and applies when its own switch is on
  * a sync point keeps its raw motor angles (theta, and the MCU's zeta) next to the raw predicted pose, so QUEST and MAC
    autotune can rebuild every prediction from the current switches and profile -- with the worm gear correction on,
    a sync point is predicted through it, as the pointing is at runtime
  * on the digital twin with the worm gears it cannot see: QUEST, the pointing and MAC autotune reach the solve-noise
    floor with the worm gear correction on, and stay worm-limited with it off
  * switching either correction refits / restarts what depends on it; approving a profile switches the worm gear
    correction on, rejecting it switches it off
"""
import logging
import math
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest
import toml

import control_worm
from config import Config, CONFIG_TOML_PATH
from control_worm import WormFeedForward
from kinematics import (theta_to_q, q_to_azaltroll, azaltroll_to_theta_ik, azalt_to_vector, MountModelParams,
                        get_mechanical_correction_q, autotune_mac)
from quaternion import Q as Quaternion
from sim_digital_twin import Twin
from sim_guider import Worm, ARCSEC

SOLVE_NOISE = 2.0
WORM = Worm(amplitude_arcsec=(40.0, 60.0, 100.0), theta_deg=6.0, h2=0.15, seed=3)
ZETA_OFFSET = np.array([-179.47, 45.12, 0.0])      # theta_raw (518) - zeta (517), as on the real mount


def zeta_profile(worm):
    """The twin's worm as a profile on the MCU's angles (zeta), as the worm profile test measures it."""
    coef = np.zeros((3, 4))
    for m in range(3):
        A = worm.amp[m] * ARCSEC
        coef[m] = [A * np.cos(worm.phi[m]), A * np.sin(worm.phi[m]),
                   A * worm.h2 * np.cos(worm.psi[m]), A * worm.h2 * np.sin(worm.psi[m])]
    return WormFeedForward(worm_theta=worm.theta, harmonics=(1, 2), coef=coef,
                           angle_reference={'M1': 'zeta', 'M2': 'zeta', 'M3': 'zeta'})


def true_error_deg(theta):
    return WORM.error_deg(np.asarray(theta, float) - ZETA_OFFSET)          # the worm turns with the MCU's angles


@pytest.fixture
def profile_path(tmp_path):
    path = tmp_path / 'worm_profile.json'
    zeta_profile(WORM).save(path)
    return path


def twin(monkeypatch, profile_path=None, worm=False, drift=False, mac=False, tmp_path=None):
    """The twin with the given switches; profile_path: the worm profile file (default: none)."""
    if profile_path is None:
        profile_path = (tmp_path or __import__('pathlib').Path('/nonexistent')) / 'no_worm_profile.json'
    monkeypatch.setattr(control_worm, 'WORM_PROFILE_PATH', profile_path)
    tw = Twin(monkeypatch, config={'advanced_alignment': True, 'advanced_align_mac': mac, 'advanced_pec_worm': worm,
                                   'advanced_pec_drift': drift})
    tw.polaris._zeta_raw_offset = list(ZETA_OFFSET)
    return tw


# ── the switches ───────────────────────────────────────────────────────────────────────────────
def test_config_has_both_switches_on_by_default_and_no_single_pec_switch():
    raw = toml.load(CONFIG_TOML_PATH)
    flat = {k: v for section in raw.values() if isinstance(section, dict) for k, v in section.items()}
    assert flat['advanced_pec_drift'] is True and flat['advanced_pec_worm'] is True
    assert 'advanced_pec' not in flat


def test_the_worm_gear_correction_needs_its_switch_as_well_as_a_profile(monkeypatch, profile_path):
    theta = np.array([150.0, 50.0, 20.0])
    tw = twin(monkeypatch, profile_path, worm=False)
    tw.polaris._sm.update_worm_ff(theta)
    assert tw.polaris._sm.corrQ_WFF.degrees == 0
    monkeypatch.setattr(Config, 'advanced_pec_worm', True)
    tw.polaris._sm.update_worm_ff(theta)
    assert tw.polaris._sm.corrQ_WFF.degrees * 3600 > 5


def test_switched_on_without_a_profile_it_warns_once_and_corrects_nothing(monkeypatch, tmp_path, caplog):
    tw = twin(monkeypatch, tmp_path / 'missing.json', worm=True)
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            tw.polaris._sm.update_worm_ff(np.array([150.0, 50.0, 20.0]))
    assert tw.polaris._sm.corrQ_WFF.degrees == 0
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and 'worm' in r.getMessage().lower()]
    assert len(warnings) == 1


def test_the_drift_correction_learns_only_with_its_own_switch(monkeypatch, tmp_path):
    tw = twin(monkeypatch, tmp_path=tmp_path, drift=False)
    assert tw.polaris._sm.update_pec_model(1e-4, 1e-4) is False
    monkeypatch.setattr(Config, 'advanced_pec_drift', True)
    tw.polaris._sm.update_pec_model(1e-4, 1e-4)                 # the first update seeds the model
    assert tw.polaris._sm._pec_n >= 0 and tw.polaris._sm.update_pec_model(1e-4, 1e-4) is True


# ── sync points keep their raw motor angles ──────────────────────────────────────────────────────
def place(tw, theta):
    """What polaris.py sets each tick at motor angles theta (KF state): the raw pose and angles for a sync point."""
    p, sm = tw.polaris, tw.polaris._sm
    q = theta_to_q(*theta)
    p._motorQ_state = p._q1 = q
    p._theta_state = np.array(theta, float)
    p._theta_raw = np.array(theta, float)
    sm.update_worm_ff(theta)
    p._p_azimuth, p._p_altitude, p._p_roll = q_to_azaltroll(q)         # raw, as polaris.update_sky_positions


def test_a_sync_point_keeps_its_raw_motor_angles(monkeypatch, tmp_path):
    tw = twin(monkeypatch, tmp_path=tmp_path)
    theta = np.array(azaltroll_to_theta_ik(120.0, 45.0, 20.0))
    place(tw, theta)
    e = tw.polaris._sm.standard_entry()
    assert np.allclose(e['theta'], theta) and np.allclose(e['zeta'], theta - ZETA_OFFSET)
    tw.polaris._zeta_raw_offset = None                          # no 517 yet: the MCU's angles aren't known
    assert tw.polaris._sm.standard_entry()['zeta'] is None


def test_the_raw_motor_angles_survive_saving_and_loading(monkeypatch, tmp_path):
    tw = twin(monkeypatch, tmp_path=tmp_path)
    sm = tw.polaris._sm
    place(tw, np.array(azaltroll_to_theta_ik(120.0, 45.0, 20.0)))
    e = sm.standard_entry()
    e.update(a_ra=1.0, a_dec=-40.0, a_az=121.0, a_alt=45.5)
    sm.sync_history = [e]
    sm.saveSyncDataToFile(tmp_path / 'sync_points.json')
    sm.sync_history = []
    sm.loadSyncDataFromFile(tmp_path / 'sync_points.json')
    assert np.allclose(sm.sync_history[0]['theta'], e['theta']) and np.allclose(sm.sync_history[0]['zeta'], e['zeta'])


def test_with_the_worm_switch_on_a_sync_point_is_predicted_through_the_worm_gear_correction(monkeypatch, profile_path):
    theta = np.array(azaltroll_to_theta_ik(120.0, 45.0, 20.0))
    tw = twin(monkeypatch, profile_path, worm=False)
    place(tw, theta)
    sm = tw.polaris._sm
    e = sm.standard_entry()
    raw = np.array(sm.entry_to_pred_vector(e)[0])
    assert np.allclose(raw, azalt_to_vector(e['p_az'], e['p_alt']))
    monkeypatch.setattr(Config, 'advanced_pec_worm', True)
    sm.update_worm_ff(theta)
    worm = np.array(sm.entry_to_pred_vector(e)[0])
    az, alt, _ = q_to_azaltroll((sm.corrQ_WFF * theta_to_q(*theta)).normalised)     # the runtime pose
    assert np.allclose(worm, azalt_to_vector(az, alt), atol=1e-9)
    assert math.degrees(math.acos(np.clip(raw @ worm, -1, 1))) * 3600 > 5
    old = {k: v for k, v in e.items() if k not in ('theta', 'zeta')}          # a sync point saved before this version
    assert np.allclose(sm.entry_to_pred_vector(old)[0], raw)


# ── the twin: hidden alignment, hidden worm gears, plate solves ───────────────────────────────────
class Sky:
    """The twin's true pointing: a hidden alignment, optionally hidden mechanical errors, and the worm gears."""
    def __init__(self, seed, mac_true=None):
        rng = np.random.default_rng(seed)
        self.rng = rng
        tilt_axis = [math.cos(rng.uniform(0, 6.28)), math.sin(rng.uniform(0, 6.28)), 0]
        self.A = (Quaternion(axis=[0, 0, 1], degrees=rng.uniform(1, 3)) *
                  Quaternion(axis=tilt_axis, degrees=rng.uniform(0.3, 0.8))).normalised
        self.mac = MountModelParams.from_config({**MAC_ZERO, **(mac_true or {})})

    def true_q(self, theta):
        q = theta_to_q(*theta)
        rbc, _ = get_mechanical_correction_q(q, self.mac)
        return (self.A * rbc * theta_to_q(*(theta + true_error_deg(theta)))).normalised

    def sync(self, tw, poses):
        for th in poses:
            place(tw, th)
            az, alt, _ = q_to_azaltroll(self.true_q(th))
            az += self.rng.normal(0, SOLVE_NOISE / 3600) / max(math.cos(math.radians(alt)), 0.2)
            alt += self.rng.normal(0, SOLVE_NOISE / 3600)
            ra, dec = tw.polaris.altaz2radec(alt, az)
            tw.polaris._sm.process_quest_sync(ra, dec, az, alt)

    def pointing_rms(self, tw, n=150):
        sm, errs = tw.polaris._sm, []
        for th in poses(np.random.default_rng(99), n, spread=False):
            sm.update_worm_ff(th)
            cam, _ = sm.baseQ_to_topoQ(theta_to_q(*th), theta=th)
            a1, l1, _ = q_to_azaltroll(cam)
            a2, l2, _ = q_to_azaltroll(self.true_q(th))
            v1, v2 = np.array(azalt_to_vector(a1, l1)), np.array(azalt_to_vector(a2, l2))
            errs.append(math.degrees(math.acos(np.clip(v1 @ v2, -1, 1))) * 3600)
        return math.sqrt(np.mean(np.square(errs)))


MAC_ZERO = {'m3_tilt_dm2': 0.0, 'm3_tilt_dm1': 0.0, 'm3_tilt_dm3': 0.0, 'm2_tilt_dm2_amp': 0.0, 'm2_tilt_dm2_zero': 0.0,
            'm2_roll_coupling': 0.0, 'm2_roll_zero': 45.0, 'm1_offset': 0.0, 'm2_offset': 0.0, 'm3_offset': 0.0}


def poses(rng, n, spread=True):
    out, base = [], rng.uniform(0, 360)
    while len(out) < n:
        az = (base + 360 * len(out) / n + rng.uniform(-15, 15)) % 360 if spread else rng.uniform(0, 360)
        out.append(np.array(azaltroll_to_theta_ik(az, rng.uniform(30, 70), rng.uniform(-35, 35)), float))
    return out


def quest_rms(tw):
    sm = tw.polaris._sm
    sm.compute_azalt_residuals()
    r = [e['residual_magnitude'] for e in sm.sync_history if not e['deleted'] and 'residual_magnitude' in e]
    return math.sqrt(np.mean(np.square(r))) * 3600


@pytest.mark.parametrize('seed', [0, 1, 2])
def test_with_the_worm_gear_correction_on_quest_and_the_pointing_reach_the_solve_noise(monkeypatch, profile_path, seed):
    """Twin 2026-10-06 (6 syncs, worms 40/60/100"): worm off QUEST ~75", pointing ~55"; on: both ~2"."""
    sky = Sky(seed)
    on = twin(monkeypatch, profile_path, worm=True)
    sky.sync(on, poses(np.random.default_rng(seed), 6))
    assert quest_rms(on) < 6.0 and sky.pointing_rms(on) < 6.0
    monkeypatch.setattr(Config, 'advanced_pec_worm', False)       # switching off: the same syncs, refitted without it
    on.polaris._sm.optimize_alignQ_B2T()
    assert quest_rms(on) > 25.0


MAC_DEFAULT = {'m3_tilt_dm1': -261.30, 'm3_tilt_dm2': -148.69, 'm2_tilt_dm2_amp': 94.78, 'm2_tilt_dm2_zero': 20.88}
MAC_TRUE = {**MAC_DEFAULT, 'm3_tilt_dm1': -230.0, 'm2_tilt_dm2_amp': 80.0, 'm2_tilt_dm2_zero': 30.0}


@pytest.mark.parametrize('worm, max_dm1_err', [(True, 2.0), (False, None)])
def test_mac_autotune_predicts_the_sync_points_as_quest_does(monkeypatch, profile_path, worm, max_dm1_err):
    """Twin 2026-10-06 (10 syncs): with the worm gear correction on, autotune finds m3_tilt_dm1 to <1' (off: ~12')."""
    errs = []
    for seed in range(3):
        sky = Sky(seed, mac_true=MAC_TRUE)
        tw = twin(monkeypatch, profile_path, worm=worm, mac=True)
        for k, v in {**MAC_ZERO, **MAC_DEFAULT}.items():
            monkeypatch.setattr(Config, k, v, raising=False)
        sky.sync(tw, poses(np.random.default_rng(seed), 10))
        r = tw.polaris._sm.autotune_mac()
        errs.append(abs(r['m3_tilt_dm1'] - MAC_TRUE['m3_tilt_dm1']))
    if max_dm1_err:
        assert max(errs) < max_dm1_err
    else:
        assert max(errs) > 3.0                                   # the worm, unmodelled, leaks into the MAC terms


def test_autotune_without_a_worm_rotation_predicts_from_the_raw_pose():
    rng = np.random.default_rng(0)
    entries = []
    for th in poses(rng, 6):
        az, alt, roll = q_to_azaltroll(theta_to_q(*th))
        entries.append(dict(deleted=False, p_az=az, p_alt=alt, p_roll=roll, a_az=(az + 0.5) % 360, a_alt=alt))
    base = MountModelParams.from_config({**MAC_ZERO, **MAC_DEFAULT})
    a = autotune_mac(entries, base)
    b = autotune_mac(entries, base, worm_q=lambda e: Quaternion())
    assert a['rms_before'] == pytest.approx(b['rms_before']) and a['m3_tilt_dm1'] == pytest.approx(b['m3_tilt_dm1'])


# ── switching, approving ───────────────────────────────────────────────────────────────────────
class FakeSM:
    def __init__(self):
        self.calls = []
    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return lambda *a, **k: self.calls.append(name)


def fake_polaris():
    from polaris import Polaris
    p = SimpleNamespace(_sm=FakeSM(), logger=logging.getLogger('test'), _pid=SimpleNamespace())
    p.make_config_params_live = lambda changed: Polaris.make_config_params_live(p, changed)
    return p, Polaris


def test_switching_the_worm_gear_correction_refits_the_alignment_and_restarts_the_drift_model():
    p, _ = fake_polaris()
    p.make_config_params_live({'advanced_pec_worm': True})
    assert {'clear_sync_guiding', 'optimize_alignQ_B2T', 'refresh_pid_setpoints_from_q1'} <= set(p._sm.calls)


def test_switching_the_drift_correction_restarts_its_model():
    p, _ = fake_polaris()
    p.make_config_params_live({'advanced_pec_drift': False})
    assert p._sm.calls == ['reset_pec_model']


@pytest.mark.parametrize('approved', [True, False])
def test_approving_a_profile_switches_the_worm_gear_correction_on_and_rejecting_switches_it_off(monkeypatch, tmp_path,
                                                                                                approved):
    import polaris as polaris_mod
    p, Polaris = fake_polaris()
    p._sm.worm_profile_path = lambda: str(tmp_path / 'worm_profile.json')
    monkeypatch.setattr(polaris_mod, 'apply_profile', lambda path: True)
    monkeypatch.setattr(polaris_mod, 'revert_profile', lambda path: True)
    Config.load(tomlpath=CONFIG_TOML_PATH, pilotpath='/nonexistent')
    monkeypatch.setattr(Config, 'advanced_pec_worm', not approved, raising=False)
    saved = []
    monkeypatch.setattr(Config, 'save_pilot_overrides', classmethod(lambda cls, *a: saved.append(True)))
    assert Polaris.worm_profile_approval(p, approved)
    assert Config.advanced_pec_worm is approved and saved
    assert 'optimize_alignQ_B2T' in p._sm.calls


# ── logging, for the notebooks ────────────────────────────────────────────────────────────────
def test_the_pecconfig_line_names_both_switches(monkeypatch, tmp_path, caplog):
    from analyse_helpers import parse_pecconfig
    tw = twin(monkeypatch, tmp_path=tmp_path, drift=True, worm=False)
    monkeypatch.setattr(Config, 'log_pec', True)
    sm = tw.polaris._sm
    sm._log_pec_config = True
    with caplog.at_level(logging.INFO):
        sm.init_pec_model()
    line = next(r.getMessage() for r in caplog.records if 'PECCONFIG' in r.getMessage())
    cfg = parse_pecconfig(line)
    assert cfg['drift'] is True and cfg['worm'] is False and cfg['tau'] == pytest.approx(sm._pec_tau)
    old = parse_pecconfig('PECCONFIG tau_sec,450.0,min_dt_sec,0.05')       # Beta 7: logged whether PEC was on or not
    assert old['drift'] is None and old['worm'] is None and old['tau'] == 450.0


def test_the_log_catalog_reads_the_drift_switch_and_the_old_single_switch():
    from catalog_logs import _config_pec_state
    assert _config_pec_state({'advanced_pec_drift': True}) is True
    assert _config_pec_state({'advanced_pec': False}) is False                       # logs before the split
    assert _config_pec_state({'advanced_sync_guiding': True}) is None


# ── status, for Pilot's Position page ─────────────────────────────────────────────────────────
def test_each_motors_worm_correction_is_kept_for_the_status(monkeypatch, profile_path):
    theta = np.array([150.0, 50.0, 20.0])
    tw = twin(monkeypatch, profile_path, worm=True)
    sm = tw.polaris._sm
    sm.update_worm_ff(theta)
    want = zeta_profile(WORM).error_deg(theta, zeta_offset=ZETA_OFFSET)
    assert np.allclose(sm.worm_error_deg, want) and np.abs(want).max() * 3600 > 5
    monkeypatch.setattr(Config, 'advanced_pec_worm', False)
    sm.update_worm_ff(theta)
    assert np.all(sm.worm_error_deg == 0)
