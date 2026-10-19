#!/usr/bin/env bash
# Protects the SD card. With protection on, the Pi runs from a read-only copy
# of the card and keeps every change in memory, so pulling the power can't
# damage the card, and every restart puts the Pi back exactly as it was
# (new Bluetooth pairings, PIN changes and logs are forgotten).
#
#     bash deploy/readonly.sh on       then restart
#     bash deploy/readonly.sh off      then restart (do this before updating)
#     bash deploy/readonly.sh status
#
# Needs no extra packages and no internet (raspi-config's version downloads
# "overlayroot"). Emergency off switch: put the card in a computer, open
# cmdline.txt on the small "bootfs" drive and delete the words "boot=overlay ".
set -euo pipefail

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;31m%s\033[0m\n' "$*" >&2; }

CMDLINE=/boot/firmware/cmdline.txt
[ -f "$CMDLINE" ] || CMDLINE=/boot/cmdline.txt
BOOTDIR="$(dirname "$CMDLINE")"
SCRIPT=/etc/initramfs-tools/scripts/overlay

protected_now()  { [ "$(findmnt -n -o FSTYPE /)" = overlay ]; }
protected_next() { grep -qw "boot=overlay" "$CMDLINE"; }

boot_writable() {
  # The boot partition is normally writable, even with protection on.
  if ! touch "$BOOTDIR/.touchdesk-test" 2>/dev/null; then
    sudo mount -o remount,rw "$BOOTDIR"
  fi
  sudo rm -f "$BOOTDIR/.touchdesk-test"
}

status() {
  if protected_now; then echo "Now:          protected (read-only)"; else echo "Now:          writable"; fi
  if protected_next; then echo "After restart: protected (read-only)"; else echo "After restart: writable"; fi
}

case "${1:-status}" in
  on)
    if protected_next; then
      echo "Protection is already switched on."; status; exit 0
    fi
    if ! protected_now; then
      # The step below relies on these parts of Debian's start-up scripts.
      LOCAL=/usr/share/initramfs-tools/scripts/local
      for fn in local_mount_root local_top local_device_setup local_premount; do
        if ! grep -q "^${fn}()" "$LOCAL" 2>/dev/null; then
          warn "This Raspberry Pi OS's start-up scripts have changed ($fn missing) - not switching protection on."
          exit 1
        fi
      done
      grep -q "^checkfs()" /usr/share/initramfs-tools/scripts/functions || { warn "checkfs missing - not switching protection on."; exit 1; }
      say "Adding the read-only start-up step"
      sudo tee "$SCRIPT" >/dev/null <<'EOF'
# TouchDesk SD card protection -*- shell-script -*-
# Used only when the kernel command line has boot=overlay. Replaces
# local_mount_root() from /scripts/local: the card is mounted read-only on
# /lower and a RAM-backed overlay on top of it becomes the root filesystem.
. /scripts/local

local_mount_root()
{
	local_top
	local_device_setup "${ROOT}" "root file system"
	ROOT="${DEV}"
	if [ -z "${ROOTFSTYPE}" ] || [ "${ROOTFSTYPE}" = auto ]; then
		FSTYPE=$(get_fstype "${ROOT}")
	else
		FSTYPE=${ROOTFSTYPE}
	fi
	local_premount

	modprobe "${FSTYPE}" || true
	checkfs "${ROOT}" root "${FSTYPE}"
	mkdir -p /lower /upper
	if [ "${FSTYPE}" != "unknown" ]; then
		mount -r -t "${FSTYPE}" ${ROOTFLAGS} "${ROOT}" /lower
	else
		mount -r ${ROOTFLAGS} "${ROOT}" /lower
	fi
	modprobe overlay || insmod "/lower/lib/modules/$(uname -r)/kernel/fs/overlayfs/overlay.ko"
	mount -t tmpfs tmpfs /upper
	mkdir -p /upper/data /upper/work
	if ! mount -t overlay -o lowerdir=/lower,upperdir=/upper/data,workdir=/upper/work overlay "${rootmnt}"; then
		# Never leave the Pi unbootable: fall back to the normal writable root.
		umount /lower
		mount -w -t "${FSTYPE}" ${ROOTFLAGS} "${ROOT}" "${rootmnt}"
	fi
}
EOF
      grep -qx overlay /etc/initramfs-tools/modules || echo overlay | sudo tee -a /etc/initramfs-tools/modules >/dev/null

      say "Rebuilding the start-up files (takes a minute or two)"
      sudo update-initramfs -u -k all

      say "Checking the new start-up files"
      FOUND=0
      for f in "$BOOTDIR"/initramfs*; do
        [ -f "$f" ] || continue
        FOUND=1
        # (Not grep -q: it stops reading early, the decompressor then fails
        # with "zstd failed" and pipefail turns that into a false alarm.)
        if ! lsinitramfs "$f" | grep 'scripts/overlay$' >/dev/null; then
          warn "$f doesn't contain the read-only step - not switching protection on."
          exit 1
        fi
        echo "  $(basename "$f"): OK"
      done
      if [ "$FOUND" = 0 ]; then
        warn "No start-up files (initramfs) found in $BOOTDIR - not switching protection on."
        exit 1
      fi
    fi
    say "Switching protection on"
    boot_writable
    sudo sed -i '1 s/^/boot=overlay /' "$CMDLINE"
    echo "Done. Restart the Pi for it to take effect."
    ;;
  off)
    if ! protected_next; then
      echo "Protection is already switched off."; status; exit 0
    fi
    say "Switching protection off"
    boot_writable
    sudo sed -i -E '1 s/(^| )boot=overlay( |$)/\1/' "$CMDLINE"
    echo "Done. Restart the Pi, then make your changes or run the installer."
    ;;
  status)
    status
    ;;
  *)
    echo "Usage: bash deploy/readonly.sh on|off|status" >&2
    exit 2
    ;;
esac
