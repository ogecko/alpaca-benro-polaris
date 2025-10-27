Polaris - Camera Controller Global Group

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