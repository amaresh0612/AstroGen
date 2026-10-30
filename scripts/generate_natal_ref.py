"""
One-time script to generate data/natal_ref.json from birth details.

Computes the KP natal chart independently using Swiss Ephemeris (Lahiri).
Does NOT import from app.py — safe to run from any terminal.

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

import sys, os, json, math, io
from datetime import date, time, datetime, timedelta
from typing import Optional

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ensure repo root is importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from analysis.significator_strength import (
    build_natal_significator_block,
    _serialize_strength_map,
    KP_METHODOLOGY,
)

import swisseph as swe
import pytz
try:
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder
    _GEO_AVAILABLE = True
except ImportError:
    _GEO_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
         "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
SIGN_LORDS = {
    "Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon",
    "Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars",
    "Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter",
}
NAKSHATRAS = [
    ("Ashwini","Ketu"),("Bharani","Venus"),("Krittika","Sun"),
    ("Rohini","Moon"),("Mrigashira","Mars"),("Ardra","Rahu"),
    ("Punarvasu","Jupiter"),("Pushya","Saturn"),("Ashlesha","Mercury"),
    ("Magha","Ketu"),("Purva Phalguni","Venus"),("Uttara Phalguni","Sun"),
    ("Hasta","Moon"),("Chitra","Mars"),("Swati","Rahu"),
    ("Vishakha","Jupiter"),("Anuradha","Saturn"),("Jyeshtha","Mercury"),
    ("Mula","Ketu"),("Purva Ashadha","Venus"),("Uttara Ashadha","Sun"),
    ("Shravana","Moon"),("Dhanishta","Mars"),("Shatabhisha","Rahu"),
    ("Purva Bhadrapada","Jupiter"),("Uttara Bhadrapada","Saturn"),("Revati","Mercury"),
]
VIMSH_ORDER = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
VIMSH_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]
TOTAL_YEARS = sum(VIMSH_YEARS)  # 120
PLANET_IDS  = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS, "Saturn": swe.SATURN,
    "Rahu": swe.TRUE_NODE,
}
NAK_WIDTH = 360.0 / 27.0

# Numerology Chaldean table
CHALDEAN = {
    'a':1,'b':2,'c':3,'d':4,'e':5,'f':8,'g':3,'h':5,'i':1,'j':1,'k':2,
    'l':3,'m':4,'n':5,'o':7,'p':8,'q':1,'r':2,'s':3,'t':4,'u':6,'v':6,
    'w':6,'x':5,'y':1,'z':7,
}

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _jd(dt_utc: datetime) -> float:
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute/60.0 + dt_utc.second/3600.0)


def _sid_lon(jd: float, body: int) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    res, _ = swe.calc_ut(jd, body, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return float(res[0]) % 360.0


def _nak_star_sub(lon: float) -> tuple[str, str, str]:
    idx = int(lon / NAK_WIDTH) % 27
    name, star = NAKSHATRAS[idx]
    offset_min = (lon % NAK_WIDTH) * 60.0
    nak_min    = NAK_WIDTH * 60.0
    s_idx = VIMSH_ORDER.index(star)
    cum, sub = 0.0, star
    for i in range(9):
        j = (s_idx + i) % 9
        sub_min = (VIMSH_YEARS[j] / TOTAL_YEARS) * nak_min
        cum += sub_min
        if offset_min <= cum:
            sub = VIMSH_ORDER[j]
            break
    return name, star, sub


def _pada(lon: float) -> int:
    return int((lon % NAK_WIDTH) / (NAK_WIDTH / 4)) + 1


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
                tf = TimezoneFinder()
                tz = tf.timezone_at(lat=geo.latitude, lng=geo.longitude) or "Asia/Kolkata"
                return geo.latitude, geo.longitude, tz
        except Exception as e:
            print(f"  (geocode failed: {e} — please enter manually)")
    lat  = float(input(f"  Latitude for {place}: "))
    lng  = float(input(f"  Longitude for {place}: "))
    tz   = input(f"  Timezone (e.g. Asia/Kolkata): ").strip() or "Asia/Kolkata"
    return lat, lng, tz


def _local_to_utc(dob: date, tob: time, tz_name: str) -> datetime:
    tz = pytz.timezone(tz_name)
    local = tz.localize(datetime(dob.year, dob.month, dob.day, tob.hour, tob.minute, tob.second))
    return local.astimezone(pytz.utc).replace(tzinfo=None)


def _cuspal_sublords(cusps_sid: list[float]) -> dict[str, str]:
    result = {}
    for i, lon in enumerate(cusps_sid[:12], 1):
        _, _, sub = _nak_star_sub(lon)
        result[str(i)] = sub
    return result


def _vimsh_dashas(moon_lon: float, birth_utc: datetime) -> list[dict]:
    """Calculate full Vimshottari MD timeline from Moon longitude and birth datetime."""
    nak_idx   = int(moon_lon / NAK_WIDTH) % 27
    nak_name, start_lord = NAKSHATRAS[nak_idx]
    elapsed   = (moon_lon % NAK_WIDTH) / NAK_WIDTH  # fraction elapsed in nak
    s_idx     = VIMSH_ORDER.index(start_lord)

    # First dasha: remaining portion
    first_years = VIMSH_YEARS[s_idx] * (1 - elapsed)
    periods = []
    cur = birth_utc
    for i in range(9):
        idx   = (s_idx + i) % 9
        lord  = VIMSH_ORDER[idx]
        years = first_years if i == 0 else VIMSH_YEARS[idx]
        days  = years * 365.25
        end   = cur + timedelta(days=days)
        periods.append({"lord": lord, "start": cur.strftime("%Y-%m-%d"),
                        "end": end.strftime("%Y-%m-%d"), "years": round(years, 4)})
        cur = end
    # Continue until 120 years covered
    for cycle in range(1, 12):
        for i in range(9):
            idx  = (s_idx + i) % 9
            lord = VIMSH_ORDER[idx]
            years= VIMSH_YEARS[idx]
            days = years * 365.25
            end  = cur + timedelta(days=days)
            periods.append({"lord": lord, "start": cur.strftime("%Y-%m-%d"),
                            "end": end.strftime("%Y-%m-%d"), "years": round(years, 4)})
            cur = end
    return periods


def _active_md_ad_pd(timeline: list[dict], query_dt: datetime) -> tuple[dict, dict, dict]:
    """Walk timeline to find active MD / AD / PD at query_dt."""
    for maha in timeline:
        md_start = datetime.strptime(maha["start"], "%Y-%m-%d")
        md_end   = datetime.strptime(maha["end"],   "%Y-%m-%d")
        if md_start <= query_dt <= md_end:
            # Calculate AD inside this MD
            md_days   = (md_end - md_start).days
            s_idx     = VIMSH_ORDER.index(maha["lord"])
            cur       = md_start
            for i in range(9):
                idx   = (s_idx + i) % 9
                lord  = VIMSH_ORDER[idx]
                ratio = VIMSH_YEARS[idx] / TOTAL_YEARS
                ad_days = md_days * ratio
                ad_end  = cur + timedelta(days=ad_days)
                if cur <= query_dt <= ad_end:
                    ad = {"lord": lord, "start": cur.strftime("%Y-%m-%d"),
                          "end": ad_end.strftime("%Y-%m-%d")}
                    # PD inside AD
                    ad_duration = ad_days
                    a_idx = VIMSH_ORDER.index(lord)
                    ad_cur = cur
                    for j in range(9):
                        p_idx  = (a_idx + j) % 9
                        p_lord = VIMSH_ORDER[p_idx]
                        pd_days= ad_duration * (VIMSH_YEARS[p_idx] / TOTAL_YEARS)
                        pd_end = ad_cur + timedelta(days=pd_days)
                        if ad_cur <= query_dt <= pd_end:
                            pd = {"lord": p_lord, "start": ad_cur.strftime("%Y-%m-%d"),
                                  "end": pd_end.strftime("%Y-%m-%d")}
                            return maha, ad, pd
                        ad_cur = pd_end
                    return maha, ad, {}
                cur = ad_end
            return maha, {}, {}
    return {}, {}, {}


def _numerology_reduce(n: int) -> int:
    while n > 9 and n not in (11, 22):
        n = sum(int(d) for d in str(n))
    return n


def _name_number(name: str) -> int:
    total = sum(CHALDEAN.get(c.lower(), 0) for c in name if c.isalpha())
    return _numerology_reduce(total)


def _life_path(dob: date) -> int:
    return _numerology_reduce(sum(int(c) for c in str(dob.year) + f"{dob.month:02d}" + f"{dob.day:02d}"))


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
        dob    = date.fromisoformat(dob_s)
        parts  = tob_s.split(":")
        tob    = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    except ValueError as e:
        print(f"\nERROR parsing date/time: {e}")
        sys.exit(1)

    print(f"\n  Looking up coordinates for: {place}")
    lat, lng, tz_name = _geocode(place)
    print(f"  → {lat:.4f}°, {lng:.4f}°  |  {tz_name}")

    # Convert to UTC
    utc_dt   = _local_to_utc(dob, tob, tz_name)
    jd_birth = _jd(utc_dt)

    print("\n  Calculating chart...")
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa_ut(jd_birth)

    # Placidus cusps (tropical) → sidereal
    cusps_trop, ascmc_trop = swe.houses(jd_birth, lat, lng, b"P")
    cusps_sid = [(c - ayanamsa) % 360.0 for c in cusps_trop[:12]]
    asc_sid   = cusps_sid[0]

    # Planets
    planets_out: dict = {}
    for pname, pid in PLANET_IDS.items():
        res, _ = swe.calc_ut(jd_birth, pid, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
        lon = float(res[0]) % 360.0
        sign  = SIGNS[int(lon / 30) % 12]
        nak, star, sub = _nak_star_sub(lon)
        planets_out[pname] = {
            "longitude":  round(lon, 6),
            "sign":       sign,
            "degree":     _dms(lon),
            "house":      0,
            "nakshatra":  nak,
            "pada":       _pada(lon),
            "star_lord":  star,
            "sub_lord":   sub,
            "sign_lord":  SIGN_LORDS.get(sign, ""),
            "retrograde": pname in ("Rahu", "Ketu"),
        }

    # Ketu = Rahu + 180
    rahu_lon = planets_out["Rahu"]["longitude"]
    ketu_lon = (rahu_lon + 180.0) % 360.0
    sign  = SIGNS[int(ketu_lon / 30) % 12]
    nak, star, sub = _nak_star_sub(ketu_lon)
    planets_out["Ketu"] = {
        "longitude":  round(ketu_lon, 6),
        "sign":       sign,
        "degree":     _dms(ketu_lon),
        "house":      0,
        "nakshatra":  nak,
        "pada":       _pada(ketu_lon),
        "star_lord":  star,
        "sub_lord":   sub,
        "sign_lord":  SIGN_LORDS.get(sign, ""),
        "retrograde": True,
    }

    # Houses
    houses_out: dict = {}
    for i, lon in enumerate(cusps_sid[:12], 1):
        sign  = SIGNS[int(lon / 30) % 12]
        nak, star, sub = _nak_star_sub(lon)
        houses_out[str(i)] = {
            "cusp_degree": round(lon, 6),
            "sign":        sign,
            "degree":      _dms(lon),
            "nakshatra":   nak,
            "star_lord":   star,
            "sub_lord":    sub,
        }

    cuspal_sublords = _cuspal_sublords(cusps_sid)

    from analysis.cuspal_houses import assign_cuspal_houses
    planets_out = assign_cuspal_houses(planets_out, houses_out, include_whole_sign=True)

    significators, strength_map = build_natal_significator_block(planets_out, houses_out)
    sig_matrix = _serialize_strength_map(strength_map)
    moon_lon        = planets_out["Moon"]["longitude"]
    timeline        = _vimsh_dashas(moon_lon, utc_dt)
    today           = datetime.now()
    locked_md, locked_ad, locked_pd = _active_md_ad_pd(timeline, today)

    natal_ref = {
        "_meta": {
            "source_report": f"Generated by scripts/generate_natal_ref.py on {date.today().isoformat()}",
            "generated_date": date.today().isoformat(),
            "version": "1.0",
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
        "planets":         planets_out,
        "houses":          houses_out,
        "cuspal_sublords": cuspal_sublords,
        "significators":   significators,
        "significator_matrix": sig_matrix,
        "kp_methodology":  KP_METHODOLOGY,
        "dasha": {
            "locked_md":     locked_md,
            "locked_ad":     locked_ad,
            "locked_pd":     locked_pd,
            "full_timeline": timeline,
        },
        "numerology": {
            "name_number": _name_number(name),
            "life_path":   _life_path(dob),
        },
    }

    out_path = os.path.join(_ROOT, "data", "natal_ref.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(natal_ref, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved to {out_path}")
    print(f"  Name:        {name}")
    print(f"  Birth:       {dob.isoformat()} {tob.strftime('%H:%M:%S')} local | {place}")
    print(f"  Ayanamsa:    {ayanamsa:.4f}° (Lahiri)")
    print(f"  Lagna:       {houses_out['1']['sign']} {houses_out['1']['degree']}")
    print(f"  Lagna CSL:   {cuspal_sublords.get('1','?')}")
    print(f"  10th CSL:    {cuspal_sublords.get('10','?')}")
    print(f"  Active MD:   {locked_md.get('lord','?')} ({locked_md.get('start','?')} → {locked_md.get('end','?')})")
    print(f"  Active AD:   {locked_ad.get('lord','?')} ({locked_ad.get('start','?')} → {locked_ad.get('end','?')})")
    print(f"  Active PD:   {locked_pd.get('lord','?')} ({locked_pd.get('start','?')} → {locked_pd.get('end','?')})")
    print(f"  Name Number: {natal_ref['numerology']['name_number']}")
    print(f"  Life Path:   {natal_ref['numerology']['life_path']}")
    print(f"\n  Review the file and verify against your authoritative KP report.")
    print(f"  NEVER commit data/natal_ref.json to git.\n")


if __name__ == "__main__":
    main()
