[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Raspberry Pi Setup Guide

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
(pyenv) pi@alpaca:~/alpaca-benro-polaris $ top

top - 22:38:21 up  8:03,  2 users,  load average: 0.42, 0.46, 0.46
Tasks: 150 total,   2 running, 148 sleeping,   0 stopped,   0 zombie
%Cpu(s): 5.2 us,  0.6 sy,  0.0 ni, 95.6 id,  0.0 wa,  0.0 hi,  0.1 si,  0.0 st
MiB Mem :    416.1 total,     94.8 free,    204.8 used,    170.8 buff/cache
MiB Swap:    416.0 total,    387.1 free,     28.9 used.    211.3 avail Mem

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
   1942 root      20   0  608352 113132  41640 R  22.4  26.5   8:33.13 python3

```
## Install Raspberry Pi OS
1. Download the Raspberry Pi Imager from the [official website](https://www.raspberrypi.com/software/)
2. Open the imager_2.0.0.exe and follow the installation instructions, choosing to run the program at the finish of installation.
3. Using the imaging program
    1. Select your Raspberry Pi Device eg Raspberry Pi Zero 2 W, then click **NEXT**
    2. Choose your Operating System as **Raspberry Pi OS (64-bit)**, then click **NEXT**. If you are using a Raspberry Pi Zero 2 W and want a "headless Pi", select **Raspberry Pi OS (other)**, then choose **Raspberry Pi OS Lite (64-bit)**, then click **NEXT**
    3. Select your Storage Device that will hold the OS, then click **NEXT**
    4. Enter the device hostname eg **alpaca**, then click **NEXT**
    5. Choose your localisation settings, then click **NEXT**
    6. Choose your user name and password, then click **NEXT**
    7. Choose your local wifi network you want the Pi to connect to, then click **NEXT**
    8. Enable SSH. Use default password authtication, then click **NEXT**
    9. Use default disabled Raspberry Pi Connect, then click **NEXT**
    10. Write the image to the SD Card, click **WRITE**

## Installation of Pre-Requisites and Alpaca Driver
These insructions are based from a fresh install of Raspberry Pi OS Lite, written by the [Raspberry Pi imager](https://www.raspberrypi.com/software/). Connect a **keyboard** and **monitor** directly to the Raspberry Pi, or setup a remote terminal program such as **MobaXterm** or **VS Code**. Login with the username and password you configured during image creation, and then follow the instructions below.


4. Download the setup script
    ```Bash
    cd ~
    wget https://raw.githubusercontent.com/ogecko/alpaca-benro-polaris/dev2_1/platforms/raspberry_pi/setup.sh -O setup.sh
    ```
5. Make it executable and Run the setup script
    ```Bash
    chmod +x ./setup.sh
    ./setup.sh
    ```
    Note that if you want to fetch a specific branch from the Git-Hub repository you can pass the Branch name as the first argument to setup.sh. For example, the following command will fetch the **dev2_1** branch.
    ```
    ./setup.sh dev2_1
    ```
6. Wait for the following tasks to complete
    * ==SETUP== 1. Update the software on the system, and install dependencies needed for git
    * ==SETUP== 2. Clone/Fetch the alpaca-benro-polaris software from Git-Hub.
    * ==SETUP== 3. Create a pyenv and add to ~/.bashrc.
    * ==SETUP== 4. Install the python dependencies needed for the application.
    * ==SETUP== 5. Updating config.toml with 'alpaca_pilot_port = 8080'
    * ==SETUP== 6. Set up [systemd] services to start the Polaris Driver at boot time
    * ==SETUP== 7. Starts the polaris-driver service.

7. The Alpaca Driver should now be installed and setup

## Monitoring and Diagnostic commands

8. To activate the pyenv created by the setup script and added to the .bashrc
    ```Bash
    source ~/.bashrc
    ```
9. To monitor and control the status of the Alpaca Driver Daemon Service
    ```Bash
    sudo systemctl status polaris-driver       # Check the service status 
    sudo systemctl stop polaris-driver         # Stop the service 
    sudo systemctl start polaris-driver        # Start the service  
    journalctl -u polaris-driver -f            # View the logs
    ```

10. Optionally install build tools  
    On some Raspberry Pi platforms you may encounter issues when installing the `requirements.txt`, where a package is not available for your platform. For example, on the **Raspberry Pi Zero 2 W**, there is no compiled version of **numpy** or **scipi** available for pip to install. The script works around this issue by using apt-get to install both of these packages globally outside of pip. 
    
    If you encounter other package dependancy issues you may need to install build tools to generate any missing package from scratch.
    ```Bash
    sudo apt install gfortran
    sudo apt install libopenblas-dev
    ```

    
## Installing TPLink Driver on Pi Zero 2 (OPTIONAL)
The TPLink Wifi Adapter chipset may not be supported natively on the Pi Zero 2 kernel. You may meed to build and install a suitable driver using the following procedure. 

11. Connect the TPLink to the Raspberry Pi Zero 2 and list the usb devices connected. This is to confirm the chipset is RTL8821AU.
    ```Bash
    $ lsusb
    Bus 001 Device 002: ID 2357:0120 TP-Link Archer T2U PLUS [RTL8821AU]
    Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
    ```
12. Install the build tools
    ```Bash
    echo "deb http://archive.raspberrypi.org/debian/ bookworm main" | sudo tee /etc/apt/sources.list.d/raspi.list
    sudo apt update
    sudo apt install -y dkms git build-essential raspberrypi-kernel-headers
    ```
    > Note: Raspberry Pi Foundation builds kernel packages against Bookworm (not Trixie). This is why we add the bookworm archive, so we can install the raspberrypi-kernel-headers.

13. Get the drivers source code
    ```Bash
    git clone https://github.com/aircrack-ng/rtl8812au.git
    cd rtl8812au
    ```

14. Build and install with DKMS
    ```Bash
    sudo dkms add .
    dkms status
    ```
    Use the registered name from `dmks status` to build and install. Both commands should show "done." when complete.
    ```Bash
    sudo dkms build realtek-rtl88xxau/5.6.4.2~20230501
    sudo dkms install realtek-rtl88xxau/5.6.4.2~20230501
    ```
    If the build fails half way through on a Raspberry Pi Zero 2 W, you may need to increase the swap size with the following commands, then repeat the build and install commands above.

    To create a temporary file-backed swap
    ```
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    swapon --show
    # To remove swap (after you have build and installed the module)
    sudo swapoff /swapfile
    sudo rm /swapfile
    ```
    Or use a memory based swap.
    ```
    sudo systemctl stop polaris
    sudo swapoff /dev/zram0
    echo $((2*1024*1024*1024)) | sudo tee /sys/block/zram0/disksize
    sudo mkswap /dev/zram0
    sudo swapon /dev/zram0
    swapon --show
    ``` 
    
15. Load the module
    ```Bash
    sudo modprobe 88XXau
    ````
16. Verify the network interface is active  
    You should see wlan0, and another auto-generated name like **wlan0** or **wlxe4fac4e6dea5**.
    ```Bash
    $ ip link show
    1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
        link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    2: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DORMANT group default qlen 1000
        link/ether d8:3a:dd:65:71:2e brd ff:ff:ff:ff:ff:ff
    3: wlan1: <NO-CARRIER,BROADCAST,MULTICAST,UP,LOWER_UP> mtu 2312 qdisc mq state DORMANT mode DORMANT group default qlen 1000
        link/ether e4:fa:c4:e6:de:a5 brd ff:ff:ff:ff:ff:ff
    ````


## Identify Wifi Interface and Polaris SSID
17. List all Wifi Network Interfaces/Adapters available. It should show `wlan0` for the standard Pi Zero interface and something like `wlan1` for the TPLink. Remember the TPLink interface name for the next section.
    ```Bash
    iw dev | grep Interface
    ```
18. Ensure the Polaris is powered on and list all Wifi Networks SSID visible, replacing `wlan1` with your TPLINK Interface name (if it is different). Look for a Polaris SSID of `polaris_xxxxxxx`. Remember the Polaris SSID for the next section.
    ```Bash
    sudo iw wlan1 scan | grep SSID
    ```



## Setup of Wifi Connection to Polaris
The following procedure describes how to setup a Raspberry Pi Zero 2 with a TPLINK adapter, to connect to the Polaris automatically.

19. Change to the platforms/raspberry_pi directory and make the wifi.sh script executable.
    ```
    cd platforms/raspberry_pi
    chmod +x wifi.sh
    ```
20. Run the WiFi Setup script, changing the interface **wlan1** and SSID name **polaris_3b3906** according
    ```
    sudo ./wifi.sh wlan1 polaris_b83c06
    ```

21. Wait for the following tasks to complete
    * == STEP == 1. Create wpa_supplicant config file 
    * == STEP == 2. Create [systemd] service to connect to wlan1
    * == STEP == 3. Create [systemd] service to set static IP address on wlan1

22. Check connectivity to the Polaris device
    ```
    $ ip addr show wlan1
    3: wlan1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 2312 qdisc mq state UP group default qlen 1000
        link/ether e4:fa:c4:e6:de:a5 brd ff:ff:ff:ff:ff:ff
        inet 192.168.0.100/24 scope global wlan1
        valid_lft forever preferred_lft forever

    $ iw dev
    phy#1
            Interface wlan1
                    ifindex 3
                    wdev 0x100000001
                    addr e4:fa:c4:e6:de:a5
                    ssid polaris_3b3906
                    type managed
                    channel 36 (5180 MHz), width: 80 MHz, center1: 5210 MHz
                    txpower 20.00 dBm
    phy#0
            Unnamed/non-netdev interface
                    wdev 0x2
                    addr da:3a:dd:65:71:2e
                    type P2P-device
                    txpower 31.00 dBm
            Interface wlan0
                    ifindex 2
                    wdev 0x1
                    addr d8:3a:dd:65:71:2e
                    ssid atlas_6G
                    type managed
                    channel 7 (2442 MHz), width: 20 MHz, center1: 2442 MHz
                    txpower 31.00 dBm

    $ ping 192.168.0.1
    PING 192.168.0.1 (192.168.0.1) 56(84) bytes of data.
    64 bytes from 192.168.0.1: icmp_seq=1 ttl=64 time=3.94 ms
    64 bytes from 192.168.0.1: icmp_seq=2 ttl=64 time=1.63 ms
    64 bytes from 192.168.0.1: icmp_seq=3 ttl=64 time=1.59 ms
    64 bytes from 192.168.0.1: icmp_seq=4 ttl=64 time=1.59 ms

    ```

5. To monitor and control the status of the Polaris Wifi Connection Service
    ```Bash
    sudo systemctl status polaris-wlan1       # Check the wlan1 connect service status 
    sudo systemctl stop polaris-wlan1         # Stop the wlan1 connect service 
    sudo systemctl start polaris-wlan1        # Start the wlan1 connect service  
    journalctl -u polaris-wlan1 -f            # View the wlan1 connect logs
    journalctl -u polaris-ip                  # View the wlan1 assign static ip logs
    ```

## Diagnosing Wifi and Bluetooth Connections
To check whether the Raspberry Pi Wifi or Bluetooth is blocked: 
```
$ rfkill list
0: hci0: Bluetooth
        Soft blocked: yes
        Hard blocked: no
1: phy0: Wireless LAN
        Soft blocked: no
        Hard blocked: no
2: phy1: Wireless LAN
        Soft blocked: no
        Hard blocked: no
```
To unblock Raspberry Pi Bluetooth and Wifi:
```
$ sudo rfkill unblock bluetooth
$ sudo rfkill unblock wifi
```
To bring up the wlan1 wifi interface:
```
$ sudo ip link set wlan1 up
```
To scan the wlan1 wifi interface for active SSIDs:
```
$ sudo iw wlan1 scan | grep SSID
        SSID: polaris_b83c06
        SSID: atlas_6G
        SSID: atlas_6G
        SSID: OPTUS_734AC2_5GHz
```
To check the network status:
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
To check polaris services:
```
$ systemctl list-unit-files | grep polaris
polaris-driver.service                       enabled         enabled
polaris-ip.service                           enabled         enabled
polaris-wlan1.service                        enabled         enabled

$ systemctl status | grep polaris
           │ ├─polaris-driver.service
           │ │ └─2646 /home/pi/alpaca-benro-polaris/pyenv/bin/python3 /home/pi/alpaca-benro-polaris/driver/main.py
           │ ├─polaris-wlan1.service
               │ └─2667 grep --color=auto polaris

```

To add another access point to wlan0. You can use wlan0 to connect the Raspberry Pi multiple access points. For example, you may want to it to connect to your home network while at home, and your laptops hotspot while at a dark sky site.

1. Add an connection to your laptop's access point.
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

3. To check Network Manager status
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

4. To remove a connection from Network Manager
    ```
    $ nmcli connection show
    NAME                    UUID                                  TYPE      DEVICE
    netplan-wlan0-atlas_6G  fe8758eb-c76a-3d01-9580-21c52199d208  wifi      wlan0
    lo                      4bddf44c-f07a-4d0d-a8c5-fcf2a4f57512  loopback  lo
    laptop                  38ac0174-c389-404d-a32c-d795370b4a61  wifi      --

    $ sudo nmcli connection delete 38ac0174-c389-404d-a32c-d795370b4a61
    ```
## Manual Configuration of Alpaca Driver
On Linux (including Raspberry Pi OS), ports below 1024 (like port 80) require root privileges. We need to change the default Web Server Port for Alpaca Pilot to a free port number. 

This is done automatically in setup.sh, but if you did not use this method, then use the following manual procedure.

1. Update Web Server Port  
     Change the setting in the file  `driver/config.toml` to the following.
    ```driver/config.toml
    alpaca_pilot_port = 8080
    ```


## Upgrading Bluez Bluetooth Library to v5.66 
If you are using an older version of the Bluetooth library then you may need to upgrade.

1. Check version of Bluetooth. If you are using v5.55-1 then proceed to upgrade.
    ```Bash
    $ bluetoothd --version
    Version: 5.66-1
    ```

1. Install prerequisites
    ```Bash
    sudo apt-get install libglib2.0-dev libdbus-1-dev libudev-dev libreadline-dev libical-dev libtool python3-docutils autoconf automake make gcc
    ```

2. Perform the upgrade and install
    ```Bash
    wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.66.tar.xz
    tar xf bluez-5.66.tar.xz
    cd bluez-5.66
    ./configure --prefix=/usr --mandir=/usr/share/man --sysconfdir=/etc --localstatedir=/var
    make
    sudo make install
    ```

> Note: There is a known issue where the Raspberry Pi can discover the Polaris device over Bluetooth but is unable to enable its Wi-Fi connection. This upgrade does not resolve the Wi-Fi enablement issue. As a workaround, power the Polaris off and then back on to re-enable Wi-Fi. If the Alpaca Driver is running, it should automatically reconnect once the Polaris Wi-Fi becomes available.
