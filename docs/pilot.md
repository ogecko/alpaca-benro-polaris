[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./Pilot.md) | [Control](./Control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Alpaca Pilot App
[Connecting](#2-connecting) | [Settings](#3-settiings) | [Dashboard](#4-settiings) | [Searching](#5-searching)  | [Tuning](#6-tuning) | [Diagnostics](#7-diagnostics) 

## Alpaca Pilot -  Video Demonstration
You can view a demonstration of parts of this documentation in the following YouTube Video.
[![Capturing Images](https://img.youtube.com/vi/HCJNchWL2Yg/0.jpg)](https://www.youtube.com/watch?v=HCJNchWL2Yg)

## 1. What is Alpaca Pilot

## 2. Launching and Connecting
### Launching Alpaca Pilot
### Connecting to the Alpaca Driver
### Connecting the Driver to Benro Polaris

## 3. Settings
### Saving Settings
### Observing Site Information
### Advanced Control Features
### Standard Control Features

## 4. Dashboard
### Status and Motor Indicators
### Equatorial vs Az/Alt
### Home, Park, Stop, Track
Find Home and Park. Both of these functions use the slower absolute motor positions M1, M2, M3. This is the only way we can ensure unwinding of cables. FindHome will return these motors to M1=M2=M3=0, which may not correspond to Az180, Alt45, especially if you have done a single or multi-point alignment. The same with Park, it remembers the M1, M2, M3 positions when you Save the Park Position (or 0,0,0 as a default). If you realign the Polaris with single or multi-point align, the Az/Alt of your park position may change, but the motor angles wont.
### Dial Interaction
#### Scale adjustment
#### Relative Goto
#### Absolute Goto
#### Slewing

## 5. Searching
### Search Bar
### Side Bar
### DSO Objects
### Orbitals

## 6. Tuning
### Speed Calibration
With the calibration there is no realy right answer and being closer to "zero" doesnt really matter. The intent is to make the driver understand what speeds it will get when it commands the mount to go at a specific cmd. The right answer is the result from your own mount. Faster or slower than the baseline doesnt really matter. The %change is just a check that its not too large a change like >20% which may indicate a bad test result. 7% is fine. send through your results if your unsure what to approve, but I'd suggest approving all.
### Kalman Filter Tuning
### PID Tuning
### Alpaca Driver Network Services

## 7. Diagnostics
### Log Output
### Log Settings
### Position
### PWM Testing


