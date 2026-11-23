"""
Natal/birth location must never be used as a silent default for dynamic calculations.
"""
from __future__ import annotations

from datetime import date

import pytest

from analysis.almanac_builder import build_almanac
from analysis.context import PredictionLocationRequired, build_prediction_context
from analysis.pack_builder import build_90day_pack
from reports.enhanced_pdf import build_enhanced_pdf
from tests.conftest import HYDERABAD, LONDON

D = date(2026, 10, 31)


@pytest.mark.parametrize("missing", ["query_lat", "query_lng", "query_tz"])
def test_context_requires_location(natal, missing):
    kwargs = {**HYDERABAD, missing: None}
    with pytest.raises(PredictionLocationRequired):
        build_prediction_context(natal, D, "09:00:00", **kwargs)


def test_almanac_requires_location(natal):
    with pytest.raises(PredictionLocationRequired):
        build_almanac(natal, from_date=D, days=1)


def test_pack_requires_location(natal):
    with pytest.raises(PredictionLocationRequired):
        build_90day_pack(natal, D, 1, "Nowhere", None, None, None)


def test_context_uses_prediction_location_not_birth(natal):
    ctx = build_prediction_context(natal, D, "09:00:00", **LONDON)
    assert ctx["query_location"] == "London, UK"
    assert ctx["query_tz"] == "Europe/London"
    assert ctx["ruling_planets"]["reference_location"] == "London, UK"
    assert ctx["ruling_planets"]["reference_tz"] == "Europe/London"
    # London sunrise in late October is ~07:00 local, Hyderabad ~06:10
    assert ctx["panchanga"]["sunrise"].startswith("06:5") or ctx["panchanga"]["sunrise"].startswith("07:")


def test_pdf_rejects_location_that_differs_from_context(natal):
    ctx = build_prediction_context(natal, D, "09:00:00", **HYDERABAD)
    with pytest.raises(ValueError):
        build_enhanced_pdf(natal, ctx, include_almanac=False, query_lat=51.5, query_lng=-0.12,
                           query_tz="Europe/London")
