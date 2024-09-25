[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarium](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Main Todo List of Pending Items to Complete

## Development Pending
* None
  
## QA Pending
* Final Beta Test feedback followup.
  
## Testing Pending
* None
  
## Requests for Benro to assist (in order of priority)
* Protocol required on BT to establish wifi
* Changes to allow minor MoveAxis while sidereal tracking enabled, without backlash - for guiding
* Incorporation of Driver into BP firmware

## Backlog
* Testing on Raspbery Pi
* Testing on Docker
* Testing of Sky Safari
* Develop automated test for drift over movable range of Polaris
* Stellarium Desktop Binary protocol for position updates
* Hand controller web app
* Config web app
* Simplify install with Pi2EXE / Pi2APP

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
