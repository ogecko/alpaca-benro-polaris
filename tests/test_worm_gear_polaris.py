"""
The Polaris glue of the M#-WORM-GEAR test (polaris.Polaris.worm_gear_test, sync_telescope, worm_gear_approval), run
against a stand-in Polaris: syncs during a test go to SyncManager.record_worm_sync and nowhere else; the test turns
tracking on and back off, shows progress, fits, stores the result in the profile file and fills the row; approval
applies it and reloads the feed-forward.
"""
import asyncio
import json
import logging
import os
import sys
from types import SimpleNamespace
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

import polaris as polaris_mod
from polaris import Polaris
from control import CalibrationManager
from control_worm import WormCalibration


class Lifecycle:
    def __init__(self):
        self.stopped = False
        self.events = []
    def start(self): self.events.append('start')
    def reset(self): self.events.append('reset')
    def should_stop(self): return self.stopped


class FakeSM:
    def __init__(self, path):
        self.worm_test = None
        self.path = path
        self.recorded = []
        self.reloaded = 0
    def worm_profile_path(self): return self.path
    def record_worm_sync(self, *a): self.recorded.append(a)
    def reload_worm_ff(self): self.reloaded += 1
    def sync_az_alt(self, *a): raise AssertionError('applied to the alignment model during a worm gear test')


def fake_polaris(tmp_path):
    p = SimpleNamespace(lifecycle=Lifecycle(), _sm=FakeSM(str(tmp_path / 'worm_profile.json')),
                        _cm=CalibrationManager(False), logger=logging.getLogger('test'), _tracking=False, calls=[])
    p._cm.createTestDataFromBaseline()
    async def start_tracking():
        p._tracking = True; p.calls.append('start_tracking')
    async def stop_tracking():
        p._tracking = False; p.calls.append('stop_tracking')
    p.start_tracking, p.stop_tracking = start_tracking, stop_tracking
    p.radec2altaz = lambda ra, dec: (45.0, 180.0)
    p.worm_gear_approval = lambda axis, approved: Polaris.worm_gear_approval(p, axis, approved)
    return p


@pytest.fixture
def cfg(monkeypatch):
    for k, v in dict(advanced_control=True, advanced_tracking=True, advanced_alignment=True, pec_worm_ff=False).items():
        monkeypatch.setattr(polaris_mod.Config, k, v, raising=False)


def sweep_syncs(test, rng):
    """Feed the running test what record_worm_sync would: a 60" worm on the motor's angle."""
    while not test.done:
        pos = test.positions[test.index]
        angle = 40.0 + pos
        err = 60.0 * np.sin(2 * np.pi * angle / 6.0 + np.radians(120.0)) + rng.normal(0, 2.0)
        test.on_sync({'t': float(len(test.samples)), 'angle': angle, 'err_arcsec': err, 'sensitivity': 0.9})


def test_sync_during_a_test_is_recorded_not_applied(tmp_path, cfg):
    p = fake_polaris(tmp_path)
    p._sm.worm_test = WormCalibration(1)
    asyncio.run(Polaris.sync_telescope(p, a_ra=5.0, a_dec=-20.0))
    assert p._sm.recorded == [(5.0, -20.0, 180.0, 45.0)]


def test_worm_gear_test_runs_fits_stores_and_fills_the_row(tmp_path, cfg):
    p = fake_polaris(tmp_path)
    p._cm.pendingWormGearTest(1, ['M2-WORM-GEAR'])
    rng = np.random.default_rng(0)

    async def run():
        task = asyncio.create_task(Polaris.worm_gear_test(p, 1))
        while p._sm.worm_test is None:
            await asyncio.sleep(0.01)
        assert p._tracking and p.calls == ['start_tracking']
        await asyncio.sleep(0.6)
        assert p._cm.test_data['M2-WORM-GEAR']['test_status'] == 'PENDING 0/49'
        sweep_syncs(p._sm.worm_test, rng)
        await asyncio.wait_for(task, 5)
    asyncio.run(run())

    assert p.calls == ['start_tracking', 'stop_tracking'] and p._sm.worm_test is None
    assert p.lifecycle.events == ['start', 'reset']
    row = p._cm.test_data['M2-WORM-GEAR']
    assert row['test_status'] == 'COMPLETED'
    assert row['test_result'].endswith('°') and row['test_change'] == 'new' and 'rms n48' in row['test_stdev']
    d = json.load(open(p._sm.path))
    cal = d['calibration']['M2']
    assert cal['amplitude_arcsec'] == pytest.approx(60.0, abs=3.0) and cal['phase_deg'] == pytest.approx(120.0, abs=3.0)
    assert len(cal['samples']) == 49 and not cal['applied']

    p._cm.on_worm_gear_approval = p.worm_gear_approval
    p._cm.toggleApproval(1, ['M2-WORM-GEAR'])
    assert row['test_status'] == 'APPROVED' and p._sm.reloaded == 1
    assert json.load(open(p._sm.path))['angle_reference'] == {'M2': 'zeta'}
    p._cm.toggleApproval(1, ['M2-WORM-GEAR'])
    assert row['test_status'] == 'REJECTED' and p._sm.reloaded == 2
    assert json.load(open(p._sm.path))['motors']['M2'] == [0.0, 0.0]


def test_stopping_early_keeps_tracking_as_it_was_and_reports_stopped(tmp_path, cfg):
    p = fake_polaris(tmp_path)
    p._tracking = True

    async def run():
        task = asyncio.create_task(Polaris.worm_gear_test(p, 0))
        while p._sm.worm_test is None:
            await asyncio.sleep(0.01)
        p.lifecycle.stopped = True
        await asyncio.wait_for(task, 5)
    asyncio.run(run())
    assert p.calls == [] and p._tracking
    assert p._cm.test_data['M1-WORM-GEAR']['test_status'] == 'STOPPED'
    assert not os.path.exists(p._sm.path)                       # nothing recorded: nothing written


def test_an_empty_run_keeps_the_previous_result(tmp_path, cfg):
    from control_worm import store_calibration
    p = fake_polaris(tmp_path)
    store_calibration(p._sm.path, 1, {'status': 'COMPLETED', 'coef': [1.0, 2.0], 'checks': {'n': 48}})

    async def run():
        task = asyncio.create_task(Polaris.worm_gear_test(p, 1))
        while p._sm.worm_test is None:
            await asyncio.sleep(0.01)
        p.lifecycle.stopped = True
        await asyncio.wait_for(task, 5)
    asyncio.run(run())
    assert json.load(open(p._sm.path))['calibration']['M2']['coef'] == [1.0, 2.0]


def test_no_syncs_times_out_as_no_data(tmp_path, cfg, monkeypatch):
    p = fake_polaris(tmp_path)
    monkeypatch.setattr(polaris_mod, 'WormCalibration',
                        lambda axis: WormCalibration(axis, no_sync_timeout_s=0.3))   # 2 minutes, shortened
    asyncio.run(asyncio.wait_for(Polaris.worm_gear_test(p, 1), 5))
    assert p._cm.test_data['M2-WORM-GEAR']['test_status'] == 'NO DATA'
    assert p._sm.worm_test is None and p.calls == ['start_tracking', 'stop_tracking']


def test_pulse_guiding_during_a_test_aborts_it_and_is_not_applied(tmp_path, cfg, monkeypatch):
    monkeypatch.setattr(polaris_mod.Config, 'advanced_pulse_guiding', True, raising=False)
    p = fake_polaris(tmp_path)
    p._sm.worm_test = WormCalibration(1)
    p._sm.process_pulse_guide_axis = lambda *a: (_ for _ in ()).throw(AssertionError('pulse applied'))
    p._lock = __import__('threading').Lock()
    Polaris.pulse_guide(p, 0, 500)
    assert p._sm.worm_test.aborted and 'pulse guide' in p._sm.worm_test.abort_reason


def test_start_and_end_log_lines_mark_the_test_for_the_log_catalog(tmp_path, cfg, caplog):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
    from catalog_logs import _classify
    p = fake_polaris(tmp_path)
    p._tracking = True

    async def run():
        task = asyncio.create_task(Polaris.worm_gear_test(p, 2))
        while p._sm.worm_test is None:
            await asyncio.sleep(0.01)
        p.lifecycle.stopped = True
        await asyncio.wait_for(task, 5)
    with caplog.at_level(logging.INFO, logger='test'):
        asyncio.run(run())
    kinds = [(_classify(f"2026-10-04T20:00:00.000 INFO {r.getMessage()}") or (None,))[0] for r in caplog.records]
    assert [k for k in kinds if k and k.startswith('worm_test')] == ['worm_test_start', 'worm_test_end']
