# PolarisSlewRelative - CCDciel script: move the Benro Polaris by the given offsets (Polaris:SlewRelative).
#
# Install: run install.bat (Windows), or copy this file to CCDciel's configuration folder as "PolarisSlewRelative.script".
#          See docs/ccdciel.md, Scripting.
# Arguments: one or more key=value pairs, separated by spaces. Each value is added to the current target.
#   Equatorial:  ra (hours)  dec  pa          Topocentric: az  alt  roll        Galactic: l  b  gpa
#   Motors:      m1  m2  m3 (motor angles; can't be combined with the other keys)
#   Values are decimal degrees (hours for ra), or h:m:s / d:m:s text, e.g. ra=10:45:03 dec=-59:41:04
#   Examples:    alt=0.5 roll=-10      ra=0:00:30      m3=5
# Returns when the slew is complete.
#
# The driver's address is read from CCDciel's mount settings (ASCOM Alpaca tab), so nothing needs editing.
# Set HOST / PORT below only to override it. Uses the Python standard library only.

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ACTION = 'Polaris:SlewRelative'
HOST = None             # e.g. "192.168.50.54" to override CCDciel's mount setting
PORT = None             # e.g. 5555
TIMEOUT_S = 300         # the action returns when the goto is complete
KEYS = ('ra', 'dec', 'pa', 'az', 'alt', 'roll', 'l', 'b', 'gpa', 'm1', 'm2', 'm3')
MOTORS = ('m1', 'm2', 'm3')


def log(msg):
    print(msg)
    try:
        from ccdciel import ccdciel
        ccdciel('LogMsg', msg)
    except Exception:
        pass


def driver_address():
    """(host, port, device) of the mount from CCDciel's configuration (ASCOMRestmount), or the overrides."""
    host, port, device = HOST, PORT, 0
    if host is None or port is None:
        folder = os.path.dirname(os.path.abspath(sys.argv[0]))     # CCDciel runs scripts from its config folder
        try:
            root = ET.parse(os.path.join(folder, 'ccdciel.conf')).getroot()
            mount = root.find('.//ASCOMRestmount')
            host = host or mount.get('Host')
            port = port or int(mount.get('Port'))
            device = int(mount.get('Device', 0))
        except Exception as e:
            raise RuntimeError(f'Cannot read the mount address from {folder}\\ccdciel.conf ({e}); set HOST and PORT') from e
    return host, int(port), device


def alpaca_action(action, params=None):
    """Run an Alpaca device action on the driver; returns its Value."""
    host, port, device = driver_address()
    url = f'http://{host}:{port}/api/v1/telescope/{device}/action'
    data = urllib.parse.urlencode({'Action': action, 'Parameters': '' if params is None else json.dumps(params),
                                   'ClientID': 100, 'ClientTransactionID': 1}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data, method='PUT'), timeout=TIMEOUT_S) as r:
        result = json.loads(r.read().decode())
    if result.get('ErrorNumber', 0) != 0:
        raise RuntimeError(f"Alpaca error {result['ErrorNumber']}: {result.get('ErrorMessage')}")
    return result.get('Value')


def parse_coords(args):
    """key=value pairs (or a JSON object) -> {key: number or text}. Raises ValueError with a readable message."""
    text = ' '.join(args).strip()
    if text.startswith('{'):                                         # JSON, as CCDciel may pass it (quotes lost)
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r'([{\s,])([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', text)
        pairs = list(json.loads(text).items())
    else:
        pairs = []
        for token in text.replace(',', ' ').split():
            if '=' not in token:
                raise ValueError(f'expected key=value, got {token!r}')
            key, value = token.split('=', 1)
            pairs.append((key, value))
    coords = {}
    for key, value in pairs:
        key = key.strip().lower()
        if key not in KEYS:
            raise ValueError(f'unknown key {key!r} (use {", ".join(KEYS)})')
        if isinstance(value, (int, float)):
            coords[key] = float(value)
            continue
        value = str(value).strip()
        try:
            coords[key] = float(value)                               # decimal degrees (hours for ra)
        except ValueError:
            if not re.search(r'\d', value):
                raise ValueError(f'{key}={value!r} is not a number or h:m:s / d:m:s value')
            coords[key] = value                                      # text: the driver parses h:m:s / d:m:s
    if not coords:
        raise ValueError('no coordinates given')
    if any(k in MOTORS for k in coords) and any(k not in MOTORS for k in coords):
        raise ValueError('motor keys (m1, m2, m3) can\'t be combined with the other keys')
    return coords


def main():
    try:
        coords = parse_coords(sys.argv[1:])
    except ValueError as e:
        log(f'PolarisSlewRelative: {e}')
        sys.exit(1)
    try:
        log(f'PolarisSlewRelative: {" ".join(f"{k}={v}" for k, v in coords.items())}')
        log(f'PolarisSlewRelative: {alpaca_action(ACTION, coords)}')
    except Exception as e:
        log(f'PolarisSlewRelative: failed: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
