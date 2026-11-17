"""
Hardware test: is the 532/533/534 slow-jog `level` shared between motors?

Firmware RE (A Polaris System Design.md, finding 1) suggests the MCU 'B' handler
stores `level` in a single byte and the level->speed routine (0x800886c) re-sends
*both* active Az/Alt axes with that one speed. If so, starting M2 (Alt, 533) at
level 3 would also speed up an already-running M1 (Az, 532) jog from level 1 to
level 3. M3 (534) is forwarded to a separate astro module, so it is expected to
be independent.

For each pair (A, B) this test:
  1. stops all motors
  2. runs A at RAW rate 0.8 and measures A's velocity          -> baseline
  3. starts B at RAW rate 3.5 and measures A and B              -> does A change?
  4. stops B and measures A                                     -> does A stay changed?
  5. stops all motors

Motors are driven via the Polaris:MoveMotor action in RAW units. The default
fractional rates put the driver's MotorSpeedController in SLOW_PWM mode (0.8 dithers
levels -1<->+1 at 90% duty, 3.5 dithers 3<->4), matching how the driver jogs in normal use; both are
well below 1 deg/s. Integer rates (--rate-a 1 --rate-b 3) use plain SLOW mode instead,
where each axis sends a 53x message only when its own rate changes. Velocity is measured by a
linear fit of `traw` (raw motor angle, deg) polled from Polaris:StatusFetch.

Requires: driver connected, tracking off, PID idle. All motors are stopped on exit,
including on error or Ctrl-C.

Usage:
    python utility/speed_test.py [--host localhost] [--port 5555] [--rate-a 0.8] [--rate-b 3.5]
"""
import argparse
import itertools
import json
import sys
import time

import numpy as np
import requests

MOTOR_NAMES = {0: "M1 (Az, 532)", 1: "M2 (Alt, 533)", 2: "M3 (Roll, 534)"}
RATE_A = 0.8           # RAW rate for motor A (<1 => SLOW_PWM dithering -1<->+1)
RATE_B = 3.5           # RAW rate for motor B
SETTLE_S = 3.0          # wait after a speed change before measuring
MEASURE_S = 8.0         # measurement window
SAMPLE_S = 0.25         # status poll interval
SHARED_THRESHOLD = 1.5  # A's speed ratio (after/before) above this => level is shared

_txn = itertools.count(1)


class Polaris:
    def __init__(self, host, port):
        self.url = f"http://{host}:{port}/api/v1/telescope/0"

    def _check(self, r, what):
        r.raise_for_status()
        body = r.json()
        if body.get("ErrorNumber"):
            raise RuntimeError(f"{what}: {body}")
        return body.get("Value")

    def get(self, prop):
        r = requests.get(f"{self.url}/{prop}", params={"ClientID": 77, "ClientTransactionID": next(_txn)}, timeout=10)
        return self._check(r, prop)

    def action(self, name, params=None):
        data = {"Action": name, "Parameters": json.dumps(params or {}),
                "ClientID": 77, "ClientTransactionID": next(_txn)}
        return self._check(requests.put(f"{self.url}/action", data=data, timeout=10), name)

    def status(self):
        return self.action("Polaris:StatusFetch")

    def move_motor(self, axis, raw_rate):
        self.action("Polaris:MoveMotor", {"axis": axis, "rate": raw_rate, "unit": "RAW"})

    def stop_all(self):
        for axis in (0, 1, 2):
            self.move_motor(axis, 0)


def measure_velocity(p: Polaris, duration=MEASURE_S, interval=SAMPLE_S):
    """Return per-axis velocity (deg/s) from a linear fit of traw over `duration`."""
    t, theta = [], []
    end = time.monotonic() + duration
    while time.monotonic() < end:
        s = p.status()
        t.append(time.monotonic())
        theta.append(s["traw"])
        time.sleep(interval)
    t = np.array(t) - t[0]
    theta = np.unwrap(np.array(theta, dtype=float), period=360.0, axis=0)
    return np.array([np.polyfit(t, theta[:, axis], 1)[0] for axis in range(3)])


def fmt(v):
    return f"{v:+.5f} dps"


def run_pair(p: Polaris, a: int, b: int, alt_dir: int, rate_a=RATE_A, rate_b=RATE_B):
    """Run A at rate_a, then add B at rate_b, then stop B. Returns result dict."""
    dir_a = alt_dir if a == 1 else 1
    dir_b = alt_dir if b == 1 else 1
    na, nb = MOTOR_NAMES[a], MOTOR_NAMES[b]
    print(f"\n=== {na} RAW {rate_a}  vs  {nb} RAW {rate_b} ===")

    p.stop_all()
    time.sleep(SETTLE_S)

    p.move_motor(a, rate_a * dir_a)
    time.sleep(SETTLE_S)
    v1 = measure_velocity(p)
    print(f"  phase 1  {na} alone      : {na} {fmt(v1[a])}   {nb} {fmt(v1[b])}   cmd {p.status()['motorcmd']}")

    p.move_motor(b, rate_b * dir_b)
    time.sleep(SETTLE_S)
    v2 = measure_velocity(p)
    print(f"  phase 2  +{nb} running : {na} {fmt(v2[a])}   {nb} {fmt(v2[b])}   cmd {p.status()['motorcmd']}")

    p.move_motor(b, 0)
    time.sleep(SETTLE_S)
    v3 = measure_velocity(p)
    print(f"  phase 3  {nb} stopped    : {na} {fmt(v3[a])}   {nb} {fmt(v3[b])}   cmd {p.status()['motorcmd']}")

    p.stop_all()

    base = abs(v1[a])
    ratio2 = abs(v2[a]) / base if base > 1e-6 else float("nan")
    ratio3 = abs(v3[a]) / base if base > 1e-6 else float("nan")
    shared = ratio2 > SHARED_THRESHOLD
    print(f"  {na} speed ratio vs baseline: with {nb} running x{ratio2:.2f}, after {nb} stopped x{ratio3:.2f}")
    print(f"  => level is {'SHARED' if shared else 'INDEPENDENT'} between {na} and {nb}")
    return {"a": a, "b": b, "v1": v1, "v2": v2, "v3": v3, "ratio2": ratio2, "ratio3": ratio3, "shared": shared}


def preflight(p: Polaris):
    if not p.get("connected"):
        sys.exit("Driver is not connected to the Polaris.")
    s = p.status()
    if s["tracking"]:
        sys.exit("Tracking is on - turn tracking off before running this test (PID would override motor speeds).")
    if s["pidmode"] not in ("IDLE", "PRESETUP", "LIMIT"):
        sys.exit(f"PID mode is {s['pidmode']} - wait for the mount to be idle.")
    if s["slewing"]:
        sys.exit("Mount is slewing - wait for it to finish.")
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=5555)
    ap.add_argument("--rate-a", type=float, default=RATE_A, help="RAW rate for the running motor (default %(default)s)")
    ap.add_argument("--rate-b", type=float, default=RATE_B, help="RAW rate for the probe motor (default %(default)s)")
    args = ap.parse_args()

    p = Polaris(args.host, args.port)
    s = preflight(p)
    # Move Alt towards mid-range so a few tenths of a degree can't hit a limit.
    alt_dir = -1 if s["traw"][1] > 45 else 1
    print(f"Start traw {np.round(s['traw'], 3).tolist()}; Alt direction {alt_dir:+d}")

    results = []
    try:
        results.append(run_pair(p, 0, 1, alt_dir, args.rate_a, args.rate_b))   # Az vs Alt: expected shared per firmware RE
        results.append(run_pair(p, 0, 2, alt_dir, args.rate_a, args.rate_b))   # Az vs Roll: expected independent (astro module)
    finally:
        p.stop_all()
        print("\nAll motors stopped.")

    print("\n=== Summary ===")
    for r in results:
        print(f"  {MOTOR_NAMES[r['a']]} vs {MOTOR_NAMES[r['b']]}: "
              f"{'SHARED' if r['shared'] else 'independent'} "
              f"(x{r['ratio2']:.2f} with B running, x{r['ratio3']:.2f} after B stopped)")


if __name__ == "__main__":
    main()
