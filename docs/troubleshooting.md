[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarim](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Troubleshooting
### Cannot start the Benro Polaris.
There is a known issue with the recommended Benro Polaris device startup procedure. "Power On. In the off state, double press and hold the [Power Button], and release it after hearing “beep beep beep” three times to turn on the device. ".  Its worse than an old lawnmower at starting. If your device doesnt start, try the following:
1. Remove Power cable - Dont have the Benro Polaris charging, while trying to start.
2. Send to Park - use a Long Press to send the Benro Polaris to the parked position and ensure Power LED is off.
3. Short Press - Every second or so (but no faster), until Power LED is illuminated.
4. Long Press - As soon as its illuminated, do a long press, releasing after "beep, beep beep".
   
### Cannot see "`communications init... done`" in the log.
* Use the Alpaca Benro Polaris Driver log window to help diagnose your problem. The messages aim to help point you in the right direction. The driver will continue to retry connecting until you have resolved any issues.
* Confirm the Benro Polaris is in Astro Mode.
* Confirm the Benro Polaris Compass and Star Alignment steps are complete.
* Confirm the Benro Polaris App is still running (we hope to remove this requirement).
* Confirm your Cammera hasn't gone to power save mode.
* Confirm the mini-PC has connected with the polaris-XXXXX hotspot. It should look like the following:
<img style="display: block; margin: auto;" width="362" height="222" src="images/abp-troubleshoot-wifi1.png"> 

  
### Cannot see any log message except two `INFO ==STARTUP==` lines
* Check which Wifi adapter is being used. There is a known issue with the Mele Quieter 4C not being able to connect to the Polaris Wifi. Do not use the MediaTek RZ616 Wi-Fi 6E 160MHz (Driver version 3.3.0.595) built in Wifi Adapter. Use the [TP-Link AC600 USB WiFi Adapter](https://www.amazon.com/wireless-USB-WiFi-Adapter-PC/dp/B07P5PRK7J/) instead.
* Check your IP Configuration using a Command Prompt to run `ipconfig.exe`. Ensure your Mini-PC has a valid IP Address from the Benro Polaris DHCP server. It should look like the following:
<img style="display: block; margin: auto;"  src="images/abp-troubleshoot-wifi2.png"> 


### Connection from Mini-PC to Polaris Wifi drops out
* Check that the Benro Polaris App is connected and running. When the App closes the Benro Polaris will drop its WiFi hotspot. Unforuntately you need to keep the app running, within range of the Benro Polaris, to keep the Polaris WiFi up, so that ABP can connect.
* Check for RF interference. eg. Turn off your microwave in the kitchen.
* Check for RF signal strength. Move your remote desktop machine closer to the mini-pc. 
* Check resouce usage on mini-PC. Ensure it has plenty of free ram and CPU.


### Cannot connect Remote Desktop to Mini-PC
* Check Mini-PC state. Reconnect a monitor and Keyboard to the Mini-PC and check that it is up and running. Windows Updates can be delivered every month that may effect the state of the device.
* Check IP connectivity. From a command prompt, use `ping <hostname>` to ensure you have IP connectivity and DNS lookup to your Mini-PC. You may find using the Mini-PC's `IP4-address` in Remote Desktop rather than `<hostname>` may make it easier to connect.
* Check the Mini-PC Hotspot is connected first. You can unplug the TPlink to force the Nina hotspot to use the embedded Wifi of the Mele. Once you have connected to the mini-pc via Remote Desktop, re-plug in the TPLink.
* Check that you have not dropped connection to the Mini-PCs WiFi hotspot.

### Cannot connect StellariumPLUS to ABP
* Check IP connectivity. You need to run StellariumPLUS on a mobile device that can communicate with the ABP driver. We do not recommend running StellariumPLUS on the same device as the Benro Polaris App. Unfortunately the Benro Polaris App takes over the phones WiFi and forces it to talk only the the BP. When in use it doesnt allow connectivity to your home network or Mini-PC hotspot. We suggest using Stellarium Plus on a separate iPad.

### Cannot connect Nina to ABP
* Check which driver you select. Use the ASCOM Alpaca drivers over the ASCOM drivers. If you have ABP broadcasing on all interfaces (default) you may have 4 versions of it available. Don't use @160.254.253.159. 
* You can limit what IP Address the driver exposes the Alpaca Service on, by setting the field `alpaca_ip_address` in `driver/config.toml`. To limit the Alpaca Service only to applications that are running on the Mini-PC (ie no remote applications), set it the following.
```
alpaca_ip_address = '127.0.0.1' 
```

### Cannot obtain a good autofocus run with Nina?
* Check your Lens Stabilisation is off. This interfers with sidereal tracking.
* Check you Lens AutoFocus is off. This intereres with image capture.
* Check for Lens Cap not removed. Not kidding.
* Check for clouds.
* Check for haze or smoke.
* Check for occulusion by trees or buildings.
* Check for that you are close to focus before starting a Nina Focus run.

