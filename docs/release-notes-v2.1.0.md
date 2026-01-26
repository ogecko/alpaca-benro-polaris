[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Release Notes

## Alpaca Benro Polaris Driver  
* **Version:** 2.1.0 Beta1
* **Release Date:** TBD 
* **Availability:** Download from [Alpaca Driver v2.1.0 Download ZIP](https://github.com/ogecko/alpaca-benro-polaris/archive/refs/tags/v2.1.0.zip)
* **License:** Distributed exclusively for backers of the [Kickstarter Project](https://www.kickstarter.com/projects/jdmorriso/alpaca-benro-polaris-driver-v20?ref=d1hx2v)
* **Current Branch:** releases/2_1_0_beta1

## Demonstration Videos
* **20 - Podcast Video:** Podcast Video at https://youtu.be/KUBCTnEsnlE
* **21 - Preview Demo:** Demonstration Video at https://youtu.be/0QSKD1GCzOc
* **22 - Starting and Using:** Demonstration Video at https://youtu.be/Wv_ZvBtZZ4Q
* **23 - Rotator Framing:** Demonstration Video at https://youtu.be/_Swd-jIyQis
* **24 - Multi Point Alignment:** Demonstration Video at https://youtu.be/4CMO0R_yphw
* **25 - Equipment Safety:** Demonstration Video at https://youtu.be/45EP-DExSOQ
* **26 - Tracking Orbitals:** Demonstration Video at https://youtu.be/no47ZNagEDk
* **27 - Pulse Guiding:** Demonstration Video at https://youtu.be/dn1nLxT5eWw
* **28 - Panoramas:** Demonstration Video at TBD
* **31 - Kalman Filter:** Demonstration Video at https://youtu.be/aDFKAWBNQHU
* **32 - Speed Calibration:** Demonstration Video at https://youtu.be/U_0-mBDuTjE
* **33 - PID Tuning:** Demonstration Video at https://youtu.be/6vJbSb0gl3M

## Win11 Upgrade Instructions
* Uninstall Python 3.12.7
* Remove old `C:\Users\Nina\Documents\alpaca-benro-polaris>` directory.
* Follow the standard [Installation Guide](./installation.md) to install the new version of Python, the Alpaca Driver and its requirements.txt
* WARNING: Update Stellarium Desktop Telescope Settings for Alpaca Driver V2.0
    * Recreate the Stellarium Desktop ASCOM Settings, as the Alpaca Driver name has changed in V2.0
    * Change the ASCOM Telescope Co-ordinate System to "Equinox of the date (JNow)", as this is the default for Alpaca Driver V2.0
    * Nina does not need to change, as it reads the correct settings from the Alpaca Driver

## What's new in v2.1.0 
- **[Panorama Settings]** Add flexible Panorama Grid for Landscape (untracked), Sky (Horizon-Locked), Sky (tracked), that can be revisted, reordered and reused.
- **[Panorama Calculator]** Use the Panel Spacing Calculator to determine your sensor’s field of view (FOV) and the recommended panel step for a desired image overlap.
- **[Panorama Automation]** Add device actions PanoGrid and PanoSlew for automation in Nina Advanced Sequencer and CCDScripts
- **[Panel Navigation]** Add optional Panel navigation controls on the main dashboard
- **[Advanced Sequencer]** Add Panorama Actions for use in Nina's Advanced Sequencer and Templates.
- **[Meteor Calendar]** Added a link to the International Meteor Organization’s Meteor Shower Calendar on the Comets page.
- **[Sky Conditions]** Added a Sky Conditions page providing sunrise and sunset times, moonrise and moonset, eclipse data, cloud cover, jet stream forecasts, and light pollution information.
- **[Stop Driver]** The Alpaca Pilot Connect page now allows you to stop the Alpaca Driver directly.
- **[Class Documentation]** Added definitions of Catalog Class object classification codes to pilot.md to help guide imaging and filter strategy.
- **[Flat Frames]** Added a flat-frame orientation example to catalog.sample.json
- **[Config Updates]** Stream config updates so that all Alpaca Pilot Clients receive the new configuration settings immediately (used for Panoramas) 

## New Features (enabled by Nina)

## New Features (enabled by Stellarium)

## Upgraded Win11 Requirements.txt Compatibility
- **[Python 3.13.9]**: Upgraded Python support from 3.13.5.
- **[Python 3.13.5]**: Upgraded Python support from 3.13.1.
- **[Uvicorn 0.35.0]**: Upgraded Uvicorn support from 0.33.0.
- **[Ephem 4.2]**: Upgraded Ephem support from 4.1.6.
- **[numpy 2.3.2]**: Upgraded numpy support from 1.24.4.
- **[scipy 1.16.1]**: Upgraded scipy support from 1.16.0.

## Documentation (Alpaca Driver)
- **[Nina Advanced Sequencer]**: Add documentation on using Nina's advanced sequencer with Alpaca Driver
- **[Auto Guiding]**: Add documentation on using PHD2 for auto-guiding 
- **[Auto Power On]**: Add hardware note for Mele Quieter 4C to use BIOS settings for **Auto Power On**
- **[Troublshooting A5]**: Add resolution to http.sys claiming port 80
- **[Troublshooting B6]**: Add description on how to reset Polaris password

## Untested New Features
Please let us know if you can try any of these features.
- **[Lumix Nina Plugin]**: Supports Panasonic Lumix Cameras and Lens. Untested.
- **[Pentax on ASCOM]**: ASCOM Camera driver supports a range of cameras. Untested.

## Bug Fixes (from v2.0.0 version)
- **[fix #62]**: Alpaca Driver SupportedActions method incorrectly lists "Polaris:J2000GotoPolaris:Ack" as a single action
- **[fix #68]**: Setting an Az/Alt/Roll target may intermittently be ignored due to race condition from the tracking loop
- **[fix #70]**: Correctly detect and resolve potential gimbal lock solutions where second mechanical axis is near zero.
- **[fix #71]**: Alpaca Pilot Sidebar Menu should only highlight the active catalog link (not all catalog links).

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
* Nina v3.1.1.9001, HocusFocus v3.0.0.17, ASTAP 2024.08.11
* PHD2 v2.6.14
* CCDciel Version beta 0.9.87-3346 Windows
* GraXpert 3.1.0rc2
* Siril v1.4.0
* Siril v1.2.5
* Siril v1.2.3 de49749
### Drivers and Utilities
* Windows Remote Desktop v10.0.22621
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

## Known Issues
- **[Gimbal Lock]**: There is potential gimbal lock at low or negative altitudes. Especially at Azimuth ≈ 0°, Altitude ≈ 0°, Roll ≠ 0°. Please watch mount at all times.
- **[Python 3.14.0]**: Pyephem is does not have a compiled version for 3.14 as of end Nov 2025. Use Python 3.13.9 instead.


## Potential Future Enhancements
- **[Stellarium MacOS]**: Add position update support to the Stellarium Binary protocol.
- **[Software Delivery]**: Deliver as an App rather than a zip file, eliminating the command line.
- **[INDI support]**: Add support for INDI protocol, enabling apps like KStars.
- **[Emedded Driver]**: The driver should be embedded on the Benro Polaris Device. Benro Change.

## Deprecations
- **[RA 1.04]**: Special RA Axis move command in V1.0 has been replaced with Alpaca Pilot direct RA radial dial control.
- **[N-Point Alignment]**: N-Point Alignment in V1.0 has been replaced with Multi-Point Alignment
  