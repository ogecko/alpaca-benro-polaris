[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarium](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Troubleshooting
### B1 - Cannot start the Benro Polaris Device.
There is a known issue with the recommended Benro Polaris device startup procedure. "Power On. In the off state, double press and hold the [Power Button], and release it after hearing “beep beep beep” three times to turn on the device. ".  Its worse than an old lawnmower at starting. If your device doesnt start, try the following:
1. Remove Power cable - Dont have the Benro Polaris charging, while trying to start.
2. Send to Park - use a Long Press to send the Benro Polaris to the parked position and ensure Power LED is off.
3. Short Press - Every second or so (but no faster), until Power LED is illuminated.
4. Long Press - As soon as its illuminated, do a long press, releasing after "beep, beep beep".

Another word of caution. Do not travel with the Astro USB cable or Camera USB Cable plugged into the Benro Polaris. There is a chance that movement within your bag may damage the cable. This can even lead to damage of the Benro Polaris and costly repairs.

### B2 - Cannot connect BP App to the Benro Polaris Device
Sometimes the BP App cannot search and connect to the BP over Bluetooth or Wifi. The Searching for device might list your device in white but it never turns green or connects and shows a green check-mark.
* Fully exit close the BP App on your phone.
* Reset all Bluetooth and Wifi communications on your phone. Easiest way to do this is to toggle `Airplane/Flight Mode`  on and off. 
* Restart the BP App and it should find and connect to your BP.
   
### C1 - Cannot see "`communications init... done`" in the log.
* Use the Alpaca Benro Polaris Driver log window to help diagnose your problem. The messages aim to help point you in the right direction. The driver will continue to retry connecting until you have resolved any issues.
* Confirm the Benro Polaris is in Astro Mode.
* Confirm the Benro Polaris Compass and Star Alignment steps are complete.
* Confirm the Benro Polaris App is still running (we hope to remove this requirement).
* Confirm your Cammera hasn't gone to power save mode.
* Confirm the mini-PC has connected with the polaris-XXXXX hotspot. It should look like the following:
<img style="display: block; margin: auto;" width="362" height="222" src="images/abp-troubleshoot-wifi1.png"> 

  
### C2 - Cannot see any log message except two `INFO ==STARTUP==` lines
* Check your device doesnt have any IT policy to not allow connecting to an open WIFI like the Polaris Hotspot.
* Check which Wifi adapter is being used. There is a known issue with the Mele Quieter 4C not being able to connect to the Polaris Wifi. Do not use the MediaTek RZ616 Wi-Fi 6E 160MHz (Driver version 3.3.0.595) built in Wifi Adapter. Use the [TP-Link AC600 USB WiFi Adapter](https://www.amazon.com/wireless-USB-WiFi-Adapter-PC/dp/B07P5PRK7J/) instead.
* Check your IP Configuration using a Command Prompt to run `ipconfig.exe`. Ensure your Mini-PC has a valid IP Address from the Benro Polaris DHCP server. It should look like the following:
  
<img style="display: block; margin: auto;"  src="images/abp-troubleshoot-wifi2.png"> 


### C3 - Connection from Mini-PC to Polaris Wifi drops out
* Check that the Benro Polaris App is connected and running. When the App closes the Benro Polaris will drop its WiFi hotspot. Unforuntately you need to keep the app running, within range of the Benro Polaris, to keep the Polaris WiFi up, so that ABP can connect.
* Check for RF interference. eg. Turn off your microwave in the kitchen.
* Check for RF signal strength. Move your remote desktop machine closer to the mini-pc. 
* Check resouce usage on mini-PC. Ensure it has plenty of free ram and CPU.

### C4 - Still cannot get communications with Polaris Wifi
To further help diagnose communication problems between ABP and the Polaris, you can use `Telnet` or `PuTTY` to directly connect to the Polaris. This will isolate whether the problem is ABP related or not.

On Win11:
* Use the following link to [Download PuTTY](https://www.putty.org/) (a telnet client) to your device running the Driver.
* Select the 64-bit x86 version for the Windows installer.
* Double click on the file you downloaded to install PuTTY.
* Perform the normal BP App setup (a) Search for Device (b) Connect to polaris_xxxxxx (c) Select Atro Mode (d) Align Compass (e) Align Star (f) Confirm.
* Connect the Device running ABP to the Polaris Wifi Hotspot.

<img style="display: block; margin: auto;" width="362" height="222" src="images/abp-troubleshoot-wifi1.png"> 

* Run the PuTTY app.
  
![PuTTY Setup](images/abp-putty1.png)

* Enter `192.168.0.1` into the HostName (or IP address) field.
* Enter `9090` into the Port field.
* Select Connection Type `Other` and drop down `Telnet`.
* Click `Open`
* Select `Yes` when asked by User Account Control, Do you want to allow this app to make changes to your device? This opens the firewall to allow PuTTY to communicate with BP.

The PuTTY application should show a window with the raw communications from the Benro Polaris. If your connection is working it should like the following.

![PuTTY Setup](images/abp-putty2.png)

### C5 - No Telnet/PuTTY communications with Polaris Wifi
If you cannot see the raw communications scrolling in PuTTY then there is a problem connunicating with your device independant of Alpaca Benro Polaris.
* Check you are not running AntiVirus Software that may block open Wifi Connections
* Check you do not have an IT or Windows policy blocking open Wifi Connections.
* Check for IP connectivity to the Polaris by using a Command Window to ping the Benro Polaris.
```
C:\Users\Astro> ping 192.168.0.1
Reply from 192.168.0.1: bytes=32 time=1ms TTL=64
Reply from 192.168.0.1: bytes=32 time=2ms TTL=64
Reply from 192.168.0.1: bytes=32 time=2ms TTL=64
Reply from 192.168.0.1: bytes=32 time=2ms TTL=64

Ping statistics for 192.168.0.1:
    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 1ms, Maximum = 2ms, Average = 1ms
C:\Users\Astro> 
```
* If the ping does not respond within a few milliseconds, go back through C1-C3 to double check the setup. 


### N1 - Cannot connect Nina to ABP
* Check which driver you select. Use the ASCOM Alpaca drivers over the ASCOM drivers. If you have ABP broadcasing on all interfaces (default) you may have 4 versions of it available. Don't use @160.254.253.159. 
* You can limit what IP Address the driver exposes the Alpaca Service on, by setting the field `alpaca_ip_address` in `driver/config.toml`. To limit the Alpaca Service only to applications that are running on the Mini-PC (ie no remote applications), set it the following.
```
alpaca_ip_address = '127.0.0.1' 
```

### N2 - Cannot obtain a good autofocus run with Nina?
* Check your Lens Stabilisation is off. This interfers with sidereal tracking.
* Check you Lens AutoFocus is off. This intereres with image capture.
* Check for Lens Cap not removed. Not kidding.
* Check for clouds.
* Check for haze or smoke.
* Check for occulusion by trees or buildings.
* Check for that you are close to focus before starting a Nina Focus run.

### N3 - Cannot plate solve with Nina and ASTAP?
* Check you are in Focus
* Check to make sure you telescope focal length is set correctly in equipment options, including any reducer or extender. Plate solving wants an approximately correct field of view as input and frequently fails if not set to the right values.
* Check if you are using any filters. Using a narrow band filter on the camera, like the L-Ultimate Optolong HaOIII filter, can make plate solving more challenging for ASTAP.### R1 - Cannot connect Remote Desktop to Mini-PC
* Check Mini-PC state. Reconnect a monitor and Keyboard to the Mini-PC and check that it is up and running. Windows Updates can be delivered every month that may effect the state of the device.
* Check IP connectivity. From a command prompt, use `ping <hostname>` to ensure you have IP connectivity and DNS lookup to your Mini-PC. You may find using the Mini-PC's `IP4-address` in Remote Desktop rather than `<hostname>` may make it easier to connect.
* Check the Mini-PC Hotspot is connected first. You can unplug the TPlink to force the Nina hotspot to use the embedded Wifi of the Mele. Once you have connected to the mini-pc via Remote Desktop, re-plug in the TPLink.
* Check that you have not dropped connection to the Mini-PCs WiFi hotspot.

### S1 - Cannot connect StellariumPLUS to ABP
* Check IP connectivity. You need to run StellariumPLUS on a mobile device that can communicate with the ABP driver. We do not recommend running StellariumPLUS on the same device as the Benro Polaris App. Unfortunately the Benro Polaris App takes over the phones WiFi and forces it to talk only the the BP. When in use it doesnt allow connectivity to your home network or Mini-PC hotspot. We suggest using Stellarium Plus on a separate iPad.
* Check StellariumPLUS Alignment Flag. StellariumPLUS will show your telescope as Not Aligned whenever the ABP driver cannot communicate with the Benro Polaris.

