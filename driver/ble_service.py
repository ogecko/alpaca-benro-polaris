import asyncio
import json
from bleak import BleakScanner, BleakClient, exc
from shr import LifecycleController, bytes2hexascii
from config import Config
import time

ENABLE_WIFI_COMMAND = "enable_wifi"
SEND_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
RECV_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

class BLE_Controller():
    def __init__(self, logger, lifecycle:LifecycleController):
        self.logger = logger
        self.lifecycle = lifecycle
        self.devices: dict[str, dict] = { }
        self.selectedDevice = None
        self.isEnablingWifi = False
        self.isWifiEnabled = False


    def get_address_by_name(self, name: str | None) -> str | None:
        if not name:
            return None
        name = name.lower()
        for addr, info in self.devices.items():
            if info.get("name", "").lower() == name:
                return addr
        return None

    def scannerCallback(self, device, adv):
        name = (adv.local_name or device.name or "").lower()
        if name.startswith("polaris"):
            self.devices[device.address] = {
                "name": name,
                "address": device.address,
                "service_uuids": adv.service_uuids,
                "rssi": adv.rssi,
                "last_seen": time.time(),
            }
            if self.selectedDevice is None:     # select the first one we discover
                self.selectedDevice = name
            if Config.log_polaris_ble:
                self.logger.info(f"BLE Discovered Polaris: {device.address} ({self.devices[device.address]})")

    def prune_stale_devices(self, timeout=30):
        now = time.time()
        stale = [addr for addr, info in self.devices.items() if now - info.get("last_seen", 0) > timeout]
        for addr in stale:
            self.logger.info(f"BLE Pruning stale device: {addr}")
            if self.selectedDevice == self.devices.get(addr, {}).get("name"):
                self.selectedDevice = None
            del self.devices[addr]

    def notification_handler(self, sender, data):
        if Config.log_polaris_ble:
            self.logger.info(f"BLE Received from Polaris: {data.decode(errors='ignore')}")

    async def listCharacteristics(self):
        for address, device in self.devices.items():
            try:
                async with BleakClient(address) as client:
                    for service in client.services:
                        self.logger.info(f"Service: {service.uuid} - {service.description}")
                        for char in service.characteristics:
                            props = ", ".join(char.properties)
                            if Config.log_polaris_ble:
                                self.logger.info(f"  Characteristic: {char.uuid} ({char.description}) [{props}]")
            except Exception as e:
                self.logger.warn(f"Failed to connect to {address}: {e}")

    def setSelectedDevice(self, name):
        if any(dev.get("name") == name for dev in self.devices.values()):
            self.selectedDevice = name

    async def enableWifi(self):
        name = self.selectedDevice
        address = self.get_address_by_name(name)
        if not address:
            self.logger.warn(f"BLE No Polaris device found with name '{name}'")
            return
        self.isEnablingWifi = True
        self.isWifiEnabled = False
        max_attempts = 3
        for attempt in range(1, max_attempts+1):
            try:
                async with BleakClient(address) as client:
                    await client.start_notify(RECV_UUID, self.notification_handler)
                    await client.write_gatt_char(SEND_UUID, b'enable_wifi', response=True)
                    if Config.log_polaris_ble:
                        self.logger.info(f"BLE Send request to enable Wifi {address}")
                    data = await client.read_gatt_char(RECV_UUID)
                    if Config.log_polaris_ble:
                        self.logger.info(f"BLE Read request complete {bytes2hexascii(data)}")
                    self.isEnablingWifi = False
                    self.isWifiEnabled = True
                    return
            except Exception as e:
                self.logger.warn(f"BLE Attempt {attempt} failed to enable Wifi {address}: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(1)
                else:
                    self.logger.warn(f"BLE failed to enable wifi after {max_attempts}")
                    self.isEnablingWifi = False



    async def runBleScanner(self):
        async with BleakScanner(self.scannerCallback) as scanner:
            while not self.lifecycle.should_shutdown():
                self.prune_stale_devices()
                await asyncio.sleep(15)

