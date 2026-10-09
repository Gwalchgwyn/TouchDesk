"""Conversion between Behringer fader floats (0.0-1.0) and decibels.

X-Air and X32 desks use the same four-segment fader law:

    float  0.0    -> -inf dB (off)
    float  0.0625 -> -60 dB
    float  0.25   -> -30 dB
    float  0.5    -> -10 dB
    float  0.75   ->   0 dB (unity)
    float  1.0    -> +10 dB
"""

from __future__ import annotations

import math

MIN_DB = -90.0
MAX_DB = 10.0


def float_to_db(value: float) -> float:
    """Desk fader float -> dB. Returns -inf for a fully closed fader."""
    v = min(max(float(value), 0.0), 1.0)
    if v <= 0.0:
        return -math.inf
    if v >= 0.5:
        return 40.0 * v - 30.0
    if v >= 0.25:
        return 80.0 * v - 50.0
    if v >= 0.0625:
        return 160.0 * v - 70.0
    return 480.0 * v - 90.0


def db_to_float(db: float) -> float:
    """dB -> desk fader float, clamped to the desk's range."""
    if db is None or math.isinf(db) and db < 0:
        return 0.0
    if db >= MAX_DB:
        return 1.0
    if db >= -10.0:
        return (db + 30.0) / 40.0
    if db >= -30.0:
        return (db + 50.0) / 80.0
    if db >= -60.0:
        return (db + 70.0) / 160.0
    if db > MIN_DB:
        return (db + 90.0) / 480.0
    return 0.0


def format_db(db: float) -> str:
    if math.isinf(db) or db <= MIN_DB:
        return "-∞"
    whole = round(db)
    return "0 dB" if whole == 0 else f"{whole:+d} dB"
