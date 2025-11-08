[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./Pilot.md) | [Control](./Control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Advanced Motion Control
[Challenges](#challenges-with-existing-control) | [Rotator](#alpaca-rotator) | [Alignment](#polar-alignment) | [Safety](#equipment-safety) | [Filtering](#kalman-filter) | [Speed Controller](#speed-controller) | [PID Controller](#pid-controller) | [Guiding](#pulse-guiding) | [Tracking](#tracking) 

## Challenges with existing Control
PODCAST LINK - [20 - Deep Dive Podcast on Alpaca Benro Polaris V2.0](https://youtu.be/KUBCTnEsnlE)

The Benro Polaris mount, especially with its Astro Attachment, is popular among amateur astrophotographers for its compact design and app-driven interface. But while the hardware is excellent, the software can leave many users frustrated.

When version 1.0 of the Alpaca Driver was launched, it allowed advanced imaging and planetarium software to work with the Polaris. As more people used these applications, limitations quickly surfaced:
- Tracking drift was noticeable during long imaging sessions
- Promised features like three-star alignment never materialized
- Users lacked the precision tools needed for serious deep sky work

With version 2.0 of the Alpaca Driver, we introduce a complete rewrite of the motion control system. The motors are now driven using advanced algorithms that dramatically improve tracking accuracy, responsiveness, and stability.

This guide covers describes each of the new motion control concepts introduced in V2.0

## Alpaca Rotator
VIDEO DEMO - [23 - Alpaca Rotator Framing in Nina and Stellarium](https://youtu.be/_Swd-jIyQis)

The Driver now supports the ASCOM Alpaca Rotator Interface v3, unlocking the third axis of the Polaris to control the camera’s Position Angle relative to the celestial sky. This helps Nina to correctly frame image capture of single targets, as well as compose multi-panel panoramas of expansive deep sky objects.

It also enables rotation around the camera’s boresight while maintaining Az/Alt or RA/Dec coordinates. We’ve improved GOTO commands to preserve roll angle, unlike the stock Polaris firmware, which always resets the roll to zero after every GOTO.


**Roll Angle** - Describes how your camera is rotated relative to the local horizon. A Roll Angle of 0 means that the camera is perfectly level with the horizon. A positive roll (e.g. +30°) means the camera is rotated counterclockwise when viewed from behind the scope, the image rotates clockwise. A negative roll (e.g. –30°) means the camera is rotated clockwise, the image rotates counterclockwise. It ranges from -180 to +180 but is constrained by the Benro Polaris to a much smaller range.

***Parallactic Angle*** - Describes how the sky is rotated at the point you're imaging, based on your location and the time of observation, independent of your cameras rotation. It’s the angle between celestial North and straight up (the zenith) at the target’s position. For example, if you're imaging directly above the South Pole, the parallactic angle is 0°, celestial North aligns with zenith. It ranges from -180 to +180.

***Position Angle*** - Describes how your camera is rotated relative to celestrial North as projected onto the sky.  It ranges from 0 to 360 degrees. A position angle of 0 means the top of your image points towards celestrial North, 90 means top points towards celestrial East, 180 Celestrial South, and 270 Celestrial West. This is the standard used in the ASCOM RotatorV3 interface, and is useed in plate solving, mosaics, and image alignment.

## Polar Alignment
VIDEO DEMO - [24 - Multi Point Alignment and Tripod Tilt](https://youtu.be/4CMO0R_yphw)

Version 2.0 of the driver supports two polar alignment methods: **Single-Point Alignment** and **Multi-Point Alignment**. With Multi-Point Alignment, you no longer need to obsess over leveling your tripod. The model detects and corrects tilt. So you can even purposefully tilt the mount to image the 18° zenith circle.


### Single-Point Alignment
This method uses the standard Benro Polaris alignment technique, exposed as a SYNC function for Alpaca clients. It enables clients to adjust the Polaris mount so its current pointing direction matches a known celestial position.

The key advantage is that alignment corrections are applied directly within the Benro Polaris, benefiting all connected clients. However, this method depends heavily on precise tripod leveling and is susceptible to drift and tracking inconsistencies.


### Multi-Point Alignment
Multi-Point Alignment also uses the SYNC function, but builds a correction model from three or more known positions. This model compensates for tripod tilt, polar misalignment, cone error, and other mechanical offsets that can affect pointing and tracking accuracy.

The algorithm is adapted from techniques used in NASA satellite launches. It’s efficient, closed-form, and quaternion-based, delivering high-precision polar alignment. The Alpaca Pilot App lets you monitor the model’s development in real time. You can evaluate how well it fits the collected SYNC points, and optionally remove outliers to refine its accuracy.

### Adding SYNC Points
You can add SYNC points using several methods, all compatible with both alignment modes. For Multi-Point Alignment, adding more points spread across the sky improves model precision. Methods to add SYNC points include:

* **NINA’s Plate-Solve + Sync**. 
Initiate a plate-solve and sync manually from the Image tab, at the start of an imaging schedule, or as a scheduled step.

* **Stellarium’s Sync Feature**. 
Center a star or DSO in the camera frame, select it in Stellarium, and click the SYNC button in the Telescope Control dialog.

* **Alpaca Pilot’s Celestial Sync**.
Similar to Stellarium: align the camera to a known celestial position and sync with the known RA/Dec coordinates.

* **Alpaca Pilot’s Geographic Sync**.
Ideal for daytime alignment. Point the camera at a known horizon landmark, then click its location on the map. The app calculates its elevation and derives Azimuth/Altitude coordinates relative to your observing site.

* **Alpaca Pilot’s Manual Sync**. Manually enter the true current pointing direction of the mount as RA/Dec or Az/Alt co-ordinates.

## Equipment Safety

VIDEO DEMO - [25 - Home, Park and Motor Angle Limits](https://youtu.be/45EP-DExSOQ)

## Kalman Filter
VIDEO DEMO - [31 - Setting Overrides, Kalman Filtering and PWM](https://youtu.be/aDFKAWBNQHU)

## Speed Controller
VIDEO DEMO - [32 = Calibrating Speed Control for your Polaris](https://youtu.be/U_0-mBDuTjE)


## PID Controller

## Pulse Guiding

## Tracking


