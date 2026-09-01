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

### 0.2 Angle-domain vs time-domain periodogram, per motor, per session — 🟡 In progress, promising but not conclusive yet

**Revised from the original plan**: runs on `theta_resid_i` from 0.1's PECLOG-only derivation
(no KFLOG needed, since neither of our two files has any), using `lombscargle_periodogram()`
(new, in `analyse_helpers.py`) rather than `scipy.signal.periodogram` — PECLOG's guide-sync
cadence is irregular, which a standard FFT-based periodogram assumes away.

**Two real methodological bugs found and fixed by testing against real data before trusting
any result, not by inspecting the numbers once and moving on:**

- **No detrending, at first.** The very first real-data run showed power rising monotonically
  all the way to `max_period` (the search cap, `span/2`) with no local peak at all, for every
  motor/segment tried — a textbook slow-trend signature. Confirmed synthetically: adding a
  linear trend to a clean known-period test signal reproduced the exact same failure (spurious
  peak at the range edge, weak power) until `lombscargle_periodogram()` was given a
  `detrend=True` default (matching `analyse_pec.ipynb`'s own existing periodogram cells).
- **Raw peak power isn't comparable across different sample sizes.** Even after detrending,
  results kept landing near suspiciously round cycle-counts across unrelated
  motors/segments — a known small-sample periodogram bias (a long period has more freedom to
  fit noise relative to how few independent cycles are actually observed). Fixed by adding
  `periodogram_false_alarm_probability()` — a permutation test (shuffle `y`, x held fixed,
  see how often noise alone beats the real peak) — validated against synthetic clean-signal
  (FAP=0.000) and pure-noise (FAP=0.520, i.e. "not significant," exactly as it should be)
  cases before trusting it on real data.

**Results so far, with FAP (lower = more trustworthy):**

| File | Segment | n | Motor | Peak period | Power | FAP |
|---|---|---|---|---|---|---|
| `08_02.log` | 12:43→19:20 (6.62h) | 567 | M1 | 45.55° | 0.083 | **0.000** |
| `08_02.log` | 12:43→19:20 (6.62h) | 567 | M2 | 13.47° | 0.206 | **0.000** |
| `08_02.log` | 12:43→19:20 (6.62h) | 567 | M3 | 34.63° | 0.150 | **0.000** |
| `08_02.log` | 09:29→12:32 (3.03h) | 84 | M1/M2/M3 | — | — | 0.29–0.83 (not significant — too few points) |
| `syncguide1.log` | 08:09→09:10 (1.0h) | 45 | M1 | 6.66° | 0.496 | **0.000** |
| `syncguide1.log` | 08:09→09:10 (1.0h) | 45 | M3 | 7.16° | 0.411 | **0.000** |
| `syncguide1.log` | 08:09→09:10 (1.0h) | 45 | M2 | 0.57° | 0.301 | 0.005 (borderline) |
| `syncguide1.log` | 09:25→11:43 (2.3h) | 51 | all | — | — | 0.04–0.96 (not significant) |

`08_02.log`'s best segment gives a statistically significant angle-domain period for **all
three motors** — a real finding worth having, on its own. `syncguide1.log`'s 1-hour segment
also finds a significant (M1/M3) short-period signal, but **this is not a genuine
cross-session disagreement**: that segment's angular span is only 15.9°/14.3° (M1/M3), capping
its searchable period range at 7.95°/7.16° — it is *structurally incapable* of finding `08_02`'s
45.5°/34.6° periods at all, so the two results aren't comparable and this pairing can't confirm
or refute cross-session consistency either way. Checked this explicitly before writing it up as
a finding, rather than reporting the raw numbers as a disagreement.

**Update: ran the same analysis across 4 more sessions/nights (`tarantula1`, `07_20`
[`master.log`/`h2.log` confirmed identical — same underlying capture], `08_03`), filtered to
only compare findings whose testable range (`span/2`) actually covers the peak being compared
against (avoids the exact `syncguide1`-vs-`08_02` mistake above). Sorting all FAP<0.05 results
by peak period reveals a real cross-session pattern:**

- **M1**: three *independent, mutually-testable* sessions across two different nights (July 22
  `syncguide1`, July 25 `tarantula1`'s two segments) all land at **6.44°–7.40°** — a tight
  cluster given these are independent noisy estimates, and none of them are anywhere near
  their own testable-range ceiling (7.95°/18.26°/30.61° vs peaks of 6.66°/7.40°/6.44° — not an
  edge artifact this time). `08_02`'s headline 45.55° doesn't match this directly, **but its
  own periodogram's second-strongest local peak, checked explicitly, is at 7.130°** (power
  0.064, vs 0.083 for the 45.55° global max) — the ~7° signal is present in that session too,
  just outcompeted by something stronger, not absent.
- **M3**: four sessions cluster at **4.99°–7.16°** (`08_03`, `07_20`, `tarantula1`, and
  `syncguide1` again, the last right at its own testable ceiling so weaker evidence on its
  own). `08_02`'s M3 periodogram, checked the same way as M1's, does **not** show a
  corresponding secondary peak near 5–7° (its top three local peaks are 34.63°/23.65°/10.28°)
  — a genuine gap in the corroboration, not glossed over.
- **M2** stays scattered (0.57°, 0.78°, 5.94°, 13.47° — no cluster), consistent with the
  earlier KFLOG shift finding that M2 looks mechanically different from M1/M3.

**Read on this at the time:** M1 and M3 both show a period in roughly the same 5–7.5° range,
found independently across four sessions spanning three different nights, with testable ranges
that genuinely cover it. Ratio check on `08_02`'s two dominant (not the ~6-7°) peaks: M1=45.55°
vs M3=34.63° are 27.2% apart, not a close match, and not a clean small-integer ratio either
(nearest 4/3, 1.3% off — too loose to read into).

### ⚠️ Correction: the above used the wrong signal — resid is PEC-contaminated

Caught by a direct question ("did you remove any effect of PEC from the logs?") that turned
out to matter a lot. Checked: `inhibit_1` was `VALID` (PEC actively correcting, real per-cycle
corrections up to 7.2 arcmin) for 542/567 rows (95.6%) of `08_02`'s segment. `theta_pred`/
`theta_resid` above are built from PECLOG's `az`/`alt`/`roll`, which is the PID's *already
PEC-corrected* present value (it flows through `q_syncguide_B`) — so `theta_resid` measures
whatever error is left over **after** PEC's current RA/Dec-space correction, not the raw
mechanical periodic error. Everything in the table above is potentially contaminated by
however well or badly the *current, RA/Dec-space* model happens to be doing.

**Fix**: `total_accum` is the field the driver's own code deliberately keeps free of this
("the fit's training signal; deliberately doesn't shrink as PEC improves" — `_pec_log()`'s own
docstring) — it's also exactly what `analyse_pec.ipynb`'s existing "Right Ascension/Declination
Period" cells already periodogram, for the same reason, just in RA/Dec instead of theta-space.
Added `derive_theta_from_total_accum()`, reconstructing a PEC-independent theta trajectory by
anchoring each PEC-model segment's start position and adding `total_accum`'s RA/Dec drift onto
it, run through the same kinematics chain.

**Re-ran everything with the corrected signal — and it exposed a second, more fundamental
problem, not just a domain question.** Pairing `theta_pred` (x) against the new `theta_true`
(y) directly doesn't work: they correlate at 1.0000 (PEC's correction is tiny — arcmin-scale —
against ~100° of real tracking motion), so `lombscargle_periodogram`'s internal linear detrend
strips out nearly everything, and the tiny leftover reproduced the exact edge-of-range bias
already fixed once before. Fixed properly by detrending `theta_true` against **time** first
(matching the existing RA/Dec cells' own convention) before pairing with `theta_pred` — this
dropped their correlation to ~0.07–0.09 for M1/M3 (0.76 for M2, still elevated).

That fix did *not* recover a clean result, though — quite the opposite. Recomputing peak/
testable_max ratios across every session/motor: **old (resid-based) mean ratio 0.58, spread
0.20–1.00** (genuinely varied, several well clear of the edge) vs **new (total_accum-based,
time-detrended) mean ratio 0.90**, almost every single result between 0.67–1.00. Tried
higher-order (quadratic, cubic, quintic) detrending against time to see if it was just
under-fit curvature — made it *worse*: peaks stayed pinned near the edge while `wobble_std`
collapsed from 7555→169 arcsec (degree 5), a clear overfitting signature, not a fix.

**Conclusion: `total_accum`'s residual, even properly detrended, is dominated by non-periodic
structure — real secular drift curvature and/or one-off disturbances (the kind found earlier
in this investigation, e.g. the RA-specific dip in `08_29m.log`) — that overwhelms any genuine
short-period signal at these segment durations.** This is not a time-vs-angle domain question
any more; it's a data-sufficiency problem that affects both domains equally. The earlier ~6-7°
cross-session cluster should be treated as a weaker, not-yet-validated hint rather than the
promising finding it was reported as — it came from the contaminated signal, and the properly
corrected one isn't yet clean enough at these durations to confirm or refute it either way.

**This raises the bar for Phase 0.2, and for tonight's planned capture** (see below): what's
needed isn't just "comparable angular coverage to `08_02`," it's enough continuous duration for
`total_accum`'s non-periodic secular component to be small relative to many repeats of
whatever the true periodic component is — likely several times longer than anything captured
so far, on a single uninterrupted target.

**Pass criterion for the hypothesis (unchanged):** the angle-domain period for a given motor
should be consistent (within some tolerance, e.g. ±10%) across sessions/orientations with
*comparable angular coverage* where the *time* period is not, and — if the shared-motor
suspicion is right — M1 and M3 should converge to a similar angular period as each other.
**Provisionally met for the ~6-7° signal** (M1 cluster tight and clean; M3 cluster present but
`08_02` doesn't corroborate it internally) — promising enough to justify continuing, not yet
strong enough to call confirmed. Next useful step: find or capture a session with `08_02`-scale
angular coverage (several hours, ~100°) on a *different* night, to see whether a long session
can be found where ~6-7° is the dominant peak rather than 08_02's odd-one-out ~35-45° result,
which would settle whether that's session-specific noise or a second real component.

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

---

## Log inventory update (logs2 import)

Scanned a new `logs/logs2` drop (81 files across a top level plus 4 subdirectories with
generic `alpaca.log.N` names). Most duplicated existing content exactly (same basename, same
byte size — confirmed via full comparison, not assumed). Moved only the genuinely new,
PECLOG-qualifying files/directories into `logs/logs` (not copied — originals no longer in
logs2): `alpaca.greg_Beta3_08_02.log`, `alpaca.log.1/.2/.3` (no collision with anything
existing under those names), and whole subdirectories `vlogs/`, `Logs AutotuneMAC/`,
`Logs10-Jun-2026_PEC/`, plus `logs/` renamed to `logs2_logs/` to avoid a confusing
`logs/logs/logs/` nesting. Notable find: `vlogs/alpaca.log.4`, 3246 legacy-format PECLOG
entries — but only 2.13h span / 1.16h continuous segment, and **from a different site**
(43.75°N, 6.92°E — northern hemisphere, matching the earlier "first time on a northern target"
context) — `find_site_location()` picked this up correctly per-file, no manual handling
needed. Re-scanned the full expanded set for continuous PECLOG duration: `08_02.log`'s 11.19h
remains the longest available by a wide margin; nothing in the new import beats it.

## Recommended target for tonight's confirmation capture

Simulated candidate starting Az/Alt across a grid, holding RA/Dec fixed (pure sidereal
tracking, no PEC) and running the real kinematics chain (`azalt_to_radec` → track forward →
`radec_to_altaz` → `calc_parallactic_angle` for roll → `azaltroll_to_theta`) forward several
hours, maximizing M1+M3 total angular travel subject to keeping `theta_pred_2` (M2) below 79°
(clear of the confirmed `THETA2_MAX=81.5` near-singularity) and altitude above 10°.

**Best found: start at Az=176°, Alt=35°** (a target deep in the south circumpolar region for
this site, ~Dec=-86.6° at the reference time used — in practice just slew to this Az/Alt at
tonight's actual start time, no need to match a specific star or date). Mechanism: this close
to the pole, Az/Alt barely change over the session, but **roll has to sweep hard** (+69° to
-85° over the simulated 9h) to compensate for the fast-changing parallactic angle near a pole —
and that roll sweep, not Az/Alt translation, is what drives large M1/M3 motion, so alt (and
hence M2) stays comfortably moderate (~35-74°) for most of the session instead of climbing
toward the ceiling the way a more conventional near-zenith target would.

Simulated over a 9-hour window from this start: **M1 travels 147.9° (vs 101° in `08_02.log`'s
real 6.62h segment), M3 travels 106.5° (vs 83.8°)**, both comfortably better than anything
captured so far, with M2 staying in [37.2°, 73.9°] throughout — safely clear of the boundary.
At 9.5h, M2 reaches 79.97° (borderline); at 10h, 83° (past the safe margin) — so **~9 hours
continuous is the recommended session length** from this start.

Caveats: roll sign/convention here uses `-calc_parallactic_angle()`, matching the convention
used elsewhere in this investigation but not independently re-verified against the driver's
own live roll-tracking code path; mechanical corrections (MAC) and QUEST alignment aren't
included (both are normally small perturbations, shouldn't change the big picture, but haven't
been checked). Keep sidereal tracking + field derotation on throughout, avoid any
goto/jog/tracking-toggle for the full session (see `find_tracking_segments()` — a single
interruption would split this into separate, shorter segments for analysis purposes).

**Confirmed for tonight**: starting at Az=176°, Alt=35°, Roll=+60° (close to the simulated
t=0 roll of ~69° — small offset shouldn't matter, roll evolves via normal field-derotation
tracking from there, not fixed).

**Superseded** — Dec=-86.6° (the original recommendation above) is only ~3.4° from the SCP,
correctly flagged as unrealistic (essentially no real targets there, unusual mechanically).
Redone anchored on 47 Tucanae (NGC 104, RA=00h24m05.67s, Dec=-72°04'52.6" — still circumpolar
from this site, circumpolar limit is Dec ≤ -56.3° at lat=-33.655°), searching over start
time/hour-angle instead of free Dec:

**Start when 47 Tuc is at Az≈159°, Alt≈41°, Roll≈+73°** — ~4h before it transits due south
(transit: Az=180°, Alt=51.7°, the session's highest point). Since the simulation's reference
date (2026-08-31) is today, this converts directly to a real clock time: ≈9:40 PM AEST
tonight (Sydney, UTC+10, no DST until October) — not independently verified beyond the
`ephem` calculation itself, worth a sanity check against a planetarium app before committing.
Track 8 hours through transit and beyond, naturally symmetric around it.

Simulated: **M1 travels 115.4°, M3 travels 95.5°** (both better than `08_02.log`'s real
101°/83.8°), M2 in [51.7°, 77.9°] — but M2 starts at 77.4° already close to the 81.5°
boundary and climbs back to 76.9° by hour 8, so *both* ends of the session are somewhat close
to the ceiling, not just one — starting a bit later (closer to transit) trades span for more
margin if wanted.

---

## Historical RLS/EMA context (from the user, confirms the code-level analysis above)

"RLS with no harmonics" (`n_harmonics=0`, pure `a*t` linear fit) is "our old non-harmonic
correction" — confirmed: it didn't handle the trend flattening, exactly as the code structure
predicts (a single constant-rate parameter can't represent a rate that changes shape over
time). RLS with 2 harmonics (current default) wasn't satisfying either. EMA was tried and
gave "quite poor" results in practice, abandoned — "maybe prematurely." This matches the
mechanism found by reading `_update_ema()`: EMA smooths the *raw combined* observed rate with
no periodic/secular separation at all, so it's structurally unable to tell a genuine secular
stop from the periodic component's own rate crossing zero — a real, expected failure mode, not
just a tuning problem. This is independent supporting evidence for the decoupled-adaptation-
rate design direction proposed above (give the secular/trend term its own process-noise rate,
separate from the harmonics, rather than either a single shared RLS λ or EMA's total
conflation) — EMA's failure doesn't rule out a Kalman-style local-linear-trend + harmonics
model; it's closer to a data point for *why* that decoupling matters.

## Additional data point: `alpaca.pec_rls_Alpha_06_03_pulseguide_pec.log`

User-flagged: multiple PEC restarts (11 `n`-resets found), and "very clear periodic
behaviour." Investigated the largest clean segment (rows 249:8727, n=8478, 98.5min,
~0.7s cadence — over 10x denser than any sync-guide session analyzed so far). Confirmed
directly from the raw data: Dec's `total_accum` climbs almost monotonically (0→70.7 arcmin
over 98.5min, ~43 arcmin/hr) — a strong secular drift, visually obvious even without a
periodogram. RA's `total_accum` shows genuine wave-like oscillation on top. Both signatures
the user described, in the same dataset.

Time-domain periodogram of raw `total_accum` (matching the notebook's existing RA/Dec period
cells) gives, for the first time in this investigation, a **clean, single, dominant,
highly-significant peak with no competing secondary peaks**: RA period=31.47min (power=0.758,
FAP=0.000), Dec period=44.61min (power=0.660, FAP=0.000) — RA's is close to the driver's
configured 34min worm period. Far cleaner than anything from the sparser sync-guide sessions,
attributable to the much higher sample density.

Angle-domain (properly corrected: `total_accum`→theta, time-detrended, x-axis computed
directly from az/alt/roll with no `resid` dependency — pulse-guide mode logs mostly
no-fresh-observation status lines, `resid` is NaN on 8408/8478 rows even though
`total_accum` isn't, so the x-axis must not require `resid` or it throws away 99% of the
data for no reason): **M1 peak=7.96° (power 0.145), M3 peak=7.50° (power 0.188)** — close to
each other (~6% apart) and in a similar range to the earlier (now-downgraded) cross-session
~6-7° cluster. Peak/testable_max ratios are 0.82-0.88 — better than the worst edge-biased
results seen earlier, but not as clean as the time-domain result above, so treat as a
tentative further data point for the ~6-7° hypothesis, not confirmation on its own.

---

## Dedicated PEC-off, sync-guide-on capture: `logs/archive/alpaca.soak_nopec_Beta4.3_08_31a*.log`

Exactly the missing dataset from 0.0's log inventory — Config.advanced_pec off,
advanced_sync_guiding on, log_position on (KFLOG available). 20 rotated files, 366MB,
232416 KFLOG rows, 2026-08-31 19:08:52 → 2026-09-01 08:41:33 (~13.5h nominal span). Site:
same as before (-33.655°, 151.122°, Sydney).

**Real interruption found and precisely bounded** (not from `find_tracking_segments()`'s
REST-command boundaries, which found a different, spurious split — from the raw KFLOG/PIDLOG
timestamp gaps directly): driver telemetry gap 2026-09-01 00:41:42.411 → 00:57:12.591
(15.5min — the reboot). A second disruption follows at 03:30:24: `synctocoordinates` to
RA=0.394h/Dec=-71.75° (essentially 47 Tuc) immediately followed by `findhome` +
`"Advanced Control: STOP tracking"` — almost certainly the point the TP-Link IP fix actually
completed and reconnection finished (matches the user's account of a longer recovery than the
15.5min driver-process gap alone suggests).

**Tracking stopping at 03:30:24 is expected, not a bug — user stopped the session there
deliberately (3:30 AM).** `θ_ref_raw` (only populated "while actively tracking") has exactly
5 non-NaN rows in all 93231 KFLOG rows of the 03:30→08:41 window — all in the last second
before the stop took effect — and no "START tracking" appears anywhere afterward, confirming
tracking genuinely didn't resume, but that's simply because the session ended there.
**The 03:30→08:41 log content is not usable for tracking/PE analysis** (nothing to analyze,
not "went wrong") — user is removing these later log files from the archive.

**Also found: sync-guiding stopped at the same point, for the same reason.** Cross-checked via
`load_sync_guiding_residuals()` (430 total corrections across the whole file set) — the very
last one is at 03:30:21.876, matching the reconnection's `synctocoordinates` to the
millisecond. Zero corrections after that, simply because the session ended there (not a
re-arming failure — originally misread as one before the user clarified).

**Net usable data: two segments**, not one continuous ~13.5h run:
- **Segment 1**: 19:08:52 → 00:41:42 (~5.5h), 295 sync-guide residual events, 93756 KFLOG rows.
- **Segment 2**: 00:57:12 → 03:30:21 (~2.5h), 135 residual events (87 usable after the theta2
  guard — this window overlaps the earlier-noted noisier PID-error stretch), ~45418 KFLOG rows.
- Segment 3 (03:30→08:41): KFLOG exists but is not usable (no tracking, see above).

**Methodological correction needed before analyzing Segments 1/2, found by reasoning through
what a *long*, actively-guided session actually means for the KFLOG-based ground truth**:
`θ_meas_raw − θ_ref_raw` (the original Phase 0.1 plan, and what `analyse_pec.ipynb`'s
existing "Base vs Corrected Frame Shift" section uses) is *not* clean here the way it looked
in earlier, shorter investigations. Traced why: `topoQ_to_baseQ()` (which builds `theta_ref`)
explicitly does not undo Sync Guiding Corrections (SGC) — confirmed from its own docstring
("no undo Sync Guiding Corrections (SGC)") — but `θ_meas_raw` *does* physically reflect every
sync-guide correction ever applied (they cause real motor motion, as established earlier in
this investigation). Over a session with hundreds of real corrections, this means
`θ_meas_raw − θ_ref_raw` isn't "raw uncorrected PE" — it's raw PE *plus the ever-growing
cumulative effect of every correction ever applied*, since `θ_ref_raw` never learns about
them. Confirmed empirically before trusting it: Segment 1's raw shift reaches tens of
thousands of arcsec (multiple degrees) with a smooth, U-shaped/reversing trajectory — real
secular drift, not noise, but the wrong signal for isolating PE, for the same structural
reason `resid` was the wrong signal before PEC's contamination was found (same shape of bug,
different mechanism: SGC this time, not PEC's feed-forward).

**Fix, mirroring the `total_accum` fix**: since there's no PECLOG here (no `total_accum`
either), added `load_sync_guiding_residuals()` (parses `SYNC GUIDING ... Residuals` lines
directly — works with zero PECLOG, since `process_guide_sync()` logs this line
unconditionally) and `derive_theta_from_sync_residuals()` (anchors each session/segment's
first usable event, reconstructs `true_ra/dec(t) = anchor + cumsum(resid)(t)/60`, converts to
theta via the same kinematics chain — position source is `θ_meas_raw`, converted to az/alt/roll
via `kinematics.theta_to_azaltroll()`, since there's no PECLOG `az`/`alt`/`roll` to use here).
No separate "add back PEC's correction" term needed — with PEC off, `resid` alone is already
the complete uncorrected-drift signal, an even more direct case than `total_accum`'s.

**Results** (`periodogram_false_alarm_probability`, `n_shuffles=200`, linear-detrended before
the call since the periodogram function's own detrend is against x, not t):

| Segment | Motor | n | x span | TIME peak | TIME power/FAP | ANGLE peak | ANGLE power/FAP | testable_max |
|---|---|---|---|---|---|---|---|---|
| 1 (5.5h) | M1 | 295 | 97.3° | 132.44min | 0.124 / 0.000 | 42.75° | 0.280 / 0.000 | 48.63° |
| 1 | M2 | 295 | 23.7° | 134.50min | 0.164 / 0.000 | 11.84° | 0.250 / 0.000 | 11.84° (edge) |
| 1 | M3 | 295 | 79.1° | 132.36min | 0.124 / 0.000 | 35.08° | 0.317 / 0.000 | 39.57° |
| 2 (2.5h) | M1 | 87 | 19.2° | 46.22min | 0.571 / 0.000 | 8.83° | 0.664 / 0.000 | 9.62° |
| 2 | M2 | 87 | 20.0° | 29.16min | 0.114 / 0.290 (n.s.) | 8.66° | 0.115 / 0.300 (n.s.) | 10.01° |
| 2 | M3 | 87 | 11.4° | 43.76min | 0.276 / 0.000 | 5.05° | 0.353 / 0.000 | 5.71° |

**Read on this**: M1≈M3 (not M2) holds up again, in both segments, on a fifth and sixth
independent measurement (now across five different nights total counting the earlier ones) —
Segment 1: 132.44 vs 132.36min (essentially identical). Segment 2: 46.22 vs 43.76min (also
close to each other). That cross-motor consistency-within-a-segment is the most repeatable
signal in this whole investigation so far. What is *not* yet resolved: Segment 2's time-domain
period is roughly 1/3 of Segment 1's (44-46min vs 132min) — could be genuine harmonic
aliasing (a shorter segment latching onto a higher harmonic of the same true period a longer
one resolves as fundamental) or could be two genuinely different measurements not yet
reconciled; not distinguished yet. Angle-domain peaks remain closer to their testable_max
ceilings than ideal (88-100%), so the *absolute* angular period numbers from this data still
carry the same caveat as before — the cross-motor pattern is the reliable part, not yet the
specific degree value.

## New driver feature: `SGLOG` — self-sufficient sync-guide telemetry without `log_position`

Motivated directly by the previous section: the 08_31 capture needed `log_position` (KFLOG)
on just to recover motor position for `derive_theta_from_sync_residuals()`, which is what
produced 20 rotated 20MB files for a single overnight run. That's avoidable — `process_guide_sync()`
already computes everything needed at the moment of each sync-guide correction, it just wasn't
being logged in structured form.

**`driver/control.py` changes** (`process_guide_sync()`):
- A new `SGLOG {dict}` line, logged unconditionally right after the existing plain-text
  `"SYNC GUIDING ... Residuals"` line (same as PECLOG's own logging — independent of
  `Config.log_pec`/`Config.log_position`, so it's available even with both off). Fields:
  `resid` (this correction, arcmin, same convention as PECLOG's `resid`), `total_accum`
  (cumsum since reset, arcmin), `theta_raw` ([M1,M2,M3] degrees, straight from
  `self.polaris._theta_raw` — no more need to nearest-match against KFLOG to get a position),
  `az`/`alt`/`roll` (topocentric PV, same convention as PECLOG), `interval_sec` (smoothed EMA
  time between syncs), and `age_518` (telemetry staleness, same diagnostic PECLOG carries).
- **`total_accum` reuses the existing `self.delta_guide_accum[0]`/`[1]` state, not a new
  counter.** First cut of this added a dedicated `sg_accum_ra`/`sg_accum_dec` pair — caught in
  review as redundant: `accumulate_sync_guiding_residuals()` (called right before the SGLOG
  block, same as before) already does `delta_guide_accum[0] += ra_resid` /
  `[1] += dec_resid`, the identical cumulative sum, just in degrees rather than arcmin
  (scaled ×60 when logged). Tracing the reset call sites showed `delta_guide_accum`'s
  semantics are actually *more* correct for this than a dedicated counter would have been: it
  resets in `clear_sync_guiding()` (same as a dedicated counter would), but *also* in
  `clear_guide_pulses()` — called from `optimize_alignQ_B2T()` whenever the QUEST `alignQ_B2T`
  model is recomputed (only happens on the non-sync-guiding path through `sync_az_alt()`,
  i.e. rare during steady guiding) — exactly the moment a stale cumulative total would
  otherwise silently mean something different against the new alignment model. A separate
  counter reset only by `clear_sync_guiding()` would have kept summing straight through an
  alignment change. Removed the dedicated state entirely; SGLOG now just reads
  `delta_guide_accum` after `accumulate_sync_guiding_residuals()` has updated it.
- Verified with `compile()`; not yet exercised against a live driver run (no capture has used
  it yet — it's brand new).

**`utility/analyse_helpers.py`**: added `load_sglog(log_filenames, log_dir='.')`, parsing
`SGLOG {dict}` lines into a DataFrame with the same `resid_1/2`/`az`/`alt`/`roll`/
`total_accum_1/2` column shape `load_pec()` produces, so `derive_theta_from_total_accum()`
works on SGLOG output directly (its PEC-independence assumption already matches how SGLOG's
`total_accum` is constructed). `theta_raw_1/2/3` is carried straight through, so for a
PEC-off/log_position-off session, SGLOG alone is now sufficient for the theta-space pipeline —
no KFLOG needed, and no nearest-timestamp matching (`load_sync_guiding_residuals()` +
`derive_theta_from_sync_residuals()` remain the fallback path for logs captured before this
change). Raises if no SGLOG lines are found, matching `load_pec()`'s behavior.

**Not yet done**: no real SGLOG data exists to validate against (next capture will be the
first). Once one exists, worth a quick sanity check that `load_sglog()`'s `total_accum` column
reproduces `cumsum(resid)` to rounding precision, the same check already done for PECLOG's
`total_accum` against `08_29` data.
