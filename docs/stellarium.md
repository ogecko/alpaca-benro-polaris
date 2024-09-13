[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarim](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Using Stellarium with Benro Polaris
## Telescope Control Compatibility
The APB Driver supports both the Alpaca ASCOM and SynScan protocols. This opens up a wide range of Telescope Control applications that are now compatible with the Benro Polaris. Out of all those listed we recommend Stellarium PLUS and Stellarium Desktop.

### Supported and Tested

* Stellariium Mobile PLUS (IOS, Android)- paid, telescope control via SynScan protocol.
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

## 1. Using Stellarium Mobile PLUS
Stellarium Mobile PLUS is ideal for use on a tablet or mobile phone, either Android or IOS. It includes more features than the free Stellarium Web and the free Stellarium Mobile offerings.

### Connecting to the Driver
Stellarium Plus connects to the driver over the network using SynScan protocol. It is the simplest to setup, and you only need to do this once. To connect Stellarium PLUS: 
1. Select the Hamburger menu from the top left
2. Select Observing Tools > Telescope Control
3. Toggle it off/ and on to bring up the popup bottom left
4. In the Host field, enter the IP Address of the ABP Driver.
5. In the Port field, leave a default of 10001.
6. Click the Link toggle to start connection.
7. Stellarium will attempt to connect to the driver. 
8. Choose Sync Location (Stellarium site alt/az will be sent to the driver)
9.  Choose Sync Time (Stellariam will send its time to the driver)

A Yellow Not Aligned flag will indicate the driver has not complete initialisation of its communications with the Benro Polaris and may still be out of alignment. 
    
### Goto Co-ordinates
Commanding the Benro Polaris to move is as simple as Selecting the Target Object then clicking the Goto Icon. The icon will flash red while the mount is slewing and while it is re-establishing sidereal tracking.

### Changing Field of View
As the telescope sweeps across the sky you will see a reticule marking its path. You can tailor the size of the reticule to match your camera and lens setup. This allows you to eailsy visualise your framing.

If you lose site of where the mount is pointing in Stellarium simply click this second icon and the view will imediately pan to your reticle.

### Move Axis Commands
The third icon on the Telescope Popup allows you to move the primary and secondary axis of the Benro Polaris. 

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

Note that Move Axis in Nina allows you to enter fractional speeds. Due to Benro Polaris these only have effect from 5.1 to 9.0 (ie for the Benro Polaris Fast Move commands).

### Sync Co-ordinates
You can help improve the aim of the Benro Polaris by Syncing with a known object in the sky. 
1. Aim the telescope with the known object in the center of the eyepiece using the Move Axis commands.
2. Find the know object in Stellarium and select it.
3. Tap the Sync icon on the Telescope Control Popup. 
4. The Reticle should imediately shift to your selected target.
5. All RA/Dec coordinates sent and received from Polaris will now be offset by this amount.

To reset the RA/Dec Offset, simply tap the disconnect and reconnect icons on the Telescope Control Ppopup in Stellarium. For more understanding of how this works refer to Section 3 below.

## 2. Using Stellarium Desktop
Stellarium Desktop has the broadest set of features of all versions of Stellarium. It is very flexible, allowing you to customise what is shown (deep sky objects, satelites, meteor showers, planets, etc) and how it is shown (annotations, projections, landscapes, etc), including numerous sky surveys. 

It includes an extensize Whats Up Tonight tool to allow you to plan targets for imaging. It also includes an extensive library of plug-ins which add more functionality to the application. Its a very powerful platform.


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
Unfortunately Stellarium Desktop does not include native Alpaca support. You will need to install the ASCOM Platform if you havent already. After the ASCOM platform has been installed you can add an ASCOM Telescope by using the following procedure:
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
Commanding the Benro Polaris to move is as simple as Selecting the Target Object then pressing `Ctrl+1` on Windows. 

You can also bring up the `Slew Telescope To` dialog by preessing `Ctrl+0`. This dialog allows you to 
* Manually enter the co-ordinates
* Select the Current Object
* Select the Center of the Screen
* Select from a customisable list of Targets
* Initiate the Slew of the Benro Polaris.

### Changing Field of View
On Windows, as the telescope sweeps across the sky you will see a reticule marking its path. You can tailor the size of the reticule to match your camera and lens setup. This allows you to easily visualise your framing.

If you lose site of where the mount is pointing in Stellarium simply press `SPACE` and the view will imediately pan to your reticle.

### Sync Co-ordinates
On Windows, you can help improve the aim of the Benro Polaris by Syncing with a known object in the sky. 
1. Aim the telescope with the known object in the center of the eyepiece using the Benro Polaris App move primary and secondary "joystick"
2. Find the know object in Stellarium Desktop and select it.
3. Press `Ctrl+0` to bring up the `Slew Telescope To` dialog and click `Sync`.
4. The Reticle should imediately shift to your selected target
5. All RA/Dec coordinates sent and received from Polaris will now be offset by this amount.

To reset the RA/Dec Offset, restard the driver. For more understanding of how this works refer to Section 3 below.


## 3. Improving Aiming Accuracy

### Understanding AI Learning - Alt/Az Offset

### Understanding Sync - RA/Dec Offset
Telescope synchronization, or ‘syncing,’ is the process of aligning your telescope with the night sky. This ensures that when you select an object to view, your telescope accurately points to it. Syncing helps your telescope’s computer system understand its orientation relative to the stars.

### Understanding Plate Solving

### Understanding Polar Alignment
