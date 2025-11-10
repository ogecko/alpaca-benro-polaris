[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Alpaca Pilot App
[Purpose](#what-is-alpaca-pilot) | 
[Launching](#i-launching-the-alpaca-pilot-application) | 
[Connecting](#ii-connecting-to-the-benro-polaris-mount) | 
[Dashboard](#iii-dashboard) | [Catalog](#catalog)  | [Tuning](#tuning) | [Diagnostics](#diagnostics) 

## What is Alpaca Pilot?

>VIDEO DEMO - [21 - Alpha Preview Demonstration of V2.0](https://youtu.be/0QSKD1GCzOc)

The **Alpaca Pilot App** is a responsive, single-page web application designed to streamline the startup, configuration and operation of the **Alpaca Driver** when used with the Benro Polaris Mount. It unlocks many of the Driver’s advanced features, enabling users to fully leverage its capabilities.

![Alpaca Pilot App](images/dashboard-dial0.png)


The Pilot App is completely optional. You can continue using Stellarium, NINA and CCDCiel with the Alpaca Driver just as you did in version 1.0, no changes required. However, choosing not to use the Pilot App means missing out on a range of enhancements that are available to you. 

The Pilot App was built to:
- Simplify the Polaris connection and startup process, eliminating the need to use the official Benro Polaris app on startup
- Make it easy to set the observing site’s latitude and longitude
- Eliminate manual editing of the config.toml configuration file
- Offer an expanded Deep Sky Catalog that surpasses Benro’s default catalog
- Enable precise motion control using geographic or equatorial coordinates
- Provide insight into the performance and diagnostics of Driver features
- Allow advanced users to fine-tune Driver performance parameters

Here’s an expanded and refined version of your **Pilot Main Menu** section in Markdown, with clear descriptions for each item and consistent formatting:

---

### **Pilot Main Menu**

The main menu of the **Alpaca Pilot** application provides centralized access to key functions, status indicators, and configuration tools for managing your Polaris mount. Each element is designed to streamline your workflow and provide intuitive control over the system.

![Alpaca Pilot Main Menu](images/pilot-menu.png)


- **① Sidebar Menu:**  Opens the collapsible side navigation menu, giving access to additional modules such as Deep Sky Objects, Performance Tuning and Documentation.

- **② Startup Page:**  Clicking the Title will display the initial startup page of the Alpaca Pilot App.

- **③ Dashboard:**  Provides real-time control and feedback for mount operations. Includes radial dials, setpoint controls, status indicators, and visual feedback for guiding, tracking, and slewing.

- **④ Connect:**  Initiates or terminates the connection to the Alpaca Driver and Polaris mount. This button reflects current connection status.

- **⑤ Settings:** Opens the configuration panel where you can set observing site latitude/longitude, define the park position, adjust preferences, and enable standard and advanced features.

- **⑥ Search Entry:** A text input field for searching catalog entries and targets. Supports shorthand formats and intelligent parsing for quick access to celestial objects.

- **⑦ Search Toggle:** Toggles the visibility of the search entry field. On narrow screens, it also expands the search input area for easier access. When a search term is present, this button acts as a quick-clear control to reset the entry.

- **⑧ Polaris Battery:** Displays the current battery level of the Polaris mount. Include color-coded indicators or warnings when battery levels are low. Also indicates charging status. On narrow screens, it can also be used to toggle fullcscreen.

- **⑨ Fullscreen:** Toggles fullscreen mode for immersive operation. This is especially useful during outdoor sessions or when using compact displays, allowing maximum space for control and feedback elements.


---

## I. Launching the Alpaca Pilot Application

>VIDEO DEMO - [22 - Launching Alpaca Pilot](https://youtu.be/Wv_ZvBtZZ4Q?t=0m7s)


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
>VIDEO DEMO - [21 - Connecting Polaris](https://youtu.be/0QSKD1GCzOc?t=0m51s)

![Pilot connect](images/pilot-connect.png)


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


## III. Dashboard
>VIDEO DEMO - [21 - Dashboard introduction](https://youtu.be/0QSKD1GCzOc?t=4m55s)

>VIDEO DEMO - [22 - Dashboard Status and Setpoint Entry](https://youtu.be/Wv_ZvBtZZ4Q?t=3m18s)

### Purpose of the Dashboard
The dashboard is the central component of the Alpaca Pilot App. It basically shows you the current **orientation of the telescope** and any **activity on the motors**. It provides **real-time telemetry** of the mount's current coordinates, including Azimuth, Altitude, Roll or Right Ascension, Declination, Position Angle. The Dashboard also provides direct control of the mount through action buttons and interaction into zoomable radial dials for each co-ordinate.

### Action Buttons
The action buttons in the top-left corner of the Dashboard offer quick access to global mount controls.

![Dashboard action buttons](images/dashboard-actions.png)

-   **① Co-ordinate Mode:** This feature allows you to **quickly switch** between two primary coordinate systems for viewing and control:
    *   **Geographical** - Azimuth, Altitude, and Roll.
    *   **Equatorial** - Right Ascension, Declination, and Position Angle.
-   **② Reset SP (Set Point):** This button appears when the mount’s actual position (Present Value) has deviated from the desired target position (Set Point). This may occur when the mount is controlled by a non Alpaca Application or when the mount is not physically able to reach the setpoint. Clicking the **Reset Set Point button** instructs all set points to reline up with the current physical values of the device.
-   **③ Find Home:** When clicked, it moves the motors and changes the orientation of the mount to wind the motor angles (**M1, M2, M3**) back to zero. If the mount is set up pointing south, this typically results in an Azimuth of 180°, an Altitude of 45°, and a Roll of 0°. If the mount cannot complete this movement within 
-   **④ Park:** This function moves the mount into a designated park position.  You can **customize and save** the park position motor angles from the settings page. Once the mount reaches the park location, a yellow banner will appear, and most functions are disabled; you must click a button to **unpark** to resume use.
-   **⑤ Stop:** This button allows you to **immediately stop** the mount. This is equivalent to an **Abort Slew** operation and will stop motion across all axes.
-   **⑥ Tracking:** This action button controls the mount's sidereal tracking state. It allows you to **initiate tracking** or **turn tracking off**. Ensure you have tracking enabled for plate-solving or imaging deep sky objects as it is no longer automatically enabled after gotos
-   **⑦ Tracking Rate:** This control allows you to **adjust the tracking rate** of the mount. The Alpaca Driver version 2.0 supports ASCOM Alpaca Drive Rates, including 0=Sidereal, 1=Lunar, 2=Solar, 3=King and 4=Custom. 

### Status Indicator
The Status Indicator (a status chip in the top right-hand corner of the Dashboard) gives the **state of the motion controller** in the Alpaca driver. Only one state is given at a time, but they are all listed here for explaination purposes.

![Dashboard indicators part 1](images/dashboard-indicators1.png)


-   **① Idle:** This state means **no commands are currently being issued** from the driver to the Polaris. In this state, the Benro Polaris (BP) app can be used without the driver interfering.
-   **② Homing:** The mount is actively moving its motors back to the zero position (0, 0, 0 motor angles).
-   **③ Parking:** The mount is moving into the customized park motor angle position.
-   **④ Parked:** The mount has reached the set park location. A banner appears, and most functions are disabled until the mount is unparked.
-   **⑤ Limit:** This indication appears on the dashboard when a **motor angle limit has been exceeded**. All control to the Polaris will be stopped. The user must click the reset button to acknowledge the limit.
-   **⑥ PreSetup:** This flag or alarm indication appears when the **observing site location (latitude, longitude)** has not been set. No action can be taken with the mount until the location is set.

![Dashboard indicators part 2](images/dashboard-indicators2.png)

-   **① Gotoing:** The mount is proceeding to the GOTO target that was just initiated.
-   **② Slewing:** The mount is executing a manual slew command.
-   **③ Rotating:** The mount is actively changing its rotation angle/position angle.
-   **④ Tracking:** The mount's tracking function is currently enabled. It will be tracking at the current tracking rate, either sidereal, lunar, solar, king or custom.
-   **⑤ Guiding:** The mount's has received a pulse-guiding command and adjusting its tracking accordingly.

### Motor Indicators

The dashboard shows any **activity on the motors** and the current **M1, M2, and M3 motor angles**. These angles show the **actual physical rotation** of each motor from its home position. Importantly, unlike coordinate axes (like azimuth), the motor angle **does not wrap around** at 360 degrees; it keeps recording how far the motor has moved. 

![Dashboard motors](images/dashboard-motors.png)

-   **① Motor Label:** The labels M1, M2 and M3 represent the Azimuth, Altitude and Astro axis accordingly.
-   **② Angular Offset:** The signed angular rotation in decimal degrees that each motor has traveled from its home or zero position.
-   **③ Motor Activity:** The orbiting dot, represents motion in the corresponding axis. It rotates in the direction and speed of the motors motion. The speed is exegerated for slow motion so very fine movement can be seen. 


### Radial Dials
The radial dials are a core part of the dashboard, designed to be flexible and interactive. They provide a quick representation of the current orientation of the mount, either in geographic or equatorial co-ordinates. 

![Dashboard radial dial](images/dashboard-dial1.png)
-   **① Scale Label:** Displays the rounded numeric values associated with a major tick on the radial dial. Clicking or Tapping on the numeric label will change the Setpoint of that co-ordinate to the given value.
-   **② Scale Bar:** The cyan arc indicates an angular scale, marked with 5 minor ticks of equal distance dividing the major ticks. Clicking or tapping on the scale bar will change the Setpoint to the exact value at that point. 
-   **③ Warning Bar:** A orange arc that highlights regions of the scale where values exceed safe or expected limits. If a pointer enters this zone, it may indicate that the angle is not reachable.
-   **④ Deviation Bar:** A green arc that indicates the real-time difference between the setpoint (SP) and the present value (PV). The arc represents the path that the mount will travel to close the deviation to zero.
-   **⑤ SP Pointer:** A green arrow pointing to the current Setpoint target value the system is trying to achieve. It remains fixed unless the setpoint is adjusted.
-   **⑥ PV Pointer:** A white triangle pointing to the Present Value of the axis. This pointer will always point to the top center of the arc. As the mount moves in real time, the scale will rotate around this pointer. 
-   **⑦ PV Readout:** A numeric display of the Present Value in Degrees, Arc-Minutes and decimal Arc-Seconds (except for Right Ascension which is in Hours, Minutes and Seconds). 
-   **⑧ SP Readout:** A numeric display of the current Set Point. This value reflects the target the system is actively trying to maintain.

<br>

When you hover your mouse or tap your finger on a radial dial, additional buttons will appear allowing you to interact with that co-ordinate.

![Dashboard radial dial active](images/dashboard-dial2.png)


- **① Range Readout:** Displays the total angular span of the radial dial, measured from left to right. This value also determines the slew rate when adjusting the Set Point using controls ⑤ or ⑥. Specifically, the slew rate is equal to (Range ÷ 20) degrees per second. As a result, it takes approximately 20 seconds to move the Set Point across the full range of the dial.
- **② Increase Range:** - Expands the scale range to accommodate larger values. Use this when the current range is too narrow or when values are changing too rapidly to interpret clearly. Scrolling the mouse wheel upward has the same effect as this control.
- **③ Decrease Range:** Narrows the scale range to enhance resolution and visual precision. This is especially useful when movements are subtle and you want finer detail in the display.
Scrolling the mouse wheel downward performs the same action as this control.
- **④ Floating Action Buttons:** - Toggles the visibility of context-sensitive presets for quickly adjusting the Set Point. The available presets depend on the coordinate type of the active radial dial:
   - Azimuth: North 0°, East 90°, South 180°, West 270°
   - Altitude: 0°, 30°, 45°, 60°
   - Roll: –75°, 0°, +70°
- **⑤ SP Decrease**  
  Decreases the current setpoint (SP) by a fixed increment, determined by the active Range setting. Use this to manually slew the target value downward.  
 *Note: The mount may take a moment to respond and align with the new setpoint.*
- **⑥ SP Increase**  
  Increases the current setpoint (SP) by a fixed increment, based on the current Range. Use this to manually slew the target value upward.  
  *Note: The mount may take a moment to respond and align with the new setpoint.*
- **⑦ SP Data Entry**  
  Enables direct numeric input of the setpoint value. Ideal for precise adjustments or bypassing incremental steps. After entering the desired value, confirm to apply it. The input field supports a variety of formats:

  **Absolute Setpoint Formats**
  - `90.234` — Decimal degrees (or hours for Right Ascension)  
  - `90:30` — Degrees and minutes  
  - `90:30:25.2` — Degrees, arcminutes, and decimal arcseconds  
  - `:30.5` — Decimal arcminutes  
  - `-90` — Negative decimal degrees  

  **Relative Setpoint Formats**
  - `d-2` — Decrease by 2 degrees (or hours for Right Ascension)  
  - `d:30` — Increase by 30 arcminutes  
  - `d::40` — Increase by 40 arcseconds  
  - `d2.5` — Increase by 2.5 decimal degrees


## IV. Catalog

>VIDEO DEMO - [22 - Alpaca Pilot Catalog](https://youtu.be/Wv_ZvBtZZ4Q?t=6m42s)

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


