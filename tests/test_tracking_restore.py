"""
Tracking restore after a driver restart (driver/tracking_restore.py, Polaris.restore_tracking_on_start):

  * the state saved while tracking (target, offsets, time, Polaris session fingerprint) round-trips through the file,
    written atomically; a change of tracking or target is saved at once, the time alone is not a change
  * it is restored only when it is recent, the Polaris is in the same session (518 - 517 offset), the mount is not
    parked / at a limit, advanced tracking is on and the target is above the horizon -- each refusal says why
  * restored: TRACK on the saved target, and the PID brings a mount that drifted degrees back onto it (twin)
  * refused: a mount still running its last SLOW command is stopped; a still one, or one the Polaris tracks by
    itself, or one this driver has started moving meanwhile, is left alone
"""
import asyncio
import json
import logging
import math
import os
import sys
from types import SimpleNamespace
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

import tracking_restore as tr
import polaris as polaris_mod
from polaris import Polaris

NOW = 1_800_000_000.0
OFFSET = [12.3, -0.4, 0.2]


def tracking_state(**kw):
    pid = SimpleNamespace(delta_sp=np.array([150.0, -40.0, 10.0]), delta_offst=np.zeros(3),
                          alpha_offst=np.zeros(3), gamma_offst=np.zeros(3), orbital_sp_name=None)
    state = tr.capture(True, pid, 0, OFFSET, now=NOW)
    state.update(kw)
    return state


def reason(state=None, **kw):
    args = dict(now=NOW + 30, zeta_raw_offset=OFFSET, pid_mode='IDLE', atpark=False, advanced=True, target_alt=40.0)
    args.update(kw)
    return tr.refuse_reason(tracking_state() if state is None else state, **args)


# ── the saved state ───────────────────────────────────────────────────────────────────────────
def test_state_round_trips_through_the_file(tmp_path):
    path = tmp_path / 'tracking_state.json'
    s = tracking_state()
    tr.save(s, path)
    assert tr.load(path) == json.loads(json.dumps(s))
    assert not os.path.exists(str(path) + '.tmp')                 # written via a temporary file


def test_missing_or_broken_file_is_no_state(tmp_path):
    assert tr.load(tmp_path / 'none.json') is None
    (tmp_path / 'bad.json').write_text('{"tracking": tru')
    assert tr.load(tmp_path / 'bad.json') is None


def test_only_tracking_and_target_changes_count_as_a_change():
    a, b = tracking_state(), tracking_state(saved_at=NOW + 100, zeta_raw_offset=[0, 0, 0])
    assert tr.change_key(a) == tr.change_key(b)
    assert tr.change_key(a) != tr.change_key(tracking_state(delta_sp=[151.0, -40.0, 10.0]))
    assert tr.change_key(a) != tr.change_key(tracking_state(tracking=False))


def test_not_tracking_saves_no_target():
    s = tr.capture(False, None, 0, OFFSET, now=NOW)
    assert s['tracking'] is False and 'delta_sp' not in s


# ── when to restore ───────────────────────────────────────────────────────────────────────────
def test_restores_a_recent_state_from_the_same_session():
    assert reason() is None


@pytest.mark.parametrize('state, kw, why', [
    (None, {}, 'no saved tracking state'),
    ('off', {}, 'not tracking'),
    ('', dict(advanced=False), 'advanced'),
    ('', dict(now=NOW + tr.MAX_AGE_S + 60), 'min old'),
    ('', dict(zeta_raw_offset=[12.3 + 0.5, -0.4, 0.2]), 'restarted or re-calibrated'),
    ('', dict(zeta_raw_offset=None), 'fingerprint'),
    ('', dict(atpark=True), 'parked'),
    ('', dict(pid_mode='LIMIT'), 'LIMIT'),
    ('', dict(pid_mode='PRESETUP'), 'PRESETUP'),
    ('', dict(target_alt=-5.0), 'below the horizon'),
])
def test_each_refusal_says_why(state, kw, why):
    s = {None: None, 'off': tr.capture(False, None, 0, OFFSET, now=NOW), '': tracking_state()}[state]
    args = dict(now=NOW + 30, zeta_raw_offset=OFFSET, pid_mode='IDLE', atpark=False, advanced=True, target_alt=40.0)
    args.update(kw)
    r = tr.refuse_reason(s, **args)
    assert r is not None and why in r, r


def test_session_fingerprint_wraps_at_360():
    assert reason(zeta_raw_offset=[12.3 - 360.0, -0.4, 0.2]) is None


def test_is_moving():
    assert not tr.is_moving([10.0, 20.0, 30.0], [10.001, 20.0, 30.0])
    assert tr.is_moving([10.0, 20.0, 30.0], [10.0, 20.02, 30.0])
    assert tr.is_moving([179.99, 0, 0], [-179.98, 0, 0])
    assert not tr.is_moving(None, [0, 0, 0])


# ── refused: stop a mount still running its last command ──────────────────────────────────────
class Motor:
    def __init__(self, calls):
        self.calls = calls
    async def stop(self):
        self.calls.append('stop')


class FakePolaris:
    """What _restore_or_stop reads; 517 angles change between the two samples when `moving`."""
    def __init__(self, moving, state, benro=False, tracking=False, mode='IDLE'):
        self.samples = iter([[10.0, 40.0, 0.0], [10.0 + (0.02 if moving else 0.0), 40.0, 0.0]])
        self._zeta = next(self.samples)
        self._zeta_raw_offset = OFFSET
        self._pid = SimpleNamespace(mode=mode)
        self.atpark, self._tracking_in_benro, self._tracking, self._slewing = False, benro, tracking, False
        self.lifecycle = SimpleNamespace(should_stop=lambda: False)
        self.logger = logging.getLogger('test')
        self.calls = []
        self._motors = {a: Motor(self.calls) for a in range(3)}
        self.state, self.restored = state, []
        self.radec2altaz = lambda ra, dec: (40.0, 180.0)

    @property
    def _zeta_meas(self):
        return self._zeta

    def next_sample(self):
        self._zeta = next(self.samples, self._zeta)

    async def _restore_tracking(self, state):
        self.restored.append(state)


@pytest.fixture
def run_check(monkeypatch):
    def run(p):
        for key in ('advanced_control', 'advanced_tracking'):
            monkeypatch.setattr(polaris_mod.Config, key, True, raising=False)
        monkeypatch.setattr(tr, 'load', lambda path=None: p.state)
        monkeypatch.setattr(tr, 'MOTION_WINDOW_S', 0.0)
        real_sleep = asyncio.sleep

        async def sleep(s):                                  # the motion window: the 517 angles move on
            p.next_sample()
            await real_sleep(0)
        monkeypatch.setattr(asyncio, 'sleep', sleep)
        asyncio.run(Polaris._restore_or_stop(p))
        return p
    return run


def test_refused_and_moving_stops_all_motors(run_check):
    p = run_check(FakePolaris(moving=True, state=tracking_state(saved_at=NOW - 3600)))
    assert p.calls == ['stop'] * 3 and not p.restored


def test_refused_and_still_is_left_alone(run_check):
    p = run_check(FakePolaris(moving=False, state=None))
    assert p.calls == [] and not p.restored


def test_refused_but_tracked_by_the_polaris_itself_is_left_alone(run_check):
    p = run_check(FakePolaris(moving=True, state=None, benro=True))
    assert p.calls == []


def test_refused_but_this_driver_moved_it_meanwhile_is_left_alone(run_check):
    p = run_check(FakePolaris(moving=True, state=None, tracking=True, mode='TRACK'))
    assert p.calls == []


def test_a_good_state_is_restored_not_stopped(run_check, monkeypatch):
    s = tracking_state()
    monkeypatch.setattr(tr.time, 'time', lambda: NOW + 30)
    p = run_check(FakePolaris(moving=True, state=s))
    assert p.restored == [s] and p.calls == []


# ── restored: the PID brings the mount back onto the saved target (twin) ──────────────────────
def test_restore_brings_a_drifted_mount_back_on_target(monkeypatch):
    from sim_digital_twin import Twin
    from kinematics import azaltroll_to_theta_ik
    from test_motion_outcomes import CANDIDATE, TRACK_POSE

    tw = Twin(monkeypatch, config=CANDIDATE)
    tw.place(azaltroll_to_theta_ik(*TRACK_POSE))
    tw.start_tracking()
    tw.run(20)
    state = tr.capture(True, tw.pid, 0, OFFSET)
    theta = np.array(tw.theta)

    # the restart: a fresh driver, the mount 2-3 deg off after running its last SLOW command for a few minutes
    tw2 = Twin(monkeypatch, config=CANDIDATE)
    tw2.place(theta + np.array([2.0, -1.5, 0.5]))
    p = tw2.polaris
    p.logger = logging.getLogger('test')

    async def start_tracking():
        tw2.start_tracking()
    p.start_tracking = start_tracking
    asyncio.run(Polaris._restore_tracking(p, state))
    assert tw2.pid.mode == 'TRACK' and p._tracking
    tw2.run(40)
    ra, dec = state['delta_sp'][0] / 15, state['delta_sp'][1]
    sep = math.hypot((ra - p.rightascension) * 15 * math.cos(math.radians(dec)), dec - p.declination) * 3600
    assert sep < 30, f'{sep:.0f}" from the restored target after 40 s'
