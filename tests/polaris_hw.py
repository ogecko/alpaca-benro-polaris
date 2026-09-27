"""
Shared helpers for hardware tests that drive a live driver + Polaris over the Alpaca API.

Motors are driven with Polaris:MoveMotor; velocity is a linear fit of `traw` (raw motor
angles, deg) polled from Polaris:StatusFetch. Driver address: POLARIS_HOST / POLARIS_PORT
env vars (default localhost:5555).
"""
import itertools
import json
import os
import time

import numpy as np
import requests

HOST = os.environ.get("POLARIS_HOST", "localhost")
PORT = int(os.environ.get("POLARIS_PORT", "5555"))
URL = f"http://{HOST}:{PORT}/api/v1/telescope/0"

MOTOR_NAMES = {0: "M1 (Az, 532)", 1: "M2 (Alt, 533)", 2: "M3 (Roll, 534)"}
SAMPLE_S = 0.25

_txn = itertools.count(1)


def _check(r, what):
    r.raise_for_status()
    body = r.json()
    if body.get("ErrorNumber"):
        raise RuntimeError(f"{what}: {body}")
    return body.get("Value")


def get(prop, timeout=10):
    r = requests.get(f"{URL}/{prop}", params={"ClientID": 77, "ClientTransactionID": next(_txn)}, timeout=timeout)
    return _check(r, prop)


def action(name, params=None, timeout=10):
    data = {"Action": name, "Parameters": json.dumps(params or {}),
            "ClientID": 77, "ClientTransactionID": next(_txn)}
    return _check(requests.put(f"{URL}/action", data=data, timeout=timeout), name)


def status():
    return action("Polaris:StatusFetch")


def move_motor(axis, rate, unit="RAW"):
    action("Polaris:MoveMotor", {"axis": axis, "rate": rate, "unit": unit})


def stop_all():
    for axis in (0, 1, 2):
        move_motor(axis, 0)


def measure_velocity(duration):
    """Per-axis velocity (deg/s) from a linear fit of traw over `duration` seconds."""
    t, theta = [], []
    end = time.monotonic() + duration
    while time.monotonic() < end:
        theta.append(status()["traw"])
        t.append(time.monotonic())
        time.sleep(SAMPLE_S)
    t = np.array(t) - t[0]
    theta = np.unwrap(np.array(theta, dtype=float), period=360.0, axis=0)
    return np.array([np.polyfit(t, theta[:, axis], 1)[0] for axis in range(3)])


def hardware_tests_disabled_reason():
    """None if the driver allows hardware unit tests (config log_hardware_unit_tests, the 'Allow Hardware
    Unit Tests' toggle in Pilot's Log Settings), else why not. Tests that send real protocol commands to the
    Polaris - they move the mount - must skip unless this is None."""
    try:
        cfg = action("Polaris:ConfigFetch", {"configNames": ["log_hardware_unit_tests"]}, timeout=2)
    except Exception as e:
        return f"driver not reachable at {HOST}:{PORT} ({e.__class__.__name__})"
    if not cfg.get("log_hardware_unit_tests", False):
        return "hardware unit tests are disabled (config log_hardware_unit_tests / Pilot Log Settings)"
    return None


def idle_reason():
    """None if the Polaris is connected and idle, else why not."""
    try:
        if not get("connected", timeout=2):
            return "driver is not connected to the Polaris"
        s = status()
    except Exception as e:
        return f"driver not reachable at {HOST}:{PORT} ({e.__class__.__name__})"
    if s["tracking"]:
        return "Polaris is tracking"
    if s["pidmode"] != "IDLE":
        return f"PID mode is {s['pidmode']}, not IDLE"
    if s["slewing"]:
        return "Polaris is slewing"
    return None


def direction(axis):
    """Alt moves toward mid-range so it can't run into a limit; other axes move positive."""
    if axis == 1:
        return -1 if status()["traw"][1] > 45 else 1
    return 1


def speed_controller():
    """'coordinated' or 'legacy', as selected in the driver config (unknown on older drivers)."""
    try:
        return "coordinated" if action("Polaris:ConfigFetch", {"configNames": ["coordinated_speed_control"]}).get("coordinated_speed_control") else "legacy"
    except Exception:
        return "unknown"


def put(prop, value_name, value, timeout=10):
    data = {value_name: value, "ClientID": 77, "ClientTransactionID": next(_txn)}
    return _check(requests.put(f"{URL}/{prop}", data=data, timeout=timeout), prop)


def set_tracking(on: bool):
    put("tracking", "Tracking", str(bool(on)))


def slew_absolute(az, alt, roll, timeout=120):
    """Blocking Az/Alt/Roll slew via Polaris:SlewAbsolute."""
    action("Polaris:SlewAbsolute", {"az": az, "alt": alt, "roll": roll, "isasync": False}, timeout=timeout)


def set_speed_controller(use_v2: bool):
    action("Polaris:ConfigUpdate", {"coordinated_speed_control": bool(use_v2)})
    time.sleep(0.5)


def sample_tracking_error(duration):
    """PID error signal (theta_ref - theta_pv, deg) sampled at 4 Hz: (n, 3) array plus motorcmd samples."""
    errs, cmds = [], []
    end = time.monotonic() + duration
    while time.monotonic() < end:
        s = status()
        errs.append(s["errsig"])
        cmds.append(tuple(c.strip() for c in s["motorcmd"]))
        time.sleep(SAMPLE_S)
    return np.array(errs, dtype=float), cmds
