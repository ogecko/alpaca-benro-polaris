"""
Tests for the PEC rate benchmark in utility/pe_analysis.py: the driver's real PecAxis replayed causally
over a drift series, scored on how well its applied rate tracks the actual drift rate, and on the drift
left for the guider per correction interval.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

from pe_analysis import true_rate, replay_pec_rate, rate_scores, PecModel

T = np.arange(0, 3 * 3600, 20.0)            # 3 h sampled every 20 s


def reversing_drift(t, amp_rate=20.0, period_s=90 * 60):
    """Drift whose rate (arcsec/min) is amp_rate * sin(2 pi t / period): reverses twice per period."""
    w = 2 * np.pi / period_s
    y = -amp_rate / 60 / w * np.cos(w * t)                  # arcsec; d/dt = amp_rate/60 * sin(w t) arcsec/s
    rate = amp_rate * np.sin(w * t)                        # arcsec/min
    return y - y[0], rate


def test_true_rate_recovers_a_known_rate():
    y, rate = reversing_drift(T)
    est = true_rate(T, y, half_window_s=150)
    ok = ~np.isnan(est)
    assert np.abs(est[ok] - rate[ok]).max() < 0.5             # arcsec/min


def test_true_rate_is_nan_where_the_window_is_incomplete():
    y, _ = reversing_drift(T)
    est = true_rate(T, y, half_window_s=300)
    assert np.isnan(est[0]) and np.isnan(est[-1])
    assert not np.isnan(est[len(T) // 2])


def test_replayed_ema_learns_a_constant_rate():
    y = 12.0 * T / 60                                       # 12 arcsec/min
    r = replay_pec_rate(T, y, PecModel('ema', mode='ema', tau_s=600))
    assert r[-1] == pytest.approx(12.0, rel=0.02)
    assert r[0] == 0.0                                      # nothing learnt before the first two samples


def test_replayed_rls_linear_learns_a_constant_rate():
    y = -7.0 * T / 60
    r = replay_pec_rate(T, y, PecModel('rls0', mode='rls', n_harmonics=0, tau_s=1260))
    assert r[-1] == pytest.approx(-7.0, rel=0.05)


def test_scores_no_pec_baseline_and_a_perfect_oracle():
    y, rate = reversing_drift(T)
    s = rate_scores(T, y, {'oracle': rate}, guide_intervals_s=(120,), ref_half_window_s=150, warmup_s=600)
    assert s['rate_rms']['no_pec'] == pytest.approx(np.sqrt(np.mean(rate[(T >= 600)] ** 2)), rel=0.05)
    assert s['rate_rms']['oracle'] < 0.05 * s['rate_rms']['no_pec']
    # even the exact instantaneous rate leaves the curvature of the drift over the interval
    assert s['guide_rms'][120]['oracle'] < 0.10 * s['guide_rms'][120]['no_pec']


def test_ema_tau_has_an_interior_optimum_on_a_noisy_reversing_drift():
    rng = np.random.default_rng(0)
    y, _ = reversing_drift(T)
    y = y + rng.normal(0, 4.0, len(T))                      # 4" measurement noise
    scores = {}
    for tau in (20, 60, 120, 300, 900, 3600):
        r = replay_pec_rate(T, y, PecModel(f'ema{tau}', mode='ema', tau_s=tau))
        scores[tau] = rate_scores(T, y, {'m': r}, guide_intervals_s=(120,), ref_half_window_s=300)['rate_rms']['m']
    best = min(scores, key=scores.get)
    assert best not in (20, 3600)                           # too fast chases noise, too slow lags the reversals
    assert scores[20] > 2 * scores[best] and scores[3600] > 2 * scores[best]


def test_benchmark_segments_and_pooled_relative():
    from pe_analysis import Segment, benchmark_segments, pooled_relative
    rng = np.random.default_rng(1)
    segs = []
    for k in range(3):
        y, _ = reversing_drift(T, amp_rate=10 + 5 * k)
        y = y + rng.normal(0, 3.0, len(T))
        theta = np.column_stack([T / 3600, T / 3600, T / 3600])
        segs.append(Segment(f"s{k}", f"s{k}", T, y, 0.5 * y, theta))
    models = [PecModel('ema 2m', 'ema', 0, 120), PecModel('ema 60m', 'ema', 0, 3600)]
    df = benchmark_segments(segs, models, guide_intervals_s=(120,), ref_half_windows_s=(300,))
    assert set(df['metric']) == {'guide residual 120s', 'rate (ref +-5.0 min)'}
    assert set(df['model']) == {'no_pec', 'ema 2m', 'ema 60m'}
    assert set(df['kind']) == {'sync'}                     # 20 s sampling counts as sync-like
    rel = pooled_relative(df)
    assert rel.loc['no_pec', 'guide residual 120s'] == pytest.approx(1.0)
    assert rel.loc['ema 2m', 'guide residual 120s'] < rel.loc['ema 60m', 'guide residual 120s'] < 1.0
