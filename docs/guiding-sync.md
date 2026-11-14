# Sync Guiding
[Choosing an Approach](#choosing-an-approach) ·
[How It Works](#how-sync-guiding-works) ·
[Periodic Error Correction](#periodic-error-correction) ·
[Sync Guiding with NINA](#sync-guiding-with-nina) ·
[Sync Guiding with CCDciel](#sync-guiding-with-ccdciel)

Guiding corrects the tracking errors that remain after alignment. Multi-Point Alignment gives the Benro Polaris an accurate pointing model, but periodic error and other mechanical errors still make the target drift. The Polaris's periodic error is over 14 arc minutes, on a repeating 35-minute cycle, so without guiding, long exposures at long focal lengths show drift and trailed stars.

## Choosing an Approach

The Alpaca Driver supports two approaches to guiding:

* **Sync Guiding** needs no extra hardware. Your imaging software plate-solves an image from your main camera every 1 to 3 minutes and syncs the result, and the driver corrects the drift. It's the easiest way to start, and it suits sub-exposures of up to a few minutes.
* **[Pulse Guiding](./guiding-pulse.md)** uses a small guide scope and guide camera with PHD2, which corrects the mount every few seconds, within each exposure. It suits the longest focal lengths and exposures, up to about 300 seconds.

![Sync guiding or pulse guiding](images/phd2-choice.png)

Use one approach or the other, not both. Running them together makes them fight: the guider holds its guide star at the lock position it set when guiding started, so it pulls each sync correction straight back. To keep the target centred during a long pulse-guided session, use NINA's **Center After Drift** trigger instead.

## How Sync Guiding Works

Normally a plate-solve sync adds a new point to the Multi-Point Alignment model. With **Sync Guiding (Plate-solve)** switched on in Alpaca Pilot's settings, a sync taken **without slewing** is treated differently: the driver uses the small difference between where the mount thought it was pointing and where the plate solve says it is pointing as a guiding correction, and moves the mount back onto the target.

* **No extra hardware:** No guide scope or guide camera to buy, mount, power or cable up.
* **Accurate:** A full-frame plate solve measures the pointing far more precisely than a single guide star.
* **Hands-free:** The corrections happen during your normal imaging sequence, without stopping to re-centre.

Each correction also feeds Periodic Error Correction, which learns how the mount is drifting and corrects it continuously between syncs.

## Periodic Error Correction

Periodic Error Correction (PEC) predicts the Polaris's tracking errors and corrects them before they show in your images. Switch on its two parts in Alpaca Pilot's settings:

* **PEC Drift Correction** learns the slow drift from your guiding corrections, whether from sync guiding or pulse guiding.
* **PEC Worm Gear Correction** cancels the wobble from each motor's worm gear, with or without guiding. It needs a [Worm Gear Calibration](./initial-setup.md#worm-gear-calibration) first.

The **PEC** button on Alpaca Pilot's status panel switches both on and off together. For how PEC works, see [Periodic Error Correction](./kinematics.md#periodic-error-correction) in the Kinematics Reference.

## Sync Guiding with NINA

1. **Switch on the features.** In Alpaca Pilot's settings, switch on **Multi-Point Alignment**, **Sync Guiding (Plate-solve)** and **PEC Drift Correction** (and **PEC Worm Gear Correction**, once you have a worm gear profile).
2. **Align the mount.** Reset any old Multi-Point Alignment, turn on tracking, and capture at least three sync points: ideally at your celestial pole, and along the path your target will take (see [Multi-Point Alignment](./initial-setup.md#multi-point-alignment)).
3. **Centre the target.** Use NINA's **Slew and Center** to put your target in the middle of the frame. The first sync after a goto adds an alignment point and starts sync guiding; the following syncs are used as guiding corrections.
4. **Start the PEC model (optional).** On NINA's Imaging tab, run a few manual plate solves about 30 seconds apart. This helps PEC learn the drift sooner.
5. **Build the sequence.** In NINA's Advanced Sequencer, create a loop that takes your light frames with a **Smart Exposure**, then runs a **Solve and Sync**, so that a sync happens every 1 to 3 minutes. For example, with 30 s sub-exposures, take 4 frames between each sync.
6. **Start the sequence**, and watch the first few syncs. In Alpaca Pilot, the **Sync Guiding** and **Periodic Error Correction** rows of the status panel show the corrections arriving.

## Sync Guiding with CCDciel
CCDciel can also sync guide, using the Alpaca Driver's `PolarisSyncGuide` script:

* In Alpaca Pilot, enable **Multi-Point Alignment** and **Sync Guiding (Plate-solve)**.
* Install the Alpaca Driver's CCDciel scripts (see [Alpaca Driver Scripts](./ccdciel.md#alpaca-driver-scripts)), then add a `PolarisSyncGuide` step to your plan after the light frames, so it runs every 1 to 3 minutes of imaging. It solves the image just taken (no extra exposure) with CCDciel's `Astrometry_sync` command.
* After a goto, the first sync adds an alignment point and turns sync guiding on; the following syncs are used as guiding corrections (if within 3 degrees).
* After a sync the driver moves the mount back onto its target, so the script waits a few seconds (the settle argument) before the next exposure.
* Sync guiding with CCDciel is new: please report how it works for you.
* Don't combine sync guiding with pulse guiding: the guider pulls each sync correction straight back to its lock position.
