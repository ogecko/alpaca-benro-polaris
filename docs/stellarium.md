[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarim](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Using Stellarium with Benro Polaris
## Telescope Control Compatibility
The APB Driver supports both the Alpaca ASCOM and SynScan protocols. This opens up a wide range of Telescope Control applications now compatible with the Benro Polaris. Out of all those listed, we recommend Stellarium PLUS and Stellarium Desktop.

### Supported and Tested

* Stellariium Mobile PLUS (IOS, Android) - paid, telescope control via SynScan protocol.
* Stellarium Desktop (Win) - free, telescope control via ASCOM Alpaca
* Stellarium Desktop (MacOS, Linux) - free, telescope control via a binary protocol
* Nina (Win) - free, telescope control via Alpaca
* CCDciel (MacOS) - free, telescope control via Alpaca

### Potentially Supported (untested)

* Sky Safari 7 Plus and Pro - paid, telescope control via Alpaca 

### Not supported

* Stellariium Web - free, no telescope control
* Stellarium Mobile (IOS, Android) - free, no telescope control
* Sky Safari 7 Basic - free, no telescope control
* Skyportal - Celestron’s free version of Skysafari
* SynScan App and SynScan Pro App - Not currently supported

## 1. Using Stellarium Mobile PLUS
Stellarium Mobile PLUS is ideal for use on a tablet or mobile phone, either Android or IOS. It includes more features than the free Stellarium Web and the free Stellarium Mobile offerings.

### Connecting to the Driver
Stellarium Plus connects to the driver over the network using SynScan protocol. It is the most straightforward setup; you only need to do this once. To connect Stellarium PLUS: 
1. Select the Hamburger menu from the top left
2. Select Observing Tools > Telescope Control
3. Toggle it off/ and on to bring up the popup at the bottom left
4. In the Host field, enter the IP Address of the ABP Driver.
5. In the Port field, leave a default of 10001.
6. Click the Link toggle to start the connection.
7. Stellarium will attempt to connect to the driver.
8. Choose Sync Location (Stellarium site alt/az will be sent to the driver)
9. Choose Sync Time (Stellariam will send its time to the driver)

A Yellow Not Aligned flag indicates that the driver has not completed initializing its communications with the Benro Polaris and may still be out of alignment.

### Goto Co-ordinates
Commanding the Benro Polaris to move is as simple as Selecting the Target Object and clicking the Goto Icon. The icon will flash red while the mount is slewing and re-establishing sidereal tracking.

### Changing Field of View
As the telescope sweeps across the sky, you will see a reticule marking its path. You can tailor the size of the reticule to match your camera and lens setup, allowing you to visualize your framing easily.

If you lose sight of where the mount is pointing in Stellarium, simply click this second icon, and the view will immediately pan to your reticle.

### Move Axis Commands
The third icon on the Telescope Popup allows you to move the primary and secondary axes of the Benro Polaris. The Driver supports move commands on the third (Astro) axis of the Benro Polaris, but we have not found any applications that support the third axis at this stage.

Speeds 1 to 5 match the slow Move Axis speeds of the Polaris. Speeds 6 to 9 map to a variable faster speed ranging from 1 to 2000 units. The table below gives you an approximate speed for each value.

| Rate | Rotational Speed |
| ---- | ---------------- |
|   1  | 21.5 arcsec/s    |
|   2  | 1.1 arcmin/s     |
|   3  | 2.8 arcmin/s     |
|   4  | 5.3 arcmin/s     |
|   5  | 12.5 arcmin/s    |
|   6  | 32.5 arcmin/s    |
|   7  | 1.5 degree/s     |
|   8  | 3.0 degree/s     |
|   9  | 5.2 degree/s     |

Note that Move Axis in Nina allows you to enter fractional speeds. Due to Benro Polaris, these only have effect from 5.1 to 9.0 (i.e., for the Benro Polaris Fast Move commands).

### Sync Co-ordinates
You can help improve the aim of the Benro Polaris by Syncing with a known object in the sky.

* Using the Move Axis controls, aim the telescope with the known object in the center of the eyepiece or image.
* Find the known object in Stellarium and select it.
* Tap the Sync icon on the Telescope Control Popup.
* The Reticle should immediately shift to your selected target.
* This amount will now offset all RA/Dec coordinates sent and received from Polaris.

To reset the RA/Dec Offset, simply tap the disconnect and reconnect icons on the Telescope Control Popup in Stellarium. For a better understanding of how this works, refer to Section 3 below.

## 2. Using Stellarium Desktop
Stellarium Desktop has the broadest set of features of all versions of Stellarium. It is flexible, allowing you to customize what is shown (deep sky objects, satellites, meteor showers, planets, etc.) and how it is revealed (annotations, projections, landscapes, etc.), including numerous sky surveys.

It includes an extensive What's Up Tonight tool for planning imaging targets. It also includes an extensive library of plug-ins that add more functionality to the application. It's a very powerful platform.


### Connecting to the Driver on MacOS/Linux
Stellarium Desktop on MacOS and Linux does not support native Alpaca or ASCOM. We have implemented a simple External Software Binary Protocol that only allows GOTO functionality. You can add an External Software Telescope by using the following procedure:
1.  Select the `Plug-ins` tab on the Configuration Dialog menu bar.
2.  Scroll down the list of plugins and find the `Telescope Control plugin`.
3.  Check `Load at startup` on the Telescope Control Dialog.
4.  Close Stellarium and Restart Stellarium from the Desktop.
5.  Press `Ctrl+0` to open the Slew Telescope Dialog
6.  Click the `Configure Telescopes` button at the bottom of this dialog.
7.  Click on the `Add Telescope` button (3rd one at the bottom of the Telescope Control Configure dialog).
8.  Choose Telescope controlled by `External software or a remote computer` and enter `Benro Polaris` into the Name field.
9.  In the Host field, enter the IP Address of the ABP Driver.
10. In the TCP Port field, leave a default of 10001.
11. Click OK

### Connecting to the Driver on Windows
Unfortunately, Stellarium Desktop does not include native Alpaca support. You must install the ASCOM Platform if you haven't already done so. After the ASCOM platform has been installed, you can add an ASCOM Telescope by using the following procedure:
1.  Select the `Plug-ins` tab on the Configuration Dialog menu bar.
2.  Scroll down the list of plugins and find the `Telescope Control plugin`.
3.  Check `Load at startup` on the Telescope Control Dialog.
4.  Close Stellarium and Restart Stellarium from the Desktop.
5.  Press `Ctrl+0` to open the Slew Telescope Dialog
6.  Click the `Configure Telescopes` button at the bottom of this dialog.
7.  Click on the `Add Telescope` button (3rd one at the bottom of the Telescope Control Configure dialog).
8.  Choose Telescope controlled by `ASCOM` and enter `Benro Polaris` into the Name field.
9.  Leave the Coordinate System as `J2000 (default)`, 
10. Check `Start/Connect on Startup`.
11. Scroll down to the ASCOM Settings.
12. Click `Choose ASCOM Telescope`
13. Click the `Alpaca` tab on the ASCOM Telescope Chooser dialog box.
14. Click `Enable Discovery` from the Alpaca tab
15. Click `Discover Now` from the Alpaca tab
16. For a local AAPB, Choose `Benro Polaris` from the drop down-menu, then click `OK`.
17. For a remote AAPB, Click `Create Alpaca Driver (Admin)` from the drop-down.
    a. Click `Yes` for  User Account Control.
    b. Enter the name `Benro Polaris`, then click `OK`.
    c. Click `Properties` on the ASCOM Telescope Chooser dialog box.
    d. Change the Remote Device Host Name/IP address (`127.0.0.1` for Loopback)
    e. Change the Alpaca Port to `5555`.
    f. Click `OK`.
18.  Click `OK` on ASCOM Telescope chooser dialog.
19.  Click `OK` on Add a New Telescope dialog.
20.  Click `Connect` and close the Telescopes dialog.
21.  You have now added the Benro Polaris telescope and connected it.

### Goto Co-ordinates
On Windows, commanding the Benro Polaris to move is as simple as Selecting the Target Object and pressing `Ctrl+1`.

You can also bring up the `Slew Telescope To` dialog by pressing `Ctrl+0`. This dialog allows:
* Manually enter the co-ordinates
* Select the Current Object
* Select the Center of the Screen
* Select from a customisable list of Targets
* Initiate the Slew of the Benro Polaris.

### Changing Field of View
On Windows, as the telescope sweeps across the sky, you will see a reticule marking its path. You can tailor the size of the reticule to match your camera and lens setup, allowing you to visualize your framing easily.

If you lose sight of where the mount is pointing in Stellarium, simply press `SPACE`, and the view will immediately pan to your reticle.

### Sync Co-ordinates
On Windows, you can help improve the aim of the Benro Polaris by Syncing with a known object in the sky. 
1. Using the Benro Polaris App, aim the telescope with the known object in the center of the eyepiece or image
2. Find the know object in Stellarium Desktop and select it.
3. Press `Ctrl+0` to bring up the `Slew Telescope To` dialog and click `Sync`.
4. The Reticle should imediately shift to your selected target
5. This amount will now offset all RA/Dec coordinates sent and received from Polaris.

To reset the RA/Dec Offset, restart the driver. Refer to Section 3 below for a better understanding of how this works.


## 3. Improving Aiming Accuracy
This section is optional and only provided to give you insight into the design and inner workings of the Alpaca Benro Polaris Driver.

### Understanding RA to Alt/Az - Location/Time Offset
The Benro Polaris is primarily an Altitude/Azimuth mount as opposed to an Equatorial mount. Although the third axis does help with sidereal tracking, the primary axis is Azimuth, and the secondary axis is Altitude.

The Driver must convert RA/Dec coordinates to Alt/Az when it commands Polaris. To do this accurately, you must have the correct time and location. It retrieves the time from the system clock, and the initial location is retrieved from config.toml, with the option to sync it from Stellarium or Nina later.

```
config.toml

site_latitude = -33.8598874    # Site latitude (degrees, positive North)
site_longitude = 151.2021771   # Site longitude (degrees, positive East)
site_elevation = 39            # The elevation above sea level (meters)

```
During testing, we noticed the Benro Polaris consistently misaligns it's aiming position due to the time taken to re-engage sidereal tracking. To compensate for this, the Driver calculates where the Alt/Az position of the coordinates will be a few seconds into the future. This can also be tuned in config.toml.
```
config.toml

aiming_adjustment_time = 20    # Aiming time (in seconds) in the future.

```

### Understanding AI Learning - Alt/Az Offset
We also noticed that whenever the Benro Polaris is commanded to slew to an Alt/Az coordinate, the final position it tells us it has arrived at after sidereal tracking is re-enabled can be consistently off.

The Driver compares the final Alt/Az with the aimed Alt/Az for every GOTO command. It uses an Adaptive Integrative algorithm (hence the AI) to determine an Alt/Az offset to correct for any consistent error it notices. You can see this in the log after each GOTO command is complete.
```
Refer to Log file
```

If you notice that the Alt/Az offset is consistently the same, you can set the initial Alt/Az offset to prevent the Driver from relearning on every startup. Copy the offset from the log to the settings in config.toml. The driver does not refine the Alt/Az offset if the error is too large. This can also be set in config.toml.

And finally, you can disable the time, Alt, and Az aiming adjustments using config.toml. When disabled, any RA/Dec coordinates are converted to Alt/Az and sent straight to Polaris without any fine-tuning adjustments.
```
config.toml

aiming_adjustment_enabled = true  # Allow time, Alt and Az fine aiming adjustments
aiming_adjustment_az = 0          # The initial az aiming adjustment (in decimal degrees)
aiming_adjustment_alt = 0         # The initial alt aiming adjustment (in decimal degrees)
aim_max_error_correction = 0.5    # Ignore errors over this maximum angle (decimal degrees)

```


### Understanding Sync - RA/Dec Offset
Telescope synchronization, or ‘syncing,’ aligns your telescope with the night sky. Syncing helps the Driver understand where the telescope is pointing compared to where Polaris thinks it is.

After identifying the actual center of view (from visual observation or plate-solving), you will notice that both Stellarium and Polaris may have it wrong. Syncing will help correct anything upstream of the Driver.

As soon as you select the actual object at the center of view and press Sync, you will notice Stellarium immediately correct itself and position the reticule over the target you have synced with. Nothing is sent to Polaris, as the sync is purely within the Driver.

The Driver remembers an RA/Dec offset to add to all coordinates sent to Polaris. It subtracts this offset every time Polaris tells the Driver where it thinks it is pointing. You will see this offset in the logs when the Driver converts from ASCOM RA/Dec coordinates to Polaris RA/Dec coordinates.

This should not be confused with polar alignment, which is aligning your telescope's understanding of where the celestial polar axis is oriented relative to the Benro Polaris. Polar alignment is vital for sidereal tracking and minimizing the movement of stars during longer exposures.

### Understanding Plate Solving
And finally plate solving is a game changer. I guarantee you will have a smile on your face the first time Nina successfully plate solves and automatically moves the Benro Polaris to point at what you asked it to point at in the first place. With spot on accuracy and validity.

Refer [Using Nina](./nina.md) for more on Plate Solving.
