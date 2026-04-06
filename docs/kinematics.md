[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)



# Alpaca Benro Polaris Driver — Kinematics Reference
[Overview](#1-overview) | 
[Base](#21-base-frame-b---representations-and-conversions) | 
[Topo](#22-topocentric-frame-t---representations-and-conversions) | 
[Equatorial ](#23-equatorial-frame-e---representations) | 
[Forward Kinematics](#31-forward-kinematics--motors--sky-angular-position) | 
[Inverse Kinematics](#32-inverse-kinematics--sky--motors-angular-position) | 
[Feed Forward](#33-inverse-kinematics--sky--motors-angular-velocity-feed-forward) | 
[QUEST](#34-quest-alignment-optimisation) |
[RBC](#35-rotation-bias-correction-rbc) |
[LGC](#36-local-gaussian-correction-lgc) |


## 1. Overview

The Benro Polaris is a 3-axis motorised camera mount. Controlling it precisely requires
transforming between four reference frames: the camera sensor, the mount base, the local
sky, and the celestial sphere. This document defines those frames, the variables and
quaternions that live in each, and the kinematic chains that connect them.

---

## 2. Reference Frames

Each frame has a fixed set of basis axes. The scale of each reference frame is arbitrary, since Polaris kinematic mathematics is angle-based, and quaternions are defined on a unit sphere. Vectors and quaternions are tagged with
the frame they are expressed in.

| Frame | Name | Description | `+X` axis | `+Y` axis | `+Z` axis |
|-------|------|-------------|-----------|-----------|-----------|
| **C** | Camera Frame | Camera sensor geometry, independent of pointing direction, negative Z axis is camera boresight, looking skywards.  |  Image "up"             | Image "left"          | -ve boresight            |
| **B** | Base Frame   | Mechanical frame as bolted to tripod (assuming Az 180, Alt 45 after All Axis Reset). Differs from T by Multi-Point Alignment (`alignQ_B2T`)| Axis 2 red button side | Back SD card side     | Axis 1 up            |
| **T** | Topo Frame  | True local sky frame at observing site, with all corrections applied. Home of Az, Alt, Roll   | East                   | North                 | Zenith               |
| **E** | Equatorial Frame   | Earth-centred celestial frame, with all corrections applied. Home of RA, Dec, PA       | RA = 0h, Dec = 0°      | RA = 6h, Dec = 0°     | North Celestial Pole |

---

### 2.1 Base Frame (B) - Representations and Conversions

#### Mechanical Orientation and Angular Velocity
The Base Frame represents the mechanical orientation of the mount as either motor angles
or a quaternion. Both are equivalent, the choice is purely pragmatic. Angular velocity in the Base Frame drives individual motor speeds. The Jacobian `J(theta)` is a matrix that, for a given orientation `(theta)`, describes how small changes in the motor axis angles `(theta_dot)`, produce motion of the camera. It maps between motor axis rates and B frame angular velocity.

| Representation | Type       | Description  | Use for |
|----------------|------------|--------------|---------|
| `theta`        | angles     | Mechanical orientation as motor angles `(theta1, theta2, theta3)` | Jacobian, PID error signal, Kalman Filter state |
| `theta1`        | angle     | Motor 1 angular position [0 to 360); equal to az when theta3=0, diverges otherwise. +ve=cw (looking down towards mount, 0=North)| PID error signal |
| `theta2`        | angle     | Motor 2 angular position (-8 to +83); equal to alt when theta3=0, diverges otherwise; +ve=upwards (looking side on to mount, 0=Horizontal). | PID error signal |
| `theta3`        | angle     | Motor 3 (Astro) angular position (-180 to +180); rotation around camera up +X_C, swinging camera side to side; +ve=cw (looking down towards mount. 0=Level) | PID error signal |
| `motorQ_C2B`   | quaternion | Mechanical orientation as quaternion rotating vectors from C→B; equivalent to theta    | Composition, interpolation, kinematic chain     |
| `omega_base`   | vector | Angular velocity in Base frame `(omega1, omega2, omega3)` deg/s   | Jacobian input, feed-forward solve   |
| `omega_raw`    | vector | Raw angular velocity from device (proxy = `omega_ref`)            | Kalman Filter observation            |
| `omega_op`     | vector | Control output velocity sent to motors                            | Motor commands     

#### Conversion Functions

| From           | To             | Function                           | Notes |
|----------------|----------------|------------------------------------|-------|
| `motorQ_C2B`   | `theta`        | `= q_to_theta(motorQ)`             | Two solutions possible (elbow up/down). Resolved by proximity to last position. |
| `theta`        | `motorQ_C2B`   | `= theta_to_q(*theta)`      |  Determine quaternion that represents a given set of motor angles.                                                                        |
| `omega_topo`   | `omega_base`      | `= topoVec_to_baseVec(omega_topo, cameraQ_C2T)` | Undoes T-frame corrections, applies `alignQ_B2T_inv`. See Feed Forward. |
| `theta_dot`    | `omega_base`      | `= J(theta) · theta_dot` | joint rates → B frame angular velocity.  |
| `omega_base`   | `theta_dot`      | `= J⁻¹(theta) · omega_base` | B frame angular velocity → joint rates. Used to calculate FF joint rates. |

#### Variable Suffixes

Suffixes distinguish the level of processing applied to a mechanical orientation variable.

| Suffix   | Applies to  | Meaning                                                          |
|----------|-------------|------------------------------------------------------------------|
| `_raw`   | orientation | Uncorrected value direct from device                             |
| `_state` | orientation | Kalman Filter smoothed/estimated value                           |
| `_adj`   | orientation | Mechanically adjusted after KF + PEC + RBC                       |
| `_pv`    | orientation | Process Variable after KF + PEC + RBC + QUEST + LGC + Roll       |
| `_sp`    | orientation | User Set Point target value (pre slew offset and pulse guiding)  |
| `_ref`   | orientation | Final Reference target value for the control loop                |
| `_op`    | velocity    | Control output velocity for the motors                           |



---

### 2.2 Topocentric Frame (T) - Representations and Conversions

#### Sky Orientation and Angular Velocity

The Topocentric Frame represents the camera's sky orientation as either Az/Alt/Roll angles
or a quaternion. Both are equivalent, the choice is purely pragmatic. The Topocentric Frame Angluar Velocity typically represents the sidereal or orbital tracking velocity of a target object.


| Representation | Type       | Description  | Use for |
|----------------|------------|--------------|---------|
| `alpha`        | angles     | Sky orientation as topocentric angles `(az, alt, roll)`        | Display, ephem, PID setpoints, sync history        |
| `az`          | angle  | Azimuth — Measured in the horizon plane (0-360), from North toward East        | Target coordinate              |
| `alt`          | angle  | Altitude — Measured from horizon plane (-90 to +90), up toward Zenith        | Target coordinate              |
| `roll`          | angle  | Roll — rotation around boresight (-75 to +75), relative to the local horizon plane;  0=horizontal, +ve=camera rotates CCW when viewed from rear          | Target coordinate              |
| `cameraQ_C2T`  | quaternion | Sky orientation as quaternion rotating vectors from C→T; equivalent to alpha         | Composition, interpolation, kinematic chain, SLERP |
| `omega_topo`      | vector | Angular velocity in Topocentric frame, computed from `cameraQ_C2T` change over time | Feed-forward starting point |

#### Conversion Functions

| From           | To             | Function                           | Notes |
|----------------|----------------|------------------------------------|-------|
| `cameraQ_C2T`  | `alpha`         | ` = q_to_azaltroll(cameraQ)`   |   Determine sky angles for a given quaternion                             |
| `alpha`         | `cameraQ_C2T`  | ` = azaltroll_to_q(*alpha)`    |   Determine quaternion that represents a given set of sky                 |

---

### 2.3 Equatorial Frame (E) - Representations

#### Equatorial Orientation
| Representation | Type   | Description                                                                                  | Use for                        |
|----------------|--------|----------------------------------------------------------------------------------------------|--------------------------------|
| `delta`        | angles | Equatorial orientation as `(RA, Dec, PA)`                                                    | Target coordinates, tracking   |
| `ra`           | angle  | Right Ascension — sidereal time the DSO will pass the meridian, eastward from vernal equinox (hours)       | Target coordinate              |
| `dec`          | angle  | Declination — angle from celestial equator: −90° (south), 0° (equator), +90° (north)        | Target coordinate              |
| `pa`           | angle  | Position Angle — angle from celestial north pole to camera up (+X_C); PA = parallactic + roll | Target coordinate             |
| `para`         | angle  | Parallactic Angle — angle between celestial north pole and zenith at the target RA/Dec       | Derived, used to compute PA    |
| `LST`          | time   | Local Sidereal Time — the RA currently on the meridian at the observing site. LST = RA + HA  | Time reference for tracking    |
| `HA`           | time   | Hour Angle — how far a target has travelled past the meridian. HA = LST − RA. Negative before meridian, positive after | Derived, used in ephem |



Conversion between T and E frames is handled by `pyephem` using the observer's site
coordinates and time. Angles are always used in practice for the E frame.

---
## 3. Kinemtaics Flows


### 3.1 Forward Kinematics — Motors → Sky Angular Position

Converts the raw IMU quaternion from the Polaris device into a fully corrected sky
orientation. 

```
motorQ_raw              Raw C→B quaternion from Polaris IMU (q1, from 518 message)
theta_raw               Raw motor angles = q_to_theta(motorQ_raw) used in KF
omega_raw               Raw angular velocity (proxy = omega_ref)
    │
    ▼ Kalman Filter(theta_raw, omega_raw)
theta_state             KF smoothed motor morientation angles
motorQ_state            KF smoother motor orientation quaternion C→B
alpha_state             KF sky angles = q_to_azaltroll(motorQ_state) used in QUEST (p_az,p_alt,p_roll)
    │
    ▼ Periodic Error Correction, optional (future — currently theta_adj = theta_state)
    ▼ Rotation Bias Correction, optional (corrQ_RBC)
theta_adj              adjusted motor orientation angles
motorQ_adj             adjusted motor orientation quaternion (theta_to_q)
    │
    ▼ Frame Transform baseQ_to_topoQ = corrQ_roll ∘ corrQ_LGC ∘ alignQ_B2T ∘ motorQ_adj
    ▼     QUEST Alignment (alignQ_B2T) 
    ▼     Local Gaussian Correction (corrQ_LGC)
    ▼     Roll Sync Adjustment (corrQ_roll)
cameraQ_pv             Fully corrected C→T pointing quaternion
alpha_pv               (a_az, a_alt, a_roll) = q_to_azaltroll(cameraQ_pv)
delta_pv               (a_ra, a_dec, a_pa)   = pyephem(az, alt, roll), used as ASCOM co-ordinates
```

### 3.2 Inverse Kinematics — Sky → Motors Angular Position

Converts a target sky orientation into the motor angles required to achieve it. Undoes
corrections in exact reverse order of the forward chain. No `corrQ_RBC⁻¹` is needed as
RBC is applied at the measurement stage, not in the alignment chain.

```
delta_sp                DSO Target equatorial coordinates (RA, Dec, PA)
    │
    ▼     Pulse Guiding delta_offset += delta_g_sp(ms) * guide_rate
    ▼     Slewing       delta_offst  += delta_v_sp * dt
    ▼     Add offset    delta_ref    =  delta_sp + delta_offst
delta_ref               DSO Target adjusted equatorial coordinates (RA, Dec, PA)
    │
    │ ---  SIDEREAL  ---OR--- ORBITAL ---
    ▼   delta2body() ---OR--- pyephem.body(Orbital Parameters) 
  body                  Target pyephem body
    │
    │ --- TRACK MODE ---OR--- AUTO MODE --- (ie goto or slew with no tracking)
    ▼     body2alpha ---OR--- alphar_ref = alpha_sp + alpha_offst 
alpha_ref               Target topocentric angles (az, alt, roll)
cameraQ_ref             Target C→T quaternion = azaltroll_to_q(*alpha_ref)
    │
    ▼ Shortest Path SO(3) slerp from cameraQ_pv to cameraQ_ref
cameraQ_step
    │
    ▼ Frame Transform topoQ_to_baseQ = corrQ_roll⁻¹ ∘ corrQ_LGC⁻¹ ∘ alignQ_B2T⁻¹ ∘ cameraQ_step
    ▼    Undo Roll Sync Adjustment      (corrQ_roll⁻¹, T frame)
    ▼    Undo Local Gaussian Correction (corrQ_LGC⁻¹, T frame)
    ▼    QUEST Alignment inverse        (alignQ_B2T_inv, T→B)
motorQ_ref              Target C→B quaternion
theta_ref               Target motor angles (θ1, θ2, θ3) = q_to_theta(motorQ_ref)
    │                        two solutions possible (elbow up/down).
    │                        resolved by proximity to last known position.
    ▼  PID Error Signal
error_signal            = theta_ref - theta_adj
    │
    ├── omega_kp        = +Kp · error_signal             Proportional
    ├── omega_ki        = +Ki · ∫ error_signal dt        Integral
    ├── omega_kd        = -Kd · omega_op                 Derivative (velocity damping)
    ├── omega_ff        = -Kf · omega_ff                 Tracking joint rates
    │
    ▼  PID + Feed Forward
omega_tgt               = omega_kp + omega_ki + omega_kd + omega_ff
    │
    ▼  Constrain (acceleration limit Ka, velocity limit Kv, position limit Config.z_min/max_limit)
omega_ctl                Desired motor control velocities
omega_op                 Requested motor Speed Controller outputs
    │
    ▼  Motor Speed Controller (interpolate speed commands and SLOW_PWM)
polaris_protocol         Slew SLOW and FAST commands
```

---

### 3.3 Inverse Kinematics — Sky → Motors Angular Velocity (Feed Forward)

Converts the rate of change of the sky target into motor joint rates for sidereal tracking
feed-forward. The Jacobian `J(theta_adj)` is expressed in the **B frame**, so `omega_topo`
must be converted to `omega_base` before the solve. No `corrQ_RBC⁻¹` is needed — RBC is
already accounted for in `theta_adj` and therefore in the Jacobian.

```
cameraQ_ref             Target C→T quaternion (from last two control steps)
    │
    ▼  calculate_angular_velocity(cameraQ_C2T_ref_last, cameraQ_C2T_ref, dt)
omega_topo              Angular velocity of sky target in T frame
    │
    ▼  topoVec_to_baseVec(omega_topo, cameraQ_pv)
    │  Undo T-frame corrections and rotate T → B:
    │  corrQ_roll⁻¹(T) → corrQ_LGC⁻¹(T) → alignQ_B2T_inv(T→B)
omega_base              Angular velocity in B frame
    │
    ▼  Inverse Jacobian Solution = J⁻¹(theta_adj) · omega_base
theta_dot               Motor joint rates (radians)
    │
    ▼  degrees(theta_dot)
omega_ff                Feed-forward motor joint rates
```

---

### 3.4 QUEST Alignment Optimisation

QUEST finds the optimal `alignQ_B2T` that minimises the angular residual between
IMU-predicted and plate-solved observed positions across all sync points.

Smoothed `alpha_state` values (`p_az`, `p_alt`, `p_roll`) are stored in sync history. RBC is
applied at optimisation time so that toggling `advanced_align_roll` immediately
recalculates `alignQ_B2T` without requiring new sync observations.

```
For each sync point in history:

    v_pred = azalt_to_vector(p_az, p_alt)              ← alpha_raw stored values

    if advanced_align_roll:
        motorQ_entry = azaltroll_to_q(p_az, p_alt, p_roll)
        motorQ_adj   = corrQ_RBC ∘ motorQ_entry         ← apply RBC at optimisation time
        v_pred       = azalt_to_vector(*q_to_azaltroll(motorQ_adj)[:2])

    v_obs = azalt_to_vector(a_az, a_alt)               ← plate-solved observed position

QUEST optimises alignQ_B2T to minimise Σ angle(alignQ_B2T · v_pred, v_obs)
```

---
### 3.5 Rotation Bias Correction (RBC)

Through extensive testing (around 1,000 plate-solves across a grid of mechanical 
positions), we confirmed that the Polaris IMU systematically mis-reports the camera 
rotation angle. This causes a predictable pointing offset whose magnitude depends on 
the current rotation angle (p_roll) and altitude (p_alt).

Because the error changes with mechanical orientation, it cannot be absorbed by 
QUEST's rigid-body alignment. A sync point taken at one rotation angle gives QUEST 
contradictory information to a sync point taken at the same altitude and azimuth but at a different rotation angle, 
preventing convergence to a stable solution.

The effect is modest at low altitudes and small rotation angles, but grows significantly with larger altitudes (toward the zenith) and with larger roll angles (away from horizontal). At 70° altitude and ±70° rotation, the uncorrected error reaches ±205 arcmin in roll and ±563 arcmin (~9°) in azimuth.

#### Root Cause

M3 (theta3) controls the camera up-vector rotation. The IMU has two coupled encoder
errors in M3:

| Coefficient     | Physical Meaning                                                                 |
|-----------------|----------------------------------------------------------------------------------|
| `roll_model_a`  | **Gain error** — M3 reports slightly less rotation than actually occurred. Scales with altitude because a roll error projects onto Az by `tan(alt)` as azimuth lines converge toward the zenith. Hardware characteristic of the Polaris unit (encoder linearity, mechanical flex in M3 arm). Stable across setups and SPA alignments. |
| `roll_model_b`  | **Zero-point offset** — IMU believes theta3=0 but the camera up-vector is not quite level. Residual bias at zero altitude independent of how far M3 has rotated. Also a hardware characteristic, stable across setups. |

#### Discovery and Calibration

The error was discovered by plate-solving ~1000 images across a porcupine grid of
Az/Alt/Roll positions using Single Point Alignment (no QUEST). Three components of the deviation between plate-solved and predicted positions (`dev_roll`), were identified:

| Component | Description                                              | Handled by        |
|-----------|----------------------------------------------------------|-------------------|
| [1] Global SPA bias    | ~2.5° constant roll offset from SPA-only alignment | QUEST (any sync point) |
| [2] Polar misalignment | ~0.9° sinusoidal Az-dependent variation from mount tilt | QUEST (multi-point sync) |
| [3] Rotation bias      | Roll-dependent residual — `f(p_roll, p_alt)` | RBC — QUEST cannot fix this |

Component [3] is what RBC corrects. After removing [1] and [2], the residual follows:

roll_error (arcmin) = (roll_model_a · tan(alt) + roll_model_b) · p_roll
---

Fitted from calibration data: R² = 0.995 for slope vs tan(alt), per-cell R² > 0.96.
Given this fitted model, the Roll and Az corrections are as follows
#### Roll Error (arcmin)

| alt \ p_roll | -70° | -60° | -50° | -40° | -30° | -20° | -10° | +0° | +10° | +20° | +30° | +40° | +50° | +60° | +70° |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **0°** | -18 | -15 | -13 | -10 | -8 | -5 | -3 | +0 | +3 | +5 | +8 | +10 | +13 | +15 | +18 |
| **10°** | -30 | -25 | -21 | -17 | -13 | -8 | -4 | +0 | +4 | +8 | +13 | +17 | +21 | +25 | +30 |
| **20°** | -42 | -36 | -30 | -24 | -18 | -12 | -6 | +0 | +6 | +12 | +18 | +24 | +30 | +36 | +42 |
| **30°** | -57 | -49 | -41 | -33 | -24 | -16 | -8 | +0 | +8 | +16 | +24 | +33 | +41 | +49 | +57 |
| **40°** | -75 | -64 | -53 | -43 | -32 | -21 | -11 | +0 | +11 | +21 | +32 | +43 | +53 | +64 | +75 |
| **50°** | -99 | -85 | -71 | -56 | -42 | -28 | -14 | +0 | +14 | +28 | +42 | +56 | +71 | +85 | +99 |
| **60°** | -136 | -116 | -97 | -78 | -58 | -39 | -19 | +0 | +19 | +39 | +58 | +78 | +97 | +116 | +136 |
| **70°** | -205 | -176 | -146 | -117 | -88 | -59 | -29 | +0 | +29 | +59 | +88 | +117 | +146 | +176 | +205 |

#### Az Error (arcmin)

| alt \ p_roll | -70° | -60° | -50° | -40° | -30° | -20° | -10° | +0° | +10° | +20° | +30° | +40° | +50° | +60° | +70° |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **0°** | +0 | +0 | +0 | +0 | +0 | +0 | +0 | +0 | +0 | +0 | +0 | +0 | +0 | +0 | +0 |
| **10°** | -5 | -4 | -4 | -3 | -2 | -1 | -1 | +0 | +1 | +1 | +2 | +3 | +4 | +4 | +5 |
| **20°** | -15 | -13 | -11 | -9 | -7 | -4 | -2 | +0 | +2 | +4 | +7 | +9 | +11 | +13 | +15 |
| **30°** | -33 | -28 | -23 | -19 | -14 | -9 | -5 | +0 | +5 | +9 | +14 | +19 | +23 | +28 | +33 |
| **40°** | -63 | -54 | -45 | -36 | -27 | -18 | -9 | +0 | +9 | +18 | +27 | +36 | +45 | +54 | +63 |
| **50°** | -118 | -101 | -84 | -67 | -50 | -34 | -17 | +0 | +17 | +34 | +50 | +67 | +84 | +101 | +118 |
| **60°** | -235 | -201 | -168 | -134 | -101 | -67 | -34 | +0 | +34 | +67 | +101 | +134 | +168 | +201 | +235 |
| **70°** | -563 | -483 | -402 | -322 | -241 | -161 | -80 | +0 | +80 | +161 | +241 | +322 | +402 | +483 | +563 |

The key takeaways are clear from the numbers, roll correction at typical observing altitudes (40°–60°) ranges from around ±75 to ±136 arcmin at maximum p_roll. The az correction is much more dramatic, reaching ±563 arcmin (nearly 10°) at 70° altitude and ±70° p_roll.

#### Re-Calibration of the model parameters
A calibration utility, `fits_extract.py`, is provided to derive the correction 
coefficients for your specific mount. This script is optional as the standard model parameters should be sufficient. Re-calibrating is only recommended for advanced technical specialists, aiming to optimise their performance without additional support. To use it:

1. Capture images across a grid of altitude, azimuth and rotation positions using 
   Single Point Alignment (no QUEST). Aim for good coverage across the full rotation 
   range at several altitude and azimuth combinations.
2. Batch plate-solve all images using ASTAP.
3. Run `fits_extract.py -extract` to read the FITS files and build a CSV of predicted 
   versus plate-solved values.
4. Run `fits_extract.py -model` to fit the correction model and print the 
   `roll_model_a` and `roll_model_b` coefficients for your mount.
5. Adjust these parameters by editing directly in `config.toml`

The default coefficients were derived from a 1,000 image test on a single unit. 
As the coefficients reflect hardware characteristics of the M3 encoder, linearity 
and zero-point offset, they should be stable across setups and SPA alignments, 
but may differ between individual Polaris units.

---
### 3.6 Local Gaussian Correction (LGC)

Even after QUEST alignment, a small residual pointing error typically remains at any
given sky position. This occurs because QUEST fits a single rigid-body rotation
(`alignQ_B2T`) across all sync points. It finds the global optimum but cannot perfectly
satisfy every individual point. 

This can be a problem for **Slew and Center** commands that verify the accuracy of a GOTO command. After a plate-solve, the controlling application makes a corrective slew to the target. If there is a residual error at this sync point, then it may take several corrective slews to narrow in on the target. The LGC corrects this residual locally around the most
recent sync point, fading to identity as the mount moves away.

#### Concept

After a sync, the residual error at that sync point is known exactly. It is the
difference between the QUEST-corrected predicted position and the observed plate-solved
position. LGC applies this residual as a full correction at the sync point, then
spatially fades it using a Gaussian weight as a function of angular distance:

**weight = exp(−angular_distance² / (2 · σ²))**
**where: σ = 15° (default)**

At the sync point itself: `weight = 1.0` — full correction applied.  
At 15° away: `weight = exp(-0.5) ≈ 0.61` — correction at 61%.  
At 30° away: `weight = exp(-2.0) ≈ 0.14` — correction at 14%.  
Beyond ~45°: `weight < 0.05` — correction effectively zero, LGC inactive.

This means the mount points with maximum accuracy near the last sync point and
gracefully degrades to QUEST-only accuracy as it moves away, without any
discontinuity.


---
## 4. Summary — Full Kinematic Chain

```
motorQ_raw          (C→B, raw from IMU)
theta_raw / alpha_raw / omega_raw
    │
    ▼  KF + PEC + RBC
theta_adj / motorQ_adj    (B frame, mechanically adjusted)
    │
    ▼  corrQ_RBC           Rotation Bias Correction     B frame
    ▼  alignQ_B2T          QUEST Alignment              B → T
    ▼  corrQ_LGC           Local Gaussian Correction    T frame
    ▼  corrQ_roll          Roll Sync Adjustment         T frame
    │
cameraQ_C2T_pv      (C→T, fully aligned, process variable)
alpha_pv            (T frame sky angles)
    │
    ▼  pyephem             Topocentric → Equatorial
    │
delta_pv            (RA, Dec, PA)
```

The inverse chain (`topoQ_to_baseQ`) undoes the frame transforms in exact reverse order.
RBC is handled at the measurement/PEC stage and does not appear in the inverse chain.

---