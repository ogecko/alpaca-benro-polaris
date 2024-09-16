[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarium](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Beta Testing
## Beta Testing Guidelines
* Document the test environment, focus areas annd results in [docs/betatest.md](./betatest.md).
* Try to perform real world use case tests as well as load and performance tests.
* Keep a record of what tests you perform and the results
* Report any issues noticed as issues in Github
* Try to reproduce and document steps to reproduce, isolate what is causing the issue, diagnose yourself if you can.
* Test the documentation where possible, if its missing help author or improve them.
* Confirm you will send a final summary of Beta testing feedback to me by 25 Sep, so we have time to address any issues.
* Confirm you will not share any pre-release code or docs with others.

## Confirmed Beta Testers, Registered on GitHub
* David Morrison (PCCGG) - Dark site testing of mini-PC, Canon R5, Stellarium, ConformU, Nina
* Vladimir Vyskocil (PCCGG) - for the MacOS testing and support for example, and Raspberry Pi maybe.  ZWO ASI 585 MC 
* Spiderx01 (William S) (PCCG) - SurfacePC, Mini-PC
* 5x5Stuido (John H) (PCCGG) - Happy to beta test,, Pentax K1 - Nikon Z6 - android (Confirmed added to Github)
* bakermanz (RBA) (PCCGG) - So if you need a Beta tester for Mac, please feel free to give me a shout. Mac (using Codeweaver's Crossover) 
* Ladislav (Ladi S) (PCCGG) - I am happy to help with Beta testing on Mac OS.
* saltyminty (Mingyang W) (PCCGG) -  I was wondering if I could join the alpaca beta testing? 
* hqureshi79 (Humayun Q) (Kickstarter)- would love to join beta testing.
* Chris-F2024 - (via VV) - Win Laptop, Nina
* Cosimo (CS) (PCCGG) -  I'd like to beta test alpaca. 
* RjhNZ (RH) (PCCGG) - Nice concept, happy to buy you several coffees and will beta test the hell out of your work. 
   
## Potential Beta Testers
* Charles Thomas (PCCGG) - Glad to be a beta tester. (Messenger DM 1/9)
* Vasilis Triantafyllou (PCCGG) - Count me in! Could also help with beta testing (Messenger DM 2/9)
* Craig Bobchin (PCCGG) - I am willing to help beta test. I have a Pentax K-1 as my main camera.
* Steve Everitt (PCCGG) - I also shoot with Pentax cameras and am happy to assist with any beta testing. I live in Lanzarote so get a lot more opportunity than most.
* @PdTCH (Youtube)  - will sing up for the kickstarter and let u know for betatesting (Messaged on YT 15/9)
  
## Potential Followup
* Ian Morgan - Pentax
* Pratik Patel - SW Development (Messenger DM 1/9)
* Florian Fortin - Nina user, Travel (Messenger DM 1/9)

# Beta Test Results Summary

# jdm5001 (DM)
## Test Environment
* Location: Sydney, Australia | NSW National Park 
* Optics: Canon R5, RF135mm, RF800mm,, NEEWER USB Lens Heater
* Mount: Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.40, Astro V1.0.2.11, Android App v3.0.27
* ABP Driver + Nina Platform (hardware): Mele Quieter 4C, Intel N100 800Mhz, 16Gb Ram, 2Tb SSD, INIU 140W Battery
* ABP Driver + Nina Platform (software): Win 11 Pro v23H2, Nina v3.1.1.9001
* Siril + Stellarium Platform: Desktop PC, AMD 7950X, Win 11 Pro v23H2, Stellarium v24.2, Siril v1.2.3 de49749
  
## Test coverage
* Testing Polaris protocol all cmds and responses used across BP, Canon R5 and Win 11 platform. 
* Tested ASCOM Alpaca interface fully with Nina, Stellarium and ConformU apps.
* Tested in Sydney and NSW Kosciuszko National Park (dark sky for remote test, no internet).
* Tested targets M4, M8, M16, M17, M20, M24 M83, C63, C77, C78, C92, SMC, IC4605, Moon, random stars in southern hemisphere.

## Test Results
TBD




# Vladimir Vyskocil
## Test Environment
* Location: France
* Optics: Canon R6 Mk II connected via USB3
* Optics: ZWO ASI585MC camera, a Sigma 120-400mm and 1.4x extender.
* Mount: Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.40, Astro V1.0.2.11, Android App v3.0.27
* ABP Driver + CCDceil (hardware): Laptop is a 14 inch MacBook Pro with Apple M1 Pro CPU, 32Go RAM, MacOS Sonoma 14.6.1
* ABP Driver + Nina Platform (hardware): ASUS Vivobook Pro 16X OLED K6604JV
13th Gen Intel® Core™ i9-13980HX 2.2Ghz 24 cores, 32 Go RAM, NVidia RTX 4060 Laptop GPU
* ABP Driver + Nina Platform (software): Windows 11 Family, Python 3.12.6, ASCOM Platform needed.
* Siril + Stellarium Platform: 
* CCDciel : [INDIstarter](https://github.com/pchev/indistarter) for the INDI ZWO camera driver, as there are no Alcapa driver for that camera, [SkyChart](https://github.com/pchev/skychart) which is used in CCDciel for the goto and [ASTAP](http://www.hnsky.org/astap.htm) for the plate solving in CCDciel


## Test coverage
MacOS testing and support, Raspberry Pi maybe. ZWO ASI 585 MC camera.
Tried with success (in the living room) : Nina with a Canon R6 mk II connected using USB3 and Stellarium.

## Test Results
TBD




# Spiderx01 (WS)
## Test Environment
* Location: US
* Optics: Meade LX 200 
* Mount: Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.40, Astro V1.0.2.11, IOS App v1.4.4
* ABP Driver (hardware): Surface PC (unsuccessful)
* ABP Driver + Nina Platform (hardware): Minis Forum UM350 Mini-PC, Netgear usb wifi adapter, (unsucessful)
* ABP Driver + Nina Platform (software): 
* Safari Platform:  iPhone and iPad, Safari 7
  
## Test coverage
Pentax K1 - Nikon Z6 - android

## Test Results
TBD




# 5x5Stuido (JH)
## Test Environment
* Location: 
* Optics: 
* Mount: Benro Polaris fried.
* ABP Driver + Nina Platform (hardware): 
* ABP Driver + Nina Platform (software): 
* Siril + Stellarium Platform: 
  
## Test coverage
Pentax K1 - Nikon Z6 - android

## Test Results
TBD



# bakermanz (RBA)
## Test Environment
* Location: Auckland, New Zealand
* Optics: Nikon Z8 (z14-24mm F2.8)
* Mount: Benro Polaris
* ABP Driver: Mac (Apple M1 Silicon chipset)
* ABP Driver: older Mac (Intel chipset), I’ve installed Windows 10 Home (OS
build 19045.2965) which can be used from the initial boot up - enabling the
Mac to effectively operate like a Windows PC (unsuccessful - two continual
360 degree rotations of the Benro Polaris)
* ABP Driver + Nina Platform (software): Mac (Apple M1 Silicon chipset) using the Codeweavers Crossover (WINE application) (unsuccessful as each
program can only be run in isolation)
* Siril + Stellarium Platform:
  
## Test coverage
Pentax K1 - Nikon Z6 - android
Intending to use MacOS version of ABP on Apple M1 SiliconMacBook Pro and SynScan with Stellarium etc

## Test Results
TBD




# Ladislav (LS)
## Test Environment
* Location: Wellington, New Zealand
* Optics: Sony a7RV + 24mm f1.4
* Mount: Benro Polaris
* ABP Driver: Mac (Apple M3 Pro Silicon)
* ABP Driver + Nina Platform (Software): Mac Apple M3 Pro Silicon + parallels - Win 11 Home

## Test coverage
Pentax K1 - Nikon Z6 - android

## Test Results
TBD





# Saltyminty (MW)
## Test Environment
* Location: US
* Optics: Canon R, 16mm 2.8, 24-240mm f4-6.3
* Mount: Benro Polaris
* ABP Driver: Mac (M1), CCdciel (still working on it haha)

## Test coverage
Pentax K1 - Nikon Z6 - android

## Test Results
TBD






# Chris-F2024
## Test Environment
* Location: 
* Optics: 
* Mount: 
* ABP Driver + Nina Platform (hardware): 
* ABP Driver + Nina Platform (software): 
* Siril + Stellarium Platform: 
  
## Test coverage
Pentax K1 - Nikon Z6 - android

## Test Results
TBD






# hqureshi79 (HQ)
## Test Environment
Location: ACT, Australia
Optics: Canon R10, (R5 Mark II on the way), Takahashi FS-60CB
Mount: Benro Polaris Astro
ABP Driver + Nina Platform (hardware):
ABP Driver + Nina Platform (software):
Siril + Stellarium Platform:
  
## Test coverage
Pentax K1 - Nikon Z6 - android

## Test Results
TBD


---------------------

# 
## Test Environment
* Location: 
* Optics: 
* Mount: 
* ABP Driver + Nina Platform (hardware): 
* ABP Driver + Nina Platform (software): 
* Siril + Stellarium Platform: 
  
## Test coverage
Pentax K1 - Nikon Z6 - android

## Test Results
TBD


