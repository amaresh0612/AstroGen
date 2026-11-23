"""
Ruling-Planet interval engine — exact sign / star / sub windows for a local day.

The KP Ruling Planet set has seven components:

    Day Lord · Ascendant sign / star / sub lord · Moon sign / star / sub lord

Four of them (day lord and the Moon trio) move slowly enough to be read off a
daily record. The ascendant trio changes roughly every few minutes, so a single
daily value cannot answer "what were the RPs at 15:30?". This module computes
the complete set of change boundaries for a local day so a stored pack can
answer exact-time RP questions without recalculating anything.

Method
------
Sign, nakshatra and KP sub boundaries sit at fixed sidereal longitudes
(``kp_cut_longitudes`` — 260 of them). Both the ascendant and the Moon advance
monotonically, so instead of sampling and hoping no short sub is skipped, every
cut longitude in the day's swept arc is solved for directly by bisection. No
change can be missed by construction.

Interval labels are evaluated at the interval midpoint, which keeps them
consistent with ``kp_constants.nak_star_sub`` (a longitude exactly on a
boundary belongs to the earlier sub).
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pytz
import swisseph as swe

from analysis.kp_constants import (
    NAK_WIDTH, NAKSHATRAS, SIGN_LORDS, VARA_LORDS, VIMSHOTTARI_ORDER, VIMSHOTTARI_TOTAL,
    VIMSHOTTARI_YEARS, astro_weekday, jd_to_utc_datetime, localize, nak_star_sub, sign_of,
)

# Field order of every compact interval array stored in the pack.
RP_INTERVAL_FIELDS = ["start", "end", "sign", "sign_lord", "nakshatra", "star_lord", "sub_lord"]

# Bisection resolution for a boundary time: half a second.
BOUNDARY_TOLERANCE_SECONDS = 0.5
_TOL_DAYS = BOUNDARY_TOLERANCE_SECONDS / 86400.0

# Coarse bracketing steps. Only need to be fine enough that the body advances
# well under 360 degrees per step; 1 min (asc ~0.25 deg) and 15 min (Moon
# ~0.14 deg) are far inside that.
ASC_COARSE_MINUTES = 1.0
MOON_COARSE_MINUTES = 15.0

# Expected ascendant interval count for a 24h day: ~249 subs plus the sign cuts
# that fall inside a nakshatra. Used as a sanity band by pack validation.
ASC_INTERVALS_PER_DAY_MIN = 230
ASC_INTERVALS_PER_DAY_MAX = 300

_CUTS_CACHE: Optional[list[float]] = None


def kp_cut_longitudes() -> list[float]:
    """
    Every sidereal longitude at which a sign, nakshatra or KP sub changes.

    Nakshatra starts coincide with sub starts, and 0 Aries coincides with both,
    so the union is 249 sub boundaries plus the 11 sign boundaries that fall
    inside a nakshatra.
    """
    global _CUTS_CACHE
    if _CUTS_CACHE is not None:
        return _CUTS_CACHE

    cuts: set[float] = {round(s * 30.0, 9) for s in range(12)}
    for n, (_, star) in enumerate(NAKSHATRAS):
        base = n * NAK_WIDTH
        cuts.add(round(base, 9))
        start = VIMSHOTTARI_ORDER.index(star)
        cum = 0.0
        for i in range(9):
            k = (start + i) % 9
            cum += (VIMSHOTTARI_YEARS[k] / float(VIMSHOTTARI_TOTAL)) * NAK_WIDTH
            cuts.add(round((base + cum) % 360.0, 9))
    _CUTS_CACHE = sorted(cuts)
    return _CUTS_CACHE


def lords_at(lon: float) -> tuple[str, str, str, str, str]:
    """(sign, sign lord, nakshatra, star lord, sub lord) for a sidereal longitude."""
    sign = sign_of(lon)
    nak, star, sub = nak_star_sub(lon)
    return sign, SIGN_LORDS[sign], nak, star, sub


def ascendant_longitude(jd_ut: float, lat: float, lng: float) -> float:
    """Sidereal (Lahiri) ascendant in degrees."""
    _, ascmc = swe.houses(jd_ut, lat, lng, b"P")
    return (ascmc[0] - swe.get_ayanamsa_ut(jd_ut)) % 360.0


def moon_longitude(jd_ut: float) -> float:
    """Sidereal (Lahiri) Moon longitude in degrees."""
    res, _ = swe.calc_ut(jd_ut, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return float(res[0]) % 360.0


def _jd(dt_aware: datetime) -> float:
    u = dt_aware.astimezone(pytz.utc)
    hours = u.hour + u.minute / 60.0 + (u.second + u.microsecond / 1e6) / 3600.0
    return swe.julday(u.year, u.month, u.day, hours)


def _boundary_jds(
    lon_fn: Callable[[float], float],
    jd_start: float,
    jd_end: float,
    coarse_minutes: float,
) -> list[float]:
    """
    Julian days at which ``lon_fn`` crosses a KP cut longitude inside the span.

    ``lon_fn`` must advance monotonically (true for both the ascendant and the
    Moon). Longitudes are unwrapped onto a continuous scale so every cut in the
    swept arc is solved individually rather than discovered by sampling.
    """
    step = coarse_minutes / 1440.0
    samples: list[tuple[float, float, float]] = []  # (jd, wrapped, unwrapped)

    prev_wrapped = lon_fn(jd_start)
    unwrapped = prev_wrapped
    samples.append((jd_start, prev_wrapped, unwrapped))

    t = jd_start
    while t < jd_end:
        t = min(t + step, jd_end)
        wrapped = lon_fn(t)
        unwrapped += (wrapped - prev_wrapped) % 360.0
        samples.append((t, wrapped, unwrapped))
        prev_wrapped = wrapped

    start_u, end_u = samples[0][2], samples[-1][2]
    cuts = kp_cut_longitudes()

    targets: list[float] = []
    cycle = math.floor(start_u / 360.0) * 360.0
    while cycle < end_u:
        for c in cuts:
            v = cycle + c
            if start_u < v < end_u:
                targets.append(v)
        cycle += 360.0
    targets.sort()

    boundaries: list[float] = []
    idx = 0
    for target in targets:
        while idx + 1 < len(samples) and samples[idx + 1][2] < target:
            idx += 1
        lo_jd, lo_wrapped, lo_u = samples[idx]
        hi_jd = samples[idx + 1][0]

        def u_at(jd: float) -> float:
            return lo_u + (lon_fn(jd) - lo_wrapped) % 360.0

        a, b = lo_jd, hi_jd
        while b - a > _TOL_DAYS:
            mid = (a + b) / 2.0
            if u_at(mid) < target:
                a = mid
            else:
                b = mid
        boundaries.append((a + b) / 2.0)

    return boundaries


def _clock(dt_local: datetime, day_end: datetime) -> str:
    """Local wall clock; the closing instant of the day renders as 24:00:00."""
    if dt_local >= day_end:
        return "24:00:00"
    return dt_local.strftime("%H:%M:%S")


def _intervals(
    lon_fn: Callable[[float], float],
    jd_start: float,
    jd_end: float,
    coarse_minutes: float,
    tz: pytz.BaseTzInfo,
    day_end_local: datetime,
) -> list[list]:
    """Compact ``RP_INTERVAL_FIELDS`` rows covering [jd_start, jd_end) with no gaps."""
    edges = [jd_start] + _boundary_jds(lon_fn, jd_start, jd_end, coarse_minutes) + [jd_end]

    rows: list[list] = []
    for a, b in zip(edges, edges[1:]):
        if b - a <= 0:
            continue
        sign, sign_lord, nak, star, sub = lords_at(lon_fn((a + b) / 2.0))
        start_s = _clock(jd_to_utc_datetime(a).astimezone(tz), day_end_local)
        end_s = _clock(jd_to_utc_datetime(b).astimezone(tz), day_end_local)
        if rows and rows[-1][2:] == [sign, sign_lord, nak, star, sub]:
            rows[-1][1] = end_s          # coincident cuts produced a duplicate label
            continue
        rows.append([start_s, end_s, sign, sign_lord, nak, star, sub])
    return rows


def rp_snapshot(jd_ut: float, lat: float, lng: float, day_lord: str) -> dict:
    """Full seven-part RP set at one instant."""
    a_sign, a_sign_lord, a_nak, a_star, a_sub = lords_at(ascendant_longitude(jd_ut, lat, lng))
    m_lon = moon_longitude(jd_ut)
    m_sign, m_sign_lord, m_nak, m_star, m_sub = lords_at(m_lon)

    rp_list: list[str] = []
    for p in (day_lord, a_sign_lord, a_star, a_sub, m_sign_lord, m_star, m_sub):
        if p and p not in rp_list:
            rp_list.append(p)

    return {
        "day_lord": day_lord,
        "ascendant": {
            "sign": a_sign, "sign_lord": a_sign_lord,
            "nakshatra": a_nak, "star_lord": a_star, "sub_lord": a_sub,
        },
        "moon": {
            "sign": m_sign, "sign_lord": m_sign_lord,
            "nakshatra": m_nak, "star_lord": m_star, "sub_lord": m_sub,
        },
        "rp_list": rp_list,
    }


def build_day_rp(
    day: date,
    lat: float,
    lng: float,
    tz_name: str,
    reference_time: str = "09:00",
) -> dict:
    """
    Complete ruling-planet block for one local day at one location.

    Covers local midnight to the next local midnight with gapless ascendant and
    Moon intervals, plus a full seven-part snapshot at ``reference_time``.
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    tz = pytz.timezone(tz_name)

    start_local = localize(tz_name, datetime(day.year, day.month, day.day))
    next_day = day + timedelta(days=1)
    end_local = localize(tz_name, datetime(next_day.year, next_day.month, next_day.day))
    jd_start, jd_end = _jd(start_local), _jd(end_local)
    span_minutes = round((jd_end - jd_start) * 1440.0)

    day_lord = VARA_LORDS[astro_weekday(day)]

    asc_rows = _intervals(
        lambda jd: ascendant_longitude(jd, lat, lng),
        jd_start, jd_end, ASC_COARSE_MINUTES, tz, end_local,
    )
    moon_rows = _intervals(moon_longitude, jd_start, jd_end, MOON_COARSE_MINUTES, tz, end_local)

    ref_hh, ref_mm = (int(x) for x in reference_time.split(":")[:2])
    ref_local = localize(tz_name, datetime(day.year, day.month, day.day, ref_hh, ref_mm))
    snapshot = rp_snapshot(_jd(ref_local), lat, lng, day_lord)
    snapshot["local_time"] = ref_local.isoformat()
    snapshot["reference_time"] = reference_time

    return {
        "date": day.isoformat(),
        "weekday": day.strftime("%A"),
        "timezone": tz_name,
        "utc_offset": start_local.strftime("%z"),
        "day_lord": day_lord,
        "coverage": {
            "start": start_local.isoformat(),
            "end": end_local.isoformat(),
            "local_day_minutes": span_minutes,
        },
        "interval_fields": RP_INTERVAL_FIELDS,
        "interval_note": (
            "start/end are local wall-clock times on this date in this timezone; "
            "24:00:00 means the next local midnight. Intervals are gapless and "
            "half-open [start, end). Resolve an exact-time RP query by locating "
            "the ascendant and Moon interval that contains the queried time."
        ),
        "reference_snapshot": snapshot,
        "ascendant_windows": asc_rows,
        "moon_windows": moon_rows,
    }


def _to_seconds(clock: str) -> int:
    h, m, s = (int(x) for x in clock.split(":"))
    return h * 3600 + m * 60 + s


def rp_at_local_time(day_rp: dict, clock: str) -> dict:
    """
    Resolve the stored seven-part RP set for a local wall-clock time.

    This is the lookup the AI performs against the pack; it is also what the
    tests use to prove an exact-time query never falls back to the daily
    reference snapshot.
    """
    want = _to_seconds(clock if clock.count(":") == 2 else clock + ":00")

    def find(rows: list[list]) -> Optional[list]:
        for row in rows:
            if _to_seconds(row[0]) <= want < _to_seconds(row[1]):
                return row
        return None

    asc = find(day_rp.get("ascendant_windows", []))
    moon = find(day_rp.get("moon_windows", []))
    if asc is None or moon is None:
        raise ValueError(f"{clock} is outside the stored windows for {day_rp.get('date')}")

    rp_list: list[str] = []
    for p in (day_rp["day_lord"], asc[3], asc[5], asc[6], moon[3], moon[5], moon[6]):
        if p not in rp_list:
            rp_list.append(p)

    return {
        "date": day_rp.get("date"),
        "local_time": clock,
        "day_lord": day_rp["day_lord"],
        "ascendant": {"sign": asc[2], "sign_lord": asc[3], "nakshatra": asc[4],
                      "star_lord": asc[5], "sub_lord": asc[6],
                      "window": {"start": asc[0], "end": asc[1]}},
        "moon": {"sign": moon[2], "sign_lord": moon[3], "nakshatra": moon[4],
                 "star_lord": moon[5], "sub_lord": moon[6],
                 "window": {"start": moon[0], "end": moon[1]}},
        "rp_list": rp_list,
    }
