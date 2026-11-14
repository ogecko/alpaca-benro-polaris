# Getting Started

## Quick Start

1. **Back the project.** The driver is distributed for [Kickstarter Project](https://www.kickstarter.com/projects/jdmorriso/alpaca-benro-polaris-driver-v20?ref=7xf94o) backers ([licence](https://github.com/ogecko/alpaca-benro-polaris/blob/main/LICENSE)).
2. **Prepare a platform.** [MiniPC](./hardware.md) (recommended), Laptop, Mac, Pi or Docker.
3. **Install the driver.** [Windows](./installation.md) · [macOS](./installation_macos.md) · [Raspberry Pi](./raspberrypi.md) · [Docker](./docker.md)
4. **Connect with Alpaca Pilot.** [Connecting Polaris](./pilot.md#connecting-polaris)
5. **Initial setup.** [Site Location](./initial-setup.md#site-location) · [Alignment](./initial-setup.md#multi-point-alignment) · [Calibration](./initial-setup.md#motor-speed-calibration)
6. **Add your astrophotography app.** [Stellarium](./stellarium.md) · [NINA](./nina.md) · [CCDciel](./ccdciel.md) · [PHD2](./guiding-pulse.md)
7. **Capture images.** [Deep-sky](./dso-imaging.md) · [Planetary](./planetary.md) · [Satellites](./orbitals.md) · [Panoramas](./panoramas.md)

If something goes wrong, the [Troubleshooting Guide](./troubleshooting.md) and [FAQ](./faq.md) cover the most common issues.

## A Beginner's Guide
So you've just got your hands on the Benro Polaris, congratulations! This guide will take you through the basics of astrophotography with the Polaris and introduce you to the world of Alpaca, a powerful tool that can elevate your astrophotography experience. Use it as a learning guide on the various topics to master to become better at astrophotography.
### Learning the Benro Polaris
The Benro Polaris is a fantastic tool for getting started with astrophotography. It's portable, easy to use, is great for astro panaramas and can track the stars for short exposures. We recommend learning how to use the Benro Polaris stand alone initially. Become familiar with its capabilities and limitations. Here's a simplified breakdown of how to use it:

1. Level the Base: Accurate levelling is crucial for precise tracking. Use the built-in bubble level or a separate spirit level, aiming for ±0.3 degrees or better.
2. Power On: The Polaris has a specific power-on sequence: double press and hold the power button until you hear three beeps.
3. Connect with the Benro App: Download and install the Benro Polaris App on your smartphone. Connect to the Polaris using the app via Bluetooth or WiFi.
4. Enter Astro Mode: In the app, switch to Astro Mode, which activates the star tracking functionality.
5. Compass Calibration: Follow the app's instructions to calibrate the compass. This helps the Polaris understand its orientation.
6. Star Alignment: Choose a bright star in the sky and use the app to align the Polaris with it. This step fine-tunes the tracking accuracy.
7. Mount Your Camera: Attach your camera to the Polaris using the Astro Kit's quick-release plate. Ensure it's securely mounted.
8. Compose and Focus: Use your camera's live view to compose your shot and achieve focus. A Bahtinov mask can be helpful for precise focusing.
9. Start Shooting: Set your camera to manual mode, adjust your exposure settings, and start capturing some night sky panaramas!

### Understanding Alpaca
ASCOM Alpaca is a software standard that enables communication between different astronomy devices and applications. The Alpaca Driver is a software driver that implements the ASCOM Alpaca standard for the Benro Polaris. It will help you get more out of your Benro Polaris and allow you to build more advanced skills in astrophotography.

The Alpaca Driver is installed on a separate device (like a mini-PC or laptop) that connects to your Polaris via Wi-Fi. It includes Alpaca Pilot, a browser app for controlling and monitoring the mount from a phone, tablet or PC. Why use Alpaca? The Alpaca Driver unlocks the Polaris's potential by enabling:

* Advanced Software Compatibility: You can use powerful astrophotography applications like Stellarium and Nina to control your Polaris, offering more features and better control than the Benro app.
* Multi-Point Alignment: This feature uses plate-solving technology to refine the Polaris's alignment with multiple reference points, correcting for tripod tilt and significantly improving pointing and tracking accuracy.
* Plate Solving: Precisely center your target by analyzing star patterns in an image and comparing them to a database. This makes framing your shot much easier.
* Remote Control: Operate your setup from the comfort of indoors using a mini-PC and remote desktop software. This is especially helpful in cold weather or for long imaging sessions.
* Autofocus: Alpaca allows integration with autofocus tools like Hocus Focus in Nina, achieving optimal focus for your lens.

A great summary video which shows how Alpaca fits into a typical imaging session can be found in [Using the Benro Polaris with NINA - a game changer!](https://www.youtube.com/watch?v=D3JZOp0TFbk)

### Choosing Equipment
When selecting a camera and lens for astrophotography, what you currently have is probably your best option. If you are purchasing new equipment consider your target and desired outcome. For panoramas, wider focal lengths like 16mm, 24mm, or even 50mm are suitable, capturing a broader view of the Milky Way or nightscapes. For deep-sky objects like nebulae and galaxies, longer focal lengths, such as 135mm, 200mm, 400mm, or even 800mm, are necessary to magnify distant objects.

Faster lenses (with lower f-numbers like f/1.4, f/2.8) are beneficial because they allow more light to reach the camera sensor in a shorter time. This is crucial in astrophotography, as you're often dealing with dim objects. A faster lens allows you to use shorter exposure times while maintaining good image brightness, reducing the impact of tracking errors and capturing more detail. 

Various camera options are available for astrophotography, each with its pros and cons:

* DSLRs: A good starting point, offering a familiar interface and decent image quality.
* Astro-modified DSLRs: These DSLRs have been modified to improve their sensitivity to red wavelengths of light, important for capturing emissions from nebulae.
* Mirrorless Cameras: Becoming increasingly popular for astrophotography due to their compact size, electronic viewfinders, and advanced features.
* Dedicated Astro Camera: Designed specifically for astrophotography, offering high sensitivity, low noise, and cooling capabilities for optimal image quality.

As you become more familiar with Nina, you may want to explore using a dedicated imaging telescope, filters, monochrome cameras, focusers, and other equipment. The choice depends on your budget, experience, and desired level of image quality. 

### Choosing Your Alpaca Setup
We recommend starting out by installing the Alpaca Driver on a laptop with Stellarium.

* Install the Alpaca Driver and Stellarium on your laptop. This setup allows you to control the Polaris from Alpaca Pilot and Stellarium, find deep-sky objects, and watch its position update in real-time.

Once this is successful you may want to consider getting a Mini-PC and installing the Alpaca Driver with Nina for more advanced features.

* A mini-PC allows you to use Nina to control the Polaris, camera, and potentially other equipment. It provides enhanced processing power, remote control, and a better overall user experience. Start by learning how to install and setup Nina. Then move on to learning how to perform an autofocus run, perform plate solving, create a sequence and capture images.

More information on the Alpaca setup can be found in [Architecture](./architecture.md#hardware-architectures) and [Preparing the MiniPC](./hardware.md).
  
#### Installing the Driver
The installation process varies slightly depending on your chosen platform. Step-by-step instructions are in the guides for [Windows](./installation.md), [macOS](./installation_macos.md), [Raspberry Pi](./raspberrypi.md) and [Docker](./docker.md), but here's a simplified overview:

1. Install the Driver: Run the setup script or commands for your platform. They download the driver from GitHub and install Python and the required libraries for you.
2. Start the Driver: Run the Alpaca Driver on your device. Check the driver's log window for confirmation messages.
3. Configure Settings: Open Alpaca Pilot in your web browser and use its Settings page to set your [observing site location](./initial-setup.md#site-location) and other preferences. There is no need to edit configuration files by hand.

#### Connecting the Driver

1. Power On: Level the Polaris and power it on, then enable its Wi-Fi hotspot (usually named "polaris-######").
2. Connect: Use Alpaca Pilot to connect the driver to the Polaris.
3. Enter Astro Mode: Switch to Astro Mode in Alpaca Pilot. You can skip the Benro app's compass and single star alignment, and use Multi-Point Alignment instead.

More information on connecting can be found in the [Alpaca Pilot Guide](./pilot.md#connecting-polaris).

### Learning Stellarium
Become familiar with using Stellarium to identify targets in the night sky and commanding the Polaris to point your camera to them. Some of the benefits you will get from using Stellarium include:

* Extensive Catalogue: Stellarium boasts an expansive catalogue of celestial objects, exceeding what's available in the Benro Polaris App. This allows you to explore a wider range of targets for your astrophotography sessions.
* Telescope Control: Stellarium offers comprehensive control over the Benro Polaris through both the Alpaca ASCOM and SynScan protocols. This means you can use Stellarium to slew to targets, adjust tracking, and synchronise coordinates with the Polaris.
* GOTO Functionality: One of the standout features is the "GOTO Coordinates" capability, enabling you to command the Benro Polaris to move to a selected target with a simple click. This streamlines the process of finding and framing your desired objects.
* Reticle and Field of View: Stellarium displays a reticle that marks the telescope's path across the sky. You can customise the reticle size to match your camera and lens setup, aiding in visualising your framing.
  
To enhance your understanding of Stellarium, consider exploring the following resources:

* Alpaca Documentation: Includes a brief description on [Using Stellarium](./stellarium.md).
* Stellarium's Official Website: The official website (https://stellarium.org/) offers comprehensive documentation, tutorials, and user guides to help you learn the software's features and functionalities.
* Online Communities and Forums: Numerous online communities and forums dedicated to astronomy and astrophotography provide valuable insights, tips, and tutorials on using Stellarium.
* YouTube Videos: Search for "Stellarium tutorials" on YouTube to find a wide range of video guides covering various aspects of the software.

These resources, combined with the insights from the sources, can help you learn Stellarium effectively and leverage its capabilities to enhance your astrophotography experience with the Benro Polaris. 

### Learning NINA
Nina can be overwhelming at first, but start by simply connecting a camera and learning how to take images. As you become more familiar you can integrate other equipment and learn its more advanced features such as sequencing, autofocus, plate solving, polar alignment. 

The Alpaca Documentation on [Using Nina](./nina.md) will guide you through: 

* Equipment Setup: The sources describe how to connect your camera and mount to NINA, providing guidance on the necessary steps and settings.
* Finding Targets: You'll find explanations on using NINA's Sky Atlas to locate celestial objects and how to add them to your imaging sequence.
* Framing Images: The sources detail NINA's Framing Assistant, which helps you visualise and plan your shots, including panoramas.
* Capturing Images: They cover NINA's image capture capabilities, allowing you to control camera settings, take exposures, and monitor the process in real-time.
* Sequencing: You'll learn about setting up image sequences, incorporating actions like autofocus and plate solving.
* Autofocus: The sources explain how to use NINA's autofocus features, including setting up and using the Hocus Focus plugin for improved star detection.
* Plate Solving: They explain how to use plate-solving with NINA and ASTAP to accurately align the Benro Polaris.

In addition to the standard Alpaca documentation here are some additional resources you can use to learn more about Nina.

* NINA's Official Website: The official website for NINA (https://nighttime-imaging.eu/) is a valuable resource for documentation, tutorials, and a user forum where you can ask questions and get help from the community. 
* Astro What Website: The sources recommend the Astro What website for instructions on installing NINA and its prerequisites. This website might also have other helpful resources for learning NINA.
* YouTube Channels: You can find a wealth of information on using NINA on YouTube. The sources specifically recommend the following channels:
    * [Nina, by Chris Woodhouse](https://www.youtube.com/playlist?list=PLsB_vBMDYE_qPSftsM7EHooX1sozEY5zP): A 17-part series of tutorials that cover Nina are the absolute best.
Chris Woodhouse’s NINA 17-part series covers everything
    * [Cuiv, The Lazy Geek Youtube Channel](https://www.youtube.com/@CuivTheLazyGeek): This channel is known for in-depth tutorials on various astrophotography software and equipment.
    * [Patriot Astro Youtube Channel](https://www.youtube.com/watch?v=Ta5t4dCEjNc): This channel provides tutorials and guides focused on NINA and other astrophotography tools.
* Online Forums: Active astrophotography communities like Cloudy Nights (https://www.cloudynights.com/) and Stargazers Lounge (https://stargazerslounge.com/) have dedicated sections for NINA where users share their experiences, tips, and solutions to common problems. 

By utilising these resources, you can gain a strong foundation in using NINA for astrophotography with the Benro Polaris. 

### Learning Sequencing
NINA has two sequencers. The Legacy Sequencer is a simple list of targets and exposures, and is a good place to start. As you add more astronomy equipment, such as filter wheels, focusers, power hubs and dedicated astronomy cameras, it's worth learning NINA's Advanced Sequencer. It builds your imaging session from instructions that you drag into place, so you can:

* Control All Your Equipment: Cool the camera before imaging and warm it afterwards, switch filters, turn power hub outputs and dew heaters on and off, and park the mount when you're done.
* Repeat and Wait: Use loops and conditions to repeat a set of instructions for a number of exposures, for a period of time, or until dawn.
* React to Conditions: Use triggers to run an autofocus when the temperature or star sizes change, or to re-center the target when it drifts.
* Reuse Your Workflows: Save a sequence as a template and reuse it for each new target.

The Advanced Sequencer can look complicated at first, but it isn't once you get the hang of it, and you will never go back to the Legacy Sequencer.

The Advanced Sequencer also gives you access to the Device Actions exposed by the Alpaca Driver, which go beyond the ASCOM standard. Together, they are needed to use the Alpaca Driver's [Sync Guiding](./guiding-sync.md), which runs a Solve and Sync every few minutes during your sequence, and [Panorama Grids](./panoramas.md), which use the `Polaris:PanoGrid` and `Polaris:PanoSlew` Device Actions to step through each panel.

To learn the Advanced Sequencer, you can consider these resources:

* Alpaca Documentation: [Advanced Sequence](./nina.md#advanced-sequence) in the NINA guide describes the instructions that work with the Alpaca Driver, and the [Device Actions](./alpaca-api.md#device-actions) reference lists each Device Action with examples.
* NINA Documentation: The [Advanced Sequencer](https://nighttime-imaging.eu/docs/master/site/sequencer/advanced/advanced/) section of the NINA documentation explains each instruction, condition and trigger.

### Learning Guiding
Multi-Point Alignment gives the Polaris an accurate pointing and tracking model, but small errors remain. The Polaris has a periodic error of over 14 arc minutes on a repeating 35-minute cycle, as well as mechanical errors that cause slow drift. At wide focal lengths these errors are barely visible, but at 200mm and beyond they show up as drifting targets and trailed stars. Guiding measures where the stars actually are and corrects the mount as you image, allowing longer focal lengths and longer exposures.

The Alpaca Driver supports two approaches to guiding. We recommend learning them in this order:

* Sync Guiding: Start here, as it needs no extra hardware. Your imaging software plate solves an image from your main camera every 1 to 3 minutes and syncs the result, and the driver treats any remaining error as a guiding correction. In NINA, this is a "Solve and Sync" instruction added to your imaging sequence.
* Pulse Guiding: Once you are comfortable with sync guiding, you can add a small guide scope and guide camera. PHD2 watches a guide star and sends small corrections to the driver every few seconds, correcting errors within a single exposure. This suits the longest focal lengths and exposures beyond 2 minutes.

Both approaches also feed the driver's Periodic Error Correction, which learns how your Polaris drifts and corrects for it before it shows up in your images.

To learn guiding, you can consider these resources:

* Alpaca Documentation: [Sync Guiding](./guiding-sync.md) explains both approaches and Periodic Error Correction, [Worm Gear Calibration](./initial-setup.md#worm-gear-calibration) measures your mount's worm gears, and [Pulse Guiding](./guiding-pulse.md) walks you through setting up PHD2, calibrating, pulse guiding and improving guiding performance with the Polaris.
* PHD2 Documentation: The [PHD2 User Manual](https://openphdguiding.org/manual/) covers every feature, and the [PHD2 Best Practices](https://openphdguiding.org/phd2-best-practices/) guide explains how to get good results quickly.
* Online Communities and Forums: The [PHD2 user forum](https://groups.google.com/g/open-phd-guiding) is very active, and the developers will review your guide logs if you ask for help.


### Learning Siril
Siril is a powerful, open-source image processing software widely used in astrophotography for tasks like stacking, calibration, and enhancing astrophotography images. Once you have a set of images, you can use image stacking like Siril, to combine multiple images of the same target. This image stacking can improve the signal-to-noise ratio, revealing fainter details and reducing noise. Siril is a free and powerful software for astrophotography image processing, including stacking.

Learning to use stacking software like Siril is another deep area to develop skills in. Key areas to learn include 

* Using an automated script to perform the stacking. 
* Understaning how to manually stack images to alter the process.
* Learning how to manually stretch and optimise the final image.
* How enhance nebula with star removal and other techniques.

To learn Siril, you can consider these resources:

* Siril's Official Website: The official website (https://siril.org/) offers comprehensive documentation, tutorials, and a user forum where you can find answers to your questions.
* YouTube Tutorials: Many astrophotographers create tutorials demonstrating Siril's functionalities and workflows. Searching for "Siril tutorials" on YouTube should yield helpful results.
* Online Communities and Forums: Astrophotography communities like Cloudy Nights (https://www.cloudynights.com/) and Stargazers Lounge (https://stargazerslounge.com/) have sections dedicated to Siril, where users share their experiences, tips, and troubleshooting advice.


### Learning AutoStakkert!
The Benro Polaris can also image the planets, and AutoStakkert! is the free program at the heart of planetary imaging. Planets are small and bright, so instead of a few long exposures you record a video of thousands of very short exposures. AutoStakkert! then grades every frame, keeps only the sharpest, and aligns and stacks them. This "lucky imaging" freezes the shimmer of the atmosphere and reveals detail such as Jupiter's cloud bands and Saturn's rings. A good stack starts with a good video, so key areas to learn include:

* Choosing a Focal Length: Planets are tiny, so use your longest lens with an extender, ideally on a small astronomy camera with small pixels.
* Capturing Video: Use SharpCap with an astronomy camera, or EOS Utility with a Canon camera. Keep exposures short, set the gain so the histogram stays clear of the right-hand side, and use USB 3 for a high frame rate.
* Stacking with AutoStakkert!: Analyse the video to grade every frame, stack the best 10 to 25 percent using a grid of alignment points, and use Drizzle 3.0x to recover finer detail.
* Composing a Wider Shot: Combine the stacked planet with a longer exposure that shows its moons.

The [Planetary Imaging](./planetary.md) guide covers each of these steps, using an image of Saturn and its moons as an example.

### Further Learning

* Alpaca Driver Documentation: This is the go-to resource for detailed instructions, troubleshooting tips, and information on specific features. The documentation can be found at [Home](./index.md) and on the [documentation site](https://ogecko.github.io/alpaca-benro-polaris/).
* Nina User Manual and Tutorials: Nina has extensive documentation and numerous video tutorials available online to guide you through its features and workflows. The Alpaca Driver documentation points you to a number of specific Nina resources.
* Stellarium User Guide: Stellarium's website and user forum offer valuable information on using the software for astrophotography planning and telescope control. The Alpaca Driver documentation points you to a specific Stellarium resource at the University of Western Australia.
* Siril Tutorials: Explore online tutorials and videos to learn how to use Siril effectively for image stacking, processing, and enhancing your astrophotos.

Note: This document provides a basic introduction to the Benro Polaris and Alpaca. For in-depth information and specific instructions, please refer to the resources mentioned above and the Alpaca Driver's comprehensive documentation.




