# PEC Drift — When to Learn, When to Apply

Branch: `feature/equatorial_mode` (Oct 2026). Started from 2026-10-20 20:45, when PEC Drift Correction learnt PHD2's
catch-up after guiding started before tracking as a -30"/min Dec drift, applied it for 20 min (-165"), and PHD2 spent
those minutes pulsing it back. This study sets out which guide corrections PEC should learn from, which it should not
(**ignore** cases), when the rate it has learnt is fit to apply (**inhibit** cases), how each case is detected for
both sync guiding and pulse guiding, and the data that verifies the design.

Code: `driver/control_pec.py` (`PecMixin`, `PecAxis`, `GuiderCalibrationDetector`). Analysis:
`utility/analyse_tracking.ipynb` section 3 (who corrected the drift), `utility/analyse_sessions.ipynb`.

---

## Terms

* **Drift**: the slowly varying rate at which the sky moves against the mount after the worm feed-forward, per axis
  (RA, Dec). PEC learns it from the running total of guide corrections, y(t) = pulse guiding + sync guiding + PEC
  applied (`correction_breakdown`), as an EMA of the rate over `pec_tau_sec` (450 s).
* **Learn**: fold a guide correction into the rate. **Ignore** = take the correction into the total (it really was a
  correction) but not into the rate, keep applying the rate already learnt, and restart the rate's differencing
  afterwards (`PecAxis.hold`). An ignore case says why a correction isn't evidence of drift; it can last for one
  correction (`STEP`) or for a span of them (`REVERSAL`, `ACQUIRE`).
* **Discard** = drop the correction altogether, not even into the total (`OUTLIER` today). Kept for corrections that
  can't be real; dropping a real one leaves the total short by it from then on.
* **Apply**: feed the learnt rate forward to the PID every tick. **Inhibit** = don't apply it (the axis's rate isn't
  trusted yet, or no longer). An inhibit case says why.
* **Reset**: throw the model away (a new pointing). Not an ignore: nothing learnt before it is kept.

The two lists below are the names logged in PECLOG: `inhibit` (per axis, today) and, proposed, `ignore` (the ignore
case, e.g. `'REVERSAL:M2'`, `'ACQUIRE'`; it replaces today's `paused`, which carries only the motors of a reversal or
slack crossing, e.g. `'M2'` — the notebooks read both, for older logs).

---

## Requirements

* **R1 Learn only drift.** A correction that measures anything else (a re-centre, a guider's deliberate move, a
  mechanical transient, a stale position) is ignored, whichever guider sent it.
* **R2 One design for sync and pulse guiding.** Both reduce to y(t) per axis. Thresholds are rates (correction ÷ update
  interval) or are scaled by each axis's own update interval: a 5 min sync gap with a 60" residual and a 2 s pulse of
  1" are the same 12"/min.
* **R3 Use what the driver knows.** Events the driver sees exactly (tracking on, goto/rotate complete, a pulse it
  rejected, a motor reversal, BLC acting, stale 518 data) start an ignore case directly, without waiting for the signal.
* **R4 Judge bursts over time, not per update.** A catch-up, a dither or a slack crossing spans many pulses; a rule
  that sees one update at a time either misses it or, after a few in a row, learns it.
* **R5 Bounded damage.** Whatever the ignore cases miss moves the rate only so far per update (robust update), so one missed
  case can't fit -30"/min.
* **R6 Undo what was learnt in hindsight.** A case recognised only after it started (a calibration on its 3rd pulse,
  a burst once it is clear) rolls the model back to where the case began.
* **R7 Don't hide real drift.** A genuine change of drift (a flip, a new target, cable drag) is still learnt within
  about τ; corrections ignored on clean guiding cost little learning time.
* **R8 Apply only a trustworthy rate.** The rate is applied once it rests on enough time and corrections, not merely
  enough corrections (3 pulses arrive in 4 s).
* **R9 Explain itself.** Each ignore and inhibit is logged with its case name (PECLOG `ignore`, `inhibit`) and drawn by
  the analysis notebooks.
* **R10 Testable offline and closed loop.** Every case has archived examples and a digital twin scenario.

---

## Inhibit cases (apply or not)

| Name | Meaning | Current | Proposed |
|---|---|---|---|
| `IDLE` | the model has no data yet | before the first ingest | keep |
| `TOO_FEW_OBS` | fewer than `pec_min_observations` (3) corrections | n < 3 | keep, and add `MIN_SPAN` |
| `MIN_SPAN` | the rate rests on too short a time | — | **new**: learnt over at least 2 min and 3 updates (sync guiding: 3 syncs). 2026-10-20 was VALID 10 s after its first pulse |
| `HIGH_RMSE` | prediction rms ≥ `pec_max_rmse_arcmin` (6') | yes | keep, scaled by the update interval (R2) |
| `LOW_R2` | R² < `pec_min_r2` (0.5) | yes | keep; R² was 1.0 on the 2026-10-20 catch-up (a steady catch-up fits a line), so it can't stand alone |
| `UNCERTAIN` | the rate's standard error is large against the rate | — | **new**: inhibit while the rate's standard error exceeds max(1"/min, 50% of the rate) |
| `NOT_CONVERGED` | — | in the enum, never set | remove, or use for `UNCERTAIN` |
| `STALE` | no update for > 3x the usual interval (≥ 300 s) | yes (PECLOG `stale` flag, not the enum) | move into the enum; the first update after it starts a `GAP` ignore |
| `VALID` | apply | yes | keep |

---

## Ignore cases (learn or not)

Each case: what it is, whether it occurs under pulse guiding (PG) and sync guiding (SG), what PEC does today, and the
proposed detection and when it ends. *Event* = detected from the driver's own state (R3); *signal* = detected from the
corrections (R4). A case that spans corrections ends when its minimum time has passed **and** the burst test (below)
reports the axis settled.

| Name | Case | PG | SG | Current | Proposed detection | Ends |
|---|---|---|---|---|---|---|
| `ACQUIRE` | settling onto the target after tracking starts, a goto/rotate/slew completes, or guiding starts | the guider pulls the star onto its lock position | the first syncs remove the goto's pointing error | model reset at goto/pan/roll, then learnt from the first correction | event: tracking on, move complete, first pulse after `GAP` | 60 s PG / 2 syncs SG, and settled |
| `CATCHUP` | recovering an offset that built while the guider couldn't act | full-length pulses (2026-10-20 20:45) | a large first residual | learnt | event: a pulse the driver rejected (`Cannot pulse guide while not tracking`), then the first accepted pulses | as `ACQUIRE`, from the first accepted pulse; roll back to the first rejection |
| `GAP` | resuming after the guider stopped (star lost, clouds, solves failing) | yes | yes | `STALE` stops applying; the first update after is learnt | event: first update after `STALE` | as `ACQUIRE` |
| `CALIBRATEPHD2` | PHD2's calibration, backlash clearing, recentre | identical pulses, one axis, one direction | — | detected on 3 *consecutive* identical pulses, rolled back, quiet 20 s | per axis: each axis's own last pulse, so interleaved RA/Dec pulses don't break the run; pulses ≥ 1 s only | 20 s quiet (today) |
| `CALIBRATECCD` | CCDciel's calibration ramp | each pulse 1.5x the last, ≥ 300 ms | — | detected (same detector) | per axis, as above | 20 s quiet |
| `SATURATED` | the guider is clamped at its longest pulse | repeated pulses at the axis's maximum duration | — | learnt | signal: a pulse within 10% of the longest seen on that axis, 2+ in a row | when pulses drop below 50% of it |
| `BURST` | a one-sided excess over a short window: dither recovery, re-centre, any settling the events miss | yes (dither ~10-30 s) | a re-centre | per-update `STEP`, learnt after 3 in a row | signal: short-window rate (3 updates or 30 s) vs the model's rate, beyond kσ and one-sided | settled: back within kσ for 2 updates |
| `STEP` | a single jump: bad plate solve, guide star swap, hot pixel | rare | 2026-10-17 23:27 (+165", then -185") | yes: > 4σ and ≥ 30", folded in, learnt after 2 in a row | keep, but compare rates (residual ÷ interval) so SG and PG use one rule | the next update |
| `OUTLIER` | a residual too big to be drift at all | rare | wrong field, failed solve | yes: > `pec_max_resid_arcmin` (10') **discarded** (not in the total) | keep, scaled by the update interval; discard or ignore (open question) | the next update |
| `REVERSAL` | a motor reversing its tracking direction crosses its gear backlash | yes | yes | yes: from 120 s before the turn to 0.2 deg past it (2026-10-11 SMC M2) | keep | as today |
| `SLACK` | a motor left uncompensated after a goto crosses its slack | yes | yes (2026-10-18 20:36: M2, 50'/h learnt) | yes (`crossing_slack`) | keep | engaged, ≤ 15 min |
| `SLIP` | M2 creeping ahead then slipping back 10-30" (heavy payload) | yes | yes | — (a large one is a `STEP`) | event: the slip signature on M2's 518 angle (`m2_slips`), live | 2 updates |
| `BLC` | Backlash Compensation acting (take-up push, hold) | yes | yes | — | event: `backlash.active` or a push | when BLC releases |
| `STALL` | corrections refer to a stale position: 518 data late, event loop lag, Wi-Fi gap | yes | yes | — | event: `age_518` > 1 s, event-loop lag warnings | 5 s after recovery |
| `NONSIDEREAL` | not sidereal tracking: orbital, Moon/Sun, custom rate | yes | yes | model reset at TrackOrbital (to check: pulses learnt while tracking an orbital?) | event: tracking rate ≠ sidereal | rate back to sidereal (then `ACQUIRE`) |
| `WORMTEST` | the worm profile test steps the motors | — | — | yes (PEC learning stopped) | keep | test ends |
| `JOG` | the user jogs or pans while tracking | yes | yes | reset (pan) | keep reset; jogs as `ACQUIRE` afterwards | as `ACQUIRE` |

**Resets** (not ignores, current): goto, pan, roll, tracking off, settings change, `reset_pec_model`. Proposed: each is
followed by `ACQUIRE`.

---

## Detection design

Three layers, applied per axis to y(t):

1. **Event gates** (R3). The driver's events start ignore cases directly: `ACQUIRE`, `CATCHUP`, `GAP`, `REVERSAL`,
   `SLACK`, `SLIP`, `BLC`, `STALL`, `NONSIDEREAL`, `WORMTEST`, `JOG`. Each has a minimum time; release also needs the
   burst test to report the axis settled. Cheap and exact, and they cover the cases seen so far that matter most.
2. **Signal tests** (R2, R4), all on rates scaled by the axis's own update interval:
   * **burst test**: the rate over a short window (3 updates or 30 s, whichever is longer) against the model's rate
     and its σ; one-sided and beyond kσ is `BURST`, and its "back within kσ" is the settled signal for every case that spans corrections;
   * **saturation** (PG): `SATURATED`;
   * **calibration**, per axis: `CALIBRATEPHD2`, `CALIBRATECCD`;
   * **step** and **outlier**, as rates: `STEP`, `OUTLIER`.
3. **Robust update** (R5). Before each update's observed rate enters the EMA it is clipped to the model's rate ± kσ
   (Huber-style). A missed case can then move the rate by at most kσ x α per update; a real change of drift still gets
   through over a few updates (R7).

**Rollback** (R6): each ignore case that is recognised late snapshots the model at its start (as the calibration
detector does today with `run_start`) and restores it when confirmed: `CATCHUP` from the first rejected pulse,
`BURST` from its first update, `CALIBRATE*` from the run's start.

**Logging** (R9): PECLOG `ignore` (replacing `paused`) carries the case name and, for mechanical cases, the motor
(`'REVERSAL:M2'`, `'SLACK:M3'`); `inhibit` per axis as today plus `MIN_SPAN` / `UNCERTAIN` / `STALE`. A
`->> Polaris: PEC drift ignoring corrections (CATCHUP)` / `... learning again` line at each change (today: `PEC drift
learning paused` / `resumed`). The notebook shades each case in section 3, reading `ignore` or, on older logs,
`paused`.

---

## Verification

### Data we have

* **76 archived sessions** (`utility/sessions.toml`): 45 sync guiding, 11 pulse guiding (PHD2), 12 both, 8 unguided.
  PECLOG on all of them; KFLOG/PIDLOG (`log_position`) on some (2026-10-20 the first with BLC state).
* **PHD2 guide logs** for most pulse-guided sessions (`load_phd2_guidelog`): calibrations, dithers, star lost, the
  guider's own error and pulses.
* **The mount-drift total is nearly independent of PEC**: y(t) includes what PEC applied, so the same drift is seen
  whatever PEC did. Gate designs can therefore be replayed open loop on the logged y(t) (`pe_analysis.replay_pec_rate`).
* **Ground truth** for replay: the centred ±5 min drift rate (`pe_analysis.true_rate`), with windows around known
  events left out.
* **Digital twin, closed loop**: `tests/sim_guider.py` — `SimGuider` (PG, PHD2-like: frame time, aggression, guide
  rate) and `SimPlateSolver` (SG: interval, solve noise), with drift and worm, already used by
  `tests/test_pec_twin_drift.py` and `test_pec_twin_worm_ff.py`. The only place the PEC-vs-guider fight itself shows.
* **Live**: `utility/replay/replay.py` replays a recorded request sequence against the driver on nina01.

### Plan

1. **Event catalogue** (read-only): from the archive, every instance of each ignore case — driver log lines (goto,
   tracking, rotate, `Cannot pulse guide`, BACKLASH, reversals, PECLOG `step`/`stale`, lag warnings, restarts), PHD2
   events (calibration, dither, star lost), `m2_slips`. Gives each case's frequency, a test set per case, and the
   clean stretches for measuring corrections ignored needlessly.
2. **Baseline score** of today's PEC on the catalogue: replay and score (below).
3. **Add the layers one at a time** (events, signal tests, robust update), each scored on the replay and given a twin
   scenario: guiding before tracking (`CATCHUP`), a PHD2 calibration (`CALIBRATEPHD2`), dithers every 2 min
   (`BURST`), star lost for 60 s (`GAP`), bad solves (`STEP`), an M2 slip (`SLIP`), a reversal (`REVERSAL`), a goto
   then sync guiding (`ACQUIRE`), and a genuine step change of drift (R7).
4. **Live check** on nina01 for the cases the twin can't model well (`CATCHUP` with PHD2, `SATURATED`).

### Scores and acceptance criteria (proposed)

* **Rate error after a case**: the learnt rate within 2"/min of the truth throughout and after each case instance.
* **No fight**: over any 10 min, the guider's and PEC's totals don't oppose each other by more than 30" (today's
  `PEC undone by guider %` in the notebook, windowed).
* **Needless ignores**: on clean stretches, ≤ 5% of learning time lost.
* **Real drift still learnt** (R7): a step change of drift reaches 63% of its new value within 1.5 τ (twin).
* **No regression**: on every session class, replay rate error rms no worse than today's.

---

## Evidence so far

* **2026-09-29** PHD2 calibration learnt as an RA drift of -785"/h, guiding then fought it at +363"/min →
  `CALIBRATEPHD2` (built).
* **2026-10-11** SMC: M2's reversal at 21:19, the guider's pull-back learnt as drift → `REVERSAL` (built).
* **2026-10-17 22:42** PHD2 stopped with the rate at -12.8"/min, applied for 12.6 min (-161" RA) → `STALE` (built);
  the restart after it → `GAP` (proposed).
* **2026-10-17 23:27** a +165" Dec sync then -185": +22"/min learnt → `STEP` (built).
* **2026-10-18 20:36** M2 at 0.24"/s crossing its 432" slack after a goto under 6 s syncs: 50'/h learnt, fought for
  30 min → `SLACK` (built).
* **2026-10-19 20:37-20:43** M3's reversal under PHD2 with BLC latched: 5-15" kicks at each push, Dec to 22" →
  `REVERSAL` ignored the corrections; BLC no longer compensates reversals (d9f53c5a).
* **2026-10-20 20:45** PHD2 guiding before tracking: 36 pulses rejected, then -37.5" Dec pulses every 3-5 s; VALID
  after 10 s at R² 1.0, -30"/min learnt, -165" applied by 20:58 while PHD2 pulsed from -239" back to +48" →
  `CATCHUP`, `SATURATED`, `MIN_SPAN` (proposed). The calibration detector missed the repeated pulses: RA pulses in
  between reset its run (→ per-axis runs).

---

## Open questions

* The burst test's window and k for sync guiding with long intervals (2-5 min): enough updates to judge?
* `SLIP` live: can the driver see a slip in time from the 518 angles alone (`m2_slips` works offline on PECLOG)?
* `NONSIDEREAL`: are pulses learnt while tracking an orbital today?
* Rollback depth: how far back can `CATCHUP` safely restore (the model before the rejected pulses may itself be from a
  previous target)?
* Should `ACQUIRE` also cover the first minutes after a driver restart with tracking restored?
* `OUTLIER`: discard (today) or ignore? Discarding a real correction leaves the total short by it from then on;
  ignoring keeps the total right but needs the threshold to be sure it isn't drift.
