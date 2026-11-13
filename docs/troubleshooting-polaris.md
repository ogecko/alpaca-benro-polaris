# Benro Polaris Troubleshooting
Problems with the Benro Polaris itself and the Benro app, including starting and charging the Polaris, its Wi-Fi and password, tracking quality and star alignment.

See [Troubleshooting](./troubleshooting.md) for the other guides, and the [FAQ](./faq.md) for common questions.

## B1 - Polaris Won't Start
There is a known issue with the recommended Benro Polaris device startup procedure. "Power On. In the off state, double press and hold the [Power Button], and release it after hearing “beep beep beep” three times to turn on the device. ".  Its worse than an old lawnmower at starting. If your device doesnt start, try the following:

1. Remove Power cable - Dont have the Benro Polaris charging, while trying to start.
2. Send to Park - use a Long Press to send the Benro Polaris to the parked position and ensure Power LED is off.
3. Short Press - Every second or so (but no faster), until Power LED is illuminated.
4. Long Press - As soon as its illuminated, do a long press, releasing after "beep, beep beep".

Another word of caution. Do not travel with the Astro USB cable or Camera USB Cable plugged into the Benro Polaris. There is a chance that movement within your bag may damage the cable. This can even lead to damage of the Benro Polaris and costly repairs.

## B2 - Benro App Can't Connect
Sometimes the BP App cannot search and connect to the BP over Bluetooth or Wifi. The Searching for device might list your device in white but it never turns green or connects or shows a green check-mark.

* Fully exit close the BP App on your phone.
* Reset all Bluetooth and Wifi communications on your phone. Easiest way to do this is to toggle `Airplane/Flight Mode`  on and off. 
* Restart the BP App and it should find and connect to your BP.

## B3 - Poor Sidereal Tracking
As an Alt/Az mount, the leveling of the Benro Polaris Tripod Head is a critical factor in the accuracy of your star tracking. To adjust the Polaris so it is as level as possible：

* Double-tap both virtual joysticks on the BP app to center the Polaris axes.
* Place a circular spirit level on top of the Astro Kit's quick-release plate and adjust the tripod to achieve a level of ±0.3 degrees or better.
* A [HACCURY Luminous 1° Round level bubble](https://www.aliexpress.com/item/4000457838875.html) can help you achieve accurate leveling. 
* A [Sunwayfoto DYH-68B Leveling Base](https://www.amazon.com/Sunwayfoto-DYH-68B-Profile-Leveling-Butterfly/dp/B09ZT3HVMN/) and [LEOFOTO
QS-50K 50mm Quick Link Set](https://www.amazon.com/Leofoto-QS-50K-Plates-Tripod-Release/dp/B0981C36RX) can ease the leveling process AND as act as a standoff to provide extra clearance for the Benro Polaris knobs!

## B4 - Can't Join Home Wi-Fi
The current firmware of the Benro Polaris does not allow connection to other WiFi networks. It can only host its own Wi-Fi hotspot.

This is no longer a limitation. The Alpaca Driver can serve as a proxy for the Polaris. It is capable of connecting to both the Polaris Wi-Fi Hotspot and your home Wi-Fi network. This allows you to manage the Polaris from any device connected to your home Wi-Fi, including an iPad, a phone, a desktop, or a laptop.

## B5 - Battery Won't Charge
The Polaris may have a design flaw that causes it to reject high-speed or smart chargers when the battery is in a low 1% state. It requires a slow, steady 5V source to restore sufficient power for the charging circuit to work correctly. Once it gets past that initial threshold, you can switch to a faster charger if needed. To fix the issue:

- Use a basic 5V 2.4A charger or an old battery pack via USB-A.
- Avoid smart or high-speed USB-C PD chargers initially.
- Let it charge without interruptions.
- Once it’s above 10–20%, you can switch to your usual power source.


## B6 - Resetting the Password
To reset the password of your Benro Polaris

1. Download the [Password Resetting Package](https://www.benro.com/en/downloads/page/polaris-reset-password.html) and place on to your SD card; 
2. Insert your SD card into Polaris, and power cycle the Polaris. 
3. When the Polaris powers up, it will read the SD card and reset your password.
4. After resetting your password, please take the SD card out and delete the password resetting package from the SD card.


## B7 - Benro Polaris Manual
The user manual can be found at the following link - [Polaris User Manual English](https://resource.benro.com/assets/benro/manual/polaris/polaris_user_manual_en.pdf).

## B8 - Star Alignment Fails
If the **Single Star Alignment** does not complete successfully, the Polaris may be stuck in an unknown connection state. You can identify this by using the Alpaca Pilot Connect Page. Click on the **Skip** button next to **Single Star Alignment**. If the status momentarily turns green, then turns back to red, it is likely you have this problem. The following recovery steps may help clear the connection:

1. Power-cycle the Polaris
    * Turn the Polaris off.
    * Wait at least 2 minutes.
    * Turn the Polaris back on and retry the Single Star Alignment.
2. Force a fresh network connection
    * Change your Wi-Fi connection to the Polaris from automatic addressing to Manual IPv4.
    * Use the following settings:
        * IP Address: 192.168.0.5
        * Subnet Mask: 255.255.255.0
    * Reconnect and retry the alignment process.

This forces the Polaris to establish a new clean connection, which may clear the stuck state.
