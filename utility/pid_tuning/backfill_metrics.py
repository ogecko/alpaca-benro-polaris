#!/usr/bin/env python3
"""
Recompute every run's metrics in results.jsonl from its saved raw capture file,
using the current metrics.py -- lets a metrics.py improvement (e.g. adding the
RA/Dec/PA equatorial frame) retroactively apply to historical runs without
re-running them on hardware. Only touches runs whose capture file still exists
on disk; leaves others untouched.

Usage:
  uv run python utility/pid_tuning/backfill_metrics.py
"""
import json
from pathlib import Path

import metrics

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.jsonl"
CAPTURES_DIR = HERE / "captures"


def recompute(run):
    capture_path = HERE / run["capture_file"]
    if not capture_path.exists():
        return None
    records = [json.loads(line) for line in open(capture_path) if line.strip()]
    if run["test"] == "steady":
        settle_skip = None
        # Reconstruct the settle_skip used originally isn't stored explicitly;
        # infer from n_records/duration is unreliable, so just reuse a safe
        # default consistent with what run_experiment.py's --settle-skip
        # default has been throughout this session.
        settle_skip = 30.0
        return metrics.steady_state_metrics(records, settle_skip_s=settle_skip)
    else:
        event_times = run.get("disturbance_params", {}).get("event_times", [])
        return metrics.disturbance_metrics(records, event_times)


def main():
    lines = [json.loads(l) for l in open(RESULTS_PATH) if l.strip()]
    updated = 0
    for run in lines:
        new_metrics = recompute(run)
        if new_metrics is None:
            continue
        run["metrics"] = new_metrics
        updated += 1
    with open(RESULTS_PATH, "w") as f:
        for run in lines:
            f.write(json.dumps(run) + "\n")
    print(f"recomputed metrics for {updated}/{len(lines)} runs")


if __name__ == "__main__":
    main()
