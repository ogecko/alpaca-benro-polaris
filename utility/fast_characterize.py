"""
Characterise the Polaris FAST motor mode (513/514/521 'speed:n') on hardware, bypassing the driver's
speed controller: raw FAST frames are sent on a second TCP client to the Polaris (refreshed every
50 ms, as the MCU watchdog requires), and motor angles are read from the driver (Polaris:StatusFetch
traw, timestamped by age518).

Measures, per axis:
  1. static map: steady speed (deg/s) for a range of FAST speed units, incl. the stall threshold
  2. step response: 0 -> u1 -> u2 -> 0, velocity from successive 518 samples, fitted delay + lag

The driver must be running, connected and idle (tracking off). The mount moves up to ~40 deg on
M1/M3 (directions alternate to stay near the start). Stops all motors on exit.

Usage: python utility/fast_characterize.py [--axes 0,2] [--quick]
"""
import argparse
import sys
import threading
import time

import numpy as np

sys.path[:0] = ['utility', 'tests']
from state2_test import PolarisRaw           # noqa: E402
import polaris_hw as hw                      # noqa: E402

FAST_CMD = {0: "513", 1: "514", 2: "521"}


class FastSender:
    """Keeps sending the current FAST speed for one axis every 50 ms."""
    def __init__(self, pr, axis):
        self.pr, self.axis, self.speed, self._stop = pr, axis, 0, False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        while not self._stop:
            if self.speed:
                self.pr.sock.sendall(f"1&{FAST_CMD[self.axis]}&3&speed:{int(self.speed)};#".encode())
            time.sleep(0.05)

    def stop(self):
        self.speed = 0
        self._stop = True
        self._t.join()
        self.pr.stop(self.axis)


_last_traw = [None]


def sample(duration):
    """(t, theta) for every new 518 position (traw only changes every 0.2 s): t = local receive time less age518."""
    out = []
    end = time.monotonic() + duration
    while time.monotonic() < end:
        s = hw.status()
        traw = tuple(s["traw"])
        if traw != _last_traw[0]:
            _last_traw[0] = traw
            out.append((time.monotonic() - s.get("age518", 0.0), np.array(traw, dtype=float)))
        time.sleep(0.02)
    return out


def fit_rate(samples, axis):
    t = np.array([s[0] for s in samples])
    th = np.unwrap(np.array([s[1][axis] for s in samples]), period=360)
    return float(np.polyfit(t - t[0], th, 1)[0])


def static_map(pr, axis, units):
    rows, sign = [], 1
    for u in units:
        fs = FastSender(pr, axis)
        fs.speed = sign * u
        time.sleep(1.5)
        v = fit_rate(sample(2.5), axis) * sign
        fs.stop()
        time.sleep(1.0)
        rows.append((u, v))
        print(f"  M{axis + 1} FAST {u:5d}: {v:7.4f} deg/s", flush=True)
        sign = -sign
    return rows


def step_response(pr, axis, u1, u2, hold=3.0):
    fs = FastSender(pr, axis)
    t0 = time.monotonic()
    events = []
    rec = []

    def logger():
        while not stop[0]:
            rec.extend(sample(0.2))

    stop = [False]
    th = threading.Thread(target=logger, daemon=True)
    th.start()
    time.sleep(1.0)
    for u in (u1, u2, 0):
        events.append((time.monotonic(), u))
        fs.speed = u
        if u == 0:
            fs.stop()
        time.sleep(hold)
    stop[0] = True
    th.join()
    rec.sort(key=lambda r: r[0])
    t = np.array([r[0] for r in rec])
    th_ = np.unwrap(np.array([r[1][axis] for r in rec]), period=360)
    tm, v = (t[1:] + t[:-1]) / 2, np.diff(th_) / np.diff(t)
    return events, tm, v


def fit_lag(events, tm, v):
    """Per step: steady speeds before/after, dead time (first 10% of the change) and time constant (63%)."""
    out = []
    for (te, _u), nxt in zip(events, events[1:] + [(tm[-1] + 1, None)]):
        before = np.median(v[(tm > te - 1.0) & (tm < te)]) if np.any((tm > te - 1.0) & (tm < te)) else 0.0
        seg = (tm >= te) & (tm < nxt[0])
        after = np.median(v[seg][-5:])
        change = after - before
        if abs(change) < 1e-3:
            continue
        frac = (v[seg] - before) / change
        ts = tm[seg] - te
        t10 = ts[np.argmax(frac >= 0.1)] if np.any(frac >= 0.1) else np.nan
        t63 = ts[np.argmax(frac >= 0.63)] if np.any(frac >= 0.63) else np.nan
        out.append((before, after, t10, t63 - t10))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--axes", default="0,2")
    ap.add_argument("--quick", action="store_true", help="fewer static points")
    args = ap.parse_args()
    s = hw.status()
    if not s["connected"] or s["tracking"] or s["pidmode"] != "IDLE":
        sys.exit("Polaris must be connected and idle")
    cfg = hw.action("Polaris:ConfigFetch", {"configNames": ["polaris_ip_address", "polaris_port"]})
    pr = PolarisRaw(cfg["polaris_ip_address"], cfg["polaris_port"])
    print(f"battery {s.get('battery_level')}%  start traw {np.round(s['traw'], 2).tolist()}")
    units = [300, 500, 1000, 2000] if args.quick else [200, 250, 300, 350, 400, 500, 700, 1000, 1500, 2000, 2500]
    try:
        for axis in [int(a) for a in args.axes.split(",")]:
            print(f"== M{axis + 1} static map")
            static_map(pr, axis, units)
            print(f"== M{axis + 1} step response 0 -> 1000 -> 2000 -> 0")
            for before, after, dead, tau in fit_lag(*step_response(pr, axis, 1000, 2000)):
                print(f"  {before:6.3f} -> {after:6.3f} deg/s: dead time {dead:.2f} s, time constant {tau:.2f} s", flush=True)
    finally:
        pr.stop_all()
        time.sleep(0.5)
        pr.close()
        print(f"stopped. battery {hw.status().get('battery_level')}%")


if __name__ == "__main__":
    main()
