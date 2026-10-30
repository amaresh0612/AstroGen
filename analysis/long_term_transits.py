"""
Long-term transit window engine.

Tracks Jupiter, Saturn, Rahu, and Ketu sign-change dates over a horizon
(default 5 years) and enriches each window with:
    - Transit house in the natal chart
    - Transit nakshatra and star/sub lord
    - Relevant natal planets in the transit area
    - Relevant event houses impacted

Ingress timestamps are deterministic for the same:
  ephemeris (Swiss) · ayanamsa (Lahiri) · planet · exact UT sign crossing.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import swisseph as swe

SIGNS = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces",
]
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
VIMSHOTTARI_ORDER = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
VIMSHOTTARI_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
TOTAL_YEARS = sum(VIMSHOTTARI_YEARS)

PLANET_IDS = {
    "Jupiter": swe.JUPITER,
    "Saturn":  swe.SATURN,
    "Rahu":    swe.TRUE_NODE,
}

TRANSIT_ENGINE_META = {
    "ephemeris": "Swiss Ephemeris (swisseph)",
    "ayanamsa": "Lahiri",
    "timezone_display": "Asia/Kolkata",
    "ingress_convention": (
        "Exact UT sign-boundary crossing; ingress_date = UTC calendar date"
    ),
}


def _sid_lon(jd: float, body: int) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    res, _ = swe.calc_ut(jd, body, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return float(res[0]) % 360.0


def _nak_star_sub(lon: float) -> tuple[str, str, str]:
    nak_width  = 360.0 / 27.0
    nak_idx    = int(lon / nak_width) % 27
    name, star = NAKSHATRAS[nak_idx]
    nak_min    = nak_width * 60.0
    offset_min = (lon % nak_width) * 60.0
    s_idx      = VIMSHOTTARI_ORDER.index(star)
    cum        = 0.0
    sub        = star
    for i in range(9):
        idx = (s_idx + i) % 9
        sub_min = (VIMSHOTTARI_YEARS[idx] / TOTAL_YEARS) * nak_min
        cum += sub_min
        if offset_min <= cum:
            sub = VIMSHOTTARI_ORDER[idx]
            break
    return name, star, sub


def _transit_house(transit_lon: float, asc_lon: float) -> int:
    """Whole-sign house of transit planet relative to natal ascendant."""
    asc_sign_idx = int(asc_lon / 30) % 12
    tr_sign_idx  = int(transit_lon / 30) % 12
    return ((tr_sign_idx - asc_sign_idx) % 12) + 1


def _relevant_natal_planets(transit_house: int, natal_planets: dict) -> list[str]:
    """Planets natally in or owning the transit house."""
    result = []
    for pname, pdata in natal_planets.items():
        if pdata.get("house") == transit_house:
            result.append(pname)
    return result


def _jd(d: date, hour: float = 12.0) -> float:
    """Julian day at given UT hour."""
    return swe.julday(d.year, d.month, d.day, hour)


def _planet_lon(pname: str, pid: Optional[int], jd: float) -> float:
    if pname == "Ketu":
        rahu_lon = _sid_lon(jd, swe.TRUE_NODE)
        return (rahu_lon + 180.0) % 360.0
    return _sid_lon(jd, pid)


def _sign_idx(lon: float) -> int:
    return int(lon / 30) % 12


def _refine_ingress_day(
    pname: str,
    pid: Optional[int],
    day_lo: date,
    day_hi: date,
    new_sign_idx: int,
) -> date:
    """Binary-search the first day in [day_lo, day_hi] where planet is in new_sign at noon UT."""
    lo, hi = day_lo, day_hi
    while (hi - lo).days > 0:
        mid = lo + timedelta(days=(hi - lo).days // 2)
        lon = _planet_lon(pname, pid, _jd(mid))
        if _sign_idx(lon) == new_sign_idx:
            hi = mid
        else:
            lo = mid + timedelta(days=1)
    return hi


def _refine_ingress_jd(
    pname: str,
    pid: Optional[int],
    ingress_day: date,
    new_sign_idx: int,
) -> float:
    """
    Binary-search exact UT Julian Day of sign crossing near ingress_day.

    Deterministic for the same ephemeris / ayanamsa / planet.
    """
    jd_lo = _jd(ingress_day - timedelta(days=1), 12.0)
    jd_hi = _jd(ingress_day, 12.0)

    if _sign_idx(_planet_lon(pname, pid, jd_lo)) == new_sign_idx:
        jd_lo = _jd(ingress_day - timedelta(days=2), 0.0)
    if _sign_idx(_planet_lon(pname, pid, jd_hi)) != new_sign_idx:
        jd_hi = _jd(ingress_day + timedelta(days=1), 12.0)

    for _ in range(48):
        mid = (jd_lo + jd_hi) / 2.0
        if _sign_idx(_planet_lon(pname, pid, mid)) == new_sign_idx:
            jd_hi = mid
        else:
            jd_lo = mid
    return jd_hi


def _jd_to_utc_iso(jd: float) -> str:
    """Convert Julian Day (UT) to ISO-8601 UTC string."""
    year, month, day, hour_f = swe.revjul(jd, swe.GREG_CAL)
    hours = int(hour_f)
    minutes = int((hour_f - hours) * 60)
    seconds = int(round((((hour_f - hours) * 60) - minutes) * 60))
    if seconds >= 60:
        seconds = 0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        hours += 1
    dt = datetime(int(year), int(month), int(day), hours % 24, minutes, min(seconds, 59))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_iso_to_local(utc_iso: str, tz_name: str = "Asia/Kolkata") -> str:
    try:
        import pytz
        utc_dt = datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
        local_dt = utc_dt.astimezone(pytz.timezone(tz_name))
        return local_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        return utc_iso


def _scan_slow_ingresses(
    natal_asc_lon: float,
    natal_planets: dict,
    from_date: date,
    end_date: date,
    include_interpretation: bool,
    event_house_map: Optional[dict] = None,
) -> list[dict]:
    """Shared ingress scanner — single authoritative date engine."""
    results: list[dict] = []
    planets_to_scan = {
        "Jupiter": swe.JUPITER,
        "Saturn":  swe.SATURN,
        "Rahu":    swe.TRUE_NODE,
        "Ketu":    None,
    }
    calc_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for pname, pid in planets_to_scan.items():
        scan_start = from_date - timedelta(days=7)
        cur = scan_start
        prev_sign_idx = -1

        while cur <= end_date:
            lon = _planet_lon(pname, pid, _jd(cur))
            sign_idx = _sign_idx(lon)

            if sign_idx != prev_sign_idx and prev_sign_idx != -1:
                window_start = cur - timedelta(days=7)
                ingress_day = _refine_ingress_day(
                    pname, pid, window_start, cur, sign_idx,
                )
                jd_ing = _refine_ingress_jd(pname, pid, ingress_day, sign_idx)
                utc_iso = _jd_to_utc_iso(jd_ing)
                # Canonical display date = UTC calendar date of exact crossing
                ingress_date = date.fromisoformat(utc_iso[:10])

                if ingress_date >= from_date:
                    ing_lon = _planet_lon(pname, pid, jd_ing)
                    nak, star_lord, sub_lord = _nak_star_sub(ing_lon)
                    tr_house = _transit_house(ing_lon, natal_asc_lon)
                    rel_planets = _relevant_natal_planets(tr_house, natal_planets)
                    local_iso = _utc_iso_to_local(
                        utc_iso, TRANSIT_ENGINE_META["timezone_display"],
                    )

                    entry: dict = {
                        "planet":                 pname,
                        "from_sign":              SIGNS[prev_sign_idx],
                        "to_sign":                SIGNS[sign_idx],
                        "ingress_date":           ingress_date.isoformat(),
                        "ingress_datetime_utc":   utc_iso,
                        "ingress_datetime_local": local_iso,
                        "ingress_jd_ut":          round(jd_ing, 8),
                        "ephemeris":              TRANSIT_ENGINE_META["ephemeris"],
                        "ayanamsa":               TRANSIT_ENGINE_META["ayanamsa"],
                        "timezone":               TRANSIT_ENGINE_META["timezone_display"],
                        "calculation_timestamp":  calc_ts,
                        "transit_house":          tr_house,
                        "transit_nakshatra":      nak,
                        "star_lord":              star_lord,
                        "sub_lord":               sub_lord,
                        "transit_longitude":      round(ing_lon, 4),
                    }
                    if include_interpretation:
                        impacted_topics: list[str] = []
                        relevant_houses: list[int] = []
                        if event_house_map:
                            for topic, houses in event_house_map.items():
                                if tr_house in houses:
                                    impacted_topics.append(topic)
                                    for h in houses:
                                        if h not in relevant_houses:
                                            relevant_houses.append(h)
                        notes_parts = []
                        if rel_planets:
                            notes_parts.append(
                                f"Natal {', '.join(rel_planets)} in this house"
                            )
                        if star_lord:
                            notes_parts.append(
                                f"Star lord {star_lord} activates its natal significators"
                            )
                        if sub_lord:
                            notes_parts.append(
                                f"Sub lord {sub_lord} determines outcome"
                            )
                        if impacted_topics:
                            notes_parts.append(f"Impacts: {', '.join(impacted_topics)}")
                        entry.update({
                            "relevant_natal_planets": rel_planets,
                            "relevant_event_houses":  sorted(set(relevant_houses)),
                            "impacted_topics":        impacted_topics,
                            "notes":                  "; ".join(notes_parts) if notes_parts else "",
                        })
                    else:
                        entry["conjunct_natal_planets"] = rel_planets

                    results.append(entry)

            prev_sign_idx = sign_idx
            cur += timedelta(days=1)

    results.sort(key=lambda x: x.get("ingress_datetime_utc") or x["ingress_date"])
    return results


def compute_long_term_transits(
    natal_asc_lon: float,
    natal_planets: dict,
    from_date: Optional[date] = None,
    horizon_years: int = 5,
    event_house_map: Optional[dict] = None,
) -> list[dict]:
    """
    Compute Jupiter / Saturn / Rahu / Ketu sign-change windows
    enriched with KP context.
    """
    if from_date is None:
        from_date = date.today()

    end_date = date(from_date.year + horizon_years, from_date.month, from_date.day)
    return _scan_slow_ingresses(
        natal_asc_lon, natal_planets, from_date, end_date,
        include_interpretation=True,
        event_house_map=event_house_map,
    )


def compute_long_term_transits_raw(
    natal_asc_lon: float,
    natal_planets: dict,
    from_date: Optional[date] = None,
    horizon_years: int = 5,
) -> list[dict]:
    """
    Raw slow-planet ingress data — calculations only, no interpretation fields.
    """
    if from_date is None:
        from_date = date.today()

    end_date = date(from_date.year + horizon_years, from_date.month, from_date.day)
    return _scan_slow_ingresses(
        natal_asc_lon, natal_planets, from_date, end_date,
        include_interpretation=False,
    )
