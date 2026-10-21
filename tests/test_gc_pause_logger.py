"""
Diagnostic for the 2026-10-09 kicks: the driver's event loop stalled 0.6-1.3 s every ~10 min at normal CPU (each
followed by a 12-38" kick on all three motors); a full garbage collection is the prime suspect. With log_heartbeat on,
shr.GcPauseLogger logs every collection that takes at least GC_LOG_MIN_S.
"""
import gc
import logging
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import shr


class Clock:
    def __init__(self):
        self.t = 0.0
    def __call__(self):
        return self.t


def test_a_slow_collection_is_logged_and_a_quick_one_is_not(caplog):
    clock = Clock()
    g = shr.GcPauseLogger(logging.getLogger('test'), min_s=0.1, clock=clock)
    with caplog.at_level(logging.WARNING, logger='test'):
        g('start', {'generation': 0})
        clock.t += 0.02
        g('stop', {'generation': 0, 'collected': 5, 'uncollectable': 0})
        g('start', {'generation': 2})
        clock.t += 0.75
        g('stop', {'generation': 2, 'collected': 12345, 'uncollectable': 0})
    msgs = [r.getMessage() for r in caplog.records]
    assert len(msgs) == 1 and msgs[0].startswith('->> GC pause: 0.750s, generation 2, collected 12345')


def test_install_hooks_into_real_collections_once_and_remove_unhooks(caplog):
    g = shr.GcPauseLogger(logging.getLogger('test'), min_s=0.0)       # log every collection
    try:
        g.install()
        g.install()
        assert gc.callbacks.count(g) == 1
        with caplog.at_level(logging.WARNING, logger='test'):
            gc.collect()
        assert any('GC pause' in r.getMessage() and 'generation 2' in r.getMessage() for r in caplog.records)
    finally:
        g.remove()
    assert g not in gc.callbacks
