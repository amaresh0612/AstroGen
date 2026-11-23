"""
One-time script to generate data/natal_ref.json from birth details.

Computes the KP natal chart independently using Swiss Ephemeris (Lahiri).
Does NOT import from app.py — safe to run from any terminal. Arithmetic
(sub-lords, cuspal occupancy, Vimshottari) comes from analysis/* modules that
tests/test_app_parity.py keeps identical to app.py.

Usage (from repo root, with venv active):
    python scripts/generate_natal_ref.py

You will be prompted for birth details. The output is saved to data/natal_ref.json
and should be treated as the locked source of truth thereafter.

IMPORTANT:
- Run this script ONCE per person.
- After generation, review the JSON and confirm values match your authoritative report.
- Never commit this file to git (it contains birth data / PII).
- data/natal_ref.json is already in .gitignore.
"""
from __future__ import annotations

import io
import json
import os
import sys
from datetime import date, datetime, time
from typing import Optional

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure repo root is importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytz
import swisseph as swe

from analysis.cuspal_houses import assign_cuspal_houses
from analysis.kp_constants import SIGN_LORDS, localize, nak_star_sub, sign_of
from analysis.nakshatra_utils import get_nakshatra_and_pada
from analysis.significator_strength import (
    KP_METHODOLOGY,
    _serialize_strength_map,
    build_natal_significator_block,
)
from analysis.vimshottari import lock_dasha, mahadasha_timeline

try:
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder
    _GEO_AVAILABLE = True
except ImportError:
    _GEO_AVAILABLE = False

PLANET_IDS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.TRUE_NODE,
}

# Numerology Chaldean table
CHALDEAN = {
    'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 8, 'g': 3, 'h': 5, 'i': 1, 'j': 1, 'k': 2,
    'l': 3, 'm': 4, 'n': 5, 'o': 7, 'p': 8, 'q': 1, 'r': 2, 's': 3, 't': 4, 'u': 6, 'v': 6,
    'w': 6, 'x': 5, 'y': 1, 'z': 7,
}


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _jd(dt_utc: datetime) -> float:
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0)


def _dms(lon: float) -> str:
    d = int(lon % 30)
    m = int((lon % 1) * 60)
    s = int(((lon % 1) * 60 % 1) * 60)
    return f"{d}°{m}'{s}\""


def _geocode(place: str) -> tuple[float, float, str]:
    """Return (lat, lng, tz_name). Falls back to prompt if geopy unavailable."""
    if _GEO_AVAILABLE:
        try:
            geo = Nominatim(user_agent="astrogen_natal").geocode(place, timeout=10)
            if geo:
                tz = TimezoneFinder().timezone_at(lat=geo.latitude, lng=geo.longitude)
                if tz:
                    return geo.latitude, geo.longitude, tz
        except Exception as e:
            print(f"  (geocode failed: {e} — please enter manually)")
    lat = float(input(f"  Latitude for {place}: "))
    lng = float(input(f"  Longitude for {place}: "))
    tz = input("  Timezone (e.g. Asia/Kolkata): ").strip()
    pytz.timezone(tz)
    return lat, lng, tz


def _numerology_reduce(n: int) -> int:
    while n > 9 and n not in (11, 22):
        n = sum(int(d) for d in str(n))
    return n


def _name_number(name: str) -> int:
    total = sum(CHALDEAN.get(c.lower(), 0) for c in name if c.isalpha())
    return _numerology_reduce(total)


def _life_path(dob: date) -> int:
    return _numerology_reduce(sum(int(c) for c in str(dob.year) + f"{dob.month:02d}" + f"{dob.day:02d}"))


def _point(lon: float) -> dict:
    sign = sign_of(lon)
    nak, star, sub = nak_star_sub(lon)
    return {
        "longitude": round(lon, 6),
        "sign": sign,
        "degree": _dms(lon),
        "nakshatra": nak,
        "pada": get_nakshatra_and_pada(lon)[3],
        "star_lord": star,
        "sub_lord": sub,
        "sign_lord": SIGN_LORDS[sign],
    }


# ---------------------------------------------------------------------------
# Pure builder (no I/O) — used by main() and tests
# ---------------------------------------------------------------------------

def build_natal_ref(
    name: str,
    dob: date,
    tob: time,
    place: str,
    lat: float,
    lng: float,
    tz_name: str,
    lock_dt: Optional[datetime] = None,
) -> dict:
    birth_local = datetime(dob.year, dob.month, dob.day, tob.hour, tob.minute, tob.second)
    utc_dt = localize(tz_name, birth_local).astimezone(pytz.utc).replace(tzinfo=None)
    jd_birth = _jd(utc_dt)

    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa_ut(jd_birth)

    # Placidus cusps (tropical) → sidereal
    cusps_trop, _ = swe.houses(jd_birth, lat, lng, b"P")
    cusps_sid = [(c - ayanamsa) % 360.0 for c in cusps_trop[:12]]

    # Natal planets = tropical − ayanamsa, as app._calc_planet_longitude_sidereal
    # (FLG_SIDEREAL differs by ~10″, enough to move dasha balance by a day).
    planets_out: dict = {}
    lons: dict[str, float] = {}
    for pname, pid in PLANET_IDS.items():
        res, _ = swe.calc_ut(jd_birth, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)
        lons[pname] = (float(res[0]) - ayanamsa) % 360.0
        planets_out[pname] = {
            **_point(lons[pname]),
            "house": 0,
            "retrograde": pname == "Rahu" or float(res[3]) < 0,
        }
    lons["Ketu"] = (lons["Rahu"] + 180.0) % 360.0
    planets_out["Ketu"] = {**_point(lons["Ketu"]), "house": 0, "retrograde": True}

    houses_out: dict = {}
    for i, lon in enumerate(cusps_sid, 1):
        p = _point(lon)
        houses_out[str(i)] = {
            "cusp_degree": p["longitude"], "sign": p["sign"], "degree": p["degree"],
            "nakshatra": p["nakshatra"], "star_lord": p["star_lord"], "sub_lord": p["sub_lord"],
        }
    cuspal_sublords = {h: d["sub_lord"] for h, d in houses_out.items()}

    planets_out = assign_cuspal_houses(planets_out, houses_out, include_whole_sign=True)
    significators, strength_map = build_natal_significator_block(planets_out, houses_out)

    # Dasha seeded from LOCAL birth wall time, exactly as app.py does
    timeline = mahadasha_timeline(lons["Moon"], birth_local)
    dasha = lock_dasha(timeline, lock_dt or datetime.now())

    return {
        "_meta": {
            "source_report": f"Generated by scripts/generate_natal_ref.py on {date.today().isoformat()}",
            "generated_date": date.today().isoformat(),
            "version": "1.1",
        },
        "birth": {
            "name":     name,
            "date":     dob.isoformat(),
            "time":     tob.strftime("%H:%M:%S"),
            "place":    place,
            "lat":      round(lat, 6),
            "lng":      round(lng, 6),
            "tz":       tz_name,
            "ayanamsa": round(ayanamsa, 6),
        },
        "planets":             planets_out,
        "houses":              houses_out,
        "cuspal_sublords":     cuspal_sublords,
        "significators":       significators,
        "significator_matrix": _serialize_strength_map(strength_map),
        "kp_methodology":      KP_METHODOLOGY,
        "dasha":               dasha,
        "numerology": {
            "name_number": _name_number(name),
            "life_path":   _life_path(dob),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _prompt(label: str, default: str = "") -> str:
    if default:
        val = input(f"  {label} [{default}]: ").strip()
        return val or default
    return input(f"  {label}: ").strip()


def main() -> None:
    print("\n╔══════════════════════════════════════════════╗")
    print("║  AstroGen — Generate Locked Natal Reference  ║")
    print("╚══════════════════════════════════════════════╝\n")

    name  = _prompt("Full name")
    dob_s = _prompt("Date of birth (YYYY-MM-DD)")
    tob_s = _prompt("Time of birth (HH:MM or HH:MM:SS, 24h)")
    place = _prompt("Place of birth (City, Country)")

    try:
        dob   = date.fromisoformat(dob_s)
        parts = tob_s.split(":")
        tob   = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    except ValueError as e:
        print(f"\nERROR parsing date/time: {e}")
        sys.exit(1)

    print(f"\n  Looking up coordinates for: {place}")
    lat, lng, tz_name = _geocode(place)
    print(f"  → {lat:.4f}°, {lng:.4f}°  |  {tz_name}")

    print("\n  Calculating chart...")
    natal_ref = build_natal_ref(name, dob, tob, place, lat, lng, tz_name)

    out_path = os.path.join(_ROOT, "data", "natal_ref.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(natal_ref, f, indent=2, ensure_ascii=False)

    d = natal_ref["dasha"]
    print(f"\n✓ Saved to {out_path}")
    print(f"  Name:        {name}")
    print(f"  Birth:       {dob.isoformat()} {tob.strftime('%H:%M:%S')} local | {place}")
    print(f"  Ayanamsa:    {natal_ref['birth']['ayanamsa']:.4f}° (Lahiri)")
    print(f"  Lagna:       {natal_ref['houses']['1']['sign']} {natal_ref['houses']['1']['degree']}")
    print(f"  Lagna CSL:   {natal_ref['cuspal_sublords'].get('1', '?')}")
    print(f"  10th CSL:    {natal_ref['cuspal_sublords'].get('10', '?')}")
    for lvl in ("md", "ad", "pd"):
        p = d[f"locked_{lvl}"]
        print(f"  Active {lvl.upper()}:   {p.get('lord', '?')} ({p.get('start', '?')} → {p.get('end', '?')})")
    print(f"  Locked PD rows: {len(d['locked_periods'])}")
    print(f"  Name Number: {natal_ref['numerology']['name_number']}")
    print(f"  Life Path:   {natal_ref['numerology']['life_path']}")
    print("\n  Review the file and verify against your authoritative KP report.")
    print("  NEVER commit data/natal_ref.json to git.\n")


if __name__ == "__main__":
    main()
