"""
PredictionContext orchestrator.

This is the single entry point for all prediction work.
It accepts:
    - The locked natal reference (loaded from data/natal_ref.json)
    - A query date, time, location, and mode

It calls all analysis engines in the correct order and assembles a
PredictionContext dict — the one object passed to reports and AI prompts.

Dependency flow (strict):
    natal_ref.json
          ↓
    context.py  ← date + time + location
          ↓
    PredictionContext
          ↓
    reports/* / AI prompt

No report or AI layer should call individual engines directly.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pytz
import swisseph as swe

from analysis.panchanga import compute_panchanga, _rise_set
from analysis.hora import compute_hora, get_hora_at
from analysis.tarabala import compute_tarabala_full
from analysis.ruling_planets import compute_ruling_planets
from analysis.dasha_fine import get_dasha_state, get_active_sukshma, get_active_prana
from analysis.numerology_daily import compute_numerology_daily
from analysis.long_term_transits import compute_long_term_transits
from analysis.significator_strength import (
    compute_significator_strength_from_natal,
    get_planet_signification_summary,
)
from analysis.promise_denial import compute_all_topics
from analysis.nakshatra_utils import get_nakshatra_and_pada
from schemas.event_houses import EVENT_HOUSES

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
VIMSHOTTARI_ORDER = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
VIMSHOTTARI_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
TOTAL_YEARS = sum(VIMSHOTTARI_YEARS)
PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE,
}

DEFAULT_NATAL_REF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "natal_ref.json"
)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_natal_ref(path: Optional[str] = None) -> dict:
    """Load and return the locked natal reference JSON."""
    p = path or DEFAULT_NATAL_REF_PATH
    if not os.path.exists(p):
        raise FileNotFoundError(
            f"Natal reference not found at {p}. "
            "Run: python scripts/generate_natal_ref.py"
        )
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _compute_antardashas(maha_dasha: dict) -> list[dict]:
    """Compute 9 antardashas for a given mahadasha (pure math, no app.py import)."""
    maha_years = float(maha_dasha["years"])
    try:
        start_idx = VIMSHOTTARI_ORDER.index(maha_dasha["lord"])
    except ValueError:
        start_idx = 0
    antars = []
    cur = maha_dasha["start"]
    if isinstance(cur, str):
        cur = datetime.strptime(cur[:10], "%Y-%m-%d")
    for i in range(9):
        idx = (start_idx + i) % 9
        years = maha_years * VIMSHOTTARI_YEARS[idx] / TOTAL_YEARS
        days = int(years * 365)   # KP legacy formula: no rounding
        end = cur + timedelta(days=days)
        antars.append({"lord": VIMSHOTTARI_ORDER[idx],
                       "start": cur, "end": end, "years": years})
        cur = end
    return antars


def _compute_pratyantardashas(antar_dasha: dict) -> list[dict]:
    """Compute 9 pratyantardashas for a given antardasha."""
    antar_years = float(antar_dasha["years"])
    try:
        start_idx = VIMSHOTTARI_ORDER.index(antar_dasha["lord"])
    except ValueError:
        start_idx = 0
    pratas = []
    cur = antar_dasha["start"]
    if isinstance(cur, str):
        cur = datetime.strptime(cur[:10], "%Y-%m-%d")
    for i in range(9):
        idx = (start_idx + i) % 9
        years = antar_years * VIMSHOTTARI_YEARS[idx] / TOTAL_YEARS
        days = int(years * 365)
        end = cur + timedelta(days=days)
        pratas.append({"lord": VIMSHOTTARI_ORDER[idx],
                       "start": cur, "end": end, "years": years})
        cur = end
    return pratas


def _find_active_ad_pd_from_timeline(natal_ref: dict, query_dt: datetime) -> tuple[dict, dict]:
    """Walk the full dasha timeline to find active AD and PD at query_dt."""
    def _parse(v) -> datetime:
        if isinstance(v, datetime):
            return v
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(v), fmt)
            except Exception:
                pass
        return datetime.min

    def _fmt(v) -> str:
        return v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)[:10]

    try:
        timeline = natal_ref.get("dasha", {}).get("full_timeline", [])
        for maha in timeline:
            if _parse(maha["start"]) <= query_dt <= _parse(maha["end"]):
                for ad in _compute_antardashas(maha):
                    if ad["start"] <= query_dt <= ad["end"]:
                        ad_dict = {"lord": ad["lord"],
                                   "start": _fmt(ad["start"]),
                                   "end":   _fmt(ad["end"])}
                        for prat in _compute_pratyantardashas(ad):
                            if prat["start"] <= query_dt <= prat["end"]:
                                pd_dict = {"lord": prat["lord"],
                                           "start": _fmt(prat["start"]),
                                           "end":   _fmt(prat["end"])}
                                return ad_dict, pd_dict
                        return ad_dict, {}
    except Exception:
        pass
    dasha = natal_ref.get("dasha", {})
    return dasha.get("locked_ad", {}), dasha.get("locked_pd", {})


def _find_active_pd_from_timeline(natal_ref: dict, query_dt: datetime) -> dict:
    """Walk the full dasha timeline to find active PD at query_dt."""
    _, pd = _find_active_ad_pd_from_timeline(natal_ref, query_dt)
    return pd


def _compute_transits(jd: float, natal_ref: dict) -> dict:
    """Compute sidereal transit positions for all planets."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    natals   = natal_ref.get("planets", {})
    asc_lon  = float(natals.get("Sun", {}).get("longitude", 0))  # placeholder
    # Use natal asc from house 1 cusp
    house1   = natal_ref.get("houses", {}).get("1", {})
    asc_lon  = float(house1.get("cusp_degree", 0))

    result: dict = {}
    for pname, pid in PLANET_IDS.items():
        try:
            res, _ = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
            lon   = float(res[0]) % 360.0
            sign  = SIGNS[int(lon / 30) % 12]
            nak, star, sub = _nak_star_sub(lon)
            asc_sign_idx   = int(asc_lon / 30) % 12
            tr_sign_idx    = int(lon / 30) % 12
            tr_house        = ((tr_sign_idx - asc_sign_idx) % 12) + 1
            nat  = natals.get(pname, {})
            result[pname] = {
                "longitude":    round(lon, 4),
                "sign":         sign,
                "degree":       f"{int(lon % 30)}°{int((lon % 1)*60)}'",
                "nakshatra":    nak,
                "star_lord":    star,
                "sub_lord":     sub,
                "transit_house":tr_house,
                "natal_sign":   nat.get("sign", ""),
            }
        except Exception:
            pass

    if "Rahu" in result:
        ketu_lon = (result["Rahu"]["longitude"] + 180.0) % 360.0
        sign     = SIGNS[int(ketu_lon / 30) % 12]
        nak, star, sub = _nak_star_sub(ketu_lon)
        asc_sign_idx   = int(asc_lon / 30) % 12
        tr_sign_idx    = int(ketu_lon / 30) % 12
        tr_house        = ((tr_sign_idx - asc_sign_idx) % 12) + 1
        nat_k = natals.get("Ketu", {})
        result["Ketu"] = {
            "longitude":    round(ketu_lon, 4),
            "sign":         sign,
            "degree":       f"{int(ketu_lon % 30)}°{int((ketu_lon % 1)*60)}'",
            "nakshatra":    nak,
            "star_lord":    star,
            "sub_lord":     sub,
            "transit_house":tr_house,
            "natal_sign":   nat_k.get("sign", ""),
        }
    return result


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def build_prediction_context(
    natal_ref: dict,
    query_date: date,
    query_time_local: Optional[str] = "06:00:00",
    query_location: Optional[str] = None,
    query_lat: Optional[float] = None,
    query_lng: Optional[float] = None,
    query_tz: Optional[str] = None,
    query_mode: str = "DAILY",
    topics: Optional[list[str]] = None,
) -> dict:
    """
    Build the complete PredictionContext for a given date/time/location.

    Parameters
    ----------
    natal_ref       : Loaded natal_ref.json dict (locked source of truth).
    query_date      : The date being queried.
    query_time_local: Local time string "HH:MM:SS" (default "06:00:00").
    query_location  : Display name for location (defaults to birth place).
    query_lat/lng   : Override coordinates (defaults to birth coords).
    query_tz        : Timezone string (defaults to birth tz).
    query_mode      : "DAILY" / "MONTHLY" / "LONG_TERM" / "EVENT_SPECIFIC"
    topics          : For EVENT_SPECIFIC, list of topic keys.

    Returns
    -------
    PredictionContext dict.
    """
    birth   = natal_ref.get("birth", {})
    lat     = float(query_lat  if query_lat  is not None else birth.get("lat",  20.0))
    lng     = float(query_lng  if query_lng  is not None else birth.get("lng",  78.0))
    tz_name = query_tz or birth.get("tz", "Asia/Kolkata")
    location_label = query_location or birth.get("place", "")

    # Parse local datetime → UTC
    time_parts = (query_time_local or "06:00:00").split(":")
    hh, mm, ss = int(time_parts[0]), int(time_parts[1]), int(time_parts[2]) if len(time_parts) > 2 else 0
    tz_obj = pytz.timezone(tz_name)
    local_dt = tz_obj.localize(datetime(query_date.year, query_date.month, query_date.day, hh, mm, ss))
    utc_dt   = local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                    utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)

    # ── Panchanga ────────────────────────────────────────────────
    panch = compute_panchanga(query_date, lat, lng, tz_name)
    jd_rise     = panch.get("jd_sunrise")
    jd_set      = panch.get("jd_sunset")

    # ── Hora ─────────────────────────────────────────────────────
    from datetime import timedelta
    next_day    = query_date + timedelta(days=1)
    jd_next_rise = _rise_set(next_day, lat, lng, swe.SUN, 1)
    hora_data: dict = {}
    current_hora: dict = {}
    if jd_rise and jd_set and jd_next_rise:
        hora_data = compute_hora(query_date, jd_rise, jd_set, jd_next_rise, tz_name)
        slot = get_hora_at(hora_data, local_dt)
        if slot:
            current_hora = slot

    # ── Kalam ────────────────────────────────────────────────────
    def _fmt_jd(jd_v):
        if not jd_v:
            return "--:--"
        from analysis.panchanga import _jd_to_local
        dt = _jd_to_local(jd_v, tz_name)
        return dt.strftime("%H:%M") if dt else "--:--"

    def _kalam_window(slot_n: int, jd_rise_v, jd_set_v) -> dict:
        if not jd_rise_v or not jd_set_v:
            return {"start": "--:--", "end": "--:--"}
        day_secs = (jd_set_v - jd_rise_v) * 86400.0
        slot_jd  = day_secs / 8.0 / 86400.0
        s = jd_rise_v + (slot_n - 1) * slot_jd
        return {"start": _fmt_jd(s), "end": _fmt_jd(s + slot_jd)}

    astro_day = (query_date.weekday() + 1) % 7
    RAHU_SLOTS   = [8, 2, 7, 5, 6, 4, 3]
    YAMA_SLOTS   = [5, 4, 3, 2, 1, 7, 6]
    GULIKA_SLOTS = [7, 6, 5, 4, 3, 2, 1]
    kalam_state = {
        "rahu_kalam_start":  _kalam_window(RAHU_SLOTS[astro_day],   jd_rise, jd_set)["start"],
        "rahu_kalam_end":    _kalam_window(RAHU_SLOTS[astro_day],   jd_rise, jd_set)["end"],
        "yamaganda_start":   _kalam_window(YAMA_SLOTS[astro_day],   jd_rise, jd_set)["start"],
        "yamaganda_end":     _kalam_window(YAMA_SLOTS[astro_day],   jd_rise, jd_set)["end"],
        "gulika_start":      _kalam_window(GULIKA_SLOTS[astro_day], jd_rise, jd_set)["start"],
        "gulika_end":        _kalam_window(GULIKA_SLOTS[astro_day], jd_rise, jd_set)["end"],
    }

    # ── Transits ─────────────────────────────────────────────────
    transits = _compute_transits(jd, natal_ref)

    # ── Moon state ───────────────────────────────────────────────
    moon_t = transits.get("Moon", {})
    moon_lon = float(moon_t.get("longitude", 0))
    moon_sign = moon_t.get("sign", "")
    moon_nak, moon_star, moon_sub = _nak_star_sub(moon_lon)
    _, _, _, moon_pada = get_nakshatra_and_pada(moon_lon)
    moon_state = {
        "longitude":  moon_lon,
        "sign":       moon_sign,
        "nakshatra":  moon_nak,
        "pada":       moon_pada,
        "star_lord":  moon_star,
        "sub_lord":   moon_sub,
        "sign_lord":  SIGN_LORDS.get(moon_sign, ""),
    }

    # ── Tarabala ─────────────────────────────────────────────────
    natal_moon  = natal_ref.get("planets", {}).get("Moon", {})
    tara = compute_tarabala_full(
        natal_moon.get("nakshatra", "Ashwini"),
        natal_moon.get("sign", "Aries"),
        moon_nak,
        moon_sign,
    )

    # ── Significator strength (canonical — from locked matrix or compute) ──
    strength_map = compute_significator_strength_from_natal(natal_ref)

    # ── Ruling Planets ───────────────────────────────────────────
    rp = compute_ruling_planets(
        query_dt_utc=utc_dt,
        lat=lat,
        lng=lng,
        tz_name=tz_name,
        significators=natal_ref.get("significators", {}),
        topic_houses=EVENT_HOUSES,
    )

    # ── Dasha ────────────────────────────────────────────────────
    dasha_section = natal_ref.get("dasha", {})
    locked_md = dasha_section.get("locked_md", {})
    # Always compute AD and PD dynamically from the full timeline
    # (locked_ad/locked_pd in the JSON may be empty for older natal refs)
    locked_ad, locked_pd = _find_active_ad_pd_from_timeline(natal_ref, local_dt.replace(tzinfo=None))
    dasha_state = get_dasha_state(locked_md, locked_ad, locked_pd, local_dt.replace(tzinfo=None))

    # ── Numerology ───────────────────────────────────────────────
    num_natal = natal_ref.get("numerology", {})
    num = compute_numerology_daily(
        query_date,
        int(num_natal.get("name_number", 0)),
        int(num_natal.get("life_path", 0)),
    )

    # ── Promise/Denial ───────────────────────────────────────────
    topics_to_analyse = topics
    if query_mode == "EVENT_SPECIFIC" and not topics_to_analyse:
        topics_to_analyse = ["career", "marriage", "travel", "wealth"]
    elif query_mode in ("DAILY", "MONTHLY") and not topics_to_analyse:
        topics_to_analyse = ["career", "relationship", "wealth"]
    elif query_mode == "LONG_TERM" and not topics_to_analyse:
        topics_to_analyse = list(EVENT_HOUSES.keys())

    pd_list = compute_all_topics(
        natal_ref.get("planets", {}),
        natal_ref.get("houses", {}),
        natal_ref.get("cuspal_sublords", {}),
        strength_map,
        dasha_state.get("md_lord", ""),
        dasha_state.get("ad_lord", ""),
        dasha_state.get("pd_lord", ""),
        topics=topics_to_analyse or [],
        significators=natal_ref.get("significators", {}),
    )

    # ── Event evidence trail (Fix 4) ─────────────────────────────
    # For each topic, assemble the full KP decision chain so the AI
    # never has to re-derive it from raw numbers.
    rp_event_match = rp.get("rp_event_match", {})
    event_evidence: list[dict] = []
    for entry in pd_list:
        topic = entry["topic"]
        sc    = entry.get("score", {})
        pct10 = sc.get("pct10", 0.0)
        dark  = entry.get("dark_houses", [])

        # Confidence label derived from score + gaps
        if pct10 >= 8.0 and not dark:
            confidence = "High — all primary houses activated"
        elif pct10 >= 6.0 and len(dark) <= 1:
            confidence = f"Moderate — H{','.join(str(h) for h in dark)} not in active dasha" if dark else "Moderate"
        elif pct10 >= 4.0:
            confidence = "Low-Moderate — partial activation; watch sub-period"
        else:
            confidence = "Low — topic not strongly supported in current period"

        # RP overlap for this topic
        topic_rp = rp_event_match.get(topic, {})
        rp_rows = topic_rp.get("matching_rp", []) if isinstance(topic_rp, dict) else []

        # Transit triggers for this topic (houses of topic in active transits)
        required_h = set(entry.get("primary_houses", []))
        transit_triggers = [
            f"{pn} in H{td['transit_house']} ({td['sign']}, star {td['star_lord']}, sub {td['sub_lord']})"
            for pn, td in transits.items()
            if td.get("transit_house") in required_h
        ]

        event_evidence.append({
            "event":              topic.upper(),
            "topic_label":        entry["topic_label"],
            "required_houses":    entry["primary_houses"],
            "house_activation":   list(entry.get("house_activation", {}).values()),
            "csl_chain":          entry.get("csl_analyses", []),
            "natal_significators":{
                p: {"houses": sorted(hmap.keys()), "best_level": min(i["level"] for i in hmap.values())}
                for p, hmap in strength_map.items()
                if any(h in required_h and hmap[h]["level"] <= 3 for h in hmap)
            },
            "dasha_activation": {
                "md":             dasha_state.get("md_lord", ""),
                "ad":             dasha_state.get("ad_lord", ""),
                "pd":             dasha_state.get("pd_lord", ""),
                "covered_houses": entry.get("dasha_covered_houses", []),
                "missing_houses": entry.get("dasha_uncovered_houses", []),
                "detail":         entry.get("dasha_alignment", ""),
            },
            "ruling_planets":    rp.get("rp_list", []),
            "rp_event_overlap":  rp_rows,
            "transit_triggers":  transit_triggers,
            "score":             pct10,
            "manifestations":    entry.get("manifestations", []),
            "confidence":        confidence,
        })

    # ── Long-term transits (LONG_TERM / EVENT_SPECIFIC only) ──────
    lt_transits: list[dict] = []
    if query_mode in ("LONG_TERM", "EVENT_SPECIFIC"):
        house1_deg = float(natal_ref.get("houses", {}).get("1", {}).get("cusp_degree", 0))
        lt_transits = compute_long_term_transits(
            natal_asc_lon=house1_deg,
            natal_planets=natal_ref.get("planets", {}),
            from_date=query_date,
            horizon_years=5,
            event_house_map=EVENT_HOUSES,
        )

    # ── Build significator entries for context ────────────────────
    sig_entries: list[dict] = []
    for pname, house_map in strength_map.items():
        for h, info in house_map.items():
            sig_entries.append({
                "planet":         pname,
                "house":          h,
                "level":          info["level"],
                "level_label":    info["level_label"],
                "reasons":        info["reasons"],
            })
    sig_entries.sort(key=lambda x: (x["level"], x["house"]))

    # ── Panchanga state ───────────────────────────────────────────
    panchanga_state = {
        "date":           query_date.isoformat(),
        "tithi":          panch.get("tithi", ""),
        "tithi_number":   panch.get("tithi_number", 0),
        "vara":           panch.get("vara", ""),
        "moon_nakshatra": panch.get("moon_nakshatra", ""),
        "moon_pada":      panch.get("moon_pada", 0),
        "yoga":           panch.get("yoga", ""),
        "karana":         panch.get("karana", ""),
        "sunrise":        panch.get("sunrise") or "--:--",
        "sunset":         panch.get("sunset")  or "--:--",
        "moonrise":       panch.get("moonrise"),
        "moonset":        panch.get("moonset"),
    }

    # ── Hora state ────────────────────────────────────────────────
    hora_state = {
        "current_hora_lord":  current_hora.get("lord", ""),
        "current_hora_start": current_hora.get("start", ""),
        "current_hora_end":   current_hora.get("end", ""),
        "full_day_sequence":  hora_data.get("all_horas", []),
    }

    # ── Tarabala state ────────────────────────────────────────────
    tarabala_state = {
        "natal_moon_nakshatra":   natal_moon.get("nakshatra", ""),
        "transit_moon_nakshatra": moon_nak,
        "tara_number":            tara.get("tara_number", 0),
        "tara_category":          tara.get("tara_category", ""),
        "chandrashtama":          tara.get("chandrashtama", False),
        "suitability":            tara.get("suitability", ""),
    }

    # ── Numerology state ──────────────────────────────────────────
    numerology_state = {
        "name_number":       int(num_natal.get("name_number", 0)),
        "life_path":         int(num_natal.get("life_path", 0)),
        "day_number":        num.get("day_number", 0),
        "day_number_meaning":num.get("day_number_meaning", ""),
    }

    return {
        # Query metadata
        "query_date":     query_date.isoformat(),
        "query_time":     query_time_local or "06:00:00",
        "query_location": location_label,
        "query_lat":      lat,
        "query_lng":      lng,
        "query_mode":     query_mode,
        # From locked natal reference
        "birth_name":  birth.get("name", ""),
        "birth_date":  birth.get("date", ""),
        "birth_place": birth.get("place", ""),
        # Dynamic layers
        "dasha":           dasha_state,
        "transits":        transits,
        "moon":            moon_state,
        "ruling_planets":  rp,
        "panchanga":       panchanga_state,
        "kalam":           kalam_state,
        "hora":            hora_state,
        "tarabala":        tarabala_state,
        "numerology":      numerology_state,
        # Analysis layers
        "significators":        sig_entries,
        "long_term_transits":   lt_transits,
        "event_analyses":       pd_list,
        "event_evidence":       event_evidence,
    }
