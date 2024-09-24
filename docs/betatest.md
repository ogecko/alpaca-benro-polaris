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
* Spiderx01 (William Siers) (PCCG) - SurfacePC, Mini-PC
* 5x5Stuido (John Harrison) (PCCGG) - Happy to beta test,, Pentax K1 - Nikon Z6 - android (Confirmed added to Github)
* bakermanz (Mark) (PCCGG) - So if you need a Beta tester for Mac, please feel free to give me a shout. Mac (using Codeweaver's Crossover) 
* Ladislav (Ladi Slav) (PCCGG) - I am happy to help with Beta testing on Mac OS.
* saltyminty (Mingyang Wang) (PCCGG) -  I was wondering if I could join the alpaca beta testing? 
* hqureshi79 (Humayun Qureshi) (Kickstarter)- would love to join beta testing.
* Chris-F2024 - (via VV) - Win Laptop, Nina
* Cosimo (Cosimo Streppone) (PCCGG) -  I'd like to beta test alpaca. 
* RjhNZ (Richard Healey) (PCCGG) - Nice concept, happy to buy you several coffees and will beta test the hell out of your work. 
* Matt17463 (Matthew McDaniel) -  I'd love to help with your Benro driver project. 
* Cynical Sarge (Andrew Sargent) - I would like to participate in the Beta testing of the Polaris driver.
  
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
* Mount: Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.40, Astro V1.0.2.11, iOS App v1.4.4, Android App v3.0.27
* ABP Driver + CCDciel (hardware): Laptop is a 14 inch MacBook Pro with Apple M1 Pro CPU, 32Go RAM, MacOS Sonoma 14.6.1
* ABP Driver + Nina Platform (hardware): ASUS Vivobook Pro 16X OLED K6604JV
13th Gen Intel® Core™ i9-13980HX 2.2Ghz 24 cores, 32 Go RAM, NVidia RTX 4060 Laptop GPU
* ABP Driver + Nina Platform (software): Windows 11 Family, Python 3.12.6, ASCOM Platform needed.
* Siril + Stellarium Platform: MacBook Pro with Apple M1 Pro CPU, 32Go RAM, MacOS Sonoma 14.6.1
* Stellarium Mobile Plus v1.12.9 Plateform (hardware): iPad Pro 11" 1st gen
* CCDciel : [INDIstarter](https://github.com/pchev/indistarter) for the INDI ZWO camera driver, as there are no Alcapa driver for that camera, [SkyChart](https://github.com/pchev/skychart) which is used in CCDciel for the goto and [ASTAP](http://www.hnsky.org/astap.htm) for the plate solving in CCDciel


## Test coverage
* MacOS testing and support. ZWO ASI 585 MC camera using INDIstarter, CCDciel, SkyChart, Stellarium Mobile Plus iOS.
* Tried with success (in the living room and on real target) : Nina with a Canon R6 mk II connected using USB3 and Stellarium.

## Test Results
### MacOS, CCDciel, INDIstarter, SkyChart or Stellarium Mobile Plus
TBD
### Windows 11, Nina
TBD



# Spiderx01 (WS)
## Test Environment
* Location: US
* Optics: Meade LX 200 
* Mount: Benro Polaris Hw 1.3.1.4, Firmware V6.0.0.40, Astro V1.0.2.11, IOS App v1.4.4
* ABP Driver (hardware): Surface PC (unsuccessful)
* ABP Driver + Nina Platform (hardware): Minis Forum UM350 Mini-PC, Netgear usb wifi adapter, (unsucessful)
* ABP Driver + Nina Platform (software): 
* Stellarium Platform (software): Stellarium v24.2
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



# bakermanz (Mark)
## Test Environment
* Location: Auckland, New Zealand
* Optics: Nikon Z8 (z14-24mm F2.8)
* Mount: Benro Polaris
* ABP Driver: 14” MacBook Pro 2021 (Apple M1 Silicon chipset) originally
tested using macOS 14 Sonoma and more recently, the latest released
version macOS 15 Sequoia
* ABP Driver: older 13” MacBook Pro 2013 (Intel chipset), using Bootcamp
Windows 10 Home (OS build 19045.2965) - enabling the Mac to effectively
operate as a Windows PC 
  
## Test coverage
Nikon Z8 - iPhone 15 Pro Max (see above) with Stellarium PLUS

## Test Results
* Having tested ABP both in Windows format (bootcamp 2013 MacBook with
Windows 10) and also the Mac version of ABP (on M1 MacBook), actually
found the connection more stable and quicker to load using the Mac version.
* ABP works well with the very latest and just released (16 Sept 24) version of
macOS 15 Sequoia, which is excellent.
* Latest desktop version of Stellarium (24.3) for macOS works well, though much
better using Stellarium PLUS via iPhone
* Stellarium PLUS tested on iPhone 15 Max Pro using both iOS17.6.1 and also
the very latest version iOS 18 (released 16 Sept 24). The App runs excellent on
both versions of iOS and the telescope GoTo function is brilliant
* Using macOS, tested NINA (Windows only program) and the original Windows
ABP driver using Codeweavers Crossover (WINE) - unsuccessful, since each
program can then only be run in isolation and not integrate with the other
programs
* As a Mac user, fully accept that most Astro programs are Windows based and
NINA doesn’t run on macOS. As such, a mini PC (Windows) would be
preferable to install and run ABP - but hopefully Stellarium PLUS (on iPhone)
could be used.
* Amazing development project and an awesome upgrade to the existing
functionality of the Benro Polaris


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




# Matt17463 (MM)
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





# CynicalSarge (Andrew Sargent) (PCCGG)
## Test Environment
* Location: Melbourne, Australia
* Optics: Canon 6D MkII, Canon EF 50mm f1.8, Canon 800D, Sigma DC 17-50mm f2.8, Tamron 16-300mm f3.5-6.3
* Mount: Benro Polaris
* ABP Driver + Nina Platform (hardware): Microsoft Surface Laptop 2
* ABP Driver + Nina Platform (software): Windows 11
* Siril + Stellarium Platform: Microsoft Surface Laptop 2, Windows 11

## Test Results
TBD


# RjhNZ (Richard Healey)
## Test Environment
* Location: NW
* Optics: Sony A7Riv, Pentax K1, K3, K5 and K7. 
* Mount: Benro Polaris
* ABP Driver + Nina Platform (hardware): 
* ABP Driver + Nina Platform (software): 
* Siril + Stellarium Platform: 
  
## Test coverage
Pentax K1 - Nikon Z6 - android

## Test Results
Firewall issue on first use
Challenges getting Sony working with ASCOM Camera driver


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


