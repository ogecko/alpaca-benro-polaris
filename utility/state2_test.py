"""
Low-level hardware test of the 532/533/534 slow-jog `state:2` ("continue"/hold) speeds.

Firmware (A Polaris System Design.md §5.4): the MCU treats state 1 and state 2 identically
except that 0x800886c picks the second float of the shared level's pair for state 2
(L1..5 = 0.0002, 0.0005, 0.001, 0.002, 0.004 vs 0.0001, 0.0003, 0.0008, 0.0015, 0.0035 for
state 1). State is stored per axis, so two axes at the same level should be able to run at
different speeds (state 1 vs state 2).

The driver only ever sends state 0/1, so this test opens its own TCP connection to the
Polaris (the firmware accepts multiple clients) and sends raw 53x frames. Velocity is read
from the driver (Polaris:StatusFetch `traw`), which must be running, connected and idle.

Tests:
  1. speed ladder: per motor and level 1..5, start at state 1, measure, switch to state 2
     without stopping, measure
  2. state 2 directly from standstill (level 1)
  3. per-axis state at a shared level: M1 state 1 + M2 state 2 at level 1, then swapped

All motors are stopped (state 0) on exit, including on error or Ctrl-C.

Usage:
    python utility/state2_test.py [--host localhost] [--port 5555] [--axes 0,1,2] [--max-level 5]
"""
import argparse
import itertools
import json
import socket
import sys
import threading
import time

import numpy as np
import requests

MOTOR_NAMES = {0: "M1 (Az, 532)", 1: "M2 (Alt, 533)", 2: "M3 (Roll, 534)"}
SLOW_CMD = {0: "532", 1: "533", 2: "534"}
# Firmware table (§5.3): deg/s = 60 x step
EXPECTED_DPS = {1: {1: 0.006, 2: 0.018, 3: 0.048, 4: 0.090, 5: 0.210},
                2: {1: 0.012, 2: 0.030, 3: 0.060, 4: 0.120, 5: 0.240}}
SETTLE_S = 2.0
MEASURE_S = 5.0
SAMPLE_S = 0.25

_txn = itertools.count(1)


class Driver:
    """Alpaca REST access to the running driver - used only to read status."""
    def __init__(self, host, port):
        self.url = f"http://{host}:{port}/api/v1/telescope/0"

    def action(self, name, params=None):
        data = {"Action": name, "Parameters": json.dumps(params or {}),
                "ClientID": 78, "ClientTransactionID": next(_txn)}
        r = requests.put(f"{self.url}/action", data=data, timeout=10)
        r.raise_for_status()
        body = r.json()
        if body.get("ErrorNumber"):
            raise RuntimeError(f"{name}: {body}")
        return body["Value"]

    def status(self):
        return self.action("Polaris:StatusFetch")

    def config(self, names):
        return self.action("Polaris:ConfigFetch", {"configNames": names})


class PolarisRaw:
    """Second TCP client to the Polaris for sending raw 53x frames."""
    def __init__(self, ip, port):
        self.sock = socket.create_connection((ip, port), timeout=5)
        self.sock.settimeout(1.0)
        self._stop = False
        # Drain everything the Polaris pushes to us so its send buffer never backs up.
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()

    def _drain(self):
        while not self._stop:
            try:
                if not self.sock.recv(65536):
                    return
            except socket.timeout:
                continue
            except OSError:
                return

    def slow(self, axis, direction, state, level):
        key = 0 if direction > 0 else 1
        msg = f"1&{SLOW_CMD[axis]}&3&key:{key};state:{state};level:{level};#"
        self.sock.sendall(msg.encode())
        time.sleep(0.05)
        return msg

    def stop(self, axis):
        self.slow(axis, +1, 0, 0)

    def stop_all(self):
        for axis in (0, 1, 2):
            self.stop(axis)

    def close(self):
        self._stop = True
        self.sock.close()


def measure_velocity(drv: Driver, duration=MEASURE_S):
    t, theta = [], []
    end = time.monotonic() + duration
    while time.monotonic() < end:
        theta.append(drv.status()["traw"])
        t.append(time.monotonic())
        time.sleep(SAMPLE_S)
    t = np.array(t) - t[0]
    theta = np.unwrap(np.array(theta, dtype=float), period=360.0, axis=0)
    return np.array([np.polyfit(t, theta[:, a], 1)[0] for a in range(3)])


def direction_for(drv, axis, flip):
    """Alternate direction each run; Alt always heads back towards 45 deg."""
    if axis == 1:
        return -1 if drv.status()["traw"][1] > 45 else 1
    return 1 if flip else -1


def speed_ladder(drv, pr, axis, max_level):
    rows = []
    for level in range(1, max_level + 1):
        d = direction_for(drv, axis, level % 2)
        pr.slow(axis, d, 1, level)
        time.sleep(SETTLE_S)
        v1 = abs(measure_velocity(drv)[axis])
        pr.slow(axis, d, 2, level)          # switch to state 2 without stopping
        time.sleep(SETTLE_S)
        v2 = abs(measure_velocity(drv)[axis])
        pr.stop(axis)
        time.sleep(1.0)
        rows.append((level, v1, v2))
        print(f"  {MOTOR_NAMES[axis]} L{level}: state1 {v1:.5f} dps (fw {EXPECTED_DPS[1][level]:.3f})"
              f"   state2 {v2:.5f} dps (fw {EXPECTED_DPS[2][level]:.3f})   ratio {v2 / v1 if v1 else float('nan'):.2f}")
    return rows


def state2_from_idle(drv, pr, axis):
    d = direction_for(drv, axis, True)
    pr.slow(axis, d, 2, 1)
    time.sleep(SETTLE_S)
    v = abs(measure_velocity(drv)[axis])
    pr.stop(axis)
    time.sleep(1.0)
    print(f"  {MOTOR_NAMES[axis]} state2 L1 from standstill: {v:.5f} dps (fw {EXPECTED_DPS[2][1]:.3f})")
    return v


def per_axis_state(drv, pr, state_m1, state_m2, level=1):
    d1 = direction_for(drv, 0, True)
    d2 = direction_for(drv, 1, True)
    pr.slow(0, d1, state_m1, level)
    pr.slow(1, d2, state_m2, level)
    time.sleep(SETTLE_S)
    v = np.abs(measure_velocity(drv))
    pr.stop_all()
    time.sleep(1.0)
    print(f"  L{level}: M1 state{state_m1} {v[0]:.5f} dps (fw {EXPECTED_DPS[state_m1][level]:.3f})   "
          f"M2 state{state_m2} {v[1]:.5f} dps (fw {EXPECTED_DPS[state_m2][level]:.3f})")
    return v[0], v[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="localhost", help="driver host")
    ap.add_argument("--port", type=int, default=5555, help="driver Alpaca port")
    ap.add_argument("--axes", default="0,1,2", help="axes for the speed ladder")
    ap.add_argument("--max-level", type=int, default=5)
    args = ap.parse_args()

    drv = Driver(args.host, args.port)
    s = drv.status()
    if not s["connected"] or s["tracking"] or s["pidmode"] != "IDLE" or s["slewing"]:
        sys.exit(f"Polaris must be connected and idle (connected={s['connected']} tracking={s['tracking']} "
                 f"pidmode={s['pidmode']} slewing={s['slewing']})")
    cfg = drv.config(["polaris_ip_address", "polaris_port"])
    pr = PolarisRaw(cfg["polaris_ip_address"], cfg["polaris_port"])
    print(f"Start traw {np.round(s['traw'], 3).tolist()}")

    try:
        print("\n=== 1. Speed ladder (state 1, then state 2 without stopping) ===")
        for axis in [int(a) for a in args.axes.split(",")]:
            speed_ladder(drv, pr, axis, args.max_level)

        print("\n=== 2. State 2 directly from standstill ===")
        for axis in (0, 1):
            state2_from_idle(drv, pr, axis)

        print("\n=== 3. Per-axis state at a shared level ===")
        per_axis_state(drv, pr, 1, 2)
        per_axis_state(drv, pr, 2, 1)
    finally:
        pr.stop_all()
        time.sleep(0.5)
        pr.close()
        print(f"\nAll motors stopped. End traw {np.round(drv.status()['traw'], 3).tolist()}")


if __name__ == "__main__":
    main()
