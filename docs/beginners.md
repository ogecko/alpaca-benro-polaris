# Benro Polaris and Alpaca: A Beginner's Guide to Astrophotography
So you've just got your hands on the Benro Polaris, congratulations! This guide will take you through the basics of astrophotography with the Polaris and introduce you to the world of Alpaca, a powerful tool that can elevate your astrophotography experience. Use it as a learning guide on the various topics to master to become better at astrophotography.
## Getting Started with the Benro Polaris
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

## Understanding Alpaca and How It Fits In
ASCOM Alpaca is a software standard that enables communication between different astronomy devices and applications. The Alpaca Benro Polaris Driver (ABP) is a softare driver that implements the ASCOM Alpaca standard. It will help you get more out of you Benro Polaris and allow you to build more advanced skills in astrophotography. 

The Alpaca Benro Polaris Driver (ABP) is installed on a separate device (like a mini-PC or laptop) that connects to your Polaris via WiFi. Why use Alpaca? The ABP Driver unlocks the Polaris's potential by enabling:
* Advanced Software Compatibility: You can use powerful astrophotography applications like Stellarium and Nina to control your Polaris, offering more features and better control than the Benro app.
* N-Point Alignment: This feature uses plate-solving technology to refine the Polaris's alignment with multiple reference points, significantly improving tracking accuracy.
* Plate Solving: Precisely center your target by analyzing star patterns in an image and comparing them to a database. This makes framing your shot much easier.
* Remote Control: Operate your setup from the comfort of indoors using a mini-PC and remote desktop software. This is especially helpful in cold weather or for long imaging sessions.
* Autofocus: Alpaca allows integration with autofocus tools like Hocus Focus in Nina, achieving optimal focus for your lens.

A great summary video which shows how Alpaca fits into a typical imaging session can be found in [Using the Benro Polaris with NINA - a game changer!](https://www.youtube.com/watch?v=D3JZOp0TFbk&t=33s)

## Choosing the Right Imaging Equipment
When selecting a camera and lens for astrophotography, what you currently have is probably your best option. If you are purchasing new equipment consider your target and desired outcome. For panoramas, wider focal lengths like 16mm, 24mm, or even 50mm are suitable, capturing a broader view of the Milky Way or nightscapes. For deep-sky objects like nebulae and galaxies, longer focal lengths, such as 135mm, 200mm, 400mm, or even 800mm, are necessary to magnify distant objects.

Faster lenses (with lower f-numbers like f/1.4, f/2.8) are beneficial because they allow more light to reach the camera sensor in a shorter time. This is crucial in astrophotography, as you're often dealing with dim objects. A faster lens allows you to use shorter exposure times while maintaining good image brightness, reducing the impact of tracking errors and capturing more detail. 

Various camera options are available for astrophotography, each with its pros and cons:
* DSLRs: A good starting point, offering a familiar interface and decent image quality.
* Astro-modified DSLRs: These DSLRs have been modified to improve their sensitivity to red wavelengths of light, important for capturing emissions from nebulae.
* Mirrorless Cameras: Becoming increasingly popular for astrophotography due to their compact size, electronic viewfinders, and advanced features.
* Dedicated Astro Camera: Designed specifically for astrophotography, offering high sensitivity, low noise, and cooling capabilities for optimal image quality.

As you become more familiar with Nina, you may want to explore using a dedicated imaging telescope, filters, monochrome cameras, focusers, and other equipment. The choice depends on your budget, experience, and desired level of image quality. 

## Choosing Your Alpaca Setup
We recommend starting out by installing Alpaca Benro Polaris on a laptop with Stellarium. 
* Install the ABP Driver, Python, and Stellarium on your laptop. This setup allows you to control the Polaris, find deep-sky objects, and watch its position update in real-time. 

Once this is successful you may want to consider getting a Mini-PC and installing Alpaca with Nina for more advcanced features.
* A mini-PC allows you to use Nina to control the Polaris, camera, and potentially other equipment. It provides enhanced processing power, remote control, and a better overall user experience. Start by learning how to install and setup Nina. Then move on to learning how to perform an autofocus run, perform plate solving, create a sequence and capture images.

More information on the Alpaca Setup can be found in the [Hardware Guide](./hardware.md).
  
### Installing the Alpaca Benro Polaris Driver
The installation process varies slightly depending on your chosen platform (Windows, MacOS, Raspberry Pi). Detailed instructions can be found in the ABP project's documentation, but here's a simplified overview:
1. Install Python: Make sure you have Python 3+ installed on your device.
2. Download the Driver: Get the latest ABP Driver zip file from the Github repository.
3. Extract and Install: Extract the zip file to a convenient location. Follow the platform-specific instructions to install the driver and its dependencies.
4. Configure Settings: You'll need to adjust some settings in a configuration file (config.toml), like your location coordinates and other preferences.

### Connecting the Driver to Your Polaris
1. Initial Setup with the Benro App: Follow the steps mentioned earlier to level, power on, calibrate, and align your Polaris using the Benro app.
2. Connect Your Device: Connect your laptop/mini-PC to the Polaris's WiFi hotspot (usually named "polaris-######").
3. Start the Driver: Run the ABP Driver on your device. Check the driver's log window for confirmation messages.

More information on installing Alpaca can be found in the [Installation Guide](./installation.md). The physical connection of a typical mini-PC setup is shown in the 

## Learning Stellarium
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

## Learning NINA
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
  * Cuiv, The Lazy Geek Youtube Channel: This channel is known for in-depth tutorials on various astrophotography software and equipment.
  * Patriot Astro Youtube Channel: This channel provides tutorials and guides focused on NINA and other astrophotography tools.
* Online Forums: Active astrophotography communities like Cloudy Nights (https://www.cloudynights.com/) and Stargazers Lounge (https://stargazerslounge.com/) have dedicated sections for NINA where users share their experiences, tips, and solutions to common problems. 

By utilising these resources, you can gain a strong foundation in using NINA for astrophotography with the Benro Polaris. 

## Learning Siril
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

## Resources for Further Learning include:
* Alpaca Benro Polaris Project Documentation: This is the go-to resource for detailed instructions, troubleshooting tips, and information on specific features. The documentation can be found at [Home](../README.md) . 
* Nina User Manual and Tutorials: Nina has extensive documentation and numerous video tutorials available online to guide you through its features and workflows. The Alpaca Benro Polaris documentation points you to a number of specific Nina resources.
* Stellarium User Guide: Stellarium's website and user forum offer valuable information on using the software for astrophotography planning and telescope control. The Alpaca Benro Polaris documentation points you to a specific Stellarium resource at the University of Western Australia.
* Siril Tutorials: Explore online tutorials and videos to learn how to use Siril effectively for image stacking, processing, and enhancing your astrophotos.

Note: This document provides a basic introduction to the Benro Polaris and Alpaca. For in-depth information and specific instructions, please refer to the resources mentioned above and the ABP project's comprehensive documentation.




