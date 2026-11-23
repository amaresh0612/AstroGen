"""
ReportLab section builder — KP Analysis Packet.

Produces pages containing:
    1. Significator strength table (Level 1–4 per planet × house)
    2. Promise/Denial verdicts per topic
    3. Long-term Jupiter/Saturn/Rahu/Ketu transit windows

Consumed by reports/enhanced_pdf.py — never called directly.
"""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, PageBreak

ACCENT    = colors.HexColor("#8B4513")
GOLD      = colors.HexColor("#C9963A")
HEADER_BG = colors.HexColor("#FFF8DC")
ALT_ROW   = colors.HexColor("#FAFAF5")
PROMISED_COLOR = colors.HexColor("#DFF0D8")
CONFLICT_COLOR = colors.HexColor("#FFE0E0")
WEAK_COLOR     = colors.HexColor("#FFF3CD")

PLANETS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]


def build_kp_packet_section(
    strength_map: dict,
    promise_denial_list: list[dict],
    long_term_transits: list[dict],
) -> list:
    """
    Build ReportLab flowables for the KP Analysis Packet.

    Parameters
    ----------
    strength_map       : Output of significator_strength.compute_significator_strength()
    promise_denial_list: Output of promise_denial.compute_all_topics()
    long_term_transits : Output of long_term_transits.compute_long_term_transits()

    Returns
    -------
    list of ReportLab flowables.
    """
    styles   = getSampleStyleSheet()
    tiny     = ParagraphStyle("kp_tiny",  parent=styles["Normal"], fontSize=6,  leading=7)
    small    = ParagraphStyle("kp_small", parent=styles["Normal"], fontSize=7,  leading=8)
    bold7    = ParagraphStyle("kp_bold",  parent=styles["Normal"], fontSize=7,
                               fontName="Helvetica-Bold", leading=8)
    head_sty = ParagraphStyle("kp_head",  parent=styles["Normal"], fontSize=7,
                               fontName="Helvetica-Bold", alignment=TA_CENTER, leading=8)
    title_sty = ParagraphStyle("kp_title", parent=styles["Heading2"],
                                textColor=ACCENT, fontSize=11)
    h3_sty    = ParagraphStyle("kp_h3",   parent=styles["Heading3"],
                                textColor=ACCENT, fontSize=9)

    story = []

    # ── 1. Significator strength table ───────────────────────────
    story.append(Paragraph("KP Significator Strength", title_sty))
    story.append(Paragraph(
        "Level 1 = In Star of Occupant  |  Level 2 = Occupant  |  "
        "Level 3 = In Star of Owner  |  Level 4 = Owner  |  "
        "Rahu/Ketu also carry their sign lord's and same-sign planets' houses",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.1 * inch))

    # Headers: Planet | H1 H2 … H12
    sig_headers = ["Planet"] + [f"H{h}" for h in range(1, 13)]
    sig_widths  = [0.7 * inch] + [0.42 * inch] * 12

    sig_data = [[Paragraph(h, head_sty) for h in sig_headers]]
    for pname in PLANETS:
        row = [Paragraph(pname, bold7)]
        house_map = strength_map.get(pname, {})
        for h in range(1, 13):
            info = house_map.get(h)
            cell = Paragraph(f"L{info['level']}" if info else "", tiny)
            row.append(cell)
        sig_data.append(row)

    sig_table = Table(sig_data, colWidths=sig_widths, repeatRows=1)
    sig_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW]),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 0.2 * inch))

    # ── 2. KP Activation Score Card ─────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("KP Activation Score Card", title_sty))
    story.append(Paragraph(
        "Each topic is rated 0–10 from three KP layers: "
        "<b>Layer 1 — CSL Direct-House Support</b> (0–3): does each primary house's "
        "cuspal sub-lord appear in that planet's locked natal <i>signified_houses</i> "
        "for the <b>same</b> house? "
        "(Simplified scoring test — not full classical KP promise.) "
        "<b>Layer 2 — Dasha Permission</b> (0–3): does any active MD/AD/PD lord signify each "
        "primary house (L1–L4)? This is the gating factor — without dasha permission the score is capped. "
        "<b>Layer 3 — Significator Quality</b> (0–2): L1/L2/L3 natal significators for the topic. "
        "Formula: (CSL + Dasha + Sigs) / 8 × 10. "
        "Hard caps: zero dasha coverage → ≤4.0; any completely dark house → ≤6.0. "
        "Label bands: STRONG ≥8.0, ACTIVE ≥6.5, MODERATE ≥5.0, MIXED ≥4.0, WEAK &lt;4.0. "
        "Ruling Planets are reported separately and do not change the score.",
        ParagraphStyle("score_note", parent=styles["Normal"], fontSize=7,
                       textColor=colors.HexColor("#444444"), leading=9),
    ))
    story.append(Spacer(1, 0.10 * inch))

    sc_headers = ["Topic", "H", "Score\n/10", "CSL Direct-House", "Dasha Permission", "Evidence themes"]
    sc_widths  = [0.85*inch, 0.50*inch, 0.48*inch, 1.35*inch, 1.40*inch, 2.67*inch]
    sc_data    = [[Paragraph(h, head_sty) for h in sc_headers]]

    SCORE_COLORS = [
        (8.0, colors.HexColor("#1B5E20"), colors.HexColor("#C8E6C9")),  # strong
        (5.5, colors.HexColor("#E65100"), colors.HexColor("#FFF3E0")),  # moderate
        (0.0, colors.HexColor("#B71C1C"), colors.HexColor("#FFEBEE")),  # weak
    ]

    for entry in promise_denial_list:
        sc = entry.get("score", {})
        pct = sc.get("pct10", 0.0)

        # Audit trail: "H6 → Jupiter → Direct CSL: NO"
        csl_analyses = entry.get("csl_analyses", [])
        house_act = entry.get("house_activation", {})
        if csl_analyses:
            csl_cell = "\n".join(
                a.get("pdf_line")
                or (
                    f"H{a['house']} → {a['csl']} → Direct CSL: "
                    f"{'YES' if a.get('csl_direct_support', a.get('csl_promise')) else 'NO'}"
                )
                for a in csl_analyses
            )
        else:
            csl_cell = entry.get("csl_verdict", "")[:80]

        # Dasha: "H6 → Saturn | H10 → none | H11 → Mercury,Jupiter"
        primary = entry.get("primary_houses", [])
        if house_act and primary:
            dasha_parts = []
            for h in primary:
                ha = house_act.get(h) or house_act.get(str(h)) or {}
                lords = ha.get("dasha_lords") or []
                dasha_parts.append(
                    f"H{h} → {', '.join(lords) if lords else 'none'}"
                )
            dasha_str = "\n".join(dasha_parts)
            detail = entry.get("dasha_alignment", "")
            if detail and "not activated" in detail.lower():
                dasha_str += f"\n{detail.split('.')[-1].strip()}" if "." in detail else ""
        else:
            dasha_str = entry.get("dasha_alignment", "")

        # Evidence themes (ranked) — not predictions; post-promotion mode when confirmed
        mfst = entry.get("manifestations", [])
        dark = entry.get("dark_houses", [])
        mode = entry.get("manifestation_mode", "standard")
        mfst_text = ""
        if mode == "post_promotion_assessment":
            mfst_text = "[Post-promotion assessment — milestone confirmed]\n"
        if mfst:
            ranked = [m for m in mfst if not m.startswith("Note:")]
            caveat = [m for m in mfst if m.startswith("Note:")]
            mfst_text += "\n".join(f"• {m}" for m in ranked[:3])
            if caveat:
                mfst_text += f"\n⚠ {caveat[0]}"
        elif dark:
            mfst_text += f"H{','.join(str(h) for h in dark)} uncovered — partial activation"

        # Score colour
        txt_col, bg_col = colors.HexColor("#333333"), colors.white
        for threshold, tc, bc in SCORE_COLORS:
            if pct >= threshold:
                txt_col, bg_col = tc, bc
                break

        verdict = entry.get("verdict", "")
        sc_data.append([
            Paragraph(entry.get("topic_label", ""), small),
            Paragraph(str(entry.get("primary_houses", "")).strip("[]"), tiny),
            Paragraph(
                f"{pct:.1f}\n{verdict}",
                ParagraphStyle("sc_num", parent=styles["Normal"],
                               fontSize=8, fontName="Helvetica-Bold",
                               textColor=txt_col, leading=10)),
            Paragraph(csl_cell, tiny),
            Paragraph(dasha_str, tiny),
            Paragraph(mfst_text, tiny),
        ])

    sc_table = Table(sc_data, colWidths=sc_widths, repeatRows=1)
    sc_styles: list = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW]),
    ]
    # colour the score cell per row
    for i, entry in enumerate(promise_denial_list, start=1):
        pct = entry.get("score", {}).get("pct10", 0.0)
        _, bg_col = colors.HexColor("#333333"), colors.white
        for threshold, _, bc in SCORE_COLORS:
            if pct >= threshold:
                bg_col = bc
                break
        sc_styles.append(("BACKGROUND", (2, i), (2, i), bg_col))

    sc_table.setStyle(TableStyle(sc_styles))
    story.append(sc_table)
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "Score guide: 8–10 = Strong activation (CSL Direct-House + dasha aligned) · "
        "6–7 = Moderate (partial — some houses dark or weak CSL Direct-House Support) · "
        "4–5 = Low-Moderate (dasha partially aligned, significant gaps) · "
        "0–3 = Weak (topic not supported in current period). "
        "Dark house = CSL does not directly signify that house AND no active dasha lord covers it. "
        "CSL Direct-House Support ≠ full classical KP promise.",
        ParagraphStyle("score_legend", parent=styles["Normal"], fontSize=6.5,
                       textColor=colors.HexColor("#555555"), leading=8.5),
    ))

    # ── 3. Long-term transit windows ─────────────────────────────
    if long_term_transits:
        story.append(PageBreak())
        story.append(Paragraph("Long-Term Transit Windows (5 Years)", title_sty))
        story.append(Paragraph(
            "Jupiter, Saturn, Rahu, Ketu sign-change dates (Lahiri / Swiss Ephemeris). "
            "Ingress date = UTC calendar date of exact sign crossing (noon-refined).",
            styles["Normal"],
        ))
        story.append(Spacer(1, 0.1 * inch))

        lt_headers = ["Planet", "Ingress (UTC)", "Sign Change", "H#",
                      "Nakshatra", "Star/Sub", "Potentially Activated Topics", "Notes"]
        lt_widths  = [0.65*inch, 0.95*inch, 0.85*inch, 0.30*inch,
                      0.80*inch, 0.70*inch, 1.15*inch, 1.35*inch]
        lt_data    = [[Paragraph(h, head_sty) for h in lt_headers]]

        for lt in long_term_transits:
            ing_disp = lt.get("ingress_datetime_utc") or lt.get("ingress_date", "")
            if len(str(ing_disp)) > 16:
                ing_disp = str(ing_disp)[:16].replace("T", " ")
            lt_data.append([
                Paragraph(lt.get("planet", ""), small),
                Paragraph(str(ing_disp), small),
                Paragraph(f"{lt.get('from_sign','')} → {lt.get('to_sign','')}", tiny),
                Paragraph(str(lt.get("transit_house", "")), tiny),
                Paragraph(lt.get("transit_nakshatra", ""), tiny),
                Paragraph(f"{lt.get('star_lord','')} / {lt.get('sub_lord','')}", tiny),
                Paragraph(", ".join(lt.get("impacted_topics", []))[:120], tiny),
                Paragraph(lt.get("notes", "")[:150], tiny),
            ])

        lt_table = Table(lt_data, colWidths=lt_widths, repeatRows=1)
        lt_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("GRID",       (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW]),
        ]))
        story.append(lt_table)

    return story
