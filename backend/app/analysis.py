"""Pure analysis functions: forecast selection and error metrics.

Sign convention: error = forecast - actual.
  error > 0  -> forecast OVER-stated wind (buyer is short of power -> must buy more later)
  error < 0  -> forecast UNDER-stated wind (buyer over-bought)
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone

from . import config
from .data import DataStore, iso

HALF_HOUR = timedelta(minutes=30)


# ---------- time helpers ----------
def parse_cutoff(value: str) -> time:
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("cutoff must look like HH:MM") from exc


def decision_time(delivery_day: date, cutoff: str) -> datetime:
    """UTC instant of the buy decision: day D-1 at `cutoff` UK local time."""
    local = datetime.combine(delivery_day - timedelta(days=1), parse_cutoff(cutoff), tzinfo=config.LONDON)
    return local.astimezone(timezone.utc)


def day_window(day: date) -> tuple[datetime, datetime]:
    """[start, end) of a UK local day in UTC."""
    start = datetime.combine(day, time(0, 0), tzinfo=config.LONDON).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=config.LONDON).astimezone(timezone.utc)
    return start, end


def iter_targets(start: datetime, end: datetime):
    t = start
    while t < end:
        yield t
        t += HALF_HOUR


# ---------- statistics ----------
def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    k = (len(v) - 1) * p / 100.0
    lo = math.floor(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def metrics(errors: list[float], actuals: list[float]) -> dict:
    n = len(errors)
    if n == 0:
        return {"n": 0}
    abs_err = [abs(e) for e in errors]
    mae = sum(abs_err) / n
    mean_actual = sum(actuals) / n
    p10 = percentile(errors, 10)
    p90 = percentile(errors, 90)
    return {
        "n": n,
        "mean_actual_mw": round(mean_actual, 1),
        "mae_mw": round(mae, 1),
        "rmse_mw": round(math.sqrt(sum(e * e for e in errors) / n), 1),
        "bias_mw": round(sum(errors) / n, 1),
        "nmae_pct": round(100 * mae / mean_actual, 1) if mean_actual else None,
        "p50_abs_mw": round(percentile(abs_err, 50), 1),
        "p90_abs_mw": round(percentile(abs_err, 90), 1),
        "p95_abs_mw": round(percentile(abs_err, 95), 1),
        # Risk numbers a buyer cares about:
        "p90_over_mw": round(max(p90, 0.0), 1),   # forecast too high by at least this in 10% of periods
        "p90_under_mw": round(max(-p10, 0.0), 1),  # forecast too low by at least this in 10% of periods
        "over_share_pct": round(100 * sum(1 for e in errors if e > 0) / n, 1),
    }


# ---------- forecast selection ----------
def day_ahead_points(store: DataStore, delivery_day: date, cutoff: str) -> list[dict]:
    """For each half-hour of the delivery day: latest forecast known at decision time."""
    decided_at = decision_time(delivery_day, cutoff)
    start, end = day_window(delivery_day)
    points = []
    for t in iter_targets(start, end):
        hit = store.latest_forecast(t, decided_at)
        points.append({
            "t": iso(t),
            "forecast_mw": hit[1] if hit else None,
            "published": iso(hit[0]) if hit else None,
            "actual_mw": store.actuals.get(t),
        })
    return points


def collect_pairs(store: DataStore, start_day: date, end_day: date, mode: str,
                  cutoff: str, horizon_h: float) -> list[dict]:
    """(forecast, actual) pairs for all targets in [start_day, end_day]."""
    rows = []
    start, _ = day_window(start_day)
    _, end = day_window(end_day)
    for t in iter_targets(start, end):
        actual = store.actuals.get(t)
        if actual is None:
            continue
        if mode == "dayahead":
            local_day = t.astimezone(config.LONDON).date()
            hit = store.latest_forecast(t, decision_time(local_day, cutoff))
        else:  # fixed horizon: latest forecast published at least `horizon_h` before target
            hit = store.latest_forecast(t, t - timedelta(hours=horizon_h))
        if hit is None:
            continue
        rows.append({"t": t, "forecast": hit[1], "actual": actual, "published": hit[0],
                     "error": hit[1] - actual})
    return rows


def accuracy(store: DataStore, start_day: date, end_day: date, mode: str,
             cutoff: str, horizon_h: float) -> dict:
    pairs = collect_pairs(store, start_day, end_day, mode, cutoff, horizon_h)
    errors = [p["error"] for p in pairs]
    actuals = [p["actual"] for p in pairs]

    by_hour: dict[int, list[dict]] = {}
    by_day: dict[date, list[dict]] = {}
    for p in pairs:
        local = p["t"].astimezone(config.LONDON)
        by_hour.setdefault(local.hour, []).append(p)
        by_day.setdefault(local.date(), []).append(p)

    def summarise(rows: list[dict]) -> dict:
        e = [r["error"] for r in rows]
        return {"n": len(e), "mae_mw": round(sum(abs(x) for x in e) / len(e), 1),
                "bias_mw": round(sum(e) / len(e), 1)}

    return {
        "metrics": metrics(errors, actuals),
        "series": [{"t": iso(p["t"]), "forecast_mw": p["forecast"], "actual_mw": p["actual"],
                    "error_mw": round(p["error"], 1)} for p in pairs],
        "by_hour": [{"hour": h, **summarise(rows)} for h, rows in sorted(by_hour.items())],
        "by_day": [{"date": d.isoformat(), **summarise(rows)} for d, rows in sorted(by_day.items())],
        "histogram": histogram(errors),
    }


def histogram(errors: list[float], width: float = 500.0) -> list[dict]:
    if not errors:
        return []
    lo = math.floor(min(errors) / width) * width
    hi = math.floor(max(errors) / width) * width
    bins = {lo + i * width: 0 for i in range(int((hi - lo) / width) + 1)}
    for e in errors:
        bins[math.floor(e / width) * width] += 1
    return [{"from_mw": b, "to_mw": b + width, "count": c} for b, c in sorted(bins.items())]


def horizon_profile(store: DataStore, start_day: date, end_day: date,
                    max_h: int = config.MAX_HORIZON_H) -> list[dict]:
    """Error statistics as a function of how far ahead the forecast was made."""
    start, _ = day_window(start_day)
    _, end = day_window(end_day)
    targets = [t for t in iter_targets(start, end) if t in store.actuals]
    out = []
    for h in range(1, max_h + 1):
        errs, acts = [], []
        for t in targets:
            hit = store.latest_forecast(t, t - timedelta(hours=h))
            if hit is None:
                continue
            errs.append(hit[1] - store.actuals[t])
            acts.append(store.actuals[t])
        if errs:
            m = metrics(errs, acts)
            out.append({"horizon_h": h, "n": m["n"], "mae_mw": m["mae_mw"],
                        "rmse_mw": m["rmse_mw"], "bias_mw": m["bias_mw"],
                        "p90_abs_mw": m["p90_abs_mw"]})
    return out
