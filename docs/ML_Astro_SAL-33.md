#  MLAstro SAL-33 Official Thread
Summary of Cloudy Nights Forum thread p1-49

## 1. Core specifications
- **Payload:** visual load is 15 kg without a counterweight, or 20 kg with a 5 kg counterweight. For imaging, Minh recommends about two-thirds (about 70%) of the visual load, and he only guarantees performance within that range.
- **Alt-az versus equatorial:** capacity is the same in both modes.
- **Drive:** 17:100 strain-wave (harmonic) gearing on both axes.
- **Slew:** adjustable, up to 4°/s.
- **Brakes:** a physical brake on RA and a back-EMF brake on DEC.
- **Pointing memory:** the mount keeps its position through a power cycle.
- **Weight and build:** the mount head is 5.6 kg (a later post says 5.3 kg), CNC aluminium with silver anodising. All panels are aluminium. The construction is bolted and modular, with swappable side panels including laser-etched ones.
- **Power:** the power supply isn't included, and there's no DC output on the mount.
- **Other hardware details:** there's a bubble level on the front, and two M4 holes on the side (per a user). The shipping box is 33.5 × 33.5 × 19 cm.
- **Motors:** 48 mm NEMA17 steppers, which Minh says give about 25% more torque than the 40 mm motors common in competing mounts.
- **Drivers:** TMC2209 drivers in UART mode, socketed for swapping faulty ones rather than upgrading.
- **Tripod interface:** the mount uses a 3/8" thread plus 3 × M6 holes, the same as a ZWO AM5, according to MLAstro's product page.

## 2. Load, balance, counterweights and the gearbox bearing
- **Balance:** you don't balance a harmonic mount. A perfectly balanced harmonic performs badly, because these gearboxes need preloading. Minh gave the workable imbalance range for the SAL-33 as roughly 2 to 22 N·m. He never balances his own harmonic mounts, but says the setup must not tip over.
- **User disagreement:** a user argued that balance still matters for tripod flexure and stability, and that his harmonic mounts guide better when not seriously imbalanced.
- **No extra counterweight to compensate:** counterweights only balance torque about the RA axis. The gearbox's cross-roller bearing carries the radial load of the entire system (scope, counterweight and mount head) and already works near its limit. Overloading it risks damaging the bearing and can leave the mount unusable.
- **Total-load limit:** Minh said never to put more than 25 kg on the SAL-33, counterweight included. A user reading the chart on the product page described a 29 kg maximum total load, so check the chart yourself.
- **Limits depend on OTA size:** they depend on the telescope's centre-to-saddle distance. Torque is force times distance, so size matters as much as mass.
- **Latitude:** the chart values are at latitude 0. Minh says the dependence is small and to use the chart limits at all latitudes.
- **Safety margin:** built-in margin is for short spikes, such as bumping a door frame, not sustained overload. This applies to all harmonic mounts and worm-gear mounts too.
- **Counterweight hardware:** the bar is 20 mm with roughly an M12×1.75 thread (Minh wrote M12.5). ZWO's counterweight bar also fits, and it's about 10 mm longer. Counterweights aren't sold by MLAstro.
- **User experience:** DevonRob uses a 5 kg counterweight and finds harmonic mounts guide better heavier. He runs an EdgeHD 9.25 at 13-14 kg for imaging.

## 3. Reliability and service
- **Cold-temperature issue:** Batch 2 had a cold-weather problem that Minh attributed to a capacitor. He says coverage for it extends beyond the warranty, and affected owners should email MLAstro. Details were on Facebook and I couldn't see them.
- **Serviceability:** parts such as mainboards, drivers, motors and brakes are designed to be user-replaceable. MLAstro has forwarding warehouses in the US (Oregon), UK, France and Australia. Servicing videos are being added gradually.
- **Warranty:** one year, limited.

## 4. Firmware, software and connectivity
- **Firmware base:** official OnStepX hardware. The firmware and pin map are open source on GitHub (minhlead/MLAstro-SAL-33). Modifications that brick the mount void the warranty.
- **Updates:**
  - A first firmware update in Dec 2025 fixed occasional meridian flip failures, mostly affecting ASIAIR.
  - 10.27.p (mid-2026) is called important. After flashing, the motor and driver are briefly unpowered without the brake engaged. If the load falls, back-EMF could burn the driver, and one user did. So update with the scope off or reasonably balanced, and be ready to catch it.
  - You can stay on your current version if it works. Check your version in the last line of Config in MLAstro Hub.
- **Flashing:** it's done from Chrome using a web flasher. The SAL-33's chip shows as CP2102. Flashing SAL-33 firmware onto another ESP32 device bricks that device, and a user bricked an SVbony SV241 Pro this way. If the "hold BOOT" error appears, change computers or hold the BOOT button under the front plate. A flasher fix went live on Sept 8. Flashing can't be built into MLAstro Hub because of an ESP flash-tool licensing problem.
- **Web server versus Hub:** the SmartWebServer is deprecated, and MLAstro Hub (Windows, Android, Apple) is the recommended interface. If you still use the SWS, the address is http://192.168.0.1 (not https).
- **Restoring lost WiFi:**
  1. Open the front plate.
  2. Set the switch on the controller board to ESP8266/SWS.
  3. Connect by USB and open https://test.mlastro.com/ in Chrome.
  4. Flash the SWS commercial release.
  5. Move the switch back to ESP32/OnStepX and restart.
- **Bluetooth:** Android only. iPhones can't see the mount.
- **Windows setup:** ASCOM Platform 7.1.3, the CP210x Universal Windows Driver and OnStep ASCOM driver 1.0.43. The Hub .exe must be "unblocked" in Properties.
- **Software compatibility:** the standard OnStep driver works with KStars/Ekos/INDI, NINA, ASIAIR (WiFi ports 9997-9999, 9999 recommended) and any ASCOM app. Minh says WiFi latency can hurt guiding, so use a wired connection for guiding. SkyTrack satellite tracking should work, but he hadn't tested it.
- **Tracking:** ASIAIR can change solar, sidereal and King rates. On Batch 1, tracking began at power-up. From Batch 2 onward you must enable it or issue a goto.
- **Slew scripting:** the ASCOM MoveAxis call takes a sidereal multiplier, and arbitrary fractional values work. For example, `MoveAxis(0, 3.2)` gives 3.2× sidereal in RA. SharpCap's built-in list only shows six fixed rates.
- **Limits and alt-az alignment:** slew and axis limits can be set in the web server. To use alt-az, set the mount upright, choose Alt-Az in the configurator and power cycle. Minh does simple level-plus-one-sync or 3-9 star alignments, and the alignment isn't blind (you need to know star names).
- **Under development:** experimental collision detection using StallGuard, and a mount-modelling update for goto accuracy. Balance monitoring is not planned.
- **Anti-cable-snag:** it only lengthens the meridian flip and doesn't interfere with it.

## 5. Polar alignment and the Zero-Shift base
- **How it works:** you adjust alt-az with the locking bolts still tight and then leave them. The mechanism is patent-pending and undisclosed, using tight-tolerance machining and bearings. Minh claims no play in the altitude adjustment, unlike the EmCanAstro EM31.
- **Adjusters:** alt-az adjusters are simple screw-on pins. Batch 2 and later use finer-thread azimuth screws for better control and wind resistance. Batch 1 owners got a retrofit offer.
- **Methods:** digital polar alignment using the imaging scope, a PoleMaster or an iPolar. The side panel has a provision for an iPolar or PoleMaster. For daytime solar use, polar align at night and leave it, or use the day routine (rough alignment, goto the Sun, then centre it with the adjusters).
- **Modular base:** the mount head detaches by removing four screws. The old base could become an EQ wedge for a Seestar or star tracker.
- **Alignment and tracking:** Minh says easier alignment is mostly convenience. Many people guide better with polar alignment slightly off, because perfect alignment makes DEC corrections flip sides more often. That matters little on a harmonic mount, but on worm-gear mounts DEC backlash can elongate stars.
- **Robotic polar alignment kit:** a retrofit for the SAL-33 and SAL-66, with a one-knob azimuth adjustment, motors on the south side of the pier, and a WiFi web interface. It integrates with NINA's 3PPA and KStars' routine but probably not ASIAIR. An evaluation SAL-33 went to INDI's lead developer. The target was late 2026. Its load limit may be lower than the mount's.

## 6. Performance and guiding
- **Periodic error:** a prototype test gave under 20" peak-to-peak RA with a 14 kg rig, and Minh's production target is ±10" on the smallest cycle. He says a fixed PEC isn't practical, because PE varies cycle to cycle.
- **Predictive PEC:** PHD2's predictive PEC is his recommendation for RA. It kicks in after about two cycles (roughly 900 s), with RA predictive weight around 100%.
- **Guiding figures:** the reported numbers are Minh's relayed reports of 0.35" best and 1-1.5" in 20-30 mph wind, plus user reports. paling reached 0.66" after a first-night 1", DevonRob got under 1" in poor seeing, and TerryD1 got 0.3-0.4" in average seeing.
- **Minh's claim:** he says the mount should reliably guide under 1" unless seeing is poor or there's a lot of wind. He suspects ASIAIR's RMS reads low.
- **PHD2 recommendations (Jan 2026):**
  - Use PHD2's calibration assistant and enable multistar guiding and "Assume DEC orthogonality to RA".
  - For heavy rigs he runs high aggressiveness. For lighter ones and poor seeing, start at 0.35 minimum move and 50% aggressiveness, then raise it. Use 1-1.5 s guide exposures in poor seeing, since 0.5 s needs stable seeing.
  - His Sept 2026 advice was RA and DEC minimum move 0.25" and about 70% weight.
- **Focal length:** for long-exposure DSO he recommends staying under about 1000 mm. He says harmonic PE is large, guiding is reactive, and long focal lengths mean few guide stars and more wind and seeing sensitivity. He calls this conservative rather than a hard limit. It doesn't apply to solar or planetary work. Minh says 30 s unguided exposures are challenging on any harmonic mount.
- **Alt-az visual:** Minh reports good gotos in alt-az (objects land in the field of a 20 mm eyepiece on a 1300 mm scope) and no microstepping error.

## 7. Mounting, tripods and accessories
- **Compatibility:** anything that works with an AM5 works with the SAL-33.
- **P-200 pier extension:** MLAstro's P-200 adapts common tripods and is natively compatible with Avalon T-Pod. Fasten it with M6 screws under 20 mm, mushroom or socket head, using a 4 mm Allen key. Washers are optional and protect the base plate from scratches.
- **Adapters:** MLAstro adapters exist for Celestron CPC1100, SW EQ6 (usable without the P-200), iOptron and Sky-Watcher tripods, Meade 2" tripods (which use the tripod's six top-plate holes, so retract the centre rod), and the iOptron Tri-Pier 360. Custom adapters are available.
- **Exceptions:** EQ3/EQ5 tripods have a non-removable azimuth pin, so use the P-200 to clear it. The ZWO PE200 has no holes for MLAstro's EQ6 adapter, and users described workarounds and a Starizona adapter.
- **Tripod advice:** Minh recommends a steel, medium to heavy tripod over carbon, which is lighter, tips more easily and vibrates more. He prefers the iOptron CEM60/70 two-M8 connection to the EQ6's single centre screw, because he says the cast EQ6 top plate may not be machined flat. A user suggested Sky-Watcher EQ5/EQ6 tripods.
- **Saddle:** a collar kit is available for saddles wider than 90 mm. A saddle 12 V/USB hub cannot be retrofitted, because it needs a hollow harmonic drive, and Minh has no plan to add one.
- **Guide scope:** mount it side by side on a Losmandy dovetail. The PoleMaster holes aren't on the moving part.

## 8. Roadmap and business (brief)
- **SAL-66:** a larger mount with a saddle hub and full 12 V/USB. An earlier estimate was about 30 kg without a counterweight and 40 kg with one, using a size-25 RA gearbox. The target price was under $2,000, and it was speculative.
- **Other plans:** encoders and direct drive are considered for the larger mount only. Minh declined to build a smaller mount for pricing reasons.
- **Price:** $999 for the first 50, then $1,099, then $1,249 from Batch 6 (Feb 2026). Minh said margins are thin and cited costs. Payment is PayPal only, with full payment at preorder, though alternatives were planned.
- **Shipping:** it ranged from $140 in early 2026 to $199-$270 by April 2026, with a tariff- and tax-inclusive courier option. Refunds are available before shipping.
- **Production status:** Batch 9 sold out on Sept 14, 2026. Preorders now roll into Batch 10 with an estimated shipping window of mid to late Nov 2027. Batch 9 ships through early Oct 2026.

To cover the unread stretch, you could read the thread directly from about page 22 to page 45, or point me at a specific date range or topic and I can try to search for it.