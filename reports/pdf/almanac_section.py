"""
ReportLab section builder — almanac table (default 90 days).

Produces one or more A4 landscape pages containing the almanac grid.
Each page fits approximately 20 days.

Consumed by reports/enhanced_pdf.py — never called directly.
"""
from __future__ import annotations

from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)

ACCENT     = colors.HexColor("#8B4513")
GOLD       = colors.HexColor("#C9963A")
HEADER_BG  = colors.HexColor("#FFF8DC")
ALT_ROW    = colors.HexColor("#FAFAF5")
CHANDRA_BG = colors.HexColor("#FFE0E0")


def _cell(text: str, style, wrap: bool = False):
    if wrap:
        return Paragraph(str(text), style)
    return str(text)


def build_almanac_section(almanac_rows: list[dict]) -> list:
    """
    Build a list of ReportLab flowables for the almanac.

    Parameters
    ----------
    almanac_rows : Output from analysis/almanac_builder.build_almanac()

    Returns
    -------
    list of ReportLab flowables to append to a story.
    """
    styles = getSampleStyleSheet()
    tiny   = ParagraphStyle("tiny",   parent=styles["Normal"], fontSize=6,  leading=7)
    small  = ParagraphStyle("small",  parent=styles["Normal"], fontSize=7,  leading=8)
    header = ParagraphStyle("header", parent=styles["Normal"], fontSize=7,
                             fontName="Helvetica-Bold", alignment=TA_CENTER, leading=8)

    story = []

    # Section heading
    title_style = ParagraphStyle("alt", parent=styles["Heading2"],
                                  textColor=ACCENT, fontSize=12)
    story.append(Paragraph(
        f"{len(almanac_rows)}-Day Panchanga & Kalam Reference", title_style,
    ))
    story.append(Paragraph(
        "Pre-calculated daily reference: Panchanga, Kalam, Hora, Tarabala, Dasha  "
        "· Kalam col: R=Rahu Kalam, Y=Yamaganda, G=Gulika (hh:mm-hh:mm)  "
        "· Tara: T1=Janma … T9=Mitra  ·  C: Y=Chandrashtama (avoid new ventures)  "
        "· Num=Numerology day number",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.15 * inch))

    # Column definitions — total ≤ 7.27" to fit portrait A4 with 0.5" margins
    # Tara (T1-T9) and Chandrashtama (C/N) are two separate columns
    # Rahu/Yama/Gulika merged into one "Kalam" column (R:hh-hh / Y:hh-hh / G:hh-hh)
    COL_HEADERS = [
        "Date", "D", "Rise/<br/>Set",
        "Tithi", "Moon Nak", "Yoga/Kar",
        "Kalam (R/Y/G)", "Tara", "C", "Num", "MD/AD/PD",
        "Hora Seq",
    ]
    COL_WIDTHS = [
        0.47*inch, 0.30*inch, 0.52*inch,
        0.68*inch, 0.75*inch, 0.68*inch,
        0.90*inch, 0.35*inch, 0.22*inch, 0.30*inch, 0.75*inch,
        1.35*inch,
    ]

    ROWS_PER_PAGE = 20

    for page_start in range(0, len(almanac_rows), ROWS_PER_PAGE):
        chunk = almanac_rows[page_start: page_start + ROWS_PER_PAGE]

        table_data = [[Paragraph(h, header) for h in COL_HEADERS]]

        for row in chunk:
            if row.get("error"):
                table_data.append([row["date"], "ERROR", row["error"]] + [""] * 10)
                continue

            # Hora sequence (day horas only, lords abbreviated)
            hora_seq  = row.get("hora_sequence", [])
            # Abbreviated hora lord name (2 chars)
            _HORA_ABBR = {
                "Sun": "Su", "Moon": "Mo", "Mars": "Ma",
                "Mercury": "Me", "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa",
            }

            def _hora_token(h: dict) -> str:
                lord = h.get("lord", "?")
                abbr = _HORA_ABBR.get(lord, lord[:2])
                start = h.get("start", "")
                # Use HH:MM (first 5 chars of "HH:MM:SS" or "HH:MM")
                time_str = start[:5] if len(start) >= 5 else (start[:2] if len(start) >= 2 else "?")
                return f"{abbr}({time_str})"

            day_horas   = [h for h in hora_seq if h.get("period") == "day"]
            night_horas = [h for h in hora_seq if h.get("period") == "night"]
            # Fall back: first 12 = day, next 12 = night
            if not day_horas and hora_seq:
                day_horas   = hora_seq[:12]
                night_horas = hora_seq[12:]

            day_str   = " ".join(_hora_token(h) for h in day_horas)
            night_str = " ".join(_hora_token(h) for h in night_horas)
            hora_str  = f"D:{day_str}\nN:{night_str}" if night_str else f"D:{day_str}"

            # Tara + Chandrashtama (now two separate columns)
            tara_str = f"T{row.get('tara_number','')}"
            chandra_str = "Y" if row.get("chandrashtama") else ""

            # Combined Kalam: Rahu / Yamaganda / Gulika (all three on separate lines)
            def _kal(window: dict, label: str) -> str:
                if not window:
                    return f"{label}:--"
                s = window.get("start", "--")
                e = window.get("end", "--")
                return f"{label}:{s}-{e}"

            kalam_str = "\n".join([
                _kal(row.get("rahu_kalam",   {}), "R"),
                _kal(row.get("yamaganda",    {}), "Y"),
                _kal(row.get("gulika_kalam", {}), "G"),
            ])

            # MD/AD/PD abbreviation
            dasha_str = "/".join(filter(None, [
                row.get("active_md", "")[:3],
                row.get("active_ad", "")[:3],
                row.get("active_pd", "")[:3],
            ]))

            table_data.append([
                Paragraph(row.get("date", "")[5:], tiny),
                Paragraph(row.get("weekday", "")[:1], tiny),
                Paragraph(f"{row.get('sunrise','--')}\n{row.get('sunset','--')}", tiny),
                Paragraph(row.get("tithi", ""), tiny),
                Paragraph(f"{row.get('moon_nakshatra','')}/P{row.get('moon_pada','')}", tiny),
                Paragraph(f"{row.get('yoga','')}/{row.get('karana','')}", tiny),
                Paragraph(kalam_str, tiny),             # R/Y/G combined
                Paragraph(tara_str, tiny),
                Paragraph(chandra_str, tiny),           # Y or blank
                Paragraph(str(row.get("day_number", "")), tiny),
                Paragraph(dasha_str, tiny),
                Paragraph(hora_str, tiny),
            ])

        t = Table(table_data, colWidths=COL_WIDTHS, repeatRows=1)

        row_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
            ("TEXTCOLOR",  (0, 0), (-1, 0), ACCENT),
            ("GRID",       (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE",   (0, 1), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW]),
        ]
        # Highlight Chandrashtama rows
        for i, row in enumerate(chunk, start=1):
            if row.get("chandrashtama"):
                row_styles.append(("BACKGROUND", (0, i), (-1, i), CHANDRA_BG))

        t.setStyle(TableStyle(row_styles))
        story.append(t)

        if page_start + ROWS_PER_PAGE < len(almanac_rows):
            story.append(PageBreak())

    return story


def _window_str(window: dict) -> str:
    if not window:
        return "--"
    return f"{window.get('start','--')}\n{window.get('end','--')}"
