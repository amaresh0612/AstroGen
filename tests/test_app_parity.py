"""
analysis/* must reproduce app.py (the KP source of truth) exactly.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from analysis.cuspal_houses import house_from_longitude
from analysis.kp_constants import NAK_WIDTH, VIMSHOTTARI_ORDER, VIMSHOTTARI_TOTAL, VIMSHOTTARI_YEARS, nak_star_sub
from analysis.nakshatra_utils import get_nakshatra_and_pada
from analysis.vimshottari import mahadasha_timeline, subdivide


def _sub_boundaries() -> list[float]:
    """Every KP sub-lord boundary in the zodiac, plus points just either side."""
    pts = []
    for n in range(27):
        start = n * NAK_WIDTH
        si = VIMSHOTTARI_ORDER.index(nak_star_sub(start + 1e-9)[1])
        cum = 0.0
        for i in range(9):
            cum += VIMSHOTTARI_YEARS[(si + i) % 9] / VIMSHOTTARI_TOTAL * NAK_WIDTH
            b = start + cum
            pts += [b - 1e-7, b, b + 1e-7]
    return [p % 360.0 for p in pts]


SWEEP = [i * 0.01 for i in range(36000)]


def test_app_not_in_legacy_dasha_mode(app_fns):
    assert app_fns["LEGACY_KP_DASHA"] is False, "update analysis/vimshottari.py if legacy mode is enabled"


@pytest.mark.parametrize("lons", [SWEEP, _sub_boundaries()], ids=["sweep_0.01deg", "sub_boundaries"])
def test_sublord_matches_app(app_fns, lons):
    bad = [(lon, nak_star_sub(lon)[2], app_fns["get_sublord_kp_standard"](lon))
           for lon in lons if nak_star_sub(lon)[2] != app_fns["get_sublord_kp_standard"](lon)]
    assert not bad, bad[:5]


def test_nakshatra_pada_matches_app(app_fns):
    pts = SWEEP + [n * NAK_WIDTH / 4 + d for n in range(108) for d in (-1e-7, 0.0, 1e-7)]
    bad = [p for p in pts if get_nakshatra_and_pada(p) != tuple(app_fns["get_nakshatra_and_pada"](p))]
    assert not bad, bad[:5]


def test_cuspal_house_matches_app(app_fns):
    cusps_sets = [
        [10.0 + 30 * i for i in range(12)],
        [355.2, 22.9, 51.0, 80.4, 112.7, 146.3, 175.2, 202.9, 231.0, 260.4, 292.7, 326.3],
        [201.5, 229.0, 259.8, 291.3, 322.0, 350.1, 21.5, 49.0, 79.8, 111.3, 142.0, 170.1],
    ]
    for cusps in cusps_sets:
        for lon in [i * 0.25 for i in range(1440)] + [c for c in cusps]:
            assert house_from_longitude(lon, cusps) == app_fns["get_house_number_from_degree"](lon, cusps), (lon, cusps)


@pytest.mark.parametrize("moon_lon,birth", [
    (0.0, datetime(1970, 1, 1, 0, 0)),
    (123.4567, datetime(1989, 12, 6, 5, 45)),
    (359.9999, datetime(2001, 7, 9, 23, 59)),
    (213.3333333, datetime(1992, 3, 15, 10, 30)),
])
def test_dasha_tree_matches_app(app_fns, moon_lon, birth):
    app_md = app_fns["calculate_vimshottari_dasha"](moon_lon, birth)
    ours = mahadasha_timeline(moon_lon, birth)
    assert [(m["lord"], m["start"], m["end"]) for m in ours] == \
           [(m["lord"], m["start"], m["end"]) for m in app_md]

    for app_m, our_m in zip(app_md, ours):
        app_ads = app_fns["compute_antardashas"](app_m)
        our_ads = subdivide(our_m["lord"], our_m["start"], our_m["end"], our_m["years"])
        assert [(a["lord"], a["start"], a["end"]) for a in our_ads] == \
               [(a["lord"], a["start"], a["end"]) for a in app_ads]
        for app_a, our_a in zip(app_ads[:3], our_ads[:3]):
            app_pds = app_fns["compute_pratyantardashas"](app_a)
            our_pds = subdivide(our_a["lord"], our_a["start"], our_a["end"], our_a["years"])
            assert [(p["lord"], p["start"], p["end"]) for p in our_pds] == \
                   [(p["lord"], p["start"], p["end"]) for p in app_pds]
