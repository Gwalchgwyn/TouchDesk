"""Exercise the BlueZ code against a pretend D-Bus (no Bluetooth hardware here)."""

import types

from touchdesk import bluetooth


class FakeBus:
    def __init__(self, objects, calls):
        self.objects, self.calls = objects, calls

    def get_object(self, service, path):
        return path


def make_fake_dbus(state, calls):
    class Interface:
        def __init__(self, obj, iface):
            self.obj, self.iface = obj, iface

        def GetManagedObjects(self, timeout=None):
            if state.get("broken"):
                raise RuntimeError("org.freedesktop.DBus.Error.ServiceUnknown")
            return state["objects"]

        def __getattr__(self, name):
            def call(timeout=None):
                calls.append((self.obj, name))

            return call

    return types.SimpleNamespace(SystemBus=lambda: FakeBus(state, calls), Interface=Interface)


def test_no_phone_then_phone_connects(qapp, monkeypatch):
    state, calls = {"objects": {}}, []
    monkeypatch.setattr(bluetooth, "dbus", make_fake_dbus(state, calls))
    bt = bluetooth.create_backend(True)
    changes = []
    bt.changed.connect(lambda: changes.append(1))
    bt._poll()
    assert not bt.has_player and bt.device_name == ""
    bt.play()  # must be harmless with nothing connected
    assert calls == []

    state["objects"] = {
        "/org/bluez/hci0/dev_AA": {"org.bluez.Device1": {"Connected": True, "Alias": "Rhian's phone"}},
        "/org/bluez/hci0/dev_AA/player0": {
            "org.bluez.MediaPlayer1": {"Status": "playing", "Track": {"Title": "Song", "Artist": "Band"}}
        },
    }
    bt._poll()
    assert bt.has_player and bt.device_name == "Rhian's phone"
    assert bt.track["Title"] == "Song" and bt.status == "playing"
    assert changes
    bt.toggle()  # playing -> pause
    assert calls[-1] == ("/org/bluez/hci0/dev_AA/player0", "Pause")


def test_bluetooth_service_down_is_survivable(qapp, monkeypatch):
    state, calls = {"objects": {}, "broken": True}, []
    monkeypatch.setattr(bluetooth, "dbus", make_fake_dbus(state, calls))
    bt = bluetooth.create_backend(True)
    bt._poll()
    bt._poll()
    assert not bt.has_player
    state["broken"] = False
    state["objects"] = {"/p": {"org.bluez.MediaPlayer1": {"Status": "paused", "Track": {}}}}
    bt._poll()
    assert bt.has_player


# ---------------------------------------------------------------- artwork
def make_obex_dbus(log, fail_session=False):
    """Pretend obexd: sessions, thumbnails written to disk, transfer status."""

    class Iface:
        def __init__(self, obj, iface):
            self.obj, self.iface = obj, iface

        def CreateSession(self, address, opts, timeout=None):
            log.append(("CreateSession", address, opts["Target"], int(opts["PSM"])))
            if fail_session:
                raise RuntimeError("org.bluez.obex.Error.Failed")
            return "/org/bluez/obex/client/session1"

        def RemoveSession(self, path, timeout=None):
            log.append(("RemoveSession", path))

        def GetThumbnail(self, target, handle, timeout=None):
            log.append(("GetThumbnail", handle))
            with open(target, "wb") as f:
                f.write(b"\xff\xd8 fake jpeg")
            return "/org/bluez/obex/client/session1/transfer1", {}

        def Get(self, iface, prop, timeout=None):
            return "complete"

    class Bus:
        def __init__(self, *a, **k):
            pass

        def get_object(self, service, path):
            return path

    return types.SimpleNamespace(SessionBus=Bus, Interface=Iface, UInt16=int)


def wait_for(cond, timeout=3):
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def test_cover_art_fetched_per_track(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bluetooth, "dbus", make_obex_dbus(calls))
    art = bluetooth.CoverArt(tmp_path)
    art.update(("AA:BB", 4101, ""))  # player offers artwork; no image yet
    assert wait_for(lambda: art._session and not art._busy)
    assert calls[0] == ("CreateSession", "AA:BB", "bip-avrcp", 4101)
    art.update(("AA:BB", 4101, "1000001"))
    assert wait_for(lambda: art.path.endswith("1000001.jpg"))
    art.update(("AA:BB", 4101, "1000001"))  # same track: no second download
    assert [c[0] for c in calls].count("GetThumbnail") == 1
    art.update(("AA:BB", 4101, ""))  # track without artwork
    assert art.path == ""
    assert wait_for(lambda: not art._busy)
    art.update(None)  # phone gone
    assert wait_for(lambda: ("RemoveSession", "/org/bluez/obex/client/session1") in calls)


def test_phone_without_artwork_support_is_left_alone(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bluetooth, "dbus", make_obex_dbus(calls, fail_session=True))
    art = bluetooth.CoverArt(tmp_path)
    art.update(("AA:BB", 4101, ""))
    assert wait_for(lambda: not art._busy)
    art.update(("AA:BB", 4101, "123"))
    art.update(("AA:BB", 4101, "123"))
    assert [c[0] for c in calls] == ["CreateSession"], "don't keep retrying a phone that said no"
    assert art.path == ""


# ---------------------------------------------------------------- remembered phones
def make_paired_dbus(state, removed):
    class Interface:
        def __init__(self, obj, iface):
            self.obj, self.iface = obj, iface

        def GetManagedObjects(self, timeout=None):
            return state["objects"]

        def RemoveDevice(self, path, timeout=None):
            removed.append(path)
            state["objects"].pop(path, None)

    return types.SimpleNamespace(SystemBus=lambda: FakeBus(state, []), Interface=Interface)


def phone(n, connected=False):
    return (f"/org/bluez/hci0/dev_{n}", {"org.bluez.Device1": {
        "Address": f"AA:{n}", "Adapter": "/org/bluez/hci0", "Paired": True,
        "Connected": connected, "Alias": f"Phone {n}"}})


def test_remembers_at_most_the_limit_forgetting_oldest(qapp, monkeypatch, tmp_path):
    import time as _t

    state, removed = {"objects": dict([phone(1), phone(2), phone(3)])}, []
    monkeypatch.setattr(bluetooth, "dbus", make_paired_dbus(state, removed))
    bt = bluetooth.BlueZBackend(max_remembered=3, seen_file=tmp_path / "seen.json")
    bt._seen = {"AA:1": _t.time() - 100, "AA:2": _t.time() - 900, "AA:3": _t.time() - 50}
    bt._poll()
    assert bt.remembered == 3 and removed == []
    state["objects"].update(dict([phone(4, connected=True)]))  # a new phone pairs: 4 > limit
    bt._poll()
    assert removed == ["/org/bluez/hci0/dev_2"], "the least recently used phone goes"
    assert bt.remembered == 3
    assert "AA:4" in bt._seen, "connected phones are remembered as recently used"


def test_never_forgets_the_connected_phone(qapp, monkeypatch, tmp_path):
    state, removed = {"objects": dict([phone(1, connected=True), phone(2)])}, []
    monkeypatch.setattr(bluetooth, "dbus", make_paired_dbus(state, removed))
    bt = bluetooth.BlueZBackend(max_remembered=1, seen_file=tmp_path / "seen.json")
    bt._poll()
    assert removed == ["/org/bluez/hci0/dev_2"]


def test_forget_all(qapp, monkeypatch, tmp_path):
    state, removed = {"objects": dict([phone(1), phone(2), phone(3, connected=True)])}, []
    monkeypatch.setattr(bluetooth, "dbus", make_paired_dbus(state, removed))
    bt = bluetooth.BlueZBackend(seen_file=tmp_path / "seen.json")
    bt._poll()
    assert bt.forget_all() == 3
    assert state["objects"] == {}
