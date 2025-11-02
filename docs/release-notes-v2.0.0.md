# Release Notes

## Alpaca Benro Polaris Driver  
* **Version:** 2.0.0 Beta4
* **Release Date:** 9-Nov-2025   
* **Availability:** Download from https://github.com/ogecko/alpaca-benro-polaris
* **Current Branch:** releases/2_0_beta4 

## Demonstration Videos
* **Podcast Video:** Podcast Video at https://youtu.be/KUBCTnEsnlE
* **Preview Demo:** Demonstration Video at https://youtu.be/0QSKD1GCzOc 
* **Starting and Using:** Demonstration Video at https://youtu.be/Wv_ZvBtZZ4Q
* **Rotator Framing:** Demonstration Video at https://youtu.be/_Swd-jIyQis
* **Speed Calibration:** Demonstration Video at https://youtu.be/U_0-mBDuTjE

## Win11 Upgrade Instructions
* Uninstall Python 3.12.7
* Remove old `C:\Users\Nina\Documents\alpaca-benro-polaris-main>` directory.
* Follow the standard [Installation Guide](./installation.md) to install the new version of Python, the Alpaca Driver and its requirements.txt
* WARNING: Update Stellarium Desktop Telescope Settings for Alpaca Driver V2.0
    * Recreate the Stellarium Desktop ASCOM Settings, as the Alpaca Driver name has changed in V2.0
    * Change the ASCOM Telescope Co-ordinate System to "Equinox of the date (JNow)", as this is the default for Alpaca Driver V2.0
    * Nina does not need to change, as it reads the correct settings from the Alpaca Driver

## What's new in beta4
- **[Nearby Catalog]** Enable side menu to show nearby catalog targets, sorted by angular proximity to current RA and Dec
- **[Delta Angles]** Relative angles can be entered using a 'd' prefix. eg entering 'd2' in the RA axis setpoint will increase the current value by 2 hours
- **[Partial Angles]** Partial angles can be entered using a ':' separator. eg entering ':2' means 2 arcmin, entering '::10' means 10 arcsec



## What's new in beta3
- **[Epoch Change]** Default epoch for live coordinates changed from J2000 to JNow (ASCOM-recommended)
- **[PID Integral]** Improved reliability of PID integral term: preloads with offset to cancel derivative, clamps to 3× sidereal rate
- **[PID Tuning]** Updated default PID parameters to improve responsiveness: increased Kp to 1.0, Ki to 0.05, and reduced Kd to 0.5
- **[PID Status]** Added PID Status chip to the tuning page for real-time GOTO completion monitoring
- **[Aiming Ajustment]** The default V1.0 Aiming Adjustment feature will be disabled as we no longer need forward aiming
- **[Chart Gridlines]** Highlight horizontal gridline at Y = 0 for better visibility on all charts
- **[GOTO Tolerance]** Reduced GOTO tolerance to 0.5 arcminutes to allow more time for tracking stabilization
- **[Goto Timeout]** If GOTO fails to reach tolerance within 45s, system returns to IDLE or TRACKING
- **[Sync Residual]** Enforce zero residual at the most recent sync, by applying a final local correction atop globally optimized multi-point alignment
- **[Weighted Sync]** Multi-point sync now prioritizes recent, nearby, and polar-adjacent points for improved global alignment
- **[Limit Syncs]** Capped sync history to 10 points; lowest-weighted entries are discarded when new syncs are added
- **[Sync Diagnostics]** New Driver Log setting enables optional logging of sync weights used in QUEST model calculations
- **[Bluetooth LE]** Enhanced Bluetooth Low Energy support on macOS
- **[Warning Banner]** Connection warnings now appear on all pages, including the Connection Page
- **[Park Notification]** Clear notification you cannot find Home while mount is Parked
- **[Catalog Search]** Catalog search now includes DSOs below horizon and near zenith
- **[Issue #52]** Fixed bug preventing Home and Park after 45s timeout post-GOTO
- **[Issue #53]** Improved radial dial click compatibility with Firefox browser
- **[FAQ B5]** Added FAQ documentation note on Benro Polaris load capacity
- **[ASCOM 7.1]** Verified compatibility with ASCOM Platform 7.1


## What’s new in beta2
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
* ASCOM Platform 7.1 (Build 4707)
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
### Alpaca Pilot compatible Browsers
* Firefox version 115+ 
* Google Chrome version 115+
* Microsoft Edge version 115+
* Apple Safari 14+

## Known Issues
- **[Gimbal Lock]**: There is potential gimbal loack at low altitudes. Please watch mount at all times.


## Potential Future Enhancements
- **[Raspberry Pi]** Official support and testing on Raspberry  Pi
- **[CCDciel Support]**: Official support and testing for CCDciel for MacOS.
- **[Stellarium MacOS]**: Add position update support to the Stellarium Binary protocol.
- **[Software Delivery]**: Deliver as an App rather than a zip file, eliminating the command line.
- **[INDI support]**: Add support for INDI protocol, enabling apps like KStars.
- **[Emedded Driver]**: The driver should be embedded on the Benro Polaris Device. Benro Change.

## Deprecations
- **[RA 1.04]**: Special RA Axis move command in V1.0 has been replaced with Alpaca Pilot direct RA radial dial control.
- **[N-Point Alignment]**: N-Point Alignment in V1.0 has been replaced with Multi-Point Alignment
  