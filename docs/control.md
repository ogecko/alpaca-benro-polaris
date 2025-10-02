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

Version 2.0 of the driver offers two methods for polar alignment: Single Point Alignment and Multi-Point Alignment.

### Single-Point Alignment
The Single-Point Alignment method uses the standard Benro Polaris alignment technique as a SYNC function for Alpaca Clients. This allows clients to adjust the Benro Polaris to align its current pointing direction with a known position.

The advantage of this method is that the alignment correction is made directly in the Benro Polaris, benefiting all connected clients. However, this approach heavily relies on accurately leveling the tripod and is vulnerable to drift and inconsistent tracking.

### Multi-Point Alignment
The Multi-Point Alignment method also provides a SYNC function for Alpaca clients. By syncing with three or more known positions, it creates a correction model that accounts for factors such as tripod tilt, polar misalignment, cone error, and other mechanical offsets that might affect pointing and tracking accuracy.

This algorithm is derived from a method used in various NASA satellite launches. It is efficient, employs a closed-form solution, and utilizes quaternions to achieve precise polar alignment.

The Alpaca Pilot App allows you to monitor the development of this model. You can assess how accurately the model fits all received SYNCs. Additionally, you have the option to remove any inaccurate SYNCs to help improve the model's performance. The app also provides a new method for syncing during the day: simply point your camera at a known landmark on the horizon and click on a map to confirm its location. The app will calculate the elevation of the point you clicked on and determine the true azimuth and altitude of your current pointing position.


