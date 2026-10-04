# PolarisSyncGuide - CCDciel script: plate-solve the current image and sync the mount (Sync Guiding).
#
# Install: run install.bat (Windows), or copy this file to CCDciel's configuration folder as "PolarisSyncGuide.script".
#          See docs/ccdciel.md, Scripting.
# Arguments: optional settle time in seconds (default 5) to wait after the sync.
#
# Run it from a plan step every 1 to 3 minutes of imaging. It solves the image already taken (no extra exposure)
# with CCDciel's Astrometry_sync and syncs the mount without slewing. With Sync Guiding enabled in the Alpaca
# Driver, the first sync after a goto adds an alignment point and the following ones are used as guiding
# corrections (residuals up to 3 deg). After a sync the driver moves the mount back onto its target, so the script
# waits SETTLE_S before the next exposure starts.

import sys
import time

from ccdciel import ccdciel

SETTLE_S = 5.0


def log(msg):
    print(msg)
    try:
        ccdciel('LogMsg', msg)
    except Exception:
        pass


def main():
    settle = SETTLE_S
    if len(sys.argv) > 1 and sys.argv[1].strip():
        try:
            settle = float(sys.argv[1])
        except ValueError:
            log(f'PolarisSyncGuide: the argument must be a settle time in seconds, not {sys.argv[1]!r}')
            sys.exit(1)
    if not ccdciel('Telescope_Connected').get('result'):
        log('PolarisSyncGuide: telescope not connected')
        sys.exit(1)
    r = ccdciel('Astrometry_sync')
    result = r.get('result')
    status = result.get('status') if isinstance(result, dict) else result
    if 'error' in r or not str(status).startswith('OK'):         # 'OK!', or 'Failed!' with the reason
        log(f'PolarisSyncGuide: plate solve and sync failed: {r.get("error") or status}')
        sys.exit(1)
    log(f'PolarisSyncGuide: synced, settling {settle:g} s')
    time.sleep(settle)


if __name__ == '__main__':
    main()
