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
### Feedback
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



## Beta Tester: Mark (FB: William Siers; GH: Spiderx01)
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



## Beta Tester: Mark (FB: Richard Healey; GH: RjhNZ)
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
...
### Feedback
...


## RFC
FB: Andrew Sargent; GH: CynicalSarge
FB: Mingyang Wang; GH: saltyminty