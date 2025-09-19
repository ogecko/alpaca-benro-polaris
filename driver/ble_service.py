import asyncio
import json
from bleak import BleakScanner, BleakClient, exc
from shr import LifecycleController, bytes2hexascii
from config import Config

ENABLE_WIFI_COMMAND = "enable_wifi"
SEND_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
RECV_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

class BLE_Controller():
    def __init__(self, logger, lifecycle:LifecycleController):
        self.logger = logger
        self.lifecycle = lifecycle
        self.devices: dict[str, dict] = {}

    def get_address_by_name(self, name: str) -> str | None:
        name = name.lower()
        for address, info in self.devices.items():
            if info["name"] == name:
                return address
        return None


    def scannerCallback(self, device, adv):
        name = (adv.local_name or device.name or "").lower()
        if name.startswith("polaris"):
            self.devices[device.address] = {
                "name": name,
                "address": device.address,
                "service_uuids": adv.service_uuids,
                "rssi": adv.rssi,
            }
            if Config.log_polaris_ble:
                self.logger.info(f"BLE Discovered Polaris: {device.address} ({self.devices[device.address]})")

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

    async def enableWifi(self, name):
        address = self.get_address_by_name(name)
        if not address:
            self.logger.warn(f"BLE No Polaris device found with name '{name}'")
            return
        device = self.devices[address]
        try:
            async with BleakClient(address) as client:
                await client.start_notify(RECV_UUID, self.notification_handler)
                await client.write_gatt_char(SEND_UUID, b'enable_wifi', response=True)
                if Config.log_polaris_ble:
                    self.logger.info(f"BLE Sent request to enable Wifi {address}")
                data = await client.read_gatt_char(RECV_UUID)
                if Config.log_polaris_ble:
                    self.logger.info(f"BLE Read request {bytes2hexascii(data)}")
                await asyncio.sleep(30) # give time for client notification_handler
        except Exception as e:
            self.logger.warn(f"Failed to enable Wifi {address}: {e}")


    async def runBleScanner(self):
        async with BleakScanner(self.scannerCallback) as scanner:
            await asyncio.sleep(15)
            while not self.lifecycle.should_shutdown():
                await self.lifecycle.wait_for_event()

