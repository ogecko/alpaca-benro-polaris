#!/usr/bin/env python3
"""
Standardized, repeatable PID tuning experiment for TRACK mode.

Two test types (see docs/control.md's PID/PEC sections for background):

  steady       -- test (d): undisturbed sidereal tracking. No injected
                  disturbance; measures steady-state RMS/max error per axis.
                  This is the priority scenario.

  disturbance  -- test (c): disturbance rejection. Injects a train of events
                  and measures peak overshoot + settling time per axis, per
                  event. Three interchangeable disturbance mechanisms
                  (--disturbance-kind):
                    step        Polaris:SlewRelative (default) -- moves the
                                PID setpoint directly, never touches
                                sync_history/alignment. Safe for repeated runs.
                    sync        real synctocoordinates -- exercises the actual
                                sync-guiding path (q_syncguide_B), but only if
                                advanced_sync_guiding is on; also feeds the
                                live QUEST/MPA fit, so use sparingly against a
                                real alignment model. (PEC's guide-correction
                                path is exercised the same way, with
                                advanced_pec additionally enabled.)
                    pulseguide  real ASCOM PulseGuide -- what autoguiders like
                                PHD2 actually send.

Every run: (1) optionally applies a gain override via Polaris:ConfigUpdate
(live, no restart), (2) slews to the requested Az/Alt/Roll, (3) clears
sync-guiding state via a tracking off/on toggle for a clean baseline, (4) runs
the test while capturing 'pid'+'kf' websocket telemetry, (5) computes metrics,
and (6) appends one JSON record to results.jsonl (durable -- survives a
session/container restart) plus the raw deduplicated telemetry to
captures/<run_id>.jsonl for later re-analysis.

Usage:
  uv run python utility/pid_tuning/run_experiment.py \\
      --label baseline --test steady --az 240 --alt 45 --roll 0 --duration 90

  uv run python utility/pid_tuning/run_experiment.py \\
      --label kd_roll_0.6 --test disturbance --az 240 --alt 45 --roll 0 \\
      --kd 0.5,0.5,0.6 --events 5 --event-interval 15 --event-arcsec 20 \\
      --duration 150
"""
import argparse
import json
import threading
import time
from pathlib import Path

import alpaca_client as ac
import telemetry
import metrics

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.jsonl"
CAPTURES_DIR = HERE / "captures"

GAIN_KEYS = ["pid_Kp", "pid_Ki", "pid_Kd", "pid_Ka", "pid_Kv", "pid_Ke"]
KF_KEYS = ["kf_measure_noise", "kf_process_noise"]


def parse_triple(s):
    if s is None:
        return None
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected 3 comma-separated values, e.g. 1.0,1.0,0.8")
    return parts


def parse_six(s):
    if s is None:
        return None
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 6:
        raise argparse.ArgumentTypeError(
            "expected 6 comma-separated values [pos1,pos2,pos3,vel1,vel2,vel3], e.g. "
            "0.003,0.006,0.006,0.0016,0.003,0.0016")
    return parts


def apply_gain_overrides(args):
    changes = {}
    if args.kp is not None:
        changes["pid_Kp"] = parse_triple(args.kp)
    if args.ki is not None:
        changes["pid_Ki"] = parse_triple(args.ki)
    if args.kd is not None:
        changes["pid_Kd"] = parse_triple(args.kd)
    if args.kf_measure_noise is not None:
        changes["kf_measure_noise"] = parse_six(args.kf_measure_noise)
    if args.kf_process_noise is not None:
        changes["kf_process_noise"] = parse_six(args.kf_process_noise)
    if changes:
        ac.config_update(changes)


def current_gains():
    return ac.config_fetch(GAIN_KEYS)


def current_kf_params():
    return ac.config_fetch(KF_KEYS)


def current_pec_state():
    return ac.config_fetch(["advanced_pec", "advanced_sync_guiding", "advanced_alignment", "advanced_align_mac"])


def run_steady_test(duration_s, settle_skip_s):
    records = telemetry.capture(duration_s, topics=("pid", "kf"))
    result = metrics.steady_state_metrics(records, settle_skip_s=settle_skip_s)
    return records, result, []


DISTURBANCE_KINDS = ("step", "sync", "pulseguide")


def _inject_disturbance(kind, event_arcsec, pulseguide_direction, pulseguide_duration_ms):
    if kind == "step":
        # Polaris:SlewRelative -- moves the PID setpoint directly, never touches
        # sync_history/alignment. Safe to fire many times during a tuning sweep.
        ac.step_ra_arcsec(event_arcsec)
    elif kind == "sync":
        # Real sync -- exercises the actual sync-guiding path (q_syncguide_B), but
        # ONLY if advanced_sync_guiding is enabled; otherwise it's just an instant
        # re-alignment. Also records into sync_history and feeds the live
        # QUEST/MPA fit -- don't run this many times against a real alignment model.
        ac.sync_ra_offset_arcsec(event_arcsec)
    elif kind == "pulseguide":
        # Real ASCOM PulseGuide -- the actual mechanism autoguiders (PHD2 etc.) use.
        ac.pulse_guide(pulseguide_direction, pulseguide_duration_ms)
    else:
        raise ValueError(f"unknown disturbance kind {kind!r}, expected one of {DISTURBANCE_KINDS}")


def run_disturbance_test(duration_s, n_events, interval_s, pre_settle_s, kind,
                          event_arcsec, pulseguide_direction, pulseguide_duration_ms):
    if kind == "sync":
        sg = ac.config_fetch(["advanced_sync_guiding"])["advanced_sync_guiding"]
        if not sg:
            print("warning: --disturbance-kind sync but advanced_sync_guiding is OFF -- "
                  "this will just be an instant re-alignment, not a test of the sync-guiding path")

    result_holder = {}

    def _capture():
        result_holder["records"] = telemetry.capture(duration_s, topics=("pid", "kf"))

    t = threading.Thread(target=_capture)
    t.start()
    # Let the post-toggle settling transient (can run 20-40s -- see README) die down
    # before the first event, so event 1 isn't confounded by baseline-establishment
    # noise rather than genuine disturbance-response.
    time.sleep(pre_settle_s)

    event_times = []
    for i in range(n_events):
        _inject_disturbance(kind, event_arcsec, pulseguide_direction, pulseguide_duration_ms)
        event_times.append(time.time())
        if i < n_events - 1:
            time.sleep(interval_s)

    t.join()
    records = result_holder["records"]
    result = metrics.disturbance_metrics(records, event_times)
    return records, result, event_times


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--label", required=True, help="short name for this run, e.g. 'baseline' or 'kd_roll_0.6'")
    p.add_argument("--test", choices=["steady", "disturbance"], required=True)
    p.add_argument("--az", type=float, required=True)
    p.add_argument("--alt", type=float, required=True)
    p.add_argument("--roll", type=float, required=True)
    p.add_argument("--duration", type=float, default=90.0, help="total capture window, seconds")
    p.add_argument("--settle-skip", type=float, default=30.0,
                    help="[steady] seconds to discard at the start as post-slew/toggle settling "
                         "transient before computing steady-state metrics -- observed settling "
                         "after a slew/tracking-toggle can run 20-40s, don't set this too low")
    p.add_argument("--kp", help="override pid_Kp as 'M1,M2,M3', e.g. 1.0,1.0,1.0")
    p.add_argument("--ki", help="override pid_Ki as 'M1,M2,M3'")
    p.add_argument("--kd", help="override pid_Kd as 'M1,M2,M3'")
    p.add_argument("--kf-measure-noise", help="override kf_measure_noise as 'pos1,pos2,pos3,vel1,vel2,vel3' (6 values)")
    p.add_argument("--kf-process-noise", help="override kf_process_noise as 'pos1,pos2,pos3,vel1,vel2,vel3' (6 values)")
    p.add_argument("--events", type=int, default=5, help="[disturbance] number of events")
    p.add_argument("--event-interval", type=float, default=15.0, help="[disturbance] seconds between events")
    p.add_argument("--disturbance-kind", choices=DISTURBANCE_KINDS, default="step",
                    help="[disturbance] 'step' (Polaris:SlewRelative, default) sets the PID setpoint "
                         "directly and never touches sync_history/alignment -- safe for repeated tuning "
                         "runs. 'sync' exercises the real sync-guiding path (needs advanced_sync_guiding "
                         "on) but records into sync_history/feeds the live alignment fit -- use sparingly "
                         "against a real alignment model. 'pulseguide' uses the real ASCOM PulseGuide API "
                         "(what autoguiders like PHD2 actually send).")
    p.add_argument("--event-arcsec", type=float, default=20.0,
                    help="[disturbance, kind=step|sync] RA offset per event")
    p.add_argument("--pulseguide-direction", type=int, default=ac.PULSEGUIDE_EAST,
                    help="[disturbance, kind=pulseguide] 0=N 1=S 2=E 3=W")
    p.add_argument("--pulseguide-duration-ms", type=int, default=1000,
                    help="[disturbance, kind=pulseguide] pulse duration in ms, 1-10000")
    p.add_argument("--pre-settle", type=float, default=25.0,
                    help="[disturbance] seconds to wait after the clean-baseline toggle before the "
                         "first event, so it isn't confounded by the post-toggle settling transient")
    p.add_argument("--notes", default="", help="free-text notes for the results log")
    p.add_argument("--no-reset-alignment", action="store_true",
                    help="skip the default MPA reset (advanced_alignment off/on, which wipes "
                         "sync_history) -- pass this to preserve an existing real alignment model, "
                         "at the cost of run-to-run reproducibility for any 'sync'-kind disturbance test")
    args = p.parse_args()

    ac.wait_until_connected(timeout=10)
    apply_gain_overrides(args)
    gains = current_gains()
    kf_params = current_kf_params()
    pec_state = current_pec_state()

    if args.no_reset_alignment:
        print("NOTE: --no-reset-alignment passed -- MPA model left untouched")
    else:
        print("Resetting MPA (advanced_alignment off/on) for a clean, reproducible baseline -- "
              "this wipes sync_history. Pass --no-reset-alignment to preserve an existing model.")
        ac.reset_alignment()

    ac.set_tracking(True)
    ac.slew_absolute(args.az, args.alt, args.roll, isasync=False)
    ac.clean_tracking_baseline()

    actual_az, actual_alt, actual_roll = ac.azimuth(), ac.altitude(), ac.roll()

    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}_{args.label}"
    print(f"[{run_id}] test={args.test} orientation=({actual_az:.2f},{actual_alt:.2f},{actual_roll:.2f}) "
          f"gains={gains}")

    if args.test == "steady":
        records, result, event_times = run_steady_test(args.duration, args.settle_skip)
    else:
        min_duration = args.pre_settle + (args.events - 1) * args.event_interval + 25.0
        if args.duration < min_duration:
            print(f"warning: --duration {args.duration}s is short for this event schedule "
                  f"(pre-settle + events + trailing window needs ~{min_duration:.0f}s) -- "
                  f"the last event(s) may look artificially 'unsettled' just from running out of capture time")
        records, result, event_times = run_disturbance_test(
            args.duration, args.events, args.event_interval, args.pre_settle, args.disturbance_kind,
            args.event_arcsec, args.pulseguide_direction, args.pulseguide_duration_ms)

    expected_min = args.duration * 2  # ~5-6Hz combined pid+kf rate; well under half that means something's wrong
    if len(records) < expected_min * 0.2:
        print(f"WARNING: only {len(records)} telemetry records captured over {args.duration}s "
              f"(expected order of {expected_min:.0f}+) -- the websocket connection likely failed "
              f"for some/all of this run (e.g. ws://↔wss:// scheme mismatch after a driver restart). "
              f"This result is probably NOT trustworthy -- check before relying on it.")

    CAPTURES_DIR.mkdir(exist_ok=True)
    capture_path = CAPTURES_DIR / f"{run_id}.jsonl"
    with open(capture_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    summary = {
        "run_id": run_id,
        "timestamp": time.time(),
        "label": args.label,
        "test": args.test,
        "requested_orientation": {"az": args.az, "alt": args.alt, "roll": args.roll},
        "actual_orientation": {"az": actual_az, "alt": actual_alt, "roll": actual_roll},
        "gains": gains,
        "kf_params": kf_params,
        "pec_state": pec_state,
        "alignment_reset": not args.no_reset_alignment,
        "duration_s": args.duration,
        "n_records": len(records),
        "capture_file": str(capture_path.relative_to(HERE)),
        "metrics": result,
        "notes": args.notes,
    }
    if args.test == "disturbance":
        summary["disturbance_params"] = {
            "kind": args.disturbance_kind,
            "n_events": args.events, "interval_s": args.event_interval, "event_arcsec": args.event_arcsec,
            "pulseguide_direction": args.pulseguide_direction, "pulseguide_duration_ms": args.pulseguide_duration_ms,
            "event_times": event_times,
        }

    with open(RESULTS_PATH, "a") as f:
        f.write(json.dumps(summary) + "\n")

    print(json.dumps(summary["metrics"], indent=2))
    print(f"[{run_id}] appended to {RESULTS_PATH}, raw capture at {capture_path}")


if __name__ == "__main__":
    main()
