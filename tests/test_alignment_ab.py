"""
utility/alignment_ab.py: A/B of the alignment model (Mechanical Alignment Correction on) against the existing
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

from alignment_ab import parse_sync_tables, alignments, quest_weighted_q, loo_errors_arcmin
from align_model import corrected_theta, boresights
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
    """With equal weights it is the unweighted QUEST rotation that the alignment model starts from."""
    t = synthetic_rows(POSES, d2=0, d3=0, s2=0)
    a = alignments(t, min_points=4)[0]
    q = quest_weighted_q(a['pred'], a['obs'], np.ones(len(a['obs'])))
    assert np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(q.q, Q_TRUE.q)))))) < 1e-5   # arccos near 1


def test_the_model_predicts_held_out_points_where_rotation_only_quest_cannot():
    a = alignments(synthetic_rows(POSES), min_points=4)[0]
    err = loo_errors_arcmin(a, s2=0.01)
    assert np.max(err['model']) < 0.1                                     # the hidden terms, recovered
    assert np.sqrt(np.mean(err['quest'] ** 2)) > 20                       # the driver's QUEST with MAC off
