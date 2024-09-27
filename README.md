[Home](./README.md) | [Hardware Guide](docs/hardware.md) | [Installation Guide](docs/installation.md) | [Using Stellarium](docs/stellarium.md) | [Using Nina](docs/nina.md) | [Troubleshooting](docs/troubleshooting.md) | [FAQ](docs/faq.md)

# Introduction
![Overview](docs/images/abp-overview.png)


Are you interested in trying your hand at amateur astrophotography? Invest in a [Benro Polaris with its Astro Kit](https://www.benro-polaris.com/), and this project will transform it from a great Tripod Head to a full-featured, open Telescope Mount. This project aims to provide users with a way to control their Benro Polaris using more advanced astrophotography software, including [Stellarium](https://stellarium.org/en/), [Nina](https://nighttime-imaging.eu/), and other applications that support the ASCOM Alpaca platform. 

# Intended Audience
The project documentation and features target individuals familiar with astrophotography concepts and software like deep sky astronomy, image sequencing, plate solving, polar alignment, equatorial coordinates, and image stacking. The first release is intended for users comfortable with technical setups involving MacOS or Windows, mini-PCs, Command Windows, and Networks, as these are presented as options for running the Alpaca-Benro-Polaris Driver.

# Project Purpose
The [Benro Polaris](https://www.benro-polaris.com/) tripod head is a great product. It's manufactured to a high standard, comes in a compact and sturdy design, and its mobile App has many easy-to-use features. Although its not cheap, it is cheaper than a modern telescope mount like the [ZWO AM3 Harmonic Equatorial Mount](https://www.zwoastro.com/product/zwo-am3-harmonic-equatorial-mount/). The Polaris can also be used for other photography projects beyond astro-photography.

That said, the mobile App and firmware updates appear to have slowed down. Many of the promised features from the original [Kickstarter Project](https://www.kickstarter.com/projects/jdmorriso/alpaca-benro-polaris-driver?ref=9a035f)  haven't materialised. We are still waiting for 3 Point Alignment, a larger catalogue of deep sky objects, linking with planetarium software, improved sequencing of image capture, plate solving and framing. The product has more potential if only we could enable it.

That is what this project is all about. The intention is to open up the Benro Polaris with an HTTP-based [REST API](https://www.ibm.com/topics/rest-apis) that will allow other applications to leverage this great platform. 

The Alpaca Benro Polaris (`ABP`) supports a standard [ASCOM](https://ascom-standards.org/) device interface called  [ITelescopeV3 interface](https://ascom-standards.org/Help/Developer/html/T_ASCOM_DeviceInterface_ITelescopeV3.htm) to control the Benro Polaris tripod head. This standard interface supports applications like [Stellarium Desktop](https://stellarium.org/en/) (a free open-source planetarium application) and [Nina](https://nighttime-imaging.eu/) (Nighttime Imaging 'N' Astronomy - An astrophotography imaging suite). 

The ABP also supports a subset of the [SynSCAN protocol](https://inter-static.skywatcher.com/downloads/synscanserialcommunicationprotocol_version33.pdf) over the network. This allows the Driver to support mobile applications like [Stellarium Mobile PLUS](https://stellarium-labs.com/stellarium-mobile-plus/) or [Sky Safari 7 Plus and Pro](https://skysafariastronomy.com/).

The priorities of this open-source project reflect feedback from the [Polaris Camera Controller Global Group](https://www.facebook.com/groups/326138891873755). This group provided great suggestions and encouragement for this project, with over 120 supporting it in just 2 days. I've summarised the feedback comments below with features getting the most requests listed as high-priority. The open-source project meets ALL feasible requests. There are still some challenges to the 3-point alignment; although we have some ideas!

![Overview](docs/images/abp-priorities.png)

# Documentation Overview
The Alpaca Benro Polaris has documentation to help you prepare your hardware, install software and use the features in Stellarium and Nina. Since the ABP is an ASCOM standard driver, many other applications can make use of it. Let us know what you've found that works.

## [Release Notes](./docs/release-notes-v1.0.0.md)
The [Release Notes](./docs/release-notes-v1.0.0.md) is a reference document that outlines new features, bug fixes, known issues and untested features of the Alpaca Benro Polaris Driver. The new features are organised by application to help document what new capabilities are enabled by using the driver with a given application.

## [Hardware Guide](./docs/hardware.md)
The [Hardware Guide(s)](./docs/hardware.md) outlines the recommended hardware platforms for running the Alpaca Benro Polaris Driver, ranging from basic laptop setups to more advanced mini-PC configurations for controlling all astronomy equipment. It offers step-by-step guidance on setting up a "NinaAir" mini-PC, ensuring users can establish a robust and dedicated astrophotography control center.

## [Installation Guide](./docs/installation.md)
The [Installation Guide](./docs/installation.md) provides step-by-step instructions for installing and running the Alpaca Benro Polaris Driver on Windows 11 or MacOS, including setting up prerequisite software like Python and configuring Stellarium for initial use. It walks users through each step of the installation process, ensuring they can successfully install the driver and connect to their Benro Polaris.

## [Using Stellarium](./docs/stellarium.md)
The [Using Stellarium Guide](./docs/stellarium.md) focuses on using Stellarium with the Benro Polaris, explaining how to establish a connection, control the mount, and leverage Stellarium's features. It outlines the compatibility of different Stellarium versions and protocols, guiding users on connecting their setup and navigating Stellarium's interface for effective telescope control.

The University of Western Australia has [A Guide To Using Stellarium](https://nighttime-imaging.eu/docs/master/site/pdf/Manual.pdf) for a more complete reference.

## [Using Nina](./docs/nina.md)
The [Using Nina Guide](./docs/nina.md) explains how to use Nina with the Benro Polaris for capturing, focusing, and aligning astrophotography images. It delves into essential features of Nina, such as equipment setup, target finding, image sequencing, and autofocus techniques, empowering users to optimize their astrophotography workflow.

For more detailed reference material refer to the thorough [Nina online documentation](https://nighttime-imaging.eu/docs/master/site/) or [Nina PDF Manual](https://nighttime-imaging.eu/docs/master/site/pdf/Manual.pdf) for the standard documentation. You can find some very informative, long form videos on Nina at the following youtube channels.
* [Cuiv, The Lazy Geek Youtube Channel](https://www.youtube.com/@CuivTheLazyGeek)
* [Patriot Astro Youtube channel](https://www.youtube.com/@PatriotAstro)

## [Troubleshooting and FAQ](./docs/troubleshooting.md)
We have included a comprehensive [Troubleshooting Guide](./docs/troubleshooting.md) which provides solutions for common issues encountered while setting up and using the Alpaca Benro Polaris Driver. It offers practical advice on starting the Benro Polaris device, establishing a network connection, and troubleshooting plate-solving issues with Nina and ASTAP.

A list of [Frequently Asked Questions](./docs/faq.md) addresses common questions about the Alpaca standard, the Benro Polaris's capabilities, and the use of Nina and Stellarium for astrophotography. It clarifies misconceptions about Alpaca and provides realistic expectations for using the Benro Polaris for deep-sky photography, emphasizing the importance of proper equipment and settings.

## [Beta Test Results](./docs/betatest.md)
The [Beta Test Results](./docs/betatest.md) provides an analysis and summary of the beta test results and feedback for the Alpaca Benro Polaris Driver, highlighting its strengths and areas for improvement. Additionally, it outlines the guidelines followed during the beta testing phase and lists the individuals involved along with their testing environments and experiences.

# Recognition
I'd like to thank the following people who helped make this project a reality:

## Technical Expertise
* Vladimir Vyskocil - for his significant contribution to the project, work on the protocol, exploring an initial prototype, being a sounding board, and inspiration for this project.
* Stefan Berg - for creating and maintaining N.i.n.a. 
* Robert B. Denny - for his work in writing a template for Alpaca drivers everywhere.
* Steven Byrnes - and the SeeStar_alp driver developers for sharing their great work.
* Peter Simpson - for leading the ASCOM architecture and developing the conformance test suite.
* ASCOM Initiative Members - for their tireless standards work to improve astronomy  device  compatibility. 

## Beta Testers
The Beta Testers' perseverance and feedback helped improve the documentation and final quality of the software. I greatly appreciate their encouragement and the testing they performed.

* Vladimir Vyskocil 
* Spiderx01 (William Siers) 
* 5x5Stuido (John Harrison) 
* bakermanz (Mark) 
* Ladislav (Ladi Slav) 
* saltyminty (Mingyang Wang) 
* hqureshi79 (Humayun Qureshi) 
* Chris-F2024 
* Cosimo (Cosimo Streppone) 
* RjhNZ (Richard Healey)
* Matt17463 (Matthew McDaniel)
* Cynical Sarge (Andrew Sargent)

## Kickstarter Backers
I want to thank all the 120 [Kickstarter Project Backers](https://www.kickstarter.com/projects/jdmorriso/alpaca-benro-polaris-driver/community?ref=9a035f), especially those who pledged Game-Changing and That's-Awesome amounts. I will keep the [Kickstarter project](https://www.kickstarter.com/projects/jdmorriso/alpaca-benro-polaris-driver?ref=9a035f) open to continue funding ongoing support and making enhancements to this project. PS. Let me know if you want to be anonymous.

|  GAME CHANGER | Thats Awesome | Thats Awesome | Thats Awesome |
|:---:|:---:|:---:|:---:|
| **Devon** | Adrian Squirrell | Ed | Max Izod |
| **Evie-Jeane Vyse** | Alan Smallbone | Fank Heirnash | Michael C |
| **Mack Cameron** | Alessio Zanotti | Fernando Ribeiro | Mike Drinkwater |
| **Mark Bahu** | Alex Murdoch | Fernando Villaverde Gaviña | Moshe Salama |
| **Peter** | Alvin Christie | Humayun Qureshi | Nagendra Narayan |
| **Richard Swaim** | Amy Kemp | Ian Cannan | Patryk Lesiecki |
| **Simone Chiari** | Andreas Bichler | Ian Morgan | Paul Moulton |
| **William Siers** | Andrew Roberts | Ilya Chernikov | Paul Olsavsky |
|  | Baha Baydar | Jack Cale | Paul Rickwood |
|  | Bikram Ghosh | James White | Paul Vandeputte |
|  | Bill Lazar | John | Peps Choufme |
|  | Blair Dunlop | Jonathan Shribman | Pudeldestodes |
|  | Boyce Fitzgerald | Juan Manuel López Fernández | Richard Healey |
|  | Brad Anderson | Juan Martinez | Rob Bristow |
|  | Cameron Palmer | Kaingc | Roger Good |
|  | Carlo Mascellani | Kym Wallis | Sandra Coffey |
|  | Charles T. Simet | Ladislav Svoboda | Santanu Majumder |
|  | Dan Suskin | Mahmudur Rahman | Simon Modera |
|  | David Proudfoot | Mangoe | Steve Renter |
|  | Donald Dunbar | Mark Penberthy | Steven |
|  |  |  | Stlwarehouse |




## User Group Feedback
* I'd really like to thank everyone who posted feedback on the [Polaris Camera Controller Global Group](https://www.facebook.com/groups/326138891873755).

* Many users expressed encouragement, excitement and great support for the project, using phrases like:
  * "Just wow!", "So much of this yes", "Love it", "This is a cool project", "Would be awesome", "Yes yes please", "I'm all in", "Absolute game changer", "Great", "Please make this work", "Very exciting", "Super job", "Wow Wonderful", "100% Super enthusiastic about this", "This is absolutely wicked", "Sounds Great"
  * "Awesome initiative", "Amazing work", "Most certainly very worthwhile",  "Bring it on !!", "I am TOTALY blowen away by this", "Outstanding work", "Keeping a bllodshot eye on this thread!", "I think we are going to have to name a star after you", "not a star, an entire Nebula, the Morrison Nebula!" :-)
* Specific features that received positive feedback included:
  * Plate solving, three-point alignment, integration with Stellarium, and the ability to use Nina with the Benro Polaris.
* Users expressed a desire to: 
  * Improve the Benro Polaris's tracking accuracy, particularly with longer lenses.
  * Make the Benro Polaris a more portable astrophotography solution.
  * Offer help with beta testing the project.
  * Reach out to Benro for backing.
* Overall, the feedback from the Polaris Camera Controller Global Group was overwhelmingly positive, with users expressing enthusiasm for the project's potential to unlock the full capabilities of the Benro Polaris.



## Organisations and Services
* Benro - for creating and distributing such great products, including the Benro Polaris.
* Napkin AI - for making it so easy to create all the diagrams.
* Copilot AI - for attempting to help with coding.
* Notebook LM - for the [Deep Dive Podcast](https://youtu.be/puRRH7VJ6cw) and helping synthesize the beta feedback.
* Grammarly - for reviewing and editing the documentation.
* GitHub - for hosting git and providing many vanilla dev support tools.
* Kickstarter - for helping so many creatives.

And finaly, just a brief note about risks....

## Caution - Use at own Risk
Please be aware that this is not official Benro Software. If you decide to use it - you are doing so at your own risk.

There is a chance of voiding the warranty or damaging your Benro Polaris hardware. There is a chance that you may use the driver/hardware in a way, unintended by its design. The driver is not official Benro software. They may not support you. Due to the extensive testing, the risk of hardware damage is very low.

Also note that the ASCOM Alpaca standard is not secure. It is open by design. Simply stated, Alpaca and network security are separate things. Only use within an isolated protected virtual or local network.

Finally, it's important to note that while the Alpaca Benro Polaris Driver unlocks significant potential from the Benro Polaris, it cannot entirely overcome the device's inherent hardware limitations. Users aiming for extended exposures, particularly with longer focal lengths, might still encounter tracking errors despite the driver's enhancements. Therefore, managing your expectations regarding the Polaris's capabilities, especially for deep-sky astrophotography, is crucial.
