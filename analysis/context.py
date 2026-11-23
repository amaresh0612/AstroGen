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
    context.py  ← date + time + PREDICTION location (required, never natal)
          ↓
    PredictionContext
          ↓
    reports/* / AI prompt

No report or AI layer should call individual engines directly.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Optional

import pytz
import swisseph as swe

from analysis.panchanga import compute_panchanga, _rise_set, _jd_to_local
from analysis.hora import compute_hora, get_hora_at
from analysis.tarabala import compute_tarabala_full
from analysis.ruling_planets import compute_ruling_planets
from analysis.dasha_fine import get_dasha_state
from analysis.vimshottari import resolve_dasha
from analysis.numerology_daily import compute_numerology_daily
from analysis.long_term_transits import compute_long_term_transits
from analysis.significator_strength import (
    KP_METHODOLOGY, natal_significators, significators_are_current,
)
from analysis.fine_windows import fine_dasha_windows, lord_house_links
from analysis.promise_denial import compute_all_topics
from analysis.nakshatra_utils import get_nakshatra_and_pada
from analysis.kp_constants import (
    GULIKA_SLOTS, RAHU_SLOTS, SIGN_LORDS, YAMA_SLOTS,
    astro_weekday, is_ambiguous_local, localize, nak_star_sub,
)
from analysis.transits import TRANSIT_HOUSE_BASIS, transit_snapshot
from schemas.event_houses import EVENT_HOUSES

DEFAULT_NATAL_REF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "natal_ref.json"
)


class PredictionLocationRequired(ValueError):
    """Raised when a dynamic calculation is requested without a prediction location."""


def require_prediction_location(lat, lng, tz_name) -> tuple[float, float, str]:
    """Validate prediction coordinates. Natal location is never substituted."""
    if lat is None or lng is None or not tz_name:
        raise PredictionLocationRequired(
            "Prediction location (lat, lng, timezone) is required for Panchanga, Kalam, "
            "Hora and Ruling Planets. Birth location is never used as a default."
        )
    pytz.timezone(tz_name)
    return float(lat), float(lng), tz_name


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
    query_time_local: Local time string "HH:MM[:SS]" (default "06:00:00").
    query_location  : Display name of the prediction location.
    query_lat/lng   : Prediction coordinates — REQUIRED.
    query_tz        : Prediction timezone — REQUIRED.
    query_mode      : "DAILY" / "MONTHLY" / "LONG_TERM" / "EVENT_SPECIFIC"
    topics          : Topic keys to analyse (mode-specific default when None).

    Raises
    ------
    PredictionLocationRequired if lat/lng/tz are missing.
    """
    lat, lng, tz_name = require_prediction_location(query_lat, query_lng, query_tz)
    birth = natal_ref.get("birth", {})
    location_label = (query_location or "").strip() or f"{lat:.4f}, {lng:.4f}"

    # Parse local datetime → UTC
    time_parts = (query_time_local or "06:00:00").split(":")
    hh, mm = int(time_parts[0]), int(time_parts[1])
    ss = int(time_parts[2]) if len(time_parts) > 2 else 0
    naive_local = datetime(query_date.year, query_date.month, query_date.day, hh, mm, ss)
    dst_ambiguous = is_ambiguous_local(tz_name, naive_local)
    local_dt = localize(tz_name, naive_local)
    utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                    utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0)

    # ── Panchanga ────────────────────────────────────────────────
    panch = compute_panchanga(query_date, lat, lng, tz_name)
    jd_rise = panch.get("jd_sunrise")
    jd_set = panch.get("jd_sunset")

    # ── Hora ─────────────────────────────────────────────────────
    # Before today's sunrise the active hora belongs to the previous day's night.
    hora_day = query_date - timedelta(days=1) if (jd_rise and jd < jd_rise) else query_date
    if hora_day == query_date:
        h_rise, h_set = jd_rise, jd_set
    else:
        h_rise = _rise_set(hora_day, lat, lng, swe.SUN, 1, tz_name)
        h_set = _rise_set(hora_day, lat, lng, swe.SUN, 2, tz_name)
    h_next = _rise_set(hora_day + timedelta(days=1), lat, lng, swe.SUN, 1, tz_name)
    hora_data: dict = {}
    current_hora: dict = {}
    if h_rise and h_set and h_next:
        hora_data = compute_hora(hora_day, h_rise, h_set, h_next, tz_name)
        current_hora = get_hora_at(hora_data, local_dt) or {}

    # ── Kalam ────────────────────────────────────────────────────
    def _fmt_jd(jd_v):
        if not jd_v:
            return "--:--"
        dt = _jd_to_local(jd_v, tz_name)
        return dt.strftime("%H:%M") if dt else "--:--"

    def _kalam_window(slot_n: int) -> dict:
        if not jd_rise or not jd_set:
            return {"start": "--:--", "end": "--:--"}
        slot_jd = (jd_set - jd_rise) / 8.0
        s = jd_rise + (slot_n - 1) * slot_jd
        return {"start": _fmt_jd(s), "end": _fmt_jd(s + slot_jd)}

    wd = astro_weekday(query_date)
    rahu_w, yama_w, gulika_w = (_kalam_window(RAHU_SLOTS[wd]), _kalam_window(YAMA_SLOTS[wd]),
                                _kalam_window(GULIKA_SLOTS[wd]))
    kalam_state = {
        "rahu_kalam_start": rahu_w["start"], "rahu_kalam_end": rahu_w["end"],
        "yamaganda_start":  yama_w["start"], "yamaganda_end":  yama_w["end"],
        "gulika_start":     gulika_w["start"], "gulika_end":   gulika_w["end"],
    }

    # ── Transits ─────────────────────────────────────────────────
    natal_planets = natal_ref.get("planets", {})
    transits = transit_snapshot(jd, natal_ref.get("houses", {}))
    for pname, td in transits.items():
        td["natal_sign"] = natal_planets.get(pname, {}).get("sign", "")

    # ── Moon state ───────────────────────────────────────────────
    moon_t = transits.get("Moon", {})
    moon_lon = float(moon_t.get("longitude", 0))
    moon_sign = moon_t.get("sign", "")
    moon_nak, moon_star, moon_sub = nak_star_sub(moon_lon)
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
    natal_moon = natal_planets.get("Moon", {})
    tara = compute_tarabala_full(
        natal_moon.get("nakshatra", "Ashwini"),
        natal_moon.get("sign", "Aries"),
        moon_nak,
        moon_sign,
    )

    # ── Significators (stored when current method, else recomputed in memory) ──
    significators, strength_map = natal_significators(natal_ref)

    # ── Ruling Planets ───────────────────────────────────────────
    rp = compute_ruling_planets(
        query_dt_utc=utc_dt,
        lat=lat,
        lng=lng,
        tz_name=tz_name,
        significators=significators,
        topic_houses=EVENT_HOUSES,
        location_label=location_label,
    )

    # ── Dasha — MD/AD/PD looked up from the natal lock, never re-derived ──
    query_naive = local_dt.replace(tzinfo=None)
    resolved = resolve_dasha(natal_ref, query_naive)
    dasha_state = get_dasha_state(resolved["md"], resolved["ad"], resolved["pd"], query_naive)
    dasha_state["source"] = resolved["source"]
    dasha_state["house_links"] = {
        lvl: lord_house_links(dasha_state.get(f"{lvl}_lord"), significators)
        for lvl in ("md", "ad", "pd", "sukshma", "prana")
        if dasha_state.get(f"{lvl}_lord")
    }
    fine_windows = {
        "note": ("Sukshma/Prana windows beneath the locked PD with the houses each lord "
                 "signifies. Evidence only — not part of the activation score."),
        "sukshma": fine_dasha_windows(natal_ref, query_naive - timedelta(days=7),
                                      query_naive + timedelta(days=90), significators, "sukshma"),
        "prana": fine_dasha_windows(natal_ref, query_naive - timedelta(days=1),
                                    query_naive + timedelta(days=7), significators, "prana"),
    }

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
        natal_planets,
        natal_ref.get("houses", {}),
        natal_ref.get("cuspal_sublords", {}),
        strength_map,
        dasha_state.get("md_lord", ""),
        dasha_state.get("ad_lord", ""),
        dasha_state.get("pd_lord", ""),
        topics=topics_to_analyse or [],
        significators=significators,
    )

    # ── Event evidence trail ─────────────────────────────────────
    # For each topic, assemble the full KP decision chain so the AI
    # never has to re-derive it from raw numbers.
    rp_event_match = rp.get("rp_event_match", {})
    event_evidence: list[dict] = []
    for entry in pd_list:
        topic = entry["topic"]
        sc = entry.get("score", {})
        pct10 = sc.get("pct10", 0.0)
        dark = entry.get("dark_houses", [])

        if pct10 >= 8.0 and not dark:
            confidence = "High — all primary houses activated"
        elif pct10 >= 6.0 and len(dark) <= 1:
            confidence = f"Moderate — H{','.join(str(h) for h in dark)} not in active dasha" if dark else "Moderate"
        elif pct10 >= 4.0:
            confidence = "Low-Moderate — partial activation; watch sub-period"
        else:
            confidence = "Low — topic not strongly supported in current period"

        topic_rp = rp_event_match.get(topic, {})
        rp_rows = topic_rp.get("matching_rp", []) if isinstance(topic_rp, dict) else []

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
            "natal_significators": {
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
            "sukshma_windows": [
                {"lord": w["lord"], "start": w["start"], "end": w["end"], "houses": w["topics"][topic]}
                for w in fine_windows["sukshma"] if topic in w["topics"]
            ],
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
            natal_planets=natal_planets,
            from_date=query_date,
            horizon_years=5,
            event_house_map=EVENT_HOUSES,
            natal_houses=natal_ref.get("houses", {}),
        )

    # ── Significator entries ──────────────────────────────────────
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

    hora_state = {
        "hora_day":           hora_day.isoformat(),
        "current_hora_lord":  current_hora.get("lord", ""),
        "current_hora_start": current_hora.get("start", ""),
        "current_hora_end":   current_hora.get("end", ""),
        "full_day_sequence":  hora_data.get("all_horas", []),
    }

    tarabala_state = {
        "natal_moon_nakshatra":   natal_moon.get("nakshatra", ""),
        "transit_moon_nakshatra": moon_nak,
        "tara_number":            tara.get("tara_number", 0),
        "tara_category":          tara.get("tara_category", ""),
        "chandrashtama":          tara.get("chandrashtama", False),
        "suitability":            tara.get("suitability", ""),
    }

    numerology_state = {
        "name_number":       int(num_natal.get("name_number", 0)),
        "life_path":         int(num_natal.get("life_path", 0)),
        "day_number":        num.get("day_number", 0),
        "day_number_meaning": num.get("day_number_meaning", ""),
    }

    return {
        # Query metadata
        "query_date":     query_date.isoformat(),
        "query_time":     query_time_local or "06:00:00",
        "query_location": location_label,
        "query_lat":      lat,
        "query_lng":      lng,
        "query_tz":       tz_name,
        "query_time_dst_ambiguous": dst_ambiguous,
        "query_mode":     query_mode,
        "transit_house_basis": TRANSIT_HOUSE_BASIS,
        # From locked natal reference
        "birth_name":  birth.get("name", ""),
        "birth_date":  birth.get("date", ""),
        "birth_place": birth.get("place", ""),
        # Dynamic layers
        "dasha":           dasha_state,
        "fine_dasha_windows": fine_windows,
        "significator_method": {
            "version": KP_METHODOLOGY["version"],
            "levels": KP_METHODOLOGY["levels"],
            "node_agency": KP_METHODOLOGY["node_agency"],
            "recomputed_from_natal": not significators_are_current(natal_ref),
        },
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
