"""
Schema 2.5 — coverage semantics, nested diffs, representative rejections.

Matching thresholds (rp_convergence_v2) are unchanged; these tests lock the
auditability contract and the documented half-coverage behaviour.
"""
from __future__ import annotations

from datetime import date

import pytest

from analysis.pack_builder import SCHEMA_VERSION, build_90day_pack
from analysis.rp_coverage import (
    COVERAGE_EXAMPLES,
    COVERAGE_SEMANTICS,
    explain_children_vs_relationship,
    min_houses_required,
)
from analysis.rp_triggers import (
    REASON_HOUSE,
    build_rp_trigger_windows,
)
from schemas.event_houses import EVENT_HOUSES

HYD = dict(
    prediction_city="Hyderabad, India",
    prediction_lat=17.385,
    prediction_lng=78.4867,
    prediction_tz="Asia/Kolkata",
)


def test_coverage_thresholds_for_documented_topics():
    assert min_houses_required(3) == 2  # career, relationship
    assert min_houses_required(4) == 2  # promotion, wealth
    assert min_houses_required(2) == 1  # children
    for topic, ex in COVERAGE_EXAMPLES.items():
        assert ex["primary_houses"] == EVENT_HOUSES[topic]
        assert ex["min_required"] == min_houses_required(ex["n"])
        assert len(ex["example_pass"]) >= ex["min_required"]
        assert len(ex["example_fail"]) < ex["min_required"]


def test_half_coverage_lets_career_core_pass_promotion():
    """[6,11] meets need=2 for career (3) and promotion (4) — documented limit."""
    assert len([6, 11]) >= min_houses_required(len(EVENT_HOUSES["career"]))
    assert len([6, 11]) >= min_houses_required(len(EVENT_HOUSES["promotion"]))
    assert len([6, 11]) >= min_houses_required(len(EVENT_HOUSES["wealth"]))
    assert "sufficiently selective" in COVERAGE_SEMANTICS["selectivity_assessment"] or \
           "NOT sufficiently selective" in COVERAGE_SEMANTICS["selectivity_assessment"]


def test_children_single_house_fails_relationship_coverage():
    msg = explain_children_vs_relationship([5])
    assert msg is not None
    assert "min_required=1" in msg or "children" in msg
    assert "relationship" in msg
    assert explain_children_vs_relationship([5, 11]) is None  # both pass


def _lvl(h: int, level: int = 1) -> dict:
    return {h: {"level": level, "link": "test"}}


def test_synthetic_children_only_interval_appears_in_cross_audit():
    """
    One interval matches house 5 only → children ACCEPT, relationship REJECT
    on coverage (need 2). Cross-audit must surface the exclusive children moment.
    """
    # Planets: Mercury L1 for house 5 only; Jupiter L1 for nothing useful for 7/11
    strength = {
        "Mercury": {5: {"level": 1, "link": "t"}, 11: {"level": 3, "link": "t"}},
        "Jupiter": {5: {"level": 1, "link": "t"}},
        "Venus": {7: {"level": 3, "link": "t"}},  # L3 only — not in L1-L2 filter
        "Sun": {2: {"level": 2, "link": "t"}},
        "Moon": {4: {"level": 2, "link": "t"}},
        "Mars": {3: {"level": 2, "link": "t"}},
        "Saturn": {8: {"level": 2, "link": "t"}},
        "Rahu": {12: {"level": 2, "link": "t"}},
        "Ketu": {6: {"level": 2, "link": "t"}},
    }
    # Asc/Moon rows: sub=Mercury (L1 for 5), star=Jupiter (L1 for 5) → in l1 for children
    # For relationship, L1 set is planets that signify 5/7/11 at L1 → Mercury, Jupiter
    # matched houses for relationship from those RPs: only 5 → need 2 → fail
    asc = ["00:00:00", "12:00:00", "Aries", "Mars", "Aswini", "Jupiter", "Mercury"]
    moon = ["00:00:00", "24:00:00", "Taurus", "Venus", "Rohini", "Moon", "Mercury"]
    day = {
        "date": "2026-11-22",
        "location": {"timezone": "Asia/Kolkata"},
        "dasha": {
            "md": {"lord": "Mercury"},
            "ad": {"lord": "Jupiter"},
            "pd": {"lord": "Mercury"},
        },
        "ruling_planets": {
            "day_lord": "Mercury",
            "reference_snapshot": {
                "moon": {"sign_lord": "Venus", "star_lord": "Moon", "sub_lord": "Mercury"},
            },
            "ascendant_windows": [asc],
            "moon_windows": [moon],
        },
    }
    tw = build_rp_trigger_windows(
        [day], strength,
        topics={"relationship": [5, 7, 11], "children": [5, 11]},
    )
    ch = tw["topics"]["children"]["summary"]
    rel = tw["topics"]["relationship"]["summary"]
    assert ch["windows_total"] >= 1
    assert rel["windows_total"] == 0
    audit = tw["cross_topic_audit"]["children_vs_relationship"]
    assert audit is not None
    assert audit["subset_only_count"] >= 1
    sample = audit["subset_only_samples"][0]
    assert sample["date"] == "2026-11-22"
    assert sample["matched_houses"] == [5]
    assert sample["grade"] in ("STRONG", "ACTIVE")
    assert "min_required=1" in (sample.get("why_qualifies_for_subset_not_superset") or "")


def test_synthetic_gate_only_has_representative_rejections():
    """Gate passes (day lord + dasha in L1-L2) but every interval fails — samples stored."""
    strength = {
        "Mercury": {2: {"level": 1, "link": "t"}, 7: {"level": 1, "link": "t"},
                    10: {"level": 1, "link": "t"}, 11: {"level": 1, "link": "t"}},
        "Sun": {2: {"level": 2, "link": "t"}},
        "Moon": {7: {"level": 2, "link": "t"}},
        "Mars": {10: {"level": 2, "link": "t"}},
        "Venus": {11: {"level": 2, "link": "t"}},
        "Jupiter": {3: {"level": 1, "link": "t"}},  # not business houses at L1 for deciding
        "Saturn": {8: {"level": 1, "link": "t"}},
        "Rahu": {12: {"level": 1, "link": "t"}},
        "Ketu": {6: {"level": 1, "link": "t"}},
    }
    # Asc/Moon subs are Saturn/Rahu — L1 for non-business houses → ASC/MOON L1 mismatch
    asc = ["00:00:00", "24:00:00", "Leo", "Sun", "Magha", "Ketu", "Saturn"]
    moon = ["00:00:00", "24:00:00", "Cancer", "Moon", "Pushya", "Saturn", "Rahu"]
    day = {
        "date": "2026-11-23",
        "location": {"timezone": "Asia/Kolkata"},
        "dasha": {
            "md": {"lord": "Mercury"},
            "ad": {"lord": "Venus"},
            "pd": {"lord": "Sun"},
        },
        "ruling_planets": {
            "day_lord": "Mercury",
            "reference_snapshot": {
                "moon": {"sign_lord": "Moon", "star_lord": "Saturn", "sub_lord": "Rahu"},
            },
            "ascendant_windows": [asc],
            "moon_windows": [moon],
        },
    }
    tw = build_rp_trigger_windows(
        [day], strength,
        topics={"business": [2, 7, 10, 11], "marriage": [2, 7, 11]},
    )
    for topic in ("business", "marriage"):
        block = tw["topics"][topic]
        assert block["summary"]["days_passing_gate"] == 1
        assert block["summary"]["windows_total"] == 0
        assert block["diagnostics"]["dasha_permission_without_rp_windows"] is True
        samples = block["diagnostics"]["representative_rejections"]
        assert samples, f"{topic} must expose rejected candidates"
        s0 = samples[0]
        for key in (
            "asc_star_lord", "asc_sub_lord", "moon_star_lord", "moon_sub_lord",
            "day_lord", "matched_planets", "matched_houses", "required_houses",
            "failed_conditions", "reason_codes",
        ):
            assert key in s0
        assert s0["required_houses"] == EVENT_HOUSES[topic]
        assert s0["reason_codes"]


@pytest.fixture(scope="module")
def pack14(natal):
    return build_90day_pack(
        natal_ref=natal, start_date=date(2026, 11, 22), num_days=14,
        reference_time="09:00", **HYD,
    )


def test_pack_schema_2_5_diagnostics(pack14):
    assert SCHEMA_VERSION >= "2.5"
    assert pack14["schema_version"] >= "2.5"
    tw = pack14["rp_trigger_windows"]
    assert tw["criteria"]["diagnostics_schema"] == "1.1"
    assert "coverage_semantics" in tw["criteria"]
    assert "methodology_limitations" in tw["criteria"]
    assert "cross_topic_audit" in tw
    assert tw["cross_topic_audit"]["career_promotion_wealth"]["promotion_equals_wealth"] is True
    # Thresholds unchanged vs v2.4 behaviour for promotion≡wealth
    p = tw["topics"]["promotion"]["summary"]
    w = tw["topics"]["wealth"]["summary"]
    assert p == w
    # Each topic carries coverage_rule + representative_rejections list
    for topic in ("career", "promotion", "business", "marriage"):
        d = tw["topics"][topic]["diagnostics"]
        assert d["coverage_rule"]["min_houses_required"] == min_houses_required(
            len(EVENT_HOUSES[topic])
        )
        assert isinstance(d["representative_rejections"], list)
        assert "activation_scope_counts" in d


def test_pack_warnings_document_selectivity_limits(pack14):
    blob = " ".join(pack14["validation"]["warnings"]).lower()
    assert "promotion" in blob and "wealth" in blob
    assert pack14["validation"]["overall"] == "PASS"
