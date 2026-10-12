"""
Extended (slow) check of Backlash Compensation (advanced_backlash) over the whole sky, and below the horizon down to
-30 deg (reached on the flipped branch, M3 near 180 deg; equatorial mode will use these): at each pose, while tracking
with backlash in every motor, small Slew & Center corrections and a larger goto, compensated and not. Skipped in the
regular suite; run with

    uv run pytest --runslow tests/test_backlash_compensation_poses.py      # the assertions, one test per pose
    uv run python tests/test_backlash_compensation_poses.py                 # the comparison table
    uv run python tests/test_backlash_compensation_poses.py --below         # ... below the horizon only

Compensated, the gotos should land with each tracking motor's backlash taken up, except where the mount's reach ends:
M2 within ~12 deg of gimbal lock (M1 and M3 turning about nearly the same axis) or at its 81.5 deg limit, and a motor at
its turning point at the target (under 0.5"/s: no settled tracking side). There it must do no worse than uncompensated.
"""
import math
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

from kinematics import azaltroll_to_theta_ik, reachable_azaltroll
from test_backlash_compensation import STEP, aligned_radec, engaged, tracking_twin
from test_motion_outcomes import radec_sep_arcmin, run_goto

AZ = range(0, 360, 45)
ALT = (-5, 5, 20, 40, 60, 75, 85)
ROLL = (-45, 0, 45)
BELOW_AZ, BELOW_ALT = range(0, 360, 90), (-10, -15, -20, -30)     # below the horizon
CORRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]          # Slew & Center corrections of STEP in RA / Dec
LARGE = 3.0                                                # deg: a larger goto while tracking (RA and Dec)
NORMAL_THETA2 = (12.0, 76.0)                               # deg: M2 away from gimbal lock and from its 81.5 deg limit
TURNING_ARCSEC_S = 0.5                                     # a motor tracking slower than this is at its turning point
GOTO_TIMEOUT_S = 44.9                                      # the driver's goto timeout (45 s): the goto never settled


def poses(grid=None):
    """The grid, as the driver would reach it (roll limited at low altitude): unique reachable poses. grid: 'sky' or
    'below' (default both)."""
    grids = {'sky': (AZ, ALT), 'below': (BELOW_AZ, BELOW_ALT)}
    out = []
    for az_range, alt_range in (grids.values() if grid is None else [grids[grid]]):
        for az in az_range:
            for alt in alt_range:
                for roll in ROLL:
                    p = tuple(round(float(v), 2) for v in reachable_azaltroll(az, alt, roll))
                    if p not in out:
                        out.append(p)
    return out


def run_pose(pose, on):
    """One pose: the corrections then the large goto. [dict(move, time to complete or None, error arcmin, engaged,
    edge)], edge: at the end of the mount's reach or a motor at its turning point."""
    mp = pytest.MonkeyPatch()
    try:
        tw = tracking_twin(mp, on=on, pose=pose)
        out = []
        moves = [(f'{d_ra:+d}RA{d_dec:+d}Dec', d_ra * STEP, d_dec * STEP) for d_ra, d_dec in CORRECTIONS] + \
                [('3 deg goto', LARGE, -LARGE)]
        for label, d_ra, d_dec in moves:
            cosd = math.cos(math.radians(tw.pid.delta_sp[1]))
            done, _, _ = run_goto(tw, lambda: tw.slew_relative(ra=d_ra / max(cosd, 0.1) / 15, dec=d_dec))
            tw.run(5.0)
            err = radec_sep_arcmin(tw.pid.delta_sp[0] / 15, tw.pid.delta_sp[1], *aligned_radec(tw))
            t2 = abs(azaltroll_to_theta_ik(*pose)[1])
            edge = (not NORMAL_THETA2[0] <= t2 <= NORMAL_THETA2[1] or not NORMAL_THETA2[0] <= abs(tw.theta[1]) <= NORMAL_THETA2[1]
                    or float(np.min(np.abs(tw.pid.omega_ff))) * 3600 < TURNING_ARCSEC_S)
            out.append(dict(move=label, time=done, err=err, engaged=all(engaged(tw)), edge=edge))
        return out
    finally:
        mp.undo()


@pytest.mark.slow
@pytest.mark.parametrize('pose', poses(), ids=lambda p: f'az{p[0]:.0f}_alt{p[1]:.0f}_roll{p[2]:.0f}')
def test_compensated_gotos_land_with_the_backlash_taken_up(pose):
    on = run_pose(pose, True)
    off = None
    for i, r in enumerate(on):
        assert r['time'] is not None, (r['move'], 'timed out')
        if not r['edge']:
            assert r['err'] < 1.5, r                       # the odd quick reversal hidden between samples: < 1.5'
        if r['edge'] or r['err'] >= 0.5:                   # no worse than uncompensated ...
            off = off or run_pose(pose, False)
            if off[i]['time'] >= GOTO_TIMEOUT_S:           # ... where that settles at all (not at gimbal lock)
                continue
            assert r['err'] <= off[i]['err'] + 0.5, (r, 'off', off[i])


if __name__ == '__main__':
    import logging
    import pandas as pd
    logging.disable(logging.INFO)
    rows = []
    for pose in poses('below' if '--below' in sys.argv else 'sky'):
        for on in (False, True):
            rows += [dict(az=pose[0], alt=pose[1], roll=pose[2], comp=on, **r) for r in run_pose(pose, on)]
        last = rows[-5:]
        print(f"az {pose[0]:6.1f} alt {pose[1]:5.1f} roll {pose[2]:6.1f}: compensated time "
              f"{' '.join(f'{r['time']:4.1f}' if r['time'] is not None else ' t/o' for r in last)} s, "
              f"error {' '.join(f'{r['err']:4.2f}' for r in last)}', engaged {sum(r['engaged'] for r in last)}/5",
              flush=True)
    df = pd.DataFrame(rows)
    df['small'] = df['move'] != '3 deg goto'
    if os.environ.get('CSV'):
        df.to_csv(os.environ['CSV'], index=False)
    print("\nSummary (5' corrections and 3 deg gotos), off vs compensated -- away from the edges of the mount's reach:")
    for small, g0 in df[~df['edge']].groupby('small'):
        for on, g in g0.groupby('comp'):
            t = g['time'].dropna()
            print(f"  {'corrections' if small else '3 deg gotos'} {'compensated' if on else 'off        '}: "
                  f"time median {t.median():4.1f} s, p90 {t.quantile(0.9):4.1f} s, timeouts {g['time'].isna().sum()}; "
                  f"error median {g['err'].median():4.2f}', p90 {g['err'].quantile(0.9):4.2f}', max {g['err'].max():5.2f}'; "
                  f"engaged {g['engaged'].mean():.0%}  ({len(g)} gotos)")
    edge = df[df['edge']].pivot_table(index=['az', 'alt', 'roll', 'move'], columns='comp', values='err')
    if len(edge):
        settled = df[df['edge'] & ~df['comp'] & (df['time'] < GOTO_TIMEOUT_S)].set_index(['az', 'alt', 'roll', 'move']).index
        edge = edge[edge.index.isin(settled)]
        worse = edge[edge[True] > edge[False] + 0.5]
        print(f"\nAt the edges (gimbal lock, the M2 limit, a motor at its turning point), where off settles: {len(edge)} gotos, compensated "
              f"worse than off by over 0.5' in {len(worse)}")
        if len(worse):
            print(worse.round(2).to_string())
