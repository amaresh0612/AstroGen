"""
Single source for KP lookup tables and small time helpers used by analysis/*.

Arithmetic mirrors app.py (get_sublord_kp_standard, get_house_number_from_degree);
tests/test_app_parity.py asserts the two stay identical.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytz

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
SIGN_LORDS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}
NAKSHATRAS = [
    ("Ashwini", "Ketu"), ("Bharani", "Venus"), ("Krittika", "Sun"),
    ("Rohini", "Moon"), ("Mrigashira", "Mars"), ("Ardra", "Rahu"),
    ("Punarvasu", "Jupiter"), ("Pushya", "Saturn"), ("Ashlesha", "Mercury"),
    ("Magha", "Ketu"), ("Purva Phalguni", "Venus"), ("Uttara Phalguni", "Sun"),
    ("Hasta", "Moon"), ("Chitra", "Mars"), ("Swati", "Rahu"),
    ("Vishakha", "Jupiter"), ("Anuradha", "Saturn"), ("Jyeshtha", "Mercury"),
    ("Mula", "Ketu"), ("Purva Ashadha", "Venus"), ("Uttara Ashadha", "Sun"),
    ("Shravana", "Moon"), ("Dhanishta", "Mars"), ("Shatabhisha", "Rahu"),
    ("Purva Bhadrapada", "Jupiter"), ("Uttara Bhadrapada", "Saturn"), ("Revati", "Mercury"),
]
NAKSHATRA_NAMES = [n for n, _ in NAKSHATRAS]
NAK_WIDTH = 360.0 / 27.0

VIMSHOTTARI_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
VIMSHOTTARI_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
VIMSHOTTARI_TOTAL = 120

VARA_LORDS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]  # Sunday first

# Day-eighth slot (1–8 from sunrise) per weekday, Sunday first
RAHU_SLOTS = [8, 2, 7, 5, 6, 4, 3]
YAMA_SLOTS = [5, 4, 3, 2, 1, 7, 6]
GULIKA_SLOTS = [7, 6, 5, 4, 3, 2, 1]


def sign_of(lon: float) -> str:
    return SIGNS[int(float(lon) % 360.0 // 30) % 12]


def nak_star_sub(lon: float) -> tuple[str, str, str]:
    """(nakshatra, star lord, sub lord) — same boundaries as app.get_sublord_kp_standard."""
    arc = float(lon) % 360.0
    nak_idx = min(int(arc / NAK_WIDTH), 26)
    name, star = NAKSHATRAS[nak_idx]
    inside_min = (arc - nak_idx * NAK_WIDTH) * 60.0
    start = VIMSHOTTARI_ORDER.index(star)
    cum = 0.0
    sub = VIMSHOTTARI_ORDER[(start + 8) % 9]
    for i in range(9):
        k = (start + i) % 9
        cum += (VIMSHOTTARI_YEARS[k] / float(VIMSHOTTARI_TOTAL)) * 800.0
        if inside_min <= cum:
            sub = VIMSHOTTARI_ORDER[k]
            break
    return name, star, sub


def astro_weekday(d) -> int:
    """Sunday=0 … Saturday=6."""
    return (d.weekday() + 1) % 7


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def jd_to_utc_datetime(jd: float) -> datetime:
    """Julian Day (UT) → aware UTC datetime."""
    return datetime.fromtimestamp((jd - 2440587.5) * 86400.0, tz=timezone.utc)


def localize(tz_name: str, naive: datetime) -> datetime:
    """
    Attach a timezone to a wall-clock time. DST gaps/overlaps resolve to
    standard time; use ``is_ambiguous_local`` to detect and surface them.
    """
    return pytz.timezone(tz_name).localize(naive, is_dst=False)


def is_ambiguous_local(tz_name: str, naive: datetime) -> bool:
    """True if the wall-clock time is skipped or repeated by a DST transition."""
    try:
        pytz.timezone(tz_name).localize(naive, is_dst=None)
        return False
    except (pytz.exceptions.AmbiguousTimeError, pytz.exceptions.NonExistentTimeError):
        return True
