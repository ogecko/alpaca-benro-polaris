"""
load_pec() backfills 'resid' from the separate 'SYNC GUIDING ... Residuals' line ONLY for the
legacy PECLOG format, which never logged resid. A modern pulse-guide PECLOG row has resid for
one axis and None for the other -- that None means "this pulse was on the other axis" and must
stay NaN, otherwise every sync's residual is counted again on each pulse row within 2 s of it.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import math
import pytest

from analyse_helpers import load_pec

SYNC = ("2026-09-30T01:32:15.007 INFO ->> Polaris: SYNC GUIDING    "
        "Ra +000d00'01.18\", Dec +000d00'21.65\" Residuals\n")


def peclog(ts, resid):
    return (f"{ts} INFO PECLOG {{'n': 5, 'inhibit': ['VALID', 'VALID'], 'resid': {resid}, "
            f"'pec_accum': [0.0, 0.0], 'total_accum': [0.1, 0.2]}}\n")


LEGACY = ("2026-09-30T01:32:15.950 INFO PECLOG  n,2,VALID,VALID, | R2,0.9,0.9, | rmse,0.1,0.1, | "
          "Rate,-3.2,+6.7, | Guide,-0.8,+1.8, | Accum,-0.8,+1.8, | Pos,205.79,17.30,-0.68, | "
          "RA_model,-3.2,0.0,0.0, | Dec_model,+6.7,0.0,0.0, | lambda,0.98,0.98\n")


@pytest.fixture
def log(tmp_path):
    p = tmp_path / 'alpaca.log'
    p.write_text(
        peclog("2026-09-30T01:32:14.154", "[-0.0083, None]")      # RA pulse, 0.85 s before the sync
        + SYNC
        + peclog("2026-09-30T01:32:15.007", "[0.0197, 0.3608]")   # the sync's own PECLOG row
        + peclog("2026-09-30T01:32:15.877", "[None, 0.012]")      # Dec pulse, 0.87 s after
        + LEGACY,
        encoding='utf-8')
    return str(p)


def test_modern_pulse_rows_are_not_backfilled_from_a_nearby_sync(log):
    df, _ = load_pec(log)
    assert math.isnan(df['resid_2'].iloc[0])
    assert math.isnan(df['resid_1'].iloc[2])


def test_modern_rows_keep_their_own_resid(log):
    df, _ = load_pec(log)
    assert df['resid_1'].iloc[0] == pytest.approx(-0.0083)
    assert list(df['resid_2'].iloc[1:3]) == pytest.approx([0.3608, 0.012])


def test_legacy_rows_are_still_backfilled_from_the_sync_line(log):
    df, _ = load_pec(log)
    legacy = df.iloc[3]
    assert legacy['resid_1'] == pytest.approx(1.18 / 60)
    assert legacy['resid_2'] == pytest.approx(21.65 / 60)


def test_no_helper_column_leaks_into_the_result(log):
    df, _ = load_pec(log)
    assert not any(c.startswith('_') for c in df.columns)
