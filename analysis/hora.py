"""
Unequal Hora calculation engine.

Implements true unequal Hora:
  - Day Hora:   sunrise → sunset divided into 12 equal slots
  - Night Hora: sunset → next sunrise divided into 12 equal slots

Weekday lord sequence follows the standard Vedic Hora order.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import swisseph as swe
import pytz

# Hora lord sequence: each day starts with its Vara lord, then follows
# the standard Chaldean order (descending speed: Sun, Venus, Mercury,
# Moon, Saturn, Jupiter, Mars — repeating).
CHALDEAN = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]

# Day-start hora lord by weekday (Sunday=0 … Saturday=6, Vedic astro day)
# Sunday → Sun, Monday → Moon, Tuesday → Mars, Wednesday → Mercury,
# Thursday → Jupiter, Friday → Venus, Saturday → Saturn
VARA_START: dict[int, str] = {
    0: "Sun", 1: "Moon", 2: "Mars", 3: "Mercury",
    4: "Jupiter", 5: "Venus", 6: "Saturn",
}


def _chaldean_index(lord: str) -> int:
    return CHALDEAN.index(lord)


def _hora_lord(start_lord: str, offset: int) -> str:
    idx = (_chaldean_index(start_lord) + offset) % 7
    return CHALDEAN[idx]


def _jd_to_local_str(jd: float, tz_name: str) -> Optional[str]:
    try:
        y, m, d, h = swe.revjul(jd)
        hh = int(h); mm = int((h - hh) * 60); ss = int(((h - hh) * 60 - mm) * 60)
        utc = datetime(int(y), int(m), int(d), hh, mm, ss, tzinfo=pytz.utc)
        local = utc.astimezone(pytz.timezone(tz_name))
        return local.strftime("%H:%M")
    except Exception:
        return None


def _jd_to_local_dt(jd: float, tz_name: str) -> Optional[datetime]:
    try:
        y, m, d, h = swe.revjul(jd)
        hh = int(h); mm = int((h - hh) * 60); ss = int(((h - hh) * 60 - mm) * 60)
        utc = datetime(int(y), int(m), int(d), hh, mm, ss, tzinfo=pytz.utc)
        return utc.astimezone(pytz.timezone(tz_name))
    except Exception:
        return None


def compute_hora(
    date_val: date,
    jd_sunrise: float,
    jd_sunset: float,
    jd_next_sunrise: float,
    tz_name: str = "Asia/Kolkata",
) -> dict:
    """
    Compute the full unequal Hora sequence for a day.

    Parameters
    ----------
    date_val        : The date being computed.
    jd_sunrise      : Julian Day of sunrise (from panchanga.py).
    jd_sunset       : Julian Day of sunset.
    jd_next_sunrise : Julian Day of sunrise on the following day.
    tz_name         : Local timezone for display.

    Returns
    -------
    dict with:
        day_horas    : list[dict] — 12 horas sunrise→sunset
        night_horas  : list[dict] — 12 horas sunset→next sunrise
        all_horas    : combined ordered list
    """
    # Weekday lord (0=Sun … 6=Sat, using Python weekday shifted)
    py_weekday = date_val.weekday()           # Mon=0 … Sun=6
    astro_day  = (py_weekday + 1) % 7         # Sun=0 … Sat=6
    first_lord = VARA_START[astro_day]

    # Hora 1 of the day starts at sunrise with the Vara lord
    day_secs   = (jd_sunset       - jd_sunrise) * 86400.0
    night_secs = (jd_next_sunrise - jd_sunset)  * 86400.0

    day_hora_secs   = day_secs   / 12.0
    night_hora_secs = night_secs / 12.0

    day_horas: list[dict] = []
    night_horas: list[dict] = []

    for i in range(12):
        jd_start = jd_sunrise + i * day_hora_secs / 86400.0
        jd_end   = jd_sunrise + (i + 1) * day_hora_secs / 86400.0
        day_horas.append({
            "sequence": i + 1,
            "lord":  _hora_lord(first_lord, i),
            "start": _jd_to_local_str(jd_start, tz_name),
            "end":   _jd_to_local_str(jd_end,   tz_name),
            "period": "day",
        })

    # Night hora starts with the lord 13 positions after first (next cycle)
    night_first = _hora_lord(first_lord, 12)
    for i in range(12):
        jd_start = jd_sunset + i * night_hora_secs / 86400.0
        jd_end   = jd_sunset + (i + 1) * night_hora_secs / 86400.0
        night_horas.append({
            "sequence": 13 + i,
            "lord":  _hora_lord(night_first, i),
            "start": _jd_to_local_str(jd_start, tz_name),
            "end":   _jd_to_local_str(jd_end,   tz_name),
            "period": "night",
        })

    return {
        "date":        date_val.isoformat(),
        "vara_lord":   first_lord,
        "day_horas":   day_horas,
        "night_horas": night_horas,
        "all_horas":   day_horas + night_horas,
        "day_hora_duration_min":   round(day_hora_secs / 60.0, 1),
        "night_hora_duration_min": round(night_hora_secs / 60.0, 1),
    }


def get_hora_at(
    hora_data: dict,
    query_time_local: datetime,
) -> Optional[dict]:
    """
    Find which hora is active at query_time_local (timezone-aware datetime).
    Returns the matching hora slot or None.
    """
    for slot in hora_data.get("all_horas", []):
        start_s = slot.get("start")
        end_s   = slot.get("end")
        if not start_s or not end_s:
            continue
        try:
            # Parse HH:MM against the query date
            q_date = query_time_local.date()
            tz = query_time_local.tzinfo
            s_dt = query_time_local.replace(
                hour=int(start_s[:2]), minute=int(start_s[3:]), second=0, microsecond=0
            )
            e_dt = query_time_local.replace(
                hour=int(end_s[:2]),   minute=int(end_s[3:]),   second=0, microsecond=0
            )
            if e_dt <= s_dt:  # crosses midnight
                e_dt += timedelta(days=1)
            if s_dt <= query_time_local < e_dt:
                return slot
        except Exception:
            continue
    return None
