# PEC in Motor (Theta) Space — Validation & Implementation Plan

Branch: `feature/pec_in_theta_space`

## Background

The current PEC model fits a periodic drift signal in equatorial space (RA/Dec), against a
fixed time period `pec_T_sec` (default 2040s/34min). That's the right frame for a classical
equatorial mount, where one worm gear drives RA at a constant ~15°/hr and periodic error is
naturally RA-only and time-periodic.

This driver runs an alt-az mount (Benro Polaris) with three motors (M1/M2/M3) whose individual
rotation rates vary continuously with orientation — there is no axis running at a constant rate
the way an equatorial RA axis does. RA/Dec tracking rate is a Jacobian-weighted blend of all
three motors, and that blend changes as the mount slews across the sky. Two things follow from
this, both backed by log evidence gathered during the investigation that produced this plan
(see `utility/analyse_pec.ipynb`'s "PEC Outcome Overview" and "Base vs Corrected Frame Shift"
sections):

1. **A model fitted in RA/Dec space is fitting an orientation-dependent re-mixing of whatever
   the real per-motor PE is**, not a fixed signal — so it has no reason to generalize from one
   orientation/session to the next, even if the underlying mechanical error is completely
   static. This plausibly explains the repeated "model regresses then recovers" pattern seen
   in multiple sessions' `resid`/`r2` traces.
2. **If M1/M2/M3 share the same motor/gearbox** (suspected, not yet confirmed), each axis's
   mechanical PE should be periodic in *accumulated motor rotation angle*, not in time — a
   time-based period is only a valid proxy for that when the axis's own rotation rate is
   constant, which it isn't here.

The KFLOG "Base vs Corrected Frame Shift" diagnostic (`θ_meas_raw − θ_ref_raw` per axis) also
showed M1/M3 with a clear sawtooth/sine signature and M2 essentially flat — consistent with
M1/M3 carrying real periodic mechanical error and M2 not (or much less).

**Hypothesis under test:** fitting a periodic model per motor axis, in the motor's own
angle-domain, will (a) converge to a *consistent* period across axes and sessions where
RA/Dec-space fitting does not, and (b) produce lower steady-state guiding residual than the
current RA/Dec model, without regressing sessions where the current model already does well.

**Ground rule for this whole plan:** PEC corrections are small enough that visual inspection of
a chart is not sufficient evidence of anything. Every phase below ends in a specific number or
a pass/fail against a threshold, not "looks better."

---

## Phase 0 — Offline validation against existing log data (no driver changes)

Goal: decide, before writing any driver code, whether the hypothesis actually holds up
quantitatively against real logs. This is a hard gate — if Phase 0 doesn't show a real signal,
stop and reconsider before investing in Phase 1+.

### 0.0 Log inventory (done — findings below; re-run after any new capture)

Scanned all 69 `alpaca*.log*` files under `logs/` and `logs/logs/`. Findings:

- **Every log ≥9h duration uses the old, pre-dict `PECLOG` format** (`n,2,TOO_FEW_OBS,...`,
  comma-separated) — `analyse_helpers.parse_payload_line`/`load_pec` only handle the current
  `PECLOG {...}` dict format and silently find nothing in these. **A legacy-format PECLOG
  parser is a hard prerequisite** before any of the long sessions (which is most of the useful
  duration we have) can be used for Phase 0.1–0.3.
- **No log has "sync-guiding active, PEC completely off."** Searched all 69 files for
  `SYNC GUIDING` present with zero `PECLOG` lines of either format — none found. Every capture
  with sync-guiding on also had `advanced_pec` on. Two ways to get an uncontaminated-by-PEC
  signal without a fresh capture: use the pre-convergence portion of existing sessions
  (`inhibit != VALID` / `pec_active: False` rows — `apply_pec_drift_correction()` returns
  immediately while `_pec_active` is false, so these cycles have zero PEC feed-forward applied,
  genuinely uncorrected), or capture a new log with `advanced_pec` explicitly off. Prefer doing
  both — the pre-convergence data is free and available now, but is only ever a few minutes per
  session, so it won't carry the angle-domain periodogram (0.2) on its own.
- **Long files are not clean single-target sessions** — most have real gotos/tracking toggles
  scattered through them (checked against the actual REST calls: `slewtocoordinatesasync`,
  `slewtoaltazasync`, `tracking`, `findhome`, etc., not just PECLOG content). They do contain
  long clean (no-slew) stretches worth extracting:

  | File | Raw span | Longest clean (no-slew) stretch | Actual continuous PECLOG activity span |
  |---|---|---|---|
  | `alpaca.jdm_Beta3.1_08_02.log` | 15.11h | ~6.6h (12:43→19:20) | **11.19h** (08:09→19:21), one 44min gap, 878 entries, ~40s cadence |
  | `alpaca.jdm_Beta3.1_08_03.log` | 13.54h | — | 9.76h (09:34→19:20), one 136min gap, 693 entries |
  | `alpaca.pec_rls_Beta2.0_07_25_tarantula1.log` / `1b.log` | 10.50h | two ~2.5–2.75h chunks | 6.50h (12:55→19:25), 361 entries |
  | `alpaca.pec_rls_Beta2.0_07_20_master.log` / `_h2.log` | 12.31h | ~5.0h (11:49→16:50) | 4.64h / 5.47h — the two files end at the identical timestamp (16:28:40.972), confirming they're the same underlying capture exported/filtered two ways |
  | `alpaca.pec_rls_Beta3,9_07_29_7hrs.log` | 13.54h | — | only 3.39h despite the filename |
  | ~~`alpaca.pec_rls_Beta2.0_07_22_syncguide2.log`~~ | ~~9.29h~~ | ~~8.3h~~ | **Ruled out** — checking actual PECLOG timestamps (not just REST-command gaps) shows all 187 entries land in a 2-minute window (06:54:17→06:56:09), `n` racing 2→23, one `Guide,+nan` value in there — a rapid-fire test burst, not a real session. The rest of the file's 9.29h span has no PEC/sync-guide activity at all. |

  **`alpaca.jdm_Beta3.1_08_02.log` is now the strong candidate for the "~11 hour" session** —
  11.19 continuous hours of real PECLOG activity, essentially uninterrupted (one 44-minute gap),
  matching the recollection closely. Worth confirming against notes, but proceeding on this one
  unless something rules it out.

- **Action items before 0.1 can proceed on the long logs:**
  - (a) ✅ **Done.** `analyse_helpers.py` now has `parse_peclog_legacy()` (comma-format PECLOG,
    consistent field layout confirmed across every old-format log in this project) and
    `parse_sync_guiding_residual_line()` (recovers `resid` — absent from the legacy PECLOG
    payload itself — from the always-present `SYNC GUIDING ... Residuals` line via the DMS
    inverse of `shr.py`'s `deg2dms()`). `load_pec()` auto-detects format per line and backfills
    `resid_1`/`resid_2` for legacy rows by nearest-timestamp merge (2s tolerance), so it now
    handles a session that mixes both formats too. Validated against real logs, not just
    compiled: `chicken.log` (131/131 rows, resid cross-checked against the driver's own
    independently-logged `pec_accum` for a fresh/unsmoothed cycle — matched to 3 decimal
    places) and `alpaca.jdm_Beta3.1_08_02.log` (878/878 rows, 0 NaN resid, zero regression on
    the existing dict-format path or the rest of `analyse_pec.ipynb`'s Outcome Overview cell,
    which ran unchanged against the legacy file end-to-end).
  - (b) **Leading candidate for the ~11h session confirmed as `alpaca.jdm_Beta3.1_08_02.log`**
    (11.19h continuous PECLOG activity, one 44min gap) — still worth a sanity check against
    notes, but nothing found to rule it out.
  - (c) ✅ **Done.** `find_tracking_segments()` in `analyse_helpers.py` — splits a log into
    continuous-tracking segments at any slew/goto/tracking-toggle/park/findhome/abortslew REST
    call, returns `(start_ts, end_ts, duration_min)` for segments over a minimum length.
    Validated against the manually-checked segments above (reproduces them exactly, e.g.
    `08_02.log`'s 6.62h segment). **Caveat found while validating**: this only looks at REST
    boundaries, not whether PECLOG/tracking was actually active throughout — e.g. `08_02.log`'s
    trailing 3.62h segment is almost certainly idle/parked time (its start lines up with
    PECLOG's very last entry). Segments must be intersected with actual PECLOG timestamp
    coverage before use in 0.1/0.2, not taken at face value. For the leading candidate this
    already looks fine — its best segment (12:43→19:20, 6.62h) sits entirely inside its
    continuous 08:09→19:21 PECLOG-activity window — but this intersection should be made
    explicit in code (not just eyeballed per-file) before it's relied on generally.

### 0.1 Derive per-motor "observed theta" ground truth from existing PECLOG data ✅ Done

**Revised from the original plan**: doesn't depend on KFLOG (`θ_meas_raw`) at all, which turned
out to matter — neither `08_02.log` nor `syncguide1.log` has any KFLOG data, and long real
imaging sessions with `Config.log_position` on appear to be the exception, not the rule, in
this project's logs. Instead, `derive_theta_ground_truth(df, lat_deg, lon_deg)` in
`analyse_helpers.py` works entirely from PECLOG's own fields plus site location:

1. `predicted_ra/dec` = this row's `az`/`alt`/`roll` (the PID's PV) → ra/dec, via
   `kinematics.azalt_to_radec()` (exact `ephem`-based conversion, the same the driver itself
   uses — better than the parallactic-angle small-rotation approximation originally
   considered, and avoids needing `alignQ_B2T`, which isn't recoverable from the logs at all).
2. `observed_ra/dec` = `predicted_ra/dec` + `resid` (confirmed: `resid_1`/`resid_2` are exactly
   `process_guide_sync()`'s `ra_resid`/`dec_resid`, in arcmin of degrees — `/60` recovers
   degrees directly, no unit surprises).
3. `observed_az/alt` = `observed_ra/dec` → az/alt, via `kinematics.radec_to_altaz()`.
4. `theta_pred`/`theta_obs` = `azaltroll_to_theta(az, alt, roll)` for each pose (roll held
   fixed — a small RA/Dec offset doesn't meaningfully change field rotation).

Also needed **site latitude/longitude**, which isn't computable from anything in the plan —
resolved by finding it's actually logged, just not where first searched: a startup
`Site lat = ... | lon = ...` line, present in 31/69 of this project's logs (including both
files used to validate this). `find_site_location()` recovers it per-file (so a different
site/user is handled automatically, not a global constant).

**Two real bugs found and fixed while validating against `08_02.log` and `syncguide1.log`, not
just by reading the kinematics code:**
- `kinematics.azaltroll_to_theta()` called without an explicit `lastPos` silently returns
  `(None, None, None)` for *every* row — its own default argument passes a literal `None`
  through to `q_to_theta()`, which then fails internally and gets swallowed by the wrapper's
  `except Exception`. Fixed by carrying one `LastPosition` across all rows (mirroring the
  driver's own persistent `self._pid._lp`), advanced by `theta_pred` only after both
  `theta_pred`/`theta_obs` are computed against it each row.
- Near `kinematics.py`'s own `THETA2_MAX = 81.5` mechanical near-singularity, the IK's branch
  selection can differ between the predicted and observed pose even though the true
  positional difference is tiny — produced outliers up to ~345° before this was caught.
  `derive_theta_ground_truth()` now excludes rows with `theta_pred_2`/`theta_obs_2` above 80°
  (default, overridable), confirmed against both files: every extreme outlier found while
  debugging clustered at `theta_pred_2` ≈ 81.49–81.52°, none survived the exclusion, and the
  remaining largest residuals (a few hundred arcsec) show no such clustering — they range
  across alt 34–77°, look like genuine amplified signal rather than a numerical artifact.

Also fixed in passing: `load_pec`/`load_kf_pid`/`find_tracking_segments`/`find_site_location`
now open files with `errors="replace"`, not just `encoding="utf-8"` — `syncguide1.log` has a
genuinely non-UTF-8 byte in it (a `°` written as Latin-1 somewhere), which previously aborted
parsing the whole file.

Not yet done: cross-checking `theta_resid_i` against an independent source for a handful of
points (KFLOG isn't available on these two files to do this the original way) — worth a
lighter sanity pass (e.g. first-sync-of-session values should be small) before leaning on this
heavily in 0.2.

### 0.2 Angle-domain vs time-domain periodogram, per motor, per session

For each existing PEC session log with enough duration/samples: compute each motor's own
cumulative rotation angle θᵢ(t) from KFLOG, and run a periodogram of `theta_resid_i` (or of the
higher-rate `θ_meas_raw − θ_ref_raw`, with sync-guide correction events excised — see the
contamination note in the investigation history) in **both** domains:

- Time domain (current approach): periodogram of the residual vs elapsed time.
- Angle domain (new): resample/reparametrize the residual by θᵢ instead of t, periodogram vs
  angle.

**Pass criterion for the hypothesis:** the angle-domain period for a given motor should be
consistent (within some tolerance, e.g. ±10%) across sessions/orientations where the *time*
period is not, and — if the shared-motor suspicion is right — M1 and M3 (at minimum) should
converge to a *similar* angular period as each other. Record whatever M2 shows too; a flat/no
strong periodicity result for M2 is itself informative, matching the KFLOG shift chart.

This is the single most important check in the whole plan — it's cheap (pure offline analysis,
data already on disk), falsifiable, and directly tests the core hypothesis before any driver
code is written.

### 0.3 Fit quality / generalization comparison: per-motor vs RA/Dec

Using the same log set:

- Fit a candidate per-motor angle-domain model (constant + harmonics, same RLS/EMA machinery
  conceptually) on one session, and check its **predictive** residual on a *different* session
  (different orientation/target). Do the same for the existing RA/Dec model as the baseline.
- **Pass criterion:** per-motor model's held-out residual RMS should be lower than the RA/Dec
  model's held-out residual RMS, on a majority of held-out session pairs tried — the RA/Dec
  model is expected to generalize poorly across orientation by the hypothesis above, so this is
  the head-to-head test of whether that's actually true.

### 0.4 Decision point

Write up Phase 0's numeric results (angular-period consistency, cross-session generalization
comparison) before moving to Phase 1. This is a go/no-go gate, not a formality — if the
angle-domain period isn't consistent across sessions/axes, the core hypothesis is wrong or
needs revising before any driver work starts.

---

## Phase 1 — Driver design (theta-space PEC model + PV/FF integration)

Only start once Phase 0 passes.

### 1.1 Model math

Re-derive (or extend) the `PecAxis`-equivalent to fit against θᵢ mod Θᵢ instead of t mod T.
Feed-forward needs a *time-domain rate*, so the conversion is the chain rule:
`rate_correction(t) = f'(θᵢ) · ωᵢ(t)`, where `ωᵢ(t)` is the motor's current angular velocity
(already available). Confirm this doesn't reintroduce instability at low/zero `ωᵢ` (e.g. mount
briefly stationary) — `f'(θᵢ) · ωᵢ` correctly goes to zero there, but worth an explicit unit
test (see Phase 2).

### 1.2 Ground-truth signal, live in the driver

Reuse `process_guide_sync()`'s existing `ra_resid`/`dec_resid` computation, and add the
theta-space conversion (same forward-kinematics chain as Phase 0.1) computed live, keyed to
the raw `θ_meas` at that same instant. Log it (new fields, e.g. `PECLOG`'s existing per-axis
convention extended to 3 motors, or a new tag) so the *same* notebook tooling built in Phase 0
can analyze live driver output without rework.

### 1.3 PV/FF hookup

From the earlier investigation:

- **FF** is simpler with a per-motor model: `omega_pec_B = [d_theta1, d_theta2, d_theta3] / dt`
  directly — no `equatorial_axes_B` projection needed at all.
- **PV**: inject the per-motor correction *before* `motorQ_state = theta_to_q(*self._theta_state)`
  in `polaris.py`, not as a patch to `theta_pv` after the fact — so `cameraQ_pv` and everything
  downstream of it (Az/Alt/RA/Dec reporting, UI) stay consistent with what the PID's error
  signal sees. Confirm nothing else reads `self._theta_state` between the KF and that point
  expecting the uncorrected physical estimate, before finalizing this injection point.

### 1.4 Feature flag

New theta-space model sits behind a config flag (e.g. `Config.pec_theta_space`), default off.
The existing RA/Dec-space path stays completely untouched and remains the default — this is
what makes "no regression" checkable at all: anyone not opting in sees zero behavior change.

### 1.5 Logging compatibility

Confirm new log fields don't break existing notebook parsing — `parse_payload_line`'s
list-flattening is generic, so this should be forward-compatible automatically, but verify by
running the existing `analyse_pec.ipynb`/`analyse_kf_pid.ipynb` against a log produced with the
new fields present.

---

## Phase 2 — Unit tests

- Angle-domain model fitting: synthetic θᵢ(t) with a known injected periodic signal (including
  a case where `ωᵢ(t)` varies over the test, unlike a constant-rate equatorial test would need)
  — verify the fit recovers the known period/amplitude/phase, and that the FF rate conversion
  (`f'(θᵢ)·ωᵢ`) matches a numerically-differentiated reference.
- Theta-space ground-truth derivation (Phase 1.2): unit test against known az/alt/roll + residual
  inputs with a hand-computed expected `theta_observed`.
- PV/FF injection: verify the new theta-space path, with the feature flag off, produces
  byte-for-byte identical `theta_pv`/`omega_pec_B` behavior to the current code — this is the
  regression-safety test for anyone not opting in.
- Edge cases: zero/near-zero `ωᵢ`, PEC model reset mid-session, axis with no detectable
  periodicity (should behave gracefully, not force-fit noise).

---

## Phase 3 — Desk testing via `replay.py`

**Important scoping correction from the initial read of `replay.py`/its README:** it does not
simulate motor-level telemetry. `SYNCGUIDE_PE`/`PULSEGUIDE_PE` only fake the *guide correction
input* (a synthetic RA/Dec offset sent via `synctocoordinates`/`pulseguide`) against a real,
physically-tracking bench mount — the mount's actual motors and their actual mechanical PE (if
any) are real, not simulated. So:

### 3.1 What's testable with existing `replay.py`, no new tooling

- Run the existing `SYNCGUIDE_PE`/`PULSEGUIDE_PE` test files against a bench-connected mount
  with the new theta-space model active (flag on) vs the current default (flag off), same
  target, back-to-back or alternating runs. This validates the *control loop* end-to-end (PV/FF
  hookup, logging, no crashes/instability) and gives a real — if not perfectly known-ground-truth
  — A/B comparison, since the bench mount's own real per-motor PE (whatever it is) is being
  fitted in both cases.
- Compare resulting `resid`/theta-space-resid RMS trend between the two runs using the Phase 0
  analysis tooling, extended to read the new log fields.

### 3.2 Open question: controlled, known-ground-truth per-motor PE injection

To get the stronger guarantee ("does the model recover the *exact* true PE") would need
injecting a known synthetic disturbance at the raw-telemetry level, below the ASCOM API
`replay.py` currently operates at. This is a real gap, not yet resolved — options to evaluate:
a lower-level simulator/mock Polaris connection (if one exists or is worth building), or
accepting 3.1's real-bench-mount comparison as sufficient for this change and deferring a full
telemetry-level simulator as separate future work. Decide this explicitly before Phase 3 starts,
rather than discovering it mid-implementation.

---

## Phase 4 — Quantitative acceptance criteria (fix these before running Phase 3/5, not after)

- **Phase 0 gate:** angular period consistency across sessions/axes (0.2) and better held-out
  generalization than RA/Dec (0.3), both demonstrated with numbers, before Phase 1 starts.
- **Phase 3 (bench) gate:** theta-space model's resid RMS (first-fifth vs last-fifth of run, same
  metric already used in `analyse_pec.ipynb`'s Outcome Overview) must not be worse than the
  current model's on the same bench mount/target, and should show measurable improvement on
  repeated runs (not a single lucky run).
- **No-regression gate:** with the feature flag off, unit tests (2) must show byte-identical
  behavior to current code.
- **Field gate (Phase 5):** resid RMS trend and KFLOG base-vs-corrected shift amplitude (per
  motor) should be comparable-or-better than historical RA/Dec-mode sessions on similar
  targets — ideally an explicit same-night or same-target A/B, given night-to-night seeing/wind
  variability makes single-session comparisons noisy on their own.

---

## Phase 5 — Live field validation

- A/B protocol: same night (or closely matched nights/targets) run old mode then new mode (or
  alternate), via the `Config` flag, both `log_pec` and `log_position` on for full telemetry.
- **Strongly consider logging both models' residuals simultaneously** even when only one mode's
  correction is actually applied — i.e. keep a "shadow" RA/Dec model fitting (not driving
  anything) running alongside the live theta-space model, and vice versa on old-mode nights.
  This turns every single session into its own A/B comparison instead of needing two separate
  nights with matched conditions, which removes most of the night-to-night noise problem from
  Phase 4's field gate. Worth deciding whether this is in scope for Phase 1 or deferred.
- Repeat over multiple nights/targets before drawing a conclusion — a single night, however
  good, isn't statistically conclusive given natural seeing/wind variability.
- Reuse the exact same notebook metrics from Phase 0 throughout, so every phase of this project
  is judged by the same yardstick.

---

## Open questions to resolve early (don't let these surface mid-implementation)

1. Confirm/refute "M1/M3 same motor+gearbox, M2 different" — Phase 0.2 answers this directly.
2. Decide the Phase 3.2 ground-truth-injection gap before committing to a bench-test-only
   validation story.
3. Decide whether "shadow" dual-model logging (Phase 5) is worth the extra complexity in Phase 1,
   given how much it strengthens field validation.
4. Confirm the exact safe injection point for the PV correction (Phase 1.3) by tracing all
   readers of `self._theta_state` between the KF and `theta_to_q(*self._theta_state)`.
