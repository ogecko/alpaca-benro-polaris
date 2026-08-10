"""
connect.py

Programmatically join a Windows PC to a Benro Polaris' WiFi hotspot,
mirroring what the Benro app does automatically before it opens a
socket to the mount.

Auto-discovers nearby polaris_XXXXXX hotspots, connects automatically
if only one is found, or prompts you to pick when several are in
range. Multi-adapter aware: if the PC has more than one WiFi
interface (e.g. a built-in adapter plus a dedicated USB dongle - many
built-in chipsets can't associate with the Polaris' onboard AP at
all), it prefers a USB adapter and won't drop an unrelated active
WiFi connection on another adapter.

Simplest usage - auto-discover and connect, open network:
    python connect.py

With a password (network is WPA2, not open):
    python connect.py "" mypassword123

Target a specific SSID directly, skipping discovery:
    python connect.py polaris_b83c06
    python connect.py polaris_b83c06 mypassword123

All optional parameters, for use as a library from main.py:
    find_and_connect_to_polaris(
        password="",            # omit/empty for an open network
        timeout=15.0,           # seconds to wait per connection attempt
        interface=None,         # force a specific adapter name, e.g. "Wi-Fi 2"
        prefer_keywords=("usb",),   # adapter description keywords to prefer
        ssid_pattern=r"^polaris_[0-9a-zA-Z]+$",  # override SSID matching
    )
    connect_to_polaris(ssid, password="", timeout=15.0, interface=None,
                        prefer_keywords=("usb",))  # connect to a known SSID directly
"""

import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

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
# use authentication=open, encryption=none instead.
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


def list_interfaces() -> List[WifiInterface]:
    """Parses `netsh wlan show interfaces` into structured records. Handles
    zero, one, or many WiFi adapters present on the machine."""
    _, out, _ = _run(["netsh", "wlan", "show", "interfaces"])

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


def choose_interface(interfaces: List[WifiInterface],
                      explicit_name: Optional[str] = None,
                      prefer_keywords: tuple = ("usb",)) -> WifiInterface:
    """Picks which WiFi adapter to use for the Polaris connection.

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


def add_profile(ssid: str, password: str = "", interface: Optional[str] = None) -> None:
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
        cmd = ["netsh", "wlan", "add", "profile",
               f"filename={profile_path}", "user=current"]
        if interface:
            cmd.append(f"interface={interface}")
        code, out, err = _run(cmd)
        if code != 0:
            raise RuntimeError(f"Failed to add WLAN profile: {out}{err}")
    finally:
        Path(profile_path).unlink(missing_ok=True)


def diagnose(ssid: str, interface: Optional[str] = None) -> None:
    """Prints what Windows actually sees for this SSID and interface right
    now - the real authentication type it detected, signal strength, and
    the interface's own connection state/reason."""
    print("\n--- netsh wlan show interfaces ---")
    _, out, _ = _run(["netsh", "wlan", "show", "interfaces"])
    print(out)

    print(f"--- netsh wlan show networks mode=bssid (filtered to '{ssid}') ---")
    _, out, _ = _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    blocks = out.split("\n\n")
    matched = [b for b in blocks if ssid in b]
    print("\n\n".join(matched) if matched else
          f"'{ssid}' was NOT found in the current scan results at all.")

    print("\n--- Recent WLAN-AutoConfig events (association/auth failures) ---")
    ps_cmd = (
        "Get-WinEvent -LogName 'Microsoft-Windows-WLAN-AutoConfig/Operational' "
        "-MaxEvents 15 | Where-Object {$_.Id -in 8001,8002,8003,11001,11002} "
        "| Select-Object TimeCreated,Id,Message | Format-List"
    )
    _, out, err = _run(["powershell", "-NoProfile", "-Command", ps_cmd])
    print(out or err or "(no matching events, or Event Viewer access denied)")


def connect(ssid: str, interface: str, timeout: float = 15.0, retries: int = 3) -> bool:
    """Connects on a specific named interface, with retries - netsh wlan
    connect can fire before the WLAN service's internal scan cache has
    refreshed, producing a spurious 'specific network not available'
    even when the SSID is genuinely in range."""
    for attempt in range(1, retries + 1):
        _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
        time.sleep(2)

        code, out, err = _run([
            "netsh", "wlan", "connect",
            f"name={ssid}", f"ssid={ssid}", f"interface={interface}",
        ])
        if code != 0:
            raise RuntimeError(f"netsh wlan connect failed: {out}{err}")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for iface in list_interfaces():
                if iface.name == interface and iface.state.lower() == "connected" \
                        and iface.ssid == ssid:
                    return True
            time.sleep(1)

        if attempt < retries:
            print(f"Attempt {attempt}/{retries} timed out, retrying...")

    return False


def discover_polaris_networks(ssid_pattern: str = r"^polaris_[0-9a-zA-Z]+$") -> List[str]:
    """Scans for currently-visible SSIDs matching the Polaris naming
    pattern (e.g. polaris_b83c06). Returns a de-duplicated, sorted list
    of matching SSID names."""
    _run(["netsh", "wlan", "show", "networks", "mode=bssid"])  # refresh scan cache
    time.sleep(1)
    _, out, _ = _run(["netsh", "wlan", "show", "networks"])

    pattern = re.compile(ssid_pattern, re.IGNORECASE)
    found = set()
    for line in out.splitlines():
        m = re.match(r"^\s*SSID\s+\d+\s*:\s*(.+?)\s*$", line)
        if m and pattern.match(m.group(1)):
            found.add(m.group(1))

    return sorted(found)


def select_polaris_network(ssid_pattern: str = r"^polaris_[0-9a-zA-Z]+$") -> str:
    """Finds visible Polaris hotspots. Auto-picks the only one if there's
    exactly one; otherwise prompts the user to choose. Raises if none
    are visible."""
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


def find_and_connect_to_polaris(password: str = "", timeout: float = 15.0,
                                 interface: Optional[str] = None,
                                 prefer_keywords: tuple = ("usb",),
                                 ssid_pattern: str = r"^polaris_[0-9a-zA-Z]+$") -> bool:
    """Discovers nearby Polaris hotspot(s), resolves which one to use
    (auto if unambiguous, prompts otherwise), then connects. This is the
    entry point most callers want; use connect_to_polaris() directly if
    you already know the exact SSID."""
    ssid = select_polaris_network(ssid_pattern)
    return connect_to_polaris(ssid, password, timeout=timeout,
                               interface=interface, prefer_keywords=prefer_keywords)


def connect_to_polaris(ssid: str, password: str = "", timeout: float = 15.0,
                        interface: Optional[str] = None,
                        prefer_keywords: tuple = ("usb",)) -> bool:
    """Add/refresh the profile then connect. Call this at the top of
    main.py before opening any socket to the mount.

    interface: force a specific adapter name (e.g. 'Wi-Fi 2'). Leave
    as None to auto-select.
    prefer_keywords: when auto-selecting among multiple adapters, rank
    ones whose description matches these (default: "usb") above others.
    Override e.g. prefer_keywords=("realtek",) if that suits a
    particular user's hardware better.
    """
    interfaces = list_interfaces()
    chosen = choose_interface(interfaces, explicit_name=interface,
                               prefer_keywords=prefer_keywords)
    print(f"Using WiFi interface: {chosen.name} ({chosen.description})")

    add_profile(ssid, password, interface=chosen.name)
    ok = connect(ssid, interface=chosen.name, timeout=timeout)
    if not ok:
        diagnose(ssid, interface=chosen.name)
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 3:
        print("Usage: connect_polaris.py [SSID] [PASSWORD]")
        print("Omit SSID to auto-discover nearby Polaris hotspot(s).")
        print("Omit PASSWORD if the Polaris hotspot is open/unsecured.")
        sys.exit(1)

    ssid_arg = sys.argv[1] if len(sys.argv) >= 2 else None
    password_arg = sys.argv[2] if len(sys.argv) == 3 else ""

    try:
        if ssid_arg:
            ok = connect_to_polaris(ssid_arg, password_arg)
        else:
            ok = find_and_connect_to_polaris(password_arg)
    except RuntimeError as e:
        # Expected/anticipated failures (no device found, netsh errors,
        # no WiFi interfaces, etc.) - print just the message, no traceback.
        print(f"Error: {e}")
        sys.exit(1)
    except ValueError as e:
        # e.g. invalid password length
        print(f"Error: {e}")
        sys.exit(1)

    print("Connected." if ok else "Failed to connect within timeout.")
    sys.exit(0 if ok else 1)