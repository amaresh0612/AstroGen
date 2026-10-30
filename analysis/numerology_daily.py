"""
Numerology day number calculation.

The day number is the single-digit reduction of the calendar date.
Used as an energy/tone layer in daily predictions.
"""
from __future__ import annotations

from datetime import date


def _reduce(n: int) -> int:
    """Reduce to single digit. Preserves master numbers 11 and 22."""
    while n > 9 and n not in (11, 22):
        n = sum(int(d) for d in str(n))
    return n


def day_number(date_val: date) -> int:
    """Return the numerology day number for a given date."""
    total = date_val.day + date_val.month + date_val.year
    return _reduce(total)


DAY_NUMBER_MEANINGS: dict[int, str] = {
    1:  "Leadership, new beginnings, independence",
    2:  "Cooperation, sensitivity, relationships",
    3:  "Creativity, expression, social energy",
    4:  "Stability, hard work, discipline",
    5:  "Change, freedom, adaptability",
    6:  "Responsibility, harmony, home/family",
    7:  "Introspection, analysis, spiritual insight",
    8:  "Power, ambition, material focus",
    9:  "Completion, humanitarianism, release",
    11: "Intuition, illumination, master number",
    22: "Master builder, large ambitions, master number",
}


def day_number_meaning(n: int) -> str:
    return DAY_NUMBER_MEANINGS.get(n, "")


def compute_numerology_daily(date_val: date, name_number: int, life_path: int) -> dict:
    """Return full numerology context for a date including natal values."""
    dn = day_number(date_val)
    return {
        "date":              date_val.isoformat(),
        "day_number":        dn,
        "day_number_meaning": day_number_meaning(dn),
        "name_number":       name_number,
        "life_path":         life_path,
    }
