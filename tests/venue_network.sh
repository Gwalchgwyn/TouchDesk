#!/usr/bin/env bash
# Recreates the venue's network in software (Linux, needs root): a Pi and a
# desk on a plain switch, no router, both on 169.254.x.x addresses - then
# checks TouchDesk can find the desk on its own.
#     sudo bash tests/venue_network.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cleanup() { [ -n "${FD:-}" ] && kill "$FD" 2>/dev/null || true; ip netns del td-pi 2>/dev/null || true; ip netns del td-desk 2>/dev/null || true; }
trap cleanup EXIT
cleanup
ip netns add td-pi
ip netns add td-desk
ip link add td-a type veth peer name td-b
ip link set td-a netns td-pi
ip link set td-b netns td-desk
ip -n td-pi addr add 169.254.10.20/16 brd + dev td-a
ip -n td-desk addr add 169.254.242.230/16 brd + dev td-b
for ns in td-pi td-desk; do ip -n $ns link set lo up; done
ip -n td-pi link set td-a up
ip -n td-desk link set td-b up

ip netns exec td-desk python3 "$HERE/fake_desk.py" --port 10024 >/dev/null 2>&1 & FD=$!
sleep 1
ip netns exec td-pi env QT_QPA_PLATFORM=offscreen python3 - "$HERE" <<'PY'
import sys
sys.path[:0] = [sys.argv[1], sys.argv[1] + "/.."]
from PySide6.QtWidgets import QApplication
app = QApplication([])
from conftest import wait_until
from touchdesk import config, session
s = session.DeskSession(config.from_dict({"desk": {"ip": "auto"}}))
s.start()
ok = wait_until(lambda: s.online, 6)
print("PASS: found desk at", s.host) if ok else print("FAIL: desk not found")
sys.exit(0 if ok else 1)
PY
