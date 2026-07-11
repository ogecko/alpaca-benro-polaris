[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Beta test results
## Result Summary
|Tester|Platform|Results|Summary|
|--|--|--|--|
| [Mark](#beta-tester-mark)| [X] Platform | [ ] Results | [ ] Summary
| [Vladimir](#beta-tester-vladimir)| [X] Platform | [ ] Results | [ ] Summary
| [Greg](#beta-tester-greg-stark)| [X] Platform | [ ] Results | [ ] Summary
| [John](#beta-tester-john)| [ ] Platform | [ ] Results | [ ] Summary
| [Daniel](#beta-tester-daniel)| [ ] Platform | [ ] Results | [ ] Summary
| [Alex](#beta-tester-alex)| [ ] Platform | [ ] Results | [ ] Summary
| [William](#beta-tester-william)| [ ] Platform | [ ] Results | [ ] Summary
| [Paul](#beta-tester-paul)| [ ] Platform | [ ] Results | [ ] Summary
| [Steve](#beta-tester-steve)| [ ] Platform | [ ] Results | [ ] Summary
| [Shiv](#beta-tester-shiv)| [ ] Platform | [ ] Results | [ ] Summary
| [Mauricio](#beta-tester-mauricio)| [ ] Platform | [ ] Results | [ ] Summary
| [Greg](#beta-tester-greg-stark)| [X] Platform | [ ] Results | [ ] Summary



## Beta Tester: Mark
(Dis: Bakermanz; GH: bakermanz; FB: Real Bread Aotearoa)
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
### Results
4 July 2026
* On the Connect page, most items are ‘red’ until they have been selected. However, RESET has always had a green tick (even before it is selected). - JDM fixed in dev2_2
#### 10 July 2026 - Beta 1 Release
* Settings - 90 x 60s exposures at 400mm on NGC292 SMC. Set up went really well with no issues at all - very smooth. Advanced Sequencer using solve and sync guiding (45 iterations of 2 x 60 sec exposures)
solving every 2 minutes (after 2 exposures). MAC off for the entire test and logging for PEC on.
* 55 Used / 23 Failed Light frames - when zoomed in, a high number of images show unusual shaped stars with squiggles, indicating some kind of movement during the session (but there was no wind).
Almost as if there may have been some form of vibration or oscillation during the imaging. Using PixInsight for Weighted Batch Preprocessing (see image), shows only 55 light frames
were used (23 failed and 12 rejected due to squiggles?) - see image1
    > JDM - I analysed the logs with fits_pec.ipynb and it show excellent PEC tracking after about 10min of learning. RA drift 111 '/hr +/- 10 H1 cycle , Dec drift 22 '/hr +/- 4.4 H1 cycle. Given the good results I have a hunch that the Failed frames are due to wiggle after some of the Sync Guides. On my setup I change filters after each Sync Guide so this gives it time to settle, but with OSC there is potentially too little time to settle. You could try adding a "Wait for Time Span" instruction after the "Solve and Sync" to check whether this helps. Start with say 30s to see if it eliminate wiggle, then reduce and optimise. Let me know if this helps, I will try as well without filters. 
* MPA - as an experiment, I changed the usual existing workflow. This resulted in the best residuals I have ever had (see image2) ... not sure if this is down to the revised workflow or other factors with the Beta version.
    * Existing: (1) South Celestial Pole (2) Future Target (d-2) (3) NINA
    * Revised:(1) South Celestial Pole (2) Target (i.e NGC292 SMC) (3) T Future Target (d-2) (4) NINA
    > JDM - More spread out sync points should help and doing a sync at target is definely worth it. There is also a slighly random factor of where the worm gear positions will be at each sync point.
* Calibration Frames - At the end of the imaging session, after stopping the tracking, I adjust the Alt position to point upwards. This facilitates taking the calibration frames (Darks, Bias, Flats, Flat Darks) - when using an iPhone as a flat panel for the Flats.
* Park Position - I would expect this to return the Benro Polaris to its start position (after the
initial Reset, which mirrors the original double joystick tap on the Benro Connect App). The
unit did not return to +180° +045° -000° .,..... instead it was +191° +042° +001° (see image3)
Using the Home and Park again made no difference
    > JDM - This Park Position offset is due to the accumulated drift that has been corrected for by PEC. Given the large drift of RA 111 '/hr, this can greatly effect its position when the motors are returned to their 0,0,0 position. A solve and sync will fix this.
* MPA Persistence - Next Morning when the Mini PC was switched on (in order to copy the image files and Logs
onto USB drive), I also tried the set up process with Polaris and found that it was already set
for ‘Multipoint Alignment’ and I presume this is intentional, in case the equipment and target
were to remain the same for another session.
    > JDM - In v2.2 when the driver persists the MPA sync points and reloads them whenever the driver restarts. This preserves the alignment through driver restarts, like you experienced the next morning.
* Alignment reset - Furthermore, after the (180° 45° alignment) the start position showed its starting position as +179° +044° -001° (see image4). Selecting Park, changed this to +178° +045° -000° (see image5). Not sure why these figures aren’t always +180° +045° -000° ??
    > JDM - this may be due to rounding error as 179°59'50" is very close to 180°

### Summary




## Beta Tester: Vladimir 
(Dis: vyskocil; GH: vyskocil; FB Vladimir Vyskocil)
Notes: feedback on MacOS and Raspberry Pi 4
### Platform & Environment
* Applications: CCDCiel beta 0.9.92-3846, IndiStarter 2.4.2-220, Stellarium 25.2
* Platform: MacOS Tahoe 26.1, Raspios Trixie (2025-10-01-raspios-trixie-arm64-full.img), Firefox v145
* Hardware: MacBook Air M4 13" 32Go SSD 2To, Raspberry Pi 4 4Go VILROS 802.11n wifi dongle.
* Optics: Cooled astro camera ZWO ASI533MC Pro, lens TTArtisan 500mm f/6.3 (Canon EF), Optolong L-Pro filter, 50/205 Deluxe - TS-Optics guidescope and ZWO ASI715MC camera.
* Tripod: Manfrotto 190XPROB, precise hardware level
### Test Areas
### Results
4 July 2028
* Elevation offset - started Alpaca but I forgot to fully deploy the Polaris to be horizontal and did the usual setup. But now there is a 45 degrees offset in elevation
    > JDM - This is likely MPA/Quest model causing an offset from the home position. In v2.2 MPA is persisted to allow restarts without re-aligning. To fix, typically just toggle to SPA and back to MPA
* Latitude data entry - When a 0 is typed in lat/lon, it disappears when it’s the last digit
    > JDM - I've increased the debounce to 1.5s to allow for trailing zero data entry on lat/lon. This is fixed in the latest dev2_2
* No Astro Module - The blue tag was displaying astro v, maybe it should not be displayed at all
    > JDM - Connect page highlights missing astro module. This is fixed in the latest dev2_2
* M2 Speed Calibration - When trying to calibrate the motor M2 I an errorP
    > JDM - problem with legacy code not updated for new kinematics. This is fixed in the latest dev2_2
* Reset Astro Axis - I don’t know how to reset the astro axes
    > JDM - Home or Connect Page Reset should reset all axis to zero position.
* SP / PV deviation - It is idle but the white and green arrow are not aligned
    > JDM - When in idle, if the motors are moved the present value will deviate from the SP. pressing the vertical bar with arrows will realign the SP's.

### Feedback Summary



## Beta Tester: Greg Stark
(Dis: gbstark; GH: starkgb, KS: Greg Stark)
### Platform & Environment
* Applications: Nina 3.2.0.9001, Stellarium 25.4.0, PHD2 2.6.14
* Platform: Windows 11 Pro 25H2, Browser: Google Chrome Version 149.0.7827.115
* Hardware: MeLe 4C (32 GB with 512 GB SSD), iPhone 13 mini iOS 26.5.
* Optics: Sony a7R IV (Full Frame, IMX455?), various lens from 20mm f/1.8 to 150-500mm f/5-6.7, no filters, Guiding via QHY5III 678M w/QHY 30mm f/4.3 scope.  
* Alt setup: Player-One Poseidon C (OSC APS-C, IMX571), Borg 90FL w/Starizona Apex ED reducer (325mm f/3.6), IDAS GNB (Ha+OIII), Askar C2 ColourMagic (SII+OIII), Guiding via QHY5III 678M and OAG
### Test Areas
* Indoor slew/movement tests via Alpaca Pilot
### Results
June 2026
* Early dev2_2 build 19-Jun-26; at Az=0; changing Az around 360/0 can cause unecessary "unwind" operations. JDM - fixed in dev2_2
* When switching between the Dashboard and Multi-Point Alignment windows in the Pilot App, the coordinates on the Dashboard keep switching back to alt/az (a bit of an annoyance). JDM - Fixed in dev2_2
* On the Mac running dev2_2 with Stellarium 26.1, the RA/DEC/PA method to add SYNC points does't seem to work.  - JDM Unfortunately, Stellarium Desktop doesn't support the SynSCAN Sync command eg “S34AB,12CE”. Not sure why they don't, but Stellarium Mobile does.
July 2026
* I was trying to perform the motor speed calibration as shown in the video and it didnt work. JDM - Fixed in dev2_2
### Feedback Summary


## Beta Tester: John
(FB: John Harrison; GH: 5x5Stuido)
Notes: Ireland Week43, New 5nm filters.
### Platform & Environment
* Applications: Application Versions (Nina/Stellarium/PHD2, etc), 
* Platform: OS Version, Browser Version, etc.
* Hardware: MiniPC model, Tablet model, Phone model.
* Optics: Camera Model, Sensor, Lens Model and Focal length, Filters, Guidescope, etc

### Test Areas
...
### Results
8-Jul-2026 Even after setup the connect Polaris icon stays red instead of turning green. Reproduced several times tonight just going through the connection process - JDM fixed in dev2_2
### Feedback Summary
...




## Beta Tester: Paul
(Dis: Paul C)
### Platform & Environment
* Platform: Win11?, cheap mini PC, iOptron carbon fibre tripod
* Applications: Nina, PHD2
* Optics: astro modified Z7 with the 150-600 zoom set to 352mm, Dew Bands
* Guiding: iOptron 30mm f4 guide scope and ASI220 camera
* Power: SVBONY SV241 Pro
### Test Areas
### Results
### Feedback Summary



## Beta Tester: Daniel
(FB: Daniel Michaud; Dis: Dmich39; GH: Dmich39)
### Platform & Environment
- Mini PC : Nipogi GKIII Alder Lake N97 ,  16 GB memory 1 GB on disc  Win Pro 11, very similar to Mele. Built in Wifi port + external USB one, ( TP Link  ) 
- Benro Polaris Astro in latest firmware & Benro app version
- Solid tripod weighted with  5 kg mass , levelled carefully with 2 digital levelling tools (< 0.1 degree error in any direction)
- Arca swiss Plate carefully positioned precisely 90 degrees vs camera body with help of calliper,equerre.
- Camera Canon 5D MK III unfiltered & Canon 5D MK IV normal
- Various Canon EF L Lenses : 200 mm F2.8, 100-400 F4.5, x1.4 multiplier gen II, and x2 multiplier gen III. Heated Lens Caps due freezing conditions these days.

### Test Areas
### Results
### Feedback Summary
### Conclusion  







## Beta Tester: William
(FB: William Siers; GH: Spiderx01, Dis: williamsiers)
Notes: Phoenix Week43
### Platform & Environment
* Applications: Alpaca Pilot 
* Platform: OS Version Win11, Chrome Browser.
* Hardware: Mele 4C Mini-PC
* Optics: Camera Model, Sensor, Lens Model and Focal length, Filters, Guidescope, etc

### Test Areas
### Results
### Feedback Summary
...





## Beta Tester: Alex
(Dis: Alex; FB: Alexander M...; GH: ..)
Notes: help with producing tutorial/overview and beta testing
### Platform & Environment
* Applications: Nina 
* Platform: Win10, Python v3.12.7, Ascom platform 7.1
* Hardware: Intel MacBook pro that is running win10 via bootcamp. it is a shame it won’t run on windows for ARM… I’d love to use my M1 MacBook for this
* Optics: Nikon Z6, 135mm/300mm Lens, Filters, Guidescope, etc

### Test Areas
### Results
### Feedback Summary

## Beta Tester: Steve
(Dis: LanzaSteve; FB: Steve E...; GH: SteveE..)
Notes: Tried BP Dither
### Platform & Environment
* Applications: Application Versions (Nina/Stellarium/PHD2, etc), 
* Platform: OS Version, Browser Version, etc.
* Hardware: MiniPC model, Tablet model, Phone model.
* Optics: Camera Model, Sensor, Lens Model and Focal length, Filters, Guidescope, etc

### Test Areas
### Results
### Feedback Summary


## Beta Tester: Shiv
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
### Feedback Summary
...


## Beta Tester: Mauricio
(Dis: AstroPolo?; FB: Mauricio Salazar; GH: MauriSalazar, KS: )
Notes: Last week RC1 tester.
### Platform & Environment
* Applications: Application Versions (Nina/Stellarium/PHD2, etc), 
* Platform: OS Version, Browser Version, etc.
* Hardware: MiniPC model, Tablet model, Phone model.
* Optics: Camera Model, Sensor, Lens Model and Focal length, Filters, Guidescope, etc

### Test Areas
### Results
### Feedback Summary





## RFC
FB: Andrew Sargent; GH: CynicalSarge

FB: Mingyang Wang; GH: saltyminty

YT: @NickHartman  

YT: @robertedgar853  