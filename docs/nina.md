[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarim](./stellarium.md) | [Using Nina](./nina.md)

# Using Nina with Benro Polaris
## 1. Capturing Images
The Benro Polaris App does a great job of controling your camera to take sequences of images for panoramas, time-lapse and astro-photography. It exposes many of the camera features and makes them easy to setup and use. Unfortunately it doesnt stretch and process images, show RAW files, or make it easy to customise file names or copy them off for stacking.

If you wan to go beyond the native app, there are a range of software options that provide more tailored control of your cammera for Astrophotography. Some include:

* [BackyardEOS](https://www.otelescope.com/store/category/2-backyardeos/) (no mount control)
* [APT](https://www.astrophotography.app/) - Astro Photography Tool (paid, ASCOM support)
* [SGPro](https://www.sequencegeneratorpro.com/sgpro/) - Sequence Generator Pro (paid, ASCOM Support)
* [Nina](https://nighttime-imaging.eu/) - Nighttime Imaging 'N' Astronomy (free, ASCOM support)

We will be focusing on using Nina, since it is the recommended solution. 

Upon opening Nina, the Equipment tab allows you to discover and connect to all your various astronomy equipment. The first thing you are likely to setup, is your Camera. Nina supports Nikon and Canon cameras natively, and many other cameras through the ASCOM platform.
![Equpment](images/abp-nina-camera.png)

The Sky Atlas tab allows you to search for various objects in the sky using it's own database of deep sky objects. You can filter the list by object type, size, brightnness and even how far it rises in the sky tonight. You can add a target to a sequence, set it up for framing, or slew the Benro Polaris to point at it. 
![Sky Atlas](images/abp-nina-atlas.png)

The Framing Assistant tab allows you to visualize how you are going to frame up your target. It can download an image of the target and shows your camera frame given a particular focal length, pixel size and resolution. It also allows you to plan panoramas with multiple overlaping panels that end up as separate targets in your sequence. The ability to rotate is not currently supported by the Alpaca Benro Polaris Driver.
![Framing](images/abp-nina-framing.png)

The Flat Wizard tab helps you take flat images by finding the optimal exposure settings for your camera. It takes a set of exposures and attempts to calculate the best exposure using extrapolation. It then takes a sequennce of flats that you can then use in your stacking software.
![Flat Wizard](images/abp-nina-flats.png)

The Sequence tab helps you plan the set of images you are going to capture on each target. At the start of target you can choose to slew the Benro Polaris and center the image using plate solving (see below). You can also refine the autofocus at the start or whenever it drifts out of focus. You caan define how many lights, darks, bias and flat frames are taken at each target.
![Sequencing](images/abp-nina-sequence.png)

The Imaging tab is where you will spend most of your time. Across the top are a set of buttons to show/hide informmation and tool panels. The layout is customisable by dragging and dropping any of the tabs or frames into drop targets around the screen. You can request a live view of stretched, low resolution captures one after another. You can also request a high resolution, longer exposure which is stretched, debayered and processed. Finally you get an overview of the current sequence target and can start or stop the sequence.
![imaging](images/abp-nina-imaging.png)

The imaging tab's main image panel allows you to zoom, rotate, flip the image. You can also see a zoomed in mosiac of the images center sides and corners. You can enable a crosshair for centering the image. You can also enable star detection annotations which can help you identtify focusing and tracking issues. Finally there is a panel where you can rerview the images you have captured so far.

The options tab allows has a set of sub-tabs. On the Imaging sub tab you to customize the directory where all the images will be saved. There  is also a flexible approach to changing the naming convention of the images. You can capture additional metadata into a set of csv files using a plug-in called Session Metadata. Finaly you can copy images directly from the storage location to anywhere on your network. No more ejecting SD cards.
![imaging](images/abp-nina-options.png)

All of these image capture features are independent of the Alpaca Benro Polaris (except for slewing of course)

## 2. Selecting Targets
While Ninas Sky Atlas is good for when you dont have an internet connection, other options you may want to consider include:
* [Stellarium](https://stellarium.org/en/) - Has a hidden feature `F10` Astro Calcs > `WUT` Whats up Tonight.
* [Telescopius](https://telescopious.com/) - A website with Astronomy Tools and Target a great catalog.
* [The Sky Live](https://theskylive.com/whatsvisible) - A website that lists potential targets live.

Other sites that I've found helpful include:
* [Clear Outside](https://clearoutside.com/forecast) - Planning the best night to shoot.
* [Light Polution Map](https://www.lightpollutionmap.info) - Planning where to shoot from.
* [White Screen Online](https://www.whitescreen.online/) - For taking FLAT images



## 2. Star Detection and Autofocus
Nina Module.
Plugins Hocus Focus Plug-in, Install it.
Plugins LensAF, install it.
Half Flux Radius (HFR) vs Contrast Detection.
Takes an image, Detects stars and rejects bad ones, calc HFR.
Aberation inspector for Newtownian.


## 3. Goto Co-ordinates, Aiming accuracy and Tracking
Slew to here.

## 4. Plate Solving, Aiming validity, Drift and Centering
Where am I pointing?

## 5. Three Point Alignment and Tracking
Longer exposures, Longer focal lengths.

## 6. Putting it all together
Example of a real world trip.




