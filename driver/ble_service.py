from __future__ import annotations
import asyncio
import json
from bleak import BleakScanner, BleakClient, exc
from bleak.exc import BleakError
from shr import LifecycleController, bytes2hexascii
from config import Config
import time

ENABLE_WIFI_COMMAND = "enable_wifi"
SEND_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
RECV_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

class BLE_Controller():
    def __init__(self, logger, lifecycle:LifecycleController, isConnectedFn):
        self.logger = logger
        self.lifecycle = lifecycle
        self.devices: dict[str, dict] = { }
        self.selectedDevice = None
        self.isEnablingWifi = False
        self.isWifiEnabled = False
        self.isConnectedFn = isConnectedFn
        self._scan_lock = asyncio.Lock()

    def get_address_by_name(self, name: str | None) -> str | None:
        if not name:
            return None
        name = name.lower()
        for addr, info in self.devices.items():
            if info.get("name", "").lower() == name:
                return addr
        return None


    def prune_stale_devices(self, timeout=60):
        now = time.monotonic()
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

    async def safe_BLE_discover(self, timeout=3.0):
        async with self._scan_lock:
            try:
                return await BleakScanner.discover(timeout=timeout)
            except BleakDBusError as e:
                if "InProgress" in str(e):
                    self.logger.warning("BLE scan already in progress, skipping")
                else:
                    self.logger.warning(f"BLE Discover Attempt {attempt} failed: {e}")


    async def setSelectedDevice(self, name):
        if any(dev.get("name") == name for dev in self.devices.values()):
            if self.selectedDevice != name:
                self.selectedDevice = name
                await self.enableWifi() 

    async def enableWifi(self):
        name = self.selectedDevice
        address = self.get_address_by_name(name)
        if not address:
            return
        
        if Config.log_polaris_ble:
            await self.listCharacteristics()
            
        self.isEnablingWifi = True
        self.isWifiEnabled = False
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                if Config.log_polaris_ble:
                    self.logger.info(f"BLE Connecting to {address} (attempt {attempt})")

                async with BleakClient(address, timeout=10.0) as client:
                    # Explicitly wait for services (cross-platform)
                    try:
                        services = await getattr(client, "get_services", lambda: client.services)()
                    except Exception:
                        services = client.services

                    # Sanity-check expected UUIDs
                    send_char = services.get_characteristic(SEND_UUID)
                    recv_char = services.get_characteristic(RECV_UUID)
                    if not (send_char and recv_char):
                        raise BleakError("Expected characteristics not found")
                    if not any(p in send_char.properties for p in ("write", "write-without-response")):
                        raise BleakError(f"Characteristic {SEND_UUID} is not writable: {send_char.properties}")

                    await client.start_notify(RECV_UUID, self.notification_handler)
                    await asyncio.sleep(0.3)  # Allow macOS/Windows to settle
                    await client.write_gatt_char(SEND_UUID, b"enable_wifi", response=True)

                    if Config.log_polaris_ble:
                        self.logger.info(f"BLE Sent enable_wifi to {address}")

                    data = await client.read_gatt_char(RECV_UUID)
                    if Config.log_polaris_ble:
                        self.logger.info(f"BLE Read: {bytes2hexascii(data)}")

                    self.isEnablingWifi = False
                    self.isWifiEnabled = True
                    return

            except asyncio.TimeoutError:
                if Config.log_polaris_ble:
                    self.logger.warning(f"BLE timeout on connect attempt {attempt} for {address}")
            except asyncio.CancelledError:
                if Config.log_polaris_ble:
                    self.logger.warning(f"BLE connect cancelled (WinRT stall) on attempt {attempt}")
                await asyncio.sleep(2)  # small cooldown before retry
            except OSError as e:
                if e.winerror == -2147023673:
                    self.logger.warning("BLE operation canceled by system (WinError -2147023673)")
                    await asyncio.sleep(2)
                    continue
            except BleakError as e:
                if Config.log_polaris_ble:
                    self.logger.warning(f"BLE Attempt {attempt} failed for {address}: {e}")
            except Exception as e:
                self.logger.exception(f"Unexpected BLE error on attempt {attempt}: {e}")

            # Re-scan between retries
            if attempt < max_attempts:
                await asyncio.sleep(3)
                await self.safe_BLE_discover(timeout=3.0)

        if Config.log_polaris_ble:
            self.logger.error(f"BLE failed to enable Wi-Fi after {max_attempts} attempts")
        self.isEnablingWifi = False

    def scannerCallback(self, device, adv):
        name = (adv.local_name or device.name or "").lower()
        if Config.log_polaris_ble and Config.log_polaris_polling:
            self.logger.info(f"BLE Discovered Device Name: {name}, Address: {device.address}, RSSI: {adv.rssi}")
        if not name.startswith("polaris"):
            return
        now = time.monotonic()
        addr = device.address
        # existing or new entry
        existing = self.devices.get(addr)
        last_seen = existing.get("last_seen", 0) if existing else 0
        # Skip if we've seen it too recently (< 1s)
        if now - last_seen < 1.0:
            return
        self.devices[addr] = {
            "name": name,
            "address": addr,
            "service_uuids": adv.service_uuids,
            "rssi": adv.rssi,
            "last_seen": now,
        }
        if self.selectedDevice is None:
            asyncio.create_task(self.setSelectedDevice(name))
        if Config.log_polaris_ble:
            self.logger.info(f"BLE Discovered Polaris: {addr} ({self.devices[addr]})")

    async def runBleScanner(self):
        try:
            async with BleakScanner(self.scannerCallback) as scanner:
                self.logger.info(f'==STARTUP== Starting Bluetooth scanner.')
                while not self.lifecycle.should_shutdown():
                    self.prune_stale_devices()
                    if not self.isConnectedFn():
                        await self.enableWifi()
                    await asyncio.sleep(30)
        except (BleakError, OSError) as e:
            if ("Bluetooth device is turned off" in str(e)
            or "Failed to start scanner" in str(e)
            or "device is not ready" in str(e)):
                self.logger.warning("Bluetooth is off. Skipping BLE scan.")
            else:
                self.logger.exception(f"BLE scan failed: {e}")

