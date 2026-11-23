"""
Classical KP significator rules, node agency, verdict bands and Sukshma/Prana windows.
"""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta

import pytest

from analysis.context import build_prediction_context
from analysis.fine_windows import fine_dasha_windows, topic_links
from analysis.pack_builder import build_90day_pack
from analysis.promise_denial import VERDICT_BANDS, verdict_for_score
from analysis.significator_strength import (
    compute_significator_strength, natal_significators, significators_are_current,
)
from analysis.vimshottari import resolve_dasha
from schemas.event_houses import EVENT_HOUSES
from tests.conftest import HYDERABAD

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


def _houses_from_aries():
    return {str(h): {"sign": SIGNS[h - 1]} for h in range(1, 13)}


def _planet(house, sign, star_lord):
    return {"house": house, "sign": sign, "star_lord": star_lord}


def _synthetic():
    # Aries rising, one sign per house. Mars owns 1 & 8, Venus owns 2 & 7, etc.
    return {
        "Sun":     _planet(10, "Capricorn", "Moon"),
        "Moon":    _planet(4,  "Cancer",    "Venus"),
        "Mars":    _planet(3,  "Gemini",    "Rahu"),
        "Mercury": _planet(11, "Aquarius",  "Mars"),
        "Jupiter": _planet(9,  "Sagittarius", "Ketu"),
        "Venus":   _planet(5,  "Leo",       "Venus"),
        "Saturn":  _planet(6,  "Virgo",     "Sun"),
        "Rahu":    _planet(6,  "Virgo",     "Mercury"),
        "Ketu":    _planet(12, "Pisces",    "Mercury"),
    }


def test_star_lord_direction_is_classical():
    sm = compute_significator_strength(_synthetic(), _houses_from_aries())
    # Sun is in the star of Moon (occupies 4, owns 4/Cancer): Sun gets L1 for 4, not Moon for 10.
    assert sm["Sun"][4]["level"] == 1
    assert sm["Sun"][10]["level"] == 2             # own occupation
    assert sm["Sun"][5]["level"] == 4              # owns Leo
    assert 10 not in sm["Moon"]                    # old reversed rule would have given Moon H10
    # Mercury in star of Mars: Mars occupies 3 (L1), owns 1 and 8 (L3)
    assert sm["Mercury"][3]["level"] == 1
    assert sm["Mercury"][1]["level"] == 3 and sm["Mercury"][8]["level"] == 3


def test_node_agency():
    planets = _synthetic()
    sm = compute_significator_strength(planets, _houses_from_aries())
    # Rahu in Virgo: agent of Mercury (sign lord) and Saturn (same sign)
    for h, info in sm["Mercury"].items():
        assert h in sm["Rahu"] and sm["Rahu"][h]["level"] <= info["level"]
    for h in sm["Saturn"]:
        assert h in sm["Rahu"]
    # Mars is in Rahu's star: inherits agents' occupation (Mercury H11, Saturn H6) at L1
    assert sm["Mars"][11]["level"] == 1 and sm["Mars"][6]["level"] == 1
    # Ketu in Pisces: agent of Jupiter
    for h in sm["Jupiter"]:
        assert h in sm["Ketu"]


def test_verdict_never_contradicts_score(natal):
    ctx = build_prediction_context(natal, date(2026, 10, 31), "09:00:00", query_mode="LONG_TERM", **HYDERABAD)
    for e in ctx["event_analyses"]:
        assert e["verdict"] == verdict_for_score(e["score"]["pct10"]), e["topic"]
        if e["dark_houses"]:
            assert e["verdict"] not in ("STRONG", "ACTIVE")
    thresholds = [t for t, _ in VERDICT_BANDS]
    assert thresholds == sorted(thresholds, reverse=True)
    assert verdict_for_score(8.8) == "STRONG" and verdict_for_score(3.9) == "WEAK"


def test_topic_definitions():
    assert EVENT_HOUSES["promotion"] == [2, 6, 10, 11]
    assert {5, 9}.issubset(EVENT_HOUSES["job_change"])
    assert EVENT_HOUSES["business"] == [2, 7, 10, 11]
    assert 4 in EVENT_HOUSES["travel_home"] and EVENT_HOUSES["expenses"] == [12]
    assert topic_links([12]) .get("expenses") == [12]
    assert "travel" not in topic_links([3])          # 1 of 3 houses is below half
    assert topic_links([3, 12])["travel"] == [3, 12]


def test_sukshma_windows_are_contiguous_and_inside_pd(natal):
    sigs, _ = natal_significators(natal)
    start, end = datetime(2026, 9, 1), datetime(2026, 12, 31)
    ws = fine_dasha_windows(natal, start, end, sigs, "sukshma")
    assert ws
    assert datetime.fromisoformat(ws[0]["start"]) <= start
    assert datetime.fromisoformat(ws[-1]["end"]) >= end
    for a, b in zip(ws, ws[1:]):
        assert a["end"] == b["start"]
    for w in ws:
        mid = datetime.fromisoformat(w["start"]) + (datetime.fromisoformat(w["end"]) - datetime.fromisoformat(w["start"])) / 2
        r = resolve_dasha(natal, mid)
        assert (w["md"], w["ad"], w["pd"]) == (r["md"]["lord"], r["ad"]["lord"], r["pd"]["lord"])
        assert w["signified_houses"] == sorted(sigs[w["lord"]]["signified_houses"])
        assert w["dasha_source"] == "locked_periods"


def test_prana_windows_nest_inside_sukshma(natal):
    sigs, _ = natal_significators(natal)
    start = datetime(2026, 11, 1)
    sk = fine_dasha_windows(natal, start, start + timedelta(days=10), sigs, "sukshma")
    pr = fine_dasha_windows(natal, start, start + timedelta(days=10), sigs, "prana")
    for p in pr:
        parent = [s for s in sk if s["start"] <= p["start"] and p["end"] <= s["end"]]
        assert parent and parent[0]["lord"] == p["sukshma"]


def test_context_exposes_fine_windows(natal):
    ctx = build_prediction_context(natal, date(2026, 10, 31), "09:00:00", query_mode="LONG_TERM", **HYDERABAD)
    fw = ctx["fine_dasha_windows"]
    assert fw["sukshma"] and fw["prana"]
    assert set(ctx["dasha"]["house_links"]) >= {"md", "ad", "pd", "sukshma", "prana"}
    assert ctx["significator_method"]["version"] == "2.0"
    assert ctx["significator_method"]["recomputed_from_natal"] is False
    for ev in ctx["event_evidence"]:
        for w in ev["sukshma_windows"]:
            assert set(w["houses"]).issubset(ev["required_houses"])


def test_app_chart_uses_same_engine(natal):
    import ast
    from pathlib import Path
    from analysis.significator_strength import APP_HOUSE_KEYS, significators_from_app_chart

    chart_result = {
        "planets": {p: {"full_degree": d["longitude"], "sign": d["sign"], "nakshatra_lord": d["star_lord"]}
                    for p, d in natal["planets"].items()},
        "houses": {key: {"cusp_degree": natal["houses"][str(i)]["cusp_degree"],
                         "sign": natal["houses"][str(i)]["sign"]}
                   for i, key in enumerate(APP_HOUSE_KEYS, 1)},
    }
    got = significators_from_app_chart(chart_result)
    for p, s in natal["significators"].items():
        assert got[p]["signified_houses"] == s["signified_houses"], p
        assert got[p]["occupied_house"] == natal["planets"][p]["house"], p

    src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "compute_kp_significators")
    assert "significators_from_app_chart" in ast.unparse(fn)


def test_old_natal_file_is_recomputed_not_trusted(natal):
    old = copy.deepcopy(natal)
    old["kp_methodology"]["version"] = "1.0"
    old["significators"]["Sun"]["signified_houses"] = [4, 10]   # what the reversed rule stored
    assert not significators_are_current(old)
    sigs, _ = natal_significators(old)
    assert sigs["Sun"]["signified_houses"] == natal["significators"]["Sun"]["signified_houses"]

    ctx = build_prediction_context(old, date(2026, 10, 31), "09:00:00", **HYDERABAD)
    assert ctx["significator_method"]["recomputed_from_natal"] is True

    pack = build_90day_pack(old, start_date=date(2026, 10, 31), num_days=2,
                            prediction_city="Hyderabad, India", prediction_lat=17.385,
                            prediction_lng=78.4867, prediction_tz="Asia/Kolkata")
    assert pack["validation"]["passed"]
    assert any("predate method" in w for w in pack["validation"]["warnings"])
    assert pack["significator_method"]["natal_file_current"] is False
    assert "signified_houses" in pack["days"][0]["dasha"]["sukshma"]
