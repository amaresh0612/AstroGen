"""
KP Significator Strength Classification Engine.

Classifies each planet's connection to each house at Level 1–4:

    Level 1 (Direct Occupant):
        Planet physically occupies the house (cuspal Placidus interval).
        Strongest — planet carries the full vibration of that house.

    Level 2 (Star-Lord Link):
        Planet is the nakshatra lord (star lord) of a planet that occupies a house.
        Strong indirect link through the star-lord chain.

    Level 3 (Sign Owner):
        Planet owns the sign on the cusp of the house (sign lordship).
        Standard significator role.

    Level 4 (Indirect / Star of Owner):
        Planet is the star lord of a planet that OWNS the house.
        Weakest but still relevant for supporting analysis.

IMPORTANT: These are qualitative levels — no numeric scores are produced.
"""
from __future__ import annotations

from analysis.cuspal_houses import assign_cuspal_houses

PLANETS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]
SIGN_LORDS = {
    "Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon",
    "Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars",
    "Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter",
}
LEVEL_LABELS = {
    1: "Direct Occupant",
    2: "Star-Lord Link",
    3: "Sign Owner",
    4: "Indirect (Star of Owner)",
}


def compute_significator_strength(
    planets: dict,
    houses: dict,
) -> dict:
    """
    Compute Level 1–4 significator strength for all planets across all 12 houses.

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
    # Build occupancy map: house_num → list of planets in that house
    occupants: dict[int, list[str]] = {h: [] for h in range(1, 13)}
    for pname, pdata in planets.items():
        h = pdata.get("house")
        if isinstance(h, int) and 1 <= h <= 12:
            occupants[h].append(pname)

    # Build house ownership: house_num → sign lord
    house_owners: dict[int, str] = {}
    for h_str, hdata in houses.items():
        try:
            h = int(h_str)
        except ValueError:
            continue
        sign = hdata.get("sign", "")
        owner = SIGN_LORDS.get(sign, "")
        if owner:
            house_owners[h] = owner

    result: dict[str, dict] = {p: {} for p in PLANETS}

    for house_num in range(1, 13):
        owner = house_owners.get(house_num, "")

        for pname in PLANETS:
            pdata = planets.get(pname, {})
            star_lord = pdata.get("star_lord", "")
            reasons: list[str] = []
            best_level: int | None = None

            # Level 1: planet occupies this house
            if pdata.get("house") == house_num:
                best_level = 1
                reasons.append(f"Occupies house {house_num}")

            # Level 2: planet is star lord of an occupant of this house
            if best_level != 1:
                for occ in occupants.get(house_num, []):
                    if planets.get(occ, {}).get("star_lord") == pname:
                        best_level = 2
                        reasons.append(f"Star lord of {occ} in house {house_num}")
                        break

            # Level 3: planet owns this house
            if best_level is None and owner == pname:
                best_level = 3
                reasons.append(f"Sign owner of house {house_num}")

            # Level 4: planet is star lord of the house owner
            if best_level is None and owner:
                owner_data = planets.get(owner, {})
                if owner_data.get("star_lord") == pname:
                    best_level = 4
                    reasons.append(f"Star lord of {owner} (owner of house {house_num})")

            if best_level is not None:
                result[pname][house_num] = {
                    "level":       best_level,
                    "level_label": LEVEL_LABELS[best_level],
                    "reasons":     reasons,
                }

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


def compute_significator_strength_from_natal(natal_ref: dict) -> dict:
    """
    Canonical strength map for a natal reference.

    Uses locked significator_matrix when present; otherwise computes from
    planets/houses and writes nothing back (caller must persist if needed).
    """
    stored = natal_ref.get("significator_matrix")
    if stored:
        return _deserialize_strength_map(stored)
    return compute_significator_strength(
        natal_ref.get("planets", {}),
        natal_ref.get("houses", {}),
    )


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


KP_METHODOLOGY = {
    "significator_engine": "analysis.significator_strength.compute_significator_strength",
    "occupancy_method": "cuspal_placidus_interval",
    "occupancy_note": (
        "Planet house = sidereal longitude within consecutive cusp boundaries. "
        "NOT whole-sign. Whole-sign may be stored separately as house_whole_sign."
    ),
    "levels": {
        "1": "Direct occupant (cuspal house interval)",
        "2": "Star lord of a planet occupying the house",
        "3": "Sign owner of the house cusp",
        "4": "Star lord of the sign owner",
    },
    "signified_houses": "All houses with any L1–L4 connection (matches PDF matrix)",
    "signified_houses_l1_l3": "L1–L3 only — used for primary event activation analysis",
    "version": "1.0",
}
