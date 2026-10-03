"""
The driver's Polaris object builds as main.py builds it. Its parts are created in order (the PID before the
SyncManager), and the digital twin builds them differently, so this catches code that assumes a part exists too early
(2026-10-03: the PID's first mode change looked up the SyncManager's worm gear test and crashed startup).
"""
import asyncio
import logging
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))

from config import Config
from shr import LifecycleController


def test_polaris_builds_and_starts_idle():
    Config.load()
    from polaris import Polaris

    async def build():
        return Polaris(logging.getLogger('test'), LifecycleController())
    p = asyncio.run(build())
    assert p._pid.mode in ('IDLE', 'PRESETUP')
    assert p._sm.worm_test is None
