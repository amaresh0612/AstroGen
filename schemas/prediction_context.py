"""
PredictionContext — the single structured object passed to every report builder
and AI prompt. Assembled by analysis/context.py for a given date/time/location
against the locked natal reference.
"""
from __future__ import annotations
from typing import TypedDict, Optional


class DashaState(TypedDict):
    md_lord: str
    md_start: str
    md_end: str
    ad_lord: str
    ad_start: str
    ad_end: str
    pd_lord: str
    pd_start: str
    pd_end: str
    sukshma_lord: Optional[str]
    sukshma_start: Optional[str]
    sukshma_end: Optional[str]
    prana_lord: Optional[str]
    prana_start: Optional[str]
    prana_end: Optional[str]


class TransitPlanet(TypedDict):
    longitude: float
    sign: str
    degree: str
    nakshatra: str
    star_lord: str
    sub_lord: str
    transit_house: int       # house in natal chart
    natal_sign: str          # for comparison


class MoonState(TypedDict):
    longitude: float
    sign: str
    nakshatra: str
    pada: int
    star_lord: str
    sub_lord: str
    sign_lord: str


class RulingPlanets(TypedDict):
    reference_time: str          # ISO datetime used for calculation
    reference_location: str      # "City, Country"
    day_lord: str
    ascendant_sign: str
    ascendant_sign_lord: str
    ascendant_star_lord: str
    ascendant_sub_lord: str
    moon_sign_lord: str
    moon_star_lord: str
    moon_sub_lord: str
    rp_list: list[str]           # deduplicated ordered list
    rp_event_match: dict[str, list[str]]  # topic → matching RPs


class PanchangaState(TypedDict):
    date: str
    tithi: str
    tithi_number: int
    vara: str
    moon_nakshatra: str
    moon_pada: int
    yoga: str
    karana: str
    sunrise: str
    sunset: str
    moonrise: Optional[str]
    moonset: Optional[str]


class KalamState(TypedDict):
    rahu_kalam_start: str
    rahu_kalam_end: str
    yamaganda_start: str
    yamaganda_end: str
    gulika_start: str
    gulika_end: str


class HoraState(TypedDict):
    current_hora_lord: str
    current_hora_start: str
    current_hora_end: str
    full_day_sequence: list[dict]   # list of {lord, start, end}


class TarabalaState(TypedDict):
    natal_moon_nakshatra: str
    transit_moon_nakshatra: str
    tara_number: int
    tara_category: str
    chandrashtama: bool
    suitability: str   # "Favorable" / "Neutral" / "Unfavorable"


class NumerologyState(TypedDict):
    name_number: int
    life_path: int
    day_number: int
    day_number_meaning: str


class SignificatorEntry(TypedDict):
    planet: str
    level: int           # 1–4
    level_label: str     # "Direct Occupant", "Star-Lord Link", "Sign Owner", "Indirect"
    occupied_house: Optional[int]
    owned_houses: list[int]
    signified_houses: list[int]


class PromiseDenialEntry(TypedDict):
    topic: str
    topic_label: str
    primary_houses: list[int]
    csl_verdict: str        # What the CSL of primary house signifies
    verdict: str            # PROMISED / SUPPORTED / CONDITIONALLY SUPPORTED /
                            # WEAK / INCONCLUSIVE / CONFLICTED / NOT SUPPORTED
    supporting_evidence: list[str]
    conflicting_evidence: list[str]
    dasha_alignment: str    # how current MD/AD/PD relate to topic houses


class LongTermTransit(TypedDict):
    planet: str
    from_sign: str
    to_sign: str
    ingress_date: str
    transit_house: int
    transit_nakshatra: str
    star_lord: str
    sub_lord: str
    relevant_natal_planets: list[str]
    relevant_event_houses: list[int]
    notes: str


class EventAnalysis(TypedDict):
    topic: str
    promise_denial: PromiseDenialEntry
    relevant_significators: list[SignificatorEntry]
    ruling_planet_match: list[str]
    timing_summary: str


class PredictionContext(TypedDict):
    """
    Single structured object produced by analysis/context.py.
    Passed to all reports and AI prompts. Never constructed piecemeal elsewhere.
    """
    # Query metadata
    query_date: str         # "YYYY-MM-DD"
    query_time: str         # "HH:MM:SS" — explicit reference time
    query_location: str     # "City, Country"
    query_lat: float
    query_lng: float
    query_mode: str         # DAILY / MONTHLY / LONG_TERM / EVENT_SPECIFIC

    # From locked natal reference
    birth_name: str
    birth_date: str
    birth_place: str

    # Dynamic layers
    dasha: DashaState
    transits: dict[str, TransitPlanet]       # planet → TransitPlanet
    moon: MoonState
    ruling_planets: RulingPlanets
    panchanga: PanchangaState
    kalam: KalamState
    hora: HoraState
    tarabala: TarabalaState
    numerology: NumerologyState

    # Analysis layers
    significators: list[SignificatorEntry]
    long_term_transits: list[LongTermTransit]
    event_analyses: list[EventAnalysis]      # populated when topics are specified
