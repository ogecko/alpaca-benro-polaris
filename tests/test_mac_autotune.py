"""
kinematics.autotune_mac: fit the three MAC parameters (m2_tilt_dm2_amp, m2_tilt_dm2_zero, m3_tilt_dm1) to the sync
points, on a synthetic mount with known mechanical errors and alignment, from the parameters it starts with -- the
shipped config.toml values, or all zero (a mount whose MAC values were cleared).
"""
import math
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

from kinematics import (theta_to_q, q_to_azaltroll, azaltroll_to_theta_ik, MountModelParams,
                        get_mechanical_correction_q, autotune_mac)
from quaternion import Q as Quaternion

ZERO = dict(m3_tilt_dm2=0.0, m3_tilt_dm1=0.0, m3_tilt_dm3=0.0, m2_tilt_dm2_amp=0.0, m2_tilt_dm2_zero=0.0,
            m2_roll_coupling=0.0, m2_roll_zero=45.0, m1_offset=0.0, m2_offset=0.0, m3_offset=0.0)
SHIPPED = dict(ZERO, m3_tilt_dm1=-261.30, m2_tilt_dm2_amp=94.78, m2_tilt_dm2_zero=20.88)       # config.toml
TRUE = dict(ZERO, m3_tilt_dm1=-230.0, m2_tilt_dm2_amp=80.0, m2_tilt_dm2_zero=30.0)


def sync_points(n=10, seed=0, noise_arcsec=2.0):
    rng = np.random.default_rng(seed)
    params = MountModelParams.from_config(TRUE)
    align = (Quaternion(axis=[0, 0, 1], degrees=2.0) * Quaternion(axis=[1, 0, 0], degrees=0.5)).normalised
    entries = []
    for k in range(n):
        theta = np.array(azaltroll_to_theta_ik((360 * k / n + rng.uniform(-15, 15)) % 360, rng.uniform(30, 70),
                                               rng.uniform(-60, 60)), float)
        q = theta_to_q(*theta)
        corr, _ = get_mechanical_correction_q(q, params)
        a_az, a_alt, _ = q_to_azaltroll((align * corr * q).normalised)
        p_az, p_alt, p_roll = q_to_azaltroll(q)
        entries.append(dict(deleted=False, p_az=p_az, p_alt=p_alt, p_roll=p_roll,
                            a_az=a_az + rng.normal(0, noise_arcsec / 3600) / math.cos(math.radians(a_alt)),
                            a_alt=a_alt + rng.normal(0, noise_arcsec / 3600)))
    return entries


def same_m2_tilt(r):
    """amp sin(t2 - zero) == -amp sin(t2 - zero - 180): compare the fitted tilt as the same curve."""
    t2 = np.radians(np.linspace(0, 90, 50))
    fit = r['m2_tilt_dm2_amp'] * np.sin(t2 - np.radians(r['m2_tilt_dm2_zero']))
    true = TRUE['m2_tilt_dm2_amp'] * np.sin(t2 - np.radians(TRUE['m2_tilt_dm2_zero']))
    return np.abs(fit - true).max()


@pytest.mark.parametrize('start', [SHIPPED, ZERO], ids=['from the shipped values', 'from zero'])
def test_autotune_recovers_the_mechanical_errors(start):
    r = autotune_mac(sync_points(), MountModelParams.from_config(start))
    assert r['success'] and r['nit'] > 10
    assert r['m3_tilt_dm1'] == pytest.approx(TRUE['m3_tilt_dm1'], abs=2.0)          # arcmin
    assert same_m2_tilt(r) < 2.0                                                    # arcmin
    assert r['rms_after'] < 0.1                                                     # arcmin: down to the noise
