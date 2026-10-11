# Alignment Model — M2/M3 Offsets and M2 Scale in QUEST (Plan)

Branch: to be created from `feature/pec_theta_v2`. Analysis: October 2026, from the sync tables in `logs/archive`.

## Status (2026-10-11)

Implemented on `feature/alignment_mac_v2`; user documentation in [kinematics.md §2.3](kinematics.md#23-mechanical-alignment-corrections).

* `driver/kinematics_mac.py`: the fit (numpy, analytic derivatives, Gauss–Newton from QUEST's rotation): 0.6 ms for 10
  points on a desktop, against 20 ms for the study prototype. The control-tick correction is a closed form: about
  6 µs per tick.
* The **Mechanical Alignment Correction** switch (`advanced_align_mac`) is the A/B switch. On: the rotation and
  d2, d3 refitted unweighted at every sync, with `align_m2_scale` (%, default 1.0). When the points can't separate
  the offsets, they are held and the rotation is the existing weighted QUEST. Off: the existing QUEST, unchanged.
* The earlier MAC model has been retired (copy in `utility/legacy_mac.py` for `fits_extract.py`). Pilot's AutoTune
  now calibrates the M2 scale from the current sync points. First calibration on jdm's mount: **+0.335%**.
* `utility/alignment_ab.py` replays the archived sync tables: goto accuracy (leave-one-out) median 59.2′ (MAC off)
  → 9.6′ (on), better on 45 of 47 alignments. The two worse: 6 points at roll ~0 (greg, 9.4′ → 11.7′), and a
  narrow-roll alignment both models fit poorly (86′ → 88′).
* Timed on the Pi Zero 2 W and nina01 (Cost, below): 15.8 ms and 2.7 ms per fit, 53 µs and 9 µs per tick.
* Still to do: the live A/B on the sky (alignment RMS, first-goto error,
  drift with MAC on and off from the same syncs); the scale-or-sag test with the 300 mm.

## Summary

Multi-Point Alignment has rarely reached a low RMS: 6–10 point alignments typically report 30–60′, and up to
130′. The residuals are not noise. Across every archived log, three terms explain most of them:

* **M2 and M3 zero offsets** (or, equivalently with this data, the camera tilted on the head), fitted at each
  alignment: they change with the lens and between sessions.
* **An M2 scale of about +1–2%**, the same on every Polaris in the logs: M2 turns 1–2% further than its reported
  angle says, over the altitudes used.

With these fitted together with QUEST's rotation, alignment residuals fall from a median of 36–95′ to 2–8′.

MAC does not model these terms correctly: its zero offsets are never applied, its strongest term (the
roll-dependent `m3_tilt_dm2`) cannot be applied before QUEST and is switched off, and its M2 term is a sine that
acts as a scale and offset, fitted through a pre-QUEST sign convention that QUEST must absorb. This plan replaces
MAC's role with a joint fit.

The large drift rates PEC Drift Correction has been absorbing (e.g. M11, 10 Oct: Dec 20–28″/min, MAC off, QUEST
39–62′) are the pointing error changing along the target's path, so a better model should also shrink them.

## Evidence

### Data

Every QUEST refit logs its point table: observed RA/Dec/Az/Alt and the raw motor pose `p_az/p_alt/p_roll`
(stored before worm, MAC or sync-guide corrections, `SyncManager.standard_entry`). 1,300 distinct points from
70 logs (jdm, Mark, Vyskocil, Greg; June–October 2026). An alignment is a log's largest table before its point
count drops, without points already used by an earlier one.

### Method

The driver's forward kinematics (`theta_to_q`: `C = Rz(−θ1+90°) · Ry(−θ2−90°) · Rx(−θ3)`, boresight −z) rebuilt in
numpy with optional terms: motor zero offsets (d2, d3), scales (s1, s2, s3; s2 about θ2 = 45°), axis tilts (M2 vs
M1, M3 vs M2) and camera tilt (the camera axis vs M3). Each alignment has its own rotation (the tripod and leveling
change); terms are fitted unweighted by least squares on the angular residual.

Validation: leave one alignment out. Shared terms come from the other alignments; the held-out one gets only a
rotation.

### Joint fit — jdm, 200 mm, 10-04 / 10-06 / 10-10 (34 points, 4 alignments)

| Model | Shared terms | Fit RMS | Held-out RMS |
|---|---|---|---|
| Rotation only (QUEST) | — | 45.6′ | 45.6′ |
| + M2, M3 zero offsets | d2 +58′, d3 −55′ | 11.0′ | 13.1′ |
| + camera tilt instead | cx +58′, cy −54′ | 10.9′ | 13.4′ |
| **+ offsets + M2 scale** | d2 +50′, d3 −53′, s2 +1.0% | **7.7′** | **10.5′** |
| + M1/M3 scale | s1 +0.1%, s3 0.0% | 7.4′ | 10.1′ |
| + axis tilts, camera tilt (10 terms) | | 7.4′ | 10.8′ |

* M1 and M3 have no scale error. Axis tilts add nothing.
* Zero offsets and camera tilt are indistinguishable here (same RMS, same sizes): either describes how the
  camera sits relative to M2/M3.

### Per alignment, every mount (≥ 7 points, ≥ 20° of M2 span)

| Mount (logs) | Alignments | Rotation only | + offsets | + offsets + M2 scale | M2 scale median (half IQR) |
|---|---|---|---|---|---|
| Mark | 11 | 95′ | 8.1′ | **2.4′** | +0.96% (±0.10) |
| jdm | 12 | 36′ | 12.0′ | **5.9′** | +1.36% (±0.24) |
| early jdm (pec_rls/ema) | 10 | 49′ | 12.9′ | **5.4′** | +1.17% (±0.49) |
| jdm soak (Aug–Sep) | 9 | 60′ | 15.3′ | **7.7′** | +1.76% (±0.18) |

* **The M2 scale is a Polaris property:** +1–2% on every mount, tightest on Mark's (0.6–1.3% over 11 nights).
  With the 300 mm lens it was +2.0% against +1.0% for the 200 mm on the same mount, so it may be partly gravity
  sag (an error growing towards the horizon, roughly cos(alt)), which over 20–70° looks like a scale and offset.
* **The offsets belong to the setup:** jdm 200 mm about +50′ / −53′ on three nights; 300 mm +110′ / −2′; Mark's
  M3 offset −5°, +6° or ~0 on different nights (the M3 zero reference or the camera's rotation in its clamp
  changing between sessions).
* Terms fitted on the 200 mm nights help other setups (e.g. 300 mm: 113′ → 64′) but are not enough; the offsets
  must be fitted per alignment.

## Design

### Model

```
θ' = θ + (0, d2 + s2·(θ2 − 45°), d3)          corrected motor angles (after the worm feed-forward)
cameraQ = alignQ_B2T · theta_to_q(θ')          then sync guide, pulse guide, SCC, roll_adj as now
```

* **Per alignment** (refitted at every sync, with the rotation): `alignQ_B2T`, d2, d3.
* **Mount constant** (config, default +1.0%; refined by a calibration from many points): s2.
* Inverse (commands, reachability): `θ = θ' − (0, d2 + s2·(θ2' − 45°), d3)` solved per motor (linear in θ2).

The terms act on the motor angles, so the corrected chain stays a pure rotation of `theta_to_q`: PID, KF, reach
limits and the speed controller keep working in θ space, with one conversion at the boundary.

### Fit

* Joint least squares over the rotation and d2, d3 on the angular residual: unweighted (or robust, e.g. Huber),
  not proximity-weighted. The current recency, proximity (σ 10°) and polar weights let a rotation-only model fit
  locally around the target; with the physical terms that compensation should no longer be needed. Slew & Center
  Correction and sync guiding stay for the remaining local error.
* Fewer than 3 points, or points without a spread in roll (both signs) and altitude: fit the rotation only, with
  d2, d3 held at the last values (or a weak prior towards them), so a single sync cannot produce wild offsets.
* QUEST's closed form gives the starting rotation; a few Gauss–Newton steps refine all five parameters.

### Cost

The fit runs only when an alignment sync adds a point or a setting forces a refit (worm on/off, site latitude): a
handful of times a night. Sync-guiding syncs return before QUEST (`sync_az_alt`) and are unaffected. At every
control tick the change is adding the offsets to the motor angles before `theta_to_q`: nothing measurable.

Measured on 2026-10-11 with the M11 alignment (10 points), the driver running on each machine:

| | Pi Zero 2 W (Cortex-A53 1.0 GHz) | nina01 (Celeron N5105) | Desktop |
|---|---|---|---|
| Prototype: rotation only (scipy, numerical derivatives) | 63 ms | 11 ms | 2 ms |
| Prototype: rotation + d2, d3 | 576 ms | 95 ms | 20 ms |
| Prototype: rotation + d2, d3, s2 | 1,023 ms | 161 ms | — |
| **`kinematics_mac.fit_alignment`**: rotation + d2, d3 (each sync) | **15.8 ms** (max 17.6) | **2.7 ms** | 0.6 ms |
| **`kinematics_mac.fit_alignment`**: + s2 (AutoTune) | 16.6 ms | 2.9 ms | — |
| **`kinematics_mac.correction_q`**, per control tick | **53 µs** | 8.9 µs | ~1 µs |

The fit is numpy only, vectorised over the points, with analytic derivatives and a few Gauss–Newton steps from
QUEST's closed-form rotation; the per-tick correction is a closed form, Rz(a1) Ry(a2′) Rx(−d3) Ry(−a2) Rz(−a1),
instead of building the forward kinematics twice (63 µs on a desktop). Both meet the Pi Zero 2 W target (under
~20 ms per fit), so the fit runs inline at the sync, like QUEST did: running it off the event loop
(`asyncio.to_thread`) isn't needed, and on a Pi would gain little anyway (small numpy operations hold the GIL).

### Interactions

| Part | Change |
|---|---|
| Worm feed-forward | Unchanged: applied to the motor angles before the model |
| Earlier MAC | Retired: the Mechanical Alignment Correction switch now runs this model; the old code is in `utility/legacy_mac.py` for `fits_extract.py` |
| Sync guiding, pulse guiding | Unchanged: applied after QUEST |
| Slew & Center Correction (SCC) | Unchanged. These logs ran Sync Guiding Adjustment (SGA, `advanced_scc_choice = 2`), which seeds the sync guide offset from the QUEST residual at each sync: with smaller residuals the seeds shrink, and SGA's correction becomes a small local touch-up rather than the 13–27′ seen on 10 Oct |
| Roll Adj | A roll sync's predicted roll is rebuilt from its raw motor angles with the current MAC and QUEST rotation, and `roll_adj` re-optimised after every refit (tests in `test_mac_sync.py`) |
| Logging | QUEST table and model line add d2, d3, s2 and the unweighted RMS |
| Pilot | Alignment page shows d2, d3, s2 |

### Validation

1. **Offline replay** (done): archived alignments above.
2. **Twin tests:** inject known d2, d3, s2 into the digital twin; the fit recovers them, and gotos and tracking
   are unchanged with zero terms.
3. **On the mount:**
   * the alignment RMS on the standard 6 points, before and after;
   * first-goto error on targets away from the sync points;
   * PEC drift rate on a long track (expected to shrink with the alignment error);
   * a scale or sag check: syncs at low and high altitude in one session, with the 200 mm and the 300 mm.

## Open questions

* **Scale or sag?** A scale is constant; sag depends on the load and grows towards the horizon. If it is sag,
  model `cos(θ2)` instead and store it per lens.
* **Mark's ±6° M3 offsets:** is the M3 zero reference re-set by the firmware at power-on, or was the camera
  rotated? The 517 MCU angles (zeta) could tell, since they are logged with each point now.
* **Refraction:** check whether the observed Az/Alt are refracted; about 1–3′ below 30°, small next to the
  terms above.
* **The remaining 2–8′:** plate-solve error, backlash at the sync, worm error at the sync (≤ 1.7′), M2 slips.
* **Focuser pull and lens flexure:** a constant sideways pull on the lens (e.g. the focuser) is indistinguishable
  from an M3 zero offset, since M3 turns the camera about its own up axis, so it is part of d3. If the pull comes
  from the focuser's weight bending the lens, it depends on gravity (roll and altitude) and is flexure: test a
  droop term along the gravity-down direction in the joint fit, and an alignment with the focuser removed.
