"""
Tests for frame_shift_components() in utility/analyse_helpers.py: KFLOG's base-frame minus corrected-frame
motor angle (theta_meas_raw - theta_ref_raw) split into the steps at each sync, the smooth change between
syncs, and the fast ripple.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import numpy as np
import pandas as pd
import pytest

from analyse_helpers import frame_shift_components


def kflog(n_s=3600, dt=0.2, steps=(), ramp_arcsec_per_s=(0.0, 0.0, 0.0), ripple=2.0, theta2=40.0, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(0, n_s, dt)
    ts = pd.Timestamp('2026-09-01T20:00') + pd.to_timedelta(t, 's')
    d = {'timestamp': ts}
    for i in (1, 2, 3):
        shift = ramp_arcsec_per_s[i - 1] * t + rng.normal(0, ripple, len(t))
        for at, size in steps:
            shift = shift + np.where(t >= at, size[i - 1], 0.0)
        ref = 100.0 + 10 * i + 0.003 * t
        d[f'θ_ref_raw_{i}'] = ref if i != 2 else np.full(len(t), theta2)
        d[f'θ_meas_raw_{i}'] = d[f'θ_ref_raw_{i}'] + shift / 3600
    return pd.DataFrame(d)


def test_steps_at_syncs_are_measured():
    steps = [(600, (60.0, -10.0, -55.0)), (1200, (40.0, 5.0, -35.0))]
    kf = kflog(steps=steps)
    syncs = kf['timestamp'].iloc[0] + pd.to_timedelta([600, 1200], 's')
    comp, summary = frame_shift_components(kf, syncs)
    assert summary.loc['M1', 'sync steps sum "'] == pytest.approx(100.0, abs=3)
    assert summary.loc['M3', 'sync steps sum "'] == pytest.approx(-90.0, abs=3)
    assert summary.loc['M1', 'syncs'] == 2


def test_ramp_between_syncs_is_separated_from_the_steps():
    kf = kflog(steps=[(1800, (100.0, 0.0, 0.0))], ramp_arcsec_per_s=(0.1, 0.0, -0.05))
    syncs = kf['timestamp'].iloc[0] + pd.to_timedelta([1800], 's')
    _, summary = frame_shift_components(kf, syncs)
    assert summary.loc['M1', 'between syncs "'] == pytest.approx(0.1 * 3600, rel=0.05)
    assert summary.loc['M3', 'between syncs "'] == pytest.approx(-0.05 * 3600, rel=0.05)


def test_fast_ripple_rms():
    kf = kflog(ripple=5.0)
    comp, summary = frame_shift_components(kf, pd.Series([], dtype='datetime64[ns]'))
    assert summary.loc['M2', 'ripple rms "'] == pytest.approx(5.0, rel=0.1)
    assert set(comp.columns) >= {'t_min', 'M1 shift', 'M1 staircase', 'M1 smooth', 'M1 ripple'}


def test_m1_m3_amplification_reported_from_theta2():
    _, s_low = frame_shift_components(kflog(theta2=5.0), pd.Series([], dtype='datetime64[ns]'))
    _, s_high = frame_shift_components(kflog(theta2=60.0), pd.Series([], dtype='datetime64[ns]'))
    assert s_low.attrs['m1_m3_amplification'] == pytest.approx(1 / np.sin(np.radians(5.0)), rel=0.01)
    assert s_high.attrs['m1_m3_amplification'] < 1.2


def test_wrap_through_360_is_not_a_step():
    kf = kflog()
    kf['θ_meas_raw_1'] = (kf['θ_meas_raw_1'] + 250) % 360          # crosses 360 during the run
    kf['θ_ref_raw_1'] = (kf['θ_ref_raw_1'] + 250) % 360
    _, summary = frame_shift_components(kf, pd.Series([], dtype='datetime64[ns]'))
    assert abs(summary.loc['M1', 'net change "']) < 20


def test_ramp_undone_by_next_sync_is_detected():
    from analyse_helpers import ramp_vs_next_step
    # between syncs the shift ramps by +r, then each sync steps it back by -r: PEC pushing, sync undoing it
    t_sync = np.arange(120, 3600, 120)
    t = np.arange(0, 3600, 0.2)
    ramp_rate = np.random.default_rng(2).normal(0.3, 0.2, len(t_sync) + 1)      # arcsec/s, varies per interval
    shift = np.zeros(len(t)); level = 0.0; last = 0.0
    edges = np.r_[0, t_sync, 3600]
    for k in range(len(edges) - 1):
        m = (t >= edges[k]) & (t < edges[k + 1])
        shift[m] = level + ramp_rate[k] * (t[m] - edges[k])
        level = level + ramp_rate[k] * (edges[k + 1] - edges[k]) - ramp_rate[k] * (edges[k + 1] - edges[k])   # undone at the sync
    comp = pd.DataFrame({'t_min': t / 60, 'M1 shift': shift, 'M2 shift': 0 * shift, 'M3 shift': -shift})
    t0 = pd.Timestamp('2026-09-01T20:00')
    comp['timestamp'] = t0 + pd.to_timedelta(t, 's')
    res = ramp_vs_next_step(comp, t0 + pd.to_timedelta(t_sync, 's'))
    assert res.loc['M1', 'corr'] < -0.9 and res.loc['M1', 'share undone'] == pytest.approx(1.0, abs=0.1)
    assert res.loc['M3', 'share undone'] == pytest.approx(1.0, abs=0.1)


def test_ramp_that_follows_the_drift_is_not_undone():
    from analyse_helpers import ramp_vs_next_step
    t_sync = np.arange(120, 3600, 120)
    t = np.arange(0, 3600, 0.2)
    shift = 0.2 * t + np.cumsum(np.where(np.isin(np.round(t, 1), t_sync), 3.0, 0.0))   # steady ramp, small same-sign steps
    comp = pd.DataFrame({'t_min': t / 60, 'M1 shift': shift, 'M2 shift': shift, 'M3 shift': shift})
    t0 = pd.Timestamp('2026-09-01T20:00')
    comp['timestamp'] = t0 + pd.to_timedelta(t, 's')
    res = ramp_vs_next_step(comp, t0 + pd.to_timedelta(t_sync, 's'))
    assert res.loc['M1', 'share undone'] < 0.1


def test_goto_jumps_are_breaks_not_divergence():
    kf = kflog(ripple=2.0)
    t = (kf['timestamp'] - kf['timestamp'].iloc[0]).dt.total_seconds().values
    for i in (1, 3):                                        # a goto mid-run: the shift jumps by degrees
        kf[f'θ_meas_raw_{i}'] = kf[f'θ_meas_raw_{i}'] + np.where(t >= 1800, 3.0 * (1 if i == 1 else -1), 0.0)
    _, summary = frame_shift_components(kf, pd.Series([], dtype='datetime64[ns]'))
    assert summary.attrs['breaks'] == 1
    assert summary.loc['M1', 'range "'] < 100 and summary.loc['M3', 'ripple rms "'] < 5
