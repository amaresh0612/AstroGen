"""
Optional client facts that change interpretation framing — not chart math.

Confirmed milestones (e.g. an already-announced promotion) must never be
described as pending future events in manifestation lists or AI copy.
"""
from __future__ import annotations

from typing import Any, Optional


KNOWN_MILESTONES = frozenset({
    "promotion_announced",
    "promotion_effective",
})


def resolve_client_facts(
    natal_ref: Optional[dict] = None,
    prediction_context: Optional[dict] = None,
    override: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Merge client facts from (priority high→low): override, prediction_context,
    natal_ref._meta / natal_ref.client_facts.
    """
    merged: dict[str, Any] = {
        "confirmed_milestones": [],
        "notes": "",
    }
    for source in (
        (natal_ref or {}).get("client_facts"),
        ((natal_ref or {}).get("_meta") or {}).get("client_facts"),
        (prediction_context or {}).get("client_facts"),
        override,
    ):
        if not isinstance(source, dict):
            continue
        milestones = source.get("confirmed_milestones") or []
        if milestones:
            merged["confirmed_milestones"] = sorted({
                str(m).strip() for m in milestones if str(m).strip()
            })
        if source.get("notes"):
            merged["notes"] = str(source["notes"])
        for k, v in source.items():
            if k not in ("confirmed_milestones", "notes") and v is not None:
                merged[k] = v
    return merged


def promotion_is_confirmed(facts: dict) -> bool:
    ms = set(facts.get("confirmed_milestones") or [])
    return bool(ms & {"promotion_announced", "promotion_effective"})
