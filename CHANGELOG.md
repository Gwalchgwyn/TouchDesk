# Changelog

## 2.0.0 (in development)

Rebuilt from TouchDesk 1.1. Same look, new internals.

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
- Installer room presets: Blue Room (channels 1–4) and Green Room (5–8), each with its own Bluetooth name.
- Album artwork from the phone over Bluetooth (AVRCP 1.6 cover art via BlueZ/obexd; experimental, phone-dependent).
- Remembered phones limited to 10 (least recently used forgotten automatically), plus "Forget phones" in installer settings. 1.x could fill up until new phones couldn't pair.
- Installer settings screen behind a separate PIN.
- PIN masking and lockout; Mute All available while locked.
- Desk channel names, dB readout option, configurable maximum level.
- X32 / M32 profile (untested).
- Installer script, crash-restart launcher, Bluetooth pairing agent service.
- Automated tests and a small stand-in desk for development.

### Changed
- PySide2 → PySide6 (Qt 6).
- Python 3.8 build-from-source no longer needed; uses the OS's Python.
