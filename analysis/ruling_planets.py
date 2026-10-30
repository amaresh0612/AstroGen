"""
Ruling Planets (RP) calculation engine.

Computes the complete KP Ruling Planet set for a given date, time, and location:
    Day Lord
    Ascendant Sign Lord
    Ascendant Star Lord
    Ascendant Sub Lord
    Moon Sign Lord
    Moon Star Lord
    Moon Sub Lord

Then cross-matches the RP list against event significators to identify
timing strength per topic.

IMPORTANT: RP is time AND location dependent. The reference_time parameter
must always be the explicit moment of the query — not a date-level average.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import swisseph as swe
import pytz

SIGNS = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces",
]
SIGN_LORDS = {
    "Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon",
    "Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars",
    "Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter",
}
NAKSHATRAS = [
    ("Ashwini","Ketu"),("Bharani","Venus"),("Krittika","Sun"),
    ("Rohini","Moon"),("Mrigashira","Mars"),("Ardra","Rahu"),
    ("Punarvasu","Jupiter"),("Pushya","Saturn"),("Ashlesha","Mercury"),
    ("Magha","Ketu"),("Purva Phalguni","Venus"),("Uttara Phalguni","Sun"),
    ("Hasta","Moon"),("Chitra","Mars"),("Swati","Rahu"),
    ("Vishakha","Jupiter"),("Anuradha","Saturn"),("Jyeshtha","Mercury"),
    ("Mula","Ketu"),("Purva Ashadha","Venus"),("Uttara Ashadha","Sun"),
    ("Shravana","Moon"),("Dhanishta","Mars"),("Shatabhisha","Rahu"),
    ("Purva Bhadrapada","Jupiter"),("Uttara Bhadrapada","Saturn"),("Revati","Mercury"),
]
VIMSHOTTARI_ORDER  = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
VIMSHOTTARI_YEARS  = [7, 20, 6, 10, 7, 18, 16, 19, 17]
VARA_LORDS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]


def _nak_and_sublord(lon: float) -> tuple[str, str, str]:
    """Return (nakshatra_name, star_lord, sub_lord) for a longitude."""
    nak_width = 360.0 / 27.0
    nak_idx   = int(lon / nak_width) % 27
    nak_name, star_lord = NAKSHATRAS[nak_idx]

    # Sublord via KP arc-minute method
    nak_minutes   = nak_width * 60.0
    offset_min    = (lon % nak_width) * 60.0
    total_years   = sum(VIMSHOTTARI_YEARS)
    start_idx     = VIMSHOTTARI_ORDER.index(star_lord)
    cumulative    = 0.0
    sub_lord      = star_lord
    for i in range(9):
        idx = (start_idx + i) % 9
        sub_minutes = (VIMSHOTTARI_YEARS[idx] / total_years) * nak_minutes
        cumulative += sub_minutes
        if offset_min <= cumulative:
            sub_lord = VIMSHOTTARI_ORDER[idx]
            break
    return nak_name, star_lord, sub_lord


def _sign_and_lord(lon: float) -> tuple[str, str]:
    sign = SIGNS[int(lon / 30) % 12]
    return sign, SIGN_LORDS[sign]


def compute_ruling_planets(
    query_dt_utc: datetime,
    lat: float,
    lng: float,
    tz_name: str = "Asia/Kolkata",
    significators: Optional[dict] = None,
    topic_houses: Optional[dict] = None,
) -> dict:
    """
    Compute full KP Ruling Planets for a given UTC datetime and location.

    Parameters
    ----------
    query_dt_utc  : Explicit UTC datetime of the query moment.
    lat, lng      : Geographic coordinates of the query location.
    tz_name       : Timezone for display.
    significators : Optional dict of planet → signified_houses (from natal ref).
    topic_houses  : Optional dict of topic → list[int] (from event_houses.py).

    Returns
    -------
    dict with all RP components and event match analysis.
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    jd = swe.julday(query_dt_utc.year, query_dt_utc.month, query_dt_utc.day,
                    query_dt_utc.hour + query_dt_utc.minute / 60.0 + query_dt_utc.second / 3600.0)

    # Ascendant
    cusps_trop, ascmc_trop = swe.houses(jd, lat, lng, b"P")
    ay = swe.get_ayanamsa_ut(jd)
    asc_sid = (ascmc_trop[0] - ay) % 360.0

    asc_sign, asc_sign_lord = _sign_and_lord(asc_sid)
    _, asc_star_lord, asc_sub_lord = _nak_and_sublord(asc_sid)

    # Moon
    moon_res, _ = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    moon_lon = float(moon_res[0]) % 360.0
    moon_sign, moon_sign_lord = _sign_and_lord(moon_lon)
    _, moon_star_lord, moon_sub_lord = _nak_and_sublord(moon_lon)

    # Day Lord
    local_dt = datetime.fromtimestamp(
        (jd - 2440587.5) * 86400.0, tz=pytz.timezone(tz_name)
    )
    py_weekday = local_dt.weekday()      # Mon=0 … Sun=6
    astro_day  = (py_weekday + 1) % 7   # Sun=0 … Sat=6
    day_lord   = VARA_LORDS[astro_day]

    # Build RP list (deduplicated, preserving priority order)
    rp_ordered = [day_lord, asc_sign_lord, asc_star_lord, asc_sub_lord,
                  moon_sign_lord, moon_star_lord, moon_sub_lord]
    rp_list: list[str] = []
    seen: set[str] = set()
    for p in rp_ordered:
        if p and p not in seen:
            rp_list.append(p)
            seen.add(p)

    # Cross-match RPs against event significators — house-overlap analysis
    rp_event_match: dict[str, dict] = {}
    if significators and topic_houses:
        for topic, houses in topic_houses.items():
            event_set = set(houses)
            rows_for_topic = []
            for rp in rp_list:
                sig = significators.get(rp, {})
                natal_sigs = list(sig.get("signified_houses", []))
                overlap = sorted(set(natal_sigs) & event_set)
                if overlap:
                    rows_for_topic.append({
                        "planet":       rp,
                        "natal_sigs":   sorted(natal_sigs),
                        "event_houses": sorted(event_set),
                        "overlap":      overlap,
                        "strength": (
                            "Strong"  if len(overlap) >= 2
                            else "Moderate"
                        ),
                    })
            # Summary: planet names with overlap for quick reference
            rp_event_match[topic] = {
                "event_houses": sorted(event_set),
                "matching_rp":  rows_for_topic,
                "rp_names":     [r["planet"] for r in rows_for_topic],
                "rp_support": (
                    "Strong"      if sum(1 for r in rows_for_topic if r["strength"] == "Strong") >= 2
                    else "Active" if rows_for_topic
                    else "Weak"
                ),
            }
            # Backward-compatible alias — prefer rp_support in new code
            rp_event_match[topic]["verdict"] = rp_event_match[topic]["rp_support"]

    # Local time string for reference
    ref_time_str = local_dt.strftime("%Y-%m-%d %H:%M %Z")

    return {
        "reference_time":      ref_time_str,
        "reference_lat":       round(lat, 4),
        "reference_lng":       round(lng, 4),
        "reference_location":  tz_name,
        "ascendant_longitude": round(asc_sid, 4),
        "ascendant_sign":      asc_sign,
        "day_lord":            day_lord,
        "ascendant_sign_lord": asc_sign_lord,
        "ascendant_star_lord": asc_star_lord,
        "ascendant_sub_lord":  asc_sub_lord,
        "moon_longitude":      round(moon_lon, 4),
        "moon_sign":           moon_sign,
        "moon_sign_lord":      moon_sign_lord,
        "moon_star_lord":      moon_star_lord,
        "moon_sub_lord":       moon_sub_lord,
        "rp_list":             rp_list,
        "rp_event_match":      rp_event_match,
    }
