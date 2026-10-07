"""
utility/worm_analysis.py, used by analyse_worm_profile.ipynb and analyse_tracking.ipynb:

  * a test's fit sample by sample: the fit's parts (each motor's worm, the rest) add up to it, and fit + residual is
    the measurement
  * the worm feed-forward rebuilt from PECLOG's motor angles and pose matches the driver's own split along RA and Dec
  * each motor's worm is recovered from an RA/Dec series with drift and PEC resets
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
import pytest

from kinematics import theta_to_q, q_to_azaltroll, calc_equatorial_axes_B
from quaternion import Q as Quaternion
from control_worm import WormFeedForward
from worm_analysis import test_fit_details as fit_details, wff_coupling, predicted_wff, worm_terms, wff_matches_profile
from test_worm_profile import synthetic_test

LAT = -33.65
COEF = np.array([[20.0, -25.0], [-60.0, 5.0], [40.0, 30.0]])            # a sin + b cos per motor, arcsec
COEF2 = np.array([[20.0, -25.0, 0.0, 0.0], [-60.0, 5.0, -12.0, -6.0], [40.0, 30.0, 0.0, 0.0]])   # with M2's 2nd harmonic


def test_the_fit_details_add_up():
    d = fit_details(synthetic_test())
    assert len(d) == 2 * 47
    assert np.allclose(d['fitted'] + d['residual'], d['measured'])
    assert np.allclose(d['worm_M1'] + d['worm_M2'] + d['worm_M3'] + d['nuisance'], d['fitted'])
    assert d['residual'].std() == pytest.approx(2.0, abs=0.8)


def peclog(n=400, offset=(150.0, 45.0, 0.0), reset_at=250, seed=0):
    """PECLOG-like rows: motors turning as tracking does, a fixed alignment, the logged pose and the driver's wff."""
    rng = np.random.default_rng(seed)
    align = Quaternion(axis=[0.1, 0.2, 1.0], degrees=12.0) * Quaternion(axis=[1.0, 0.0, 0.0], degrees=2.0)
    ff = WormFeedForward(worm_theta=6.0, harmonics=(1,), coef=COEF, angle_reference={'M1': 'zeta', 'M2': 'zeta', 'M3': 'zeta'})
    zeta_off = np.array([-179.5, 45.1, 0.0])
    rows = []
    for i in range(n):
        zeta = np.array([10.0, 5.0, -3.0]) + np.array([0.02, 0.004, 0.012]) * i
        theta = zeta + zeta_off
        cam = (align * theta_to_q(*theta)).normalised
        az, alt, roll = q_to_azaltroll(cam)
        q = ff.correction_q(theta, zeta_offset=zeta_off)                     # as the driver: base-frame rotation
        axes = calc_equatorial_axes_B(cam, align.inverse, LAT)
        c = np.linalg.solve(np.column_stack(axes), np.asarray(q.axis) * q.degrees) if q.degrees > 1e-12 else np.zeros(3)
        rows.append(dict(t_sec=15.0 * i, n=i - reset_at if i >= reset_at else i + 5, az=az, alt=alt, roll=roll,
                         **{f'theta_raw_{m + 1}': theta[m] for m in range(3)},
                         **{f'zeta_offset_{m + 1}': zeta_off[m] for m in range(3)},
                         wff_1=c[0] * 60, wff_2=c[1] * 60))
    return pd.DataFrame(rows)


def test_the_rebuilt_worm_feed_forward_matches_the_drivers_split():
    df = peclog()
    C, fit_err = wff_coupling(df, LAT)
    assert fit_err < 0.01                                                    # arcmin: a rigid alignment, recovered
    pred = predicted_wff(df, C, COEF, harmonics=(1,))
    logged = df[['wff_1', 'wff_2']].to_numpy()
    assert np.abs(pred - logged).max() < 0.002 * np.abs(logged).max() + 1e-6


def test_worm_terms_recover_the_profile_through_drift_and_resets():
    df = peclog()
    C, _ = wff_coupling(df, LAT)
    y = predicted_wff(df, C, COEF, harmonics=(1,))
    t = df['t_sec'].to_numpy() / 3600
    after_reset = (np.arange(len(df)) >= 250)[:, None]                     # the totals restart at the PEC reset
    y = y + np.column_stack([0.5 * t + 0.2 * t ** 2, -0.3 * t]) + np.where(after_reset, 1.0, 0.0)
    terms, rms = worm_terms(df, y, C, harmonics=(1,))
    for m, row in terms.iterrows():
        assert row['a'] == pytest.approx(COEF[m, 0], abs=0.5) and row['b'] == pytest.approx(COEF[m, 1], abs=0.5)
    assert rms < 1e-3


def test_worm_terms_fit_both_harmonics_by_default_as_the_driver_applies_them():
    """Real log 2026-10-06: fitting only 1st harmonics to a profile with M2's 2nd harmonic leaked it into the other
    motors (M1 9" for 32"); with both, the profile in use comes back."""
    df = peclog()
    C, _ = wff_coupling(df, LAT)
    y = predicted_wff(df, C, COEF2, harmonics=(1, 2))
    terms, rms = worm_terms(df, y, C)
    for m in range(3):
        for h in (1, 2):
            row = terms[(terms['motor'] == f'M{m + 1}') & (terms['harmonic'] == h)].iloc[0]
            assert row['a'] == pytest.approx(COEF2[m, 2 * h - 2], abs=0.5) and row['b'] == pytest.approx(COEF2[m, 2 * h - 1], abs=0.5)


def test_worm_terms_flag_motors_too_few_turns_to_separate():
    df = peclog(n=60)                                                          # M2 turns 0.04 deg a row: < 1 turn
    C, _ = wff_coupling(df, LAT)
    terms, _ = worm_terms(df, predicted_wff(df, C, COEF2, harmonics=(1, 2)), C)
    m2 = terms[terms['motor'] == 'M2'].iloc[0]
    assert m2['turns'] < 2 and not m2['reliable']


def test_the_logged_correction_is_checked_against_the_profile_directly():
    df = peclog()
    C, _ = wff_coupling(df, LAT)
    ok = wff_matches_profile(df, C, np.hstack([COEF, np.zeros((3, 2))]), harmonics=(1, 2))   # the profile peclog() used
    assert ok['corr'] > 0.999 and ok['rms_diff_arcsec'] < 0.5
    bad = wff_matches_profile(df, C, COEF2, harmonics=(1, 2))                  # a different profile: it shows
    assert bad['rms_diff_arcsec'] > 1.0


def test_each_term_reports_the_worm_phase_of_its_peak():
    from control_worm import peak_deg
    df = peclog()
    C, _ = wff_coupling(df, LAT)
    terms, _ = worm_terms(df, predicted_wff(df, C, COEF2, harmonics=(1, 2)), C)
    for t in terms.itertuples():
        assert t.peak == pytest.approx(peak_deg(t.a, t.b, harmonic=t.harmonic), abs=1e-6)

