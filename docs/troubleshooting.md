[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarim](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Troubleshooting
### Cannot connect Mini-PC/ABP to Polaris Wifi
* Check that the Benro Polaris App is connected and running. When the App closes the Benro Polaris will drop its WiFi hotspot. Unforuntately you need to keep the app running, within range of the Benro Polaris, to keep the Polaris WiFi up, so that ABP can connect.
* Check which Wifi adapter is being used. There is a known issue with the Mele Quieter 4C not being able to connect to the Polaris Wifi. Use the [TP-Link AC600 USB WiFi Adapter](https://www.amazon.com/wireless-USB-WiFi-Adapter-PC/dp/B07P5PRK7J/)
* Check for RF interference. eg. Turn off your microwave in the kitchen.
* Check for RF signal strength. Move your remote desktop machine closer to the mini-pc. 
* Check resouce usage on mini-PC. Ensure it has plenty of free ram and CPU.


### Cannot connect Remote Desktop to Mini-PC
* Check the Mini-PC Hotspot is connected first. You can unplug the TPlink to force the Nina hotspot to use the embedded Wifi of the Mele. Once you have connected to the mini-pc via Remote Desktop, re-plug in the TPLink.
* Check that you have not dropped connection to the Mini-PCs WiFi hotspot.
 
### Cannot connect Nina to ABP
* Check which driver you select. Use the ASCOM Alpaca drivers over the ASCOM drivers. If you have ABP broadcasing on all interfaces (default) you may have 4 versions of it available. Don't use @160.254.253.159. You can limit what IP it uses by setting the field `alpaca_ip_address` in `driver/config.toml` to something like.
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

