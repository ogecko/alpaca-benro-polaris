"""
Tests for correction_breakdown() in utility/analyse_helpers.py: from PECLOG, the mount drift and who corrected it
(pulse guiding, sync guiding, PEC), as running totals and as rates, plus the PEC rate terms the driver used.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import numpy as np
import pandas as pd
import pytest

from analyse_helpers import correction_breakdown


def peclog_df(n_s=3600, dt=10.0, reset_at=None):
    """Synthetic PECLOG rows: RA pulse rows (resid_1 only), Dec pulse rows (resid_2 only), and a sync row (both)
    every 120 s; PEC applies a constant 0.1 arcmin per row on RA. total_accum accumulates resid + pec_accum."""
    rows, n, acc = [], 1, [0.0, 0.0]
    t0 = pd.Timestamp('2026-09-30T01:00')
    for k, t in enumerate(np.arange(0, n_s, dt)):
        if reset_at is not None and t == reset_at:
            n, acc = 1, [0.0, 0.0]
        sync = (k % 12 == 0) and k > 0
        r1 = 0.05 if sync else (0.02 if k % 2 == 0 else None)
        r2 = -0.03 if sync else (-0.01 if k % 2 == 1 else None)
        pec1 = 0.1 if r1 is not None else 0.0                 # arcmin applied since the last RA ingest
        pec2 = 0.0
        if r1 is not None: acc[0] += r1 + pec1
        if r2 is not None: acc[1] += r2 + pec2
        rows.append(dict(timestamp=t0 + pd.Timedelta(seconds=float(t)), t_sec=float(t), n=n,
                         resid_1=np.nan if r1 is None else r1, resid_2=np.nan if r2 is None else r2,
                         pec_accum_1=pec1, pec_accum_2=pec2, total_accum_1=acc[0], total_accum_2=acc[1],
                         fit_rate_1=12.0, fit_rate_2=0.0,
                         applied_rate_1=12.0, applied_rate_2=0.0, inhibit_1='VALID', inhibit_2='LOW_R2'))
        n += 1
    return pd.DataFrame(rows)


def test_mount_drift_is_the_sum_of_the_corrections():
    b = correction_breakdown(peclog_df())
    for ax in ('ra', 'dec'):
        x = b[ax]
        assert np.allclose(x['mount_drift'], x['pulse_guide'] + x['sync_guide'] + x['pec_applied'])


def test_mount_drift_matches_total_accum_joined_across_a_reset():
    df = peclog_df(reset_at=1800.0)
    b = correction_breakdown(df)
    x = b['ra']
    jump = x['mount_drift'].diff().abs().max()
    assert jump < 2.0 * 60 * 0.15                               # no restart-to-zero jump at the reset
    assert x['mount_drift'].iloc[-1] == pytest.approx((df['total_accum_1'].iloc[1799 // 10] + df['total_accum_1'].iloc[-1]) * 60, rel=0.01)
    assert list(b['resets']) == [df['timestamp'].iloc[180]]


def test_units_are_arcsec_and_arcsec_per_min():
    b = correction_breakdown(peclog_df())
    x = b['ra']
    rows_with_ra = (peclog_df()['resid_1'].notna()).sum()
    assert x['pec_applied'].iloc[-1] == pytest.approx(rows_with_ra * 0.1 * 60)
    mid = len(x) // 2
    assert x['pec_applied_rate'].iloc[mid] == pytest.approx(0.1 * 60 * (rows_with_ra / 360) / (10 / 60), rel=0.05)


def test_rates_sum_to_the_drift_rate():
    b = correction_breakdown(peclog_df())
    x = b['ra'].dropna(subset=['drift_rate'])
    assert np.allclose(x['drift_rate'], x['pulse_guide_rate'] + x['sync_guide_rate'] + x['pec_applied_rate'], atol=1e-9)


def test_pec_model_rate_and_active_per_axis():
    b = correction_breakdown(peclog_df())
    x = b['ra']
    assert x['pec_model_rate'].iloc[-1] == pytest.approx(12.0)
    assert bool(x['pec_active'].iloc[-1]) and not bool(b['dec']['pec_active'].iloc[-1])


# ── worm feed-forward nights ──────────────────────────────────────────────────────────────────
def with_wff(df):
    """PECLOG wff (arcmin): the feed-forward's correction at each row, split along RA/Dec (a level, not a sum)."""
    df = df.copy()
    df['wff_1'] = 0.2 * np.sin(df['t_sec'] / 600)
    df['wff_2'] = -0.1 * np.cos(df['t_sec'] / 600)
    return df


def test_without_wff_the_worm_ff_column_is_zero():
    b = correction_breakdown(peclog_df())
    assert (b['ra']['worm_ff'] == 0).all() and (np.nan_to_num(b['ra']['worm_ff_rate']) == 0).all()   # NaN: window edges


def test_on_a_worm_feed_forward_night_mount_drift_adds_back_what_it_corrected():
    df = with_wff(peclog_df())
    b = correction_breakdown(df)
    for ax, i in (('ra', 1), ('dec', 2)):
        x = b[ax]
        own = df[f'resid_{i}'].notna()
        w = df.loc[own, f'wff_{i}'].values * 60
        assert np.allclose(x['worm_ff'], w - w[0])                # running total from the first row, arcsec
        assert np.allclose(x['mount_drift'], x['pulse_guide'] + x['sync_guide'] + x['pec_applied'] + x['worm_ff'])
        assert np.allclose(x['drift_rate'], x['pulse_guide_rate'] + x['sync_guide_rate'] + x['pec_applied_rate']
                           + x['worm_ff_rate'], equal_nan=True)


def test_wff_missing_on_early_rows_counts_as_none_applied_yet():
    df = with_wff(peclog_df())
    df.loc[df['t_sec'] < 600, ['wff_1', 'wff_2']] = np.nan
    x = correction_breakdown(df)['ra']
    early = x['t_sec'] < 600
    assert (x.loc[early, 'worm_ff'] == 0).all() and not np.isnan(x['worm_ff']).any()
