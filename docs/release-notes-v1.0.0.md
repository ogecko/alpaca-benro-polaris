# Release Notes

## Alpaca Benro Polaris Driver  
**Version:** 1.0.0  
**Release Date:** 29-September-2024   
**Availability:** Download from https://github.com/ogecko/alpaca-benro-polaris    
**Win11 Install:** Demonstration Video at https://youtu.be/ipbWT54afhY    
**MacOS Install:** Demonstration Video at https://youtu.be/ZT91dpLObP8


## New Features (enabled by StellariumPLUS)
- **[Telescope Control]**: Provides comprehensive control over the telescope.
- **[Larger Catalog]**: Includes an extensive catalog of celestial objects, surpassing the BP App.
- **[GOTO Coordinates]**: Command the Benro Polaris to move to a selected target  with a simple click.
- **[Move Axis]**: Control the primary and secondary axes of the Benro Polaris for precise adjustments.
- **[Move Rate]**: Adjust the movement speed across a continuous range from slow to fast.
- **[Slewing Status]**: Monitor the Polaris movement status as it slews to a new target. 
- **[Aligned Status]**: Indicates the alignment status of the Polaris.
- **[Reticle Position]**: Instantly recognize the telescope’s current pointing position.
- **[Reticle FOV]**: Customize the reticle size to match your camera and lens setup for accurate framing.
- **[Sync Coordinates]**: Improve aiming accuracy by syncing with a known celestial object.
- **[Sync Alignment]**: Ensure Polaris alignment by syncing with a known celestial object.
- **[Sync Location]**: Send Stellarium’s site altitude and azimuth to the driver for accurate positioning.
- **[Sync Time]**: Check that Stellarium and Driver times are in sync for precise tracking.
- **[Network Comms]**: Connects to the driver over the network using the SynScan protocol.
- **[OS Supported]**: Supports IOS and Android.
- **[Hardware Supported]**: Supports iPad, Tablets and Mobile Phones.

## New Features (enabled by Stellarium Desktop)
- **[Telescope Control]**: Provides comprehensive control over the telescope.
- **[Even Larger Catalog]**: Includes an extensive catalog of celestial objects, surpassing the BP App.
- **[What’s Up Tonight]**: A tool for planning the best celestial objects to observe.
- **[GOTO Coordinates]**: Command the Benro Polaris to move to a selected target  with a simple click.
- **[Slew Telescope To]**: More flexible dialog to control Polaris target selection and syncing.
- **[Reticle Position]**: Instantly recognize the telescope’s current pointing position.
- **[Reticle FOV]**: Customize the reticle size to match your camera and lens setup for accurate framing.
- **[Sync Coordinates]**: Improve aiming accuracy by syncing with a known celestial object.
- **[Sync Alignment]**: Ensure Polaris alignment by syncing with a known celestial object.
- **[Full Customization]**: Allows users to customize what is shown and how it is shown. 
- **[App Extendability]**: A library of plug-ins that add additional functionality to the application.
- **[Win11 Network]**: Connects to the driver over the network using Alpaca protocol.
- **[MacOS Network]**: Connects to the driver over the network using Binary protocol.
- **[OS Supported]**: It supports MacOS, Linux and Windows.
- **[Hardware Supported]**: It supports Laptops and Desktops.

## New Features (enabled by Nina)
- **[Telescope Control]**: Provides comprehensive control over the telescope.
- **[Larger Catalog]**: Includes an extensive offline catalog of celestial objects, surpassing the BP App.
- **[GOTO Coordinates]**: Command the Benro Polaris to slew to a selected target.
- **[Abort Slew]**: Immediately stop the Benro Polaris movement during a slew operation.
- **[Park UnPark]**: Reset the three Benro Polaris axes position.
- **[Tracking Control]**: Enable or disable the Polaris sidereal tracking.
- **[Move Alt/Az Axis]**: Control the azimuth and altitude axes for precise adjustments.
- **[Move Equatorial Axis**]: Control the right ascension and declination axes for precise adjustments.
- **[Move Rate]**: Adjust the movement speed across a continuous range from slow to fast.
- **[Equipment Setup]**: Support discovering and connecting various astronomy equipment.
- **[Sky Atlas]**: Enables offline searching and filtering of deep sky objects.
- **[Framing Images]**: Helps visualize and plan shots offline, including panoramas.
- **[Flat Wizard]**: Finds optimal exposure settings and captures flat images for stacking.
- **[Target Sequencing]**: Plan target slewing, centering, syncing, and image capture.
- **[Image Capture]**: Allows for live monitoring and control of image capture.
- **[Options Settings]**: Allows customization of image directories and naming conventions.
- **[Autofocus Run]**: Optimize the focusing of your lens, initiated manually or within a sequence.
- **[Star Detection]**: Robust star detection algorithm with annotations, history, and customization.
- **[Plate Solving]**: Identifies Polaris orientation by matching stars in an image to a database.
- **[Target Centering]**: Iteratively aims the Polaris at a target using plate-solving until within tolerance.
- **[Sync Aligning]**: Aligns the Polaris with a known celestial object by observation or plate solving.
- **[3 Point Alignment]**: Accurately polar align a telescope using three reference points.
- **[N Point Alignment]**: Accurately polar align a telescope using multiple reference points.
- **[Drift Correction]**: Compensate for the telescope’s drift-off target.
- **[Tilt Analysis]**: Allows review of SyncOffsets around the 360° Azimuth axis
- **[Simple Setup]**: Allows Polaris compass and polar alignment with a single plate-solve.
- **[Network Comms]**: Connects to the driver over the network using Alpaca protocol.
- **[OS Supported]**: Supports Windows.
- **[Hardware Supported]**: Supports Laptop, Desktop, MiniPC, SurfacePC
- **[Client Supported]**: Supports Local UI, Remote Desktop, and Mobile Remote Desktop Apps.
- **[Cameras Supported]**: Support additional camera models through the ASCOM platform.
- **[Sony Nina Plugin]**: Supports Sony Cameras and Lens. 

## New Features (Alpaca Driver)
- **[ASCOM ConformU]**: Passes standard validation tests for ITelescopeV3.
- **[Driver Discovery]**: Provides Alpaca Discovery services.
- **[ASCOM Alpaca Protocol]**: Supports the ASCOM Alpaca protocol.
- **[SynSCAN Protocol]**: Supports the SynSCAN protocol (for StellariumPLUS).
- **[Stellarium Binary Protocol]**: Supports the Binary Protocol (for MacOS Stellarium Desktop).
- **[Polaris Protocol]**: Supports the Benro Polaris protocol.
- **[Refraction Correction]**: Adjusts for atmospheric refraction to improve aiming accuracy. 
- **[Aim Correction]**: Adjusts for consistent Polaris inaccuracy on goto Alt/Az.
- **[Time Correction]**: Adjusts for time delay caused by Polaris backlash removal.
- **[Pointing Model]**: Support Alt/Az and RA/Dec Sync Offset pointing models.
- **[Goto Coordinates]** Supports GOTO target, Alt/Az, Ra/Dec. Sync or aSync.
- **[Move Axis]**: Controls the movement of primary, secondary and tertiary axes.
- **[Move Equatorial]**: Controls the movement of RA, Dec axes.
- **[Park Unpark]**: Allows reset of all axis positions.
- **[Sync Aligning]**: Aligns the Polaris with a known celestial object by observation or plate solving.
- **[N Point Alignment]**: Accurately polar align a telescope using multiple reference points.
- **[Drift Correction]**: Compensate for the telescope’s drift-off target.
- **[Tilt Analysis]**: Allows review of SyncOffsets around the 360° Azimuth axis
- **[Simple Setup]**: Allows Polaris compass and polar alignment with a single plate-solve.
- **[Configurable Settings]**: Allows tailoring of Driver behavior via config.toml
- **[Site Location]**: Allows command line parameters, config.toml, Synscan, and Alpaca location sync.
- **[AHRS Data Logging]**: Logs data from the Attitude and Heading Reference System (AHRS).
- **[Move Rate Data Logging]**: Logs movement rates of the telescope’s axes.
- **[Diagnostics Logging]**: Captures detailed logs of system operations and errors.
- **[Watchdog Timer]**: Monitors the health of the Driver/Polaris, taking action when needed.
- **[Comms Recovery]**: Automatically recovers communication with applications. 
- **[Network Comms]**: Connects to the Polaris over the WiFi network
- **[Nina Support]**: Support the latest version of Nina
- **[Stellarium Desktop Support]**: Support the latest version of Stellarium Desktop.
- **[StellariumPLUS Support]**: Support the latest version of StellariumPLUS for mobile.
- **[Dark Site Support]**: Allows operation, even without an internet connection.
- **[OS Supported]**: Supports Windows, Linux, MacOS, RaspberryOS, Docker.
- **[Hardware Supported]**: Supports Laptop, Desktop, MiniPC, SurfacePC, Raspberry Pi
- **[Client Supported]**: Supports Local UI, Remote Desktop, and Mobile Remote Desktop Apps.
- **[Cameras Supported]**: Support additional camera models through the ASCOM platform.
- **[Video Demonstrations]**: Visual demonstrations of installation and operation.
- **[Full Documentation]**: Hardware, Installation, Nina, Stellarium, Troubleshooting and FAQ Guides.

## Untested New Features
Please let us know if you can try any of these features.
- **[Raspberry Pi]**: Supports running on Raspberry Pi Zero2, Pi 4, and Pi 5.
- **[Docker Support]**: Supports running in Docker containers.
- **[Lumix Nina Plugin]**: Supports Panasonic Lumix Cameras and Lens. Untested.
- **[Pentax on ASCOM]**: ASCOM Camera driver supports a range of cameras. Untested.

## Bug Fixes (from Beta versions)
- **[BP Keepalive]**: Implement Wifi Keepalive, reduce phone battery usage, by closing BP App.
- **[AHRS Keepalive]**: Ensure AHRS continues to inform of position updates.
- **[Stelarium Lag]**: Longevity testing of Stellarium introduced lag in position readout.
- **[Network Recovery]**: Improved network communications recovery.
- **[Network Exceptions]**: Handle more Win and MacOS network exceptions.
- **[Park Reliability]**: Ensure tracking is disabled before Parking.
- **[Sync Function]**: Correct Sync operation to pass ConformU tests.
- **[Sync To Polaris]**: Implement alignment command for Polaris.
- **[Refraction Correction]**: Adjusts for atmospheric refraction to improve the accuracy. 
- **[StellariumPLUS coord]**: Translate SynScan Epoch to J2000.
- **[Move Rate Continuity]**: Improve Move Rate continuity from 5.01 to 6.00.
- **[Install Guide]**: Improve MacOS and Win installation guide based on Beta feedback.
- **[Docs Improvement]**: Numerous documentation improvements and better troubleshooting.

## Tested Compatible Hardware and Software
### Photography Equipment
* Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.40, Astro V1.0.2.11
* Canon R5, RF135mm, RF800mm
* Canon R6 Mk II connected via USB3
* Canon R, 16mm 2.8, 24-240mm f4-6.3
* Canon 6D MkII, Canon EF 50mm f1.8
* Canon 800D, Sigma DC 17-50mm f2.8, Tamron 16-300mm f3.5-6.3
* Nikon Z8 (z14-24mm F2.8)
* Sony Alpha 7R IV
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
* Benro Polaris Android App v3.0.27, iOS App v1.4.4,
* Stellarium Mobile PLUS v1.12.9 Android and iOS.
* Stellarium Desktop v24.2.0 Windows
* Nina v3.1.1.9001, HocusFocus v3.0.0.17, ASTAP 2024.08.11
* Nina v3.1.2.9001, HocusFocus v3.0.0.18, LensAF v2.1.0.2, Scope Control  v2.0.2.0
* CCDciel Version beta 0.9.87-3346 Windows
* Siril v1.2.3 de49749
### Drivers
* ASCOM Platform 7 RC7
* ASCOM Platform 6.6 SP2
### Operating Systems
* Windows 11 Pro v23H2
* Windows 10
* MacOS Sonoma 14.6.1
* MacOS Sequoia 15
* iOS 17.6  
* iPadOS v17.6.1
  

## Known Issues
- **[Sky Safari 7 Plus]**: One Beta tester was unable to connect to Sky Safari 7 Plus.

## Potential Future Enhancements
- **[Raspberry Pi]** Official support and testing on Raspberry  Pi
- **[Docker Support]** Official support and testing on Docker.
- **[Sky Safari]** Official support and testing on Sky Safari.
- **[CCDciel Support]**: Official support and testing for CCDciel for MacOS.
- **[Stellarium MacOS]**: Add position update support to the Stellarium Binary protocol.
- **[Software Delivery]**: Deliver as an App rather than a zip file, eliminating the command line.
- **[WiFi Setup]**: Eliminate the need for BP App to set up Polaris WiFi Hotspot.
- **[Astro Mode Setup]**: Eliminate the need for the BP App to manually change mode to Astro and align.
- **[Setup GUI]**: Deliver a Graphical UI to manage config.toml and provide a base UI. 
- **[Control GUI]**: Deliver a Graphical UI for Telescope Control, as a multi-platform web app.
- **[Drift Repport]** Develop an automated test for drift over a movable range of Polaris.
- **[INDI support]**: Add support for INDI protocol, enabling apps like KStars.
- **[Emedded Driver]**: The driver should be embedded on the Benro Polaris Device. Benro Change.
- **[Pulse Guiding]**: Allow micro-move axis commands while tracking without backlash. Benro Change.

## Deprecations
- **[None Known]**: No features deprecated as this is the first release.
  