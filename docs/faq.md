[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarium](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Alpaca Usage Questions
### A1 - Is Alpaca a physical device?
The Alpaca Driver will be an open source software release. The software needs to be installed and setup on a Mini-PC, Laptop, Desktop, Raspberry Pi , SurfacePC, or other device that can join the BP's Wifi Hotspot. Refer to the [Hardware Guide](./hardware.md) for more information on the ways you can run the Driver.

### A1 - Does the driver need to be uploaded to the Polaris? 
The Driver needs to run on a platform that supports Python and has Wifi connectivity to the Benro Polaris. Currently no change is needed to the Benro Polaris, its firmware or its app.

### A3 - Can I use the Driver on my Mobile Device?
The driver needs to be installed on a device that (a) supports Python and (b) can connect to the Benro Polaris wifi Network. Initially, we are exploring a Laptop, mini-PC, Raspberry Pi, and MacOS. We will provide guidelines on what we have successfully tested and how to set them up.

# Benro Polaris Capability Questions

### B1 - Can the Benro Polaris really be used for Deep Sky Photography?
Yes. As an Alt/Az Mount and no guiding you will be limited to relatively short exposures. But with a good camera, an 800mm lens, ABP, Nina and Siril you can take some great photos of Deep Sky objects.

### B2 - What is the longest Focal Length that Benro Polaris can track with?
I've succeeded with 800mm and exposures of up to 15 seconds. I created an hour-long stacked exposure with a powerful desktop and around 240 images. The keeper rate was high. Vladimir has taken images at 1750mm equivalent focal length, using a ZWO ASI585MC camera, a Sigma 120-400mm and 1.4x extender. Exposures of 15s up to around 100 images stacked. Great results.

# Nina Capability Questions
### N1 - There is only one USB on my Camera how can I connect both Nina and BP App?
The Camera USB must be connected to either the BP App or an astrophotography imaging App like Nina, whichever you choose. Once you have set up the mount, Nina is quite capable of performing all imaging functions and more, including autofocus, plate solving, framing, and image sequencing. However, nothing stops you from disconnecting the Camera from Nina and returning to the BP App.

### N2 - Do I still need to plug my camera into the Benro Polaris?
If you are using Nina or CCDceil for imaging, you dont really need to plug your camera into the Ben Polaris Tripod Head any more. You only need to connect the camera via USB into the NinaAir. Nina can then help with focusing, platesolving, taking image sequences etc.

### N3 - Can Nina access the Cameras SD Card?
Nina doesn't access the Camera SD Card. It communicates with the camera via the physical USB cable using either a native or ASCOM camera driver. Nina supports Canon and Nikon cameras natively and Sony and other cameras via the ASCOM Camera driver. We've had one Beta tester have success with the ASCOM camera driver on a Sony A7Riv, but we have yet to have someone test it on Pentax or other cameras.

### N4 - Can i use Nina on my Mobile Device?
Nina is a Windows application that best runs on a desktop, laptop, or mini PC. It can be operated remotely using Remote Desktop. There are Remote Desktop apps for both Android and Apple Mobile platforms. So, it will be possible to use Nina from a phone, but the user experience is not ideal.

### N5 - Can Nina generate a file with the coordinates associated with each image?
Nina includes a plug-in called Session Manager that can record this and so much more into a set of csv files

### N6 - Is auto-guiding going to be possible?
I'm sorry, but auto-guiding is unlikely. Drift of long sequences can be fixed with ABP, Nina, and slew/center.

# Stellarium Usage Questions
### S1 - Will Stellarium work via Wifi or is a cable necessary?
Stellarium does not need USB connectivity. It can be run on a mini-PC, an iPhone, an Android Phone, an iPad, a Laptop, a Desktop, or a mini-PC. However, it will need network or Wi-Fi connectivity to the Driver.

### S2 - Will Stellarium work on the same phone as BP App?
Yes. We originally required the BP App to remain running in the background. This is no longer the case. You can close the BP App once you have the Polaris WiFi established and the Driver connected. With the BP app closed you can save on Battery usage and reconnect to the internet to use Stellarium Plus.