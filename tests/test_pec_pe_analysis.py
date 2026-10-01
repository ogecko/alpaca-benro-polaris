"""
Tests for utility/pe_analysis.py -- per-motor periodic-error analysis over the extracted segment
datasets (utility/extract_segments.py): worm-angle scan and forecast skill of candidate models.

Synthetic segments carry a known worm error on one motor (period THETA of that motor's angle) at
different motor rates, so a per-motor angle period and a fixed time period can be told apart.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import numpy as np
import pandas as pd
import pytest

from pe_analysis import Segment, theta_scan, time_scan, best_theta, forecast_skill, rolling_forecast, load_segments

THETA = 6.0


def synthetic(name, session, rates, worm_motor, amp=60.0, hours=2.5, dt=30.0, noise=3.0, seed=0, trend=(5.0, -3.0)):
    rng = np.random.default_rng(seed)
    t = np.arange(0, hours * 3600, dt)
    theta = np.column_stack([10 + r * t / 3600 for r in rates]) * np.array([1, 1, 1])
    phase = rng.uniform(0, 2 * np.pi)
    worm = amp * np.sin(2 * np.pi * theta[:, worm_motor] / THETA + phase)
    ra = trend[0] * t / 60 + worm + rng.normal(0, noise, len(t))
    dec = trend[1] * t / 60 + 0.5 * worm + rng.normal(0, noise, len(t))
    return Segment(name=name, session=session, t=t, ra=ra, dec=dec, theta=theta)


@pytest.fixture
def segs():
    # the worm on M3 at four different M3 rates -> time periods 18-45 min, never a fixed one
    out = [synthetic(f"s{k}", f"sess{k}", rates=(2.0, 3.0, r3), worm_motor=2, seed=k)
           for k, r3 in enumerate((8.0, 11.0, 14.0, 20.0))]
    # a worm on M1 in two more sessions
    out += [synthetic(f"m1_{k}", f"sessm1{k}", rates=(r1, 2.0, 3.0), worm_motor=0, seed=10 + k)
            for k, r1 in enumerate((9.0, 16.0))]
    return out


def test_scan_peaks_at_the_worm_angle_of_the_motor_carrying_it(segs):
    scan = theta_scan(segs, np.arange(3.0, 12.01, 0.25))
    best = best_theta(scan)
    assert best['M3'] == pytest.approx(THETA, abs=0.3)
    assert best['M1'] == pytest.approx(THETA, abs=0.3)


def test_scan_can_leave_out_a_session(segs):
    scan = theta_scan(segs, np.arange(3.0, 12.01, 0.25), exclude_session='sess0')
    assert scan.attrs['n_segments'] == len(segs) - 1


def time_signal_segments():
    """A fixed 28-min period in time while M3 turns at very different rates."""
    rng = np.random.default_rng(3)
    segs = []
    for k, r3 in enumerate((7.0, 10.0, 14.0, 21.0)):
        t = np.arange(0, 2.5 * 3600, 30.0)
        theta = np.column_stack([10 + 2 * t / 3600, 10 + 3 * t / 3600, 10 + r3 * t / 3600])
        sig = 60 * np.sin(2 * np.pi * t / (28 * 60) + rng.uniform(0, 6))
        segs.append(Segment(f"t{k}", f"s{k}", t, sig + rng.normal(0, 3, len(t)), 0.5 * sig, theta))
    return segs


def test_time_scan_finds_a_fixed_time_period():
    scan = time_scan(time_signal_segments(), np.arange(10, 80.1, 1) * 60)
    assert scan['power'].idxmax() / 60 == pytest.approx(28, abs=1.5)


def test_a_time_signal_scores_higher_on_the_time_scan_than_any_motor_angle_scan():
    segs = time_signal_segments()
    angle = theta_scan(segs, np.arange(3.0, 12.01, 0.25))
    time = time_scan(segs, np.arange(10, 80.1, 1) * 60)
    assert time['power'].max() > 1.5 * angle['M3'].max()


def test_a_worm_signal_scores_higher_on_its_motor_angle_scan_than_the_time_scan(segs):
    m3_only = [s for s in segs if s.session.startswith('sess') and not s.session.startswith('sessm1')]
    angle = theta_scan(m3_only, np.arange(3.0, 12.01, 0.25))
    time = time_scan(m3_only, np.arange(10, 80.1, 1) * 60)
    assert angle['M3'].max() > 1.5 * time['power'].max()


def test_forecast_prefers_the_worm_model_on_worm_data(segs):
    thetas = {'M1': THETA, 'M2': THETA, 'M3': THETA}
    res = pd.DataFrame([forecast_skill(s, thetas) for s in segs])
    assert (res['worm'] < res['trend']).mean() >= 0.8
    assert res['worm'].median() < 0.5 * res['trend'].median()
    assert res['worm'].median() < res['time_34_17'].median()


def test_forecast_reports_holdout_rms_for_every_model(segs):
    r = forecast_skill(segs[0], {'M1': THETA, 'M2': THETA, 'M3': THETA})
    assert set(r) >= {'segment', 'trend', 'time_34_17', 'worm', 'worm_h2', 'fast_motors'}
    assert r['fast_motors'] == ['M3']


def test_load_segments_reads_the_extracted_datasets(tmp_path):
    t = np.arange(0, 4000, 20.0)
    d = pd.DataFrame({'timestamp': pd.Timestamp('2026-09-01') + pd.to_timedelta(t, 's'), 't_sec': t,
                      'drift_ra_arcsec': np.sin(t / 500), 'drift_dec_arcsec': np.cos(t / 500),
                      'theta1': 1 + t / 3600, 'theta2': 2.0 + 0 * t, 'theta3': 3 + 10 * t / 3600})
    d.to_csv(tmp_path / 'alpaca.a__seg1.csv', index=False)
    d.iloc[:100].to_csv(tmp_path / 'alpaca.b__seg0.csv', index=False)          # too short
    pd.DataFrame([{'session': 'alpaca.a', 'segment': 1, 'file': 'alpaca.a__seg1.csv'},
                  {'session': 'alpaca.b', 'segment': 0, 'file': 'alpaca.b__seg0.csv'}]).to_csv(tmp_path / 'index.csv', index=False)
    segs = load_segments(str(tmp_path), min_minutes=60)
    assert [s.name for s in segs] == ['alpaca.a#1']
    assert segs[0].rates == pytest.approx([1.0, 0.0, 10.0], abs=1e-6)


def test_rolling_forecast_favours_the_worm_on_worm_data(segs):
    thetas = {'M1': THETA, 'M2': THETA, 'M3': THETA}
    res = pd.DataFrame([rolling_forecast(s, thetas) for s in segs])
    assert (res['worm'] < 0.6 * res['trend']).all()
    assert (res['worm'] < res['time_34_17']).mean() >= 0.8


def test_rolling_forecast_on_pure_drift_gives_the_models_nothing_to_gain():
    t = np.arange(0, 3 * 3600, 30.0)
    rng = np.random.default_rng(1)
    theta = np.column_stack([10 + 2 * t / 3600, 10 + 3 * t / 3600, 10 + 13 * t / 3600])
    s = Segment('d', 'd', t, 10 * t / 60 + rng.normal(0, 3, len(t)), -4 * t / 60 + rng.normal(0, 3, len(t)), theta)
    r = rolling_forecast(s, {'M1': THETA, 'M2': THETA, 'M3': THETA})
    assert r['worm'] == pytest.approx(r['trend'], rel=0.25)
    assert r['n_windows'] >= 10
