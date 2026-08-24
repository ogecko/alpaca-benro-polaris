# PID tuning harness (TRACK mode)

Standardized, repeatable test protocol for empirically tuning `pid_Kp`/`pid_Ki`/`pid_Kd`
for TRACK mode (sidereal tracking, sync/pulse guiding, orbital tracking all share this PID
mode -- see `PID_Controller.mode` in `driver/control.py`). GOTO/jog tuning (`AUTO` mode) is
out of scope here.

Designed to survive a lost/restarted session: every run's parameters, gains, and computed
metrics are appended to `results.jsonl` (git-tracked, durable), and the full raw telemetry
for each run is saved to `captures/<run_id>.jsonl` (gitignored -- can grow large over a
tuning sweep, but still survives locally) so it can be re-analyzed later without re-running
on hardware.

## Two test types

- **`steady`** -- test (d), the priority case. Undisturbed sidereal tracking at a fixed
  orientation; no injected disturbance. Measures steady-state RMS/max/mean position error
  per axis (M1/az, M2/alt, M3/roll).

- **`disturbance`** -- test (c). Injects a train of events and measures, per axis per event:
  peak overshoot and settling time (how long until the error is last outside a threshold
  band). This is disturbance *rejection*, distinct from steady-state quality -- a gain set
  can be excellent at one and mediocre at the other. Three interchangeable disturbance
  mechanisms (`--disturbance-kind`), which are **not** equivalent-severity at the same
  magnitude -- pick based on what you're actually testing:

  - **`step`** (default) -- `Polaris:SlewRelative`. Moves the PID setpoint directly, an
    instant hard step (harsh -- e.g. ~12-21" overshoot for a 20" step in early testing).
    Never touches `sync_history`/alignment, so it's safe to fire repeatedly during a tuning
    sweep. This is the standard choice for general Kp/Ki/Kd characterization.
  - **`sync`** -- a real `synctocoordinates` call. Only exercises the actual sync-guiding
    path (`q_syncguide_B`, gradually smoothed -- much gentler, e.g. ~1.5-4.5" overshoot for
    the same 20" magnitude) if `advanced_sync_guiding` is on; otherwise it's just an instant
    re-alignment. Also feeds the live QUEST/MPA fit (see MPA reset below). PEC's
    guide-correction path is exercised the same way, with `advanced_pec` additionally
    enabled.
  - **`pulseguide`** -- the real ASCOM `PulseGuide` REST API (`--pulseguide-direction`,
    `--pulseguide-duration-ms`) -- what autoguiders like PHD2 actually send.

Every run: slews to the requested Az/Alt/Roll, resets the Multi-Point Alignment model
(`advanced_alignment` off/on -- **wipes `sync_history`**, see below), then clears
sync-guiding state with a tracking off/on toggle (per `docs/control.md`'s "getting a clean
baseline" note) before starting, so results aren't contaminated by a previous run's state or
by real astronomical sync points.

### MPA reset is destructive by default

Every run resets the alignment model to identity/empty by default (`ac.reset_alignment()`),
because `sync`-kind disturbance events and `Polaris:SlewAbsolute`-driven positioning both
interact with the live QUEST/MPA fit, and a growing pile of synthetic tuning-experiment sync
points would otherwise contaminate it run over run. This is fine on a dev/test mount but
**will destroy a real alignment model built from genuine astronomical observations** -- pass
`--no-reset-alignment` to skip it (at the cost of run-to-run reproducibility for `sync`-kind
tests).

## Usage

```bash
cd /home/jdm/projects/alpaca-benro-polaris
uv run python utility/pid_tuning/run_experiment.py \
    --label baseline --test steady --az 240 --alt 45 --roll 0 --duration 90

uv run python utility/pid_tuning/run_experiment.py \
    --label kd_roll_0.6 --test disturbance --az 240 --alt 45 --roll 0 \
    --kd 0.5,0.5,0.6 --disturbance-kind step \
    --events 5 --event-interval 15 --event-arcsec 20 --duration 150
```

Gain overrides (`--kp`/`--ki`/`--kd`, each `M1,M2,M3`) are applied live via
`Polaris:ConfigUpdate` -- no restart needed. Omit them to test whatever gains are currently
live (still recorded in the result). Overrides are **not** persisted back to
`driver/config.toml` -- promote a winning gain set there manually once chosen.

Requires the driver running natively and reachable at `localhost:5555`/`5556` (see
`docs/control.md` section 1).

## Reading results

`results.jsonl` is one JSON object per line: label, test type, requested + actual
orientation, the full gain set (`pid_Kp/Ki/Kd/Ka/Kv/Ke`), KF noise params
(`kf_measure_noise`/`kf_process_noise` -- these affect the measured PV feeding
`error_signal`, so they matter for reproducibility too), PEC/alignment state in effect,
whether the MPA was reset, computed metrics, and (for `disturbance` runs) the disturbance
kind/params and exact wall-clock time of each injected event. `captures/<run_id>.jsonl` has
the raw deduplicated `pid`+`kf` telemetry records (same schema as the live websocket -- see
`docs/control.md` section 2) for anything not captured by the summary metrics.

`summarize.py` gives a compact, one-row-per-run comparison table (gains + headline outcome
metric per axis) instead of reading raw nested JSON:

```bash
uv run python utility/pid_tuning/summarize.py                        # all runs
uv run python utility/pid_tuning/summarize.py --test steady          # only steady runs
uv run python utility/pid_tuning/summarize.py --test disturbance --kind step
```

`report.py` generates a proper HTML report -- one row per run, grouped columns per axis
(RMS Error / Overshoot / Settle Time x M1/M2/M3), best value per axis+metric highlighted:

```bash
uv run python utility/pid_tuning/report.py            # writes report.html next to this file
```

To view it: publish `report.html` as a Claude Artifact and re-publish to the same URL after
each regeneration, or -- if you're driving the mount from WSL2 while viewing from the Windows
host, this works directly, no republish needed, just refresh after regenerating:

```
\\wsl.localhost\<your-distro-name>\home\<user>\projects\alpaca-benro-polaris\utility\pid_tuning\report.html
```

(confirmed working for this project's setup: `\\wsl.localhost\Ubuntu-26.04\home\jdm\projects\alpaca-benro-polaris\utility\pid_tuning\report.html`)

## Orientation coverage

Test at more than one Az/Alt before trusting a gain change generally -- FF-model accuracy
varies significantly with sky position (large near the horizon and toward the pole; see the
orientation-sweep findings referenced in issue #88). A gain set tuned at one point isn't
guaranteed to generalize; the moderate-altitude, away-from-horizon-and-pole points used so
far in this investigation include Az240/Alt45, Az240/Alt45/Roll-60, and Az60/Alt50.
