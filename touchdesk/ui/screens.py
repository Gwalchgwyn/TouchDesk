"""The screens: lock, mixer, Bluetooth and installer settings."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from touchdesk import __version__
from touchdesk.bluetooth import BluetoothBackend
from touchdesk.config import Config
from touchdesk.session import DeskSession
from touchdesk.ui.widgets import ArtView, ChannelStrip, IconButton, PinPad


# ------------------------------------------------------------------ lock
class LockScreen(QWidget):
    """PIN entry with a cool-down after too many wrong guesses."""

    unlocked = Signal()
    admin = Signal()
    touched = Signal()

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.failures = 0
        self.locked_until = 0.0
        self.pad = PinPad("Enter PIN")
        self.pad.submitted.connect(self._check)
        self.pad.touched.connect(self.touched)
        self.back = QPushButton("Back")
        self.back.setObjectName("AdminButton")
        self.back.hide()
        lay = QVBoxLayout(self)
        lay.addWidget(self.pad, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.back)
        lay.addLayout(row)
        self._tick = QTimer(self, interval=250)
        self._tick.timeout.connect(self._countdown)

    def reset(self) -> None:
        self.pad.clear()

    def _check(self, pin: str) -> None:
        sec = self.config.security
        if time.monotonic() < self.locked_until:
            return
        if pin == sec["admin_pin"]:
            self.failures = 0
            self.pad.clear()
            self.admin.emit()
        elif pin == sec["pin"]:
            self.failures = 0
            self.pad.clear()
            self.unlocked.emit()
        else:
            self.failures += 1
            left = int(sec["max_attempts"]) - self.failures
            if left <= 0:
                self.failures = 0
                self.locked_until = time.monotonic() + int(sec["lockout_seconds"])
                self.pad.set_locked(True)
                self._countdown()
                self._tick.start()
            else:
                self.pad.clear(f"Wrong PIN - {left} {'try' if left == 1 else 'tries'} left")

    def _countdown(self) -> None:
        remaining = math.ceil(self.locked_until - time.monotonic())
        if remaining <= 0:
            self._tick.stop()
            self.pad.set_locked(False)
            self.pad.clear("")
        else:
            self.pad.clear(f"Too many wrong PINs. Try again in {remaining} s")


# ------------------------------------------------------------------ bluetooth
class BluetoothPanel(QWidget):
    touched = Signal()

    def __init__(self, backend: BluetoothBackend, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self.bt = backend
        header = QLabel("Bluetooth Player")
        header.setObjectName("BtHeader")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device = QLabel("")
        self.device.setObjectName("BtDevice")
        self.device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device.setWordWrap(True)

        self.art = ArtView(round(110 * scale))
        info = QVBoxLayout()
        info.setSpacing(2)
        self.values = {}
        for key, name in (("Title", "BtTitle"), ("Artist", "BtValue"), ("Album", "BtField")):
            v = QLabel("")
            v.setObjectName(name)
            v.setMinimumWidth(10)
            info.addWidget(v)
            self.values[key] = v
        info.addStretch(1)
        now_playing = QHBoxLayout()
        now_playing.setSpacing(14)
        now_playing.addWidget(self.art, 0, Qt.AlignmentFlag.AlignTop)
        now_playing.addLayout(info, 1)

        self.prev = IconButton("prev")
        self.playpause = IconButton("play")
        self.next = IconButton("next")
        self.prev.clicked.connect(self.bt.previous)
        self.playpause.clicked.connect(self.bt.toggle)
        self.next.clicked.connect(self.bt.next)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for b in (self.prev, self.playpause, self.next):
            b.pressed.connect(self.touched)
            buttons.addWidget(b)
        buttons.addStretch(1)

        inner = QWidget()
        inner.setMaximumWidth(520)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(16, 12, 16, 12)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(inner)
        lay.addStretch(1)
        lay.addWidget(header)
        lay.addWidget(self.device)
        lay.addSpacing(14)
        lay.addLayout(now_playing)
        lay.addSpacing(16)
        lay.addLayout(buttons)
        lay.addStretch(1)

        self.bt.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        bt = self.bt
        if not bt.available:
            self.device.setText("Bluetooth isn't available on this unit")
        elif bt.device_name:
            self.device.setText(f"Connected: {bt.device_name}")
        else:
            self.device.setText("No device connected.\nPair your phone with this unit to play music.")
        self.art.set_image(bt.art_path if bt.has_player else "")
        for key, lbl in self.values.items():
            text = (bt.track or {}).get(key, "") if bt.has_player else ""
            if key == "Title" and bt.has_player and not text:
                text = "Nothing playing"
            w = max(lbl.width(), 120)
            lbl.setText(lbl.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, w))
            lbl.setToolTip(text)
        for b in (self.prev, self.playpause, self.next):
            b.setEnabled(bt.has_player)
        self.playpause.set_kind("pause" if bt.status == "playing" else "play")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.refresh()


# ------------------------------------------------------------------ mixer
class MixerScreen(QWidget):
    touched = Signal()

    def __init__(self, config: Config, session: DeskSession, bt_panel: BluetoothPanel | None, parent=None):
        super().__init__(parent)
        self.config = config
        self.session = session
        self.strips: list[ChannelStrip] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        n = len(config.channels)
        for i, ch in enumerate(config.channels):
            s = ChannelStrip(i, ch.label, ch.icon)
            s.moved.connect(session.set_position)
            s.toggled.connect(session.set_on)
            s.touched.connect(self.touched)
            self.strips.append(s)
            lay.addWidget(s, 1)
        if bt_panel is not None:
            # TouchDesk 1.x layout: strips on the left, player on the right.
            lay.addWidget(bt_panel, 8 - n)
        else:
            lay.addStretch(8 - n)

        self.banner = QLabel(self)
        self.banner.setObjectName("Banner")
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setWordWrap(True)

        session.channel_changed.connect(self.update_strip)
        session.connection_changed.connect(self.update_connection)
        self.apply_settings()
        self.update_connection(session.online)

    def apply_settings(self) -> None:
        for i, s in enumerate(self.strips):
            s.level_display = self.config.data["level_display"]
            self.update_strip(i)

    def update_strip(self, i: int) -> None:
        st = self.session.channels[i]
        name = st.desk_name if self.config.data["use_desk_names"] and st.desk_name else ""
        self.strips[i].show_state(self.session.position(i), st.level, st.on, name)

    def update_connection(self, online: bool) -> None:
        for s in self.strips:
            s.setEnabled(online)
        if online:
            self.banner.hide()
        else:
            where = "Searching the network for the sound desk…" if self.session.host is None else "Can't reach the sound desk. Trying again…"
            self.banner.setText(where + "\nCheck the desk is switched on and the network cable is plugged in.")
            self.banner.show()
            self._place_banner()

    def _place_banner(self) -> None:
        n = len(self.strips)
        w = self.width() * n / 8  # the strips take n/8 of the width
        bw = min(int(w) - 20, 520)
        bw = max(bw, 200)
        b = self.banner
        b.ensurePolished()
        b.setFixedWidth(bw)
        # Size to the wrapped text ourselves: QLabel.heightForWidth ignores the
        # stylesheet padding, which clipped the text on the Pi's own fonts.
        chrome = max(0, bw - b.contentsRect().width())  # padding + border, both sides
        text_h = b.fontMetrics().boundingRect(
            QRect(0, 0, bw - chrome, 10_000),
            int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignCenter),
            b.text(),
        ).height()
        b.setFixedHeight(text_h + chrome + 4)
        self.banner.move(int((w - self.banner.width()) / 2), int((self.height() - self.banner.height()) / 2))
        self.banner.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # isHidden, not isVisible: before the window is shown, isVisible is
        # always False and the banner would keep its pre-layout size.
        if not self.banner.isHidden():
            self._place_banner()

    def showEvent(self, e):
        super().showEvent(e)
        if not self.banner.isHidden():
            self._place_banner()


# ------------------------------------------------------------------ admin
def local_addresses() -> list[str]:
    out = []
    for a in QNetworkInterface.allAddresses():
        if a.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol and not a.isLoopback():
            out.append(a.toString())
    return out


def power_status() -> str:
    """The Pi's own record of power problems since it was switched on.

    Uses the firmware's 'throttled' flags (vcgencmd get_throttled). Returns ""
    when not on a Raspberry Pi.
    """
    import shutil
    import subprocess

    exe = shutil.which("vcgencmd")
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, "get_throttled"], capture_output=True, text=True, timeout=2).stdout
        flags = int(out.strip().split("=")[-1], 16)
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    if flags & 0x1:
        return "<span style='color:#ff4d4d'>LOW VOLTAGE NOW - check the power supply</span>"
    if flags & 0x10000:
        return "<span style='color:#f0a020'>Low voltage detected since power-on</span>"
    if flags & 0x40004:
        return "<span style='color:#f0a020'>Slowed down by heat or power since power-on</span>"
    return "OK"


class AdminScreen(QWidget):
    """Installer settings, reached with the admin PIN."""

    closed = Signal()
    settings_changed = Signal()
    exit_requested = Signal()
    touched = Signal()

    LOCK_CHOICES = [5, 15, 30, 60, 0]

    def __init__(self, config: Config, session: DeskSession, bt: BluetoothBackend | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.session = session
        self.bt = bt
        self._forget_armed = False
        self.pages = QStackedWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.pages)

        self.pages.addWidget(self._build_menu())
        self.pages.addWidget(self._build_finder())
        self.pin_page = self._build_pin_page()
        self.pages.addWidget(self.pin_page)

        session.info_changed.connect(lambda _: self.refresh())
        session.connection_changed.connect(lambda _: self.refresh())
        session.desks_found.connect(self._show_found)
        self.refresh()

    # -- helpers
    def _button(self, text: str, fn, primary=False) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("AdminButton")
        if primary:
            b.setProperty("primary", "true")
        b.clicked.connect(fn)
        b.pressed.connect(self.touched)
        return b

    def _save(self) -> None:
        self.config.save()
        self.settings_changed.emit()
        self.refresh()

    # -- main menu
    def _build_menu(self) -> QWidget:
        page = QWidget()
        title = QLabel("Installer settings")
        title.setObjectName("AdminTitle")
        self.info = QLabel()
        self.info.setObjectName("AdminInfo")
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.b_find = self._button("Find desk", self._find)
        self.b_lock = self._button("", self._toggle_lock)
        self.b_timeout = self._button("", self._cycle_timeout)
        self.b_levels = self._button("", self._toggle_levels)
        self.b_names = self._button("", self._toggle_names)
        self.b_pin = self._button("Change user PIN", lambda: self._change_pin("pin"))
        self.b_admin_pin = self._button("Change installer PIN", lambda: self._change_pin("admin_pin"))
        self.b_forget = self._button("", self._forget)
        self.b_exit = self._button("Exit to desktop", self.exit_requested.emit)
        self.b_done = self._button("Done", self.closed.emit, primary=True)

        grid = QGridLayout()
        grid.setSpacing(8)
        buttons = [self.b_find, self.b_lock, self.b_timeout, self.b_levels, self.b_names,
                   self.b_pin, self.b_admin_pin, self.b_forget, self.b_exit]
        for i, b in enumerate(buttons):
            grid.addWidget(b, i // 2, i % 2)
        grid.addWidget(self.b_done, 4, 1)
        self.b_forget.setVisible(self.bt is not None and self.bt.available)
        if self.bt is not None:
            self.bt.changed.connect(self.refresh)

        left = QVBoxLayout()
        left.addWidget(title)
        left.addSpacing(6)
        left.addWidget(self.info, 1)
        lay = QHBoxLayout(page)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.addLayout(left, 4)
        lay.addSpacing(12)
        lay.addLayout(grid, 6)
        return page

    def refresh(self) -> None:
        c, s = self.config, self.session
        info = s.info or {}
        desk = info.get("model") or s.profile.label
        if info.get("name"):
            desk += f" “{info['name']}”"
        status = "connected" if s.online else ("searching…" if s.host is None else "not responding")
        mode = "found automatically" if c.desk_ip.lower() == "auto" else "fixed address"
        lines = [
            f"<b>Desk:</b> {desk}",
            f"<b>Address:</b> {s.host or '—'}:{s.port} ({mode})",
            f"<b>Status:</b> {status}",
        ]
        if info.get("firmware"):
            lines.append(f"<b>Desk firmware:</b> {info['firmware']}")
        lines += [
            f"<b>This unit:</b> {', '.join(local_addresses()) or 'no network'}",
            *( [f"<b>Power:</b> {p}"] if (p := power_status()) else [] ),
            f"<b>TouchDesk:</b> {__version__}",
            f"<b>Settings file:</b> {c.path or '—'}",
        ]
        self.info.setText("<br>".join(lines))
        sec = c.security
        self.b_lock.setText(f"PIN lock: {'On' if sec['pin_enabled'] else 'Off'}")
        mins = int(sec["lock_after_minutes"])
        self.b_timeout.setText(f"Auto-lock: {f'{mins} min' if mins else 'Never'}")
        self.b_timeout.setEnabled(bool(sec["pin_enabled"]))
        self.b_levels.setText("Levels shown as: " + ("dB" if c.data["level_display"] == "db" else "0–10"))
        self.b_names.setText("Names from: " + ("the desk" if c.data["use_desk_names"] else "settings"))
        if self.bt is not None:
            n = self.bt.remembered
            if self._forget_armed:
                self.b_forget.setText(f"Tap again to forget {n}")
            else:
                self.b_forget.setText(f"Forget phones ({n})")
            self.b_forget.setEnabled(n > 0 or self._forget_armed)

    def _forget(self) -> None:
        """Two taps: the first asks for confirmation, the second forgets every phone."""
        if not self._forget_armed:
            self._forget_armed = True
            QTimer.singleShot(5000, self._disarm_forget)
        else:
            self._forget_armed = False
            n = self.bt.forget_all() if self.bt else 0
            self.b_forget.setText(f"Forgot {n} phone{'s' if n != 1 else ''}")
            QTimer.singleShot(2500, self.refresh)
            return
        self.refresh()

    def _disarm_forget(self) -> None:
        if self._forget_armed:
            self._forget_armed = False
            self.refresh()

    def _toggle_lock(self) -> None:
        self.config.security["pin_enabled"] = not self.config.security["pin_enabled"]
        self._save()

    def _cycle_timeout(self) -> None:
        cur = int(self.config.security["lock_after_minutes"])
        ch = self.LOCK_CHOICES
        self.config.security["lock_after_minutes"] = ch[(ch.index(cur) + 1) % len(ch)] if cur in ch else ch[0]
        self._save()

    def _toggle_levels(self) -> None:
        d = self.config.data
        d["level_display"] = "0-10" if d["level_display"] == "db" else "db"
        self._save()

    def _toggle_names(self) -> None:
        d = self.config.data
        d["use_desk_names"] = not d["use_desk_names"]
        self._save()

    # -- desk finder
    def _build_finder(self) -> QWidget:
        page = QWidget()
        self.finder_title = QLabel("Searching for desks…")
        self.finder_title.setObjectName("AdminTitle")
        self.finder_list = QVBoxLayout()
        self.finder_list.setSpacing(8)
        back = self._button("Back", lambda: self.pages.setCurrentIndex(0))
        again = self._button("Search again", self._find)
        auto = self._button("Always search automatically", self._use_auto)
        row = QHBoxLayout()
        row.addWidget(back)
        row.addWidget(again)
        row.addWidget(auto)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.addWidget(self.finder_title)
        lay.addLayout(self.finder_list)
        lay.addStretch(1)
        lay.addLayout(row)
        return page

    def _find(self) -> None:
        self._clear_found()
        self.finder_title.setText("Searching for desks…")
        self.pages.setCurrentIndex(1)
        self.session.find_desks()

    def _clear_found(self) -> None:
        while self.finder_list.count():
            w = self.finder_list.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _show_found(self, desks: list) -> None:
        self._clear_found()
        if not desks:
            self.finder_title.setText("No desks answered. Check the desk is on and on the same network.")
            return
        self.finder_title.setText("Tap a desk to use it:")
        for d in desks[:5]:
            label = f"{d.get('model') or 'Desk'}  {d.get('name', '')}  —  {d.get('ip')}"
            self.finder_list.addWidget(self._button(label, lambda _=False, ip=d.get("ip"): self._use(ip)))

    def _use(self, ip: str) -> None:
        self.config.data["desk"]["ip"] = ip
        self.session.use_desk(ip)
        self._save()
        self.pages.setCurrentIndex(0)

    def _use_auto(self) -> None:
        self.config.data["desk"]["ip"] = "auto"
        self._save()
        self.pages.setCurrentIndex(0)
        self.session.auto = True

    # -- PIN change
    def _build_pin_page(self) -> QWidget:
        page = QWidget()
        self.pin_pad = PinPad("New PIN")
        self.pin_pad.submitted.connect(self._pin_entered)
        self.pin_pad.touched.connect(self.touched)
        cancel = self._button("Cancel", lambda: self.pages.setCurrentIndex(0))
        lay = QVBoxLayout(page)
        lay.addWidget(self.pin_pad, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(cancel)
        lay.addLayout(row)
        return page

    def _change_pin(self, key: str) -> None:
        self._pin_key, self._pin_first = key, None
        who = "user" if key == "pin" else "installer"
        self.pin_pad.prompt.setText(f"New {who} PIN (4–8 digits)")
        self.pin_pad.clear()
        self.pages.setCurrentIndex(2)

    def _pin_entered(self, pin: str) -> None:
        other = self.config.security["admin_pin" if self._pin_key == "pin" else "pin"]
        if self._pin_first is None:
            if not 4 <= len(pin) <= 8:
                self.pin_pad.clear("PIN must be 4 to 8 digits")
            elif pin == other:
                self.pin_pad.clear("User and installer PINs must be different")
            else:
                self._pin_first = pin
                self.pin_pad.prompt.setText("Enter it again to confirm")
                self.pin_pad.clear()
        elif pin != self._pin_first:
            self._pin_first = None
            self.pin_pad.prompt.setText("New PIN (4–8 digits)")
            self.pin_pad.clear("They didn't match - start again")
        else:
            self.config.security[self._pin_key] = pin
            self._save()
            self.pages.setCurrentIndex(0)
