"""
Sukshma (Level 4) and Prana (Level 5) Dasha calculation engine.

REPORT LOCK RULE (strictly enforced):
    LOCKED:    MD / AD / PD — read from natal_ref.json via analysis.vimshottari.resolve_dasha.
    CALCULATED: SD (Sukshma, L4) and Prana (L5) are derived beneath the locked PD.

The engine accepts locked dasha values as input and subdivides only the
levels below PD. It will never override or silently replace MD/AD/PD.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from analysis.vimshottari import DAYS_PER_YEAR, parse_dt, subdivide


def _subdivide(parent_lord: str, parent_start: datetime, parent_end: datetime) -> list[dict]:
    years = (parent_end - parent_start).total_seconds() / 86400.0 / DAYS_PER_YEAR
    periods = subdivide(parent_lord, parent_start, parent_end, years)
    for p in periods:
        p["years"] = round(p["years"], 4)
    return periods


def compute_sukshma_dashas(pd_lord: str, pd_start: datetime, pd_end: datetime) -> list[dict]:
    """Nine Sukshma (L4) sub-periods within a locked Pratyantar Dasha."""
    return _subdivide(pd_lord, pd_start, pd_end)


def compute_prana_dashas(sd_lord: str, sd_start: datetime, sd_end: datetime) -> list[dict]:
    """Nine Prana (L5) sub-periods within a Sukshma Dasha."""
    return _subdivide(sd_lord, sd_start, sd_end)


def _active(periods: list[dict], query_dt: datetime) -> Optional[dict]:
    for p in periods:
        if p["start"] <= query_dt < p["end"]:
            return p
    return None


def get_active_sukshma(pd_lord: str, pd_start: datetime, pd_end: datetime,
                       query_dt: datetime) -> Optional[dict]:
    """Active Sukshma at query_dt, or None if outside the PD range."""
    if not (pd_start <= query_dt < pd_end):
        return None
    return _active(compute_sukshma_dashas(pd_lord, pd_start, pd_end), query_dt)


def get_active_prana(pd_lord: str, pd_start: datetime, pd_end: datetime,
                     query_dt: datetime) -> Optional[dict]:
    """Active Prana at query_dt, or None."""
    sd = get_active_sukshma(pd_lord, pd_start, pd_end, query_dt)
    if not sd:
        return None
    return _active(compute_prana_dashas(sd["lord"], sd["start"], sd["end"]), query_dt)


def get_dasha_state(
    locked_md: dict,
    locked_ad: dict,
    locked_pd: dict,
    query_dt: Optional[datetime] = None,
) -> dict:
    """
    Locked MD/AD/PD combined with calculated SD/Prana beneath them.

    Period dicts carry lord/start/end; ``start_iso``/``end_iso`` (from
    resolve_dasha) are preferred for sub-day precision when present.
    """
    query_dt = query_dt or datetime.now()

    def _bound(d: dict, key: str) -> Optional[datetime]:
        return parse_dt(d.get(f"{key}_iso") or d.get(key))

    pd_lord = locked_pd.get("lord", "")
    pd_start, pd_end = _bound(locked_pd, "start"), _bound(locked_pd, "end")

    sd = prana = None
    if pd_lord and pd_start and pd_end:
        sd = get_active_sukshma(pd_lord, pd_start, pd_end, query_dt)
        if sd:
            prana = get_active_prana(pd_lord, pd_start, pd_end, query_dt)

    def _fmt(dt: Optional[datetime]) -> str:
        return dt.strftime("%Y-%m-%d") if dt else ""

    def _d(v) -> str:
        return str(v or "")[:10]

    return {
        # LOCKED — from natal_ref.json
        "md_lord":  locked_md.get("lord", ""),
        "md_start": _d(locked_md.get("start")),
        "md_end":   _d(locked_md.get("end")),
        "ad_lord":  locked_ad.get("lord", ""),
        "ad_start": _d(locked_ad.get("start")),
        "ad_end":   _d(locked_ad.get("end")),
        "pd_lord":  pd_lord,
        "pd_start": _d(locked_pd.get("start")),
        "pd_end":   _d(locked_pd.get("end")),
        # CALCULATED beneath PD
        "sukshma_lord":  sd["lord"] if sd else None,
        "sukshma_start": _fmt(sd["start"]) if sd else None,
        "sukshma_end":   _fmt(sd["end"]) if sd else None,
        "prana_lord":    prana["lord"] if prana else None,
        "prana_start":   _fmt(prana["start"]) if prana else None,
        "prana_end":     _fmt(prana["end"]) if prana else None,
    }
