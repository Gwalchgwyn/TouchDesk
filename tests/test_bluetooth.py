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
