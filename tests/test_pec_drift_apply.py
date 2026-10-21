"""
Where the PEC drift correction is applied (SyncManager.step_pec_drift, every PID control step).

Each tick it does two things with the same step: shifts the present value (q_syncguide_B) and publishes a feed-forward
velocity (omega_pec_B) that PID.feed_forward() turns into motor rates. The feed-forward is used only while tracking,
so the present-value shift must be too: a converged model applies nothing outside TRACK (not just because a goto or
tracking-off happens to reset it).
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

import control
from control_pec import PecInhibit
from kinematics import azaltroll_to_theta_ik
from sim_digital_twin import Twin

POSE = (180.0, 45.0, 0.0)
RATE = 1e-3                         # deg/s, a converged drift model's rate on each axis


def converge(sm):
    """Put the drift model in its applying state, as after enough good guide corrections."""
    for ax in (sm._pec_ra, sm._pec_dec):
        ax.inhibit = PecInhibit.VALID
        ax.rate = RATE
    sm._pec_active = True
    sm._pec_t0 = sm._pec_last_apply = control.time.monotonic()


def twin(monkeypatch):
    tw = Twin(monkeypatch, config={'advanced_pec_drift': True, 'coordinated_speed_control': True})
    tw.place(azaltroll_to_theta_ik(*POSE))
    return tw


def test_a_converged_drift_model_applies_nothing_while_not_tracking(monkeypatch):
    tw = twin(monkeypatch)
    sm = tw.polaris._sm
    assert tw.pid.mode != 'TRACK'
    converge(sm)
    before = sm.q_syncguide_B
    tw.run(5)
    assert (sm.q_syncguide_B * before.inverse).normalised.degrees < 1e-9
    assert not np.any(sm.omega_pec_B)


def test_while_tracking_it_shifts_the_present_value_and_feeds_forward_the_same_step(monkeypatch):
    tw = twin(monkeypatch)
    tw.start_tracking()
    tw.run(2)
    sm = tw.polaris._sm
    converge(sm)
    before = sm.q_syncguide_B
    tw.run(5)
    moved = (sm.q_syncguide_B * before.inverse).normalised.degrees
    assert moved > 0.5 * RATE * 5                               # ~ the rate on both axes, for 5 s
    assert np.any(sm.omega_pec_B) and np.any(tw.pid.omega_pec)
