[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

## Alpaca Driver and Mobile Devices

### A1 – Is Alpaca a physical device?
No. Alpaca is an astronomy standard, a kind of universal language that lets astronomy apps and devices communicate. The **Alpaca Driver** is a Python-based program that acts as a translator between your Benro Polaris and other Alpaca-compatible software.

### A2 – Does the Alpaca Driver run on the Polaris itself?
Not currently. The Driver runs on a separate device, like a mini-PC, Laptop, MacBook, Raspberry Pi, or Desktop, that connects to the Polaris via Wi-Fi. This keeps the Polaris firmware untouched while allowing more powerful processing and flexibility.

### A3 – Can I run the Alpaca Driver on my phone or iPad?
Not directly. The Driver requires a Python runtime and continuous background processing, something mobile platforms like iOS and Android don’t reliably support due to battery-saving restrictions. Even the current Polaris app struggles with power drain during extended use.

However, you can still use your phone or tablet to **control** the system remotely:
- Use the **Alpaca Pilot App** via any modern browser (Chrome, Safari, Firefox, Edge) on mobile or tablet.
- Use **Stellarium PLUS** (iOS/Android) to control the Polaris via SynScan protocol.
- Use **Remote Desktop** apps to control your mini-PC from a phone or tablet and operate tools like NINA."

### A4 – Can I run the Alpaca Driver on macOS?
Yes. The Alpaca Driver runs natively on macOS and is a fully supported platform. However, some companion applications have platform-specific limitations:
- NINA (for plate-solving, sequencing, autofocus) is Windows-only. A similar application called CCDciel can be used on macOS.
- Stellarium PLUS is available as a mobile app for iOS and Android

If you're using macOS, you can run the Driver directly and pair it with Stellarium Desktop or other Alpaca-compatible tools. 

### A5 – Why do I need a PC or mini-PC?
The Alpaca Driver maintains real-time communication with the Polaris and exposes multiple control interfaces, including Alpaca, SynScan, HTTP, WebSockets, and Bluetooth. It also supports advanced features including plate-solving (via Nina/ASTAP), extended image sequencing (via Nina), QUEST modeling, Orbital tracking, PID-based motion control.  

These capabilities require:
- Persistent background processing without interruption 
- Concurrent handling of multiple communication stacks
- Real-time processing for time critical tasks
- Sufficient CPU and memory resources to support compute-intensive tasks
- Sufficient file storage for long imaging sessions

Mobile devices, while convenient, aren’t designed for this kind of sustained workload. A mini-PC offers the stability, performance, and flexibility needed.

### A5 – Will mobile support improve in the future?
Possibly. There are promising directions:
- Embedding the Driver into Polaris firmware 
- Potentially exploring lightweight plate-solving on mobile devices

There is an open feature request to patch the Polaris firmware and embed the Driver directly into the device. While technically feasible, it’s a complex effort with firmware risks and IP concerns. It’s tracked as issue #33: Patch Polaris firmware to run Alpaca natively, but not planned for V2.0.

For now, the best experience comes from pairing the Polaris with a mini-PC and using mobile devices as remote interfaces.


# Benro Polaris Capability Questions

### B1 - Can the Benro Polaris really be used for Deep Sky Photography?
Yes, you can definitely use the Benro Polaris for deep-sky photography, but there are limitations! As an Alt/Az mount without auto-guiding, you're limited to relatively short exposures to avoid star trails. However, by combining a good camera, a longer lens (up to 800mm), and the advanced features unlocked by the Alpaca Benro Polaris Driver and software like Nina, you can capture stunning images of deep-sky objects. 

Think of it this way: 
* Shorter Exposures are Key: Because the Benro Polaris isn't an equatorial mount, you need to keep your exposures short to prevent star trails.
* Stacking is Your Friend: To compensate for shorter exposures and capture fainter details, you'll use image stacking techniques. Nina can help you capture sequences of images that you'll combine later during processing.
* Software Enhances Hardware: The Alpaca Benro Polaris Driver unlocks features like plate-solving and precise target centering, significantly improving your results.

### B2 - What is the longest Focal Length that Benro Polaris can track with?
The maximum focal length you can effectively use with the Benro Polaris for astrophotography depends on factors like your camera, lens, the accuracy of your polar alignment, and even environmental conditions.

Here's some results from the Beta Testers:
* 800mm with Success: One user successfully captured deep-sky images using an 800mm lens and exposures up to 15 seconds. Stacking around 240 images resulted in a high-quality, hour-long exposure. 
* 1750mm Equivalent Focal Length Achieved: Another user, Vladimir, pushed the limits further, achieving impressive results at an equivalent focal length of 1750mm by combining a Sigma 120-400mm lens with a 1.4x extender and a ZWO ASI585MC camera. This demonstrates the Benro Polaris's potential for longer focal lengths with the right equipment and settings. 
  
Keep in mind that longer focal lengths amplify any tracking errors, making precise polar alignment and potentially shorter exposures crucial.

### B3 - Can the Alpaca Project improve aiming performance?
Yes, the Benro Polaris often exhibits consistent aiming inaccuracies, especially after re-engaging sidereal tracking post-slewing. The Alpaca Driver V2.0 dramatically enhances mount accuracy, stability and responsiveness. The new PID Motion control eliminates backlash compensation, improves aiming accuracy, manages acceleration profiles, and support real-time redirection.

### B4 - Can the Alpaca Project improve tracking performance?
Yes, significantly. Alpaca V2.0 introduces major improvements to tracking precision and capabilities. Key improvements include
- **PID Motion Control:** The Driver features a real-time PID-based motion controller that replaces the native Polaris firmware, delivering smoother tracking, faster recovery from disturbances.
- **Plate-Solving:** By integrating with tools like ASTAP and NINA, the Driver enables precise target acquisition and automatic centering, correcting for mount misalignment.
- **Multi-Point Alignment:** The Driver supports QUEST modeling, allowing users to build a multi-point sky model that compensates for polar misalignment, cone error, and mount flexure.
- **Pulse-Guiding:** ASCOM Alpaca pulse-guiding support enables real-time corrections from guiding software like PHD2, improving long-exposure tracking accuracy and eliminating drift.
- **Orbital Tracking:** The Driver can track over 32,000 satellites, planets, and moons using real-time TLE data, updating mount setpoints every 200 ms for accurate tracking of fast-moving or dynamic targets.

### B5 - What is the heaviest load the Polaris can handle?
The Benro USA Site claims the Astro version of the Polaris can handle a load of 7 kg (15.4 lbs). Pretty impressive for such a small mount, without a counterweight. 

I have tested the performance of the Polaris with my rig up to around 4.4kg (Canon R5, RF 800mm lens, Dew Heater, Mini-PC, Gemini Focuser, ArcaSwiss Mounting Bar, Svbony 50mm Guide Scope, Touptek GPM462M Guide Camera). The Polaris seems to easily handle this load and performs sidereal tracking well. 

# Nina Capability Questions
### N1 - How can I connect both Nina and BP App to my Camera via USB?
You don't need to connect your camera to both Nina and the Benro Polaris App simultaneously. Choose one or the other. Once you've set up your mount, Nina can handle all imaging functions, including:
* Autofocus
* Plate Solving
* Framing
* Image Sequencing

After capturing your images in Nina, you can always disconnect your camera and go back to using the BP App if needed.

### N2 - Do I still need to plug my camera into the Benro Polaris?
When using Nina or CCDciel for imaging, you don't need to keep your camera plugged into the Benro Polaris. Once the mount is set up, connect your camera directly to the mini-PC running Nina via USB.

Nina takes over. Focusing: Using your camera's lens autofocus motor or an external focuser. Plate Solving: To confirm and correct the Benro Polaris's pointing. Image Capture: Taking sequences of light, dark, bias, and flat frames.

### N3 - Can Nina access the Cameras SD Card?
No, Nina doesn't directly access the images stored on your camera's SD card. Instead, it communicates directly with the camera through the USB cable using either a native camera driver (for supported Canon and Nikon cameras) or an ASCOM camera driver (for Sony and other camera models). 

This direct communication allows Nina to 
* Control camera settings
* Capture images
* Download images directly to your mini-PC's hard drive

### N4 - Can I use Nina on my Mobile Device?
Nina is designed as a Windows application and works best on a desktop, laptop, or mini-PC. However, you can indirectly use Nina from your phone or tablet with a remote desktop app. These apps allow you to control a computer remotely over Wi-Fi or a mobile network.

Keep in mind that using Nina via remote desktop from a mobile device might not provide the ideal user experience due to the smaller screen size and potential lag. 

### N5 - Can Nina generate a meta data for each image?
Yes, Nina can do this! It has a handy plug-in called Session Manager that can record various metadata for each image, including:

* Coordinates (RA/Dec): So you know exactly where each image was pointing.
* Weather Conditions: Temperature, humidity, etc., which can be useful for analysis.
* Target Information: The object you were imaging.
* Star Detection Stats

This information is saved in CSV files, making it easy to import and use in other astrophotography software.


# Stellarium Usage Questions
### S1 - Will Stellarium work via Wifi or is a cable necessary?
Stellarium doesn't require a USB connection to work with the Alpaca Benro Polaris Driver. It can connect wirelessly through your Wi-Fi network. This means you can use Stellarium on various devices:

* Mini-PC: For a dedicated astrophotography setup.
* Laptop/Desktop: For planning and control from your primary computer.
* iPhone/Android Phone/iPad: For a portable planetarium and control interface.

### S2 - Will Stellarium work on the same phone as BP App?
Yes, you can use Stellarium on the same phone where you have the Benro Polaris App installed. In the past, the BP App needed to run in the background. However, the Alpaca Benro Polaris Driver can now keep the Polaris Wi-Fi connection alive even after you close the BP App. This is great for saving battery life on your phone.

