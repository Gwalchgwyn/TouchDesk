# TouchDesk
Touch-screen based OSC enabled digital sound desk communication software for use on Raspberry Pi.

TouchDesk is the working name for prototype software that allows remote use of a digital sound desk from a Raspberry Pi using a touchscreen.
It allows a sound technician or installer to set up a sound desk as they would normally, but leave the end-user with a simple, clean, and limited interface
on what settings can be used or adjusted, thus preventing unintentional damage and limits confusion to those with little experience or knowledge of sound equipment.
A technician may use some of the advanced features of a sound desk such as parametric or graphical EQs, compressors, expanders, duckers, gain pots, or any other 
feature, and then present just a mute button and fader in a clean, low-profile, wall-mountable, touchscreen up to the max distance of a PoE enabled Cat5/6 cable. 
This can also be done over a wireless network if the Raspberry Pi is powered locally. It currently also provides a rudimentary interface for Bluetooth connectivity,
allowing the RPi to become a Bluetooth audio sink and outputting that audio to its 3.5mm stereo jack. This gives the installer the option of transferring audio into
the same sound desk to be manipulated by the TouchDesk software.

TouchDesk uses Python 3 as its main language, with PySide2 for its GUI. It communicates with sound equipment using OSC language, and a Python extension called "Python-osc". Documentation for this can be found here: https://python-osc.readthedocs.io/en/latest/ The script also uses BlueAlsa and dbus for controlling and using the RPis bluetooth features within Python. The code found on the following website was used and adapted for use in this script: https://scribles.net/controlling-bluetooth-audio-on-raspberry-pi/. I would also like to thank the user Eyllanesc on StackOverflow for their help with integrating this into TouchDesk: https://stackoverflow.com/questions/64615035/integrating-two-python-scripts-into-one/64656528#64656528

The purpose of writing this script was to allow sound technicians and installers a cheap and viable way to provide a simple interface for end-users to operate a sound system in, say for instance, a school or recreation center without the need of a sound technician present or greater knowledge of sound control devices such as mixing desks. Many local community centers rely heavily on having a working sound system for the various community events that may occur in them, and sadly they are often working on a very limited budget. This software offers a cheap and effective solution to the problem of having a bulky and often confusing system in place for those without prior knowledge of sound systems. Used in conjunction with a Raspberry Pi, a touchscreen can be wall mounted and controls limited to just a fader and mute button. The device can be powered over PoE, so no expensive electrical work is needed. The limited interface can prevent unintentional damage (by restricting use of gain pots and compressors), and its locking ability can prevent use from unauthorised people.

I am not a programmer. This project started for me when the coronavirus lockdown began in March 2020. With time on my hands i watched a few YouTube videos on coding in Python, did a little research, bought a book on QT for Python and gave it a go. Through many hours of trial, error, and late night googling, i have created this script. It has been deployed on a site since September 2020 (It is Jan 4th 2021 at time of writing) and have had no problems reported so far apart from minor aesthetic criticisms (the password lock time-out was increased from 2 minutes to 15). The Raspberry Pis installed have been running 24/7 since installation without any reported issue. Users have said that its far easier for them to use and understand. Its smaller profile has also allowed them extra physical space to conduct their activities.

There are a number of things i would like to change and upgrade with the script, however my inexperience with coding and lack of knowledge in the field is now reaching a point where i feel i need help from people who know more than i and are interested in developing this further. My intention with this software is to have it available for free forever, i do not want anyone selling or profiting directly from the script, however it is intended for installers to use as part of a sale of a sound system installation.

Currently it only has commands for use with the Behringer X-Air range of desks, and only tested with the Behringer XR12. However, as it uses OSC language, it can in theory be used with ANY desk that utilises OSC language. This will require input from many people who can provide a list of OSC commands for a particular brand and make of sound desk. To make further progress with TouchDesk, an "admin" interface will be required, so that an installer or technician can select the brand and make of desk being used in the installation. Once selected, the OSC commands of that particular desk can be called from a dictionary and used as a variable in the script to send the correct OSC command structure to the sound desk. An "admin" interface can also allow the installer to change or disable password requirements of the script. There is also potential for interface customisation - currently it only provides 4 channels within its interface, but these channels can easily be created dynamically through the use of dictionaries. Adding other features such as EQ controls or compressors can also be done. There is essentially no reason why the manufacturers tablet apps can't be recreated or reimagined and customised through this method.

If anyone with any experience in coding is interested in contributing to this project, please let me know. I am contactable through my email: info@reedaudiovisual.com
