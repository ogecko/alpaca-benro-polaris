[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# General Final Release Checklist
- [ ] Check Driver package vulnerabilities
  - [ ] uv audit
  - [ ] uv pip list
  - [ ] uv pip show urllib3
  - [ ] uv tree --invert --package urllib3 
  - [ ] uv tree --group notebooks               # see pyproject.toml [dependency-groups]
  - [ ] uv add "urllib3==2.7.0" 
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
- [ ] Explore whether sky position drifts with given raw motor angle orientation over a long session. Does sync history need time/drift correction

<br>
<br>

# Future Development Exploration

## 1. Plate-Solving on the Raspberry Pi Zero 2W

**Goal:** Retrieve an image directly from the Benro Polaris's own camera (over the existing BLE/Wifi protocol already used for FILE/STORAGE queries in `polaris.py`), plate-solve it locally on the Pi Zero 2W, and feed the result into the Driver's existing "Plate Solved/ASCOM" sync/correction pipeline in `control.py` (see `driver/control.py:1873`). End state: on-demand and periodic plate-solve/sync entirely on-Pi, no laptop, NINA, or ASTAP required for basic pointing refinement.

**Benefits:** Accurate GOTO centering and drift-free tracking straight out of the Polaris itself — no laptop, NINA, or ASTAP required for a fully self-contained rig.

### Phase 0 — Risk Reduction Prototypes
- Image retrieval: extend the existing FILE (`771`) / STORAGE (`775`) handling in `polaris.py` (currently only logged, not downloaded) into an actual file transfer. Prototype standalone, measure latency and resolution of a still pulled from the Polaris.
- Solve engine choice: evaluate tetra3 (Apache-2.0, pure Python) vs cedar-solve/cedar-detect (faster, but cedar-detect is FSL-licensed) against our licensing/distribution needs. Also weigh a portable core (e.g. Rust, compiled to native arm64 for the Pi and to WASM for the browser) so the same solver can run in Alpaca Pilot. See item 6, Plate-Solving Synergy. Decide before deeper integration.
- Solve database: build a star-pattern database sized to typical cameras used with the Polaris (a one-time generation step). Generate it from the same merged Gaia/Hipparcos/Pilot star catalog as the item 6 Sky Map, so the map and the solver share one reference catalog. Confirm database file size and solve accuracy on real sample images, not synthetic ones. Explore whether ASTAP databases could be used.
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


## 5. Extend Driver to support non-Polaris mounts

**Goal:** Refactor the driver architecture to support multi-protocol mount communication, moving beyond the current Polaris-only implementation.

The initial phase will focus on implementing the extended Meade LX200 protocol over USB, Bluetooth, and Wi-Fi. This will establish native support for the SAL-33 (an OnStepX-based harmonic mount). As part of this refactor, the closed-source OnStepX ASCOM driver will be replaced with a pure, cross-platform Alpaca driver.

**Benefits:** Universal Mount Compatibility. Enables Alpaca Pilot to control a broad range of mounts that support the extended LX200-compatible harmonic mounts (e.g., SAL-33, WD-20E, FG-17, AM5N, and others). 

## 6. Sky Map

**Goal:** A GPU-rendered, star-accurate sky map inside Alpaca Pilot that serves as the common visual backdrop for the Atlas / Live / Replay views sketched in item 7. It shows the sky exactly as the mount and camera see it: current pointing, target pointing, the camera frame rolled to its true orientation, and live or captured images laid on top of a real star field. The view moves smoothly and with momentum in whichever Pilot reference frame is active (Topocentric, Equatorial or Galactic).

**Benefits:** Framing, target selection and checking pointing all happen in one place, with no Stellarium or NINA framing assistant needed. A captured image can be checked against the real sky straight away, and the map gives the Plate-Solving (item 1) and Camera (item 2) goals somewhere to show their results.

### Requirements

**Data**
- Star catalog complete to about **mag 11**, with a real colour for each star. Built by merging the existing Pilot catalog (named stars, `C1 = 3`) with Gaia DR3. Gaia supplies faint-star completeness and BP–RP colour. Pilot, Hipparcos or the Yale BSC supply the brightest stars (Gaia saturates or leaves gaps below about G ≈ 3) and common names.
- The star field is fixed in the equatorial (ICRS/J2000) frame. Stars never move in the data. Only the view changes.
- DSOs come from the existing Pilot catalog (`catalog_*.json`: position, size `Sz`, type `C1`/`C2`, rating `Rt`), so the map and the Catalog page always agree.
- Constellation stick figures and IAU constellation boundaries.
- The star data is also the reference catalog for plate-solving (item 1): one build pipeline and one source of truth for both drawing and solving.

**Plate-Solving**
- Solve an image in the browser while it is being viewed (Replay, captured images, Live Preview), so it is placed on the map by its real position without loading the Pi.
- The same solver and database also run on the Pi for item 1's closed-loop sync when no client is connected.
- Positions are correct for the date shown (precession/nutation, proper motion to epoch). For Replay, that is the image's capture time.

**View / Camera**
- The view is fully set by **orientation + field of view**. It can be driven by the user, the mount, or an animation.
- Direct control of Zoom (FOV), plus the three axes of the active Pilot reference frame (`ui.coordFrame`):
  - Topocentric: Az / Alt / Roll
  - Equatorial: RA / Dec / PA
  - Galactic: l / b / GPA
- Pointer, touch (pinch/rotate) and keyboard input go through the existing `useKeyMap` / `useActionRegistry`.
- Motion has momentum and inertia (fling, then glide to a stop) and stays smooth at 60 fps. It should feel at least as good as color-sense, but built on a modern, frame-rate-independent approach.
- Animated transitions to: current mount pointing, target pointing, a captured image's centre/PA/FOV, and a selected object centred on screen. Transitions take the shortest rotation and zoom out and back in over long distances.
- Optional follow modes: lock to mount pointing, lock to target, or free.
- Zoom range: from a whole-sky view (≥ 120° FOV) down to about a 0.5° camera field without visible distortion or loss of precision.

**Overlays** (each can be switched on/off; drawn in this order)
1. Live Preview: the current camera frame, placed and rotated on the sky.
2. Captured Image(s): past frames placed by their plate-solve (or by mount pointing if unsolved).
3. Stars: colour from BP–RP; brightness and size from magnitude through a realistic PSF (e.g. Moffat) that matches camera seeing and pixel scale when zoomed in.
4. Constellation lines (and optionally boundaries).
5. DSOs: markers or ellipses scaled to `Sz`, styled by type.
6. Target reticle and Current Mount reticle: the camera sensor rectangle (from sensor size and focal length) rolled to the mount/rotator orientation.
7. Grids: Topocentric (Alt/Az with horizon), Equatorial (RA/Dec) and Galactic (l/b), each labelled.
8. Labels: the top N stars, constellations and DSOs in view, ranked by brightness or rating, with no overlapping labels.
- Tap or click selects the nearest object, which opens its details and allows Goto / Target / Centre.

**Non-functional**
- Runs on the devices people use for Pilot (Windows/Mac browsers, iPad, Android tablets and phones) at 60 fps.
- The Pi Zero 2W only serves static files. All computation happens in the browser.
- The first view loads fast: bright stars appear immediately. Fainter stars stream in for the region in view first, then the surroundings, then along the direction of motion.

### Potential Architecture

**Rendering engine**
- Use three.js `WebGPURenderer` with TSL shaders. It falls back to WebGL2 automatically, which covers older iOS and Firefox devices. Use your own shaders and your own camera controller rather than `OrbitControls` or the built-in perspective projection. Raw WebGPU is the alternative if three.js gets in the way, but you lose the fallback.
- Custom projection in the vertex shader: gnomonic at narrow FOV (matches camera images exactly), stereographic at wide FOV (a plain perspective camera breaks down past about 120°), blended between the two.
- The vertex shader does all per-star work. Star vectors are never rotated on the CPU. Each frame the CPU composes **one** 3×3 matrix and uploads it as a uniform, working in float64 because the angles involved (LST, precession) are large:
  - precession/nutation (J2000 → date)
  - the frame rotation (topocentric/galactic)
  - `q_view`
- Proper motion is baked in at build time.
- Annual aberration (up to about 20″) is not a rotation. The shader applies it cheaply per star as `normalize(v + β)`, with `β` (Earth velocity / c) passed as a uniform.
- Precision: float32 on the GPU is fine. Near 1.0 it resolves about 0.025″, while a 0.5° FOV on a 2000 px canvas is about 0.9″/px. The real limit is how compactly stars are *stored* (see tile-relative encoding below), not the rotation.

**Star data pipeline (build time, in `utility/`)**
- A Python script queries Gaia DR3 (`G < 11`) over TAP and cross-matches Hipparcos via `hipparcos2_best_neighbour`. It adds bright stars from Pilot, Hipparcos or BSC, propagates proper motion to about J2026, and converts BP–RP to Teff and then to linear sRGB.
- Output is HEALPix binary tiles (e.g. nside 16–32, about 3.7°–1.8° per tile), layered by magnitude (≤ 6 all-sky, then 6–8, 8–10, 10–11 per tile).
- Tile-relative encoding: each star is stored as int16 (u, v) offsets in its tile's tangent plane, about 0.1–0.2″ resolution, plus a uint8 magnitude and a uint8 colour index, for 6 bytes per star. The tile centre is a per-tile uniform or a storage-buffer entry, and the shader rebuilds the unit vector. Avoid 2×16-bit oct-encoding of the whole sphere: it resolves only about 10″, which is visible at a 0.5° FOV.
- About 1–1.5M stars comes to roughly 6–10 MB in total, served as static files from `pilot/public/`.

**Streaming (view first)**
- The ≤ 6 mag all-sky layer (about 5k–9k stars, under 60 KB) loads first, so the map is never empty.
- Deeper layers load per tile, only for tiles that intersect the view (a cheap CPU test over a few thousand tiles). The magnitude limit rises as FOV shrinks, and for each tile brighter layers load before fainter ones.
- Load order: nearest the view centre first, then a margin ring, then tiles ahead of the current angular velocity.
- Transitions: at the start of an animated move, prefetch the destination tiles. The flight time hides the download.
- On the GPU, tiles are sub-allocated into one large storage-buffer pool with LRU eviction. Stars are drawn with one instanced (or indirect) draw per visible tile-layer, and tiles outside the view are culled on the CPU before drawing.
- The hinted plate-solver reads the same loaded tiles.

**Stars in the shader**
- Each star is an instanced quad, since hardware points are limited to 1 px in WebGPU. Quad size comes from magnitude and FOV.
- The fragment shader draws a Moffat or Gaussian profile with flux ∝ 10^(-0.4·m), accumulated additively into an HDR (float16) target and then tone-mapped. This conserves energy, so bright stars bloom naturally and faint ones fade in smoothly as you zoom. PSF FWHM is taken from the current camera pixel scale and seeing, so the map looks like the real image.

**View model and controls**
- The single source of truth is a quaternion `q_view` (ICRS → camera) plus `fov`. Frame-specific controls are applied in the active frame and converted back:
  - Equatorial is the identity frame.
  - Galactic uses a fixed rotation matrix.
  - Topocentric uses a matrix that changes with time (LST + site latitude, from `status`/`config`). This is why the view recomputes every frame while the star buffer never changes.
- Roll/PA/GPA is measured from the active frame's "up" (zenith, NCP, NGP). Az/Alt, RA/Dec, l/b and roll are always derived from `q_view` for display, never stored separately, which avoids gimbal lock at the poles and zenith.
- Motion comes from critically-damped springs on angular velocity and log(fov), stepped by `requestAnimationFrame` with real dt. On release, pointer velocity (smoothed over the last ~100 ms) becomes angular momentum with exponential decay. Honour `prefers-reduced-motion`.
- Transitions: slerp the orientation while zoom follows a smooth zoom-and-pan path (van Wijk & Nuij), so long moves zoom out, travel, then zoom back in. Duration scales with angular distance. Any user input interrupts an animation and carries its velocity into free motion.

**Overlays**
- Grids: a procedural full-screen fragment pass that works out each pixel's coordinates in the chosen frame and draws anti-aliased lines, with line spacing adapting to FOV. This is cheap and needs no geometry.
- Constellations: HIP-indexed line pairs (e.g. Stellarium's modern sky culture; check the licence) resolved against the star buffer at build time, drawn as instanced screen-space-width line segments. Boundaries come from the IAU/Davenport vertex list.
- Images: a quad per image, defined by its WCS (centre, PA, pixel scale, size). The fragment shader un-projects gnomonically, so an image lines up exactly with the stars at any view projection. Live Preview is the same thing with a streaming texture.
- Reticles: the sensor rectangle as four great-circle arcs about the pointing, rolled by PA or rotator angle, with a crosshair. Blue for current and red for target, matching the colours in item 7.
- Labels and picking: done on the CPU with a HEALPix spatial index over bright stars, DSOs and constellation centroids. Each frame, cull to the view, rank, take the top N and do greedy collision layout. Draw into a DOM or Canvas2D layer positioned from the projected coordinates. With a few dozen labels, this is simpler and sharper than SDF text on the GPU. Picking uses the same index (nearest in angle), so no GPU picking pass is needed.

**Plate-Solving Synergy**
- **Hinted solving first.** We nearly always know the rough pointing (mount/QUEST model, typically within a degree or so), the pixel scale and the roll (camera config and rotator). That turns solving into local matching:
  1. Take catalog stars from the HEALPix tiles around the hint. The Sky Map has usually loaded these already.
  2. Project them gnomonically at the known scale.
  3. Match them to detected centroids with triangle/quad hashing and a small search over roll and offset.
  4. Least-squares fit a WCS (centre, PA, scale, optional SIP distortion), then verify.

  This needs only the render catalog, not a pattern database. It is fast in plain TS/WASM and on the Pi.
- **Blind fallback.** When there is no hint, or the hint is wrong (after a sync failure or an unknown image), fall back to a tetra3-style pattern database built by the same `utility/` pipeline from the same stars. Size it to the FOV range of cameras used with the Polaris. The browser downloads it only when a blind solve is first needed and caches it in Cache Storage/IndexedDB.
- **Star detection** (background estimation, peak finding, centroiding) can run as WebGPU compute in the browser, reusing the Sky Map's GPU device. On the Pi it runs natively (numpy or Rust).
- **One portable core.** To avoid keeping a Python solver and a TS solver in step, write the solver once, e.g. in Rust:
  - Built for arm64 as a Python extension (PyO3) for the Driver.
  - Built as WASM, running in a Web Worker, for Pilot.

  The alternatives are:
  - Pure TS in Pilot, with a Python port on the Pi.
  - tetra3 via Pyodide in the browser (large download, slow start).
- **Solution feeds everything.** A browser solve writes its WCS onto the image record (Replay placement) and can optionally be sent to the Driver as a Sync through the same path as external ASCOM plate-solve syncs (`control.py`). The browser then becomes a solver for item 1 before the on-Pi solver exists.
- **Map as test harness.** The PSF star renderer can generate synthetic frames with known WCS, noise and seeing for solver unit tests. Real-image validation (item 1, Phase 0) still applies.

**Pilot integration**
- `SkyMap.vue` component plus a `skymap` Pinia store holding view state, layer toggles, selection and follow mode.
- Reads `status` (pointing, `siderealtime`, `gpv`), `config` (site, sensor/focal length), `catalog` (DSOs) and `ui.coordFrame`.
- Emits Goto / Target / Sync through the existing device actions.
- Solar-system bodies (item 7's "Orbit") are computed once per frame on the CPU and injected as a small dynamic buffer.

**Out of scope / stretch**
- HiPS or TOAST survey imagery (DSS/Mellinger) as a background layer.
- Atmospheric refraction and extinction.
- Ground/horizon panorama.
- Volumetric DSO rendering.

### Phase 0 — Risk Reduction Prototypes
- Device check: WebGPU vs WebGL2-fallback performance for about 1M instanced stars on the slowest target tablet or phone.
- Data size: build the G < 11 merge once. Measure tile sizes, completeness against Pilot's named stars, and how good the colours are.
- Controller feel: a standalone prototype of the quaternion + spring + momentum controller with transitions, compared side by side against color-sense before any overlays are built.
- Precision: confirm arcsecond placement at 0.5° FOV against a known plate-solved image.
- Hinted solve: a TS/WASM prototype that solves a real Polaris/NINA frame in the browser from the mag ≤ 11 tiles given a 2° pointing hint. Measure time on a phone, and compare its WCS with ASTAP.

### Phase 1 — Star Field + Controller
Tiled star loading, PSF rendering, custom projection, and the full controller in all three reference frames.

### Phase 2 — Pointing Overlays
Grids, current and target reticles, follow modes, and animated transitions to mount/target.

### Phase 3 — Catalog Overlays
Constellations, DSOs, top-N labels, and tap-to-select wired to Goto/Target.

### Phase 4 — Image Overlays
Captured images placed by WCS and Live Preview, solved in the browser by the hinted solver (blind fallback later). Shares the solver core with item 1. Depends on item 2 (camera) for a live source; can use NINA/ASTAP images in the meantime.

### Phase 5 — Dashboard Integration
Embed as the Atlas / Live / Replay backdrop from item 7. Replay renders the sky at the capture time.

### Open Questions
- The draft said "mag -11". This plan assumes the intended faint limit is **+11**, since the brightest star (Sirius) is about −1.5. Confirm, and decide whether 11 is still right on phones given the download size.
- Should the Topocentric view draw a horizon or ground, and apply refraction near the horizon?
- Where does the image WCS come from before the solver lands: mount pointing plus rotator only, or imported solved FITS?
- Is a Rust toolchain acceptable in the build (Pi arm64 wheels plus WASM), or should the solver stay pure TS + Python?
- Is hinted-only solving enough, or is blind solving needed from day one? This decides whether the pattern database is needed early.


## 7. UX Rationalisation
### Connect
### Dashboard
* Multi Camera View               - Main Camera, Guide Camera, Whole Sky Camera, Mount Camera
* Atlas  - (boresight + offsight) - Space Background, Overlay Labels | Stars | Constellations | DSO | Reticle | Grids
* Live   - (current boresight)    - Camera Background, Zoomable, Panable, Atlas Overlay
* Replay - (past boresight)       - Image Background, Zoomable, Panable, Atlas Overlay, Image Stats Overlay

* Modes ? 
  * Preview (quick capture, not saved) 
  * Focus (manual or auto) 
  * Alignment (manual, auto MPA seq) 
  * Atlas (move target red, blue current, search, goto,sync,stop) 
  * Guiding (focus, align w/main, exposure/gain, capture, select guide star, calib, guide start, aggr)
  * Folders (navigate, open, delete, goto solved image RA/Dec/PA)
  * Autorun config (target name, Light|D|B|F, meridian flip, Interval, Repeat, Filter, end sequ, estimated duration, start/pause/stop)
  * Live 
  * Plan 
  * Video 

* Timeline - Guiding History | Star Detection History | Image History | Catalog Search | Focus Run | Alignment Run
* Mount Status - Radial Dials, Control Status
* Capture Status - Progress

* Exposure Control - Shutter, F-stop, ISO/Gain, WB, EV, Bin, Cooler, Filter
* Capture Control- Capture/Sequence, Start, Stop, Loop, Progress 
* Target Control - Catalog, Search, Panel | Sync | Goto | Target
* Mount Control - N | S | W | E | Speed | Track | Home | Park | Stop
* Focus Control - Calibrate | In | Out 
* Guide Control - Calibrate | RA Aggr | Dec Aggr | PEC | MAC 

### Setup
* filename - camera, filter, data, 
