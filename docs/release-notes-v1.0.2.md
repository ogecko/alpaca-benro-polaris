# Release Notes

## Alpaca Benro Polaris Driver  
**Version:** 1.0.2
**Release Date:** TBD   
**Availability:** Download from https://github.com/ogecko/alpaca-benro-polaris    
**Win11 Install:** Demonstration Video at https://youtu.be/ipbWT54afhY    
**MacOS Install:** Demonstration Video at https://youtu.be/ZT91dpLObP8

## Win11 Upgrade Instructions
* Uninstall Python 3.12.7
* Remove old `C:\Users\Nina\Documents\alpaca-benro-polaris-main>` directory.
* Follow the standard [Installation Guide](./installation.md) to install the new version of Python, the Alpaca Driver and its requirements.txt

## New Features (enabled by Nina)
- **[Nina and Nikon Z8]**: Nina v3.2 now supports Nikon Z8 cameras 

## New Features (enabled by Stellarium)
- **[Qt6 Support ]**: Latest Stellarium verision is supported (Qt6 UI library works with ASCOM Platform 7)

## New Features (Alpaca Driver)
- **[Log Files]**: The default logging location has changed from the `driver` directory to the `logs` direcotry
- **[Driver Startup]**: Log Alpaca Driver version number on startup
- **[Field Rotation]**: Calculate the current Field Rotation from quaternions in 518 msg from Polaris
- **[Image Cleanup]**: Add scatter plots to indicate rejected images based on key statistics

## Upgraded Win11 Requirements.txt Compatibility
- **[Python 3.13.5]**: Upgraded Python support from 3.13.1.
- **[Falcon 4.0.2]**: Upgraded Falcon support from 4.0.2.
- **[Uvicorn 0.33.0]**: Upgraded Uvicorn support from 0.33.0.
- **[Ephem 4.1.6]**: Upgraded Ephem support from 4.1.6.
 
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
  