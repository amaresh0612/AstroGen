"""
Vimshottari MD → AD → PD — the only subdivision code in analysis/*.

Arithmetic is identical to app.py compute_antardashas / compute_pratyantardashas
with LEGACY_KP_DASHA = False:
    child_years = parent_years × lord_years / 120
    child_end   = child_start + child_years × 365.25 days
    last child's end is pinned to the parent's end

Lock model
----------
At natal lock time, ``lock_dasha`` subdivides app.py's raw mahadasha datetimes
once and stores PD-level rows in ``natal_ref["dasha"]["locked_periods"]``.
``resolve_dasha`` answers every later query from that table. It only falls
back to subdividing ``full_timeline`` for natal files written before the table
existed, and says so in ``source``.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from analysis.kp_constants import NAKSHATRAS, VIMSHOTTARI_ORDER, VIMSHOTTARI_TOTAL, VIMSHOTTARI_YEARS

NAK_LORDS = [lord for _, lord in NAKSHATRAS]

DAYS_PER_YEAR = 365.25
LOCK_YEARS_BEFORE = 1
LOCK_YEARS_AFTER = 6   # covers the 5-year long-term transit horizon + a 90-day pack

SOURCE_LOCKED_TABLE = "locked_periods"
SOURCE_LOCKED_PD = "locked_md_ad_pd"
SOURCE_DERIVED = "derived_from_full_timeline"
SOURCE_UNAVAILABLE = "unavailable"

_ISO = "%Y-%m-%dT%H:%M:%S"


def parse_dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if not v:
        return None
    s = str(v)
    for fmt, n in ((_ISO, 19), ("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(s[:n], fmt)
        except ValueError:
            continue
    return None


def iso(dt: datetime) -> str:
    return dt.strftime(_ISO)


def subdivide(lord: str, start: datetime, end: datetime, years: float) -> list[dict]:
    """Nine sub-periods of a period, starting from its own lord."""
    si = VIMSHOTTARI_ORDER.index(lord)
    out: list[dict] = []
    cur = start
    for i in range(9):
        k = (si + i) % 9
        y = float(years) * (VIMSHOTTARI_YEARS[k] / float(VIMSHOTTARI_TOTAL))  # app.py operation order
        nxt = cur + timedelta(days=DAYS_PER_YEAR * y)
        out.append({"lord": VIMSHOTTARI_ORDER[k], "start": cur, "end": nxt, "years": y})
        cur = nxt
    out[-1]["end"] = end
    return out


def mahadasha_timeline(moon_lon: float, birth_local: datetime, horizon_years: float = 100.0) -> list[dict]:
    """
    Mahadasha list from birth — same as app.calculate_vimshottari_dasha:
    balance of the Moon-nakshatra lord's period first, 365.25-day years,
    last period clamped to ``horizon_years`` after birth.
    """
    nak_width = 360.0 / 27.0
    arc = float(moon_lon) % 360.0
    nak_idx = min(int(arc // nak_width), 26)
    start_idx = VIMSHOTTARI_ORDER.index(NAK_LORDS[nak_idx])
    balance = VIMSHOTTARI_YEARS[start_idx] * (1.0 - (arc - nak_idx * nak_width) / nak_width)

    birth = parse_dt(birth_local)
    horizon_end = birth + timedelta(days=DAYS_PER_YEAR * horizon_years)
    out = [{"lord": VIMSHOTTARI_ORDER[start_idx], "start": birth,
            "end": birth + timedelta(days=DAYS_PER_YEAR * balance), "years": balance}]
    i = 1
    while True:
        k = (start_idx + i) % 9
        s = out[-1]["end"]
        out.append({"lord": VIMSHOTTARI_ORDER[k], "start": s,
                    "end": s + timedelta(days=DAYS_PER_YEAR * VIMSHOTTARI_YEARS[k]),
                    "years": VIMSHOTTARI_YEARS[k]})
        i += 1
        if (out[-1]["end"] - birth).days > DAYS_PER_YEAR * horizon_years:
            if (out[-1]["start"] - birth).days >= DAYS_PER_YEAR * horizon_years:
                out.pop()
            else:
                out[-1]["end"] = horizon_end
                out[-1]["years"] = (horizon_end - out[-1]["start"]).days / DAYS_PER_YEAR
            break
        if i > 40:
            break
    return out


def _normalise_timeline(timeline: Iterable[dict]) -> list[dict]:
    rows = []
    for m in timeline or []:
        s, e = parse_dt(m.get("start")), parse_dt(m.get("end"))
        if s is None or e is None or m.get("lord") not in VIMSHOTTARI_ORDER:
            continue
        years = m.get("years")
        years = float(years) if years not in (None, "") else (e - s).total_seconds() / 86400.0 / DAYS_PER_YEAR
        rows.append({"lord": m["lord"], "start": s, "end": e, "years": years})
    return rows


def _pd_rows(mahas: list[dict], win_start: datetime, win_end: datetime) -> list[dict]:
    rows: list[dict] = []
    for md in mahas:
        if md["end"] <= win_start or md["start"] >= win_end:
            continue
        for ad in subdivide(md["lord"], md["start"], md["end"], md["years"]):
            if ad["end"] <= win_start or ad["start"] >= win_end:
                continue
            for pd in subdivide(ad["lord"], ad["start"], ad["end"], ad["years"]):
                if pd["end"] <= win_start or pd["start"] >= win_end:
                    continue
                rows.append({
                    "md": md["lord"], "md_start": iso(md["start"]), "md_end": iso(md["end"]),
                    "ad": ad["lord"], "ad_start": iso(ad["start"]), "ad_end": iso(ad["end"]),
                    "pd": pd["lord"], "pd_start": iso(pd["start"]), "pd_end": iso(pd["end"]),
                })
    return rows


def build_locked_periods(
    timeline: Iterable[dict],
    lock_dt: datetime,
    years_before: int = LOCK_YEARS_BEFORE,
    years_after: int = LOCK_YEARS_AFTER,
) -> list[dict]:
    """PD-level rows covering [lock_dt − years_before, lock_dt + years_after)."""
    win_start = lock_dt - timedelta(days=DAYS_PER_YEAR * years_before)
    win_end = lock_dt + timedelta(days=DAYS_PER_YEAR * years_after)
    return _pd_rows(_normalise_timeline(timeline), win_start, win_end)


def _period(row: dict, level: str) -> dict:
    s, e = row[f"{level}_start"], row[f"{level}_end"]
    return {"lord": row[level], "start": s[:10], "end": e[:10], "start_iso": s, "end_iso": e}


def _row_at(rows: list[dict], query_dt: datetime) -> Optional[dict]:
    for r in rows:
        if parse_dt(r["pd_start"]) <= query_dt < parse_dt(r["pd_end"]):
            return r
    return None


def lock_dasha(timeline: Iterable[dict], lock_dt: Optional[datetime] = None) -> dict:
    """
    Build the natal_ref ``dasha`` section: locked MD/AD/PD at lock_dt plus the
    locked PD table. ``timeline`` entries may carry datetimes (app.py raw) or strings.
    """
    lock_dt = lock_dt or datetime.now()
    mahas = _normalise_timeline(timeline)
    rows = build_locked_periods(mahas, lock_dt)
    cur = _row_at(rows, lock_dt)
    empty = {"lord": "", "start": "", "end": ""}
    return {
        "locked_at": iso(lock_dt),
        "method": "Vimshottari, 365.25-day year, last sub-period pinned to parent end (app.py)",
        "locked_md": {k: v for k, v in _period(cur, "md").items() if not k.endswith("_iso")} if cur else dict(empty),
        "locked_ad": {k: v for k, v in _period(cur, "ad").items() if not k.endswith("_iso")} if cur else dict(empty),
        "locked_pd": {k: v for k, v in _period(cur, "pd").items() if not k.endswith("_iso")} if cur else dict(empty),
        "locked_periods": rows,
        "full_timeline": [
            {"lord": m["lord"], "start": iso(m["start"]), "end": iso(m["end"]), "years": round(m["years"], 6)}
            for m in mahas
        ],
    }


def resolve_dasha(natal_ref: dict, query_dt: datetime) -> dict:
    """
    Active MD/AD/PD at query_dt (naive local wall time, same basis as birth time).

    Returns {"md": {...}, "ad": {...}, "pd": {...}, "source": str}. Each period
    dict has lord, start/end (YYYY-MM-DD) and start_iso/end_iso.
    """
    query_dt = parse_dt(query_dt)
    dasha = natal_ref.get("dasha") or {}

    row = _row_at(dasha.get("locked_periods") or [], query_dt)
    if row:
        return {"md": _period(row, "md"), "ad": _period(row, "ad"), "pd": _period(row, "pd"),
                "source": SOURCE_LOCKED_TABLE}

    lpd = dasha.get("locked_pd") or {}
    s, e = parse_dt(lpd.get("start")), parse_dt(lpd.get("end"))
    if s and e and s <= query_dt < e and lpd.get("lord"):
        def _p(d: dict) -> dict:
            return {"lord": d.get("lord", ""), "start": str(d.get("start", ""))[:10],
                    "end": str(d.get("end", ""))[:10],
                    "start_iso": d.get("start", ""), "end_iso": d.get("end", "")}
        return {"md": _p(dasha.get("locked_md") or {}), "ad": _p(dasha.get("locked_ad") or {}),
                "pd": _p(lpd), "source": SOURCE_LOCKED_PD}

    mahas = _normalise_timeline(dasha.get("full_timeline") or [])
    rows = _pd_rows(mahas, query_dt - timedelta(days=1), query_dt + timedelta(days=1))
    row = _row_at(rows, query_dt)
    if row:
        return {"md": _period(row, "md"), "ad": _period(row, "ad"), "pd": _period(row, "pd"),
                "source": SOURCE_DERIVED}

    empty = {"lord": "", "start": "", "end": "", "start_iso": "", "end_iso": ""}
    return {"md": dict(empty), "ad": dict(empty), "pd": dict(empty), "source": SOURCE_UNAVAILABLE}
