"""
Tarabala and Chandrashtama calculation engine.

Tarabala measures the relationship between the transit Moon nakshatra and
the natal Moon nakshatra, cycling through 9 categories of 3 nakshatras each.

Chandrashtama: Moon is in the 8th nakshatra from natal Moon nakshatra
(counted by sign group), indicating a period of emotional tension.

IMPORTANT: Tarabala is a supporting Vedic timing layer — it does NOT
override KP promise/denial. Use it as a qualitative suitability indicator.
"""
from __future__ import annotations

from analysis.kp_constants import NAKSHATRA_NAMES as NAKSHATRAS, SIGNS

TARA_CATEGORIES = [
    (1, "Janma",     "Birth — neutral, requires attention"),
    (2, "Sampat",    "Wealth — favorable"),
    (3, "Vipat",     "Danger — unfavorable"),
    (4, "Kshema",    "Well-being — favorable"),
    (5, "Pratyak",   "Obstacle — unfavorable"),
    (6, "Sadhana",   "Achievement — favorable"),
    (7, "Naidhana",  "Death/Loss — unfavorable"),
    (8, "Mitra",     "Friend — favorable"),
    (9, "Parama Mitra", "Best Friend — highly favorable"),
]


def _nak_index(nakshatra_name: str) -> int:
    """Return 0-based index of a nakshatra name."""
    try:
        return NAKSHATRAS.index(nakshatra_name)
    except ValueError:
        return 0


def compute_tarabala(natal_moon_nakshatra: str, transit_moon_nakshatra: str) -> dict:
    """
    Compute Tarabala for a given transit Moon nakshatra relative to natal Moon nakshatra.

    The distance is counted forward from the natal nakshatra (inclusive).
    The result cycles through 9 Tara categories of 3 nakshatras each.
    """
    natal_idx   = _nak_index(natal_moon_nakshatra)
    transit_idx = _nak_index(transit_moon_nakshatra)

    # Forward distance (1-based, inclusive)
    distance = ((transit_idx - natal_idx) % 27) + 1

    # Tara number: cycles through 9, each covering 3 nakshatras
    tara_num = ((distance - 1) % 9) + 1

    rec = TARA_CATEGORIES[tara_num - 1]
    favorable = tara_num in (2, 4, 6, 8, 9)

    return {
        "natal_moon_nakshatra":   natal_moon_nakshatra,
        "transit_moon_nakshatra": transit_moon_nakshatra,
        "distance":               distance,
        "tara_number":            tara_num,
        "tara_name":              rec[1],
        "tara_description":       rec[2],
        "tara_category":          f"{rec[1]} ({tara_num}) — {rec[2]}",
        "favorable":              favorable,
        "suitability":            "Favorable" if favorable else "Unfavorable" if tara_num in (3,5,7) else "Neutral",
    }


def compute_chandrashtama(natal_moon_sign: str, transit_moon_sign: str) -> bool:
    """
    Returns True if transit Moon is in Chandrashtama (8th sign from natal Moon sign).
    """
    natal_idx   = SIGNS.index(natal_moon_sign)   if natal_moon_sign   in SIGNS else 0
    transit_idx = SIGNS.index(transit_moon_sign) if transit_moon_sign in SIGNS else 0
    return ((transit_idx - natal_idx) % 12) == 7


def compute_tarabala_full(
    natal_moon_nakshatra: str,
    natal_moon_sign: str,
    transit_moon_nakshatra: str,
    transit_moon_sign: str,
) -> dict:
    """Combined Tarabala + Chandrashtama result."""
    tara = compute_tarabala(natal_moon_nakshatra, transit_moon_nakshatra)
    chandra = compute_chandrashtama(natal_moon_sign, transit_moon_sign)
    tara["chandrashtama"] = chandra
    if chandra:
        tara["suitability"] = "Unfavorable"
        tara["chandrashtama_note"] = "Moon in 8th from natal Moon sign — emotional/physical strain"
    else:
        tara["chandrashtama_note"] = ""
    return tara
