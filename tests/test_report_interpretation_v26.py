"""Phase-1/3 interpretation & consistency regressions (schema 2.6)."""
from __future__ import annotations

from datetime import date

import pytest

from analysis.pack_builder import SCHEMA_VERSION, build_90day_pack
from analysis.promise_denial import (
    MANIFESTATION_MAP,
    POST_PROMOTION_MANIFESTATION_MAP,
    _rank_manifestations,
    compute_promise_denial,
)
from analysis.report_consistency import (
    check_promotion_framing,
    check_timed_vs_static_interpretation,
    run_prepublication_checks,
)
from analysis.significator_strength import natal_significators
from reports.pdf.rp_evidence_section import summarise_rp_triggers_for_pdf
from schemas.client_facts import promotion_is_confirmed, resolve_client_facts

HYD = dict(
    prediction_city="Hyderabad, India",
    prediction_lat=17.385,
    prediction_lng=78.4867,
    prediction_tz="Asia/Kolkata",
)


def test_post_promotion_manifestations_never_pending():
    items = _rank_manifestations("promotion", 8.0, [], promotion_confirmed=True)
    blob = " ".join(items).lower()
    for banned in ("shortlisting", "not yet indicated", "awaiting", "pending"):
        assert banned not in blob
    assert any("implementation" in x.lower() or "authority" in x.lower() for x in items)


def test_unconfirmed_promotion_map_still_exists():
    assert "promotion" in MANIFESTATION_MAP
    assert "promotion" in POST_PROMOTION_MANIFESTATION_MAP


def test_compute_promise_denial_respects_confirmed_milestone(natal):
    _, strength = natal_significators(natal)
    dasha = natal.get("dasha") or {}
    md = (dasha.get("locked_md") or {}).get("lord", "Saturn")
    ad = (dasha.get("locked_ad") or {}).get("lord", "Mercury")
    pd = (dasha.get("locked_pd") or {}).get("lord", "Venus")
    entry = compute_promise_denial(
        "promotion",
        natal["planets"], natal["houses"], natal["cuspal_sublords"], strength,
        md, ad, pd,
        significators=natal.get("significators"),
        confirmed_milestones=["promotion_announced"],
    )
    assert entry["manifestation_mode"] == "post_promotion_assessment"
    blob = " ".join(entry["manifestations"]).lower()
    assert "shortlisting" not in blob


def test_consistency_blocks_pending_promotion_copy():
    issues = check_promotion_framing(
        ["Promotion discussion or shortlisting"],
        confirmed=True,
    )
    assert any(i["code"] == "PROMOTION_STILL_PENDING" for i in issues)


def test_consistency_blocks_zero_window_as_time_supported():
    summary = {
        "topics": {
            "business": {
                "windows_total": 0,
                "days_passing_gate": 39,
                "timing_label": "Timing support absent",
            },
            "marriage": {
                "windows_total": 0,
                "days_passing_gate": 39,
                "dasha_permission_without_rp_windows": True,
            },
        }
    }
    issues = check_timed_vs_static_interpretation(
        narrative_text="Business is time-supported by ruling planets this quarter.",
        rp_trigger_summary=summary,
    )
    assert any(i["code"] == "ZERO_WINDOW_AS_TIME_SUPPORTED" for i in issues)


def test_rp_trigger_summary_labels_timing(natal):
    pack = build_90day_pack(
        natal_ref=natal, start_date=date(2026, 11, 22), num_days=7,
        reference_time="09:00", **HYD,
    )
    assert SCHEMA_VERSION == "2.6"
    assert "reproducibility" in pack
    assert pack["reproducibility"]["rp_criteria_id"] == "rp_convergence_v2"
    summary = summarise_rp_triggers_for_pdf(pack["rp_trigger_windows"])
    assert summary["max_windows_listed_per_day"] == 6
    for topic, block in summary["topics"].items():
        assert "windows_total" in block and "windows_listed" in block
        assert "timing_label" in block
        assert block["windows_listed"] <= block["windows_total"] or block["windows_total"] == 0


def test_prepublication_pass_on_clean_pack(natal):
    pack = build_90day_pack(
        natal_ref=natal, start_date=date(2026, 11, 22), num_days=3,
        reference_time="09:00", **HYD,
    )
    result = run_prepublication_checks(natal_ref=natal, pack=pack, narrative_text="")
    assert result["overall"] in ("PASS", "WARNINGS")
    assert result["block_publication"] is False


def test_client_facts_resolve_promotion():
    facts = resolve_client_facts(
        {"client_facts": {"confirmed_milestones": ["promotion_effective"]}},
    )
    assert promotion_is_confirmed(facts)


def test_children_only_interval_explanation_preserved():
    """Documented children-only moment semantics (house 5, need 1 vs relationship need 2)."""
    from analysis.rp_coverage import explain_children_vs_relationship
    msg = explain_children_vs_relationship([5])
    assert msg and "min_required=1" in msg and "relationship" in msg
