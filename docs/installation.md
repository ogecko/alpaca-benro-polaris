[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarim](./stellarium.md) | [Using Nina](./nina.md)

# Installation Guide 
![Overview](images/abp-overview.png)

## Software Installation

### Installing the ASCOM Platform
ASCOM stands for Astronomy Common Object Model. It is a universal standard for Astronomy and is used by many different applications and equipment manufacturers. The standard was modernised with a HTTP/REST API in 2018 under the ASCOM Alpaca initiative. This `Alpaca Benro Polaris Driver (ABP) is compliant with the ASCOM ITelescopeV3 interface and provides an Alpaca ASCOM compliant REST API. 

You will need to install the ASCOM Platform software on any device that is going to host or use the Alpaca Benro Polaris Driver. You will need to install the Platform on any device running Stellarium as it is not bundled by default. You do not need to install the ASCOM Platform on a laptop that just uses Remote Desktop to access the NinaAir. 

#### To install the ASCOM Platform.
1. Download the ASCOM Platform from https://ascom-standards.org/ (Download Buttton on RHS)
2. The remaining instructions assume you are using ASCOM Platform 6.6SP2 
3. Open the installlation .exe file and click `Yes` on the User Account Control dialog.
4. Click `Next` to install any pre-requisites eg Microsoft .nett Framework 3.5 Service Pack 1 
5. This can take quite some time to download and install (5 min for me)
6. Once the blue window shows operation completed successfully, press any `key` to continue.
7. Accept the ASCOM Platform Installer default options and click `Install`.
8. Click `Finish`.

### Installing Python and libraries

### Installing ASCOM Benro Polaris Driver

### Installing Stellarium
Stellarium is a free open source planetarium for your computer. 
While there are free and paid Mobile Stelarium Apps and free Web versions, 
I'd recommend using the desktop version as it is full featured and has been 
tested with ABP.

#### To install the desktop version of Stellarium
1. Download the relevent desktop version from https://stellarium.org/en/
2. The remaining instructions assume you are using v24.2 of the Windows x86 64bit version for Windows 10+
3. Open the installlation .exe file and click `Yes` on the User Account Control dialog.
4. Select your language and click `OK`.
5. Select `I accept the agreement` and click `Next`.
6. Choose your installation folder and click `Next`.
7. Select `Start Menu Folder` and click `Next`.
8. Select `For all users` and click `Next`.
9. Click `Install`.
10. Check `Launch Stellarium` and click `Finish`.

#### To setup Stellarium for initial use
1. Press `F11` to exit full screen mode.
2. Press `A` to remove the Atmosphere. Press 'D' to see Deep Sky Objects.
3. Press `F2` to open the Configuration Dialog.
4. Select the `Extras` tab on the Configuration Dialog menu bar.
5. Click `Get catalog 5 of 9` and repeat for `6`,`7`,`8` and `9 of 9`.
6. If you are copying Oculars settings, duplicate the following file:
   `C:\Users\XXXXX\AppData\Roaming\Stellarium\modules\Oculars\ocular.ini`

#### To add Benro Polaris Telescope Control
1.  Select the `Plug-ins` tab on the Configuration Dialog menu bar.
2.  Scroll down the list of plugins and find the `Telescope Control plugin`.
3.  Check `Load at startup` on the Telescope Control Dialog.
4.  Close Stellarium and Restart Stellarium from the Desktop.
5.  Press `Ctrl+0` to open the Slew Telescope Dialog
6.  Click the `Configure Telescopes` button at the bottom of this dialog.
7.  Click on the `Add Telescope` button (3rd one at the bottom of the Telescope Control Configure dialog).
8.  Choose Telescope controlled by `ASCOM` and enter `Benro Polaris` into the Name field.
9.  Leave the Coordinate System as `J2000 (default)`, 
10. Check `Start/Connect on Startup`.
11. Scroll down to the ASCOM Settings.
12. Click `Choose ASCOM Telescope`
13. Click the `Alpaca` tab on the ASCOM Telescope Chooser dialog box.
14. Click `Enable Discovery` from the Alpaca tab
15. Click `Discover Now` from the Alpaca tab
16. For a local AAPB, Choose `Benro Polaris` from the drop down menu, then click `OK`.
17. For a remote AAPB, Click `Create Alpaca Driver (Admin)` from the drop down.
    a. Click `Yes` for  User Account Control.
    b. Enter the name `Benro Polaris`, then click `OK`.
    c. Click `Properties` on the ASCOM Telescope Chooser dialog box.
    d. Change the Remote Device Host Name/IP address (`127.0.0.1` for Loopback)
    e. Change the Alpaca Port to `5555`.
    f. Click `OK`.
18.  Click `OK` on ASCOM Telescope choser dialog.
19.  Click `OK` on Add a New Telescope dialog.
20.  Click `Connect` and close the Telescopes dialog.
21.  You have now added the Benro Polaris telescope and connected.


## Installing Nina


