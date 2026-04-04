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

Each frame has a fixed set of basis axes. Vectors and quaternions are tagged with
the frame they are expressed in.

| Frame | Name | Description | `+X` axis | `+Y` axis | `+Z` axis |
|-------|------|-------------|-----------|-----------|-----------|
| **C** | Camera Frame | Camera sensor geometry, independent of pointing direction, -Z axis is camera boresight, looking skywards.  |  Image "up"             | Image "left"          | -ve boresight            |
| **B** | Base Frame   | Mechanical frame as bolted to tripod (Az 180, Alt 45 after All Axis Reset). Differs from T by Multi-Point Alignment (`alignQ_B2T`)| Axis 2 red button side | Back SD card side     | Axis 1 up            |
| **T** | Topo Frame  | True local sky frame at observing site, will all corrections applied. Home of Az, Alt, Roll   | East                   | North                 | Zenith               |
| **E** | Equatorial Frame   | Earth-centred celestial frame, with all corrections applied. Home of RA, Dec, PA       | RA = 0h, Dec = 0°      | RA = 6h, Dec = 0°     | North Celestial Pole |

---

### 2.1 Base Frame (B) - Representations and Conversions

#### Mechanical Orientation and Angular Velocity
The Base Frame represents the mechanical orientation of the mount as either motor angles
or a quaternion. Both are equivalent, the choice is purely pragmatic. Angular velocity in the Base Frame drives individual motor speeds. The Jacobian `J(theta)` maps between B frame angular velocity and motor joint rates.

| Representation | Type       | Description  | Use for |
|----------------|------------|--------------|---------|
| `theta`        | angles     | Mechanical orientation as motor angles `(theta1, theta2, theta3)` | Jacobian, PID error signal, Kalman Filter state |
| `motorQ_C2B`   | quaternion | Mechanical orientation as quaternion rotating vectors from C→B    | Composition, interpolation, kinematic chain     |
| `omega_B`      | vector | Angular velocity in Base frame `(omega1, omega2, omega3)` deg/s   | Jacobian input, feed-forward solve   |
| `omega_raw`    | vector | Raw angular velocity from device (proxy = `omega_ref`)            | Kalman Filter observation            |
| `omega_op`     | vector | Control output velocity sent to motors                            | Motor commands     

#### Conversion Functions

| From           | To             | Function                           | Notes |
|----------------|----------------|------------------------------------|-------|
| `motorQ_C2B`   | `theta`        | `= motorQ_C2B_to_theta(motorQ)`      | Two solutions possible (elbow up/down). Resolved by proximity to last position. |
| `theta`        | `motorQ_C2B`   | `= theta_to_motorQ_C2B(*theta)`      |  Determine quaternion that represents a given set of motor angles.                                                                        |
| `omega_T`      | `omega_B`      | `= topoVec_to_baseVec(omega_T, cameraQ_C2T)` | Undoes T-frame corrections, applies `alignQ_B2T_inv`. See Feed Forward. |
| `theta_dot`      | `omega_B`      | `= J(theta) · theta_dot` | B frame angular velocity → joint rates. |
| `omega_B`      | `theta_dot`      | `= J⁻¹(theta) · omega_B` | joint rates → B frame angular velocity. |

#### Variable Suffixes

Suffixes distinguish the level of processing applied to a mechanical orientation variable.

| Suffix   | Applies to  | Meaning                                                          |
|----------|-------------|------------------------------------------------------------------|
| `_raw`   | orientation | Uncorrected value direct from device                             |
| `_state` | orientation | Kalman Filter smoothed/estimated value                           |
| `_adj`   | orientation | Mechanically adjusted after KF + PEC + RBC                       |
| `_pv`    | orientation | Process Variable after KF + PEC + RBC + QUEST + LGC + Roll       |
| `_ref`   | orientation | Setpoint / reference / target value for the control loop         |
| `_op`    | velocity    | Control output velocity for the motors                           |



---

### 2.2 Topocentric Frame (T) - Representations and Conversions

#### Sky Orientation and Angular Velocity

The Topocentric Frame represents the camera's sky orientation as either Az/Alt/Roll angles
or a quaternion. Both are equivalent, the choice is purely pragmatic. The Topocentric Frame Angluar Velocity typically represents the sidereal or orbital tracking velocity of a target object.


| Representation | Type       | Description  | Use for |
|----------------|------------|--------------|---------|
| `alpha`        | angles     | Sky orientation as topocentric angles `(az, alt, roll)`        | Display, ephem, PID setpoints, sync history        |
| `cameraQ_C2T`  | quaternion | Sky orientation as quaternion rotating vectors from C→T         | Composition, interpolation, kinematic chain, SLERP |
| `omega_T`      | vector | Angular velocity in Topocentric frame, computed from `cameraQ_C2T` change over time | Feed-forward starting point |

#### Conversion Functions

| From           | To             | Function                           | Notes |
|----------------|----------------|------------------------------------|-------|
| `cameraQ_C2T`  | `alpha`         | ` = cameraQ_C2T_to_azaltroll(cameraQ)`   |   Determine sky angles for a given quaternion                             |
| `alpha`         | `cameraQ_C2T`  | ` = alpha_to_cameraQ_C2T(*alpha)`        |   Determine quaternion that represents a given set of sky angles                             |

---

### 2.3 Equatorial Frame (E) - Representations

#### Equatorial Orientation

| Representation | Type   | Description                              | Use for                             |
|----------------|--------|------------------------------------------|-------------------------------------|
| `delta`        | angles | Equatorial orientation as `(RA, Dec, PA)` | Target coordinates, tracking, ephem |

Conversion between T and E frames is handled by `pyephem` using the observer's site
coordinates and time. Angles are always used in practice for the E frame.

---
## 3. Kinemtaics Flows


### 3.1 Forward Kinematics — Motors → Sky Angular Position

Converts the raw IMU quaternion from the Polaris device into a fully corrected sky
orientation. 

```
motorQ_raw              Raw C→B quaternion from Polaris IMU (q1, from 518 message)
theta_raw               Raw motor angles = motorQ_C2B_to_theta(motorQ_raw) used in KF
alpha_raw               Raw sky angles = cameraQ_C2T_to_azaltroll(motorQ_raw) used in sync
omega_raw               Raw angular velocity (proxy = omega_ref)
    │
    ▼ Kalman Filter(theta_raw, omega_raw)
theta_state             KF smoothed motor angles
alpha_state             KF smoothed sky angles
    │
    ▼ Periodic Error Correction, optional (future — currently theta_corr = theta_state)
    ▼ Rotation Bias Correction, optional (corrQ_RBC)
theta_adj              adjusted motor orientation angles
motorQ_adj             adjusted motor orientation quaternion (theta_to_motorQ_C2B)
    │
    ▼ Frame Transform baseQ_to_topoQ = corrQ_roll ∘ corrQ_LGC ∘ alignQ_B2T ∘ motorQ_adj
    ▼     QUEST Alignment (alignQ_B2T) 
    ▼     Local Gaussian Correction (corrQ_LGC)
    ▼     Roll Sync Adjustment (corrQ_roll)
cameraQ_C2T_pv         Fully corrected C→T pointing quaternion
alpha_pv               (az, alt, roll) = cameraQ_C2T_to_azaltroll(cameraQ_C2T_corr)
delta_pv               (RA, Dec, PA)   = pyephem(az, alt, roll)
```

### 3.2 Inverse Kinematics — Sky → Motors Angular Position

Converts a target sky orientation into the motor angles required to achieve it. Undoes
corrections in exact reverse order of the forward chain. No `corrQ_RBC⁻¹` is needed as
RBC is applied at the measurement stage, not in the alignment chain.

```
delta_ref               DSO Target equatorial coordinates (RA, Dec, PA)
    │
    ▼ delta2body(delta_ref) or pyephem.body(Orbital Parameters) 
  body                  Target pyephem body
    │
    ▼ body2alpha
alpha_ref               Target topocentric angles (az, alt, roll)
cameraQ_C2T_ref         Target C→T quaternion = azaltroll_to_q(*alpha_ref)
    │
    ▼ Frame Transform topoQ_to_baseQ = corrQ_roll⁻¹ ∘ corrQ_LGC⁻¹ ∘ alignQ_B2T⁻¹ ∘ cameraQ_C2T_ref
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
    ▼  Constrain (acceleration limit Ka, velocity limit Kv)
omega_op                Control output velocity → motor commands                            
```

---

### 3.3 Inverse Kinematics — Sky → Motors Angular Velocity (Feed Forward)

Converts the rate of change of the sky target into motor joint rates for sidereal tracking
feed-forward. The Jacobian `J(theta_adj)` is expressed in the **B frame**, so `omega_T`
must be converted to `omega_B` before the solve. No `corrQ_RBC⁻¹` is needed — RBC is
already accounted for in `theta_adj` and therefore in the Jacobian.

```
cameraQ_C2T_ref         Target C→T quaternion (from last two control steps)
    │
    ▼  calculate_angular_velocity(cameraQ_C2T_ref_last, cameraQ_C2T_ref, dt)
omega_T                 Angular velocity of sky target in T frame
    │
    ▼  topoVec_to_baseVec(omega_T, cameraQ_C2T_pv)
    │  Undo T-frame corrections and rotate T → B:
    │  corrQ_roll⁻¹(T) → corrQ_LGC⁻¹(T) → alignQ_B2T_inv(T→B)
omega_B                 Angular velocity in B frame
    │
    ▼  J⁻¹(theta_adj) · omega_B
theta_dot               Motor joint rates
    │
    ▼  degrees(theta_dot)
omega_ff                Feed-forward motor joint rates
```

---

### 3.4 QUEST Alignment Optimisation

QUEST finds the optimal `alignQ_B2T` that minimises the angular residual between
IMU-predicted and plate-solved observed positions across all sync points.

Raw `alpha_raw` values (`p_az`, `p_alt`, `p_roll`) are stored in sync history. RBC is
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

The Polaris IMU systematically mis-reports the camera rotation angle depending on the
mechanical configuration of the three motor axes. Because the same Az/Alt pointing can
be reached at different rotation angles — requiring different M3 positions — this error
varies with mechanical configuration and cannot be corrected by QUEST's single
rigid-body alignment.

#### Root Cause

M3 (theta3) controls the camera up-vector rotation. The IMU has two coupled encoder
errors in M3:

| Coefficient     | Physical Meaning                                                                 |
|-----------------|----------------------------------------------------------------------------------|
| `roll_model_a`  | **Gain error** — M3 reports slightly less rotation than actually occurred. Scales with altitude because a roll error projects onto Az by `tan(alt)` as azimuth lines converge toward the zenith. Hardware characteristic of the Polaris unit (encoder linearity, mechanical flex in M3 arm). Stable across setups and SPA alignments. |
| `roll_model_b`  | **Zero-point offset** — IMU believes theta3=0 but the camera up-vector is not quite level. Residual bias at zero altitude independent of how far M3 has rotated. Also a hardware characteristic, stable across setups. |

#### Discovery and Calibration

The error was discovered by plate-solving ~1000 images across a porcupine grid of
Az/Alt/Roll positions using Single Point Alignment (no QUEST). Three components of
`dev_roll` (solved − predicted) were identified:

| Component | Description                                              | Handled by        |
|-----------|----------------------------------------------------------|-------------------|
| [1] Global SPA bias    | ~2.5° constant roll offset from SPA-only alignment | QUEST (any sync point) |
| [2] Polar misalignment | ~0.9° sinusoidal Az-dependent variation from mount tilt | QUEST (multi-point sync) |
| [3] Rotation bias      | Roll-dependent residual — `f(p_roll, p_alt)` | RBC — QUEST cannot fix this |

Component [3] is what RBC corrects. After removing [1] and [2], the residual follows:

> roll_error (arcmin) = (roll_model_a · tan(alt) + roll_model_b) · p_roll

Fitted from calibration data: R² = 0.995 for slope vs tan(alt), per-cell R² > 0.96.

To recalibrate, use `fits_extract.py`:

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