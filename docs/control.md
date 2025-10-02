[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./Pilot.md) | [Control](./Control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Advanced Control
[Launching](#2-launching) | [Connecting](#3-connecting) | [Searching](#4-searching) | [Settings](#5-settiings) | [Tuning](#6-tuning) | [Diagnostics](#7-diagnostics) 

## Control -  Video Demonstration
You can view a demonstration of parts of this documentation in the following YouTube Video.
[![Capturing Images](https://img.youtube.com/vi/HCJNchWL2Yg/0.jpg)](https://www.youtube.com/watch?v=HCJNchWL2Yg)

## 1. Challenges with existing Control

## 2. Kinematics and Co-ordinates

## 3. Rotator
### Definitions
**Roll Angle** - Describes how your camera is rotated relative to the local horizon. A Roll Angle of 0 means that the camera is perfectly level with the horizon. A positive roll (e.g. +30°) means the camera is rotated counterclockwise when viewed from behind the scope, the image rotates clockwise. A negative roll (e.g. –30°) means the camera is rotated clockwise, the image rotates counterclockwise. It ranges from -180 to +180 but is constrained by the Benro Polaris to a much smaller range.

***Parallactic Angle*** - Describes how the sky is rotated at the point you're imaging, based on your location and the time of observation, independent of your cameras rotation. It’s the angle between celestial North and straight up (the zenith) at the target’s position. For example, if you're imaging directly above the South Pole, the parallactic angle is 0°, celestial North aligns with zenith. It ranges from -180 to +180.

***Position Angle*** - Describes how your camera is rotated relative to celestrial North as projected onto the sky.  It ranges from 0 to 360 degrees. A position angle of 0 means the top of your image points towards celestrial North, 90 means top points towards celestrial East, 180 Celestrial South, and 270 Celestrial West. This is the standard used in the ASCOM RotatorV3 interface, and is useed in plate solving, mosaics, and image alignment.




## 4. Motor Speed Control

## 5. Kalman Filtering

## 6. MPC and PID Control

## 7. Tracking

## 8. Pulse Guiding

## 9. Polar Alignment

Version 2.0 of the driver supports two polar alignment methods: **Single-Point Alignment** and **Multi-Point Alignment**.


### Single-Point Alignment
This method uses the standard Benro Polaris alignment technique, exposed as a SYNC function for Alpaca clients. It enables clients to adjust the Polaris mount so its current pointing direction matches a known celestial position.

The key advantage is that alignment corrections are applied directly within the Benro Polaris, benefiting all connected clients. However, this method depends heavily on precise tripod leveling and is susceptible to drift and tracking inconsistencies.


### Multi-Point Alignment
Multi-Point Alignment also uses the SYNC function, but builds a correction model from three or more known positions. This model compensates for tripod tilt, polar misalignment, cone error, and other mechanical offsets that can affect pointing and tracking accuracy.

The algorithm is adapted from techniques used in NASA satellite launches. It’s efficient, closed-form, and quaternion-based, delivering high-precision polar alignment.

The Alpaca Pilot App lets you monitor the model’s development in real time. You can evaluate how well it fits the collected SYNC points, and optionally remove outliers to refine its accuracy.

### Adding SYNC Points
You can add SYNC points using several methods, all compatible with both alignment modes. For Multi-Point Alignment, adding more points improves model precision.

* **NINA’s Plate-Solve + Sync**. 
Initiate a plate-solve and sync manually from the Image tab, at the start of an imaging schedule, or as a scheduled step.

* **Stellarium’s Sync Feature**. 
Center a star or DSO in the camera frame, select it in Stellarium, and click the SYNC button in the Telescope Control dialog.

* **Alpaca Pilot’s Celestial Sync**.
Similar to Stellarium: align the camera to a known celestial position and enter the RA/Dec coordinates manually.

* **Alpaca Pilot’s Geographic Sync**.
Ideal for daytime alignment. Point the camera at a known horizon landmark, then click its location on the map. The app calculates its elevation and derives Azimuth/Altitude coordinates relative to your observing site.

