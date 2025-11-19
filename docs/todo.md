[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Development Todo List

## Alpaca Pilot App
- [X] Implement Alpaca Pilot App Framework
- [X] Implement Alpaca Pilot sidebar menu and toolbar menu
- [X] Implment Alpaca Pilot routing
- [ ] Check Driver version to see if client needs refreshing

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
- [x] Alpaca near Zenith (18° circle) tracking and gotoing by tilting mount  
- [X] Fix Reduce number of Nina plate-solve and sync to get to target
- [ ] Fix SYNC events are not cleared in client after driver restart

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
- [ ] Fix zero Altitude movement, at Azimuth of 0/360, and roll

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
- [ ] Improve stability of tracking before allowing first plate-solve (after a GOTO) to proceed

## Reliability and degrdation
- [X] Proper task cleanup in polaris.restart(), especially to fix no position updates for over 2s. Restarting AHRS
- [X] Fix when Pilot left behind other window, and Chrome hangs
- [X] Alpaca Pilot close inactive websocket clients
- [X] Alpaca pilot feature degredation when not in Advanced Control
- [X] Alpaca pilot feature degredation when no Multi-Point Alignment
- [X] Alpaca pilot feature degredation when no Rotator
- [X] Alpaca pilot feature degredation when no Bluetooth
- [ ] Alpaca Pilot memory and logevity tests

## Documentation
- [X] Kickstarter project
- [X] Youtube training videos 20 Podcast, 21 Demo1, 22 Demo2, 23 Rotator, 24 Alignment, 25 Safety
- [X] Youtube advanced videos 31 Kalman, 32 Speed Cal 
- [X] Documentation on new features 
- [ ] Review of existing Documentation (Readme, Hardware, Install done)
- [ ] Remaining documentation on Pulse Guiding
- [ ] Remaining Youtube video on 27 Guiding, 33 PID Tuning

## Performance
- [X] Feedforward Control Integration (minimise overshoot)
- [X] Improve fine grained tracking precision
- [X] Improve Kalman Filter tuning
- [X] Integral Anti-Windup dontaccumulate when output is saturated or quantized
- [X] Store Motor Calibration data to a file
- [X] Improve tracking performance beyond BP implementation
- [ ] Remove obsolete performance tests and notebooks 
- [ ] Move image culling to Alpaca Pilot

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
- [ ] Ability to add custom targets to catalog
- [ ] Ability to switch catalogs from settings
- [ ] Add images of each target
- [ ] Add a details page for each target
- [ ] Fix J2000 co-ordinate display of 60" for Running chicken RA: +11ʰ38ᵐ60.0ˢ   |   Dec: -63°11′60.0″ 
- [ ] Calc Sunset, Sunrise, Naut Set, Naut Rise, Moonrise, MoonSet

## Orbitals
- [X] Add Orbitals menu, Planets, Moons, Satellites
- [X] Add Catalog entries for Sun, Moon, Planets, Planetary Moons
- [X] Update status chip for more detail on tracking orbital status
- [X] Allow searchable catalog of over 32k satellites 
- [X] Allow pre-targeting of orbitals, waiting for their rising
- [X] Implement ASCOM Lunar Tracking rate
- [X] Implement ASCOM Solar Tracking rate
- [X] Implement ASCOM Custom Tracking rate

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


