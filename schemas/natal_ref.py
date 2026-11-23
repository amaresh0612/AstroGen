"""
TypedDict definitions matching data/natal_ref.json.

The natal reference is locked once generated. Fields present here mirror
exactly what the JSON stores. Never add computed/derived fields as if they
were source data.
"""
from __future__ import annotations
from typing import TypedDict, Optional


class BirthData(TypedDict):
    name: str
    date: str          # ISO: "YYYY-MM-DD"
    time: str          # "HH:MM:SS" local
    place: str
    lat: float
    lng: float
    tz: str            # e.g. "Asia/Kolkata"
    ayanamsa: float    # Lahiri value at birth


class PlanetData(TypedDict):
    longitude: float   # sidereal 0–360
    sign: str
    degree: str        # DMS string e.g. "14°23'11\""
    house: int         # cuspal Placidus house 1–12 (NOT whole-sign)
    nakshatra: str
    pada: int
    star_lord: str
    sub_lord: str
    sign_lord: str
    retrograde: bool


class HouseData(TypedDict):
    cusp_degree: float
    sign: str
    degree: str
    nakshatra: str
    star_lord: str
    sub_lord: str


class DashaEntry(TypedDict):
    lord: str
    start: str   # ISO date string
    end: str     # ISO date string
    years: float


class LockedDasha(TypedDict):
    lord: str
    start: str
    end: str


class LockedPeriodRow(TypedDict):
    """One Pratyantar with its parents. Timestamps are local wall time "YYYY-MM-DDTHH:MM:SS"."""
    md: str
    md_start: str
    md_end: str
    ad: str
    ad_start: str
    ad_end: str
    pd: str
    pd_start: str
    pd_end: str


class DashaSection(TypedDict, total=False):
    locked_at: str                       # lock moment (local wall time ISO)
    method: str
    locked_md: LockedDasha               # active at locked_at
    locked_ad: LockedDasha
    locked_pd: LockedDasha
    locked_periods: list[LockedPeriodRow]  # lock−1y … lock+6y; engines read MD/AD/PD only from here
    full_timeline: list[dict]            # mahadashas (lord/start/end/years)


class NumerologyData(TypedDict):
    name_number: int
    life_path: int


class SignificatorData(TypedDict):
    occupied_house: Optional[int]
    owned_houses: list[int]
    signified_houses: list[int]


class MetaData(TypedDict):
    source_report: str    # filename / description of source
    generated_date: str   # ISO date when this file was created
    version: str


class NatalRef(TypedDict):
    _meta: MetaData
    birth: BirthData
    planets: dict[str, PlanetData]          # Sun … Ketu
    houses: dict[str, HouseData]            # "1" … "12"
    cuspal_sublords: dict[str, str]         # "1" … "12" → lord name
    significators: dict[str, SignificatorData]
    dasha: DashaSection
    numerology: NumerologyData
