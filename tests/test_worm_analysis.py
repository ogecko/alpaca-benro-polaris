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
    assert len(d) == 2 * 50
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



# ── worm_gains: how much of each motor's profile the mount really had ─────────────────────────────────────────────
def tracking_rows(hours=3.0, dt=2.0, rates_arcsec_s=(20.0, 8.0, 15.0), roll_deg=25.0):
    """PECLOG-like rows of a long track: each motor turning several worm periods, a fixed alignment, a PEC reset."""
    align = Quaternion(axis=[0.1, 0.2, 1.0], degrees=12.0)
    zeta_off = np.array([-179.5, 45.1, 0.0])
    n = int(hours * 3600 / dt)
    i = np.arange(n)
    zeta = np.array([10.0, 20.0, roll_deg]) + np.outer(i * dt, np.array(rates_arcsec_s) / 3600)
    rows = []
    for k in range(n):
        theta = zeta[k] + zeta_off
        az, alt, roll = q_to_azaltroll((align * theta_to_q(*theta)).normalised)
        rows.append(dict(t_sec=dt * k, n=k - n // 2 if k >= n // 2 else k + 5, az=az, alt=alt, roll=roll,
                         **{f'theta_raw_{m + 1}': theta[m] for m in range(3)},
                         **{f'zeta_offset_{m + 1}': zeta_off[m] for m in range(3)}))
    return pd.DataFrame(rows)


def shifted(coef, deg):
    """Each harmonic's a sin + b cos advanced by deg of its own phase."""
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    out = np.array(coef, float).copy()
    for j in range(out.shape[1] // 2):
        a, b = out[:, 2 * j].copy(), out[:, 2 * j + 1].copy()
        out[:, 2 * j], out[:, 2 * j + 1] = a * c - b * s, a * s + b * c
    return out


@pytest.fixture(scope='module')
def track():
    df = tracking_rows()
    C, _ = wff_coupling(df, LAT)
    return df, C


def test_worm_gains_recover_each_motors_amplitude_and_phase_through_drift_and_resets(track):
    from worm_analysis import worm_gains
    df, C = track
    true = COEF2.copy()
    true[0] *= 1.0
    true[1] = 1.1 * shifted(COEF2[1:2], 20.0)[0]                          # M2: 10% stronger, 20 deg later
    true[2] *= 1.25                                                       # M3: 25% stronger (as 2B on 2026-10-11)
    y = predicted_wff(df, C, true)
    t = df['t_sec'].to_numpy() / 3600
    y = y + np.column_stack([0.5 * t + 0.2 * t ** 2, -0.3 * t])           # slow drift (arcmin)
    y = y + np.where((df['n'].diff() < 0).cumsum().to_numpy()[:, None] > 0, 1.0, 0.0)   # totals restart at a PEC reset
    y = y + np.random.default_rng(0).normal(0, 2 / 60, y.shape)           # 2" of noise
    gains, summary = worm_gains(df, C, COEF2, y)
    g = gains.set_index('motor')
    assert g.loc['M1', 'ratio'] == pytest.approx(1.0, abs=0.05) and abs(g.loc['M1', 'phase_deg']) < 3
    assert g.loc['M2', 'ratio'] == pytest.approx(1.1, abs=0.05) and g.loc['M2', 'phase_deg'] == pytest.approx(20, abs=3)
    assert g.loc['M3', 'ratio'] == pytest.approx(1.25, abs=0.05) and abs(g.loc['M3', 'phase_deg']) < 3
    assert g['reliable'].all()
    assert summary['left_fitted'] < summary['left_now']                    # the fitted gains explain what was left


def test_worm_gains_of_an_exact_profile_are_one(track):
    from worm_analysis import worm_gains
    df, C = track
    gains, summary = worm_gains(df, C, COEF2, predicted_wff(df, C, COEF2))
    assert np.allclose(gains['gain'], 1.0, atol=0.01) and np.allclose(gains['quadrature'], 0.0, atol=0.01)
    assert summary['left_now'] < 0.05                                      # "/min
