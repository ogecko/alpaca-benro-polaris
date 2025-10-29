# Release Notes

## Alpaca Benro Polaris Driver  
* **Version:** 2.0.0 Beta3
* **Release Date:** 31-Oct-2025   
* **Availability:** Download from https://github.com/ogecko/alpaca-benro-polaris
* **Current Branch:** releases/2_0_beta3 
* **Podcast Video:** Podcast Video at https://youtu.be/KUBCTnEsnlE
* **Demo Video 1:** Demonstration Video at https://youtu.be/0QSKD1GCzOc 
* **Demo Video 2:** Demonstration Video at https://youtu.be/Wv_ZvBtZZ4Q
* **Speed Calibration:** Demonstration Video at https://youtu.be/U_0-mBDuTjE

## Win11 Upgrade Instructions
* Uninstall Python 3.12.7
* Remove old `C:\Users\Nina\Documents\alpaca-benro-polaris-main>` directory.
* Follow the standard [Installation Guide](./installation.md) to install the new version of Python, the Alpaca Driver and its requirements.txt
* WARNING: Update Stellarium Desktop Telescope Settings for Alpaca Driver V2.0
    * Recreate the Stellarium Desktop ASCOM Settings, as the Alpaca Driver name has changed in V2.0
    * Change the Telescope Co-ordinate System to "Equinox of the date (JNow)", as this is the default for Alpaca Driver V2.0
    * Nina does not need to change, as it reads the correct settings from the Alpaca Driver

## What's new since beta2
- **[Epoch Change]** Changed default epoch from J2000 to Jnow for all live co-ordinates (recommended default from ASCOM)
- **[Goto Timeout]** When a GOTO does not achieve GOTO tolerance after 45s, it will stop the motors and return to IDLE
- **[Weighted Sync]** Syncs with higher recency, closer proximity, or closer to the pole are given more weight in multi-point alignment
- **[Limit Syncs]** Limit to a maximum of 10 sync points, discarding lowest-weighted points when new syncs performed.
- **[Sync Diagnostics]** Added a new Driver Log Setting to optionally log the weights when calculating the QUEST model.
- **[Bluetooth LE]** Improved handling of Bluetooth LE on MacOS
- **[Warning Banner]** Show warning banner on Connection Page as well as every other page
- **[Park Notification]** Pilot notifies that you Cannot perform find Home while Parked
- **[Catalog Search]** When searching catalog for specific DSO, allow below horizon and near zenith
- **[Home Parked]** Notify that you cannot find Home while the mount is Parked.
- **[PID Tuning]** Adjust default PID tuning, increase Kp to 1.0, increase Ki to 0.05, decrease Kd to 0.5
- **[Issue #52]** Fixed Home and Park do not work after 45s has expired since last goto
- **[Issue #53]** Improve Pilot Radial Dial click on scale compatibility with Firefox Browser

## What’s new since beta1
- **[PID Integral]** Corrected integral component calculation for better error convergence to zero
- **[PID Acceleration]** Increased default max acceleration from 3 to 5°/s² for quicker response
- **[PID Tuning]** Added a full PID Tuning page with support for goto, slew, pulse tests, and full parameter exposure
- **[Guide Rate]** Pulse Guide rates can now be configured directly from Alpaca Pilot Settings
- **[Chart UX]** Improved chart behavior on resize, smoother scrolling, and consistent color mapping for SP, PV, OP, Mx
- **[Chart Legends]** All charts now include trace legends
- **[Chart Statistics]** Performance metrics now displayed on all charts
- **[M1–M3 Readout]** Dashboard now shows absolute angle readouts for motors M1, M2, and M3
- **[Find Home]** New feature to return the mount to true Home (M1 = M2 = M3 = 0), safely unwinding cables
- **[Set Park]** Park location is now customizable
- **[Advanced Park]** Rewritten Park logic for ASCOM compliance — smoother, interruptable, and PID-driven
- **[Parking & Homing]** New PID states added to monitor transitions to Park and Home positions
- **[NINA Support]** Find Home, Set Park, Park, and UnPark are now accessible from any Alpaca client, including NINA and Alpaca Pilot
- **[Celestial Poles]** North and South Celestial Poles added to the catalog for easier alignment
- **[QUEST Paper]** A research paper on QUEST has been added to the documentation

Let me know if you want a changelog version, a markdown export, or a short announcement for Discord or GitHub.

- **[Chart UX]** Improve charts for resize, smooth scroll and color consistency across app for SP, PV, OP, Mx.
- **[Chart Legends]** Add trace legend to all charts
- **[Chart Statistics]** Add performance statistics to all charts
- **[M1-3 readout]** Add absolute angle readouts for motors M1, M2, M3 on dashboard
- **[Find Home]** Returns mount to true Home position (M1=M2=M3=0), unwinding cables. 
- **[Set Park]** Ability to customise the Park location.
- **[Advanced Park]** Rewrite V1.0 Park to be more ASCOM compliant. Uses PID controller, smoother Park, interruptable, unwinds.
- **[Parking, Homing]** Add new PID states for monitoring transition to Park and Home positions
- **[Nina Support]** Find Home, Set Park, Park and UnPark are accessable from any Alpaca Client, including Nina, Alpaca Pilot and others.
- **[Celestrial Poles]** Added North and South Celestrial Poles to the catalog to easy alignment
- **[QUEST Paper]** Added a research paper on QUEST in docs

## Beta Agreement
Please read and confirm your agreement with [Beta Agreement](./beta_agreement.md) if you havent already.


## New Features (Alpaca Pilot)
- **[Modern App]**: Alpaca Pilot offers an elegant, adaptive UI for control and management of Alpaca Drivers
- **[Responsive UI]**: Adapts seamlessly to phones, tablets, and desktops for a consistent experience across devices
- **[Live Dashboard]**: Real-time telemetry of current Azimuth, Altitude, Roll, Right Ascension, Declination, Position Angle, and Local Sidereal Time
- **[Dashboard Status]**: Display mount state including parked, tracking, slewing, gotoing, PID active, and pulse guiding
- **[Motor Activity]**: Indicate motor activity and speed on the dashboard
- **[Interactive Dials]**: Precision radial dials with zoomable scales for accurate readout and tap-to-set angular targeting
- **[Radial Scales]**: Show warning limits on angles; fix wraparound and pointer issues near ±90° and 360/0
- **[Quick Actions]**: Floating action buttons for axis control; commands for Eq-Az toggle, park, unpark, abort, track, and tracking rate
- **[Manual Slew]**: Slew manually by Alt/Az/Roll or RA/Dec/PA with adjustable slew rate
- **[Connection Page]**: Connect to Benro Polaris without the Benro App; discover nearby devices via Bluetooth LE and enable WiFi
- **[Configuration Page]**: Instantly view and modify Alpaca Driver settings; save and restore configuration changes
- **[Map Verification]**: Display site coordinates on an interactive map to visually confirm the location
- **[Site Autocomplete]**: Automatically retrieve location name, elevation, and current pressure via external web services
- **[Battery Level]**: Shows charging state and battery percentage in the Alpaca Pilot heading bar
- **[Log Streaming]**: - Real-time remote monitoring of Alpaca Driver log activity; includes log viewer and log level control
- **[Nina integration]**: Launch Alpaca Pilot directly from the Settings Cogs in NINA’s Equipment tab
- **[PWM Testing]**: Dedicated PWM test page with improved SLOW speed handling
- **[Speed Calibration]**: Speed calibration test management with cancel and hookup support
- **[Position Diagnostics]**: Dedicated diagnostics page for mount position and movement
- **[Alignment Tools]**: Single-point and multi-point alignment using Polaris internal model and QUEST modeling; sync with map landmarks and RA/Dec or Az/Alt coordinates
- **[Sync Analysis]**: Residual display, editing, and removal of sync points; tripod level correction
- **[Rotator Support]**: Full rotator control including Halt, Sync, Reverse, MoveRel, MoveAbs, MoveMech, Position(PA), TargetPosition(PA)
- **[Target Catalog]**: Expanded catalog with search, filter, pagination, and sync/goto integration
- **[Imaging Enhancements]**: Long exposure stabilization, auto-leveling, Zenith imaging, drift suppression, and dithering support

## New Features (Alpaca Driver)
- **[Alpaca Actions]**: Expose extended ASCOM Actions for Driver Restart, Config Service Control
- **[Task Orchestration]**: Streamlined task lifecycle management with coordinated creation and teardown
- **[Configuration Service]**: Enhanced config handling with support for saving overrides and restoring defaults
- **[Network Services]**: Unified control over network services and port bindings for cleaner security management
- **[Web Service]**: Introduced embedded Web and Sockets Service to host the Alpaca Pilot Single Page Application
- **[Log Services]**: Aligned logging configuration across all network services
- **[Log Files]**: Default log output now directed to the `logs` directory (previously `driver`)
- **[Driver Startup]**: Driver version now logged on startup for traceability
- **[Field Rotation]**: Field Rotation derived from Polaris quaternion data in 518 messages
- **[Image Cleanup]**: Added scatter plots to visualize rejected images based on statistical thresholds
- **[CORS Middleware]**: Integrated middleware for Cross-Origin Request support
- **[Testing Framework]**: Introduced testing framework for Alpaca Driver validation and regression checks
- **[Performance Enhancements]**: Improved tracking precision, Kalman Filter tuning, and motor calibration persistence

## New Features (ASCOM Alpaca Rotator support)
- **[ASCOM Rotator]** Implement the ASCOM Alpaca Rotator device standard
- **[Nina Integration]** Support Nina Equipment tab and Rotator Control
- **[Paralactic Angle]** Parallactic Angle, Position Angle and Roll Angle Targeting
- **[Direct Slew]** Direct Slew to Defined Angular Pose

## New Features (ASCOM Alpaca FindHome, SetPark, Park, UnPark support, using Telescope v4 standard)
- **[Find Home]** Returns mount to true Home position, unwinding cables. 
- **[Set Park]** Ability to customise the Park location.
- **[Advanced Park]** Rewrite of Benro Polaris Park from V1.0 to be more ASCOM compliant. Uses PID controller, smoother Park, interruptable, unwinds, custom locations.
- **[Nina Support]** Find Home, Set Park, Park and UnPark are accessable from any Alpaca Client, including Nina, Alpaca Pilot and others.

## New Features (Advanced Position Control Algorithm)
- **[Kinematic Solver]** Quaternion-based kinematics and inverse solutions
- **[PID Tuning]** Optimised PID Control for mount orientation control from Alpaca Driver
- **[Motor Control]** Independant Motor Speed Control
- **[Rate Interpolation]** Angular Rate Interpolation Framework
- **[Angular Metrics]** Real-time Angular Position and Velocity Measurement
- **[Orientation Filter]** Orientation Estimation via Kalman Filtering
- **[Speed Profiling]** Speed Calibration & Response Profiling
- **[Input Normalisation]** Speed Control Input Normalisation across SLOW and FAST Polaris commands
- **[Constraint Limiting]** Constraint-Aware Position, Velocity and Acceleration Limiting
- **[Motor Limits]** Add Motor Angle Limit for anti-windup protection

# New Features (Ephem Position Calculation)
- **[Orbital Positioning]** Accurate Orbital Positioning of Earth and Target Body
- **[Light Compensation]** Light Travel Time Compensation for Apparent Position
- **[Epoch Alignment]** Epoch-Based Coordinate Precession Alignment
- **[Relativistic Deflection]** Relativistic Light Deflection near Solar Limb
- **[Nutation Correction]** Earth Nutation Correction (Polar Axis Wobble)
- **[Velocity Aberration]** Aberration of Light Due to Earth’s Orbital Velocity
- **[Refraction Modeling]** Atmospheric Refraction Modeling (Pressure & Temperature Based)
- **[Parallax Offset]** Observer-Based Parallax Offset Correction
- **[Geocentric Generation]** Astrometric Geocentric Coordinate Generation
- **[Position Refinemen]** Apparent Geocentric Position Refinement
- **[Topocentric Output]** Topocentric Apparent Coordinate Output (RA, Dec, PA | Alt, Az, Roll)

# New Features (Precision Goto Control)
- **[Trajectory Planning]** Kinematically Optimised Mount Trajectory
- **[Loop Accuracy]** Improved Goto accuracy through closed loop control
- **[Roll Targeting]** Goto allows specifying a roll angle for precise orientation
- **[Fixed Movement]** Goto allows moving to a fixed terrestrial coordinate (without auto-enabling tracking mode)
- **[Realtime Control]** Real time Goto initiation and interruption (no need to wait for previous commands to finish)
- **[Motion Smoothing]** Smooth acceleration and deacceleration profiles
- **[Backlash Removal]** Benro Polaris backlash removal process eliminated

## New Features (Precision Slew Control)
- **[Roll Stability]** Improved roll movement (Azimuth and Altitude are maintained during roll movement)
- **[Vertical Stability]** Improved vertical movement (Altitude axis now moves directly upward, even when the mount is tilted)
- **[Speed Boost]** Increased Maximum Alpaca Axis Speed to 8.4 degrees/s
- **[Interruptable Slew]** Slew supports real-time interruption
- **[Az/Alt/Roll Slew]** Slew by Azimuth, Altitude, and Roll coordinates (replaces direct motor axis control)
- **[RA/Dec/PA Skew]** Slew by Right Ascension, Declination and Polar Angle (when tracking enabled)

## New Features (Precision Tracking Control)
- **[Tracking Rates]** Support ASCOM Alpaca Drive Rate Config (0=Sidereal, 1=Lunar, 2=Solar, 3=King)
- **[Reduced Drift]** PID Control of Target position for zero drift and closed loop tracking
- **[Feed Forward]** Feedforward control anticipates motion and tracking sidereal velocities
- **[Deep-Sky Tracking]**: Support for tracking deep-sky objects with high precision
- **[Pulse Guiding]**: ASCOM Pulse Guide API support; Nina Dithering and PHD2 integration

## New Features (enabled by Nina)
- **[Nina and Nikon Z8]**: Nina v3.2 now supports Nikon Z8 cameras 

## New Features (enabled by Stellarium)
- **[Qt6 Support ]**: Latest Stellarium verision is supported (Qt6 UI library works with ASCOM Platform 7)

## Upgraded Win11 Requirements.txt Compatibility
- **[Python 3.13.5]**: Upgraded Python support from 3.13.1.
- **[Uvicorn 0.35.0]**: Upgraded Uvicorn support from 0.33.0.
- **[Ephem 4.2]**: Upgraded Ephem support from 4.1.6.
- **[numpy 2.3.2]**: Upgraded numpy support from 1.24.4.
- **[scipy 1.16.1]**: Upgraded scipy support from 1.16.0.

## Documentation (Alpaca Driver)
- **[Troublshooting B6]**: Add description on how to reset Polaris password
- **[Troublshooting B7]**: Add link to Polaris User Manual
- **[Troubleshoot C1b]**: Describe how to define Manual Network settings to force IPv4 setup
- **[Gemini EAF]**: Add instructions to install Gemini EAF Driver
- **[Mobile Hotspot]**: Add instructions to use Registry to start the Mobile Hotspot

## Untested New Features
Please let us know if you can try any of these features.
- **[Raspberry Pi]**: Known problems running on Raspberry Pi Zero2, Pi 4, and Pi 5.
- **[Lumix Nina Plugin]**: Supports Panasonic Lumix Cameras and Lens. Untested.
- **[Pentax on ASCOM]**: ASCOM Camera driver supports a range of cameras. Untested.

## Bug Fixes (from v1.0.0 version)
- **[Fix #024]**: First GOTO after a PlateSolve and SYNC, may overcorrect the offset by 2x the right amount.
- **[Fix #023]**: Docker build process is now working.
- **[Fix #018]**: Explicitly check for 'NaN' on all float inputs on REST API.
- **[Fix #019]**: Ensure SynScan RA/Dec/Lat/Lon/etc are all range and 'NaN' checked.
- **[Fix #020]**: Implement AbortSlew with SynScan protocol 'M' for Stellarium.
- **[Fix #036]**: Polaris protocol parsing should gracefully handle partially received messages.

## Tested Compatible Hardware and Software
### Photography Equipment
* Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.54, Astro V1.0.2.14
* Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.48, Astro V1.0.2.14
* Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.40, Astro V1.0.2.11
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
* MacBook Pro with Apple M1 Pro CPU (ABP Driver and CCDCiel)
* MacBook Pro 14” 2021 
* MacBook Pro 13” 2013
* Mele Quieter 4C, Intel N100 800Mhz (ABP Driver and Nina)
* Minis Forum UM350 (ABP Driver and Nina)
* ASUS Vivobook Pro 16X OLED K6604JV (ABP Driver and Nina)
* Laptop Windows 10 Home (ABP Driver and Nina)
* Desktop PC, AMD 7950X (Stellarium Desktop, Siril)
* Desktop PC, AMD Ryzen 5 3600
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
* Stellarium Desktop v24.2 Windows
* Stellarium Desktop v24.3 Qt5 Windows (not Qt6 version)
* Stellarium Desktop v25.2 Qt6 Windows (requires ASCOM Platform 7)
* Nina v3.1.1.9001, HocusFocus v3.0.0.17, ASTAP 2024.08.11
* Nina v3.1.2.9001, HocusFocus v3.0.0.18, LensAF v2.1.0.2, Scope Control  v2.0.2.0
* CCDciel Version beta 0.9.87-3346 Windows
* Siril v1.2.3 de49749
### Drivers and Utilities
* Windows Remote Desktop v10.0.22621
* ASCOM Platform 7 Update 3 RC7 (not Update 2 version)
* ASCOM Platform 7 RC7
* ASCOM Platform 6.6 SP2
### Operating Systems
* Windows 11 Pro v23H2, 
* Windows 10
* MacOS Sonoma 14.6.1
* MacOS Sequoia 15
* iOS 17.6  
* iPadOS v17.6.1
  

## Known Issues
- **[Gimbal Lock]**: There is potential gimbal loack at low altitudes. Please watch mount at all times.
- **[Stellarium 24.3]**: Stellarium Desktop v24.3 has known issues with telescope control. See [Troubleshooting S2](./troubleshooting.md).


## Potential Future Enhancements
- **[Raspberry Pi]** Official support and testing on Raspberry  Pi
- **[CCDciel Support]**: Official support and testing for CCDciel for MacOS.
- **[Stellarium MacOS]**: Add position update support to the Stellarium Binary protocol.
- **[Software Delivery]**: Deliver as an App rather than a zip file, eliminating the command line.
- **[WiFi Setup]**: Eliminate the need for BP App to set up Polaris WiFi Hotspot.
- **[Astro Mode Setup]**: Eliminate the need for the BP App to manually change mode to Astro and align.
- **[Setup GUI]**: Deliver a Graphical UI to manage config.toml and provide a base UI. 
- **[Control GUI]**: Deliver a Graphical UI for Telescope Control, as a multi-platform web app.
- **[INDI support]**: Add support for INDI protocol, enabling apps like KStars.
- **[Emedded Driver]**: The driver should be embedded on the Benro Polaris Device. Benro Change.
- **[Pulse Guiding]**: Allow micro-move axis commands while tracking without backlash. Benro Change.

## Deprecations
- **[None Known]**: No features deprecated as this is the second release.
  