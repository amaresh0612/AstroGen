"""
Static reference JSON builders — separate from the 90-day calculation pack.

Produces:
  • kp_rules.json              — topic house mappings + KP methodology (no predictions)
  • longterm_transits_*.json   — raw slow-planet ingress calculations (no interpretation)
"""
from __future__ import annotations

from datetime import date

from analysis.kp_constants import utc_now_iso
from analysis.long_term_transits import compute_long_term_transits_raw
from analysis.transits import TRANSIT_HOUSE_BASIS
from analysis.natal_fingerprint import natal_reference_filename
from schemas.event_houses import EVENT_HOUSES, TOPIC_LABELS

RULES_SCHEMA_VERSION = "1.0"
RULES_VERSION = "2026.11"
TRANSITS_SCHEMA_VERSION = "1.0"


def build_kp_rules() -> dict:
    """Return static KP event-house rules for AI interpretation."""
    return {
        "schema_version": RULES_SCHEMA_VERSION,
        "rules_version": RULES_VERSION,
        "generated_at": utc_now_iso(),
        "notes": (
            "Topic-specific house mappings and KP evaluation order only. "
            "No scores, no predictions, no generic denial-house labels."
        ),
        "event_house_map": {topic: list(houses) for topic, houses in EVENT_HOUSES.items()},
        "topic_labels": {topic: TOPIC_LABELS.get(topic, topic) for topic in EVENT_HOUSES},
        "kp_methodology": {
            "evaluation_order": [
                "cuspal_sublord_of_required_houses",
                "natal_significators",
                "locked_dasha_md_ad_pd",
                "ruling_planets_at_query_time",
                "transits_as_trigger",
            ],
            "dasha_role": "permission — event cannot manifest without dasha covering required houses",
            "transit_role": "trigger — confirms timing, not primary verdict",
            "rp_role": "calculated dynamically at exact query time/location",
            "house_context_rule": (
                "Each house's relevance is topic-specific. Do not apply generic denial "
                "labels (e.g. H12 is required for travel/foreign settlement)."
            ),
        },
    }


build_kp_event_rules = build_kp_rules


def _horizon_end(from_date: date, horizon_years: int) -> date:
    try:
        return from_date.replace(year=from_date.year + horizon_years)
    except ValueError:  # 29 Feb → 28 Feb
        return from_date.replace(year=from_date.year + horizon_years, day=28)


def longterm_transits_filename(from_date: date, horizon_years: int = 5) -> str:
    """Reusable cache filename keyed by date range, not birth date."""
    return f"longterm_transits_{from_date.year}_{_horizon_end(from_date, horizon_years).year}.json"


def build_longterm_transits(
    natal_ref: dict,
    from_date: date,
    horizon_years: int = 5,
) -> dict:
    """Raw long-term transit ingress data — calculations only, no interpretation fields."""
    house1_deg = float(natal_ref.get("houses", {}).get("1", {}).get("cusp_degree", 0))
    transits = compute_long_term_transits_raw(
        natal_asc_lon=house1_deg,
        natal_planets=natal_ref.get("planets", {}),
        from_date=from_date,
        horizon_years=horizon_years,
        natal_houses=natal_ref.get("houses", {}),
    )
    return {
        "schema_version": TRANSITS_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "valid_from": from_date.isoformat(),
        "valid_to": _horizon_end(from_date, horizon_years).isoformat(),
        "horizon_years": horizon_years,
        "ayanamsa": "Lahiri",
        "cache_key": longterm_transits_filename(from_date, horizon_years),
        "natal_reference_file": natal_reference_filename(natal_ref),
        "transit_house_basis": TRANSIT_HOUSE_BASIS,
        "notes": (
            "Raw slow-planet sign-change ingress data only. "
            "Topic relevance is determined by the AI layer using kp_rules.json."
        ),
        "transits": transits,
    }
