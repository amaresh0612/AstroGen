"""
Sidereal transit snapshot against the locked natal chart.

House basis (also exported as TRANSIT_HOUSE_BASIS for JSON consumers):
    transit_house       — natal Placidus cusp interval containing the transit
                          longitude (KP occupancy, same rule as natal planets)
    transit_house_sign  — whole-sign count from the natal Lagna sign
"""
from __future__ import annotations

import swisseph as swe

from analysis.cuspal_houses import get_cusp_longitudes, house_from_longitude, whole_sign_house
from analysis.kp_constants import SIGN_LORDS, nak_star_sub, sign_of

TRANSIT_PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE,
}

TRANSIT_HOUSE_BASIS = (
    "transit_house = natal Placidus cusp interval containing the transit longitude (KP); "
    "transit_house_sign = whole-sign count from the natal Lagna sign"
)


def sidereal_longitude(jd_ut: float, body: int) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    res, _ = swe.calc_ut(jd_ut, body, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return float(res[0]) % 360.0


def _entry(lon: float, cusps: list[float]) -> dict:
    sign = sign_of(lon)
    nak, star, sub = nak_star_sub(lon)
    return {
        "longitude": round(lon, 4),
        "sign": sign,
        "sign_lord": SIGN_LORDS[sign],
        "degree": f"{int(lon % 30)}\u00b0{int((lon % 1) * 60)}'",
        "nakshatra": nak,
        "star_lord": star,
        "sub_lord": sub,
        "transit_house": house_from_longitude(lon, cusps),
        "transit_house_sign": whole_sign_house(lon, cusps[0]),
    }


def transit_snapshot(jd_ut: float, natal_houses: dict) -> dict:
    """Planet → transit entry for Sun…Saturn, Rahu (true node) and Ketu."""
    cusps = get_cusp_longitudes(natal_houses)
    lons = {p: sidereal_longitude(jd_ut, pid) for p, pid in TRANSIT_PLANET_IDS.items()}
    lons["Ketu"] = (lons["Rahu"] + 180.0) % 360.0
    return {p: _entry(lon, cusps) for p, lon in lons.items()}
