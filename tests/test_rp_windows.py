"""
Pre-stored Ruling Planets in the 90-day pack.

Covers the engine (analysis/rp_windows.py, analysis/rp_triggers.py) and the
acceptance tests for answering date- and time-specific questions from the
static pack alone, with no website, no API and no chart regeneration.
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime

import pytest
import pytz
import swisseph as swe

from analysis.kp_constants import VARA_LORDS, astro_weekday
from analysis.pack_builder import build_90day_pack
from analysis.rp_triggers import WINDOW_FIELDS
from analysis.rp_windows import (
    ASC_INTERVALS_PER_DAY_MAX, ASC_INTERVALS_PER_DAY_MIN, RP_INTERVAL_FIELDS,
    ascendant_longitude, build_day_rp, kp_cut_longitudes, lords_at, moon_longitude,
    rp_at_local_time,
)
from analysis.ruling_planets import compute_ruling_planets
from schemas.event_houses import EVENT_HOUSES

HYD = dict(lat=17.385, lng=78.4867, tz_name="Asia/Kolkata")
JAN_18 = date(2027, 1, 18)


def _secs(clock: str) -> int:
    h, m, s = (int(x) for x in clock.split(":"))
    return h * 3600 + m * 60 + s


@pytest.fixture(scope="module")
def day_rp() -> dict:
    return build_day_rp(JAN_18, HYD["lat"], HYD["lng"], HYD["tz_name"], "09:00")


@pytest.fixture(scope="module")
def jan_pack(natal) -> dict:
    """A pack whose coverage is January 2027 — the month the user asks about."""
    return build_90day_pack(
        natal_ref=natal,
        start_date=date(2027, 1, 1),
        num_days=31,
        prediction_city="Hyderabad, India",
        prediction_lat=HYD["lat"],
        prediction_lng=HYD["lng"],
        prediction_tz=HYD["tz_name"],
        reference_time="09:00",
    )


# ── Engine ────────────────────────────────────────────────────────────────

def test_cut_table_is_complete_and_minimal():
    """Every stored cut changes a lord, and no interval hides a change."""
    cuts = kp_cut_longitudes()
    assert len(cuts) == 249

    for c in cuts:
        assert lords_at((c - 0.001) % 360.0) != lords_at((c + 0.001) % 360.0), c

    edges = cuts + [360.0]
    for a, b in zip(edges, edges[1:]):
        labels = {lords_at(a + (b - a) * j / 40.0) for j in range(1, 40)}
        assert len(labels) == 1, f"lord change hidden inside {a}–{b}"


def test_day_covers_local_midnight_to_midnight_without_gaps(day_rp):
    assert day_rp["interval_fields"] == RP_INTERVAL_FIELDS
    assert day_rp["timezone"] == "Asia/Kolkata"
    assert day_rp["coverage"]["local_day_minutes"] == 1440

    for key in ("ascendant_windows", "moon_windows"):
        rows = day_rp[key]
        assert rows[0][0] == "00:00:00"
        assert rows[-1][1] == "24:00:00"
        for prev, nxt in zip(rows, rows[1:]):
            assert prev[1] == nxt[0], f"{key} gap at {prev[1]}"
        assert all(_secs(r[1]) > _secs(r[0]) for r in rows)


def test_every_ascendant_change_is_represented(day_rp):
    """Independent minute-by-minute scan finds no lord change the pack missed."""
    tz = pytz.timezone(HYD["tz_name"])
    start = tz.localize(datetime(JAN_18.year, JAN_18.month, JAN_18.day))
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    rows = day_rp["ascendant_windows"]
    assert ASC_INTERVALS_PER_DAY_MIN <= len(rows) <= ASC_INTERVALS_PER_DAY_MAX

    for minute in range(0, 1440, 7):
        moment = start.replace(hour=minute // 60, minute=minute % 60)
        u = moment.astimezone(pytz.utc)
        jd = swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60.0)
        sign, sign_lord, nak, star, sub = lords_at(
            ascendant_longitude(jd, HYD["lat"], HYD["lng"])
        )
        stored = rp_at_local_time(day_rp, f"{minute // 60:02d}:{minute % 60:02d}:00")
        assert stored["ascendant"]["sub_lord"] == sub, moment
        assert stored["ascendant"]["star_lord"] == star
        assert stored["ascendant"]["sign_lord"] == sign_lord
        assert stored["ascendant"]["sign"] == sign
        assert stored["ascendant"]["nakshatra"] == nak


def test_moon_windows_track_the_moon(day_rp):
    tz = pytz.timezone(HYD["tz_name"])
    start = tz.localize(datetime(JAN_18.year, JAN_18.month, JAN_18.day))
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    for minute in range(0, 1440, 37):
        moment = start.replace(hour=minute // 60, minute=minute % 60)
        u = moment.astimezone(pytz.utc)
        jd = swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60.0)
        _, sign_lord, _, star, sub = lords_at(moon_longitude(jd))
        stored = rp_at_local_time(day_rp, f"{minute // 60:02d}:{minute % 60:02d}:00")
        assert (stored["moon"]["sign_lord"], stored["moon"]["star_lord"],
                stored["moon"]["sub_lord"]) == (sign_lord, star, sub), moment


def test_reference_snapshot_matches_the_validated_rp_engine(day_rp):
    """The new engine must agree with analysis/ruling_planets.py, the existing source."""
    utc_dt = datetime(2027, 1, 18, 3, 30)  # 09:00 IST
    legacy = compute_ruling_planets(utc_dt, HYD["lat"], HYD["lng"], HYD["tz_name"])
    snap = day_rp["reference_snapshot"]

    assert snap["day_lord"] == legacy["day_lord"]
    assert snap["ascendant"]["sign"] == legacy["ascendant_sign"]
    assert snap["ascendant"]["sign_lord"] == legacy["ascendant_sign_lord"]
    assert snap["ascendant"]["star_lord"] == legacy["ascendant_star_lord"]
    assert snap["ascendant"]["sub_lord"] == legacy["ascendant_sub_lord"]
    assert snap["moon"]["sign_lord"] == legacy["moon_sign_lord"]
    assert snap["moon"]["star_lord"] == legacy["moon_star_lord"]
    assert snap["moon"]["sub_lord"] == legacy["moon_sub_lord"]
    assert snap["rp_list"] == legacy["rp_list"]


# ── Acceptance A: monthly forecast ────────────────────────────────────────

def test_a_every_january_day_has_its_own_rp(jan_pack):
    days = jan_pack["days"]
    assert len(days) == 31
    assert jan_pack["valid_from"] == "2027-01-01"
    assert jan_pack["valid_to"] == "2027-01-31"

    for d in days:
        rp = d["ruling_planets"]
        assert rp["date"] == d["date"]
        assert rp["day_lord"] == VARA_LORDS[astro_weekday(date.fromisoformat(d["date"]))]
        assert rp["ascendant_windows"] and rp["moon_windows"]

    # Not one snapshot reused: the RP sets genuinely differ across the month.
    sets = {tuple(d["ruling_planets"]["reference_snapshot"]["rp_list"]) for d in days}
    assert len(sets) > 5


def test_a_january_rp_differs_from_a_november_snapshot(natal, jan_pack):
    nov = build_day_rp(date(2026, 11, 22), HYD["lat"], HYD["lng"], HYD["tz_name"], "09:00")
    jan = jan_pack["days"][17]["ruling_planets"]
    assert jan["date"] == "2027-01-18"
    assert jan["reference_snapshot"]["rp_list"] != nov["reference_snapshot"]["rp_list"]


# ── Acceptance B / C: specific date and specific time ─────────────────────

def test_b_specific_date_is_directly_addressable(jan_pack):
    by_date = {d["date"]: d for d in jan_pack["days"]}
    day = by_date["2027-01-18"]
    assert day["ruling_planets"]["day_lord"] == "Moon"      # Monday
    assert day["ruling_planets"]["reference_snapshot"]["reference_time"] == "09:00"


def test_c_exact_time_uses_the_stored_interval_not_the_snapshot(jan_pack):
    by_date = {d["date"]: d for d in jan_pack["days"]}
    rp = by_date["2027-01-18"]["ruling_planets"]
    at_1530 = rp_at_local_time(rp, "15:30:00")

    assert _secs(at_1530["ascendant"]["window"]["start"]) <= _secs("15:30:00")
    assert _secs(at_1530["ascendant"]["window"]["end"]) > _secs("15:30:00")

    snapshot = rp["reference_snapshot"]
    assert at_1530["ascendant"]["sub_lord"] != snapshot["ascendant"]["sub_lord"]

    utc_dt = datetime(2027, 1, 18, 10, 0)  # 15:30 IST
    legacy = compute_ruling_planets(utc_dt, HYD["lat"], HYD["lng"], HYD["tz_name"])
    assert at_1530["ascendant"]["sub_lord"] == legacy["ascendant_sub_lord"]
    assert at_1530["ascendant"]["star_lord"] == legacy["ascendant_star_lord"]
    assert at_1530["moon"]["sub_lord"] == legacy["moon_sub_lord"]
    assert at_1530["rp_list"] == legacy["rp_list"]


# ── Acceptance D: dasha transitions ───────────────────────────────────────

def test_d_every_dasha_level_is_present_and_locked(jan_pack):
    window = [d for d in jan_pack["days"] if "2027-01-22" <= d["date"] <= "2027-01-25"]
    assert len(window) == 4

    for d in window:
        for level in ("md", "ad", "pd", "sukshma", "prana"):
            assert d["dasha"][level]["lord"], f"{d['date']} missing {level}"
        assert "LOCKED" in d["dasha"]["source"]


def test_d_sukshma_timeline_exposes_every_transition(jan_pack):
    """Per-day dasha samples 09:00; the timeline must not skip a short Sukshma."""
    windows = jan_pack["sukshma_timeline"]["windows"]
    assert windows
    assert windows[0]["start"] == "2027-01-01T00:00:00"
    assert windows[-1]["end"] == "2027-02-01T00:00:00"
    for prev, nxt in zip(windows, windows[1:]):
        assert prev["end"] == nxt["start"], f"gap at {prev['end']}"
        assert prev["lord"] != nxt["lord"]

    assert len({w["lord"] for w in windows}) > 1
    daily = {d["dasha"]["sukshma"]["lord"] for d in jan_pack["days"]}
    assert daily <= {w["lord"] for w in windows}


def test_d_prana_timeline_is_complete_and_gapless(jan_pack):
    windows = jan_pack["prana_timeline"]["windows"]
    assert windows
    assert windows[0]["start"] == "2027-01-01T00:00:00"
    assert windows[-1]["end"] == "2027-02-01T00:00:00"
    for prev, nxt in zip(windows, windows[1:]):
        assert prev["end"] == nxt["start"], f"prana gap at {prev['end']}"
    for w in windows:
        assert w["md"] and w["ad"] and w["pd"] and w["sukshma"] and w["lord"]
        assert "signified_houses" in w and "topics" in w
    daily = {d["dasha"]["prana"]["lord"] for d in jan_pack["days"]}
    assert daily <= {w["lord"] for w in windows}


# ── Acceptance E: natal protection ────────────────────────────────────────

def test_e_building_a_pack_never_mutates_the_natal_reference(natal):
    before = copy.deepcopy(natal)
    build_90day_pack(
        natal_ref=natal, start_date=date(2027, 1, 1), num_days=2,
        prediction_city="Hyderabad, India", prediction_lat=HYD["lat"],
        prediction_lng=HYD["lng"], prediction_tz=HYD["tz_name"], reference_time="09:00",
    )
    assert natal == before
    assert natal["dasha"]["locked_md"] == before["dasha"]["locked_md"]
    assert natal["significators"] == before["significators"]


def test_e_pack_carries_the_natal_fingerprint_unchanged(natal, jan_pack):
    from analysis.natal_fingerprint import build_natal_fingerprint
    expected = build_natal_fingerprint(natal)
    stored = {k: v for k, v in jan_pack["natal_reference"].items() if k != "note"}
    assert stored == expected


# ── Acceptance F: no external dependency ──────────────────────────────────

def test_f_rp_questions_are_answerable_from_serialised_json_alone(jan_pack):
    """Round-trip through JSON, then answer a timed question with no ephemeris."""
    parsed = json.loads(json.dumps(jan_pack))
    rp = {d["date"]: d["ruling_planets"] for d in parsed["days"]}["2027-01-18"]

    answer = rp_at_local_time(rp, "15:30:00")
    assert answer["day_lord"] and len(answer["rp_list"]) >= 4
    assert answer["ascendant"]["sub_lord"] and answer["moon"]["sub_lord"]


# ── Acceptance G: out-of-range disclosure ─────────────────────────────────

def test_g_dates_outside_coverage_are_absent_not_invented(jan_pack):
    covered = {d["date"] for d in jan_pack["days"]}
    assert "2027-03-01" not in covered
    assert jan_pack["valid_to"] < "2027-03-01"

    for block in jan_pack["rp_trigger_windows"]["topics"].values():
        assert all(row[0] in covered for row in block["windows"])
        assert all(row[0] in covered for row in block["days"])

    assert "out_of_range" in jan_pack["usage"]


def test_g_time_outside_the_stored_day_raises(day_rp):
    with pytest.raises(ValueError):
        rp_at_local_time(day_rp, "24:30:00")


# ── Trigger windows ───────────────────────────────────────────────────────

def test_every_kp_rules_topic_has_a_trigger_section(jan_pack):
    topics = jan_pack["rp_trigger_windows"]["topics"]
    assert set(topics) == set(EVENT_HOUSES)
    for topic, block in topics.items():
        assert block["houses"] == EVENT_HOUSES[topic]
        assert len(block["days"]) == len(jan_pack["days"])


def test_trigger_windows_only_cite_real_significators(jan_pack):
    tw = jan_pack["rp_trigger_windows"]
    assert tw["window_fields"] == WINDOW_FIELDS

    for topic, block in tw["topics"].items():
        sigs = set(block["significators"]["l1_l2"])
        houses = set(block["houses"])
        for row in block["windows"]:
            assert set(row[11]) <= sigs, topic
            assert set(row[12]) <= houses, topic
            assert row[13], "a window must record its dasha permission"
            assert row[3] in ("STRONG", "ACTIVE")
            assert _secs(row[2]) > _secs(row[1])


def test_trigger_windows_respect_dasha_permission(jan_pack):
    """A window can never appear on a day whose MD/AD/PD ignores the topic."""
    for block in jan_pack["rp_trigger_windows"]["topics"].values():
        gated = {row[0] for row in block["days"] if row[5] == "NO_GATE"}
        assert not ({row[0] for row in block["windows"]} & gated)


def test_rp_criteria_is_v2_with_diagnostics(jan_pack):
    tw = jan_pack["rp_trigger_windows"]
    assert tw["criteria"]["id"] == "rp_convergence_v2"
    assert tw["criteria"]["diagnostics_schema"] == "1.1"
    for topic, block in tw["topics"].items():
        assert "diagnostics" in block
        assert "gate_reason" in tw["day_fields"]
        assert len(block["days"][0]) == len(tw["day_fields"])
        assert block["summary"]["windows_listed"] <= block["summary"]["windows_total"]
        assert block["diagnostics"]["houses_evaluated"] == EVENT_HOUSES[topic]
        assert "days_detail" in block["diagnostics"]


def test_pack_validation_passes_with_rp_layers(jan_pack):
    val = jan_pack["validation"]
    assert val["trust_status"]["ruling_planets"] == "PASS"
    assert val["trust_status"]["rp_trigger_windows"] == "PASS"
    assert val["trust_status"]["fine_dasha_timelines"] == "PASS"
    assert val["overall"] == "PASS", val["issues"][:5]

    summary = val["rp_summary"]
    assert summary["days_with_rp"] == 31
    assert summary["reference_timezone"] == "Asia/Kolkata"
    assert summary["ascendant_intervals"] > 31 * ASC_INTERVALS_PER_DAY_MIN
    assert set(summary["trigger_windows_per_topic_listed"]) == set(EVENT_HOUSES)
    assert summary["prana_windows"] > summary["sukshma_windows"] > 0
    assert summary["rp_criteria"] == "rp_convergence_v2"
