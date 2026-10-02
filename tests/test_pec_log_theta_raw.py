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
