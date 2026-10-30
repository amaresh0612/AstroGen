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
    Pages 5+ : 60-day almanac (landscape, ~20 days per page)

Usage
-----
    from analysis.context import load_natal_ref, build_prediction_context
    from reports.enhanced_pdf import build_enhanced_pdf
    from datetime import date

    natal = load_natal_ref()
    ctx   = build_prediction_context(natal, date.today(), query_mode="LONG_TERM")
    pdf_bytes = build_enhanced_pdf(natal, ctx, almanac_days=60)
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

from analysis.context import load_natal_ref, build_prediction_context
from analysis.almanac_builder import build_almanac
from analysis.significator_strength import compute_significator_strength_from_natal
from analysis.promise_denial import compute_all_topics
from analysis.long_term_transits import compute_long_term_transits
from reports.pdf.almanac_section import build_almanac_section
from reports.pdf.kp_packet_section import build_kp_packet_section
from schemas.event_houses import EVENT_HOUSES

ACCENT    = colors.HexColor("#8B4513")
GOLD      = colors.HexColor("#C9963A")
HEADER_BG = colors.HexColor("#FFF8DC")


def _cover_story(natal_ref: dict, ctx: dict, styles,
                 query_city: Optional[str] = None,
                 query_lat: Optional[float] = None,
                 query_lng: Optional[float] = None,
                 query_tz: Optional[str] = None) -> list:
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

    # Prediction location (explicitly separate from natal/birth location)
    pred_city = query_city or birth.get("place", "")
    pred_lat  = query_lat  if query_lat  is not None else birth.get("lat", 0)
    pred_lng  = query_lng  if query_lng  is not None else birth.get("lng", 0)
    pred_tz   = query_tz   if query_tz   is not None else birth.get("tz", "Asia/Kolkata")
    same_as_natal = (query_city is None or
                     query_city.strip().lower() == birth.get("place", "").strip().lower())

    pred_rows = [
        ["Prediction City",  pred_city],
        ["Prediction Coords", f"{pred_lat:.4f}°, {pred_lng:.4f}°"],
        ["Prediction TZ",    pred_tz],
        ["Same as natal?",   "YES — birth place used" if same_as_natal
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
    if transits:
        tr_rows = [["Planet", "Transit Sign", "Nak", "Star", "Sub", "House"]]
        for pname in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]:
            t = transits.get(pname, {})
            if not t:
                continue
            tr_rows.append([pname, t.get("sign",""), t.get("nakshatra",""),
                             t.get("star_lord",""), t.get("sub_lord",""),
                             str(t.get("transit_house",""))])
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

        # RP event alignment (if computed)
        rp_match = rp.get("rp_event_match", {})
        if rp_match:
            rp_align_sty = ParagraphStyle("rp_align_h", parent=styles["Normal"],
                                          fontSize=7, textColor=colors.HexColor("#333333"),
                                          leading=9, spaceBefore=2)
            bold7 = ParagraphStyle("bold7", parent=styles["Normal"],
                                   fontSize=7, fontName="Helvetica-Bold", leading=9)
            tiny6 = ParagraphStyle("tiny6", parent=styles["Normal"],
                                   fontSize=6, leading=8)

            story.append(Paragraph("RP × Event House Alignment", h3_sty))
            story.append(Paragraph(
                "For each topic, each Ruling Planet's natal house significations are checked "
                "against the required event houses.  "
                "Overlap = houses shared by the RP's natal significators and the topic's event houses.  "
                "RP Support: Strong = 2+ overlap per RP;  Active = 1 overlap;  Weak = no overlap. "
                "This measures RP support only — not event outcome.",
                ParagraphStyle("rp_note", parent=styles["Normal"], fontSize=6.5,
                               textColor=colors.HexColor("#555555"), leading=8.5),
            ))
            story.append(Spacer(1, 0.06 * inch))

            for topic, data in rp_match.items():
                if not isinstance(data, dict):
                    continue
                verdict     = data.get("rp_support", data.get("verdict", "Weak"))
                event_h     = data.get("event_houses", [])
                matching_rp = data.get("matching_rp", [])
                if not matching_rp:
                    continue

                verdict_col = (colors.HexColor("#2E7D32") if verdict == "Strong"
                               else colors.HexColor("#E65100") if verdict == "Active"
                               else colors.HexColor("#B71C1C"))

                story.append(Paragraph(
                    f"<b>{topic.upper()}</b>  "
                    f"— Event houses: {','.join(str(h) for h in event_h)}  "
                    f"— RP Support: <b>{verdict}</b>",
                    rp_align_sty,
                ))
                # One row per matching RP
                tbl_data = [[
                    Paragraph("RP", bold7),
                    Paragraph("Natal Sigs", bold7),
                    Paragraph("Event H", bold7),
                    Paragraph("Overlap", bold7),
                    Paragraph("Strength", bold7),
                ]]
                for row_r in matching_rp:
                    tbl_data.append([
                        Paragraph(row_r["planet"], tiny6),
                        Paragraph(str(row_r["natal_sigs"]).strip("[]"), tiny6),
                        Paragraph(str(row_r["event_houses"]).strip("[]"), tiny6),
                        Paragraph(", ".join(str(h) for h in row_r["overlap"]), tiny6),
                        Paragraph(row_r["strength"], tiny6),
                    ])
                rt = Table(tbl_data,
                           colWidths=[0.70*inch, 1.50*inch, 0.70*inch, 0.80*inch, 0.60*inch])
                rt.setStyle(TableStyle([
                    ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#E3F2FD")),
                    ("GRID",        (0, 0), (-1, -1), 0.3, colors.grey),
                    ("TEXTCOLOR",   (-1, 1), (-1, -1), verdict_col),
                    ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
                ]))
                story.extend([rt, Spacer(1, 0.06 * inch)])

    story.append(PageBreak())
    return story


def build_enhanced_pdf(
    natal_ref: dict,
    prediction_context: dict,
    almanac_days: int = 60,
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
    almanac_days       : Number of almanac days (default 60).
    topics             : Topics for promise/denial (defaults to main topics).
    include_almanac    : Whether to append the 60-day almanac section.
    include_kp_packet  : Whether to include significator/promise/denial tables.
    include_long_term  : Whether to include long-term transit windows.
    query_lat/lng/tz   : Current location for dynamic calculations.
                         If omitted, falls back to natal location (birth place).

    Returns
    -------
    io.BytesIO PDF buffer — ready for st.download_button or file write.
    """
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
    story.extend(_cover_story(natal_ref, prediction_context, styles,
                               query_city=query_city,
                               query_lat=query_lat, query_lng=query_lng,
                               query_tz=query_tz))

    # ── KP Analysis Packet ────────────────────────────────────────
    if include_kp_packet:
        from datetime import date as _date
        query_date_str = prediction_context.get("query_date", "")
        try:
            ref_date = _date.fromisoformat(str(query_date_str)[:10])
        except (ValueError, TypeError):
            ref_date = _date.today()

        strength_map = compute_significator_strength_from_natal(natal_ref)
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
            significators=natal_ref.get("significators", {}),
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
            )
        story.extend(build_kp_packet_section(
            strength_map,
            pd_list,
            lt_list if include_long_term else [],
        ))

    # ── 60-day almanac ────────────────────────────────────────────
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
    natal_ref_path: Optional[str] = None,
    query_location: Optional[str] = None,
) -> io.BytesIO:
    """
    Shortcut: load natal ref and build the enhanced report for today.

    python -c "
    from reports.enhanced_pdf import build_today_report
    buf = build_today_report()
    open('enhanced_report.pdf','wb').write(buf.read())
    "
    """
    natal = load_natal_ref(natal_ref_path)
    ctx   = build_prediction_context(
        natal,
        date.today(),
        query_mode="LONG_TERM",
        query_location=query_location,
    )
    return build_enhanced_pdf(natal, ctx)
