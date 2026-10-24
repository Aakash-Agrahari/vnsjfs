from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app import analysis
from backend.app.data import build_store, iso

UTC = timezone.utc


def make_store():
    """Target 2026-01-10 12:00Z has three forecasts published at 08:00, 10:00 on D-1 and 06:00 on D."""
    target = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
    fc = [
        [iso(target), iso(datetime(2026, 1, 9, 8, 0, tzinfo=UTC)), 5000],
        [iso(target), iso(datetime(2026, 1, 9, 10, 0, tzinfo=UTC)), 6000],
        [iso(target), iso(datetime(2026, 1, 10, 6, 0, tzinfo=UTC)), 7000],
    ]
    return build_store({"source": "test"}, [[iso(target), 6500]], fc), target


def test_decision_time_is_previous_day_at_cutoff():
    assert analysis.decision_time(date(2026, 1, 10), "09:00") == datetime(2026, 1, 9, 9, 0, tzinfo=UTC)


def test_cutoff_excludes_forecasts_published_after_decision():
    store, target = make_store()
    pts = analysis.day_ahead_points(store, date(2026, 1, 10), "09:00")
    p = next(p for p in pts if p["t"] == iso(target))
    assert p["forecast_mw"] == 5000          # the 10:00 forecast was not yet published
    p2 = next(p for p in analysis.day_ahead_points(store, date(2026, 1, 10), "10:30") if p["t"] == iso(target))
    assert p2["forecast_mw"] == 6000


def test_no_forecast_available_gives_none():
    store, target = make_store()
    pts = analysis.day_ahead_points(store, date(2026, 1, 10), "07:00")
    assert next(p for p in pts if p["t"] == iso(target))["forecast_mw"] is None


def test_horizon_mode_uses_latest_forecast_at_least_h_before_target():
    store, target = make_store()
    # 24h before target = 9 Jan 12:00 -> latest published <= that is 10:00 (6000)
    pairs = analysis.collect_pairs(store, date(2026, 1, 10), date(2026, 1, 10), "horizon", "09:00", 24)
    assert pairs[0]["forecast"] == 6000
    pairs = analysis.collect_pairs(store, date(2026, 1, 10), date(2026, 1, 10), "horizon", "09:00", 6)
    assert pairs[0]["forecast"] == 7000


def test_error_sign_over_forecast_is_positive():
    store, _ = make_store()
    res = analysis.accuracy(store, date(2026, 1, 10), date(2026, 1, 10), "dayahead", "10:30", 24)
    assert res["metrics"]["bias_mw"] == -500        # 6000 forecast vs 6500 actual -> under-forecast
    assert res["metrics"]["mae_mw"] == 500


def test_metrics_basic():
    m = analysis.metrics([100, -100, 300, -300], [1000] * 4)
    assert m["mae_mw"] == 200 and m["bias_mw"] == 0
    assert m["rmse_mw"] == pytest.approx(223.6, abs=0.1)
    assert m["nmae_pct"] == 20.0
    assert m["over_share_pct"] == 50.0


def test_percentile_interpolates():
    assert analysis.percentile([1, 2, 3, 4], 50) == 2.5
    assert analysis.percentile([], 90) is None


def test_histogram_bins_cover_range():
    h = analysis.histogram([-600, 10, 20, 700])
    assert sum(b["count"] for b in h) == 4
    assert h[0]["from_mw"] == -1000 and h[-1]["from_mw"] == 500


def test_horizon_profile_shape():
    store, _ = make_store()
    prof = analysis.horizon_profile(store, date(2026, 1, 10), date(2026, 1, 10), max_h=30)
    by_h = {p["horizon_h"]: p for p in prof}
    assert by_h[1]["mae_mw"] == 500  # 7000 vs 6500
    assert by_h[26]["mae_mw"] == 500    # 10:00 D-1 forecast (6000) is the latest one >= 26h ahead
    assert by_h[27]["mae_mw"] == 1500   # only the 08:00 D-1 forecast (5000) is >= 27h ahead
    assert 30 not in by_h               # nothing had been published 30h ahead
