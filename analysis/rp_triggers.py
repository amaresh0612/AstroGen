"""
Topic-specific Ruling-Planet trigger windows.

Takes the daily RP blocks produced by ``analysis.rp_windows`` and the locked
natal significators, and precomputes the moments at which the ruling planets
converge on a topic's houses.

What this is
------------
An **activation filter**. A trigger window says "the ruling planets in force at
this moment are strong significators of these houses". It is not proof of an
event and does not replace natal promise (cuspal sublord) or dasha permission.

Matching criterion (rp_convergence_v2) — unchanged in this revision
------------------------------------------------------------------
* Ascendant sub lord and Moon sub lord must signify at **Level 1**.
* Ascendant star lord at L1–L2; day lord at L1–L2.
* Dasha permission at L1–L2.
* Matched houses cover at least half of the topic's primary houses (min 1).

Natal significators, CSLs and ``EVENT_HOUSES`` are not altered.

v2.5 diagnostics (thresholds unchanged)
---------------------------------------
Coverage semantics, activation-scope tags, nested-topic window diffs,
and representative rejected intervals for GATE_ONLY / near-miss audit.
"""
from __future__ import annotations

from typing import Iterable, Optional

from analysis.rp_coverage import (
    COVERAGE_SEMANTICS,
    classify_activation_scope,
    explain_children_vs_relationship,
    matched_houses_for_planets,
    min_houses_required,
)
from analysis.significator_strength import get_strong_significators_for_houses
from schemas.event_houses import EVENT_HOUSES, TOPIC_LABELS

MAX_REPRESENTATIVE_REJECTIONS = 8
MAX_NESTED_DIFF_SAMPLES = 12

WINDOW_FIELDS = [
    "date", "start", "end", "grade",
    "asc_sign_lord", "asc_star_lord", "asc_sub_lord",
    "moon_sign_lord", "moon_star_lord", "moon_sub_lord",
    "day_lord", "matched_planets", "matched_houses", "dasha_matched",
]
DAY_FIELDS = [
    "date", "day_lord", "day_lord_signifies", "moon_rp_matched", "dasha_matched",
    "gate", "gate_reason",
    "windows_total", "strong_windows", "active_minutes", "strong_minutes", "windows_listed",
    # Compact per-day funnel (also expanded under topic diagnostics.days_detail)
    "cand_intervals", "pass_asc_l1", "pass_moon_l1", "pass_asc_star",
    "pass_house_coverage", "reject_top",
]

MAX_WINDOWS_LISTED_PER_DAY = 6

# Interval rejection / gate reason codes — assigned only for conditions that failed.
REASON_DASHA_MISSING = "DASHA_PERMISSION_MISSING"
REASON_DAY_LORD = "DAY_LORD_NOT_L1_L2"
REASON_ASC_SUB_L1 = "ASC_L1_MISMATCH"          # deciding asc sub not L1
REASON_MOON_SUB_L1 = "MOON_L1_MISMATCH"        # deciding moon sub not L1
REASON_ASC_STAR = "ASC_STAR_NOT_L1_L2"
REASON_HOUSE = "HOUSE_COVERAGE_INSUFFICIENT"
REASON_ASC_MOON = "ASC_MOON_CONVERGENCE_INSUFFICIENT"  # both deciding subs failed

CRITERIA = {
    "id": "rp_convergence_v2",
    "diagnostics_schema": "1.1",
    "version_note": (
        "Matching thresholds remain rp_convergence_v2. Diagnostics 1.1 adds "
        "coverage semantics, activation-scope tags, nested-topic diffs, and "
        "representative rejected intervals. Natal significators and house maps "
        "are unchanged. Identical activation across topics is explained when "
        "primary house sets are equal or nested — it is not forced apart."
    ),
    "significator_levels": {
        "asc_sub_and_moon_sub": "L1 only (in star of occupant) — deciding RPs",
        "asc_star_and_day_lord": "L1-L2",
        "dasha_permission": "L1-L2",
        "house_coverage": (
            "matched houses from the window's RPs must cover at least "
            "ceil(len(primary_houses)/2), minimum 1"
        ),
    },
    "coverage_semantics": COVERAGE_SEMANTICS,
    "day_gate": [
        "day lord signifies the topic at L1-L2",
        "at least one of the locked MD/AD/PD lords signifies the topic at L1-L2",
    ],
    "window_match": [
        "ascendant sub lord signifies at L1",
        "Moon sub lord signifies at L1",
        "ascendant star lord signifies at L1-L2",
        "matched houses cover at least half of the topic's primary houses",
    ],
    "grade": {
        "STRONG": (
            "day lord, ascendant star lord, ascendant sub lord and Moon sub lord "
            "all signify at L1, and house coverage is met"
        ),
        "ACTIVE": "window match satisfied but not all four core RPs at L1",
    },
    "merge": "contiguous matching intervals of the same grade are merged into one window",
    "listing": (
        f"windows[] lists at most {MAX_WINDOWS_LISTED_PER_DAY} windows per topic per day — the "
        "best moments of that day. windows_total / active_minutes / strong_* are from the "
        "complete qualifying set before the cap. Listed is always a subset of total."
    ),
    "aggregation": (
        "For a month or a range, aggregate days[] totals. Use windows[] only to name "
        "specific moments. Exact-time RP comes from days[].ruling_planets intervals."
    ),
    "not_a_prediction": (
        "RP convergence is an activation filter only. Zero RP windows with dasha "
        "permission means timing support is absent — not denial of natal promise."
    ),
    "methodology_limitations": [
        (
            "promotion and wealth share identical EVENT_HOUSES [2,6,10,11]; "
            "identical RP activation is correct under house-only matching."
        ),
        (
            "Half-coverage (ceil(n/2)) lets career [6,10,11] and promotion/wealth "
            "share windows when matched houses are e.g. [6,11] (meets need=2 for both)."
        ),
        (
            "children [5,11] need 1 house; relationship [5,7,11] need 2 — a single "
            "house-5 or house-11 hit can activate children without relationship."
        ),
        (
            "A more topic-sensitive coverage rule is methodologically discussable "
            "but would be a new convention (not applied). Thresholds stay v2."
        ),
    ],
    "reason_codes": [
        REASON_DASHA_MISSING, REASON_DAY_LORD, REASON_ASC_SUB_L1, REASON_MOON_SUB_L1,
        REASON_ASC_STAR, REASON_HOUSE, REASON_ASC_MOON,
    ],
}


def _secs(clock: str) -> int:
    h, m, s = (int(x) for x in clock.split(":"))
    return h * 3600 + m * 60 + s


def _clock(secs: int) -> str:
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"


def _min_houses_required(n_houses: int) -> int:
    return min_houses_required(n_houses)


def topic_significators(strength_map: dict, houses: Iterable[int]) -> dict:
    houses = list(houses)
    return {
        "l1": get_strong_significators_for_houses(strength_map, houses, 1),
        "l1_l2": get_strong_significators_for_houses(strength_map, houses, 2),
        "l1_l3": get_strong_significators_for_houses(strength_map, houses, 3),
    }


def _matched_houses(planets: Iterable[str], strength_map: dict, houses: Iterable[int],
                    max_level: int = 2) -> list[int]:
    return matched_houses_for_planets(planets, strength_map, houses, max_level=max_level)


def _rejection_sample(
    date_s: str, a: int, b: int, asc: list, moon: list, day_lord: str,
    reasons: list[str], evidence: dict, houses: list[int], need_houses: int,
    matched_planets: list[str],
) -> dict:
    return {
        "date": date_s,
        "start": _clock(a),
        "end": _clock(b),
        "duration_seconds": b - a,
        "asc_sign_lord": asc[3],
        "asc_star_lord": asc[5],
        "asc_sub_lord": asc[6],
        "moon_sign_lord": moon[3],
        "moon_star_lord": moon[5],
        "moon_sub_lord": moon[6],
        "day_lord": day_lord,
        "matched_planets": matched_planets,
        "matched_houses": evidence.get("matched_houses", []),
        "required_houses": list(houses),
        "min_houses_required": need_houses,
        "failed_conditions": list(reasons),
        "reason_codes": list(reasons),
        "evidence_flags": {
            k: v for k, v in evidence.items() if k != "matched_houses"
        },
    }


def _planet_level_for_houses(planet: str, strength_map: dict, houses: Iterable[int]) -> Optional[int]:
    """Best (lowest) significator level of planet for any of the topic houses, or None."""
    best = None
    wanted = set(houses)
    for h, info in strength_map.get(planet, {}).items():
        if h in wanted:
            lv = info["level"]
            if best is None or lv < best:
                best = lv
    return best


def _dasha_lords(day: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for lvl in ("md", "ad", "pd"):
        lord = (day.get("dasha", {}).get(lvl) or {}).get("lord")
        if lord:
            out.append((lvl.upper(), lord))
    return out


def _merged_intervals(asc_rows: list[list], moon_rows: list[list]) -> list[tuple[int, int, list, list]]:
    edges = sorted({_secs(r[0]) for r in asc_rows} | {_secs(r[1]) for r in asc_rows}
                   | {_secs(r[0]) for r in moon_rows} | {_secs(r[1]) for r in moon_rows})
    out: list[tuple[int, int, list, list]] = []
    ai = mi = 0
    for a, b in zip(edges, edges[1:]):
        while ai < len(asc_rows) - 1 and _secs(asc_rows[ai][1]) <= a:
            ai += 1
        while mi < len(moon_rows) - 1 and _secs(moon_rows[mi][1]) <= a:
            mi += 1
        out.append((a, b, asc_rows[ai], moon_rows[mi]))
    return out


def _house_set_relations(topics: dict[str, list[int]]) -> dict[str, dict]:
    """For each topic, note identical / subset / superset peers (explainability only)."""
    items = {t: tuple(h) for t, h in topics.items()}
    out: dict[str, dict] = {}
    for topic, houses in items.items():
        hs = set(houses)
        identical = sorted(t for t, h in items.items() if t != topic and h == houses)
        subsets = sorted(t for t, h in items.items() if t != topic and set(h) < hs)
        supersets = sorted(t for t, h in items.items() if t != topic and hs < set(h))
        out[topic] = {
            "houses": list(houses),
            "identical_house_set_with": identical,
            "has_subsets": subsets,
            "subset_of": supersets,
            "note": (
                f"Shares an identical primary house set with {identical}; "
                "identical RP activation is expected when significators and dasha gates match."
                if identical else
                f"Primary houses are a subset of {supersets}; activation may track those topics "
                "when matched houses always satisfy this topic's coverage too."
                if supersets else
                "Primary house set is unique among topics."
            ),
        }
    return out


def _gate_reasons(day_lord_ok: bool, dasha_matched: list[str]) -> list[str]:
    reasons: list[str] = []
    if not day_lord_ok:
        reasons.append(REASON_DAY_LORD)
    if not dasha_matched:
        reasons.append(REASON_DASHA_MISSING)
    return reasons


def _evaluate_interval(
    asc: list, moon: list, day_lord: str,
    l1: dict, l12: dict, houses: list[int], need_houses: int, strength_map: dict,
) -> tuple[Optional[dict], list[str], dict]:
    """
    Return (window_dict_or_None, rejection_reasons, evidence_flags).

    Reasons list every failed condition (not just the first).
    """
    asc_sub, asc_star, asc_sign = asc[6], asc[5], asc[3]
    m_sub, m_star, m_sign = moon[6], moon[5], moon[3]

    asc_sub_lv = _planet_level_for_houses(asc_sub, strength_map, houses)
    moon_sub_lv = _planet_level_for_houses(m_sub, strength_map, houses)
    asc_star_lv = _planet_level_for_houses(asc_star, strength_map, houses)

    evidence = {
        "asc_sub_l1": asc_sub_lv == 1,
        "asc_sub_l2": asc_sub_lv is not None and asc_sub_lv <= 2,
        "moon_sub_l1": moon_sub_lv == 1,
        "moon_sub_l2": moon_sub_lv is not None and moon_sub_lv <= 2,
        "asc_star_l1_l2": asc_star_lv is not None and asc_star_lv <= 2,
        "asc_contribution": asc_sub_lv == 1 or (asc_star_lv is not None and asc_star_lv <= 2),
        "moon_contribution": moon_sub_lv == 1,
    }

    reasons: list[str] = []
    if asc_sub not in l1:
        reasons.append(REASON_ASC_SUB_L1)
    if m_sub not in l1:
        reasons.append(REASON_MOON_SUB_L1)
    if asc_sub not in l1 and m_sub not in l1:
        reasons.append(REASON_ASC_MOON)
    if asc_star not in l12:
        reasons.append(REASON_ASC_STAR)

    rp_set = (day_lord, asc_sign, asc_star, asc_sub, m_sign, m_star, m_sub)
    matched_planets = sorted({p for p in rp_set if p in l12})
    matched_h = _matched_houses(matched_planets, strength_map, houses, max_level=2)
    evidence["matched_houses"] = matched_h
    evidence["matched_planets"] = matched_planets
    evidence["house_coverage_ok"] = len(matched_h) >= need_houses
    if len(matched_h) < need_houses:
        reasons.append(REASON_HOUSE)

    if reasons:
        return None, reasons, evidence

    core = (day_lord, asc_star, asc_sub, m_sub)
    grade = "STRONG" if all(p in l1 for p in core) else "ACTIVE"
    return {
        "grade": grade,
        "asc": (asc_sign, asc_star, asc_sub),
        "moon": (m_sign, m_star, m_sub),
        "matched": matched_planets,
        "matched_houses": matched_h,
        "l1_count": sum(1 for p in set(core) if p in l1),
        "evidence": {
            "l1_match": sorted({p for p in rp_set if p in l1}),
            "l2_match": sorted({p for p in rp_set if p in l12 and p not in l1}),
            "asc_contribution": True,
            "moon_contribution": True,
            "house_coverage": matched_h,
        },
    }, [], evidence


def build_rp_trigger_windows(
    days_list: list[dict],
    strength_map: dict,
    topics: Optional[dict] = None,
    max_listed: int = MAX_WINDOWS_LISTED_PER_DAY,
) -> dict:
    """
    Precompute per-topic RP trigger windows across every day in the pack.

    Each topic is evaluated independently against its own primary house list
    (a fresh list copy). There is no cross-topic result cache.
    """
    topics = {t: list(houses) for t, houses in (topics or EVENT_HOUSES).items()}
    relations = _house_set_relations(topics)
    result_topics: dict = {}
    # Full accepted-window fingerprints for nested/identical topic diffs (audit).
    topic_accept_index: dict[str, list[dict]] = {}

    for topic, houses in topics.items():
        # Independent evaluation — fresh copies, no shared mutable result objects.
        houses = list(houses)
        need_houses = _min_houses_required(len(houses))
        sigs = topic_significators(strength_map, houses)
        l1, l12 = dict(sigs["l1"]), dict(sigs["l1_l2"])
        l13 = dict(sigs["l1_l3"])

        day_rows: list[list] = []
        windows: list[list] = []
        days_detail: list[dict] = []
        counts = {
            "days_with_dasha_permission": 0,
            "days_passing_gate": 0,
            "days_gate_only": 0,
            "windows_total": 0,
            "windows_listed": 0,
            "strong_windows": 0,
            "active_minutes": 0,
            "strong_minutes": 0,
        }
        contributing_planets: set[str] = set()
        contributing_houses: set[int] = set()
        gate_fail_reasons: dict[str, int] = {}
        reject_totals: dict[str, int] = {}
        representative_rejections: list[dict] = []
        scope_counts: dict[str, int] = {}
        accepted_full: list[dict] = []

        for day in days_list:
            rp = day.get("ruling_planets")
            if not rp:
                continue
            date_s = day["date"]
            day_lord = rp["day_lord"]
            dasha_matched = [f"{lvl}:{lord}" for lvl, lord in _dasha_lords(day) if lord in l12]
            if dasha_matched:
                counts["days_with_dasha_permission"] += 1

            moon_ref = rp["reference_snapshot"]["moon"]
            moon_rp_matched = sorted(
                {p for p in (moon_ref["sign_lord"], moon_ref["star_lord"], moon_ref["sub_lord"])
                 if p in l12}
            )
            day_lord_ok = day_lord in l12
            gate_rs = _gate_reasons(day_lord_ok, dasha_matched)
            gate = not gate_rs

            empty_funnel = {
                "cand_intervals": 0, "pass_asc_l1": 0, "pass_moon_l1": 0,
                "pass_asc_star": 0, "pass_house_coverage": 0, "reject_top": "",
            }

            if not gate:
                reason_key = ";".join(gate_rs)
                gate_fail_reasons[reason_key] = gate_fail_reasons.get(reason_key, 0) + 1
                day_rows.append([
                    date_s, day_lord, day_lord_ok, moon_rp_matched, dasha_matched,
                    "NO_GATE", reason_key, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, "",
                ])
                days_detail.append({
                    "date": date_s, "gate": "NO_GATE", "gate_reasons": gate_rs,
                    "dasha_permission": bool(dasha_matched),
                    "dasha_matched": dasha_matched,
                    "houses_evaluated": houses,
                    "min_houses_required": need_houses,
                    **empty_funnel,
                    "rejection_reasons": {r: 0 for r in gate_rs},
                    "windows_total": 0, "windows_listed": 0,
                    "strong_windows": 0, "active_minutes": 0, "strong_minutes": 0,
                    "note": "Day gate failed — interval RP convergence was not evaluated.",
                })
                continue
            counts["days_passing_gate"] += 1

            asc_rows = rp["ascendant_windows"]
            moon_rows = rp["moon_windows"]
            funnel = {
                "cand_intervals": 0,
                "pass_asc_l1": 0,
                "pass_moon_l1": 0,
                "pass_asc_star": 0,
                "pass_house_coverage": 0,
            }
            day_rejects: dict[str, int] = {}
            raw: list[dict] = []

            for a, b, asc, moon in _merged_intervals(asc_rows, moon_rows):
                funnel["cand_intervals"] += 1
                w, reasons, evidence = _evaluate_interval(
                    asc, moon, day_lord, l1, l12, houses, need_houses, strength_map,
                )
                if evidence.get("asc_sub_l1"):
                    funnel["pass_asc_l1"] += 1
                if evidence.get("moon_sub_l1"):
                    funnel["pass_moon_l1"] += 1
                if evidence.get("asc_star_l1_l2"):
                    funnel["pass_asc_star"] += 1
                if evidence.get("house_coverage_ok"):
                    funnel["pass_house_coverage"] += 1
                if reasons:
                    for r in reasons:
                        day_rejects[r] = day_rejects.get(r, 0) + 1
                        reject_totals[r] = reject_totals.get(r, 0) + 1
                    sample = _rejection_sample(
                        date_s, a, b, asc, moon, day_lord,
                        reasons, evidence, houses, need_houses,
                        evidence.get("matched_planets", []),
                    )
                    prefer = REASON_HOUSE in reasons or (
                        evidence.get("asc_sub_l1") and evidence.get("moon_sub_l1")
                    )
                    sample["_prefer"] = bool(prefer)
                    if len(representative_rejections) < MAX_REPRESENTATIVE_REJECTIONS:
                        representative_rejections.append(sample)
                    elif prefer:
                        for i, old in enumerate(representative_rejections):
                            if not old.get("_prefer"):
                                representative_rejections[i] = sample
                                break
                    continue
                assert w is not None
                w["start"], w["end"] = a, b
                raw.append(w)

            merged: list[dict] = []
            for w in raw:
                prev = merged[-1] if merged else None
                if (prev and prev["end"] == w["start"] and prev["grade"] == w["grade"]
                        and prev["asc"] == w["asc"] and prev["moon"] == w["moon"]):
                    prev["end"] = w["end"]
                else:
                    merged.append(dict(w))

            strong = [w for w in merged if w["grade"] == "STRONG"]
            # Durations from the COMPLETE qualifying set — never from the listed cap.
            strong_min = round(sum(w["end"] - w["start"] for w in strong) / 60.0)
            active_min = round(sum(w["end"] - w["start"] for w in merged) / 60.0)
            counts["windows_total"] += len(merged)
            counts["strong_windows"] += len(strong)
            counts["active_minutes"] += active_min
            counts["strong_minutes"] += strong_min
            if not merged:
                counts["days_gate_only"] += 1

            for w in merged:
                contributing_planets.update(w["matched"])
                contributing_houses.update(w["matched_houses"])
                scope_info = classify_activation_scope(
                    topic, w["matched_houses"], houses, relations[topic],
                )
                scope_counts[scope_info["scope"]] = scope_counts.get(scope_info["scope"], 0) + 1
                accepted_full.append({
                    "date": date_s,
                    "start": _clock(w["start"]),
                    "end": _clock(w["end"]),
                    "duration_seconds": w["end"] - w["start"],
                    "grade": w["grade"],
                    "matched_houses": w["matched_houses"],
                    "matched_planets": w["matched"],
                    "activation_scope": scope_info,
                })

            ranked = sorted(
                merged,
                key=lambda w: (w["grade"] != "STRONG", -w["l1_count"],
                               -(w["end"] - w["start"]), w["start"]),
            )[:max_listed]
            for w in sorted(ranked, key=lambda w: w["start"]):
                windows.append([
                    date_s, _clock(w["start"]), _clock(w["end"]), w["grade"],
                    w["asc"][0], w["asc"][1], w["asc"][2],
                    w["moon"][0], w["moon"][1], w["moon"][2],
                    day_lord, w["matched"], w["matched_houses"], dasha_matched,
                ])
            counts["windows_listed"] += len(ranked)

            top_reject = ""
            if day_rejects:
                top_reject = max(day_rejects.items(), key=lambda kv: kv[1])[0]

            day_rows.append([
                date_s, day_lord, day_lord_ok, moon_rp_matched, dasha_matched,
                "TRIGGER" if merged else "GATE_ONLY",
                "PASS_NO_WINDOW" if not merged else "PASS",
                len(merged), len(strong), active_min, strong_min, len(ranked),
                funnel["cand_intervals"], funnel["pass_asc_l1"], funnel["pass_moon_l1"],
                funnel["pass_asc_star"], funnel["pass_house_coverage"], top_reject,
            ])
            days_detail.append({
                "date": date_s,
                "gate": "TRIGGER" if merged else "GATE_ONLY",
                "gate_reasons": [],
                "dasha_permission": True,
                "dasha_matched": dasha_matched,
                "houses_evaluated": houses,
                "min_houses_required": need_houses,
                "l1_planets": sorted(l1),
                "l2_planets": sorted(set(l12) - set(l1)),
                **funnel,
                "rejection_reasons": day_rejects,
                "windows_total": len(merged),
                "windows_listed": len(ranked),
                "listed_is_subset": len(ranked) <= len(merged),
                "strong_windows": len(strong),
                "active_minutes": active_min,
                "strong_minutes": strong_min,
                "note": (
                    "Dasha permission present; no interval met asc-sub L1 + moon-sub L1 "
                    "+ house coverage. Timing support absent — not a denial of promise."
                    if not merged else
                    f"{len(merged)} qualifying windows; {len(ranked)} listed (cap {max_listed})."
                ),
            })

        dasha_no_rp = (
            counts["days_with_dasha_permission"] > 0
            and counts["windows_total"] == 0
        )
        # Prove listed never exceeds total, and minutes come from full set
        assert counts["windows_listed"] <= counts["windows_total"]

        topic_accept_index[topic] = accepted_full

        diagnostics = {
            "houses_evaluated": houses,
            "min_houses_required": need_houses,
            "house_set_relations": relations[topic],
            "evaluation_independence": (
                "Topic evaluated in its own loop with a fresh house-list copy; "
                "no cross-topic activation cache."
            ),
            "coverage_rule": {
                "formula": COVERAGE_SEMANTICS["formula"],
                "min_houses_required": need_houses,
                "primary_houses": houses,
            },
            "l1_planets": sorted(l1),
            "l2_planets": sorted(set(l12) - set(l1)),
            "l1_count": len(l1),
            "l1_l2_count": len(l12),
            "l1_l3_count": len(l13),
            "contributing_planets": sorted(contributing_planets),
            "contributing_houses": sorted(contributing_houses),
            "activation_scope_counts": scope_counts,
            "gate_fail_reasons": gate_fail_reasons,
            "rejection_reason_totals": reject_totals,
            "representative_rejections": [
                {k: v for k, v in s.items() if k != "_prefer"}
                for s in representative_rejections
            ],
            "dasha_permission_without_rp_windows": dasha_no_rp,
            "dasha_without_rp_note": (
                "MD/AD/PD grant permission on some days, but no interval met the "
                "L1 asc/Moon-sub + house-coverage window test. Timing support is "
                "absent; this is not proof of denial."
                if dasha_no_rp else ""
            ),
            "identical_activation_explanation": (
                relations[topic]["note"]
                if relations[topic]["identical_house_set_with"] or relations[topic]["subset_of"]
                else ""
            ),
            "days_detail": days_detail,
        }

        result_topics[topic] = {
            "label": TOPIC_LABELS.get(topic, topic),
            "houses": houses,
            "significators": {k: sorted(v) for k, v in sigs.items()},
            "significator_levels": {k: sigs["l1_l3"][k] for k in sorted(sigs["l1_l3"])},
            "summary": counts,
            "diagnostics": diagnostics,
            "days": day_rows,
            "windows": windows,
        }

    cross_audit = _build_cross_topic_audit(topic_accept_index, relations, result_topics)

    return {
        "note": (
            "Precomputed RP activation windows per topic (criteria "
            f"{CRITERIA['id']}, diagnostics {CRITERIA['diagnostics_schema']}). "
            "Each topic is evaluated independently against its own primary houses. "
            "windows_total/active_minutes are complete; windows[] is capped. "
            "Zero RP windows ≠ denial of natal promise. Matching thresholds "
            "unchanged from v2; diagnostics 1.1 add coverage semantics and audits."
        ),
        "criteria": CRITERIA,
        "house_set_relations": relations,
        "cross_topic_audit": cross_audit,
        "timezone": (days_list[0].get("location", {}).get("timezone", "") if days_list else ""),
        "day_fields": DAY_FIELDS,
        "window_fields": WINDOW_FIELDS,
        "max_windows_listed_per_day": max_listed,
        "coverage": {
            "from": days_list[0]["date"] if days_list else None,
            "to": days_list[-1]["date"] if days_list else None,
        },
        "topics": result_topics,
    }


def _window_fingerprint(w: dict) -> tuple:
    return (
        w["date"], w["start"], w["end"], w["grade"],
        tuple(w.get("matched_houses") or []),
    )


def _build_cross_topic_audit(
    topic_accept_index: dict[str, list[dict]],
    relations: dict,
    result_topics: dict,
) -> dict:
    """
    Pairwise diffs for identical and nested topics — explains shared vs exclusive
    activations without changing match results.
    """
    pairs = []
    seen = set()
    for topic, rel in relations.items():
        for peer in rel.get("identical_house_set_with") or []:
            key = tuple(sorted((topic, peer)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append(("identical_houses", topic, peer))
        for peer in rel.get("has_subsets") or []:
            key = ("nested", topic, peer)  # topic is larger
            if key in seen:
                continue
            seen.add(key)
            pairs.append(("nested_superset", topic, peer))

    out_pairs = []
    for kind, a, b in pairs:
        wa = topic_accept_index.get(a) or []
        wb = topic_accept_index.get(b) or []
        sa = {_window_fingerprint(w): w for w in wa}
        sb = {_window_fingerprint(w): w for w in wb}
        # For nested, also compare by (date,start,end) ignoring houses — same RP moment
        if kind == "nested_superset":
            # a = larger topic, b = subset topic
            ka = {(w["date"], w["start"], w["end"]) for w in wa}
            kb = {(w["date"], w["start"], w["end"]) for w in wb}
            only_b_keys = kb - ka
            only_a_keys = ka - kb
            only_b = [
                w for w in wb if (w["date"], w["start"], w["end"]) in only_b_keys
            ][:MAX_NESTED_DIFF_SAMPLES]
            only_a = [
                w for w in wa if (w["date"], w["start"], w["end"]) in only_a_keys
            ][:MAX_NESTED_DIFF_SAMPLES]
            annotated_only_b = []
            for w in only_b:
                item = dict(w)
                if b == "children" and a == "relationship":
                    item["why_qualifies_for_subset_not_superset"] = (
                        explain_children_vs_relationship(item.get("matched_houses") or [])
                        or (
                            f"children matched_houses={item.get('matched_houses')} "
                            f"meet min_required=1 for [5,11]; relationship needs 2 of [5,7,11]."
                        )
                    )
                else:
                    item["why_qualifies_for_subset_not_superset"] = (
                        f"Matched houses {item.get('matched_houses')} satisfy "
                        f"{b} min_required="
                        f"{result_topics[b]['diagnostics']['min_houses_required']} "
                        f"but not {a} min_required="
                        f"{result_topics[a]['diagnostics']['min_houses_required']} "
                        f"(primary {result_topics[a]['houses']})."
                    )
                annotated_only_b.append(item)
            out_pairs.append({
                "relation": kind,
                "superset_topic": a,
                "subset_topic": b,
                "superset_windows_total": len(wa),
                "subset_windows_total": len(wb),
                "shared_moments": len(ka & kb),
                "subset_only_count": len(only_b_keys),
                "superset_only_count": len(only_a_keys),
                "subset_only_samples": annotated_only_b,
                "superset_only_samples": only_a,
                "selectivity_note": (
                    f"{b} can activate with fewer matched houses "
                    f"(need {result_topics[b]['diagnostics']['min_houses_required']} of "
                    f"{result_topics[b]['houses']}) than {a} "
                    f"(need {result_topics[a]['diagnostics']['min_houses_required']} of "
                    f"{result_topics[a]['houses']})."
                ),
            })
        else:
            shared = len(set(sa) & set(sb))
            out_pairs.append({
                "relation": kind,
                "topic_a": a,
                "topic_b": b,
                "windows_a": len(wa),
                "windows_b": len(wb),
                "identical_fingerprint_count": shared,
                "note": (
                    f"{a} and {b} share primary houses "
                    f"{result_topics[a]['houses']}; identical activation is expected."
                ),
            })

    # Explicit children vs relationship pointer for deliverable #2
    children_vs_rel = None
    for p in out_pairs:
        if p.get("relation") == "nested_superset" and p.get("subset_topic") == "children" \
                and p.get("superset_topic") == "relationship":
            children_vs_rel = p
            break

    return {
        "note": (
            "Audit only. Matching thresholds unchanged. Use subset_only_samples to "
            "explain children vs relationship (and similar nested pairs)."
        ),
        "pairs": out_pairs,
        "children_vs_relationship": children_vs_rel,
        "career_promotion_wealth": {
            "career_summary": (result_topics.get("career") or {}).get("summary"),
            "promotion_summary": (result_topics.get("promotion") or {}).get("summary"),
            "wealth_summary": (result_topics.get("wealth") or {}).get("summary"),
            "promotion_equals_wealth": (
                (result_topics.get("promotion") or {}).get("summary")
                == (result_topics.get("wealth") or {}).get("summary")
            ),
            "limitation": COVERAGE_SEMANTICS["selectivity_assessment"],
        },
    }
