[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Raspberry Pi Setup Guide
[Versions](#which-pi-should-i-buy) | 
[Image Creation](#install-raspberry-pi-os-image) | 
[Alpaca Installation](#installation-of-pre-requisites-and-alpaca-driver) | 
[Troubleshooting](#troubleshooting-the-raspberry-pi)


## Overview

![Pi](images/abp-hardware-pi.png)

Raspberry Pi are a series of small single-board computers (SBCs) developed in the United Kingdom by the Raspberry Pi Foundation in association with Broadcom.

Note that these instructions assume some basic knowledge of linux systems, and is not intended to be a general tutorial on how to use a Raspberry Pi system running Linux.

## Which Pi should I buy?

Most Raspberry Pi models with networking support will work. Avoid Pico boards and the original Raspberry Pi Zero.
The Alpaca Driver has been validated on the following platforms:
- **Raspberry Pi Zero 2 W / WH** running Raspbian Pi OS Lite (64-bit) - Debian Trixie
- **Raspberry Pi 4 (8 GB)** running Raspberry Pi OS (64-bit) - Debian Trixie

For reference, when running advanced motion control algorithms and tracking a sidereal target, the Alpaca Driver uses roughly 22% of the CPU and 26% of the available memory on a **Raspberry Pi Zero 2 W**.
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
## Install Raspberry Pi OS Image
1. Download the Raspberry Pi Imager from the [official website](https://www.raspberrypi.com/software/)
2. Open the imager_2.0.0.exe and follow the installation instructions, choosing to run the program at the finish of installation.
3. Using the imaging program
    1. Select your Raspberry Pi Device eg Raspberry Pi Zero 2 W, then click **NEXT**
    2. Choose your Operating System as **Raspberry Pi OS (64-bit)**, then click **NEXT**. If you are using a Raspberry Pi Zero 2 W and want a "headless Pi", select **Raspberry Pi OS (other)**, then choose **Raspberry Pi OS Lite (64-bit)**, then click **NEXT**
    3. Select your Storage Device that will hold the OS, then click **NEXT**
   > Do not format the SD card as FAT32, as Windows may automatically mount and lock it, preventing the imager from writing to the card. Instead, use Disk Management to carefully delete any existing partitions on the SD card before proceeding.
    4. Enter the device hostname eg **alpaca**, then click **NEXT**
    5. Choose your localisation settings, then click **NEXT**
    6. Choose your user name and password, then click **NEXT**
    7. Choose your local wifi network you want the Pi to connect to, then click **NEXT**
    8. Enable SSH. Use default password authtication, then click **NEXT**
    9.  Use default disabled Raspberry Pi Connect, then click **NEXT**
    10. Write the image to the SD Card, click **WRITE**
4. Remove the SD Card storage device and insert it into your Raspberry Pi

## Installation of Pre-Requisites and Alpaca Driver
These insructions are based from a fresh install of Raspberry Pi OS Lite, written by the [Raspberry Pi imager](https://www.raspberrypi.com/software/). Connect a **keyboard** and **monitor** directly to the Raspberry Pi, or setup a remote terminal program such as **Powershell ssh**,  **MobaXterm** or **VS Code**. Login with the username and password you configured during image creation, and then follow the instructions below.

5. Connect a keyboard/screen to the Raspberry Pi, or connect a remote terminal like MobaXterm. Logon to the Raspberry Pi using the credentials you setup in the imager.
6. Download the setup script
    ```Bash
    cd ~
    wget https://raw.githubusercontent.com/ogecko/alpaca-benro-polaris/dev2_2/platforms/raspberry_pi/setup.sh -O setup.sh
    ```
7. Make it executable and Run the setup script
    ```Bash
    chmod +x ./setup.sh
    ./setup.sh
    ```
    Note that if you want to fetch a specific branch from the Git-Hub repository you can pass the Branch name as the first argument to setup.sh. For example, the following command will fetch the **dev2_2** branch.
    ```
    ./setup.sh dev2_2
    ```
8. Wait for the following tasks to complete
    * ==SETUP== 1. Update the software on the system, and install dependencies needed for git and uv
    * ==SETUP== 2. Clone/Fetch the alpaca-benro-polaris software from Git-Hub.
    * ==SETUP== 3. Install uv, adding it to ~/.bashrc.
    * ==SETUP== 4. Sync the python dependencies needed for the application with uv.
    * ==SETUP== 5. Updating config.toml with 'alpaca_pilot_http_port = 8080' and 'alpaca_pilot_https_port = 8443'
    * ==SETUP== 6. Ensure Bluetooth is powered on, needed for BLE communication with the Polaris.
    * ==SETUP== 7. Grant passwordless nmcli access, needed for join_wifi.py to join the Polaris hotspot.
    * ==SETUP== 8. Set up [systemd] services to start the Polaris Driver at boot time
    * ==SETUP== 9. Starts the polaris-driver service.

    [uv](https://docs.astral.sh/uv/) is a fast Python package/project manager. The script installs it automatically (equivalent to running `curl -LsSf https://astral.sh/uv/install.sh | sh`) if it isn't already on your system, then runs `uv sync` to create the virtual environment (`.venv`) and install the exact dependency versions pinned in `uv.lock` — no separate `pip`, `python3-venv` or platform `requirements.txt` is required.

9. Start Alpaca Pilot and Connect to the Polaris

    The Alpaca Driver should now be installed and running. To open Alpaca Pilot, open a browser and navigate to `http://<hostname>:8080` (e.g. `http://alpaca:8080`) or `http://ap.local:8080`. Note the `:8080` is required on the Raspberry Pi (see [P5](#p5---manual-configuration-of-alpaca-pilot-port)) since Linux won't let a non-root process bind ports below 1024. 

    A dedicated USB Wifi adapter (e.g. TP-Link Archer T2U PLUS) is recommended for connecting to the Polaris. The onboard Wifi on a Pi Zero 2 W can't associate with the Polaris' own hotspot. 

    Click **Connect** on the toolbar, then follow the Connect page: power on the Polaris, select it from the **Device** dropdown, and click the **Wi-Fi** button. The Driver enables the Polaris' Wi-Fi hotspot over Bluetooth, then joins the Polaris network. Once connected, the Driver should automatically connect to the Polaris too. See the [Alpaca Pilot Users Guide - Connecting Devices](./pilot.md#ii-connecting-devices) for the full step-by-step, including what each button and indicator on the Connect page does.

    If the Pi doesn't join the Polaris hotspot automatically, see [P1](#p1---diagnosing-wifi-and-bluetooth-network-issues) for how to diagnose and join manually.

## Monitoring and Diagnostic commands

10. To activate the .venv created by the setup script and added to the .bashrc
    ```Bash
    source ~/.bashrc
    ```
11. To monitor and control the status of the Alpaca Driver Daemon Service
    ```Bash
    sudo systemctl status polaris-driver       # Check the service status 
    sudo systemctl stop polaris-driver         # Stop the service 
    sudo systemctl start polaris-driver        # Start the service  
    journalctl -u polaris-driver -f            # View the logs
    ```

## Troubleshooting the Raspberry Pi
### P1 - Diagnosing Wifi and Bluetooth Network Issues
The Alpaca Pilot's Connect page (see the [Users Guide](./pilot.md#ii-connecting-devices)) handles Wifi and Bluetooth automatically: Bluetooth discovers the Polaris and enables its hotspot, then the Driver joins the Pi to that hotspot via `driver/join_wifi.py` (NetworkManager/`nmcli` under the hood) and assigns it a static IP. Use the commands below to diagnose when something isn't working.

**Bluetooth** (BLE discovery / enabling the Polaris' Wi-Fi hotspot)
```Bash
rfkill list                             # check for a soft/hard block (apt install rfkill if missing)
sudo rfkill unblock bluetooth           # or: echo 0 | sudo tee /sys/class/rfkill/rfkill0/soft
sudo hciconfig hci0 up
```

**USB Wifi adapter** — the Pi's onboard Wifi can't associate with the Polaris' own hotspot, so a dedicated USB adapter (e.g. TP-Link Archer T2U PLUS, chipset RTL8821AU) is recommended. Connect it to the port labelled `USB`, not `PWR IN` (power only, no data lines). Raspberry Pi OS Trixie's `rtw88` driver family auto-loads this chipset — no build required.
```Bash
lsusb                        # confirm it's detected, note the chipset
dmesg | grep -i rtw88        # confirm the driver loaded and got firmware
ip link show                 # confirm a new wlan* interface appeared (e.g. wlan1 alongside onboard wlan0)
sudo ip link set wlan1 up    # bring it up if needed
```
If `lsusb` sees the adapter but no `wlan*` interface appears, your kernel doesn't have `rtw88` mainlined (older Raspberry Pi OS releases) — build it with DKMS from [aircrack-ng/rtl8812au](https://github.com/aircrack-ng/rtl8812au) instead. On a Pi Zero 2 W the build can exhaust RAM; add temporary swap first if it fails partway through, then remove it once the build succeeds:
```Bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
# ... retry the DKMS build, then:
sudo swapoff /swapfile && sudo rm /swapfile
```

**Confirm the Polaris hotspot is visible**
```Bash
iw dev | grep Interface           # apt install iw if missing
sudo iw wlan1 scan | grep SSID    # look for polaris_xxxxxx
```

**Manually join, or re-run the join** — `join_wifi.py` is exactly what the Alpaca Pilot's Wi-Fi button calls; run it directly for more detail than the button's log line, or to join without opening Alpaca Pilot at all. It's idempotent, so re-running is always safe.
```Bash
cd ~/alpaca-benro-polaris
.venv/bin/python3 driver/join_wifi.py polaris_b83c06   # or omit the SSID to auto-discover
```
If it fails with `Insufficient privileges`: NetworkManager's own polkit rule only allows unauthenticated connection changes from a "local and active" seat session — neither an SSH session nor the Driver's own systemd service (`User=pi`, no seat at all) qualifies, even though the `pi` user can otherwise `sudo` freely. setup.sh installs a scoped passwordless sudo rule for this (`/etc/sudoers.d/polaris-nmcli`); recreate it manually if missing:
```Bash
echo "pi ALL=(ALL) NOPASSWD: $(command -v nmcli)" | sudo tee /etc/sudoers.d/polaris-nmcli
sudo chmod 440 /etc/sudoers.d/polaris-nmcli
sudo visudo -cf /etc/sudoers.d/polaris-nmcli   # validates the file before it's trusted
```

**Check connection status**
```Bash
nmcli -t -f DEVICE,STATE,CONNECTION device status   # is wlan1 connected to the right SSID?
ip addr show wlan1                                  # confirm the static IP (192.168.0.100/24 by default)
ping 192.168.0.1                                    # confirm reachability
journalctl -u NetworkManager -f                     # NetworkManager logs
```
### P2 - Diagnosing Wifi Connections
To check the network status. The `ip a` command displays all network interfaces and their assigned IP addresses (IPv4 and IPv6), including interface state and MAC address.:
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
### P3 - Diagnosing Polaris daemon services
To check polaris services:
```
$ systemctl list-unit-files | grep polaris
polaris-driver.service                       enabled         enabled

$ systemctl status | grep polaris
           │ ├─polaris-driver.service
           │ │ └─2646 /home/pi/alpaca-benro-polaris/.venv/bin/python3 /home/pi/alpaca-benro-polaris/driver/main.py
               │ └─2667 grep --color=auto polaris

```
The Wifi connection to the Polaris is a NetworkManager connection profile, not a systemd service -- see [P1](#p1---diagnosing-wifi-and-bluetooth-network-issues) above for how to check its status instead.
### P4 - Adding additional access points to wlan0
You can use wlan0 to connect the Raspberry Pi to one of multiple access points. For example, you may want to it to connect to your home network while at home, and your laptops hotspot while at a dark sky site.

1. Add a connection for your laptop's access point.
    ```
    sudo nmcli connection add type wifi ifname wlan0 con-name laptop ssid "hotspot_SSID"     
    sudo nmcli connection modify laptop wifi-sec.key-mgmt wpa-psk wifi-sec.psk "hotspot_password" 
    sudo nmcli connection modify laptop connection.autoconnect yes connection.autoconnect-priority 20    
    ```
 
    > Note: On Raspberry Pi OS (Trixie), the initial Wi-Fi network configured via Raspberry Pi Imager is written to a Netplan YAML file. Netplan then uses NetworkManager as its renderer to create and manage the actual Wi-Fi connection profile. The Netplan configuration files are located in /etc/netplan/*.yaml. You can also set the priority of the netplan connection, higher numeric values indicate higher priority when multiple known networks are available.

2. Confirm the connection has been added.
    ```
    $ nmcli -f NAME,TYPE,DEVICE,AUTOCONNECT,ACTIVE,STATE,AUTOCONNECT-PRIORITY connection show
    NAME                    TYPE      DEVICE  AUTOCONNECT  ACTIVE  STATE      AUTOCONNECT-PRIORITY
    netplan-wlan0-atlas_6G  wifi      wlan0   yes          yes     activated  10
    lo                      loopback  lo      no           yes     activated  0
    laptop                  wifi      --      yes          no      --         20
    ```

3. Check that the Raspberry Pi can see your laptop hotspot. You may need to edit its Hotspot configuration to ensure it broadcasts on the 2.4Ghz band.
    ```
    $ sudo iw wlan0 scan | grep SSID
        SSID: atlas_6G
        SSID: atlas_6G
        SSID: polaris_b83c06
        SSID: laptop_hotspot
    ```

4. Reconnect to laptop hotspot. Request NetworkManager to reconsider autoconnect rules for the interface, rescan for network availaibility, and connect to laptop hotspot.
    ```
    sudo nmcli device reapply wlan0
    sudo nmcli device wifi rescan ifname wlan0
    sudo nmcli connection up laptop
    ```

5. To check Network Manager status
    ```
    $ nmcli radio
    WIFI-HW  WIFI     WWAN-HW  WWAN
    enabled  enabled  missing  enabled

    $ nmcli device status
    DEVICE         TYPE      STATE                   CONNECTION
    wlan0          wifi      connected               netplan-wlan0-atlas_6G
    lo             loopback  connected (externally)  lo
    p2p-dev-wlan0  wifi-p2p  disconnected            --
    wlan1          wifi      unavailable             --

    $ nmcli device wifi list
    IN-USE  BSSID              SSID      MODE   CHAN  RATE        SIGNAL  BARS  SECURITY
       *A0:36:BC:40:77:88  atlas_6G  Infra  5     405 Mbit/s  73      ▂▄▆_  WPA2
        08:62:66:96:3F:31  atlas_6G  Infra  5     195 Mbit/s  54      ▂▄__  WPA2
        CC:28:AA:5A:89:1A  atlas_6G  Infra  5     405 Mbit/s  50      ▂▄__  WPA2
    ```

6. To remove a connection from Network Manager
    ```
    $ nmcli connection show
    NAME                    UUID                                  TYPE      DEVICE
    netplan-wlan0-atlas_6G  fe8758eb-c76a-3d01-9580-21c52199d208  wifi      wlan0
    lo                      4bddf44c-f07a-4d0d-a8c5-fcf2a4f57512  loopback  lo
    laptop                  38ac0174-c389-404d-a32c-d795370b4a61  wifi      --

    $ sudo nmcli connection delete 38ac0174-c389-404d-a32c-d795370b4a61
    ```

### P5 - Manual Configuration of Alpaca Pilot Port
On Linux (including Raspberry Pi OS), ports below 1024 (like port 80 and 443) require root privileges. We need to change the default Web Server Ports for Alpaca Pilot to free, unprivileged port numbers. Note that both `alpaca_pilot_http_port` and `alpaca_pilot_https_port` must be changed, even if you leave `enable_https = false`, since the driver checks that both ports are bindable at startup.

This is done automatically in setup.sh, but if you did not use this method, then use the following manual procedure.

1. Update Web Server Ports  
     Change the settings in the file  `driver/config.toml` to the following.
    ```driver/config.toml
    alpaca_pilot_http_port = 8080
    alpaca_pilot_https_port = 8443
    ```

### P6 - Optionally install build tools  
The setup script installs Python dependencies with `uv sync --no-dev --locked --no-build-package numpy --no-build-package scipy`, which forces **numpy** and **scipy** to come from pre-built wheels rather than being compiled from source. Pre-built `aarch64` wheels for these packages are available on PyPI for the **Raspberry Pi Zero 2 W** and **Raspberry Pi 4**, so this should succeed without any extra build tools.

If you encounter other package dependency issues (for example a new dependency without a pre-built wheel for your platform), you may need to install build tools to compile it from scratch.
```Bash
sudo apt install gfortran
sudo apt install libopenblas-dev
```

### P7 - `ping ap.local` works but the browser can't reach Alpaca Pilot
On the Pi, Alpaca Pilot runs on port 8080 rather than the standard port 80 (see [P5](#p5---manual-configuration-of-alpaca-pilot-port)). `ping ap.local` only tests that the `ap.local` mDNS name resolves to the Pi's IP address — ICMP has no concept of ports, so it succeeds regardless. A browser given a bare `http://ap.local` (no port) will instead try to connect on the default port 80, where nothing is listening, and fail. Always include the port: `http://ap.local:8080`.

