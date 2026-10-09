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

say "Creating a background service that accepts pairing automatically"
sudo tee /etc/systemd/system/touchdesk-bt-agent.service >/dev/null <<EOF
[Unit]
Description=TouchDesk Bluetooth pairing agent (accepts connections without a PIN)
After=bluetooth.service
Requires=bluetooth.service

[Service]
ExecStartPre=/bin/sleep 2
ExecStartPre=-/usr/bin/bluetoothctl system-alias "$NAME"
ExecStartPre=-/usr/bin/bluetoothctl power on
ExecStartPre=-/usr/bin/bluetoothctl discoverable-timeout 0
ExecStartPre=-/usr/bin/bluetoothctl discoverable on
ExecStartPre=-/usr/bin/bluetoothctl pairable on
ExecStart=/usr/bin/bt-agent --capability=NoInputNoOutput
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable touchdesk-bt-agent.service
sudo systemctl restart touchdesk-bt-agent.service

say "Bluetooth ready"
cat <<EOF
  The Pi should now appear as "$NAME" in your phone's Bluetooth list.
  Audio playback needs the desktop session running (it is, when TouchDesk is up).
  If sound comes out of HDMI instead of the 3.5 mm jack, right-click the speaker
  icon on the desktop taskbar and choose the AV jack / Headphones output.

  Check the agent:   systemctl status touchdesk-bt-agent
EOF
