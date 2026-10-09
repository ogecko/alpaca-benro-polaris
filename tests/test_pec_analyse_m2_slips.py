"""
Tests for the M2 slip detector in utility/analyse_helpers.py (analyse_tracking.ipynb section 9): while tracking, a
heavy payload can make M2 creep ahead and then slip back ~10-30" at once, which the guider sees as a kick. Found in
the PECLOG motor angles (theta_raw, ~1 s apart while pulse guiding).
"""
import os
import sys
sys.path[:0] = [os.path.abspath(os.path.join(os.path.dirname(__file__), '..', p)) for p in ('utility', 'driver')]

import numpy as np
import pandas as pd

from analyse_helpers import m2_slips, m2_slip_summary

T0 = pd.Timestamp('2026-10-08 20:00:00')


def peclog(m2_rate_arcsec_s, minutes=10, slip_every_s=None, slip_arcsec=20.0, theta=(100.0, 40.0, 0.0), dt=1.0):
    """PECLOG rows dt apart with M2 turning at a steady rate, slipping back every slip_every_s."""
    t = np.arange(0, minutes * 60, dt)
    m2 = theta[1] + m2_rate_arcsec_s * t / 3600
    if slip_every_s:
        m2 -= np.sign(m2_rate_arcsec_s) * slip_arcsec / 3600 * np.floor(t / slip_every_s)
    return pd.DataFrame({'timestamp': T0 + pd.to_timedelta(t, unit='s'), 't_sec': t,
                         'theta_raw_1': theta[0], 'theta_raw_2': m2, 'theta_raw_3': theta[2]})


def test_each_slip_back_against_m2s_motion_is_found():
    steps = m2_slips(peclog(10.0, slip_every_s=12))
    assert abs(steps['slip'].sum() - 600 // 12) <= 2
    assert np.allclose(steps.loc[steps['slip'], 'size'], 20.0, atol=1.5)


def test_smooth_tracking_has_no_slips():
    assert m2_slips(peclog(10.0))['slip'].sum() == 0
    assert m2_slips(peclog(-6.0))['slip'].sum() == 0


def test_a_step_forward_is_not_a_slip():
    steps = m2_slips(peclog(-10.0, slip_every_s=12, slip_arcsec=-20.0))     # jumps along the motion
    assert steps['slip'].sum() == 0


def test_lifting_or_lowering_the_lens():
    # Roll 0: M2's angle is the altitude (theta2 = arccos(cos roll x cos alt)), so M2 turning up lifts the lens
    assert set(m2_slips(peclog(10.0))['direction']) == {'lifting'}
    assert set(m2_slips(peclog(-10.0))['direction']) == {'lowering'}
    assert set(m2_slips(peclog(0.0))['direction']) == {'still'}


def test_gaps_and_slews_are_left_out():
    df = peclog(10.0, slip_every_s=12, dt=5.0)                # sync guiding only: rows too far apart
    assert m2_slips(df).empty
    assert m2_slips(peclog(200.0)).empty                       # slewing, not tracking


def test_summary_counts_slips_per_hour_by_direction_and_speed():
    steps = pd.concat([m2_slips(peclog(10.0, slip_every_s=12)), m2_slips(peclog(-3.0))])
    s = m2_slip_summary(steps).set_index(['direction', 'speed'])
    lift = s.loc[('lifting', '8-11')]
    assert abs(lift['hours'] - 10 / 60) < 0.01 and abs(lift['slips per hour'] - 300) < 15
    assert lift['median size "'] == 20.0
    assert s.loc[('lowering', '2-5'), 'slips per hour'] == 0


def test_summary_marks_slips_seen_by_the_guider():
    steps = m2_slips(peclog(10.0, slip_every_s=12))
    t = steps.loc[steps['slip'], 'timestamp']
    jumps = pd.concat([t + pd.Timedelta('1s'), t + pd.Timedelta('2s')]).sort_values()      # the star jumps, then is back
    frames = pd.DataFrame({'timestamp': pd.concat([pd.Series([T0]), jumps]).values,
                           'ra_arcsec': np.r_[0.0, np.tile([12.0, 0.0], len(t))], 'dec_arcsec': 0.0})
    s = m2_slip_summary(steps, frames).set_index(['direction', 'speed'])
    assert s.loc[('lifting', '8-11'), 'seen by guider %'] == 100
