[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarim](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Raspberry Pi Setup Guide

## Overview

![Pi](https://assets.raspberrypi.com/static/raspberry-pi-4-labelled@2x-1c8c2d74ade597b9c9c7e9e2fff16dd4.png)

Raspberry Pi are a series of small single-board computers (SBCs) developed in the United Kingdom by the Raspberry Pi Foundation in association with Broadcom.

Note that these instructions assume some basic knowledge of linux systems, and is not intended to be a general tutorial on how to use a Raspberry Pi system running Linux.

## Which Pi should I buy?

Most any Pi with networking should work. We recommend Pi 3 or newer. 

Avoid Pi Zero, and Pico variants.

## Installing
These insructions are based from a fresh install of Raspberry Pi OS Lite, written by the [Raspberry Pi imager](https://www.raspberrypi.com/software/)

To automatically set up the Raspberry Pi for Alpaca Benro Polaris, run the following command as a non-root user:

```
curl -s https://github.com/ogecko/alpaca-benro-polaris.git/platforms/raspberry_pi/setup.sh | bash
```

This script will perform the following:

1. Update the software on the system, and install dependencies needed for git
2. Clone the alpaca-benro-polaris software from github
3. Install the python dependencies needed for the application
4. Modify the default config file to work on all network interfaces (wifi and ethernet)
5. Set up [systemd](https://en.wikipedia.org/wiki/Systemd) services to start the `polaris.service` at boot time
6. Starts the service

## Updating

An update script is provided to properly stop the polaris service, and update the software appropriately

To update, on the raspberry pi run the following command:
```
~/alpaca-benro-polaris/raspberry_pi/update.sh
```

## Checking logs

In the event of something going wrong, the first thing to check is the log from the service.

This can be found in the `logs` subfolder.

```
user@astro:~/alpaca-benro-polaris $ ls logs/
alpyca.log  alpyca.log.2
```

Note that logs are [rotated](https://en.wikipedia.org/wiki/Log_rotation) on a timer, and appended with an integer. The log without an integer is the newest log.

## Service status

The `pollaris` service is controlled via `systemd`. 

Super user access(root) is not needed for getting status.

The command to run is:

`systemctl status pollaris`

## Service control (start, stop, restart)

The `polaris` service can be started/stopped/restarted using the appropriate verb via the following command:

`sudo systemctl stop polaris`

Replace the `stop` verb with the appropriate action that you are trying to achieve.

## Persistent logs

Should you find the need to look over systemd logs across boots, you can use `journalctl` to do so.

Eg:

`journalctl -u polaris`

