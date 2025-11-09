[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)
# Beta test results

## Beta Tester: Vladimir (Dis: vyskocil; GH: vyskocil; FB Validimir V..)
Notes: feedback on MacOS
### Platform & Environment
...
### Test Areas
...
### Results
...
### Feedback
...


## Beta Tester: Mark (Dis: Bakermanz; GH: bakermanz; FB: Real Bread Aotearoa)
Notes: connect ok, tracking pulsing, top 360
### Platform & Environment
* Location: Auckland, New Zealand
* Optics: Z 6II (Astro Modified) and Z8, Nikkor Z 100-400mm f/4.5-5.6 VR S
* Mount: Benro Polaris (latest device version 6.0.0.54 and astro kit version 1.0.2.14)
* ABP Driver: 2.0 Beta 1(Windows version)
* N.I.N.A: Version 3.2 RC12

* Option 1 - for testing purposes and as backup
    * 14” MacBook Pro 2021 (M1) macOS Tahoe (26.0.1)
    * Windows 11 Pro version 24H2 via Parallels Desktop 26 for Mac (26.1.1)
* Option 2 - main system
    * Mele Quieter 4C with tp-link Archer T1300U Nano USB Wi-Fi Adapter
    * Intel N100 800MHz, 16Gb Ram, 512Gb SSD) with Anker 140W Battery
    * Windows 11 Pro version 24H2
* TP-link travel router (AC750 Wi-Fi TL-WR902AC) connected via ethernet - provides wifi to allow iPad Pro (M4) iPadOS 26.0.1 to control mini PC via ‘Windows App Mobile’ (version 11.2.1)
### Test Areas
* iPhone 15 Pro Max (iOS 26.0.1) with Stellarium PLUS (version 1.15.0)
* MacBook Pro (Windows) with Stellarium (version ) using ASCOM 7
* Mini PC (Windows) with Stellarium (version ) using ASCOM 7 
### Results
1. Stellarium PLUS (iPhone) communicates perfectly with ABP 2.0 on Mini PC, giving
GoTo functionality beyond Benro Polaris basic star catalogue.

2. Stellarium Desktop on Mini PC - works well with ABP 2.0, when selecting targets for
use in N.I.N.A. and ‘Image source coordinates’ are input from Planetarium. When
testing, the ABP driver was able to successfully slew the Benro Polaris to a comet (C/
2025 R2) for the imaging sequence in N.I.N.A.

3. Benro Polaris tracks well with ABP 2.0 using ‘Slew and centre’ in N.I.N.A. and plate
solving with ASTAP
### Beta1 Feedback
* Bluetooth on startup

    On start up, ABP 2.0 seems to be looking for bluetooth? From the log;
    ```
    ERROR BLE scan failed: Failed to start scanner. Is Bluetooth turned on?
    File "C\Users\anthonylong\AppData\Local\Programs\Python\Python313\Lib\sitepackages\bleak\__init__.py",
    line 140, in __aenter__await self._backend.start()
    File "C:\Users\anthonylong\AppData\Local\Programs\Python\Python313\Lib\sitepackages\bleak\backends\winrt\scanner.py", line 282, in start
    raise BleakError("Failed to start scanner. Is Bluetooth turned on?")
    bleak.exc.BleakError: Failed to start scanner. Is Bluetooth turned on?
    ```
* Site Location on startup

    APB 2.0 also reports a site latitude /longitude warning, still displaying the Sydney coordinates. Checking the config.toml file, shows both the amended (New Zealand)
    version and a second newly created file, with the original Sydney coordinates. Even when this file is deleted, it is always recreated again, when launching the ABP driver.
    Perhaps this now needs to be changed in Pilot?
    Regardless, the coordinates are correct in NINA

    Please disregard my second observation comment about config.toml .... since I've just used Pilot to change the coordinates instead

* MiniPC Hotspot 

    I have always had issues with the Hotspot feature on the Mini Pc, in particular because I am most
    often using the equipment away from the home wi-fi and as such, do not have access to any
    network.
    Whilst it originally worked perfectly well last year, it began to become unreliable, particularly
    following several Windows 11 updates. Despite following online guidance from Cuiv the Lazy
    Geek (‘elusive hotspot’ etc) and various start up and registry changes, I still had issues - usually at
    the most inconvenient moments (imaging the night sky) - where it was consistently requiring
    connection to a wi-fi network….. which clearly wasn’t available.
    As a consequence, I simply gave up and replaced this method of connectivity with a travel router,
    which I have found works very well in my set up.

* Travel Router

    Tp-link AC750 (WR902AC) is connected to the Mele 4C via ethernet and generates its own local
    wi-fi network. I also use one of the USB-A ports on the mini PC to power the unit. This enables
    me to connect to its local wi-fi network and control N.I.N.A on the mini PC, without any
    connection drop outs whatsoever.

* Tablet Control - connects to travel router wif-fi

    I use an iPad with the latest version of Microsoft’s “Windows App Mobile” (formally called Remote
    Desktop), in order to connect to the mini PC (using the above method)

* Wi-Fi Adapter - connects to Benro Polaris wi-fi

    Originally I used the tp-link AC600, which worked well for about 12 months before becoming
    unreliable. Once again, this may be due to Windows 11 updates, although a self test did show an
    intermittent fault on the unit. There was a fair bit of movement in the USB-A port and its antenna
    made it vulnerable to accidentally being dislodged.
    I now use a very small (no lengthy antenna to dislodge) tp-link Archer T1300U Nano, which fits
    more securely in the USB-A port of the mini PC. Being less than 1cm tall, it is also less vulnerable
    to being dislodged, compared to my previous AC600.

* Alpaca Pilot

    **Connection** Pilot needs to have access to the Polaris wi-fi and the ABP driver needs to be running - Correction Pilot only needs connection to ABP driver.

    **Nina Gear Icon** Pilot access via N.I.N.A. gear icon - open N.I.N.A. and select ‘Mount’ (via telescope icon),
    which should display the address of the Alpaca Benro Polaris Telescope in the drop down
    menu at the top of the screen (192.168.0.2). May need to use the refresh icon, so that the
    Alpaca Benro Polaris Telescope can be detected. Select the gear icon to open Pilot before the
    Alpaca Benro Polaris Telescope is actually connected.
    Otherwise, if the Alpaca Benro Polaris Telescope is connected first, the gear icon becomes
    greyed out and Pilot can longer be accessed using this method (disconnecting the Alpaca
    Benro Polaris Telescope, makes the gear icon available)

    **Browser Start** Pilot access via browser - N.I.N.A. will display the address of the Alpaca Benro Polaris
    Telescope ‘Mount’ (see above) and by inputting these details (192.168.0.2) into the browser,
    Pilot can be accessed at anytime. These details (192.168.0.2) can also be used on the iPhone

    **Observing Site Information** - the map is greyed out when using the iPad (N.I.N.A gear
    icon or via browser) because there is no access to internet). As such, I used the iPhone to
    access Pilot via its browser, because it can provide necessary internet access it’s via 4G,
    allowing the location map to be visible and move the pin, to change location etc.

    **Tripod Leveling** Haven’t quite worked out how to avoid the necessity to mess around levelling the tripod, but
    understand Pilot has such a feature (somewhere?)

### Beta 2 Feedback
* Background 

    Due to continued cloudy conditions, all previous testing (connectivity with Stellarium etc) was only conducted during the day - so plate solving could not be undertaken (for both BETA 1 and 2). However, I was able to successfully image using BETA 2, over the weekend:

    * Witch Head Nebula - Friday 31 Oct 25
    * Horsehead Nebula - Saturday 01 Nov 25

* Equipment

    * Nikon Z6 II (Astro modified) with Nikkor Z 100-400mm
    * 300mm f6.3 20 sec ISO 800
    * Tested on both Mele Quieter 4C and MacBook Pro (M1) using Parallels Desktop 26 (as per my previous report submission)

* Workflow - Night 1 and Night 2

    Results for BETA 2 using both ‘systems’ was exactly the same and the issues I encountered, could be down to user error and unfamiliarity with set up.
    1. Connect to Pilot through N.I.N.A. (gear icon) and park
    2. Focus (LensAF), take image and plate solve (so mount knows where it is pointing in
    the sky)
    3. At this point, the camera and Polaris was pointing directly at Orion in the sky
    4. In N.I.N.A, unpack and set sidereal tracking
    5. Use the framing assistant to select target (e.g. Horsehead Nebula)
    6. Select ‘Slew and centre’ Polaris immediately moved away from pointing at Orion and turned a full 90° before trying to initiate another plate solve - which failed, because it was now pointing at the house.
    7. Close everything down and repeat the setup and workflow - but exactly the same 90°issue. (JDM - LIKELY ALIGNMENT ISSUE)
    8. In order to continue, I had to shut everything down and revert to using the original iPhone methodology - completely skipping Pilot. This worked excellent (gave no issues with the 90° turns) and I was able to continue to the N.I.N.A ‘Legacy Sequencer’ (taking 20 frames, plate solving and repeating 12 times for 240 images)
    9. Plate Solving - previously it would immediately solve or take 2-3 attempts if ‘telescope out of tolerance’, before continuing. However, it now takes 8-10 attempts for evert single plate solve within the sequence  as if there is a drift issue. (JDM - FIXED IN BETA3)
    10. Despite the imaging sessions taker far longer than usual (due to the extended time with each plate solve), the overall image results were absolutely fine.
    11. Exactly the same issue on both consecutive nights

* Summary of Issues

    * Conflict between Pilot and N.I.N.A (90° turns with ‘Slew and centre’)?
    * Increased repeated plate solving attempts (“telescope not in tolerance”)

* Causes & Solutions

    I suspect this may be down to user error and I’ve probably missed a step or 2 two somewhere, because it works absolutely fine using the iPhone set up methodology - though it doesn’t explain the plate solving change.
    I have now removed Beta 2 and installed Beta 3 - so unfortunately, I don’t have access to any logs from the imaging sessions.

### Beta 3 Feedback
Multi-Point Alignment (06 Nov 25)

Background - The sky was clear and although there was a full moon (not ideal), I was aiming in the opposite direction. The tripod and Benro Polaris were pointing South East towards the Large Magellanic Cloud (LMC)

Workflow
1. Start ABP driver, open N.I.N.A., connect to Pilot through N.I.N.A. (gear icon) and
ensure location details are correct in Pilot (-36.730621 / 174.742580)
(NB - ‘Compass Alignment’ is set to Az 180 and ‘Single Star Alignment’ set at Az 180 Alt 45) .. both
skipped and ‘Reset all Polaris Axes’)
2. Pilot Dashboard - Park
3. As always, use bubble level (0.1°) and Leofoto “Tripod Leveler Stand with +/-5 Degree
Precision Adjustment Bracket, to ensure as level as possible
www.amazon.com/dp/B092M5G7VD?ref=ppx_yo2ov_dt_b_fed_asin_title
4. N.I.N.A. - connect camera, focuser and telescope (also set focal length to 300mm),
(Note: N.I.N.A. shows site latitude -36 43’ 50” and longitude 174 44’ 33”
This equates to -36.7306 which is the same as in Pilot and 174.7369 which is different to that shown in
Pilot - see 1 above …. Pilot is correctly showing 174.742580)
5. N.I.N.A. - Calibrate lens and focus (using ‘LensAF’ Plug In)
6. Pilot Dashboard - Unpark and toggle tracking on (in order to sync)
7. N.I.N.A. - initiate manual plate solve via image>plate solving (using play button)
(this first result was now displayed in the Pilot Telescope Alignment Model)
8. Pilot Catalog - select South Celestrial Pole and “Goto”
(this caused the Polaris to slew, automatically initiate a plate solve and again, this second result was
now displayed in the Pilot Telescope Alignment Model)
9. Pilot Catalog - select target (LMC) and “Goto”
(Again this caused the Polaris to slew, automatically initiate a plate solve and this third result was now
displayed in the Pilot Telescope Alignment Model)
10. Pilot Connect - Multi Point Alignment now showing green tick
11. N.I.N.A. Framing Assistant - using Offline Sky Map, enter target details (LMC) in Coordinates box and Load Image
12. N.I.N.A. Framing Assistant - select ‘Slew and centre’ … which initiates plate solving
and once completed (telescope within tolerance), add target to Sequence etc
13. N.I.N.A. Legacy Sequencer - set to 20 images (15 sec exposure) and cycle repeated, so that plate solving between every 20 images (‘slew to target and centre target’ both set to ON)
*After about 100 images, there were too many clouds in that area, to continue*
Observations
For all intents and purposes, everything seemed to go very smoothly and without issue.

However:

1. Pilot Dashboard - Park at the end of the session, gave some strange results on the display: Azimuth +130 Altitude +46 Roll -10
I was expecting these figures to return to the original ones, from when the mount was first parked during the initial set up (at point 2 above)
Azimuth +178 Altitude +81 Roll 0
2. Note - After the sequence was stopped (due to cloud), as an experiment, I used N.I.N.A. (framing assistant) to enter the Orion Nebula and as expected, Polaris did slew across and attempt a plate solve.
The plate solve failed and on checking the image in N.I.N.A., the tops of the trees were covering half the entire frame (hence the failure). I then tried other targets (where there was no cloud) and again the Polaris was pointing a fair bit lower than it should have been.
3. Checking the frames this morning, all images are streaked, which suggests the mount was either out of alignment or the tracking was off.
Alignment - all the residuals were below 5 (3 sync points) and if tracking was turned off, it would not be able to plate solve and sync
Tracking - audible throughout the sequence and successfully plate solved once
telescope within tolerance, after every 20 images
I suspect user error but struggling to work out the error of my ways

### Beta 3 Feedback
Multi-Point Alignment (07 Nov 25)
*  Background
    - Using the iPhone compass app (set to true north), the tripod and Benro Polaris were set up to perfectly face South
    - Bubble level (0.1°) and Leofoto “Tripod Leveler Stand with +/-5 Degree Precision Adjustment Bracket, to ensure as level as possible Although neither of these steps should actually be necessary (with plate solving), I wanted to eliminate every possible element, that could possibly impact on the alignment. At the time, (23:00) there was a full moon starting to rise (NE), so imaging of the LMC was taken from the opposite direction (SE) of the Bortle 5 sky. 
* Workflow
    1. During the Pilot connection stage, I selected the ’Reset all Polaris Axes’ and ensured that the ‘Observing Site Information’ location details were correct (xx / xx) and at this point (NB - ‘Compass Alignment’ is set to Az 180 and ‘Single Star Alignment’ set at Az 180 Alt 45) .. skipped)
    2. Pilot Dashboard - showing these figures;
    Azimuth +184° M1 0.2°
    Altitude +79° M2 -0.1°
    Roll -5° M3 1.1°
    3. Pilot Dashboard - after selecting ‘Park’ it was now showing these figures;
    Azimuth +178° M1 -0.0°
    Altitude +79° M2 0.0°
    Roll -0° M3 -0.0°
    (slight change in Azimuth Roll and ‘M’, compared to the initial set up using ‘Reset all Polaris Axes’)
    4. Pilot Dashboard - Unpark and toggle tracking on (in order to sync)
    5. N.I.N.A. - initiate manual plate solve via image>plate solving (using play button)
    (this first result was now displayed in the Pilot Telescope Alignment Model)
    6. Pilot Catolg - used for “Goto” and then plate solved using N.I.N.A.
    First - South Celestrial Pole
    Second - LMC +2 hours in future (EQ mode used to enter d-2)
    Third - LMC (real time)
    7. Multi-Point Alignment - results showing;
    (a) Telescope Alignment Model - great residuals (the highest being only 2.2°)
    (b) Correction Summary - results showing;
    Az Correction 17.0°
    Tilt Correction 31.5°
    Highest Tilt Az 322.9°
    8. Pilot Dashboard - showing these figures;
    Azimuth +151° M1 -52.1°
    Altitude +41° M2 -3.5°
    Roll -10° M3 7.3
    9. N.I.N.A. Framing Assistant - using Offline Sky Map, enter target details (LMC) in Coordinates box and Load Image
    10. N.I.N.A. Framing Assistant - select ‘Slew and centre’ … which initiates plate solving
    and once completed (telescope within tolerance), use ‘Add target to Sequence’ etc
    11. N.I.N.A. Legacy Sequencer - set to 20 images (20 sec exposure) and cycle repeated,
    so that plate solving between every 20 images (‘slew to target and centre target’ both
    set to ON)
    12. PROBLEM - on checking the images, all showed elongation of stars and trailing.
    There were also strange shapes (squiggles) on some images - despite no movement
    of tripod whatsoever and there was zero wind. I was beginning to wonder if the Benro
    Polaris unit itself, had developed a fault.
    13. Restart imaging without using Multi-Point Alignment - reverting back to just using N.I.N.A. with ABP Beta 3 - Sidereal tracking was set in N.I.N.A.
    This resulted in pin point stars for every image on the same target (LMC) and so this eliminates the possibility of any potential fault, with the Benro Polaris unit 
*  Observations
    * Multi-Point Alignment had good residuals from the 3 sync points but the ‘Correction Summary’ shows high levels of correction (tilt etc) … despite the meticulous set up
    with bubble level etc
    * Could there be a difference between the sidereal tracking used in Pilot, compared to when it was set using N.I.N.A ? (star streaks and squiggles on images)
    * There seems to be a difference with the ‘Park’ position in Pilot compared to the Benro Connect App (joysticks) and N.I.N.A.

## Response

Mark, thanks again for the tests. Definitely something strange going on. Here are some comments.

2. After reset Axes, its strange to have an Alt of +79. Even roll +5 seems strange.
Especially when the Single Star align Skip has a value of Az180, alt 45. 
Could the Skips have been done before the reset was fully finished?
Its important to have the Polaris fully stopped before pressing the skip star align button.
This is true for plate-solves as well. Need to make sure Polaris/Alpaca are tracking steady before initiating.

7. A residual of 2.2 degrees is not that great. It ideally should be in arc-sec or maybe arc-min.
Also it seems very strange that you have a tilt correction of 31.5 degrees as I'm sure your tripod wasnt tilted that much.
Even the high Azimuth correction seems strange considering you aligned the Tripod with South.
Would love to see a screen capture of the residuals.
Or better yet, goto the Driver Log and enable Log Settings, Log Multi-Point Sync.
Then do your plate solves and send me the captured Alpaca log file.

Can you rerun steps 1-3 and see if you can reproduce the same Altitude at M1=M2=M3=0, after waiting for the mount to stop fully before pressing Skip Single Start Align?
The tracking problem looks like a bad multi-point alignment model, the more detailed logs of the syncs next time will help diagnose it. 

### Beta 3 Feedback
Day Time Testing  (08 Nov 25)
* Background
    * I followed your advice regarding waiting between the three steps (Reset all axes, skip compass alignment and skip single star alignment) As a result, the weird initial Altitude 79° that I previously reported, has now gone and shows 45° User Error - Previously, I had simply gone down the ‘list’ and ticked one-by-one (without waiting)
* Observations
    1. Despite not waiting, the ‘Connect’ display in Pilot immediately gave green ticks for
    all three steps- so naturally, I had assumed all was well …. when in fact it wasn’t
    2. During my previous image testing (07 Nov 25), I had also experienced a possible
    conflict between the ‘GoTo’ in Pilot and the ’Slew and centre’ in N.I.N.A.
    This was where the target (LMC) had been selected from the Pilot Catalog and used
    for the third Multi-Point Alignment sync point. The target details (LMC), were then
    entered into the N.I.N.A. Framing Assistant.
    N.I.N.A - Once the target was entered (followed by ‘Load Image’), the ‘Slew and
    centre’ would result in the Benro Polaris moving away from its current position.
    NB - Pilot and N.I.N.A. were identifying the target at different position….. conflict
    3. Test (daytime)
    (i) Pilot Catalog - select LMC and ‘GoTo’ - Polaris moves to target
    (ii) N.I.N.A. - enter LMC in the Faming Assistant, ‘Load Image’ followed by ‘Slew and
    centre’ ….. Polaris no longer moves away from its position
    This appears to fix my Multi-Point Alignment issues, which will now need to be confirmed
    at night- where plate solving can be used.
    Further Testing
    Driver Log will be enabled with “Log Multi-Point Sync”.
    There may be a delay (forecast cloudy conditions in New Zealand for next week) and Beta
    4. will most likely be used for further testing.





## Beta Tester: Mark (FB: John Harrison; GH: 5x5Stuido)
Notes: Ireland Week43, New 5nm filters.
### Platform & Environment
...
### Test Areas
...
### Results
...
### Feedback
...



## Beta Tester: Mark (FB: William Siers; GH: Spiderx01, Dis: williamsiers)
Notes: Phoenix Week43
### Platform & Environment
...
### Test Areas
...
### Results
...
### Feedback
...


## Beta Tester: Daniel (Dis: Dmich39; GH: Dmich39)
Notes: Typical User, Non technical
### Platform & Environment
...
### Test Areas
...
### Results
...
### Feedback
...



## Beta Tester: Richard (FB: Richard Healey; GH: RjhNZ)
Notes: Maybe, but, other commitments
### Platform & Environment
...
### Test Areas
...
### Results
...
### Feedback
...


## Beta Tester: Alex (Dis: Alex; FB: Alexander M...; GH: ..)
Notes: help with producing tutorial/overview and beta testing
### Platform & Environment
...
### Test Areas
...
### Results
...
### Feedback
...


## Beta Tester: Steve (Dis: LanzaSteve; FB: Steve E...; GH: SteveE..)
Notes: Tried BP Dither
### Platform & Environment
...
### Test Areas
...
### Results
26/10/2025
    windows 11 laptop
    start BP (repaired so first time)
    bp on tripod
    mount Pentax & Rok 135
    connect with USB to laptop 
    insert wifi dongle, connect to BP wifi
    star alpaca driver v2 "comm init done" no phone used
    start stellarium
    find A6 Lemmon
    start NINA
    connect camera
    connect mount Alpaca BP Telescope 
    check focal length in options > Equipment, amend as necessary
    open framing again check focal length
    get coordinates from planetarium
    cannot rotate mount to target, no movement
    same in NINA, gets coordinates from stella but no slew
    go to stella config > plugins > scope control 
        status connecting ¦ type local,ascom ¦ name BP
    stays on connecting
    tried a park in nina didn't react so ....
    disconnect from nina, close stella
    connect phone
    calibrate compass
    goto something
    start stella still no scope control in stella
    nina started, coordinates from stella slewed successfully to target
    plate solve failed, clods and obstructions in FOV so moved the rig 1 meter forward.
    tried another platesolve, slew an centre and it contorted the rig into some very weird angles.
    parked and tried again, this time it did the opposite of the weirdness (see photos)
    tried to manually turn BP using the east button in nina and the rotator is turning too
    used bp app on phone to goto target using coordinates written in from stella and it went to the cords without rotator turning
    back to nina > framing get cords from stella success
    slew and centre 
    forced to quit, clouds :(

### Feedback
...


## Beta Tester: Shiv Verma 
(Dis: shiv_93263; FB: Shiv Verma; GH: SVerma033, KS: Shiv Verma)

Notes: I do have a relationship with the MAC Group the nation-wide distributors of the Benro product line here in the USA.  
### Platform & Environment
Hardware: 
* MeLE Quieter 4C, MackBook Pro 14inch M3 Pro with 18GB memory, MAC Studio with 64GB Memory, IPad and the iPhone 16 Pro

Optics: 
* As a Panasonic Lumix Ambassador, I have: Full frame - Panasonic Lumix S1R II, S5 II, S5 IIX and all their lenses
* MFT - GH6, G9 II and all the MFT Lenses
* Sony A7R V, Sony A6500 (Astro Modified) - 20MM, 24, MM, 50mm, 16-35, 24 - 70mm, 70-200mm, 200-600mm

Platform: 
* Windows 11 Pro on the MeLE, Mac OS 26.0.1 on both Macs and on the iPad
* Stellarium Desktop, NiNA, with related SW and drivers

### Test Areas
...
### Results
...
### Feedback
...

## RFC
FB: Andrew Sargent; GH: CynicalSarge
FB: Mingyang Wang; GH: saltyminty
KS: Shiv Verma