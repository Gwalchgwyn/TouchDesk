"""Bluetooth media controls (play/pause/skip and track info) via BlueZ.

TouchDesk 1.x crashed on start-up if no phone was connected. This version
simply checks every second for a connected player and shows "no device"
until one appears, so Bluetooth can never stop the mixer from working.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger(__name__)

POLL_MS = 1000
DBUS_TIMEOUT_S = 1.0

try:  # dbus-python only exists on the Pi (python3-dbus)
    import dbus  # type: ignore
except Exception:  # pragma: no cover - depends on the machine
    dbus = None


class BluetoothBackend(QObject):
    """Interface the UI talks to. The base class is 'Bluetooth not available'."""

    changed = Signal()

    available = False
    device_name = ""  # connected phone/tablet, "" if none
    has_player = False
    status = ""  # "playing", "paused", "stopped", ...
    track: dict = {}

    def start(self) -> None:
        pass

    def play(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def next(self) -> None:
        pass

    def previous(self) -> None:
        pass

    def toggle(self) -> None:
        if self.status == "playing":
            self.pause()
        else:
            self.play()


class BlueZBackend(BluetoothBackend):
    available = True

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.track = {}
        self._bus = None
        self._player_path: str | None = None
        self._timer = QTimer(self, interval=POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._last_error = ""

    def start(self) -> None:
        self._poll()
        self._timer.start()

    def _get_bus(self):
        if self._bus is None:
            self._bus = dbus.SystemBus()
        return self._bus

    def _poll(self) -> None:
        try:
            bus = self._get_bus()
            mgr = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
            objects = mgr.GetManagedObjects(timeout=DBUS_TIMEOUT_S)
            device_name, player_path, status, track = "", None, "", {}
            for path, ifaces in objects.items():
                dev = ifaces.get("org.bluez.Device1")
                if dev and bool(dev.get("Connected", False)):
                    device_name = str(dev.get("Alias") or dev.get("Name") or "Device")
                player = ifaces.get("org.bluez.MediaPlayer1")
                if player is not None:
                    player_path = str(path)
                    status = str(player.get("Status", ""))
                    raw = player.get("Track", {}) or {}
                    track = {k: str(raw.get(k, "")) for k in ("Title", "Artist", "Album")}
            self._last_error = ""
        except Exception as e:  # bluetoothd not running, permissions, etc.
            msg = str(e)
            if msg != self._last_error:
                log.warning("Bluetooth unavailable: %s", msg)
                self._last_error = msg
            self._bus = None
            device_name, player_path, status, track = "", None, "", {}
        new = (device_name, player_path, status, track)
        old = (self.device_name, self._player_path, self.status, self.track)
        if new != old:
            self.device_name, self._player_path, self.status, self.track = new
            self.has_player = player_path is not None
            self.changed.emit()

    def _call(self, method: str) -> None:
        if not self._player_path:
            return
        try:
            obj = self._get_bus().get_object("org.bluez", self._player_path)
            getattr(dbus.Interface(obj, "org.bluez.MediaPlayer1"), method)(timeout=DBUS_TIMEOUT_S)
        except Exception as e:
            log.warning("Bluetooth %s failed: %s", method, e)
        QTimer.singleShot(300, self._poll)

    def play(self) -> None:
        self._call("Play")

    def pause(self) -> None:
        self._call("Pause")

    def next(self) -> None:
        self._call("Next")

    def previous(self) -> None:
        self._call("Previous")


def create_backend(enabled: bool, parent: QObject | None = None) -> BluetoothBackend | None:
    """None = Bluetooth switched off in settings (panel hidden)."""
    if not enabled:
        return None
    if dbus is None:
        log.warning("python3-dbus isn't installed - Bluetooth controls disabled")
        return BluetoothBackend(parent)
    return BlueZBackend(parent)
