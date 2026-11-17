"""
Diagnostic for the 2026-10-09 kicks: the driver's event loop stalled 0.6-1.3 s every ~10 min at normal CPU (each
followed by a 12-38" kick on all three motors); a full garbage collection is the prime suspect. With log_heartbeat on,
shr.GcPauseLogger logs every collection that takes at least GC_LOG_MIN_S, flagging one the OS stretched (CPU time well
under wall time); shr.freeze_startup_heap keeps the startup heap out of the once-per-session full collection.
"""
import gc
import logging
import os
import sys
import weakref
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

import shr


class Clock:
    def __init__(self):
        self.t = 0.0
    def __call__(self):
        return self.t


def test_a_slow_collection_is_logged_and_a_quick_one_is_not(caplog):
    clock, cpu = Clock(), Clock()
    g = shr.GcPauseLogger(logging.getLogger('test'), min_s=0.1, clock=clock, cpu_clock=cpu)
    with caplog.at_level(logging.WARNING, logger='test'):
        g('start', {'generation': 0})
        clock.t += 0.02
        cpu.t += 0.02
        g('stop', {'generation': 0, 'collected': 5, 'uncollectable': 0})
        g('start', {'generation': 2})
        clock.t += 0.75
        cpu.t += 0.70
        g('stop', {'generation': 2, 'collected': 12345, 'uncollectable': 0})
    msgs = [r.getMessage() for r in caplog.records]
    assert len(msgs) == 1 and msgs[0].startswith('->> GC pause: 0.750s, generation 2, collected 12345')
    assert msgs[0].endswith('CPU 0.700s')        # the collector was doing the work: not an OS stall


def test_a_collection_stretched_while_the_process_was_starved_is_flagged_as_an_os_stall(caplog):
    clock, cpu = Clock(), Clock()
    g = shr.GcPauseLogger(logging.getLogger('test'), min_s=0.1, clock=clock, cpu_clock=cpu)
    with caplog.at_level(logging.WARNING, logger='test'):
        g('start', {'generation': 0})
        clock.t += 2.963
        cpu.t += 0.016
        g('stop', {'generation': 0, 'collected': 1809, 'uncollectable': 0})
    msgs = [r.getMessage() for r in caplog.records]
    assert len(msgs) == 1 and msgs[0].startswith('->> GC pause: 2.963s, generation 0')
    assert msgs[0].endswith('CPU 0.016s: OS stall, the process was starved of CPU')


def test_freeze_startup_heap_freezes_live_objects_frees_garbage_and_does_not_report_its_own_collection(caplog):
    class Cycle:
        pass
    g = shr.GcPauseLogger(logging.getLogger('test'), min_s=0.0)       # would log every collection
    try:
        g.install()
        a, b = Cycle(), Cycle()
        a.other, b.other = b, a
        freed = weakref.ref(a)
        del a, b                                                        # garbage only the collector can free
        with caplog.at_level(logging.INFO, logger='test'):
            shr.freeze_startup_heap(logging.getLogger('test'))
        msgs = [r.getMessage() for r in caplog.records]
        assert not any('GC pause' in m for m in msgs)
        assert len(msgs) == 1 and msgs[0].startswith('==STARTUP== Froze ') and 'startup objects' in msgs[0]
        assert gc.get_freeze_count() > 0
        assert freed() is None                                          # collected before the freeze
        assert gc.callbacks.count(g) == 1                               # the pause logger is back
    finally:
        g.remove()
        gc.unfreeze()
    assert gc.get_freeze_count() == 0


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
