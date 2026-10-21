"""
PECLOG carries the raw MCU motor angles (theta_raw, as SGLOG does), so every PEC session -- pulse or sync guided --
can be used to learn and test per-motor worm models (utility/pe_analysis.py, analyse_pec_theta.ipynb) without
KFLOG's log_position volume.
"""
import ast
import logging
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import numpy as np

from control import SyncManager
from test_sync_manager import Polaris, mock_config          # noqa: F401  (fixture)


def peclog_payload(caplog, sm):
    with caplog.at_level(logging.INFO, logger='test'):
        sm._pec_log(0.001, None, (0.0, 0.0))
    line = next(r.getMessage() for r in caplog.records if r.getMessage().startswith('PECLOG '))
    return ast.literal_eval(line[len('PECLOG '):])


def test_peclog_includes_the_raw_motor_angles(mock_config, caplog):
    mock_config.log_pec = True
    sm = SyncManager(logging.getLogger('test'), Polaris())
    sm.polaris._theta_raw = np.array([12.3456789, 40.1, -5.5])
    assert peclog_payload(caplog, sm)['theta_raw'] == [12.34568, 40.1, -5.5]


def test_peclog_theta_raw_is_none_before_the_first_518(mock_config, caplog):
    mock_config.log_pec = True
    sm = SyncManager(logging.getLogger('test'), Polaris())
    sm.polaris._theta_raw = None
    assert peclog_payload(caplog, sm)['theta_raw'] == [None, None, None]


# ── 517 motor angles (zeta): the MCU's own angles, free of the compass / SPA heading in 518 ──

def test_zeta_raw_offset_is_theta_raw_minus_zeta_wrapped_to_180():
    from control_worm import zeta_raw_offset
    assert zeta_raw_offset([190.0, 50.0, -5.0], [5.0, 4.5, -5.25]) == [-175.0, 45.5, 0.25]
    assert zeta_raw_offset(None, [1.0, 2.0, 3.0]) is None
    assert zeta_raw_offset([1.0, 2.0, 3.0], None) is None


def test_peclog_includes_zeta_its_offset_to_theta_raw_and_age(mock_config, caplog):
    import time
    mock_config.log_pec = True
    sm = SyncManager(logging.getLogger('test'), Polaris())
    sm.polaris._theta_raw = np.array([12.0, 40.0, -5.0])
    sm.polaris._zeta_meas = [-168.123456, -5.0, -5.0]
    sm.polaris._zeta_raw_offset = [180.12345678, 45.0, 0.0]
    sm.polaris._last_517_timesec = time.monotonic() - 12.0
    p = peclog_payload(caplog, sm)
    assert p['zeta'] == [-168.12346, -5.0, -5.0]
    assert p['zeta_offset'] == [180.12346, 45.0, 0.0]
    assert 11.5 < p['zeta_age'] < 13.0


def test_peclog_zeta_fields_are_none_before_the_first_517(mock_config, caplog):
    mock_config.log_pec = True
    sm = SyncManager(logging.getLogger('test'), Polaris())
    p = peclog_payload(caplog, sm)
    assert p['zeta'] == [None, None, None] and p['zeta_offset'] == [None, None, None] and p['zeta_age'] is None
