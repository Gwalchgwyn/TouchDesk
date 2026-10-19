# Rebuilding a TouchDesk unit from scratch

A step-by-step guide to putting TouchDesk on a new SD card: for a failed card, a replacement Pi, or a new room. You need no internet at the venue and no programming knowledge. Allow about 45 minutes.

If you just want to get a room working again quickly and still have the **old card**, try putting it back in first.

---

## What you need

- A Windows laptop (a Mac or Linux works the same way; the commands below are typed into a terminal instead of PowerShell).
- A **microSD card**, 16 GB or larger. Get a "High Endurance" card (e.g. SanDisk High Endurance, Samsung PRO Endurance): these units run 24/7 and ordinary cards wear out.
- A microSD card reader for the laptop.
- A network cable to plug the laptop into the **same switch** as the sound desk and the TouchDesk screens.

## Before you go to the venue (needs internet)

1. Install **Raspberry Pi Imager** on the laptop: <https://www.raspberrypi.com/software/>
2. Download the **offline installer** from the latest TouchDesk release: <https://github.com/Gwalchgwyn/touchdesk/releases/latest>
   It's the file named like `TouchDesk-offline-2.0.1.tgz` under *Assets*. Save it in your **Documents** folder and **rename it to `TouchDesk-offline.tgz`** so the commands below work as written. Don't unzip it.

That's everything that needs the internet. The Pis never go online.

---

## Step 1: Prepare the SD card

1. Put the SD card in the laptop and open **Raspberry Pi Imager**.
2. **Device:** Raspberry Pi 4.
3. **Operating system:** *Raspberry Pi OS (64-bit)*, the version **with desktop**. TouchDesk's offline installer was made for **Raspberry Pi OS 13 ("Trixie")**. If that's no longer the version Imager shows, see *"The installer says the bundle was made for a different version"* at the end.
4. **Storage:** the SD card. Check carefully that it's the card and not another drive.
5. When asked about customisation, choose **Edit settings** and set:
   - **Hostname:** `touchdesk-green` for the Green Room, or `touchdesk-blue` for the Blue Room
   - **Username:** `pi` **Password:** `pi`
   - **Wireless LAN:** leave it **off**
   - **Locale:** your time zone and keyboard (e.g. Europe/London, gb)
   - **Services** tab: tick **Enable SSH**, and choose **Use password authentication**
6. Save, then **Yes** to write. It takes about 10 minutes.

**If Imager says the card is write-protected:** the card has an old Pi installation on it that Windows won't overwrite. Open PowerShell as administrator and type:

```
diskpart
list disk
```

Find the SD card by its size (e.g. 29 GB for a 32 GB card). Be certain: the next commands erase whatever disk you pick. Then, replacing `2` with the card's disk number:

```
select disk 2
clean
exit
```

Then start Imager again.

## Step 2: Start the Pi

1. Take the old card out of the Pi (keep it, labelled, as a backup) and put the new one in.
2. Power the Pi on. Wait for the desktop: about 2 minutes. It's normal for it to restart once by itself on its very first start.
3. Plug the laptop into the venue's network switch.

## Step 3: Copy the installer to the Pi

Open **PowerShell** on the laptop (Start menu, type *PowerShell*). Copy and paste this line, changing `green` to `blue` for the Blue Room:

```
scp "$env:USERPROFILE\Documents\TouchDesk-offline.tgz" pi@touchdesk-green.local:
```

- If it asks *"Are you sure you want to continue connecting?"*, type `yes` and press Enter.
- When it asks for the **password**, type `pi` and press Enter. **Nothing appears on screen as you type the password, which is normal.**
- It's done when you see `100%`.

**If it says "Could not resolve hostname", "Connection refused" or "timed out":** the new Pi drops off the network for a moment every minute or so until TouchDesk is installed (there's no router at the venue). Wait 30 seconds and run the same line again; it usually works within a few tries. If it still fails after a few minutes, unplug the Pi's network lead for 5 seconds and plug it back in.

## Step 4: Install TouchDesk

Paste this line. Use `green` **twice** for the Green Room, or `blue` **twice** for the Blue Room:

```
ssh -t pi@touchdesk-green.local "tar xzf TouchDesk-offline.tgz && cd TouchDesk && bash deploy/install.sh --room green --bluetooth && sudo raspi-config nonint do_vnc 0 && sudo reboot"
```

- Password: `pi` (type it straight away; if you wait too long it gives up). It may ask for the password a second time partway through.
- It asks for a **User PIN**: what people type to unlock the screen. Press Enter for `1234`, or type your own.
- It asks for an **Installer PIN**: for the settings screen. Press Enter for `000000`, or type your own (different from the user PIN).
- The installer prints its progress in blue. It takes a few minutes, then the Pi restarts by itself and PowerShell says the connection closed. That's expected.

If the connection drops before the installer starts (same reasons as in Step 3), just run the line again.

## Step 5: Check it works

After the restart, TouchDesk should start full screen by itself.

- [ ] The top bar says **Green Room** or **Blue Room** and **Desk connected**.
- [ ] Unlock with the user PIN. Moving a fader on the screen moves the right desk channel (Green: 1–4, Blue: 5–8).
- [ ] **Mute All** mutes only that room's four channels.
- [ ] On a phone, the Pi appears in the Bluetooth list as **Green Room** / **Blue Room** and connects without a code. Music plays through channel 4 (Green) / 8 (Blue).
- [ ] Type the **installer PIN** on the lock screen. *This unit* shows a `169.254…` address, and *Power* says **OK**.

## Step 6: Protect the SD card

This makes the Pi run from a read-only copy of the card. Pulling the power can then no longer damage the card, and every restart puts the Pi back exactly as it is now. Phones paired since, PIN changes made on the touchscreen and logs are all forgotten at the next restart, so **set the PINs you want first** (Step 4 asks for them).

```
ssh -t pi@touchdesk-green.local "bash TouchDesk/deploy/readonly.sh on && sudo reboot"
```

(Change `green` to `blue` for the Blue Room. Password `pi`.) After the restart, the installer settings screen shows **SD card: protected**.

Done. Label the old card and keep it somewhere safe.

---

## Rooms at a glance

| Room | Hostname | Installer option | Desk channels | Mix | Bluetooth name |
|---|---|---|---|---|---|
| Green Room (Room 1) | `touchdesk-green` | `--room green` | 1–4 (4 = Bluetooth) | Aux 1 | Green Room |
| Blue Room (Room 2) | `touchdesk-blue` | `--room blue` | 5–8 (8 = Bluetooth) | Aux 2 | Blue Room |

Default passwords and PINs: Pi login `pi` / `pi`; user PIN `1234`; installer PIN `000000`, unless whoever installed it chose others.

## Using the installer settings screen

Type the **installer PIN** on the lock screen. From there you can:

- **Forget phones**: tap twice to clear every remembered phone (the Pi forgets old ones by itself after 10).
- Switch the PIN lock on or off, change the auto-lock time, change either PIN, and show levels as 0–10 or dB.
- **Exit to desktop**: closes TouchDesk. To start it again, tap the TouchDesk icon on the taskbar, or the icon on the desktop. Restarting the Pi also starts it.

## Updating TouchDesk later

The SD card protection has to be switched off while updating, or the update would vanish at the next restart.

1. Switch protection off (the Pi restarts):
   ```
   ssh -t pi@touchdesk-green.local "bash TouchDesk/deploy/readonly.sh off && sudo reboot"
   ```
2. Download the newer `TouchDesk-offline.tgz` (or a smaller `TouchDesk-update.tgz`) into Documents, then run Step 3 and Step 4 again with that file name, but leave off `&& sudo raspi-config nonint do_vnc 0`. Settings and PINs are kept.
3. Switch protection back on: Step 6.

The same goes for changing PINs or other settings permanently: switch protection off, restart, make the change, then switch it back on.

If the installer says *"SD card protection is on"*, do step 1 first.

## Seeing the screen from the laptop (optional)

The installer turns on remote screen access (VNC). Install **TigerVNC Viewer** (<https://github.com/TigerVNC/tigervnc/releases>, the `vncviewer64` file), connect to `touchdesk-green.local` or `touchdesk-blue.local`, and log in as `pi` / `pi`. (RealVNC Viewer now wants an account, which is why TigerVNC is suggested.)

## If something goes wrong

**The screen says "Searching for desk" and never connects.** Check the desk is on and the Pi's network lead is in. The screen and the desk must be on the same switch.

**A lightning-bolt symbol in the corner of the screen, or Power isn't "OK".** The Pi isn't getting enough power. Replace the PoE splitter or its lead first; a weak splitter has caused this before. Ideally use one rated 5 V 3 A or more.

**The Pi shows a "kernel panic" or won't start.** Almost always a worn-out SD card. Make a new card with this guide.

**The Pi won't start after switching protection on.** Put the card in the laptop, open the small drive called **bootfs**, open `cmdline.txt` in Notepad, delete the words `boot=overlay ` at the very start of the line (keep everything else on that one line), save, and put the card back.

**A forgotten installer PIN.** With protection on, just restart the Pi: PINs go back to what they were when protection was switched on.

**The installer says the bundle was made for a different Raspberry Pi OS version.** Imager has moved on to a newer Raspberry Pi OS than the offline installer was made for. Either:
- in Imager, choose an older *Raspberry Pi OS (64-bit)* release based on Debian 13 "Trixie", if it's offered; or
- for this one install, plug the Pi into a router with internet, then run:
  ```
  ssh -t pi@touchdesk-green.local "cd TouchDesk && rm -rf offline/debs && bash deploy/install.sh --room green --bluetooth && sudo raspi-config nonint do_vnc 0 && sudo reboot"
  ```
  It downloads what it needs once. Afterwards, back at the venue it runs offline as normal. To make a new offline installer from that Pi for next time, run `bash deploy/make-offline-bundle.sh` on it.

**Bluetooth audio is quiet.** Turn the phone's own volume up first. The Pi sets its own output to 100% every time TouchDesk starts. If it's still quiet, raise the channel's gain on the desk.

**Logs, for whoever is helping you:** `~/.local/state/touchdesk/touchdesk.log` on the Pi.
