"""
Shared nakshatra / pada calculation — matches app.py get_nakshatra_and_pada logic.

Uses explicit offset within the nakshatra (not longitude % nak_width) to avoid
boundary/indexing errors at pada transitions.
"""
from __future__ import annotations

import math

from analysis.kp_constants import NAKSHATRAS

NAK_WIDTH = 13.0 + (20.0 / 60.0)  # 13°20'
PADA_WIDTH = NAK_WIDTH / 4.0      # 3°20'
_EPS = 1e-6


def get_nakshatra_and_pada(deg360: float) -> tuple[str, str, int, int]:
    """
    Return (nak_name, nak_lord, nak_index, pada) for sidereal longitude 0–360°.
    """
    arc = float(deg360) % 360.0
    nak_index = int(math.floor(arc / NAK_WIDTH))
    if nak_index >= 27:
        nak_index = 26

    nak_name, nak_lord = NAKSHATRAS[nak_index]
    inside_nak = arc - (nak_index * NAK_WIDTH)

    if inside_nak + _EPS >= NAK_WIDTH:
        inside_nak = 0.0
        nak_index = min(26, nak_index + 1)
        nak_name, nak_lord = NAKSHATRAS[nak_index]

    fraction = inside_nak / PADA_WIDTH
    if abs(round(fraction) - fraction) <= (_EPS / PADA_WIDTH):
        fraction = round(fraction)

    pada = int(math.floor(fraction)) + 1
    if pada < 1:
        pada = 1
    elif pada > 4:
        pada = 4

    return nak_name, nak_lord, nak_index, pada


def moon_nakshatra_dict(moon_lon: float) -> dict:
    """Return nakshatra dict with name, lord, pada, index."""
    name, lord, idx, pada = get_nakshatra_and_pada(moon_lon)
    return {
        "name": name,
        "lord": lord,
        "pada": pada,
        "index": idx,
    }
