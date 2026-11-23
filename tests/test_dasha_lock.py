"""
MD/AD/PD are locked in natal_ref and only ever looked up.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta

from analysis.dasha_fine import get_dasha_state
from analysis.vimshottari import (
    SOURCE_DERIVED, SOURCE_LOCKED_TABLE, SOURCE_UNAVAILABLE, parse_dt, resolve_dasha,
)
from tests.conftest import LOCK_DT


def test_locked_periods_contiguous_and_cover_window(natal):
    rows = natal["dasha"]["locked_periods"]
    assert rows
    for a, b in zip(rows, rows[1:]):
        assert a["pd_end"] == b["pd_start"], (a, b)
    assert parse_dt(rows[0]["pd_start"]) <= LOCK_DT - timedelta(days=365)
    assert parse_dt(rows[-1]["pd_end"]) >= LOCK_DT + timedelta(days=6 * 365)


def test_locked_md_ad_pd_agree_with_table(natal):
    d = natal["dasha"]
    r = resolve_dasha(natal, LOCK_DT)
    assert r["source"] == SOURCE_LOCKED_TABLE
    for lvl in ("md", "ad", "pd"):
        assert r[lvl]["lord"] == d[f"locked_{lvl}"]["lord"]
        assert r[lvl]["start"] == d[f"locked_{lvl}"]["start"]


def test_lookup_changes_exactly_at_pd_boundary(natal):
    rows = natal["dasha"]["locked_periods"]
    boundary = parse_dt(rows[10]["pd_end"])
    before = resolve_dasha(natal, boundary - timedelta(seconds=1))
    after = resolve_dasha(natal, boundary)
    assert before["pd"]["lord"] == rows[10]["pd"]
    assert after["pd"]["lord"] == rows[11]["pd"]


def test_table_is_used_even_if_timeline_is_tampered(natal):
    tampered = copy.deepcopy(natal)
    for m in tampered["dasha"]["full_timeline"]:
        m["lord"] = "Ketu"
    q = LOCK_DT + timedelta(days=200)
    assert resolve_dasha(tampered, q) == resolve_dasha(natal, q)


def test_old_natal_without_table_is_derived_and_flagged(natal):
    old = copy.deepcopy(natal)
    del old["dasha"]["locked_periods"]
    q = LOCK_DT + timedelta(days=400)
    r = resolve_dasha(old, q)
    assert r["source"] == SOURCE_DERIVED
    assert r["pd"]["lord"] == resolve_dasha(natal, q)["pd"]["lord"]


def test_unavailable_when_no_dasha(natal):
    empty = {k: v for k, v in natal.items() if k != "dasha"}
    assert resolve_dasha(empty, LOCK_DT)["source"] == SOURCE_UNAVAILABLE


def test_sukshma_and_prana_sit_inside_locked_pd(natal):
    q = LOCK_DT + timedelta(days=17, hours=5)
    r = resolve_dasha(natal, q)
    st = get_dasha_state(r["md"], r["ad"], r["pd"], q)
    assert st["pd_lord"] == r["pd"]["lord"]
    assert st["sukshma_lord"] and st["prana_lord"]
    assert r["pd"]["start"] <= st["sukshma_start"] <= q.strftime("%Y-%m-%d") <= st["sukshma_end"] <= r["pd"]["end"]
