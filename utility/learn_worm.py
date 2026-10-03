"""
Learn the worm feed-forward profile (driver/control_worm.WormFeedForward) from archived drift segments.

Each motor's gear train after the motor has a periodic error the MCU can't see: the true output angle = the motor
angle + e_i(theta_i), a 6.0 deg worm (60 teeth, 960:1 = 16 x 60). utility/analyse_pec_theta.ipynb shows the M2 and
M3 profiles repeat night to night on the raw motor angles, so a profile fitted on past sessions applies to future
ones. This fits it in motor space on RA and Dec drift jointly (pe_analysis.fit_worm) over the segments with raw motor
angles, and writes it where the driver reads it (Config.pec_worm_profile, in the data folder); turn it on with
Config.pec_worm_ff.

The fitted profile is the physical gear error, same sign and scale (tests/test_pec_twin_worm_ff.py).

Model: by default the shared one (one amplitude for all motors and a phase each, a pure 6 deg sine), which the archive
supports; --per-motor fits independent 2-harmonic profiles.

Angles: theta_raw from 518, as the driver's control tick uses. M1 is left out by default: its 518 angle includes each
session's compass / Single Point Alignment heading, so its worm phase changes from night to night.

    uv run python utility/learn_worm.py --exclude mark greg vyskocil          # other people's mounts
    uv run python utility/learn_worm.py --include soak_Beta4.4 jdm_Beta7 --dry-run
"""
import argparse
import datetime
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'driver'))
sys.path.insert(0, HERE)

from pe_analysis import load_segments, fit_worm, fit_shared_worm, worm_phase_table, phase_consistency   # noqa: E402
from control_worm import WormFeedForward                                                # noqa: E402

MOTORS = ('M1', 'M2', 'M3')
RAW_SOURCES = ('kflog', 'sglog', 'peclog_raw')       # segments whose motor angles are 518 theta_raw


def learn_profile(segs, lat_of, motors=('M2', 'M3'), worm_theta=6.0, harmonics=(1, 2), shared=False, **fit_kw):
    """WormFeedForward fitted on `segs` (pe_analysis.Segment with raw motor angles), keeping only `motors`, with its
    provenance in .meta. lat_of(session) -> site latitude. None if there are no segments.
    shared: one amplitude for all motors and a phase each, a pure sine (pe_analysis.fit_shared_worm) -- what the
    archive supports; otherwise independent per-motor profiles with `harmonics`."""
    if not segs:
        return None
    parts = [(s.t, s.ra, s.dec, s.theta, lat_of(s.session)) for s in segs]
    if shared:
        prof, harmonics = fit_shared_worm(parts, worm_theta=worm_theta, **fit_kw), (1,)
    else:
        prof = fit_worm(parts, worm_theta=worm_theta, harmonics=tuple(harmonics), **fit_kw)
    coef = np.asarray(prof.coef, float).reshape(3, -1).copy()
    keep = [MOTORS.index(m) for m in motors]
    coef[[m for m in range(3) if m not in keep]] = 0.0
    ff = WormFeedForward(worm_theta=worm_theta, harmonics=tuple(harmonics), coef=coef)
    turn = np.linspace(0, worm_theta, 360)
    amp = {}
    for m in keep:
        th = np.zeros((len(turn), 3))
        th[:, m] = turn
        e = np.array([ff.error_deg(x)[m] for x in th]) * 3600
        amp[MOTORS[m]] = round(float(np.ptp(e) / 2), 1)
    ff.meta = {'learnt_from': sorted({s.session for s in segs}), 'segments': len(segs), 'fitted_motors': list(motors),
               'angles': 'theta_raw (518)', 'amplitude_arcsec': amp,
               'model': 'shared amplitude, phase per motor' if shared else f'per motor, harmonics {list(harmonics)}',
               'created': datetime.date.today().isoformat()}
    if shared:
        ff.meta['phase_deg'] = {MOTORS[m]: round(float(np.degrees(np.arctan2(coef[m, 1], coef[m, 0])) % 360), 1)
                                for m in keep}
    return ff


def main():
    from config import DATA_DIR
    from sessions import site_latitude
    from extract_segments import DEFAULT_SITE
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--seg-dir', default=os.path.join(HERE, '..', 'logs', 'archive', 'segments'),
                    help='segment datasets (built by analyse_pec_theta.ipynb / extract_segments.py)')
    ap.add_argument('--include', nargs='*', default=[], help='only sessions whose name contains one of these')
    ap.add_argument('--exclude', nargs='*', default=[], help='leave out sessions whose name contains one of these '
                                                             '(e.g. other mounts)')
    ap.add_argument('--motors', nargs='*', default=['M2', 'M3'], choices=MOTORS)
    ap.add_argument('--worm', type=float, default=6.0, help='deg of motor rotation per worm turn')
    ap.add_argument('--per-motor', action='store_true', help='independent profile per motor (2 harmonics) instead of '
                                                               'the shared model (one amplitude, a phase per motor)')
    ap.add_argument('--min-minutes', type=float, default=60)
    ap.add_argument('--out', default=os.path.join(DATA_DIR, 'worm_profile.json'))
    ap.add_argument('--dry-run', action='store_true', help='report only, write nothing')
    a = ap.parse_args()

    idx = pd.read_csv(os.path.join(a.seg_dir, 'index.csv'))
    raw = set(idx.loc[idx['theta_source'].isin(RAW_SOURCES), 'session'] + '#' + idx['segment'].astype(int).astype(str))
    segs = [s for s in load_segments(a.seg_dir, min_minutes=a.min_minutes) if s.name in raw
            and (not a.include or any(x in s.session for x in a.include))
            and not any(x in s.session for x in a.exclude)]
    lat_of = lambda session: site_latitude(session, default=DEFAULT_SITE[0])
    ff = learn_profile(segs, lat_of, motors=a.motors, worm_theta=a.worm, shared=not a.per_motor)
    if ff is None:
        sys.exit('no segments with raw motor angles match')
    print(f"{len(segs)} segments from {len(ff.meta['learnt_from'])} sessions:")
    for s in ff.meta['learnt_from']:
        print(f"  {s}")
    tab = worm_phase_table(segs, lat_of, worm_theta=a.worm)
    print(f"\n{'motor':6s}{'amplitude':>11s}{'segments >= 2 turns':>21s}{'phase repeats (R, p)':>24s}")
    for m in a.motors:
        g = tab[(tab['motor'] == m) & (tab['amp'] >= 10)]
        c = phase_consistency(g['phase'])
        ph = f"   phase {ff.meta['phase_deg'][m]:5.1f}" if 'phase_deg' in ff.meta else ''
        print(f"{m:6s}{ff.meta['amplitude_arcsec'][m]:>10.1f}\"{len(g):>21d}{c['R']:>16.2f}, {c['p']:.3f}{ph}")
    if a.dry_run:
        print('\n--dry-run: nothing written')
        return
    ff.save(a.out)
    print(f"\nwrote {a.out} -- turn it on with pec_worm_ff = true (config.toml)")


if __name__ == '__main__':
    main()
