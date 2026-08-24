#!/usr/bin/env python3
"""
Compact, scannable summary of utility/pid_tuning/results.jsonl -- one row per
run, showing the gains used and the headline outcome metric(s) per axis, so
different parameter sets can be compared at a glance instead of reading raw
nested JSON.

Usage:
  uv run python utility/pid_tuning/summarize.py                 # all runs
  uv run python utility/pid_tuning/summarize.py --test steady   # only steady runs
  uv run python utility/pid_tuning/summarize.py --test disturbance --kind step
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.jsonl"

AXES = ["M1_az", "M2_alt", "M3_roll"]


def load_results():
    if not RESULTS_PATH.exists():
        return []
    return [json.loads(line) for line in open(RESULTS_PATH) if line.strip()]


def fmt_gain_triple(gains, key):
    v = gains.get(key)
    if v is None:
        return "-"
    return "/".join(f"{x:g}" for x in v)


def steady_row(r):
    m = r["metrics"]
    return " ".join(f"{ax.split('_')[1]}={m[ax]['rms_arcsec']:.2f}\"" for ax in AXES if ax in m)


def disturbance_row(r):
    m = r["metrics"]
    parts = []
    for ax in AXES:
        if ax not in m:
            continue
        d = m[ax]
        settle = f"{d['median_settling_time_s']:.1f}s" if d["median_settling_time_s"] is not None else "N/A"
        parts.append(f"{ax.split('_')[1]}=ov{d['mean_overshoot_arcsec']:.1f}\"/t{settle}"
                     + (f"(!{d['n_unsettled']})" if d["n_unsettled"] else ""))
    return " ".join(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--test", choices=["steady", "disturbance"], help="filter to one test type")
    p.add_argument("--kind", choices=["step", "sync", "pulseguide"], help="[disturbance] filter to one disturbance kind")
    args = p.parse_args()

    rows = load_results()
    if args.test:
        rows = [r for r in rows if r["test"] == args.test]
    if args.kind:
        rows = [r for r in rows if r.get("disturbance_params", {}).get("kind") == args.kind]
    rows.sort(key=lambda r: r["timestamp"])

    if not rows:
        print("no matching runs in results.jsonl")
        return

    header = f"{'label':22s} {'test':11s} {'orientation':18s} {'Kp':10s} {'Ki':14s} {'Kd':10s}  outcome"
    print(header)
    print("-" * len(header))
    for r in rows:
        o = r["actual_orientation"]
        orientation = f"{o['az']:.0f}/{o['alt']:.0f}/{o['roll']:.0f}"
        gains = r["gains"]
        kp = fmt_gain_triple(gains, "pid_Kp")
        ki = fmt_gain_triple(gains, "pid_Ki")
        kd = fmt_gain_triple(gains, "pid_Kd")
        test = r["test"]
        if test == "disturbance":
            test = f"dist/{r.get('disturbance_params', {}).get('kind', '?')}"
        outcome = steady_row(r) if r["test"] == "steady" else disturbance_row(r)
        print(f"{r['label']:22s} {test:11s} {orientation:18s} {kp:10s} {ki:14s} {kd:10s}  {outcome}")


if __name__ == "__main__":
    main()
