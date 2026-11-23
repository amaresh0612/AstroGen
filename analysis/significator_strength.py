"""
KP Significator Strength Classification Engine.

Classical KP four-fold significators, strongest first. For planet P whose
star (nakshatra) lord is S:

    Level 1 (In Star of Occupant):  S occupies the house.
    Level 2 (Occupant):             P occupies the house (cuspal Placidus interval).
    Level 3 (In Star of Owner):     S owns the sign on the house cusp.
    Level 4 (Owner):                P owns the sign on the house cusp.

Rahu / Ketu act as agents: besides their own L1–L4 links they carry the
significations of their sign lord and of planets in the same sign, at the
level those planets hold. A planet in the star of a node therefore also
receives the node's agency houses (L1 for houses the agents occupy, L3 for
houses they own).

IMPORTANT: These are qualitative levels — no numeric scores are produced.
"""
from __future__ import annotations

from analysis.cuspal_houses import assign_cuspal_houses
from analysis.kp_constants import SIGN_LORDS

PLANETS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]
NODES = ("Rahu", "Ketu")
LEVEL_LABELS = {
    1: "In Star of Occupant",
    2: "Occupant",
    3: "In Star of Owner",
    4: "Owner",
}


def _house_owners(houses: dict) -> dict[int, str]:
    owners: dict[int, str] = {}
    for h_str, hdata in houses.items():
        try:
            h = int(h_str)
        except ValueError:
            continue
        owner = SIGN_LORDS.get(hdata.get("sign", ""), "")
        if owner:
            owners[h] = owner
    return owners


def _node_agents(node: str, planets: dict) -> list[str]:
    """Planets a node represents: its sign lord, then planets in the same sign."""
    ndata = planets.get(node, {})
    agents: list[str] = []
    sign_lord = ndata.get("sign_lord") or SIGN_LORDS.get(ndata.get("sign", ""), "")
    if sign_lord and sign_lord not in NODES:
        agents.append(sign_lord)
    for q in PLANETS:
        if q in NODES or q in agents:
            continue
        if ndata.get("sign") and planets.get(q, {}).get("sign") == ndata.get("sign"):
            agents.append(q)
    return agents


def compute_significator_strength(
    planets: dict,
    houses: dict,
) -> dict:
    """
    Compute classical KP Level 1–4 significators for all planets across 12 houses.

    Parameters
    ----------
    planets : dict from natal_ref.json 'planets'
        Each entry has: house (int, cuspal), longitude, nakshatra, star_lord, sign, sign_lord
    houses  : dict from natal_ref.json 'houses'
        Keys "1"–"12", each with: cusp_degree, sign, star_lord, sub_lord

    Returns
    -------
    dict: planet_name → {
        house_n: {"level": int, "level_label": str, "reasons": list[str]}
        ...  (only houses where a level 1–4 connection exists)
    }
    """
    owners = _house_owners(houses)
    owned_by = {p: sorted(h for h, o in owners.items() if o == p) for p in PLANETS}

    def occupied(p: str) -> int | None:
        h = planets.get(p, {}).get("house")
        return h if isinstance(h, int) and 1 <= h <= 12 else None

    # Houses each planet "holds" for its star-dependants: occupation and ownership.
    # For nodes, agency adds the agents' occupation/ownership.
    held_occ: dict[str, list[tuple[int, str]]] = {}
    held_own: dict[str, list[tuple[int, str]]] = {}
    for p in PLANETS:
        occ = [(occupied(p), p)] if occupied(p) else []
        own = [(h, p) for h in owned_by[p]]
        if p in NODES:
            for a in _node_agents(p, planets):
                if occupied(a):
                    occ.append((occupied(a), a))
                own.extend((h, a) for h in owned_by[a])
        held_occ[p], held_own[p] = occ, own

    result: dict[str, dict] = {p: {} for p in PLANETS}

    def add(p: str, h: int, level: int, reason: str) -> None:
        cur = result[p].get(h)
        if cur is None or level < cur["level"]:
            result[p][h] = {"level": level, "level_label": LEVEL_LABELS[level], "reasons": [reason]}
        elif level == cur["level"] and reason not in cur["reasons"]:
            cur["reasons"].append(reason)

    for p in PLANETS:
        star = planets.get(p, {}).get("star_lord", "")
        if star in held_occ:
            for h, via in held_occ[star]:
                tail = "" if via == star else f" (agent of {via} in H{h})"
                add(p, h, 1, f"In star of {star}, occupant of H{h}{tail}")
        if occupied(p):
            add(p, occupied(p), 2, f"Occupies H{occupied(p)}")
        if star in held_own:
            for h, via in held_own[star]:
                tail = "" if via == star else f" (agent of {via}, owner of H{h})"
                add(p, h, 3, f"In star of {star}, owner of H{h}{tail}")
        for h in owned_by[p]:
            add(p, h, 4, f"Owns H{h}")

    # Node agency: a node also signifies whatever its agents signify, at their level.
    for node in NODES:
        for a in _node_agents(node, planets):
            for h, info in list(result[a].items()):
                add(node, h, info["level"], f"Agent of {a}: {info['reasons'][0]}")

    return result


def get_planet_signification_summary(strength_map: dict) -> dict:
    """
    Returns a flat summary: planet → sorted list of (house, level) tuples.
    Useful for AI context injection.
    """
    summary: dict[str, list[dict]] = {}
    for pname, houses in strength_map.items():
        entries = sorted(
            [{"house": h, "level": v["level"], "label": v["level_label"]}
             for h, v in houses.items()],
            key=lambda x: (x["level"], x["house"]),
        )
        summary[pname] = entries
    return summary


def get_strong_significators_for_houses(
    strength_map: dict,
    target_houses: list[int],
    max_level: int = 3,
) -> dict[str, int]:
    """
    Return planets that signify any of target_houses at level ≤ max_level.
    Returns: {planet: best_level}
    """
    result: dict[str, int] = {}
    for pname, houses in strength_map.items():
        for h, info in houses.items():
            if h in target_houses and info["level"] <= max_level:
                existing = result.get(pname)
                if existing is None or info["level"] < existing:
                    result[pname] = info["level"]
    return dict(sorted(result.items(), key=lambda x: x[1]))


def _serialize_strength_map(strength_map: dict) -> dict:
    """JSON-safe strength map (house keys as strings)."""
    out: dict = {}
    for pname, houses in strength_map.items():
        out[pname] = {
            str(h): {
                "level":       info["level"],
                "level_label": info["level_label"],
                "reasons":     info["reasons"],
            }
            for h, info in houses.items()
        }
    return out


def _deserialize_strength_map(data: dict) -> dict:
    """Restore strength map from natal_ref storage."""
    out: dict = {}
    for pname, houses in data.items():
        out[pname] = {
            int(h): {
                "level":       info["level"],
                "level_label": info["level_label"],
                "reasons":     info["reasons"],
            }
            for h, info in houses.items()
        }
    return out


def significators_are_current(natal_ref: dict) -> bool:
    """True when the stored significators were built with this engine's method."""
    method = (natal_ref.get("kp_methodology") or {}).get("version")
    return (method == KP_METHODOLOGY["version"]
            and bool(natal_ref.get("significator_matrix"))
            and bool(natal_ref.get("significators")))


def natal_significators(natal_ref: dict) -> tuple[dict, dict]:
    """
    (significators, strength_map) for a natal reference.

    Stored values are used only when built with the current method; otherwise
    they are recomputed in memory from the locked planets/cusps (nothing is
    written back — the natal file stays immutable).
    """
    if significators_are_current(natal_ref):
        return natal_ref["significators"], _deserialize_strength_map(natal_ref["significator_matrix"])
    return build_natal_significator_block(
        natal_ref.get("planets", {}),
        natal_ref.get("houses", {}),
    )


def compute_significator_strength_from_natal(natal_ref: dict) -> dict:
    """Canonical strength map for a natal reference (see natal_significators)."""
    return natal_significators(natal_ref)[1]


def build_natal_significator_block(
    planets: dict,
    houses: dict,
) -> tuple[dict, dict]:
    """
    Build canonical natal significators + strength matrix from chart data.

    This is the ONLY derivation path for signified_houses in natal.json.
    Planet occupancy is always re-derived from cusp intervals before L1–L4.
    """
    planets_cuspal = assign_cuspal_houses(planets, houses, include_whole_sign=False)
    strength_map = compute_significator_strength(planets_cuspal, houses)

    house_owners: dict[int, str] = {}
    for h_str, hdata in houses.items():
        try:
            h = int(h_str)
        except ValueError:
            continue
        owner = SIGN_LORDS.get(hdata.get("sign", ""), "")
        if owner:
            house_owners[h] = owner

    significators: dict = {}
    for pname in PLANETS:
        pdata = planets_cuspal.get(pname, {})
        house_map = strength_map.get(pname, {})
        owned = sorted(h for h, owner in house_owners.items() if owner == pname)
        all_houses = sorted(house_map.keys())
        l1_l3 = sorted(h for h, info in house_map.items() if info["level"] <= 3)

        significators[pname] = {
            "occupied_house":       pdata.get("house"),
            "owned_houses":         owned,
            "signified_houses":     all_houses,
            "signified_houses_l1_l3": l1_l3,
            "connections": {
                str(h): {
                    "level":       info["level"],
                    "level_label": info["level_label"],
                }
                for h, info in house_map.items()
            },
        }

    return significators, strength_map


APP_HOUSE_KEYS = ["1st (Lagna)", "2nd", "3rd", "4th", "5th", "6th",
                  "7th", "8th", "9th", "10th", "11th", "12th"]


def significators_from_app_chart(chart_result: dict) -> dict:
    """
    Significators for an app.py `calculate_comprehensive_chart` result.

    Same engine as natal_ref (cuspal occupancy, classical levels, node agency).
    Returns planet → {occupied_house, owned_houses, signified_houses, ...}.
    """
    planets_raw = chart_result.get("planets", {}) or {}
    houses_raw = chart_result.get("houses", {}) or {}
    planets = {
        p: {
            "longitude": float(d.get("full_degree", 0.0)) % 360.0,
            "sign": d.get("sign", ""),
            "sign_lord": SIGN_LORDS.get(d.get("sign", ""), ""),
            "star_lord": d.get("nakshatra_lord", ""),
        }
        for p, d in planets_raw.items() if p in PLANETS
    }
    houses = {
        str(i): {
            "cusp_degree": float((houses_raw.get(key) or {}).get("cusp_degree", 0.0)) % 360.0,
            "sign": (houses_raw.get(key) or {}).get("sign", ""),
        }
        for i, key in enumerate(APP_HOUSE_KEYS, 1)
    }
    return build_natal_significator_block(planets, houses)[0]


KP_METHODOLOGY = {
    "significator_engine": "analysis.significator_strength.compute_significator_strength",
    "occupancy_method": "cuspal_placidus_interval",
    "occupancy_note": (
        "Planet house = sidereal longitude within consecutive cusp boundaries. "
        "NOT whole-sign. Whole-sign may be stored separately as house_whole_sign."
    ),
    "levels": {
        "1": "Planet in the star of an occupant of the house",
        "2": "Occupant of the house (cuspal interval)",
        "3": "Planet in the star of the house owner",
        "4": "Owner of the sign on the house cusp",
    },
    "node_agency": (
        "Rahu/Ketu also signify what their sign lord and same-sign planets signify; "
        "planets in a node's star inherit the agents' occupied (L1) and owned (L3) houses."
    ),
    "signified_houses": "All houses with any L1–L4 connection (matches PDF matrix)",
    "signified_houses_l1_l3": "L1–L3 only — strong significators (Sig Quality layer)",
    "version": "2.0",
}
