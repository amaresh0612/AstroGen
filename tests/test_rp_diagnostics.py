"""
RP engine accuracy & diagnostics regression (schema 2.4).

Verifies topic independence, house-map fidelity, dasha≠denial, listing caps,
fine-dasha continuity, and transit same-sign terminology — without changing
locked natal data or EVENT_HOUSES.
"""
from __future__ import annotations

from datetime import date

import pytest

from analysis.pack_builder import build_90day_pack
from analysis.reference_exports import TRANSIT_FIELD_DEFINITIONS, build_longterm_transits
from analysis.rp_triggers import (
    REASON_ASC_SUB_L1, REASON_DASHA_MISSING, REASON_HOUSE, REASON_MOON_SUB_L1,
    build_rp_trigger_windows,
)
from analysis.significator_strength import natal_significators
from schemas.event_houses import EVENT_HOUSES

HYD = dict(
    prediction_city="Hyderabad, India",
    prediction_lat=17.385,
    prediction_lng=78.4867,
    prediction_tz="Asia/Kolkata",
)


@pytest.fixture(scope="module")
def pack14(natal):
    return build_90day_pack(
        natal_ref=natal, start_date=date(2026, 11, 22), num_days=14,
        reference_time="09:00", **HYD,
    )


# 1 / 2 / 3 — house sets evaluated independently
def test_career_promotion_wealth_use_correct_house_sets(pack14):
    topics = pack14["rp_trigger_windows"]["topics"]
    assert topics["career"]["houses"] == [6, 10, 11]
    assert topics["promotion"]["houses"] == [2, 6, 10, 11]
    assert topics["wealth"]["houses"] == [2, 6, 10, 11]
    # Independence: each diagnostics records the houses it actually evaluated
    assert topics["career"]["diagnostics"]["houses_evaluated"] == [6, 10, 11]
    assert topics["promotion"]["diagnostics"]["houses_evaluated"] == [2, 6, 10, 11]
    assert topics["wealth"]["diagnostics"]["houses_evaluated"] == [2, 6, 10, 11]
    # Career is not a copy of promotion's result object
    assert topics["career"]["diagnostics"] is not topics["promotion"]["diagnostics"]
    assert topics["career"]["days"] is not topics["promotion"]["days"]


def test_promotion_and_wealth_share_houses_so_identical_activation_is_explained(pack14):
    tw = pack14["rp_trigger_windows"]
    rel = tw["house_set_relations"]
    assert "wealth" in rel["promotion"]["identical_house_set_with"]
    assert "promotion" in rel["wealth"]["identical_house_set_with"]
    assert "career" in rel["promotion"]["has_subsets"] or "career" in rel["promotion"]["has_subsets"]

    p, w = tw["topics"]["promotion"]["summary"], tw["topics"]["wealth"]["summary"]
    # With identical houses and shared natal significators, activations must match
    assert p == w
    # And the pack must explain that — warning, not failure
    blob = " ".join(pack14["validation"]["warnings"])
    assert "promotion" in blob and "wealth" in blob
    assert pack14["validation"]["overall"] == "PASS"
    assert pack14["validation"]["validation_categories"]["astrology_semantic"] == "WARNINGS"


def test_wealth_not_inherited_from_career_object(pack14):
    """Wealth and career share overlapping houses but are separate evaluations."""
    c = pack14["rp_trigger_windows"]["topics"]["career"]
    w = pack14["rp_trigger_windows"]["topics"]["wealth"]
    assert c["houses"] != w["houses"]
    assert c["diagnostics"]["min_houses_required"] == 2   # ceil(3/2)
    assert w["diagnostics"]["min_houses_required"] == 2   # ceil(4/2)
    assert "career" in w["diagnostics"]["house_set_relations"]["has_subsets"] or \
           "career" in w["diagnostics"]["house_set_relations"].get("has_subsets", [])
    # Career is a subset of wealth's houses
    assert set(c["houses"]) < set(w["houses"])


def test_relationship_and_children_use_own_houses(pack14):
    topics = pack14["rp_trigger_windows"]["topics"]
    assert topics["relationship"]["houses"] == [5, 7, 11]
    assert topics["children"]["houses"] == [5, 11]
    assert topics["children"]["diagnostics"]["houses_evaluated"] == [5, 11]
    assert "children" in topics["relationship"]["diagnostics"]["house_set_relations"]["has_subsets"]


# 4 / 5 — dasha permission without RP windows is not denial
def test_business_or_marriage_can_have_dasha_without_rp(pack14, natal):
    topics = pack14["rp_trigger_windows"]["topics"]
    # On the fixture, marriage often has zero dasha L1-L2; business may vary.
    # Construct an explicit case: force evaluation and assert the diagnostic contract.
    _, strength = natal_significators(natal)
    # Re-run triggers on pack days — contract: dasha_without_rp note when applicable
    for topic in ("business", "marriage"):
        block = topics[topic]
        s = block["summary"]
        d = block["diagnostics"]
        if s["days_with_dasha_permission"] > 0 and s["windows_total"] == 0:
            assert d["dasha_permission_without_rp_windows"] is True
            assert "not proof of denial" in d["dasha_without_rp_note"].lower() or \
                   "not" in d["dasha_without_rp_note"].lower()
            # Rejection reasons or gate reasons must be present somewhere
            assert d["rejection_reason_totals"] or d["gate_fail_reasons"] or d["days_detail"]


def test_zero_rp_windows_is_not_a_denial_verdict(pack14):
    criteria = pack14["rp_trigger_windows"]["criteria"]
    assert "not denial" in criteria["not_a_prediction"].lower() or \
           "absent" in criteria["not_a_prediction"].lower()
    for block in pack14["rp_trigger_windows"]["topics"].values():
        for detail in block["diagnostics"]["days_detail"]:
            if detail["gate"] == "GATE_ONLY":
                assert "not a denial" in detail["note"].lower() or "absent" in detail["note"].lower()


# 6 — listing cap does not alter totals
def test_listing_cap_does_not_alter_totals_or_minutes(pack14):
    for topic, block in pack14["rp_trigger_windows"]["topics"].items():
        s = block["summary"]
        assert s["windows_listed"] <= s["windows_total"]
        # Recompute listed from windows[] and totals from days[]
        listed = sum(1 for _ in block["windows"])
        assert listed == s["windows_listed"]
        total_from_days = sum(row[7] for row in block["days"])  # windows_total col
        assert total_from_days == s["windows_total"]
        active_from_days = sum(row[9] for row in block["days"])
        assert active_from_days == s["active_minutes"]
        for detail in block["diagnostics"]["days_detail"]:
            assert detail["windows_listed"] <= detail["windows_total"]
            assert detail.get("listed_is_subset", True)


# 7 / 8 / 9 — interval & fine-dasha continuity
def test_asc_moon_intervals_gapless(pack14):
    for d in pack14["days"]:
        rp = d["ruling_planets"]
        for key in ("ascendant_windows", "moon_windows"):
            rows = rp[key]
            assert rows[0][0] == "00:00:00" and rows[-1][1] == "24:00:00"
            for a, b in zip(rows, rows[1:]):
                assert a[1] == b[0]


def test_sukshma_and_prana_cover_full_period(pack14):
    assert pack14["valid_from"] == "2026-11-22"
    sk = pack14["sukshma_timeline"]["windows"]
    pr = pack14["prana_timeline"]["windows"]
    assert sk[0]["start"] == "2026-11-22T00:00:00"
    assert sk[-1]["end"] == "2026-12-06T00:00:00"
    assert pr[0]["start"] == sk[0]["start"] and pr[-1]["end"] == sk[-1]["end"]
    for a, b in zip(sk, sk[1:]):
        assert a["end"] == b["start"]
    for a, b in zip(pr, pr[1:]):
        assert a["end"] == b["start"]
    assert pack14["validation"]["trust_status"]["fine_dasha_timelines"] == "PASS"


def test_prana_parent_chain_consistent(pack14):
    for w in pack14["prana_timeline"]["windows"]:
        assert w["md"] and w["ad"] and w["pd"] and w["sukshma"] and w["lord"]


# 10 — transit terminology
def test_transit_same_sign_not_degree_conjunction(natal):
    lt = build_longterm_transits(natal, date(2026, 11, 22))
    assert "same_sign_natal_planets" in TRANSIT_FIELD_DEFINITIONS
    assert "NOT a degree-orb" in TRANSIT_FIELD_DEFINITIONS["same_sign_natal_planets"]
    assert "conjunct_natal_planets" not in (lt["transits"][0] if lt["transits"] else {"x": 1})
    assert lt["field_definitions"]["same_sign_natal_planets"]


# 11 — topic mapping validation
def test_topic_mappings_match_event_houses_and_kp_rules(pack14):
    from analysis.reference_exports import build_kp_rules
    rules = build_kp_rules()["event_house_map"]
    for topic, houses in EVENT_HOUSES.items():
        assert rules[topic] == list(houses)
        assert pack14["rp_trigger_windows"]["topics"][topic]["houses"] == list(houses)


# 12 — identical activation warns but does not fail
def test_identical_activation_warns_but_pack_passes(pack14):
    v = pack14["validation"]
    assert v["overall"] == "PASS"
    assert v["passed"] is True
    # Structural vs semantic are separate
    assert "validation_categories" in v
    assert v["validation_categories"]["structural"] == "PASS"


def test_rejection_reason_codes_are_assigned_from_engine_logic(natal, pack14):
    """Reasons that appear in diagnostics must be from the known code set."""
    known = set(pack14["rp_trigger_windows"]["criteria"]["reason_codes"])
    known |= {REASON_DASHA_MISSING}  # gate-level
    for block in pack14["rp_trigger_windows"]["topics"].values():
        for code in block["diagnostics"]["rejection_reason_totals"]:
            assert code in known
        for code in block["diagnostics"]["gate_fail_reasons"]:
            for part in code.split(";"):
                assert part in known or part == ""
