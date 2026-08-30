[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Release Notes

## Alpaca Benro Polaris Driver  
* **Version:** 2.2.0 Beta 4
* **Release Date:** 12-Aug-2026
* **Availability:** Download from [Alpaca Driver v2.2 Beta 4 ZIP file](https://github.com/ogecko/alpaca-benro-polaris/archive/refs/heads/dev2_2.zip)
* **License:** Distributed exclusively for backers of the [Kickstarter Project](https://www.kickstarter.com/projects/jdmorriso/alpaca-benro-polaris-driver-v20?ref=d1hx2v)
* **Current Branch:** dev2_2

## Demonstration Videos
* **40 - Podcast Video:** Podcast Video at https://youtu.be/ouJ52WcTY2M
* **41 - Installation Video:** Installation Video at https://youtu.be/qXRiTLS2EaY

## Win11 Upgrade Instructions
* Upgrade Python to 3.13.15 by downloading Windows Installer (64 bit) for Python 3.13.15 and running the install program.
* Upgrade pip using the command `python -m pip install --upgrade pip`
* If you are using ASCOM, upgrade to ASCOM Platform 7.1.3
* Remove the old `C:\Users\Nina\Documents\alpaca-benro-polaris>` directory.
* Follow the standard [Installation Guide](./installation.md) to install the Alpaca Driver v2.2.0
* Ensure you install all pre-requisite packages using the command `pip install -r platforms/win/requirements.txt` as v2.2 includes 3 new dependencies
* WARNING: Update Stellarium Desktop Telescope Settings for Alpaca Driver V2.x
    * Recreate the Stellarium Desktop ASCOM Settings, as the Alpaca Driver name has changed in V2.x
    * Change the ASCOM Telescope Co-ordinate System to "Equinox of the date (JNow)", as this is the default for Alpaca Driver V2.x
    * Nina does not need to change, as it reads the correct settings from the Alpaca Driver

## What's new in v2.2 Beta 5 
- **[zeroconf dependancy]** Installation requires `pip install -r platforms/win/requirements.txt` to pickup new zeroconf dependancy
- **[mDNS Service]** Advertise Alpaca Pilot hostname as `ap.local` (configurable via Network Settings) for easy discovery from iPads and other devices on the local network.
- **[mDNS Certificate]** Changing mDNS hostname from Network Settings regenerates HTTPS root certificate, requiring reinstallation.
- **[Kalman Filter]** Improve KF performance (fixed measurement cadence, use true velocity measurement, robust to protocol backlog draining)
- **[KF Tuning Page]** Allow page to monitor trending signals during tracking and fix bug where page callup could reset KF Tuning Parameters
- **[Docker Images]** Documented how to Install, Clone, Build and Run the driver in a docker image using platforms/docker/run.sh 
- **[Python dependencies]** Add option to install using UV to manage python.exe and package dependancies with uv.lock
- **[numpy Compatibility]** Pin numpy to `>=2.3.5,<2.4.0` (fix #89). Note 2.4+ requires x86-64-v2, SIGILLs on pre-2009 CPUs
- **[Connection Handling]** Faster connection timeouts, duplicate-cycle prevention, and immediate manual reconnects.
- **[Wi-Fi Join]** The Connect Page’s Wi-Fi button instructs the driver to enable **and join** the Polaris Wi-Fi network. No more manually finding `polaris_xxxxxx` in Windows’ Wi-Fi list.
- **[Protocol Handling]** Added reply timeouts, ensuring dropped or lost Polaris responses no longer have potential to block the driver.
- **[Local Timezone]** Show all log messages with local timestamp (rather than UTC), both in alpaca.log and in Alpaca Pilot
- **[Log Replay]** New replay.py tool to allow a captured log file to be replayed on another mount for system testing and diagnosis.
- **[Mobile App]** Support mobile home screen install. On iOS or iPadOS use Safari / Share / Add to Home Screen. On Android use Chrome / Install and create shortcut.

## What's new in v2.2 Beta 4
- **[Universal Jogging]** Extends jogging to all 9 axes (Az/Alt/Roll, RA/Dec/PA, GLon/GLat/GPA) with improved responsiveness. 
- **[Non Tracked Jogging]** Fine motion jogging when tracking is enabled or disabled.
- **[Keyboard Map]** Control the Benro Polaris and Alpaca Pilot directly using the keyboard commands (see pilot.md for keymap)
- **[Sidereal Tracking]** Smoother Sidereal tracking by changing non-orbital motion to pure RA rotation.
- **[PID Ki]** Faster PID settling as Ki is inhibited during jogging, sync guiding and pulse guiding. 
- **[PID Kd]** Improved response to jogging and sync pulses as Kd now damps velocity error and eliminates steady state bias
- **[Alignment Roll]** Added the Roll angle to the list of Sync Points on the Alpaca Pilot Alignment page
- **[Chart Scales]** Simplify Y axis chart scales to reduce duplication of co-ordinate precision
- **[Restart Robustness]** Workaround Win11 path issue when user name has spaces
- **[Siril Scripts]** Incorporated RC Astro Tools, Veralux Star Composer and Statistical Stretch into scripts.
- **[Pilot Proxy]** Improved the Alpaca Pilot connection to the Alpaca Driver by using a proxy that no longer requires a hostname or port for the REST API

## What's new in v2.2 Beta 3
- **[Download Links]** Updated all documentation download links to refer explicitly to v2.2 Beta 3
- **[Brightest Catalog]** Quickly find alignment targets with a list of the brightest nearby stars, planets, star clusters, and celestial poles.
- **[Dashboard Status]** Monitor the health and status of the Alignment Model, Sync Guiding, Pulse Guiding, Periodic Error Correction (PEC), and Tracking Performance from the dashboard.
- **[PEC Performance]** Integrate Periodic Error Correction (PEC) into the PID feed-forward signal to reduce micro "wiggles" in star shapes.
- **[PEC EMA Model]** Added optional PEC Exponential Moving Average Model (retain default as Recursive Least Squares Model with 2 Harmonics)
- **[MAC Autotune Docs]** Add documentation on how to use Mechanical Alignment Correction Autotune.
- **[Scale Warnings]** Adjust scale warning indicators to consider Roll Sync Adjustments.
- **[CPU Resilience]** Better resilience to CPU-intensive applications (such as Hocus Focus) by collapsing queued message bursts into a single, up-to-date refresh.
- **[Flat White]** Added support for capturing flat frames from a display screen via the new Flat White menu item.
- **[Peak Finder]**: Added Sky Conditions link to identify a mountain peak that Polaris is pointing toward and determine its elevation.
- **[Connect Checklist]** Add Checks for L-Bracket Orientation, Site Location and tracking of Reset All Axes to Connect page. 
- **[Connect Reliability]** Improve Alpaca Pilot connection setup to the Driver by proxying web sockets via http(s)
- **[Connect Astro Module]** Connect page highlights missing Astro Module
- **[Persist Guide State]** Persist Guide State between Driver restarts
- **[Persist Co-ordinate Frame]** Dashboard co-ordinate frame is persisted across F5 refresh and page changes, while separate for each browser tab.
- **[Persist Zoom Range]** Each radial dial on the Dashboard retains its zoom range when navigating between pages.
- **[Persist Filters]** Filters persist when returning to the main Catalog page, but reset when opening a specific catalog view (Stars, Nebulae, etc.).
- **[Siril Scripts]** Add Siril Python Scripts to help automate Galactic Panorama processing
- **[Lat/Lon Data Entry]** Increased debounce to allow for trailing zeros in lat/lon data entry
- **[Catalog Updates]** Minor updates to catalog data on some entities brightness and classification
- **[Panel Spacing Calculator]** Added a 16mm option, updated FOV labels to use the Reference Frame, and added controls to adjust the number of rows and columns directly within the calculator.

## What's new in v2.2.0

### Refactored Kinematics
- **[Galactic Coordinates]** Dashboard supports Topocentric, Equatorial and now Galactic Frames for naviagation relative to the milky way galaxy's spine.
- **[Reachable Targets]**: Resolve Target Orientation to a reachable orientation given Polaris Limits in Alt and Roll
- **[Improved Accuracy]** Reduce tracking RMS Error by up to 70%, by synchronising 518 and PID calculations.
- **[Kinematics Status]** A new Kinematics page that provides a comprehensive overview of both Forward and Inverse Kinematics workflows.
- **[Negative Azimuth]** Goto's now support altitudes down to -79° by flipping the astro axis in the opposite direction. Previously limited to -8°.
- **[Scale Warnings]** Real-time scale warning markers on Roll, RA, Dec based on Benro Polaris Mechanical Limits.
- **[Smoother Rolling]** Enhance boresight rotation by limiting specific motor speeds to maintain pointing direction.
- **[Gimbal Lock]** Improve handling of Gimbal Lock when M2=0, with better solution choosing, hysteresis to reduce uncertainty, and add status icon to Pilot.
- **[At Home]**: Upgrade to ASCOM ITelescopeV4 FindHome method (non-blocking) and associated AtHome property. Include in Pilot Status indicator.

### Goto and Pointing Correction Models
- **[Goto Completion]** Reduce post-goto star trails by stabilising tracking before marking goto as complete, tightening tollerance x20 when tracking enabled.
- **[Progress Indicator]** Add a circular progress indicator showing remaining angular distance for Goto, Rotate, Home, and Park operations.
- **[Slew & Center Correction]** Reduce the number of corrective slews with three alternate algorithms - Zero Last Residual (ZLR), Local Guasssian Adjustment (LGA) and Sync Guiding Adjustment (SGA).
- **[Mechanical Correction]** Correction models for potentially tilted or misaligned Astro and Altitude motor axes.
- **[Windup Prevention]** Automatically detects when a move would over-rotate an axis and reroutes 360° in the opposite direction to prevent cable damage
- **[Zenith/Horizon Crossing]** Handles the physical axis flip needed when pointing through zenith or to negative altitudes, equivalent to a meridian flip

### Dark Site Operations
- **[Persist Locations]** Pilot Settings allows multiple Observing Site Locations to be saved, loaded and deleted for offline use.
- **[Persist Orbitals]** Orbitals fetched successfully are stored in the catalog, allowing offline use and later retrieval, refresh, or deletion. 
- **[Persist Alignment]** Multi-Point Alignment model is saved to disk and restored automatically on driver restart, allowing imagaging sessions to continue, uninterupted.
- **[Cleaner Alignment]** The alignment model is based on KF cleaned measurements rather than raw Polaris data. 

### Auto-Guiding Improvements
- **[Sync Guiding]** Drift correction made simple; no guide camera, no extra PHD2 software, just plate-solving.
- **[Pulse Guiding]** Refine pulse guiding accuracy by refactoring state management and incorporating PID feed-forward control for pulses.
- **[Polar Alignment]** Guiding adjustments applied as corrections rather than setpoint changes to maintain polar alignemnt
- **[Drift and PEC]** Models linear and harmonic drift in RA and Dec to correct alignment and periodic errors, significantly improving sidereal tracking accuracy.

### Panorama Improvements
- **[Pano Presets]**  Ability to configure, save and load Panoramas presets
- **[Pano Recenter]** Add btn on the Dashboard to recenter the PanoGrid to match the mounts current orientation
- **[Solve and Center]**  Allow Nina Scripting to "Solve and Sync" then use Device Action Polaris:PanoSlew {"panel": -1} to center on current panel
- **[Pano Swap]**  Add btn to switch between Landscape and Portrait orientation (swapping hstep and vstep values)
- **[Pano Copy]**  Add btn to copy PanoGrid Parameters for easy pasting into Nina Advanced Sequencer.
- **[Pano Roll]** The Reference Roll Angle affects the full panorama in Sky-Celestial mode; in other modes, it rotates individual panels.
- **[Anchor Position]**  Allow Anchor Position to be specified in Topocentric, Equatorial or Galactic coordinates.
- **[Pano Galactic]**  Add "Sky - Milky Way" panorama that aligns with the milky way spine using Galactic coordinates. 
- **[Pano Calculator]**  Calculates the full PanoGrid field of view (FOV), (as well as the sensor FOV, hstep, and vstep) 
- **[Siril Scripts]**  Automate Siril image processing (calibrate, group, stack, composit and stretch) for multi Panel mono images in a Galactic Pano.

## Utilities and Visualisation
- **[Rename Directories]** Utility script to rename FLAT, LIGHT, BIAS, DARK directories to be Siril compliant (rename_dirs.py). Nina Scheduler compatible.
- **[FITS Extract]** Utility script to extract meta-data from plate-solved FITS images and calibrate Mechanical Correction Models (fits_extract.py)
- **[Driver Stop]**: On the Connect page, provide options to restart or stop the Alpaca Driver.
- **[Driver Instance]**: On the Connect page, display the Alpaca Driver Hostname:Port to clearly identify the current connected instance.
- **[HTTPS Support]**: Alpaca Pilot now support https, enabling location and clipboard services in the browser.

### Diagnostics and System
- **[Heartbeat Diagnostics]**: Introduce a heartbeat monitor and additional telemetry statistics to assist in diagnosing late position updates.
- **[Smoother Control]** Improve PID robustness to irregular 518 messages from CPU hogs (drop stale 518 msgs and guard against backlog flushing that may cause spikes in control)
- **[Auto Reload]**: Alpaca Pilot will automatically reload when it detects it is on a different version or protocol than the Driver
- **[IPv6 Discovery]**: Revamped IPv6 Alpaca Discovery for support on MacOS, Linux and Windows.
- **[Chart Axes]** Show angles in Degrees, Arc-minutes, and Arc-seconds on all charts (instead of decimal degrees).
- **[Chart RMSError projection]** Apply cos(Dec) and cos(Alt) scaling to RA/Az RMS error to correct for polar projection effects.
- **[Deviation Charts]** Add ΔTopographic and ΔMotor charts to PID Tuning page to remove underlying sidereal trends and show SP deviation only.

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
* Stellarium Desktop v26.2 Qt6 Windows (recommended)
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
  