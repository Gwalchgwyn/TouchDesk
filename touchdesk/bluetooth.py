"""Bluetooth media controls (play/pause/skip and track info) via BlueZ.

TouchDesk 1.x crashed on start-up if no phone was connected. This version
simply checks every second for a connected player and shows "no device"
until one appears, so Bluetooth can never stop the mixer from working.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from pathlib import Path

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
    art_path = ""  # album artwork image file, "" if none

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
        self._art = CoverArt()

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
            art_req = None
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
                    port = player.get("ObexPort")
                    dev_obj = objects.get(player.get("Device", ""), {}).get("org.bluez.Device1", {})
                    if port and dev_obj.get("Address"):
                        art_req = (str(dev_obj["Address"]), int(port), str(raw.get("ImgHandle", "")))
            self._art.update(art_req)
            self._last_error = ""
        except Exception as e:  # bluetoothd not running, permissions, etc.
            msg = str(e)
            if msg != self._last_error:
                log.warning("Bluetooth unavailable: %s", msg)
                self._last_error = msg
            self._bus = None
            device_name, player_path, status, track = "", None, "", {}
            self._art.update(None)
        new = (device_name, player_path, status, track, self._art.path)
        old = (self.device_name, self._player_path, self.status, self.track, self.art_path)
        if new != old:
            self.device_name, self._player_path, self.status, self.track, self.art_path = new
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


class CoverArt:
    """Fetches album artwork from the phone over Bluetooth (AVRCP 1.6 cover art).

    No internet involved. BlueZ marks this "experimental", so bluetoothd must
    run with experimental features on (bluetooth-setup.sh does that), and many
    phones/apps don't send artwork at all - in which case nothing happens.

    How it works: when the phone's player advertises an ObexPort, we open an
    OBEX "bip-avrcp" session to it. The phone then includes an ImgHandle in
    each track's details, and we ask obexd for that image's thumbnail.
    The slow D-Bus calls run on a background thread so the screen never stalls.
    """

    RETRY_AFTER_S = 30

    def __init__(self, folder: Path | None = None):
        self.folder = folder or Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / "touchdesk-art"
        self.path = ""  # latest finished image (read by the UI thread)
        self._target = None  # (address, port) we have/are opening a session to
        self._session = None
        self._handle = ""  # image handle currently shown or being fetched
        self._busy = False
        self._failed_at = 0.0
        self._lock = threading.Lock()

    # called from the UI thread every poll
    def update(self, req) -> None:
        with self._lock:
            if self._busy:
                return
            if req is None:
                if self._target:
                    self._start(self._close, self._session)
                    self._target = self._session = None
                self._handle, self.path = "", ""
                return
            address, port, handle = req
            if (address, port) != self._target:
                if self._session:
                    self._start(self._close, self._session)
                if time.monotonic() - self._failed_at < self.RETRY_AFTER_S:
                    return
                self._target, self._session = (address, port), None
                self._handle, self.path = "", ""
                self._start(self._open, address, port)
            elif self._session and handle and handle != self._handle:
                self._handle = handle
                self._start(self._fetch, self._session, handle)
            elif not handle and self._handle:
                self._handle, self.path = "", ""

    def _start(self, fn, *args) -> None:
        self._busy = True

        def run():
            try:
                fn(*args)
            except Exception as e:
                log.info("Album artwork not available: %s", e)
                with self._lock:
                    if fn is self._open:
                        self._failed_at = time.monotonic()
                        self._target = None
            finally:
                with self._lock:
                    self._busy = False

        threading.Thread(target=run, daemon=True).start()

    def _client(self):
        bus = dbus.SessionBus(private=True)
        return bus, dbus.Interface(bus.get_object("org.bluez.obex", "/org/bluez/obex"), "org.bluez.obex.Client1")

    def _open(self, address: str, port: int) -> None:
        bus, client = self._client()
        session = client.CreateSession(address, {"Target": "bip-avrcp", "PSM": dbus.UInt16(port)}, timeout=15)
        with self._lock:
            self._session = str(session)
        log.info("Album artwork connection open to %s", address)

    def _close(self, session) -> None:
        if session:
            bus, client = self._client()
            client.RemoveSession(session, timeout=5)

    def _fetch(self, session: str, handle: str) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.folder / f"{''.join(c for c in handle if c.isalnum())}.jpg"
        if not target.exists():
            bus = dbus.SessionBus(private=True)
            image = dbus.Interface(bus.get_object("org.bluez.obex", session), "org.bluez.obex.Image1")
            transfer, _ = image.GetThumbnail(str(target), handle, timeout=10)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    props = dbus.Interface(bus.get_object("org.bluez.obex", transfer), "org.freedesktop.DBus.Properties")
                    status = str(props.Get("org.bluez.obex.Transfer1", "Status", timeout=2))
                except Exception:
                    status = "complete" if target.exists() else "gone"
                if status in ("complete", "error", "gone"):
                    break
                time.sleep(0.2)
        if target.exists() and target.stat().st_size > 0:
            with self._lock:
                if self._handle == handle:
                    self.path = str(target)
            for old in self.folder.glob("*.jpg"):  # keep only the latest few
                if old != target and time.time() - old.stat().st_mtime > 600:
                    old.unlink(missing_ok=True)


def create_backend(enabled: bool, parent: QObject | None = None) -> BluetoothBackend | None:
    """None = Bluetooth switched off in settings (panel hidden)."""
    if not enabled:
        return None
    if dbus is None:
        log.warning("python3-dbus isn't installed - Bluetooth controls disabled")
        return BluetoothBackend(parent)
    return BlueZBackend(parent)
