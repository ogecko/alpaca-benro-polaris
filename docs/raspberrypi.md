[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Raspberry Pi Setup Guide
[Versions](#which-pi-should-i-buy) | 
[Image Creation](#install-the-raspberry-pi-os-image) | 
[Alpaca Installation](#install-pre-requisites-and-the-alpaca-driver) | 
[Setup.sh Reference](#setupsh-command-reference) | 
[Troubleshooting](#troubleshooting-the-raspberry-pi)


## Overview

![Pi](images/abp-hardware-pi.png)

Raspberry Pi are small, low-cost computers that can run the Alpaca Driver without needing a full Windows or Mac laptop attached to your telescope setup. They can be a great solution for a low-powered, light-weight, and portable Alpaca Driver with the Benro Polaris.

You don't need any programming experience to follow this guide. Everything is done by copying pre-written commands into a terminal window and pressing Enter. Just follow the steps in order. Where a step is optional or only needed if something goes wrong, that's called out clearly.

## Which Pi should I buy?

Most Raspberry Pi models with networking support will work. Avoid Pico boards and the original Raspberry Pi Zero.
The Alpaca Driver has been validated on the following platforms:
- **Raspberry Pi Zero 2 W / WH** running Raspbian Pi OS Lite (64-bit) - Debian Trixie
- **Raspberry Pi 4 (8 GB)** running Raspberry Pi OS (64-bit) - Debian Trixie

For reference, when running advanced motion control algorithms and tracking a sidereal target, the Alpaca Driver uses roughly 22% of the CPU and 26% of the available memory on a **Raspberry Pi Zero 2 W**. This is comfortably within what even the cheapest Pi model can handle. The technical output below is just supporting evidence for that claim; you don't need to understand it.
```
(.venv) pi@alpaca:~/alpaca-benro-polaris $ top

top - 22:38:21 up  8:03,  2 users,  load average: 0.42, 0.46, 0.46
Tasks: 150 total,   2 running, 148 sleeping,   0 stopped,   0 zombie
%Cpu(s): 5.2 us,  0.6 sy,  0.0 ni, 95.6 id,  0.0 wa,  0.0 hi,  0.1 si,  0.0 st
MiB Mem :    416.1 total,     94.8 free,    204.8 used,    170.8 buff/cache
MiB Swap:    416.0 total,    387.1 free,     28.9 used.    211.3 avail Mem

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
   1942 root      20   0  608352 113132  41640 R  22.4  26.5   8:33.13 python3

```
## Install the Raspberry Pi OS Image
1. Download the Raspberry Pi Imager from the [official website](https://www.raspberrypi.com/software/)
2. Open the downloaded exe file to install the Imaging program on your PC, following it's installation instructions. Choose to run the program at the end of installation.
3. Using the Imaging program
    1. Select your Raspberry Pi Device eg Raspberry Pi Zero 2 W, then click **NEXT**
    2. Choose your Operating System as **Raspberry Pi OS (64-bit)**, then click **NEXT**. If you are using a Raspberry Pi Zero 2 W, then choose a "Lite OS" (you control it remotely rather than needing a mouse and Desktop). Select **Raspberry Pi OS (other)**, then choose **Raspberry Pi OS Lite (64-bit)**, then click **NEXT**
    3. Select your Storage Device that will hold the OS, then click **NEXT**
       > Do not format the SD card with FAT32, as Windows may automatically mount and lock it, preventing the imaging program from writing to the card. Instead, use Disk Management to carefully delete any existing partitions on the SD card before proceeding.
    4. Enter the device hostname eg **alpaca**, then click **NEXT**
    5. Choose your localisation settings, then click **NEXT**
    6. Choose your user name eg **pi** and a password, then click **NEXT**. Remember this for step 6 below.
    7. Choose your local wifi network you want the Raspberry Pi to connect to, then click **NEXT**
    8. Enable SSH. Use default password authtication, then click **NEXT**
    9.  Use default disabled Raspberry Pi Connect, then click **NEXT**
    10. Write the image to the SD Card, click **WRITE**
4. Remove the SD Card storage device and insert it into your Raspberry Pi

## Install Pre-Requisites and the Alpaca Driver
These instructions assume a fresh install of Raspberry Pi OS Lite, written using the [Raspberry Pi Imager](https://www.raspberrypi.com/software/). 

5. Prepare the Raspberry Pi Zero 2W hardware. Connect the middle MicroUSB Port to a TPLink USB Wifi Adapter using a Micro-USB to USB-A (female) cable. Connect the outer MicroUSB port to a power source, using a Micro-USB to USB-C cable, and wait for it to power up.

6. On your PC, open a **Command Prompt** or **Powershell Window** and connect to the Raspberry Pi with the following command. If you used your own `username` and `hostname` in the image above then replace `pi@alpaca` with your `username@hostname`. Enter your username's `password` when prompted. Once `ssh` connects, any commands you enter will run on the Raspberry Pi. 
    ```
    ssh pi@alpaca
    ```

7. On the Raspberry Pi, download the Alpaca Driver setup.sh script. This is a program that automatically installs everything the Alpaca Driver needs, so you don't have to do it by hand.
    ```Bash
    wget https://raw.githubusercontent.com/ogecko/alpaca-benro-polaris/dev2_2/platforms/raspberry_pi/setup.sh -O setup.sh
    ```
8. Make the script runnable, then run it.
    ```Bash
    chmod +x ./setup.sh
    ```
    ```Bash
    ./setup.sh
    ```
    Note that if you want to install a specific version of the Alpaca Driver, you can pass the Git-Hub Branch name as the first argument to setup.sh. For example, the following command will fetch the **dev2_2** branch.
    ```
    ./setup.sh dev2_2
    ```
9. The setup script will download and install all the software needed for the Alpaca Driver, setting it up to automatically start whenever the Raspberry Pi is powered on. It will also setup the Bluetooth and Wifi network of the Raspberry Pi. 

    | Wifi Mode | Description | 
    | --------- | ----------- |
    | Alpaca Station Mode (wlan0, STA)| By default the Raspberry Pi will attempt to join to an existing wireless network or router. This may be your home network or a travel router. |
    | Alpaca Hotspot Mode (wlan0, AP) | As a fallback, if it cannot join in Station Mode, the Raspberry Pi will act as its own hotspot with an SSID called `alpaca-hotspot` by default. This allows other devices to join to it directly to access Alpaca Pilot and the Alpaca Rest API. This is useful at a dark site where you may not have any internet connection.|
    | Polaris Hotspot (wlan1)| The Raspberry Pi will attempt to use the TPLink USB Wifi Adapter (wlan1) to join the Polaris Hotspot with SSID `polaris_xxxxxx`. This is used by the driver to communicate with the Polaris.|

    The setup script will first ask you to set a password for the fallback Alpaca Hotspot — press **Enter** to accept the suggested default, or type your own (must be at least 8 characters). The script then works through a series of setup tasks automatically, each printed as a line starting with `==SETUP==`. This can take a few minutes, especially the first time. When it's done, you'll see a box confirming the setup is complete.

10. Start Alpaca Pilot and Connect to the Polaris

    The Alpaca Driver should now be installed and running.

    To open Alpaca Pilot, open a web browser on any device connected to the same Wi-Fi network as the Raspberry Pi, and go to:
    ```
    http://ap.local:8080
    ```
    > The `:8080` part is required — leaving it off will fail to load the page, even though other things (like `ping`) might still work. See [P7](#p7---ping-aplocal-works-but-the-address-wont-open-in-a-browser) if you run into this.

    To connect to the Polaris using Alpaca Pilot:
    * Click **Connect** on the toolbar, then follow the steps on the Connect page.
    * Power on the Polaris and wait for it to appear in the device list (found automatically over Bluetooth).
    * Click the **Wi-Fi** button — the Raspberry Pi will automatically join the Polaris' own Wi-Fi network.

    If the Pi doesn't join the Polaris automatically, see [P1](#p1---diagnosing-wifi-and-bluetooth-network-issues) for how to check what's wrong.


## Setup.sh Command Reference
You won't normally need any of these options — running `./setup.sh` on its own (as in step 8 above) is enough for most people. They're here for reference if you want to customise something, such as adding a second known Wi-Fi network (see [P4](#p4---adding-an-additional-homesite-wifi-network)) or checking the current defaults. Running `./setup.sh -h` on your own Pi always shows the same thing, straight from the script itself:
```
Usage: setup.sh [-n sta_ssid] [-w sta_password] [-a ap_ssid] [-p ap_password] [-h] [branch]

Options:
    -n <ssid>      Wifi network SSID to prioritise in Station Mode (STA) on wlan0 --
                   creates it (using -w as its password) if it doesn't already exist,
                   otherwise just prioritises the existing one and ignores -w. Default:
                   whichever network wlan0 is currently connected to (on a freshly-
                   imaged Pi, that's already the Raspberry Pi Imager's own network) --
                   so -n is normally only needed to add an *additional* known network.
    -w <password>  Password for the network named by -n (only used when creating it).
    -a <ssid>      SSID for the Access Point (AP) fallback wlan0 broadcasts when no
                   known STA network is in range, e.g. at a dark site.
                   (default: alpaca-hotspot)
    -p <password>  Password for the AP fallback, min 8 chars for WPA2.
                   (default: prompted interactively, or 'alpacabp' if
                   not running in a terminal)
    -h             Print this help and exit.
    branch         Git branch to install, as a plain trailing argument.
                   (default: main)
```
Options can be combined, and it's always safe to re-run `./setup.sh` on a Pi that's already set up — it won't undo anything, it just re-applies (or updates) whatever you tell it. For example, to add a second Wi-Fi network *and* change the dark-site hotspot's name and password in one go:
```Bash
./setup.sh -n "OfficeWifi" -w "OfficePassword" -a "my-scope" -p "differentpass"
```

## Monitoring and Diagnostic commands

The Alpaca Driver runs automatically in the background (even after a reboot) as what Linux calls a "service" — you don't need to start it by hand. The commands below let you check on it or restart it if needed.

11. To check on or control the Alpaca Driver:
    ```Bash
    sudo systemctl status polaris-driver       # Check whether it's running
    sudo systemctl stop polaris-driver         # Stop it
    sudo systemctl start polaris-driver        # Start it again
    journalctl -u polaris-driver -f            # Watch its log messages live (Ctrl+C to stop watching)
    ```

## Troubleshooting the Raspberry Pi
The sections below (labelled P1, P2, etc.) cover specific problems people have run into. You shouldn't need any of them for a normal install — skip straight past this section unless something's actually gone wrong, and jump to whichever entry best matches what you're seeing.

### P1 - Diagnosing Wifi and Bluetooth Network Issues
Normally, connecting to the Polaris is fully automatic (see step 9 above): Bluetooth is used briefly just to find the Polaris and turn on its Wi-Fi, then the Pi joins that Wi-Fi network by itself. This section is for when that doesn't work.

**If Bluetooth won't turn on at all** (you'll see a message like `Bluetooth unavailable` in the Driver's logs):
```Bash
sudo apt install rfkill      # a small tool for checking wireless on/off switches, if not already installed
rfkill list                  # shows if Bluetooth or Wifi is switched off in software
sudo rfkill unblock bluetooth
sudo hciconfig hci0 up
```

**If the Pi can't see or join the Polaris' Wi-Fi network at all:** the Raspberry Pi's own built-in Wi-Fi often can't connect to the kind of Wi-Fi network the Polaris creates. A small USB Wi-Fi adapter plugged into the Pi (we've tested the TP-Link Archer T2U PLUS) fixes this. Plug it into the port labelled `USB` — not `PWR IN`, which is power-only and won't work. It should be recognised automatically with no extra setup. To check:
```Bash
lsusb                        # confirm the adapter shows up in this list at all
ip link show                 # look for a new network interface, e.g. wlan1, alongside the existing wlan0
```
If `lsusb` shows the adapter but no new network interface (like `wlan1`) appears, your Pi's software is too old to recognise it automatically. Building the missing piece yourself is possible but technical — see [aircrack-ng/rtl8812au](https://github.com/aircrack-ng/rtl8812au) if you want to attempt it, or ask for help.

**To check whether the Polaris' Wi-Fi network is currently visible:**
```Bash
sudo apt install iw          # a small Wifi tool, if not already installed
sudo iw wlan1 scan | grep SSID    # look for a name starting with "polaris_"
```
(Use whichever interface name showed up for your USB adapter above instead of `wlan1` if it's different.)

**To manually join the Polaris' network** — this is the exact same thing the **Wi-Fi** button in Alpaca Pilot does; running it yourself here just shows you more detail if something's going wrong. It's safe to run more than once.
```Bash
cd ~/alpaca-benro-polaris
.venv/bin/python3 driver/join_wifi.py polaris_b83c06   # replace with your Polaris' actual name, found in step 9
```
If this fails with a message containing `Insufficient privileges`, run the following once to grant the permission it needs, then try again:
```Bash
echo "pi ALL=(ALL) NOPASSWD: $(command -v nmcli)" | sudo tee /etc/sudoers.d/polaris-nmcli
sudo chmod 440 /etc/sudoers.d/polaris-nmcli
sudo visudo -cf /etc/sudoers.d/polaris-nmcli   # double-checks the change is valid before it's trusted
```

**To check the current connection status:**
```Bash
nmcli -t -f DEVICE,STATE,CONNECTION device status   # is wlan1 connected to something starting with "polaris"?
ip addr show wlan1                                  # confirm it has an address (192.168.0.100 by default)
ping 192.168.0.1                                    # confirm the Pi can actually reach the Polaris
journalctl -u NetworkManager -f                     # NetworkManager logs
```
### P2 - Diagnosing Wifi Connections
These commands show more detail about the Pi's network connections generally, useful if P1 above didn't solve things. `ip a` lists every network connection the Pi has and the address each one was given — look for `wlan0` (built-in Wifi, should show your home network's address) and `wlan1` (the USB adapter, should show `192.168.0.100` when connected to the Polaris):
```
$ ip a
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host noprefixroute
       valid_lft forever preferred_lft forever
2: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether d8:3a:dd:65:71:2e brd ff:ff:ff:ff:ff:ff
    inet 192.168.50.160/24 brd 192.168.50.255 scope global dynamic noprefixroute wlan0
       valid_lft 49228sec preferred_lft 49228sec
    inet6 fe80::da3a:ddff:fe65:712e/64 scope link proto kernel_ll
       valid_lft forever preferred_lft forever
3: wlan1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 2312 qdisc mq state UP group default qlen 1000
    link/ether e4:fa:c4:e6:de:a5 brd ff:ff:ff:ff:ff:ff
    inet 192.168.0.100/24 scope global wlan1
       valid_lft forever preferred_lft forever
```
To check if the Raspberry Pi is connected to your network router and what routes are configured:
```
$ iw dev wlan0 link
        SSID: atlas_6G
        freq: 2432.0
        RX: 52687490 bytes (340502 packets)
        TX: 55221927 bytes (349678 packets)
        signal: -28 dBm
        rx bitrate: 72.2 MBit/s
        tx bitrate: 72.2 MBit/s
        bss flags: short-slot-time
        dtim period: 1
        beacon int: 100

$ iw dev wlan1 link
Connected to 94:bb:43:c9:e1:f1 (on wlan1)
        SSID: polaris_b83c06
        freq: 2452.0
        signal: -24 dBm
        tx bitrate: 72.2 MBit/s
        bss flags: short-slot-time
        dtim period: 0
        beacon int: 15

$ ip route
default via 192.168.50.1 dev wlan0 proto dhcp src 192.168.50.160 metric 600
192.168.0.0/24 dev wlan1 proto kernel scope link src 192.168.0.100
192.168.50.0/24 dev wlan0 proto kernel scope link src 192.168.50.160 metric 600

```
To scan the wlan1 wifi interface for active SSIDs:
```
$ sudo iw wlan1 scan | grep SSID
        SSID: polaris_b83c06
        SSID: atlas_6G
        SSID: atlas_6G
        SSID: OPTUS_734AC2_5GHz
```
### P3 - Checking whether the Alpaca Driver itself is running
```
sudo systemctl status polaris-driver
```
This is the same command from step 11 above — it tells you whether the Driver program is currently running. Note that this only checks the Driver itself, not the Wi-Fi connection to the Polaris — see [P1](#p1---diagnosing-wifi-and-bluetooth-network-issues) for that.

### P4 - Adding an additional home/site Wifi network
By default, the Pi remembers one Wi-Fi network (whatever you set up in the Raspberry Pi Imager) and falls back to its own hotspot when that's not in range (see step 9 above). If you'd like it to also recognise a **second** network — for example, a different location you regularly visit that does have Wi-Fi — re-run the setup script and tell it about the new network:
```Bash
cd ~/alpaca-benro-polaris/platforms/raspberry_pi
./setup.sh -n "OtherNetworkName" -w "OtherNetworkPassword"
```
This is safe to run again on an already-set-up Pi — it won't undo anything, it just adds the new network to the list the Pi already knows about. You can repeat this for as many extra networks as you like.

If you'd rather do this by hand instead of re-running the script, here's the equivalent directly:
```Bash
sudo nmcli connection add type wifi ifname wlan0 con-name "OtherNetworkName" ssid "OtherNetworkName"
sudo nmcli connection modify "OtherNetworkName" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "OtherNetworkPassword"
sudo nmcli connection modify "OtherNetworkName" connection.interface-name wlan0 connection.autoconnect-priority 10
```

### P5 - Manually setting the Alpaca Pilot web address port
Linux normally reserves the standard web address ports (80 and 443) for programs run as an administrator, for security reasons. Since the Alpaca Driver deliberately doesn't run with those extra privileges, it needs to use different port numbers instead — that's why you always go to `http://ap.local:8080` rather than plain `http://ap.local`.

The setup script does this for you automatically. If for some reason it didn't (or you're setting things up by hand), open the file `driver/config.toml` and change these two lines to match:
```driver/config.toml
alpaca_pilot_http_port = 8080
alpaca_pilot_https_port = 8443
```
(Both lines need changing, even if you're not using the secure/HTTPS option — the Driver checks both when it starts up.)

### P6 - If installing extra software fails
The setup script deliberately downloads ready-made versions of two number-crunching packages (**numpy** and **scipy**) that the Driver depends on, rather than building them from source, since building them on a Raspberry Pi can take a very long time or fail. Ready-made versions are available for the Raspberry Pi Zero 2 W and Raspberry Pi 4, so this normally isn't a problem.

If you ever see a *different* package fail to install because no ready-made version exists for your Pi, you may need to install some general-purpose build tools so it can be built from scratch instead:
```Bash
sudo apt install gfortran
sudo apt install libopenblas-dev
```

### P7 - `ping ap.local` works, but the address won't open in a browser
This is almost always a missing `:8080` — see [P5](#p5---manually-setting-the-alpaca-pilot-web-address-port) above for why the Pi needs it. `ping` only checks that the Pi can be found on the network at all, which works regardless of what's actually running there — it doesn't test the web page itself. Make sure you're typing the full address with the port number: `http://ap.local:8080`.

