[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Beta test results
## Result Summary
|Tester|Platform|Results|Summary|
|--|--|--|--|
| [Mark](#beta-tester-mark)           | [X] Platform | [ ] Results | [ ] Summary
| [Vladimir](#beta-tester-vladimir)   | [X] Platform | [ ] Results | [ ] Summary
| [Greg](#beta-tester-greg-stark)     | [X] Platform | [ ] Results | [ ] Summary
| [John](#beta-tester-johnphantom)    | [ ] Platform | [ ] Results | [ ] Summary
| [lowend1hz](#beta-tester-lowend1hz) | [ ] Platform | [ ] Results | [ ] Summary
| [Daniel](#beta-tester-daniel)       | [ ] Platform | [ ] Results | [ ] Summary
| [Alex](#beta-tester-alex)           | [ ] Platform | [ ] Results | [ ] Summary
| [William](#beta-tester-william)     | [ ] Platform | [ ] Results | [ ] Summary
| [Paul](#beta-tester-paul)           | [ ] Platform | [ ] Results | [ ] Summary
| [Steve](#beta-tester-steve)         | [ ] Platform | [ ] Results | [ ] Summary
| [Shiv](#beta-tester-shiv)           | [ ] Platform | [ ] Results | [ ] Summary
| [Mauricio](#beta-tester-mauricio)   | [ ] Platform | [ ] Results | [ ] Summary
| [Greg](#beta-tester-greg-stark)     | [X] Platform | [ ] Results | [ ] Summary



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
#### 11 July 2026 - Beta 1 Release
* As expected 30s at 400mm was absolutely fine. I tried Wait for Time Span before each and every exposure at 60s but these delays did not eliminate the squiggles … tried 10s, 20s, 30s, 45s, 60s … things improved with a longer delay but still not great (see attached image). I guess delays of 60s and beyond, before every exposure simply eats into the overall time for the imaging sequence. That being said, I’m really happy with solve and sync at 30s in my light poluuted city
* 90 x 60s exposures at 400mm on C92 Carina Nebula. MAC off for the entire test and logging for PEC on. Set up went really well with no issues at all - very smooth
* MPA Settings - I used the previous revised MPA Workflow:
(1) South Celestial Pole (2) Target (i.e C92 Carina Nebula) (3) Future Target (d-2) (4) NINA
Again, this resulted in good residuals, which may be attributable to the version.
* Advanced Sequencer using solve and sync guiding (45 iterations of 2 x 60 sec exposures) solving every 2 minutes (after 2 exposures)
* "Wait for Time Span" instruction after the "Solve and Sync, was added to the NINA Template. However, it did not work correctly, in this position in the sequence. The solution was to add it before “Smart Exposure” ..... This meant that after a “Solve and Sync” had completed, there was am intentional delay, before the next set of “Smart Exposure” (in may case 2 x 60 sec). With a "Wait for Time Span” of 15s, sufficient time was available to al.low the plate solve (from “Solve and Sync”) to complete and disappear off the screen, before running the “Smart
Exposure”
* Light frames - despite these changes, when zoomed in, a high number of images show unusual shaped stars with squiggles, indicating some kind of movement during the session (but there was no wind) -‘Winged birds, tadpoles and small streaks’ were evident in many frames. Almost as if there may have been some form of vibration or oscillation during the imaging.
* Having previously used “Solve and Sync” successfully on C/2025 R3 (PANSTARRS) using feature-pec_refactor (15 May 26 ) with 30sec exposures at 300mm, I’m wondering if my recent 60s exposures at 400mm may be pushing things?
* Using PixInsight for Weighted Batch Preprocessing, shows only 36 light frames out of 90,
could be used.
* Thoughts - since the Carina Nebula is in close proximity to the South Celestial Pole, I’m
wondering whether the MPA sync points were too close together, to get a good alignment?
Perhaps the MPA workflow may have benefited from being adjusted to:
(1) South Celestial Pole
(2) Target (i.e C92 Carina Nebula)
(3) Future Target (d-2)
(4) Future Target (d-2)
(5) NINA
This may have given a better ‘spread’ of the MPA manual plate solves and sync
    > JDM - I checked log files and could not see any Heartbeat or Event Loop lags.

#### 15 July 2026 - Beta 1 Release
* Exposures at 400mm on C92 Carina Nebula. Set up went really well with no issues at all - very smooth
*  Advanced Sequencer using solve and sync guiding and tests performed at both 30s and 60s
to try and identify potential slight ‘wiggle’ after Nina finishes an exposure (disturbance to the
PID controller?). maybe this causes a slight wiggle. (iterations of 2 x 60 sec exposures) solving
every 2 minutes (after 2 exposures). NINA Advanced Sequencer was used for several runs, each using ‘Solve and sync’ every 2
minutes
* First run, using settings (known to be fine) as a control sample:
Loop For Iterations - 10.
Smart Exposure - 4 x 30s.
Solve and Sync.
No issues whatsoever and all stars sharp
* Second run, increasing exposure time and adding a delay before each exposure:
Loop For Iterations - 10.
Wait for Time Span - 10s.
Take Exposure - 60s.
Wait for Time Span - 10s.
Take Exposure - 60s.
Solve and Sync.
All images show ‘squiggles, winged birds and tadpoles’, indicating movement during the
exposure. There was no wind or vibration from any other source to cause this.
* Subsequent runs used increasing time delay, before each exposure:
20s, 30s, 45s and 60s
*  Light frames - despite these changes, when zoomed in, a high number of images show the
unusual shaped stars; indicating some form of oscillation during the imaging.
* Previous imaging sessions at 400mm and 30s (using Solve and sync), have been fine in several
different versions of the driver, including this latest Beta 1. Perhaps 60s exposures is pushing things and if a delay in excess of 60s (Wait for Time Span) is required between every single exposure, this substantially increases the total imaging session time.
* At this stage, I am unsure what changes can be made, in order to eliminate the apparent
movement during exposures. Despite this, 30s exposures is perhaps all that is needed,
especially in light polluted city areas - this always gives fantastic results
* The target used for testing (C92 Carina Nebula/Caldwell) in close proximity to the South
Celestial Pole and I’m wondering whether the MPA sync points were too close together, to get
a good alignment? With 30s exposures this may not be as crucial, compared to longer exposures?
* Perhaps the MPA workflow may have benefited from being adjusted to:
(1) South Celestial Pole
(2) Target (i.e C92 Carina Nebula)
(3) Future Target (d-2)
(4) Future Target (d-2)
(5) NINA
This may have given a better ‘spread’ of the MPA manual plate solves and sync
    > JDM - Mark, you are the greatest, thanks for exploring the cause of the 60s subexposure anomalies. 
    Your latest results confirm there's an issue on subs greater than 30s. The last change to PEC was 3-June, adding the harmonics, which was necessary to cater for the oscillations in the drift rate. If you get a chance, can you compare the current dev2_2 to this old version from 3-June and see if the problem disappears? I've re-created the feature/pec_refactor branch so you can refetch the old version.

#### feature-pec_ff_status - 26 July 2026
1. 60s exposures at 400mm on Caldwell C92 (Carina Nebula)
2. Initial setup went really well, with no connectivity issues at all. As always, tripod was perfectly
aligned to face South (180°) and levelled. Whilst probably unnecessary, I wanted to eliminate
any possible links in the ‘error chain’
3. Alignment workflow (following AF run using ‘LensAF’ and ‘Hocus Focus' N.I.N.A Plugins)
a. Initial single point alignment (image>plate solve in N.I.N.A)
b. Multipoint set and slew to South Celestial Pole (second plate solve in N.I.N.A)
c. Slew to target C92 Caldwell (third plate solve in N.I.N.A)
d. EQ RA coordinates set to d-2 (fourth plate solve in N.I.N.A)
e. N.I.N.A > Framing assistant > target > Slew and Centre (fifth plate solve in N.I.N.A)
NB. The target used for testing (Caldwell C92) is in close proximity to the South Celestial Pole
and was deliberately chosen to test for any streaks in the images (due to proximity to pole)
4. Perform Autotune Pec sequence x10 iterations to facilitate learning of PEC
5. N.I.N.A Advanced Sequencer - add target to Sequence (existing template) for ‘Solve and sync’
every 2 minutes (after every 2 exposures of 60s)
Loop For Iterations - 20
Smart Exposure - 2 x 60s
Solve and Sync
6. Following first run, driver was stopped to allow addition to be made to config.toml
(pec_n_harmonics = 1)
7. Polaris WiFi had to be restarted using Benro Connect App on iPhone
8. Driver restarted and multipoint alignment from first run had been automatically saved (green
check)
9. NINA - Equipment > reconnected both rotator and telescope (since driver had been stopped
and Polaris WiFi had disconnected) ..... connections for both camera and LensAF were still ok
10. Performed a manual plate solve, so that position in sky could be ascertained and then used
NINA Framing Assistant, to ‘slew and centre’ target.
11. Perform Autotune Pec sequence x10 iterations to facilitate learning of PEC
12. N.I.N.A Advanced Sequencer - add target to Sequence (existing template) for ‘Solve and sync’
every 2 minutes (after every 2 exposures of 60s)
Loop For Iterations - 10
Smart Exposure - 2 x 60s
Solve and Sync
13. Light frames - when zoomed in (200%), all 20 images are showing the unusual shaped stars
and squiggles; indicating some form of oscillation during the imaging. There was an
occasional light wind, but no vibration from any other source.

#### releases-2_2_beta3 - 28 July 2026
1. 60s exposures at 400mm on SMC and then Caldwell C92 (Carina Nebula)
2. Focus using LensAF and Hocus Focus
3. Run Multi-Point Alignment (SPole and 5 x Points) Template
4. Run MAC Autotune in Pilot and Apply
5. NINA Framing Assistant - Slew and Centre on first target (SMC)
6. Run PEC Tune Template (15x iterations)
7. NINA Framing Assistant - Add target to Advanced Sequencer (existing template) for ‘Solve
and sync’ every 2 minutes (after every 2 exposures of 60s)
Loop For Iterations - 10
Smart Exposure - 2 x 60s
Solve and Sync
8. NINA Framing Assistant - Slew and Centre on second target (Caldwell C92)
9. Run PEC Tune Template (15x iterations)
10. NINA Framing Assistant - Add target to Advanced Sequencer (existing template) for ‘Solve
and sync’ every 2 minutes (after every 2 exposures of 60s)
Loop For Iterations - 10
Smart Exposure - 2 x 60s
Solve and Sync
11. Light frames -there was no wind, but no vibration from any other source.
First run of 20 images on SMC - fantastic
18/20 perfect images (90%) and that was being really pedantic (well zoomed in at 300%)
Second run of 20 images on Caldwell C92 - not good
4/20 perfect images (20%) many showing winged and vertical tadpole misshaped stars
12. Observations - at the end of the first run (SMC), the camera was angled sideways (M3 rotator)
and it appeared that the M1 motor hadn’t moved ..... being positioned about 30° from the
original set up point. Even when the slew and centre was actioned for the second target
(Caldwell C92), it did not move. Looks as if only the M3 was ‘tracking’ the target.
Haven’t noticed this behaviour before and the camera is usually pretty level when imaging.
I’ve attached a few images showing the position of the mount and camera, between each
imaging run
13. Imaging on the first target was absolutely excellent and not sure whether my workflow for the
second target was correct (between bullet point 7 and 8, perhaps I should have parked the
mount?)


#### releases-2_2_beta3 - 29 July 2026
1. 60s exposures at 400mm on Caldwell C92 (Carina Nebula)
2. Focus using LensAF and Hocus Focus
3. Run Multi-Point Alignment (SPole and 5 x Points) template
4. Run MAC Autotune in Pilot and Apply
5. NINA Framing Assistant - Slew and Centre on Caldwell 92
6. Run PEC Tune Template (15x iterations)
7. NINA Framing Assistant - Add target to Advanced Sequencer (existing template) for ‘Solve
and sync’ every 2 minutes (after every 2 exposures of 60s)
Loop For Iterations - 10
Smart Exposure - 2 x 60s
Solve and Sync
8. Light frames -there was no wind or vibration from any other source.
8/20 perfect images (40%) when zoomed in at 200%
Several showing winged and misshaped stars, whilst others had small streaks and tadpoles,
Despite this, PixInsight was able to stack 14/20 (56%) images to produce great results
Effectively, this gives just over 50% success rate
9. Observations - on completion of the “Multi-Point Alignment (SPole and 5 x Points)” template,
the camera was angled sideways (M3 rotator) and it appeared that the M1 motor hadn’t
moved. Even when the slew and centre was actioned for the target in NINA (Caldwell 92) it did
not move. Looks as if only the M3 was ‘tracking’ the target (photo attached)
10. Residuals were extremely high (see image) and I guess this wouldn’t have helped the tracking
... though it’s interesting that the first six images in the imaging sequence, were perfect and it
deteriorated thereafter. It was random as to when a sharp image was produced and then a
misshaped star image occurred (no specific pattern)
11. With my previous MPA workflow, all motors have moved and the camera has always been
level and in line with the top of the Benro Astro Module, throughout the imaging. With the new
“Multi-Point Alignment (SPole and 5 x Points)” template, the camera is always tilted and
twisted at strange angles, throughout the imaging and looks as if only M3 (field rotator) is
tracking the target.
12. As a suggestion, I was wondering if it would be possible to realign the ‘twisted’ camera
position, straight after the new “Multi-Point Alignment” template run .... Something similar to
PARK (but that actually stops the tracking). Then the NINA ‘slew and centre’ would put the
camera on target as before (i.e. camera not twisted) and all three motors would be able to
track the target.
With the current twisted camera angles, it will probably make it difficult to use the NINA to
change the framing of the target. Speaking of which, I always connect the ‘Rotator’ (ASCOM)
within NINA ..... but wondering whether this could possibly impact on something, even though
I’m not currently changing the framing angle (?) ... just trying to consider all the variables, that
may be contributing to the issue.
13. Generally, I think that the new methodology to perform the MPA is absolutely brilliant .... No
longer faffing about, entering targets (pole, target, switching to EQ mode and entering d-2 etc)
and repeatedly needing to complete manual plate solves and syncs within NINA. It’s genius,
but just need to find a way to incorporate the M1 motor in the sequence and eliminate the
apparent M3 being the only tracking motor - though I fully accept there may be valid reasons
behind this.


#### releases-2_2_beta3 - 02 August 2026
1. 60s exposures at 400mm on Caldwell C92 (Carina Nebula)
2. Focus using LensAF and Hocus Focus
3. Run Multi-Point Alignment (SPole and 5 x Points) template
4. Run MAC Autotune in Pilot - not applied (red warning with autotune results showing ‘Weak’ -
image already sent earlier via FB messenger)
5. NINA Framing Assistant - Slew and Centre on Caldwell 92
6. Run PEC Tune Template (15x iterations)
7. Plate solve issues due trees being visible at bottom of frame (as per earlier FB messenger)
8. Clear run and select new target. Slew and centre to LMC
9. Run PEC Tune Template (15x iterations)
10. Plate solve issues again, possibly due to full moon? (as per FB messenger)
11. Clear run and select new target. Slew and centre to SMC
12. Run PEC Tune Template (15x iterations) - plate solving absolutely fine (even with full moon)
13. NINA Framing Assistant - Add target to Advanced Sequencer (existing template) for ‘Solve
and sync’ every 2 minutes (after every 2 exposures of 60s)
Loop For Iterations - 10
Smart Exposure - 2 x 60s
Solve and Sync
14. Light frames -there was partial wind, but no vibration from any other source (mechanical or
footsteps etc)
Many showing winged and misshaped stars, whilst others had small streaks and tadpoles (as
per earlier FB messenger)
15. Observations - on completion of the “Multi-Point Alignment (SPole and 5 x Points)” template,
the camera was now back to its start point (az180 alt 33 roll 0) - perfect. However, when using
NINA to slew and centre to target, it struggled and was needing many plate solves. Cancelled
this process and used Pilot to goto SMC ..... NINA was then fine with slew and centre.
16. Residuals were extremely high (images already sent earlier via FB messenger)
17. With my previous MPA workflow (d-2 etc), residuals were superior compared to the new MPA
template script. The tripod is always set up in the same location (with dots of paint on the
driveway, to mark the position of the 3 spiked feet on the tripod). The tripod adjustable base
ensures that the Benro Polaris is always in the same ‘fixed’ position and its bubble level is
centred) - this has remained the same throughout all the weeks of testing
18. MPA Template Script - noticed that the position of the M1 motor did not always reflect the
“az” figure in the script. Difficult to ascertain its movement properly during the dark, so ran the
template in the daytime to visually monitor the mount position (albeit without solve and sync
succeeding)
19. Here are my findings:

    | Point | Az | Alt | Roll | Comments
    | -- | -- | -- | -- | --
    |1| 180| 33| 0| Ok
    |2| 105| 50| 45| Ok
    |3| 135| 35| 65| Az 225
    |4| 156| 67| 0| Az 105
    |5| 224| 52| -65| Az doesn’t move (still at 105)
    |6| 254| 62| -45| ? Az looks like 225 but maybe Ok
    |7| 180| 33| 0| Ok
20. The actual figures “Az” within ‘comments’ are based on physically looking at the position of
the mount and may not be accurate.
Point 3 - shows a completely different position (225) to the template figure (135)
Point 4 - shows a completely different position (105) to the template figure (156)
Point 5 - the Az position did not move (stayed at 105) - template figure should be (224)
Point 6 - visually difficult to ascertain position but appears different position (225) to the
template figure (254)
21. Whilst this figures are approximations (‘by eye’), they show clear differences and I;’m
wondering if this is impacting on the success of the MPA etc

#### releases-2_2_beta4.3- 04 September 2026
* See alpaca.mark_Beta4.3_09_04_a*.log; Includes issue #88 fixes 1-13, not 14
* Report on the 2 hour session, without PEC
* The issue at 20:50 was actually not footfall, but it was me switching on the camera whilst connecting to NINA (I had omitted to do this) - so this resulted in the erratic movement of the mount etc. My fault completely
* First  image was taken at 20:56 and the images were a bit mixed (some okay, others with squiggles etc)
* Images zoomed in to 200% and showing time stamp
* From 21:33 virtually all good until 21:46 … fine for another 5 mins (21:51), then good for 8 mins (21:59 until 22:02)
* Thereafter, virtually every image from 22:09 were excellent, right until the end of the session at 23:03 - about 70 images over almost an hour
* There was some wind at times, which might explain the squiggles - but brilliant performance for the last hour 
* On the face of it, dev2_2 (wiithout PEC) is much improved

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
4 July 2028 - Beta 1 Release
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

11 July 2026 - Beta 1 Release
* I have a question about Sync Guiding: how Alpaca is managing to not interfere with the ongoing shooting ? Does this needs a special step in the sequence ? I think so, but is this possible with CCDCiel ? 
When taking a sequence I'm usually asking CCDCiel to plate solve from time to time the last taken picture without stopping the sequence, I now understand that this may introduce some shaking from the mount if Alpaca issue a correction when a frame is being captured ?
    > JDM - When the Driver interprets a sync as a sync guide, it updates its position and lets the PID controller shift it back to the current SP. This might cause a disturbance if the shift is significant, but PEC should be keeping this small. Havent tried with CCDciel yet but you may need to add a small delay after the sync to allow the PID to resettle.
* Do you have some special advice helping to setup Polaris with Alpca in daytime for tracking the Sun ?
I'll use a ND 100 000 filter before and after the totality but will be taking it away at the totality to have a chance to capture the Sun corona ! Maybe you might release an Alpaca Total Eclipse Edition
    > JDM - I havent tried using Polaris for solar at all yet. Let me know if you learn any insights.
* You may integrate PeakFinder in the Sky Conditions tab : https://www.peakfinder.com
    > JDM - Great idea. I've added it in dev2_2 and included the site info, and telescope pointing direction in the link!

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
June 2026 - Alpha 1 Release
* Early dev2_2 build 19-Jun-26; at Az=0; changing Az around 360/0 can cause unecessary "unwind" operations. 
    > JDM - fixed in dev2_2
* When switching between the Dashboard and Multi-Point Alignment windows in the Pilot App, the coordinates on the Dashboard keep switching back to alt/az (a bit of an annoyance). 
    > JDM - Fixed in dev2_2
* On the Mac running dev2_2 with Stellarium 26.1, the RA/DEC/PA method to add SYNC points does't seem to work. 
    > JDM - Unfortunately, Stellarium Desktop doesn't support the SynSCAN Sync command eg “S34AB,12CE”. Not sure why they don't, but Stellarium Mobile does.
July 2026
* I was trying to perform the motor speed calibration as shown in the video and it didnt work. 
    > JDM - Fixed in dev2_2
### Feedback Summary





## Beta Tester: John/Phantom
(Dis: John Harrison/Phantom/Phantomcnt; GH: 5x5Stuido, KS: , FB: )
Notes: England, New 5nm filters.
### Platform & Environment
* Applications: Application Versions (Nina/Stellarium/PHD2, etc), 
* Platform: OS Version, Browser Version, etc.
* Hardware: MiniPC model, Tablet model, Phone model.
* Optics: Camera Model, Sensor, Lens Model and Focal length, Filters, Guidescope, etc
### Test Areas
### Results
4 June 2026 - Alpha 1
* Pano Portrait/Landscape - switching between landscape and vertical panos is on my wish list
    > JDM - I've included a swap button on the Pano Settings page
19 June 2026 - Alpha 1
* Pano Presets - is it worth being able to save the settings for later use? 
    > JDM - We could add a Save/Load feature like we did for Locations, but I think this is for a future releases consideration. I spoke too early before. I made the location save/restore into a more generic preset save/restore feature. Now we can save preconfigured Panoramas and restore them easily.

5-8 July 2026 - Beta 1 Release
* Easier Connect for non DSO Users - The l bracket is a bug I suffer with and I know at least a handful of people also have the same issue. I'd guess it'll be at least a few dozen with the same issue. You could potentially allow people to toggle on and off what they want to see.
    > JDM - I've added L-Bracket and Site Location to the Connect Page checklist. 
* Even after setup the connect Polaris icon stays red instead of turning green. Reproduced several times tonight just going through the connection process
> JDM fixed in dev2_2

11 June 2026 - Beta 1 Release
* Catalog Filter Persistence - something I noted from last night, if you set a filter in the catalogue, hit goto and then come back, the filter is then cleared on your return. 
    > JDM - fixed in dev2_2. Catalog Filters persist when returning to the main Catalog page, but reset when opening a specific catalog view (Stars, Nebulae, etc.).
* Residuals - I had a residual with an orange triangle next to it. Obviously that means bad 😂. But I couldn't specifically find the meaning of it in the document. 
    > JDM - Fixed in dev2_2. Expanded on meaning of outlier residuals in control.md at https://github.com/ogecko/alpaca-benro-polaris/blob/dev2_2/docs/control.md#e-review-model-residuals

16 July 2026 - Galactic Panorama Video feedback
* Quick description of galactic coords and why. Maybe brief image in framing assistant to show how each mode would layout Pano to get the same image 
* 3rd axis for roll. Benro don't use this function so it will be worth a mention that alpaca does 
* Copy and paste coords to Nina is an excellent addition. Maybe an annotation to the name of the plugin needed for those extras Polaris commands
* Mention a pano like this all can be done manually with a device like a tablet, pi zero 2 paired with your phone. Nina is used to increase efficiency and better supports DSO functions. Useful but not necessary for all.
* Flat white feature is excellent. I did get a surprise when I first clicked on it 😂
* Maybe a skip to autopano chapter mark for those with lights only. I think it would be safe to assume a non Nina shooter would be checking images as they take them and so would cull in the field. 
* Mention where to get autopano on GitHub
* Siril scripts excellent 
* I think it's outside the scope of the tutorials, but I did have the thought that osc processing vid could be useful
* I am getting a kick out of you shoot from Aus, so many DSO I don't know! Running chicken nebula 



### Feedback Summary



## Beta Tester: lowend1hz
(Dis: lowend1hz; FB:  GH: wbuchanan, William Buchanan, KS: )
(https://github.com/wbuchanan/NikonCameraSettings)
### Platform & Environment
* Applications: Application Versions (Nina/Stellarium/PHD2, etc), 
* Platform: OS Version, Browser Version, etc.
* Hardware: MiniPC model, Tablet model, Phone model.
* Optics: Camera Model, Sensor, Lens Model and Focal length, Filters, Guidescope, etc
### Test Areas
### Results
26 May 2026 - Alpha 1
* Vertical Panos - I'm going to start thinking about to implement this myself, but I started thinking yesterday about how to execute it and figured I would mention it to you as well.  Currently, the panorama implementation is focused primarily on multicolumn panoramas with some support for multiple rows to create panoramas that are horizontally oriented.  However, creating vertically oriented panorama requires a slightly different implementation due to the mechanical limitations of the device.  For example, capturing a vertical panorama with a 180° FoV (effectively 180° of rotation in the altitude direction) would requires a different mechanical implementation compared to a horizontal panorama with a 180° FoV (requiring 180° of rotation in the azimuth direction).  There won't be a way to allow this for all focal lengths due to the mechanical limitations of the device, but for short enough focal lengths it should be possible to provide the requisite coverage.  With a panoramic head like the Nodal Ninja M2 (https://www.nodalninja.com/m2-no-rotator/F8000#top_c) it is fairly trivial to do this since there is no mechanical limitation, but for the Polaris we would need a way to first determine whether there would be sufficient overlap at the mechanical limits and then should be able to achieve the same.  The post-processing would be a bit more difficult since some of the frames would have the orientation shifted, but I imagine it should still be feasible.  One challenge would be determining if it would be better to treat this like a separate "mode"/"module" or to try incorporating it directly into the existing panorama code base.  Given that these types of panorama are less common, my inclination would be to implement it as a separate "mode"/"module" with a toggle in the UI, if nothing else to avoid introducing regressions into the existing panorama functionality.  Do you have any thoughts/ideas about something like this?
> JDM - Added Galactic Panos with multiple changes. The kinematics now properly adjust the roll or alt so that the panel is always reachable even when it is at an Alt of say 120. The logic wraps altitudes over the top, and also wraps roll angles to upside down if it cannot reach it. The PanoGrids can now work in Topocentric, Equatorial or Galactic Reference Frames. Changing the reference frame changes the anchor co-ord as well as what vstep/hstep adjust between panels. For topo, its a Az/Alt grid; for equatorial its a RA/Dec grid, for galactic its a glat/glon grid.
* Polaris is challenged vertically and never reached panels near the zenith | The driver now understands its limits and gives priority to Az/Alt, but will compromise rotation and then Alt if necessary.
* Couldn't find a Siril script to handle mosaics, especially the more tedious mono workflow. | We now have Siril scripts to preprocess, stack, compose, stretch, and convert using Siril, Graxpert and Veralux (feel free to tailor)
* When multiple panels are involved, it gets even worse with stacking images, especially when Siril renames them pp_00001, etc | Now the Siril script automatically adds a prefix to each file, clearly identifying what panel it belongs to eg  GLATNNN_GLONNNN_
* Dealing with the flat wizard, darks and biases between Nina and Sirils expectations meant a lot of file copying and directory renaming. |Now a script can rename directories and the Siril scripts will work off a standard calibration subdirectory.
* Over the top Altitude and meridian flips really confused the stitching software, not understanding how to mirror the images. | Now all panel tiffs are flipped automatically to align in the same way as the first panel, making it easier for Kolor Giga Pano.

### Feedback Summary





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




## Beta Tester: JavaMD
(Dis: JavaMD / Steve Egge; FB:  GH: , KS: )
### Platform & Environment
* Applications: Application Versions (Nina/Stellarium/PHD2, etc), 
* Platform: OS Version, Browser Version, etc.
* Hardware: MiniPC model, Tablet model, Phone model.
* Optics: Camera Model, Sensor, Lens Model and Focal length, Filters, Guidescope, etc
### Test Areas
### Results
11 July 2026 - Beta 1 Release
* Still trying to get Alpaca to work with my Benro. reinstalled everthing once again .... separating with login's on the mele as I also have a AM5N mount I bought out of frustration with a thought of moving on .... but the BP is SO much lighter .... at any rate here are my latest from trying to connect.
> JDM - Have you tried walking through the troubleshooting guide on communications? 
* Thanks ... got connected by turning ipv6 off.  Now need to see why NINA doesn't recognize the Nikon z6ii connected to the polaris.
### Feedback Summary



## RFC
FB: Andrew Sargent; GH: CynicalSarge

FB: Mingyang Wang; GH: saltyminty

YT: @NickHartman  

YT: @robertedgar853  