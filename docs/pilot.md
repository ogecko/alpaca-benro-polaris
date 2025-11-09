[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Alpaca Pilot App
[Objectives](#what-is-alpaca-pilot) | [Settings](#3-settiings) | [Dashboard](#4-settiings) | [Searching](#5-searching)  | [Tuning](#6-tuning) | [Diagnostics](#7-diagnostics) 

## What is Alpaca Pilot?

VIDEO DEMO - [21 - Alpha Preview Demonstration of V2.0](https://youtu.be/0QSKD1GCzOc)

The **Alpaca Pilot App** is a responsive, single-page web application designed to streamline the startup, configuration and operation of the **Alpaca Driver** when used with the Benro Polaris Mount. It unlocks many of the Driver’s advanced features, enabling users to fully leverage its capabilities.

The Pilot App is completely optional. You can continue using NINA and CCDCiel with the Alpaca Driver just as you did in version 1.0, no changes required. However, choosing not to use the Pilot App means missing out on a range of enhancements that are available to you. 

The Pilot App was built to:
- Simplify the Polaris connection and startup process, no need for the official Benro Polaris app
- Make it easy to set the observing site’s latitude and longitude
- Eliminate manual editing of the config.toml configuration file
- Offer an expanded Deep Sky Catalog that surpasses Benro’s default
- Enable precise motion control using geographic or equatorial coordinates
- Provide insight into the performance and diagnostics of Driver features
- Allow advanced users to fine-tune Driver performance parameters


---

## I. Launching the Alpaca Pilot Application

The Alpaca Pilot App can be accessed via external imaging software or directly through a web browser on a desktop, tablet, or phone.

### Method A: Launching from NINA (Nighttime Imaging 'N' Astronomy)

If you are using NINA, you can launch the Alpaca Pilot App directly from the NINA equipment setup interface:

1.  **Access Equipment Setup:** Navigate to NINA's Equipment setup.
2.  **Mount Connection:** Choose the device for the ABP driver.
3.  **Use Settings Cog:** Before connecting, click the **settings cog button**.
4.  **Fire Up App:** Clicking the settings cog will fire up the Alpaca Pilot application, allowing you to monitor the connection process in detail.

### Method B: Launching via Web Browser

You can access the Alpaca Pilot App directly from any browser using the driver's hostname or IP address.

1. **Start Driver:** Ensure the driver is running on your Mini-PC
1. **Open Browser:** On your phone, table, or laptap that has network access to your Mini-PC, open a Browser of your choice. You can use Chrome, Firefox, Safari, Edge or any modern browser.
1.  **Use Hostname:** Enter the Mini-PC hostname into the address bar
2.  **Use IP Address:** Alternatively, you can type in the IP address of the Mini-PC.
4.  **Full Screen Feature:** On a phone, you can click on the battery icon to make the application go **full screen** to take up the full real estate available.

### Method C: Launching Multiple Instances

The Pilot application is very flexible, allowing users to open up multiple windows simultaneously to facilitate operations and monitoring. To achieve this, you can right-click or hover on any of the navigation links across the top of the application (such as Dashboard, Connections, or Settings) and choose to open them in a new tab or a new window. 

For example, you might choose to open the Catalog as a new window and position it off to the right, while keeping the main Dashboard open on the left. This configuration allows for streamlined workflows, such as performing quick searches for celestial objects in the Catalog while monitoring the mount's status and coordinates on the Dashboard as you navigate to the selected target.

---

## II. Connecting to the Benro Polaris Mount

The ABP Driver uses Bluetooth Low Energy (BLE) to discover and connect to the Benro Polaris device. BLE is entirely optional and is only used during the initial discovery phase. Once connected, the Driver communicates over Wi-Fi.
- If your Mini-PC does not support BLE, you can manually enable the Polaris Wi-Fi hotspot using the Benro Polaris App.
- Alternatively, if BLE is available, you can monitor the connection process directly within the Alpaca Pilot App, which provides real-time feedback during discovery and initialization.


### Step A: Powering On and Device Discovery

1. **Power On the Polaris**  
   Turn on the Benro Polaris (BP) mount.

2. **Device Discovery**  
   The Driver continuously scans for Polaris devices via Bluetooth Low Energy (BLE).  
   - If no devices are found, the Pilot App will prompt you to verify that the Polaris is powered on.

3. **Select a Device**  
   Detected devices appear in the **Device** dropdown.  
   - The first discovered device is selected automatically.  
   - If multiple devices are listed, choose the one you wish to connect to.

4. **Enable Wi-Fi**  
   The Driver will attempt to enable the selected Polaris’s Wi-Fi hotspot.  
   - You can also manually trigger this by clicking the **blue Wi-Fi button** next to the device dropdown.  
   - Once Wi-Fi is successfully enabled, a **blue Wi-Fi signal icon** will appear.


### Step B: Connect Mini-PC to Polaris Wi-Fi

1. **Automatic Connection**  
   If your Mini-PC has previously connected to the Polaris, it should automatically reconnect, just as it did in version 1.0. This may take up to a minute before the network becomes accessible to the Alpaca Driver.

2. **Manual Connection**  
   If this is your first time connecting:  
   - On Windows 11, open **Network Settings**  
   - Monitor available Wi-Fi networks until you see a device named `polaris_xxxxx`  
   - Select it to initiate the connection

3. **Confirm Connection Status**  
   Wait until the network status displays **"No Internet, open"**. Once connected, the Alpaca Driver will establish communication with the Polaris and begin initialization, reading hardware and firmware version details.

4. **Troubleshooting Tips**  
   If you experience issues connecting to the Polaris, consult the [Troubleshooting Guide](./troubleshooting.md) for diagnostic steps and solutions.


### Step C: Initial Setup with the Alpaca Pilot App

Follow these steps to prepare your Benro Polaris mount for Astro Mode using the Alpaca Pilot App:

1. **Switch to Astro Mode**  
   When the Pilot App launches, it will display the current Polaris mode. This is typically **Photo Mode** on first power-up. Use the dropdown menu to switch to **Astro Mode**.

2. **Initiate Axis Reset**  
   Click the **Reset** button to command the Polaris to reset all three axes. This replicates the double-tap gesture on each joystick in the Benro Polaris App.

3. **Wait for Reset Completion**  
   Allow the mount to finish its reset sequence. Wait until all axes reach their final positions and all motion ceases.

4. **Skip Compass Alignment**  
   Normally, entering Astro Mode requires a Compass Alignment via the Benro Polaris App. With Pilot, you can bypass this by pressing **Skip**.  
   - The default Azimuth is **180°**, but you can manually set it to approximate the mount’s current camera direction.  
   - Note: This Azimuth setting is not equivalent to the Compass Align direction used in the Benro app. It is 180° offset.

5. **Skip Single Star Alignment**  
   Astro Mode also typically requires a Single Star Alignment. You can skip this step in Pilot by pressing **Skip**.  
   - Defaults: Azimuth **180°**, Altitude **45°**  
   - You may adjust these to match the camera’s current orientation.

6. **Set Observing Site Location**  
   If the app displays a warning that **latitude and longitude are unset**, go to **Settings** in the menu bar.  
   - Use the map to locate your observing site and click to set it.  
   - The app will attempt to auto-fill altitude, pressure, and location name via a web service.

7. **Begin Plate Solving**  
   With setup complete, you're ready to use the Driver and perform your first plate solve.


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


