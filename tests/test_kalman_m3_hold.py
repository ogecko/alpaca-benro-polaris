"""
The Kalman filter takes M3's 518 value as a measurement only when it refreshes (KalmanFilter._m3_rows), while M3 is
commanded faster than KF_M3_AWARE_MIN_DPS.

The Polaris sends 518 every 0.2 s but M3's value in it is sample-and-hold, refreshed every ~0.6 s. Taken as a fresh
measurement each time, the held value pulled the estimate back to where M3 was: during a 4 deg/s roll the reported
pointing swung ~100' (hardware test 2026-10-19: 97') while the camera moved ~20', and the coordinated path's reference
carried a fixed 0.18 s M3 delay to match. Slower (tracking, small corrections) every 518 is a measurement as before:
refresh-only there made the legacy controller's tracking swing and a below-horizon 5' correction time out.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import logging
import time

import numpy as np
import pytest

from config import Config
from control import KalmanFilter, KF_M3_AWARE_MIN_DPS, KF_M3_HOLD_MAX_S, KF_M3_REFRESH_DEG

ALL, NO_M3 = [0, 1, 2, 3, 4, 5], [0, 1, 3, 4]
FAST = np.array([0.0, 0.0, 4.0])                   # deg/s commanded: a roll
SLOW = np.array([0.0, 0.0, KF_M3_AWARE_MIN_DPS / 2])


KF_CONFIG = {                                     # driver/config.toml
    'kf_measure_noise': [0.0031622776601683794, 0.00630957344480193, 0.01584893192461114, 0.001584893192461114,
                         0.0031622776601683794, 0.2547885891542383],
    'kf_process_noise': [5.011872336272725e-05, 7.943282347242822e-05, 0.00012589254117941674, 0.0001, 0.0001, 0.0001],
    'kf_goto_noise_scale': 0.1, 'measurement_dt': 0.2, 'measurement_catchup_max_dt': 2.0, 'log_position': False,
}


@pytest.fixture
def kf(monkeypatch):
    for key, value in KF_CONFIG.items():
        monkeypatch.setattr(Config, key, value, raising=False)
    clock = {'t': 100.0}
    monkeypatch.setattr(time, 'monotonic', lambda: clock['t'])
    f = KalmanFilter(logging.getLogger('test'), np.zeros(6))
    f.clock = clock
    return f


def rows(kf, m3, omega_ref, t, omega3=0.0):
    kf.clock['t'] = t
    theta, omega = np.array([[10.0], [45.0], [m3]]), np.array([[0.0], [0.0], [omega3]])
    return kf._m3_rows(theta, omega, omega_ref), float(omega[2, 0])


def test_a_held_m3_value_is_not_a_measurement_while_m3_moves_fast(kf):
    rows(kf, 20.0, FAST, 100.0)                                            # a refresh
    assert rows(kf, 20.0, FAST, 100.2)[0] == NO_M3                         # the held value repeated
    assert rows(kf, 20.0, FAST, 100.4)[0] == NO_M3
    got, omega3 = rows(kf, 22.4, FAST, 100.6, omega3=12.0)                 # refreshed: 2.4 deg in 0.6 s
    assert got == ALL
    assert omega3 == pytest.approx(4.0)                                    # its rate across the refresh, not the step


def test_slower_every_518_is_a_measurement_as_before(kf):
    rows(kf, 20.0, SLOW, 100.0)
    assert rows(kf, 20.0, SLOW, 100.2)[0] == ALL
    got, omega3 = rows(kf, 20.0 + KF_M3_REFRESH_DEG * 2, SLOW, 100.4, omega3=0.01)
    assert got == ALL and omega3 == 0.01                                   # its own velocity measurement kept


def test_no_refresh_for_the_hold_max_means_m3_is_current_again(kf):
    rows(kf, 20.0, FAST, 100.0)
    assert rows(kf, 20.0, FAST, 100.0 + KF_M3_HOLD_MAX_S - 0.1)[0] == NO_M3
    assert rows(kf, 20.0, FAST, 100.0 + KF_M3_HOLD_MAX_S + 0.1)[0] == ALL  # nearly still: its value is current


def test_observe_carries_m3_on_between_refreshes(kf):
    """Between refreshes the state follows the commanded speed (predict) instead of the held value."""
    kf.observe([10.0, 45.0, 20.0], [0.0, 0.0, 4.0], FAST)
    for k in range(1, 3):
        kf.clock['t'] = 100.0 + 0.2 * k
        kf.predict(FAST)
        kf.observe([10.0, 45.0, 20.0], [0.0, 0.0, 0.0], FAST)             # held
    assert float(kf.x[2, 0]) > 20.0 + 0.5                                  # carried on, not pulled back to 20


# ── on the twin ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_fast_roll_reports_the_pointing_without_the_m3_hold_swing(monkeypatch):
    """A +45 roll at Alt 61 (4 deg/s, M1/M3 FAST calibrated): the reported Az/Alt follows the camera. With every 518
    a measurement it swung 106' while the camera moved 22'; now 21' and 17' (twin, 2026-10-19)."""
    from kinematics import azaltroll_to_theta_ik, azaltroll_to_q, q_to_azaltroll, quaternion_difference, theta_to_q
    from sim_digital_twin import Twin
    sep = lambda a, b: quaternion_difference(azaltroll_to_q(a[0], a[1], 0.0), azaltroll_to_q(b[0], b[1], 0.0))[0] * 60
    tw = Twin(monkeypatch, config={"coordinated_speed_control": True}, seed=0, calibrated=True)
    tw.place(azaltroll_to_theta_ik(180.0, 61.0, 0.0))
    tw.run(3)
    p, sm = tw.polaris, tw.polaris._sm
    true_azalt = lambda: q_to_azaltroll(sm.alignQ_B2T * theta_to_q(*tw.true_theta))[:2]
    true0, rep0 = true_azalt(), (p._p_azimuth, p._p_altitude)
    p.goto_complete_at = None
    tw.pid.set_alpha_target({'roll': 45.0})
    tw.pid.set_goto_complete_callback(p.markGotoAsComplete)
    worst = [0.0, 0.0]

    def rec(t):
        worst[0] = max(worst[0], sep(rep0, (p._p_azimuth, p._p_altitude)))
        worst[1] = max(worst[1], sep(true0, true_azalt()))
    t0 = tw.clock.t
    while tw.clock.t - t0 < 30 and p.goto_complete_at is None:
        tw.run(0.2, on_measure=rec)
    done = p.goto_complete_at
    tw.close()
    assert done is not None and done - t0 < 18.0, done
    assert worst[0] < 40.0, f"reported pointing swung {worst[0]:.0f}'"     # every 518 a measurement: 106'
    assert worst[1] < 25.0, f"camera moved {worst[1]:.0f}'"                # the 0.18 s M3 delay: 22'
