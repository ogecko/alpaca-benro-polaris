"""
The worm profile test on the digital twin (tests/sim_digital_twin.py), with gear worms the driver cannot see
(tests/sim_guider.Worm, 1st and 2nd harmonic on every motor). Plate solves of the true pointing arrive every 15 s through
SyncManager.record_worm_sync (what Polaris.sync_telescope calls while the test runs):

  * a sync is kept once every motor has settled; each kept sync steps all three motors on their schedule by moving the
    tracked target (PID_Controller.step_motor_targets), and sidereal tracking holds it in between: TRACK throughout
  * syncs are recorded, not applied: no sync-guide correction, no QUEST point; PEC and the worm feed-forward pause
  * the joint fit recovers every motor's worm on its MCU angles, at a pose with roll and near the pole
  * anything else moving the mount ends the test
"""
import numpy as np
import pytest

from sim_digital_twin import Twin
from sim_guider import Worm, ARCSEC
from kinematics import azaltroll_to_theta_ik, theta_to_q, q_to_azaltroll
from control_worm import WormProfileTest, WormFeedForward, fit_worm_profile, POSITIONS

POSE = (90.0, 40.0, 30.0)
CONFIG = {"coordinated_speed_control": True, "advanced_sync_guiding": True, "advanced_alignment": True,
          "advanced_pec_drift": True, "advanced_pec_worm": True}
WORM = Worm(amplitude_arcsec=(35.0, 60.0, 50.0), theta_deg=6.0, h2=0.15, seed=11)


def true_azalt(tw, worm):
    theta = tw.mcu.position
    theta = theta + worm.error_deg(theta)
    az, alt, _ = q_to_azaltroll(tw.polaris._sm.alignQ_B2T * theta_to_q(*theta))
    return az, alt


def run_profile_test(monkeypatch, pose, worm=WORM, interval_s=15.0, noise_arcsec=2.0, seed=0):
    tw = Twin(monkeypatch, config=CONFIG, seed=seed)
    tw.place(azaltroll_to_theta_ik(*pose))
    tw.start_tracking()
    tw.run(30)
    sm, pid = tw.polaris._sm, tw.pid
    rng = np.random.default_rng(seed)
    start = tw.theta
    sm.worm_test = WormProfileTest()
    modes = set()
    while not sm.worm_test.done:
        tw.run(interval_s, on_measure=lambda t: modes.add(pid.mode))
        az, alt = true_azalt(tw, worm)
        az += rng.normal(0, noise_arcsec / ARCSEC) / max(np.cos(np.radians(alt)), 0.2)
        alt += rng.normal(0, noise_arcsec / ARCSEC)
        ra, dec = tw.polaris.altaz2radec(alt, az)
        sm.record_worm_sync(ra, dec, az, alt)
    test, sm.worm_test = sm.worm_test, None
    return tw, test, start, modes


def h1_error(result, worm, m):
    A = worm.amp[m] * ARCSEC
    a, b = result['motors'][f'M{m + 1}']['coef'][:2]
    return float(np.hypot(a - A * np.cos(worm.phi[m]), b - A * np.sin(worm.phi[m])))


@pytest.mark.slow
@pytest.mark.parametrize('pose', [POSE, (180.0, 45.0, -7.0)], ids=['roll 30', 'near the pole'])
def test_the_profile_test_recovers_every_motors_worm(monkeypatch, pose):
    tw, test, start, modes = run_profile_test(monkeypatch, pose)
    assert len(test.samples) == len(POSITIONS) and modes == {'TRACK'}
    sm = tw.polaris._sm
    assert sm.q_syncguide_B.degrees < 1e-9                                  # recorded, not applied
    assert not [e for e in sm.sync_history if not e.get('deleted')]
    r = fit_worm_profile([test.samples])
    assert r['status'] == 'COMPLETED', r['checks']
    for m in range(3):              # twin 2026-10-05, 4 noise seeds per pose: typically 1-7", worst 10.8" (M1 near pole)
        assert h1_error(r, WORM, m) < 12.0, (m, r['motors'])
    assert r['checks']['rms_arcsec'] < 5.0


def test_step_motor_targets_moves_each_motor_its_own_step(monkeypatch):
    tw = Twin(monkeypatch, config=CONFIG)
    tw.place(azaltroll_to_theta_ik(*POSE))
    tw.start_tracking()
    tw.run(20)
    before = tw.theta
    tw.pid.step_motor_targets([0.6, -0.45, 0.375])
    tw.run(15)
    tracked = tw.theta - before - np.array([0.6, -0.45, 0.375])           # what is left is 15 s of sidereal tracking
    assert np.all(np.abs(tracked) < 0.1)
    assert tw.pid.mode == 'TRACK'


def test_the_test_pauses_pec_and_the_worm_feed_forward(monkeypatch):
    tw = Twin(monkeypatch, config=CONFIG)
    tw.place(azaltroll_to_theta_ik(*POSE))
    sm = tw.polaris._sm
    ff = WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=np.full((3, 2), 30.0))
    monkeypatch.setattr(sm, '_worm_ff_profile', lambda: ff)
    sm.update_worm_ff(tw.theta)
    assert sm.corrQ_WFF.degrees > 0
    sm.worm_test = WormProfileTest()
    sm.update_worm_ff(tw.theta)
    assert sm.corrQ_WFF.degrees == 0
    sm.omega_pec_B = np.array([1e-3, 0.0, 0.0])
    tw.start_tracking()
    tw.run(2)
    assert not np.any(tw.pid.omega_pec)


def started(monkeypatch):
    tw = Twin(monkeypatch, config=CONFIG)
    tw.place(azaltroll_to_theta_ik(*POSE))
    tw.start_tracking()
    tw.run(5)
    tw.polaris._sm.worm_test = WormProfileTest()
    return tw


@pytest.mark.parametrize('action, reason', [
    (lambda tw: tw.goto_altaz(80.0, 40.0), 'goto'),
    (lambda tw: tw.slew_relative(ra=0.1), 'goto'),
    (lambda tw: tw.pid.set_pid_mode('PARKING'), 'PARKING'),
    (lambda tw: tw.pid.set_tracking_off(), 'AUTO'),
    (lambda tw: (tw.pid.set_axis_velocities({'ra': 0.01}), tw.run(1)), 'jog'),
    (lambda tw: tw.pid.rotator_move_relative(5.0), 'rotator'),
])
def test_moving_the_mount_otherwise_aborts_the_test(monkeypatch, action, reason):
    tw = started(monkeypatch)
    test = tw.polaris._sm.worm_test
    action(tw)
    assert test.aborted and reason in test.abort_reason


def test_the_tests_own_steps_and_tracking_do_not_abort_it(monkeypatch):
    tw = started(monkeypatch)
    test = tw.polaris._sm.worm_test
    tw.pid.step_motor_targets([0.6, -0.45, 0.375])
    tw.run(20)
    assert not test.aborted


def test_pid_mode_changes_before_the_sync_manager_exists(monkeypatch):
    """Polaris.__init__ builds the PID (which sets its mode) before the SyncManager: the worm test checks must cope."""
    tw = Twin(monkeypatch, config=CONFIG)
    sm = tw.polaris._sm
    del tw.polaris._sm
    tw.pid.set_pid_mode('IDLE')
    assert not tw.pid.worm_test_active()
    tw.polaris._sm = sm
