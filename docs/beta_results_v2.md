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


## RFC
FB: Andrew Sargent; GH: CynicalSarge
FB: Mingyang Wang; GH: saltyminty
KS: Shiv Verma