"""
60-day almanac builder.

Orchestrates all date-specific calculation engines across a configurable
number of days (default 60) and returns a list of AlmanacRow dicts.

This is an optional inspection/cache output. It is NOT the core prediction
path — use analysis/context.py for single-date PredictionContext.

Engines called per day (all from analysis/):
    panchanga    → Tithi, Vara, Nak, Yoga, Karana, Sunrise, Sunset
    hora         → Unequal Hora sequence
    muhurtha     → Rahu Kalam, Yamaganda, Gulika (reuses app.py function)
    tarabala     → Tara + Chandrashtama
    dasha_fine   → Active MD/AD/PD (locked) + SD/Prana
    numerology_daily → Day number
    ruling_planets   → Day Lord + Moon-based RPs (date-level, no ascendant)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import swisseph as swe
import pytz

from analysis.panchanga import compute_panchanga, _rise_set, _jd_to_local
from analysis.hora import compute_hora
from analysis.tarabala import compute_tarabala_full
from analysis.dasha_fine import get_dasha_state
from analysis.numerology_daily import compute_numerology_daily

VARA_LORDS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]
_VIM_ORDER = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
_VIM_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
_VIM_TOTAL = 120


def _local_antardashas(maha: dict) -> list:
    try:
        si = _VIM_ORDER.index(maha["lord"])
    except ValueError:
        si = 0
    my = float(maha.get("years", 17))
    cur = maha["start"] if isinstance(maha["start"], datetime) else \
          datetime.strptime(str(maha["start"])[:10], "%Y-%m-%d")
    result = []
    for i in range(9):
        idx = (si + i) % 9
        years = my * _VIM_YEARS[idx] / _VIM_TOTAL
        end = cur + timedelta(days=int(years * 365))
        result.append({"lord": _VIM_ORDER[idx], "start": cur, "end": end, "years": years})
        cur = end
    return result


def _local_pratyantardashas(ad: dict) -> list:
    try:
        si = _VIM_ORDER.index(ad["lord"])
    except ValueError:
        si = 0
    ay = float(ad["years"])
    cur = ad["start"]
    result = []
    for i in range(9):
        idx = (si + i) % 9
        years = ay * _VIM_YEARS[idx] / _VIM_TOTAL
        end = cur + timedelta(days=int(years * 365))
        result.append({"lord": _VIM_ORDER[idx], "start": cur, "end": end, "years": years})
        cur = end
    return result


def _find_active_ad_pd(natal_ref: dict, query_dt: datetime) -> tuple[dict, dict]:
    """Walk full_timeline to find active AD and PD at query_dt (no app.py import)."""
    def _parse(v) -> datetime:
        if isinstance(v, datetime):
            return v
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(v)[:19], fmt)
            except Exception:
                pass
        return datetime.min

    def _fmt(dt) -> str:
        return dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]

    try:
        timeline = natal_ref.get("dasha", {}).get("full_timeline", [])
        for maha in timeline:
            if _parse(maha["start"]) <= query_dt <= _parse(maha["end"]):
                for ad in _local_antardashas(maha):
                    if ad["start"] <= query_dt <= ad["end"]:
                        ad_dict = {"lord": ad["lord"],
                                   "start": _fmt(ad["start"]),
                                   "end":   _fmt(ad["end"])}
                        for prat in _local_pratyantardashas(ad):
                            if prat["start"] <= query_dt <= prat["end"]:
                                return ad_dict, {"lord": prat["lord"],
                                                 "start": _fmt(prat["start"]),
                                                 "end":   _fmt(prat["end"])}
                        return ad_dict, {}
    except Exception:
        pass
    dasha = natal_ref.get("dasha", {})
    return dasha.get("locked_ad", {}), dasha.get("locked_pd", {})


def _fmt_window(start_jd: Optional[float], end_jd: Optional[float], tz_name: str) -> dict:
    def _s(jd):
        if jd is None:
            return "--:--"
        dt = _jd_to_local(jd, tz_name)
        return dt.strftime("%H:%M") if dt else "--:--"
    return {"start": _s(start_jd), "end": _s(end_jd)}


def _compute_kalam_windows(date_val: date, lat: float, lng: float, tz_name: str) -> dict:
    """Compute Rahu Kalam, Yamaganda, Gulika from scratch using same logic as app.py."""
    jd_rise = _rise_set(date_val, lat, lng, swe.SUN, 1, tz_name)
    jd_set  = _rise_set(date_val, lat, lng, swe.SUN, 2, tz_name)

    if jd_rise is None or jd_set is None:
        empty = {"start": "--:--", "end": "--:--"}
        return {"rahu_kalam": empty, "yamaganda": empty, "gulika_kalam": empty}

    day_secs = (jd_set - jd_rise) * 86400.0
    slot_jd  = day_secs / 8.0 / 86400.0

    py_weekday = date_val.weekday()
    astro_day  = (py_weekday + 1) % 7

    RAHU_SLOTS   = [8, 2, 7, 5, 6, 4, 3]
    YAMA_SLOTS   = [5, 4, 3, 2, 1, 7, 6]
    GULIKA_SLOTS = [7, 6, 5, 4, 3, 2, 1]

    def window(n: int) -> dict:
        s = jd_rise + (n - 1) * slot_jd
        return _fmt_window(s, s + slot_jd, tz_name)

    return {
        "rahu_kalam": window(RAHU_SLOTS[astro_day]),
        "yamaganda":  window(YAMA_SLOTS[astro_day]),
        "gulika_kalam": window(GULIKA_SLOTS[astro_day]),
        "jd_sunrise":  jd_rise,
        "jd_sunset":   jd_set,
    }


def build_almanac(
    natal_ref: dict,
    from_date: Optional[date] = None,
    days: int = 60,
    query_lat: Optional[float] = None,
    query_lng: Optional[float] = None,
    query_tz: Optional[str] = None,
) -> list[dict]:
    """
    Build a list of almanac row dicts for 'days' days starting from from_date.

    Parameters
    ----------
    natal_ref  : Loaded natal_ref.json dict.
    from_date  : Start date (defaults to today).
    days       : Number of days to compute (default 60).
    query_lat  : Override latitude for dynamic calculations (current location).
    query_lng  : Override longitude for dynamic calculations (current location).
    query_tz   : Override timezone for dynamic calculations (current location).

    If query_lat/lng/tz are provided they are used for Panchanga, Kalam, and Hora.
    The natal_ref location is used ONLY for natal chart data.

    Returns
    -------
    list of dicts — one per day, matching AlmanacRow schema.
    """
    if from_date is None:
        from_date = date.today()

    birth    = natal_ref.get("birth", {})
    # Use query location for dynamic calculations; fall back to natal location
    lat      = query_lat  if query_lat  is not None else float(birth.get("lat", 20.0))
    lng      = query_lng  if query_lng  is not None else float(birth.get("lng", 78.0))
    tz_name  = query_tz   if query_tz   is not None else birth.get("tz", "Asia/Kolkata")
    num_data = natal_ref.get("numerology", {})
    name_num = int(num_data.get("name_number", 0))
    life_path= int(num_data.get("life_path", 0))

    # Natal Moon info for Tarabala
    natal_moon     = natal_ref.get("planets", {}).get("Moon", {})
    natal_moon_nak = natal_moon.get("nakshatra", "Ashwini")
    natal_moon_sign= natal_moon.get("sign", "Aries")

    # Locked dasha for dasha_fine — compute AD/PD dynamically from full_timeline
    dasha_section = natal_ref.get("dasha", {})
    locked_md = dasha_section.get("locked_md", {})
    # AD/PD may be absent from older natal refs; compute dynamically
    _ref_ad, _ref_pd = _find_active_ad_pd(natal_ref, datetime.now())

    rows: list[dict] = []

    for i in range(days):
        day = from_date + timedelta(days=i)
        query_dt = datetime(day.year, day.month, day.day, 6, 0, 0)  # 6 AM reference

        try:
            # Panchanga
            panch = compute_panchanga(day, lat, lng, tz_name)

            # Kalam windows
            kalam = _compute_kalam_windows(day, lat, lng, tz_name)
            jd_sunrise = kalam.get("jd_sunrise")
            jd_sunset  = kalam.get("jd_sunset")

            # Next day sunrise for night hora
            next_day = day + timedelta(days=1)
            jd_next_sunrise = _rise_set(next_day, lat, lng, swe.SUN, 1, tz_name)

            # Hora
            hora_data: dict = {}
            if jd_sunrise and jd_sunset and jd_next_sunrise:
                hora_data = compute_hora(day, jd_sunrise, jd_sunset, jd_next_sunrise, tz_name)

            # Transit Moon for Tarabala
            swe.set_sid_mode(swe.SIDM_LAHIRI)
            jd_ref = jd_sunrise or swe.julday(day.year, day.month, day.day, 6.0)
            moon_res, _ = swe.calc_ut(jd_ref, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
            transit_moon_lon = float(moon_res[0]) % 360.0
            transit_moon_nak = panch.get("moon_nakshatra", "Ashwini")
            transit_moon_sign= panch.get("moon_sign", "Aries")

            tara = compute_tarabala_full(
                natal_moon_nak, natal_moon_sign, transit_moon_nak, transit_moon_sign
            )

            # Dasha state — AD stays constant across 60 days; PD may shift
            locked_ad, locked_pd = _find_active_ad_pd(natal_ref, query_dt)
            if not locked_ad:
                locked_ad = _ref_ad
            if not locked_pd:
                locked_pd = _ref_pd
            dasha_state = get_dasha_state(locked_md, locked_ad, locked_pd, query_dt)

            # Numerology
            num = compute_numerology_daily(day, name_num, life_path)

            # Day lord
            astro_day = (day.weekday() + 1) % 7
            day_lord = VARA_LORDS[astro_day]

            # Hora sequence — all 24 (12 day + 12 night), preserving period tag
            hora_seq = []
            for slot in (hora_data.get("all_horas") or [])[:24]:
                hora_seq.append({
                    "lord":   slot["lord"],
                    "start":  slot.get("start", ""),
                    "end":    slot.get("end", ""),
                    "period": slot.get("period", "day"),
                })

            rows.append({
                "date":     day.isoformat(),
                "weekday":  panch.get("weekday", ""),
                "vara":     panch.get("vara", day_lord),
                "sunrise":  panch.get("sunrise") or "--:--",
                "sunset":   panch.get("sunset")  or "--:--",
                "moonrise": panch.get("moonrise"),
                "moonset":  panch.get("moonset"),
                # Panchanga
                "tithi":         panch.get("tithi", ""),
                "tithi_number":  panch.get("tithi_number", 0),
                "moon_nakshatra": panch.get("moon_nakshatra", ""),
                "moon_pada":      panch.get("moon_pada", 0),
                "moon_sign":      panch.get("moon_sign", ""),
                "yoga":           panch.get("yoga", ""),
                "karana":         panch.get("karana", ""),
                # Kalam
                "rahu_kalam":   kalam.get("rahu_kalam",   {"start":"--:--","end":"--:--"}),
                "yamaganda":    kalam.get("yamaganda",    {"start":"--:--","end":"--:--"}),
                "gulika_kalam": kalam.get("gulika_kalam", {"start":"--:--","end":"--:--"}),
                # Tarabala
                "tara_number":   tara.get("tara_number", 0),
                "tara_category": tara.get("tara_category", ""),
                "chandrashtama": tara.get("chandrashtama", False),
                # Numerology
                "day_number":   num.get("day_number", 0),
                # Dasha
                "active_md":    dasha_state.get("md_lord", ""),
                "active_ad":    dasha_state.get("ad_lord", ""),
                "active_pd":    dasha_state.get("pd_lord", ""),
                "active_pd_end":dasha_state.get("pd_end", ""),
                # Hora
                "hora_sequence": hora_seq,
                # Day-level Ruling Planets
                "day_lord":       day_lord,
                "moon_sign_lord": panch.get("moon_star_lord", ""),  # sign lord derived from sign
                "moon_star_lord": panch.get("moon_star_lord", ""),
                "moon_sub_lord":  "",  # sublord calculated per full RP in context.py
            })

        except Exception as e:
            rows.append({
                "date":  day.isoformat(),
                "error": str(e),
            })

    return rows
