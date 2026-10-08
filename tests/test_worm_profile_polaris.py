"""
The Polaris glue of the worm profile test (polaris.Polaris.worm_profile_test, sync_telescope, worm_profile_approval),
run against a stand-in Polaris: syncs during a test go to SyncManager.record_worm_sync and nowhere else; the test turns
tracking on and back off, shows progress, fits, keeps the test in the profile file and fills the row with the pooled
profile; approval applies it and reloads the feed-forward, rejection restores the previous profile.
"""
import asyncio
import json
import logging
import os
import sys
from types import SimpleNamespace
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

import polaris as polaris_mod
from polaris import Polaris
from control import CalibrationManager
from control_worm import PROFILE_TEST, WormProfileTest, WormFeedForward, POSITIONS
from test_worm_profile import synthetic_test, TRUE, coef_error


class Lifecycle:
    def __init__(self):
        self.stopped = False
        self.events = []
    def start(self): self.events.append('start')
    def reset(self): self.events.append('reset')
    def should_stop(self): return self.stopped


class FakeSM:
    def __init__(self, path, separation=30.0):
        self.worm_test = None
        self.path = path
        self.separation = separation
        self.recorded = []
        self.reloaded = 0
    def worm_profile_path(self): return self.path
    def motor_separation(self, theta): return self.separation, [0.7, 1.0, 1.0]
    def record_worm_sync(self, *a): self.recorded.append(a)
    def reload_worm_ff(self): self.reloaded += 1
    def sync_az_alt(self, *a): raise AssertionError('applied to the alignment model during a worm profile test')


def fake_polaris(tmp_path, separation=30.0, roll=30.0, roll_move_finishes=True):
    p = SimpleNamespace(lifecycle=Lifecycle(), _sm=FakeSM(str(tmp_path / 'worm_profile.json'), separation),
                        _cm=CalibrationManager(False), logger=logging.getLogger('test'), _tracking=False, calls=[],
                        _pid=SimpleNamespace(theta_pv=[180.0, 45.0, 10.0], alpha_pv=[180.0, 45.0, roll]), rolls=[],
                        _worm_test_rolling=False, synced_while_rolling=[])
    def slew_axis(coords):
        p.rolls.append(coords['roll'])
        p._pid.alpha_pv[2] = coords['roll']
    async def wait_for_goto_complete():
        # a solve-and-sync arriving mid-rotation must be ignored, not become an alignment point
        p.synced_while_rolling.append(asyncio.create_task(Polaris.sync_telescope(p, a_ra=5.0, a_dec=-20.0)))
        await asyncio.sleep(0)
        if not roll_move_finishes:
            await asyncio.sleep(10)
    p.slew_axis, p.wait_for_goto_complete = slew_axis, wait_for_goto_complete
    p._worm_test_roll = lambda target, timeout_s=120.0: Polaris._worm_test_roll(p, target, 0.2 if not roll_move_finishes else timeout_s)
    p._cm.createTestDataFromBaseline()
    p._cm.ensureWormProfileRow()
    async def start_tracking():
        p._tracking = True; p.calls.append('start_tracking')
    async def stop_tracking():
        p._tracking = False; p.calls.append('stop_tracking')
    p.start_tracking, p.stop_tracking = start_tracking, stop_tracking
    p.radec2altaz = lambda ra, dec: (45.0, 180.0)
    p.worm_profile_approval = lambda approved: Polaris.worm_profile_approval(p, approved)
    p.live = []
    p.make_config_params_live = lambda changed: p.live.append(dict(changed))
    return p


@pytest.fixture
def cfg(monkeypatch):
    for k, v in dict(advanced_control=True, advanced_tracking=True, advanced_alignment=True).items():
        monkeypatch.setattr(polaris_mod.Config, k, v, raising=False)
    monkeypatch.setattr(polaris_mod.Config, 'save_pilot_overrides', classmethod(lambda cls, *a: None))   # not data/


def feed(test, seed=0):
    """Feed the running test what record_worm_sync would, one settled sync per position."""
    samples = synthetic_test(seed=seed)
    while not test.done:
        now = 20.0 * test.index
        test.track_settle(0.0, now)
        test.track_settle(0.0, now + 2.0)
        s = samples[test.index]
        test.on_sync({k: s[k] for k in ('t', 'zeta', 'res', 'J')}, now=now + 10.0)


def run_test(p, seed=0, stop=False):
    async def run():
        task = asyncio.create_task(Polaris.worm_profile_test(p))
        while p._sm.worm_test is None:
            await asyncio.sleep(0.01)
        if stop:
            p.lifecycle.stopped = True
        else:
            await asyncio.sleep(0.6)
            assert p._cm.test_data[PROFILE_TEST]['test_status'] == f'PENDING 0/{len(POSITIONS)}'
            feed(p._sm.worm_test, seed)
        await asyncio.wait_for(task, 5)
    asyncio.run(run())


def test_sync_during_a_test_is_recorded_not_applied(tmp_path, cfg):
    p = fake_polaris(tmp_path)
    p._sm.worm_test = WormProfileTest()
    asyncio.run(Polaris.sync_telescope(p, a_ra=5.0, a_dec=-20.0))
    assert p._sm.recorded == [(5.0, -20.0, 180.0, 45.0)]


def test_the_test_runs_fits_keeps_the_test_and_shows_the_pooled_profile(tmp_path, cfg):
    p = fake_polaris(tmp_path)
    p._cm.pendingWormProfileTest([PROFILE_TEST])
    run_test(p, seed=0)
    assert p.calls == ['start_tracking', 'stop_tracking'] and p._sm.worm_test is None
    assert p.lifecycle.events == ['start', 'reset']
    row = p._cm.test_data[PROFILE_TEST]
    assert row['test_status'] == 'COMPLETED' and row['test_result'].startswith('M1 ') and 'rms n47' in row['test_stdev']
    h = json.load(open(p._sm.path))['calibration_history']
    assert len(h) == 1 and len(h[0]['samples']) == len(POSITIONS) and h[0]['status'] == 'COMPLETED'

    run_test(p, seed=1)                                          # a second test: the row pools both
    assert p._cm.test_data[PROFILE_TEST]['test_change'].startswith('pooled 2 tests:')

    p._cm.on_worm_profile_approval = p.worm_profile_approval
    p._cm.toggleApproval(0, [PROFILE_TEST])
    assert row['test_status'] == 'APPROVED' and p._sm.reloaded == 1
    assert row['dps'] == row['test_result'] and row['test_change'].endswith('+0"')       # baseline: now the pooled profile
    assert p.live[-1] == {'advanced_pec_worm': True}            # approving switches the worm gear correction on
    ff = WormFeedForward.load(p._sm.path)
    assert ff.angle_reference == {'M1': 'zeta', 'M2': 'zeta', 'M3': 'zeta'}
    assert all(coef_error(ff.coef[m][:2], TRUE[M][:2]) < 4.0 for m, M in enumerate(('M1', 'M2', 'M3')))
    p._cm.toggleApproval(0, [PROFILE_TEST])
    assert row['test_status'] == 'REJECTED' and p._sm.reloaded == 2
    assert p.live[-1] == {'advanced_pec_worm': False}
    assert np.all(WormFeedForward.load(p._sm.path).coef == 0)


def test_stopping_early_keeps_tracking_as_it_was_and_reports_stopped(tmp_path, cfg):
    p = fake_polaris(tmp_path)
    p._tracking = True
    run_test(p, stop=True)
    assert p.calls == [] and p._tracking
    assert p._cm.test_data[PROFILE_TEST]['test_status'] == 'STOPPED'
    assert not os.path.exists(p._sm.path)                       # nothing recorded: nothing written


def test_no_syncs_times_out_as_no_data(tmp_path, cfg, monkeypatch, caplog):
    p = fake_polaris(tmp_path)
    monkeypatch.setattr(polaris_mod, 'WormProfileTest', lambda: WormProfileTest(no_sync_timeout_s=0.3))  # 60 s, shortened
    with caplog.at_level(logging.INFO, logger='test'):
        asyncio.run(asyncio.wait_for(Polaris.worm_profile_test(p), 5))
    log = ' '.join(r.getMessage() for r in caplog.records)
    assert 'requires plate-solve syncs' in log and 'nothing saved' in log
    assert p._cm.test_data[PROFILE_TEST]['test_status'] == 'NO DATA'
    assert p._sm.worm_test is None and p.calls == ['start_tracking', 'stop_tracking']


def test_a_pose_with_m1_and_m3_moving_the_field_the_same_way_is_warned_about(tmp_path, cfg, caplog):
    p = fake_polaris(tmp_path, separation=3.0)
    with caplog.at_level(logging.WARNING, logger='test'):
        run_test(p, stop=True)
    assert any('Roll' in r.getMessage() for r in caplog.records)


def test_pulse_guiding_during_a_test_aborts_it_and_is_not_applied(tmp_path, cfg, monkeypatch):
    monkeypatch.setattr(polaris_mod.Config, 'advanced_pulse_guiding', True, raising=False)
    p = fake_polaris(tmp_path)
    p._sm.worm_test = WormProfileTest()
    p._sm.process_pulse_guide_axis = lambda *a: (_ for _ in ()).throw(AssertionError('pulse applied'))
    p._lock = __import__('threading').Lock()
    Polaris.pulse_guide(p, 0, 500)
    assert p._sm.worm_test.aborted and 'pulse guide' in p._sm.worm_test.abort_reason


def test_start_and_end_log_lines_mark_the_test_for_the_log_catalog(tmp_path, cfg, caplog):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
    from catalog_logs import _classify
    p = fake_polaris(tmp_path)
    p._tracking = True
    with caplog.at_level(logging.INFO, logger='test'):
        run_test(p, stop=True)
    kinds = [(_classify(f"2026-10-04T20:00:00.000 INFO {r.getMessage()}") or (None,))[0] for r in caplog.records]
    assert [k for k in kinds if k and k.startswith('worm_test')] == ['worm_test_start', 'worm_test_end']


# ── the pose: a roll that separates M1 and M3 ─────────────────────────────────────────────────
def test_near_roll_0_the_test_rotates_to_25_deg_first_and_back_when_finished(tmp_path, cfg):
    p = fake_polaris(tmp_path, roll=5.0)
    run_test(p)
    assert p.rolls == [25.0, 5.0] and p._cm.test_data[PROFILE_TEST]['test_status'] == 'COMPLETED'
    assert len(p.synced_while_rolling) == 2 and p._sm.recorded == []     # syncs while rotating: ignored, not recorded
    assert all(t.done() and t.exception() is None for t in p.synced_while_rolling)   # nor applied (FakeSM would raise)


def test_with_enough_roll_the_pose_is_left_alone(tmp_path, cfg):
    p = fake_polaris(tmp_path, roll=-30.0)
    run_test(p)
    assert p.rolls == []


def test_a_negative_roll_rotates_to_minus_25_and_a_stopped_test_does_not_rotate_back(tmp_path, cfg):
    p = fake_polaris(tmp_path, roll=-8.0)
    run_test(p, stop=True)
    assert p.rolls == [-25.0]


def test_a_roll_move_that_does_not_finish_stops_the_test(tmp_path, cfg):
    p = fake_polaris(tmp_path, roll=0.0, roll_move_finishes=False)
    asyncio.run(asyncio.wait_for(Polaris.worm_profile_test(p), 5))
    assert p._cm.test_data[PROFILE_TEST]['test_status'] == 'STOPPED' and p._sm.worm_test is None
    assert p.calls == ['start_tracking', 'stop_tracking']
