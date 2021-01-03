import sys

from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *

import dbus
import dbus.mainloop.glib

import argparse
import random
import time
import os.path

from pythonosc import osc_message_builder
from pythonosc import udp_client

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--ip", default="169.254.242.230", help="The ip of the OSC server")
parser.add_argument("--port", type=int, default=10024, help="The port the OSC server is listening on")
args = parser.parse_args()

client = udp_client.SimpleUDPClient(args.ip, args.port)

mainfont = "Carlito Bold"

faderon = """
QSlider::vertical {
    background-color: #2b2b2b;
    border-right: 1px solid black;
    border-bottom: 1px solid black;
    border-left: none;
    border-top: none;
    }

QSlider::groove:vertical {
    height: 300px;
    width: 8px;
    border-radius: 3px;        
    }

QSlider::handle:vertical {
    background: #8d8d8d;
    border: 2px solid black;
    height: 45px;
    margin: 0 -20px; /* expand outside the groove */
    border-radius: 24px;               
    }

QSlider::add-page:vertical {
    background: #007fe0;
    border-radius: 3px;
    }

QSlider::sub-page:vertical {
    background: white;
    border-radius: 3px;
    } 

QSlider::handle:vertical:pressed {
    background: #565656;
    }"""

faderoff = """
QSlider::vertical {
    background-color: #4a4a4a;
    border-right: 1px solid black;
    border-bottom: 1px solid black;
    border-left: none;
    border-top: none;
    }

QSlider::groove:vertical {
    height: 300px;
    width: 8px;
    border-radius: 3px;        
    }

QSlider::handle:vertical {
    background: #cdcdcd;
    border: 2px solid black;
    height: 45px;
    margin: 0 -20px; /* expand outside the groove */
    border-radius: 24px;               
    }

QSlider::add-page:vertical {
    background: #70b0e1;
    border-radius: 3px;
    }

QSlider::sub-page:vertical {
    background: white;
    border-radius: 3px;
    } 

QSlider::handle:vertical:pressed {
    background: #b0b0b0;
    }"""

muteon = """ 
background-color: #2b2b2b; 
color: #f80101; 
font-size: 36px;
border: none;
border-right: 1px solid black;
border-left: none;
border-top: none;

"""

muteoff = """
background-color: #4a4a4a; 
color: #818181; 
font-size: 36px;
border: none;
border-right: 1px solid black;
border-left: none;
border-top: none;
"""

chanlabon = """
background: #2b2b2b; 
color: white; 
font-size: 18px; 
border-right: 1px solid black; 
border-bottom: 1px solid black;
border-left: none;
border-top: none;
"""

chanlaboff = """
background: #4a4a4a; 
color: white; 
font-size: 18px; 
border-right: 1px solid black; 
border-bottom: 1px solid black;
border-left: none;
border-top: none;
"""

volumeon = """
background: #2b2b2b; 
color: white; 
font-size: 18px; 
border-right: 1px solid black; 
border-bottom: 1px solid black;
border-left: none;
border-top: none;
"""

volumeoff = """
background: #4a4a4a; 
color: white; 
font-size: 18px; 
border-right: 1px solid black; 
border-bottom: 1px solid black;
border-left: none;
border-top: none;
"""

passwordkeys = """ 
QPushButton::enabled {
background-color: #2b2b2b; 
color: white; 
font-size: 36px;
border: 1px solid black;
border-radius: 35px;
}
QPushButton::pressed {
background-color: #606060; 
color: white; 
font-size: 36px;
border: 1px solid black;
border-radius: 35px;
}
"""

enterdelbtns = """ 
QPushButton::enabled {
background-color: #2b2b2b; 
color: white; 
font-size: 30px;
border: 1px solid black;
border-radius: 35px;
}
QPushButton::pressed {
background-color: #606060; 
color: white; 
font-size: 30px;
border: 1px solid black;
border-radius: 35px;
}
"""

tabbar = """
QTabBar::tab {
    height: 50px; 
    width: 106px;
    background: #0d1f2d;
    color: white;
    font-size: 16px;
    border: none;
    border-right: 1px solid white;
    }
QTabBar::tab:selected{
    background: #082740;
    border: none;
    border-right: 1px solid white;
    border-bottom: 1px #082740;
    }
QTabBar::tab:disabled{
    background: #203140;
    color: grey;
    }
QTabBar::tab:pressed{
    background: #082740;
    }
"""

bluetoothbtn = """ 
QPushButton::enabled {
background-color: #2b2b2b; 
color: white; 
font-size: 35px;
border: 1px solid black;
border-radius: 32px;
}
QPushButton::pressed {
background-color: #606060; 
color: white; 
font-size: 35px;
border: 1px solid black;
border-radius: 32px;
}
"""

bluetoothtext = """
color: white; 
font-size: 20px;
border: none;
"""


class MuteButton(QPushButton):
    def __init__(self):
        QPushButton.__init__(self)
        self.setText("ON")
        self.setFont(mainfont)

        self.setFixedWidth(98)
        self.setFixedHeight(48)

        self.setStyleSheet(muteon)


class VolumeLabel(QLabel):
    def __init__(self):
        QLabel.__init__(self)
        self.setText("0")
        self.setFixedWidth(49)
        self.setFixedHeight(28)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(mainfont)
        self.setStyleSheet(volumeon)


class ChannelLabel(QLabel):
    def __init__(self, number):
        QLabel.__init__(self)
        self.number = number
        self.bluechan = 4
        if self.number == self.bluechan:
            self.bluetoothicon = QPixmap("./images/bluetooth2.png")
            self.bluetoothiconoff = QPixmap("./images/bluetoothoff.png")
            self.setPixmap(self.bluetoothicon)
        else:
            self.setText(f"#{str (number)}")
            self.setAlignment(Qt.AlignCenter)
            self.setFont(mainfont)

        self.setStyleSheet(chanlabon)
        self.setFixedWidth(49)
        self.setFixedHeight(28)

    def set_label(self, state):
        if state == 1:
            if self.number == self.bluechan:
                self.bluetoothicon = QPixmap("./images/bluetooth2.png")
                self.setPixmap(self.bluetoothicon)
                self.setStyleSheet(chanlabon)
            else:
                self.setText(f"#{str(self.number)}")
                self.setAlignment(Qt.AlignCenter)
                self.setFont(mainfont)
                self.setStyleSheet(chanlabon)
        elif state == 0:
            if self.number == self.bluechan:
                self.bluetoothiconoff = QPixmap("./images/bluetoothoff.png")
                self.setPixmap(self.bluetoothiconoff)
                self.setStyleSheet(chanlaboff)
            else:
                self.setText(f"#{str(self.number)}")
                self.setAlignment(Qt.AlignCenter)
                self.setFont(mainfont)
                self.setStyleSheet(chanlaboff)


        # this frame works, keep as example (28/05/2020)
        # frame = QFrame(self)
        # frame.setFrameShape(QFrame.Box)
        # frame.setFrameShadow(QFrame.Plain)
        # frame.setLineWidth(1)
        # frame.setMidLineWidth(1)


class Fader(QSlider):
    def __init__(self):
        QSlider.__init__(self)
        self.fader = QSlider(Qt.Vertical)
        self.setFixedWidth(98)
        self.setFixedHeight(338)
        self.setStyleSheet(faderon)


class ChannelStrip(QWidget):
    def __init__(self, channum):
        QWidget.__init__(self)
        self.channum = channum
        self.setFixedHeight(422)
        self.setFixedWidth(98)

        self.mute = MuteButton()
        self.volume = VolumeLabel()
        self.chanlab = ChannelLabel(self.channum)
        self.fader = Fader()

        mutelayout = QVBoxLayout()
        mutelayout.addWidget(self.mute)
        volumelayout = QVBoxLayout()
        volumelayout.addWidget(self.volume)
        chanlablayout = QVBoxLayout()
        chanlablayout.addWidget(self.chanlab)
        faderlayout = QVBoxLayout()
        faderlayout.addWidget(self.fader)

        volchanstrip = QHBoxLayout()
        volchanstrip.addLayout(chanlablayout)
        volchanstrip.addLayout(volumelayout)

        channelstrip = QVBoxLayout()
        channelstrip.setContentsMargins(0, 0, 0, 0)
        channelstrip.setSpacing(0)
        channelstrip.setAlignment(Qt.AlignCenter)

        channelstrip.addLayout(faderlayout)
        channelstrip.addLayout(volchanstrip)
        channelstrip.addLayout(mutelayout)

        self.fader.valueChanged.connect(self.fader_value)
        self.fader.valueChanged.connect(update_timer)
        self.mute.released.connect(self.mute_pressed)
        self.mute.released.connect(update_timer)

        self.setLayout(channelstrip)

    def fader_value(self):
        value = int(self.fader.value() / 9.9)
        self.volume.setText(str(value))
        sentvalue = float(self.fader.value()/132)
        client.send_message(f"/ch/0{self.channum}/mix/fader/", sentvalue)

    def send_mute(self, status):
        client.send_message(f"/ch/0{self.channum}/mix/", status)

    def mute_pressed(self):
        state = self.mute.text()
        if state == "ON":
            self.send_mute(0)
            self.fader.setStyleSheet(faderoff)
            self.volume.setStyleSheet(volumeoff)
            self.chanlab.set_label(0)
            self.mute.setStyleSheet(muteoff)
            self.mute.setText("OFF")

        elif state == "OFF":
            self.send_mute(1)
            self.fader.setStyleSheet(faderon)
            self.volume.setStyleSheet(volumeon)
            self.chanlab.set_label(1)
            self.mute.setStyleSheet(muteon)
            self.mute.setText("ON")

    def mute_all(self):
        self.send_mute(0)
        self.fader.setStyleSheet(faderoff)
        self.volume.setStyleSheet(volumeoff)
        self.chanlab.set_label(0)
        self.mute.setStyleSheet(muteoff)
        self.mute.setText("OFF")


class NetworkMenu(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.testlabel = QLabel("NETWORK MENU")
        self.testlabel.setStyleSheet("color: white; border: none")
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.testlabel)
        self.setLayout(layout)

class AudioManager(QObject):
    statusChanged = Signal(str)
    infoChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player_iface = None
        self._transport_prop_iface = None

    def initialize(self):
        bus = dbus.SystemBus()
        obj = bus.get_object("org.bluez", "/")
        mgr = dbus.Interface(obj, "org.freedesktop.DBus.ObjectManager")
        player_iface = None
        transport_prop_iface = None
        for path, ifaces in mgr.GetManagedObjects().items():
            if "org.bluez.MediaPlayer1" in ifaces:
                player_iface = dbus.Interface(
                    bus.get_object("org.bluez", path), "org.bluez.MediaPlayer1"
                )
            elif "org.bluez.MediaTransport1" in ifaces:
                transport_prop_iface = dbus.Interface(
                    bus.get_object("org.bluez", path), "org.freedesktop.DBus.Properties"
                )
        if not player_iface:
            raise Exception("Error: Media Player not found.")
        if not transport_prop_iface:
            raise Exception("Error: DBus.Properties iface not found.")

        self._player_iface = player_iface
        self._transport_prop_iface = transport_prop_iface

        bus.add_signal_receiver(
            self.handle_property_changed,
            bus_name="org.bluez",
            signal_name="PropertiesChanged",
            dbus_interface="org.freedesktop.DBus.Properties",
        )


    def play(self):
        self._player_iface.Play()
        update_timer()

    def pause(self):
        self._player_iface.Pause()
        update_timer()

    def next(self):
        self._player_iface.Next()
        update_timer()

    def previous(self):
        self._player_iface.Previous()
        update_timer()

    def set_volume(self, Volume):
        if Volume not in range(0, 128):
            raise ValueError("Possible Values: 0-127")
        self._transport_prop_iface.Set(
            "org.bluez.MediaTransport1", "Volume", dbus.UInt16(vol)
        )

    def handle_property_changed(self, interface, changed, invalidated):
        if interface != "org.bluez.MediaPlayer1":
            return
        for prop, value in changed.items():
            if prop == "Status":
                self.statusChanged.emit(value)
            elif prop == "Track":
                info = dict()
                for key in ("Title", "Artist", "Album"):
                    info[key] = str(value.get(key, ""))
                self.infoChanged.emit(info)

class BluetoothMenu(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self._manager = AudioManager()
        self._manager.initialize()
        self._manager.infoChanged.connect(self.handle_info_changed)

        self.playbtn = QPushButton("▶")
        self.pausebtn = QPushButton("⏸")
        self.nextbtn = QPushButton("⏭")
        self.prevbtn = QPushButton("⏮")
        self.resetbtn = QPushButton("🔄")

        self.playbtn.setFixedSize(65, 65)
        self.pausebtn.setFixedSize(65, 65)
        self.nextbtn.setFixedSize(65, 65)
        self.prevbtn.setFixedSize(65, 65)
        self.resetbtn.setFixedSize(65, 65)
        self.playbtn.setFont(QFont("SEGUISYM", 1))
        self.pausebtn.setFont(QFont("SEGUISYM", 1))
        self.nextbtn.setFont(QFont("SEGUISYM", 1))
        self.prevbtn.setFont(QFont("SEGUISYM", 1))
        self.resetbtn.setFont(QFont("SEGUISYM", 1))

        self.titlelabel = QLabel()
        self.artistlabel = QLabel()
        self.albumlabel = QLabel()

        self.titlelabel.setFixedSize(300, 50)
        self.artistlabel.setFixedSize(300, 50)
        self.albumlabel.setFixedSize(300, 50)
        self.titlelabel.setAlignment(Qt.AlignLeft)
        self.artistlabel.setAlignment(Qt.AlignLeft)
        self.albumlabel.setAlignment(Qt.AlignLeft)

        self.statictitle = QLabel("Track:")
        self.staticartist = QLabel("Artist:")
        self.staticalbum = QLabel("Album:")
        self.statictitle.setAlignment(Qt.AlignRight)
        self.staticartist.setAlignment(Qt.AlignRight)
        self.staticalbum.setAlignment(Qt.AlignRight)

        self.playbtn.setStyleSheet(bluetoothbtn)
        self.pausebtn.setStyleSheet(bluetoothbtn)
        self.nextbtn.setStyleSheet(bluetoothbtn)
        self.prevbtn.setStyleSheet(bluetoothbtn)
        self.resetbtn.setStyleSheet(bluetoothbtn)
        self.titlelabel.setStyleSheet(bluetoothtext)
        self.artistlabel.setStyleSheet(bluetoothtext)
        self.albumlabel.setStyleSheet(bluetoothtext)
        self.statictitle.setStyleSheet(bluetoothtext)
        self.staticartist.setStyleSheet(bluetoothtext)
        self.staticalbum.setStyleSheet(bluetoothtext)

        #BtnStates = {
        #    playon: "./images/playon.png",
        #    playoff: "./images/playoff.png",
        #    pauseon: "./images/playbtn.png",
        #    pauseoff: "./images/offpressbtn.png"
        #}

        #self.playicon = QPixmap("./images/play.png")
        #self.playbtn.setPixmap(self.playicon)
        #self.pauseicon = QPixmap("./images/pause.png")
        #self.pausebtn.setPixmap(self.pauseicon)
        #self.nexticon = QPixmap("./images/next.png")
        #self.nextbtn.setPixmap(self.nexticon)
        #self.previcon = QPixmap("./images/prev.png")
        #self.prevbtn.setPixmap(self.previcon)
        #self.reseticon = QPixmap("./images/reset.png")
        #self.resetbtn.setPixmap(self.reseticon)

        self.playbtn.released.connect(self._manager.play)
        self.pausebtn.released.connect(self._manager.pause)
        self.nextbtn.released.connect(self._manager.next)
        self.prevbtn.released.connect(self._manager.previous)
        self.resetbtn.released.connect(self.resetbtnfunc)

        self.blueheader = QLabel("Bluetooth Player")
        self.blueheader.setStyleSheet("color: white; text-decoration: underline; font-size: 25px; border: none;")
        self.blueheader.setContentsMargins(0, 0, 0, 30)
        self.blueheader.setAlignment(Qt.AlignCenter)

        self.bluestaticlabel = QVBoxLayout()
        self.bluevarilabel = QVBoxLayout()
        self.bluelabellayout = QHBoxLayout()
        self.bluebtnlayout = QHBoxLayout()
        layout = QVBoxLayout()

        self.bluestaticlabel.setAlignment(Qt.AlignRight)
        self.bluevarilabel.setAlignment(Qt.AlignLeft)
        self.bluelabellayout.setAlignment(Qt.AlignCenter)
        self.bluebtnlayout.setAlignment(Qt.AlignHCenter)

        self.bluestaticlabel.addWidget(self.statictitle)
        self.bluestaticlabel.addWidget(self.staticartist)
        self.bluestaticlabel.addWidget(self.staticalbum)

        self.bluevarilabel.addWidget(self.titlelabel)
        self.bluevarilabel.addWidget(self.artistlabel)
        self.bluevarilabel.addWidget(self.albumlabel)

        self.bluebtnlayout.addWidget(self.prevbtn)
        self.bluebtnlayout.addWidget(self.pausebtn)
        self.bluebtnlayout.addWidget(self.playbtn)
        self.bluebtnlayout.addWidget(self.nextbtn)
        self.bluebtnlayout.addWidget(self.resetbtn)

        self.bluelabellayout.addLayout(self.bluestaticlabel)
        self.bluelabellayout.addLayout(self.bluevarilabel)
        layout.addWidget(self.blueheader)
        layout.addLayout(self.bluelabellayout)
        layout.addLayout(self.bluebtnlayout)

        layout.setAlignment(Qt.AlignCenter)

        self.setLayout(layout)

    def resetbtnfunc(self):
        self._manager = 0
        self._manager = AudioManager()
        self._manager.initialize()
        self._manager.infoChanged.connect(self.handle_info_changed)
        update_timer()

    def handle_info_changed(self, info):
        #print(info)
        self.titlelabel.setText(info["Title"])
        self.artistlabel.setText(info["Artist"])
        self.albumlabel.setText(info["Album"])

        #self.artistlabel.setText(f"""Artist: {info["Artist"]}""") keep as an example
        #print(f"""Track: {info["Title"]}""")


class MainMenu(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignLeft)

        self.channelstrip1 = ChannelStrip(1)
        self.channelstrip2 = ChannelStrip(2)
        self.channelstrip3 = ChannelStrip(3)
        self.channelstrip4 = ChannelStrip(4)
        self.bluetoothmenu = BluetoothMenu()

        layout.addWidget(self.channelstrip1)
        layout.addWidget(self.channelstrip2)
        layout.addWidget(self.channelstrip3)
        layout.addWidget(self.channelstrip4)
        layout.addWidget(self.bluetoothmenu)

        self.setLayout(layout)


class PasswordMenu(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.inputfield = QLineEdit()
        self.inputfield.setFixedHeight(80)
        self.inputfield.setFixedWidth(215)
        self.setStyleSheet("QLineEdit::disabled{background:white; font-size:40px; color: black; border: 3px solid black;}")
        self.inputfield.setFont(mainfont)
        self.inputfield.setAlignment(Qt.AlignCenter)
        self.inputfield.setContentsMargins(0, 0, 0, 10)
        self.inputfield.setDisabled(True)

        self.delbtn = QPushButton("Del")
        self.delbtn.setFixedWidth(70)
        self.delbtn.setFixedHeight(70)
        self.delbtn.setStyleSheet(enterdelbtns)
        self.delbtn.setFont(mainfont)

        self.enterbtn = QPushButton("Ent")
        self.enterbtn.setFixedWidth(70)
        self.enterbtn.setFixedHeight(70)
        self.enterbtn.setStyleSheet(enterdelbtns)
        self.enterbtn.setFont(mainfont)

        layout = QGridLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.column = 0
        self.row = 1

        for n in range(10):
            btn = QPushButton(str(n+1))
            btn.pressed.connect(lambda n=n: self.add_num(n+1))
            btn.pressed.connect(update_timer)
            btn.setStyleSheet(passwordkeys)
            btn.setFont(mainfont)
            btn.setFixedWidth(70)
            btn.setFixedHeight(70)

            if n+1 == 10:
                layout.addWidget(self.delbtn, 4, 0)
                layout.addWidget(btn, 4, 1)
                btn.setText("0")
                btn.setFont(mainfont)
            else:
                layout.addWidget(btn, self.row, self.column)
                self.column += 1
            if self.column == 3:
                self.row += 1
                self.column = 0

        self.numbers = []

        layout.addWidget(self.enterbtn, 4, 2)

        fieldlayout = QVBoxLayout()
        fieldlayout.addWidget(self.inputfield)
        fieldlayout.setAlignment(Qt.AlignHCenter)

        outerlayout = QVBoxLayout()
        outerlayout.addLayout(fieldlayout)
        outerlayout.addLayout(layout)
        outerlayout.setAlignment(Qt.AlignCenter)

        self.delbtn.pressed.connect(self.delete_num)
        self.delbtn.pressed.connect(update_timer)

        self.setLayout(outerlayout)

    def add_num(self, a):
        self.inputfield.setStyleSheet("font-size:40px")
        if (len(self.numbers)) < 4:
            if a != 10:
                self.numbers.append(a)
            else:
                self.numbers.append(0)
            self.x = ""
            for f in self.numbers:
                self.x += str(f)  # Change str(f) to "*" to hide pin. Pin test is handled in password_unlock func

            self.inputfield.setText(self.x)

    def delete_num(self):
        self.x = ""
        if not self.numbers:
            pass
        else:
            self.numbers.remove(self.numbers[-1])
            for f in self.numbers:
                self.x += str(f)
            self.inputfield.setText(self.x)

class BluetoothMenus(QStackedWidget):
    def __init__(self):
        QStackedWidget.__init__(self)

        #two menus required, one for displaying and connecting to a device, the 2nd to display a music control interface


class ActionWindow(QStackedWidget):
    def __init__(self):
        QStackedWidget.__init__(self)

        layout = QVBoxLayout()
        layout.setMargin(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        self.setFixedWidth(785)
        self.setFixedHeight(422)
        self.setStyleSheet("background: #082740; border: 1px solid white; margin: 0px; padding: 0px;")

        self.passwordmenu = PasswordMenu()
        self.mainmenu = MainMenu()
        self.networkmenu = NetworkMenu()
        self.bluetoothmenu = BluetoothMenu()
        self.addWidget(self.passwordmenu)
        self.addWidget(self.mainmenu)
        #self.addWidget(self.networkmenu)
        self.addWidget(self.bluetoothmenu)

        layout.addWidget(self)

        self.setLayout(layout)


class TabBar(QTabBar):
    def __init__(self):
        QTabBar.__init__(self)

        self.setFixedHeight(50)
        self.setStyleSheet(tabbar)

        self.setFont(mainfont)
        self.addTab("Main Menu")
        #self.addTab("Network")
        #self.addTab("Bluetooth")
        #self.addTab("")

        self.setContentsMargins(0, 0, 0, 0)


class MuteAll(QPushButton):
    def __init__(self):
        QPushButton.__init__(self)
        self.setText("Mute All")
        self.setFont(mainfont)
        self.setStyleSheet("""
            QPushButton::enabled {
            height: 50px; 
            width: 106px;
            background: #0d1f2d;
            color: white;
            font-size: 16px;
            border: none;
            border-left: 1px solid white;
            border-bottom: none;
            }
            QPushButton::pressed{
            background: #082740;
            }
            """)


class LogOut(QPushButton):
    def __init__(self):
        QPushButton.__init__(self)
        self.setText("Log Out")
        self.setFont(mainfont)
        self.setStyleSheet("""
            QPushButton::enabled {
            height: 50px; 
            width: 106px;
            background: #0d1f2d;
            color: white;
            font-size: 16px;
            border: none;
            border-left: 1px solid white;
            border-bottom: none;
            }
            QPushButton::pressed{
            background: #082740;
            }
            """)


class MenuLayout(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        # self.setFixedHeight(60)
        self.setFixedWidth(800)
        self.setStyleSheet("background: purple; border: 5px solid green; margin: 0px; spacing: 0px")


        self.tabs = TabBar()
        self.muteall = MuteAll()
        self.logout = LogOut()

        self.setStyleSheet("background: #0d1f2d; border: none; margin: 0px; spacing: 0px")
        #self.tabs.setStyleSheet("background: #0d1f2d; border: none; margin: 0px; spacing: 0px")

        tablayout = QHBoxLayout()
        tablayout.setContentsMargins(0, 0, 0, 0)
        tablayout.setSpacing(0)
        tablayout.setMargin(0)
        tablayout.setAlignment(Qt.AlignLeft)

        tablayout.addWidget(self.tabs)

        buttonlayout = QHBoxLayout()
        buttonlayout.setContentsMargins(0, 0, 0, 0)
        buttonlayout.setSpacing(0)
        buttonlayout.setMargin(0)
        buttonlayout.setAlignment(Qt.AlignRight)

        buttonlayout.addWidget(self.muteall)
        buttonlayout.addWidget(self.logout)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setMargin(0)

        layout.addLayout(tablayout)
        layout.addLayout(buttonlayout)

        self.setLayout(layout)


class MainWindow(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.setCursor(Qt.BlankCursor)
        self.showFullScreen()
        #self.setFixedWidth(800)
        #self.setFixedHeight(480)
        self.setStyleSheet("background: #0d1f2d;")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.add_timeout)
        self.timer.start(1000)
        self.x = 0

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setMargin(0)

        self.actionwindow = ActionWindow()
        self.menus = MenuLayout()

        menulayout = QVBoxLayout()
        menulayout.setContentsMargins(0, 0, 0, 0)
        menulayout.setSpacing(0)
        menulayout.setMargin(0)

        actionlayout = QVBoxLayout()
        actionlayout.setContentsMargins(7, 0, 0, 0)
        actionlayout.setSpacing(0)

        menulayout.addWidget(self.menus)
        actionlayout.addWidget(self.actionwindow)

        menulayout.setAlignment(Qt.AlignTop)
        actionlayout.setAlignment(Qt.AlignTop)

        layout.addLayout(menulayout)
        layout.addLayout(actionlayout)
        layout.setAlignment(Qt.AlignTop)

        self.menus.tabs.tabBarClicked.connect(self.tab_click)
        self.menus.tabs.tabBarClicked.connect(update_timer)
        self.menus.muteall.released.connect(self.mute_all)
        self.menus.muteall.released.connect(update_timer)
        self.actionwindow.passwordmenu.enterbtn.released.connect(self.password_unlock)
        self.actionwindow.passwordmenu.enterbtn.released.connect(update_timer)
        self.menus.logout.pressed.connect(self.log_out)
        self.menus.tabs.setDisabled(True)

        self.setLayout(layout)

    def log_out(self):
        self.actionwindow.setCurrentIndex(0)
        self.menus.tabs.setDisabled(True)

    def password_unlock(self):
        y = ""
        for g in self.actionwindow.passwordmenu.numbers:
            y += str(g)

        if y == "1234":
            self.actionwindow.setCurrentIndex(1)
            self.menus.tabs.setEnabled(True)
            self.actionwindow.passwordmenu.inputfield.setText("")
            self.actionwindow.passwordmenu.numbers = []
        else:
            self.actionwindow.passwordmenu.inputfield.setText("PIN INCORRECT")
            self.actionwindow.passwordmenu.inputfield.setStyleSheet("font-size: 20px")
            self.actionwindow.passwordmenu.numbers = []

    def mute_all(self):
        self.actionwindow.mainmenu.channelstrip1.mute_all()
        self.actionwindow.mainmenu.channelstrip2.mute_all()
        self.actionwindow.mainmenu.channelstrip3.mute_all()
        self.actionwindow.mainmenu.channelstrip4.mute_all()

    def tab_click(self, x):
        self.actionwindow.setCurrentIndex(x+1)

    def mousePressEvent(self, event):
        self.reset_timer()

    def add_timeout(self):          # auto logout timer
        self.x += 1
        #print(self.x)              # for test purposes
        if self.x == 900:           # number of seconds until timeout. 900s=15m
            self.ask_password()

    def reset_timer(self):
        self.x = 0

    def ask_password(self):
        self.actionwindow.setCurrentIndex(0)
        self.menus.tabs.setDisabled(True)
        self.actionwindow.bluetoothmenu.titlelabel.setText("")
        self.actionwindow.bluetoothmenu.artistlabel.setText("")
        self.actionwindow.bluetoothmenu.albumlabel.setText("")


def update_timer():
    window.reset_timer()

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

app = QApplication(sys.argv)


window = MainWindow()
window.show()
app.exec_()
