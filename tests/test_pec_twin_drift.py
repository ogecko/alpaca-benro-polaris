"""
PEC outcome tests on the digital twin (tests/sim_digital_twin.py), with a known drift the driver
cannot see injected into the true pointing (tests/sim_guider.py) -- the stand-in for periodic or
model error. The twin knows the true pointing, so these check PEC end to end: the real
SyncManager (PEC model, pulse and sync guiding), PID feed-forward and Ki, and the v2 speed controller.

Guards (must hold):
  * pulse guiding (PHD2-like guider): PEC learns a constant drift with the right sign and takes
    over the correction from the guider
  * sync guiding (plate solve + sync every 2 min, no guide scope): PEC cuts the error between solves
Goals (expected to fail until fixed):
  * sync guiding with the default worm-period harmonics (pec_n_harmonics = 2) does not degrade over
    time on a drift with no periodic part -- today the harmonics fit the sawtooth between solves and
    PEC overshoots (RA 4.0" at 20-30 min -> 7.4" at 50-60 min; with pec_n_harmonics = 0 it holds ~5")

Documented behaviour:
  * an ASCOM East/North pulse moves the mount to -RA/-Dec: a pulse shifts the PV and the PID moves
    the mount back to the target, so the physical move is opposite to the reported RA/Dec jump.
    Guiders calibrate the direction, so guiding is unaffected.

The drift simulations take 20-40 s each and are marked slow: run them with `uv run pytest --runslow`.
"""
import numpy as np
import pytest

from sim_digital_twin import Twin
from sim_guider import SimGuider, SimPlateSolver, ARCSEC
from kinematics import azaltroll_to_theta_ik

TRACK_POSE = (135.0, 45.0, 0.0)
DRIFT_RA, DRIFT_DEC = 20.0, 10.0          # arcsec/min, constant
PEC_CONFIG = {"coordinated_speed_control": True, "advanced_pec": True, "advanced_pulse_pec_tuning": True,
              "advanced_sync_guiding": True, "advanced_alignment": True}


def constant_drift(t):
    return DRIFT_RA * t / 60 / ARCSEC, DRIFT_DEC * t / 60 / ARCSEC


def tracking_twin(monkeypatch, config):
    tw = Twin(monkeypatch, config={**PEC_CONFIG, **config}, seed=0)
    tw.place(azaltroll_to_theta_ik(*TRACK_POSE))
    tw.start_tracking()
    tw.run(30)
    return tw


def pec_rate_arcsec_min(tw):
    sm = tw.polaris._sm
    return sm._pec_ra._applied_rate * ARCSEC * 60, sm._pec_dec._applied_rate * ARCSEC * 60


def test_pulses_move_the_mount_opposite_to_the_ascom_direction(monkeypatch):
    tw = tracking_twin(monkeypatch, {"advanced_pec": False})
    g = SimGuider(tw)
    g.calibrate()
    tw.close()
    assert (g.east_sign, g.north_sign) == (-1, -1)


@pytest.mark.slow
def test_pulse_guiding_pec_learns_a_constant_drift_and_relieves_the_guider(monkeypatch):
    tw = tracking_twin(monkeypatch, {"pec_mode": "rls", "pec_n_harmonics": 0})
    g = SimGuider(tw, drift=constant_drift)
    g.start()
    g.guide(30 * 60)
    pec_ra, pec_dec = pec_rate_arcsec_min(tw)
    guider_ra, guider_dec = g.correction_rate_arcsec_min(0, since_s=20 * 60), g.correction_rate_arcsec_min(1, since_s=20 * 60)
    tw.close()
    # same sign and close to the drift the guider had to correct without PEC (+20/+10 "/min)
    assert pec_ra == pytest.approx(DRIFT_RA, rel=0.25)
    assert pec_dec == pytest.approx(DRIFT_DEC, rel=0.25)
    # the guider is left with a small part of it
    assert abs(guider_ra) < 0.25 * DRIFT_RA
    assert abs(guider_dec) < 0.25 * DRIFT_DEC


def sync_guided_rms(monkeypatch, config, minutes=30, since_min=10):
    tw = tracking_twin(monkeypatch, config)
    s = SimPlateSolver(tw, drift=constant_drift, interval_s=120)
    s.start()
    s.guide(minutes * 60)
    rms = s.error_rms_arcsec(since_s=since_min * 60), s
    tw.close()
    return rms


@pytest.mark.slow
def test_sync_guiding_pec_cuts_the_error_between_solves(monkeypatch):
    (off_ra, off_dec), _ = sync_guided_rms(monkeypatch, {"advanced_pec": False})
    (on_ra, on_dec), _ = sync_guided_rms(monkeypatch, {"pec_mode": "rls", "pec_n_harmonics": 0})
    assert on_ra < 0.4 * off_ra, f"RA {on_ra:.1f}\" with PEC vs {off_ra:.1f}\" without"
    assert on_dec < 0.5 * off_dec, f"Dec {on_dec:.1f}\" with PEC vs {off_dec:.1f}\" without"


@pytest.mark.slow
@pytest.mark.xfail(strict=False, reason="goal: worm-period harmonics fit the sync sawtooth and PEC overshoots")
def test_goal_sync_guiding_pec_with_harmonics_does_not_degrade(monkeypatch):
    tw = tracking_twin(monkeypatch, {"pec_mode": "rls", "pec_n_harmonics": 2, "pec_tau_sec": 1260})
    s = SimPlateSolver(tw, drift=constant_drift, interval_s=120)
    s.start()
    s.guide(30 * 60)
    early = np.hypot(*s.error_rms_arcsec(since_s=20 * 60))
    s.guide(30 * 60)
    late = np.hypot(*s.error_rms_arcsec(since_s=50 * 60))
    tw.close()
    assert late <= 1.2 * early, f"total RMS {early:.1f}\" at 20-30 min -> {late:.1f}\" at 50-60 min"


# ---------------------------------------------------------------------------------------------------
# PEC model choice in closed loop (2026-10-01): current RLS + 2 harmonics (tau 21 min) vs EMA tau 5 min.
# The archive benchmark (utility/analyse_pec_catalog.ipynb) found EMA ~5-10 min best and the harmonic model
# no better than no PEC; these check it with the PID, speed controller and a guider in the loop.
# ---------------------------------------------------------------------------------------------------
import math                                                         # noqa: E402
from sim_guider import Worm                                         # noqa: E402

CURRENT_PEC = {"pec_mode": "rls", "pec_n_harmonics": 2, "pec_tau_sec": 1260}
EMA_5MIN = {"pec_mode": "ema", "pec_n_harmonics": 0, "pec_tau_sec": 300}
PEC_OFF = {"advanced_pec": False}


def reversing_drift(t, period_s=80 * 60):
    """RA rate 4 + 20 sin(wt), Dec rate -2 + 12 cos(wt) arcsec/min: steady drift whose rate reverses."""
    w = 2 * math.pi / period_s
    return ((4.0 * t / 60 + 20.0 / 60 / w * (1 - math.cos(w * t))) / ARCSEC,
            (-2.0 * t / 60 + 12.0 / 60 / w * math.sin(w * t)) / ARCSEC)


def slow_drift(t, period_s=180 * 60):
    w = 2 * math.pi / period_s
    return ((3.0 * t / 60 + 8.0 / 60 / w * (1 - math.cos(w * t))) / ARCSEC,
            (-2.0 * t / 60 + 5.0 / 60 / w * math.sin(w * t)) / ARCSEC)


def guided_rms(monkeypatch, kind, config, drift, pose=TRACK_POSE, worm=None, minutes=100, warm=20):
    tw = Twin(monkeypatch, config={**PEC_CONFIG, **config}, seed=0)
    tw.place(azaltroll_to_theta_ik(*pose))
    tw.start_tracking()
    tw.run(30)
    g = (SimGuider(tw, drift=drift, seeing_arcsec=0.5, worm=worm) if kind == 'pulse'
         else SimPlateSolver(tw, drift=drift, interval_s=120, solve_noise_arcsec=2.0, worm=worm))
    g.start()
    g.guide(minutes * 60)
    rms = float(np.hypot(*g.error_rms_arcsec(since_s=warm * 60)))
    tw.close()
    return rms


@pytest.mark.slow
def test_sync_guiding_ema_beats_the_harmonic_model_on_a_reversing_drift(monkeypatch):
    off = guided_rms(monkeypatch, 'sync', PEC_OFF, reversing_drift)
    current = guided_rms(monkeypatch, 'sync', CURRENT_PEC, reversing_drift)
    ema = guided_rms(monkeypatch, 'sync', EMA_5MIN, reversing_drift)
    # twin 2026-10-01: off 19.5", current 49.9" (worse than off), EMA 5 min 10.0"
    assert ema < 0.7 * off, f"EMA {ema:.1f}\" vs off {off:.1f}\""
    assert ema < 0.5 * current, f"EMA {ema:.1f}\" vs current {current:.1f}\""


@pytest.mark.slow
def test_pulse_guiding_ema_is_no_worse_than_off_and_beats_the_harmonic_model(monkeypatch):
    off = guided_rms(monkeypatch, 'pulse', PEC_OFF, reversing_drift)
    current = guided_rms(monkeypatch, 'pulse', CURRENT_PEC, reversing_drift)
    ema = guided_rms(monkeypatch, 'pulse', EMA_5MIN, reversing_drift)
    # twin: off 2.35", current 2.95", EMA 5 min 2.23"
    assert ema <= 1.02 * off and ema < current


@pytest.mark.slow
@pytest.mark.parametrize("kind", ["sync", "pulse"])
@pytest.mark.parametrize("pose", [(180.0, 50.0, 0.0), (150.0, 25.0, -30.0)], ids=["M1+M3 fast", "M1+M2 fast"])
def test_with_worm_gears_ema_is_never_meaningfully_worse_than_the_harmonic_model(monkeypatch, kind, pose):
    # 40" worm (54 teeth, 6.67 deg) on every motor + a slow model drift: the worm's period is 21-41 min here
    worm = Worm(amplitude_arcsec=(40.0, 40.0, 40.0), h2=0.35, seed=1)
    current = guided_rms(monkeypatch, kind, CURRENT_PEC, slow_drift, pose=pose, worm=worm, minutes=120, warm=30)
    ema = guided_rms(monkeypatch, kind, EMA_5MIN, slow_drift, pose=pose, worm=worm, minutes=120, warm=30)
    assert ema <= 1.05 * current, f"EMA {ema:.1f}\" vs current {current:.1f}\""
