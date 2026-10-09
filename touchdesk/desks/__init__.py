"""Desk profiles: how to talk OSC to each family of sound desk.

To add a new desk family, subclass DeskProfile and register it in PROFILES.
"""

from __future__ import annotations

from dataclasses import dataclass
import re




@dataclass(frozen=True)
class Target:
    """One thing a channel strip can control on the desk."""

    kind: str  # "ch", "aux", "fx", "bus", "main"
    number: int = 1


class DeskProfile:
    key = "base"
    label = "Generic"
    default_port = 10024
    # Seconds between /xremote renewals. Desks drop subscriptions after 10 s.
    keepalive_seconds = 8
    tested = False
    kinds: tuple[str, ...] = ("ch",)

    def base(self, t: Target) -> str:
        raise NotImplementedError

    def fader_address(self, t: Target) -> str:
        return f"{self.base(t)}/mix/fader"

    def on_address(self, t: Target) -> str:
        """1 = channel on (unmuted), 0 = muted."""
        return f"{self.base(t)}/mix/on"

    def name_address(self, t: Target) -> str:
        return f"{self.base(t)}/config/name"

    # Messages sent to keep receiving change notifications.
    def subscribe_messages(self) -> list[tuple[str, list]]:
        return [("/xremote", [])]

    # Message used to detect the desk and as a heartbeat.
    def probe_message(self) -> tuple[str, list]:
        return ("/xinfo", [])

    def probe_reply_address(self) -> str:
        return "/xinfo"

    @staticmethod
    def parse_info(args: list) -> dict:
        """Turn an /xinfo reply into {ip, name, model, firmware}.

        Different firmware versions format this differently (plain values or
        "key=value" strings), so be forgiving.
        """
        info = {"ip": "", "name": "", "model": "", "firmware": ""}
        plain = []
        for a in args:
            s = str(a)
            if "=" in s:
                k, _, v = s.partition("=")
                k = k.strip().lower()
                if "ip" in k:
                    info["ip"] = v
                elif "model" in k:
                    info["model"] = v
                elif "name" in k:
                    info["name"] = v
                elif "version" in k and "device" in k:
                    info["firmware"] = v
            else:
                plain.append(s)
        for s in plain:
            if not info["ip"] and re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", s):
                info["ip"] = s
            elif not info["model"] and re.fullmatch(r"(XR|MR|X|M)\d{2}\w*", s):
                info["model"] = s
            elif not info["name"] and not re.fullmatch(r"V?\d+(\.\d+)+", s):
                info["name"] = s
            elif re.fullmatch(r"V?\d+(\.\d+)+", s):
                info["firmware"] = s
        return info


class XAirProfile(DeskProfile):
    """Behringer X Air (XR12, XR16, XR18) and Midas MR12/MR18."""

    key = "xair"
    label = "Behringer X Air / Midas MR"
    default_port = 10024
    tested = True  # the original TouchDesk ran on an XR12
    kinds = ("ch", "aux", "fx", "bus", "main")

    def base(self, t: Target) -> str:
        if t.kind == "ch":
            return f"/ch/{t.number:02d}"
        if t.kind == "aux":
            return "/rtn/aux"
        if t.kind == "fx":
            return f"/rtn/{t.number}"
        if t.kind == "bus":
            return f"/bus/{t.number}"
        if t.kind == "main":
            return "/lr"
        raise ValueError(f"X Air desks have no '{t.kind}' channels")


class X32Profile(DeskProfile):
    """Behringer X32 / Midas M32. Same OSC style, different paths and port."""

    key = "x32"
    label = "Behringer X32 / Midas M32"
    default_port = 10023
    tested = False
    kinds = ("ch", "aux", "fx", "bus", "main")

    def base(self, t: Target) -> str:
        if t.kind == "ch":
            return f"/ch/{t.number:02d}"
        if t.kind == "aux":
            return f"/auxin/{t.number:02d}"
        if t.kind == "fx":
            return f"/fxrtn/{t.number:02d}"
        if t.kind == "bus":
            return f"/bus/{t.number:02d}"
        if t.kind == "main":
            return "/main/st"
        raise ValueError(f"X32 desks have no '{t.kind}' channels")


PROFILES: dict[str, DeskProfile] = {p.key: p for p in (XAirProfile(), X32Profile())}


def get_profile(key: str) -> DeskProfile:
    try:
        return PROFILES[key]
    except KeyError:
        raise ValueError(
            f"Unknown desk model '{key}'. Choose one of: {', '.join(PROFILES)}"
        ) from None
