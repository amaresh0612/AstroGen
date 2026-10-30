"""
Promise and Denial analysis engine.

Determines whether an event is supported by the natal chart using
KP principles. The verdict is qualitative — no numeric scores.

Verdict states (per PRD §8 feedback):
    PROMISED             — strong multi-level support, CSL confirms
    SUPPORTED            — good signification, dasha aligns
    CONDITIONALLY SUPPORTED — partial evidence, mixed CSL or weak dasha
    WEAK / INCONCLUSIVE  — insufficient significators or missing data
    CONFLICTED           — roughly equal supporting and conflicting indicators
    NOT SUPPORTED        — denial indicators outweigh support

"Delayed" is NOT a verdict state — delay is an interpretation based on
Saturn involvement, 8/12 house links, and dasha sequence, which the
AI layer evaluates from supporting evidence.
"""
from __future__ import annotations

from typing import Optional
from schemas.event_houses import EVENT_HOUSES, DENIAL_HOUSES, TOPIC_LABELS

VERDICTS = [
    "STRONG",
    "ACTIVE",
    "MODERATE",
    "MIXED",
    "WEAK",
]

# -----------------------------------------------------------------------
# Manifestation map: topic → (threshold, ranked list of manifestations)
# Threshold is the score/10.  The engine picks the group whose threshold
# the current score meets or exceeds, then returns the ranked items.
# -----------------------------------------------------------------------
_M = [  # (min_score, manifestations_list)
    (7.5, []),   # strong — filled per topic below
    (4.5, []),   # moderate
    (0.0, []),   # weak
]

MANIFESTATION_MAP: dict[str, list[tuple[float, list[str]]]] = {
    "career": [
        (7.5, ["Promotion or significant role advancement",
               "New high-responsibility assignment", "Job change to better position"]),
        (4.5, ["Increased recognition / visibility",
               "Leadership or project ownership opportunity",
               "Performance evaluation milestone"]),
        (0.0, ["Career networking or skill-building phase",
               "Minor role adjustment", "Background career movement"]),
    ],
    "promotion": [
        (7.5, ["Direct promotion with title / compensation change",
               "Fast-track advancement in current organisation"]),
        (4.5, ["Promotion discussion or shortlisting",
               "Increased authority without title change yet"]),
        (0.0, ["Recognition only — formal promotion not yet indicated",
               "Groundwork period"]),
    ],
    "job_change": [
        (7.5, ["Successful job change to new organisation",
               "High-profile offer and transition"]),
        (4.5, ["Active job search yielding strong leads",
               "Internal transfer or lateral move"]),
        (0.0, ["Exploring options — concrete change not yet supported",
               "Restlessness without clear opening"]),
    ],
    "marriage": [
        (7.5, ["Marriage / formal commitment",
               "Engagement or setting a wedding date"]),
        (4.5, ["Serious relationship progressing toward commitment",
               "Family introduction or approval discussions"]),
        (0.0, ["Relationship formation — marriage timing not yet supported",
               "Social / meeting opportunities"]),
    ],
    "relationship": [
        (7.5, ["Deep emotional commitment or reunion",
               "Significant romantic development"]),
        (4.5, ["Reconnection with existing partner",
               "New meaningful romantic meeting"]),
        (0.0, ["Social interactions, light connections",
               "Introspective or detached phase"]),
    ],
    "children": [
        (7.5, ["Pregnancy / childbirth", "Adoption or major parental milestone"]),
        (4.5, ["Active planning / fertility window", "Parenting responsibility increases"]),
        (0.0, ["Background fertility theme — direct timing not strongly supported"]),
    ],
    "property": [
        (7.5, ["Property purchase, construction, or significant acquisition"]),
        (4.5, ["Active property search, loan approval, or negotiation"]),
        (0.0, ["Property interest — acquisition not yet strongly supported"]),
    ],
    "travel": [
        (7.5, ["Significant domestic or international travel",
               "Purposeful journey with concrete outcomes"]),
        (4.5, ["Short travel or business trip", "Travel planning materialising"]),
        (0.0, ["Restlessness without confirmed travel window"]),
    ],
    "foreign_settlement": [
        (7.5, ["Relocation abroad or long-term foreign assignment"]),
        (4.5, ["Visa / immigration process, foreign opportunity opening"]),
        (0.0, ["Foreign interest — settlement not yet strongly supported"]),
    ],
    "wealth": [
        (7.5, ["Significant income increase, windfall, or investment gain"]),
        (4.5, ["Steady financial improvement, bonus, or savings milestone"]),
        (0.0, ["Modest financial movement — major wealth event not indicated"]),
    ],
    "education": [
        (7.5, ["Major educational milestone, qualification, or admission"]),
        (4.5, ["Ongoing study with positive progression"]),
        (0.0, ["Learning phase without major credential event"]),
    ],
    "health": [
        (7.5, ["Recovery milestone or significant health improvement"]),
        (4.5, ["Ongoing health management — watchful but stable"]),
        (0.0, ["Low vitality period — rest and prevention recommended"]),
    ],
    "spirituality": [
        (7.5, ["Deep spiritual breakthrough, pilgrimage, or initiation"]),
        (4.5, ["Active spiritual practice, study, or retreat"]),
        (0.0, ["Spiritual background theme"]),
    ],
}


def _rank_manifestations(topic: str, score_pct10: float, dark_houses: list[int]) -> list[str]:
    """
    Return an ordered list of the most likely manifestations.

    When critical houses are dark (not activated by either CSL or dasha):
    - "Strong" tier items are demoted to conditional
    - "Moderate" tier items become the primary recommendations
    This enforces the Reality Check Rule: Dasha = Permission.
    """
    tiers = MANIFESTATION_MAP.get(topic, [])
    if not tiers:
        return ["Refer to natal chart for topic-specific timing"]

    # Select tier by score
    primary_items: list[str] = []
    for threshold, items in tiers:
        if score_pct10 >= threshold:
            primary_items = list(items)
            break
    if not primary_items:
        primary_items = tiers[-1][1] if tiers else []

    if not dark_houses:
        return primary_items

    # Dark houses exist — demotion logic
    # Find the moderate tier (second tier)
    moderate_items: list[str] = []
    strong_items: list[str] = []
    if len(tiers) >= 1:
        strong_items = list(tiers[0][1])
    if len(tiers) >= 2:
        moderate_items = list(tiers[1][1])

    h_str = ", ".join(f"H{h}" for h in dark_houses)

    if score_pct10 >= 7.5:
        # Would have been strong — demote strong items to conditional
        result = list(moderate_items)
        result += [f"[Conditional — requires {h_str} activation] {item}"
                   for item in strong_items[:2]]
        result.append(
            f"Note: {h_str} not activated by current MD/AD/PD — "
            "upgrade manifestation only when a sub-period activating these houses begins."
        )
        return result
    else:
        # Score already at moderate/weak tier — just add caveat
        result = list(primary_items)
        result.append(
            f"Note: {h_str} not activated by current dasha — "
            "full manifestation may require an additional sub-period trigger."
        )
        return result

PLANETS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]
SIGN_LORDS = {
    "Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon",
    "Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars",
    "Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter",
}


def _signified_houses_for_planet(
    planet: str,
    significators: Optional[dict],
    strength_map: dict,
) -> list[int]:
    """
    Sole house list for CSL Direct-House Support.

    Prefer locked natal significators[planet].signified_houses.
    Fall back to strength_map keys only when significators are absent.
    """
    if significators:
        block = significators.get(planet) or {}
        houses = block.get("signified_houses")
        if houses is not None:
            return sorted(int(h) for h in houses)
    return sorted(int(h) for h in strength_map.get(planet, {}).keys())


def _csl_direct_house_support(
    csl_planet: str,
    house_num: int,
    significators: Optional[dict],
    strength_map: dict,
) -> dict:
    """
    Layer 1 — CSL Direct-House Support (simplified scoring test):

        CSL planet → natal.significators[CSL].signified_houses
                  → contains house_num?

    This is NOT full classical KP promise — only direct-house membership.
    """
    sig_houses = _signified_houses_for_planet(csl_planet, significators, strength_map)
    if house_num in sig_houses:
        info = strength_map.get(csl_planet, {}).get(house_num, {})
        return {
            "csl_direct_support": True,
            "csl_promise":        True,  # alias for older consumers
            "csl_level":          info.get("level"),
            "csl_level_label":    info.get("level_label"),
            "csl_signified_houses": sig_houses,
        }
    return {
        "csl_direct_support": False,
        "csl_promise":        False,
        "csl_level":          None,
        "csl_level_label":    None,
        "csl_signified_houses": sig_houses,
    }


def _csl_denies(csl_planet: str, denial_houses: list[int], strength_map: dict) -> list[int]:
    """Return which denial_houses the CSL planet signifies."""
    csl_houses = strength_map.get(csl_planet, {})
    return [h for h in denial_houses if h in csl_houses]


def _active_dasha_alignment(
    dasha_lords: list[str],
    primary_houses: list[int],
    strength_map: dict,
    max_level: int = 3,
) -> tuple[list[str], list[str]]:
    """
    Check which active dasha lords (MD, AD, PD) signify primary_houses.
    Returns (supporting, non_supporting).
    """
    supporting, non_supporting = [], []
    for lord in dasha_lords:
        lord_houses = strength_map.get(lord, {})
        aligned = any(h in lord_houses and lord_houses[h]["level"] <= max_level
                      for h in primary_houses)
        (supporting if aligned else non_supporting).append(lord)
    return supporting, non_supporting


def compute_promise_denial(
    topic: str,
    planets: dict,
    houses: dict,
    cuspal_sublords: dict,
    strength_map: dict,
    active_md: str,
    active_ad: str,
    active_pd: str,
    significators: Optional[dict] = None,
) -> dict:
    """
    Compute promise/denial verdict for a single topic.

    Parameters
    ----------
    topic           : One of the keys in EVENT_HOUSES (e.g. "career")
    planets         : natal_ref.json 'planets'
    houses          : natal_ref.json 'houses'
    cuspal_sublords : natal_ref.json 'cuspal_sublords' (str keys "1"–"12")
    strength_map    : Output of significator_strength.compute_significator_strength()
    active_md/ad/pd : Current dasha lord strings
    significators   : Locked natal significators dict — REQUIRED for CSL
                      Direct-House Support (uses signified_houses only)
    """
    primary_houses = EVENT_HOUSES.get(topic, [])
    denial_houses  = DENIAL_HOUSES.get(topic, [])
    topic_label    = TOPIC_LABELS.get(topic, topic.title())

    if not primary_houses:
        return {
            "topic": topic,
            "topic_label": topic_label,
            "verdict": "WEAK / INCONCLUSIVE",
            "supporting_evidence": ["Unknown topic — no house mapping available"],
            "conflicting_evidence": [],
            "dasha_alignment": "",
            "csl_verdict": "",
            "primary_houses": [],
        }

    supporting_evidence: list[str] = []
    conflicting_evidence: list[str] = []

    # --- CSL Direct-House Support for EACH primary house ---
    csl_analyses: list[dict] = []
    csl_verdict_str = ""
    csl_support_houses: list[int] = []

    for h_num in primary_houses:
        h_str = str(h_num)
        csl = cuspal_sublords.get(h_str, "")
        if not csl:
            csl_analyses.append({
                "house":              h_num,
                "csl":                "—",
                "csl_direct_support": False,
                "csl_promise":        False,
                "csl_level":          None,
                "csl_signified_houses": [],
                "supports":           [],
                "denies":             [],
                "note":               f"H{h_num} → CSL unavailable — Direct CSL support: NO",
                "pdf_line":           f"H{h_num} → — → Direct CSL: NO",
            })
            conflicting_evidence.append(f"H{h_num} CSL not available")
            continue

        support = _csl_direct_house_support(csl, h_num, significators, strength_map)
        csl_ok    = support["csl_direct_support"]
        csl_level = support["csl_level"]
        sig_houses = support["csl_signified_houses"]
        h_deny    = _csl_denies(csl, denial_houses, strength_map)

        if csl_ok:
            csl_support_houses.append(h_num)
            note = (
                f"H{h_num} → {csl} → Direct CSL support: YES"
                + (f" (L{csl_level})" if csl_level else "")
            )
            supporting_evidence.append(note)
            if h_deny:
                conflicting_evidence.append(
                    f"H{h_num} CSL {csl} also signifies denial {h_deny}"
                )
        elif h_deny:
            note = (
                f"H{h_num} → {csl} → Direct CSL support: NO "
                f"(sigs {sig_houses}; denial {h_deny})"
            )
            conflicting_evidence.append(note)
        else:
            note = (
                f"H{h_num} → {csl} → Direct CSL support: NO "
                f"(sigs {sig_houses})"
            )
            conflicting_evidence.append(note)

        csl_analyses.append({
            "house":                h_num,
            "csl":                  csl,
            "csl_direct_support":   csl_ok,
            "csl_promise":          csl_ok,  # alias
            "csl_level":            csl_level,
            "csl_level_label":      support.get("csl_level_label"),
            "csl_signified_houses": sig_houses,
            "supports":             [h_num] if csl_ok else [],
            "denies":               h_deny,
            "note":                 note,
            "pdf_line": (
                f"H{h_num} → {csl} → Direct CSL: {'YES' if csl_ok else 'NO'}"
            ),
        })

    # Compact CSL verdict string for PDF display
    csl_verdict_str = "  |  ".join(a["note"] for a in csl_analyses)

    # --- Significator count across primary houses (L1–L3) ---
    strong_sigs: dict[str, int] = {}
    for pname, house_map in strength_map.items():
        for h, info in house_map.items():
            if h in primary_houses and info["level"] <= 3:
                existing = strong_sigs.get(pname)
                if existing is None or info["level"] < existing:
                    strong_sigs[pname] = info["level"]

    if strong_sigs:
        sig_str = ", ".join(f"{p}(L{v})" for p, v in sorted(strong_sigs.items(), key=lambda x: x[1]))
        supporting_evidence.append(f"Strong significators for {topic}: {sig_str}")
    else:
        conflicting_evidence.append(f"No strong (L1–L3) significators found for {topic}")

    # --- Check significators also strongly signify denial houses ---
    for pname in strong_sigs:
        denial_links = [h for h in denial_houses
                        if h in strength_map.get(pname, {})
                        and strength_map[pname][h]["level"] <= 2]
        if denial_links:
            conflicting_evidence.append(
                f"{pname} also strongly signifies denial houses {denial_links}"
            )

    # --- Dasha alignment: per-lord, per-house breakdown ---
    dasha_lords = [d for d in [active_md, active_ad, active_pd] if d]
    dasha_supporting, dasha_non = _active_dasha_alignment(dasha_lords, primary_houses, strength_map)

    # House-by-house coverage by the active dasha lords
    dasha_covered: set[int] = set()
    lord_detail_parts: list[str] = []
    for lord in dasha_lords:
        lord_houses_in_topic = [
            h for h in primary_houses
            if h in strength_map.get(lord, {})
            and strength_map[lord][h]["level"] <= 3
        ]
        if lord_houses_in_topic:
            lord_detail_parts.append(f"{lord}→H{','.join(str(h) for h in lord_houses_in_topic)}")
            dasha_covered.update(lord_houses_in_topic)
        else:
            lord_detail_parts.append(f"{lord}→—")

    uncovered = [h for h in primary_houses if h not in dasha_covered]

    if dasha_supporting and not uncovered:
        dasha_alignment_str = (
            f"Dasha: all primary houses covered. "
            f"{' | '.join(lord_detail_parts)}"
        )
        supporting_evidence.append(dasha_alignment_str)
    elif dasha_supporting and uncovered:
        dasha_alignment_str = (
            f"Dasha: partial — {' | '.join(lord_detail_parts)}. "
            f"H{','.join(str(h) for h in uncovered)} not activated by current dasha lords."
        )
        supporting_evidence.append(f"Dasha lords aligned: {', '.join(dasha_supporting)}")
        conflicting_evidence.append(
            f"H{','.join(str(h) for h in uncovered)} not directly activated by MD/AD/PD"
        )
    elif dasha_non:
        dasha_alignment_str = (
            f"Dasha: no lord directly aligned. "
            f"{' | '.join(lord_detail_parts)}"
        )
        conflicting_evidence.append(dasha_alignment_str)
    else:
        dasha_alignment_str = "Dasha data unavailable"

    # --- Per-house activation matrix (before verdict + scoring) ---
    n_houses = len(primary_houses) or 1
    house_activation: dict[int, dict] = {}
    for h in primary_houses:
        analysis = next((a for a in csl_analyses if a["house"] == h), None)
        h_csl_ok   = bool(analysis and analysis.get("csl_direct_support", analysis.get("csl_promise")))
        h_dasha_ok = h in dasha_covered
        dasha_lords_for_h = [
            lord for lord in dasha_lords
            if h in strength_map.get(lord, {})
            and strength_map[lord][h]["level"] <= 3
        ]
        house_activation[h] = {
            "house":             h,
            "csl":               analysis.get("csl", "") if analysis else "",
            "csl_direct_support": h_csl_ok,
            "csl_promise":       h_csl_ok,
            "csl_level":         analysis.get("csl_level") if analysis else None,
            "csl_signified_houses": (
                analysis.get("csl_signified_houses", []) if analysis else []
            ),
            "dasha_permission":  h_dasha_ok,
            "dasha_lords":       dasha_lords_for_h,
            "csl_ok":            h_csl_ok,
            "dasha_ok":          h_dasha_ok,
            "pdf_audit": (
                f"H{h}: CSL {analysis.get('csl', '—') if analysis else '—'} "
                f"→ {'YES' if h_csl_ok else 'NO'}; "
                f"Dasha → {', '.join(dasha_lords_for_h) if dasha_lords_for_h else 'none'}"
            ),
        }

    csl_covered         = sum(1 for a in house_activation.values() if a["csl_ok"])
    dasha_covered_count = sum(1 for a in house_activation.values() if a["dasha_ok"])

    # --- Verdict logic ---
    s = len(supporting_evidence)
    c = len(conflicting_evidence)
    csl_ok = csl_covered >= max(1, (n_houses + 1) // 2)
    dasha_ok = len(dasha_supporting) >= 2

    if csl_ok and dasha_ok and s >= 3 and c == 0:
        verdict = "STRONG"
    elif csl_ok and dasha_ok and s >= 2:
        verdict = "ACTIVE"
    elif csl_ok and (dasha_ok or s >= 2) and c <= 1:
        verdict = "MODERATE"
    elif not csl_ok and not strong_sigs:
        verdict = "WEAK"
    elif s > 0 and c > 0 and abs(s - c) <= 1:
        verdict = "MIXED"
    elif s > 0 and c > s:
        verdict = "MODERATE"
    else:
        verdict = "WEAK"

    # --- Scoring ---
    csl_score   = round(csl_covered / n_houses * 3, 2)
    dasha_score = round(dasha_covered_count / n_houses * 3, 2)

    # Significator quality bonus (0-2)
    sig_bonus = 0
    for lvl in strong_sigs.values():
        sig_bonus += max(0, 4 - lvl)
    sig_bonus = min(2, sig_bonus)

    raw   = csl_score + dasha_score + sig_bonus   # 0–8
    pct10 = round(raw / 8 * 10, 1)

    # Dark houses: CSL fails AND Dasha fails for that specific house
    dark_houses = [h for h, a in house_activation.items()
                   if not a["csl_ok"] and not a["dasha_ok"]]

    # Gating caps — dasha is the permission layer
    if dasha_covered_count == 0:
        pct10 = min(pct10, 4.0)
    elif dark_houses:
        pct10 = min(pct10, 6.0)

    rp_score = 0   # RP sub-score added by calling context when RPs are available
    total_score = raw

    return {
        "topic":                topic,
        "topic_label":          topic_label,
        "primary_houses":       primary_houses,
        "csl_planet":           csl_analyses[0]["csl"] if csl_analyses else "",
        "csl_verdict":          csl_verdict_str,
        "csl_analyses":         csl_analyses,
        "verdict":              verdict,
        "supporting_evidence":  supporting_evidence,
        "conflicting_evidence": conflicting_evidence,
        "dasha_alignment":      dasha_alignment_str,
        "dasha_covered_houses": sorted(dasha_covered),
        "dasha_uncovered_houses": uncovered,
        "dark_houses":          dark_houses,
        "house_activation":     house_activation,
        "strong_significators": strong_sigs,
        "manifestations":       _rank_manifestations(topic, pct10, dark_houses),
        "score": {
            "pct10":        pct10,
            "csl_layer":    round(csl_score, 1),
            "dasha_layer":  round(dasha_score, 1),
            "sig_bonus":    sig_bonus,
            "rp_bonus":     rp_score,
            "dark_h":       dark_houses,
        },
    }


def compute_all_topics(
    planets: dict,
    houses: dict,
    cuspal_sublords: dict,
    strength_map: dict,
    active_md: str,
    active_ad: str,
    active_pd: str,
    topics: Optional[list[str]] = None,
    significators: Optional[dict] = None,
) -> list[dict]:
    """
    Compute promise/denial for multiple topics.
    Defaults to main life topics if topics is None.

    Pass locked natal significators so CSL Direct-House Support uses
    signified_houses as the sole membership test.
    """
    if topics is None:
        from schemas.event_houses import ALL_TOPICS
        topics = list(ALL_TOPICS)
    return [
        compute_promise_denial(
            topic, planets, houses, cuspal_sublords, strength_map,
            active_md, active_ad, active_pd,
            significators=significators,
        )
        for topic in topics
    ]
