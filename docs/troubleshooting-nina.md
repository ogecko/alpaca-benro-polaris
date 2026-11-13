# NINA Troubleshooting
Problems using NINA with the Alpaca Driver, including remote access to a MiniPC running NINA, choosing the mount, autofocus, plate solving and connecting cameras.

See [Troubleshooting](./troubleshooting.md) for the other guides, and the [FAQ](./faq.md) for common questions.

## N1 - Remote Desktop Fails

* There are a range of remote desktop applications avalable which you might want to try:
    * Microsoft Remote Desktop - Free with Windows 11 Pro. Some testers have had issues connecting via MS Remote desktop. I've been using it quite successfully.
    * AnyDesk - "Best remote desktop solution for occasional users" - Techradar. 
        Successfully used by a beta tester.
    * Splashtop - "Powerful remote desktop with impressive features" - Techradar. I've used this on my home network successfully.
    * TeamViewer - "Best remote PC software for cross-platform compatibility" - Techradar.
    * RemotePC - Short free trial.
    * LogMeIn - Lacks a free trial.
    * Zoho Assist - Free tier very limited.
* When using AnyDesk and certain other programs, you might need to use an [HDMI Dummy Plug](https://www.amazon.com/dp/B0CKKLTWMN) to get video output from the mini PC if a monitor is not connected. Microsoft Remote Desktop Client does not require this, but it may not be available for some mobile devices.

## N2 - Still Can't Connect

* Windows Updates can be delivered every month that may effect the state of the device.
* Check Mini-PC state. Reconnect a monitor and Keyboard to the Mini-PC and check that it is up and running. 

## N3 - No Internet Access

* This type of configuration is more challenging and can be confusing, but it is possible.
* There are two Wifi Hotspots in this configuration, the BP Hotspot and the Mini-PC Hotspot. 
* Check that your laptop has not dropped connection to the Mini-PCs hotspot.
* Check IP connectivity. From a command prompt, use `ping <hostname>` to ensure you have IP connectivity and DNS lookup to your Mini-PC. 
* You may find using the Mini-PC's `IP4-address` in Remote Desktop rather than `<hostname>` may make it easier to connect.
* Check that the MiniPC Hotspot is not using the TPLink. You can unplug the TPlink to force the MiniPC hotspot to use the embedded Wifi of the Mele. 
* Once you have connected to the Mini-PC via Remote Desktop, then re-plug in the TPLink, to allow the Alpaca Driver to use it to connect with the BP Hotspot.

## N4 - Which Mount to Select

* The Alpaca Driver defaults to broadcasting `ASCOM Alpaca` services on all network interfaces on the MiniPC. 
* If you have the ASCOM Platform installed, Nina will also detect all the `ASCOM direct` interfaces to the Alpaca Driver. 
* We recommend connecting to the Alpaca Driver via `ASCOM Alpaca` services rather than `ASCOM`. Choose one of the Mounts under `ASCOM Alpaca`.
* You can limit what IP Address the driver exposes the `ASCOM Alpaca` Service on, by setting the field `alpaca_restapi_ip_address` in `driver/config.toml`. 
* To limit the Alpaca Service only to applications that are running on the Mini-PC (ie no remote applications), set it the following.
```
alpaca_restapi_ip_address = '127.0.0.1' 
```

## N5 - Poor Autofocus

* Check your Lens Stabilisation is off. This interfers with sidereal tracking.
* Check you Lens AutoFocus is off on the Lens and Camera Body. If left on this may cause the camera focusing system to hunt interering with the image capture process.
* Check for Lens Cap not removed. Not kidding.
* Check for clouds.
* Check for haze or smoke.
* Check for occulusion by trees or buildings.
* Check for that you are close to focus before starting a Nina Focus run.

## N6 - Plate Solving Fails

* Check you are in Focus
* Check to make sure you Camera Pixel Size and Telescope Focal Length is set correctly in Nina's Options > Equipment tab, including any reducer or extender. Plate solving wants an approximately correct field of view as input and frequently fails if not set to the right values. 
* The focal_length and focal_ratio in config.toml are provided because of the ASCOM standard, but are not used by Nina. You do not need to update these when you change lenses.
* When using plate-solving to do the first polar alignment of the Polaris, you need to set the exposure length short so that you dont get star trails. If it is too short you will not get enough stars for the plate solve to work. To overcome this trade off, do a compas alignment so that the Polaris is at least roughly polar aligned.
* Check if you are using any filters. Using a narrow band filter on the camera, like the L-Ultimate Optolong HaOIII filter, can make plate solving more challenging for ASTAP.
* Check you have downloaded the relevant STAR databases. For 200mm lens and less you may need to download the [Wide field STAR database G05](https://www.hnsky.org/astap.htm)

## N7 - Sony Camera
Some later models of Sony cameras (e.g., Sony Alpha 7R IV) are not recognized by the Sony Plug-in that is included with Nina. 
To resolve this:

* You can download more up to date ASCOM Sony drivers from  the [ASCOMSonyCameraDriver GitHub repository](https://github.com/dougfor.../ASCOMSonyCameraDriver/releases).

Alternatively, you can use the following procedure to try and get the Nina Driver to recognise your camera:

* Attach your camera via USB. Configure as you would to connect to the Polaris.
* Turn on your camera.
* Enter Device Manager in the Windows desktop search bar.
* Click on the Device Manager icon to open the Device Manager.
* Check for the linr `libusbK Usb Devices`.
* If the line does not exist, close the Device Manager. You are correctly configured.
* If the line `libusbK Usb Devices` exists:
    * Left-click on the entry to expand the entry. You should now see Sony Remote Control Devices.
    * Right-click on `Sony Remote Control Devices` and select `Update Driver`.
    * Select `Browse my computer for drivers`.
    * Select `Let me pick from a list of available drivers on my computer`.
    * Left-click on `MTP USB Device`.
    * Your driver should now update.  NOTE: Your camera is now listed under `Portable device`. Other software may not function correctly with the Device Manager configured this way. 
    * You can change back to the original setting by following these steps and selecting `libusbK Usb Devices` as the new driver instead of `MTP USB Device`.

Hopefully, Nina will now connect to your camera.

## N8 - Nikon D850
There is a known issue with connecting a D850 via USB2 with Nina. Try connecting the Nikon D850 via a USB3 or USB-C port. See this [Redit Post on the D850 and Nina](https://www.reddit.com/r/AskAstrophotography/comments/169yzsd/nikon_d850_will_not_connect_to_nina/) for more details.

## N9 - Stellarium in NINA
The Nina Sky Atlas has a feature to allow you to get target coordinates from your configured Planetarium Software. You can set the Options / Planetarium software as Stellarium with a given Host IP Address and Port. 

You need to configure Stellarium, adding the Remote Control Plug-in, enabling it to run at startup. Restarting Stellarium allows you to configure the plug-in to automatically enable the server on startup. 

The Remote Control Plug-in defaults to port 8090. This port can conflict with other software you may have on your computer eg Wonderware RecoverIt. If you cannot get Nina to retreive the coordinates from Stellarium try setting the port number to 8091 in both Stellarium and Nina. This may fix the integration between Nina and Stellarium.
