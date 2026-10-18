"""
Pilot's Wi-Fi button (Polaris:bleEnableWifi -> BLE_Controller.enableWifiAndJoin): a second request while a join is
running is ignored, rather than starting a second join on the same adapter (two arrived 4 ms apart, 2026-10-17).
"""
import asyncio
import logging
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'driver')))
from ble_service import BLE_Controller                                              # noqa: E402


def test_second_enable_wifi_while_joining_is_ignored():
    joins = []

    async def join(ssid):
        joins.append(ssid)
        await asyncio.sleep(0.05)
        return True

    ble = SimpleNamespace(isEnablingWifi=False, isWifiEnabled=False, isConnectedFn=lambda: False,
                          selectedDevice='polaris_test', joinWifiNetwork=join, logger=logging.getLogger('test'))

    async def two_clicks():
        await asyncio.gather(BLE_Controller.enableWifiAndJoin(ble), BLE_Controller.enableWifiAndJoin(ble))

    asyncio.run(two_clicks())
    assert joins == ['polaris_test']
    assert ble.isEnablingWifi is False and ble.isWifiEnabled is True

    asyncio.run(BLE_Controller.enableWifiAndJoin(ble))          # a later click, once the first has finished, runs
    assert joins == ['polaris_test', 'polaris_test']
