# PolarisPanoSlew - CCDciel script: slew the Benro Polaris to the next panorama panel (Polaris:PanoSlew).
#
# Install: run install.bat (Windows), or copy this file to CCDciel's configuration folder as "PolarisPanoSlew.script".
#          See docs/ccdciel.md, Scripting.
# Arguments: none to slew to the next panel of the grid defined in Alpaca Pilot (wrapping to panel 1 after the
#          last), or a panel number to slew to that panel. Returns when the slew is complete.
#
# The driver's address is read from CCDciel's mount settings (ASCOM Alpaca tab), so nothing needs editing.
# Set HOST / PORT below only to override it. Uses the Python standard library only.

import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HOST = None             # e.g. "192.168.50.54" to override CCDciel's mount setting
PORT = None             # e.g. 5555
TIMEOUT_S = 300         # the action returns when the goto is complete


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


def main():
    try:
        panel = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].strip() else None
    except ValueError:
        log(f'PolarisPanoSlew: the argument must be a panel number, not {sys.argv[1]!r}')
        sys.exit(1)
    params = None if panel is None else {'panel': panel}
    try:
        log(f'PolarisPanoSlew: slewing to {"the next panel" if panel is None else f"panel {panel}"}')
        log(f'PolarisPanoSlew: {alpaca_action("Polaris:PanoSlew", params)}')
    except Exception as e:
        log(f'PolarisPanoSlew: failed: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
