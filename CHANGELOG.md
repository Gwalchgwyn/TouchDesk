# Changelog

## 2.0.0 (2026-10-19)

Rebuilt from TouchDesk 1.1. Same look, new internals. Installed and tested at the original venue on both rooms (XR12, firmware 1.09).

### Fixed (bugs in 1.1)
- Crashed at start-up when no Bluetooth device was connected (likely why a cloned SD card wouldn't run on a replacement Pi: new Pi, new Bluetooth address, phone not paired).
- Bluetooth player was created twice; auto-logout cleared the hidden copy.
- The Bluetooth reset button stacked up duplicate listeners each time it was pressed.
- `set_volume` referred to an undefined variable.
- Images loaded from a relative `./images` folder that wasn't in the repository.
- OSC addresses had trailing slashes and used `/ch/0N/mix/` for mute; now the documented `/ch/NN/mix/on` and `/ch/NN/mix/fader`, which also work for channels 10 and up.
- Screen didn't reflect the desk's real state at start-up or after changes made elsewhere.
- Desk IP address was hard-coded; a link-local address can change, which would silently break the screen.
- Auto-start ran as root from `/etc/profile` on every login shell.

### Added
- Two-way sync with the desk (`/xremote` subscription, re-read on reconnect).
- Desk auto-discovery, connection status and offline banner. Discovery works on networks with no router (switch only, 169.254.x.x addresses).
- Installer configures the Pi's wired connection to fall back to a 169.254.x.x address when there's no DHCP server (NetworkManager doesn't by default).
- Settings file with validation and on-screen error reporting.
- Configurable channels: choose which four desk channels a screen controls.
- Installer room presets: Green Room / Room 1 (channels 1–4) and Blue Room / Room 2 (5–8), each with its own Bluetooth name.
- Album artwork from the phone over Bluetooth (AVRCP 1.6 cover art via BlueZ/obexd; experimental, phone-dependent).
- Remembered phones limited to 10 (least recently used forgotten automatically), plus "Forget phones" in installer settings. 1.x could fill up until new phones couldn't pair.
- Installer settings screen behind a separate PIN, showing desk, network and power health (the Pi's low-voltage record since power-on).
- PIN masking and lockout; Mute All available while locked.
- Desk channel names, dB readout option, configurable maximum level.
- X32 / M32 profile (untested).
- Fully offline install: packages bundled in `offline/`, no internet or `apt-get update` needed; already-installed packages skipped on upgrades. `deploy/make-offline-bundle.sh` collects packages from a working Pi.
- Desktop icon, menu entry and taskbar button to start TouchDesk; launcher refuses to start a second copy.
- The Pi's audio output is set to 100% each time TouchDesk starts (Raspberry Pi OS defaults to about 40%).
- Step-by-step re-imaging guide (`docs/reimage-guide.md`).
- Installer script, crash-restart launcher, Bluetooth pairing agent service.
- Automated tests and a small stand-in desk for development.

### Changed
- PySide2 → PySide6 (Qt 6).
- Python 3.8 build-from-source no longer needed; uses the OS's Python.
