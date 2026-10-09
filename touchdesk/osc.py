"""Low-level OSC over UDP, driven by Qt's event loop (no threads)."""

from __future__ import annotations

import logging

from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.osc_packet import OscPacket, ParseError
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QHostAddress, QUdpSocket

log = logging.getLogger(__name__)


def build_message(address: str, args: list) -> bytes:
    b = OscMessageBuilder(address=address)
    for a in args:
        if isinstance(a, bool):
            b.add_arg(int(a), OscMessageBuilder.ARG_TYPE_INT)
        elif isinstance(a, int):
            b.add_arg(a, OscMessageBuilder.ARG_TYPE_INT)
        elif isinstance(a, float):
            b.add_arg(a, OscMessageBuilder.ARG_TYPE_FLOAT)
        else:
            b.add_arg(str(a), OscMessageBuilder.ARG_TYPE_STRING)
    return b.build().dgram


class OscSocket(QObject):
    """Sends OSC messages and emits every message that comes back.

    Desks reply to whichever IP/port sent the request, so one socket is used
    for both sending and receiving.
    """

    message = Signal(str, list, str)  # address, args, sender ip

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._sock = QUdpSocket(self)
        if not self._sock.bind(QHostAddress.SpecialAddress.AnyIPv4, 0):
            log.error("Could not open a UDP socket: %s", self._sock.errorString())
        self._sock.readyRead.connect(self._read)

    def send(self, host: str, port: int, address: str, args: list | None = None) -> bool:
        data = build_message(address, list(args or []))
        if host == "broadcast":
            dest = QHostAddress(QHostAddress.SpecialAddress.Broadcast)
        else:
            dest = QHostAddress(host)
            if dest.isNull():
                log.warning("Not a valid IP address: %r", host)
                return False
        sent = self._sock.writeDatagram(data, dest, port)
        if sent < 0:
            log.debug("Send to %s:%s failed: %s", host, port, self._sock.errorString())
            return False
        return True

    def _read(self) -> None:
        while self._sock.hasPendingDatagrams():
            dgram = self._sock.receiveDatagram()
            data = bytes(dgram.data().data())
            sender = dgram.senderAddress()
            # Strip the "::ffff:" prefix from IPv4-mapped addresses.
            ip = sender.toString()
            if ip.startswith("::ffff:"):
                ip = ip[7:]
            try:
                packet = OscPacket(data)
            except ParseError:
                log.debug("Ignoring a packet that isn't OSC from %s", ip)
                continue
            for m in packet.messages:
                msg = m.message
                self.message.emit(msg.address, list(msg.params), ip)
