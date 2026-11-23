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

from analysis.kp_constants import SIGN_LORDS, VARA_LORDS, astro_weekday, jd_to_utc_datetime, nak_star_sub, sign_of

_nak_and_sublord = nak_star_sub


def _sign_and_lord(lon: float) -> tuple[str, str]:
    sign = sign_of(lon)
    return sign, SIGN_LORDS[sign]


def compute_ruling_planets(
    query_dt_utc: datetime,
    lat: float,
    lng: float,
    tz_name: str = "Asia/Kolkata",
    significators: Optional[dict] = None,
    topic_houses: Optional[dict] = None,
    location_label: Optional[str] = None,
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

    # Day Lord (civil weekday at the prediction location)
    local_dt = jd_to_utc_datetime(jd).astimezone(pytz.timezone(tz_name))
    day_lord = VARA_LORDS[astro_weekday(local_dt)]

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
        "reference_location":  location_label or f"{lat:.4f}, {lng:.4f}",
        "reference_tz":        tz_name,
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
