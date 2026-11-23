"""Unified Calculation & Evidence PDF — natal tables + enhanced evidence, no AI."""
from __future__ import annotations

from datetime import date

from analysis.context import build_prediction_context
from reports.unified_pdf import build_unified_pdf
from schemas.event_houses import ALL_TOPICS

HYDERABAD = dict(
    query_location="Hyderabad, India",
    query_lat=17.385,
    query_lng=78.4867,
    query_tz="Asia/Kolkata",
)


def test_unified_pdf_builds_without_ai_and_without_chart_result(natal):
    ctx = build_prediction_context(
        natal, date(2026, 11, 22), "09:00:00",
        query_mode="LONG_TERM", topics=list(ALL_TOPICS), **HYDERABAD,
    )
    buf = build_unified_pdf(
        natal, ctx, chart_result=None, almanac_days=3, topics=list(ALL_TOPICS),
        include_almanac=True, **{k: HYDERABAD[k] for k in ("query_lat", "query_lng", "query_tz")},
    )
    data = buf.getvalue()
    assert data.startswith(b"%PDF")
    assert len(data) > 15_000
    # No AI summary path is required — build succeeds with no OpenAI.


def test_unified_pdf_rejects_missing_prediction_location(natal):
    from analysis.context import PredictionLocationRequired
    import pytest

    ctx = build_prediction_context(
        natal, date(2026, 11, 22), "09:00:00",
        query_mode="LONG_TERM", **HYDERABAD,
    )
    # Strip location from a shallow copy so the builder's guard fires.
    bad = dict(ctx)
    bad["query_lat"] = None
    with pytest.raises(PredictionLocationRequired):
        build_unified_pdf(natal, bad, almanac_days=1, include_almanac=False)
