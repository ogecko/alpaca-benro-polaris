[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# General Final Release Checklist
- [ ] Complete todo checklist
- [ ] Check Driver package vulnerabilities
  - [ ] pip-audit
  - [ ] pip show urllib
  - [ ] pipdeptree -reverse --package bleach 
  - [ ] pip install --upgrade urllib3==2.7.0
  - [ ] Modify all requirements.txt files accordingly
- [ ] Check Pilot package vulnerabilities
  - [ ] Check non-breaking updates (dry run): quasar info;  quasar upgrade;        Apply the updates: quasar upgrade -i
  - [ ] Check major potentially breaking updates (dry run): quasar upgrade -m;     Apply the updates: quasar upgrade -m -i
  - [ ] Check runtime dependencies:                         npm audit --omit=dev   Apply the updates: npm audit fix
  - [ ] npm list --depth=0
  - [ ] npm install axios@^1.13.5
  - [ ] npm list axios
  - [ ] Upgrade Node on win11 by downloading installer from https://nodejs.org/en/download
- [ ] Check GitHub open issues
  - [ ] No CodeQL Security or Quality issues
  - [ ] No Malware or Vulnerability issues
  - [ ] No AI findings that have not been addressed
  - [ ] Confirmed any open GitHub issues are acceptable for release
- [ ] Final Changes - git checkout dev2_2, git pull origin dev2_2
  - [ ] Check version # in readme.md, release-notes-vX.X.X.md, shy.py, installation.md, AboutPage.vue, AltLayout.vue, package.json, abp-overview.png
  - [ ] Check download links in release-notes-vX.X.X.md, installation.md x 2
  - [ ] Build Pilot for release
  - [ ] Confirm all Alpaca ConformU tests pass
  - [ ] Confirm all Alpaca Driver unit tests pass
  - [ ] Confirm all Alpaca Pilot unit tests pass
- [ ] Create Branch - releases/2_2_0 based on dev2_2
- [ ] Merge into main - git checkout main, git pull origin main, git merge releases/v2.2.0, git push origin main
- [ ] Draft Github New Release and Tag - on main branch
  - [ ] Release Title: Alpaca Benro Polaris Driver v2.2.0
  - [ ] Release Notes: Refer to https://github.com/ogecko/alpaca-benro-polaris/blob/releases/2_2_0/docs/release-notes-v2.2.0.md
  - [ ] Set as latest release
- [ ] Announce on Kickstarter, Facebook, Discord
- [ ] Create new Dev Branch - dev2_3 based on dev2_2

# Alpaca Driver v2.2 Development Todo List
- [X] RPi - Update setup.sh for Raspberry Pi to use UV rather than pip and refresh to latset trixy distro
- [ ] Win - Create setup.bat for Windows and move to UV
- [ ] CCDCiel - Confirm Rotator Sync works correctly on CCDCiel
- [ ] Close candidate enhancement list
    - [ ] Manual Align - Direct Control and List of targets
    - [ ] Goto - Determine ideal settle time for Benro Polaris and v2.2
    - [ ] CCDCiel - Auto install Alpaca Driver scripts for CCDCiel
    - [ ] CCDCiel - Test session using CCDCiel and document Pano, Sync Guiding
- [ ] Close open questions
    - [ ] Flip - Can we improve horizon flip/windup prevention at Az 30 or Az 0?
    - [ ] PEC - Can we identify Guiding Application Calibration pulses so PEC can ignore them?
    - [ ] Sync Guiding - Check whether immediate pulse guide return is cause of bad subexposure. ie detail till converged.
    - [ ] Connection - why does changing IP address allow connection to proceed?
- [ ] Create youtube videos for v2.2 content
    - [X] Create video on Win11 install and connect
    - [X] Create video on dashboard and motion changes
    - [X] Create video on Galactric Panorama Workflow
    - [X] Create video on improving pointing, tracking, guiding performance
    - [X] Create video on Pi install and connect
    - [ ] Create video on CCDCiel

# Candidate minor enhancements for the Catalog
- [ ] Ability to switch catalogs from settings
- [ ] Add images of each catalog target and add a details page for each target
- [ ] Fix J2000 co-ordinate display of 60" for Running chicken RA: +11ʰ38ᵐ60.0ˢ   |   Dec: -63°11′60.0″ 

<br>
<br>

# Future Development Exploration
## 1. Plate-Solving on the Raspberry Pi Zero 2W

**Goal:** Retrieve an image directly from the Benro Polaris's own camera (over the existing BLE/Wifi protocol already used for FILE/STORAGE queries in `polaris.py`), plate-solve it locally on the Pi Zero 2W, and feed the result into the Driver's existing "Plate Solved/ASCOM" sync/correction pipeline in `control.py` (see `driver/control.py:1873`). End state: on-demand and periodic plate-solve/sync entirely on-Pi, no laptop, NINA, or ASTAP required for basic pointing refinement.

**Benefits:** Accurate GOTO centering and drift-free tracking straight out of the Polaris itself — no laptop, NINA, or ASTAP required for a fully self-contained rig.

### Phase 0 — Risk Reduction Prototypes
- Image retrieval: extend the existing FILE (`771`) / STORAGE (`775`) handling in `polaris.py` (currently only logged, not downloaded) into an actual file transfer. Prototype standalone, measure latency and resolution of a still pulled from the Polaris.
- Solve engine choice: evaluate tetra3 (Apache-2.0, pure Python) vs cedar-solve/cedar-detect (faster, but cedar-detect is FSL-licensed) against our licensing/distribution needs. Decide before deeper integration.
- Solve database: build a star-pattern database sized to typical cameras used with the Polaris. (one-time generation step). Confirm database file size and solve accuracy on real sample images, not synthetic ones. Explore whether ASTAP databases could be used.
- On-device performance: run centroid-extraction + solve as a standalone script directly on a Pi Zero 2W (not a dev machine) to get real timing/memory numbers. Target: comparable to or better than cedar-solve's published ~200ms Pi Zero 2 benchmark.
- Concurrency check: run the solve prototype alongside the live `polaris-driver` service and confirm combined memory stays within the Pi Zero 2W's ~416MB usable budget (see the `top` benchmark already in `docs/raspberrypi.md`).

### Phase 1 — Standalone CLI Prototype
Build a one-off utility (alongside existing scripts in `utility/`) that: fetches the most recent Polaris JPG, extracts star centroids, plate-solves, and prints RA/Dec/rotation. Compare against the Driver's own QUEST-modeled pointing for the same moment. No Driver integration yet — this phase only proves the algorithm and timing on real hardware.

### Phase 2 — Driver Integration (On-Demand)
Wire the standalone solver into the Driver process. Add a way to trigger a solve on demand (e.g. an Alpaca Pilot "Solve Now" button or a small REST endpoint) that fetches an image, solves it, and feeds the result into the same code path `control.py` already uses for external Plate-Solve/Sync requests — so the rest of the QUEST/PEC pipeline needs no changes.

### Phase 3 — Closed-Loop Automation
Replace the manual "Solve and Sync every 2–5 minutes" NINA workflow (see `docs/guiding.md` Approach 1) with a Driver-internal periodic solve loop, so hardware-free drift correction works even with no client software connected at all.

### Phase 4 — Hardening & Docs
Field-test across a full session, handle solve failures (clouds, filters, poor focus) gracefully without disturbing tracking/PEC, then document setup and expected performance in `docs/`.

## 2. Alpaca Camera Support for the Driver

**Goal:** Expose the Benro Polaris's own onboard camera as a standard ASCOM Alpaca `ICameraV3` device within the Driver, alongside the existing Telescope/Rotator devices — driven by the currently-unused camera protocol already visible in `polaris.py` (the `_polaris_mode` mode switch — Photo/Pano/Timelapse/HDR/Astro/Video — and the FILE (`771`)/STORAGE (`775`) responses). This gives any Alpaca-aware client (NINA, CCDciel) a standard way to capture/download images straight from the Polaris without its native app, and gives the Plate-Solving goal above a real image source instead of ad-hoc retrieval.

**Benefits:** No USB tether cable to the camera. Capture wirelessly straight from the Polaris through a standard Alpaca camera, usable by NINA/CCDciel and by our own Alpaca Pilot.

### Phase 0 — Risk Reduction Prototypes
- Reverse-engineer/confirm the full capture sequence (mode switch → trigger exposure → poll for FILE ready → retrieve) standalone, outside the Alpaca layer.
- Determine how much exposure control the protocol actually exposes (duration, ISO/gain) versus what's fixed by the Polaris app's own settings — this bounds how much of `ICameraV3` can realistically be implemented.
- Measure image transfer size/latency against Alpaca's expected `ImageReady`-polling timing model, and confirm it's workable on the Pi Zero 2W's storage/memory.
- Assess whether the "Video" mode can back a lightweight preview/live-view capability distinct from full-resolution stills.

### Phase 1 — Minimal Read-Only Camera Device
Implement the bare-minimum `ICameraV3` surface (Connected, CameraState, StartExposure via the existing mode/trigger sequence, ImageReady, ImageArray) — enough to pass ConformU and complete a basic NINA/CCDciel connection test.

### Phase 2 — Exposure Controls & Metadata
Add Gain/ISO and exposure-duration controls where the protocol supports them, plus correct image metadata (bit depth, Bayer pattern if RAW) so downstream apps display/debayer correctly.

### Phase 3 — Converge with Plate-Solving Goal
Swap the ad-hoc image retrieval in the Plate-Solving goal's Phase 1 prototype over to this Camera device's exposure/`ImageArray` path, so the two goals share one retrieval implementation instead of duplicating it.

### Phase 4 — Live View / Streaming (Stretch)
Investigate whether the protocol's video-streaming mode can back a lightweight live-view or MJPEG-style framing feed.

### Phase 5 — Docs & ConformU Validation
Add Camera ConformU checks alongside the existing Telescope/Rotator checks already run in the `# General Final Release Checklist`, and document supported features/limitations.

## 3. PHD2 on the Raspberry Pi Zero 2W

**Goal:** Run PHD2 itself on the Pi Zero 2W, using a USB-attached guide scope/camera for pulse-guiding, and have it drive the Driver's existing ASCOM Alpaca `ITelescopeV3.PulseGuide` interface — eliminating the Windows/Mac Mini-PC currently required for the "Pulse Guiding" workflow in `docs/guiding.md`. The main imaging camera stays on the existing Polaris/Alpaca path; only the guiding loop moves onto the Pi.

**Benefits:** No laptop or Mini-PC needed for autoguiding — a smaller, cheaper, fully self-contained rig with the same long-exposure tracking benefits guiding already provides.

### Phase 0 — Risk Reduction Prototypes
- Build PHD2 from source for our actual Debian Trixie arm64 image and confirm it runs at all (compiling on-device may be too slow/memory-heavy for the Zero 2W — test whether cross-compiling on a Pi 4 or dev machine is needed instead).
- USB power budget: the Zero 2W's single micro-USB OTG port already carries the TPLink Wifi adapter (per `docs/raspberrypi.md`). Prototype a *powered* USB hub carrying both the Wifi adapter and a guide camera; watch `dmesg`/`lsusb` for brownout disconnects under sustained use.
- Guide camera capture: validate the specific guide camera model captures reliably on this OS/arch (native SDK or INDI driver) completely independent of PHD2 first.
- Mount bridge: PHD2 on Linux has no ASCOM (Windows-only) and no native Alpaca chooser — it expects INDI for mount control. Prototype a minimal INDI "telescope" device that only implements guide-pulse properties (`TELESCOPE_TIMED_GUIDE_NS/WE`) and forwards them to the Driver's existing Alpaca `PulseGuide` endpoint. Validate with a generic INDI test client before involving PHD2.
- Headless operation: confirm PHD2 runs under Xvfb on the Lite (no-desktop) OS image, remains reachable over its Server API (TCP 4400), and can be viewed/controlled remotely via VNC for the one-time setup steps.

### Phase 1 — Guide Camera Standalone on the Pi
Get PHD2 + the guide camera looping exposures on the Pi with no mount connected yet. Validate exposure timing and image quality over VNC, matching the manual focus/rotate/align workflow in `docs/guiding.md` §3.2.

### Phase 2 — INDI↔Alpaca Bridge in Isolation
Validate the bridge alone: send synthetic guide pulses through it and confirm the Driver's PID loop reacts the same way it does today via the Windows/ASCOM path. No PHD2 involved yet — isolates bridge correctness from PHD2/camera behavior.

### Phase 3 — End-to-End Pulse Guiding on the Pi
Connect PHD2 → bridge → Driver end-to-end on the Pi. Perform calibration per the existing `docs/guiding.md` §4 workflow via VNC (one-time), then validate guiding accuracy against the documented baseline (~1.5–3.0 arcsec RMS).

### Phase 4 — Headless Field Operation
Package the bridge (and Xvfb) as systemd services alongside `polaris-driver.service`, so a normal session needs VNC only for the one-off setup/calibration steps, not for ongoing guiding. Test an unattended multi-hour session.

### Phase 5 — Docs & Hardware Guidance
Document the required powered USB hub, tested guide camera models, and setup workflow in `docs/hardware.md` / `docs/guiding.md` / `docs/raspberrypi.md`.

## 4. INDI Support for the Driver

**Goal:** Expose the Driver's existing Telescope/Rotator (and, once far enough along, Camera) control as a proper INDI device, so the broader Linux astronomy ecosystem (KStars/Ekos, INDI-based CCDciel, PHD2-on-Linux) can drive the Benro Polaris the same way Windows users do today via ASCOM/Alpaca — one reusable driver instead of a bespoke bridge per INDI client. This generalizes (and can share prototype work with) the narrow guide-pulse-only INDI bridge sketched under the PHD2 goal above.

**Benefits:** Opens the Benro Polaris up to the whole Linux/KStars-Ekos astronomy community, not just Windows/NINA users, with no per-app bridge required.

### Phase 0 — Risk Reduction Prototypes
- Survey INDI driver implementation options (native C++ vs a Python INDI framework) and pick one that sits naturally alongside the Driver's existing asyncio Python codebase, confirming it's mature/performant enough for real-time pulse-guide timing.
- Prototype the narrowest possible INDI device — telescope, slew + guide-pulse only — forwarding to the Driver's existing Alpaca endpoints, and validate it against a real INDI client (`indi_getprops`, a minimal Ekos profile). This prototype can double directly as the PHD2 goal's Phase 0 mount bridge rather than being built twice.
- Check how cleanly INDI's coordinate/site-location property model maps onto the Driver's existing topocentric/QUEST model in `control.py`, particularly around the Alt/Az-vs-RA/Dec rotation limitation already noted in `docs/nina.md`.
- Confirm licensing/packaging implications of depending on INDI's core libraries.

### Phase 1 — Minimal INDI Telescope Device
Connect/Disconnect, GOTO (RA/Dec), Sync, Abort, Tracking on/off, Pulse-Guide — enough for PHD2-on-Linux and basic Ekos slewing end-to-end.

### Phase 2 — Rotator & Richer Telescope Properties
Add the Rotator device plus park/unpark, site location, and slew-rate properties to match today's Alpaca feature set.

### Phase 3 — Camera Device
Once the Alpaca Camera Support goal above is far enough along, expose the same capability as an INDI Camera device so KStars/Ekos can capture, not just point.

### Phase 4 — Packaging & Docs
Package as a systemd service alongside `polaris-driver.service`, and write INDI/Ekos setup docs mirroring today's `docs/nina.md` / `docs/ccdciel.md`.

### Phase 5 — Compliance Validation
Validate against INDI's own driver compliance/test tooling (the INDI analogue of ConformU) and add to the release checklist.
