# Bench test checklist

Everything here has been tested in software against a stand-in desk. This list covers what only real hardware can prove.

## Before bench day (about 15 minutes)

1. **Flash a fresh SD card** with Raspberry Pi Imager: Raspberry Pi 4 → *Raspberry Pi OS (64-bit)* (the desktop one).
   In Imager's settings (the cog / "Edit settings"):
   - Hostname: `touchdesk-test`
   - Username `pi` and a password you choose
   - Services tab: **Enable SSH** (password authentication)
2. Boot the Pi with the touchscreen attached, plugged into the same network as your PC (and the XR12, if it's there).
3. **Set up an SSH key on the PC** so the password never needs typing into chat. In PowerShell on the PC:
   ```powershell
   ssh-keygen -t ed25519            # press Enter at every question
   type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@touchdesk-test.local "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
   ssh pi@touchdesk-test.local      # should log in without asking for the password
   ```
4. Optional but useful: have **X AIR Edit** installed on the PC.

## On the day

### Install
- [ ] Copy the code to the Pi and run `bash deploy/install.sh --room blue --bluetooth`
- [ ] Installer finishes with no red errors; note whether PySide6 came from apt or pip
- [ ] `~/.local/bin/touchdesk --windowed` opens the window

### Desk connection (XR12)
- [ ] "Searching for desk" turns to "Desk connected" with `desk.ip` set to `auto`
- [ ] Faders and ON/OFF on screen match the desk when TouchDesk starts
- [ ] Moving a fader on the touchscreen moves it in X AIR Edit, and back again
- [ ] ON/OFF on screen mutes/unmutes the channel, and back again
- [ ] Top of fader travel = 0 dB on the desk (same as 1.x)
- [ ] Mute All mutes channels 1–4 and nothing else, including from the lock screen
- [ ] Re-run the installer with `--room green`: screen says Green Room and controls channels 5–8
- [ ] Unplug the desk's network cable: banner appears within ~10 s; plug back in: recovers and re-reads levels
- [ ] Power-cycle the desk: TouchDesk reconnects by itself
- [ ] "Find desk" in installer settings lists the XR12
- [ ] Names from the desk: rename a channel in X AIR Edit and it changes on screen

### Venue network (no router)
- [ ] Connect only the Pi and the XR12 to a plain switch (no router, no internet)
- [ ] Reboot the Pi: in installer settings, "This unit" shows a `169.254.x.x` address
- [ ] TouchDesk finds the desk by itself and shows "Desk connected"
- [ ] Power-cycle the XR12 on the switch: TouchDesk reconnects

### Touchscreen
- [ ] Fader drag feels right, no jitter while dragging
- [ ] Wrong PIN ×5 pauses the keypad; correct PIN works afterwards
- [ ] Auto-lock (set it to 5 min in installer settings to test)
- [ ] Long-press on the top bar (with PIN lock off) reaches installer settings
- [ ] Text sizes readable at arm's length

### Bluetooth
- [ ] Pi appears as "Blue Room" (then "Green Room") on a phone and pairs with no PIN
- [ ] Music plays out of the 3.5 mm jack
- [ ] Track/artist show on screen; play/pause/skip work
- [ ] Album artwork: try an Android phone and an iPhone, with Spotify and the built-in music app. Note which show artwork (placeholder note otherwise)
- [ ] Artwork changes when the track changes
- [ ] Start TouchDesk with **no** phone connected: it starts normally (the 1.x crash)
- [ ] Phone walks out of range and back: no crash

### Kiosk behaviour
- [ ] Reboot: TouchDesk starts full screen by itself, no cursor
- [ ] Screen doesn't blank after 10+ minutes
- [ ] `pkill -9 -f "python.* -m touchdesk"` from SSH: it comes back within ~3 s
- [ ] "Exit to desktop" in installer settings leaves it closed
- [ ] Leave it running overnight; check `~/.local/state/touchdesk/touchdesk.log` next day

## If something fails

Note the step and copy the last part of the log. Run `~/.local/bin/touchdesk --windowed --verbose` for full detail.
