"""
Worm feed-forward on the digital twin (tests/sim_digital_twin.py) with a gear worm the driver cannot see
(tests/sim_guider.Worm: true output angle = MCU angle + error, 6.0 deg worm on M2 and M3):

  * a profile fitted from the guide corrections (utility/pe_analysis.fit_worm) is the
    physical gear error -- same sign and scale -- so it can be written to the profile file as it is
  * with the profile, sync guiding (plate solve every 2 min) no longer chases the worm between solves
  * with the profile, pulse guiding (PHD2-like) has less error and the guider corrects less

Errors are the guiders' RA/Dec coordinate errors (RA in RA-coordinate arcsec, so larger than on the sky away from the
equator). The simulations take 30-60 s each: run them with `uv run pytest --runslow`.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import numpy as np
import pytest

from sim_digital_twin import Twin, LAT
from sim_guider import SimGuider, SimPlateSolver, Worm, ARCSEC
from kinematics import azaltroll_to_theta_ik
from control_worm import WormFeedForward
import control_worm

POSE = (180.0, 50.0, 0.0)                 # M3 turns ~15 deg/hr: the 6 deg worm repeats every ~24 min
WORM = Worm(amplitude_arcsec=(0.0, 30.0, 50.0), theta_deg=6.0, h2=0.35, seed=1)
CONFIG = {"coordinated_speed_control": True, "advanced_pulse_pec_tuning": True, "advanced_sync_guiding": True,
          "advanced_alignment": True, "pec_tau_sec": 450}


def true_profile(worm):
    """The twin's worm as a profile: A [sin(phi + p) + h2 sin(2 phi + q)] -> per harmonic sin and cos coefficients."""
    coef = np.zeros((3, 4))
    for m in range(3):
        A = worm.amp[m] * ARCSEC
        coef[m] = [A * np.cos(worm.phi[m]), A * np.sin(worm.phi[m]),
                   A * worm.h2 * np.cos(worm.psi[m]), A * worm.h2 * np.sin(worm.psi[m])]
    return WormFeedForward(worm_theta=worm.theta, harmonics=(1, 2), coef=coef)


def test_true_profile_reproduces_the_twin_worm():
    ff = true_profile(WORM)
    for x in np.linspace(0, 12, 9):
        th = np.array([10.0, 20.0 + x, 30.0 + x])
        assert np.allclose(ff.error_deg(th), WORM.error_deg(th), atol=1e-12)


def guide(monkeypatch, kind, config, minutes, record=False):
    tw = Twin(monkeypatch, config={**CONFIG, **config}, seed=0)
    tw.place(azaltroll_to_theta_ik(*POSE))
    tw.start_tracking()
    tw.run(30)
    g = (SimGuider(tw, seeing_arcsec=0.5, worm=WORM) if kind == 'pulse'
         else SimPlateSolver(tw, interval_s=120, solve_noise_arcsec=2.0, worm=WORM))
    g.start()
    rec = []
    if record:
        frame = g._frame
        g._frame = lambda t: (frame(t), rec.append((tw.clock.t, *tw.mcu.position)))
    g.guide(minutes * 60)
    tw.close()
    return g, np.array(rec)


@pytest.mark.slow
def test_a_profile_fitted_from_the_guide_corrections_is_the_physical_gear_error(monkeypatch):
    from pe_analysis import fit_worm
    g, rec = guide(monkeypatch, 'pulse', {"advanced_pec": False}, minutes=90, record=True)
    c = np.array(g.corrections)                                     # (t, axis, deg) as PEC sees them
    t, th = rec[:, 0], rec[:, 1:4]
    ra, dec = ([c[(c[:, 0] <= x) & (c[:, 1] == ax), 2].sum() * ARCSEC for x in t] for ax in (0, 1))
    prof = fit_worm([(t, np.array(ra), np.array(dec), th, LAT)], worm_theta=6.0, harmonics=(1, 2))
    grid = np.zeros((300, 3))
    grid[:, 2] = np.linspace(0, 12, 300)
    fitted, true = prof.motor_error(grid)[:, 2], WORM.error_deg(grid)[:, 2] * ARCSEC
    assert np.polyfit(true, fitted, 1)[0] == pytest.approx(1.0, abs=0.05)    # same sign, same scale
    assert np.corrcoef(true, fitted)[0, 1] > 0.99


@pytest.fixture
def profile_path(tmp_path):
    path = tmp_path / 'worm_profile.json'
    true_profile(WORM).save(path)
    return str(path)


def rms_since(g, minutes):
    return float(np.hypot(*g.error_rms_arcsec(since_s=minutes * 60)))


@pytest.mark.slow
def test_sync_guiding_with_the_feed_forward_no_longer_chases_the_worm(monkeypatch, profile_path):
    cfg = {"advanced_pec": True}
    off, _ = guide(monkeypatch, 'sync', cfg, minutes=50)                       # no profile: no worm correction
    monkeypatch.setattr(control_worm, "WORM_PROFILE_PATH", profile_path)
    on, _ = guide(monkeypatch, 'sync', cfg, minutes=50)
    # twin 2026-10-03: off ~180", on ~11" (the no-worm level: 2" solve noise, near the pole)
    assert rms_since(on, 10) < 0.15 * rms_since(off, 10), f'on {rms_since(on, 10):.1f}" off {rms_since(off, 10):.1f}"'


@pytest.mark.slow
def test_pulse_guiding_with_the_feed_forward_has_less_error_and_guider_effort(monkeypatch, profile_path):
    cfg = {"advanced_pec": False}
    off, _ = guide(monkeypatch, 'pulse', cfg, minutes=50)                      # no profile: no worm correction
    monkeypatch.setattr(control_worm, "WORM_PROFILE_PATH", profile_path)
    on, _ = guide(monkeypatch, 'pulse', cfg, minutes=50)
    effort = lambda g: sum(abs(c[2]) for c in g.corrections if c[0] - g.t0 >= 10 * 60)
    # twin 2026-10-03 (90 min): error 6.0" -> 5.0", corrections -14%
    assert rms_since(on, 10) < 0.92 * rms_since(off, 10), f'on {rms_since(on, 10):.2f}" off {rms_since(off, 10):.2f}"'
    assert effort(on) < 0.92 * effort(off)
