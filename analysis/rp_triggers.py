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
Dasha permission is applied as a gate, so a window can never appear on a date
whose MD/AD/PD ignores the topic entirely.

Why the criterion is level-based
--------------------------------
Most charts signify most houses through *some* planet, so plain membership in
``signified_houses`` matches nearly every minute of the day and carries no
information. The filter therefore uses classical KP strength: Level 1 (in the
star of an occupant) and Level 2 (occupant) are the fruit-giving significators.
"""
from __future__ import annotations

from typing import Iterable, Optional

from analysis.significator_strength import get_strong_significators_for_houses
from schemas.event_houses import EVENT_HOUSES, TOPIC_LABELS

WINDOW_FIELDS = [
    "date", "start", "end", "grade",
    "asc_sign_lord", "asc_star_lord", "asc_sub_lord",
    "moon_sign_lord", "moon_star_lord", "moon_sub_lord",
    "day_lord", "matched_planets", "matched_houses", "dasha_matched",
]
DAY_FIELDS = [
    "date", "day_lord", "day_lord_signifies", "moon_rp_matched", "dasha_matched", "gate",
    "windows_total", "strong_windows", "active_minutes", "strong_minutes", "windows_listed",
]

MAX_WINDOWS_LISTED_PER_DAY = 6

CRITERIA = {
    "id": "rp_convergence_v1",
    "significator_levels": {
        "window": "L1-L2 (in star of occupant, or occupant)",
        "dasha_permission": "L1-L3",
    },
    "day_gate": [
        "day lord signifies the topic at L1-L2",
        "at least one of the locked MD/AD/PD lords signifies the topic at L1-L3",
    ],
    "window_match": [
        "ascendant sub lord signifies at L1-L2",
        "ascendant star lord signifies at L1-L2",
        "Moon sub lord signifies at L1-L2",
    ],
    "grade": {
        "STRONG": "day lord, ascendant star lord, ascendant sub lord and Moon sub lord all signify at L1",
        "ACTIVE": "window match satisfied but not all four at L1",
    },
    "merge": "contiguous matching intervals of the same grade are merged into one window",
    "listing": (
        f"windows[] lists at most {MAX_WINDOWS_LISTED_PER_DAY} windows per topic per day — the "
        "best moments of that day, ranked by grade, then L1 count, then duration. The ascendant "
        "sub lord changes ~249 times a day, so a qualifying day commonly has far more matches "
        "than that; days[] carries the full counts and total minutes for every day, and every "
        "unlisted window can be re-derived from that day's ascendant_windows and moon_windows, "
        "which are stored in full."
    ),
    "aggregation": (
        "For a month or a range, aggregate days[] (windows_total, strong_windows, "
        "active_minutes, strong_minutes). Use windows[] only to name specific moments."
    ),
    "not_a_prediction": (
        "RP convergence is an activation filter only. Judge natal promise (cuspal "
        "sublord) and dasha permission first; treat these windows as timing support."
    ),
}


def _secs(clock: str) -> int:
    h, m, s = (int(x) for x in clock.split(":"))
    return h * 3600 + m * 60 + s


def _clock(secs: int) -> str:
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"


def topic_significators(strength_map: dict, houses: Iterable[int]) -> dict:
    """L1, L1-L2 and L1-L3 significator sets for a topic's houses."""
    houses = list(houses)
    return {
        "l1": get_strong_significators_for_houses(strength_map, houses, 1),
        "l1_l2": get_strong_significators_for_houses(strength_map, houses, 2),
        "l1_l3": get_strong_significators_for_houses(strength_map, houses, 3),
    }


def _matched_houses(planets: Iterable[str], strength_map: dict, houses: Iterable[int],
                    max_level: int = 2) -> list[int]:
    wanted = set(houses)
    out: set[int] = set()
    for p in planets:
        for h, info in strength_map.get(p, {}).items():
            if h in wanted and info["level"] <= max_level:
                out.add(h)
    return sorted(out)


def _dasha_lords(day: dict) -> list[tuple[str, str]]:
    """[(level, lord)] for the locked MD/AD/PD of a daily record."""
    out: list[tuple[str, str]] = []
    for lvl in ("md", "ad", "pd"):
        lord = (day.get("dasha", {}).get(lvl) or {}).get("lord")
        if lord:
            out.append((lvl.upper(), lord))
    return out


def _merged_intervals(asc_rows: list[list], moon_rows: list[list]) -> list[tuple[int, int, list, list]]:
    """Intersection of the ascendant and Moon interval grids for one day."""
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


def build_rp_trigger_windows(
    days_list: list[dict],
    strength_map: dict,
    topics: Optional[dict] = None,
    max_listed: int = MAX_WINDOWS_LISTED_PER_DAY,
) -> dict:
    """
    Precompute per-topic RP trigger windows across every day in the pack.

    ``days_list`` must already carry a ``ruling_planets`` block (from
    ``analysis.rp_windows.build_day_rp``) and a ``dasha`` block per day.
    """
    topics = topics or EVENT_HOUSES
    result_topics: dict = {}

    for topic, houses in topics.items():
        sigs = topic_significators(strength_map, houses)
        l1, l12, l13 = sigs["l1"], sigs["l1_l2"], sigs["l1_l3"]

        day_rows: list[list] = []
        windows: list[list] = []
        counts = {"days_with_dasha_permission": 0, "days_passing_gate": 0,
                  "windows_total": 0, "windows_listed": 0, "strong_windows": 0,
                  "active_minutes": 0, "strong_minutes": 0}

        for day in days_list:
            rp = day.get("ruling_planets")
            if not rp:
                continue
            date_s = day["date"]
            day_lord = rp["day_lord"]
            dasha_matched = [f"{lvl}:{lord}" for lvl, lord in _dasha_lords(day) if lord in l13]
            if dasha_matched:
                counts["days_with_dasha_permission"] += 1

            moon_ref = rp["reference_snapshot"]["moon"]
            moon_rp_matched = sorted(
                {p for p in (moon_ref["sign_lord"], moon_ref["star_lord"], moon_ref["sub_lord"])
                 if p in l12}
            )
            day_lord_signifies = day_lord in l12
            gate = bool(day_lord_signifies and dasha_matched)

            if not gate:
                day_rows.append([date_s, day_lord, day_lord_signifies, moon_rp_matched,
                                 dasha_matched, "NO_GATE", 0, 0, 0, 0, 0])
                continue
            counts["days_passing_gate"] += 1

            raw: list[dict] = []
            for a, b, asc, moon in _merged_intervals(rp["ascendant_windows"], rp["moon_windows"]):
                asc_sub, asc_star, asc_sign = asc[6], asc[5], asc[3]
                m_sub, m_star, m_sign = moon[6], moon[5], moon[3]
                if not (asc_sub in l12 and asc_star in l12 and m_sub in l12):
                    continue
                core = (day_lord, asc_star, asc_sub, m_sub)
                grade = "STRONG" if all(p in l1 for p in core) else "ACTIVE"
                matched = sorted({p for p in (day_lord, asc_sign, asc_star, asc_sub,
                                              m_sign, m_star, m_sub) if p in l12})
                raw.append({
                    "start": a, "end": b, "grade": grade,
                    "asc": (asc_sign, asc_star, asc_sub),
                    "moon": (m_sign, m_star, m_sub),
                    "matched": matched,
                    "l1_count": sum(1 for p in set(core) if p in l1),
                })

            merged: list[dict] = []
            for w in raw:
                prev = merged[-1] if merged else None
                if (prev and prev["end"] == w["start"] and prev["grade"] == w["grade"]
                        and prev["asc"] == w["asc"] and prev["moon"] == w["moon"]):
                    prev["end"] = w["end"]
                else:
                    merged.append(dict(w))

            strong = [w for w in merged if w["grade"] == "STRONG"]
            strong_min = round(sum(w["end"] - w["start"] for w in strong) / 60.0)
            active_min = round(sum(w["end"] - w["start"] for w in merged) / 60.0)
            counts["windows_total"] += len(merged)
            counts["strong_windows"] += len(strong)
            counts["active_minutes"] += active_min
            counts["strong_minutes"] += strong_min

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
                    day_lord, w["matched"],
                    _matched_houses(w["matched"], strength_map, houses),
                    dasha_matched,
                ])
            counts["windows_listed"] += len(ranked)

            day_rows.append([date_s, day_lord, day_lord_signifies, moon_rp_matched,
                             dasha_matched, "TRIGGER" if merged else "GATE_ONLY",
                             len(merged), len(strong), active_min, strong_min, len(ranked)])

        result_topics[topic] = {
            "label": TOPIC_LABELS.get(topic, topic),
            "houses": list(houses),
            "significators": {k: sorted(v) for k, v in sigs.items()},
            "significator_levels": {k: sigs["l1_l3"][k] for k in sorted(sigs["l1_l3"])},
            "summary": counts,
            "days": day_rows,
            "windows": windows,
        }

    return {
        "note": (
            "Precomputed RP activation windows per topic. Timestamps are local "
            "wall-clock times in the pack's prediction timezone on the stated date."
        ),
        "criteria": CRITERIA,
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
