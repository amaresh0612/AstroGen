"""
End-to-end engine checks on a fictional chart: context, pack, exports, PDF.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from analysis.context import build_prediction_context
from analysis.cuspal_houses import get_cusp_longitudes, house_from_longitude, validate_cuspal_occupancy
from analysis.natal_fingerprint import build_natal_fingerprint
from analysis.pack_builder import build_90day_pack
from analysis.reference_exports import build_kp_rules, build_longterm_transits, longterm_transits_filename
from analysis.vimshottari import parse_dt
from reports.enhanced_pdf import build_enhanced_pdf
from schemas.event_houses import ALL_TOPICS
from tests.conftest import HYDERABAD, LOCK_DT


def test_natal_occupancy_is_cuspal(natal):
    assert validate_cuspal_occupancy(natal["planets"], natal["houses"]) == []


def test_house_from_longitude_rejects_bad_cusps():
    with pytest.raises(ValueError):
        house_from_longitude(10.0, [0.0] * 12)


def test_transit_houses_are_cuspal(natal):
    ctx = build_prediction_context(natal, date(2026, 10, 31), "09:00:00", **HYDERABAD)
    cusps = get_cusp_longitudes(natal["houses"])
    for p, t in ctx["transits"].items():
        assert t["transit_house"] == house_from_longitude(t["longitude"], cusps), p
        assert 1 <= t["transit_house_sign"] <= 12
    assert "cusp" in ctx["transit_house_basis"]


def test_context_all_topics_and_locked_dasha(natal):
    ctx = build_prediction_context(natal, date(2026, 10, 31), "09:00:00", query_mode="LONG_TERM",
                                   topics=list(ALL_TOPICS), **HYDERABAD)
    assert len(ctx["event_analyses"]) == len(ALL_TOPICS) == 16
    assert ctx["dasha"]["source"] == "locked_periods"
    for e in ctx["event_analyses"]:
        assert e["verdict"] in ("STRONG", "ACTIVE", "MODERATE", "MIXED", "WEAK")
        assert 0.0 <= e["score"]["pct10"] <= 10.0
        if not e["dasha_covered_houses"]:
            assert e["score"]["pct10"] <= 4.0


def test_hora_before_sunrise_belongs_to_previous_night(natal):
    ctx = build_prediction_context(natal, date(2026, 10, 31), "04:30:00", **HYDERABAD)
    assert ctx["hora"]["hora_day"] == "2026-10-30"
    assert ctx["hora"]["current_hora_lord"]
    after = build_prediction_context(natal, date(2026, 10, 31), "09:00:00", **HYDERABAD)
    assert after["hora"]["hora_day"] == "2026-10-31"
    # Saturday's first day hora is Saturn
    assert after["hora"]["full_day_sequence"][0]["lord"] == "Saturn"


def test_pack_follows_locked_pd_across_boundary(natal):
    rows = natal["dasha"]["locked_periods"]
    boundary = next(parse_dt(r["pd_end"]) for r in rows if parse_dt(r["pd_end"]) > LOCK_DT + timedelta(days=5))
    start = (boundary - timedelta(days=2)).date()
    pack = build_90day_pack(natal, start, 5, "Hyderabad, India", 17.385, 78.4867, "Asia/Kolkata",
                            reference_time="09:00")
    v = pack["validation"]
    assert v["overall"] == "PASS", v["issues"]
    assert v["warnings"] == []
    pds = [d["dasha"]["pd"]["lord"] for d in pack["days"]]
    assert len(set(pds)) == 2, pds
    assert all(d["dasha"]["source"].startswith("LOCKED") for d in pack["days"])
    assert pack["companion_files"]["longterm_transits"] == longterm_transits_filename(start)


def test_kp_rules_schema():
    rules = build_kp_rules()
    assert set(rules) == {"schema_version", "rules_version", "generated_at", "notes",
                          "event_house_map", "topic_labels", "kp_methodology"}
    assert set(rules["event_house_map"]) == set(ALL_TOPICS)


def test_longterm_transits_schema(natal):
    lt = build_longterm_transits(natal, date(2026, 10, 31))
    assert lt["valid_from"] == "2026-10-31" and lt["valid_to"] == "2031-10-31"
    assert lt["cache_key"] == "longterm_transits_2026_2031.json"
    assert lt["transits"]
    for t in lt["transits"]:
        assert {"planet", "ingress_date", "transit_house", "transit_house_sign",
                "conjunct_natal_planets"} <= set(t)
        for p in t["conjunct_natal_planets"]:
            assert natal["planets"][p]["sign"] == t["to_sign"]


def test_fingerprint_schema_and_stability(natal):
    fp = build_natal_fingerprint(natal)
    assert fp["chart_id"] == "Test_Subject-19920315-1030"
    assert len(fp["hash"]) == 16 and fp["locked"] is True
    relocked = dict(natal, dasha={**natal["dasha"], "locked_at": "2030-01-01T00:00:00"})
    assert build_natal_fingerprint(relocked)["hash"] == fp["hash"]


def test_pdf_builds(natal):
    ctx = build_prediction_context(natal, date(2026, 10, 31), "09:00:00", query_mode="LONG_TERM",
                                   topics=list(ALL_TOPICS), **HYDERABAD)
    buf = build_enhanced_pdf(natal, ctx, almanac_days=3, topics=list(ALL_TOPICS))
    data = buf.getvalue()
    assert data.startswith(b"%PDF") and len(data) > 10_000
