"""
Minimal Alpaca REST client for driving the live driver during PID tuning experiments.

Talks to the standard ASCOM Alpaca Telescope device (devicenumber=0) plus the
custom Polaris:* actions, and the Rotator device for Roll Angle. See
docs/control.md "Developer: Automated PID/PEC Testing via Alpaca API" for the
underlying protocol this wraps.
"""
import itertools
import time

import requests

HOST = "localhost"
REST_PORT = 5555
TELESCOPE_BASE = f"http://{HOST}:{REST_PORT}/api/v1/telescope/0"
ROTATOR_BASE = f"http://{HOST}:{REST_PORT}/api/v1/rotator/0"

_client_id = 42
_txn = itertools.count(1)


def _params(extra=None):
    p = {"ClientID": _client_id, "ClientTransactionID": next(_txn)}
    if extra:
        p.update(extra)
    return p


def _get(base, path, extra=None):
    r = requests.get(f"{base}/{path}", params=_params(extra), timeout=10)
    r.raise_for_status()
    body = r.json()
    if body.get("ErrorNumber"):
        raise RuntimeError(f"GET {path}: {body}")
    return body["Value"]


def _put(base, path, data=None, timeout=10):
    r = requests.put(f"{base}/{path}", data=_params(data), timeout=timeout)
    r.raise_for_status()
    body = r.json()
    if body.get("ErrorNumber"):
        raise RuntimeError(f"PUT {path}: {body}")
    return body


def action(name, parameters, timeout=10):
    import json
    return _put(TELESCOPE_BASE, "action", {"Action": name, "Parameters": json.dumps(parameters)}, timeout=timeout)


def connected():
    return _get(TELESCOPE_BASE, "connected")


def tracking():
    return _get(TELESCOPE_BASE, "tracking")


def set_tracking(state: bool):
    return _put(TELESCOPE_BASE, "tracking", {"Tracking": str(bool(state))})


def clean_tracking_baseline():
    """Toggle tracking off/on -- clears sync-guiding state (q_syncguide_B, PEC model)
    in-memory, per docs/control.md section 4."""
    set_tracking(False)
    set_tracking(True)


def reset_alignment():
    """Toggle advanced_alignment off/on -- disabling it calls
    SyncManager.set_alignQ_to_identity(), which clears sync_history (all
    Multi-Point Alignment sync points) and resets alignQ_B2T to identity.
    Re-enabling starts the MPA model fresh, empty. DESTRUCTIVE to any real
    alignment model built from genuine astronomical syncs -- only use this
    against a mount you're happy to have its MPA model wiped and rebuilt."""
    config_update({"advanced_alignment": False})
    config_update({"advanced_alignment": True})


def azimuth():
    return _get(TELESCOPE_BASE, "azimuth")


def altitude():
    return _get(TELESCOPE_BASE, "altitude")


def roll():
    return _get(ROTATOR_BASE, "mechanicalposition")


def right_ascension():
    return _get(TELESCOPE_BASE, "rightascension")


def declination():
    return _get(TELESCOPE_BASE, "declination")


def slewing():
    return _get(TELESCOPE_BASE, "slewing")


def slew_absolute(az, alt, roll_deg, isasync=False):
    """Az/Alt/Roll slew via the custom Polaris:SlewAbsolute action -- see
    docs/control.md "Positioning with Polaris:SlewAbsolute". Blocks until
    complete unless isasync=True (a blocking slew can legitimately take well
    over 10s on real hardware, hence the generous timeout)."""
    timeout = 10 if isasync else 90
    return action("Polaris:SlewAbsolute", {"az": az, "alt": alt, "roll": roll_deg, "isasync": isasync}, timeout=timeout)


def sync_to_coordinates(ra_hours, dec_deg):
    """Do not use this for repeated tuning-experiment disturbances -- every
    sync is recorded into SyncManager.sync_history and feeds the live
    QUEST/Multi-Point Alignment fit, so many synthetic syncs will contaminate
    the real alignment model. Use step_ra_arcsec() (Polaris:SlewRelative)
    instead, which moves the PID setpoint directly and never touches
    sync_history. Kept here only for the one-off PEC convergence test
    described in docs/control.md section 4, where recording into the PEC
    model *is* the point."""
    return _put(TELESCOPE_BASE, "synctocoordinates", {"RightAscension": ra_hours, "Declination": dec_deg})


def slew_relative(coords: dict, isasync=True):
    """Step the PID setpoint by a relative offset via the custom
    Polaris:SlewRelative action -- does NOT touch sync_history/alignment.
    coords keys: ra (hours), dec/pa/az/alt/roll/l/b/gpa (degrees). isasync
    defaults to True so this returns immediately rather than blocking until
    the goto-complete criterion fires, which would fight a caller's own
    event-timing loop."""
    return action("Polaris:SlewRelative", {**coords, "isasync": isasync})


def step_ra_arcsec(offset_arcsec):
    """Step the PID's RA setpoint by offset_arcsec via Polaris:SlewRelative --
    the alignment-model-safe disturbance for PID tuning experiments."""
    slew_relative({"ra": offset_arcsec / 3600 / 15})


PULSEGUIDE_NORTH, PULSEGUIDE_SOUTH, PULSEGUIDE_EAST, PULSEGUIDE_WEST = 0, 1, 2, 3


def pulse_guide(direction: int, duration_ms: int):
    """Standard ASCOM Alpaca PulseGuide -- the real mechanism autoguiders
    (PHD2 etc.) use, distinct from both SlewRelative and sync. Requires
    tracking, not slewing, not parked (enforced server-side). duration_ms:
    1-10000."""
    return _put(TELESCOPE_BASE, "pulseguide", {"Direction": direction, "Duration": duration_ms})


def config_fetch(names):
    return action("Polaris:ConfigFetch", {"configNames": list(names)})["Value"]


def config_update(changes: dict):
    return action("Polaris:ConfigUpdate", changes)["Value"]


def restart_driver():
    return action("Polaris:RestartDriver", {})


def wait_until_connected(timeout=30, poll=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if connected():
                return True
        except Exception:
            pass
        time.sleep(poll)
    raise TimeoutError("driver did not reconnect in time")


def wait_until_settled(timeout=60, poll=1):
    """Block until the telescope is not slewing and the rotator is not moving."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not slewing() and not _get(ROTATOR_BASE, "ismoving"):
            return True
        time.sleep(poll)
    raise TimeoutError("mount did not settle in time")
