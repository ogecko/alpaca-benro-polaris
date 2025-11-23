[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Raspberry Pi Setup Guide

## Overview

![Pi](images/abp-hardware-pi.png)

Raspberry Pi are a series of small single-board computers (SBCs) developed in the United Kingdom by the Raspberry Pi Foundation in association with Broadcom.

Note that these instructions assume some basic knowledge of linux systems, and is not intended to be a general tutorial on how to use a Raspberry Pi system running Linux.

## Which Pi should I buy?

Most Raspberry Pi models with networking support will work. Avoid Pico boards and the original Raspberry Pi Zero.
The Alpaca Driver has been validated on the following platforms:
- **Raspberry Pi Zero 2 W / WH** running Raspbian (Debian Bullseye)
- **Raspberry Pi 4 (8 GB)** running Raspberry Pi OS (Debian Trixie)

## Installation of Pre-Requisites
These insructions are based from a fresh install of Raspberry Pi OS Lite, written by the [Raspberry Pi imager](https://www.raspberrypi.com/software/)

1. Update your system 
    ```Bash
    sudo apt update && sudo apt upgrade -y
    ```
2. Create a virtual Python Environment  
    1. Check your Python version is 3.9.2 
        ```Bash
        python --version
        ```
    2. Update your verion of pip
        ```Bash
        python3 -m pip install --upgrade pip
        ```
    3. Create a Python virtual environment for the Alpaca Driver.
        ```Bash
        sudo apt-get install python3-venv
        cd alpaca-benro-polaris
        python -m venv ./pyenv
        export PATH=~/.pyenv/bin:$PATH
        ```
3. Install Alpaca Driver pre-requisites
    ```Bash
    pip install -r platforms/raspberry_pi/requirements.txt
    ```

4. Optionally install build tools  
    On some Raspberry Pi platforms you may encounter issues when installing the `requirements.txt`, where a package is not available for your platform. You may need to install build tools to generate the package from scratch.
    ```Bash
    sudo apt install gfortran
    sudo apt install libopenblas-dev
    ```

    
## Installing TPLink Driver on Pi Zero 2 (OPTIONAL)
The TPLink Wifi Adapter chipset may not be supported natively on the Pi Zero 2 kernel. We may meed to install the proper driver.

1. Connect the TPLink to the Raspberry Pi Zero 2 and list the usb devices connected. This is to confirm the chipset is RTL8821AU.
    ```Bash
    $ lsusb
    Bus 001 Device 002: ID 2357:0120 TP-Link Archer T2U PLUS [RTL8821AU]
    Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
    ```
2. Install the build tools
    ```Bash
    sudo apt update
    sudo apt install -y dkms git raspberrypi-kernel-headers build-essential
    ```

3. Get the drivers source code
    ```Bash
    git clone https://github.com/aircrack-ng/rtl8812au.git
    cd rtl8812au
    ```

4. Build and install with DKMS
    ```Bash
    sudo dkms add .
    dkms status
    ```
    Use the registered name from `dmks status` to build and install
    ```Bash
    sudo dkms build realtek-rtl88xxau/5.6.4.2~20230501
    sudo dkms install realtek-rtl88xxau/5.6.4.2~20230501
    ```
5. Load the module
    ```Bash
    MODULE=$(basename $(ls /lib/modules/$(uname -r)/updates/*.ko* | head -n1) .ko.xz)
    sudo modprobe $MODULE
    ````
6. Verify the network interface is active  
    You should see wlan0, and another auto-generated name like wlxe4fac4e6dea5.
    ```Bash
    $ ip link show
    1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
        link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    2: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP mode DORMANT group default qlen 1000
        link/ether d8:3a:dd:65:71:2e brd ff:ff:ff:ff:ff:ff
    3: wlxe4fac4e6dea5: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 2312 qdisc mq state UP mode DORMANT group default qlen 1000
        link/ether e4:fa:c4:e6:de:a5 brd ff:ff:ff:ff:ff:ff

    ````


## Diagnose the Wifi Connections
1. List all Wifi Network Adapters
    ```Bash
    iw dev
    ```
2. List the current state of the wifi network
    ```Bash
    iwconfig
    ```
3. List the current connection
    ```Bash
    iwgetid -r 
    ```
4. List all Wifi networks available
    ```Bash
    sudo iw wlan0 scan |grep SSID
    ```
## Manual Configuration of Alpaca Driver

5. Update Web Server Port  
    On Linux (including Raspberry Pi OS), ports below 1024 (like port 80) require root privileges. We need to change the default Web Server Port for Alpaca Pilot to a free port number. Change the setting in the file  `driver/config.toml` to the following.
    ```driver/config.toml
    alpaca_pilot_port = 8080
    ```

## Service status

The `polaris` service is controlled via `systemd`. 

Super user access(root) is not needed for getting status.

The command to run is:

`systemctl status polaris`

## Service control (start, stop, restart)

The `polaris` service can be started/stopped/restarted using the appropriate verb via the following command:

`sudo systemctl stop polaris`

Replace the `stop` verb with the appropriate action that you are trying to achieve.

## Persistent logs

Should you find the need to look over systemd logs across boots, you can use `journalctl` to do so.

Eg:

`journalctl -u polaris`

