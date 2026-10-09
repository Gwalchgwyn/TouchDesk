"""A tiny stand-in for an X Air desk, for automated tests only.

It answers /xinfo, remembers values it is sent, replies to queries, and
pushes changes to /xremote subscribers - the same behaviour TouchDesk relies
on from the real desk. It is NOT an emulator of the whole desk.

Run it by hand to try TouchDesk without a desk:
    python3 tests/fake_desk.py --port 10024
"""

from __future__ import annotations

import argparse
import socket
import threading
import time

from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.osc_packet import OscPacket


def _build(address, args):
    b = OscMessageBuilder(address=address)
    for a in args:
        b.add_arg(a)
    return b.build().dgram


class FakeDesk:
    def __init__(self, port: int = 0, name: str = "XR12-FAKE", model: str = "XR12", host: str = "0.0.0.0"):
        self.name, self.model = name, model
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.state: dict[str, object] = {}
        for n in range(1, 17):
            self.state[f"/ch/{n:02d}/mix/fader"] = 0.75
            self.state[f"/ch/{n:02d}/mix/on"] = 1
            self.state[f"/ch/{n:02d}/config/name"] = f"Ch {n}"
        self.state["/lr/mix/fader"] = 0.75
        self.state["/lr/mix/on"] = 1
        self.state["/lr/config/name"] = ""
        self.subscribers: dict[tuple, float] = {}
        self.received: list[tuple[str, list]] = []
        self.silent = False  # pretend to be unplugged
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._lock = threading.Lock()

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        self.sock.close()

    def _run(self):
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65535)
            except (socket.timeout, OSError):
                continue
            if self.silent:
                continue
            try:
                packet = OscPacket(data)
            except Exception:
                continue
            for m in packet.messages:
                self._handle(m.message.address, list(m.message.params), addr)

    def _handle(self, address, args, addr):
        with self._lock:
            self.received.append((address, args))
        if address == "/xinfo":
            self.sock.sendto(_build("/xinfo", ["127.0.0.1", self.name, self.model, "1.22"]), addr)
        elif address == "/xremote":
            self.subscribers[addr] = time.monotonic()
        elif not args:
            if address in self.state:
                self.sock.sendto(_build(address, [self.state[address]]), addr)
        else:
            if address in self.state:
                self.state[address] = args[0]
                self._notify(address, exclude=addr)

    def _notify(self, address, exclude=None):
        now = time.monotonic()
        for sub, t in list(self.subscribers.items()):
            if now - t > 10:
                del self.subscribers[sub]
                continue
            if sub != exclude:
                self.sock.sendto(_build(address, [self.state[address]]), sub)

    def external_change(self, address, value):
        """Simulate someone changing the desk from another app."""
        self.state[address] = value
        self._notify(address)

    def sent_to(self, address):
        with self._lock:
            return [a for (addr, a) in self.received if addr == address]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=10024)
    ns = ap.parse_args()
    d = FakeDesk(ns.port).start()
    print(f"Fake desk listening on UDP {d.port}. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        d.stop()
