#!/usr/bin/env bash
# Removes TouchDesk. Your settings file is kept unless you pass --purge.
set -euo pipefail
rm -f "$HOME/.config/autostart/touchdesk.desktop" "$HOME/.local/bin/touchdesk"
rm -rf "$HOME/.local/share/touchdesk"
if systemctl list-unit-files touchdesk-bt-agent.service >/dev/null 2>&1; then
  sudo systemctl disable --now touchdesk-bt-agent.service 2>/dev/null || true
  sudo rm -f /etc/systemd/system/touchdesk-bt-agent.service
  sudo systemctl daemon-reload
fi
if [ "${1:-}" = "--purge" ]; then
  rm -rf "$HOME/.config/touchdesk" "$HOME/.local/state/touchdesk"
  echo "TouchDesk and its settings removed."
else
  echo "TouchDesk removed. Settings kept in ~/.config/touchdesk (use --purge to remove them too)."
fi
