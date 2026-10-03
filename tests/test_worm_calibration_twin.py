"""
The M#-WORM calibration test on the digital twin (tests/sim_digital_twin.py), with a gear worm the driver cannot see
(tests/sim_guider.Worm). Plate solves of the true pointing arrive every 10 s through SyncManager.record_worm_sync (what
Polaris.sync_telescope calls while a test runs):

  * each kept sync steps the test motor 0.5 deg by moving the tracked target (PID_Controller.step_motor_target), and
    sidereal tracking holds it in between: TRACK throughout, the other motors only track
  * syncs are recorded, not applied: no sync-guide correction, no QUEST point; PEC and the worm feed-forward pause
  * the fit recovers the twin's worm amplitude and phase on the motor's MCU angles
"""
import numpy as np
import pytest

from sim_digital_twin import Twin
from sim_guider import Worm, ARCSEC
from kinematics import azaltroll_to_theta_ik, theta_to_q, q_to_azaltroll
from control_worm import WormCalibration, fit_worm_calibration

POSE = (180.0, 50.0, 0.0)
CONFIG = {"coordinated_speed_control": True, "advanced_sync_guiding": True, "advanced_alignment": True,
          "advanced_pec": True, "pec_worm_ff": False}


def true_azalt(tw, worm):
    theta = tw.mcu.position
    theta = theta + worm.error_deg(theta)
    az, alt, _ = q_to_azaltroll(tw.polaris._sm.alignQ_B2T * theta_to_q(*theta))
    return az, alt


def run_calibration(monkeypatch, axis, worm, interval_s=10.0, noise_arcsec=2.0, seed=0):
    tw = Twin(monkeypatch, config=CONFIG, seed=seed)
    tw.place(azaltroll_to_theta_ik(*POSE))
    tw.start_tracking()
    tw.run(30)
    sm, pid = tw.polaris._sm, tw.pid
    rng = np.random.default_rng(seed)
    start = tw.theta
    sm.worm_test = WormCalibration(axis)
    trace = []
    while not sm.worm_test.done:
        tw.run(interval_s, on_measure=lambda t: trace.append((pid.mode, *t.theta)))
        az, alt = true_azalt(tw, worm)
        az += rng.normal(0, noise_arcsec / ARCSEC)
        alt += rng.normal(0, noise_arcsec / ARCSEC)
        ra, dec = tw.polaris.altaz2radec(alt, az)
        sm.record_worm_sync(ra, dec, az, alt)
    test, sm.worm_test = sm.worm_test, None
    return tw, test, start, trace


@pytest.mark.slow
def test_worm_calibration_recovers_the_m2_worm(monkeypatch):
    worm = Worm(amplitude_arcsec=(30.0, 60.0, 30.0), theta_deg=6.0, h2=0.0, seed=3)     # M1, M3 worms: tracking drift
    tw, test, start, trace = run_calibration(monkeypatch, 1, worm)
    s = test.samples
    assert len(s) == len(test.positions)

    # TRACK throughout, the test motor swept +/-6 deg around the start and back, the others only tracking
    modes = {m for m, *_ in trace}
    assert modes == {'TRACK'}
    th = np.array([x[1:] for x in trace])
    assert th[:, 1].max() - start[1] == pytest.approx(6.0, abs=0.3)
    assert th[:, 1].min() - start[1] == pytest.approx(-6.0, abs=0.3)
    assert abs(th[-1, 1] - start[1]) < 0.5
    t = np.arange(len(th))
    for m in (0, 2):                                            # the others just track: smooth, not the M2 sweep
        assert np.abs(th[:, m] - np.polyval(np.polyfit(t, th[:, m], 2), t)).max() < 0.3

    # recorded, not applied
    sm = tw.polaris._sm
    assert sm.q_syncguide_B.degrees < 1e-9
    assert not [e for e in sm.sync_history if not e.get('deleted')]

    r = fit_worm_calibration([x['angle'] for x in s], [x['err_arcsec'] for x in s], [x['t'] for x in s],
                             [x['direction'] for x in s])
    assert r['status'] == 'COMPLETED'
    assert r['amplitude_arcsec'] == pytest.approx(60.0, abs=8.0)
    want = np.degrees(worm.phi[1]) % 360
    assert (r['phase_deg'] - want + 180) % 360 - 180 == pytest.approx(0.0, abs=8.0)
    assert r['checks']['best_worm_theta'] == pytest.approx(6.0, abs=0.15)


def test_step_motor_target_moves_only_that_motor(monkeypatch):
    tw = Twin(monkeypatch, config=CONFIG)
    tw.place(azaltroll_to_theta_ik(*POSE))
    tw.start_tracking()
    tw.run(20)
    before = tw.theta
    tw.pid.step_motor_target(0, 0.5)
    tw.run(15)
    tracked = tw.theta - before - np.array([0.5, 0.0, 0.0])     # what is left is 15 s of sidereal tracking
    assert np.all(np.abs(tracked) < 0.1)
    assert tw.pid.mode == 'TRACK'


def test_worm_test_pauses_pec_and_the_worm_feed_forward(monkeypatch):
    tw = Twin(monkeypatch, config={**CONFIG, "pec_worm_ff": True})
    tw.place(azaltroll_to_theta_ik(*POSE))
    sm = tw.polaris._sm
    from control_worm import WormFeedForward
    ff = WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=np.full((3, 2), 30.0))
    monkeypatch.setattr(sm, '_worm_ff_profile', lambda: ff)
    sm.update_worm_ff(tw.theta)
    assert sm.corrQ_WFF.degrees > 0
    sm.worm_test = WormCalibration(1)
    sm.update_worm_ff(tw.theta)
    assert sm.corrQ_WFF.degrees == 0
    sm.omega_pec_B = np.array([1e-3, 0.0, 0.0])
    tw.start_tracking()
    tw.run(2)
    assert not np.any(tw.pid.omega_pec)


@pytest.mark.slow
@pytest.mark.parametrize('axis', [0, 2])
def test_worm_calibration_recovers_the_m1_and_m3_worms(monkeypatch, axis):
    amp = np.full(3, 30.0)
    amp[axis] = 60.0
    worm = Worm(amplitude_arcsec=tuple(amp), theta_deg=6.0, h2=0.0, seed=5)
    tw, test, start, trace = run_calibration(monkeypatch, axis, worm)
    s = test.samples
    print(f"M{axis + 1} sensitivity {np.mean([x['sensitivity'] for x in s]):.2f}")
    r = fit_worm_calibration([x['angle'] for x in s], [x['err_arcsec'] for x in s], [x['t'] for x in s],
                             [x['direction'] for x in s])
    assert r['status'] == 'COMPLETED'
    assert r['amplitude_arcsec'] == pytest.approx(60.0, abs=10.0)
    want = np.degrees(worm.phi[axis]) % 360
    assert (r['phase_deg'] - want + 180) % 360 - 180 == pytest.approx(0.0, abs=10.0)


def started(monkeypatch):
    tw = Twin(monkeypatch, config=CONFIG)
    tw.place(azaltroll_to_theta_ik(*POSE))
    tw.start_tracking()
    tw.run(5)
    tw.polaris._sm.worm_test = WormCalibration(1)
    return tw


@pytest.mark.parametrize('action, reason', [
    (lambda tw: tw.goto_altaz(170.0, 40.0), 'goto'),
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
    tw.pid.step_motor_target(1, 0.5)
    tw.run(20)
    assert not test.aborted
