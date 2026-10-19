#!/usr/bin/env bash
# TouchDesk installer for Raspberry Pi OS (desktop edition).
#
# Run it as the normal desktop user (not root), from the TouchDesk folder:
#     bash deploy/install.sh                           # install or upgrade
#     bash deploy/install.sh --room green --bluetooth  # Green Room (Room 1): channels 1-4
#     bash deploy/install.sh --room blue --bluetooth   # Blue Room (Room 2): channels 5-8
#
#   --room green|blue   set the room name (top bar + Bluetooth name) and its channels
#   --bluetooth         also set the Pi up as a Bluetooth speaker
#   --no-network        leave the Pi's network settings alone
#
# Safe to run again: it upgrades the app but keeps your settings
# (except the room, if you give --room).

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$HOME/.local/share/touchdesk"
APP="$DATA/app"
VENV="$DATA/venv"
CONF_DIR="$HOME/.config/touchdesk"
CONF="$CONF_DIR/config.json"
BIN="$HOME/.local/bin"
WITH_BT=0
NET=1
ROOM=""
while [ $# -gt 0 ]; do
  case "$1" in
    --bluetooth) WITH_BT=1 ;;
    --no-network) NET=0 ;;
    --room) shift; ROOM="${1:-}" ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done
case "$ROOM" in
  ""|blue|green) ;;
  *) echo "--room must be 'blue' or 'green'"; exit 1 ;;
esac

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!!  %s\033[0m\n' "$*"; }

# With SD card protection on, everything installed would vanish at the next restart.
if [ "$(findmnt -n -o FSTYPE / 2>/dev/null)" = overlay ]; then
  warn "SD card protection is on, so nothing installed now would survive a restart."
  warn "Run:  bash deploy/readonly.sh off  then restart the Pi and run the installer again."
  warn "Afterwards:  bash deploy/readonly.sh on  and restart."
  exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
  echo "Please run this as your normal user (e.g. pi), not with sudo. It will ask for your password when needed."
  exit 1
fi

# Everything TouchDesk needs from the OS. The Pis are meant to be offline,
# so these normally come from the bundled offline/ folder, not the internet.
NEEDED_PKGS="python3 python3-venv python3-dbus fonts-crosextra-carlito bluez bluez-tools bluez-obexd \
python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets python3-pyside6.qtnetwork"
OFFLINE="$SRC/offline"
missing_pkgs() {
  local p out=""
  for p in $NEEDED_PKGS; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || out="$out $p"
  done
  echo "$out"
}

say "System packages"
MISSING="$(missing_pkgs)"
if [ -z "$MISSING" ]; then
  echo "Already installed - nothing to do."
elif ls "$OFFLINE"/debs/*.deb >/dev/null 2>&1; then
  echo "Installing from the offline bundle (no internet needed):$MISSING"
  # dpkg installs exactly these files; apt isn't asked to download anything.
  sudo dpkg -i --skip-same-version "$OFFLINE"/debs/*.deb
  MISSING="$(missing_pkgs)"
  if [ -n "$MISSING" ]; then
    warn "Still missing after the offline install:$MISSING"
    warn "This bundle was made for a different Raspberry Pi OS version. Run deploy/make-offline-bundle.sh on a working Pi with the same OS."
    exit 1
  fi
else
  echo "Downloading:$MISSING"
  if ! sudo apt-get update -q || ! sudo apt-get install -y -q $MISSING; then
    warn "Couldn't download the packages above. TouchDesk Pis are usually offline -"
    warn "use the offline installer package (with an offline/ folder) instead."
    exit 1
  fi
fi

say "Copying TouchDesk to $APP"
mkdir -p "$DATA"
rm -rf "$APP.new"
mkdir -p "$APP.new"
cp -r "$SRC/touchdesk" "$APP.new/"
cp "$SRC/config.example.json" "$APP.new/"
rm -rf "$APP"
mv "$APP.new" "$APP"
find "$APP" -name __pycache__ -prune -exec rm -rf {} +

say "Setting up Python environment"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv --system-site-packages "$VENV"
fi
if ls "$OFFLINE"/wheels/*.whl >/dev/null 2>&1; then
  "$VENV/bin/pip" install -q --no-index --find-links "$OFFLINE/wheels" --upgrade "python-osc>=1.8"
elif ! "$VENV/bin/python" -c "import pythonosc" 2>/dev/null; then
  "$VENV/bin/pip" install -q --upgrade "python-osc>=1.8"
fi
if ! "$VENV/bin/python" -c "import PySide6.QtWidgets, PySide6.QtNetwork" 2>/dev/null; then
  warn "Qt for Python (PySide6) isn't working. Make sure this is the 64-bit Raspberry Pi OS (Debian 13 or later)."
  exit 1
fi
"$VENV/bin/python" -c "import PySide6, pythonosc; print('PySide6', PySide6.__version__)"

say "Settings"
mkdir -p "$CONF_DIR"
if [ -f "$CONF" ]; then
  echo "Keeping your existing settings: $CONF"
else
  cp "$SRC/config.example.json" "$CONF"
  echo "Created $CONF"
  if [ -z "$ROOM" ] && [ -t 0 ]; then
    echo "Which room is this unit for?"
    echo "  1) Green Room (Room 1, desk channels 1-4)"
    echo "  2) Blue Room  (Room 2, desk channels 5-8)"
    echo "  3) Neither - I'll edit the settings file myself"
    read -r -p "Choose 1, 2 or 3 [3]: " CHOICE || true
    case "${CHOICE:-3}" in 1) ROOM=green ;; 2) ROOM=blue ;; esac
  fi
  if [ -t 0 ]; then
    read -r -p "User PIN for the touchscreen [1234]: " PIN || true
    read -r -p "Installer PIN for the settings screen (4-8 digits, different) [000000]: " APIN || true
    PIN="${PIN:-1234}"; APIN="${APIN:-000000}"
    "$VENV/bin/python" - "$CONF" "$PIN" "$APIN" <<'PY'
import json, sys
path, pin, apin = sys.argv[1:4]
with open(path) as f:
    c = json.load(f)
c["security"]["pin"], c["security"]["admin_pin"] = pin, apin
with open(path, "w") as f:
    json.dump(c, f, indent=2)
PY
  fi
fi
if [ -n "$ROOM" ]; then
  "$VENV/bin/python" - "$CONF" "$ROOM" <<'PY'
import json, sys
path, room = sys.argv[1:3]
title, first = {"green": ("Green Room", 1), "blue": ("Blue Room", 5)}[room]
with open(path) as f:
    c = json.load(f)
c.setdefault("display", {})["title"] = title
# Wall plates are #1-#3; the 4th input is the Pi's own Bluetooth audio.
c["channels"] = [
    {"label": "#1", "type": "ch", "number": first},
    {"label": "#2", "type": "ch", "number": first + 1},
    {"label": "#3", "type": "ch", "number": first + 2},
    {"label": "Bluetooth", "type": "ch", "number": first + 3, "icon": "bluetooth"},
]
with open(path, "w") as f:
    json.dump(c, f, indent=2)
print(f"Set up as {title}: desk channels {first}-{first + 3}")
PY
fi
# Check the settings file is valid before going further.
if ! PYTHONPATH="$APP" "$VENV/bin/python" -c "
import sys
from touchdesk import config
try:
    config.load('$CONF')
except config.ConfigError as e:
    print(e); sys.exit(1)
"; then
  warn "Fix the settings file above, then run this installer again."
  exit 1
fi

say "Creating the launcher"
mkdir -p "$BIN"
cat > "$BIN/touchdesk" <<EOF
#!/usr/bin/env bash
# Starts TouchDesk and restarts it if it ever crashes.
# Choosing "Exit to desktop" in the installer settings stops it for good.
export PYTHONPATH="$APP"
# Only ever one copy: tapping the desktop icon while it's running does nothing.
exec 9>"\${XDG_RUNTIME_DIR:-/tmp}/touchdesk.lock"
if ! flock -n 9; then
  echo "TouchDesk is already running." >&2
  exit 0
fi
# Pi's audio output to 100% on every start (the OS defaults to ~40%, and the
# desk channel's gain is set expecting full level). Runs in the background
# because the audio system may still be starting when TouchDesk does.
"$BIN/touchdesk-volume" >/dev/null 2>&1 &
while true; do
  "$VENV/bin/python" -m touchdesk "\$@" && exit 0
  echo "TouchDesk stopped unexpectedly - restarting in 3 seconds" >&2
  sleep 3
done
EOF
chmod +x "$BIN/touchdesk"
cat > "$BIN/touchdesk-volume" <<'EOF'
#!/usr/bin/env bash
# Sets the Pi's audio output (the 3.5 mm jack feeding the desk) to 100%, unmuted.
command -v wpctl >/dev/null || exit 0
for _ in $(seq 30); do
  if wpctl inspect @DEFAULT_AUDIO_SINK@ >/dev/null 2>&1; then
    wpctl set-mute @DEFAULT_AUDIO_SINK@ 0
    wpctl set-volume @DEFAULT_AUDIO_SINK@ 1.0
    exit 0
  fi
  sleep 1
done
EOF
chmod +x "$BIN/touchdesk-volume"

say "Adding a TouchDesk icon (desktop, menu and taskbar)"
# So it can be restarted with a tap if it's ever closed - no keyboard or mouse needed.
ICON_DIR="$HOME/.local/share/icons"
mkdir -p "$ICON_DIR" "$HOME/.local/share/applications" "$HOME/Desktop"
cp "$SRC/deploy/touchdesk.svg" "$ICON_DIR/touchdesk.svg"
cat > "$HOME/.local/share/applications/touchdesk.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TouchDesk
Comment=Start the TouchDesk sound desk remote
Exec=$BIN/touchdesk
Icon=$ICON_DIR/touchdesk.svg
Terminal=false
Categories=AudioVideo;
DESKTOP
cp "$HOME/.local/share/applications/touchdesk.desktop" "$HOME/Desktop/TouchDesk.desktop"
# Not executable: it doesn't need to be, and an executable text file looks
# like a script to the desktop.
chmod -x "$HOME/Desktop/TouchDesk.desktop"
# Tapping a desktop icon asks "Execute / Open?" unless quick_exec is on.
# Raspberry Pi OS 13's desktop (pcmanfm-pi) reads it from its own settings
# file, not libfm.conf as older versions did, so set it in both.
python3 - "$HOME/.config/pcmanfm/default/pcmanfm.conf" "$HOME/.config/libfm/libfm.conf" <<'PY'
import configparser, os, sys
for path in sys.argv[1:]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = configparser.ConfigParser(interpolation=None, strict=False)
    c.optionxform = str
    c.read(path)
    if not c.has_section("config"):
        c.add_section("config")
    c.set("config", "quick_exec", "1")
    with open(path, "w") as f:
        c.write(f, space_around_delimiters=False)
PY
# One-tap button on the taskbar, next to the browser/files/terminal buttons.
PANEL_SYS=/etc/xdg/wf-panel-pi/wf-panel-pi.ini
PANEL_USR="$HOME/.config/wf-panel-pi/wf-panel-pi.ini"
if [ -f "$PANEL_SYS" ]; then
  mkdir -p "$(dirname "$PANEL_USR")"
  python3 - "$PANEL_SYS" "$PANEL_USR" <<'PY'
import configparser, sys
sys_ini, usr_ini = sys.argv[1:3]
def load(path):
    c = configparser.ConfigParser(interpolation=None)
    c.optionxform = str
    c.read(path)
    return c
s, u = load(sys_ini), load(usr_ini)
if not u.has_section("panel"):
    u.add_section("panel")
launchers = u.get("panel", "launchers", fallback=s.get("panel", "launchers", fallback="")).split()
if "touchdesk" not in launchers:
    launchers.insert(0, "touchdesk")
u.set("panel", "launchers", " ".join(launchers))
with open(usr_ini, "w") as f:
    u.write(f)
PY
fi

say "Starting TouchDesk automatically when the desktop loads"
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/touchdesk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TouchDesk
Comment=Touchscreen sound desk remote
Exec=$BIN/touchdesk
X-GNOME-Autostart-enabled=true
EOF

if [ "$NET" -eq 1 ] && command -v nmcli >/dev/null; then
  say "Network: allow 169.254.x.x addresses when there's no router"
  # Venues often have just a switch: the desk and Pis then give themselves
  # 169.254.x.x ("link-local") addresses. Older Raspberry Pi OS did this by
  # itself; NetworkManager (Raspberry Pi OS 12+) doesn't unless asked.
  # Where a router hands out addresses (DHCP), that still works as normal.
  # "fallback" (only when there's no other address) needs NetworkManager 1.52+;
  # older versions get "enabled" (a 169.254 address alongside any DHCP one).
  NM_VER="$(nmcli --version | grep -oE '[0-9]+(\.[0-9]+)+' | head -1)"
  if printf '1.52.0\n%s\n' "$NM_VER" | sort -V -C; then LL=fallback; else LL=enabled; fi
  FOUND=0
  while IFS=: read -r NAME TYPE; do
    [ "$TYPE" = "802-3-ethernet" ] || continue
    FOUND=1
    METHOD="$(nmcli -g ipv4.method connection show "$NAME")"
    if [ "$METHOD" != "auto" ]; then
      echo "  '$NAME' uses a fixed address ($METHOD) - leaving it alone."
      continue
    fi
    if sudo nmcli connection modify "$NAME" ipv4.link-local "$LL" ipv4.may-fail yes ipv4.dhcp-timeout 2147483647; then
      echo "  '$NAME': DHCP when available, otherwise 169.254.x.x (link-local: $LL)"
    else
      warn "Couldn't change '$NAME'."
    fi
  done < <(nmcli -t -f NAME,TYPE connection show)
  [ "$FOUND" -eq 1 ] && echo "  Takes effect after the next reboot (or cable re-plug)."
  [ "$FOUND" -eq 0 ] && warn "No wired network connection found to adjust."
fi

if command -v raspi-config >/dev/null; then
  say "Turning off screen blanking"
  sudo raspi-config nonint do_blanking 1 || warn "Couldn't change screen blanking - turn it off in Raspberry Pi Configuration > Display."
fi

if [ "$WITH_BT" -eq 1 ]; then
  BT_NAME="$("$VENV/bin/python" -c "import json,sys; print(json.load(open(sys.argv[1])).get('display',{}).get('title') or 'TouchDesk')" "$CONF")"
  bash "$SRC/deploy/bluetooth-setup.sh" "$BT_NAME"
fi

say "Done"
cat <<EOF
  App:       $APP
  Settings:  $CONF
  Log:       ~/.local/state/touchdesk/touchdesk.log

  Try it now in a window:    $BIN/touchdesk --windowed
  It will start full screen by itself after the next reboot.
EOF
