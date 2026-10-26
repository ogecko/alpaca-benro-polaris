[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Release Notes

## Alpaca Benro Polaris Driver  
* **Version:** 2.2.0 Release
* **Release Date:** TBD
* **Availability:** Download from [Alpaca Driver v2.2 ZIP file](https://github.com/ogecko/alpaca-benro-polaris/archive/refs/heads/dev2_2.zip)
* **License:** Distributed exclusively for backers of the [Kickstarter Project](https://www.kickstarter.com/projects/jdmorriso/alpaca-benro-polaris-driver-v20?ref=d1hx2v)
* **Current Branch:** releases/2_2_0

## Demonstration Videos
* **YouTube Channel:** The Pilot sidebar's Videos link now points to the [full YouTube channel](https://www.youtube.com/@jdm5001/featured), including v2.2 videos:
* **40 - Deep Dive Podcast:** Deep Dive Podcast on Alpaca Benro Polaris V2.2 at https://youtu.be/ouJ52WcTY2M
* **41 - Installation on Win11:** Installation of Alpaca Driver v2.2 on Win11 at https://youtu.be/qXRiTLS2EaY
* **42 - Installation on Raspberry Pi:** Installation of Alpaca Driver v2.2 on a Raspberry Pi at https://youtu.be/4_zNjTEfG6Y
* **43 - Beta Preview:** Beta Preview Demonstration of v2.2 at https://youtu.be/YfUGk_6oSYE
* **44 - Galactic Panorama Workflow:** Galactic Panorama Workflow at https://youtu.be/f1YoKFxFse4
* **45 - Less Drift and Better Tracking:** Less Drift and Better Tracking on the Benro Polaris at https://youtu.be/ugxQ13Z1Mu4

## Win11 Upgrade Instructions
* If you are using ASCOM, upgrade to ASCOM Platform 7.1.3
* Remove the old `C:\Users\Nina\Documents\alpaca-benro-polaris>` directory.
* Follow the standard [Installation Guide](./installation.md) to install the Alpaca Driver v2.2.0. The new `setup.bat` installs Git, uv, Python and every pre-requisite package for you, so there is no need to install or upgrade Python or pip yourself.
* WARNING: Update Stellarium Desktop Telescope Settings for Alpaca Driver V2.x
    * Recreate the Stellarium Desktop ASCOM Settings, as the Alpaca Driver name has changed in V2.x
    * Change the ASCOM Telescope Co-ordinate System to "Equinox of the date (JNow)", as this is the default for Alpaca Driver V2.x
    * Nina does not need to change, as it reads the correct settings from the Alpaca Driver

## What's new in v2.2.0

### Precision Tracking, PEC and Backlash Compensation

- **[Improved Tracking Accuracy]** Reduce tracking RMS error through synchronised kinematics, improved motor speed control and PID calculations, and more robust handling of delayed position updates.
- **[Periodic Error Correction]** Combine drift learning, harmonic error modelling, worm-gear correction, and PID feed-forward to reduce periodic errors, residual drift, and star-shape distortions.
- **[Backlash Compensation]** Takes up gear backlash after a goto, improving tracking settle time. 
- **[Sidereal Tracking]** Improve tracking smoothness and stability, including at low altitudes and zero roll.
- **[Orbital Tracking]** Improve tracking accuracy for satellites and other orbitals through more accurate orbital setpoints.

### Pointing, Alignment and Motion Control

- **[Advanced Kinematics]** Support Topocentric, Equatorial, and Galactic coordinate frames, reachable target orientations, and improved forward and inverse kinematics.
- **[Mechanical Alignment Correction]** Improve multi-point alignment, mechanical axis correction, and polar alignment accuracy using cleaner measurements and improved alignment fitting.
- **[Goto Accuracy]** Improve blind Goto Accuracy and Slew & Center correction cycle time.
- **[Motion Planning]** Plan complete goto trajectories, including motor speed profiles, braking, flips, unwinds, and rolls, reducing slew times and tracking disturbances.
- **[Axis Limits and Orientation]** Improve gimbal-lock handling, zenith and horizon crossing, negative-altitude pointing, mechanical limit warnings, and cable-windup prevention.
- **[Jogging and Manual Control]** Extend responsive jogging to all nine axes, including non-tracking operation, keyboard control, and ramped speed changes.
- **[Roll Accuracy]** Improve pointing accuracy during rolls and provide a preset to minimise M2 movement over the following 120 minutes.

### Guiding and Calibration

- **[Sync Guiding]** Support plate-solving-based sync guiding, without the need for a separate guide camera 
- **[Pulse Guilding]** More accurate ASCOM pulse guiding by adjusting present value rather than the set point.
- **[PHD2 Calibration]** Support a single calibration that PHD2 can rotate to different position angles and targets
- **[PHD2 & CCDceil Calibration]** Ignore calibration pulses when learning periodic error drift
- **[Backlash Compensation]** Ignore backlash pushthrough when learning periodic drift
- **[Guiding Documentation]** Improve guidance for diagnosing common guiding and alignment problems.

### Panorama Planning and Imaging Automation

- **[Flexible Panorama Planning]** Configure, save, and load panorama presets, calculate sensor and grid fields of view, adjust panel spacing, and switch between landscape and portrait layouts.
- **[Panorama Positioning]** Recenter panorama grids, configure reference roll and anchor positions, and support Topocentric, Equatorial, and Galactic reference frames.
- **[Galactic Panoramas]** Align panorama grids with the Milky Way using Galactic coordinates.
- **[Automated Imaging Workflows]** Expand Nina and CCDciel scripting for slews, sync guiding, panoramas, solve-and-center operations, and panel navigation.
- **[Siril Processing]** Automate calibration, grouping, stacking, compositing, and stretching for multi-panel and Galactic panorama images.

### Installation, Connectivity and Reliability

- **[Simplified Installation]** Automate Windows and Raspberry Pi installation, Python environment setup, dependency management, driver updates, firewall configuration, and automatic startup.
- **[Network Connectivity]** Improve Wi-Fi setup, network discovery, IPv6 support, mDNS hostname configuration, HTTPS certificates, and Raspberry Pi Bluetooth compatibility.
- **[Connection Reliability]** Improve connection timeouts, reconnect handling, protocol response timeouts, WebSocket proxying, and recovery from transient network failures.
- **[Control-Loop Resilience]** Improve PID stability under irregular position updates, prevent stale message backlogs, and reduce the impact of CPU-intensive applications.
- **[Recovery and State Persistence]** Save and restore multi-point alignment and tracking state across driver restarts
- **[Device Management]** Add driver restart, stop, and host operating-system shutdown controls, plus connected-instance identification.

### Dashboard, Diagnostics and Observing Tools

- **[GPS Location]** Locate the observing site with a GPS receiver plugged into the Alpaca Driver's computer (thanks to @rbaranga for authorship).
- **[Operational Status]** Display alignment, guiding, PEC, tracking performance, device connectivity, and system status.
- **[Motion Feedback]** Show progress for goto, rotate, home, and park operations.
- **[Tracking Analysis]** Improve live chart performance, angular scales, RMS-error projections, and PID deviation charts.
- **[Persistent Interface State]** Retain coordinate frames, dial zoom ranges, and catalog filters across supported navigation workflows.
- **[Observing Tools]** Add bright-object discovery, mountain-peak identification and elevation information, and improved site and equipment setup checks.
- **[Offline Operation]** Persist observing locations, orbital data, and alignment models for use without continuous network access.

### Application Integration and Automation

- **[ASCOM Alpaca Integration]** Improve driver discovery, connection stability, telescope-control compatibility, and browser-based communication.
- **[Nina Device Actions]** Add absolute and relative multi-axis slews, abort-slew controls, and expanded panorama actions for Advanced Sequencer workflows.
- **[Stellarium Integration]** Improve desktop telescope support, selection, stability, and configuration guidance.
- **[CCDciel and PHD2 Integration]** Expand scripting, guiding workflows, and supporting documentation.

### Utilities, Compatibility and Documentation

- **[Imaging Utilities]** Add FITS metadata extraction, mechanical correction calibration support, flat-frame capture, and Siril-compatible directory renaming.
- **[Installation and Troubleshooting Guides]** Expand documentation for Windows, Raspberry Pi, Docker, network connectivity, guiding, alignment, kinematics, panorama workflows, and common errors.
- **[Software Compatibility]** Refresh Python and application dependencies, address security advisories, and document supported operating systems, hardware, and astronomy applications.
- **[Maintenance and Bug Fixes]** Improve driver connection management, dashboard interaction, alignment-state handling, and overall runtime robustness.


### New Features (enabled by Nina)
- **[Pano Actions]** Move Panorama Actions to top of Device Action List for easier access from Nina Dropdown.
- **[Device Actions]** Additional Device Actions added for Nina Advanced Sequencer
    - **Polaris:SlewRelative** Slews any axis relative to current setpoint. All Optional Parameters {"ra":h, "dec":d, "pa":d, "az":d, "alt":d, "roll":d, "l":d, "b":d, "gpa":d}
    - **Polaris:SlewAbsolute** Slews any axis to new setpoint. All Optional Parameters {"ra":h, "dec":d, "pa":d, "az":d, "alt":d, "roll":d, "l":d, "b":d, "gpa":d}
    - **Polaris:AbortSlew** Stops all axis motion, turns off tracking, unparks the mount.
    - where: h=decimal hours, d=decimal degrees; h and d can also be strings with dms format eg "14:30:10" or "180d30m15s" or "90d30m"

### New Features (enabled by Stellarium)
- **[Stellarium 26.2]** Improved ASCOM Telescope support, fixing stability, and improving ease of telescope selection. 

## Upgraded Win11 Requirements.txt Compatibility
- **[Python 3.13.15]**: Upgraded Python support from 3.13.9.
- **[Python 3.11]**: Minimum Python version supported.
- **[starlette 1.3.1]**: Upgraded aiohttp support from 0.49.1.
- **[aiohttp 3.14.3]**: Upgraded aiohttp support from 3.13.3.
- **[urlib3 2.7.0]**: Upgraded urlib3 support from 2.6.3.
- **[psutil 7.0.0]**: New dependency in Alpaca Driver v2.2.
- **[cryptography 48.0.1]**: New dependency in Alpaca Driver v2.2.
- **[requests 2.33.0]**: Made transitive dependency explicit in Alpaca Driver v2.2.
- **[idna 3.15]**: Made transitive dependency explicit in Alpaca Driver v2.2.
- **[numpy 2.3.5]**: Downgraded from 2.4.2. Note 2.4+ requires x86-64-v2, SIGILLs on pre-2009 CPUs. See issue #89.

## Documentation (Alpaca Driver)
- **[CCDciel Guide]**: Add the CCDciel users guide for the Benro Polaris (ccdciel.md)
- **[Rotator Alignment]**: Add a section on the importance of Rotator Alignment, and how to perform a manual Position Angle Sync (control.md)
- **[Kinematics Reference]**: Defines Reference Frames, Kinematic Flows and Correction Algorithms
- **[Microsoft Account]**: Prevent Windows from syncing Wi-Fi settings across PCs using the same Microsoft account (hardware.md)
- **[Auto Startup]**: Define how to make the Alpaca Driver start automatically on Windows (installation.md, Step 5)
- **[Guiding 16-bit]**: Describe how to configure the guide camera as a 16-bit camera (guiding.md, Section 3.1)
- **[Guiding Calibration]**: Provide best practice recommendations in choosing a guiding calibration location (guiding.md, Section 4)
- **[Persit Alignment]**: Document the need to reset Multi-Point Alignment on new setup (control.md, section Alignment III.F)
- **[Pano Orbitals]**: Descrone how to capture the moon or other orbitals in a workflow (pilot.md, Section 4.4)
- **[Troublshooting A6]**: How to troublshoot shortcut error messages on Windows
- **[Troublshooting B8]**: Single Star Alignment Will Not Complete
- **[Troublshooting C0]**: Improve communications reliability by reducing periodic network frequency scanning.
- **[Troublshooting C6]**: Added troubleshooting C6 for Win11 wifi diagnostic commands

## Bug Fixes (from v2.1.0 version)
- **[fix #84]**: Driver can get confused as to the state of the L-Bracket setting on connection
- **[fix #82]**: Correct dashboard Scale Label interaction (allow click when near zoom buttons, dont double fire slew)
- **[fix #81]**: Improve error message shown when trying to run multiple instances of Alpaca Driver
- **[fix #80]**: Refined connection management logic to minimize unnecessary reconnections and support manual connection handling
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
* GPS Receivers: u-blox 7 UBX-G7020; G71 G-Mouse VK-172; BN-808 G-Mouse UBX-M8030-KT; M10 G-Mouse UBX-M10050-KB (u-blox SR1612U10)
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
* Stellarium Desktop v26.3 Qt6 Windows (recommended)
* Stellarium Desktop v26.2 Qt6 Windows 
* Stellarium Desktop v26.1 Qt6 Windows (DO NOT USE - unstable, prone to crash)
* Stellarium Desktop v25.2 Qt6 Windows (requires ASCOM Platform 7)
* Stellarium Desktop v24.3 Qt5 Windows (not Qt6 version)
* Stellarium Desktop v24.2 Windows
* Nina v3.2.0.9001, HocusFocus v4.0.0.1, LensAF v3.1.2.2, Scope Control  v2.0.2.1, Session Metadata 2.6.3.0
* Nina v3.2.0.9001, HocusFocus v3.0.0.21, LensAF v2.1.0.3, Scope Control  v2.0.2.1
* Nina v3.1.2.9001, HocusFocus v3.0.0.18, LensAF v2.1.0.2, Scope Control  v2.0.2.0
* Nina v3.1.1.9001, HocusFocus v3.0.0.17
* ASTAP 2026.05.19
* ASTAP 2026.02.09
* ASTAP 2024.08.11
* PHD2 v2.6.14
* CCDciel Version beta 0.9.87-3346 Windows
* GraXpert 3.1.0rc2
* Siril v1.4.4
* Siril v1.4.3
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
- **[Python 3.14.0]**: Pyephem is does not have a compiled version for 3.14 as of end Nov 2025. Use Python 3.13.15 instead.

## Potential Future Enhancements
- **[Software Delivery]**: Deliver as an App rather than a zip file, eliminating the command line.
- **[INDI support]**: Add support for INDI protocol, enabling apps like KStars.
- **[Emedded Driver]**: The driver should be embedded on the Benro Polaris Device. Benro Change.

## Deprecations
- **[RA 1.04]**: Special RA Axis move command in V1.0 has been replaced with Alpaca Pilot direct RA radial dial control.
- **[N-Point Alignment]**: N-Point Alignment in V1.0 has been replaced with Multi-Point Alignment
  