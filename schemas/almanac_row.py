"""
TypedDict for a single row in the almanac.
Data container only — no calculation logic.
"""
from __future__ import annotations
from typing import TypedDict, Optional


class KalamWindow(TypedDict):
    start: str   # "HH:MM" local time
    end: str     # "HH:MM" local time


class HoraSlot(TypedDict):
    lord: str
    start: str   # "HH:MM" local time
    end: str     # "HH:MM" local time


class AlmanacRow(TypedDict):
    date: str               # "YYYY-MM-DD"
    weekday: str            # "Monday" etc.
    vara: str               # Vedic day lord name
    sunrise: str            # "HH:MM" local
    sunset: str             # "HH:MM" local
    moonrise: Optional[str] # "HH:MM" or None
    moonset: Optional[str]  # "HH:MM" or None

    # Panchanga
    tithi: str              # e.g. "Shukla Panchami (5)"
    tithi_number: int       # 1–30
    moon_nakshatra: str
    moon_pada: int
    moon_sign: str
    yoga: str
    karana: str

    # Kalam windows
    rahu_kalam: KalamWindow
    yamaganda: KalamWindow
    gulika_kalam: KalamWindow

    # Tarabala
    tara_number: int        # 1–9
    tara_category: str      # e.g. "Sampat (2) — Wealth"
    chandrashtama: bool     # True if Moon in 8th from natal Moon sign

    # Numerology
    day_number: int         # single-digit or master number

    # Active dasha
    active_md: str
    active_ad: str
    active_pd: str
    active_pd_end: str      # ISO date when current PD ends

    # Hora sequence (day + night combined, ordered from sunrise)
    hora_sequence: list[HoraSlot]

    # Day lord (first Ruling Planet — constant for the day)
    day_lord: str
    moon_sign_lord: str
    moon_star_lord: str
    moon_sub_lord: str
