"""
Natal chart tables for the unified PDF — planets, chart image, full dasha timeline.

Built from the locked natal_ref (always available). When a live session
``chart_result`` is also passed, the chart wheel PNG is embedded if the
already-loaded ``app`` module exposes ``render_chart_png_bytes_pil``.

Does not include significators, current transits, or AI narrative — those live
in the enhanced evidence sections of the unified PDF.
"""
from __future__ import annotations

import html
import io
import sys
from datetime import datetime, timedelta
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage, Paragraph, Spacer, Table, TableStyle

from analysis.kp_constants import SIGN_LORDS
from analysis.vimshottari import parse_dt, subdivide

ACCENT = colors.HexColor("#8B4513")
HEADER_BG = colors.HexColor("#FFF8DC")
PLANET_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]


def _h3(styles):
    return ParagraphStyle("natal_h3", parent=styles["Heading3"], textColor=ACCENT, fontSize=10)


def _wrap(styles):
    return ParagraphStyle(
        "natal_wrap", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7, leading=8,
    )


def _P(text, style):
    return Paragraph(html.escape("" if text is None else str(text)), style)


def _planet_rows(natal_ref: dict, wrap) -> list[list]:
    planets = natal_ref.get("planets", {})
    houses = natal_ref.get("houses", {})
    csl = natal_ref.get("cuspal_sublords", {})

    rows = [[
        _P(h, wrap) for h in (
            "House", "Entity", "Sign", "Degree", "Nakshatra",
            "Pada", "Nak Lord", "Sub-lord", "Sign Lord", "Cusp Sublord",
        )
    ]]

    h1 = houses.get("1", {})
    rows.append([
        _P("1 (Lagna)", wrap), _P("Ascendant", wrap),
        _P(h1.get("sign", ""), wrap), _P(h1.get("degree", ""), wrap),
        _P(h1.get("nakshatra", ""), wrap), _P("", wrap),
        _P(h1.get("star_lord", ""), wrap), _P(h1.get("sub_lord", ""), wrap),
        _P(SIGN_LORDS.get(h1.get("sign", ""), ""), wrap),
        _P(csl.get("1", h1.get("sub_lord", "")), wrap),
    ])

    by_house: dict[int, list] = {i: [] for i in range(1, 13)}
    for pname in PLANET_ORDER:
        pdata = planets.get(pname) or {}
        h = int(pdata.get("house") or pdata.get("house_cuspal") or 0)
        if 1 <= h <= 12:
            by_house[h].append((pname, pdata))

    for h in range(1, 13):
        for pname, pdata in by_house[h]:
            label = pname + (" (R)" if pdata.get("retrograde") else "")
            rows.append([
                _P(str(h), wrap), _P(label, wrap),
                _P(pdata.get("sign", ""), wrap), _P(pdata.get("degree", ""), wrap),
                _P(pdata.get("nakshatra", ""), wrap),
                _P(str(pdata.get("pada", "") or ""), wrap),
                _P(pdata.get("star_lord", ""), wrap),
                _P(pdata.get("sub_lord", ""), wrap),
                _P(pdata.get("sign_lord") or SIGN_LORDS.get(pdata.get("sign", ""), ""), wrap),
                _P(csl.get(str(h), ""), wrap),
            ])
    return rows


def _chart_image(chart_result: Optional[dict]):
    """Embed the session chart wheel when app.py is already loaded."""
    if not chart_result:
        return None
    app_mod = sys.modules.get("app")
    render = getattr(app_mod, "render_chart_png_bytes_pil", None) if app_mod else None
    if not callable(render):
        return None
    planets = chart_result.get("planets")
    cusps = chart_result.get("house_cusps_degrees")
    if not planets or not cusps:
        return None
    try:
        png = render(planets, cusps, size=1200, show_pada=True)
        return RLImage(io.BytesIO(png), width=4.5 * inch, height=4.5 * inch)
    except Exception:
        return None


def _maha_antar_table(natal_ref: dict, styles) -> list:
    timeline = (natal_ref.get("dasha") or {}).get("full_timeline") or []
    if not timeline:
        return []

    now = datetime.now()
    data = [["MAHADASHA", "MAHA PERIOD", "YRS", "ANTARDASHA", "ANTAR PERIOD", "YRS"]]
    for maha in timeline:
        start, end = parse_dt(maha.get("start")), parse_dt(maha.get("end"))
        if not start or not end:
            continue
        years = float(maha.get("years") or (end - start).days / 365.25)
        antars = subdivide(maha["lord"], start, end, years)
        first = True
        for antar in antars:
            cur = antar["start"] <= now <= antar["end"]
            data.append([
                maha["lord"].upper() if first else "",
                (f"{start.strftime('%b %Y')} \u2013 {end.strftime('%b %Y')}" if first else ""),
                f"{years:.1f}" if first else "",
                antar["lord"].upper() + (" \u25c0" if cur else ""),
                f"{antar['start'].strftime('%b %Y')} \u2013 {antar['end'].strftime('%b %Y')}",
                f"{antar['years']:.1f}",
            ])
            first = False

    if len(data) == 1:
        return []

    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(data)):
        if "\u25c0" in data[i][3]:
            cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FFF3CD")))
        elif i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FDF8F0")))

    t = Table(data, colWidths=[1.0*inch, 1.35*inch, 0.45*inch, 1.0*inch, 1.35*inch, 0.45*inch],
              repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return [
        Spacer(1, 0.15 * inch),
        Paragraph("Vimshottari Dasha: Complete Life Timeline (Mahadasha & Antardasha)", _h3(styles)),
        t,
    ]


def _pratyantar_table(natal_ref: dict, styles) -> list:
    """PD rows from the locked table covering roughly now−3y … now+8y."""
    rows = (natal_ref.get("dasha") or {}).get("locked_periods") or []
    if not rows:
        return []

    win_start = datetime.now() - timedelta(days=365.25 * 3)
    win_end = datetime.now() + timedelta(days=365.25 * 8)
    data = [["DASA", "ANTARDASHA", "PRATYANTARDASHA", "DATE", "MONTH", "YEAR"]]
    for r in rows:
        s = parse_dt(r.get("pd_start"))
        e = parse_dt(r.get("pd_end"))
        if not s or not e or e < win_start or s > win_end:
            continue
        data.append([
            str(r.get("md", "")).upper(),
            str(r.get("ad", "")).upper(),
            str(r.get("pd", "")).upper(),
            s.strftime("%d"), s.strftime("%m"), s.strftime("%Y"),
        ])

    if len(data) == 1:
        return []

    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a3728")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (3, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for i in range(1, len(data)):
        cmds.append(("BACKGROUND", (0, i), (-1, i),
                     colors.HexColor("#FDF8F0") if i % 2 == 0 else colors.white))

    t = Table(data,
              colWidths=[1.1*inch, 1.2*inch, 1.5*inch, 0.6*inch, 0.65*inch, 0.75*inch],
              repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return [
        Spacer(1, 0.2 * inch),
        Paragraph(
            f"Pratyantardasha Detail  ({win_start.strftime('%b %Y')} \u2013 {win_end.strftime('%b %Y')})",
            _h3(styles),
        ),
        t,
    ]


def _muhurtha_table(query_date, query_lat: float, query_lng: float, query_tz: str, styles) -> list:
    """Rahu / Yama / Gulika for the prediction date at the prediction location."""
    from analysis.almanac_builder import _compute_kalam_windows
    from analysis.panchanga import compute_panchanga

    try:
        panch = compute_panchanga(query_date, query_lat, query_lng, query_tz)
        kalam = _compute_kalam_windows(query_date, query_lat, query_lng, query_tz)
    except Exception as exc:
        return [Paragraph(f"Muhurtha Kalas unavailable: {exc}", styles["Normal"])]

    def _w(block: dict) -> str:
        s, e = (block or {}).get("start", "--:--"), (block or {}).get("end", "--:--")
        return f"{s} \u2013 {e}"

    rows = [
        ["KALA", "TIME", "GUIDANCE"],
        ["Sunrise", panch.get("sunrise") or "--:--", "Start of daytime"],
        ["Rahu Kalam", _w(kalam.get("rahu_kalam")), "Avoid new beginnings / important decisions"],
        ["Yama Kantam", _w(kalam.get("yamaganda")), "Inauspicious for travel & new ventures"],
        ["Gulika Kalam", _w(kalam.get("gulika_kalam")), "Avoid auspicious ceremonies"],
        ["Sunset", panch.get("sunset") or "--:--", "End of daytime"],
    ]
    t = Table(rows, colWidths=[1.3*inch, 1.7*inch, 3.0*inch], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a3728")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 2), (-1, 4), colors.HexColor("#FFF5E6")),
    ]))
    return [
        Spacer(1, 0.15 * inch),
        Paragraph(
            f"Daily Muhurtha Kalas  —  {query_date.strftime('%A, %d %b %Y')}  ({query_tz})",
            _h3(styles),
        ),
        t,
    ]


def build_natal_chart_section(
    natal_ref: dict,
    chart_result: Optional[dict] = None,
    query_date=None,
    query_lat: Optional[float] = None,
    query_lng: Optional[float] = None,
    query_tz: Optional[str] = None,
) -> list:
    """
    ReportLab flowables: planet/cusp table, optional chart image, full MD/AD
    timeline, locked PD detail, and prediction-location muhurtha kalas.
    """
    styles = getSampleStyleSheet()
    wrap = _wrap(styles)
    story: list = [
        Paragraph("Natal Chart — Planetary Positions", _h3(styles)),
        Spacer(1, 0.08 * inch),
    ]

    col_widths = [
        0.45*inch, 1.00*inch, 0.7*inch, 0.8*inch, 1.6*inch,
        0.35*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.0*inch,
    ]
    planet_table = Table(_planet_rows(natal_ref, wrap), colWidths=col_widths, repeatRows=1)
    planet_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.extend([planet_table, Spacer(1, 0.12 * inch)])

    img = _chart_image(chart_result)
    if img is not None:
        story.extend([img, Spacer(1, 0.1 * inch)])

    story.extend(_maha_antar_table(natal_ref, styles))
    story.extend(_pratyantar_table(natal_ref, styles))

    if query_date is not None and query_lat is not None and query_lng is not None and query_tz:
        story.extend(_muhurtha_table(query_date, query_lat, query_lng, query_tz, styles))

    return story
