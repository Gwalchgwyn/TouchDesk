"""Loading, validating and saving TouchDesk's settings file (JSON)."""

from __future__ import annotations

import copy
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from touchdesk.desks import Target, get_profile

log = logging.getLogger(__name__)

DEFAULT_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "touchdesk" / "config.json"

DEFAULTS: dict = {
    "desk": {
        "model": "xair",
        # "auto" = search the network for the desk. Or give a fixed IP address.
        "ip": "auto",
        # null = the model's normal port (10024 for X Air, 10023 for X32).
        "port": None,
        # With ip "auto" and several desks on the network, pick the one with this name.
        "name": "",
    },
    "channels": [
        {"label": "#1", "type": "ch", "number": 1},
        {"label": "#2", "type": "ch", "number": 2},
        {"label": "#3", "type": "ch", "number": 3},
        {"label": "#4", "type": "ch", "number": 4, "icon": "bluetooth"},
    ],
    # Show the names typed into the desk itself instead of the labels above.
    "use_desk_names": False,
    # The loudest any fader can go, in dB. 0 = unity, the same as TouchDesk 1.x.
    "max_level_db": 0,
    # "0-10" (the TouchDesk 1.x style) or "db".
    "level_display": "0-10",
    "security": {
        "pin_enabled": True,
        "pin": "1234",
        # Entering this PIN on the lock screen opens the installer settings.
        "admin_pin": "000000",
        # 0 = never lock automatically.
        "lock_after_minutes": 15,
        "max_attempts": 5,
        "lockout_seconds": 60,
    },
    "bluetooth": {
        "enabled": True,
    },
    "display": {
        # Shown in the top bar, e.g. the venue's name. Empty = "TouchDesk".
        "title": "",
        "fullscreen": True,
        "hide_cursor": True,
    },
}

CHANNEL_KINDS = {"ch", "aux", "fx", "bus", "main"}
LEVEL_DISPLAYS = {"0-10", "db"}


class ConfigError(ValueError):
    pass


@dataclass
class ChannelConfig:
    label: str
    target: Target
    icon: str = ""


@dataclass
class Config:
    data: dict
    path: Path | None = None
    channels: list[ChannelConfig] = field(default_factory=list)

    # Convenience accessors ---------------------------------------------
    @property
    def desk_model(self) -> str:
        return self.data["desk"]["model"]

    @property
    def desk_ip(self) -> str:
        return str(self.data["desk"]["ip"]).strip()

    @property
    def desk_port(self) -> int:
        port = self.data["desk"]["port"]
        return int(port) if port else get_profile(self.desk_model).default_port

    @property
    def security(self) -> dict:
        return self.data["security"]

    def save(self, path: Path | None = None) -> None:
        """Write atomically so a power cut can't leave a half-written file."""
        target = Path(path or self.path or DEFAULT_PATH)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
        self.path = target
        log.info("Saved settings to %s", target)


def _merge(defaults: dict, user: dict) -> dict:
    out = copy.deepcopy(defaults)
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def from_dict(user: dict, path: Path | None = None) -> Config:
    if not isinstance(user, dict):
        raise ConfigError("The settings file must contain a JSON object { ... }")
    data = _merge(DEFAULTS, user)
    errors: list[str] = []

    try:
        profile = get_profile(data["desk"]["model"])
    except ValueError as e:
        errors.append(str(e))
        profile = None

    sec = data["security"]
    for key in ("pin", "admin_pin"):
        sec[key] = str(sec[key])
        if not sec[key].isdigit() or not 4 <= len(sec[key]) <= 8:
            errors.append(f"security.{key} must be 4 to 8 digits")
    if sec["pin"] == sec["admin_pin"]:
        errors.append("security.pin and security.admin_pin must be different")

    if data["level_display"] not in LEVEL_DISPLAYS:
        errors.append(f"level_display must be one of {sorted(LEVEL_DISPLAYS)}")
    try:
        mx = float(data["max_level_db"])
        if not -30 <= mx <= 10:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("max_level_db must be a number between -30 and 10")

    channels: list[ChannelConfig] = []
    raw = data["channels"]
    if not isinstance(raw, list) or not raw:
        errors.append("channels must be a list with at least one channel")
        raw = []
    if len(raw) > 16:
        errors.append("TouchDesk supports at most 16 channels on screen")
    for i, ch in enumerate(raw, start=1):
        if not isinstance(ch, dict):
            errors.append(f"channel {i} must be an object")
            continue
        kind = ch.get("type", "ch")
        if kind not in CHANNEL_KINDS:
            errors.append(f"channel {i}: type must be one of {sorted(CHANNEL_KINDS)}")
            continue
        if profile and kind not in profile.kinds:
            errors.append(f"channel {i}: {profile.label} has no '{kind}' channels")
            continue
        try:
            number = int(ch.get("number", 1))
            if number < 1:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"channel {i}: number must be a whole number of 1 or more")
            continue
        label = str(ch.get("label") or f"#{number}")
        channels.append(ChannelConfig(label=label, target=Target(kind, number), icon=str(ch.get("icon", ""))))

    if errors:
        raise ConfigError("Problems in the settings file:\n  - " + "\n  - ".join(errors))
    return Config(data=data, path=path, channels=channels)


def load(path: Path | str | None = None) -> Config:
    """Load settings. A missing file gives the built-in defaults (and writes them out)."""
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        log.warning("No settings file at %s - using defaults", p)
        cfg = from_dict({}, p)
        try:
            cfg.save(p)
        except OSError as e:
            log.warning("Could not write default settings: %s", e)
        return cfg
    try:
        with open(p, encoding="utf-8") as f:
            user = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{p} is not valid JSON (line {e.lineno}, column {e.colno}): {e.msg}") from None
    return from_dict(user, p)
