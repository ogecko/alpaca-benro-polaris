[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarium](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Main Todo List of Pending Items to Complete

## Development Pending
  
## QA Pending
* None.
  
## Testing Pending
* None

## Exploration
### Understanding
* Determine what the 2 quanterions returned from 518 are
* Determine what the current  yaw, pitch, roll from 517 are
### Rotator implementation
* Determine if field rotation can be set in a goto command
* Determine if field rotation can be set using combined MoveAxis, without effecting alt/az
* Determine algorithm for Equatorial Field Rotation
* Implement as a rotator ASCOM service
### Tracking Performance Improvement via pulsing moveAxis - FAILED
* Determine if a pulse in MoveAxis can be issued without disabling sidereal tracking - No, any MoveAxis disables tracking momentarily.
### Tracking Performance Improvement via tweaking settings
* Determine delta alt/az/rot sensitivity to changes in sitelat/lon, align ra/dec, goto alt/az, time
* Determine if drift can be offset by ajusting these values
* Let plate solving fix any side effects
### Tracking Performance Improvement via ABP controlled tracking
* Explore whether Polaris can be mounted in equatorial mode
* Explore whether RA can be controlled manually via Az when mounted equatorial
* Slowest Move Speed 1 is 21.5 arc-sec/s. We need 15.04 arc-sec/s. 
* Can pulsing the Move Speed 1 allow us to get a slower speed? 

## Requests for Benro to assist (in order of priority)
* Protocol required on BT to establish wifi
* Changes to allow minor MoveAxis while sidereal tracking enabled, without backlash - for guiding
* Incorporation of Driver into BP firmware

## Backlog
- **[Raspberry Pi]** Official support an testing on Raspbery Pi
- **[Docker Support]** Official support an testing on Docker.
- **[Sky Safari]** Official support an testing on Sky Safari.
- **[CCDciel Support]**: Official support and testing for CCDciel for MacOS.
- **[Stellarium MacOS]**: Add position update support to the Stellarium Binary protocol.
- **[Software Delivery]**: Deliver as an App rather than a zip file, eliminating  command line.
- **[WiFi Setup]**: Eliminate need for BP App to setup Polaris WiFi Hotspot.
- **[Astro Mode Setup]**: Eliminate need for BP App to manually change mode to Astro and align.
- **[Setup GUI]**: Deliver a Graphical UI to manage config.toml and provide a base UI. 
- **[Control GUI]**: Deliver a Graphical UI for Telescope Control, as multi-platform webapp.
- **[Drift Repport]** Develop automated test for drift over movable range of Polaris.
- **[INDI support]**: Add support for INDI protocol, enabling apps like KStars.
- **[Emedded Driver]**: Driver should be embedded on the Benro Polaris Device. Benro Change.
- **[Pulse Guiding]**: Allow micro move axis commands, while tracking, without backlash. Benro Change.

 
## Completed during campaign
* Close Beta testing
* N Point Alignment - Sync will optionally re-align Benro Polaris rather than just being within the Driver
* Add Watchdog to re-enable AHRS or even reboot connection if we dont see any position updates from Polaris
* Fix position lag after extended use of Stellarium (due to remaining buffer messages growing and not being processed)
* Fix Synscan protocol processing as it appears not to use J2000 epoch (effects StellariumPLUS GOTO Accuracy)
* AbortSlew - Review BP Log and implement
* Change Final Release Version Number
* Change README.md with Kickstarter backers
* Eliminate need to keep Mobile app running
* Stellarium resource issue - likely fps issue check stellarium config.ini
* Explore BP log file on its SD Card
* Nina occasionally reports Connection close uneccesarily to ABP.
* Change Sync to optionally calibrate compass
* Change Sync to include two point models 0 = Alt/Az Offset, 1 = RA/Dec Offset
* Resolve why Platsolve doesnt auto Sync on Nina - Fixed
* Resolve Williams comms issue - resolved with cleanup of PC
* Stronger Stellarium Synscan communications error handling
* Properly handle exceptions in background tasks on comms re-estab.
* Installation Videos MacOS and Win11 v2
* Stellarium Telescope Control Video
* Nina Autofocus Video
* Nina Overview Video
* Apple ecosystem testing
* Alpha Testing
* Move Fast and Slow commands
* Park and UnPark commands (uses the Benro Polaris axis reset feature)
* Goto Alt/Az, RA/Dec, and Target command
* A learning algorithm was built into the driver to improve Benro Polaris GOTO accuracy.
* Vladimir and I confirmed plate-solving works, and now we know where it's pointing!
* Sync commands (allows you to correct BP offset on visual or plate solve confirmation of actual pointing position)
* A subset of SynScan protocol to support Stellarium PLUS mobile users.
* A binary protocol to support Stellarium MacOS users.
* A Periodic Error report to quantify your Benro Polaris tracking accuracy.
* Performance Data logging 1 - RA/Dec Error, 2 - Move Axis Turn Rate
* MacOS, RaspberryPi, and Docker platform support (some yet untested)
* Improved BP connection robustness and recovery.
* Addressed some issues from Beta Test.
* Documentation, including troubleshooting and FAQ sections.
* Benro outreach
* Beta Release completed, testing underway
* Github project created (not public yet)
* MacOS compatility changes
* RaspberryPi and Docker platform porting
* Documentation - installation, hardware, nina (capturing)
* Training Video(s) - Nina Capturing
* Created aa Security Policy for the project

## Completed pre-launch
* Asynchronous asgi app
* ASCOM Discovery
* ASCOM 53 Properties
* ASCOM 25 Methods
* Polaris Connection logic improved
* Slew to Alt/Az sync and async
* Slew to RA/Dec sync and async
* Slew +10' RA for 3 pnt alignment
* Nina Plate solving
* Nina Autofocus
* Nina Centering
* Nina HocusFocus star detection
* Nina Long/Lat sync
* Stellarium Telescope connect
* Stellarium Slew to RA/Dec
* Stellarium Positioin readout
* AutoLearning Slew correction
* Sidereal Tracking fix
* Improved Tracking settle correction
* Polaris msg decoding robusness
* Protection of  command overwrite
* Multi client connection support
