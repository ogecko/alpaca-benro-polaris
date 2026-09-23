[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [CCDciel](./ccdciel.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Mac Setup Guide

## MacOS Installation Video Demonstration
You can view a demonstration of parts of this documentation in the following YouTube Video.
[![Install and Setup on MacOS](https://img.youtube.com/vi/ZT91dpLObP8/0.jpg)](https://www.youtube.com/watch?v=ZT91dpLObP8)

## Overview
The Alpaca Benro Polaris driver is provided as a bundle of Python scripts and needs the command line, via the Terminal application, to install and run.

You do not need to install Python yourself. The following installation procedure uses [uv](https://docs.astral.sh/uv/) to install the correct Python version and every required library automatically.

## Installing

### Installing the Alpaca Benro Polaris Driver code
1. Download the [Alpaca Benro Polaris ZIP file](https://github.com/ogecko/alpaca-benro-polaris/archive/refs/heads/dev2_2.zip) from this Github repository.

2. Expand the zip file to a location of your choice (like in your home directory), then open a Terminal window and enter the following:

    ```
    cd alpaca-benro-polaris
    ```

3. Install uv, which manages the correct Python version and all required libraries for you:

    ```
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    If the `uv` command isn't found afterwards, close and reopen Terminal, then `cd` back into the `alpaca-benro-polaris` folder.

4. Install the driver's Python dependencies with uv. This creates a `.venv` folder containing everything the driver needs:

    ```
    uv sync --no-dev --locked
    ```

### Running the Alpaca Benro Polaris Driver

5. Start the Alpaca Benro Polaris driver with the following command from within the installation directory:

    ```
    .venv/bin/python3 driver/main.py
    ```

6. The Alpaca Benro Polaris Driver window should look like this.
![Winidows Shortcut](images/abp-startup.png)


### Starting the Alpaca Pilot App

With the Alpaca Driver running you can now start the Alpaca Pilot App from any browser. 

7. Open **Safari**, **Firefox**, **Chrome**, or your preferred browser.
8. Enter the following into the address bar, where hostname is the name of the machine you are running the Driver on. 
   ```
   http://hostname
   ```

9. The Alpaca Pilot App should look like this:
![Pilot Startup](images/pilot-startup.png)
10. Click **Connect** on the top toolbar of the Alpaca Pilot Window. This page will allow you to follow through the steps to connect the Driver to the Benro Polaris device.

### Connecting the Driver to Polaris
There are a few preliminary steps before you can use the Polaris. You'll need to do the following:

11. Setup your Benro Polaris tripod head and turn on the Benro Polaris. If you cant turn it on, see [Troubleshooting B1](./troubleshooting.md#b1---cannot-start-the-benro-polaris-device).
12. Turn on the Mac and connect it to your camera via USB.
13. Connect your Mac to the polaris-###### hotspot using WIFI (this will disconnect you from the previous WIFI and you'll loose the Internet connection)
14. Wait for connection.
15. Using the Alpaca Pilot App Connect Page, follow the checkmark steps to complete the setup of the Polaris. Refer to the [Pilot Users Guide - Connecting Devices](./pilot.md#ii-connecting-devices) for more details and a full step by step procedure. Make sure all checkmarks are green (except for the final Multi-Point Alignment step, which will only turn green after you’ve aligned on three or more stars).

16. Once the Driver has connected successfully to the Polaris the Alpaca Driver window should look like this.
![Winidows Shortcut](images/abp-startup.png)

### Troubleshooting
If you don't see the `communications init... done` message then you may want to check the [Troubleshooting Guide C1](./troubleshooting.md#c1a---cannot-see-communications-init-done-in-the-log-wi-fi-2-not-connected) for steps to diagnose and fix any issues.

### Stellarium
If you want to use the Stellarium application on Mac and its Remote Telescope control protocol you'll have to edit the  `driver/config.toml` file, set the `stellarium_port` to a value other than `0`, for example `10001`, restart the ABP driver script and configure the telescope link in Stellarium.
