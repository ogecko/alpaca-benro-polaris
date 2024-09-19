[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarium](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Mac Setup Guide

## MacOS Installation Video Demonstration
You can view a demonstration of parts of this documentation in the following YouTube Video.
[![Install and Setup on MacOS](https://img.youtube.com/vi/ZT91dpLObP8/0.jpg)](https://www.youtube.com/watch?v=ZT91dpLObP8)

## Overview
For the first release of the Alpaca Benro Polaris driver would be provided as a bundle of Python scripts and will need the usage of the command line with the help of the Terminal application.

A recent MacOS release with Python 3 is recommanded as the Alpca Benro Polaris requires Python 3+ to be run, upgrading the preinstalled Python release on older MacOS is out of the scope of this guide.

## Installing

### Checking Python version
Open a terminal window and type the following command to check the preinstalled Python version:

```
$ python --version
Python 3.9.6
```

On MacOS the minimal tested version is `3.9.6` 

### Installing the Alpca Benro Polaris Driver code
1. Download the [Alpaca Benro Polaris zip file ](https://github.com/ogecko/alpaca-benro-polaris/archive/refs/heads/main.zip) from this Github repository.

2. Expand the zip file to a location of your choice (like in your home directory) and from a command prompt enter the following:

	```
    cd alpaca-benro-polaris
    
    pip3 install -r platforms/macos/requirements.txt
	```

### Running the Alpaca Benro Polaris Driver
Start the Alpaca Benro Polaris driver with the following command from within the installation directory:

```
python3 driver\main.py
```

Before you do, though, you'll need to do the following:

1. Setup your Benro Polaris tripod head, camera, Mac, and power.
2. Remove your lens cap (I often forget this step!).
3. Level the Benro Polaris as accurately as possible (important). 
4. Turn on the Benro Polaris (how many times doesn't it turn on?).
5. Using the Benro Polaris App, connect and change to `Astro Mode`.
6. Start the `Calibrate Compass` and tap `Confirm`.
7. Select a star to align with, tap `Goto`, wait, then tap `Confirm`. 
8. Turn on the Mac and connect it to your camera via USB.
9. Connect your Mac to the polaris-###### hotspot using WIFI (this will disconnect you from the previous WIFI and you'll loose the Internet connection)
11. Wait for connection.

One last step is to review the file  `driver/config.toml`. You will need to change the `site_latitude` and `site_longitude` to ensure the driver calculates the correct slewing co-ordinates for your location. All other settings can be left as default or tweaked. 

Fingers crossed, you can now start the Alpaca Benro Polaris Driver (as above).

The Alpaca Benro Polaris Driver window should look like this.
![Winidows Shortcut](images/abp-startup.png)

Now you can start exploring Alpaca applications like CCDciel, or even write your own REST-based application.

### Stellarium
If you want to use the Stellarium application on Mac and its Remote Telescope control protocol you'll have to edit the  `driver/config.toml` file, set the `stellarium_port` to a value other than `0`, for example `10001`, restart the ABP driver script and configure the telescope link in Stellarium.
