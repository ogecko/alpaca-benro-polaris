from __future__ import annotations
import asyncio
import sys
import time
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError
from shr import LifecycleController, bytes2hexascii
from config import Config

POLARIS_ADVERTISED_UUID = "00007370-0000-1000-8000-00805f9b34fb"
SEND_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
RECV_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

IS_LINUX   = sys.platform == "linux"
IS_WINDOWS = sys.platform == "win32"
IS_MACOS   = sys.platform == "darwin"

CONNECT_TIMEOUT    = 15.0 if IS_LINUX else 10.0
POST_CONNECT_SLEEP = 1.0  if IS_LINUX else 0.3
NOTIFY_TIMEOUT     = 5.0

# Substrings identifying "no usable Bluetooth" conditions, as opposed to unexpected
# scanner errors. Includes the FileNotFoundError bleak/dbus_fast raise when there's no
# D-Bus/BlueZ to connect to at all (e.g. containers, WSL2) rather than an adapter that's
# merely off.
BT_UNAVAILABLE_MESSAGES = (
    "Bluetooth device is turned off",
    "Failed to start scanner",
    "No powered Bluetooth adapters found",
    "device is not ready",
    "No such file or directory",
    "was not provided by any .service files",   # BlueZ/D-Bus service not installed or not running (e.g. native WSL2)
)


class BLE_Controller:
    def __init__(self, logger, lifecycle: LifecycleController, isConnectedFn):
        self.logger         = logger
        self.lifecycle      = lifecycle
        self.isConnectedFn  = isConnectedFn
        self.devices: dict[str, dict] = {}
        self.selectedDevice = None
        self.isEnablingWifi = False
        self.isWifiEnabled  = False
        self._wifi_lock     = asyncio.Lock()
        self._bt_unavailable_logged = False
        self._scanner: BleakScanner | None = None
        self._scanning      = False

    # ------------------------------------------------------------------
    # Device registry helpers
    # ------------------------------------------------------------------

    def get_address_by_name(self, name: str | None) -> str | None:
        if not name:
            return None
        name = name.lower()
        for addr, info in self.devices.items():
            if info.get("name", "").lower() == name:
                return addr
        return None

    def prune_stale_devices(self, timeout=60):
        now   = time.monotonic()
        stale = [
            addr for addr, info in self.devices.items()
            if now - info.get("last_seen", 0) > timeout
        ]
        for addr in stale:
            if self.selectedDevice == self.devices[addr].get("name"):
                continue    # dont prune the currently selected device
            self.logger.info(f"BLE pruning stale device: {addr}")
            del self.devices[addr]

    # ------------------------------------------------------------------
    # Notification handler
    # ------------------------------------------------------------------

    def notification_handler(self, sender, data):
        if Config.log_polaris_ble:
            self.logger.info(f"BLE << Polaris: {data.decode(errors='ignore')}")

    # ------------------------------------------------------------------
    # Scanner start / stop
    # ------------------------------------------------------------------

    async def _start_scanner(self):
        if self._scanning:
            return
        try:
            self._scanner = BleakScanner(self.scannerCallback, service_uuids=[POLARIS_ADVERTISED_UUID])
            await self._scanner.start()
            self._scanning = True
            self._bt_unavailable_logged = False
            if Config.log_polaris_ble:
                self.logger.info("BLE scanner started")
        except (BleakError, OSError) as e:
            msg = str(e)
            if any(s in msg for s in BT_UNAVAILABLE_MESSAGES):
                if not self._bt_unavailable_logged:
                    self.logger.warning(f"Bluetooth unavailable, cannot start scanner: {e}")
                    self._bt_unavailable_logged = True
            else:
                self.logger.exception(f"BLE scanner start failed: {e}")

    async def _stop_scanner(self):
        if not self._scanning or self._scanner is None:
            return
        try:
            await self._scanner.stop()
            if Config.log_polaris_ble:
                self.logger.info("BLE scanner stopped")
        except Exception as e:
            self.logger.warning(f"BLE scanner stop warning: {e}")
        finally:
            self._scanning = False

    # ------------------------------------------------------------------
    # Scanning loop
    # ------------------------------------------------------------------

    def scannerCallback(self, device, adv):
        name = (adv.local_name or device.name or "").lower()
        if not name.startswith("polaris"):
            return

        now  = time.monotonic()
        addr = device.address
        existing  = self.devices.get(addr)
        last_seen = existing.get("last_seen", 0) if existing else 0

        # Only log every 30s for known devices; always log new ones
        log_threshold = 30.0 if existing else 0.0
        should_log    = (now - last_seen) >= log_threshold

        if now - last_seen < 1.0:
            return

        self.devices[addr] = {
            "name":          name,
            "address":       addr,
            "service_uuids": adv.service_uuids,
            "rssi":          adv.rssi,
            "last_seen":     now,
        }

        if self.selectedDevice is None:
            asyncio.create_task(self.setSelectedDevice(name))

        if Config.log_polaris_ble and should_log:
            self.logger.info(f"BLE Polaris registered: {addr} ({self.devices[addr]})")


    async def runBleScanner(self):
        try:
            self.logger.info("==STARTUP== Bluetooth scanner running.")
            while not self.lifecycle.should_shutdown():
                self.prune_stale_devices()
                if self.isConnectedFn():
                    # Connected — scanner not needed, make sure it's off
                    await self._stop_scanner()
                else:
                    # Not connected — ensure scanner is running to find Polaris
                    await self._start_scanner()
                    await self.enableWifi()
                await asyncio.sleep(30)

        except (BleakError, OSError) as e:
            msg = str(e)
            if any(s in msg for s in BT_UNAVAILABLE_MESSAGES):
                self.logger.warning("Bluetooth is off -- skipping BLE scan.")
            else:
                self.logger.exception(f"BLE scan failed: {e}")
            await asyncio.sleep(10)
        finally:
            await self._stop_scanner()

    # ------------------------------------------------------------------
    # Device selection
    # ------------------------------------------------------------------

    async def setSelectedDevice(self, name):
        if any(dev.get("name") == name for dev in self.devices.values()):
            if self.selectedDevice != name:
                self.selectedDevice = name
                await self.enableWifi()

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def listCharacteristics(self, address: str):
        try:
            async with BleakClient(address, timeout=CONNECT_TIMEOUT) as client:
                await asyncio.sleep(POST_CONNECT_SLEEP)
                for service in client.services:
                    self.logger.info(f"  Service: {service.uuid} -- {service.description}")
                    for char in service.characteristics:
                        props = ", ".join(char.properties)
                        self.logger.info(
                            f"    Char: {char.uuid} ({char.description}) [{props}]"
                        )
        except Exception as e:
            if Config.log_polaris_ble:
                self.logger.info(f"listCharacteristics skipped for {address}: {e}")

    # ------------------------------------------------------------------
    # Platform helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_needs_response(char) -> bool:
        props = char.properties
        if IS_LINUX:
            return "write-without-response" not in props
        return "write" in props

    async def _reset_bluetooth_adapter(self):
        if not IS_LINUX:
            return
        try:
            proc = await asyncio.create_subprocess_exec(
                "hciconfig", "hci0", "reset",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except Exception as e:
             if Config.log_polaris_ble:
                self.logger.info(f"BLE adapter reset skipped/failed: {e}")

    # ------------------------------------------------------------------
    # Core: enable Wi-Fi over BLE
    # ------------------------------------------------------------------

    async def enableWifi(self):
        if self._wifi_lock.locked():
            return
        async with self._wifi_lock:
            await self._enableWifi_inner()

    async def _enableWifi_inner(self):
        name    = self.selectedDevice
        address = self.get_address_by_name(name)
        if not address:
            return

        self.isEnablingWifi = True
        self.isWifiEnabled  = False
        max_attempts        = 3

        # Stop scanner: BlueZ cannot scan and connect simultaneously.
        # We also wait longer on Linux so BlueZ fully drains any in-flight
        # advertisement processing -- this reduces (but cannot eliminate)
        # the br-connection-profile-unavailable transient error, which is
        # caused by BlueZ re-caching the device from recent advertisements.
        # We treat that error as a normal retry condition rather than trying
        # to fight it with bluetoothctl remove (which doesn't help since
        # BlueZ immediately re-caches from the advertisement pipeline).
        await self._stop_scanner()
        await asyncio.sleep(3.0 if IS_LINUX else 0.5)

        if Config.log_polaris_ble:
            await self.listCharacteristics(address)

        for attempt in range(1, max_attempts + 1):

            if self.isConnectedFn():
                if Config.log_polaris_ble:
                    self.logger.info("BLE wifi already connected, skipping remaining attempts")
                self.isEnablingWifi = False
                self.isWifiEnabled  = True
                break

            try:
                if Config.log_polaris_ble:
                    self.logger.info(
                        f"BLE connecting to {address} "
                        f"(attempt {attempt}/{max_attempts})"
                    )

                async with BleakClient(address, timeout=CONNECT_TIMEOUT) as client:
                    await asyncio.sleep(POST_CONNECT_SLEEP)

                    services  = client.services
                    send_char = services.get_characteristic(SEND_UUID)
                    recv_char = services.get_characteristic(RECV_UUID)

                    if not (send_char and recv_char):
                        raise BleakError("Expected characteristics not found")
                    if not any(p in send_char.properties
                               for p in ("write", "write-without-response")):
                        raise BleakError(
                            f"Characteristic {SEND_UUID} is not writable: "
                            f"{send_char.properties}"
                        )

                    try:
                        await asyncio.wait_for(
                            client.start_notify(RECV_UUID, self.notification_handler),
                            timeout=NOTIFY_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        self.logger.warning(
                            "BLE start_notify timed out -- continuing anyway"
                        )

                    await asyncio.sleep(0.3)

                    use_response = self._write_needs_response(send_char)
                    await client.write_gatt_char(
                        SEND_UUID, b"enable_wifi", response=use_response
                    )

                    if Config.log_polaris_ble:
                        self.logger.info(
                            f"BLE >> sent enable_wifi to {address} "
                            f"(response={use_response})"
                        )

                    data = await client.read_gatt_char(RECV_UUID)
                    if Config.log_polaris_ble:
                        self.logger.info(f"BLE << read: {bytes2hexascii(data)}")

                    self.isEnablingWifi = False
                    self.isWifiEnabled  = True
                    break

            except asyncio.TimeoutError:
                self.logger.warning(
                    f"BLE timeout on connect attempt {attempt} for {address}"
                )

            except asyncio.CancelledError:
                self.logger.warning(
                    f"BLE connect cancelled on attempt {attempt} "
                    f"(possible WinRT stall)"
                )
                await asyncio.sleep(2)

            except OSError as e:
                if IS_WINDOWS and getattr(e, "winerror", None) == -2147023673:
                    self.logger.warning(
                        "BLE operation aborted by Windows (WinError -2147023673)"
                    )
                    await asyncio.sleep(2)
                else:
                    self.logger.warning(f"BLE OSError on attempt {attempt}: {e}")

            except BleakError as e:
                err = str(e)
                # br-connection-profile-unavailable is a transient BlueZ
                # condition during startup -- log as INFO since we recover
                # automatically via retry and isConnectedFn() early exit.
                if "br-connection-profile-unavailable" in err or \
                   "NotAvailable" in err:
                    self.logger.info(
                        f"BLE attempt {attempt}: BlueZ BR/EDR cache active for "
                        f"{address}, will retry..."
                    )
                else:
                    if Config.log_polaris_ble:
                        self.logger.warning(f"BLE attempt {attempt} failed for {address}: {e}")

            except Exception as e:
                self.logger.exception(
                    f"Unexpected BLE error on attempt {attempt}: {e}"
                )

            if attempt < max_attempts and not self.isWifiEnabled:
                await asyncio.sleep(3)
                await self._reset_bluetooth_adapter()

        if not self.isWifiEnabled:
            self.logger.error(
                f"BLE failed to enable Wi-Fi after {max_attempts} attempts "
                f"for {address}"
            )
            self.isEnablingWifi = False

        if not self.isConnectedFn():
            try:
                await self._start_scanner()
            except Exception as e:
                self.logger.warning(f"BLE failed to restart scanner: {e}")