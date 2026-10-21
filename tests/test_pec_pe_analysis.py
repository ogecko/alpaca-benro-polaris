"""
Tests for utility/pe_analysis.py -- per-motor periodic-error analysis over the extracted segment
datasets (utility/extract_segments.py): worm-angle and time scans.

Synthetic segments carry a known worm error on one motor (period THETA of that motor's angle) at
different motor rates, so a per-motor angle period and a fixed time period can be told apart.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import numpy as np
import pandas as pd
import pytest

from pe_analysis import Segment, theta_scan, time_scan, load_segments

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
    best = {m: float(scan[m].idxmax()) for m in ('M1', 'M3')}
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


def write_segment(dirpath, session, k, t, ra, dec=None):
    th = np.column_stack([10 + t / 3600, 20 + 3 * t / 3600, 30 + 10 * t / 3600])
    d = pd.DataFrame({'t_sec': t, 'drift_ra_arcsec': ra, 'drift_dec_arcsec': ra * 0 if dec is None else dec,
                      'theta1': th[:, 0], 'theta2': th[:, 1], 'theta3': th[:, 2]})
    name = f'{session}__seg{k}.csv'
    d.to_csv(dirpath / name, index=False)
    return {'session': session, 'segment': k, 'file': name}


def sync_times(burst_at=(), burst_n=25, minutes=150, interval=90.0, fast=6.0):
    """Plate-solve times: one every `interval` s, with a burst of `burst_n` solves `fast` s apart at each burst_at s."""
    t, x = [], 0.0
    bursts = sorted(burst_at)
    while x < minutes * 60:
        if bursts and x >= bursts[0]:
            bursts.pop(0)
            for _ in range(burst_n):
                t.append(x)
                x += fast
        t.append(x)
        x += interval
    return np.array(t)


def test_a_leading_rapid_solve_burst_and_its_settling_are_dropped(tmp_path):
    t = sync_times(burst_at=(0.0,))
    ra = 2.0 * t / 60 + np.where(t < 160, 140.0 * t / 60, 0.0)          # the burst over-counts ~140"/min
    pd.DataFrame([write_segment(tmp_path, 'alpaca.a', 0, t, ra)]).to_csv(tmp_path / 'index.csv', index=False)
    s, = load_segments(str(tmp_path), min_minutes=60, drop_bursts=True, settle_s=300)
    assert s.name == 'alpaca.a#0'
    assert s.t[0] == 0.0 and np.min(np.diff(s.t)) >= 30                  # rebased, no fast solves left
    burst_end = t[np.where(np.diff(t) < 30)[0].max() + 1]                 # last solve of the fast run
    assert len(s.t) == int(np.sum(t >= burst_end + 300))                  # kept: from burst end + settle


def test_a_mid_segment_burst_splits_the_segment(tmp_path):
    t = sync_times(burst_at=(0.0, 140 * 60), minutes=300)
    ra = 2.0 * t / 60
    pd.DataFrame([write_segment(tmp_path, 'alpaca.b', 3, t, ra)]).to_csv(tmp_path / 'index.csv', index=False)
    segs = load_segments(str(tmp_path), min_minutes=60, drop_bursts=True, settle_s=300)
    assert [s.name for s in segs] == ['alpaca.b#3.1', 'alpaca.b#3.2']
    assert all(np.min(np.diff(s.t)) >= 30 for s in segs)


def test_pulse_guided_segments_are_dense_by_nature_and_kept_whole(tmp_path):
    t = np.arange(0, 2 * 3600, 2.0)
    pd.DataFrame([write_segment(tmp_path, 'alpaca.c', 0, t, np.sin(t / 900))]).to_csv(tmp_path / 'index.csv', index=False)
    s, = load_segments(str(tmp_path), min_minutes=60, drop_bursts=True)
    assert len(s.t) == len(t)


def test_duplicate_captures_are_loaded_once(tmp_path):
    t = sync_times()
    ra = 2.0 * t / 60 + 5 * np.sin(t / 900)
    rows = [write_segment(tmp_path, 'alpaca.x_first', 1, t, ra), write_segment(tmp_path, 'alpaca.y_copy', 4, t, ra)]
    pd.DataFrame(rows).to_csv(tmp_path / 'index.csv', index=False)
    assert [s.name for s in load_segments(str(tmp_path), min_minutes=60)] == ['alpaca.x_first#1']


def test_bursts_are_kept_by_default_now_that_their_phantom_pec_is_removed_at_extraction(tmp_path):
    t = sync_times(burst_at=(0.0,))
    pd.DataFrame([write_segment(tmp_path, 'alpaca.d', 0, t, 2.0 * t / 60)]).to_csv(tmp_path / 'index.csv', index=False)
    s, = load_segments(str(tmp_path), min_minutes=60)
    assert len(s.t) == len(t)
