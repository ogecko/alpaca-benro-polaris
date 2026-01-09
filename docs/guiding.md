[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Guiding Users Guide
[Introduction](#why-use-auto-guiding) | 
[Pre-requisites](#2-phd2-guiding-prerequisites) | 
[Equipment Setup](#3-equipment-setup) | 
[Calibration](#4-phd2-calibration) | 
[Auto-Guiding](#5-auto-guiding-with-phd2) 

## 1. Guiding Introduction

>VIDEO DEMO: [27 - Guiding the Alpaca Benro Polaris](https://youtu.be/dn1nLxT5eWw)

Guiding is a general concept that refers to any method used to correct tracking errors during exposure. It includes manual-guiding, auto-guiding, encoder-assisted guiding, and software based corrections. Auto-guiding is a specific form of guiding that uses a guide camera, guide scope, and guiding software to make continuous tracking adjustments automatically.

This document introduces how to use **PHD2** auto-guiding with the **Alpaca Benro Polaris Driver** on a **Benro Polaris mount**. It is intended for users who are new to auto-guiding, as well as those transitioning from unguided imaging.

![PHD2 Main screen](./images/phd2-main1.png)

### Why Use Auto-guiding?

Auto-guiding is used to correct **small tracking errors and drift** that occur during long-exposure or long-session astrophotography. Even with good multi-point alignment and careful setup, small mechanical imperfections, AHRS drift, atmospheric effects, and tracking rate errors may cause stars to slowly trail or drift over time. Autoguiding helps correct many of these issues.

For the Benro Polaris, the **primary benefit of auto-guiding is eliminating drift**, enabling longer more consistent imaging sessions. It’s important to set realistic expectations. Autoguiding cannot fix:

* Poor focus, optical issues, or unfavourable seeing conditions
* Vibrations caused by tripod flexure, ground instability, or wind
* Mechanical binding, balance problems, cable drag or obstructions
* The inherent mechanical in-precision of the Polaris

> Note: Auto-guiding is totally optional. You can still obtain excellent DSO images without the use of Auto-guiding. Auto-guiding is not a replacement for good setup, it is a **fine correction tool**, not a cure-all.

### How does Auto-guiding work?
Auto-guiding is controlled by a separate guiding application that connects to the guiding camera as well as the Alpaca Driver. The guiding application operates by:
* Continuously monitoring a selected guide star (or stars) from the guide camera
* Measuring small deviations from the star’s expected position
* Sending **pulse-guiding correction commands** to the Alpaca Driver

The Alpaca Driver then:
* Refines the target's equatorial setpoints
* Translates these corrections into motor-level adjustments
* Sends the updated motion commands to the Benro Polaris mount

### What Guiding Applications are supported?

The Alpaca Driver exposes pulse-guiding commands through the **ASCOM Alpaca ITelescopeV3 Interface**. Any guiding application that supports this pulse-guiding interface can work with the Alpaca Driver.
The following guiding solutions have been tested with v2.0:

* **CCDciel’s Autoguider** — provides integrated guiding, including star selection, calibration, and corrections. Ideal for macOS and non-NINA platforms.
* **PHD2** (used alongside **NINA**) — PHD2 handles guiding, while NINA manages imaging and dithering (via PHD2)
* **NINA Direct Guider** — enables dithering without a guide scope. Not recommended as we have not seen significant improvements with this solution.

The remainder of this secion will focus on the second solution, using **PHD2**.

## 2. PHD2 Guiding Prerequisites

### 2.1 Hardware Purchases and Software Installation
To perform auto-guiding you will need some additional equipment, including the following. See [Hardware Auto-Guiding Equipment](./hardware.md#guiding-scope-and-camera-optional) for more details.
* A **Guide scope** (eg SVBony SV106 Guide Scope), or an off-axis guider (OAG)
* A **Guide camera** (e.g. ToupTek GPM462M, ZWO ASI120MM, ZWO ASI220MM, etc.)
* Suitable **Mounting equipment** 


You will also need to download and install the following software onto the Mini-PC.
* **ASCOM Platform** - Download latest ASCOM Platform from the [ASCOM Home page](https://ascom-standards.org/index.htm)
* **PHD2 Guiding Application** - Download free PHD2 application from the [PHD2 Download page](https://openphdguiding.org/downloads/)

### 2.2 ASCOM Telescope and Rotator Setup
Once the ASCOM Platform is been installed, you need to use the **ASCOM Diagnostics App** to create a dynamic driver link to the Alpaca Driver's Telescope and Rotator. This step makes the Alpaca Driver's Telescope and Rotator available to all ASCOM-compatible applications, including PHD2, and only needs to be done once.

>Note: Nina does not require the ASCOM dynamic driver link to communicate with the Alpaca Driver, as it connects directly via the Alpaca protocol. Unforuntely, PHD2 on Windows only supports ASCOM, so this setup is necessary.

1. Launch **ASCOM Diagnostics App**
2. Select **Choose and Connect to Device** from **Choose Device** menu
3. Select **Telescope** from the dropdown, then click **Choose**
   * On the **ASCOM Telescope Chooser** dialog, click **Alpaca** from the menubar
   * Click **Discovery Enabled** until it is green
   * Click **Discover Now**
   * Using the dropdown, choose each **NEW ALPACA DEVICE**, Clicking **Ok** twice on each one, until no more new alpaca devices are present in the dropdown.
   * On the **ASCOM Telescope Chooser** dialog, click **Alpaca** again
   * Click **Manage Devices** to list all the new alpaca devices you added.
   * Review the **IP Address** of each Telescope driver listed, and remove all unwanted drivers.
   * Aim to leave only one Telescope driver so it is easier to choose the correct one from PHD2. 
   * Click **Close** when complete.
   * Using the dropdown, choose the **Alpaca Benro Polaris Telescope** you kept
   * Click **Ok**
   * Click **Connect** to confirm the Alpaca Driver Telescope is setup. 
4. Select **Rotator** from the dropdown, then click **Choose**
   * On the **ASCOM Rotator Chooser** dialog, click **Alpaca** from the menubar
   * Click **Discovery Enabled** until it is green
   * Click **Discover Now**
   * Using the dropdown, choose each **NEW ALPACA DEVICE**, Clicking **Ok** twice on each one, until no more new alpaca devices are present in the dropdown.
   * On the **ASCOM Rotator Chooser** dialog, click **Alpaca** again
   * Click **Manage Devices** to list all the new alpaca devices you added.
   * Review the **IP Address** of each Rotator driver listed, and remove all unwanted drivers.
   * Aim to leave only one Rotator driver AND one Telescope so it is easier to choose the correct one from PHD2. 
   * Click **Close** when complete.
   * Using the dropdown, choose the **Alpaca Benro Polaris Rotator** you kept
   * Click **Ok**
   * Click **Connect** to confirm the Alpaca Driver Rotator is setup. 
5. Close the **Device Connection Tester** dialog box
6. Close the **ASCOM Diagnostics App**

## 3. Equipment Setup
Once PHD2 has been installed, you need to perform some initial setup. This includes connecting, focusing and configuring the equipment.

### 3.1 PHD2 Connecting Equipment
Connecting PHD2 to the guide camera and Alpaca Driver (one time setup)
1. Ensure your **guide camera** is physically connected and power it on.
2. Ensure the **Alpaca Driver** is running and connected to the Polaris.
2. Launch **PHD2**
2. Select **Guide** from the **PHD2** menubar, then **Connect Equipment**
3. Choose **New Using Wizard**, from the **Manage Profiles** dropdown 
3. Camera: select your **guide camera** from the dropdown list
4. Scope: set your **Guide scope focal length** eg 190mm for SV106
5. Click **Next**
4. Mount: select **Alpaca Benro Polaris Telescope (ASCOM)** from the dropdown list
5. Click **Next**
5. Leave Adaptive Optices as None (not required), then click **Next**
6. Rotator: select **Alpaca Benro Polaris Rotator (ASCOM)** from the dropdown list
5. Click **Next**
7. Finish the wizard and save the profile
8. Click **Connect All**

### 3.2 Guide Scope and Camera setup
Focusing, Rotating and Aligning the guide camera (one time setup)
1. Ensure your **main camera** is centered on a recognisable landmark, like a powerline tower, tall building, or tall fixed object, as far away as possible. This can be done during twilight hours or even during daytime.
2. Ensure you have a laptop, tablet or phone, near the guide camera. This will allow you to remote into the Mini-PC running PHD2, make guide camera focus and alignment adjustments, and see the effect immediately.
3. Using **PHD2**, connect to all equipment
5. On the bottom left toolbar of the main PHD2 window  
    - Click **Loop Exposures**. Also available from the **Guide** menubar item.
    - Set an appropriate **Exposure Duration** from the dropdown eg 0.01 s
    - Adjust the **Gamma Adjustment Slider** to see the landmark image 
6. Focus the **guide camera**. eg for an SV106 guide scope
    - Set the helical focuser to half way
    - Slide the lipstick **guide camera** in/out to roughtly focus
    - You may need an extension tube attached to the camera to reach rough focus
    - Fine tune the focus with the helical focuser  
7. Rotate the **guide camera** to orient the landmark so it points upwards correctly.
8. Align the **guide camera** with the **main camera**. eg for an SV106 guide scope
    - Loosen the guide scope **mounting screws**
    - Adjust the mounting screws to point the **guide camera** to the exact same position as seen by the **main camera**
9. Instead of using **PHD2** to focus and align the guide camera you may consider using **Nina**. It provides an excellent **cross-hairs overlay** that can assist with alignment. 
    - Using PHD2, disconnect all equipment
    - Using Nina, open the **Image tab** and enable **cross-hair overlay**
    - Connect to the **main camera** and point mount at the landmark
    - Connect to the **guide camera**, then physically focus, rotate and align.
    - Connect back to the **main camera**

### 3.3 Configuring PHD2 Recommended Settings
Using PHD2, configure the following settings for use with the Alpaca Driver.

* Check **Enable Server** from the Tools menu, to allow Nina to work with PHD2
* Set **Exposure Duration** to 0.5 s as a starting point..
* Adjust **Gamma Adjustment Slider** to make stars visible in PHD2.
* Click the **Brain Button** or choose **Advanced Settings** from the **Guide** menu
    - Select the **Guiding** tab of **Advanced Settings**
    - Enable **Use Multiple Stars** to improve guide star stability and robustness, particularly in poorer seeing or when individual stars fluctuate in brightness.
    - Enable **Assume Dec orthogonal to RA** to help PHD2 achieve a successful calibration.  Geometrically, Right Ascension and Declination are always perpendicular. However, guiding software works in camera pixel space, not celestial coordinates. Factors such as targets near the celestial poles, guide camera rotation, small mechanical tolerances, differential flexure, and polar misalignment can cause RA and Dec to appear non-orthogonal to the guider. With the Alpaca Driver’s multi-point alignment, you should have very good polar alignment. With a stable setup and non-polar targets, it’s generally safe to let PHD2 assume Dec is orthogonal to RA. This can help improve the chances of a good calibration.
    - Ensure **Focal Length** and **Pixel size** is set correctly for your guide scope and guide camera
    - Leave all remaining settings at default to start with
![PHD2 Advanced Settings](images/phd2-settings1.png)

### 3.4 Configuring Alpaca Driver settings
Using Alpaca Pilot, configure the following Alpaca Driver guiding settings.

* **Guide Rate** - I typically use **0.75× Sidereal**, but the default **1.0×** also works well in most cases. If you feel the guiding application is pushing the mount around too much, causing it to oscillate, you can reduce the **Guide Rate**. Typically the RA and Dec guide rates are matching. This can be adjusted on the Alpaca Pilot *Settings* page.

* **Sidereal Tracking** - For guiding to work, sidereal tracking **must be enabled** in the driver. The tracking rate must be set to **Sidereal** and auto-guiding is not suitable for Lunar, Solar, or Custom Orbital tracking.

* **PID Tuning** - When autoguiding is active, you can monitor the pulse guide commands and shifts in Right Ascension and Declination Setpoints from the PID Tuning page.

* The **EQ vs Az/Alt Mode** in the Alpaca Dashboard does **not** affect guiding. It only changes which coordinate system is displayed on the radial dials.

<br>

## 4. PHD2 Calibration
Calibration teaches PHD2 how your mount responds to various pulse guiding commands. It uses the calibration data to determine what pulse guiding commands are needed to correct a certain drift or movement of the guide star.

### 4.1 Calibration Process
To Calibrate PHD2, use the Calibration Assistant:
1. On a dark and clear night, slew the Polaris close to your intended DSO target, using Nina, Stellarium or Alpaca Pilot.
2. Using **PHD2**, connect all equipment.
3. Click **Calibration Assistant** from the **Tools** menu item.
4. Note the current **Pointing Location**
5. Enter the **Calibration Location**
    - Enter a **Declination** the same as your current **Pointing Location Declination**
    - Enter a **Meridian offset** greater than ±25°, but below ±80°. ie Exclude near vertical, and near Horizon.  
    - Click **Slew** to move the mount to the **Calibration Location**
6. Click **Calibrate** to being the calibration process, typically takes 1–3 minutes

PHD2 will then start sending a sequence of pulse guide commands, monitoring how the mount moves in response to the commands. It will walk out the Right Ascension axis and back, then do the same for the Declination axis. You can monitor its progress with Alpaca Pilot.

Once the calibration process is complete, PHD2 will sumamrise the results in a popup window. You can then decide whether to **Accept calibration** or **Discard calibration**. You can also review the most recent calibration data by choosing **Review Calibration Data** from the **Tools** menu item.

A good calibration looks like the following image. Red dots indicate measured position for declination change. Blue does indicate measured position for RA change. White dots indicate reverse measurements.
![PHD2 Calibration Results](images/phd2-calibration1.png)

### 4.2 Calibration Errors

As the Alpaca Driver needs to convert RA and Dec pulses into suttle changes in M1-M3 motion speeds there can be some cross-coupling between axes, unlike an equatorial mount. This can mean that the Polaris can be slower to respond to guide pulses, or deviate slightly from expected motion, so calibration may occasionally report warnings or errors. For example:

- **Calibration failed – star did not move enough**    
    Usually due to the **Guide Rate** being too low (increase on Alpaca Pilot Settings)    
    Or the **Calibration Step size** too small (increase in PHD2, Advanced Settings, Guiding ).  
    Monitor the RA and Dec movement from Alpaca Pilot, PID Tuning page, to diagnose further.

- **Calibration failed – RA or Dec did not reverse**    
    PHD2 did not detect movement when reversing RA or Dec direction.  
    Usually due to excessive backlash or mechanical slack or sticktion  
    Try increasing **Guide Rate** or **Calibration Step size**.

- **The RA and Declination angles computed in the calibration are questionable**  
    Check that you enabled **Assume Dec orthogonal to RA**, as this will force the orthogonality error to zero.

### 4.3 Re-Calibration

PHD2 assumes that the mapping of RA and Dec pulses to pixel motion on the guide camera are fixed, as per an Equatorial mount. This implies that the Calibration only needs to be repeated if:

* You physically rotate the guide camera relative to the mounts RA or Dec axis.
* You slew to a new DSO and have a different Position Angle.
* You change the roll angle for framing, indrectly changing the Position Angle.
* You change guide scope or focal length

If you have a separate ZWO Rotator on just the main imaging sensor, and the guide camera is fixed relative to the mount, then you do not need to recalibrate on ZWO Rotator changes.


##  5. Auto-Guiding with PHD2

Once you have calibrated PHD2, auto-guiding with PHD2 is relatively simple. If you have configured Nina to use PHD2, it will automatically run through steps 1 through 4 for you. 
1. Start **PHD2** and **Connect All Equipment**
2. Click **Begin Looping Exposures** to start the guide camera
3. Click **Auto-Select Star** to select a guide star
4. Click **Begin Guiding** to start the auto-guiding process

To monitor the guiding performance, use the **View** menu in PHD2
1. Click **Display Graph** to show the auto-guiding history.
2. Click **Display Target** to show spread of motion of the guide star.
3. Click **Display Star Profile** to show the expanded guide star pixel profile.
4. Click **Display Stats** to summarise the guiding performance.

<br>

Below is a typical Graph and Statistics of an auto-guiding session.

![PHD2 Graph](./images/phd2-graph1.png)

* The Polaris has been tested to be capable of RMS Error of around 1.5 to 3.0 arc-seconds.
* Small oscillations are normal
* Large or runaway corrections indicate setup issues
* Initial results may not be perfect. Allow guiding to settle for a few minutes.


## 6. Final Notes

Guiding with PHD2 and N.I.N.A. can feel **finicky at first**, especially at longer focal lengths. Once dialed in, it dramatically reduces drift and enables longer, cleaner exposures.

Focus on star quality rather than graph perfection, make one change at a time, and keep notes of what works.


<br>
<br>



