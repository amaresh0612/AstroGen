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


def _window(
    level: str,
    period: dict,
    chain: dict,
    significators: dict,
    source: str,
    clip_start: datetime,
    clip_end: datetime,
) -> Optional[dict]:
    """One fine-dasha row, clipped to [clip_start, clip_end) with second precision."""
    start = max(period["start"], clip_start)
    end = min(period["end"], clip_end)
    if end <= start:
        return None
    return {
        "level": level,
        "lord": period["lord"],
        "start": start.isoformat(timespec="seconds"),
        "end": end.isoformat(timespec="seconds"),
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
    subdivided from the locked PD. Windows are clipped to the requested span so
    consecutive rows abut with no gaps or overlaps inside the coverage.
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
                    row = _window("sukshma", sk, chain, significators, r["source"], start, end)
                    if row:
                        windows.append(row)
                    continue
                sk_chain = {**chain, "sukshma": sk["lord"]}
                for pr in compute_prana_dashas(sk["lord"], sk["start"], sk["end"]):
                    if pr["end"] <= start or pr["start"] >= end:
                        continue
                    row = _window("prana", pr, sk_chain, significators, r["source"], start, end)
                    if row:
                        windows.append(row)
        cursor = max(pd_end, cursor + timedelta(minutes=1))
    return windows


def timeline_continuity_issues(windows: list[dict], coverage_start: datetime,
                               coverage_end: datetime, label: str) -> list[str]:
    """Gaps, overlaps, empty coverage or out-of-range edges for a fine-dasha timeline."""
    issues: list[str] = []
    if not windows:
        issues.append(f"{label}: no windows")
        return issues
    first, last = windows[0], windows[-1]
    if first["start"] != coverage_start.isoformat(timespec="seconds"):
        issues.append(
            f"{label}: first window starts at {first['start']}, "
            f"expected {coverage_start.isoformat(timespec='seconds')}"
        )
    if last["end"] != coverage_end.isoformat(timespec="seconds"):
        issues.append(
            f"{label}: last window ends at {last['end']}, "
            f"expected {coverage_end.isoformat(timespec='seconds')}"
        )
    for prev, nxt in zip(windows, windows[1:]):
        if prev["end"] != nxt["start"]:
            issues.append(f"{label}: gap/overlap at {prev['end']} → {nxt['start']}")
            if len(issues) >= 5:
                break
        if prev["start"] >= prev["end"]:
            issues.append(f"{label}: non-positive window at {prev['start']}")
            break
    return issues


def prana_parent_containment_issues(
    prana: list[dict], sukshma: list[dict],
) -> list[str]:
    """
    Each Prana window must sit inside a Sukshma whose lord matches ``sukshma``
    and whose [start,end) contains the Prana span. MD/AD/PD must match that parent.
    """
    issues: list[str] = []
    if not prana:
        return issues
    # Index sukshma by lord for quick containment search
    by_lord: dict[str, list[dict]] = {}
    for sk in sukshma:
        by_lord.setdefault(sk["lord"], []).append(sk)

    for w in prana:
        parents = by_lord.get(w.get("sukshma", ""), [])
        containing = [
            sk for sk in parents
            if sk["start"] <= w["start"] and w["end"] <= sk["end"]
        ]
        if not containing:
            issues.append(
                f"prana at {w['start']}→{w['end']} (sukshma={w.get('sukshma')}) "
                "has no containing Sukshma parent window"
            )
        else:
            sk = containing[0]
            for lvl in ("md", "ad", "pd"):
                if w.get(lvl) != sk.get(lvl):
                    issues.append(
                        f"prana at {w['start']}: {lvl}={w.get(lvl)} != "
                        f"parent sukshma {lvl}={sk.get(lvl)}"
                    )
                    break
        if not (w.get("md") and w.get("ad") and w.get("pd") and w.get("sukshma") and w.get("lord")):
            issues.append(f"prana at {w.get('start')} missing MD/AD/PD/Sukshma/lord chain")
        if len(issues) >= 8:
            break
    return issues
