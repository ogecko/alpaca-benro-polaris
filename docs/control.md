[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./Pilot.md) | [Control](./Control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Advanced Motion Control
[Challenges](#challenges-with-existing-control) | [Rotator](#alpaca-rotator) | [Alignment](#alignment-models) | [Safety](#equipment-safety) | [Filtering](#kalman-filter) | [Speed Controller](#speed-controller) | [PID Controller](#pid-controller) | [Guiding](#pulse-guiding) | [Tracking](#tracking) 

# Challenges with existing Control
PODCAST LINK - [20 - Deep Dive Podcast on Alpaca Benro Polaris V2.0](https://youtu.be/KUBCTnEsnlE)

The Benro Polaris mount, especially with its Astro Attachment, is popular among amateur astrophotographers for its compact design and app-driven interface. But while the hardware is excellent, the software can leave many users frustrated.

When version 1.0 of the Alpaca Driver was launched, it allowed advanced imaging and planetarium software to work with the Polaris. As more people used these applications, limitations quickly surfaced:
- Tracking drift was noticeable during long imaging sessions
- Promised features like three-star alignment never materialized
- Users lacked the precision tools needed for serious deep sky work

With version 2.0 of the Alpaca Driver, we introduce a complete rewrite of the motion control system. The motors are now driven using advanced algorithms that dramatically improve tracking accuracy, responsiveness, and stability.

This guide covers describes each of the new motion control concepts introduced in V2.0

# Alpaca Rotator
VIDEO DEMO - [23 - Alpaca Rotator Framing in Nina and Stellarium](https://youtu.be/_Swd-jIyQis)



The Alpaca Rotator feature is an advanced capability within the Alpaca Benro Polaris (ABP) Driver, specifically designed to enhance precision framing and complex imaging sequences for deep-sky astrophotography.

This guide outlines the purpose, setup, control concepts, and practical usage of the Alpaca Rotator, drawing on the capabilities introduced in the version 2.0 driver.

---

## I. Introduction and Core Function

The Alpaca Rotator functionality unlocks and controls the third axis of the Benro Polaris mount.

*   **Primary Purpose:** The main goal of the Alpaca Rotator is to help achieve **better framing of deep sky objects** and assist significantly with **mosaics and panoramas**.
*   **ASCOM Standard:** The feature is implemented by supporting the **ASCOM Alpaca Rotator Interface v3** standard.
*   **Rotation Maintenance:** The rotator enables rotation around the camera’s boresight while **maintaining the existing Azimuth/Altitude (Az/Alt) or Right Ascension/Declination (RA/Dec) coordinates**.
*   **GOTO Enhancement:** Unlike the standard Polaris firmware, the ABP Driver’s new **GOTO commands preserve the roll angle** instead of automatically resetting it to zero after every GOTO operation.

---

## II. Key Concepts: Roll Angle vs. Position Angle

The ABP Driver allows control over rotation using two coordinate systems: Roll Angle (in the geographic system) and Position Angle (in the equatorial system).

### Roll Angle (Az/Alt/Roll)

The roll angle is generally considered **intuitive**.

*   It represents the **angle or tilt of the camera relative to the horizon**.
*   The driver automatically calculates how the mount needs to move all motors to achieve a specified roll (e.g., a 30° roll) while keeping the Azimuth and Altitude coordinates consistent.
*   The roll angle corresponds directly to the rotation of **Motor 3**.

### Position Angle (RA/Dec/PA)

The Position Angle (PA) is a **consistent reference** used for framing that is independent of the observer's location. It is often harder to understand than the roll angle.

*   The Position Angle is defined in the **equatorial coordinate system**.
*   A PA of **0 degrees** means the top of the image frame is pointing toward the **celestial North Pole**.
*   Angles **increase in a counter-clockwise fashion**.

---

## III. Rotator Setup and Control

### Connecting in NINA

To enable rotator control in third-party applications like NINA (Nighttime Imaging 'N' Astronomy):

1.  In NINA’s Equipment setup, navigate to the **Rotator equipment** section.
2.  Perform a **device discovery** to find the Alpaca Rotator.
3.  Connect to the device. NINA will then have **full control of the rotation axis**.

### Control via Alpaca Pilot App

The Alpaca Pilot App offers direct, real-time control over the rotation axis.

*   **Dashboard Viewing:** The **Dashboard** features **Zoomable Radial Dials** that display the mount’s current roll and position angle (PA) coordinates. You can quickly switch between Azimuth/Altitude/Roll and Right Ascension/Declination/Position Angle views.
*   **Direct Input:** You can **click on the set point** and directly enter a numerical value for the desired roll or position.
*   **Presets (Az/Alt Mode):** When in Azimuth/Altitude mode, you can use the **floating action button** on the roll set point to quickly navigate to common presets, such as **zero degrees** or **plus or minus 45 degrees**.
*   **Movement:** The driver calculates the **best way to move the head** to the target roll/PA location, and the green arrow indicates the desired point. Slew commands now support moving by **Azimuth, Altitude, and Roll coordinates**.

---

## IV. Rotator in Imaging Applications

The Alpaca Rotator is crucial for advanced framing techniques, particularly when using software like NINA and Stellarium.

### Framing with NINA

The rotator function is natively integrated with NINA’s framing capabilities.

1.  **Framing Assistant:** In NINA's Framing Assistant, you can **change the proposed rotation angle** (Position Angle) to see the framing adjust visually.
2.  **Rotation View:** Enabling the **rotation view** within the Framing Assistant allows you to change the orientation of the image perspective, which makes the framing process easier.
3.  **Sequenced Correction:** During an imaging sequence, after NINA performs a plate solve and determines the position angle of the captured image, it will **correct any angular offset** by issuing minor adjustments to the rotator to correctly position the panel.

### Mosaics and Panoramas

The rotator enables precise, structured imaging for large targets.

*   **Tiled Mosaics:** When planning a tiled mosaic (e.g., three wide and two high), NINA calculates the Right Ascension and Declination for each panel.
*   **Preserving Alignment:** By enabling **"preserve alignment"** in NINA, the system automatically recalculates the specific position angle for each individual panel, ensuring the overall mosaic results in a rectangular image.

### Integrating with Stellarium

To visualize your framing accurately in Stellarium, an adjustment is necessary.

*   **Coordinate Mismatch:** Stellarium’s internal "rotation angle" setting uses a different frame of reference than the standard ASCOM Position Angle used by the driver and NINA.
*   **Correcting the Angle:** To achieve the same framing in Stellarium as calculated in NINA (e.g., a proposed PA of 140°), you must input the **negative of the Position Angle** into Stellarium’s rotation angle setting (e.g., -140°).

---



# Alignment Models
VIDEO DEMO - [24 - Multi Point Alignment and Tripod Tilt](https://youtu.be/4CMO0R_yphw)

The V2.0 Alpaca Driver re-engineered the alignment and sync interfaces to support two distinct alignment methods, transforming how the Benro Polaris (BP) achieves accurate polar alignment. This guide outlines the features and operational principles of the two primary alignment modes; Single-Point and Multi-Point Alignment. 

### I. Single-Point Alignment (SPA)

Single-Point Alignment (SPA) is the more traditional alignment method supported by the  Driver:

*   **Function:** It **mirrors the standard Polaris method**, syncing the mount to a single known celestial position.
*   **Correction:** Corrections resulting from the sync apply globally.
*   **Requirement:** This method **relies on precise tripod leveling**.
*   **Limitation:** SPA can be susceptible to drift.
*   **Usage:** Alignment can be achieved simply with a **single plate-solve**. 

When using the Pilot App for initial setup, you can skip the Compass Align and Star Align steps, as the driver will use a default value (assuming the mount is pointing south at 45 degrees altitude). The first plate-solve will correct any misalignment.

The Single Point Alignment is simpler to perform and is still a valid method for alignment of your Benro Polaris. Only progress to Multi Point Alignment when you are prepared to monitor and fine tune the alignment model.

### II. Multi-Point Alignment (MPA) 

Multi-Point Alignment (MPA), is the advanced alignment feature recommended for achieving high precision:

*   **Function:** This method builds a detailed **correction model** from three or more known synchronization (SYNC) positions.
*   **Compensation:** The model compensates for multiple sources of error that a single point cannot correct, including **tripod tilt, polar misalignment, cone error**, and other mechanical offsets.
*   **Algorithm:** The technology is adapted from the **QUEST algorithm**, which uses a closed-form, quaternion-based solution to provide a precise result.
*   **Benefit:** A major advantage of MPA is that users **no longer need to obsess over leveling their tripod**, as the model is designed to detect and correct for tilt.
*   **Procedure:** To perform  Multi Point Alignment, you simply **perform multiple synced plate solves**. Each new sync automatically adds to the Driver's knowledge of the Polaris alignment at different orientations and times.


Here is the procedure for performing Multi-Point Alignment and information regarding the necessary synchronization points, based on the version 2.0 driver and its integration with applications like NINA (Nighttime Imaging 'N' Astronomy).

## III. Performing Multi-Point Alignment

### A. Initial Mount Setup

Before starting the alignment process, ensure the mount is prepared and connected to the ABP Driver:

1.  **Polaris Mode:** Power on the Benro Polaris (BP) mount and use the BP App to switch it to **Astro Mode**.
2.  **Skip Standard Alignment:** You can **skip** the standard Benro Polaris **Compass Align** and **Star Align** steps, as the driver will use default values (assuming the device is pointing South at 45 degrees altitude).
5.  **Physical Setup:** Mount your camera, place the tripod outside, and **level the Benro Polaris as accurately as possible** (though the MPA model compensates for tilt, good leveling remains important for accuracy).
6.  **Focus:** Perform a NINA Autofocus run.

### B. Initiating Alignment via Plate Solving 

The Multi-Point Alignment model is built by performing synchronization (`SYNC`) operations, typically initiated after a **plate solve**. A single, accurate sync is generally sufficient to align the Polaris initially:

1.  **Manual Plate Solve and Sync:** Perform a **manually initiated plate-solve and sync**.
    *   Plate solving uses the camera image to identify the star patterns and precisely determine the mount’s orientation.
    *   The ABP Driver automatically aligns the Benro Polaris with the resolved coordinates whenever a `Sync` command is performed.
2.  **Alignment Confirmation:** Once this first plate-solve and sync is successful, the Polaris is now considered aligned.

### C. Polar Alignment

To assist the multi-point model to be as polar aligned as possible, we recommend performing a plate-solve at your Celestrial Pole. This will ensure a point for the Celestrial Pole is in the model and help reduce residual error at that location. Use the following procedure:
1. **Launch Alpaca Pilot**: from a web browser or via Nina Equipment setup cogs.
2. **Search the catalog**: By typing 'pole' into the search bar
3. **Initiate Navigation**: Once a target is selected, click the appropriate GOTO button to immediately navigate to that location. 
4. **Wait for Completion**: Ensure the mount has fully stopped before proceding
5.  **Manual Plate Solve and Sync:** Perform a **manually initiated plate-solve and sync**.

### D. Target Trajectory Alignment

Any remaining points in the model should be placed along the trajectory of your imaging target. You can perform just one plate-solve at your target, or if you are performing a long imaging session you may want to perform a couple of plate-solves along its trajectory. 
1. **Navigate to your target**: Use Alpaca Pilot, Stellarium or Nina to select and navigate to the current location of your target
2. **Naviagate along target trajectory**: Use Alpaca Pilot to decrease the Right Ascension position by an hour or two. Enter 'd-2' into the Right Ascension setpoint field.
2. **Wait for Completion**: Ensure the mount has fully stopped before proceding
5.  **Manual Plate Solve and Sync:** Perform a **manually initiated plate-solve and sync**.
1. **Navigate back to your target**: Navigate back to the current location of your target
2. **Wait for Completion**: Ensure the mount has fully stopped before proceding
5.  **Manual Plate Solve and Sync:** Perform a **manually initiated plate-solve and sync**.

### E. Review Model Residuals

After you add any additional sync points to the model, you should review the model residuals on the Alignment page in Alpaca Pilot. When the Driver updates the model, it recalculates how well it fits all of the sync points. Any slight deviation between what that sync point said it was and what the model thinks it should have been, will be listed as a residual. The last sync point will always have zero residual. 

The other sync points that are in this list, they might have larger residuals. If you see anything above, say 5°, then you might want to consider deleting that point. And you can delete it by just clicking on the cross next to the point. If you see it above 10 or 20, then I'd definitely remove that point from the multipoint alignment model. You really want to keep them down in the arc minutes. And these are arc seconds. 



## Equipment Safety

VIDEO DEMO - [25 - Home, Park and Motor Angle Limits](https://youtu.be/45EP-DExSOQ)

## Kalman Filter
VIDEO DEMO - [31 - Setting Overrides, Kalman Filtering and PWM](https://youtu.be/aDFKAWBNQHU)

## Speed Controller
VIDEO DEMO - [32 = Calibrating Speed Control for your Polaris](https://youtu.be/U_0-mBDuTjE)


## PID Controller

## Pulse Guiding

## Tracking

