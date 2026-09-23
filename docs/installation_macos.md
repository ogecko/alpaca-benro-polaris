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
1. **Download the Alpaca Driver software**

    Open a Terminal window, then clone the repository into a location of your choice (like your home directory):

    ```
    git clone --branch dev2_2 https://github.com/ogecko/alpaca-benro-polaris.git
    ```
    ```
    cd alpaca-benro-polaris
    ```

    > Note: If this is the first time you've used `git` on this Mac, it may instead prompt you to install the Xcode Command Line Tools. Accept and wait for it to finish, then run the `git clone` command again.

2. **Install uv**

    `uv` manages the correct Python version and all required libraries for you:

    ```
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```


3. **Install Python and the required libraries**
 
    This creates a `.venv` folder containing everything the driver needs:

    ```
    uv sync --no-dev --locked
    ```
    > Note: If the `uv` command isn't found, close and reopen Terminal, then `cd` back into the `alpaca-benro-polaris` folder, and try again.

### Running the Alpaca Benro Polaris Driver

4. **Start the Alpaca Benro Polaris driver**

    From within the installation directory:

    ```
    .venv/bin/python3 driver/main.py
    ```

    > Note: The first time the driver runs, macOS may ask whether to allow it to accept incoming network connections. Click **Allow**.

5. **The Alpaca Benro Polaris Driver window should look like this**

    ![Winidows Shortcut](images/abp-startup.png)


### Starting the Alpaca Pilot App

Once the Alpaca Benro Polaris Driver is running, you can access the Alpaca Pilot App from any web browser.

6. **Open a web browser**

   Open **Safari**, **Firefox**, **Chrome**, or another supported web browser.

7. **Open the Alpaca Pilot App**

   Enter the following address in the browser's address bar:

   ```
   http://ap.local
   ```

8. **Verify that the app opens**

   The Alpaca Pilot App should display the startup screen and switch to the dashboard shown below.

   ![Pilot Startup](images/pilot-startup.png)

9. **(Optional) Enable HTTPS**

    Browser features like Location and Clipboard access only work over a secure (HTTPS) connection. If you need them, follow the [Pilot User Guide – Using Alpaca Pilot over HTTPS](./pilot.md#g-using-alpaca-pilot-over-https) to install the driver's CA certificate and switch Alpaca Pilot to HTTPS.

### Connecting the Driver to Polaris

Before you can use the Polaris, complete the following steps.

10. **Open the Connect page**

    Click **Connect** in the top toolbar of the Alpaca Pilot window. The Connect page guides you through the steps required to connect the driver to your Benro Polaris device.

11. **Set up and power on the Polaris**

    Set up your Benro Polaris tripod head and turn on the device.

    If you cannot turn on the Polaris, see [Troubleshooting B1](./troubleshooting.md#b1---cannot-start-the-benro-polaris-device).

12. **Enable and join the Polaris Wi-Fi**

    On the Connect page, click the **Wi-Fi button** next to the device dropdown to have the driver enable the Polaris's Wi-Fi hotspot over Bluetooth (the Polaris's Blue LED should light up once it's on).

    Unlike Windows and Raspberry Pi, the driver doesn't join the polaris hotspot automatically. Open the Wi-Fi menu (or **System Settings > Wi-Fi**) and connect to the `polaris_xxxxxx` network yourself — this will disconnect you from your regular Wi-Fi network, and its Internet access, for the duration of the session.

    For full details, see [Pilot User Guide – Power-on the Polaris and enable Wi-Fi](./pilot.md#c-power-on-the-polaris-ane-enable-wifi).

13. **Complete the connection procedure**

    On the **Connect** page in the Alpaca Pilot App, follow each step indicated by a checkmark.

    For detailed instructions, see the [Pilot User Guide – Connecting Devices](./pilot.md#ii-connecting-devices).

    Make sure all applicable checkmarks are green. The final **Multi-Point Alignment** step will remain incomplete until you have successfully aligned on three or more stars.

14. **Verify the connection**

    Once the Driver has connected successfully to the Polaris, the Alpaca Driver window should look like this.

    ![Winidows Shortcut](images/abp-startup.png)


### Updating the Driver

To update the Alpaca Benro Polaris Driver to the latest version, stop the driver (**Ctrl+C** in its Terminal window) if it's running, then from within the `alpaca-benro-polaris` folder run:

```
git pull
uv sync --no-dev --locked
```

Then start the driver again (see step 4 above).

Your existing settings and data, including alignment and calibration data, are preserved — they live in the `data` folder, which git leaves untouched.

### Troubleshooting
If you don't see the `communications init... done` message then you may want to check the [Troubleshooting Guide C1](./troubleshooting.md#c1a---cannot-see-communications-init-done-in-the-log-wi-fi-2-not-connected) for steps to diagnose and fix any issues.



### Stellarium
If you want to use the Stellarium application on Mac and its Remote Telescope control protocol you'll have to edit the  `driver/config.toml` file, set the `stellarium_port` to a value other than `0`, for example `10001`, restart the ABP driver script and configure the telescope link in Stellarium.
