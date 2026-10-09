import json
import math

import pytest

from conftest import wait_until
from touchdesk import config as cfgmod
from touchdesk.desks import Target, XAirProfile, X32Profile, get_profile
from touchdesk.desks.faderlaw import db_to_float, float_to_db, format_db


# ---------------------------------------------------------------- fader law
def test_unity_is_075():
    # TouchDesk 1.x capped faders at 99/132 = 0.75, which is exactly 0 dB.
    assert float_to_db(0.75) == pytest.approx(0.0)
    assert db_to_float(0) == pytest.approx(0.75)


@pytest.mark.parametrize("db", [-89, -60, -45, -30, -20, -10, -5, 0, 5, 10])
def test_db_roundtrip(db):
    assert float_to_db(db_to_float(db)) == pytest.approx(db)


def test_extremes():
    assert float_to_db(0) == -math.inf
    assert db_to_float(-math.inf) == 0.0
    assert db_to_float(99) == 1.0
    assert format_db(-math.inf) == "-∞"
    assert format_db(0.0) == "0 dB"


# ---------------------------------------------------------------- profiles
def test_xair_addresses():
    p = XAirProfile()
    assert p.fader_address(Target("ch", 1)) == "/ch/01/mix/fader"
    assert p.on_address(Target("ch", 12)) == "/ch/12/mix/on"
    assert p.name_address(Target("ch", 3)) == "/ch/03/config/name"
    assert p.fader_address(Target("main")) == "/lr/mix/fader"
    assert p.on_address(Target("aux")) == "/rtn/aux/mix/on"
    assert p.fader_address(Target("bus", 2)) == "/bus/2/mix/fader"


def test_x32_addresses():
    p = X32Profile()
    assert p.default_port == 10023
    assert p.fader_address(Target("main")) == "/main/st/mix/fader"
    assert p.on_address(Target("aux", 3)) == "/auxin/03/mix/on"


def test_parse_info_variants():
    p = get_profile("xair")
    a = p.parse_info(["192.168.1.5", "XR12-12-34-56", "XR12", "1.22"])
    assert a == {"ip": "192.168.1.5", "name": "XR12-12-34-56", "model": "XR12", "firmware": "1.22"}
    b = p.parse_info(["server_version=1.0", "ip_address=10.0.0.2", "device_name=Hall", "device_model=XR18", "device_version=1.17"])
    assert b["ip"] == "10.0.0.2" and b["name"] == "Hall" and b["model"] == "XR18" and b["firmware"] == "1.17"


# ---------------------------------------------------------------- config
def test_defaults_match_v1():
    c = cfgmod.from_dict({})
    assert [ch.target.number for ch in c.channels] == [1, 2, 3, 4]
    assert c.desk_port == 10024
    assert c.security["pin"] == "1234"


def test_bad_config_lists_every_problem():
    with pytest.raises(cfgmod.ConfigError) as e:
        cfgmod.from_dict({"desk": {"model": "yamaha"}, "security": {"pin": "12"}, "level_display": "loud"})
    msg = str(e.value)
    assert "yamaha" in msg and "pin" in msg and "level_display" in msg


def test_missing_file_writes_defaults(tmp_path):
    p = tmp_path / "config.json"
    c = cfgmod.load(p)
    assert p.exists() and c.desk_model == "xair"
    c.data["security"]["pin"] = "4321"
    c.save()
    assert json.loads(p.read_text())["security"]["pin"] == "4321"


def test_invalid_json_is_explained(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"desk": {"ip": "1.2.3.4",}}')
    with pytest.raises(cfgmod.ConfigError, match="line 1"):
        cfgmod.load(p)


# ---------------------------------------------------------------- session
def make_session(desk, **over):
    from touchdesk.session import DeskSession

    data = {"desk": {"ip": "127.0.0.1", "port": desk.port}}
    data.update(over)
    s = DeskSession(cfgmod.from_dict(data))
    return s


def test_connects_and_reads_current_state(qapp, desk):
    desk.state["/ch/02/mix/fader"] = 0.5
    desk.state["/ch/03/mix/on"] = 0
    s = make_session(desk)
    s.start()
    assert wait_until(lambda: s.online and s.channels[2].on is False and s.channels[1].level == 0.5)
    assert s.channels[0].on is True
    assert s.channels[0].desk_name == "Ch 1"
    assert desk.sent_to("/xremote"), "should subscribe for live updates"
    s.stop()


def test_moving_fader_sends_osc(qapp, desk):
    s = make_session(desk)
    s.start()
    assert wait_until(lambda: s.online)
    s.set_position(0, 1.0)  # top of travel = 0 dB by default
    assert wait_until(lambda: desk.state["/ch/01/mix/fader"] == pytest.approx(0.75))
    s.set_position(0, 0.5)
    assert wait_until(lambda: desk.state["/ch/01/mix/fader"] == pytest.approx(0.375))
    s.set_on(0, False)
    assert wait_until(lambda: desk.state["/ch/01/mix/on"] == 0)
    s.stop()


def test_max_level_setting(qapp, desk):
    s = make_session(desk, max_level_db=-10)
    s.start()
    assert wait_until(lambda: s.online)
    s.set_position(1, 1.0)
    assert wait_until(lambda: desk.state["/ch/02/mix/fader"] == pytest.approx(0.5))
    s.stop()


def test_changes_made_elsewhere_appear(qapp, desk):
    s = make_session(desk)
    s.start()
    assert wait_until(lambda: s.online and s.channels[0].level is not None)
    changed = []
    s.channel_changed.connect(changed.append)
    desk.external_change("/ch/01/mix/fader", 0.25)
    desk.external_change("/ch/04/mix/on", 0)
    assert wait_until(lambda: s.channels[0].level == 0.25 and s.channels[3].on is False)
    assert 0 in changed and 3 in changed
    s.stop()


def test_mute_all(qapp, desk):
    s = make_session(desk)
    s.start()
    assert wait_until(lambda: s.online)
    s.mute_all()
    assert wait_until(lambda: all(desk.state[f"/ch/0{n}/mix/on"] == 0 for n in range(1, 5)))
    assert desk.state["/ch/05/mix/on"] == 1, "channels not on screen must be left alone"
    s.stop()


def test_offline_and_recovery(qapp, desk, monkeypatch):
    from touchdesk import session as sess

    monkeypatch.setattr(sess, "OFFLINE_AFTER_S", 0.6)
    monkeypatch.setattr(sess, "PROBE_INTERVAL_MS", 200)
    s = make_session(desk)
    s.start()
    assert wait_until(lambda: s.online)
    desk.silent = True
    assert wait_until(lambda: not s.online, timeout=4)
    # while away, someone changes the desk
    desk.state["/ch/01/mix/fader"] = 0.1
    desk.silent = False
    assert wait_until(lambda: s.online and s.channels[0].level == 0.1, timeout=4)
    s.stop()


def test_auto_discovery_by_broadcast(qapp):
    """Needs broadcast to loop back locally; skipped where the network doesn't allow it."""
    from fake_desk import FakeDesk

    d = FakeDesk(port=0, host="0.0.0.0").start()
    try:
        from touchdesk.session import DeskSession

        s = DeskSession(cfgmod.from_dict({"desk": {"ip": "auto", "port": d.port}}))
        s.start()
        if not wait_until(lambda: s.online, timeout=4):
            pytest.skip("broadcast doesn't reach this machine's own sockets here")
        assert s.info.get("model") == "XR12"
        s.stop()
    finally:
        d.stop()
