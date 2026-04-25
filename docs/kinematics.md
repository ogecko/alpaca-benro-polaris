[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)



# Alpaca Benro Polaris Driver — Kinematics Reference
[Overview](#1-overview) | 
[QUEST](#21-quest-alignment-optimisation) |
[Slew & Center](#22-slew--center-correction) |
[Tilt Correction](#23-mechanical-alignment-corrections) |
[PEC](#24-predictive-error-correction-pec) |
[Base](#31-base-frame-b---representations-and-conversions) | 
[Topo](#32-topocentric-frame-t---representations-and-conversions) | 
[Equatorial ](#33-equatorial-frame-e---representations) | 
[Forward Flow](#41-forward-kinematics--motors--sky-angular-position) | 
[Inverse Flow](#42-inverse-kinematics--sky--motors-angular-position) | 
[Feed Forward](#43-inverse-kinematics--sky--motors-angular-velocity-feed-forward) | 


## 1. Overview

The Benro Polaris is a 3-axis motorised camera mount. Controlling it precisely requires
transforming between four reference frames: the camera sensor, the mount base, the local
sky, and the celestial sphere. This document defines those frames, the variables and
quaternions that live in each, and the kinematic optimisation and chains that connect them.


---
## 2. Kinematics Optimisation
The Alpaca Driver achieves superior tracking performance through a multi-layered suite of kinematic corrections that address both global and local mechanical errors. At its foundations is the QUEST model in Multi-Point Alignment. Layered on top of this are corrections for Sync Residuals and Rotation Bias.

### 2.1 QUEST Alignment Optimisation

#### **I. What it is and What it Solves**
**QUEST (QUaternion ESTimator)** is an advanced mathematical framework used in Multi-Point Alignment (MPA) to calculate the most accurate relationship between your Polaris mount and the night sky. In the context of the Alpaca Driver, it is a **closed-form, quaternion-based solution** designed to solve "Wahba’s problem": determining the optimal rotation that aligns a set of predicted sensor vectors with observed "ground-truth" vectors from plate solving.

Because the Benro Polaris is an **Alt/Az/Roll mount**, it lacks a physical axis naturally aligned with Earth’s rotation. This makes tracking complex, as all three motors must coordinate perfectly to follow a target. QUEST solves several critical hardware and environmental challenges that standard software cannot:
*   **Mechanical Imperfections:** It compensates for **cone error, polar misalignment, and general mechanical offsets**.
*   **Tripod Tilt:** A major advantage of QUEST is that **users no longer need to obsess over leveling their tripod**, as the model mathematically detects and corrects for tilt.
*   **Tracking Accuracy:** It minimizes the angular residuals (errors) between where the mount *thinks* it is pointing and where it *actually* is, leading to superior sidereal tracking for long-exposure deep-sky photography.

#### **II. Integration with Single Point Alignment (SPA)**
The Alpaca Driver supports two distinct modes: **Single-Point Alignment (SPA)** and **Multi-Point Alignment (QUEST/MPA)**. 
*   **SPA (The Foundation):** This mirrors the standard Polaris method by syncing to one known celestial position. While simple, it relies on **precise tripod leveling** and is highly susceptible to drift because it cannot account for complex geometric errors.
*   **QUEST (The Advanced Layer):** QUEST fits "on top" of the basic alignment by utilizing **three or more sync points** to build a detailed 3D correction model. Instead of a single global offset, QUEST finds the **optimal rotation (alignQ_B2T)** that transforms the mount's "Base Frame" into the true "Topocentric Frame" (the actual sky). 

By using QUEST, the driver can correct for the fact that a sync point taken in the East might require a slightly different correction than one taken in the West due to tripod tilt or mechanical flex.

#### **III. The Mathematics of the Model (Briefly)**
QUEST operates by minimizing a **quadratic loss function**, which is essentially the sum of the squared differences between pairs of reference vectors (stars) and measured vectors (mount sensors). 
1.  **Vector Pairing:** Each sync point provides a pair of vectors: the **predicted direction** from the mount's internal sensors and the **observed direction** from a plate solve.
2.  **Davenport Matrix:** The algorithm constructs a specialized matrix (known as a **Davenport Matrix**) from the weighted outer products of these vector pairs.
3.  **Eigenvector Solution:** The "optimal" alignment is found by identifying the **eigenvector with the largest eigenvalue** of that matrix. This provides a **unit quaternion** that represents the best-fit rotation for the entire system.

#### **IV. How to Use QUEST and Get the Best Results**
To achieve high-precision results, you must move from simply "syncing" to **strategic modeling**:

*   **Enable MPA:** Ensure Multi-Point Alignment is enabled in the Alpaca Pilot App settings or alignment page.
*   **Point Selection (The Rule of Three):** You must provide **at least three sync points** to allow the QUEST algorithm to begin building a model.
*   **Strategic Geometry:** 
    *   **Celestial Pole:** Always perform a plate solve and sync at the **Celestial Pole** (North or South). This ensures the model has an anchored reference for Earth’s rotation axis.
    *   **Target Trajectory (DSO Arc):** For the highest accuracy during imaging, place additional sync points **along the trajectory (arc)** that your target object will follow during the night. QUEST provides the best results when it is interpolating between points rather than extrapolating far away from them.
*   **Monitor Residuals:** Use the **Alignment page in Alpaca Pilot** to review "model residuals". This shows how well the QUEST model fits each sync point. Aim for residuals in the **arc-seconds**; if a point shows residuals of whole degrees, it should be deleted as it is likely a bad solve.
*   **Persistence:** From version 2.2 onwards, your QUEST model is **saved to disk**. You can restart the driver or your MiniPC mid-session without losing your refined alignment.
*   **Local Refinement:** The driver also applies a **Local Gaussian Correction (LGA)** on top of the QUEST model, which further eliminates any tiny remaining residuals specifically around your last sync point.

---
### 2.2 Slew & Center Correction

#### **I. What it is and What it Solves**
In astrophotography, the **Slew & Center** operation is a critical workflow where the mount slews to a target, performs a plate-solve to verify its position, and then makes a corrective slew to center the object, repeating the process until it is centered perfectly. The primary aim of **Slew & Center Correction** is to speed up this process by **reducing the number of correction slews** needed to zero in on a target. 

Without this correction, even a high-quality global alignment model (like QUEST) may have a small residual error at any given sky position. When a controlling application (such as NINA) performs a corrective slew based on a residual error, it may require several iterations to narrow in on the target. If the residual at the target is large and you have configured a very low pointing tollerance, the Slew & Center operation may struggle to complete.

#### **II. The Challenge: Global vs. Local Accuracy**
The QUEST algorithm finds a global optimum by fitting a single rigid-body rotation across all available sync points. While this provides excellent average accuracy across the entire sky, it cannot perfectly satisfy every individual sync point simultaneously. 

This leaves a **residual pointing error**, the difference between the model's predicted position and the actual observed plate-solved position. To achieve near-instant centering, the driver must account for this residual immediately after a sync occurs.

#### **III. Three Approaches to Correction**
The Alpaca Driver utilizes three distinct strategies to handle these residuals, ensuring the mount's "Present Value" matches the sky as accurately as possible:

1.  **Tracking Optimised Correction (TOC):**
    In this approach, you disable Slew & Center Correction, ie no correction is made to optimise slew and center operations. The QUEST model is maintained as globally optimal for sidereal tracking.
    
2.  **Zero Last Residual (ZLR):**
    In this approach, the driver forces the QUEST model to ensure the **last sync point always has a zero residual**. When a new sync is performed, the model essentially "shifts" its understanding of the sky so that the current orientation is perfectly anchored to the observed coordinates. This provides an immediate, absolute correction for the current target but can affect the global fit of the rest of the model.

3.  **Local Gaussian Adjustment (LGA):** (Recommended)
    LGA is a more sophisticated method that corrects the residual **locally around the most recent sync point** without disrupting the global integrity of the QUEST model. It applies the full correction at the exact sync location, then gracefully fades that correction both spatially and temporally. As the mount moves aways from the last sync point (σ = 10 degrees), and as time passes (σ = 3 minutes), the adjustment automatically decays back to the pure QUEST model. This ensurs the system smoothly returns to the underlying global solution.

#### **IV. The Mathematics of LGA**
LGA uses a **Gaussian weighting function** to determine how much of the local residual should be applied based on the angular distance from the last sync point. The correction fades to identity (zero additional correction) as the distance increases.

The formula for the weight is:

    weight = exp(−angular_distance² / (2 · sigma²))

*   **angular_distance:** The angular separation between the current pointing orientation and the orientation recorded at the last sync point.
*   **sigma:** This is the "spread" of the correction, with a **default value of 15°**.
*   **At the Sync Point:** The weight is 1.0, meaning the **full residual correction** is applied.
*   **At 15° Away:** The weight drops to approximately 0.61 (61% correction).
*   **At 30° Away:** The weight drops to approximately 0.14 (14% correction).
*   **Beyond 45°:** The weight is less than 0.05, meaning the LGA is effectively inactive and the mount relies solely on the QUEST model.

#### **V. Operational Benefits**
*   **Faster Centering:** By eliminating the local residual at the target, the first "corrective slew" issued by imaging software is far more likely to be the only one needed.
*   **Seamless Transitions:** Because the correction uses a Gaussian fade, there are no mechanical discontinuities or "jumps" as the mount moves across the sky.



---
### 2.3 Mechanical Alignment Corrections

#### **I. What it is and What it Solves**
**Mechanical Alignment Corrections** is a specialized pointing model that compensates for systematic, non-rigid errors caused by physical axis misalignments within the Benro Polaris mount. Unlike global errors like tripod tilt or polar misalignment, which are "rigid" and affect the entire sky equally, these mechanical errors are **orientation-dependent**. The magnitude of the error fluctuates based on the mount's orientation, specifically its **Altitude** and **Roll Angle** positions.

Without these corrections, sync points taken at different rotation angles or altitudes would provide contradictory data, preventing the **QUEST** alignment algorithm from converging on a stable solution. By modeling these hardware-specific traits, the driver ensures the alignment model receives "clean" data for high-precision pointing across the entire sky.

### **II. Benefits of the Model**

Enabling the **Mechanical Alignment Corrections** within the Alpaca Driver will improve the precision of the Benro Polaris platform. By layering **Mechanical Alignment Corrections** and **QUEST Alignment**, the system achieves a level of pointing and tracking fidelity that overcomes the inherent geometric limitations of the Alt/Az/Roll hardware.

#### **A. High-Precision Multi-Point Alignment**
The first primary effect of enabling the model is a **significant increase in the accuracy of Multi-Point Alignment (MPA)**. 
*   **Smaller Residuals:** Without these corrections, mechanical misalignments (such as axis tilts) cause the mount to report contradictory data depending on its orientation. This prevents the QUEST algorithm from converging on a stable global solution. 
*   **Consistent Data:** By applying mechanical corrections at the measurement stage, the driver provides "clean," consistent data to the alignment model. This allows the QUEST estimator to find a tighter mathematical fit, resulting in **considerably smaller residuals**

#### **B. Enhanced Slew and Center Accuracy**
The second primary effect is that **Slew and Center operations become more accurate across the entire sky**, especially at challenging orientations.
*   **Extreme Orientations:** The magnitude of mechanical errors in the Polaris hardware grows dramatically as the mount points upwards or utilizes large roll angles, sometimes reaching errors of over 200 arcminutes. The model predicts and negates these errors in real-time within the kinematic chain.
*   **Reduced Iterations:** Because the model accounts for these complex deviations, the mount's predicted position aligns much more closely with the true celestial coordinates. This ensures that imaging applications like N.I.N.A. can center a target with far **fewer corrective slews**, often achieving a perfect center on the first attempt.
*   **Global Reliability:** This increased precision is not limited to the area around a single sync point; the combined model ensures reliable pointing even when moving between targets in different parts of the sky or at large roll angles.

#### **C. Improved Guiding Performance**
For users employing a **guide scope** and auto-guiding software (such as PHD2), the advanced model provides a superior foundation for fine tracking corrections.
*   **Precise Pulse Translation:** Auto-guiding relies on the driver to translate equatorial (RA/Dec) pulse commands into coordinated motor-level adjustments (M1, M2, and M3). The Mechanical Alignment model ensures this coordinate transformation is highly accurate regardless of the mount’s orientation.
*   **Reduced Axis Cross-Coupling:** Because the Polaris is not a traditional equatorial mount, RA and Dec pulses must be carefully decomposed into multi-axis motor movements. The refined model minimizes "cross-coupling", where a correction in one axis causes an unintended shift in another, which is a common challenge for Alt/Az mounts.
*   **Lower RMS Error:** This mathematical precision allows guiding applications to settle faster and maintain a **lower overall RMS error** (often between 1.3 to 3.0 arc-seconds), which is essential for capturing sharp stars during long-exposure imaging.

Ultimately, these benefits provide the stable foundation required for professional-grade sidereal tracking and long-exposure imaging.

#### **III. The Mechanical Model Parameters**
The model identifies several fixed mechanical parameters of the mount hardware, derived from extensive analysis of "sky survey grids" (large-scale plate-solved datasets), captured at various roll angles. These fitted parameters are stored as coefficients in the `config.toml` and key parameters can be viewed and edited from the Alignment Page in Alpaca Pilot.

*   **M3 (Astro) Axis Tilt:** The physical M3 motor rotation axis may be slightly tilted from the ideal camera vertical axis. It may be tilted or cantered towards the boresight or M2 Axis. This tilt is decomposed into three components:
    *   **Altitude Component (`m3_tilt_dm2`):** Sweeps the camera boresight in altitude as the M3 axis rotates. Introduces residual errors into the M2 axis.
    *   **Azimuth Component (`m3_tilt_dm1`):** Sweeps the camera boresight in azimuth as the M3 axis rotates, an effect modulated by the current altitude. Introduces residual errors into the M1 axis.
    *   **Roll Component (`m3_tilt_dm3`):** Sweeps the camera boresight in roll, geometrically linked to the Azimuth Axis residual. Introduces residual errors into the M3 axis.
*   **M2 (Altitude) Axis Tilt:** The physical M2 motor rotatation axis may not be perfectly perpendicular to M1 (Azimuth), and can produces a sinusoidal altitude error.
    *   **Amplitude (`m2_tilt_dm2_amp`):** The peak magnitude of the altitude error. Introduces residual errors into the Altitude in a sinusoidal manner as M2 rotates.
    *   **Zero Point (`m2_tilt_dm2_zero`):** The altitude angle where the M2 error is zero, typically near or above the horizon.
*   **Axis Offsets:** Fixed user defined offsets for each motor (`m1_offset`, `m2_offset`, `m3_offset`) to help fine tune polar alignment.

#### **IV. The `fits_extract.py` Cailibration Workflow**
While these parameters can be enabled and adjusted from the Alpaca Pilot Page, the Driver provides a utility **`fits_extract.py`** to calibrate these paramters for your specific mount. You will need an astro camera capable of storing FITS file. This is intended for advanced users only.

The workflow to calibrate your mount includes:

1.  **`-extract`:** Processes a directory of FITS images to read WCS (World Coordinate System) headers from plate solves and creates a permanent CSV of raw observations comparing Polaris's predicted position (`p_*`) with the solved truth (`s_*`).
2.  **`-model`:** Uses the extracted CSV to fit the mechanical coefficients listed above alongside the QUEST alignment. It generates a `{prefix}model.txt` containing the optimized parameters.
3.  **`-validate`:** Compares the fitted model against the original data (or a subset of "out-of-sample" data) to confirm the reduction in residuals before you commit the values to your configuration.

#### **V. How to Perform Your Own Calibration**
While default coefficients are provided, advanced users can fine-tune their mount using the following workflow:

1. **Data Collection:** Using a pano grid with roll variation, capture FITS images covering a wide range of altitude, azimuth, and roll positions. Aim for full coverage of the roll range (±50°) at multiple altitudes (20°–65°). Ensure all corrections are disabled while collecting the images ie only SPA, disable MPA, SCC, LGA, ZLR, MAC, PEC.
2. **Plate Solving:** Run **ASTAP** in batch mode to solve all captured images. ASTAP must write the WCS solution directly into the FITS headers.
3. **Extraction:** Run `python fits_extract.py -extract`. This reads the FITS headers and builds a CSV comparing predicted positions with plate-solved ground truth.
4. **Modelling:** Run `python fits_extract.py -model`. This fits the RBC coefficients (`m3_tilt_dm2`, `m3_tilt_dm1`, `m2_tilt_dm2_amp`, `m2_tilt_dm2_zero`) to your data and writes them to a JSON file.
5. **Application:** Copy the fitted parameters into your **`config.toml`** file.


#### **VI. Important Implementation Details**
*   **Stability:** These coefficients reflect the physical manufacturing of your specific unit; they are independent of your site's level or polar alignment and do not need frequent recalculation.
*   **Forward Kinematics:** Corrections are applied within the **forward kinematic model** (`apply_mechanical_corrections`) before sky coordinates are calculated. This ensures the QUEST algorithm receives consistent data regardless of the mount's orientation.
*   **Persistence:** Once defined in the configuration, these corrections are applied automatically at the measurement/telemetry stage of the control loop.


#### **VII. Mechnical Correction Magnitude (arcmin) at specific Roll and Altitud Orientations**

|              Roll |   -70° |   -60° |   -50° |   -40° |   -30° |   -20° |   -10° |    +0° |   +10° |   +20° |   +30° |   +40° |   +50° |   +60° |   +70° | 
|-------------------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
|**Altitude 70°**   |   514' |    82' |    80' |    77' |    75' |    73' |    72' |    72' |    72' |    73' |    75' |    77' |    80' |    82' |   514' | 
|**Altitude 60°**   |    87' |    82' |    76' |    71' |    66' |    62' |    60' |    60' |    60' |    62' |    66' |    71' |    76' |    82' |    87' | 
|**Altitude 50°**   |    96' |    87' |    77' |    66' |    57' |    51' |    47' |    46' |    47' |    51' |    57' |    66' |    77' |    87' |    96' | 
|**Altitude 40°**   |   114' |   101' |    85' |    68' |    52' |    40' |    33' |    31' |    33' |    40' |    52' |    68' |    85' |   101' |   114' | 
|**Altitude 30°**   |   141' |   124' |   103' |    79' |    54' |    32' |    18' |    15' |    18' |    32' |    54' |    79' |   103' |   124' |   141' | 
|**Altitude 20°**   |   175' |   155' |   130' |   100' |    67' |    35' |    10' |     1' |    10' |    35' |    67' |   100' |   130' |   155' |   175' | 
|**Altitude 10°**   |   214' |   193' |   165' |   131' |    93' |    54' |    21' |    18' |    21' |    54' |    93' |   131' |   165' |   193' |   214' | 
|**Altitude  0°**   |   257' |   235' |   206' |   172' |   132' |    89' |    48' |    34' |    48' |    89' |   132' |   172' |   206' |   235' |   257' |

### 2.4 Predictive Error Correction (PEC)

#### **I. What it is and What it Solves**
**Predictive Error Correction (PEC)** is a technique used to mitigate systematic, repeating tracking errors caused by mechanical imperfections in a mount's drive system, such as gear tooth irregularities or motor inconsistencies. While the Benro Polaris hardware is excellent, its inherent mechanical imprecision and gear-driven nature can lead to "periodic error", ie small, predictable oscillations in tracking that cause stars to trail during long exposures.

PEC solves this by identifying these repeating patterns and applying proactive corrections. Instead of just reacting to a star moving off-center, a predictive system anticipates the movement based on previous cycles and counteracts it before the error becomes visible in the image.

#### **II. Implementation: External Reliance**
Currently, the **Alpaca Driver does not have a native, internal PEC recording and playback feature**. Instead, the system relies entirely on external **auto-guiding applications**, most notably **PHD2**, to handle the logic of error detection and prediction.

The workflow functions as a high-speed feedback loop:
1.  **PHD2** monitors a guide star and calculates the deviation from its expected position.
2.  Using its internal algorithms (such as the **Predictive PEC** or **Proactive PEC** guide algorithms), PHD2 models the periodic error.
3.  PHD2 sends **pulse-guiding correction commands** via the ASCOM/Alpaca interface to the driver.
4.  The Alpaca Driver refines the target’s equatorial setpoints and translates these into precise, coordinated motor-level adjustments (M1, M2, and M3) to negate the error.

#### **III. PHD2 Predictive Modeling Summary**
PHD2’s approach to predictive correction is built into its "Brain" settings and advanced guiding algorithms. It employs a sophisticated mathematical approach to tracking:
*   **Cycle Analysis:** The software observes the mount's behavior over one or more worm gear cycles to identify the frequency and amplitude of the periodic error.
*   **Gaussian Process Regression:** In its most advanced "Predictive PEC" algorithm, PHD2 uses Gaussian processes to model the non-linear errors of the mount and predict future deviations.
*   **Pulse Translation:** Once an error is predicted, PHD2 issues a "pulse" of a specific duration. The Alpaca Driver interprets this as a temporary velocity change, adjusting the mount's tracking rate for the duration of the pulse to keep the star centered.

#### **IV. How to Use and Get the Best Results**
To achieve the best predictive results with the Benro Polaris, focus on the following configuration steps in PHD2 and the Alpaca Pilot App:

*   **Multi-Star Guiding:** Always enable **"Use Multiple Stars"** in PHD2’s Advanced Settings. This provides a much cleaner signal for the predictive algorithm by averaging out atmospheric turbulence (seeing), preventing the PEC model from trying to "chase the wind".
*   **Proper Calibration:** Ensure you calibrate PHD2 near the **celestial equator and the meridian**. This is where the mount's movement is most sensitive and provides the most accurate data for the predictive model.
*   **Optimize Guide Rates:** Set the **Guide Rate** in the Alpaca Pilot Settings (typically **0.75x or 1.0x Sidereal**). If the predictive algorithm causes the mount to oscillate or over-correct, lowering this rate can smooth the response.
*   **Monitor Residuals:** Use the **PHD2 Graph and Stats** to monitor performance. The Polaris is capable of achieving an **RMS Error of 1.5 to 3.0 arc-seconds** when the predictive model is correctly tuned.
*   **16-Bit Camera Mode:** Configure your guide camera for **16-bit mode** and high ADU saturation values to provide PHD2 with the highest possible bit-depth for identifying subtle star movements.

#### **V. Important Considerations**
*   **Sidereal Only:** PEC via auto-guiding is designed for **sidereal tracking** of DSOs and stars. It is not suitable for Lunar, Solar, or custom orbital tracking.
*   **Not a Total Cure:** While PEC via PHD2 is a powerful fine-correction tool, it cannot compensate for major mechanical issues like cable drag, severe tripod instability, or poor initial alignment.
*   **Driver Refinements:** Starting with version 2.2, the driver has **refined pulse-guiding accuracy** by incorporating PID feed-forward control, which ensures that external PEC commands from PHD2 are executed with higher fidelity.

---

## 3. Reference Frames

Each frame has a fixed set of basis axes. The scale of each reference frame is arbitrary, since Polaris kinematic mathematics is angle-based, and quaternions are defined on a unit sphere. Vectors and quaternions are tagged with
the frame they are expressed in.

| Frame | Name | Description | `+X` axis | `+Y` axis | `+Z` axis |
|-------|------|-------------|-----------|-----------|-----------|
| **C** | Camera Frame | Camera sensor geometry, independent of pointing direction, negative Z axis is camera boresight, looking skywards.  |  Image "up"             | Image "left"          | -ve boresight            |
| **B** | Base Frame   | Mechanical frame as bolted to tripod (assuming Az 180, Alt 45 after All Axis Reset). Differs from T by Multi-Point Alignment (`alignQ_B2T`)| Axis 2 red button side | Back SD card side     | Axis 1 up            |
| **T** | Topo Frame  | True local sky frame at observing site, with all corrections applied. Home of Az, Alt, Roll   | East                   | North                 | Zenith               |
| **E** | Equatorial Frame   | Earth-centred celestial frame, with all corrections applied. Home of RA, Dec, PA       | RA = 0h, Dec = 0°      | RA = 6h, Dec = 0°     | North Celestial Pole |

---

### 3.1 Base Frame (B) - Representations and Conversions

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
| `theta_dot`    | `omega_base`      | `= J(theta) · theta_dot` | joint rates → B frame angular velocity.  |
| `omega_base`   | `theta_dot`      | `= J⁻¹(theta) · omega_base` | B frame angular velocity → joint rates. Used to calculate FF joint rates. |

#### Variable Suffixes

Suffixes distinguish the level of processing applied to a mechanical orientation variable.

| Suffix   | Applies to  | Meaning                                                          |
|----------|-------------|------------------------------------------------------------------|
| `_raw`   | orientation | Uncorrected value direct from device                             |
| `_state` | orientation | Kalman Filter smoothed/estimated value                           |
| `_adj`   | orientation | Mechanically adjusted after KF + PEC + RBC                       |
| `_pv`    | orientation | Process Variable after KF + PEC + RBC + QUEST + LGA + Roll       |
| `_sp`    | orientation | User Set Point target value (pre slew offset and pulse guiding)  |
| `_ref`   | orientation | Final Reference target value for the control loop                |
| `_op`    | velocity    | Control output velocity for the motors                           |



---

### 3.2 Topocentric Frame (T) - Representations and Conversions

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

### 3.3 Equatorial Frame (E) - Representations

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
## 4. Kinemtaics Flows


### 4.1 Forward Kinematics — Motors → Sky Angular Position

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
    ▼ Periodic Error Correction, optional (future)
    │
    ▼ Frame Transform baseQ_to_topoQ = corrQ_roll ∘ corrQ_LGA ∘ alignQ_B2T ∘ motorQ_adj
    ▼     Rotation Bias Correction (corrQ_RBC)  B Frame
    ▼     QUEST Alignment (alignQ_B2T)          B→T
    ▼     Local Gaussian Correction (corrQ_LGA) T Frame
    ▼     Roll Sync Adjustment (corrQ_roll) T Frame
motorQ_pv              RBC corrected only (B Frame)
cameraQ_pv             Fully corrected C→T pointing quaternion
theta_pv               RBC corrected only (B Frame)
alpha_pv               (a_az, a_alt, a_roll) = q_to_azaltroll(cameraQ_pv)
delta_pv               (a_ra, a_dec, a_pa)   = pyephem(az, alt, roll), used as ASCOM co-ordinates
```

### 4.2 Inverse Kinematics — Sky → Motors Angular Position

Converts a target sky orientation into the motor angles required to achieve it. Undoes
corrections in exact reverse order of the forward chain. 

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
    ▼ Frame Transform topoQ_to_baseQ = corrQ_roll⁻¹ ∘ corrQ_LGA⁻¹ ∘ alignQ_B2T⁻¹ ∘ corrQ_RBC⁻¹ ∘ cameraQ_step
    ▼    Undo Roll Sync Adjustment      (corrQ_roll⁻¹, T frame)
    ▼    Undo Local Gaussian Correction (corrQ_LGA⁻¹, T frame)
    ▼    QUEST Alignment inverse        (alignQ_B2T_inv, T→B)
    ▼    Undo Rotation Bias Correction  (corrQ_RBC⁻¹, B frame)
motorQ_ref              Target C→B quaternion
theta_ref               Target motor angles (θ1, θ2, θ3) = q_to_theta(motorQ_ref)
    │                        two solutions possible (elbow up/down).
    │                        resolved by proximity to last known position.
    ▼  PID Error Signal
error_signal            = theta_ref - theta_pv
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

### 4.3 Inverse Kinematics — Sky → Motors Angular Velocity (Feed Forward)

Converts the rate of change of the sky target into motor joint rates for sidereal tracking
feed-forward. The Jacobian `J(theta_pv)` is expressed in the **B frame**, so `omega_topo`
must be converted to `omega_base` before the solve. No `corrQ_RBC⁻¹` is needed — RBC is
already accounted for in `theta_pv` and therefore in the Jacobian.

```
cameraQ_ref             Target C→T quaternion (from last two control steps)
    │
    ▼  Frame Transform topoQ_to_baseQ 
motorQ_ref              Target C→B quaternion (current)
motorQ_ref_last         Target C→B quaternion (one control step in the past)
    │
    ▼  calculate_angular_velocity(motorQ_ref_last, motorQ_ref, dt)
omega_base              Angular velocity in B frame
    │
    ▼  Inverse Jacobian Solution = J⁻¹(theta_pv) · omega_base
theta_dot               Motor joint rates (radians)
    │
    ▼  degrees(theta_dot)
omega_ff                Feed-forward motor joint rates
```



---
## 5. Summary — Full Kinematic Chain

```
motorQ_raw          (C→B, raw from IMU)
theta_raw / alpha_raw / omega_raw
    │
    ▼  KF + PEC + RBC
theta_pv / motorQ_adj    (B frame, mechanically adjusted)
    │
    ▼  corrQ_RBC           Rotation Bias Correction     B frame
    ▼  alignQ_B2T          QUEST Alignment              B → T
    ▼  corrQ_LGA           Local Gaussian Correction    T frame
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