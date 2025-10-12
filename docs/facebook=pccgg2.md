Polaris -Camera Controller Global Group
David Morrison
 ·

Top contributor
 ·
ondoestSprm5
c
 
74m
t
m
O
:
th2l6u
o
6
9
e
3
 
t
102cu9
 
P
 
mah
3
08mf
r
l
0
l
a
7
4
b
M
 ·
Alpaca Driver V2.0 is coming with pulse-guiding, rotator, three star alignment and much more. I need your help. More will follow.
David Morrison
Pavel Vorobiev Uli Fehr The Alpaca Driver is an open-source project that enables third-party applications like NINA and Stellarium to control the Benro Polaris mount. Version 2.0 is nearing completion, and we’re preparing to launch the Beta testing phase. This post serves as an early heads-up for those interested in getting involved, testing new features, and helping shape the final release. Stay tuned—this community's feedback will be crucial in helping you make the most of your Polaris yet.
4d
Reply
Billy Bass
I would be more than happy to help, but I still have yet to figure out why NINA is unable to recognize my camera when I try connecting my windows tablet; I have all the Nikon software installed and the Nikon software doesn’t seem to have any issues connecting or communicating, but it makes it a bit difficult to try using it with the Alpaca driver.
5d
Reply
Baha Baydar
Billy Bass Make sure the Nikon software isn't running when you have Alpaca going. With my Canon, if the EOS app is running it takes over all communication to the camera, so Alpaca can't talk to it.
4d
Reply
Billy Bass
Baha Baydar it isn’t running. I only installed it to make sure the camera drivers would be available on the machine. The OS recognizes the camera is connected, but tells me it would be faster to use a USB3 port, which ironically is the only way to connect to that tablet and the camera body.
4d
Reply
Richard Healey
Billy Bass that's a pretty good clue that you have a problem with the type of USB cable you have in use.
4d
Reply
Billy Bass
Richard Healey except it is the same USB cable I use with the Polaris to the camera without issue every time.
4d
Reply
Richard Healey
Billy Bass it's possible that your polaris does not know or care about the many, many intricacies of USB cables (in this case almost certainly E marker) - but your OS does. It's cheap and simple to find a USB cable that has an e marker embedded and which is advertised to support an appropriate data transfer rate and USB version to rule that out as the problem.
I regularly plug in the same device to the same laptop or desktop and get the "your device would....." message when I'm using the wrong cable.
4d
Reply


Billy Bass
So you’re suggesting that manufacturers are installing USB3 male connectors on USB2 cables?
4d
Reply
Alexander Murdoch
Billy Bass would your camera happen to be a Z8? there was a funny workaround I had to do to make this camera work with NINA!
4d
Reply
Billy Bass
Alexander Murdoch I have a Z8 and Z9. I’ve not come across any work arounds specific to the Z8 though. Can you share what you’re aware of so I can try to test things?
4d
Reply
Billy Bass
Alexander Murdoch just for the hell of it, I tried with my Z9 body this morning; granted it isn’t really that different from a Z8 but does have its own distinct firmware. I can only attach a single photo at a time, but hopefully this will help clarify what is going on. Also, David Morrison, do you have any idea why the pitch, yaw, and roll values would be changing when tracking was not enabled and a camera was not attached to the Polaris?
May be an image of text
3d
Reply
Billy Bass
Alexander Murdoch here’s what NINA looks like
May be an image of text that says 'Astrenomy 2RC00S Defaul Camera Nikon Name RELEASECANDNDATE RELEASE CANCIDATE Description Driver Dype Temperature.control control Temperature Driver version Sensor name exposure Sensor size Max buning Pael PaelsizeX Mas Max eposure time Max binning Piel size vize ae Settings fecfene'
3d
Reply
Billy Bass
Alexander Murdoch and here is the operating system recognizing the camera, but suggesting the USB-C cable that I am using to connect two devices via USB-C ports is not fast enough:
May be an image of text
3d
Reply
David Morrison
Billy Bass the pitch, yaw, roll changes look like sensor noise to me. I think you can safely ignore it.
3d
Reply
Billy Bass
David Morrison interesting. I would think they might try to store/persist state and use a Boolean to indicate when state has changed (e.g., during tracking and during/after slewing set to true but false otherwise). Now I’m kind of curious to know if the noise is ignorable and if so whether it accumulates to the point that it becomes non-ignorable at some point.
3d
Reply
Real Bread Aotearoa
Billy Bass Depending on what version of NINA you have installed, will effect the connectivity with the Z8 and Z9. With NINA 3.1 HF2, Z8 will not connect natively and there is no Live View .... but as Alexander Murdoch says, there is a work around, though you still won't have Live View (needed for AF)
However, the latest BETA versions of NINA 3.2 and the Candidate Releases (currently at RC009) will now natively connect Z8 and Z9, plus you also get Live View! This allows you to take advantage of the awesome NINA 'plug in' "Lens AF" ... so you now also get autofocusing for Nikon and pin point stars.
Hope that helps.
Cheers, Mark 😀
3d
Reply




Cam Palmer
Thanks to yourself and all the other contributors for your leadership, skills and commitment to continue to develop the Polaris environment. Good on you!
4d
Reply
Baha Baydar
I can help with testing. I'm just getting everything set back up on a new laptop.
4d
Reply
Alexander Murdoch
exciting! can’t wait to give this a crack
5d
Reply
David Jensen
Blows my mind that a third party has to provide these features and not the manufacturer....
5d
Reply
Steve Everitt
Count me in. I’m in the Canary Islands so get a lot of clear skies.
4d
Reply
Eric Chiu
Going to give it a go 🙂
5d
Reply
Uli Fehr
  · 
What are you talking about?
5d
Reply
Jerry Levin
Following!
5d
Reply
William Siers
Awesome I’m in!
3d
Reply
Shiyang Steven Zhang
When can we expect it???
5d
Reply
David Morrison
Shiyang Steven Zhang Beta release will be next week. Depending on the results of the Beta test, the official release is likely in Dec 2025.
3d
Reply
Shiyang Steven Zhang
David Morrison cool!
3d
Reply




Miguelito Duarte
That's amazing. How can we help?
4d
Reply
Pavel Vorobiev
  · 
I am new to Alpaca driver subject. Is it for controlling the BP from NINA?
4d
Reply
Facebook
Facebook
Facebook
Facebook
Facebook
Facebook
Facebook
Facebook
Facebook
Facebook
Facebook


