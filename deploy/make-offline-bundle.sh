#!/usr/bin/env bash
# Run this on a WORKING TouchDesk Pi to collect the OS packages it installed,
# so other Pis with the same Raspberry Pi OS version can be set up offline.
#
#     bash deploy/make-offline-bundle.sh [output folder]   (default: ./offline)
#
# It copies the packages apt kept from the first install. Then copy the whole
# TouchDesk folder (with offline/ inside) to a USB stick or another Pi and run
# deploy/install.sh as usual - no internet needed.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$SRC/offline}"
mkdir -p "$OUT/debs"
if ! ls /var/cache/apt/archives/*.deb >/dev/null 2>&1; then
  echo "No saved packages in /var/cache/apt/archives - this Pi's package cache has been cleaned."
  exit 1
fi
cp /var/cache/apt/archives/*.deb "$OUT/debs/"
grep -E '^(PRETTY_NAME|VERSION_ID)' /etc/os-release > "$OUT/MADE_ON.txt"
uname -m >> "$OUT/MADE_ON.txt"
echo "Copied $(ls "$OUT/debs" | wc -l) packages ($(du -sh "$OUT/debs" | cut -f1)) to $OUT/debs"
