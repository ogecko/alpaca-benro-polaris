[Home](../README.md) | [Hardware](./hardware.md) | [Installation](./installation.md) | [Pilot](./pilot.md) | [Control](./control.md) | [Stellarium](./stellarium.md) | [Nina](./nina.md) | [Guiding](./guiding.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Polaris - Camera Controller Global Group

---

David Morrison - PREVIEW
Top contributor
Alpaca Driver V2.0 is coming with pulse-guiding, rotator, three star alignment and much more. I need your help. More will follow.
David Morrison
Pavel Vorobiev Uli Fehr The Alpaca Driver is an open-source project that enables third-party applications like NINA and Stellarium to control the Benro Polaris mount. Version 2.0 is nearing completion, and we’re preparing to launch the Beta testing phase. This post serves as an early heads-up for those interested in getting involved, testing new features, and helping shape the final release. Stay tuned—this community's feedback will be crucial in helping you make the most of your Polaris yet.
4d
Reply


David Morrison
Author
Pavel Vorobiev Uli Fehr The Alpaca Driver is an open-source project that enables third-party applications like NINA and Stellarium to control the Benro Polaris mount. Version 2.0 is nearing completion, and we’re preparing to launch the Beta testing phase. This post serves as an early heads-up for those interested in getting involved, testing new features, and helping shape the final release. Stay tuned—this community's feedback will be crucial in helping you make the most of your Polaris yet.
1w
Reply
Uli Fehr
  · 
David Morrison That's great, shame on me - didn't recognized this project until now.😲
1w
Reply


Billy Bass
I would be more than happy to help, but I still have yet to figure out why NINA is unable to recognize my camera when I try connecting my windows tablet; I have all the Nikon software installed and the Nikon software doesn’t seem to have any issues connecting or communicating, but it makes it a bit difficult to try using it with the Alpaca driver.
2w
Reply
Baha Baydar
Billy Bass Make sure the Nikon software isn't running when you have Alpaca going. With my Canon, if the EOS app is running it takes over all communication to the camera, so Alpaca can't talk to it.
1w
Reply
Billy Bass
Baha Baydar it isn’t running. I only installed it to make sure the camera drivers would be available on the machine. The OS recognizes the camera is connected, but tells me it would be faster to use a USB3 port, which ironically is the only way to connect to that tablet and the camera body.
1w
Reply
Richard Healey

Rising contributor
Billy Bass that's a pretty good clue that you have a problem with the type of USB cable you have in use.
1w
Reply
Billy Bass
Richard Healey except it is the same USB cable I use with the Polaris to the camera without issue every time.
1w
Reply
Richard Healey

Rising contributor
Billy Bass it's possible that your polaris does not know or care about the many, many intricacies of USB cables (in this case almost certainly E marker) - but your OS does. It's cheap and simple to find a USB cable that has an e marker embedded and which is advertised to support an appropriate data transfer rate and USB version to rule that out as the problem.
I regularly plug in the same device to the same laptop or desktop and get the "your device would....." message when I'm using the wrong cable.
1w
Reply


Billy Bass
So you’re suggesting that manufacturers are installing USB3 male connectors on USB2 cables?
1w
Reply
Alexander Murdoch

Top contributor
Billy Bass would your camera happen to be a Z8? there was a funny workaround I had to do to make this camera work with NINA!
1w
Reply
Billy Bass
Alexander Murdoch I have a Z8 and Z9. I’ve not come across any work arounds specific to the Z8 though. Can you share what you’re aware of so I can try to test things?
1w
Reply
Billy Bass
Alexander Murdoch just for the hell of it, I tried with my Z9 body this morning; granted it isn’t really that different from a Z8 but does have its own distinct firmware. I can only attach a single photo at a time, but hopefully this will help clarify what is going on. Also, David Morrison, do you have any idea why the pitch, yaw, and roll values would be changing when tracking was not enabled and a camera was not attached to the Polaris?
May be an image of text
1w
Reply
Billy Bass
Alexander Murdoch here’s what NINA looks like
May be an image of text that says 'Astrenomy 2RC00S Defaul Camera Nikon Name RELEASECANDNDATE RELEASE CANCIDATE Description Driver Dype Temperature.control control Temperature Driver version Sensor name exposure Sensor size Max buning Pael PaelsizeX Mas Max eposure time Max binning Piel size vize ae Settings fecfene'
1w
Reply
Billy Bass
Alexander Murdoch and here is the operating system recognizing the camera, but suggesting the USB-C cable that I am using to connect two devices via USB-C ports is not fast enough:
May be an image of text
1w
Reply
David Morrison
Author

Top contributor
Billy Bass the pitch, yaw, roll changes look like sensor noise to me. I think you can safely ignore it.
1w
Reply
Billy Bass
David Morrison interesting. I would think they might try to store/persist state and use a Boolean to indicate when state has changed (e.g., during tracking and during/after slewing set to true but false otherwise). Now I’m kind of curious to know if the noise is ignorable and if so whether it accumulates to the point that it becomes non-ignorable at some point.
1w
Reply
Real Bread Aotearoa

Rising contributor
Billy Bass Depending on what version of NINA you have installed, will effect the connectivity with the Z8 and Z9. With NINA 3.1 HF2, Z8 will not connect natively and there is no Live View .... but as Alexander Murdoch says, there is a work around, though you still won't have Live View (needed for AF)
However, the latest BETA versions of NINA 3.2 and the Candidate Releases (currently at RC009) will now natively connect Z8 and Z9, plus you also get Live View! This allows you to take advantage of the awesome NINA 'plug in' "Lens AF" ... so you now also get autofocusing for Nikon and pin point stars.
Hope that helps.
Cheers, Mark 😀
1w
Reply


Alexander Murdoch
Top contributor
exciting! can’t wait to give this a crack
2w
Reply
Baha Baydar
I can help with testing. I'm just getting everything set back up on a new laptop.
1w
Reply
Cam Palmer
Thanks to yourself and all the other contributors for your leadership, skills and commitment to continue to develop the Polaris environment. Good on you!
1w
Reply
Steve Everitt
Count me in. I’m in the Canary Islands so get a lot of clear skies.
1w
Reply
Daniel Michaud
More than happy to contribute !
Poor sky here but who knows ..
1w
Reply
Eric Chiu

Top contributor
Going to give it a go 🙂
2w
Reply
David Jensen
Blows my mind that a third party has to provide these features and not the manufacturer....
2w
Reply
Uli Fehr
  · 
What are you talking about?
2w
Reply
Jerry Levin
Following!
1w
Reply
William Siers
Moderator
Group expert in Photography

All-star contributor
Awesome I’m in!
1w
Reply
Shiyang Steven Zhang
When can we expect it???
2w
Reply
Miguelito Duarte
That's amazing. How can we help?
1w
Reply
Pavel Vorobiev
  · 
I am new to Alpaca driver subject. Is it for controlling the BP from NINA?
1w
Reply

---

David Morrison - PODCAST
Top contributor
Thanks for the feedback. I've got a couple of anonymous podcasters to review the Alpaca Benro Polaris V2.0 and describe what's coming up in the new release. They chose what to talk about, and they did a great job. 
I'm figuring out how to fund the remaining effort and push through Alpha and Beta testing. I'll probably set up an obligation-free Kickstarter program again, as Benro isn't sponsoring this. I appreciate any support you can give. 
If you are technical and want to help beta test, please message me directly or on Discord. If you have suggestions for this release, please feel free to share them with me on this forum.


Daniel Michaud
Bravo David , this is impressive & promising . I easily imagine there is significant time & money investment to make this happening , but I'm sure the result will be great , as ABP v1 was. Tell us please how we can contribute , a new kickstarter ? , time to test ... ? I don't have the necessary skills from a development perspective , but I will be available as much as I can .
Shame on Benro , the basis was great , but deciding to not make the product fully functional by internal effort & and relying on others is miserable
Daniel
6d
Reply
Ian Morgan

Rising contributor
Semi technical and very willing, but very time limited at the moment. One day, I hope to be of use to the project , but probably not imminently 🙂
1w
Reply
Eric Chiu

Top contributor
Thanks for the good work 🙂 the hardware have more potential.
1w
Reply
Billy Bass
Closed form just means there is an equation with an exact solution compared to open form which requires defining a threshold at which convergence is declared.
6d
Reply
Richard Healey

Rising contributor
Great work. It will be good to see where this takes us. Onwards.
6d
Reply
William Siers
Moderator
Group expert in Photography

All-star contributor
Thank you for your awesome work!
1w
Reply
Timothy McDaniel
if I’m understanding correctly, the new version connects the BP to a mini-PC via WiFi and the camera connects directly to the mini-PC via usb rather then to the BP unit like in the 1.0 version. Will it be able to run on a laptop/tablet PC or will I need to look at buying an astrophotography mini-pc?
6d
Reply
David Morrison
Author

Top contributor
Timothy McDaniel It should run on a laptop. Tablet is more challenging. Details can be found at https://github.com/.../alpaca.../blob/main/docs/hardware.md
6d
Reply
Timothy McDaniel
David, so v2.0 will allow me to connect the camera to my tablet PC and the BP via wifi? Also, by “tablet” I mean my ASUS Z13 i9 gaming tablet with a 3050ti inside.
5d
Reply
David Morrison
Author

Top contributor
Yes, should be ok, but it’s untested, although you should have plenty of power with an i9. You could test with v1.0 as it’s available now.
5d
Reply

Toby Lo
  · 
thanks for the affort! still have a hope for the polaris, benro totally give up this project, totally disappointed, and never benro anymore


---

David Morrison - KICKSTARTER
Top contributor
Alpaca V2.0 has officially entered Beta testing and launched its Kickstarter campaign! To learn more about what’s been completed, and what’s coming next, check out the Kickstarter page. It covers the progress in detail. Please DM me if you want to get involved.
Your support means a lot and helps keep the project moving forward! Thankyou.

Amr Abdulwahab
I’ve been using Alpaca v1 for a while now, and it has truly transformed the way I control my Benro Polaris in the field. The stability, precision, and the freedom it gives during long astrophotography sessions are just incredible.
I’m heading deep into Egypt’s Western Desert today to continue my shooting project under one of the darkest skies on Earth — and honestly, I can’t wait to try out the new v2 release once it’s available.
It’s inspiring to see how much effort and passion goes into developing this project.
Keep pushing forward — your work really makes a difference for those of us capturing the universe from remote places around the world.
Thank you so much David.
Greetings from Egypt 🇪🇬
3h
Reply

Real Bread Aotearoa
Rising contributor
An awesome project that transforms the Polaris well beyond anything that the manufacturer has managed to deliver. Give it your full support and realise its true potential. Amazing work by David Morrison 😀
7h
Reply
Edited

Andy Washington
Rising contributor
Still PC based (understandably) I assume?
3h
Reply
David Morrison
Author
V2 will still require a separate mini-PC to run the driver. I explored the possibility of updating the Polaris firmware directly, but without Benro’s cooperation (or at least acknowledgement), it is unlikely.
3h
Reply
Kevin Jones
just pledged for the Awesome package! bring it on David!

user avatar
Charles T. Simet
16 minutes ago
You are one of the few exceptions on Kickstarter that I'll gladly back (after being burned a number of times). You deliver on your promises and are the best communicator! Keep up the great work.


@AlvinChristie-o4z  • 1 day ago
It's looking phenomenal David...keep it up!

 • 1 day ago
Nice work!


@The-explorer  • 6 days ago
great work. Thanks, from Egypt


@outsideoursphere  • 11 days ago
this will be awesome, can’t wait to give this new version a crack!!

Reply

0 replies


@madhatterbakery-artisanmad7631  • 13 days ago (edited)
Great Podcast highlighting the amazing developments .... sounds brilliant  😀


Polaris -Camera Controller Global Group
Alexander Murdoch
 ·

Top contributor
 ·
nrsoetoSpdlc0cgff4818i1cl00
h
l778a4l7m892f37822l9
6
07u
1
ia3l2m5
 ·
A world first!! Guiding with the Benro Polaris
This image is 100 x 60 second (that’s right, 60 second!) exposures at 300mm, taken with the Benro Polaris from the Bortle 8 CBD. This will be wicked under some better skies.
Testing & experimenting has been promising, I have guiding sitting around ~2.5RMS - clearly enough to resolve this 300mm lens! Plenty of tips & tricks to come.
I’ll piece together some YouTube videos on the outside our sphere YouTube channel once this driver is available to all - exciting times! Thanks heaps to David and his development of Beta v2.0.0 of the Alpaca Driver - what a feat.
Richard Healey
Awesome news. David Morrison deserves our utmost thanks for the terrific effort he has put into getting the Alpaca driver to the place it is today. And there is more to come, like tracking rates for the sun and moon.
Considering you all dropped over a thousand dollars on the Benro - which never lived up to its promise - I sincerely hope that you have joined the Kickstarter program that is being used to help fund this effort. Not only does this have the potential to truly unlock the Polaris, it is supported within this community and I'm pretty confident the response to any questions will be far more timely than the response from the manufacturer.
And finally, I hope that benro can get behind this effort themselves. They have created a device with great potential - potential that only David and the team have been able to unlock.
2h
Reply
Eric Chiu
Wow. Keen to see how far you can push the exposure time 🙂
Mmm have to find a guide camera.
15h
Reply
Vladimir Vyskocil
Eric Chiu I had great success with 240s, yes 4 min using CCDCiel built in guider ! However I only did some quick tests and it seems there are sometimes small perturbations for such a lot shot, a lot of tests and maybe some adjustments await us.
13h
Reply


Ryan Crandall
This is good news! I was just thinking about getting a separate tracker for deep space because the Benro just can’t do it. Look forward to the YouTube video
13h
Reply
Shiyang Steven Zhang
This is amazing. Do you use a astro modified camera?
10h
Reply
Jerry Levin
How exciting!!!!!!
15h
Reply
Real Bread Aotearoa
Well done Alex in being the first to take the Polaris to another level 😀
15h
Reply
Dan Cool
Amazing!
10h
Reply
Jose Pedrero Barrios
Sticker by Super Smalls

Eric Chiu

Top contributor
Wow 🙂
1d
Reply

Ian Morgan

Rising contributor
Thanks for all the work you are doing on this. I would love to be testing and contributing but life is getting in the way. One day; I’ll really dive in with this.

Ian Morgan

Rising contributor
I backed the latest Kickstarter . Fascinated to see how the app might work out. (Though I guess it may be trickier for Pentax users)

Kevin Groth
As I start budgeting for a guide scope and cam. You're a legend David Morrison !!

Richard Healey

Rising contributor
Really impressive to see how the software can compensate so comprehensively for an out of level mount. Great work.

Eric Chiu

Top contributor
Thanks for all the great work 🙂

Allan Zilkowsky
  · 
Is the a list of equipment and requirements to test this... I would like to give this a go.

David Morrison
Author

All-star contributor
No additional equipment is required for multi-point alignment, although it will likely be most beneficial for those who have already been using V1.0 with Nina and plate-solving. V2.0 is only open for Beta testing presently, ie people who have time to help provide detailed feedback on their tests to help improve the final release. If you can assist with this and are ok with pre-release software, please DM me and I'll let you know how to join up.

Toby Lo
  · 
nice work, btw do i need to do polaris alignment? or any improvement if make it work as eq mode?

David Morrison
Author

All-star contributor
The mention of an equatorial mode at the end of the video has not yet been implemented and is a stretch goal for V2.0. It should be able to work with a plate solve, but I haven't yet prototyped the concept. Its availability will depend on demand and the availability of time.

Shiyang Steven Zhang
That’s incredible!

Dan Cool

Rising contributor
Amazing!

Eric Chiu

Top contributor
Man that performance would be worth setting up a laptop. Pretty close to a full on goo mount 🙂








------------------------------------------------------------------------------
# PANARAMA REQUEST FOR COMMENTS

Polaris -Camera Controller Global Group
David Morrison
 ·
 ·
Isn’t the Polaris already good for panoramas? I’ve had a few requests from Kevin Jones, and others for improved panorama features or a “Pro Pano” mode in Alpaca, but I’m not entirely sure what that would entail. I’d really appreciate hearing from experienced astrophotographers. What works well for you, what doesn’t, and how do you find the current Benro app? What would make a real difference?
I’ve tried creating panoramas in the past but often ran into alignment and exposure issues, especially near the zenith. The new rotator support in Alpaca V2.0 and NINA's preserve alignment option in framing should help create the "perfect rectangular mosaics.” I’m waiting for clear skies to test. 
I'm curious to hear your thoughts — what’s the one panorama feature or improvement (if any) that would make the most significant impact for you?


Koen Pijpers
Hello I mainly shoot wide images:
I would like to plan a panoramic image entirely from home/ make presets (of my focal lengths/ settings, etc). Is there a possibility that the Alpaca driver seen the current lens focal length and select that specific preset ? Have options of setting the starting position (left, right top bottom). Usually a full MW pano you want about 270 horizontal/ 70 Vertical FOV to be sure you can crop. It would be cool if you could see a low detail preview of what it would look like with your current FOV settings. To not mess up the top or sides so you have a full MW pano arch (it happens). I also would love to see a feature where I can plan my Foreground shots (without tracking). So in the field I just press start and enjoy the stars, that’s why I got this device in the first place. I will back on Kickstarter awesome developments and everybody!!

The current Benro app has some nice functionality, I like the overlap percentage, the direct preview of the image in Full JPEG.

Off topic: I would love all this to be put in a new firmware or mobile/tablet app, which would be awesome for travel, which I intend to use this thing for. Currently I didn’t travel with this because I just find the Benro software unreliable and just want a less complex star tracker and no laptop.
6d
Reply


Edited
Kevin Jones
Koen Pijpers exactly what i would have written down! the current Benro Pro Pano for wide field is pretty good but there are bugs in the software such as when you leave Pro Pano and go back in, it doesn't remember the lens size, etc. also, the start and end process of setting up the pano can be 'forgetful'. there should be a 'clear' option too to reset the pano start and end positions. i have backed this project understanding it's for deep space targets as i will use this in the future but the wide field and pano options are of high importance if they can be implemented in a better, bug free way.
5d
Reply


Koen Pijpers
The device has so much potential 🙂
4d
Reply




Eric Chiu
Keen to follow this one.
I think it may be when both star and landscape are involved.
6d
Reply


John Harrison
Here's the thing, am shooting panos manual so unless I change cameras I haven't got that functionality
4d
Reply


Billy Bass
Aside from maintaining state like others have mentioned, there are a few issues that I think would be game changers for making panoramas much better with the Polaris:
1. Rotate the camera to maintain the same horizon for each panel;
2. Allow users to control the sequence with which the panels are captured; and
3. Control of tracking for the panels.

The first is especially important when stacking or using longer exposures with a larger field of view. If taking 4x60” subs for a pano with >= 6 panels the horizon will be rotated at least 7.5 degrees between the first and last panel. This results in insufficient coverage of the sky in some panels and a pain to deal with in processing. If instead, the camera is returned back to the starting position on the RA axis there will be a stair step pattern along the horizon across panels, but better coverage of the sky and a much easier time stitching the panorama together in post and aligning with foreground shots.

The second issue is also somewhat related, though not exactly. Currently the Polaris uses a zig zag pattern of movement with multirow panoramas. This can be a pain to deal with compared to shooting each row with the same motion (i.e., left to right or right to left). There could also be use cases to shoot across the rows of the panorama before shifting the azimuth, but that also isn’t supported.

Lastly, it would be outstanding to be able to turn tracking off to take long exposure foreground shots followed by turning tracking on to take the shots of the sky in a single sequence; this is especially important since the Polaris and mobile application seem to be unable to maintain state long enough to make it easily feasible to do this consistently manually.
2h
Reply



Uli Fehr
  · 
Setting a referece point in the upper left corner, pan/tilt to see it in the down right corner to determine the FOV and use this for setting the panels
6d
Reply


















------------------------------------------------------------------------------
# Panorama Posts
BN Astro Branko NađoetsrdoSnp

Funchal, Portugal
 ·
TRACKED PANORAMA 
The Path of Light
✨️🇵🇹✨
FB: www.facebook.com/bnastrohrvatska/
I️G: www.instagram.com/bnastro000/
A panorama of the Milky Way in the darkest sky my eyes have ever seen.
I chose the São Lourenço peninsula in the east of Madeira back in Zagreb, having studied every step using Google Streetview. Since it is the easternmost point of the island, it is far from the light pollution of the largest city of Funchal and the airport named after Cristiano Ronaldo. 
So straight ahead there is the pure darkness, all the way to the coast of Africa.
🇵🇹👽🇵🇹
We first did a day hike around the peninsula, so I could find the best position for the night panorama, and then two days later I went solo with almost 30 kg of equipment on my back and spent the night, as I said, under the darkest sky ever.
Of course, a selfie had to fall under that sky cap, and here I am in the foreground; that other light in the distance comes from the lighthouse - Faro.
The daily panorama from almost the same position can be found in the COMMENTS.
📷📷📷
GEAR: Nikon d7200 astromod, Sigma Art 14 mm, SilenceCorner's Atoll ring, Benro Polaris tracker, EcoFlow River2Max, LowePro 450BP trekker
EXIF:
- sky - 8 panels x 5 photos x 1 min, f2.8, ISO 800
- foreground - 8 panels x 3 photos x 1 min, f4.0, ISO 1250 (+10 sec selfie)— at Madeira Island.


Stephen Dyer

 ·
This panorama is made up of 24 images, tracked at 30 seconds each, f/1.6, using a Canon R6 Mk II with a Sigma 28mm f/1.4 Art lens. I used the Benro Polaris and captured three full sets of images. In each set, about four of the frames showed elongated stars—two in the lower left and two in the lower right.
I’m disappointed, as I only recently received this Polaris as a replacement, which took nearly 10 months to arrive. The new unit does function, and I thought it was working perfectly. Has anyone experienced something similar or know why about 4 out of 24 images might not track correctly? I have a 3-second interval set between exposures to allow the tracking to settle. My suspicion is there may be some resistance in the gears, which might improve with use.
Any advice would be greatly appreciated.



Hiking Tig r
odeStorsnp
Astro Panoramas: shouldn’t the Polaris be leveling itself after every shot? By time mine finished 18 shots , the can was in a totally heavily tilted
Facebook
Kristjan Kõluvere

Rising contributor
No, its not leveling itself. If it would leveling after every shot you cant stack images toghter later or cant get correct overlay for panoramas. Its heavily tilted and normal because rotation of Earth. ☺️
17w
Reply
Hiking Tig r
Author
Kristjan Kõluvere thank you kindly for the explanation
17w
Reply


BN Astro Branko Nađ

 ·
TRACKED PANORAMA 
Ice Rainbow
✨☃️✨️
FB: 
Hrvatska pod zvijezdama / Croatia under the Stars
IG: www.instagram.com/bnastro000/
After weeks of baking at +30, it's nice to remember mid-February and the beautiful -7 ❄️😊
And Plitvice Lakes National Park where this late Winter panorama of the Milky Way was captured.
I was reminded of this photo the other day by the 
World Meteorological Organization when they published the best 75 photos shortlisted for their new 2026 calendar.
Among them are 3 of mine, including this panorama from Plitvice Lakes in which the so-called Zodiacal light is visible (the white band in which the sparkling Jupiter is located).
The photo is dominated by the constellation Orion the Hunter, the ruler of the Winter sky.
❄️🎯❄️
I took the photo with two cameras at the same time, because it was frikking cold ☃️, but also to get to a few more nighttime Plitvice locations.
I noticed the thin veil of clouds when I got home that made the stars appear haloed, but somehow I like that in this setting.
GEAR: Nikon Z6II, Nikon Z8 astromod, Sigma Art 20mm, Sigma Art 40mm, SilenceCorner's Atoll rings, Benro Polaris tracker, EcoFlow River2Max, LowePro 450BP backpack
- Focus on Stars mask: https://focusonstars.com/ref/bnastro/
EXIF:
- sky (Z8, 20mm) - 8 panels x 5 photos x 60 sec, ISO 640, f2.8
- foreground (Z6 II, 40mm) - 15 panels x 3 photos x 30 sec, IS0 1600, f4.0


TRACKED PANORAMA 
Lyrids above Croatia 
✨️☄️✨️
️FB: www.facebook.com/bnastrohrvatska/
IG: www.instagram.com/bnastro000/
WEB: www.bnastro.com
The April meteor shower, known as the Lyrids (because their source/radiant is from the constellation Lyra near the star Vega) recorded in Lonjsko Polje Nature Park.
📷👽📷
The bird observatory, built on the model of the former čardaks of Vojna krajina, is one of the most famous locations in Lonjsko Polje. Meteors appear in April when the Earth passes through the dust trails left by Comet Thatcher.
☄️☄️☄️
The first records of the Lyrids are about 2700 years old.
An orchestra of frogs and birds followed me all night in Lonjsko Polje (video in COMMENTS), and I decided to hunt for the Lyrids above two lookouts, with two cameras.
✨️👽✨
The constellations in photo no. 5 were drawn by my wonderful friend Tjaša Mađarević / Poster Studio Vukovar, the author of the illustrations in my book "Croatia under the Stars".
https://www.nakladaslap.com/.../a9956aa49c7f5480db8092db2...
GEAR: Nikon Z8 astromod, Sigma Art 20mm, SilenceCorner's Atoll D+ ring, Benro Polaris tracker, Astronomik L2 clip-in filter, EcoFlow River2Max, LowePro 450P trekker
EXIF:
- sky - 10 panels x 5 photos x 60 sec, f2.8, ISO 640 (plus meteors from a 3-hour timelapse)
- foreground - 10 panels x 3 photos x 30 sec, f4.0, ISO 1250— at Lonjsko Polje Nature Par


Dan Wade
nptdSsrooe9428
·
5 frame panorama.
14mm f2.
60 seconds, iso 400 for sky tracked.
60 seconds, iso 4000 for foreground untracked.


John Mitchell

 ·
Milky way panorama over St James Anglican church, Pomeroy NSW
EXIF: Foreground Canon R5, Sigma Art f1.4 DG lens, single frame taken in the late afternoon, f5.6, ISO 50, 1/2 second
Sky panorama, Benro Polaris (astro panorama, portrait mode) 3 rows by 8 frames (24 frames) f1.8, 60 seconds, f1.8. Canon RP h-alpha modified
ICE stitched.
PS polished


Michal Prodělal
rpoStdnesoh4

 ·
Tracked panorama of the zodiacal light over the Podyjí National Park and the Thayatal National Park.
Photographed on the road above the Šobeská vineyard.
You can see the arc of the Milky Way beautifully above the zodiacal light. Below in the light you can see the planet Venus. In front of the peak of the aurora is the Pleiades star cluster and almost at the top is the planet Jupiter. The light trace of red on the right above the Pleiades is the California Nebula. On the left you can see the constellation Orion and on the right between the aurora and the Milky Way is the M31 galaxy.
This photo will stay in my memory for a long time. I always say that night photography requires a lot of courage and a bit of forethought. And when I took this photo after a long time, I was afraid not because there was any wildlife nearby, or strange sounds, it is normal to hear herons, owls, rodents and wild boars and barking deer, but that night the park was completely quiet, only here and there a fan and the thermal camera did not see any wildlife in the area. Simply complete silence even on the way to the car about 2 kilometers away across the Dyje valley, nothing, no eyes shining in the light of the flashlight, just silence...
I was happy to be sitting in the car. But even now, when I think about it, I get chills down my spine.
Technical part
stars 3x5 photos 30s f2 iso 800 R6+sigma 28mm art on Benro Polaris mount
thinned 1x6 photos 30s f2.8 iso 3200
processed with lightroom, I.C.E. Photoshop + Affinity
28.2.25


Simon Torr

 ·
I’ve seen a number on pro panorama images posted where the exposure is, say 120 s. Most cameras are limited to 30s or maybe 1m.
How do you achieve much longer exposure in pro panorama.
Thanks

Dan Cool

Rising contributor
And if you want to reduce noise and eliminate airplane and satellite trails, you could take multiple 30-second exposures and then stack them. Therefore, a 120-second exposure would be four 30-second exposures.
25w
Reply
Simon Torr
Author
Thanks all - sorted
With the R8 I set to manual and the adjusted the slider to bulb and another timer came up.
Oooh I’m looking forward to playing with that now 😄😄
25w
Reply
Henrik Poulsen
canon 7D and 1100D max 30 sec. Bulb mode starts but says camera busy. Strange, because they can be controlled fine by other apps. Benro programming prob could be improved. Also the camera busy error appears in other modes
25w
Reply
Christine Lai
Some of the newer Nikon mirrorless bodies allow longer shutter speeds but you need to manually turn on the setting.
25w
Reply
William Siers
Moderator
Group expert in Photography

All-star contributor
Happy you sorted it out! But just in case others read this, some camera i.e. Sony require you to be in Mechanical Shutter not electronic shutter, unless it has Global Sensor.
25w
Reply
David Jensen

Top contributor
set your camera to bulb mode then that allows you to set a longer exposure in the benro app
25w
Reply
Andy Washington

Rising contributor
My Nikon can go to 900 seconds without using bulb.
25w
Reply
Mike White
Bulb exposure mode with the required time set in the app.


John Mitchell
Sodpetnsorlg34h4l2

 ·
John Mitchell
Sodpetnsorlg34h4l2
 
 ·
Milky Way rising & the moon setting over Angle Crossing, southern ACT.
It was a trip to practice the astro panorama function of the Benro Polaris tracking device and using a 16mm lens. Although I have better lenses for these shoots, I decided to use the Canon RF 16mm  f2.8 which is basically a cheap wide angle lens, the Sigma 20mm f1.4 or the Tamron 15-30mm f2.8 would have done a better job with the stars.
EXIF: 20 sky  frames, Canon RP h-alpha modified, f2.8, 90 secs, ISO 640.
8 foreground frames Canon R5, Sigma Art 20mm f1.4 1/100 the sec, f5.6, ISO 100
Benro Polaris tracked, astro panorama function.
With Richard Tsen


Luminita Lenuta is in Williamsdale, NSW.
Benro Polaris tracker, panorama 2 lines 14 frames at -6 degrees
Canon R8 Sigma 20mm
f 2 tv 61s iso 640 
24th June 2025
PTGui


TRACKED/STACK/BLEND/PANORAMA
Formentor Lighthouse - Mallorca - Spain
STORY:
Formentor Lighthouse is a classic, but it’s still one of my favorite spots to watch and photograph the Milky Way in Mallorca.
Not every night is the same. This one was special — not just because of the clear sky and the perfect alignment over the lighthouse, but also because of the airglow that painted the horizon. This natural phenomenon, caused by chemical reactions in the atmosphere, adds an extra touch of magic to the scene and gives the sky a unique depth that only appears under very specific conditions.
GEAR:
Panasonic S5 Astro
Panasonic 24mm f1.8
Sigma 16-28mm f2.8
Benro Polaris
Sunwayfoto T3240CK
Vanguard Alta Sky62
Exif:
Foreground:
16mm f2.8 20” ISO6400
Panorama: 10 frames
Sky:
24mm f1.8 ISO1000 40”
Panorama: 1 row 9 columns
Panels: 9 panels, 5 frames for panel
SOCIAL:
https://youtube.com/davidmaimo
https://www.facebook.com/davidmaimo.net
https://www.instagram.com/davidmaimo/
https://www.davidmaimo.net

John Mitchell
tSesnodrpo
u
u0im4
J
741
,
2
h
e
7l2u4h626
 
0u0c
5
iu9
2
81f1f
1
 
0
n
l95
2
g6im
 ·
I'd like to know how Polaris users setup the device for Milky way panorama's?
I'm an experienced astro photographer & I've used tracking devices for this type of photography & also deep space with a telescope etc.
The manual method with a tilt & panorama head is to start on the LH side, shoot the height & adjust the level manually every 2-3 sections so they'll stitch properly. Pan to the Rh side & then start again on the 2nd row to the right & repeat for the horizon view. With the Polaris, levelling manually isn't required. With the Polaris, there's 2 schools of thought here in Australia, one being as described above or setting up for the LH side from the top or peak of the MW & running the sequence. Repeat the setup but for the RH side after the LH side is completed.
We tend to use different FL lenses here also but obviously the 14-20mm f1.4 are going to give you the best results, depending on the quality of the lens. 
Using 40mm f1.4 such as the Sigma art f1.4 is also popular here but it takes too long.
Also what overlap do users use?
I tend to opt for 35-50% myself.
I'm in a camera club & there's currently 7 out of the 20 members who do astro photography who use the Benro Polaris device, each person with different levels of experience. I put myself in the experienced, not expert section.
There's other members who use other tracking devices in the group as well.
Thanks in advance.

Facebook
Boyce Fitzgerald
I usually use it with a lens 16-35. Generally, I calibrate it in Astro mode using one-star alignment. Then I shoot left to right in the northern hemisphere (I am no experienced enough to know if this matters - core is to the right) with the camera in portrait orientation set to 60 seconds per exposure with 50% overlap. A few times, I didn’t even use Astro mode. I just used panorama mode and did, for example, 20mm lens with 15 second shutter speed at ISO 3200. When I stitch these, they look great. You have so many pixels that on such a huge panorama! The ones with longer exposure may have more data, color, etc. but I don’t know if it is worth all the effort. I have done these 60 seconds tracking panos the most but may not. I consider my self somewhat of a beginner - but one with good results due to trial and error.
Don’t know if this is helpful to more experienced people like yourself.
29w
Reply
Boyce Fitzgerald
This is tracked for 60 seconds with a 35 mm lens. Lights ruined the ends so I cropped them out.


Gergő Tóth
tSesnodrpo
u
u0im4

Isabis Canyon
TRACKED/PANO/BLEND
This was the last big panorama I captured during our two-week astro trip in Namibia. I aimed to photograph the four largest galaxies visible in our sky—something only possible just before dawn.
On the left are the Large and Small Magellanic Clouds, on the right is Andromeda, and in the center, the Milky Way—all part of our galactic neighborhood, the Local Group.
To the right of the canyon is a seasonal waterfall, already dry since the rainy season. A strong green airglow was also visible to the north, appearing on the right side of the Milky Way arch.
I woke at 3:30 AM and headed to the canyon in complete darkness. Luckily, two astro friends joined me, and with our 4x4, we didn’t have to walk all the way from our accommodation.
I had to work quickly to finish the image before dawn. The sky had already begun to brighten during my final few frames, but I managed to complete the panorama without needing those exposures.
The dark skies at Isabis Farm are truly exceptional—I'd love to return to this unique place someday.
EXIF:
Sony A7IIIa + Sony A7RIII
Sony 35mm f/1.4 GM
Benro Polaris
Sky: f/1.4, 30s, ISO 1600 (24 panels x 2 rows) + H-alpha: f/1.4, 60s, ISO 3200 (21 panels x 2 rows)
Foreground: f/1.4, 30s, ISO 1600 (17 panel focus-stacked panorama)
Location: Isabis 4x4 trail
Date: 2025.05.31.

Gergő Tóth
nertpsodSo0
5

 ·
Oasis
TRACKED/PANO/BLEND
This is my first-ever double Milky Way arch panorama, showcasing the "Summer" Milky Way on the left and the "Winter" Milky Way on the right side of the image. March is a special time of year in the northern hemisphere: the Winter Milky Way sets in the evening, and just before dawn, the Summer Milky Way rises—allowing us to capture both parts of our Galaxy in a single night.
We arrived at this remote location near the Algeria–Morocco border just before sunset, giving me time to scout the surroundings and plan the shot. I captured the Winter Milky Way arch between 9–10 PM, then got a few hours of sleep in my tent. At 2 AM, my alarm woke me so I could capture the foreground in the same tripod position, followed by the Summer Milky Way arch between 3–4 AM.
It was an exhausting night of photography, but one I’ll never forget. Seeing and capturing both sides of our Galaxy in the middle of nowhere was an unforgettable experience. Post-processing this image took even more effort, but I’m thrilled to have it as part of my collection.
EXIF:
Sony A7IIIa
Sony 35mm f/1.4 GM
Benro Polaris
Sky: f/1.4, 30s, ISO 1600 (23 panels x 2 rows) + H-alpha: f/1.4, 60s, ISO 3200 (21 panels x 2 rows)
Foreground: f/1.4, 60s, ISO 800 (19 panel panorama)
Location: Morocco
Date: 2025.03.30-31.

Sylvain Dherbecourt
nertpsodSo0
5
 

 ·
Panorama of milkyway with Polaris to capture reflections on a lake in Auvergne, France.
📷 Canon EOS R astro modified with sigma 35mm f/1.4
Panorama of 28 photos, 10" f/2 2000 iso each, stacking of 7 photos, 30" each for milkyway core and Rho Ophiuchi


John Mitchell
pednosStro

 ·My first panorama with the Benro Polaris
Milky way rising over the Bombo Headland Geological Site.
With a big East coast low pushing the seas towards the coast, even at low tide, the waves were breaking over these rocks, composite.
The foreground was takes in the blue hour, Canon R5Mkii, Tamrom 35-150mm Vc Di OSD @35mm, ½ sec. f16, ISO 1600
Sky, Canon RP h-alpha modified, Sigma 40mm f/1.4 DG HSM Art Lens, f2, 1 min, ISO 1600 mounted on the Benro Polaris tracking device in astro panorama mode. 3 rows X 8 columns x 2 frames, total 48 frames


TRACKED/STACK/BLEND/PANORAMA 
Cap Salines, Mallorca 
STORY:
First photo with the new astro-modified camera, and I couldn’t be happier with the result.
Under a dark and clear sky, the winter Milky Way unfolds in all its splendor. This panorama showcases some of the season’s most iconic nebulae, such as the Orion and Rosette Nebulae, along with star clusters and distant galaxies.
GEAR:
Panasonic s5II
Panasonic s5 Astromodified
Panasonic 24mm f1.8
Sigma 16-28mm f2.8
Benro Polaris
Sunwayfoto T3240CK
EXIF:
Foreground:
16mm f2.8 15” ISO6400
Panorama: 9 frames
Sky:
 24mm f1.2 ISO3200 30"
Panorama: 3 rows, 9 columns
Panels: 27 panels, 4 frames for panel


Dan Zafra Photography
 
 ·
Tracked panorama taken in New Zealand with the BP! 🚀
EXIF:
Sky – Sony A7III Astromodified by @Spencerscamera + Sony 20 mm f/1.8 + Benro Polaris Star-tracker – Panorama of 3X7 tracked vertical images at 90 sec. f/2.2, ISO 1250
Foreground – Sony A1 + Sony 14 mm f/1.8 – Panorama of 7 vertical images at 90 sec. f/2.8, ISO 6400



BN Astro Branko Nađ
ertSspondou3

TRACKED PANORAMA
Medieval universe
☄️✨️☄️
️FB: www.facebook.com/bnastrohrvatska
IG: www.instagram.com/bnastro000/
WEB: www.bnastro.com
We are still in Milengrad, the fortress that I presented in the last post.
This panorama was taken last Winter.
✨️✨️✨️
"The old town of Milengrad, most likely built in the 13th century, on the edge of the mountain spur of Ivanščica, not far from Grtovec in Croatian Zagorje, is another one of the medieval towers that few people know about.
I'll admit, I had no idea either until a friend told me about those ruins that look like they were from Lord of the Rings. This was therefore one of my first astrophoto sessions, when I was just beginning to discover the beauty of the night sky. 
I visited Milengrad five years later, and this photo is in front of you.
As many as 117 photos and the same number of recorded minutes combined into one panorama.
It's even more incredible that I didn't see my neighbor's house in Zagreb when I was driving here because of the fog. Thick fog all the way, until I got to the top of the hill and the heavens literally opened up. The fog stayed down, it even dimmed the light coming from the towns and villages of Zagorje region, so that night I witnessed almost the brightest stars ever."
🌌🌌🌌
The DESCRIPTION of this photo is taken from my newly published book "Croatia under the stars", which you can read more about HERE
www.nakladaslap.com
📷📷📷
GEAR:
- Nikon d7200 astromod, Sigma Art 14mm, SilenceCorner's  Atoll Ring, Benro Polaris tracker, EcoFlow River2Max, LowePro BP 450 trekker
EXIF:
- sky - 2 rows x 9 panels x 5 photos x 60 sec, ISO 800, f2.5
- foreground - 1 row x 9 panels x 3 photo x 60 sec, ISO 1250, f4.0

Mohamed Rageeb

5
9l4
 ·
This image is a composite panorama of Coorongooba Campground, located along the Capertee River in Wollemi National Park, about 200 km northwest of Sydney. The campground is in a picturesque valley, surrounded by rugged escarpments, sandstone cliffs, and lush bushland. Wollemi National Park and the valley where Coorongooba Campground is situated are part of the Greater Blue Mountains World Heritage Area. This designation helps protect its unique biodiversity and geological features. The valley containing Coorongooba Campground is part of the larger Capertee Valley, which is often noted as the second-widest canyon in the world, following the Grand Canyon in the United States.
The foreground panorama consists of thirty-three images, and the southern tail of the Milky Way is a panorama of twenty-eight images, each stack of four.
The equipment used for capturing this image includes the OM1 + 12-40 Pro II and the Benro Polaris for panorama and Milky Way tracking.


Bob Masters
Snroodspte2

 ·
A new endeavor to keep the aggravation level high and the mind active.  I rode the mountain bike up to Marlette Lake on two different nights in July.  The first night I captured a panorama of the Milky Way.  It is a combination of 20 different images with a 50% overlap captured using a canon 35 mm prime lens on a Benro Polaris Astro tracking portable mount.  The images  were combined in PTGUI to create the panorama.  A week later I  captured the foreground landscape with the same lens overlapping a series of 16 images using a fixed tripod. Those images were also combined in PTGUI.  The final step was to take the two panoramas and merge them in Adobe Photoshop Creative Cloud.  The final image is actually 36 inches wide by 19 inches high at 300 dots per inch resolution.  This image has been downsized to about one percent of that initial image size in order to post on the web.


Gergő Tóth
Snroodspte2

 ·
Sunflower Milk
TRACKED/PANO/BLEND
After my first 135mm panorama, I wanted to go out again and create another Milky Way mosaic, this time with H-alpha exposures. It's much more time-consuming than typical astro-landscape photos, so I didn't focus much on the location. I hope to find a spot worthy of such detailed Milky Way mosaics one day.
EXIF:
Sony A7IIIa + Samyang 135mm f/1.8 + Sony 35mm f/1.4 GM
Sky (135mm): f/1.8, 60s, ISO 640 (9 panels x 4 rows) + H-alpha: f/1.8, 60s, ISO 2500 (8 panels x 4 rows)
Foreground (35mm): f/1.4, ISO 640, 60s (3 panels x 1 row)
Location: Hortobágy, Hungary
Date: 2024-07-06
Tracker: Benro Polaris


David Maimó Lázaro
ndoptrsoeSg

TRACKED/BLEND/PANORAMA
Formentor lighthouse, Mallorca
STORY
One of the most spectacular lighthouses we have on the island. Located 188 meters above sea level, on the cape of Formentor, with its renowned winding road that leads us to it.
EXIF
Olympus OMD EM1II Astro + Mzuiko 17mm f1.2 + Mzuiko 7-14mm f2.8
Benro Polaris
Foreground - 14 x 20” ISO 6400 7mm  f2.8
Sky - 26 x80” ISO 800 17mm f1.2
SOCIAL


BN Astro Branko Nađ
derntspoSogt7m

 ·
TRACKED PANORAMA/STACKED/BLENDED 
The path of light
✨️✨️ ✨    ️ ️
FB: www.facebook.com/bnastrohrvatska/
I️G: www.instagram.com/bnastro000/
I'm ending the miniseries of photos from Madeira with the best astrophoto I've ever managed to take, under the darkest sky my eyes have ever seen. 
I chose the Sao Lourenco peninsula in the east of Madeira while l was still in Zagreb, studying every step using Google Streetview. Since it is the easternmost point of the island, it is far from the lightpollution of the largest city of Funchal and the airport named after Cristiano Ronaldo, and straight ahead there is just pitchplack darkness, all the way to the coast of Africa.
🇵🇹👽🇵🇹
First we did a daytime hike around the peninsula, when I found the best position for the night panorama, and then I went solo two days later with 30 kg of equipment on my back and spent the night, as I said, under the darkest sky ever. Of course, the selfie had to be made under that heavenly cap, and here I am in the foreground; another light in the distance comes from a lighthouse.
See the planning with the Photopills application and the daily panorama from almost the same position in the COMMENTS section.
📷📷📷
EQUIPMENT: Nikon d7200 astromod, Sigma Art 14 mm, SilenceCorner's Atoll ring, Benro Polaris tracker, EcoFlow River2Max, LowePro 450BP trekker
EXIF: 
- sky - 8 panels x 5 photos x 1 min, f2.8, ISO 800 
- foreground - 8 panels x 3 photos x 1 min, f4.0, ISO 1250— in Madeira.


Keith Mahoney
ptordseonSl
t
 ·
Category - Blended Tracked Panorama
Story -
My thought process for the Superman Barn, was to light it from inside with such intensity, that the light beams would radiate out through the gaps in the paneling.
unfortunately, the 3 lights which I had set at 100%, were no match for the sheer size of the old American style Gambrel roof barn.
The barn, erected on a 1200-hectare property just outside Breeza N.S.W., was used in the filming of the 2006 'Superman Returns' and has slowly deteriorated ever since, adding to its unique charm.
The top image includes both the large and small Magellanic clouds, the bottom image is a crop to highlight the barn.
Sony A73 Ha modified with a Sony 24mm f1.4 lens.
Benro Polaris Star Tracker.
14 x 60 sec tracked images for the Sky.
7 x 60 sec untracked images for the foreground.
A bit of an effort to capture and process, but worth the time spent doing both.

Jason Perry
TRACKED/STACKED/PANORAMA/BLEND
SOCIALS: Facebook: https://www.facebook.com/pdogphotography/
Instagram: https://www.instagram.com/jsn_pdog/
Website: https://www.pdogastrophotography.com
STORY: Standing on one side of the iconic Lake Tyrrell platform just after midnight in August. The Milky Way core had flipped and started its descent toward the horizon. This was the moment I planned for. I was lucky enough to have the Aurora Australis make a tiny appearance on one side of the Milky Way and the light pollution from the salt mine on lake Tyrrell lit the other side.
This year I finally dove into tracked panoramas and this shot shows everything clicking into place. Seven panels across with each panel tracked for four 60 second exposures to pull maximum detail from the core, Magellanic Clouds, and the subtle aurora dancing that night. The last bit of water on the dried lakebed created perfect reflections of the platform and sky.
The foreground is 120 second exposures at f/3.5 to hold sharpness across the scene while the tracker handled the sky. I also shot shorter stacked exposures specifically for the water reflections. Then I used a little trick where I mirrored the tracked sky and blended it subtly into the existing water reflection to bring out more detail in that reflection.
All exposures stacked in Starry Landscape Stacker then stitched in PTGui. No moon that night. Just darkness and stars.
What made this special is I shot this same composition from both sides of the platform. The plan is to eventually blend this view with the summer arch from the opposite perspective. Two sides of the same story.
EXIF DATA: Stack/Blend. Taken with the Nikon D850 (astro modified) and SIgma 20mm f/2.4 Art lens. Benro Polaris tracker. Sky: 8 panels, 4 tracked frames each (32 frames total) at 60 seconds, f/1.8, ISO 1250. Foreground: 8 panels, single frame each at 60 seconds, f/1.8, ISO 1250. Water reflections: shorter stacked exposures (4 stacked at each panel: 10 seconds at f/1.8, ISO 5000, 20mm) with mirrored sky blended in for details. Stacked in Starry Landscape Stacker. Stitched in PTGui. Edited in Photoshop

Stephen Dyer
Panorama taken with the Benro Polaris at a local salt lake, which has quickly become one of my favourite locations for Milky Way photography. Captured on a Canon R6 Mark II (astro-modified) with the Samyang 14mm f/2.8, the stars are untracked. This was originally intended as my foreground set, but the sky turned out more interesting—even with the star trails—and even revealed a faint aurora.
The panorama consists of 10 frames, each exposed for 61 seconds at f/2.8, ISO 6400.

JM NatureScapes is at Little Sable Point Light.

Pentwater, MI, United States
 ·
1st tracked pano with the  benro polaris! @benrousa 
Whipsy clouds made this annoying all night, but thankfully, most of the clouds broke apart over the lake!
High thin clouds create a glowing effect on bright stars like a fog or diffuse filter
I'm super excited to be taking this amazing piece of gear everywhere this year!
Exif
Sky: Tracked 3 rows. 3 x 9
120sec, F2, iso 800. Sigma 28mm.
Froground
2 rows, 2 x 9
30sec , F2, iso 3200



Skies & Scopes - Learn Astrophotography
Sperrgebiet, Namibia by Vikas Chander Astrophotography 😮
Camera = Nikon D850
Lens = Zeiss Milvus 21mm f/2.8
Tracker = Benro Polaris
Sky Exposure = 240secs, F4, iso 800, stack of 8
Ground Exposure = 480secs, F4, iso 800, focus stacked, light painted
Software = Photoshop

Geoff Sharpe
TRACKED PANORAMA
SOCIAL
Instagram     astro.geoff     Facebook     Geoff Sharpe
STORY
On a road trip to Victoria, I caught up with Richard Tatti for a shoot at Mitre Rock which is west of Natimuk. Mitre Rock is close to Mt Arapiles and both are popular rock climbing destinations.  Mitre Rock is quite high which makes it a good subject for this time of year because the core of the Galaxy is well above the horizon just after sunset. We set up a foreground composition of a dead tree and followed this with a series of tracked images to show galaxy. I stitched the images in PTGui and blended the sky in Photoshop.
EXIF
Foreground
Sony a74 astro modified with a Sony 14mm f/1.8 GM lens at f/2.8 for 6 seconds at 3200 ISO. Three images stitched in PTGui.
Sky
Sony a74 astro modified with a Sony 14mm f/1.8 GM lens at f/1.8 for 62 seconds at 800 ISO. Five images stitched in PTGui.  Tracked on my Benro Polaris.— with Richard Tatti at Mitre Rock.


Uroš Fink
✨Field of gold🌻
CATEGORY: 
Tracked / stacked / blended
GEAR: 
Nikon Z6a
Sigma 20 1.4 Dg Dn + Megadap tze21
Benro Polaris
EXIF:
Sky: 10frames stacked  ( iso800, f2.0, 60s ) + 1frame with Lee soft 4 ( iso1600, f2.0, 30s )
Foreground: iso800, f16, 40-60s, focus stacked x3
SOCIAL: 
Website: www.urosfink.com
Prints: https://uros-fink.pixels.com/
IG: https://www.instagram.com/urosfink/
STORY:
After a couple of years, my wish came true. To photograph the Milky Way over a field of sunflowers. 
In July, before work, I went to a nearby field of sunflowers, which were in full bloom. Of course, as usual, I visited the location during the day and made a plan for this short but wonderful evening. 
Above the field of sunflowers is the galaxy we live in, the Milky Way in all its beauty.


Geoff Sharpe
Lake Tyrrell, VIC
 ·
PANORAMA TRACKED BLEND
SOCIAL
Instagram   astro.geoff    Facebook    Geoff Sharpe
STORY
In October, 2023, I did a long road trip to the Outback of New South Wales and Victoria with John Rutter, Dan Zafra and Ascen Aynat.  We shot at Lake Tyrrell (the Pink Salt Lake), in Victoria for two nights and had perfect conditions with clear skies and no wind.
I found a remote location that had a stream that drained into the lake and shot a panorama of 5 frames for the foreground. Not long after, I set up my Benro Polaris and shot 5 tracked images of the Milky Way Galaxy.
I stitched the foreground and the tracked sky images in PTGui and blended the images in Photoshop. I also used StarXTerminator to reduce the number of stars in the night sky and NoiseXTerminator to reduce the image noise.
EXIF
Sky
Sony a74 astro modified with a Sony 20mm f/1.8 GM lens at f/2.0 for 60 seconds at 2000 ISO.
Foreground
Sony a74 astro modified with a Sony 18-105 G Lens at f/5.0 for 1/15 second at 500 ISO.— at Lake Tyrrell.


David Boixo Photography
STACKED/TRACKED/BLENDED
Meteo Radar. La Panadella - Barcelona (Spain)
Landscape: 10 shots with Sony A7III + Sigma 65mm DG DN at f4 ISO3200 and 30s stacked with PS
Sky: 100 shots with Sony A7III + Sigma 65mm DG DN at f4 ISO1600 and 30s tracked with Benro Polaris and stacked with Sequator
Filtered and Blended with PS
SOCIAL
https://www.instagram.com/davidboixo
https://www.youtube.com/@DavidBoixoPhotography

Julio Saura
Winter Milky Way in Huéscar, Granada, Spain.
Category: Tracked / blended
Foreground: Sony A7IV, 20mm, f2, ISO 800, 30 sec.
Sky: Sony A7III Astromodified, 20mm, f1.8, ISO 1600, 60 sec. tracked with Benro Polaris.— en Embalse De San Clemente.
Lightroom and Photoshop
Social: Instagram: @juliosgfotografia



------------------------------------------------------------------------------
# Panorama for Lunar Eclipse

Billy Bass:
Hi David,

I very much appreciate the frank response and offer to share perspective.  For the pano, I basically need to make sure that for each shot of the moon I include comparable shots for the other panels so I can blend them in with the sky panels prior to stitching the panorama together.  When I did this last year with a 20mm lens, it basically meant having about 4-5 panels (the Milky Way center wasn’t visible) and I used the nodal ninja for everything.  This time I think it would be in my best interest to be able to take tracked shots of the sky to minimize noise and to hopefully ensure they align with the foreground panels as much as possible.  I have a cold shoe mount GPS device (which definitely does not work as advertised to add the GPS data to the EXIF, but would at least provide a consistent measure throughout the night), but am thinking there should be a way to set up the panorama like a large mosaic in NINA.  The catch is that all the foreground row panels would need to be captured without tracking enabled, and the sky row(s) would need to have the same level horizon line and azimuths as the foreground panels to make the stitching less error prone.  Throughout the night I would need to take photos of the moon with a smaller aperture and between covering the adjacent panels; these would be exposed exclusively for the moon so all the background would effectively be clipped to 0 or very small values.  During totality, I would need to enable tracking so I can expose a bit longer and may need to capture two rows of sky, depending on the focal length used.  Thankfully, lunar eclipses are significantly slower events than TSE which makes things a bit easier in that respect (along with the fact that totality would only be captured in the most westward facing panels).  Not sure if that helps explain things at all, but definitely willing to share any additional info I can.  Also, I’m not sure if you have any plans for the 2027 total solar eclipse, but I am already planning to head to Australia for it; there’s a national park in the northwest of Australia that I found and have since forgotten that seemed to have some really cool/interesting foreground that I thought would make for a good photo, but would be open to collaborate with others such as yourself who are local to Australia.


Dave:
That sounds like an amazing image if you can pull it off. Am I understanding correctly that the big-picture goal is to create a composite panoramic image of a lunar-eclipse night that includes:

* A foreground panorama (static, untracked, medium exposure)
* A tracked sky panorama (Milky Way during totality, longer exposures)
* A time sequence of the Moon’s path across the sky (short, moon-optimised exposures)

…all stitched together into a single final panorama.

That’s definitely a challenging workflow, especially with the sky rotating continuously and the sky pano during totality being time-critical.

I’m in the process of writing up some documentation for the Alpaca driver that covers use of Advanced Sequencing in NINA, and I’ll try to keep scenarios like this in mind. In principle, it should be possible to handle both tracked and untracked panoramas at defined alt/az coordinates, as well as lunar tracking, though some manual coordinate calculations may be needed.

This is all fairly new territory, so I can’t promise it will work seamlessly, but it’s certainly worth doing a trial run well ahead of the event.

Can you share what type of camera and lens you typically use, and how many panels you would use on the background, foreground and lunar mosaics? Also what tool do you use to stitch?

Billy Bass:
More than happy to share.  Last year, for the lunar eclipse, I used my Nikon Z9 body with the Nikkor Z 20mm f/1.8S lens.  The panorama had a total of 14 panels (seven positions rotating around the azimuth axis and two rows).  For the foreground, I only needed a single exposure for each position.  For the sky background I used a single 10” sub at each of the seven positions.  The lunar shots all fit in four of the positions/panels; it would have been possible to capture the moon in fewer panels, but it would have been more restrictive when putting together the panorama/mosaic.  Every five minutes, or so, I would take a photo of the moon, or two/three photos depending on where the moon was in the sky to make sure the moon could be added to the respective sky panels.  I used Lightroom/Adobe Camera Raw to do the initial processing of the images and then used Photoshop to blend the lunar shots into the sky panels.  Then I took the tiff exports of the blended sky panels from Photoshop and tiff exports of the foreground from Lightroom/ACR and used PTGui to stitch the panorama together.  While it is possible to stitch the panorama together in PixInsight, it is significantly slower of a process (by several orders of magnitude) and would create additional challenges to incorporate the foreground.

When working on panoramas featuring the Milky Way center, I’ve used lenses with focal lengths in [14, 50] mm.  When using a tracker, I would generally aim for 4 subs per sky panels that are 1’ long each.  When using untracked shots, I generally try to keep the subs’ exposure time consistent with 250 / focal length of the lens; the “rule of 500” tends to generate more star elongation than I would want and it is always easy enough to take additional subs for the same integration time.

For the lunar eclipse this year, totality coincides with the Milky Way center’s arch will have its peak around 30 degrees in altitude.  So, I’m planning to use my Ha + visible spectrum modified Nikon Z8 body for the panorama.  I’ve still not settled on the focal length just yet, but it will be in the range of [24, 35] mm.  With a 35mm focal length, I would need two rows of panels for the sky, but could capture the sky with a single row using a 24mm lens.  At 35mm I would need  13-16 panels per row, depending on whether I want 40-50% overlap in the frames.  Fifty percent overlap is fairly standard for astrolandscape panoramas, but given how little overlap is used in deep sky mosaics, I think it could be safe to reduce the overlap into the 25-30% range in the extreme.  Some of the overlap decision will be based on the specific lens used to minimize artifacts that would be visible.  For example, with my 50mm f/1.2 lens, the coma is so bad when shooting wide open that I would definitely want 50% overlap, while using my 20mm f/1.8 lens wide open has significantly less issues with coma and would make smaller overlap much more feasible.  The number of shots used for the foreground is going to depend on the exact location where I end up shooting.  The rock formation that is my current top contender doesn’t have much in the way of stuff that is very close that needs to be kept sharp, compared with more distant rock formations (though the rocks on the top of the formation reminded me of the bridge of the enterprise from Star Trek the next generation which would be cool to capture).  If I end up setting up in a place that has some features that are closer to the tripod location it may be necessary to focus stack each foreground panel.  In the case of focus stacking the total number of subs per foreground panel would be <= 10.  

For the moon shots, if using a 35mm lens and 40% overlap, I would be shooting the moon in 16 of the 26 sky panels to make sure the moon is represented in the overlapping regions of the panels; the six northern most panels won’t have any lunar shots and the 3-4 southern most oriented panels would not require any lunar shots for the first sky row.  

So overall it is a fairly complex shoot, but will hopefully turn out better than what I managed last year.

Billy:
Yes, I’ll be using the same lens for all the shots.  Although it may be possible to use multiple focal lengths for the panels with PTGui, I prefer keeping everything on the same scale.  For the moon shots, it is a fairly simple compositing.  I load the sky panel and all of the lunar shots for that panel into photoshop and then set the layer mode for the lunar shots to lighten or screen.  Then that panel gets exported as a tif with the sky and lunar shots which gets stitched with the foreground and other panels.  So it’s a pretty basic way of getting the lunar shots blended and then the arch shape ends up showing up once PTGui stitches the panorama and projects the final image on the Cartesian plane.  Because there is nothing in the background of the lunar shots (in order to properly expose the lunar surface), there really isn’t any easy way to use any method related to plate solving.  If I only intended to capture the span of the arch of the lunar path over the night and use a focal length that will capture the full path with only a single row, I could probably composite the lunar shots into their own panels and then blend that into the sky background.  I don’t think that would work as well if there are missing panels since it would mean changing the dimensions of the panorama (PTGui expects images for all the panels when using grid alignment as a starting point).  

I’ve not tried Autopano Giga myself.  All of the nightscape photography books I have mentioned using PTGui, so when I first started this stuff I defaulted to going with PTGui as well.  

In the panorama from last year’s lunar eclipse, the moon was only present in the first four sky panels (left to right naturally).  The remaining sky panels were there so I could have some sky represented over the moonbow that I captured earlier in the night (along with the foreground shots since the area was jam packed with people for the first few hours of the night).


------------------------------------------------------------------------------
# ANALYSIS OF PANO INFO ON FORUM
## Summary of prioritised issues people have creating panos with Benro Polaris

While the Benro Polaris is a powerful tool for astrophotography, users have identified several prioritised issues and desired improvements to streamline the creation of complex panoramas. These concerns range from software reliability to geometric challenges caused by the Earth's rotation.

### **1. Software Reliability and State Maintenance**
A primary frustration for users is the Benro app’s inability to "maintain state." Specifically:
*   **Volatile Settings:** The "Pro Pano" mode frequently **fails to remember lens sizes** or settings if a user exits and re-enters the menu.
*   **Setup "Forgetfulness":** The start and end positions of a panorama can be "forgetful," and there is a lack of a dedicated **"clear" or reset option** to quickly restart the setup process.
*   **Operational Errors:** Users have reported "camera busy" errors in certain modes, suggesting that the programming could be improved for better camera communication.

### **2. Geometric Challenges: Horizon Rotation**
One of the most significant technical hurdles is that the Polaris tracks the sky’s rotation, which causes the horizon to tilt relative to the camera frame over time.
*   **Tilted Frames:** In a multi-panel panorama with long exposures, the horizon may rotate by **7.5 degrees or more** between the first and last panels.
*   **Stitching Difficulties:** This rotation results in insufficient sky coverage in some frames and makes it significantly harder to align and stitch the sky panels with static foreground shots in post-processing.
*   **Proposed Solution:** Experienced users suggest a feature that would **rotate the camera to maintain a level horizon** for each panel, even if this results in a "stair-step" pattern in the raw frames, as it would be much easier to stitch.

### **3. Inflexible Sequencing and Movement**
The current automated movement patterns are often seen as restrictive:
*   **Zig-Zag Limitations:** The Polaris currently uses a **zig-zag pattern** for multi-row panoramas, but users want the ability to choose the direction (e.g., always left-to-right) or even shoot by columns instead of rows.
*   **Tracked vs. Untracked Sequencing:** There is a strong desire for a single sequence that can **turn tracking off** for foreground shots and then **turn tracking on** for the sky. Currently, users often have to manage these as separate, manual tasks, which is difficult if the app loses connection or state.

### **4. Planning and Previsualisation**
Users have expressed a need for better "home-based" planning tools:
*   **Presets and Templates:** Many want to create **presets for specific focal lengths** and field-of-view (FOV) requirements (e.g., a 270° horizontal by 70° vertical pano for a full Milky Way arch) before arriving at the location.
*   **Low-Detail Previews:** A "low detail preview" within the app would help ensure that the selected FOV actually captures the intended targets, such as the peak of a galactic arch, without missing the edges.

### **5. Mechanical and Tracking Consistency**
Some users have noted intermittent mechanical issues during long sessions:
*   **Elongated Stars:** Even when the unit is functioning, some frames in a sequence may show **elongated stars** while others are perfect. This is sometimes attributed to gear resistance that may require a "settling" period between exposures.

To understand the horizon rotation issue, imagine you are drawing a straight line across a series of post-it notes on a spinning globe; if your hand moves with the globe's rotation, the line will look straight to the "stars," but when you peel the notes off and lay them flat on a table, the line of the "ground" will appear tilted and jagged from one note to the next.

## Summary of the typical pano parameters from the various users.
Users of the Benro Polaris employ a wide range of parameters depending on their specific goals, such as capturing a full Milky Way arch or a detailed lunar eclipse mosaic. The following summary outlines the typical settings used across various field workflows:

### **1. Focal Length and Field of View**
*   **Common Range:** Most users prefer wide-angle lenses between **14mm and 35mm**. 
*   **Specific Choices:** Focal lengths like **20mm** and **24mm** are highly popular for balancing detail with the number of panels required. 
*   **High-Detail Mosaics:** More experienced photographers sometimes use longer lenses, such as **40mm, 50mm, or even 135mm**, to capture intricate details, though this significantly increases the number of required panels.
*   **Target FOV:** For a full Milky Way arch, a typical target field of view is approximately **270° horizontal by 70° vertical**.

### **2. Overlap Percentages**
*   **Standard Practice:** An overlap of **35% to 50%** is the most frequently cited range. 
*   **Quality Control:** **50% overlap** is often considered the standard for astrolandscape panoramas to ensure successful stitching and to crop out lens artifacts like coma at the frame edges.
*   **Exceptions:** Some users consider reducing overlap to **25–30%** only when using high-quality lenses with minimal distortion.

### **3. Exposure and Stacking Settings**
*   **Sky Panels (Tracked):** Typical exposures range from **30 to 90 seconds** per frame. ISO settings usually fall between **640 and 1600**, with apertures often wide open (e.g., **f/1.4 to f/2.8**).
*   **Sub-frame Stacking:** To reduce noise and eliminate satellite trails, many users capture multiple "subs" per panel—commonly **3 to 5 frames**—which are later stacked.
*   **Foreground Panels (Untracked):** These vary significantly. Some users take quick "blue hour" shots at **1/2 second and low ISO**, while others take long, high-ISO exposures (e.g., **60–90 seconds at ISO 6400**) to match the night sky.

### **4. Panorama Grid Structure**
*   **Layouts:** Common configurations include **single-row** panoramas for simple horizons or **2 to 4 rows** for vertical depth.
*   **Panel Counts:** 
    *   Small panoramas may use as few as **5 to 8 panels**.
    *   Complex projects, such as those involving lunar eclipses or high-resolution mosaics, frequently range from **14 to 48 panels**. 
    *   Extremely detailed panoramas have been reported to include up to **117 individual images**.

### **5. Software for Stitching**
*   **PTGui** is the most frequently mentioned tool for professional stitching due to its speed and accuracy with large mosaics.
*   Other commonly used software includes **Adobe Lightroom/Camera Raw** for initial processing, **Photoshop** for blending sky and foreground, and occasionally **Image Composite Editor (ICE)**.

To visualise the grid structure, imagine a **tiled wall**; for a simple view, you might only need a single row of five tiles, but to see the entire "room" of the night sky, you would need to stack four rows of tiles on top of each other, overlapping the edges so the pattern matches perfectly.

## Tools used
Based on the sources provided, photographers use a variety of specialized software tools to handle the different stages of creating a panorama, from initial raw processing to the final stitching and blending of sky and foreground elements.

### **Initial Processing and Development**
Before stitching begins, users often perform initial adjustments on their raw files.
*   **Adobe Lightroom and Adobe Camera Raw (ACR):** These are the most commonly cited tools for the **initial processing** of images. 
*   **Affinity:** This is also mentioned as a tool used during the broader processing workflow.

### **Stitching Software**
Stitching is the process of joining multiple overlapping frames into a single seamless image.
*   **PTGui:** This is widely regarded by users as a premier tool for stitching complex mosaics. It is praised for being **significantly faster** (by several orders of magnitude) than some astrophotography-specific alternatives.
*   **Image Composite Editor (ICE):** Several users rely on ICE for the stitching phase of their panoramas.
*   **PixInsight:** While primarily a deep-space processing tool, it can be used for stitching, though users note it is **considerably slower** and makes it more difficult to incorporate foreground elements.

### **Blending and Final Compositing**
Once the panels or separate panoramas (sky and foreground) are stitched, they must be blended together.
*   **Adobe Photoshop:** This is the primary tool used for **blending** specific elements—such as lunar shots into sky panels—and for the final merging of a tracked sky panorama with a static foreground panorama. 
*   **NINA (Nighttime Imaging 'N' Astronomy):** While more of a capture and sequencing tool, it is mentioned in the context of using **Advanced Sequencing** to help handle the alignment of tracked and untracked panoramas at the point of capture.



## Lunar Eclipse
Based on the sources, the three main components of Billy’s composite lunar eclipse panorama, as summarised by Dave and confirmed by Billy's technical descriptions, are:

*   **A Foreground Panorama:** This consists of static, untracked images with a medium exposure. Billy notes that these panels must be captured with tracking disabled to maintain a consistent horizon line. In his previous workflow, he only needed a single exposure for each foreground position.
*   **A Tracked Sky Panorama:** This component captures the sky—specifically the Milky Way during totality—using longer exposures. By enabling tracking for these panels, Billy aims to minimise noise and ensure the sky elements align properly with the foreground.
*   **A Time Sequence of the Moon:** This involves a series of short, moon-optimised exposures that track the Moon’s path across the sky. Billy captures these shots approximately every five minutes using a smaller aperture so that the background is effectively clipped to zero, allowing the Moon to be blended into the sky panels later.

To manage the complexity of these three layers, Billy uses **Adobe Photoshop** to blend the lunar shots into the sky panels before using **PTGui** to stitch the completed sky and foreground panoramas together.

Billy’s methodology for a lunar eclipse panorama is a multi-layered composite approach designed to balance the static nature of the Earth with the movement of the stars and the Moon. His strategy involves three distinct capture phases and a refined post-processing workflow.

### **1. The Three-Component Structure**
Billy builds his image from three primary layers to ensure maximum detail and alignment:
*   **Static Foreground:** He captures a series of **untracked images** to maintain a level horizon line,. If the location has close-up features, he may **focus stack** each panel, taking up to 10 sub-exposures per position.
*   **Tracked Sky:** He captures the background sky, including the Milky Way, using **tracking to minimise noise** and allow for longer exposures,.
*   **Lunar Time Sequence:** Every five minutes, he takes short, **moon-optimised exposures**. By using a smaller aperture, he effectively "clips" the background to black, making it easier to layer the Moon into the sky panels later.

### **2. Technical Specifications and Gear**
For his upcoming projects, Billy plans to use a **Nikon Z8** (modified for Ha + visible spectrum) with a lens in the **24mm to 35mm range**. 
*   **Grid Layout:** At 35mm, he requires **two rows of sky panels**, whereas a 24mm lens allows for a single row.
*   **Overlap:** He prefers a **50% overlap** to reduce lens artifacts like coma, though he considers **25–30%** acceptable for high-quality lenses.
*   **Lunar Placement:** To ensure the Moon is captured correctly within the mosaic, he might shoot it in as many as **16 out of 26 sky panels** so that it appears clearly in overlapping regions.

### **3. Workflow and Software**
Billy’s processing involves a specific sequence of professional tools:
*   **Initial Development:** He uses **Adobe Lightroom or Camera Raw** for the first stage of raw processing.
*   **Blending:** He uses **Photoshop** to blend the individual lunar shots into the respective tracked sky panels.
*   **Stitching:** Once the sky panels are prepared, he exports them as TIFFs and uses **PTGui** to stitch the sky and foreground together. He notes that while PixInsight is an option, PTGui is significantly faster for this type of complex panorama.

### **4. Desired Improvements for Future Panos**
Billy has identified several "game-changing" features he would like to see in the Polaris to simplify this process:
*   **Integrated Sequencing:** The ability to program a **single sequence** that automatically switches from untracked foreground shots to tracked sky shots.
*   **Horizon Maintenance:** A feature that **rotates the camera** to keep the horizon level for every panel. Without this, the Earth's rotation can cause the horizon to tilt by **7.5 degrees or more** over the course of a long panorama, making stitching and alignment with the foreground extremely difficult.
*   **Non-Zig-Zag Patterns:** He finds the current "zig-zag" movement pattern restrictive and would prefer a sequence that shoots every row in the same direction (e.g., always left-to-right).

Creating this type of panorama is like **assembling a moving jigsaw puzzle**; while you are trying to piece together the static ground, the "sky" pieces are constantly rotating and the "moon" piece is sliding across the board, requiring you to carefully map out exactly where every part belongs before they move out of frame.

--------------------------------------------------------------------------------
## Capturing Panoramas (Horizon-Locked & Sky Mosaics)

**Panorama Mosaics** allow the Polaris mount to automatically move between predefined panel positions to capture **foreground, horizon-aligned sky, or fully celestial mosaics**.

This feature is designed for:
* **Foreground or Landscape panoramas** (no tracking)
* **Horizon-aligned sky mosaics** (tracked, roll-locked)
* **Celestial sky mosaics** (tracked, free rotation)
* **Tracked orbital mosaics**


## Panorama/Mosaic Settings

Panorama settings are configured in the **Panorama Settings** card in Alpaca Pilot.

### **Panorama/Mosaic Layout**

* **Columns (cols)**:
  Number of horizontal panels across the mosaic. *Range: 2–14*

* **Rows (rows)**:
  Number of panels vertically. *Range: 1–3*

* **Horz Step (hstep)**:
  Angular distance, in **decimal degrees**, between the centers of adjacent horizontal panels. *Panel Step is typically set to ~80% of the camera horizontal field-of-view, which produces approximately 20% overlap between adjacent panels.*

* **Vert Step (vstep)**:
  Angular distance, in **decimal degrees**, between the centers of adjacent vertical panels. *Panel Step is typically set to ~80% of the camera vertical field-of-view, which produces approximately 20% overlap between adjacent panels.*

* **Panel Order (order)**:
Defines the sequence in which panels are captured.
  * **0 - Row-Major**:
    Complete each row before moving to the next row.
  * **1 - Column-Major**:
    Complete each column before moving to the next column.
  * **2 - Serpentine**:
    Alternate direction on each row or column to minimise repositioning time.

* **Orientation and Tracking (track)**:
Defines how the mount tracks and how camera rotation (roll) is handled **after moving to each panel**.

  * **0 - Landscape - Untracked**:
  Tracking is disabled. The camera frame remains fixed relative to the horizon. *Use for foreground or landscape panels where star motion is acceptable.*

  * **1 - Sky - Horizon-Locked**:
  Sidereal tracking is enabled. The camera roll is reset to **0°** at each panel. *Use for horizon-aligned sky mosaics where consistent frame orientation is required.*

  * **2 - Sky - Celestial**: 
  Sidereal tracking is enabled. Camera roll is **not modified** between panels. *Use for astronomical sky mosaics (e.g. large DSOs).*

  * **3 - Sky - Orbital**: 
  Tracking and camera roll are left unchanged.
  *Use for mosaics centered on tracked orbitals.*

---


### **Recenter at Reference Point**
Defines the coordinate system and a reference point used to position the mosaic.

* **Recenter Element (recenter)**:
  Defines the element of the mosaic to recenter at the reference point. 
  * **0 - Whole Mosaic**: Recenter the whole mosaic
  * **n - Panel n**: Recenter panel n at reference point, shifting all other panels accordingly. 
  
* **Reference Point Type (ref)**:
  Defines the co-ordinate system of the Reference Point
  * **0 - Az/Alt/Roll**: Reference Point is a Topocenteric co-ordinate
  * **1 - RA/Dec/PA**: Reference Point is an Equatorial co-ordinate. 
  * **2 - OrbitalID**: Reference Point is an Orbital ID. 
  * **3 - Current Orientation**: Use the current mount orientation as the Reference Point. Store as equatorial co-ordinate if tracking enabled, otherwise store as topocentric co-ordinate.
  
* **Reference Point**:
  Defines the Reference point used to position the mosaic.
  * **Reference Axis 1 (r1)** — Azimuth, Right Ascension or OrbitalID
  * **Reference Axis 2 (r2)** — Altitude or Declination, in decimal degrees
  * **Reference Axis 3 (r3)** — Roll or Position Angle, in decimal degrees

### **Panel Navigation**

Displays a grid of **Rows × Columns**, numbered according to the capture order.
  * **Current Panel (panel)** — Panel number currently being captured.
  
### Device Action > Telescope > Polaris:PanoSet Parameters
An Advanced Sequence can set each and/or all of these parameters using the PanoSet Action.
For Example, the following would setup a 5x3 Panorama

Parameters `{"cols":5, "rows":3, "hstep": 50, "vstep": 30, "order":2, "track":2, "recenter":3, "ref":0, "r1":180, "r2":30, "r3":10, "panel":2 }`


## Loop for each panorama panel:
* Re-point to the target **Alt/Az tile center**
* Rotate the camera about the optical axis so the **horizon is level**
* Capture tracked sub-exposures for Sky mosaics
* Capture untracked exposures for Foreground mosaics (optionally focus stacked)

## Benro Firmware Trigger Capture
Did you already investigate the Polaris protocol commands used to remote control a connected DSLR, it seems the cmd 265, 266, 267, 268, 272, 275, 282, 286, 297, ... are involved but I couldn't use the method I used before to spy the protocol using my Mac, Apple removed the tool... and I was not able to setup the Raspberry Pi to activate properly the monitor mode...

## Benefits
* Eliminates cumulative horizon tilt across panels
* Produces predictable, translation-dominant frames that are far easier to stitch
* Aligns sky panels cleanly with static foreground images
* Matches how terrestrial panorama systems operate
* Ability to save panorama templates for a given focal length, and mosaic widthxheight

This directly addresses user pain points with rotating horizons in multi-panel sky panoramas.


**Sky Mosaic Capture Notes**

* **Field rotation** still occurs during each exposure, limiting the **maximum exposure time per panel** even when tracking is enabled.
* **Time separation between adjacent panels** is critical; long delays can cause stars in overlapping regions to **misalign**.
* Using **portrait orientation** often allows a mosaic to fit in a **single row**, minimising the time between adjacent panels.
* For **multi-row mosaics**, capture panels in **column-by-column order** rather than row-by-row to keep **vertical neighbors** close in time and improve **stitching reliability**.
* Wide mosaics requiring multiple rows without careful sequencing can introduce **large time gaps** between vertically adjacent panels, increasing **stitching difficulty**.



### Sky Mosaic Capture using Locked-Horizon

**Caution:**

* **Field rotation** occurs during each exposure, limiting the **maximum exposure time per panel**.
* **Long time gaps** between adjacent panels can cause stars in overlapping regions to **misalign**, especially in multi-row mosaics.
* Wide mosaics captured without careful sequencing can result in **large vertical time separations**, increasing **stitching difficulty**.
* Projection distortion increases for **wide mosaics**, **near zenith**, **near poles**

**Recommendations:**

* Use **portrait orientation** when possible to reduce the mosaic to a **single row**, minimizing time gaps between adjacent panels.
* For **multi-row mosaics**, capture panels in **column-by-column order** rather than row-by-row to keep **vertical neighbors close in time**.
* Limit **exposure duration per panel** to reduce field rotation effects, particularly at low altitudes or near the horizon.
* Maintain sufficient **overlap** (≥25–40%) to provide stitching tolerance for small rotational shifts.



## Enforced timing limits (per adjacent panel)
To keep stitching reliable, limit sky rotation between overlapping panels to ≈ **0.3°**:
[
\Delta T_{\max}(\text{minutes}) \approx \frac{1.2}{\cos(\text{Altitude})}
]

Typical guidance:

* **20–40° alt**: 60–90 s per panel (strict)
* **45–65° alt**: 100–150 s per panel (ideal)
* **>80° alt**: warn or disable mode

Total panorama duration should be constrained:

* 1-row mosaics: ≤ 30–40 min
* 2-row mosaics: ≤ 20–25 min
* 3+ rows: discouraged


## Mosaic topology rules

* **Single-row (e.g. 10×1)**: low risk, sequential capture acceptable
* **Multi-row (e.g. 10×2)**:

  * Use **column-interleaved capture**
  * Avoid row-by-row sequencing
  * Increase vertical overlap (≥25–30%)
* **3+ rows**: strongly discourage or restrict

## Full-frame lenses — effective FOV with overlap

| Lens      | FF FOV (W×H) | **25% Overlap** | **40% overlap** | Safe mosaic size | Max rows | Max sky width |
| --------- | ------------ | ------------------------- | ------------------------- | ---------------- | -------- | ------------- |
| **14 mm** | 104° × 81°   | **78° × 61°**             | **62° × 49°**             | 1–3 × 1          | 1        | ~180°         |
| **20 mm** | 84° × 62°    | **63° × 47°**             | **50° × 37°**             | 3–6 × 1          | 2        | ~200°         |
| **24 mm** | 74° × 53°    | **56° × 40°**             | **44° × 32°**             | 3–6 × 1          | 2        | ~180°         |
| **35 mm** | 54° × 38°    | **41° × 29°**             | **32° × 23°**             | 4–8 × 1          | 2        | ~150°         |
| **50 mm** | 40° × 27°    | **30° × 20°**             | **24° × 16°**             | 5–10 × 1         | 1–2      | ~120°         |



## Bottom line

A **fixed Alt/Az grid with per-panel roll reset** is a **sound, implementable solution** that significantly improves horizon-aligned sky panoramas, provided **time, topology, and exposure limits are enforced in software**.



