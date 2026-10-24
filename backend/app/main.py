"""FastAPI application: thin HTTP layer over analysis.py."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import analysis, config
from .data import get_store, iso

app = FastAPI(title="Wind Desk API", version="1.0.0",
              description="Day-ahead wind forecast visibility and accuracy for GB power buyers.")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

CutoffParam = Query(config.DEFAULT_CUTOFF, pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
                    description="Decision time on day D-1, UK local, HH:MM")


def _store():
    try:
        return get_store()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _check_delivery(day: date) -> None:
    if not (config.DELIVERY_FIRST <= day <= config.DELIVERY_LAST):
        raise HTTPException(
            status_code=422,
            detail=f"Delivery date must be between {config.DELIVERY_FIRST} and {config.DELIVERY_LAST} "
                   "(decisions are made in January 2026, one day before delivery).")


def _check_range(start: date, end: date) -> None:
    _check_delivery(start)
    _check_delivery(end)
    if end < start:
        raise HTTPException(status_code=422, detail="end must not be before start")


@lru_cache(maxsize=256)
def _accuracy_cached(start: date, end: date, mode: str, cutoff: str, horizon: float) -> dict:
    return analysis.accuracy(_store(), start, end, mode, cutoff, horizon)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    store = _store()
    return {
        "source": store.meta.get("source"),
        "fetched_at": store.meta.get("fetched_at"),
        "actual_points": len(store.actuals),
        "forecast_points": sum(len(v[0]) for v in store.forecasts.values()),
        "delivery_first": config.DELIVERY_FIRST.isoformat(),
        "delivery_last": config.DELIVERY_LAST.isoformat(),
        "default_cutoff": config.DEFAULT_CUTOFF,
        "max_horizon_h": config.MAX_HORIZON_H,
    }


@app.get("/api/forecast")
def forecast(delivery_date: date, cutoff: str = CutoffParam):
    """Forecast a buyer can see at the decision time for one delivery day."""
    _check_delivery(delivery_date)
    store = _store()
    points = analysis.day_ahead_points(store, delivery_date, cutoff)
    known = [p for p in points if p["forecast_mw"] is not None]
    if not known:
        raise HTTPException(status_code=404, detail="No forecast was available at that decision time.")

    values = [p["forecast_mw"] for p in known]
    publishes = sorted({p["published"] for p in known})
    # Typical error of this same rule over the whole decision window, for context.
    window = _accuracy_cached(config.DELIVERY_FIRST, config.DELIVERY_LAST, "dayahead", cutoff, 0.0)["metrics"]

    return {
        "delivery_date": delivery_date.isoformat(),
        "cutoff": cutoff,
        "decision_time": iso(analysis.decision_time(delivery_date, cutoff)),
        "points": points,
        "summary": {
            "avg_mw": round(sum(values) / len(values), 1),
            "peak_mw": round(max(values), 1),
            "trough_mw": round(min(values), 1),
            "energy_mwh": round(sum(values) * 0.5, 1),
            "first_published": publishes[0],
            "last_published": publishes[-1],
            "periods_with_forecast": len(known),
            "periods_total": len(points),
        },
        "typical_error": {
            "mae_mw": window.get("mae_mw"),
            "p90_over_mw": window.get("p90_over_mw"),
            "p90_under_mw": window.get("p90_under_mw"),
            "bias_mw": window.get("bias_mw"),
            "basis": f"{config.DELIVERY_FIRST} to {config.DELIVERY_LAST}",
        },
    }


@app.get("/api/accuracy")
def accuracy(start: date, end: date,
             mode: Literal["dayahead", "horizon"] = "dayahead",
             cutoff: str = CutoffParam,
             horizon: float = Query(24, ge=0.5, le=config.MAX_HORIZON_H)):
    _check_range(start, end)
    return {"config": {"start": start.isoformat(), "end": end.isoformat(), "mode": mode,
                       "cutoff": cutoff, "horizon_h": horizon},
            **_accuracy_cached(start, end, mode, cutoff, float(horizon))}


@app.get("/api/horizon-profile")
def horizon_profile(start: date, end: date):
    _check_range(start, end)
    return {"profile": analysis.horizon_profile(_store(), start, end)}
