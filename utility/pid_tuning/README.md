# PID Tuning Utility

Standardized, repeatable test protocol for empirically tuning `pid_Kp`/`pid_Ki`/`pid_Kd`/`kf_measure_noise`/`kf_process_noise` parameters. Can cover testing for sidereal tracking, sync guiding, pulse guiding, and orbital tracking. 

Designed to survive a lost/restarted session: every run's parameters, gains, and computed
metrics are appended to `results.jsonl` (git-tracked, durable), and the full raw telemetry
for each run is saved to `captures/<run_id>.jsonl` (gitignored -- can grow large over a
tuning sweep, but still survives locally) so it can be re-analyzed later without re-running
on hardware.

## Two Test Types

- **`steady`** -- high importance case. Undisturbed sidereal tracking at a fixed orientation; no
    injected disturbance. Measures steady-state RMS/max/mean position error per axis (M1/RA,
    M2/Dec, M3/PA).

- **`disturbance`** -- disturbance rejection. Injects a train of events and measures, per axis per event:
    peak overshoot and settling time (how long until the error outside a threshold
    band). This is disturbance *rejection* is distinct from steady-state quality. A pid gain set
    can be excellent at one and mediocre at the other. Three kinds of disturbances are supported:
  
    - **`step`** (default) -- `Polaris:SlewRelative`. Moves the PID setpoint directly, an instant hard step. 
        Does not effect `sync_history`/alignment, so it's safe to fire repeatedly during a tuning
        sweep. This is the standard choice for general Kp/Ki/Kd characterization.
    - **`pulseguide`** -- the real ASCOM `PulseGuide` REST API (`--pulseguide-direction`,
        `--pulseguide-duration-ms`). What autoguiders like PHD2 actually send. This steps the PID preset value and causes the controller to drive the mount back to its target setpoint.
    - **`sync`** -- a real `synctocoordinates` call. Typically follows a plate-solve in normal operation. 
        Is used to feed the live QUEST/MPA fit (if `advanced_alignment` enabled). 
        Alternately can be used to drive sync-guiding (if `advanced_sync_guiding` enabled, and no Goto since last sync).
        Finally, can also be used to train PEC (if `advanced_sync_guiding` and `advanced_pec_drift` are enabled).

Every run: slews to the requested Az/Alt/Roll, resets the Multi-Point Alignment model
(`advanced_alignment` off/on -- **wipes `sync_history`**, see below), then clears
sync-guiding state with a tracking off/on toggle (per this document's "getting a clean
baseline" note) before starting, so results aren't contaminated by a previous run's state or
by real astronomical sync points.

**MPA reset is destructive by default**


Every run resets the alignment model to identity/empty by default, because results will depend on the live QUEST/MPA fit, and a growing pile of synthetic tuning-experiment sync points would otherwise contaminate it run over run. Use `--no-reset-alignment` to skip this (at the cost of run-to-run reproducibility for `sync`-kind
tests).

## Usage

Requires the driver running natively and reachable at `localhost:5555`/`5556` (see [Running the Driver Natively](../../docs/architecture.md#running-the-driver-natively)).
All commands below run from the repo root:

```bash
cd /home/jdm/projects/alpaca-benro-polaris
```

Gain overrides (`--kp`/`--ki`/`--kd`, each `M1,M2,M3`) and KF noise overrides
(`--kf-measure-noise`/`--kf-process-noise`, each 6 values `pos1,pos2,pos3,vel1,vel2,vel3`) are
applied live via `Polaris:ConfigUpdate` -- no restart needed. Omit them to test whatever gains
are currently live (still recorded in the result). Overrides are **not** persisted back to
`driver/config.toml`. Promote a winning gain/KF set to config.toml manually once chosen.

`--duration` must cover the whole event schedule -- roughly
`pre_settle + (events-1)*event_interval + 25`, or the last event(s) will look artificially
"unsettled" just from running out of capture time (the harness warns if you undershoot this).

**Examples**


**Steady-state** -- undisturbed sidereal tracking, RMS/max/mean error per axis:

```bash
uv run python utility/pid_tuning/run_experiment.py \
    --label baseline --test steady --az 240 --alt 45 --roll 0 --duration 90
```

**Disturbance, `step` kind (default)** -- instant setpoint jump via `Polaris:SlewRelative`,
always on RA. Good for general Kp/Ki/Kd characterization; unlike `sync`, it never touches
`sync_history`/the alignment model, so it's safe to repeat many times in a sweep:

```bash
uv run python utility/pid_tuning/run_experiment.py \
    --label kd_roll_0.6 --test disturbance --az 240 --alt 45 --roll 0 \
    --kd 0.5,0.5,0.6 --disturbance-kind step \
    --events 5 --event-interval 30 --event-arcsec 20 --pre-settle 5 --duration 160
```

**Disturbance, `sync` kind** -- exercises the real sync-guiding path (`q_syncguide_B`); needs
`advanced_sync_guiding` on to be a real test rather than an instant re-alignment, and pollutes
`sync_history`/the live MPA fit, so use sparingly against a real alignment model (see MPA reset
note below):

```bash
uv run python utility/pid_tuning/run_experiment.py \
    --label sync_baseline --test disturbance --az 240 --alt 45 --roll 0 \
    --disturbance-kind sync --event-arcsec 20 \
    --events 5 --event-interval 30 --pre-settle 5 --duration 160
```

**Disturbance, `pulseguide` kind** -- the real ASCOM `PulseGuide` API, what autoguiders like
PHD2 actually send. `--pulseguide-direction` picks the axis (`0`=N, `1`=S -> Dec; `2`=E,
`3`=W -> RA) and `--pulseguide-duration-ms` the pulse length -- a typical short guide
correction is a few hundred ms, not seconds (at 1x sidereal guide rate, 500ms ~= 7.5"):

```bash
# RA axis, realistic short pulse
uv run python utility/pid_tuning/run_experiment.py \
    --label pulseguide_ra_500ms --test disturbance --az 240 --alt 45 --roll 0 \
    --disturbance-kind pulseguide --pulseguide-direction 2 --pulseguide-duration-ms 500 \
    --events 5 --event-interval 20 --pre-settle 5 --duration 110

# Dec axis, same magnitude
uv run python utility/pid_tuning/run_experiment.py \
    --label pulseguide_dec_500ms --test disturbance --az 240 --alt 45 --roll 0 \
    --disturbance-kind pulseguide --pulseguide-direction 0 --pulseguide-duration-ms 500 \
    --events 5 --event-interval 20 --pre-settle 5 --duration 110
```

**KF noise override** -- e.g. widening measurement noise to trust the model more than raw
sensor readings:

```bash
uv run python utility/pid_tuning/run_experiment.py \
    --label kf_measure_wide --test steady --az 240 --alt 45 --roll 0 --duration 90 \
    --kf-measure-noise 0.01,0.02,0.03,0.005,0.01,0.01
```

## Reading Results

`results.jsonl` is one JSON object per line: label, test type, requested + actual
orientation, the full gain set (`pid_Kp/Ki/Kd/Ka/Kv/Ke`), KF noise params
(`kf_measure_noise`/`kf_process_noise` -- these affect the measured PV feeding
`error_signal`, so they matter for reproducibility too), PEC/alignment state in effect,
whether the MPA was reset, computed metrics, and (for `disturbance` runs) the disturbance
kind/params and exact wall-clock time of each injected event. `captures/<run_id>.jsonl` has
the raw deduplicated `pid`+`kf` telemetry records (same schema as the live websocket -- see
[Live Telemetry](../../docs/pilot-api.md#websocket)) for anything not captured by the summary metrics.

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

## Orientation Coverage

Test at more than one Az/Alt before trusting a gain change generally -- FF-model accuracy
varies significantly with sky position (large near the horizon and toward the pole; see the
orientation-sweep findings referenced in issue #88). A gain set tuned at one point isn't
guaranteed to generalize; the moderate-altitude, away-from-horizon-and-pole points used so
far in this investigation include Az240/Alt45, Az240/Alt45/Roll-60, and Az60/Alt50.

**Observation: elevated RA/PA noise near meridian (Az≈178°)**


**Symptom:** at Az178/Alt51/Roll0 (near due south / meridian transit), equatorial-frame RA
and PA tracking error is 3-4x worse than at every other orientation tested, while the
underlying motor axes (M1/M2/M3) and Dec all look completely normal.

**Evidence** (`results.jsonl` run IDs `20260825T000409_steady_az178_alt51_roll0` and
`20260825T000715_disturbance_step_az178_alt51_roll0` -- summary metrics are in git history,
raw `captures/*.jsonl` are gitignored/local-only and were not committed):

- Steady-state RMS at Az178/Alt51/Roll0: RA=3.75", PA=3.68" -- vs. RA=0.6-1.1", PA=0.4-0.75"
    at every other orientation tested that session (Az240/Alt45/Roll0, Az280/Alt30/Roll15,
    Az292/Alt30/Roll-40). Dec (0.54") and all three motors (M1=0.77", M2=0.55", M3=1.18")
    were normal at Az178 too -- only the RA/PA *combination* is affected.
- A 20" step disturbance at the same orientation recovers fast and cleanly at first
    (RA back near zero by ~3.2s), but RA/PA then settle into a **continuous, ongoing
    oscillation** for the rest of the window -- not a disturbance-recovery tail. Roughly
    4-5s period, ±3-5" amplitude, RA and PA moving as near-exact mirror images of each other
    (e.g. one sample pair: RA=+5.27", PA=-5.09"). M1/M2/M3 stay quiet (<1.5") throughout this
    same window. Because "settled" requires staying inside a threshold band continuously, every
    RA/PA event in that run showed as never settling (n_unsettled=5/5), while M1/M2/Dec showed
    n_unsettled=0.
- Ruled out as a telemetry artifact: checked both captures for gaps in the `t` field (the
    kind of 518-dropout gap that produced a separate, unrelated false-positive at
    Az292/Alt30/Roll-40 that session -- see below) and found none in either Az178 capture.
    This is real data.

**Leading hypothesis (not yet confirmed):** a geometric/kinematic sensitivity specific to
near-meridian transit. RA and PA being anti-correlated while Dec stays clean suggests a
near-singular direction in the motor-space-to-equatorial-space transform (`kinematics.py`:
`theta_to_jacobian`, `calc_equatorial_axes_B`, `azaltroll_to_q`/`q_to_azaltroll`) around
Az=180°, where ordinary small motor-space noise gets amplified into a larger apparent RA/PA
wobble. Possibly related to parallactic-angle rotation rate being at its local maximum near
transit. This has **not** been traced into the kinematics code yet -- it's inferred purely
from the telemetry symmetry (Dec unaffected, RA/PA mirrored, motors clean).

**Suggested next steps:**

1. Futher tests using PID Tuning and Telemetry monitoring at different orientations to reproduce oscillation and confirm it is meridian related.
1. Bracket the effect: repeat the steady/disturbance pair from
    `utility/pid_tuning/run_experiment.py` (see Usage above) at a few Az values either side of
    178° (e.g. 160, 170, 190, 200) at the same Alt/Roll, to see how localized to the meridian
    it is.
2. Vary Alt/Roll at Az≈178° to check whether the effect is purely Az-driven or also
    Alt/Roll-dependent.
3. Read through the kinematics transform functions listed above looking for a term that goes
    through zero or a local extremum near Az=180° (a classic sign of this kind of amplification).

**Separately, an intermittent, unrelated hardware/comms issue was also confirmed this
session:** the Polaris sometimes stops sending 518 telemetry messages for a few seconds,
during which `θ_pv` visibly freezes while `θ_sp` keeps advancing -- producing large but
spurious error readings once telemetry resumes and the estimate snaps to catch up (seen as a
~4.3s gap that inflated one disturbance run's overshoot to 60-65" before a clean retest
confirmed the underlying orientation, Az292/Alt30/Roll-40, was actually fine). Not a PID/control
bug -- flagged here only so it isn't mistaken for one if it recurs. Check for gaps in the raw
capture's `t` field before trusting any one run's "huge" overshoot number.
