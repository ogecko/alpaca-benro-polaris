
# Beta Testing
## Beta Testing Guidelines
* Document the test environment, focus areas annd results in [docs/betatest.md](./betatest.md).
* Try to perform real world use case tests as well as load and performance tests.
* Keep a record of what tests you perform and the results
* Report any issues noticed as issues in Github
* Try to reproduce and document steps to reproduce, isolate what is causing the issue, diagnose yourself if you can.
* Test the documentation where possible, if its missing help author or improve them.
* Confirm you will send a final summary of Beta testing feedback to me by 17 Sep, so we have time to address any issues.
* Confirm you will not share any pre-release code or docs with others.

## Confirmed Beta Testers
* Vladimir Vyskocil (PCCGG) - for the MacOS testing and support for example, and Raspberry Pi maybe.  ZWO ASI 585 MC 
* John Harrison (PCCGG) - Happy to beta test,, Pentax K1 - Nikon Z6 - android (Confirmed added to Github)

## Potential Beta Testers
* Charles Thomas (PCCGG) - Glad to be a beta tester. (Messenger DM 1/9)
* Vasilis Triantafyllou (PCCGG) - Count me in! Could also help with beta testing (Messenger DM 2/9)
* Craig Bobchin (PCCGG) - I am willing to help beta test. I have a Pentax K-1 as my main camera.
* Steve Everitt (PCCGG) - I also shoot with Pentax cameras and am happy to assist with any beta testing. I live in Lanzarote so get a lot more opportunity than most.
* @madhatterbakery-artisanmad7631 (Youtube) - So if you need a Beta tester for Mac, please feel free to give me a shout. Mac (using Codeweaver's Crossover) 
  
## Potential Followup
* Ian Morgan - Pentax
* Pratik Patel - SW Development (Messenger DM 1/9)
* Florian Fortin - Nina user, Travel (Messenger DM 1/9)


# Main Todo List of Pending Items to Complete
## Development Pending
* MoveAxis
* SyncCordinates
* Park
* AbortSlew
* Documentation
## QA Pending
* Eliminate need to keep Mobile app running
* Stellarium resource issue or Nina occasionally asks for Connection close uneccesarily.
## Testing Pendinig
* Alpha and Beta testing
* Apple ecosystem testing
* RaspberryPi ecosystem testing
* Completion of Conformance testing
* Compatibility testing

## Backlog
Hand controller web app
Config web app
Videos for progress updates and usage

## Completed during campaign
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
