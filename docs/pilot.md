[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Alpaca Pilot App
[Purpose](#what-is-alpaca-pilot) | 
[Launching](#i-launching-the-alpaca-pilot-application) | 
[Connect](#ii-connecting-devices) | 
[Dashboard](#iii-using-the-dashboard) | 
[Catalog](#iv-using-the-catalog) | 
[Panoramas](./panoramas.md) 

## What is Alpaca Pilot?

>VIDEO DEMO: [21 - Alpha Preview Demonstration of V2.0](https://youtu.be/0QSKD1GCzOc)

The **Alpaca Pilot App** is a responsive, single-page web application designed to streamline the startup, configuration and operation of the **Alpaca Driver** when used with the Benro Polaris Mount. It unlocks many of the Driver’s advanced features, enabling users to fully leverage its capabilities.

![Alpaca Pilot App](images/dashboard-dial0.png)

![Alpaca Pilot App](images/keyboard-map.png)


The Pilot App is completely optional. You can continue using Stellarium, NINA and CCDCiel with the Alpaca Driver just as you did in version 1.0, no changes required. However, choosing not to use the Pilot App means missing out on a range of enhancements that are available to you. 

The Pilot App was built to:
- Simplify the Polaris connection and startup process, eliminating the need to use the official Benro Polaris app on startup
- Make it easy to set the observing site’s latitude and longitude
- Eliminate manual editing of the config.toml configuration file
- Offer an expanded Deep Sky Catalog that surpasses Benro’s default catalog
- Enable precise motion control using geographic or equatorial coordinates
- Provide insight into the performance and diagnostics of Driver features
- Allow advanced users to fine-tune Driver performance parameters


---

### Pilot Main Menu

The main menu of the **Alpaca Pilot** application provides centralized access to key functions, status indicators, and configuration tools for managing your Polaris mount. Each element is designed to streamline your workflow and provide intuitive control over the system.

![Alpaca Pilot Main Menu](images/pilot-menu.png)


- **① Sidebar Menu:**  Opens the collapsible side navigation menu, giving access to additional modules such as Deep Sky Objects, Performance Tuning and Documentation.

- **② Startup Page:**  Clicking the Title will display the initial startup page of the Alpaca Pilot App.

- **③ Dashboard:**  Provides real-time control and feedback for mount operations. Includes radial dials, setpoint controls, status indicators, and visual feedback for guiding, tracking, and slewing.

- **④ Connect:**  Initiates or terminates the connection to the Alpaca Driver and Polaris mount. This button reflects current connection status.

- **⑤ Settings:** Opens the configuration panel where you can set observing site latitude/longitude, define the park position, adjust preferences, and enable standard and advanced features.
> Note: Location services are restricted in browsers on mobile phones and the Locate function in Settings will only work over HTTPS. Refer to the instructions below to [enable HTTPS in Alpaca Pilot](#enable-https-in-alpaca-pilot).
- **⑥ Search Entry:** A text input field for searching catalog entries and targets. Supports shorthand formats and intelligent parsing for quick access to celestial objects.

- **⑦ Search Toggle:** Toggles the visibility of the search entry field. On narrow screens, it also expands the search input area for easier access. When a search term is present, this button acts as a quick-clear control to reset the entry.

- **⑧ Polaris Battery:** Displays the current battery level of the Polaris mount. Includes color-coded indicators or warnings when battery levels are low. Also indicates charging status. On narrow screens, it can also be used to toggle fullcscreen.

- **⑨ Fullscreen:** Toggles fullscreen mode for immersive operation. This is especially useful during outdoor sessions or when using compact displays, allowing maximum space for control and feedback elements.


---

## I. Launching the Alpaca Pilot Application

>VIDEO DEMO: [22 - Launching Alpaca Pilot](https://youtu.be/Wv_ZvBtZZ4Q?t=0m7s)


The Alpaca Pilot App can be accessed via external imaging software or directly through a web browser on a desktop, tablet, or phone.

### Method A: Launching from NINA (Nighttime Imaging 'N' Astronomy)

If you are using NINA, you can launch the Alpaca Pilot App directly from the NINA equipment setup interface:

1.  **Access Equipment Setup:** Navigate to NINA's Equipment setup.
2.  **Mount Connection:** Choose the device for the Alpaca Driver.
3.  **Use Settings Cog:** Before connecting, click the **settings cog button**.
4.  **Fire Up App:** Clicking the settings cog will fire up the Alpaca Pilot application, allowing you to monitor the connection process in detail.

### Method B: Launching via Web Browser

You can access Alpaca Pilot from any browser on a device connected to the same network as the Mini-PC.

1. **Start Driver:** Make sure the driver is running on the Mini-PC.
2. **Open Browser:** On your phone, tablet, or laptop, open any modern browser.
3. **Open Alpaca Pilot:** Enter one of the following in the browser's address bar:
   1.  **Recommended:** `http://ap.local` (or `http://ap.local:8080/` for Linux/Pi installations)
   2.  **Hostname:** eg `http://hostname`
   3.  **IP Address:** eg `http://192.168.10.250`
4.  **Full Screen Feature:** On a phone, you can click on the battery icon to make the application go **full screen** to take up the full real estate available.

### Method C: Launching Multiple Instances

The Pilot application is very flexible, allowing users to open up multiple windows simultaneously to facilitate operations and monitoring. To achieve this, you can right-click or hover on any of the navigation links across the top of the application (such as Dashboard, Connections, or Settings) and choose to open them in a new tab or a new window. 

For example, you might choose to open the Catalog as a new window and position it off to the right, while keeping the main Dashboard open on the left. This configuration allows for streamlined workflows, such as performing quick searches for celestial objects in the Catalog while monitoring the mount's status and coordinates on the Dashboard as you navigate to the selected target.


<details>

<summary>Frequently asked questions</summary>

### What are `ap.local` and mDNS?

Alpaca Driver **v2.2 and later** include an mDNS (Multicast DNS) server. mDNS allows devices on the same local network to discover the Alpaca Driver and Alpaca Pilot Web Server without requiring a central Domain Name Server (DNS).

The Alpaca Pilot web interface is advertised on the local network using mDNS with the default hostname:

```text
http://ap.local
```

You can change the hostname advertised by mDNS from Alpaca Pilot's **Connect** page using the **Network Services** dialog.

The `ap.local` address should work when the device running your browser and the device running the driver are connected to the same local network. It will not normally work across different networks or routed subnets.

Some enterprise networks, browsers, Wi-Fi configurations, firewalls, and security policies may also block or restrict mDNS traffic. If you cannot reach Alpaca Pilot using `ap.local`, use the driver's hostname or IP address instead, as described below.

mDNS is **optional** and is not required for the Alpaca Driver or Alpaca Pilot to operate. If you can already access Alpaca Pilot using the device hostname or IPv4 address, mDNS simply provides an alternative method of access.

### What alternative methods can be used to reach Alpaca Pilot?

There are three ways to reach Alpaca Pilot:

1. **Use mDNS**

   On networks where mDNS is supported by both the network and the client device, use:

   ```text
   http://ap.local
   ```

2. **Use the driver's hostname**

   If the hostname can be resolved by the device running the browser, replace `<hostname>` with the driver's hostname and use:

   ```text
   http://<hostname>
   ```

3. **Use the driver's IP address**

   If you know the IPv4 address allocated to the driver, replace `<ipaddress>` with the driver's IPv4 address and use:

   ```text
   http://<ipaddress>
   ```

   

### How can I find the IP address of the driver?

There are several ways to find the driver's IP address.

1. **Use the driver's log file**

   The IP address is recorded in:

   ```text
   alpaca-benro-polaris/logs/alpaca.log
   ```

   Look for the `==STARTUP==` message containing the mDNS hostname. The address following the `->` characters is the IP address of the driver.

   In this example, the driver's IP address is `192.168.50.73`

   ```text
   2026-09-24T18:47:05.665 INFO ==STARTUP== Serving mDNS hostname [http://ap.local](http://ap.local) -> 192.168.50.73:80
   ```

  

2. **Use your router**

   Log in to your router's administration interface and look for a list of connected devices. Depending on the router, this may be called **Connected Devices**, **DHCP Clients**, **LAN Clients**, **Attached Devices**, or something similar.

   Look for the hostname of the device running the Alpaca Driver. The router should display the IPv4 address assigned to it.

3. **Use Windows**

   If the driver is running on Windows, open **Command Prompt** and run:

   ```text
   ipconfig
   ```

   Find the network adapter that is currently connected to your local network and look for its **IPv4 Address**.

   You can also use the following command to display the computer's hostname:

   ```text
   hostname
   ```
  

4. **Use Raspberry Pi**

   If the driver is running on a Raspberry Pi, open a terminal and run:

   ```text
   hostname -I
   ```

   This displays the IP addresses currently assigned to the Raspberry Pi.

   You can also use the following to display the Raspberry Pi's hostname:

   ```text
   hostname
   ```

### Can you use a phone's hotspot as a network?

Yes. A phone's hotspot can provide a network connection when a normal Wi-Fi network is unavailable.

| Platform                      | Windows                                                                                                               | Raspberry Pi                                                      |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Join your phone's hotspot** | On the driver's Windows device, select your phone's hotspot from the Windows Wi-Fi connection list and connect to it. | Add your phone's hotspot using the setup command described below. |
| **Example configuration**     | Use the normal Windows Wi-Fi configuration interface.                                                                 | `./setup.sh -n <ssid> -w <ssidpassword>`                          |

Once configured, the driver will join the phone's hotspot whenever it is available. If the hotspot is unavailable, it will fall back to the configured home network. If no configured network is available, it will ultimately fall back to access-point mode.

There is an important limitation when using an **Android phone as a hotspot**: Android browsers do not always resolve mDNS hostnames while the phone is operating as the hotspot. In this situation, `http://ap.local/` may not work even though the phone and driver are correctly connected to the same hotspot.

If this occurs, find the driver's IP address and access Alpaca Pilot using the IP address instead.

### How can I test mDNS?

If `ap.local` does not work, you can test whether the device running the browser can resolve the hostname.

On Windows, open **Command Prompt**. On Linux or macOS, open **Terminal**, and run:

```text
ping ap.local

nslookup ap.local
```

If these commands cannot resolve `ap.local`, mDNS may be unavailable or blocked on your network, or the client device may not support mDNS resolution in its current configuration.

Note that a successful `ping` is not required for Alpaca Pilot to work. Some devices or network configurations may block ICMP traffic while still allowing access to the web server. The important test is whether `ap.local` can be resolved to the driver's IP address.

If mDNS is unavailable, use the driver's hostname or IP address instead.

</details>



---

## II. Connecting Devices

>VIDEO DEMO: [21 - Connecting to the Driver and Polaris](https://youtu.be/0QSKD1GCzOc?t=0m51s)

When you start the Alpaca Driver, it will automatically attempt to try and connect to the Benro Polaris. The normal sequence of startup events using Alpaca Pilot are as follows:

- A. Start Alpaca Driver
- B. Launch Alpaca Pilot
- C. Power-on the Polaris ane enable Wifi
- D. Connect to the Polaris
- E. Setup the Polaris for Astro Mode

### A. Start Alpaca Driver
After you have installed the Alpaca Driver, you can start the Driver either from a terminal or from the shortcut link you setup. 

![Pilot start Driver](images/pilot-connecta.png)

### B. Launch Alpaca Pilot
Follow the instructions from the previous section to launch the Alpaca Pilot Application. Navigate to the Connect page to monitor the startup process.

When you launch the **Alpaca Pilot** application, it attempts to automatically connect to the **Alpaca Driver**. In most cases, this connection is established without user intervention. However, if the Driver is not running or network connectivity is lost, you may need to reconnect manually.

If a connection issue is detected, a warning banner will appear. You can then navigate to the **Connect** page to re-establish communication with the Driver.

![Pilot connect](images/pilot-connectb.png)


- **① Driver Host Name / IP Address:**  Enter the hostname or IP address of the mini-PC where the Alpaca Driver is running.  
**Note:** This is *not* the IP address of the Polaris device. 

- **② Driver Port:** Specifies the port used by the Alpaca Driver’s ASCOM REST API. The default is **5555**.  If you’ve changed this value in the network services, be sure to update it here as well.

- **③ Initiate Connection:**  Click this button to manually initiate or retry a connection to the Alpaca Driver.

- **④ Driver Connection Checkbox:** Toggles the connection status with the Alpaca Driver.  
   - When **disconnected**, it functions the same as the *Initiate Connection* button.  
   - When **connected**, clicking this will disconnect the session.


### C. Power-on the Polaris ane enable Wifi

![Power on Poalris and Enable Wifi](images/pilot-connectc.png)

- **① Power On the Polaris:** The Alpaca Driver uses Bluetooth Low Energy (BLE) to discover nearby Benro Polaris Devices. If none are discovered, check the power of your Benro Polaris Device.

   *Note: Bluthooth is only used for discovery and enabling Wifi. It is entirely optional. It is not used in normal operation of the Polaris.*

- **② Select a Device:**  Detected devices appear in the **Device** dropdown. The first discovered device is selected automatically. If multiple devices are listed, choose the one you wish to connect to.

- **③ Enable Wi-Fi:** The Driver will attempt to enable the selected Polaris’s Wi-Fi hotspot automatically.  
   - You can also manually trigger this by clicking the **Wi-Fi button** next to the device dropdown.  
   - If the Blue LED on the Polaris does not illumunate after 30s, you may need to use the **Benro Polaris App** to discover nearby devices, and enable its Wifi. 
   - Once Wi-Fi is successfully enabled, the Blue LED on the Polaris should illumunate.
   - On Windows and Raspberry Pi, the Wi-Fi button also automatically joins the host itself to the Polaris hotspot once it's enabled — you shouldn't need to touch the OS's own Wi-Fi settings at all in the normal case. (macOS doesn't yet auto-join — see below.)

- **Confirm Wifi Connection:** If the drivers host hasn't joined automatically after step ③, check the Log page for a "Failed to join WiFi network" message. To join the Polaris network manually: 
  - on Win11, monitor the systems Wifi List for a polaris_xxxxxx hotspot, click on it, enable automatic connection, and click Connect. Once the host has connected to the Polaris Wifi Hotspot, it should appear as follows:
   ![alt text](images/abp-troubleshoot-wifi1.png)

  - On Raspberry Pi, see [raspberrypi.md's network troubleshooting](./raspberrypi.md#p1---diagnosing-wifi-and-bluetooth-network-issues) to join manually via `join_wifi.py` or `nmcli`. 

### D. Connect to Polaris

Once Wifi network connectivity has been established to the Polaris, the Driver should automatically connect. If you have problems connecting to the Polaris, the following fields allow you to manually initiate a connection with custom settings.

![Connect to Polaris](images/pilot-connectd.png)



- **① Polaris Host Name / IP Address:** This will typically remain as **192.168.0.1**. Enter the hostname or IP address of the Polaris Device.   
   *Note: This is *not* the IP address of the Alpaca Driver.* 

- **② Polaris Port:** This will typically remain as **9090**. Specifies the port used by the Polaris. 

- **③ Initiate Connection:**  Click this button to manually initiate or retry a connection to the Polaris. 

- **④ Polaris Connection Checkbox:** Toggles the connection status with the Polaris.  
   - When **disconnected**, it functions the same as the *Initiate Connection* button.  
   - When **connected**, clicking this will disconnect from the Polaris.

<br>

   > **Troubleshooting Guide**
   If you continue to experience issues connecting to the Polaris, consult the [Troubleshooting Guide](./troubleshooting.md) for diagnostic steps and solutions.

<br>

### E. Setup the Polaris for Astro Mode

Follow these steps to prepare your Benro Polaris mount for Astro Mode using the Alpaca Pilot App:

![Pilot connect](images/pilot-connecte.png)

- **① Switch to Astro Mode:** When the Pilot App launches, it will display the current Polaris mode. This is typically **Photo Mode** on first power-up. Use the dropdown menu to switch to **Astro Mode**.

- **② Initiate Axis Reset:** Click the **Reset** button to command the Polaris to reset all three axes. This replicates the double-tap gesture on each joystick in the Benro Polaris App.

   >**Wait for Reset Completion**  
   Allow the mount to finish its reset sequence. Wait until all axes reach their final positions and all motion ceases.

- **③ Skip Compass Alignment:** Normally, entering Astro Mode requires a Compass Alignment via the Benro Polaris App. With Pilot, you can bypass this by pressing **Skip**.  
   - The default Azimuth is **180°**
   - You may adjust this to approximate the camera’s initial pointing direction, based on how the tripod is oriented.
   - Note: This value represents *true Azimuth* and is different from the Compass Align direction used in the Benro app.
   - Azimuth reference: 0°=North, 90°=East, 180°=South, 270°=West.
   - Saving Alpaca Pilot Settings will store this value.

- **④ Skip Single Star Alignment:** Astro Mode also typically requires a Single Star Alignment. You can skip this step in Pilot by pressing **Skip**.  
   - The default Azimuth is **180°**, and Altitude is **45°**  
   - You may adjust these to match the camera’s iniital pointing direction, based on how the tripod is oriented. 
   - Azimuth reference: 0°=North, 90°=East, 180°=South, 270°=West. 
   - Altitude reference: 0°=Horizontal, 10°=Slight upward tilt, 45°=Moderately upward, 82°=Near maximum upward tilt of Polaris.
   - Saving Alpaca Pilot Settings will store these values.



- **⑤ Multi Point Alignment:** Click this Button to navigate to the Alignment Page. This will allow you to enable to Multi-Point Alignment and review model residuals. After 3 or more Sync Points are added to the model this indicator will turn green. If you are using Single Point Alignment, you can ignore this red indicator on the connect page.

- **Set Observing Site Location:** If the app displays a warning that **latitude and longitude are unset**, go to **Settings** in the menu bar.  
   - Use the map to locate your observing site and click to set it, or click **Locate** to use the browser's location.  
   - The app will attempt to auto-fill altitude, pressure, and location name via a web service. Without internet, the location is named by its coordinates.
   - **GPS receiver (optional):** at a dark site without internet, a USB GPS receiver plugged into the computer running the Alpaca Driver can set the site instead. Click the arrow beside **Locate** and choose **Use GPS Receiver**. Choose its **Serial Port** (GPS receivers are marked in the list), then click **OK** and **Locate (GPS)**. The button shows its progress while it waits for three matching GPS fixes, then sets latitude, longitude and elevation.
   - If the GPS receiver can't get a fix, give it a clear view of the sky. Its first fix after being plugged in can take several minutes. Plug it directly into the computer rather than a USB hub, and keep it away from cameras and their cables, which can block GPS signals.
   - Linux also offers **GPS Daemon (GPSD)**, and the [Raspberry Pi guide](./raspberrypi.md#optional-gps-receiver) has Pi-specific notes.
   - Click **Save** at the top of Settings so the location and GPS settings are kept after a restart.

- **Begin Plate Solving:** With setup complete, you're ready to use the Driver and perform your first plate solve.

### F. Network Services
The **Network Services Dialog** on the **Connect** page is optional, but provides advanced control over how the Alpaca Driver exposes its network services. You can selectively disable specific services or change the network port they use.

This is primarily useful for:
- Reducing the network surface area of the Driver for security or performance reasons  
- Resolving port conflicts with other services running on the same system

Additionally, this dialog allows you to modify the Driver’s behavior regarding automatic reconnection to the Polaris mount. You can disable auto-reconnect if manual control is preferred or if the mount is temporarily unavailable.



![Pilot connect](images/pilot-connectf.png)


### G. Using Alpaca Pilot over HTTPS

By default, Alpaca Pilot runs as an HTTP-based Single Page Application (SPA). As a result, your browser may display the site as **“Not Secure”** and restrict certain features such as location access and clipboard integration.

Starting with version 2.2, Alpaca Pilot supports HTTPS, allowing secure browser access and full functionality. When the Driver starts it will create self-signed certificates that are used for secure access. To use HTTPS you will need to download and install the CA Certificate and enable HTTPS in Alpaca Pilot.

#### Download the CA Certificate

1. Open the **Alpaca Pilot Connect** page.
2. Open the **Network Services** dropdown dialog.
3. Click **Download CA Certificate**.

#### Install the CA Certificate on Windows

1. Open the downloaded `alpaca_pilot_ca.crt` file.
2. Click **Install Certificate**.
3. Select **Local Machine**, then click **Next**.
4. Accept **User Access Control**, click **Yes**.
4. Choose **Place all certificates in the following store**, then click **Browse**.
5. Select **Trusted Root Certification Authorities**, then click **OK**.
6. Click **Next**, then **Finish**.

#### Install the CA Certificate on macOS

1. Open the downloaded `.crt` file — **Keychain Access** will launch automatically.
2. Add the certificate to the **System** keychain.
3. Locate `alpaca-pilot-ca` in the certificate list and double-click it.
4. Expand the **Trust** section and set **When using this certificate** to **Always Trust**.
5. Close the dialog and enter your password to confirm the changes.

#### Install the CA Certificate on iOS / iPadOS

1. Open the **Alpaca Pilot Connect** page in **Safari** and download the CA certificate (Safari will prompt that a profile is ready to install).
2. Go to **Settings → General → VPN & Device Management**, tap the **alpaca-pilot-ca** profile, then tap **Install** in the top-right corner (you'll be prompted for your device passcode).
3. **This alone is not enough — the CA is installed but not yet trusted.** Go to **Settings → General → About → Certificate Trust Settings**.
4. Under **Enable Full Trust for Root Certificates**, toggle **alpaca-pilot-ca** to **on**.


#### Restart Your Browser to pickup the new CA Certificate

* **Chrome:** Navigate to `chrome://restart`
* **Safari:** Fully close Safari (swipe it away from the App Switcher)
* **Firefox:**

  1. Open `about:config`
  2. Search for `security.enterprise_roots.enabled`
  3. Set the value to `true`
  4. Restart Firefox

#### Enable HTTPS in Alpaca Pilot

1. Open the **Alpaca Pilot Connect** page.
2. Open the **Network Services** dropdown.
3. Select **HTTPS**, then click **Save**.
4. The Driver will restart with HTTPS enabled.
5. Alpaca Pilot will detect the restart and redirect to HTTPS.

#### Persistent Certificate Warnings
If you're upgrading from an earlier driver version and still see certificate warnings or connection failures after following the steps above, the browser or the OS may be holding onto stale security state from before the upgrade.

On Windows, do a full power-off rather than Restart. Windows 11 enables "Fast Startup" by default, which hibernates the session instead of fully reinitializing it on Restart. Leftover network state can persist across a restart; only a genuine power-off clears it. 

On any device that connected to an earlier version of the driver, also clear that browser's site data
* **Chrome/Edge**: Settings → Privacy and security → find the site under "All sites" and delete its data; 
* **Safari on iOS/iPadOS**: Settings → Safari → Clear History and Website Data

<br>
<br>

## III. Using the Dashboard
>VIDEO DEMO: [21 - Dashboard introduction](https://youtu.be/0QSKD1GCzOc?t=4m55s)

>VIDEO DEMO: [22 - Dashboard Status and Setpoint Entry](https://youtu.be/Wv_ZvBtZZ4Q?t=3m18s)

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
-   **⑦ Tracking Rate:** This control allows you to **change the tracking rate** of the mount. The Alpaca Driver version 2.0 supports ASCOM Alpaca Drive Rates, including 0=Sidereal, 1=Lunar, 2=Solar, 3=Custom/King. 

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

These indicators reflect the mount’s current motion or tracking mode:
-   **① Gotoing:** The mount is slewing to a target position following a GOTO command.
-   **② Slewing:** The mount is executing a manual slew operation.
-   **③ Rotating:** The mount is actively adjusting its rotation or position angle.
-   **④ Guiding:** The mount is responding to pulse-guiding commands to refine its tracking.
-   **⑤ Sidereal:** - Sidereal tracking is enabled. The mount is following the apparent motion of the stars, maintaining fixed equatorial coordinates.




![Dashboard indicators part 3](images/dashboard-indicators3.png)

When tracking an orbital object, the motion deviates from sidereal tracking. The indicator will instead display the name of the object being tracked:
-   **① Lunar:** Tracking the Moon’s motion.
-   **② Solar:** Tracking the Sun’s motion.
-   **③ Saturn:** Tracking a planetary target.
-   **④ Titan:** Tracking a planetary moon.
-   **⑤ ISS (ZARYA):** Tracking the International Space Station.
-   **⑥ SL-16 R/B:** Tracking a rocket body (spent stage).


![Dashboard indicators part 4](images/dashboard-indicators4.png)

When an orbital object is below 10° altitude, the status indicator turns orange, and its current position is appended to the tracking chip. In this state, the mount does not update its setpoint, allowing you to preselect and monitor targets before they become visible. Once the object rises above 10°, the mount will automatically slew to its position and begin tracking.

-   **① Lunar below the Horizon:** The Moon is currently at −40° altitude. The mount is standing by and will begin tracking once it rises.
-   **② Starlink below 10°:** The communications satellite is below the 10° threshold. The mount is waiting to initiate tracking.



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
   - Roll: ZM2, –60°, –30°, 0°, +30°, +60°. **ZM2** (Zero M2) Rotates to the roll angle that minimises M2 movement over the next 2 hours of tracking, within the permitted roll limits. M2 supports the camera's weight off-axis, so a heavy lens can make it struggle to track smoothly at sidereal rates, causing regular dips in tracking performance. Use ZM2 to minimise M2 movement and reduce these disturbances.
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


## IV. Using the Catalog

>VIDEO DEMO: [22 - Alpaca Pilot Catalog](https://youtu.be/Wv_ZvBtZZ4Q?t=6m42s)

The Alpaca Pilot application features an expanded and intuitive catalog designed to simplify the selection and targeting of celestial objects for astrophotography. This guide details the catalog's contents, how to navigate, filter, and use it for slewing and alignment.

![Catalog](images/pilot-catalog1.png)

### What the Catalog Includes

The catalog in the Alpaca Pilot App has been **significantly expanded** beyond the original Benro Polaris catalog.

1.  **Curated Content:** Instead of listing thousands of objects, the catalog focuses on **quality**. It includes a curated selection of over **500 premium deep sky objects**. These targets highlight the top 25% of imaging targets, based on input from experienced astrophotographers.
2.  **Object Types:** The entries can include a selection of Nebulae, Galaxies, Clusters, Stars, Planets, Moons, Satellites, Comets, Asteroids and Landmarks.
3.  **Ratings and Notes:** Each entry provides helpful notes and community ratings to guide your choices. To keep the application footprint small, items categorized as "typical," "hard," or "avoid" are excluded from the base catalog.
4. **Cross Referenced:** Each entry is cross referenced to over 25 master catalogs like Messier, Caldwell, NGC, IC, H400, Sh2, LDN etc. 

### Understanding Catalog Visual Indicators (Chips)

Each target listing features three coloured chips that provide a quick visual summary of the object's characteristics and current position:

| Chip Colour | Name | Information Provided | Examples of Categorization |
| :--- | :--- | :--- | :--- |
| **Purple** | **Rating** | Indicates the item's imaging rating. By default, the catalog is searched with the most highly rated items listed first. | Categories are used to filter to the top 25% of targets for imaging suitability. |
| **Blue** | **Visibility** | Shows the brightness (apparent magnitude) and angular size of the object. | **Size:** Greater than 100 arc minutes (e.g., Carina Nebula), Extended (30-100 arc minutes), etc.. **Brightness:** Brilliant (magnitude < 2), Bright (2–4), Visible, Dim, Faint (up to magnitude 10). |
| **Yellow** | **Position** | Gives a quick, readable sense of the target's position in the sky (azimuth and altitude). | Examples include "mid low in the southwest," "high in the north," or "near the horizon". Items high above 82 degrees (near zenith) or "below the horizon" are flagged as red. |

### Searching the Catalog
The search system is designed to be fast, intuitive, and efficient for target selection. You can find any object by simply **typing a few letters or numbers** of its name or catalogue reference.

1. **Search by Name:**
   Enter part of the object’s **common name**.

   * Example: **“rig”** →  *Rigil Kentaurus*.
   * Example: **“pole”** →  *North Celestial Pole*.

2. **Search by Reference:**
   Enter part of the object’s **catalogue designation**.

   * Example: **“M8”** → *Lagoon Nebula*
   * Example: **“NGC 5139”** → *Omega Centauri*

Common catalogue prefixes include **M**, **NGC**, **IC**, **C (Caldwell)**, **Abell**, **Arp**, **H (Herschel)**, **LDN**, and others.
For a full list of supported catalogues, see the **Reference Catalogues** section.

### Filtering Results
You can filter targets by various key attributes that affect imaging suitability, including **Type, Proximity, Quality Rating, Altitude, Classification, Angular size, Apparent magnitude (brightness)**.

![Catalog](images/pilot-catalog2.png)

1.  **Filtering by Type (Side Menu):** Use the side menu to limit results by broad object type, such as Nebula, Galaxy, Cluster, Star, Planet, Moon, Satellite, Comet, Asteroid or Landmark.
1.  **Filtering by Proximity (Side Menu):** Displays objects sorted by angular proximity to the telescope’s current pointing or the mount’s orientation. Ideal for finding nearby targets without slewing far.
2.  **Filtering by Quality Rating (Dropdown):** Filter by the visual and imaging quality rating of each object, eg Top 2%, 10%, 25%.
3.  **Filtering by Altitude (Dropdown):** Limit the list based on the height of the object in the sky.
3.  **Filtering by Classification (Dropdown):** Filter by fine grained classification of the subtype of the object.
3.  **Filtering by Size (Dropdown):** Filter by apparent angular size of the object
3.  **Filtering by Brightness (Dropdown):** Filter by visual brightness (magnitude) for selecting objects suited to your observing or imaging conditions

### GoTo (Slew) to the Target
To move the mount to a target's location, simply **click the GoTo button** associated with the item, and the mount will start moving to that location.

*   **Tracking State Preservation:** When you issue a GoTo command, the driver will preserve **whatever the tracking state was** at the time; it does not automatically turn tracking on.
*   **Roll Angle Preservation:** When you issue a GoTo command, the driver will preserve **whatever the roll angle state** at the time; it does not reset back to zero. When in equitorial model, the Roll Angle is still preserved, and the corresponding Position Angle for that orientation is selected.


### Sync with a Target
If the object you have selected is **already visible in your camera’s field of view**, you can use the sync function to align the mount's coordinates precisely. Syncing helps the Driver understand where the telescope is pointing compared to where Polaris thinks it is, correcting any upstream misalignment.



For the full list of reference catalogues, and how to extend the catalog with your own entries, see the [Catalog Reference](./catalog.md).

<br>
<br>

## V. Creating Panoramas
Alpaca Pilot's Panorama Grid lets you plan and capture multi-panel panoramas and mosaics. See [Creating Panoramas](./panoramas.md).
