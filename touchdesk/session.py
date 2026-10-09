"""Keeps TouchDesk and the desk in step, in both directions.

* Finds the desk (fixed IP, or by searching the network).
* Notices when the desk goes away and comes back, and re-reads everything
  when it returns, so the screen always shows what the desk is really doing.
* Subscribes to change notifications, so moves made on the desk, in the
  Behringer app or anywhere else show up on the touchscreen.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface

from touchdesk.config import Config
from touchdesk.desks import get_profile
from touchdesk.desks.faderlaw import db_to_float
from touchdesk.osc import OscSocket

log = logging.getLogger(__name__)

PROBE_INTERVAL_MS = 2500  # how often we check the desk is still there
OFFLINE_AFTER_S = 8.0  # silence for this long = desk is offline
SEARCH_INTERVAL_MS = 3000
RESEARCH_AFTER_S = 20.0  # in "auto" mode, search again if offline this long
ECHO_GUARD_S = 0.5  # ignore desk fader reports this soon after we moved it


def broadcast_addresses() -> list[str]:
    """Directed broadcast address of every active IPv4 network connection."""
    out = []
    flags = QNetworkInterface.InterfaceFlag
    for iface in QNetworkInterface.allInterfaces():
        f = iface.flags()
        if not (f & flags.IsUp and f & flags.IsRunning and f & flags.CanBroadcast) or f & flags.IsLoopBack:
            continue
        for entry in iface.addressEntries():
            ip, bc = entry.ip(), entry.broadcast()
            if ip.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol and not bc.isNull():
                if bc.toString() not in out:
                    out.append(bc.toString())
    return out


@dataclass
class ChannelState:
    level: float | None = None  # desk fader float 0.0-1.0
    on: bool | None = None  # True = unmuted
    desk_name: str = ""
    last_local_move: float = 0.0


class DeskSession(QObject):
    channel_changed = Signal(int)
    connection_changed = Signal(bool)
    info_changed = Signal(dict)
    desks_found = Signal(list)  # results of find_desks()

    def __init__(self, config: Config, parent: QObject | None = None, osc: OscSocket | None = None):
        super().__init__(parent)
        self.config = config
        self.profile = get_profile(config.desk_model)
        self.port = config.desk_port
        self.channels = [ChannelState() for _ in config.channels]
        self.max_float = db_to_float(float(config.data["max_level_db"]))
        self.info: dict = {}
        self.online = False
        self.host: str | None = None if config.desk_ip.lower() == "auto" else config.desk_ip
        self.auto = self.host is None
        self._last_heard = 0.0
        self._offline_since = time.monotonic()
        self._scan_results: dict[str, dict] = {}
        self._scanning = False

        self.osc = osc or OscSocket(self)
        self.osc.message.connect(self._on_message)
        self._build_routes()

        self._probe_timer = QTimer(self, interval=PROBE_INTERVAL_MS)
        self._probe_timer.timeout.connect(self._probe)
        self._keepalive_timer = QTimer(self, interval=self.profile.keepalive_seconds * 1000)
        self._keepalive_timer.timeout.connect(self._subscribe)
        self._search_timer = QTimer(self, interval=SEARCH_INTERVAL_MS)
        self._search_timer.timeout.connect(self._search)

    # ------------------------------------------------------------------ setup
    def _build_routes(self) -> None:
        self._routes: dict[str, list[tuple[int, str]]] = {}
        for i, ch in enumerate(self.config.channels):
            t = ch.target
            for field, addr in (
                ("level", self.profile.fader_address(t)),
                ("on", self.profile.on_address(t)),
                ("name", self.profile.name_address(t)),
            ):
                self._routes.setdefault(addr, []).append((i, field))

    def start(self) -> None:
        if self.auto:
            log.info("Searching the network for a %s desk", self.profile.label)
            self._search()
            self._search_timer.start()
        else:
            log.info("Connecting to desk at %s:%s", self.host, self.port)
        self._probe()
        self._probe_timer.start()

    def stop(self) -> None:
        for t in (self._probe_timer, self._keepalive_timer, self._search_timer):
            t.stop()

    # -------------------------------------------------------------- liveness
    def _probe(self) -> None:
        now = time.monotonic()
        if self.online and now - self._last_heard > OFFLINE_AFTER_S:
            self._set_online(False)
        if not self.online and self.auto and self.host and now - self._offline_since > RESEARCH_AFTER_S:
            log.info("Desk at %s hasn't answered for a while - searching again", self.host)
            self.host = None
            self._search_timer.start()
        if self.host:
            addr, args = self.profile.probe_message()
            self.osc.send(self.host, self.port, addr, args)

    def _search(self) -> None:
        """Ask every desk on the network to identify itself.

        Sent to 255.255.255.255 and also to each network connection's own
        broadcast address: on a network with no router (e.g. just a switch,
        everything on 169.254.x.x addresses) there's no default route and the
        plain 255.255.255.255 broadcast may go nowhere.
        """
        addr, args = self.profile.probe_message()
        for dest in ["broadcast", *broadcast_addresses()]:
            self.osc.send(dest, self.port, addr, args)

    def _subscribe(self) -> None:
        if self.host:
            for addr, args in self.profile.subscribe_messages():
                self.osc.send(self.host, self.port, addr, args)

    def _set_online(self, online: bool) -> None:
        if online == self.online:
            return
        self.online = online
        if online:
            log.info("Desk is online at %s", self.host)
            self._search_timer.stop()
            self._subscribe()
            self._keepalive_timer.start()
            self.refresh()
        else:
            log.warning("Lost contact with the desk at %s", self.host)
            self._offline_since = time.monotonic()
            self._keepalive_timer.stop()
        self.connection_changed.emit(online)

    def refresh(self) -> None:
        """Ask the desk for the current value of everything we show."""
        if not self.host:
            return
        for addr in self._routes:
            self.osc.send(self.host, self.port, addr, [])

    # -------------------------------------------------------------- incoming
    def _on_message(self, address: str, args: list, sender: str) -> None:
        if address == self.profile.probe_reply_address():
            info = self.profile.parse_info(args)
            info["ip"] = info.get("ip") or sender
            if self._scanning:
                self._scan_results[sender] = info
            if self.host is None and self._accept(info):
                self.host = sender
                log.info("Found %s '%s' at %s", info.get("model") or "desk", info.get("name"), sender)
        if sender != self.host:
            return
        self._last_heard = time.monotonic()
        if address == self.profile.probe_reply_address():
            info = self.profile.parse_info(args)
            info["ip"] = sender
            if info != self.info:
                self.info = info
                self.info_changed.emit(info)
        if not self.online:
            self._set_online(True)
        for idx, field in self._routes.get(address.rstrip("/"), ()):
            if not args:
                continue
            self._apply(idx, field, args[0])

    def _accept(self, info: dict) -> bool:
        wanted = str(self.config.data["desk"].get("name") or "").strip()
        return not wanted or info.get("name", "").lower() == wanted.lower()

    def _apply(self, idx: int, field: str, value) -> None:
        ch = self.channels[idx]
        try:
            if field == "level":
                # OSC floats are 32-bit; round away the noise (0.1 -> 0.10000000149).
                v = round(min(max(float(value), 0.0), 1.0), 4)
                if time.monotonic() - ch.last_local_move < ECHO_GUARD_S:
                    return
                if ch.level == v:
                    return
                ch.level = v
            elif field == "on":
                v = bool(int(value))
                if ch.on == v:
                    return
                ch.on = v
            elif field == "name":
                v = str(value).strip()
                if ch.desk_name == v:
                    return
                ch.desk_name = v
        except (TypeError, ValueError):
            log.debug("Ignoring odd value %r for channel %s %s", value, idx, field)
            return
        self.channel_changed.emit(idx)

    # ------------------------------------------------------------- outgoing
    def set_position(self, idx: int, position: float) -> None:
        """Move a fader. position is 0.0-1.0 of the on-screen fader travel."""
        position = min(max(position, 0.0), 1.0)
        ch = self.channels[idx]
        level = round(position * self.max_float, 4)
        ch.last_local_move = time.monotonic()
        if ch.level == level:
            return
        ch.level = level
        self._send(self.profile.fader_address(self.config.channels[idx].target), [level])
        self.channel_changed.emit(idx)

    def position(self, idx: int) -> float:
        """Where the on-screen fader should sit (0.0-1.0) for the desk's level."""
        level = self.channels[idx].level or 0.0
        return min(level / self.max_float, 1.0) if self.max_float > 0 else 0.0

    def set_on(self, idx: int, on: bool) -> None:
        ch = self.channels[idx]
        ch.on = on
        self._send(self.profile.on_address(self.config.channels[idx].target), [1 if on else 0])
        self.channel_changed.emit(idx)

    def mute_all(self) -> None:
        for i in range(len(self.channels)):
            self.set_on(i, False)

    def _send(self, address: str, args: list) -> None:
        if self.host:
            self.osc.send(self.host, self.port, address, args)

    # ------------------------------------------------------------ discovery
    def find_desks(self, wait_ms: int = 2500) -> None:
        """Broadcast a search; emits desks_found with every desk that answered."""
        self._scan_results = {}
        self._scanning = True
        self._search()
        QTimer.singleShot(wait_ms // 2, self._search)
        QTimer.singleShot(wait_ms, self._finish_scan)

    def _finish_scan(self) -> None:
        self._scanning = False
        self.desks_found.emit(sorted(self._scan_results.values(), key=lambda d: d.get("ip", "")))

    def use_desk(self, ip: str) -> None:
        """Switch to a different desk (e.g. picked in the installer settings)."""
        if ip == self.host:
            return
        self._set_online(False)
        self.host = ip
        self.auto = False
        self._search_timer.stop()
        self.channels = [ChannelState() for _ in self.config.channels]
        for i in range(len(self.channels)):
            self.channel_changed.emit(i)
        self._probe()
