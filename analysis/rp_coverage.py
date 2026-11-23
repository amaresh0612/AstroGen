"""
House-coverage semantics for RP trigger matching (rp_convergence_v2).

Pure documentation + helpers. Matching thresholds live in ``rp_triggers`` and
are not altered here. This module exists so the pack, docs and tests share one
precise explanation of how matched houses and min coverage are computed.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional


def min_houses_required(n_houses: int) -> int:
    """ceil(n/2), minimum 1 — the v2 coverage threshold."""
    return max(1, math.ceil(n_houses / 2.0))


def matched_houses_for_planets(
    planets: Iterable[str],
    strength_map: dict,
    primary_houses: Iterable[int],
    max_level: int = 2,
) -> list[int]:
    """
    OR-union of primary houses each planet signifies at level ≤ max_level.

    A house H is matched if **any** planet in ``planets`` has
    strength_map[planet][H].level ≤ max_level. There is no AND across planets
    and no requirement that every primary house appear.
    """
    wanted = set(primary_houses)
    out: set[int] = set()
    for p in planets:
        for h, info in strength_map.get(p, {}).items():
            if h in wanted and info["level"] <= max_level:
                out.add(h)
    return sorted(out)


def coverage_ok(matched: Iterable[int], primary_houses: Iterable[int]) -> bool:
    houses = list(primary_houses)
    return len(list(matched)) >= min_houses_required(len(houses))


# Precise examples used in pack criteria + docs (methodology illustration only).
COVERAGE_EXAMPLES = {
    "career": {
        "primary_houses": [6, 10, 11],
        "n": 3,
        "min_required": 2,
        "example_pass": [6, 11],
        "example_fail": [11],
        "note": "ceil(3/2)=2. Matching any two of {6,10,11} passes.",
    },
    "promotion": {
        "primary_houses": [2, 6, 10, 11],
        "n": 4,
        "min_required": 2,
        "example_pass": [6, 11],
        "example_fail": [6],
        "note": (
            "ceil(4/2)=2. Matching {6,11} — the career core — passes promotion "
            "without house 2 or 10. Nested with career; not more selective."
        ),
    },
    "wealth": {
        "primary_houses": [2, 6, 10, 11],
        "n": 4,
        "min_required": 2,
        "example_pass": [6, 11],
        "example_fail": [2],
        "note": (
            "Identical primary set to promotion. Under house-only matching, "
            "wealth and promotion cannot diverge."
        ),
    },
    "relationship": {
        "primary_houses": [5, 7, 11],
        "n": 3,
        "min_required": 2,
        "example_pass": [5, 11],
        "example_fail": [5],
        "note": "ceil(3/2)=2. A single house (e.g. only 5) fails relationship.",
    },
    "children": {
        "primary_houses": [5, 11],
        "n": 2,
        "min_required": 1,
        "example_pass": [5],
        "example_fail": [],
        "note": (
            "ceil(2/2)=1. Matching only house 5 (or only 11) passes children "
            "but fails relationship (needs 2 of {5,7,11})."
        ),
    },
}


COVERAGE_SEMANTICS = {
    "rule_id": "half_primary_houses_v2",
    "formula": "min_required = max(1, ceil(len(primary_houses) / 2))",
    "matched_houses": (
        "OR-union: a primary house is matched if any window RP planet "
        "(day lord, asc sign/star/sub, Moon sign/star/sub) that already "
        "cleared the L1–L2 planet filter signifies that house at L1 or L2."
    ),
    "application": (
        "After planet-level RP checks pass, len(matched_houses) must be "
        ">= min_required. Failed intervals get HOUSE_COVERAGE_INSUFFICIENT."
    ),
    "or_matching_implication": (
        "Related/nested topics can share activation windows whenever the "
        "matched house set satisfies each topic's own min_required. "
        "Identical primary house sets (promotion ≡ wealth) always share "
        "activations. Nested sets (career ⊂ promotion; children ⊂ relationship) "
        "share whenever the smaller topic's matched houses also meet the "
        "larger topic's threshold — e.g. {6,11} meets both career (need 2/3) "
        "and promotion (need 2/4)."
    ),
    "selectivity_assessment": (
        "Half-coverage is intentionally permissive. It is NOT sufficiently "
        "selective to separate promotion from career when matched houses are "
        "only the career core, nor to separate promotion from wealth at all. "
        "A stricter topic-sensitive rule (e.g. requiring a topic-unique house, "
        "or majority > half for even-sized sets) would change activation "
        "counts and is a methodology change — not applied in v2.5."
    ),
    "methodology_justification": (
        "Changing coverage to force topic uniqueness would be a new KP "
        "convention, not a fix for a calculation bug. EVENT_HOUSES already "
        "encode topic identity; when two topics share the same list, house-"
        "only RP filters cannot invent a difference. Nested topics sharing "
        "windows is expected under OR + half-coverage. Documented as a "
        "limitation; thresholds remain rp_convergence_v2."
    ),
    "examples": COVERAGE_EXAMPLES,
}


def classify_activation_scope(
    topic: str,
    matched_houses: Iterable[int],
    primary_houses: Iterable[int],
    house_set_relations: dict,
) -> dict:
    """
    Explain whether an accepted window is distinctive for this topic or
    shared with identical / nested peers (audit only — does not reject).
    """
    matched = sorted(matched_houses)
    primary = list(primary_houses)
    identical = list(house_set_relations.get("identical_house_set_with") or [])
    subsets = list(house_set_relations.get("has_subsets") or [])
    subset_of = list(house_set_relations.get("subset_of") or [])

    unique_vs_subsets: list[int] = []
    if subsets:
        # Houses in this topic that no listed proper-subset topic owns alone
        # — approximated as primary minus intersection of all subset house sets
        # (caller may pass only relation metadata; unique = primary for now
        # unless we know subset house lists).
        unique_vs_subsets = sorted(set(primary) - set(matched))  # placeholder overwritten below

    # Prefer explicit unique houses: primary houses not in ANY proper subset's set
    # Relations dict does not embed subset house lists; use matched ∩ primary
    # and flag shared_nested when matched ⊆ union of known nested cores.
    scope = "topic_ok"
    if identical:
        scope = "identical_peer_expected"
    elif subset_of:
        # This topic is nested inside a larger one — windows often also activate parent
        scope = "nested_subset_of_larger_topic"
    elif subsets:
        # Larger topic: if matched houses look like a subset-only hit, flag it
        # Career core for promotion/wealth is {6,10,11}; if 2 not matched → shared
        # We detect "no house outside the largest proper subset" when matched
        # does not include any house that appears only in this topic.
        # Without subset house lists here, use: if topic has identical empty and
        # has_subsets, and matched has fewer than min for "distinctive" heuristic:
        scope = "may_share_with_nested_subsets"

    # Refine for known EVENT_HOUSES nesting without importing cycles at call sites
    KNOWN_UNIQUE = {
        "promotion": {2},
        "wealth": {2},
        "relationship": {7},
        "business": {7},
        "career": set(),
        "children": set(),
    }
    unique_needed = KNOWN_UNIQUE.get(topic)
    if unique_needed is not None:
        hit_unique = sorted(set(matched) & unique_needed)
        unique_vs_subsets = hit_unique
        if identical:
            scope = "identical_peer_expected"
        elif unique_needed and not hit_unique and matched:
            scope = "shared_nested_subset_only"
        elif unique_needed and hit_unique:
            scope = "topic_distinctive_house_hit"
        elif not unique_needed:
            scope = "nested_subset_of_larger_topic" if subset_of else "topic_ok"

    return {
        "scope": scope,
        "matched_houses": matched,
        "topic_unique_houses_hit": unique_vs_subsets,
        "identical_peers": identical,
        "nested_subsets": subsets,
        "subset_of": subset_of,
    }


def explain_children_vs_relationship(
    matched_houses: Iterable[int],
) -> Optional[str]:
    """Why an interval can pass children but fail relationship (or vice versa)."""
    m = set(matched_houses)
    child_matched = sorted(m & {5, 11})
    rel_matched = sorted(m & {5, 7, 11})
    child_pass = len(child_matched) >= min_houses_required(2)  # 1
    rel_pass = len(rel_matched) >= min_houses_required(3)  # 2
    if child_pass and not rel_pass:
        return (
            f"matched∩children={child_matched} meets children min_required=1; "
            f"matched∩relationship={rel_matched} fails relationship min_required=2 "
            f"(needs two of {{5,7,11}})."
        )
    if rel_pass and not child_pass:
        return (
            f"relationship matched {rel_matched} but children matched {child_matched} "
            f"— unexpected under nesting; check planet filters."
        )
    return None
