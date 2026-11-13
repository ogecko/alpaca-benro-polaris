# Stellarium Troubleshooting
Problems connecting Stellarium PLUS and Stellarium Desktop to the Alpaca Driver, and using Stellarium over Remote Desktop.

See [Troubleshooting](./troubleshooting.md) for the other guides, and the [FAQ](./faq.md) for common questions.

## S1 - Stellarium PLUS
There are three approaches to connect StellariumPLUS to the Alpaca Driver, depending on your setup scenario.

* Scenario A: The Alpaca Driver device connects to Polaris Hotspot only.
    * Connect your phone to the Polaris Hotspot.
    * In Stellarium's Observing Tools Setup, enter a Network Host of `192.168.0.3` 
    * You may need to disable Mobile Data on your phone to get this to work.
* Scenario B: The Alpaca Driver device connects to Polaris Hotspot and your Home Wifi.
    * Check that the BP App is closed. This frees the phones Wifi from the Polaris Wifi. 
    * Check that your phone does not autoconnect to the Polaris Wifi.
    * Connect your phone to your Home Wifi.
    * In Stellarium's Observing Tools Setup, enter a Network Host of `192.168.X.XXX`
    * This address needs to match the IP address of your Alpaca Driver machine on your Home Wifi.
* Scenario C: The Alpaca Driver device connects to Polaris Hotspot and has its own MiniPC Hotspot.
    * Check that the BP App is closed. This frees the phones Wifi from the Polaris Wifi.
    * Check that your phone does not autoconnect to the Polaris Wifi.
    * Connect your phone to the MiniPC Hotspot.
    * In Stellarium's Observing Tools Setup, enter a Network Host of `192.168.X.XXX`
    * This address needs to match the IP address of your Alpaca Driver machine on your MiniPC Wifi.

## S2 - Still Can't Connect

* Check IP connectivity. You must run StellariumPLUS on a mobile device that can communicate with the Alpaca Driver. Use a free mobile Ping app to check that you can ping the Alpaca Driver device. If you cannot ping, then check that you are not using the phone's mobile data, that you are within range of your router's Wi-Fi signal, and that your phone is connected to your home Wi-Fi.
* Check the StellariumPLUS Host field on the Observing Tools settings popup. This needs to be set to the Alpaca Driver's IP address. Do not use 127.0.0.1 Loopback. 
* Check stellarium_telescope_ip_address in config.toml. This can be left as its default '' to make the Driver serve the SynScan protocol on any network adapter it can find. If you want to limit the IP address servered by the Driver, you can set this to the IP address of the Mini-PC on your home network. 

## S3 - ASCOM Greyed Out

* Stellarium Desktop v24.3 for Windows has two installable versions depending on a third party library it uses, called Qt. 
* The Stellarium Desktop v24.3 Qt6 version no longer has ASCOM drivers enabled. 
* We recommend you install Stellarium Desktop v24.3 Windows x86_64 **Qt5** Windows 7+ version.
* If you installed the incorrect version, simply uninstall it and reinstall the version mentioned above.
  
## S4 - Desktop Freezes

* Check fps settings. Stellarium's default is a crazy 10000 fps. We suggest reducing the default settings in the following file `C:\Users\Nina\AppData\Roaming\Stellarium\config.ini`, where Nina is replaced with your User name.
    ```
    [video]
    ...
    maximum_fps                               = 10
    minimum_fps                               = 10
    ...
    ``` 
