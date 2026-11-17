"""
Stop Driver hung for ever on nina01 (2026-11-15): BLE enableWifi swallowed the shutdown cancel and kept retrying, and
LifecycleController.shutdown_tasks' timeout never fired because wait_for(gather) waits for its own cancel to finish.
"""
import asyncio
import logging
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
import ble_service                                                                  # noqa: E402
import shr                                                                          # noqa: E402
from ble_service import BLE_Controller                                              # noqa: E402

shr.logger = logging.getLogger('test')


def test_shutdown_tasks_returns_when_a_task_ignores_its_cancel():
    async def stubborn():
        while True:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass                    # ignores the cancel, like the old BLE retry loop

    async def scenario():
        lifecycle = shr.LifecycleController()
        lifecycle.create_task(stubborn(), name='Stubborn')
        lifecycle.create_task(asyncio.sleep(10), name='Polite')
        await asyncio.wait_for(lifecycle.shutdown_tasks(timeout=0.2), timeout=2)
        return lifecycle.stuck_tasks

    # A loop of its own, left unclosed: asyncio.run would wait for ever cancelling the stubborn task on the way out
    loop = asyncio.new_event_loop()
    assert loop.run_until_complete(scenario()) == ['Stubborn']


def test_ble_enable_wifi_honours_a_real_cancel_after_stop_driver(monkeypatch):
    class StallingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            await asyncio.sleep(10)     # a connect that is still running when the driver shuts down

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(ble_service, 'BleakClient', StallingClient)

    async def nothing():
        pass

    async def scenario():
        lifecycle = SimpleNamespace(should_shutdown=lambda: False)      # STOP: should_shutdown() is False
        ble = SimpleNamespace(selectedDevice='polaris_test', get_address_by_name=lambda name: 'AA:BB',
                              isConnectedFn=lambda: False, lifecycle=lifecycle, logger=logging.getLogger('test'),
                              _stop_scanner=nothing, _start_scanner=nothing, _reset_bluetooth_adapter=nothing)
        task = asyncio.create_task(BLE_Controller._enableWifi_inner(ble))
        await asyncio.sleep(1)          # past the scanner-stop pause, into the first connect
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=1)
        return task in done and task.cancelled()

    assert asyncio.run(scenario())
