"""
Tests for utility/learn_worm.py: learn the worm feed-forward profile (driver/control_pec.WormFeedForward) from
archived segments with raw motor angles, for the motors asked for, with its provenance.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utility')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np
import pytest

from learn_worm import learn_profile
from test_pec_theta_worm import seg, TRUE, LAT, H


@pytest.fixture
def segs():
    return [seg(f'alpaca.s{k}#0', f'alpaca.s{k}', 60 + k, start=(30.0 + 50 * k, 25.0 + 12 * k, None)) for k in range(3)]


def test_learnt_profile_matches_the_true_worm_for_the_motors_asked_for(segs):
    ff = learn_profile(segs, lat_of=lambda s: LAT, motors=('M3',), harmonics=H)
    assert np.allclose(ff.coef[0], 0.0) and np.allclose(ff.coef[1], 0.0)       # M1, M2 not asked for
    assert np.abs(ff.coef[2] - TRUE[8:12]).max() < 0.15 * np.abs(TRUE[8:12]).max()
    assert ff.worm_theta == pytest.approx(6.0)


def test_profile_records_where_it_came_from(segs):
    ff = learn_profile(segs, lat_of=lambda s: LAT, motors=('M1', 'M3'), harmonics=H)
    assert ff.meta['learnt_from'] == ['alpaca.s0', 'alpaca.s1', 'alpaca.s2']
    assert ff.meta['segments'] == 3 and ff.meta['fitted_motors'] == ['M1', 'M3']
    assert ff.meta['angles'] == 'theta_raw (518)'
    assert set(ff.meta['amplitude_arcsec']) == {'M1', 'M3'}


def test_no_segments_gives_no_profile():
    assert learn_profile([], lat_of=lambda s: LAT) is None


def test_the_saved_profile_loads_back_with_its_coefficients(segs, tmp_path):
    from control_pec import WormFeedForward
    ff = learn_profile(segs, lat_of=lambda s: LAT, motors=('M2', 'M3'), harmonics=H)
    ff.save(tmp_path / 'worm_profile.json')
    back = WormFeedForward.load(tmp_path / 'worm_profile.json')
    assert back is not None and np.allclose(back.coef, ff.coef, atol=1e-4)


def test_shared_profile_has_one_amplitude_and_a_phase_per_motor(segs, tmp_path):
    from control_pec import WormFeedForward
    ff = learn_profile(segs, lat_of=lambda s: LAT, motors=('M1', 'M3'), shared=True)
    assert ff.harmonics == (1,) and ff.meta['model'] == 'shared amplitude, phase per motor'
    amp = np.hypot(ff.coef[:, 0], ff.coef[:, 1])
    assert amp[1] == 0.0 and amp[0] == pytest.approx(amp[2])
    assert set(ff.meta['phase_deg']) == {'M1', 'M3'}
    ff.save(tmp_path / 'p.json')
    assert np.allclose(WormFeedForward.load(tmp_path / 'p.json').coef, ff.coef, atol=1e-4)
