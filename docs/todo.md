[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Development Todo List
- [X] Improve co-ordination of Gimbal Lock handling
- [X] Correctly reset pid SP when removing sync points or reseting back to Single Point Alignment
- [X] Fix 7s cycle in PID OP control jumping (synchronise 518 handler and PID calculations)
- [X] Persist Multi-Point alignment model through Driver restarts
- [X] Fix Multi-Point Alignment without final zero adjust (goto adj)
- [X] RBC Rotation Based Correction to fix M3 bias effecting Az and Roll (based on plate-solve test)
- [X] Stellarium - Debug suspect Stellarium memory usage leakage (done), issue with Stellarium 25.2
- [X] Refactor Kinematics page in Pilot
- [X] Complete Kinematics page motor output, sp highlighting, settings disabling
- [X] Kinematics Page Delta_sp Position Angle needs 0-360 wrapping (currently -180 to 180), delta_ref & delta_pv ok
- [X] Replace RBC with motor-space corrections, Kinematics Page RBC Magnitude update
- [X] Complete more wholistic Mechnical Alignment Correction (replacing Roll Bias Correction)
- [X] Debug 518 message intermittant miss, document the fix was BLE Scanner related
- [X] Refactor kinematics.py and wrap180, move more kinimatic functions from control.py to kinematics.py   
- [X] Allow Roll change while in tracking mode, without resetting az/alt setpoints.
- [X] Explore how to reduce sidereal tracking drift and reduce residuals - Sync Guiding and PEC
- [X] Motion Planning - Fix Gimbal lock oscillation at Az 292, Alt 0, Roll 2, improving estimate for theta3 by using zeta3
- [X] Slew and Center - fix Sync Guiding Seeding
- [X] Actions - Add SlewAbsolute and SlewRelative to enable Advanced Sequence of MPA alignment around RA axis. 
- [X] Pilot Web Server - HTTPS so that Copy Clipboard and Map Locate work in Browser
- [X] Documentation - note about 5Ghz band
- [X] Documentation - note about TPLine frequency scan causing comms latency
- [X] Dependancies - Update compatibility with Stellarium Desktop 26.1 maybe 26.2 (if its released on time)
- [X] Motion Planning - Windup Prevention and Zenith/Horizon Crossing (equivalent to a meridian flip)
- [X] PEC - RLS upgraded to model both axes linear drift rate and harmonic drift rates
- [X] PEC - Update kinematics page with PEC Rate deg/hr (continuously applied), and Guide Pulse in degrees (rather than guide rate)
- [X] PEC - to detect crossovers where there is zero trend and reset for new phase, added harmonics and phase detection
- [X] PEC - Disable learning of PEC Model while disabled
- [X] Galactic - Add Galactic Co-ordinate system to Pilot
- [X] Galactic - Add Sky - Milky Way Panorama for aligning pano grid with Milky Way spine
- [X] Version - Upgrade to Beta version 2.2
- [X] HTTPS - Document Location GPS using phone web browser
- [X] Tests - Remove all performance tests from core
- [X] Flip - Cannot flip to -30 back to +30 at Az 210
- [X] Dependancies - Upgrade dependant libraries on Node and Python
- [X] Kinematics - use newly developed trignometric closed form solutions for IK/FK, unable as Quaternions needed in both paths for corrections 
- [X] Settings - Add ability to save observing site locations
- [ ] Settings - Add ability to save orbital parameters
- [ ] Galactic - Use Galactic co-ord for MW Pano anchor (rather than Az/Alt as they shift as MW pano proceeds)
- [ ] Close candidate enhancement list
    - [ ] Galactic - Improve fallback for unreachable roll angles in Galactic panos
    - [ ] MAC - Consider adding autotune to Mechanical Alignment Correction
    - [ ] CCDCiel - Auto install Alpaca Driver scripts for CCDCiel
    - [ ] CCDCiel - Test session using CCDCiel and document Pano, Sync Guiding
    - [ ] Nina - Test session using Nina and document Sync Guiding workflow
- [ ] Close open questions
    - [ ] Flip - Can we improve horizon flip/windup prevention at Az 30 or Az 0?
    - [ ] PEC - Can we identify Guiding Application Calibration pulses so PEC can ignore them?
    - [ ] Connection - why does changing IP address allow connection to proceed?
    - [ ] Connection - why does L-Bracket get initialised incorrectly sometimes?
- [ ] Create youtube videos for v2.2 content
    - [ ] Create video on install and connect
        - Install
            - New requirements.txt and pip install
            - Ok to copy pilot.settings.xml but new config.toml
            - Autostart doc
        - Connect
            - On connection, new banner - not completed initial single star alignment
            - Discovery - IPv6 support, ConformU support
            - Position Update late messages (reduced)
            - Driver control - Stop and Restart Driver, Restart multiple
            - Sync persistent
            - HTTPS
    - [ ] Create video on dashboard and motion changes
        - Pointing and Motion Control
            - Goto Completion - New Progress Indicator, logrithmic scale completes max axis deviation within Goto Tollerance Kc, Tracking Tollerance Kc/20 
            - Scale Warning Bars - Now change in real time to reflect Polaris Mechanical Limits, Roll = fn(Alt), Also added RA = fn(lat, LST); Dec = fn(lat), Notice Alt opened up 
            - Negative Alt - Supports below horizon pointing, transitioning through horizon flip (eqiv of meridian flip for Equatorial)
            - Gimbal Lock - Loss of degree of freedom as M1&M3 aligned, Enter Gimbal Lock when Alt < 1 deg, exit when Alt > 3 deg; Status icon, may not reach Low Rolls at Alt=0
            - Motion Planning - Typically Shortest Path in SO3 space, Caters for Zenith Singularity, Rotate maintains direction 
            - Windup Prevention - Normally shortest path, unless it predicts it will exceed motor angle limit, then reroutes 360°. Not foolproof.
            - Zenith Imaging - purposefully mount on a wedge
            - At Home - Telescope v4, async, 
    - [ ] Create video on Galactric Co-rdinates, Panoramas and scripting
        - MPA
            - Demo Advanced Sequence for MPA following targets RA movement
        - Utilities
            - PanoGrid - PanoGrid Recenter, PanoGrid Step 80%, Navigating Pano, PanoGrid Copy
            - Advanced Scheduler - Rename_dirs, RotateRelative, FindHome/Wait/Polaris:AbortSlew
    - [ ] Create video on kinematics, tracking, guiding
        - Kinematics
            - Settings Page - enabling different correction features, show alongside kinematics page, toggling on/off
            - Kinematics Page - better understanding and total rewrite 
        - Slewing
            - Mechanical Corrections - Turn on off on Alignment page, see Residuals change
            - Slew and Center - Last MPA Residual, no completion, ZLR force it, LGA on Kinematics
        - Tracking
            - PID - PID axes in dms, De-Trenmded Charts
            - PID - Improved RMS Error, Cyclic bump removed, 
            - Orbitals - tracking See PA changing, Roll Angle fixed.
        - Guiding
            - Sync Guiding - Plate-Solve/Sync using Nina in a 2-5min cycle, Before smart exposure - PID steadies while filter changing.
            - Sync Roll - How to copy Plate-Solve Roll and manual Roll Sync
            - Guiding - Pulse Guide Cross-coupling, Suspend Integral, Guiding Calibration x1.5
    - [ ] Create video on CCDCiel
    - [ ] Create video on RaspberryPi creation

## Final Release Checklist
- [ ] Complete todo checklist
- [X] Check Driver package vulnerabilities
- [X]     pip-audit
- [X]     pip show urllib
- [X]     pipdeptree | findstr urllib3
- [X]     pip install --upgrade urllib3==2.7.0
- [X]     Modify all requirements.txt files accordingly
- [X] Check Pilot package vulnerabilities
- [X]     Check non-breaking updates (dry run): quasar info;  quasar upgrade;        Apply the updates: quasar upgrade -i
- [X]     Check major potentially breaking updates (dry run): quasar upgrade -m;     Apply the updates: quasar upgrade -m -i
- [X]     Check runtime dependencies:                         npm audit --omit=dev   Apply the updates: npm audit fix
- [X]     npm list --depth=0
- [X]     npm install axios@^1.13.5
- [X]     npm list axios
- [X]     Upgrade Node on win11 by downloading installer from https://nodejs.org/en/download
- [X] Check GitHub open issues
- [X]     No CodeQL Security or Quality issues
- [X]     No Malware or Vulnerability issues
- [X]     No AI findings that have not been addressed
- [X]     Confirmed any open GitHub issues are acceptable for release
- [ ] Final Changes - git checkout dev2_2, git pull origin dev2_2
- [ ]     Check version # in readme.md, release-notes-vX.X.X.md, shy.py, AboutPage.vue, AltLayout.vue, package.json, abp-overview.png
- [ ]     Build Pilot for release
- [ ]     Confirm all Alpaca ConformU tests pass
- [ ]     Confirm all Alpaca Driver unit tests pass
- [ ]     Confirm all Alpaca Pilot unit tests pass
- [ ] Create Branch - releases/2_2_0 based on dev2_2
- [ ] Merge into main - git checkout main, git pull origin main, git merge releases/v2.2.0, git push origin main
- [ ] Draft Github New Release and Tag - on main branch
- [ ]     Release Title: Alpaca Benro Polaris Driver v2.2.0
- [ ]     Release Notes: Refer to https://github.com/ogecko/alpaca-benro-polaris/blob/releases/2_2_0/docs/release-notes-v2.2.0.md
- [ ]     Set as latest release
- [ ] Announce on Kickstarter, Facebook, Discord
- [ ] Create new Dev Branch - dev2_3 based on dev2_2

## Alpaca Pilot App
- [X] Implement Alpaca Pilot App Framework
- [X] Implement Alpaca Pilot sidebar menu and toolbar menu
- [X] Implment Alpaca Pilot routing
- [X] Add a Dashboard button to recenter Pano Grid to match mount's orientation 
- [X] At least Pano 5 rows on Dashboard before scroll bars
- [X] Detect when multiple instances of driver running and provide clearer diagnostic message
- [X] Check Driver version to see if client needs refreshing
- [X] Add a stop and restart driver (to allow pickup of python code changes)
- [X] Document how to autostart the driver on win11

## Alpaca Pilot Connection, Bluetooth LE
- [X] Implement Benro Polaris Connection process and diagnostics
- [X] Connect to Benro Polaris without the Benro App
- [X] Use BT Low Energey to Discover nearby Benro Polaris devices
- [X] Use BT Low Energey to enable Wifi on selected Benro Polaris device
- [X] Show Benro Polaris hardware and firmware versions
- [X] Allow change Polaris Mode to Astro
- [X] Allow goto Park position from Connection page
- [X] Allow skip Compass and Single Star Alignment using default values
- [X] Alpaca pilot works outside of Astro Mode eg in Photo Mode

## Alpaca Pilot Configuration/Setup 
- [X] Setup Dialog in Alpaca Pilot
- [X] Foolproof and Simple observing site lat/lon configuration
- [x] Ability to enable various advanced conrtol features and standard control features
- [X] Ability to save and restore configuration modifications
- [X] Alpaca Pilot Action ConfigUpdate pass through to live polaris and pickup from live Polaris eg lat/lon Nina changes
- [X] Alpaca pilot to restrict pid max velocity and accel in real time
- [X] Remove Alpaca Performance Recording Settings
- [X] Warn user to wait till mount stops moving, before skipping single star and compass align

## Alpaca Pilot Log 
- [X] Alpaca Pilot Log file viewer and streaming of data over Sockets
- [X] Ability to change Log Level and Log Settings
- [X] Rationalise loggin across alpaca, polaris, discovery, synscan, bluetooth protocols
- [X] Fix sizing of log scrolling window

## Alpaca Pilot Dashboard Features
- [X] Alpaca Pilot Radial Indicators
- [X] Alpaca pilot goto Az, Alt, Roll with click on Radial Scale or Radial Labels
- [X] Alpaca pilot goto RA, Dec, PA with click on Radial Scale or Radial Labels
- [X] Alpaca pilot floating action buttons for quick axis settings (az, alt, roll)
- [X] Alpaca pilot radial scales to show warning limits on angles
- [X] Alpaca Pilot SP pointer is removed around +/- 90 degrees too early
- [X] Alpaca Pilot Radial Scale PVtoSP can arc the wrong way when around 360/0 wraparound
- [X] Alpaca Pilot Home dashboard
- [X] Alpaca pilot current position main display
- [X] Alpaca Pilot is parked, is tracking, is slewing, is gotoing, is PID active, is Pulse Guiding
- [X] Alpaca pilot commands for Eq-Az toggle, park, unpark, abort, track, tracking rate
- [X] Indicate speed on Alpaca Dashboard
- [X] Indicate motor activity on Alpaca Dashboard
- [X] Alpaca pilot manual slew AltAzRoll, slew rate
- [X] Alpaca pilot manual slew RADecPA
- [X] Fix Position Angle dashboard
- [X] Fix Position Angle interaction
- [X] Fix Az/Alt/Roll interaction while tracking

## Alpaca Pilot Tuning
- [X] Alpaca Pilot KF Tuning page
- [X] Alpaca Pilot PWM Testing page
- [X] Alpaca Improved PWM_SLOW with (-1, +1) rate instead of 0
- [X] Alpaca Pilot Speed Calibration Test Management and Actions
- [X] Alpaca Pilot Speed Calibration hookup and cancel test
- [X] Alpaca Pilot Position Diagnostics Page
- [X] Alpaca Pilot PID Tuning page
- [X] Fix chart sizing when screen resized

## Alpaca Single-Point and Multi-Point Alignment
- [X] Alpaca pilot Single-Point Alignment using Polaris internal model
- [X] Alpaca pilot Multi-Point Alignment using QUEST modeling
- [X] Alpaca pilot SYNC with RA/Dec and Az/Alt co-ordinates
- [X] Alpaca pilot SYNC with landmark on map
- [X] Alpaca pilot Sync Analysis and Residual display
- [X] Alpaca pilot Sync editing and removal
- [X] Alpaca pilot Tripod Level Correction
- [X] Alpaca near Zenith (18° circle) tracking and gotoing by tilting mount  
- [X] Fix Reduce number of Nina plate-solve and sync to get to target
- [X] Fix SYNC events are not cleared in client after driver restart

## Alpaca Speed Control
- [X] Refactor low level SLOW and FAST speed controler
- [X] Implement reliable PWM control over +1 to -1 SLOW Speed
- [X] Allow first SLOW speed 0 through (dont assume it was 0)

## Alpaca Kinematics
- [X] Build comprehensive test suite for Kinematics calculations
- [X] Fix quaternian maths when alt is negative and zero
- [X] Fix 340-360 Control Kinematics, note roll flips sign near N when KF enabled
- [X] Fix Alt 0 Control Kinematics, theta1/theta3 spin at 180, maintain mechnical position
- [X] Add Anti-Windup Motor Angle Limits
- [X] Improve motor limits indication and safety protection (including with tilts)
- [X] Fix zero Altitude movement, at Azimuth of 0/360, and roll

## Alpaca Kalman Filter
- [X] Implment Kalman Filter to improve reliabilty of state assessment
- [X] Alpaca pilot Ability to optionally use KF
- [X] Introduce a Low-Pass Filter on Omega Output (aready doing this I think)

## Alpaca PID Control
- [X] Implement PID control loop
- [X] Stop PID and Motor controllers on shutdown
- [X] Implement TRACK mode
- [X] Implement slewing and gotoing state monitoring
- [X] Ensure polaris tracking is off when enabling advanced tracked
- [X] Alpaca Pilot Speed control for 0 while tracking should remain in PWM_SLOW not SLOW
- [X] Enabling tracking mid GOTO should use SP as target, not current pos
- [X] Fix bug tracking on, off, on - rotates at a faster rate
- [X] Fix delta_ref3 should represent equatorial angle (no change when tracking), alpha_ref desired camera roll angle +ve CCW, 0=horz (changes when tracking)
- [X] Add DATA6 for PID debugging
- [x] Overlay the expected tracking velocity on the omega plot
- [X] Improve responsiveness of manual slewing, incorporate desired velocity into omega_op
- [X] Explicit pid mode changes, add a 'PARK' mode, ensure no pid activity while parked.
- [X] Improve stability of tracking before allowing first plate-solve (after a GOTO) to proceed

## Reliability and degrdation
- [X] Proper task cleanup in polaris.restart(), especially to fix no position updates for over 2s. Restarting AHRS
- [X] Fix when Pilot left behind other window, and Chrome hangs
- [X] Alpaca Pilot close inactive websocket clients
- [X] Alpaca pilot feature degredation when not in Advanced Control
- [X] Alpaca pilot feature degredation when no Multi-Point Alignment
- [X] Alpaca pilot feature degredation when no Rotator
- [X] Alpaca pilot feature degredation when no Bluetooth
- [X] Alpaca Pilot memory and logevity tests

## Documentation
- [X] Kickstarter project
- [X] Youtube training videos 20 Podcast, 21 Demo1, 22 Demo2, 23 Rotator, 24 Alignment, 25 Safety
- [X] Youtube advanced videos 31 Kalman, 32 Speed Cal 
- [X] Documentation on new features 
- [X] Review of existing Documentation 
- [X] Remaining documentation on Pulse Guiding
- [X] Remaining Youtube video on 27 Guiding

## Performance
- [X] Feedforward Control Integration (minimise overshoot)
- [X] Improve fine grained tracking precision
- [X] Improve Kalman Filter tuning
- [X] Integral Anti-Windup dontaccumulate when output is saturated or quantized
- [X] Store Motor Calibration data to a file
- [X] Improve tracking performance beyond BP implementation
- [X] Remove obsolete performance tests and notebooks 
- [ ] Move image culling to Alpaca Pilot, or Document use of ASTAP for image culling

## ASCOM Rotator
- [X] Implement Rotator
- [X] Rotator Halt, Sync, Reverse, Move(relative), MoveAbs, MoveMech, Position(PA), TargetPosition(PA)
- [X] Pass ConformU test on Rotator
- [X] Pass ConformU test on Telescope

## ASCOM Park and Home
- [X] Add ASCOM FindHome command, and expose in Alpaca Pilot, use true Home co-ord from zeta
- [X] Add Park and Home to Dashboard
- [X] Change ASCOM Park to true custom Park position, persisted in settings
- [X] Add ASCOM SetPark command, and expose in Alpaca Pilot 

## Catalog
- [X] Expanded Target Catalog (Stars, Nebula, Galaxies, Clusters)
- [X] Alpaca pilot catalog of targets, search, filter, pagination
- [X] Data cleaning and creation pipeline
- [X] Fix RA hrs vs deg, qnotify of goto
- [X] GOTO from catalog
- [X] Sync from catalog
- [X] Calc current Azimuth, Altitude of dso and categorise it for filtering
- [X] Fix filter clear to only clear when filter is already open
- [X] Add South and North Celestrial Pole
- [X] Ability to add custom targets to catalog
- [X] Calc Sunset, Sunrise, Naut Set, Naut Rise, Moonrise, MoonSet
- [ ] Ability to switch catalogs from settings
- [ ] Add images of each target
- [ ] Add a details page for each target
- [ ] Fix J2000 co-ordinate display of 60" for Running chicken RA: +11ʰ38ᵐ60.0ˢ   |   Dec: -63°11′60.0″ 

## Orbitals
- [X] Add Orbitals menu, Planets, Moons, Satellites
- [X] Add Catalog entries for Sun, Moon, Planets, Planetary Moons
- [X] Update status chip for more detail on tracking orbital status
- [X] Allow searchable catalog of over 32k satellites 
- [X] Allow pre-targeting of orbitals, waiting for their rising
- [X] Implement ASCOM Lunar Tracking rate
- [X] Implement ASCOM Solar Tracking rate
- [X] Implement ASCOM Custom Tracking rate
- [X] Improve indication of failed search where no orbital parameters to track

## Precision Tracking
- [X] Deep-Sky Object Tracking 
- [X] Seamless Axis Override During Tracking
- [X] Selenographic Lunar Tracking 
- [X] Planetary and Orbital Moons Tracking
- [X] Satelite Tracking via TLE (Two Line Element)
- [X] Solar Tracking 
- [X] Commet and Asteroid Tracking

## Pulse Guiding Features
- [X] ASCOM Telescope Pulse Guide API Support
- [X] Pulse Guiding Tracking correction 
- [X] Enable Nina Dithering via Nina Direct Guider and Advanced Schedule (uses Pulse Guide API)
- [X] Guide Camera Support via PHD2
- [X] PHD2 Support via ASCOM/Alpaca
- [X] Allow setting of pulseguiderates 0.25x 0.5x 1.0x 1.5x 2.0x in Settings of Alpaca Pilot

## Imaging and User Experience Enhancements
- [X] Long Exposure Tracking Stabilization
- [X] Automated Leveling Compensation
- [X] Zenith Imaging Support (18° Circle)
- [X] Drift supression and Auto-Centering
- [X] Dithering support
- [X] Mosaic imaging support through Nina


