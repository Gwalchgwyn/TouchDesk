import json

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from conftest import pump, wait_until
from touchdesk import config as cfgmod
from touchdesk.bluetooth import BluetoothBackend, create_backend
from touchdesk.session import DeskSession
from touchdesk.ui.main_window import MainWindow


@pytest.fixture
def make_window(qapp, desk, tmp_path):
    made = []

    def _make(extra=None, bt=None):
        data = {"desk": {"ip": "127.0.0.1", "port": desk.port}}
        data.update(extra or {})
        path = tmp_path / "config.json"
        path.write_text(json.dumps(data))
        cfg = cfgmod.load(path)
        s = DeskSession(cfg)
        w = MainWindow(cfg, s, bt)
        w.resize(800, 480)
        w.show()
        s.start()
        assert wait_until(lambda: s.online and all(c.level is not None for c in s.channels))
        made.append((w, s))
        return w, s

    yield _make
    for w, s in made:
        s.stop()
        w.close()


def type_pin(w, pin):
    for d in pin:
        w.lock.pad._add(d)
    w.lock.pad._submit()


def test_starts_locked_and_unlocks(make_window):
    w, s = make_window()
    assert w.stack.currentIndex() == w.LOCK
    assert not w.lock.back.isVisible()
    type_pin(w, "1234")
    assert w.stack.currentIndex() == w.MIXER


def test_wrong_pins_lock_out_then_recover(make_window):
    w, s = make_window({"security": {"max_attempts": 2, "lockout_seconds": 1}})
    type_pin(w, "1111")
    assert "1 try left" in w.lock.pad.message.text()
    type_pin(w, "2222")
    assert all(not k.isEnabled() for k in w.lock.pad.keys)
    type_pin(w, "1234")  # ignored during the lockout
    assert w.stack.currentIndex() == w.LOCK
    assert wait_until(lambda: w.lock.pad.keys[0].isEnabled(), timeout=3)
    type_pin(w, "1234")
    assert w.stack.currentIndex() == w.MIXER


def test_admin_pin_opens_settings(make_window):
    w, s = make_window()
    type_pin(w, "000000")
    assert w.stack.currentIndex() == w.ADMIN


def test_pin_digits_are_hidden(make_window):
    w, s = make_window()
    w.lock.pad._add("1")
    w.lock.pad._add("2")
    assert "1" not in w.lock.pad.dots.text() and w.lock.pad.dots.text().count("●") == 2


def test_no_pin_mode_starts_unlocked(make_window):
    w, s = make_window({"security": {"pin_enabled": False}})
    assert w.stack.currentIndex() == w.MIXER
    assert not w.b_lock.isVisible()


def test_dragging_a_fader_moves_the_desk(make_window, desk):
    w, s = make_window({"security": {"pin_enabled": False}})
    strip = w.mixer.strips[1]
    strip.fader.setValue(500)  # what a drag does
    assert wait_until(lambda: desk.state["/ch/02/mix/fader"] == pytest.approx(0.375))
    assert strip.readout.text() == "5"


def test_on_off_button(make_window, desk):
    w, s = make_window({"security": {"pin_enabled": False}})
    strip = w.mixer.strips[0]
    assert strip.mute.text() == "ON"
    QTest.mouseClick(strip.mute, Qt.MouseButton.LeftButton)
    assert wait_until(lambda: desk.state["/ch/01/mix/on"] == 0)
    assert strip.mute.text() == "OFF"
    QTest.mouseClick(strip.mute, Qt.MouseButton.LeftButton)
    assert wait_until(lambda: desk.state["/ch/01/mix/on"] == 1)


def test_screen_follows_desk(make_window, desk):
    w, s = make_window({"security": {"pin_enabled": False}})
    desk.external_change("/ch/03/mix/fader", 0.375)
    desk.external_change("/ch/03/mix/on", 0)
    strip = w.mixer.strips[2]
    assert wait_until(lambda: strip.fader.value() == 500 and strip.mute.text() == "OFF")


def test_mute_all_works_even_when_locked(make_window, desk):
    w, s = make_window()
    assert w.stack.currentIndex() == w.LOCK
    QTest.mouseClick(w.b_muteall, Qt.MouseButton.LeftButton)
    assert wait_until(lambda: all(desk.state[f"/ch/0{n}/mix/on"] == 0 for n in range(1, 5)))


def test_controls_disabled_while_desk_offline(make_window, desk, monkeypatch):
    from touchdesk import session as sess

    monkeypatch.setattr(sess, "OFFLINE_AFTER_S", 0.5)
    w, s = make_window({"security": {"pin_enabled": False}})
    s._probe_timer.setInterval(150)
    desk.silent = True
    assert wait_until(lambda: not s.online, 3)
    assert not w.mixer.strips[0].isEnabled()
    assert w.mixer.banner.isVisible()
    assert "offline" in w.status.text().lower()
    desk.silent = False
    assert wait_until(lambda: s.online, 4)
    assert w.mixer.strips[0].isEnabled() and not w.mixer.banner.isVisible()


def test_auto_lock_after_inactivity(make_window):
    w, s = make_window()
    type_pin(w, "1234")
    w.idle.start(100)  # pretend the 15 minutes have passed
    pump(0.3)
    assert w.stack.currentIndex() == w.LOCK


def test_touching_resets_auto_lock(make_window):
    w, s = make_window()
    type_pin(w, "1234")
    w.idle.start(300)
    pump(0.2)
    QTest.mousePress(w.mixer.strips[0].name, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    QTest.mouseRelease(w.mixer.strips[0].name, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
    pump(0.2)
    assert w.stack.currentIndex() == w.MIXER
    assert w.idle.remainingTime() > 60_000


def test_admin_changes_are_saved(make_window, tmp_path):
    w, s = make_window()
    type_pin(w, "000000")
    w.admin._toggle_levels()
    w.admin._cycle_timeout()
    w.admin._change_pin("pin")
    for pin in ("5678", "5678"):
        w.admin.pin_pad.digits = pin
        w.admin.pin_pad._submit()
    saved = json.loads((tmp_path / "config.json").read_text())
    assert saved["level_display"] == "db"
    assert saved["security"]["lock_after_minutes"] == 30
    assert saved["security"]["pin"] == "5678"
    assert w.mixer.strips[0].readout.text().endswith("dB")


def test_new_pin_must_match_and_differ_from_admin(make_window):
    w, s = make_window()
    w.admin._change_pin("pin")
    w.admin.pin_pad.digits = "000000"
    w.admin.pin_pad._submit()
    assert "different" in w.admin.pin_pad.message.text()
    w.admin.pin_pad.digits = "1111"
    w.admin.pin_pad._submit()
    w.admin.pin_pad.digits = "2222"
    w.admin.pin_pad._submit()
    assert "match" in w.admin.pin_pad.message.text()
    assert s.config.security["pin"] == "1234"


def test_desk_names(make_window, desk):
    w, s = make_window({"use_desk_names": True, "security": {"pin_enabled": False}})
    assert wait_until(lambda: w.mixer.strips[0].name.text() == "Ch 1")
    desk.external_change("/ch/01/config/name", "Lectern")
    assert wait_until(lambda: w.mixer.strips[0].name.text() == "Lectern")


def test_finding_desks_from_settings(make_window, desk):
    w, s = make_window()
    found = []
    s.desks_found.connect(found.append)
    s.find_desks(wait_ms=800)
    assert wait_until(lambda: found, 3)
    # broadcast may not loop back in every test environment; the call must not break anything
    assert s.online


def test_bluetooth_without_a_phone_does_not_crash(make_window):
    """TouchDesk 1.x crashed at start-up when no phone was connected."""
    bt = BluetoothBackend()
    w, s = make_window({"security": {"pin_enabled": False}}, bt=bt)
    from touchdesk.ui.screens import BluetoothPanel

    panel = w.mixer.findChild(BluetoothPanel)
    assert panel is not None and not panel.playpause.isEnabled()
    assert w.stack.currentIndex() == w.MIXER


def test_bluetooth_backend_off_when_disabled():
    assert create_backend(False) is None


def test_blue_room_controls_channels_5_to_8(make_window, desk):
    chans = [{"label": f"#{i}", "type": "ch", "number": 4 + i} for i in range(1, 5)]
    w, s = make_window({"channels": chans, "display": {"title": "Blue Room"},
                        "security": {"pin_enabled": False}})
    w.mixer.strips[0].fader.setValue(500)
    assert wait_until(lambda: desk.state["/ch/05/mix/fader"] == pytest.approx(0.375))
    assert desk.state["/ch/01/mix/fader"] == 0.75, "Green Room's channels untouched"
    QTest.mouseClick(w.b_muteall, Qt.MouseButton.LeftButton)
    assert wait_until(lambda: all(desk.state[f"/ch/0{n}/mix/on"] == 0 for n in range(5, 9)))
    assert all(desk.state[f"/ch/0{n}/mix/on"] == 1 for n in range(1, 5)), "Mute All stays in its own room"


def test_long_press_reaches_installer_pin_and_can_go_back(make_window):
    w, s = make_window({"security": {"pin_enabled": False}})
    w._admin_requested()
    assert w.stack.currentIndex() == w.LOCK
    assert w.lock.back.isVisible(), "must be able to back out without a PIN"
    type_pin(w, "000000")
    assert w.stack.currentIndex() == w.ADMIN
    w.admin.closed.emit()
    assert w.stack.currentIndex() == w.MIXER


def test_offline_banner_fits_its_text(make_window, desk, monkeypatch):
    """Found on the real Pi: the banner kept its pre-layout size and clipped the text."""
    from touchdesk import session as sess

    monkeypatch.setattr(sess, "OFFLINE_AFTER_S", 0.5)
    w, s = make_window({"security": {"pin_enabled": False}})
    s._probe_timer.setInterval(150)
    desk.silent = True
    assert wait_until(lambda: not s.online, 3)
    w.resize(1024, 600)
    pump(0.2)
    b = w.mixer.banner
    lines = b.text().count("\n") + 1
    assert b.height() >= lines * b.fontMetrics().height()
    assert b.y() + b.height() <= w.mixer.height()


def test_forget_phones_needs_two_taps(make_window):
    class BT(BluetoothBackend):
        available = True
        remembered = 4
        forgotten = 0

        def forget_all(self):
            BT.forgotten += 1
            n, self.remembered = self.remembered, 0
            return n

    bt = BT()
    w, s = make_window({"security": {"pin_enabled": False}}, bt=bt)
    a = w.admin
    a.refresh()
    assert a.b_forget.text() == "Forget phones (4)"
    a.b_forget.click()
    assert BT.forgotten == 0 and "Tap again" in a.b_forget.text()
    a.b_forget.click()
    assert BT.forgotten == 1 and a.b_forget.text() == "Forgot 4 phones"


@pytest.mark.parametrize("flags,expect", [("0x0", "OK"), ("0x50000", "since power-on"), ("0x50005", "NOW"), ("", "")])
def test_power_status(monkeypatch, flags, expect):
    import subprocess
    import types

    from touchdesk.ui import screens

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/vcgencmd" if flags else None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=f"throttled={flags}\n"))
    result = screens.power_status()
    assert (expect in result) if expect else result == ""
