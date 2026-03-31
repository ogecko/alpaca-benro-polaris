[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Release Notes

## Alpaca Benro Polaris Driver  
* **Version:** 2.2.0 Alpha
* **Release Date:** TBD
* **Availability:** Download from [Alpaca Driver v2.1.0 Download ZIP](https://github.com/ogecko/alpaca-benro-polaris/archive/refs/tags/v2.1.0.zip)
* **License:** Distributed exclusively for backers of the [Kickstarter Project](https://www.kickstarter.com/projects/jdmorriso/alpaca-benro-polaris-driver-v20?ref=d1hx2v)
* **Current Branch:** releases/2_2_0

## Demonstration Videos
* **20 - Podcast Video:** Podcast Video at https://youtu.be/KUBCTnEsnlE
* **21 - Preview Demo:** Demonstration Video at https://youtu.be/0QSKD1GCzOc
* **22 - Starting and Using:** Demonstration Video at https://youtu.be/Wv_ZvBtZZ4Q
* **23 - Rotator Framing:** Demonstration Video at https://youtu.be/_Swd-jIyQis
* **24 - Multi Point Alignment:** Demonstration Video at https://youtu.be/4CMO0R_yphw
* **25 - Equipment Safety:** Demonstration Video at https://youtu.be/45EP-DExSOQ
* **26 - Tracking Orbitals:** Demonstration Video at https://youtu.be/no47ZNagEDk
* **27 - Pulse Guiding:** Demonstration Video at https://youtu.be/dn1nLxT5eWw
* **28 - Panoramas:** Demonstration Video at https://youtu.be/k7OoPk98UCk
* **31 - Kalman Filter:** Demonstration Video at https://youtu.be/aDFKAWBNQHU
* **32 - Speed Calibration:** Demonstration Video at https://youtu.be/U_0-mBDuTjE
* **33 - PID Tuning:** Demonstration Video at https://youtu.be/6vJbSb0gl3M

## Win11 Upgrade Instructions
* Upgrade Python to 3.13.12 by downloading Windows Installer (64 bit) for Python 3.13.12 and running the install program.
* Upgrade pip using the command `python -m pip install --upgrade pip`
* If you are using ASCOM, upgrade to ASCOM Platform 7.1.3
* Remove the old `C:\Users\Nina\Documents\alpaca-benro-polaris>` directory.
* Follow the standard [Installation Guide](./installation.md) to install the Alpaca Driver v2.1.0
* Install all pre-requisite python packages using the command `pip install -r platforms/win/requirements.txt`
* WARNING: Update Stellarium Desktop Telescope Settings for Alpaca Driver V2.x
    * Recreate the Stellarium Desktop ASCOM Settings, as the Alpaca Driver name has changed in V2.x
    * Change the ASCOM Telescope Co-ordinate System to "Equinox of the date (JNow)", as this is the default for Alpaca Driver V2.x
    * Nina does not need to change, as it reads the correct settings from the Alpaca Driver

## What's new in v2.2.0

- **[Persist Alignment]** Multi-Point Alignment model is saved to disk and restored automatically on driver restart.
- **[GOTO Correction]** Last sync residual is applied to GOTO targets rather than the alignment model, preserving optimal sidereal tracking.
- **[Reduced RMSError]** Reduce RMS Error by up to 70%, by synchronising 518 and PID calculations
- **[Forward Kinematics]** Improve forward kinematic robustness for negative azimuth angles
- **[Gimbal Lock]** Improve handling of Gimbal Lock when M2=0, with better solution choosing and hysteresis to reduce uncertainty, and add status icon to Pilot.
- **[Negative Azimuth]** Support Goto Altitude below -8°, now accessable with improved inverse kinematics solution selection, when M3 is not zero
- **[Sidereal Tracking]** Enhance sidereal tracking by computing motor error signals using the SO(3) quaternion shortest-path interpolation, ensuring more accurate and smooth orientation corrections.
- **[Roll Angle Tracking]** Enhance boresight rotation by limiting specific motor speeds to maintain pointing direction.
- **[Orbital Tracking]** Enhance orbital tracking by adding feed forward, expanding integration component, and maintaining a fixed roll angle, resulting in smoother and more stable tracking.
- **[Guiding Accuracy]** Refine pulse guiding accuracy by refactoring state management and incorporating PID feed-forward control for pulses.
- **[Guiding Integral]**: Reduce pulse-guiding overshoot by temporarily suspending integration of the error term during active guiding.
- **[Pano Recenter]**  Add btn on the Dashboard to save the current pointing orientation into the PanoGrid, recentering it in space.
- **[Pano Copy]**  Add btn to copy PanoGrid Parameters for easy pasting into Nina Advanced Sequencer.
- **[Pano Actions]** Move Panorama Actions to top of Device Action List for easier access from Nina Dropdown.
- **[Chart Axes]** Show angles in Degrees, Arc-minutes, and Arc-seconds on all charts (instead of decimal degrees).
- **[At Home]**: Upgrade to ASCOM ITelescopeV4 FindHome method (non-blocking) and associated AtHome property. Include in Pilot Status indicator.
- **[Driver Instance]**: On the Connect page, display the Alpaca Driver Hostname:Port to clearly identify the current connected instance.
- **[Driver Stop]**: On the Connect page, provide options to restart or stop the Alpaca Driver.
- **[IPv6 Discovery]**: Revamped IPv6 Alpaca Discovery for support on MacOS, Linux and Windows.

## New Features (enabled by Nina)

## New Features (enabled by Stellarium)

## Upgraded Win11 Requirements.txt Compatibility
- **[Python 3.13.12]**: Upgraded Python support from 3.13.9.
- **[Falcon 4.2.0]**: Upgraded Falcon support from 4.0.2.
- **[Uvicorn 0.35.0]**: Upgraded Uvicorn support from 0.33.0.
- **[Bleak 1.1.1]**: Upgraded Bleak support from 1.1.0.
- **[Ephem 4.2]**: Upgraded Ephem support from 4.1.6.
- **[numpy 2.4.2]**: Upgraded numpy support from 2.3.2.
- **[scipy 1.17.0]**: Upgraded scipy support from 1.16.1.
- **[certifi 2026.1.4]**: Upgraded certifi support from 2025.8.3.

## Documentation (Alpaca Driver)
- **[Microsoft Account]**: Prevent Windows from syncing Wi-Fi settings across PCs using the same Microsoft account (hardware.md)
- **[Auto Startup]**: Define how to make the Alpaca Driver start automatically on Windows (installation.md, Step 5)
- **[Guiding 16-bit]**: Describe how to configure the guide camera as a 16-bit camera (guiding.md, Section 3.1)
- **[Guiding Calibration]**: Provide best practice recommendations in choosing a guiding calibration location (guiding.md, Section 4)
- **[Persit Alignment]**: Document the need to reset Multi-Point Alignment on new setup (control.md, section Alignment III.F)
- **[Pano Orbitals]**: Descrone how to capture the moon or other orbitals in a workflow (pilot.md, Section 4.4)
- **[Troublshooting A6]**: How to troublshoot shortcut error messages on Windows
- **[Troublshooting C6]**: Added troubleshooting C6 for Win11 wifi diagnostic commands

## Bug Fixes (from v2.1.0 version)
- **[fix #81]**: Improve error message shown when trying to run multiple instances of Alpaca Driver
- **[fix #79]**: Clear Pilot SYNC list cache when driver restarts or moves to single point alignment

## Tested Compatible Hardware and Software
### Photography Equipment
* Benro Polaris Hw 1.4.1.4, Firmware V6.0.0.54, Astro V1.0.2.14 (JDM - Main Board replaced)
* Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.54, Astro V1.0.2.14
* Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.48, Astro V1.0.2.14
* Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.40, Astro V1.0.2.11
* Benro Polaris Hw 1.2.1.2, Firmware V6.0.0.54, Astro V1.0.2.14 (VV)
* Canon R5, RF 16mm, EF 35mm MkII, RF 135mm, RF 100-500mm, RF 800mm.
* Canon R6 Mk II connected via USB3
* Canon R, 16mm 2.8, 24-240mm f4-6.3
* Canon 6D MkII, Canon EF 50mm f1.8
* Canon 800D, Sigma DC 17-50mm f2.8, Tamron 16-300mm f3.5-6.3
* Sony Alpha 7R IV
* Nikon Z8
* Pentax K1 150-450mm / Irix 45mm
* ZWO ASI585MC camera, a Sigma 120-400mm and 1.4x extender.
### Computing Equipment
* MacBook Pro with Apple M1 Pro CPU (Driver and CCDCiel)
* MacBook Pro 14” 2021 
* MacBook Pro 13” 2013
* Mele Quieter 4C, Intel N100 800Mhz (Driver and Nina)
* Minis Forum UM350 (Driver and Nina)
* ASUS Vivobook Pro 16X OLED K6604JV (Driver and Nina)
* Laptop Windows 10 Home (Driver and Nina)
* Desktop PC, AMD 7950X (Stellarium Desktop, Siril)
* Desktop PC, AMD Ryzen 5 3600
* Raspberry Pi Zero 2 W and up (Driver)
### Portable/Mobile Equipment
* iPhone 13 Max (Stellarium Mobile PLUS)
* iPad Pro 3rd Generation
* Samsung Galaxy S22 Ultra (Stellarium Mobile PLUS)
* Microsoft Surface Laptop 2
### Applications
* Sky Safari 7 Pro v7.3.6 iOS
* Benro Connect Android App v3.0.30, iOS App v1.5.0
* Benro Polaris Android App v3.0.27, iOS App v1.4.4
* Stellarium Mobile PLUS v1.12.9 Android and iOS.
* Stellarium Desktop v25.2 Qt6 Windows (requires ASCOM Platform 7)
* Stellarium Desktop v24.3 Qt5 Windows (not Qt6 version)
* Stellarium Desktop v24.2 Windows
* Nina v3.2.0.9001, HocusFocus v3.0.0.21, LensAF v2.1.0.3, Scope Control  v2.0.2.1
* Nina v3.1.2.9001, HocusFocus v3.0.0.18, LensAF v2.1.0.2, Scope Control  v2.0.2.0
* Nina v3.1.1.9001, HocusFocus v3.0.0.17
* ASTAP 2026.02.09
* ASTAP 2024.08.11
* PHD2 v2.6.14
* CCDciel Version beta 0.9.87-3346 Windows
* GraXpert 3.1.0rc2
* Siril v1.4.2
* Siril v1.4.0
* Siril v1.2.5
* Siril v1.2.3 de49749
### Drivers and Utilities
* Windows Remote Desktop v10.0.22621
* ASCOM Platform 7.1.3 (Build 4851)
* ASCOM Platform 7.1 (Build 4707)
* ASCOM Platform 7 Update 3 RC7 (not Update 2 version)
* ASCOM Platform 7 RC7
* ASCOM Platform 6.6 SP2
### Operating Systems
* Windows 11 Pro v24H2 
* Windows 11 Pro v23H2 
* Windows 10
* MacOS Sonoma 14.6.1
* MacOS Sequoia 15
* iOS 17.6  
* iPadOS v17.6.1
* Raspberry Pi OS (64-bit) Debian Trixie
* Raspberry Pi OS Lite (64-bit) Debian Trixie
### Alpaca Pilot compatible Browsers
* Firefox version 115+ 
* Google Chrome version 115+
* Microsoft Edge version 115+
* Apple Safari 14+

## Untested New Features
Please let us know if you can try any of these features.
- **[Lumix Nina Plugin]**: Supports Panasonic Lumix Cameras and Lens. Untested.
- **[Pentax on ASCOM]**: ASCOM Camera driver supports a range of cameras. Untested.

## Known Issues
- **[Python 3.14.0]**: Pyephem is does not have a compiled version for 3.14 as of end Nov 2025. Use Python 3.13.12 instead.

## Potential Future Enhancements
- **[Software Delivery]**: Deliver as an App rather than a zip file, eliminating the command line.
- **[INDI support]**: Add support for INDI protocol, enabling apps like KStars.
- **[Emedded Driver]**: The driver should be embedded on the Benro Polaris Device. Benro Change.

## Deprecations
- **[RA 1.04]**: Special RA Axis move command in V1.0 has been replaced with Alpaca Pilot direct RA radial dial control.
- **[N-Point Alignment]**: N-Point Alignment in V1.0 has been replaced with Multi-Point Alignment
  