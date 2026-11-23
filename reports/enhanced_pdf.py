"""
Enhanced PDF report builder.

Assembles the full enhanced KP report from a PredictionContext (or directly
from natal_ref + almanac). This is a standalone builder — it does not modify
or replace the existing generate_pdf_report() in app.py.

Output PDF contains:
    Page 1   : Cover — birth metadata, active dasha, key chart snapshot
    Page 2   : KP Significator strength table (Level 1–4)
    Page 3   : Event promise/denial analysis
    Page 4   : Long-term transit windows (5 years)
    Pages 5+ : 90-day almanac (landscape, ~20 days per page)

Usage
-----
    from analysis.context import load_natal_ref, build_prediction_context
    from reports.enhanced_pdf import build_enhanced_pdf
    from datetime import date

    natal = load_natal_ref()
    ctx   = build_prediction_context(
        natal, date.today(), query_mode="LONG_TERM",
        query_location="Hyderabad, India", query_lat=17.385, query_lng=78.4867,
        query_tz="Asia/Kolkata",
    )
    pdf_bytes = build_enhanced_pdf(natal, ctx, almanac_days=90)
    # pdf_bytes is an io.BytesIO — pass to st.download_button or write to file.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)

from analysis.context import PredictionLocationRequired, build_prediction_context, load_natal_ref
from analysis.almanac_builder import build_almanac
from analysis.significator_strength import natal_significators
from analysis.promise_denial import compute_all_topics
from analysis.long_term_transits import compute_long_term_transits
from reports.pdf.almanac_section import build_almanac_section
from reports.pdf.kp_packet_section import build_kp_packet_section
from schemas.event_houses import EVENT_HOUSES, TOPIC_LABELS

ACCENT    = colors.HexColor("#8B4513")
GOLD      = colors.HexColor("#C9963A")
HEADER_BG = colors.HexColor("#FFF8DC")


def _fine_windows_story(ctx: dict, styles) -> list:
    """Sukshma windows with signified houses — evidence table, no interpretation."""
    windows = (ctx.get("fine_dasha_windows") or {}).get("sukshma") or []
    if not windows:
        return []
    title_sty = ParagraphStyle("fw_title", parent=styles["Heading2"], textColor=ACCENT, fontSize=11)
    note_sty = ParagraphStyle("fw_note", parent=styles["Normal"], fontSize=7, leading=9,
                              textColor=colors.HexColor("#444444"))
    head = ParagraphStyle("fw_head", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7)
    cell = ParagraphStyle("fw_cell", parent=styles["Normal"], fontSize=7, leading=9)

    rows = [[Paragraph(h, head) for h in
             ("From", "To", "MD / AD / PD", "Sukshma", "Signified houses", "Topic houses touched")]]
    for w in windows:
        touched = "; ".join(
            f"{TOPIC_LABELS.get(t, t)} (H{','.join(map(str, hs))})" for t, hs in w["topics"].items()
        ) or "—"
        rows.append([Paragraph(str(c), cell) for c in (
            w["start"].replace("T", " "), w["end"].replace("T", " "),
            f"{w['md']} / {w['ad']} / {w['pd']}", w["lord"],
            ", ".join(map(str, w["signified_houses"])) or "—", touched,
        )])
    table = Table(rows, colWidths=[0.95*inch, 0.95*inch, 1.15*inch, 0.6*inch, 1.0*inch, 2.6*inch],
                  repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAF5")]),
    ]))
    return [
        PageBreak(),
        Paragraph("Sukshma Windows (beneath locked PD)", title_sty),
        Paragraph(
            "Each Sukshma lord with the natal houses it signifies (classical KP levels, node agency). "
            "A topic is listed when the lord covers at least half of its primary houses. "
            "Evidence only — not part of the activation score and not a prediction.",
            note_sty,
        ),
        Spacer(1, 0.08 * inch),
        table,
    ]


def _cover_story(natal_ref: dict, ctx: dict, styles) -> list:
    """Build cover page flowables."""
    title_sty = ParagraphStyle("et", parent=styles["Heading1"],
                                textColor=ACCENT, alignment=TA_CENTER, fontSize=16)
    sub_sty   = ParagraphStyle("es", parent=styles["Normal"],
                                textColor=colors.HexColor("#6E665A"),
                                alignment=TA_CENTER, fontSize=9)
    h3_sty    = ParagraphStyle("eh3", parent=styles["Heading3"], textColor=ACCENT, fontSize=10)
    tiny      = ParagraphStyle("etiny", parent=styles["Normal"], fontSize=8, leading=10)
    bold8     = ParagraphStyle("ebold", parent=styles["Normal"], fontSize=8,
                                fontName="Helvetica-Bold", leading=10)

    birth = natal_ref.get("birth", {})
    dasha = ctx.get("dasha", {})
    num   = ctx.get("numerology", {})
    panch = ctx.get("panchanga", {})

    story = [
        Paragraph("AstroGen — KP Calculation & Evidence Report", title_sty),
        Paragraph(
            "KP Vedic Astrology · Locked Natal Reference  "
            "· This report contains calculated data and evidence only. "
            "Interpretation and predictions are produced by the AI layer using this data.",
            sub_sty,
        ),
        Spacer(1, 0.2 * inch),
    ]

    # Birth details table
    birth_rows = [
        ["Name",         birth.get("name", "")],
        ["Date of Birth",birth.get("date", "")],
        ["Time of Birth",birth.get("time", "")],
        ["Place",        birth.get("place", "")],
        ["Ayanamsa",     f"{birth.get('ayanamsa', 0):.4f}° (Lahiri)"],
        ["Coordinates",  f"{birth.get('lat', 0):.4f}°, {birth.get('lng', 0):.4f}°"],
        ["Timezone",     birth.get("tz", "")],
        ["Name Number",  str(num.get("name_number", ""))],
        ["Life Path",    str(num.get("life_path", ""))],
    ]
    bt = Table([[Paragraph(r[0], bold8), Paragraph(r[1], tiny)] for r in birth_rows],
               colWidths=[1.5 * inch, 4.5 * inch])
    bt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), HEADER_BG),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([Paragraph("Birth Details", h3_sty), bt, Spacer(1, 0.12 * inch)])

    # Prediction location (explicitly separate from natal/birth location) — from the context
    pred_lat, pred_lng = float(ctx["query_lat"]), float(ctx["query_lng"])
    same_as_natal = (abs(pred_lat - float(birth.get("lat", 999))) < 0.05
                     and abs(pred_lng - float(birth.get("lng", 999))) < 0.05)

    pred_rows = [
        ["Prediction City",  ctx.get("query_location", "")],
        ["Prediction Coords", f"{pred_lat:.4f}°, {pred_lng:.4f}°"],
        ["Prediction TZ",    ctx.get("query_tz", "")],
        ["Same as natal?",   "YES — prediction location entered equals birth place" if same_as_natal
                              else "NO — separate current location used ✓"],
    ]
    pt = Table([[Paragraph(r[0], bold8), Paragraph(r[1], tiny)] for r in pred_rows],
               colWidths=[1.5 * inch, 4.5 * inch])
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F4FE")),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR",  (1, 3), (1, 3),
         colors.HexColor("#2E7D32") if not same_as_natal else colors.HexColor("#B71C1C")),
    ]))
    story.extend([Paragraph("Prediction Location (Almanac / Kalam / Hora)", h3_sty),
                  pt, Spacer(1, 0.12 * inch)])

    # Active dasha
    dasha_rows = [
        ["Mahadasha",   f"{dasha.get('md_lord','')} ({dasha.get('md_start','')} → {dasha.get('md_end','')})"],
        ["Antardasha",  f"{dasha.get('ad_lord','')} ({dasha.get('ad_start','')} → {dasha.get('ad_end','')})"],
        ["Pratyantar",  f"{dasha.get('pd_lord','')} ({dasha.get('pd_start','')} → {dasha.get('pd_end','')})"],
        ["Sukshma",     f"{dasha.get('sukshma_lord','–')} ({dasha.get('sukshma_start','–')} → {dasha.get('sukshma_end','–')})"],
        ["MD/AD/PD source", dasha.get("source", "")],
    ]
    dt = Table([[Paragraph(r[0], bold8), Paragraph(r[1], tiny)] for r in dasha_rows],
               colWidths=[1.5 * inch, 4.5 * inch])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), HEADER_BG),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([Paragraph("Active Vimshottari Dasha", h3_sty), dt, Spacer(1, 0.15 * inch)])

    # Key transits snapshot
    transits = ctx.get("transits", {})
    tr_rows = [["Planet", "Transit Sign", "Nak", "Star", "Sub", "House (cusp)"]]
    for pname in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]:
        t = transits.get(pname, {})
        if not t:
            continue
        tr_rows.append([pname, t.get("sign",""), t.get("nakshatra",""),
                         t.get("star_lord",""), t.get("sub_lord",""),
                         str(t.get("transit_house",""))])
    if len(tr_rows) == 1:
        tr_rows.append(["—", "unavailable", "—", "—", "—", "—"])
    tr_table = Table(
        [[Paragraph(str(c), tiny if i > 0 else ParagraphStyle("th", parent=styles["Normal"],
                    fontName="Helvetica-Bold", fontSize=7)) for c in r]
         for i, r in enumerate(tr_rows)],
        colWidths=[0.75*inch, 0.85*inch, 1.0*inch, 0.65*inch, 0.65*inch, 0.5*inch],
    )
    tr_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAF5")]),
    ]))
    story.extend([Paragraph(f"Current Transits — {ctx.get('query_date','')}", h3_sty),
                  tr_table])

    # ── Ruling Planets ────────────────────────────────────────────
    rp = ctx.get("ruling_planets", {})
    if rp:
        story.append(Spacer(1, 0.15 * inch))
        rp_label = ParagraphStyle("rp_label", parent=styles["Normal"], fontSize=7,
                                  fontName="Helvetica-Bold", leading=9)
        rp_val   = ParagraphStyle("rp_val",   parent=styles["Normal"], fontSize=7, leading=9)
        rp_data = [
            ["Day Lord",            rp.get("day_lord", "")],
            ["Asc Sign / Sign Lord", f"{rp.get('ascendant_sign','')} / {rp.get('ascendant_sign_lord','')}"],
            ["Asc Star Lord",       rp.get("ascendant_star_lord", "")],
            ["Asc Sub Lord",        rp.get("ascendant_sub_lord", "")],
            ["Moon Sign / Sign Lord",f"{rp.get('moon_sign','')} / {rp.get('moon_sign_lord','')}"],
            ["Moon Star Lord",      rp.get("moon_star_lord", "")],
            ["Moon Sub Lord",       rp.get("moon_sub_lord", "")],
            ["RP List",             ", ".join(rp.get("rp_list", []))],
        ]
        rp_table = Table(
            [[Paragraph(r[0], rp_label), Paragraph(str(r[1]), rp_val)] for r in rp_data],
            colWidths=[1.5*inch, 4.5*inch],
        )
        rp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), HEADER_BG),
            ("GRID",       (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.extend([
            Paragraph(f"Ruling Planets — {rp.get('reference_time','')} @ {rp.get('reference_location','')}", h3_sty),
            rp_table,
        ])

        from reports.pdf.rp_evidence_section import (
            build_static_rp_alignment_section,
            build_timed_rp_activation_section,
        )
        story.extend(build_static_rp_alignment_section(rp))
        story.extend(build_timed_rp_activation_section(
            ctx.get("rp_trigger_summary"),
        ))

    story.append(PageBreak())
    return story


def build_enhanced_pdf(
    natal_ref: dict,
    prediction_context: dict,
    almanac_days: int = 90,
    topics: Optional[list[str]] = None,
    include_almanac: bool = True,
    include_kp_packet: bool = True,
    include_long_term: bool = True,
    query_lat: Optional[float] = None,
    query_lng: Optional[float] = None,
    query_tz: Optional[str] = None,
    query_city: Optional[str] = None,
) -> io.BytesIO:
    """
    Build the full enhanced KP PDF report.

    Parameters
    ----------
    natal_ref          : Loaded natal_ref.json dict.
    prediction_context : PredictionContext from analysis/context.py.
    almanac_days       : Number of almanac days (default 90).
    topics             : Topics for promise/denial (defaults to main topics).
    include_almanac    : Whether to append the almanac section.
    include_kp_packet  : Whether to include significator/promise/denial tables.
    include_long_term  : Whether to include long-term transit windows.
    query_lat/lng/tz   : Prediction location. Defaults to the one stored in
                         prediction_context; must match it when given.
                         Birth location is never used.

    Returns
    -------
    io.BytesIO PDF buffer — ready for st.download_button or file write.
    """
    ctx = prediction_context
    for key, given in (("query_lat", query_lat), ("query_lng", query_lng), ("query_tz", query_tz)):
        stored = ctx.get(key)
        if stored is None:
            raise PredictionLocationRequired(f"prediction_context has no {key}")
        if given is not None and (given != stored if key == "query_tz"
                                  else abs(float(given) - float(stored)) > 1e-6):
            raise ValueError(f"{key}={given!r} differs from prediction_context {stored!r}")
    query_lat, query_lng, query_tz = ctx["query_lat"], ctx["query_lng"], ctx["query_tz"]

    buffer = io.BytesIO()

    # Use landscape for almanac pages; standard A4 for analysis pages
    # We build a single doc on A4 (portrait); almanac uses its own rendering
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.5 * inch,  bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    story: list = []

    # ── Cover page ────────────────────────────────────────────────
    story.extend(_cover_story(natal_ref, prediction_context, styles))

    # ── KP Analysis Packet ────────────────────────────────────────
    if include_kp_packet:
        from datetime import date as _date
        query_date_str = prediction_context.get("query_date", "")
        try:
            ref_date = _date.fromisoformat(str(query_date_str)[:10])
        except (ValueError, TypeError):
            ref_date = _date.today()

        significators, strength_map = natal_significators(natal_ref)
        # Always recompute activation from locked natal significators —
        # never reuse stale event_analyses (can carry old CSL ✓/✗ bugs).
        dasha = prediction_context.get("dasha", {})
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
        )
        lt_list = prediction_context.get("long_term_transits", [])
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
        story.extend(_fine_windows_story(prediction_context, styles))

    # ── Almanac (default 90 days) ─────────────────────────────────
    if include_almanac:
        from datetime import date as _date
        query_date_str = prediction_context.get("query_date", "")
        try:
            ref_date = _date.fromisoformat(str(query_date_str)[:10])
        except (ValueError, TypeError):
            ref_date = _date.today()
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

    doc.build(story)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Convenience: build from natal_ref path + today's date
# ---------------------------------------------------------------------------

def build_today_report(
    query_location: str,
    query_lat: float,
    query_lng: float,
    query_tz: str,
    natal_ref_path: Optional[str] = None,
) -> io.BytesIO:
    """
    Shortcut: load natal ref and build the enhanced report for today at an
    explicit prediction location.

    python -c "
    from reports.enhanced_pdf import build_today_report
    buf = build_today_report('Hyderabad, India', 17.385, 78.4867, 'Asia/Kolkata')
    open('enhanced_report.pdf','wb').write(buf.read())
    "
    """
    natal = load_natal_ref(natal_ref_path)
    ctx   = build_prediction_context(
        natal,
        date.today(),
        query_mode="LONG_TERM",
        query_location=query_location,
        query_lat=query_lat,
        query_lng=query_lng,
        query_tz=query_tz,
    )
    return build_enhanced_pdf(natal, ctx)
