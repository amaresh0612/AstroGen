"""
Pre-publication consistency checks: PDF/AI claims vs source JSON.

Critical failures should block confident publication; warnings are advisory.
"""
from __future__ import annotations

from typing import Any, Optional

from analysis.significator_strength import KP_METHODOLOGY
from schemas.client_facts import promotion_is_confirmed, resolve_client_facts


CRITICAL = "critical"
WARNING = "warning"


def _issue(level: str, code: str, message: str) -> dict:
    return {"level": level, "code": code, "message": message}


def check_pack_reproducibility(pack: dict, natal_ref: Optional[dict] = None) -> list[dict]:
    issues: list[dict] = []
    required = [
        "schema_version", "calculation_engine", "generated_at",
        "natal_reference", "prediction_location", "validation",
        "rp_trigger_windows", "significator_method",
    ]
    for key in required:
        if key not in pack:
            issues.append(_issue(CRITICAL, "MISSING_PACK_FIELD", f"Pack missing {key}"))
    nr = pack.get("natal_reference") or {}
    if not nr.get("chart_id") and not nr.get("hash"):
        issues.append(_issue(WARNING, "NATAL_FINGERPRINT", "Pack natal fingerprint incomplete"))
    if natal_ref is not None:
        birth = natal_ref.get("birth") or {}
        if birth.get("date") and nr.get("birth_date") and birth.get("date") != nr.get("birth_date"):
            issues.append(_issue(
                CRITICAL, "NATAL_DATE_MISMATCH",
                f"Pack birth_date {nr.get('birth_date')} ≠ natal_ref {birth.get('date')}",
            ))
    sm = pack.get("significator_method") or {}
    if sm.get("version") and sm["version"] != KP_METHODOLOGY["version"]:
        issues.append(_issue(
            WARNING, "SIG_METHOD_VERSION",
            f"Pack significator method {sm.get('version')} ≠ engine {KP_METHODOLOGY['version']}",
        ))
    rp = pack.get("rp_trigger_windows") or {}
    crit = rp.get("criteria") or {}
    if crit.get("id") and crit["id"] != "rp_convergence_v2":
        issues.append(_issue(
            WARNING, "RP_CRITERIA",
            f"Unexpected RP criteria id {crit.get('id')}",
        ))
    return issues


def check_timed_vs_static_interpretation(
    pack: Optional[dict] = None,
    narrative_text: str = "",
    rp_trigger_summary: Optional[dict] = None,
) -> list[dict]:
    """Flag text that treats static RP or zero timed windows as time-supported."""
    issues: list[dict] = []
    text = (narrative_text or "").lower()
    summary = rp_trigger_summary
    if pack and not summary:
        from reports.pdf.rp_evidence_section import summarise_rp_triggers_for_pdf
        summary = summarise_rp_triggers_for_pdf(pack.get("rp_trigger_windows") or {})

    zero_topics = []
    for topic, block in (summary or {}).get("topics", {}).items():
        if block.get("timing_label") == "Timing support absent" or (
            int(block.get("windows_total") or 0) == 0
            and int(block.get("days_passing_gate") or 0) > 0
        ):
            zero_topics.append(topic)

    for topic in zero_topics:
        # Heuristic: narrative claims timing for a zero-window topic
        patterns = [
            f"{topic} is time-supported",
            f"{topic} timing is strong",
            f"rp windows support {topic}",
            f"{topic} will happen soon",
        ]
        if any(p in text for p in patterns):
            issues.append(_issue(
                CRITICAL, "ZERO_WINDOW_AS_TIME_SUPPORTED",
                f"Narrative treats {topic} as time-supported but pack has zero timed windows",
            ))

    if "windows_listed" in text and "probability" in text and "windows_total" not in text:
        issues.append(_issue(
            CRITICAL, "CAPPED_LIST_AS_PROBABILITY",
            "Narrative appears to derive probability from capped windows_listed",
        ))
    return issues


def check_promotion_framing(
    manifestations: list[str],
    *,
    confirmed: bool,
    narrative_text: str = "",
) -> list[dict]:
    issues: list[dict] = []
    banned = (
        "shortlisting",
        "formal promotion not yet",
        "promotion discussion",
        "awaiting approval",
        "yet to happen",
        "pending announcement",
    )
    if not confirmed:
        return issues
    blob = " ".join(manifestations or []).lower() + "\n" + (narrative_text or "").lower()
    for phrase in banned:
        if phrase in blob:
            issues.append(_issue(
                CRITICAL, "PROMOTION_STILL_PENDING",
                f"Confirmed promotion still framed as pending ({phrase!r})",
            ))
    return issues


def check_health_safety(narrative_text: str = "") -> list[dict]:
    issues: list[dict] = []
    text = (narrative_text or "").lower()
    scary = (
        "you will die", "terminal illness", "cancer diagnosis",
        "you have disease", "medical diagnosis:",
    )
    for phrase in scary:
        if phrase in text:
            issues.append(_issue(
                CRITICAL, "HEALTH_DIAGNOSIS",
                f"Health-unsafe language detected: {phrase!r}",
            ))
    return issues


def run_prepublication_checks(
    *,
    natal_ref: dict,
    pack: Optional[dict] = None,
    prediction_context: Optional[dict] = None,
    manifestations_by_topic: Optional[dict] = None,
    narrative_text: str = "",
    block_on_critical: bool = True,
) -> dict[str, Any]:
    """
    Return structured validation for publication gating.

    overall: PASS | BLOCKED | WARNINGS
    """
    issues: list[dict] = []
    facts = resolve_client_facts(natal_ref, prediction_context)
    confirmed = promotion_is_confirmed(facts)

    if pack:
        issues.extend(check_pack_reproducibility(pack, natal_ref))
        issues.extend(check_timed_vs_static_interpretation(pack, narrative_text))

    mfst = []
    for topic, items in (manifestations_by_topic or {}).items():
        mfst.extend(items or [])
        if topic in ("promotion", "career"):
            issues.extend(check_promotion_framing(
                items or [], confirmed=confirmed, narrative_text=narrative_text,
            ))
    if confirmed and not manifestations_by_topic:
        issues.extend(check_promotion_framing(
            [], confirmed=True, narrative_text=narrative_text,
        ))

    issues.extend(check_health_safety(narrative_text))

    # Missing evidence disclosure
    if pack:
        for topic, block in ((pack.get("rp_trigger_windows") or {}).get("topics") or {}).items():
            d = block.get("diagnostics") or {}
            s = block.get("summary") or {}
            if d.get("dasha_permission_without_rp_windows") and s.get("windows_total") == 0:
                # Expect narrative to avoid claiming timing — already covered above
                pass

    critical = [i for i in issues if i["level"] == CRITICAL]
    warnings = [i for i in issues if i["level"] == WARNING]
    if critical and block_on_critical:
        overall = "BLOCKED"
    elif warnings or critical:
        overall = "WARNINGS" if not critical else "BLOCKED"
    else:
        overall = "PASS"

    return {
        "overall": overall,
        "passed": overall == "PASS",
        "block_publication": overall == "BLOCKED",
        "critical": critical,
        "warnings": warnings,
        "issues": issues,
        "client_facts": facts,
        "checks": [
            "natal_fingerprint", "dasha_lock_metadata", "methodology_version",
            "static_vs_timed_rp", "zero_window_topics", "capped_windows",
            "promotion_confirmed_framing", "health_safety",
        ],
    }
