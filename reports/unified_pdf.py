"""
Unified KP Calculation & Evidence PDF.

One report for the human: natal chart tables + enhanced evidence sections.
No AI narrative. The AI Calculation Pack ZIP is a separate download.

Assembles:
  1. Enhanced cover (birth, prediction location, active dasha, RP, transits)
  2. Natal planet/cusp table, chart image, full MD/AD timeline, PD detail, muhurtha
  3. KP significator matrix + activation / promise-denial + long-term transits
  4. Sukshma evidence windows
  5. 90-day almanac

Does not call or modify ``generate_pdf_report`` in app.py.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, SimpleDocTemplate

from analysis.context import PredictionLocationRequired
from analysis.almanac_builder import build_almanac
from analysis.long_term_transits import compute_long_term_transits
from analysis.promise_denial import compute_all_topics
from analysis.significator_strength import natal_significators
from reports.enhanced_pdf import _cover_story, _fine_windows_story
from reports.pdf.almanac_section import build_almanac_section
from reports.pdf.kp_packet_section import build_kp_packet_section
from reports.pdf.natal_chart_section import build_natal_chart_section
from schemas.event_houses import EVENT_HOUSES


def build_unified_pdf(
    natal_ref: dict,
    prediction_context: dict,
    chart_result: Optional[dict] = None,
    almanac_days: int = 90,
    topics: Optional[list[str]] = None,
    include_almanac: bool = True,
    include_kp_packet: bool = True,
    include_long_term: bool = True,
    query_lat: Optional[float] = None,
    query_lng: Optional[float] = None,
    query_tz: Optional[str] = None,
    query_city: Optional[str] = None,
    confirmed_milestones: Optional[list[str]] = None,
    rp_trigger_windows: Optional[dict] = None,
) -> io.BytesIO:
    """
    Build the single KP Calculation & Evidence Report.

    ``prediction_context`` must already carry an explicit prediction location.
    ``chart_result`` is optional and only used for the natal chart wheel PNG.
    """
    ctx = prediction_context
    for key, given in (("query_lat", query_lat), ("query_lng", query_lng), ("query_tz", query_tz)):
        stored = ctx.get(key)
        if stored is None:
            raise PredictionLocationRequired(f"prediction_context has no {key}")
        if given is not None and (
            given != stored if key == "query_tz"
            else abs(float(given) - float(stored)) > 1e-6
        ):
            raise ValueError(f"{key}={given!r} differs from prediction_context {stored!r}")
    query_lat = ctx["query_lat"]
    query_lng = ctx["query_lng"]
    query_tz = ctx["query_tz"]

    query_date_str = ctx.get("query_date", "")
    try:
        ref_date = date.fromisoformat(str(query_date_str)[:10])
    except (ValueError, TypeError):
        ref_date = date.today()

    from reportlab.lib.styles import getSampleStyleSheet
    from schemas.client_facts import resolve_client_facts
    from reports.pdf.rp_evidence_section import summarise_rp_triggers_for_pdf

    styles = getSampleStyleSheet()
    story: list = []

    facts = resolve_client_facts(
        natal_ref, ctx,
        {"confirmed_milestones": confirmed_milestones} if confirmed_milestones else None,
    )
    milestones = list(facts.get("confirmed_milestones") or [])
    # Attach timed-RP summary for cover RP sections (static vs timed).
    pack_rp = rp_trigger_windows or ctx.get("rp_trigger_windows")
    if pack_rp and not ctx.get("rp_trigger_summary"):
        ctx = {**ctx, "rp_trigger_summary": summarise_rp_triggers_for_pdf(pack_rp)}
    if milestones and not ctx.get("client_facts"):
        ctx = {**ctx, "client_facts": facts}

    story.extend(_cover_story(natal_ref, ctx, styles))

    story.append(PageBreak())
    story.extend(build_natal_chart_section(
        natal_ref,
        chart_result=chart_result,
        query_date=ref_date,
        query_lat=query_lat,
        query_lng=query_lng,
        query_tz=query_tz,
    ))

    if include_kp_packet:
        story.append(PageBreak())
        significators, strength_map = natal_significators(natal_ref)
        dasha = ctx.get("dasha", {})
        pd_list = compute_all_topics(
            natal_ref.get("planets", {}),
            natal_ref.get("houses", {}),
            natal_ref.get("cuspal_sublords", {}),
            strength_map,
            dasha.get("md_lord", ""),
            dasha.get("ad_lord", ""),
            dasha.get("pd_lord", ""),
            topics=topics,
            significators=significators,
            confirmed_milestones=milestones,
        )
        lt_list = ctx.get("long_term_transits", [])
        if include_long_term and not lt_list:
            house1_deg = float(natal_ref.get("houses", {}).get("1", {}).get("cusp_degree", 0))
            lt_list = compute_long_term_transits(
                natal_asc_lon=house1_deg,
                natal_planets=natal_ref.get("planets", {}),
                from_date=ref_date,
                horizon_years=5,
                event_house_map=EVENT_HOUSES,
                natal_houses=natal_ref.get("houses", {}),
            )
        story.extend(build_kp_packet_section(
            strength_map,
            pd_list,
            lt_list if include_long_term else [],
        ))
        story.extend(_fine_windows_story(ctx, styles))

    if include_almanac:
        almanac_rows = build_almanac(
            natal_ref,
            from_date=ref_date,
            days=almanac_days,
            query_lat=query_lat,
            query_lng=query_lng,
            query_tz=query_tz,
        )
        story.append(PageBreak())
        story.extend(build_almanac_section(almanac_rows))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )
    doc.build(story)
    buffer.seek(0)
    return buffer
