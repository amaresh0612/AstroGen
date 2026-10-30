"""
Sukshma (Level 4) and Prana (Level 5) Dasha calculation engine.

REPORT LOCK RULE (strictly enforced):
    LOCKED:    MD / AD / PD — taken from natal_ref.json, never recalculated.
    CALCULATED: SD (Sukshma, L4) and Prana (L5) are derived beneath the locked PD.

The engine accepts locked dasha values as input and subdivides only the
levels below PD. It will never override or silently replace MD/AD/PD.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

DASHA_LORDS = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
DASHA_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
TOTAL_YEARS = sum(DASHA_YEARS)  # 120


def _days(years: float) -> float:
    return years * 365.25


def _subdivide(parent_lord: str, parent_start: datetime, parent_end: datetime) -> list[dict]:
    """
    Divide a dasha period into 9 sub-periods proportional to Vimshottari.
    The first sub-lord is the parent's own lord; then the sequence continues.
    """
    parent_days = (parent_end - parent_start).total_seconds() / 86400.0
    start_idx   = DASHA_LORDS.index(parent_lord)
    periods: list[dict] = []
    cur = parent_start
    for i in range(9):
        idx   = (start_idx + i) % 9
        lord  = DASHA_LORDS[idx]
        ratio = DASHA_YEARS[idx] / TOTAL_YEARS
        dur   = timedelta(days=parent_days * ratio)
        end   = cur + dur
        periods.append({
            "lord":  lord,
            "start": cur,
            "end":   end,
            "years": round(parent_days * ratio / 365.25, 4),
        })
        cur = end
    if periods:
        periods[-1]["end"] = parent_end
    return periods


def compute_sukshma_dashas(
    pd_lord: str,
    pd_start: datetime,
    pd_end: datetime,
) -> list[dict]:
    """
    Compute 9 Sukshma (L4) sub-periods within a locked Pratyantar Dasha.

    Parameters are taken directly from natal_ref.json locked_pd.
    """
    return _subdivide(pd_lord, pd_start, pd_end)


def compute_prana_dashas(
    sd_lord: str,
    sd_start: datetime,
    sd_end: datetime,
) -> list[dict]:
    """
    Compute 9 Prana (L5) sub-periods within a Sukshma Dasha.
    """
    return _subdivide(sd_lord, sd_start, sd_end)


def get_active_sukshma(
    pd_lord: str,
    pd_start: datetime,
    pd_end: datetime,
    query_dt: datetime,
) -> Optional[dict]:
    """Return the active Sukshma Dasha at query_dt, or None if outside PD range."""
    if not (pd_start <= query_dt <= pd_end):
        return None
    for sd in compute_sukshma_dashas(pd_lord, pd_start, pd_end):
        if sd["start"] <= query_dt <= sd["end"]:
            return sd
    return None


def get_active_prana(
    pd_lord: str,
    pd_start: datetime,
    pd_end: datetime,
    query_dt: datetime,
) -> Optional[dict]:
    """Return the active Prana Dasha at query_dt, or None."""
    sd = get_active_sukshma(pd_lord, pd_start, pd_end, query_dt)
    if not sd:
        return None
    for prana in compute_prana_dashas(sd["lord"], sd["start"], sd["end"]):
        if prana["start"] <= query_dt <= prana["end"]:
            return prana
    return None


def get_dasha_state(
    locked_md: dict,
    locked_ad: dict,
    locked_pd: dict,
    query_dt: Optional[datetime] = None,
) -> dict:
    """
    Return a complete dasha state dict combining locked MD/AD/PD with
    calculated SD/Prana beneath them.

    Parameters
    ----------
    locked_md, locked_ad, locked_pd : dicts with keys lord, start, end
        (start/end as ISO strings or datetime objects)
    query_dt : datetime to find active SD/Prana; defaults to now.
    """
    if query_dt is None:
        query_dt = datetime.now()

    def _parse(d: dict, key: str) -> datetime:
        v = d.get(key)
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
        return datetime.min

    pd_lord  = locked_pd.get("lord", "")
    pd_start = _parse(locked_pd, "start")
    pd_end   = _parse(locked_pd, "end")

    sd = get_active_sukshma(pd_lord, pd_start, pd_end, query_dt) if pd_lord else None
    prana = None
    if sd:
        prana = get_active_prana(pd_lord, pd_start, pd_end, query_dt)

    def _fmt(dt: Optional[datetime]) -> str:
        return dt.strftime("%Y-%m-%d") if dt else ""

    return {
        # LOCKED — from natal_ref.json
        "md_lord":  locked_md.get("lord", ""),
        "md_start": locked_md.get("start", ""),
        "md_end":   locked_md.get("end", ""),
        "ad_lord":  locked_ad.get("lord", ""),
        "ad_start": locked_ad.get("start", ""),
        "ad_end":   locked_ad.get("end", ""),
        "pd_lord":  pd_lord,
        "pd_start": locked_pd.get("start", ""),
        "pd_end":   locked_pd.get("end", ""),
        # CALCULATED beneath PD
        "sukshma_lord":  sd["lord"]    if sd    else None,
        "sukshma_start": _fmt(sd["start"]) if sd else None,
        "sukshma_end":   _fmt(sd["end"])   if sd else None,
        "prana_lord":    prana["lord"]    if prana else None,
        "prana_start":   _fmt(prana["start"]) if prana else None,
        "prana_end":     _fmt(prana["end"])   if prana else None,
    }
