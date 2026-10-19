#!/usr/bin/env bash
# Make the Pi a Bluetooth speaker that phones can connect to without anyone
# touching the Pi: always discoverable, pairing accepted automatically.
# Audio from the phone plays through the Pi's default output (set that to the
# 3.5 mm jack in the desktop's volume menu, and cable the jack into the desk).
#
# NOTE: like TouchDesk 1.x, anyone within Bluetooth range can connect.
#
#     bash deploy/bluetooth-setup.sh [name]     (default name: TouchDesk)

set -euo pipefail
NAME="${1:-TouchDesk}"

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

say "Installing Bluetooth tools"
sudo apt-get install -y -q bluez bluez-tools bluez-obexd

say "Turning on BlueZ experimental features (needed for album artwork)"
CONF=/etc/bluetooth/main.conf
if [ -f "$CONF" ]; then
  if grep -qE '^[#[:space:]]*Experimental[[:space:]]*=' "$CONF"; then
    sudo sed -i -E 's/^[#[:space:]]*Experimental[[:space:]]*=.*/Experimental = true/' "$CONF"
  else
    sudo sed -i '/^\[General\]/a Experimental = true' "$CONF"
  fi
  sudo systemctl restart bluetooth
else
  echo "No $CONF found - album artwork will stay off."
fi

say "Making sure Bluetooth isn't switched off"
sudo rfkill unblock bluetooth || true

say "Creating a background service that accepts pairing automatically"
sudo tee /etc/systemd/system/touchdesk-bt-agent.service >/dev/null <<EOF
[Unit]
Description=TouchDesk Bluetooth pairing agent (accepts connections without a PIN)
After=bluetooth.service
Requires=bluetooth.service

[Service]
# Fresh Raspberry Pi OS installs often start with Bluetooth "soft blocked",
# which stops the controller powering on. Unblock it on every start.
ExecStartPre=-/usr/sbin/rfkill unblock bluetooth
ExecStartPre=/bin/sleep 2
ExecStartPre=-/usr/bin/bluetoothctl system-alias "$NAME"
ExecStartPre=-/usr/bin/bluetoothctl power on
ExecStartPre=-/usr/bin/bluetoothctl discoverable-timeout 0
ExecStartPre=-/usr/bin/bluetoothctl discoverable on
ExecStartPre=-/usr/bin/bluetoothctl pairable on
ExecStart=/usr/bin/bt-agent --capability=NoInputNoOutput
Restart=always
RestartSec=5
# bt-agent is slow to exit on SIGTERM; don't make restarts wait 90 s.
TimeoutStopSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable touchdesk-bt-agent.service
sudo systemctl restart touchdesk-bt-agent.service

say "Removing the desktop's own Bluetooth icon"
# The taskbar's Bluetooth icon shows "Pairing..." / "Connection successful"
# pop-ups that would appear over TouchDesk. TouchDesk's pairing service
# handles phones itself, so the icon isn't needed on a wall unit.
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
right = u.get("panel", "widgets_right", fallback=s.get("panel", "widgets_right", fallback=""))
u.set("panel", "widgets_right", " ".join(w for w in right.split() if w != "bluetooth"))
with open(usr_ini, "w") as f:
    u.write(f)
PY
  echo "  Done (takes effect after the next reboot)."
else
  echo "  No taskbar settings found - skipping."
fi

say "Bluetooth ready"
cat <<EOF
  The Pi should now appear as "$NAME" in your phone's Bluetooth list.
  Audio playback needs the desktop session running (it is, when TouchDesk is up).
  If sound comes out of HDMI instead of the 3.5 mm jack, right-click the speaker
  icon on the desktop taskbar and choose the AV jack / Headphones output.

  Check the agent:   systemctl status touchdesk-bt-agent
EOF
