[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarium](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Main Todo List of Pending Items to Complete
## Development Pending
* Nina 3 Point Alignment integration with BP
* Stronger Stellarium Synscan communications error handling
* Cleanup and recreate background tasks on comms re-estab.
* AbortSlew
  
* ## QA Pending
* Eliminate need to keep Mobile app running, Keepalive 525 and 518 Exploration
* Resolve Williams comms issue
* Resolve why Platsolve doesnt auto Sync on Nina
* Stellarium resource issue or Nina occasionally asks for Connection close uneccesarily.
* Extend Troubleshooting Guide with any Beta Test feedback

## Testing Pending
* Testing using StellariumPLUS on same device as BP App
* Testing on Raspbery Pi
* Testing on Docker
* Testing of Sky Safari
* Closed Beta testing
* Open Beta testing
* RaspberryPi ecosystem testing
* Compatibility testing

## Backlog
* Hand controller web app
* Config web app
* Videos for progress updates and usage

## Completed during campaign
* Nina Overview Video
* Nina Autofocus Video
* Stellarium Telescope Control Video
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
