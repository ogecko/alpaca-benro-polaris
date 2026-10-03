"""
Worm gear periodic error for the digital twin's simulated guiders (tests/sim_guider.Worm): the true output angle
of each motor = the angle the MCU reports + a periodic error in that motor's own angle (period THETA, 6.67 deg for
a 54-tooth worm), so the error's period in time depends on each motor's rate and mixes through the kinematics.
The driver only ever sees the MCU's angle, as on the real mount.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

from sim_guider import Worm


def test_worm_error_is_periodic_in_each_motors_angle():
    w = Worm(amplitude_arcsec=(40.0, 30.0, 50.0), theta_deg=360 / 54, h2=0.3, seed=1)
    th = np.array([10.0, 20.0, 30.0])
    for i in range(3):
        shifted = th.copy(); shifted[i] += 360 / 54
        assert w.error_deg(shifted) == pytest.approx(w.error_deg(th), abs=1e-12)


def test_worm_amplitude_per_motor():
    w = Worm(amplitude_arcsec=(40.0, 0.0, 50.0), theta_deg=6.0, h2=0.0, seed=2)
    angles = np.linspace(0, 6.0, 721)
    for i, a in enumerate((40.0, 0.0, 50.0)):
        e = [w.error_deg(np.where(np.arange(3) == i, x, 0.0))[i] * 3600 for x in angles]
        assert max(e) == pytest.approx(a, abs=0.5)


def test_motor_errors_are_independent():
    w = Worm(amplitude_arcsec=(40.0, 40.0, 40.0), theta_deg=6.0, seed=3)
    base = w.error_deg(np.array([1.0, 2.0, 3.0]))
    moved = w.error_deg(np.array([1.0, 2.0, 4.5]))       # only M3 moves
    assert moved[0] == base[0] and moved[1] == base[1] and moved[2] != base[2]
