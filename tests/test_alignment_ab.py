"""
utility/alignment_ab.py: A/B of Mechanical Alignment Correction (MAC on) against the existing
weighted rotation-only QUEST (off), replayed on the sync tables in archived driver logs. Scored by goto accuracy:
each sync point held out in turn, predicted from a model fitted on the others.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))

import numpy as np
import pandas as pd
import pytest

from alignment_ab import parse_sync_tables, alignments, quest_weighted_q, loo_errors_arcmin, point_errors, blc_at_points
from kinematics_mac import corrected_theta, boresights
from kinematics import q_to_theta, azaltroll_to_q, q_to_azaltroll, theta_to_q, vector_to_az_alt
from quaternion import Q as Quaternion

POSES = [(105, 50, 45), (135, 35, 65), (155, 69, 1), (225, 52, -65), (252, 62, -44), (180, 33, -2), (60, 40, -50)]
Q_TRUE = Quaternion(axis=[0.3, -0.2, 1.0], degrees=4.3)

TABLE = """\
2026-10-10T19:54:58.197 INFO QUEST Model  | Points: 2 | w: -0.9991143 | x: -0.0037534 | y: +0.0019681 | z: -0.0418648
2026-10-10T19:54:58.197 INFO   MAC: OFF   | SGA: ON   | RMS Residual: +001d01'17.95"  | Az Correction: -004d47'58.91" | Tilt: +000d25'19.10" @ +276d30'06.43" | Roll Adj: +000d00'00.00"
2026-10-10T19:54:58.198 INFO   No  Timestamp Age h   Obs RA  Obs Dec   Obs Az  Obs Alt     p_az    p_alt   p_roll  Weight    ResAz   ResAlt   ResMag
2026-10-10T19:54:58.198 INFO  #00   19:30:39   0.4    23.04   -31.60   100.71    50.02   104.94    50.10    44.98  0.0848    +0.14'    -6.29' +000d06'17.19"
2026-10-10T19:54:58.198 INFO  #01   19:31:32   0.4     0.98   -53.14   135.28    33.96   139.26    35.18    64.83  0.0938   +25.47'   -64.74' +001d08'03.52"
"""


def synthetic_rows(poses, d2=50 / 60, d3=-53 / 60, s2=0.01):
    """A sync table whose observed directions come from hidden offsets and an M2 scale (what the model fits)."""
    rows = []
    for k, (az, alt, roll) in enumerate(poses):
        th = np.asarray(q_to_theta(azaltroll_to_q(az, alt, roll)), float)
        v = Q_TRUE.rotate(boresights(corrected_theta(th[None], d2, d3, s2))[0])
        oaz, oalt = vector_to_az_alt(v)
        rows.append(dict(log='synthetic', table_time='t', no=k, point_time=f'{k:02d}', ra=0.0, dec=-40.0,
                         obs_az=oaz, obs_alt=oalt, p_az=az, p_alt=alt, p_roll=roll))
    return pd.DataFrame(rows)


def test_parses_the_logged_sync_table(tmp_path):
    f = tmp_path / 'alpaca.test.log'
    f.write_text(TABLE)
    t = parse_sync_tables([f])
    assert len(t) == 2 and list(t['no']) == [0, 1]
    r = t.iloc[1]
    assert (r.obs_az, r.obs_alt, r.p_az, r.p_alt, r.p_roll, r.dec) == (135.28, 33.96, 139.26, 35.18, 64.83, -53.14)
    assert r.mac == 'OFF' and r.table_time == '2026-10-10T19:54:58.197'


def test_an_alignment_is_a_tables_largest_set_of_points():
    t = pd.concat([synthetic_rows(POSES[:3]).assign(table_time='a'), synthetic_rows(POSES).assign(table_time='b')])
    al = alignments(t, min_points=4)
    assert len(al) == 1 and len(al[0]['obs']) == len(POSES)


def test_weighted_quest_is_the_drivers_rotation():
    """With equal weights it is the unweighted QUEST rotation that MAC's fit starts from."""
    t = synthetic_rows(POSES, d2=0, d3=0, s2=0)
    a = alignments(t, min_points=4)[0]
    q = quest_weighted_q(a['pred'], a['obs'], np.ones(len(a['obs'])))
    assert np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(q.q, Q_TRUE.q)))))) < 1e-5   # arccos near 1


def test_the_model_predicts_held_out_points_where_rotation_only_quest_cannot():
    a = alignments(synthetic_rows(POSES), min_points=4)[0]
    err = loo_errors_arcmin(a, s2=0.01)
    assert np.max(err['model']) < 0.1                                     # the hidden terms, recovered
    assert np.sqrt(np.mean(err['quest'] ** 2)) > 20                       # the driver's QUEST with MAC off


def test_point_errors_held_out_match_the_ab_and_follow_the_sync_order():
    a = alignments(synthetic_rows(POSES), min_points=4)[0]
    pe = point_errors(a, s2=0.01, min_fit=3)
    err = loo_errors_arcmin(a, s2=0.01)
    assert np.allclose(pe['loo_quest'], err['quest']) and np.allclose(pe['loo_model'], err['model'])
    assert list(pe['k']) == list(range(len(POSES)))
    assert pe['next_model'].iloc[:3].isna().all() and pe['next_model'].iloc[3:].notna().all()


def test_the_next_point_is_predicted_from_earlier_points_only():
    """Changing a later point must not change the prediction of an earlier one (no look-ahead)."""
    rows = synthetic_rows(POSES)
    a = point_errors(alignments(rows, min_points=4)[0], s2=0.01)
    rows.loc[len(POSES) - 1, ['obs_az', 'obs_alt']] += 2.0                # move the last observation by degrees
    b = point_errors(alignments(rows, min_points=4)[0], s2=0.01)
    assert np.allclose(a['next_model'].iloc[3:-1], b['next_model'].iloc[3:-1])
    assert np.allclose(a['next_quest'].iloc[3:-1], b['next_quest'].iloc[3:-1])
    assert not np.isclose(a['loo_model'].iloc[3], b['loo_model'].iloc[3])   # the held-out fit does see it


def test_error_components_make_up_the_error():
    """Horizontal and vertical parts (arcmin) add up to the total for these small errors, and point from the
    prediction to the observed star."""
    a = alignments(synthetic_rows(POSES), min_points=4)[0]
    pe = point_errors(a, s2=0.01)
    assert np.allclose(np.hypot(pe['loo_quest_h'], pe['loo_quest_v']), pe['loo_quest'], rtol=0.02, atol=0.05)
    rows = synthetic_rows(POSES)
    rows.loc[2, 'obs_alt'] += 0.5                                         # star 30' higher than the model expects
    pe2 = point_errors(alignments(rows, min_points=4)[0], s2=0.01)
    assert pe2['loo_model_v'].iloc[2] > 20 and abs(pe2['loo_model_h'].iloc[2]) < 10


BLC_LOG = """\
2026-10-14T23:50:00.000 INFO 1.2.3.4 -> PUT /api/v1/telescope/0/slewtocoordinatesasync {'RightAscension': '1.0'}
2026-10-14T23:50:05.000 INFO ->> Polaris: BACKLASH taking up slack: M2 -432"
2026-10-14T23:50:30.000 INFO 1.2.3.4 -> PUT /api/v1/telescope/0/synctocoordinates {'RightAscension': '1.0'}
2026-10-14T23:59:50.000 INFO 1.2.3.4 -> PUT /api/v1/telescope/0/slewtocoordinatesasync {'RightAscension': '2.0'}
2026-10-14T23:59:55.000 INFO ->> Polaris: BACKLASH taking up slack: M1 -144"
2026-10-15T00:00:02.000 WARNING ->> Polaris: BACKLASH compensation stopped until the next goto or planned reversal for M1, M3: crossed its slack more than 2 times
2026-10-15T00:00:20.000 INFO 1.2.3.4 -> PUT /api/v1/telescope/0/synctocoordinates {'RightAscension': '2.0'}
2026-10-15T00:05:00.000 INFO 1.2.3.4 -> PUT /api/v1/rotator/0/movemechanical {'Position': '18.5'}
2026-10-15T00:05:40.000 INFO 1.2.3.4 -> PUT /api/v1/telescope/0/synctocoordinates {'RightAscension': '2.0'}
"""


def test_blc_at_points_classifies_the_move_before_each_sync_across_midnight(tmp_path):
    f = tmp_path / 'alpaca.blc.log'
    f.write_text(BLC_LOG)
    d = blc_at_points(f, ['23:50:30', '00:00:20', '00:05:40'], '2026-10-15T00:06:00.000')
    assert list(d['blc']) == ['compensated', 'given up', 'no slack']
    assert d['move_time'].iloc[0].startswith('2026-10-14T23:50:00')
    assert d['move_time'].iloc[1].startswith('2026-10-14T23:59:50')       # the evening before, not 00:00
    assert d['giveups'].iloc[1] == 'M1, M3' and d['takeups'].iloc[1] == 1
    assert d['move_time'].iloc[2].startswith('2026-10-15T00:05:00')       # a rotate is a move too


def test_blc_at_points_is_off_without_any_backlash_lines(tmp_path):
    f = tmp_path / 'alpaca.old.log'
    f.write_text('\n'.join(l for l in BLC_LOG.splitlines() if 'BACKLASH' not in l) + '\n')
    d = blc_at_points(f, ['23:50:30'], '2026-10-14T23:55:00.000')
    assert list(d['blc']) == ['off']
