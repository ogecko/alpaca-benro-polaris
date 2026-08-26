"""
join_wifi.py

Joins the host OS to a Benro Polaris' WiFi hotspot -- the network layer,
distinct from the driver's own application-level *connection* to the
Polaris firmware on :9090 (see polaris.py / Polaris.client(), p.connected
in Alpaca Pilot). 

Owns WiFi-join logic for every platform the driver supports. Today only
Windows is implemented (via netsh wlan, mirroring what the Benro app does
automatically before it opens a socket to the mount). Linux/Raspberry Pi
and macOS are stubs pending platform-specific implementations -- see
platforms/raspberry_pi/wifi.sh for prior art on the Linux/RPi side
(wpa_supplicant-based, a different mechanism entirely); macOS has none yet
and would need networksetup(8).

join_wifi_network() is the entry point other driver modules should call
(BLE_Controller.enableWifiAndJoin(), ble_service.py). Its implementation is
synchronous -- it shells out to platform CLI network tools and can block
for several seconds per attempt -- so callers on the driver's asyncio loop
MUST wrap it in asyncio.to_thread(), never await it directly, or it will
stall the PID control loop and everything else for the duration.

CLI usage -- auto-discover and join, open network:
    python join_wifi.py

With a password (network is WPA2, not open):
    python join_wifi.py "" mypassword123

Target a specific SSID directly, skipping discovery:
    python join_wifi.py polaris_b83c06
    python join_wifi.py polaris_b83c06 mypassword123

As a library, the entry point most callers want:
    join_wifi_network(ssid, password="", timeout=15.0, interface=None,
                       prefer_keywords=("usb",))
"""

import logging
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform == "linux"
IS_MACOS   = sys.platform == "darwin"

# Propagates to root -- picks up the driver's own timestamp/level formatting
# and file/queue handlers automatically when imported into the driver process
# (see ble_service.py), with zero extra wiring needed there, the same way the
# zeroconf/uvicorn loggers already do (see log.py). CLI/standalone use (the
# __main__ block below) configures its own plain handler so this isn't silently
# dropped when run outside the driver.
logger = logging.getLogger(__name__)

PROFILE_TEMPLATE_WPA2 = """<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <hex>{ssid_hex}</hex>
            <name>{ssid}</name>
        </SSID>
        <nonBroadcast>false</nonBroadcast>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>manual</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>
"""

# Open networks (no password) can't carry a sharedKey block at all -
# WPA2PSK requires an 8-63 char PSK, so an empty/missing password must
# use authentication=open, encryption=none instead. The Polaris hotspot is
# always open in practice, but this is kept for forward-compatibility and
# for anyone running the driver against a secured network of their own.
PROFILE_TEMPLATE_OPEN = """<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <hex>{ssid_hex}</hex>
            <name>{ssid}</name>
        </SSID>
        <nonBroadcast>false</nonBroadcast>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>manual</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>open</authentication>
                <encryption>none</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
        </security>
    </MSM>
</WLANProfile>
"""


@dataclass
class WifiInterface:
    name: str
    description: str
    state: str  # e.g. "connected", "disconnected"
    ssid: Optional[str] = None


def _run(cmd: List[str]):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    return result.returncode, result.stdout, result.stderr


# ──────────────────────────────────────────────────────────────────────────
# Windows (netsh wlan)
# ──────────────────────────────────────────────────────────────────────────

def _list_interfaces_win() -> List[WifiInterface]:
    """Parses `netsh wlan show interfaces` into structured records. Handles
    zero, one, or many WiFi adapters present on the machine."""
    _, out, _ = _run(["netsh.exe", "wlan", "show", "interfaces"])

    interfaces = []
    current = {}
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"^(Name|Description|State|SSID)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()

        if key == "Name":
            if current.get("Name"):
                interfaces.append(current)
            current = {"Name": value}
        elif key in ("Description", "State", "SSID"):
            current[key] = value

    if current.get("Name"):
        interfaces.append(current)

    return [
        WifiInterface(
            name=c["Name"],
            description=c.get("Description", ""),
            state=c.get("State", "unknown"),
            ssid=c.get("SSID"),
        )
        for c in interfaces
    ]


def _choose_interface_win(interfaces: List[WifiInterface],
                           explicit_name: Optional[str] = None,
                           prefer_keywords: tuple = ("usb",)) -> WifiInterface:
    """Picks which WiFi adapter to use for the Polaris join.

    - If the caller named one explicitly, use that.
    - If there's only one adapter, use it (matches the original
      single-adapter behaviour - will take over whatever it's doing).
    - Otherwise, rank candidates by:
        1) description matches one of prefer_keywords (default: "usb") -
           dedicated USB WiFi dongles are what ABP recommends for the
           Polaris, since most built-in laptop chipsets fail to
           associate with its onboard AP at all. Matching on "usb"
           rather than a specific vendor keeps this generic across
           whatever dongle brand a given user has (TP-Link, Realtek,
           Alfa, etc.) rather than hardcoding one.
        2) currently disconnected - so we don't tear down the user's
           existing WiFi connection on their main adapter.
      Highest-ranked candidate wins.
    """
    if not interfaces:
        raise RuntimeError("No WiFi interfaces found on this system.")

    if explicit_name:
        for i in interfaces:
            if i.name == explicit_name:
                return i
        raise RuntimeError(
            f"Interface '{explicit_name}' not found. Available: "
            f"{[i.name for i in interfaces]}"
        )

    if len(interfaces) == 1:
        return interfaces[0]

    def score(i: WifiInterface):
        is_preferred_hw = any(k.lower() in i.description.lower() for k in prefer_keywords)
        is_disconnected = i.state.lower() == "disconnected"
        return (is_preferred_hw, is_disconnected)

    return max(interfaces, key=score)


def _add_profile_win(ssid: str, password: str = "", interface: Optional[str] = None) -> None:
    """Registers (or overwrites) a WLAN profile scoped to the current user
    (no admin prompt needed), optionally scoped to a specific adapter.

    If password is empty/None, builds an OPEN-network profile instead of
    a WPA2PSK one - netsh rejects WPA2PSK profiles with an empty key
    ("Invalid PSK length") since a real PSK must be 8-63 characters.
    """
    ssid_hex = ssid.encode("utf-8").hex()
    if password:
        if not (8 <= len(password) <= 63):
            raise ValueError(
                f"WPA2 PSK must be 8-63 characters, got {len(password)}. "
                "If the Polaris hotspot has no password, pass password=''."
            )
        xml = PROFILE_TEMPLATE_WPA2.format(ssid=ssid, ssid_hex=ssid_hex, password=password)
    else:
        xml = PROFILE_TEMPLATE_OPEN.format(ssid=ssid, ssid_hex=ssid_hex)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(xml)
        profile_path = f.name

    try:
        # Delete any pre-existing profile of this name first, in both scopes
        # (best-effort -- failure here is expected/harmless, eg. it doesn't
        # exist in that particular scope). Without this, `add profile
        # user=current` fails with "already exists in group policy or
        # different user scope and cannot be overwritten" whenever the SSID
        # was previously joined manually via Windows' own WiFi UI, which
        # defaults to all-users scope rather than user=current -- ie. every
        # user who ever connected to their Polaris hotspot before this
        # feature existed.
        del_cmd = ["netsh.exe", "wlan", "delete", "profile", f"name={ssid}"]
        if interface:
            del_cmd.append(f"interface={interface}")
        _run(del_cmd + ["user=current"])
        _run(del_cmd)  # default (all-users) scope

        cmd = ["netsh.exe", "wlan", "add", "profile",
               f"filename={profile_path}", "user=current"]
        if interface:
            cmd.append(f"interface={interface}")
        code, out, err = _run(cmd)
        if code != 0:
            raise RuntimeError(f"Failed to add WLAN profile: {out}{err}")
    finally:
        Path(profile_path).unlink(missing_ok=True)


def _diagnose_win(ssid: str, interface: Optional[str] = None) -> None:
    """Prints what Windows actually sees for this SSID and interface right
    now - the real authentication type it detected, signal strength, and
    the interface's own connection state/reason. Called on join failure so
    there's something actionable in the log beyond "it didn't work"."""
    logger.info("--- netsh wlan show interfaces ---")
    _, out, _ = _run(["netsh.exe", "wlan", "show", "interfaces"])
    logger.info(out)

    logger.info(f"--- netsh wlan show networks mode=bssid (filtered to '{ssid}') ---")
    _, out, _ = _run(["netsh.exe", "wlan", "show", "networks", "mode=bssid"])
    blocks = out.split("\n\n")
    matched = [b for b in blocks if ssid in b]
    logger.info("\n\n".join(matched) if matched else
                f"'{ssid}' was NOT found in the current scan results at all.")

    logger.info("--- Recent WLAN-AutoConfig events (association/auth failures) ---")
    ps_cmd = (
        "Get-WinEvent -LogName 'Microsoft-Windows-WLAN-AutoConfig/Operational' "
        "-MaxEvents 15 | Where-Object {$_.Id -in 8001,8002,8003,11001,11002} "
        "| Select-Object TimeCreated,Id,Message | Format-List"
    )
    _, out, err = _run(["powershell.exe", "-NoProfile", "-Command", ps_cmd])
    logger.info(out or err or "(no matching events, or Event Viewer access denied)")


def _connect_win(ssid: str, interface: str, timeout: float = 15.0, retries: int = 3) -> bool:
    """Joins a specific named interface to ssid, with retries - netsh wlan
    connect can fire before the WLAN service's internal scan cache has
    refreshed, producing a spurious 'specific network not available'
    even when the SSID is genuinely in range."""
    for attempt in range(1, retries + 1):
        _run(["netsh.exe", "wlan", "show", "networks", "mode=bssid"])
        time.sleep(2)

        code, out, err = _run([
            "netsh.exe", "wlan", "connect",
            f"name={ssid}", f"ssid={ssid}", f"interface={interface}",
        ])
        if code != 0:
            raise RuntimeError(f"netsh wlan connect failed: {out}{err}")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for iface in _list_interfaces_win():
                if iface.name == interface and iface.state.lower() == "connected" \
                        and iface.ssid == ssid:
                    return True
            time.sleep(1)

        if attempt < retries:
            logger.info(f"Attempt {attempt}/{retries} timed out, retrying...")

    return False


def _join_wifi_network_win(ssid: str, password: str = "", timeout: float = 15.0,
                            interface: Optional[str] = None,
                            prefer_keywords: tuple = ("usb",)) -> bool:
    interfaces = _list_interfaces_win()
    chosen = _choose_interface_win(interfaces, explicit_name=interface,
                                    prefer_keywords=prefer_keywords)

    # Idempotency: skip the whole dance if this adapter is already on the
    # target network -- avoids a spurious brief re-association on every
    # click of the Alpaca Pilot Wi-Fi button.
    if chosen.state.lower() == "connected" and chosen.ssid == ssid:
        logger.info(f"Already joined to '{ssid}' on {chosen.name}.")
        return True

    logger.info(f"Using WiFi interface: {chosen.name} ({chosen.description})")

    _add_profile_win(ssid, password, interface=chosen.name)
    ok = _connect_win(ssid, interface=chosen.name, timeout=timeout)
    if ok:
        logger.info(f"Joined '{ssid}' on {chosen.name}.")
    else:
        _diagnose_win(ssid, interface=chosen.name)
    return ok


# ──────────────────────────────────────────────────────────────────────────
# Public, platform-dispatching entry point
# ──────────────────────────────────────────────────────────────────────────

def join_wifi_network(ssid: str, password: str = "", timeout: float = 15.0,
                       interface: Optional[str] = None,
                       prefer_keywords: tuple = ("usb",)) -> bool:
    """Join the host OS to a known Polaris SSID -- the entry point other
    driver modules should call (synchronous; wrap in asyncio.to_thread()
    from async callers). Returns False on unsupported platforms rather than
    raising; callers are responsible for logging that outcome.

    interface: force a specific adapter name (e.g. 'Wi-Fi 2', Windows only
    today). Leave as None to auto-select.
    prefer_keywords: when auto-selecting among multiple adapters, rank ones
    whose description matches these (default: "usb") above others.
    """
    if IS_WINDOWS:
        return _join_wifi_network_win(ssid, password, timeout=timeout,
                                       interface=interface, prefer_keywords=prefer_keywords)
    # Linux/Raspberry Pi: platforms/raspberry_pi/wifi.sh covers this today as a
    # separate standalone script (wpa_supplicant-based); not yet wired in here.
    # macOS: not yet implemented (would use networksetup(8)).
    return False


# ──────────────────────────────────────────────────────────────────────────
# Discovery + CLI (standalone/manual use -- not called by the driver itself,
# which always already knows the target SSID from the BLE-selected device)
# ──────────────────────────────────────────────────────────────────────────

def discover_polaris_networks(ssid_pattern: str = r"^polaris_[0-9a-zA-Z]+$") -> List[str]:
    """Scans for currently-visible SSIDs matching the Polaris naming
    pattern (e.g. polaris_b83c06). Windows only. Returns a de-duplicated,
    sorted list of matching SSID names."""
    if not IS_WINDOWS:
        raise RuntimeError("discover_polaris_networks() is only implemented on Windows.")
    _run(["netsh.exe", "wlan", "show", "networks", "mode=bssid"])  # refresh scan cache
    time.sleep(1)
    _, out, _ = _run(["netsh.exe", "wlan", "show", "networks"])

    pattern = re.compile(ssid_pattern, re.IGNORECASE)
    found = set()
    for line in out.splitlines():
        m = re.match(r"^\s*SSID\s+\d+\s*:\s*(.+?)\s*$", line)
        if m and pattern.match(m.group(1)):
            found.add(m.group(1))

    return sorted(found)


def select_polaris_network(ssid_pattern: str = r"^polaris_[0-9a-zA-Z]+$") -> str:
    """Finds visible Polaris hotspots. Auto-picks the only one if there's
    exactly one; otherwise prompts the user to choose. CLI/interactive use
    only -- raises if none are visible. Never called by the driver itself
    (which already knows the exact SSID from the BLE-selected device, and
    has no console to prompt on)."""
    candidates = discover_polaris_networks(ssid_pattern)

    if not candidates:
        raise RuntimeError(
            "No Polaris hotspot found in range.\n"
            "  - Confirm the Polaris is powered on (blue WiFi LED lit)\n"
            "  - Move closer - weak signal can drop it from scan results\n"
            "  - If using a dedicated USB WiFi adapter, confirm it's plugged in\n"
            "  - Some built-in laptop WiFi chipsets can't see/associate with the "
            "Polaris at all - a USB WiFi adapter is the standard fix"
        )

    if len(candidates) == 1:
        print(f"Found Polaris hotspot: {candidates[0]}")
        return candidates[0]

    print(f"Found {len(candidates)} Polaris hotspots:")
    for i, ssid in enumerate(candidates, 1):
        print(f"  {i}. {ssid}")

    while True:
        choice = input(f"Select a device (1-{len(candidates)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
        print("Invalid selection, try again.")


def find_and_join_wifi_network(password: str = "", timeout: float = 15.0,
                                interface: Optional[str] = None,
                                prefer_keywords: tuple = ("usb",),
                                ssid_pattern: str = r"^polaris_[0-9a-zA-Z]+$") -> bool:
    """Discovers nearby Polaris hotspot(s), resolves which one to use (auto
    if unambiguous, prompts otherwise), then joins. CLI/interactive use
    only -- see select_polaris_network()."""
    ssid = select_polaris_network(ssid_pattern)
    return join_wifi_network(ssid, password, timeout=timeout,
                              interface=interface, prefer_keywords=prefer_keywords)


if __name__ == "__main__":
    # Standalone/CLI use has no driver logging set up (init_logging() in
    # log.py never runs outside the full driver process), so without this
    # the logger.info() calls above would go nowhere. Plain "%(message)s" to
    # match the original print()-based console UX.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) > 3:
        print("Usage: join_wifi.py [SSID] [PASSWORD]")
        print("Omit SSID to auto-discover nearby Polaris hotspot(s).")
        print("Omit PASSWORD if the Polaris hotspot is open/unsecured.")
        sys.exit(1)

    ssid_arg = sys.argv[1] if len(sys.argv) >= 2 else None
    password_arg = sys.argv[2] if len(sys.argv) == 3 else ""

    try:
        if ssid_arg:
            ok = join_wifi_network(ssid_arg, password_arg)
        else:
            ok = find_and_join_wifi_network(password_arg)
    except RuntimeError as e:
        # Expected/anticipated failures (no device found, netsh errors,
        # no WiFi interfaces, etc.) - print just the message, no traceback.
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        # e.g. invalid password length
        print(f"Error: {e}")
        sys.exit(1)

    print("Joined." if ok else "Failed to join within timeout.")
    sys.exit(0 if ok else 1)
