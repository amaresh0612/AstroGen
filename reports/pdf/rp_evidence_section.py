"""
PDF sections that separate static RP-house alignment from time-specific RP activation.

Static overlap ≠ timing support. Zero timed windows ≠ natal denial.
"""
from __future__ import annotations

from typing import Optional

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

HEADER_BG = colors.HexColor("#E8E0D0")
ALT_ROW = colors.HexColor("#FAFAF5")


def build_static_rp_alignment_section(rp: dict) -> list:
    """Natal RP × event-house overlap only (not timed windows)."""
    styles = getSampleStyleSheet()
    h3 = ParagraphStyle(
        "rp_static_h", parent=styles["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4,
    )
    note = ParagraphStyle(
        "rp_static_note", parent=styles["Normal"], fontSize=6.5,
        textColor=colors.HexColor("#555555"), leading=8.5,
    )
    rp_align_sty = ParagraphStyle(
        "rp_align_h", parent=styles["Normal"], fontSize=7,
        textColor=colors.HexColor("#333333"), leading=9, spaceBefore=2,
    )
    bold7 = ParagraphStyle("bold7", parent=styles["Normal"], fontSize=7,
                           fontName="Helvetica-Bold", leading=9)
    tiny6 = ParagraphStyle("tiny6", parent=styles["Normal"], fontSize=6, leading=8)

    story: list = []
    rp_match = rp.get("rp_event_match") or {}
    if not rp_match:
        return story

    story.append(Paragraph(
        "A · Static RP–House Alignment (natal significations)", h3,
    ))
    story.append(Paragraph(
        "<b>What this establishes:</b> natal house overlap between the ruling planets "
        "at the reference snapshot and each topic’s primary houses. "
        "<b>What this does not establish:</b> whether a time-specific RP window "
        "qualified during a coverage period. Strong static overlap is <b>not</b> "
        "time-support. See section B / the AI pack’s <i>rp_trigger_windows</i>.",
        note,
    ))
    story.append(Spacer(1, 0.06 * inch))

    for topic, data in rp_match.items():
        if not isinstance(data, dict):
            continue
        verdict = data.get("rp_support", data.get("verdict", "Weak"))
        event_h = data.get("event_houses", [])
        matching_rp = data.get("matching_rp", [])
        if not matching_rp:
            continue
        verdict_col = (
            colors.HexColor("#2E7D32") if verdict == "Strong"
            else colors.HexColor("#E65100") if verdict == "Active"
            else colors.HexColor("#B71C1C")
        )
        story.append(Paragraph(
            f"<b>{topic.upper()}</b> — Event houses: "
            f"{','.join(str(h) for h in event_h)} — "
            f"<b>Static</b> RP support: <b>{verdict}</b>",
            rp_align_sty,
        ))
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
        rt = Table(
            tbl_data,
            colWidths=[0.70 * inch, 1.50 * inch, 0.70 * inch, 0.80 * inch, 0.60 * inch],
        )
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3F2FD")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("TEXTCOLOR", (-1, 1), (-1, -1), verdict_col),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.extend([rt, Spacer(1, 0.06 * inch)])
    return story


def build_timed_rp_activation_section(
    rp_trigger_summary: Optional[dict],
    *,
    max_listed_per_day: int = 6,
) -> list:
    """
    Time-specific RP window totals from the pack (or attached summary).

    Expects a compact dict:
      {
        "criteria_id": "rp_convergence_v2",
        "max_windows_listed_per_day": 6,
        "topics": {
           "business": {
              "windows_total": 0, "windows_listed": 0, "strong_windows": 0,
              "active_minutes": 0, "days_passing_gate": 39,
              "dasha_permission_without_rp_windows": True,
              "timing_label": "Timing support absent",
           }, ...
        }
      }
    """
    styles = getSampleStyleSheet()
    h3 = ParagraphStyle(
        "rp_timed_h", parent=styles["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=4,
    )
    note = ParagraphStyle(
        "rp_timed_note", parent=styles["Normal"], fontSize=6.5,
        textColor=colors.HexColor("#555555"), leading=8.5,
    )
    tiny = ParagraphStyle("rp_timed_tiny", parent=styles["Normal"], fontSize=6.5, leading=8)
    head = ParagraphStyle(
        "rp_timed_head", parent=styles["Normal"], fontSize=6.5,
        fontName="Helvetica-Bold", leading=8,
    )

    story: list = []
    story.append(Paragraph(
        "B · Time-Specific RP Activation (pack windows)", h3,
    ))

    if not rp_trigger_summary or not rp_trigger_summary.get("topics"):
        story.append(Paragraph(
            "No pack <i>rp_trigger_windows</i> summary was attached to this PDF build. "
            "Time-specific activation lives in the AI Calculation Pack only. "
            "Do <b>not</b> treat section A (static overlap) as timed support. "
            f"When present, <i>windows[]</i> lists at most <b>{max_listed_per_day}</b> "
            "windows per topic per day — a sample, not the complete set. "
            "Use <i>windows_total</i> / <i>active_minutes</i> for aggregates; "
            "never compute percentages from the capped list.",
            note,
        ))
        return story

    cap = int(rp_trigger_summary.get("max_windows_listed_per_day") or max_listed_per_day)
    criteria = rp_trigger_summary.get("criteria_id") or "rp_convergence_v2"
    story.append(Paragraph(
        f"<b>Criteria:</b> {criteria}. "
        f"<b>Listing cap:</b> at most {cap} windows listed per topic per day "
        f"(<i>windows_listed</i>). "
        "<b>Full totals:</b> <i>windows_total</i>, <i>strong_windows</i>, "
        "<i>active_minutes</i>, <i>strong_minutes</i> — use these for aggregation. "
        "RP activation is a timing filter, not a standalone prediction. "
        "Zero qualifying windows with dasha permission = "
        "<b>Timing support absent</b> under this method — not natal denial.",
        note,
    ))
    story.append(Spacer(1, 0.08 * inch))

    headers = [
        "Topic", "Gate days", "windows_total", "windows_listed",
        "strong", "active min", "Timing label",
    ]
    data = [[Paragraph(h, head) for h in headers]]
    for topic, block in (rp_trigger_summary.get("topics") or {}).items():
        label = block.get("timing_label") or (
            "Timing support absent"
            if block.get("dasha_permission_without_rp_windows")
            or (
                int(block.get("days_passing_gate") or 0) > 0
                and int(block.get("windows_total") or 0) == 0
            )
            else ("Time-supported intervals present"
                  if int(block.get("windows_total") or 0) > 0
                  else "No gate / no windows")
        )
        data.append([
            Paragraph(str(topic), tiny),
            Paragraph(str(block.get("days_passing_gate", "—")), tiny),
            Paragraph(str(block.get("windows_total", "—")), tiny),
            Paragraph(str(block.get("windows_listed", "—")), tiny),
            Paragraph(str(block.get("strong_windows", "—")), tiny),
            Paragraph(str(block.get("active_minutes", "—")), tiny),
            Paragraph(str(label), tiny),
        ])

    tbl = Table(
        data,
        colWidths=[
            0.85 * inch, 0.55 * inch, 0.75 * inch, 0.75 * inch,
            0.55 * inch, 0.65 * inch, 1.65 * inch,
        ],
        repeatRows=1,
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(
        "Do not label business, marriage, or any topic as time-supported solely because "
        "section A shows Strong static RP–house overlap.",
        note,
    ))
    return story


def summarise_rp_triggers_for_pdf(rp_trigger_windows: dict) -> dict:
    """Compact pack → PDF/AI summary (full totals vs listed)."""
    topics_out = {}
    for topic, block in (rp_trigger_windows.get("topics") or {}).items():
        s = block.get("summary") or {}
        d = block.get("diagnostics") or {}
        dasha_no = bool(d.get("dasha_permission_without_rp_windows"))
        total = int(s.get("windows_total") or 0)
        gate = int(s.get("days_passing_gate") or 0)
        if total > 0:
            timing_label = "Time-supported intervals present"
        elif dasha_no or gate > 0:
            timing_label = "Timing support absent"
        else:
            timing_label = "No dasha gate / no windows"
        topics_out[topic] = {
            "windows_total": total,
            "windows_listed": int(s.get("windows_listed") or 0),
            "strong_windows": int(s.get("strong_windows") or 0),
            "active_minutes": int(s.get("active_minutes") or 0),
            "strong_minutes": int(s.get("strong_minutes") or 0),
            "days_passing_gate": gate,
            "dasha_permission_without_rp_windows": dasha_no,
            "timing_label": timing_label,
        }
    return {
        "criteria_id": (rp_trigger_windows.get("criteria") or {}).get("id", "rp_convergence_v2"),
        "diagnostics_schema": (rp_trigger_windows.get("criteria") or {}).get(
            "diagnostics_schema", ""
        ),
        "max_windows_listed_per_day": rp_trigger_windows.get(
            "max_windows_listed_per_day", 6
        ),
        "topics": topics_out,
    }
