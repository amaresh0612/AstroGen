"""
90-Day AI-Ready Astro Calculation Pack Builder — v2.3.

Pure time-dependent calculations only. Static natal data, event rules, and
long-term transits live in separate JSON files referenced by filename.

Architecture:
    natal_ref.json          → immutable KP source of truth
    kp_rules.json           → topic house mappings + methodology
    longterm_transits_*.json → slow-planet ingress calculations
    90day_pack.json         → daily panchanga/kalam/hora/dasha/transits/RP

v2.2+: gapless daily RP intervals + rp_trigger_windows.
v2.3:  complete prana_timeline, RP matching v2, fine-dasha continuity.
v2.4:  RP rejection reason codes, per-day funnels, house-set relation
       diagnostics, topic-map validation vs EVENT_HOUSES/kp_rules,
       Prana⊂Sukshma containment checks. Matching thresholds unchanged.
v2.5:  Coverage-semantics docs in criteria, activation-scope counts,
       nested-topic diffs (children vs relationship), representative
       rejected intervals for GATE_ONLY audit. Matching thresholds unchanged.
v2.6:  Reproducibility metadata block; interpretation usage notes
       (static vs timed RP, capped windows, post-promotion framing).
       Matching thresholds unchanged (still rp_convergence_v2).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import pytz
import swisseph as swe

from analysis.context import require_prediction_location
from analysis.panchanga import compute_panchanga, _rise_set
from analysis.hora import compute_hora
from analysis.tarabala import compute_tarabala_full
from analysis.dasha_fine import get_dasha_state
from analysis.vimshottari import SOURCE_LOCKED_TABLE, resolve_dasha
from analysis.numerology_daily import compute_numerology_daily
from analysis.nakshatra_utils import get_nakshatra_and_pada
from analysis.natal_fingerprint import build_natal_fingerprint, natal_reference_filename
from analysis.reference_exports import longterm_transits_filename
from analysis.significator_strength import (
    KP_METHODOLOGY, build_natal_significator_block, natal_significators, significators_are_current,
)
from analysis.fine_windows import (
    fine_dasha_windows, lord_house_links, prana_parent_containment_issues,
    timeline_continuity_issues,
)
from analysis.reference_exports import build_kp_rules
from analysis.kp_constants import (
    GULIKA_SLOTS, RAHU_SLOTS, SIGN_LORDS, YAMA_SLOTS,
    astro_weekday, jd_to_utc_datetime, localize, nak_star_sub, sign_of, utc_now_iso,
)
from analysis.rp_triggers import build_rp_trigger_windows
from analysis.rp_windows import (
    ASC_INTERVALS_PER_DAY_MAX, ASC_INTERVALS_PER_DAY_MIN, RP_INTERVAL_FIELDS, build_day_rp,
)
from analysis.transits import TRANSIT_HOUSE_BASIS, transit_snapshot
from schemas.event_houses import EVENT_HOUSES

SCHEMA_VERSION = "2.6"
CALC_ENGINE_VERSION = "AstroGen-KP-v2.6"


def _jd_to_iso(jd: float, tz: pytz.BaseTzInfo) -> str:
    return jd_to_utc_datetime(jd).astimezone(tz).isoformat()


def _kalam_window(slot_n: int, jd_rise: float, jd_set: float,
                  tz: pytz.BaseTzInfo) -> dict:
    if not jd_rise or not jd_set or jd_set <= jd_rise:
        return {"start": None, "end": None}
    slot_jd = (jd_set - jd_rise) / 8.0
    s = jd_rise + (slot_n - 1) * slot_jd
    return {
        "start": _jd_to_iso(s, tz),
        "end": _jd_to_iso(s + slot_jd, tz),
    }


def _hora_with_iso(
    day: date,
    jd_rise: float,
    jd_set: float,
    jd_next: float,
    tz_obj: pytz.BaseTzInfo,
    hora_data: dict,
) -> list[dict]:
    """Return 24 hora slots with full ISO-8601 start/end timestamps."""
    if not jd_rise or not jd_set or not jd_next:
        return []

    day_secs = (jd_set - jd_rise) * 86400.0 / 12.0
    night_secs = (jd_next - jd_set) * 86400.0 / 12.0
    result: list[dict] = []
    day_i = night_i = 0

    for h in hora_data.get("all_horas", []):
        if h.get("period") == "day":
            jd_s = jd_rise + day_i * day_secs / 86400.0
            jd_e = jd_rise + (day_i + 1) * day_secs / 86400.0
            day_i += 1
        else:
            jd_s = jd_set + night_i * night_secs / 86400.0
            jd_e = jd_set + (night_i + 1) * night_secs / 86400.0
            night_i += 1

        dur_min = round((jd_e - jd_s) * 1440.0, 1)
        result.append({
            "sequence": h.get("sequence"),
            "lord": h.get("lord"),
            "start": _jd_to_iso(jd_s, tz_obj),
            "end": _jd_to_iso(jd_e, tz_obj),
            "start_display": h.get("start"),
            "end_display": h.get("end"),
            "segment": h.get("period", "day"),
            "duration_min": dur_min,
        })
    return result


def _moon_block(moon_lon: float) -> dict:
    nak_name, nak_lord, _, pada = get_nakshatra_and_pada(moon_lon)
    moon_sign = sign_of(moon_lon)
    _, _, sub = nak_star_sub(moon_lon)
    return {
        "longitude": round(moon_lon, 4),
        "sign": moon_sign,
        "sign_lord": SIGN_LORDS.get(moon_sign, ""),
        "nakshatra": nak_name,
        "star_lord": nak_lord,
        "sub_lord": sub,
        "pada": pada,
    }


def build_90day_pack(
    natal_ref: dict,
    start_date: date,
    num_days: int = 90,
    prediction_city: str = "",
    prediction_lat: Optional[float] = None,
    prediction_lng: Optional[float] = None,
    prediction_tz: str = "",
    reference_time: str = "09:00",
    on_progress=None,
) -> dict:
    """
    Build the 90-day calculation pack — time-dependent data only.

    Static natal data must be loaded from natal_ref.json (referenced by filename).
    Event rules → kp_rules.json. Long-term transits → longterm_transits_{from}_{to}.json.
    ``num_days`` defaults to 90; callers may pass a shorter window for tests.
    """
    prediction_lat, prediction_lng, prediction_tz = require_prediction_location(
        prediction_lat, prediction_lng, prediction_tz,
    )
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    tz_obj = pytz.timezone(prediction_tz)

    birth = natal_ref.get("birth", {})
    dasha_s = natal_ref.get("dasha", {})
    locked_md = dasha_s.get("locked_md", {})
    locked_ad = dasha_s.get("locked_ad", {})
    locked_pd = dasha_s.get("locked_pd", {})

    natal_houses = natal_ref.get("houses", {})
    natal_ref_file = natal_reference_filename(natal_ref)
    natal_fp = build_natal_fingerprint(natal_ref)

    ref_hh = int(reference_time.split(":")[0])
    ref_mm = int(reference_time.split(":")[1])
    natal_moon = natal_ref.get("planets", {}).get("Moon", {})
    num_natal = natal_ref.get("numerology", {})
    significators, _ = natal_significators(natal_ref)

    days_list: list[dict] = []

    for i in range(num_days):
        day = start_date + timedelta(days=i)
        next_day = day + timedelta(days=1)

        if on_progress:
            on_progress(i, day)

        local_ref = localize(prediction_tz, datetime(day.year, day.month, day.day, ref_hh, ref_mm))
        utc_ref = local_ref.astimezone(pytz.utc).replace(tzinfo=None)
        jd_ref = swe.julday(utc_ref.year, utc_ref.month, utc_ref.day,
                            utc_ref.hour + utc_ref.minute / 60.0)

        panch = compute_panchanga(day, prediction_lat, prediction_lng, prediction_tz)
        jd_rise = panch.get("jd_sunrise")
        jd_set = panch.get("jd_sunset")
        jd_next = _rise_set(next_day, prediction_lat, prediction_lng, swe.SUN, 1, prediction_tz)

        hora_list: list[dict] = []
        if jd_rise and jd_set and jd_next:
            hora_data = compute_hora(day, jd_rise, jd_set, jd_next, prediction_tz)
            hora_list = _hora_with_iso(day, jd_rise, jd_set, jd_next, tz_obj, hora_data)

        astro_day = astro_weekday(day)
        kalam_out = {
            "rahu": _kalam_window(RAHU_SLOTS[astro_day], jd_rise, jd_set, tz_obj),
            "yamaganda": _kalam_window(YAMA_SLOTS[astro_day], jd_rise, jd_set, tz_obj),
            "gulika": _kalam_window(GULIKA_SLOTS[astro_day], jd_rise, jd_set, tz_obj),
        }

        moon_lon = float(panch.get("moon_longitude", 0))
        moon_blk = _moon_block(moon_lon)

        tara = compute_tarabala_full(
            natal_moon.get("nakshatra", "Ashwini"),
            natal_moon.get("sign", "Aries"),
            moon_blk["nakshatra"], moon_blk["sign"],
        )
        tara_out = {
            "natal_moon_nakshatra": natal_moon.get("nakshatra", ""),
            "transit_moon_nakshatra": moon_blk["nakshatra"],
            "tara_number": tara.get("tara_number"),
            "tara_category": tara.get("tara_category", ""),
            "chandrashtama": tara.get("chandrashtama", False),
            "suitability": tara.get("suitability", ""),
        }

        num_day = compute_numerology_daily(
            day,
            int(num_natal.get("name_number", 0)),
            int(num_natal.get("life_path", 0)),
        )
        num_out = {
            "date_digits": f"{day.day}+{day.month}+{day.year}",
            "day_number": num_day.get("day_number"),
            "day_meaning": num_day.get("day_number_meaning", ""),
        }

        local_ref_naive = local_ref.replace(tzinfo=None)
        resolved = resolve_dasha(natal_ref, local_ref_naive)
        ds = get_dasha_state(resolved["md"], resolved["ad"], resolved["pd"], local_ref_naive)

        def _lord_dict(lord_key: str, start_key: str, end_key: str, links: bool = False) -> Optional[dict]:
            lord = ds.get(lord_key)
            if not lord:
                return None
            out = {"lord": lord, "start": ds.get(start_key, ""), "end": ds.get(end_key, "")}
            if links:
                out.update(lord_house_links(lord, significators))
            return out

        dasha_out = {
            "source": (
                "LOCKED — natal_ref.json locked_periods; never recalculate MD/AD/PD"
                if resolved["source"] == SOURCE_LOCKED_TABLE
                else f"{resolved['source']} — natal file has no locked_periods covering this date"
            ),
            "md": _lord_dict("md_lord", "md_start", "md_end"),
            "ad": _lord_dict("ad_lord", "ad_start", "ad_end"),
            "pd": _lord_dict("pd_lord", "pd_start", "pd_end"),
            "sukshma": _lord_dict("sukshma_lord", "sukshma_start", "sukshma_end", links=True),
            "prana": _lord_dict("prana_lord", "prana_start", "prana_end", links=True),
        }

        transits_out = {
            "reference_time": reference_time,
            "reference_iso": local_ref.isoformat(),
            "house_basis": TRANSIT_HOUSE_BASIS,
            "planets": transit_snapshot(jd_ref, natal_houses),
        }

        sun_out = {
            "sunrise": _jd_to_iso(jd_rise, tz_obj) if jd_rise else None,
            "sunset": _jd_to_iso(jd_set, tz_obj) if jd_set else None,
        }

        days_list.append({
            "date": day.isoformat(),
            "weekday": day.strftime("%A"),
            "location": {
                "city": prediction_city,
                "lat": prediction_lat,
                "lng": prediction_lng,
                "timezone": prediction_tz,
            },
            "daily_reference": {
                "panchanga_time": "sunrise",
                "transit_time": reference_time,
            },
            "sun": sun_out,
            "panchanga": {
                "tithi": panch.get("tithi", ""),
                "tithi_number": panch.get("tithi_number"),
                "vara": panch.get("vara", ""),
                "yoga": panch.get("yoga", ""),
                "karana": panch.get("karana", ""),
                "moon": moon_blk,
            },
            "kalam": kalam_out,
            "hora": hora_list,
            "tarabala": tara_out,
            "numerology": num_out,
            "dasha": dasha_out,
            "transits": transits_out,
            "ruling_planets": build_day_rp(
                day, prediction_lat, prediction_lng, prediction_tz, reference_time,
            ),
        })

    significators_block, strength_map = natal_significators(natal_ref)
    rp_triggers = build_rp_trigger_windows(days_list, strength_map)

    # Per-day dasha is sampled at the reference time, so a short Sukshma/Prana
    # can fall between samples. Full timelines make every transition visible.
    cov_start = datetime(start_date.year, start_date.month, start_date.day)
    cov_end = datetime(
        (start_date + timedelta(days=num_days)).year,
        (start_date + timedelta(days=num_days)).month,
        (start_date + timedelta(days=num_days)).day,
    )
    sukshma_timeline = fine_dasha_windows(
        natal_ref, cov_start, cov_end, significators_block, "sukshma",
    )
    prana_timeline = fine_dasha_windows(
        natal_ref, cov_start, cov_end, significators_block, "prana",
    )

    validation = _validate(
        days_list, natal_ref, prediction_lat, prediction_lng, num_days, reference_time,
        rp_triggers, prediction_tz,
        sukshma_timeline=sukshma_timeline,
        prana_timeline=prana_timeline,
        coverage_start=cov_start,
        coverage_end=cov_end,
    )

    generated_at = utc_now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "calculation_engine": CALC_ENGINE_VERSION,
        "generated_at": generated_at,
        "valid_from": start_date.isoformat(),
        "valid_to": (start_date + timedelta(days=num_days - 1)).isoformat(),
        "num_days": num_days,
        "ayanamsa": "Lahiri",
        "notes": (
            "CALCULATIONS ONLY — no predictions, no scores, no AI interpretations. "
            "Load natal data from natal_reference_file. "
            "Event rules from kp_rules.json. "
            "Long-term transits from longterm_transits.json. "
            "Ruling Planets are pre-stored per day (schema 2.2): use "
            "days[].ruling_planets.ascendant_windows / moon_windows for an exact-time "
            "query, and days[].ruling_planets.reference_snapshot only when no time is "
            "given. Never reuse one day's RP for another date."
        ),
        "usage": {
            "date_selection": (
                "Select days[] by the requested date range. The pack generation date is "
                "metadata only — never treat it as the prediction date."
            ),
            "exact_time_query": (
                "Find the ascendant_windows and moon_windows row whose [start, end) "
                "contains the local time, then combine with ruling_planets.day_lord."
            ),
            "monthly_query": (
                "Aggregate every day of the requested month from "
                "rp_trigger_windows.topics[topic].days (windows_total, active_minutes, "
                "strong_*). windows[] is a capped listing of best moments only — never "
                "treat the listed six as every qualifying window. Do not generalise from "
                "a single day's snapshot."
            ),
            "fine_dasha": (
                "Use sukshma_timeline and prana_timeline for MD→AD→PD→Sukshma→Prana "
                "transitions with second-precision local timestamps. days[].dasha samples "
                "only the reference time."
            ),
            "evidence_order": (
                "1) Locked natal promise (CSL) → 2) L1–L4 significators → "
                "3) Locked MD→AD→PD→Sukshma→Prana → 4) Valid RP interval if available → "
                "5) Transit trigger → 6) Realistic manifestation → 7) Vedic/numerology cross-check. "
                "Never jump from an RP window or transit alone to a major event. "
                "Dasha permission without RP windows = Timing support absent (not denial)."
            ),
            "static_vs_timed_rp": (
                "Static RP–house overlap (PDF section A / rp_event_match) ≠ "
                "time-specific RP activation (rp_trigger_windows). "
                "Do not call a topic time-supported from static overlap alone."
            ),
            "interpretation_labels": [
                "Supported",
                "Possible",
                "Insufficient evidence",
                "Timing support absent",
            ],
            "out_of_range": (
                "Dates outside valid_from..valid_to have no stored RP or panchanga here. "
                "Say so explicitly; never invent RP windows or planetary positions."
            ),
        },
        "reproducibility": {
            "schema_version": SCHEMA_VERSION,
            "calculation_engine": CALC_ENGINE_VERSION,
            "significator_methodology_version": KP_METHODOLOGY["version"],
            "rp_criteria_id": "rp_convergence_v2",
            "rp_diagnostics_schema": "1.1",
            "rp_matching_thresholds_unchanged_since": "2.3",
            "locked_dasha_source": (
                "natal_ref.dasha.locked_periods via analysis.vimshottari.resolve_dasha"
            ),
            "prediction_location": {
                "city": prediction_city,
                "lat": prediction_lat,
                "lng": prediction_lng,
                "timezone": prediction_tz,
            },
            "generated_at": generated_at,
            "note": (
                "Do not mix packages aligned to different natal birth dates "
                "(e.g. 1990 vs 1989). Fingerprint alignment does not verify "
                "factual birth details."
            ),
        },
        "natal_reference_file": natal_ref_file,
        "natal_reference": {
            **natal_fp,
            "note": "Fingerprint only — full chart data is in natal_reference_file",
        },
        "companion_files": {
            "kp_rules": "kp_rules.json",
            "longterm_transits": longterm_transits_filename(start_date),
        },
        "significator_method": {
            "version": KP_METHODOLOGY["version"],
            "natal_file_current": significators_are_current(natal_ref),
            "note": (
                "Sukshma/Prana house links use this method. "
                + ("" if significators_are_current(natal_ref) else
                   "The natal_ref file's stored significators use an older method — regenerate it "
                   "before relying on its significators/significator_matrix.")
            ),
        },
        "natal_lock": {
            "name": birth.get("name", ""),
            "birth_date": birth.get("date", ""),
            "birth_place": birth.get("place", ""),
            "md_lord": locked_md.get("lord", ""),
            "ad_lord": locked_ad.get("lord", ""),
            "pd_lord": locked_pd.get("lord", ""),
            "locked_at": dasha_s.get("locked_at", ""),
            "note": "Lords active at natal lock time; each day's dasha block is looked up from locked_periods",
        },
        "prediction_location": {
            "city": prediction_city,
            "lat": prediction_lat,
            "lng": prediction_lng,
            "timezone": prediction_tz,
            "note": "Birth/natal location is SEPARATE — stored in natal_ref.json only",
        },
        "sukshma_timeline": {
            "note": (
                "Every Sukshma window overlapping the coverage period, in order, beneath "
                "the locked MD/AD/PD. Clipped to coverage; consecutive rows abut. "
                "days[].dasha samples only the reference time."
            ),
            "windows": sukshma_timeline,
        },
        "prana_timeline": {
            "note": (
                "Every Prana window overlapping the coverage period, in order, beneath "
                "the locked MD/AD/PD and its Sukshma parent. Each row carries md/ad/pd/"
                "sukshma/lord (prana), signified_houses and topics. Clipped to coverage; "
                "consecutive rows abut with second-precision local timestamps."
            ),
            "windows": prana_timeline,
        },
        "rp_trigger_windows": rp_triggers,
        "validation": validation,
        "days": days_list,
    }


def _status(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _rp_seconds(clock: str) -> int:
    h, m, s = (int(x) for x in clock.split(":"))
    return h * 3600 + m * 60 + s


def _validate_rp(days_list: list[dict], reference_time: str, tz_name: str) -> tuple[list[str], dict]:
    """Daily RP blocks: presence, timezone, gapless local-day coverage, completeness."""
    issues: list[str] = []
    asc_total = moon_total = 0

    for d in days_list:
        rp = d.get("ruling_planets")
        if not rp:
            issues.append(f"{d['date']}: no ruling_planets block")
            continue
        if rp.get("timezone") != tz_name:
            issues.append(f"{d['date']}: RP timezone {rp.get('timezone')} != {tz_name}")
        if rp.get("interval_fields") != RP_INTERVAL_FIELDS:
            issues.append(f"{d['date']}: RP interval_fields do not match the engine")
        snap = rp.get("reference_snapshot", {})
        if snap.get("reference_time") != reference_time:
            issues.append(
                f"{d['date']}: RP snapshot at {snap.get('reference_time')} != pack reference {reference_time}"
            )
        if not (snap.get("ascendant", {}).get("sub_lord") and snap.get("moon", {}).get("sub_lord")):
            issues.append(f"{d['date']}: RP reference snapshot incomplete")

        span = rp.get("coverage", {}).get("local_day_minutes")
        for name, rows in (("ascendant", rp.get("ascendant_windows", [])),
                           ("moon", rp.get("moon_windows", []))):
            if not rows:
                issues.append(f"{d['date']}: no {name} RP windows")
                continue
            if rows[0][0] != "00:00:00" or rows[-1][1] != "24:00:00":
                issues.append(
                    f"{d['date']}: {name} windows span {rows[0][0]}–{rows[-1][1]}, "
                    "not the full local day"
                )
            for prev, nxt in zip(rows, rows[1:]):
                if prev[1] != nxt[0]:
                    issues.append(f"{d['date']}: {name} gap/overlap at {prev[1]} → {nxt[0]}")
                    break
            if any(_rp_seconds(r[1]) <= _rp_seconds(r[0]) for r in rows):
                issues.append(f"{d['date']}: {name} window with non-positive duration")

        asc_n, moon_n = len(rp.get("ascendant_windows", [])), len(rp.get("moon_windows", []))
        asc_total += asc_n
        moon_total += moon_n
        if span == 1440 and not (ASC_INTERVALS_PER_DAY_MIN <= asc_n <= ASC_INTERVALS_PER_DAY_MAX):
            issues.append(
                f"{d['date']}: {asc_n} ascendant intervals is outside the expected "
                f"{ASC_INTERVALS_PER_DAY_MIN}–{ASC_INTERVALS_PER_DAY_MAX} band — a change may be missing"
            )
        if len(issues) >= 8:
            break

    stats = {
        "days_with_rp": sum(1 for d in days_list if d.get("ruling_planets")),
        "ascendant_intervals": asc_total,
        "moon_intervals": moon_total,
    }
    return issues, stats


def _validate_topic_house_maps(rp_triggers: dict) -> tuple[list[str], list[str]]:
    """
    Structural issues vs soft warnings for topic → house mapping.
    Authoritative map: schemas.event_houses.EVENT_HOUSES (same source as kp_rules.json).
    """
    issues: list[str] = []
    warnings: list[str] = []
    topics = (rp_triggers or {}).get("topics", {})
    rules = build_kp_rules()
    rules_map = {t: list(h) for t, h in rules["event_house_map"].items()}

    if set(rules_map) != set(EVENT_HOUSES):
        issues.append(
            f"kp_rules topics {sorted(set(rules_map) ^ set(EVENT_HOUSES))} "
            "disagree with EVENT_HOUSES"
        )
    for topic, houses in EVENT_HOUSES.items():
        if rules_map.get(topic) != list(houses):
            issues.append(
                f"{topic}: kp_rules houses {rules_map.get(topic)} != EVENT_HOUSES {list(houses)}"
            )
        block = topics.get(topic)
        if not block:
            issues.append(f"{topic}: missing from rp_trigger_windows")
            continue
        if list(block.get("houses", [])) != list(houses):
            issues.append(
                f"{topic}: rp_trigger houses {block.get('houses')} != EVENT_HOUSES {list(houses)}"
            )
        # Duplicate house entries inside a topic
        if len(houses) != len(set(houses)):
            issues.append(f"{topic}: duplicated houses in mapping {houses}")

    # Identical house sets are allowed but must be surfaced
    by_set: dict[tuple, list[str]] = {}
    for topic, houses in EVENT_HOUSES.items():
        by_set.setdefault(tuple(houses), []).append(topic)
    for houses, names in by_set.items():
        if len(names) > 1:
            warnings.append(
                f"Topics {names} share identical primary houses {list(houses)}; "
                "identical RP activation is expected when significators and dasha gates match."
            )
    return issues, warnings


def _validate_triggers(rp_triggers: dict, days_list: list[dict]) -> tuple[list[str], dict]:
    """Trigger windows: topic coverage, valid significators, in-range dates, listed≤total."""
    issues: list[str] = []
    topics = (rp_triggers or {}).get("topics", {})
    pack_dates = {d["date"] for d in days_list}

    missing = [t for t in EVENT_HOUSES if t not in topics]
    if missing:
        issues.append(f"kp_rules topics with no trigger section: {missing}")

    map_issues, _ = _validate_topic_house_maps(rp_triggers or {})
    issues.extend(map_issues)

    per_topic: dict[str, int] = {}
    for topic, block in topics.items():
        sigs = set(block.get("significators", {}).get("l1_l2", []))
        rows = block.get("windows", [])
        summary = block.get("summary", {})
        per_topic[topic] = len(rows)
        if len(block.get("days", [])) != len(days_list):
            issues.append(f"{topic}: {len(block.get('days', []))} day rows for {len(days_list)} days")
        # Cap must not inflate totals
        if summary.get("windows_listed", 0) > summary.get("windows_total", 0):
            issues.append(
                f"{topic}: windows_listed {summary.get('windows_listed')} > "
                f"windows_total {summary.get('windows_total')}"
            )
        for detail in (block.get("diagnostics") or {}).get("days_detail") or []:
            if detail.get("windows_listed", 0) > detail.get("windows_total", 0):
                issues.append(f"{topic} {detail.get('date')}: listed > total")
                break
            if detail.get("gate") in ("TRIGGER", "GATE_ONLY") and not detail.get("listed_is_subset", True):
                issues.append(f"{topic} {detail.get('date')}: listed_is_subset is false")
                break
        for row in rows:
            if row[0] not in pack_dates:
                issues.append(f"{topic}: trigger window on {row[0]} is outside the pack coverage")
                break
            if not set(row[11]) <= sigs:
                issues.append(f"{topic}: window on {row[0]} cites a non-significator {row[11]}")
                break
            if _rp_seconds(row[2]) <= _rp_seconds(row[1]):
                issues.append(f"{topic}: window on {row[0]} has non-positive duration")
                break

    return issues, per_topic


def _validate_timelines(
    sukshma: list[dict],
    prana: list[dict],
    coverage_start: datetime,
    coverage_end: datetime,
    days_list: list[dict],
) -> list[str]:
    issues: list[str] = []
    issues.extend(timeline_continuity_issues(sukshma, coverage_start, coverage_end, "sukshma_timeline"))
    issues.extend(timeline_continuity_issues(prana, coverage_start, coverage_end, "prana_timeline"))
    issues.extend(prana_parent_containment_issues(prana, sukshma))

    # Chronological order
    for label, windows in (("sukshma", sukshma), ("prana", prana)):
        for prev, nxt in zip(windows, windows[1:]):
            if prev["start"] > nxt["start"]:
                issues.append(f"{label}: out of order at {prev['start']} → {nxt['start']}")
                break

    sk_lords = {w["lord"] for w in sukshma}
    pr_lords = {w["lord"] for w in prana}
    for d in days_list:
        sk = (d.get("dasha") or {}).get("sukshma") or {}
        pr = (d.get("dasha") or {}).get("prana") or {}
        if sk.get("lord") and sk["lord"] not in sk_lords:
            issues.append(f"{d['date']}: daily sukshma {sk['lord']} missing from sukshma_timeline")
        if pr.get("lord") and pr["lord"] not in pr_lords:
            issues.append(f"{d['date']}: daily prana {pr['lord']} missing from prana_timeline")
        if len(issues) >= 10:
            break
    return issues


def _semantic_warnings(rp_triggers: dict, num_days: int) -> list[str]:
    """
    Soft astrology-semantic flags — never fail structural validation.
    A structural PASS does not imply every RP topic behaviour is ideal.
    """
    warnings: list[str] = []
    topics = (rp_triggers or {}).get("topics", {})
    full_day_minutes = num_days * 1440
    activation_signatures: dict[tuple, list[str]] = {}

    _, map_warnings = _validate_topic_house_maps(rp_triggers or {})
    warnings.extend(map_warnings)

    for topic, block in topics.items():
        summary = block.get("summary", {})
        diag = block.get("diagnostics", {})
        gate = summary.get("days_passing_gate", 0)
        active = summary.get("active_minutes", 0)
        strong = summary.get("strong_windows", 0)
        l12 = diag.get("l1_l2_count", len(block.get("significators", {}).get("l1_l2", [])))
        rel = diag.get("house_set_relations") or {}

        if num_days >= 7 and gate == num_days and active >= full_day_minutes * 0.95:
            warnings.append(
                f"{topic}: RP gate passes all {num_days} days with near-continuous "
                f"activation ({active} active minutes). Review selectivity."
            )
        if l12 >= 8:
            warnings.append(
                f"{topic}: L1-L2 significator set has {l12}/9 planets — multi-house "
                "OR-matching makes activation broad; house-coverage + L1 deciding-sub "
                "filters constrain it. See diagnostics.rejection_reason_totals."
            )
        if (summary.get("days_with_dasha_permission", 0) > 0
                and summary.get("windows_total", 0) == 0):
            warnings.append(
                f"{topic}: dasha permission exists but zero RP windows "
                f"({diag.get('dasha_without_rp_note') or 'see diagnostics'})."
            )
        if gate > 0 and strong == 0 and summary.get("windows_total", 0) > 0:
            warnings.append(f"{topic}: {summary.get('windows_total')} ACTIVE windows but zero STRONG.")

        if summary.get("windows_listed", 0) > summary.get("windows_total", 0):
            warnings.append(f"{topic}: listed windows exceed total — totals/cap inconsistency.")

        sig = (
            summary.get("days_passing_gate"),
            summary.get("windows_total"),
            summary.get("active_minutes"),
            summary.get("strong_windows"),
        )
        activation_signatures.setdefault(sig, []).append(topic)

        # Same activation as an identical-house peer is expected; note once per pair.
        for peer in rel.get("identical_house_set_with") or []:
            if topic > peer:
                continue
            peer_sum = (topics.get(peer) or {}).get("summary") or {}
            peer_sig = (
                peer_sum.get("days_passing_gate"),
                peer_sum.get("windows_total"),
                peer_sum.get("active_minutes"),
                peer_sum.get("strong_windows"),
            )
            if peer_sig == sig and sig[1]:
                warnings.append(
                    f"{topic} and {peer} have identical RP activation and share "
                    f"primary houses {rel.get('houses')}. Expected — not a cache bug."
                )

    for sig, names in activation_signatures.items():
        if len(names) < 2 or not (sig[0] and sig[1]):
            continue
        # Skip pairs already explained by identical house sets
        unexplained = []
        for n in names:
            peers = set(
                ((topics.get(n) or {}).get("diagnostics") or {})
                .get("house_set_relations", {})
                .get("identical_house_set_with") or []
            )
            if not peers.intersection(names):
                unexplained.append(n)
        if len(unexplained) >= 2:
            warnings.append(
                f"Identical RP activation across topics with different house sets "
                f"{unexplained}: {sig}. Check subset relations / shared significators "
                "(see house_set_relations). Not an automatic failure."
            )

    # Nested half-coverage limitation (career ⊂ promotion/wealth, children ⊂ relationship)
    audit = (rp_triggers or {}).get("cross_topic_audit") or {}
    cpw = audit.get("career_promotion_wealth") or {}
    if cpw.get("promotion_equals_wealth"):
        warnings.append(
            "promotion ≡ wealth under EVENT_HOUSES [2,6,10,11]: identical RP totals "
            "are correct. Half-coverage cannot separate them (see criteria.methodology_limitations)."
        )
    c_sum, p_sum = cpw.get("career_summary") or {}, cpw.get("promotion_summary") or {}
    if c_sum and p_sum and c_sum.get("windows_total") and p_sum.get("windows_total"):
        if abs(int(c_sum["windows_total"]) - int(p_sum["windows_total"])) <= max(
            5, int(0.01 * max(c_sum["windows_total"], p_sum["windows_total"]))
        ):
            warnings.append(
                "career and promotion/wealth activations are nearly identical under "
                "half-house coverage (ceil(n/2)): matched cores like [6,11] meet need=2 "
                "for both career (3 houses) and promotion (4 houses). Selectivity limit "
                "documented in criteria.coverage_semantics — thresholds unchanged."
            )
    cvr = audit.get("children_vs_relationship")
    if cvr and cvr.get("subset_only_count"):
        sample = (cvr.get("subset_only_samples") or [None])[0]
        warnings.append(
            f"children has {cvr['subset_only_count']} RP moment(s) that relationship "
            f"does not (need 1 of [5,11] vs need 2 of [5,7,11]). "
            f"See cross_topic_audit.children_vs_relationship"
            + (f"; first exclusive: {sample.get('date')} {sample.get('start')}–"
               f"{sample.get('end')} houses {sample.get('matched_houses')}"
               if sample else "")
            + "."
        )
    return warnings


def _validate(
    days_list: list[dict],
    natal_ref: dict,
    pred_lat: float,
    pred_lng: float,
    expected_days: int,
    reference_time: str,
    rp_triggers: Optional[dict] = None,
    tz_name: str = "",
    sukshma_timeline: Optional[list] = None,
    prana_timeline: Optional[list] = None,
    coverage_start: Optional[datetime] = None,
    coverage_end: Optional[datetime] = None,
) -> dict:

    schema_issues: list[str] = []
    forbidden = {"natal_significators", "event_house_map", "long_term_transits",
                 "natal_cuspal_sublords", "event_analyses", "hourly_snapshots"}
    for d in days_list[:3]:
        for key in forbidden:
            if key in d:
                schema_issues.append(f"Forbidden field '{key}' found in daily record {d['date']}")

    internal_issues: list[str] = []
    if len(days_list) != expected_days:
        internal_issues.append(f"Expected {expected_days} days, got {len(days_list)}")
    if len({d["date"] for d in days_list}) != len(days_list):
        internal_issues.append("Duplicate dates found")
    loc_bad = [d["date"] for d in days_list if d.get("location", {}).get("lat") != pred_lat]
    if loc_bad:
        internal_issues.append(f"Location inconsistent on {len(loc_bad)} days")

    natal_issues: list[str] = []
    if not natal_ref.get("planets"):
        natal_issues.append("natal_ref appears incomplete — no planets found")

    dasha_issues: list[str] = []
    warnings: list[str] = []
    dasha_s = natal_ref.get("dasha", {})
    locked_at = dasha_s.get("locked_at")
    if locked_at:
        at_lock = resolve_dasha(natal_ref, locked_at)
        for lvl in ("md", "ad", "pd"):
            want = (dasha_s.get(f"locked_{lvl}") or {}).get("lord", "")
            if at_lock[lvl]["lord"] != want:
                dasha_issues.append(
                    f"locked_{lvl} {want} disagrees with locked_periods ({at_lock[lvl]['lord']}) at {locked_at}"
                )
    else:
        warnings.append(
            "natal_ref has no locked_periods table — AD/PD were derived from full_timeline. "
            "Re-download the natal JSON to lock them."
        )

    ref_hh, ref_mm = (int(x) for x in reference_time.split(":")[:2])
    for d in days_list:
        dd = d.get("dasha", {})
        missing = [lvl for lvl in ("md", "ad", "pd") if not (dd.get(lvl) or {}).get("lord")]
        if missing:
            dasha_issues.append(f"{d['date']}: no {'/'.join(missing).upper()} for this date")
            continue
        day = date.fromisoformat(d["date"])
        ref = datetime(day.year, day.month, day.day, ref_hh, ref_mm)
        want = resolve_dasha(natal_ref, ref)
        for lvl in ("md", "ad", "pd"):
            if dd[lvl]["lord"] != want[lvl]["lord"]:
                dasha_issues.append(
                    f"{d['date']}: {lvl.upper()} {dd[lvl]['lord']} != locked {want[lvl]['lord']}"
                )
        pd_s, pd_e = dd["pd"].get("start", ""), dd["pd"].get("end", "")
        if not (pd_s <= d["date"] <= pd_e):
            dasha_issues.append(f"{d['date']}: outside its PD window {pd_s}→{pd_e}")
        if len(dasha_issues) >= 5:
            break

    from analysis.cuspal_houses import validate_cuspal_occupancy
    occupancy_issues = validate_cuspal_occupancy(
        natal_ref.get("planets", {}),
        natal_ref.get("houses", {}),
    )

    semantic_issues: list[str] = []
    stored_sigs = natal_ref.get("significators", {})
    if stored_sigs and not significators_are_current(natal_ref):
        warnings.append(
            f"natal_ref significators predate method {KP_METHODOLOGY['version']} "
            "(classical KP + node agency); recomputed in memory — regenerate natal_ref.json"
        )
    elif stored_sigs and natal_ref.get("planets") and natal_ref.get("houses"):
        recomputed_sigs, recomputed_matrix = build_natal_significator_block(
            natal_ref.get("planets", {}),
            natal_ref.get("houses", {}),
        )
        for pname, sdata in stored_sigs.items():
            stored_h = sorted(sdata.get("signified_houses", []))
            expected_h = sorted(recomputed_sigs.get(pname, {}).get("signified_houses", []))
            if stored_h != expected_h:
                semantic_issues.append(
                    f"Significator mismatch {pname}: stored={stored_h} expected={expected_h}"
                )
        stored_matrix = natal_ref.get("significator_matrix")
        if stored_matrix:
            for pname, hmap in recomputed_matrix.items():
                for h, info in hmap.items():
                    key = str(h)
                    sm = stored_matrix.get(pname, {}).get(key, {})
                    if sm.get("level") != info["level"]:
                        semantic_issues.append(
                            f"Matrix level mismatch {pname} H{h}: "
                            f"stored L{sm.get('level')} expected L{info['level']}"
                        )
                        break
                if len(semantic_issues) >= 5:
                    break
    elif stored_sigs and not natal_ref.get("significator_matrix"):
        semantic_issues.append(
            "natal_ref missing significator_matrix — re-download natal JSON to lock canonical matrix"
        )

    stored_csl = natal_ref.get("cuspal_sublords", {})
    if not stored_csl:
        semantic_issues.append("natal_ref missing cuspal_sublords")

    panch_issues: list[str] = []
    for d in days_list:
        moon = d.get("panchanga", {}).get("moon", {})
        lon = moon.get("longitude")
        pada = moon.get("pada")
        if lon is None or pada is None:
            panch_issues.append(f"Missing moon data on {d['date']}")
            continue
        _, _, _, expected_pada = get_nakshatra_and_pada(float(lon))
        if expected_pada != pada:
            panch_issues.append(
                f"Moon pada mismatch on {d['date']}: stored={pada}, "
                f"computed={expected_pada} at lon={lon}"
            )
            if len(panch_issues) >= 5:
                break

    kalam_issues: list[str] = []
    bad_kal = [d["date"] for d in days_list
               if not d.get("kalam", {}).get("rahu", {}).get("start")]
    if bad_kal:
        kalam_issues.append(f"Rahu Kalam missing for {len(bad_kal)} days")

    hora_issues: list[str] = []
    bad_hora = [d["date"] for d in days_list
                if len([h for h in d.get("hora", []) if h.get("segment") == "day"]) != 12
                or len([h for h in d.get("hora", []) if h.get("segment") == "night"]) != 12]
    if bad_hora:
        hora_issues.append(
            f"Hora count wrong on {len(bad_hora)} days "
            f"(need 12 day + 12 night): {bad_hora[:3]}"
        )
    iso_bad = [d["date"] for d in days_list
               if d.get("hora") and "T" not in str(d["hora"][0].get("start", ""))]
    if iso_bad:
        hora_issues.append(f"Hora missing ISO timestamps on {len(iso_bad)} days")

    rp_issues, rp_stats = _validate_rp(days_list, reference_time, tz_name)
    trigger_issues, trigger_counts = _validate_triggers(rp_triggers or {}, days_list)

    timeline_issues: list[str] = []
    if coverage_start is not None and coverage_end is not None:
        timeline_issues = _validate_timelines(
            sukshma_timeline or [], prana_timeline or [],
            coverage_start, coverage_end, days_list,
        )

    dst_days = [d["date"] for d in days_list
                if (d.get("ruling_planets", {}).get("coverage", {})
                     .get("local_day_minutes", 1440)) != 1440]
    if dst_days:
        warnings.append(
            f"{len(dst_days)} day(s) are not 1440 minutes long (DST transition): "
            f"{dst_days[:3]} — wall-clock RP labels repeat or skip on those days; "
            "the interval order is authoritative."
        )

    warnings.extend(_semantic_warnings(rp_triggers or {}, len(days_list)))

    all_issues = (
        schema_issues + internal_issues + natal_issues + occupancy_issues +
        semantic_issues + panch_issues + kalam_issues + hora_issues + dasha_issues +
        rp_issues + trigger_issues + timeline_issues
    )

    layers = {
        "schema": _status(not schema_issues),
        "internal_consistency": _status(not internal_issues),
        "natal_lock": _status(not natal_issues),
        "cuspal_occupancy": _status(not occupancy_issues),
        "natal_semantic_consistency": _status(not semantic_issues),
        "panchanga_consistency": _status(not panch_issues),
        "kalam": _status(not kalam_issues),
        "hora": _status(not hora_issues),
        "dasha_lock": _status(not dasha_issues),
        "ruling_planets": _status(not rp_issues),
        "rp_trigger_windows": _status(not trigger_issues),
        "fine_dasha_timelines": _status(not timeline_issues),
    }
    overall_pass = all(v == "PASS" for v in layers.values())

    return {
        "overall": _status(overall_pass),
        "trust_status": layers,
        "issues": all_issues,
        "warnings": warnings,
        "validation_categories": {
            "structural": _status(not (
                schema_issues + internal_issues + natal_issues + occupancy_issues +
                panch_issues + kalam_issues + hora_issues + dasha_issues + rp_issues
            )),
            "internal_consistency": _status(not (
                semantic_issues + trigger_issues + timeline_issues
            )),
            "astrology_semantic": (
                "WARNINGS" if warnings else "CLEAR"
            ),
            "note": (
                "Structural PASS does not imply every RP topic signature is ideal. "
                "Read warnings for identical activations, broad L1-L2 sets, and "
                "dasha-permission-without-RP-windows."
            ),
        },
        "summary": "All checks passed" if overall_pass
                   else f"{len(all_issues)} issue(s): " + "; ".join(all_issues[:5]),
        "passed": overall_pass,
        "rp_summary": {
            "days": len(days_list),
            "coverage_from": days_list[0]["date"] if days_list else None,
            "coverage_to": days_list[-1]["date"] if days_list else None,
            "reference_timezone": tz_name,
            "reference_time": reference_time,
            **rp_stats,
            "trigger_windows_per_topic_listed": trigger_counts,
            "trigger_windows_listed_total": sum(trigger_counts.values()),
            "sukshma_windows": len(sukshma_timeline or []),
            "prana_windows": len(prana_timeline or []),
            "rp_criteria": (rp_triggers or {}).get("criteria", {}).get("id"),
            "diagnostics_schema": (rp_triggers or {}).get("criteria", {}).get("diagnostics_schema"),
        },
    }
