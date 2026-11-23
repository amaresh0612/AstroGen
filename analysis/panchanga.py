"""
Panchanga calculation engine.

Computes: Tithi, Vara, Moon Nakshatra/Pada, Yoga, Karana,
          Sunrise, Sunset, Moonrise, Moonset.

All calculations use Swiss Ephemeris (Lahiri ayanamsa) — same as app.py.
Day boundaries (sunrise/sunset) are exposed so Hora and Kalam engines
can depend on them without redundant calculation.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Optional

import swisseph as swe
import pytz

from analysis.nakshatra_utils import moon_nakshatra_dict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TITHIS = [
    (1,  "Pratipad",   "Shukla"),  (2,  "Dwitiya",    "Shukla"),
    (3,  "Tritiya",    "Shukla"),  (4,  "Chaturthi",  "Shukla"),
    (5,  "Panchami",   "Shukla"),  (6,  "Shashthi",   "Shukla"),
    (7,  "Saptami",    "Shukla"),  (8,  "Ashtami",    "Shukla"),
    (9,  "Navami",     "Shukla"),  (10, "Dashami",    "Shukla"),
    (11, "Ekadashi",   "Shukla"),  (12, "Dwadashi",   "Shukla"),
    (13, "Trayodashi", "Shukla"),  (14, "Chaturdashi", "Shukla"),
    (15, "Purnima",    "Shukla"),
    (16, "Pratipad",   "Krishna"), (17, "Dwitiya",    "Krishna"),
    (18, "Tritiya",    "Krishna"), (19, "Chaturthi",  "Krishna"),
    (20, "Panchami",   "Krishna"), (21, "Shashthi",   "Krishna"),
    (22, "Saptami",    "Krishna"), (23, "Ashtami",    "Krishna"),
    (24, "Navami",     "Krishna"), (25, "Dashami",    "Krishna"),
    (26, "Ekadashi",   "Krishna"), (27, "Dwadashi",   "Krishna"),
    (28, "Trayodashi", "Krishna"), (29, "Chaturdashi","Krishna"),
    (30, "Amavasya",   "Krishna"),
]

YOGAS = [
    "Vishkumbha","Preeti","Ayushman","Saubhagya","Shobhana",
    "Atiganda","Sukarma","Dhriti","Shula","Ganda","Vriddhi",
    "Dhruva","Vyaghata","Harshana","Vajra","Siddhi","Vyatipata",
    "Variyan","Parigha","Shiva","Siddha","Sadhya","Shubha",
    "Shukla","Brahma","Indra","Vaidhriti",
]

KARANAS = [
    "Bava","Balava","Kaulava","Taitila","Gara","Vanija","Vishti",
    "Shakuni","Chatushpada","Naga","Kimstughna",
]

from analysis.kp_constants import NAKSHATRAS, SIGNS, VARA_LORDS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _jd_ut(dt_utc: datetime) -> float:
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0)


def _sid_lon(jd: float, body: int) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    res, _ = swe.calc_ut(jd, body, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return float(res[0]) % 360.0


def _jd_to_local(jd: float, tz_name: str) -> Optional[datetime]:
    try:
        y, m, d, h = swe.revjul(jd)
        hh = int(h); mm = int((h - hh) * 60); ss = int(((h - hh) * 60 - mm) * 60)
        utc_dt = datetime(int(y), int(m), int(d), hh, mm, ss, tzinfo=pytz.utc)
        return utc_dt.astimezone(pytz.timezone(tz_name))
    except Exception:
        return None


def _rise_set(date_val: date, lat: float, lng: float, body: int, flag: int,
              tz_name: str = "UTC") -> Optional[float]:
    """Return JD of rise (flag=1) or set (flag=2) for a body on date_val.

    Searches from local midnight (expressed as UT) so the correct day's event
    is always found, regardless of timezone offset.
    """
    try:
        if tz_name and tz_name != "UTC":
            tz_obj = pytz.timezone(tz_name)
            local_midnight = datetime(date_val.year, date_val.month, date_val.day, 0, 0, 0)
            utc_midnight = tz_obj.localize(local_midnight).astimezone(pytz.utc)
            jd_start = swe.julday(
                utc_midnight.year, utc_midnight.month, utc_midnight.day,
                utc_midnight.hour + utc_midnight.minute / 60.0 + utc_midnight.second / 3600.0
            )
        else:
            jd_start = swe.julday(date_val.year, date_val.month, date_val.day, 0.0)
    except Exception:
        jd_start = swe.julday(date_val.year, date_val.month, date_val.day, 0.0)

    geopos = (float(lng), float(lat), 0.0)
    try:
        rc, tret = swe.rise_trans(jd_start, body, flag, geopos, 1013.25, 15.0)
        if rc >= 0 and tret[0] > 0:
            return tret[0]
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_tithi(sun_lon: float, moon_lon: float) -> dict:
    """Return tithi name, number (1-30) and paksha."""
    diff = (moon_lon - sun_lon) % 360.0
    tithi_num = int(diff / 12.0) + 1
    tithi_num = min(tithi_num, 30)
    rec = TITHIS[tithi_num - 1]
    return {
        "number": rec[0],
        "name":   rec[1],
        "paksha": rec[2],
        "label":  f"{rec[2]} {rec[1]} ({rec[0]})",
    }


def compute_yoga(sun_lon: float, moon_lon: float) -> dict:
    combined = (sun_lon + moon_lon) % 360.0
    idx = int(combined / (360.0 / 27)) % 27
    return {"number": idx + 1, "name": YOGAS[idx]}


def compute_karana(sun_lon: float, moon_lon: float) -> dict:
    diff = (moon_lon - sun_lon) % 360.0
    half_tithi = diff / 6.0
    idx = int(half_tithi) % 60
    # Fixed karanas: 0=Kimstughna(1st half of Shukla1), 57-59=Shakuni,Chatushpada,Naga
    if idx == 0:
        return {"name": "Kimstughna", "type": "fixed"}
    if idx in (57, 58, 59):
        fixed = ["Shakuni", "Chatushpada", "Naga"][idx - 57]
        return {"name": fixed, "type": "fixed"}
    movable_idx = (idx - 1) % 7
    return {"name": KARANAS[movable_idx], "type": "movable"}



def compute_moon_nakshatra(moon_lon: float) -> dict:
    """Return Moon nakshatra name, lord, pada, and index."""
    return moon_nakshatra_dict(moon_lon)


def compute_vara(date_val: date) -> dict:
    """Return Vedic Vara (weekday lord). Sunday=Sun, Monday=Moon, etc."""
    weekday = date_val.weekday()  # Mon=0 … Sun=6
    astro_day = (weekday + 1) % 7  # Sun=0 Mon=1 … Sat=6
    return {"number": astro_day, "lord": VARA_LORDS[astro_day], "weekday": date_val.strftime("%A")}


def compute_panchanga(date_val: date, lat: float, lng: float, tz_name: str = "Asia/Kolkata") -> dict:
    """
    Compute full Panchanga for a given date and location.

    Returns a dict with:
        tithi, vara, nakshatra, pada, moon_sign, yoga, karana,
        sunrise, sunset, moonrise, moonset (local time strings)
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    # Sunrise JD for ephemeris reference
    jd_rise = _rise_set(date_val, lat, lng, swe.SUN, 1, tz_name)
    jd_set  = _rise_set(date_val, lat, lng, swe.SUN, 2, tz_name)

    # Use sunrise as reference; fall back to noon UTC if unavailable
    if jd_rise:
        jd_ref = jd_rise
    else:
        jd_ref = swe.julday(date_val.year, date_val.month, date_val.day, 12.0 - lng / 15.0)

    # Planet longitudes at reference time
    sun_lon  = _sid_lon(jd_ref, swe.SUN)
    moon_lon = _sid_lon(jd_ref, swe.MOON)

    # Panchanga elements
    tithi   = compute_tithi(sun_lon, moon_lon)
    yoga    = compute_yoga(sun_lon, moon_lon)
    karana  = compute_karana(sun_lon, moon_lon)
    nak     = compute_moon_nakshatra(moon_lon)
    vara    = compute_vara(date_val)
    moon_sign = SIGNS[int(moon_lon / 30) % 12]

    def _fmt(jd: Optional[float]) -> Optional[str]:
        if jd is None:
            return None
        dt = _jd_to_local(jd, tz_name)
        return dt.strftime("%H:%M") if dt else None

    # Moonrise / moonset
    jd_moonrise = _rise_set(date_val, lat, lng, swe.MOON, 1, tz_name)
    jd_moonset  = _rise_set(date_val, lat, lng, swe.MOON, 2, tz_name)

    return {
        "date":          date_val.isoformat(),
        "tithi":         tithi["label"],
        "tithi_number":  tithi["number"],
        "paksha":        tithi["paksha"],
        "vara":          vara["lord"],
        "weekday":       vara["weekday"],
        "moon_nakshatra": nak["name"],
        "moon_star_lord": nak["lord"],
        "moon_pada":      nak["pada"],
        "moon_sign":      moon_sign,
        "yoga":           yoga["name"],
        "karana":         karana["name"],
        "sun_longitude":  round(sun_lon, 4),
        "moon_longitude": round(moon_lon, 4),
        # Day boundaries (used by hora.py and kalam engines)
        "jd_sunrise":    jd_rise,
        "jd_sunset":     jd_set,
        "jd_moonrise":   jd_moonrise,
        "jd_moonset":    jd_moonset,
        "sunrise":       _fmt(jd_rise),
        "sunset":        _fmt(jd_set),
        "moonrise":      _fmt(jd_moonrise),
        "moonset":       _fmt(jd_moonset),
        "tz_name":       tz_name,
    }
