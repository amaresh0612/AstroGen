"""
Sukshma / Prana window evidence beneath the locked MD/AD/PD.

The activation score reads MD/AD/PD only. Short-lived events (a trip, a piece
of news) usually show at Sukshma/Prana level, so this module lists those
windows with the houses each lord signifies and the topics whose primary
houses it touches. Evidence for the AI layer — not a score, not a prediction.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from analysis.dasha_fine import compute_prana_dashas, compute_sukshma_dashas
from analysis.vimshottari import resolve_dasha
from schemas.event_houses import EVENT_HOUSES


def topic_links(houses: list[int]) -> dict[str, list[int]]:
    """Topics where `houses` cover at least half of the primary houses."""
    hs = set(houses)
    out: dict[str, list[int]] = {}
    for topic, primary in EVENT_HOUSES.items():
        hit = sorted(hs.intersection(primary))
        if hit and len(hit) * 2 >= len(primary):
            out[topic] = hit
    return out


def lord_house_links(lord: Optional[str], significators: dict) -> dict:
    houses = sorted(int(h) for h in (significators.get(lord or "", {}) or {}).get("signified_houses", []))
    return {"signified_houses": houses, "topics": topic_links(houses)}


def _window(level: str, period: dict, chain: dict, significators: dict, source: str) -> dict:
    return {
        "level": level,
        "lord": period["lord"],
        "start": period["start"].isoformat(timespec="minutes"),
        "end": period["end"].isoformat(timespec="minutes"),
        **chain,
        **lord_house_links(period["lord"], significators),
        "dasha_source": source,
    }


def fine_dasha_windows(
    natal_ref: dict,
    start: datetime,
    end: datetime,
    significators: dict,
    level: str = "sukshma",
) -> list[dict]:
    """
    Sukshma (or Prana) windows overlapping [start, end), in time order.

    MD/AD/PD come only from resolve_dasha (the natal lock); levels below are
    subdivided from the locked PD.
    """
    if level not in ("sukshma", "prana"):
        raise ValueError("level must be 'sukshma' or 'prana'")
    windows: list[dict] = []
    seen_pd: set[str] = set()
    cursor = start
    while cursor < end:
        r = resolve_dasha(natal_ref, cursor)
        pd = r.get("pd")
        if not pd or not pd.get("start_iso"):
            cursor += timedelta(days=1)
            continue
        pd_start = datetime.fromisoformat(pd["start_iso"])
        pd_end = datetime.fromisoformat(pd["end_iso"])
        if pd["start_iso"] not in seen_pd:
            seen_pd.add(pd["start_iso"])
            chain = {"md": r["md"]["lord"], "ad": r["ad"]["lord"], "pd": pd["lord"]}
            for sk in compute_sukshma_dashas(pd["lord"], pd_start, pd_end):
                if sk["end"] <= start or sk["start"] >= end:
                    continue
                if level == "sukshma":
                    windows.append(_window("sukshma", sk, chain, significators, r["source"]))
                    continue
                sk_chain = {**chain, "sukshma": sk["lord"]}
                for pr in compute_prana_dashas(sk["lord"], sk["start"], sk["end"]):
                    if pr["end"] <= start or pr["start"] >= end:
                        continue
                    windows.append(_window("prana", pr, sk_chain, significators, r["source"]))
        cursor = max(pd_end, cursor + timedelta(minutes=1))
    return windows
