"""
Worm profiles by direction and by setup (driver/control_worm.py):

  * a motor whose worm differs with its direction of travel (the real mount's M2: 89" forward, 31" reverse) gets
    forward and reverse profiles from one joint fit, once there are enough tests each way and the two differ; a motor
    run only one way (M1), or with the same worm both ways, keeps one profile
  * the feed-forward picks each motor's profile by its direction of travel (from the PID's feed-forward rate, kept
    while it stands); sync points keep their directions for the alignment model
  * tests keep the setup (focal length and ratio) they ran with; a setup pools its own tests, else the same focal
    length's, else all; the driver applies the closest setup's profile, else the generic one
"""
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

import control_worm as cw
from control_worm import (POSITIONS, WormFeedForward, WormMixin, fit_worm_profile, store_profile_test, pooled_profile,
                          set_last_test_approved, make_setup, setup_match, setup_tests, TRACK_RATE_MIN_DPS)

WORM = 6.0
FORWARD = {'M1': [20.0, 15.0, 0, 0], 'M2': [-80.0, -40.0, 0, 0], 'M3': [-60.0, -30.0, 0, 0]}   # a1 b1 a2 b2
REVERSE = {'M1': [20.0, 15.0, 0, 0], 'M2': [-30.0, 10.0, 0, 0], 'M3': [-60.0, -30.0, 0, 0]}    # only M2 differs


def synthetic(direction, seed, noise=2.0, forward=FORWARD, reverse=REVERSE, separation_deg=40.0):
    """A test's samples where each motor arrives at every position moving `direction` (its tracking direction), with
    its forward or reverse worm, plus an offset, a drift and noise."""
    rng = np.random.default_rng(seed)
    s = np.radians(separation_deg)
    J = np.array([[0.7, 0.0], [0.0, 1.0], [np.cos(s), np.sin(s)]])
    start = rng.uniform(0, 30, 3)
    out = []
    for i, pos in enumerate(POSITIONS):
        zeta = start + pos + 0.05 * np.array(direction) * i
        d = [0, 0, 0] if i == 0 else list(direction)
        e = np.zeros(3)
        for m, M in enumerate(cw.MOTORS):
            a1, b1, a2, b2 = (forward if d[m] >= 0 else reverse)[M]
            ph = 2 * np.pi * zeta[m] / WORM
            e[m] = a1 * np.sin(ph) + b1 * np.cos(ph) + a2 * np.sin(2 * ph) + b2 * np.cos(2 * ph)
        res = J.T @ e + np.array([25.0, -15.0]) + np.array([0.01, -0.02]) * i + rng.normal(0, noise, 2)
        out.append({'t': 15.0 * i, 'zeta': zeta.tolist(), 'res': res.tolist(), 'J': J.tolist(),
                    'offset': pos.tolist(), 'direction': d})
    return out


def store(path, directions, setup=make_setup(200, 4), seed0=0):
    """Run and approve a test per direction set (each added to the pool, rebuilding the profiles)."""
    for k, d in enumerate(directions):
        s = synthetic(d, seed=seed0 + k)
        store_profile_test(path, s, fit_worm_profile([s]), setup=setup)
        set_last_test_approved(path, True)


# M1 always reverse, M2 alternating, M3 alternating out of step with M2
DIRS = [(-1, 1, 1), (-1, -1, 1), (-1, 1, -1), (-1, -1, -1), (-1, 1, 1), (-1, -1, -1)]


def h1(coef):
    return float(np.hypot(coef[0], coef[1]))


def test_a_motor_whose_worm_differs_with_direction_gets_forward_and_reverse_profiles(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store(p, DIRS)
    pooled = pooled_profile(p, setup=make_setup(200, 4))
    d = pooled['directions']
    assert pooled['status'] == 'COMPLETED'
    assert d['M2']['split'] and d['M2']['tests'] == [3, 3]
    assert d['M2']['forward']['amplitude'] == pytest.approx(h1(FORWARD['M2']), abs=4)
    assert d['M2']['reverse']['amplitude'] == pytest.approx(h1(REVERSE['M2']), abs=4)
    assert not d['M1']['split'] and 'forward' in d['M1']['reason']          # never ran forward
    assert not d['M3']['split'] and 'one profile' in d['M3']['reason']      # the same worm both ways


def test_too_few_tests_each_way_keeps_one_profile(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store(p, DIRS[:4])                                                      # two each way
    pooled = pooled_profile(p, setup=make_setup(200, 4))
    assert not any(v['split'] for v in pooled['directions'].values())


def test_the_feed_forward_picks_each_motors_profile_by_its_direction_and_follows_the_pool(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store(p, DIRS)
    ff = WormFeedForward.load(p, setup=make_setup(200, 4))
    assert set(ff.direction_coef) == {'M2'}
    theta, off = np.array([1.0, 1.5, 2.0]), [0.0, 0.0, 0.0]
    ph = 2 * np.pi * 1.5 / WORM
    true = {d: (t['M2'][0] * np.sin(ph) + t['M2'][1] * np.cos(ph)) for d, t in ((1, FORWARD), (-1, REVERSE))}
    for d in (1, -1):
        assert ff.error_deg(theta, off, direction=[0, d, 0])[1] * 3600 == pytest.approx(true[d], abs=6)
    combined = ff.error_deg(theta, off, direction=[0, 0, 0])[1]             # direction unknown: the combined fit
    assert combined == ff.error_deg(theta, off)[1]
    assert set_last_test_approved(p, False)                                  # the last test out: 2 forward left
    ff = WormFeedForward.load(p, setup=make_setup(200, 4))
    assert ff.direction_coef == {} and np.any(ff.coef)                      # too few each way: one profile


def test_the_direction_follows_the_feed_forward_rate_and_is_kept_while_standing():
    pid = SimpleNamespace(omega_ff=np.array([-0.004, 0.002, 0.0]))
    sm = SimpleNamespace(polaris=SimpleNamespace(_pid=pid), worm_direction=np.zeros(3))
    WormMixin.update_worm_direction(sm)
    assert list(sm.worm_direction) == [-1, 1, 0]
    pid.omega_ff = np.array([0.0, TRACK_RATE_MIN_DPS / 2, 0.003])          # M1, M2 stop: they stay on their flank
    WormMixin.update_worm_direction(sm)
    assert list(sm.worm_direction) == [-1, 1, 1]


def test_a_sync_point_uses_the_directions_it_was_taken_with(tmp_path):
    ff = WormFeedForward(coef=np.zeros((3, 4)), direction_coef={'M2': {'forward': [36.0, 0, 0, 0],
                                                                       'reverse': [-36.0, 0, 0, 0]}})
    sm = SimpleNamespace(worm_ff_in_use=lambda: ff, _entry_angles=WormMixin._entry_angles)
    entry = {'theta': [0.0, 1.5, 0.0], 'zeta': [0.0, 1.5, 0.0], 'wdir': [0, -1, 0]}   # sin(90 deg) at zeta 1.5
    assert WormMixin.entry_worm_error_deg(sm, entry)[1] * 3600 == pytest.approx(-36.0)
    entry['wdir'] = None                                                    # saved before directions were kept
    assert WormMixin.entry_worm_error_deg(sm, entry)[1] == 0.0              # the combined fit (zero here)


# ── setups ────────────────────────────────────────────────────────────────────────────────────
def test_setup_match_prefers_the_same_lens_then_focal_length_then_the_nearest():
    want = make_setup(200, 4)
    order = sorted([make_setup(300, 2.8), make_setup(200, 2.8), make_setup(200, 4), make_setup(400, 2), None],
                   key=lambda s: setup_match(s, want))
    assert order[:4] == [make_setup(200, 4), make_setup(200, 2.8), make_setup(300, 2.8), make_setup(400, 2)]
    assert cw.setup_name(make_setup(300, 2.8)) == '300mm F2.8' and cw.setup_name(make_setup(200)) == '200mm'
    assert make_setup(0, 4) is None and make_setup(None) is None


def test_a_setup_pools_its_own_tests_else_the_same_focal_length_else_all(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store(p, DIRS[:2], setup=make_setup(300, 2.8))
    store(p, DIRS[2:4], setup=make_setup(200, 2.8), seed0=10)
    entries = WormFeedForward.load(p).meta['calibration_history']
    same, matched = setup_tests(entries, make_setup(300, 2.8))
    assert matched == 'lens' and len(same) == 2
    same, matched = setup_tests(entries, make_setup(200, 4))
    assert matched == 'focal length' and all(e['setup']['focal_length'] == 200 for e in same)
    same, matched = setup_tests(entries, make_setup(85, 1.8))
    assert matched is None and len(same) == 4


def test_the_closest_setups_profile_applies_else_the_profile_in_use(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store(p, DIRS, setup=make_setup(200, 4))
    assert WormFeedForward.load(p, setup=make_setup(200, 4)).meta['profile_setup'] == '200mm F4'
    assert WormFeedForward.load(p, setup=make_setup(300, 2.8)).meta['profile_setup'] == '200mm F4'   # closest
    ff = WormFeedForward.load(p, setup=None)
    assert 'profile_setup' not in ff.meta and np.any(ff.coef)              # no lens set: the generic profile


def test_the_profile_in_use_is_logged_per_motor_when_loaded_and_when_a_motor_reverses():
    lines = []
    ff = WormFeedForward(coef=np.array([[20.0, 5, 0, 0], [60.0, 10, 0, 0], [0, 0, 0, 0]]),
                         direction_coef={'M2': {'forward': [90.0, 0, 0, 0], 'reverse': [30.0, 0, 0, 0]}},
                         meta={'profile_setup': '200mm F4'})
    sm = SimpleNamespace(worm_direction=np.zeros(3), logger=SimpleNamespace(info=lines.append))
    sm.worm_in_use_text = lambda prof: WormMixin.worm_in_use_text(sm, prof)
    log = lambda: WormMixin._log_worm_in_use(sm, ff)
    log()
    sm.worm_direction = np.array([-1.0, 1.0, 0.0])
    log()
    log()                                                                   # no change: no line
    sm.worm_direction = np.array([-1.0, -1.0, 0.0])
    log()
    assert lines == ['WORMPROFILE IN USE: 200mm F4: M1 duplex, M2 duplex, M3 off',
                     'WORMPROFILE IN USE: 200mm F4: M1 duplex, M2 fwd, M3 off',
                     'WORMPROFILE IN USE: 200mm F4: M1 duplex, M2 rev, M3 off']
    ff.meta['profile_setup'] = None
    assert WormMixin.worm_in_use_text(sm, ff).startswith('generic: ')


# ── robustness: a damaged entry falls back, never turns the correction off ─────────────────────
def lens_file(tmp_path, setup_profiles, direction_motors=None):
    """A profile file with a generic profile (M2 36" sin) and the given setup profiles."""
    p = str(tmp_path / 'worm_profile.json')
    ff = WormFeedForward(coef=np.array([[0, 0, 0, 0], [36.0, 0, 0, 0], [0, 0, 0, 0]]),
                         direction_coef=direction_motors or {}, angle_reference={})
    ff.meta['setup_profiles'] = setup_profiles
    ff.save(p)
    return p


def lens_profile(fl, fr, m2):
    return {'setup': make_setup(fl, fr), 'harmonics': [1, 2], 'angle_reference': {},
            'motors': {'M1': [0, 0, 0, 0], 'M2': [m2, 0, 0, 0], 'M3': [0, 0, 0, 0]}}


def m2_arcsec(ff):
    return ff.error_deg([0.0, 1.5, 0.0])[1] * 3600                       # sin(90 deg) at MCU angle 1.5


def test_a_damaged_setup_profile_is_passed_over_for_the_next_closest_then_the_generic(tmp_path):
    good = lens_profile(200, 2.8, 50.0)
    bad_coef = {**lens_profile(200, 4, 99.0), 'motors': {'M1': [0, 0], 'M2': [1, 2, 3, 4], 'M3': [0, 0, 0, 0]}}
    nan = {**lens_profile(200, 4, 99.0)}
    nan['motors'] = {**nan['motors'], 'M2': [float('nan'), 0, 0, 0]}
    p = lens_file(tmp_path, {'200mm F4': bad_coef, '200mm F4 b': nan, '200mm F2.8': good, 'junk': 'x',
                             'no setup': {'harmonics': [1, 2]}})
    ff = WormFeedForward.load(p, setup=make_setup(200, 4))
    assert ff.meta['profile_setup'] == '200mm F2.8' and m2_arcsec(ff) == pytest.approx(50.0)
    warnings = ' '.join(ff.meta['profile_warnings'])
    assert "'200mm F4' skipped" in warnings and "'junk' skipped" in warnings and "'no setup' skipped" in warnings
    p = lens_file(tmp_path, {'200mm F4': bad_coef})                     # nothing usable: the generic profile
    ff = WormFeedForward.load(p, setup=make_setup(200, 4))
    assert ff.meta['profile_setup'] is None and m2_arcsec(ff) == pytest.approx(36.0)
    p = lens_file(tmp_path, 'not a dict')
    assert m2_arcsec(WormFeedForward.load(p, setup=make_setup(200, 4))) == pytest.approx(36.0)


def test_a_damaged_forward_reverse_pair_leaves_that_motor_on_its_combined_profile(tmp_path):
    p = lens_file(tmp_path, {}, direction_motors={'M2': {'forward': [90.0, 0, 0, 0], 'reverse': [30.0, 0, 0, 0]},
                                                  'M3': {'forward': [1.0, 2.0, 3.0, 4.0], 'reverse': [0, 0, 0, 0]}})
    d = json.load(open(p))
    d['direction_motors']['M3']['reverse'] = [1, 2]                        # wrong length
    json.dump(d, open(p, 'w'))
    ff = WormFeedForward.load(p)
    assert set(ff.direction_coef) == {'M2'} and 'M3 forward / reverse' in ff.meta['profile_warnings'][0]
    assert ff.error_deg([0.0, 1.5, 0.0], direction=[0, 1, 0])[1] * 3600 == pytest.approx(90.0)


def test_a_damaged_generic_profile_is_no_profile(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    open(p, 'w').write(json.dumps({'worm_theta': 6.0, 'harmonics': [1, 2], 'motors': {'M1': [0, 0]}}))
    assert WormFeedForward.load(p) is None
    open(p, 'w').write('{not json')
    assert WormFeedForward.load(p, setup=make_setup(200, 4)) is None


def test_setup_match_ranks_a_bad_focal_length_as_unknown():
    for bad in ({'focal_length': 0}, {'focal_length': -200}, {'focal_length': 'x'}, {'focal_length': float('inf')}, {}):
        assert setup_match(bad, make_setup(200, 4))[0] == 3


def test_the_driver_loads_the_profile_for_the_lens_and_reloads_when_it_changes(tmp_path, monkeypatch):
    p = lens_file(tmp_path, {'200mm F4': lens_profile(200, 4, 50.0), '300mm F2.8': lens_profile(300, 2.8, 80.0)})
    lines = []
    sm = SimpleNamespace(worm_profile_path=lambda: p, _worm_ff_path=None, _worm_ff=None,
                         logger=SimpleNamespace(info=lines.append, warning=lines.append))
    load = lambda: WormMixin._worm_ff_profile(sm)
    monkeypatch.setattr(cw.Config, 'focal_length', 200, raising=False)
    monkeypatch.setattr(cw.Config, 'focal_ratio', 4, raising=False)
    assert m2_arcsec(load()) == pytest.approx(50.0) and 'WORMPROFILE CHOICE: the 200mm F4 profile' in lines
    n = len(lines)
    load()
    assert len(lines) == n                                               # same lens: cached, not re-read
    monkeypatch.setattr(cw.Config, 'focal_length', 300, raising=False)  # the lens changed in the settings
    assert m2_arcsec(load()) == pytest.approx(80.0)
    assert 'WORMPROFILE CHOICE: the 300mm F2.8 profile (closest to 300mm F4)' in lines
    monkeypatch.setattr(cw.Config, 'focal_length', 0, raising=False)    # unset: the generic profile
    assert m2_arcsec(load()) == pytest.approx(36.0)
    assert 'WORMPROFILE CHOICE: no profile for unset lens: the generic profile' in lines


def test_the_direction_holds_through_a_goto_until_the_motor_tracks_again():
    """The planner drives a goto's motion through its own reference, not omega_ff: the direction then stays as it was
    (the gear stays on the flank it last tracked on) and changes once tracking turns the motor the other way."""
    pid = SimpleNamespace(omega_ff=np.array([-0.004, 0.002, 0.001]))
    sm = SimpleNamespace(polaris=SimpleNamespace(_pid=pid), worm_direction=np.zeros(3))
    WormMixin.update_worm_direction(sm)
    pid.omega_ff = np.zeros(3)                                           # a goto
    WormMixin.update_worm_direction(sm)
    assert list(sm.worm_direction) == [-1, 1, 1]
    pid.omega_ff = np.array([-0.004, -0.002, 0.001])                     # tracking, M2 the other way
    WormMixin.update_worm_direction(sm)
    assert list(sm.worm_direction) == [-1, -1, 1]
    sm.polaris = SimpleNamespace()                                       # no PID yet: unchanged, no error
    WormMixin.update_worm_direction(sm)
    assert list(sm.worm_direction) == [-1, -1, 1]


# ── on the digital twin: tracking east, then west, reverses M2 ─────────────────────────────────
def test_on_the_twin_m2s_profile_follows_its_tracking_direction_across_the_meridian(monkeypatch, tmp_path, caplog):
    """A split M2 (forward 90", reverse 20"): tracking a target in the east and then one in the west turns M2 opposite
    ways. Each time the driver's direction matches M2's tracking rate, the correction is that direction's profile, and
    the change is logged once."""
    import logging
    import control_worm
    from sim_digital_twin import Twin
    from kinematics import azaltroll_to_theta_ik
    path = tmp_path / 'worm_profile.json'
    ff = WormFeedForward(coef=np.array([[0, 0, 0, 0], [50.0, 0, 0, 0], [0, 0, 0, 0]]),
                         direction_coef={'M2': {'forward': [90.0, 0, 0, 0], 'reverse': [20.0, 0, 0, 0]}})
    ff.save(path)                                                        # on 518 angles: the twin has no 517 offset
    monkeypatch.setattr(control_worm, 'WORM_PROFILE_PATH', path)
    tw = Twin(monkeypatch, config={'advanced_pec_worm': True}, seed=0)
    sm, pid = tw.polaris._sm, tw.pid
    seen = []
    with caplog.at_level(logging.INFO, logger='twin'):
        for az in (100.0, 260.0):
            if not seen:
                tw.place(azaltroll_to_theta_ik(az, 40.0, 0.0))
                tw.start_tracking()
            else:
                tw.goto_altaz(az, 40.0)
                tw.run(60)
            tw.run(120)
            d = int(sm.worm_direction[1])
            assert d == int(np.sign(pid.omega_ff[1])) and d != 0       # the way M2 tracks
            theta = tw.kf.get_state()[0]
            want = ff.error_deg(theta, direction=[0, d, 0])[1]
            assert sm.worm_error_deg[1] == pytest.approx(want, abs=1e-9)  # that direction's profile, not the combined
            seen.append(d)
    assert seen[0] == -seen[1]                                           # east and west: opposite ways
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith('WORMPROFILE IN USE: ')]
    names = {1: 'fwd', -1: 'rev'}
    # once on load (M2 not yet moved: duplex), then once per change -- not every tick
    assert lines == ['WORMPROFILE IN USE: generic: M1 off, M2 duplex, M3 off'] + \
        [f'WORMPROFILE IN USE: generic: M1 off, M2 {names[d]}, M3 off' for d in seen]
    tw.close()


def test_a_test_record_starts_with_its_status_approval_and_lens(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store(p, DIRS[:1])
    raw = json.load(open(p))['calibration_history']
    raw[0] = {k: raw[0][k] for k in ('samples', 'result', 'setup', 'approved', 'test', 'created', 'status', 'timing')}
    d = json.load(open(p))
    d['calibration_history'] = raw
    json.dump(d, open(p, 'w'))
    WormFeedForward.load(p).save(p)                                      # an older file's records are reordered
    keys = list(json.load(open(p))['calibration_history'][0])
    assert keys[:5] == ['test', 'created', 'status', 'approved', 'setup'] and keys[-1] in ('samples', 'timing')


def test_a_test_from_before_the_flags_gets_them_written_so_it_can_be_edited(tmp_path):
    p = str(tmp_path / 'worm_profile.json')
    store(p, DIRS[:2])
    d = json.load(open(p))
    for e in d['calibration_history']:
        del e['approved'], e['setup']
    json.dump(d, open(p, 'w'))
    WormFeedForward.load(p).save(p)
    h = json.load(open(p))['calibration_history']
    assert [(e['approved'], e['setup']) for e in h] == [(True, None), (True, None)]   # as they read: all approved
    h[0]['approved'] = False                                                    # rejected by hand
    d = json.load(open(p))
    d['calibration_history'] = h
    json.dump(d, open(p, 'w'))
    assert setup_tests(WormFeedForward.load(p).meta['calibration_history'], None)[0] == [
        e for e in WormFeedForward.load(p).meta['calibration_history'][1:]]
