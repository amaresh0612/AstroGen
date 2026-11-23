"""
KP cuspal house occupancy — Placidus cusp intervals (NOT whole-sign).

Planets are assigned to the house whose cusp interval contains their
sidereal longitude. This is the sole occupancy model for the KP
significator engine.
"""
from __future__ import annotations

from typing import Optional


def get_cusp_longitudes(houses: dict) -> list[float]:
    """
    Return [H1_cusp … H12_cusp] sidereal longitudes from natal houses dict.

    Keys may be int or str "1"–"12".
    """
    cusps: list[float] = []
    for h in range(1, 13):
        hdata = houses.get(str(h)) or houses.get(h) or {}
        cusps.append(float(hdata.get("cusp_degree", 0.0)) % 360.0)
    return cusps


def house_from_longitude(lon: float, cusps: list[float]) -> int:
    """
    Assign natal house (1–12) from sidereal longitude and cusp list.

    House H spans [cusp_H, cusp_{H+1}) with H12 wrapping through 0°.
    Raises ValueError for cusp lists that don't partition the zodiac.
    """
    if len(cusps) != 12:
        raise ValueError(f"Expected 12 cusps, got {len(cusps)}")
    if len({round(float(c) % 360.0, 9) for c in cusps}) != 12:
        raise ValueError("Cusps are missing or duplicated — natal houses incomplete")

    lon = float(lon) % 360.0

    for h in range(1, 13):
        start = cusps[h - 1] % 360.0
        end = cusps[h % 12] % 360.0

        if start <= end:
            if start <= lon < end:
                return h
        else:
            # Interval wraps through 360° (typically H12)
            if lon >= start or lon < end:
                return h

    raise ValueError(f"Longitude {lon:.6f}° not inside any cusp interval — cusps not in zodiac order")


def whole_sign_house(lon: float, asc_lon: float) -> int:
    """Whole-sign house — Vedic reference only; NOT used for KP significators."""
    asc_sign_idx = int(float(asc_lon) / 30) % 12
    p_sign_idx = int(float(lon) / 30) % 12
    return ((p_sign_idx - asc_sign_idx) % 12) + 1


def assign_cuspal_houses(
    planets: dict,
    houses: dict,
    *,
    include_whole_sign: bool = True,
) -> dict:
    """
    Return planets dict with corrected ``house`` (cuspal) per planet.

    Optionally adds ``house_whole_sign`` for a separate Vedic layer.
    """
    cusps = get_cusp_longitudes(houses)
    asc_lon = cusps[0] if cusps else 0.0
    out: dict = {}

    for pname, pdata in planets.items():
        p = dict(pdata)
        lon = p.get("longitude")
        if lon is not None:
            p["house"] = house_from_longitude(float(lon), cusps)
            if include_whole_sign:
                p["house_whole_sign"] = whole_sign_house(float(lon), asc_lon)
        out[pname] = p

    return out


def validate_cuspal_occupancy(
    planets: dict,
    houses: dict,
) -> list[str]:
    """
    Verify each planet's stored ``house`` matches cusp-interval assignment.

    Returns human-readable issue strings (empty = pass).
    """
    if not planets or not houses:
        return ["Missing planets or houses for occupancy validation"]

    cusps = get_cusp_longitudes(houses)
    issues: list[str] = []

    for pname, pdata in planets.items():
        lon = pdata.get("longitude")
        stored = pdata.get("house")
        if lon is None or stored is None:
            continue
        try:
            expected = house_from_longitude(float(lon), cusps)
        except ValueError as exc:
            return [f"Cusp data invalid: {exc}"]
        if int(stored) != expected:
            issues.append(
                f"{pname} occupancy: stored H{stored}, cusp interval expects H{expected} "
                f"(lon={float(lon):.6f}°, H{expected} cusp={cusps[expected - 1]:.6f}°, "
                f"H{expected % 12 + 1} cusp={cusps[expected % 12]:.6f}°)"
            )

    return issues
