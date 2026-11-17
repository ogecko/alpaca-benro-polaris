"""
Goto response test: a fixed sequence of motor-angle gotos (Polaris:SlewAbsolute m1/m2/m3, raw zeta) to measure how the
whole system - planner, PID, speed controller, MCU and battery - follows a goto: commanded vs actual speed
per motor, overshoot, settle time, and whether moving all three motors at once slows each of them.

Run it with log_position on (the script turns it on and restores it afterwards): every control tick then logs
the commanded speeds (PIDLOG) and measured positions (KFLOG), and each leg is marked in the driver's log with a
REPLAYLOG line ({'test': 'goto_response', ...}) for the analysis to find.

Each move goes out from a base pose (M2 at BASE_M2, M1/M3 where they are) and back, holding HOLD_S after each
leg. A move whose target would come within the margins of the motor limits is mirrored, else skipped.
Ctrl+C aborts the goto (Polaris:AbortSlew) and stops the test.

The driver must be running, connected and idle (tracking off). Prefer level mode (advanced_eq_mode off).
With --track the script turns tracking on first (and off again at the end if it was off): each goto is then to
the sky position of its target motor angles, tracked from there, and the final error is against the tracked
setpoint. Ctrl+C (Polaris:AbortSlew) also stops tracking.

Usage (from the repo root):
  uv run python utility/goto_response.py --plan     # print the moves and limit checks, no movement
  uv run python utility/goto_response.py --twin     # dry-run the sequence in the digital twin
  uv run python utility/goto_response.py            # run it on the mount
  add --track to any of these to run the gotos while tracking
"""
import argparse
import json
import math
import signal
import sys
import time

import numpy as np

sys.path[:0] = ['driver', 'tests']

BASE_M2 = 40.0                       # M2 (theta2) of the base pose: mid-range, room both ways
M2_RANGE = (5.0, 70.0)               # theta2 every target must stay within
Z_MARGIN = 30.0                      # targets keep this far inside the z1/z3 limits
Z2_MARGIN = 8.0                      # ... and the z2 limits
HOLD_S = 4.0                         # hold after each leg: overshoot and settle
LEG_TIMEOUT_S = 90.0                 # a leg longer than this aborts the test
POLL_S = 0.25

MOVES = [                            # (name, delta m1, m2, m3) from the base pose, deg
    ("m1_2",     2.0,  0.0,  0.0),
    ("m1_5",     5.0,  0.0,  0.0),
    ("m1_30",   30.0,  0.0,  0.0),
    ("m1_90",   90.0,  0.0,  0.0),
    ("m2_5",     0.0,  5.0,  0.0),
    ("m2_25",    0.0, 25.0,  0.0),
    ("m3_5",     0.0,  0.0,  5.0),
    ("m3_30",    0.0,  0.0, 30.0),
    ("all_5",    5.0,  5.0,  5.0),
    ("all_30",  30.0, 25.0, 30.0),
]


class AlpacaMount:
    """The running driver, over the Alpaca API."""

    def __init__(self):
        import polaris_hw as hw
        self.hw = hw

    def preflight(self, track=False):
        reason = self.hw.idle_reason()
        if reason and not (track and reason == "Polaris is tracking"):
            sys.exit(f"Not ready: {reason}")

    def status(self):
        s = self.hw.status()
        return {"tpv": np.array(s["tpv"], dtype=float), "tref": np.array(s["tref"], dtype=float),
                "zeta": np.array(s["zetameas"], dtype=float), "pidmode": s["pidmode"], "slewing": bool(s["slewing"]),
                "tracking": bool(s["tracking"])}

    def set_tracking(self, on):
        self.hw.set_tracking(on)

    def config(self, names):
        return self.hw.action("Polaris:ConfigFetch", {"configNames": names})

    def set_config(self, values):
        self.hw.action("Polaris:ConfigUpdate", values)

    def limits(self):
        c = self.config(["z1_min_limit", "z1_max_limit", "z2_min_limit", "z2_max_limit", "z3_min_limit", "z3_max_limit"])
        return (np.array([c["z1_min_limit"], c["z2_min_limit"], c["z3_min_limit"]], dtype=float),
                np.array([c["z1_max_limit"], c["z2_max_limit"], c["z3_max_limit"]], dtype=float))

    def mark(self, info):
        self.hw.action("Polaris:ReplayMark", {"test": "goto_response", **info})

    def slew(self, theta):
        s = self.status()                                 # SlewAbsolute's m1/m2/m3 are zeta: theta less the live offset
        zeta = np.asarray(theta, dtype=float) - (s["tpv"] - s["zeta"])
        self.hw.action("Polaris:SlewAbsolute", {"m1": float(zeta[0]), "m2": float(zeta[1]), "m3": float(zeta[2]),
                                                "isasync": True})

    def abort(self):
        self.hw.action("Polaris:AbortSlew")

    def sleep(self, s):
        time.sleep(s)

    def now(self):
        return time.monotonic()


class TwinMount:
    """The digital twin, driven the way Polaris.slew_axis drives the PID for m1/m2/m3 (set_theta_target)."""

    def __init__(self, eq=False):
        import pytest
        from sim_digital_twin import Twin
        self._mp = pytest.MonkeyPatch()
        self.tw = Twin(self._mp, config={"coordinated_speed_control": True, "advanced_eq_mode": eq}, seed=0)
        self.tw.place((180.0, 30.0, 0.0))
        self.tw.run(10)
        self.pending = False
        self.marks, self.trace = [], []
        self.log_position = False

    def preflight(self, track=False):
        pass

    def status(self):
        p = self.tw.pid
        return {"tpv": np.array(p.theta_pv, dtype=float), "tref": np.array(p.theta_ref, dtype=float),
                "zeta": np.array(self.tw.polaris._zeta_meas, dtype=float), "pidmode": p.mode,
                "slewing": self.pending and self.tw.polaris.goto_complete_at is None,
                "tracking": bool(self.tw.polaris._tracking)}

    def set_tracking(self, on):
        if on:
            self.tw.start_tracking()
        else:
            self.tw.polaris._tracking = False
            self.tw.pid.set_pid_mode("IDLE")

    def config(self, names):
        return {n: {"log_position": self.log_position, "advanced_eq_mode": False, "coordinated_speed_control": True}.get(n)
                for n in names}

    def set_config(self, values):
        self.log_position = values.get("log_position", self.log_position)

    def limits(self):
        from config import Config
        return (np.array([Config.z1_min_limit, Config.z2_min_limit, Config.z3_min_limit], dtype=float),
                np.array([Config.z1_max_limit, Config.z2_max_limit, Config.z3_max_limit], dtype=float))

    def mark(self, info):
        self.marks.append((self.now(), info))

    def slew(self, theta):
        self.tw.polaris.goto_complete_at = None
        self.tw.pid.set_goto_complete_callback(self.tw.polaris.markGotoAsComplete)
        self.tw.pid.set_theta_target(np.asarray(theta, dtype=float))
        self.pending = True

    def abort(self):
        self.set_tracking(False)                          # as Polaris.AbortSlew: stops tracking too
        self.pending = False

    def sleep(self, s):
        end = self.tw.clock.t + s
        while self.tw.clock.t < end - 1e-9:
            self.tw.run(min(0.2, end - self.tw.clock.t))
            self.trace.append((self.now(), self.tw.theta, self.status()["zeta"], self.tw.pid.mode))

    def now(self):
        return self.tw.clock.t


def plan(mount):
    """The legs to run, each target checked against M2_RANGE and the motor limits (mirrored, else skipped)."""
    s = mount.status()
    zmin, zmax = mount.limits()
    lo = zmin + np.array([Z_MARGIN, Z2_MARGIN, Z_MARGIN])
    hi = zmax - np.array([Z_MARGIN, Z2_MARGIN, Z_MARGIN])
    offset = s["tpv"] - s["zeta"]                         # theta = zeta + offset (constant between resets)
    base = np.array([s["tpv"][0], BASE_M2, s["tpv"][2]])

    def ok(theta):
        z = theta - offset
        return M2_RANGE[0] <= theta[1] <= M2_RANGE[1] and bool(np.all(z >= lo) and np.all(z <= hi))

    if not ok(base):
        sys.exit(f"The base pose {np.round(base, 1)} (zeta {np.round(base - offset, 1)}) is outside the limits: "
                 f"move M1/M3 nearer the middle of their range first")
    legs, notes = [("setup", base)], []
    for name, *delta in MOVES:
        delta = np.array(delta, dtype=float)
        target = base + delta
        if not ok(target):
            target = base - delta
            if not ok(target):
                notes.append(f"{name}: skipped (outside the limits both ways)")
                continue
            notes.append(f"{name}: mirrored")
        legs += [(f"{name}_out", target), (f"{name}_back", base)]
    return s, offset, legs, notes


def run(mount, legs, track=False):
    """Run the legs; returns [(name, seconds to complete, final error deg per motor)]. The final error is against
    the target motor angles, or tracking against the tracked setpoint (the target has moved on with the sky)."""
    results = []
    stop = {"now": False}

    def on_sigint(signum, frame):
        stop["now"] = True
    old = signal.signal(signal.SIGINT, on_sigint)
    try:
        for i, (name, target) in enumerate(legs):
            if stop["now"]:
                break
            mount.mark({"leg": name, "event": "start", "target": [round(float(x), 3) for x in target]})
            t0 = mount.now()
            mount.slew(target)
            mount.sleep(POLL_S)
            while mount.status()["slewing"] and not stop["now"]:
                if mount.now() - t0 > LEG_TIMEOUT_S:
                    print(f"  {name}: no completion after {LEG_TIMEOUT_S:.0f} s - aborting the test")
                    stop["now"] = True
                    break
                mount.sleep(POLL_S)
            if stop["now"]:
                mount.abort()
                mount.mark({"leg": name, "event": "aborted"})
                print("  Aborted.")
                break
            took = mount.now() - t0
            mount.sleep(HOLD_S)
            s = mount.status()
            if track and not s["tracking"]:
                print(f"  {name}: tracking stopped - stopping the test")
                mount.abort()
                break
            err = s["tpv"] - (s["tref"] if track else target)
            mount.mark({"leg": name, "event": "end", "seconds": round(took, 2), "error_deg": [round(float(x), 4) for x in err]})
            results.append((name, took, err))
            print(f"  [{i + 1:2d}/{len(legs)}] {name:12s} {took:5.1f} s   final error "
                  + " ".join(f"{e * 60:+6.1f}'" for e in err) + f"   mode {s['pidmode']}")
    finally:
        signal.signal(signal.SIGINT, old)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", action="store_true", help="print the moves and limit checks, no movement")
    ap.add_argument("--twin", action="store_true", help="dry-run in the digital twin instead of the mount")
    ap.add_argument("--track", action="store_true", help="run the gotos while tracking")
    args = ap.parse_args()

    mount = TwinMount() if args.twin else AlpacaMount()
    mount.preflight(track=args.track)
    cfg = mount.config(["log_position", "advanced_eq_mode", "coordinated_speed_control"])
    s, offset, legs, notes = plan(mount)
    print(f"Start  theta {np.round(s['tpv'], 1)}  zeta {np.round(s['zeta'], 1)}  "
          f"eq mode {cfg.get('advanced_eq_mode')}  coordinated speed control {cfg.get('coordinated_speed_control')}  "
          f"{'TRACKING' if args.track else 'tracking off'}")
    if cfg.get("advanced_eq_mode"):
        print("  Note: eq mode is on - the moves still run, but level mode is preferred for this test")
    for n in notes:
        print(f"  {n}")
    print(f"{len(legs)} legs (setup + {len(legs) - 1} out/back), M2 kept within {M2_RANGE}:")
    for name, target in legs:
        print(f"  {name:12s} -> theta {np.round(target, 1)}  zeta {np.round(target - offset, 1)}")
    if args.plan:
        return

    print("\nPress Ctrl+C at any time to abort the goto and stop.\n")
    log_position = cfg.get("log_position")
    was_tracking = s["tracking"]
    mount.set_config({"log_position": True})
    if args.track and not was_tracking:
        mount.set_tracking(True)
        mount.sleep(5.0)                                  # settle into TRACK before the first goto
        if not mount.status()["tracking"]:
            sys.exit("Tracking did not start - stopping")
    mount.mark({"event": "begin", "legs": len(legs), "moves": [m[0] for m in MOVES], "tracking": args.track})
    try:
        results = run(mount, legs, track=args.track)
    finally:
        mount.mark({"event": "finish"})
        if args.track and not was_tracking and mount.status()["tracking"]:
            mount.set_tracking(False)
        if not log_position:
            mount.set_config({"log_position": False})
    print(f"\n{len(results)}/{len(legs)} legs completed.")
    if args.twin:
        trace = mount.trace
        theta = np.array([t[1] for t in trace])
        zeta = np.array([t[2] for t in trace])
        modes = sorted({t[3] for t in trace})
        print(f"Twin: M2 range seen {theta[:, 1].min():.1f} .. {theta[:, 1].max():.1f}   "
              f"zeta min {np.round(zeta.min(axis=0), 1)} max {np.round(zeta.max(axis=0), 1)}   "
              f"PID modes {modes}   simulated time {trace[-1][0] - trace[0][0]:.0f} s")
    print(json.dumps({"legs": [(n, round(t, 2)) for n, t, _ in results]}))


if __name__ == "__main__":
    main()
