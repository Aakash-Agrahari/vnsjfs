"""Thin client for the Elexon BMRS Insights API (no API key required)."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

import httpx

from . import config
from .data import iso, parse_ts


def _get_json(client: httpx.Client, path: str, params: dict, retries: int = 4):
    url = f"{config.ELEXON_BASE}{path}"
    for attempt in range(1, retries + 1):
        try:
            resp = client.get(url, params=params, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"Elexon returned {resp.status_code} for {resp.url}: {resp.text[:300]}")
        except httpx.TransportError:
            time.sleep(2 * attempt)
    raise RuntimeError(f"Giving up on {url} {params}")


def fetch_actuals(client: httpx.Client, first: date, last: date, chunk_days: int = 5) -> list[list]:
    """FUELHH, fuelType WIND -> [[startTime, generation_MW], ...] (half-hourly)."""
    rows: dict[str, float] = {}
    day = first
    while day <= last:
        end = min(day + timedelta(days=chunk_days - 1), last)
        data = _get_json(client, "/datasets/FUELHH/stream", {
            "settlementDateFrom": day.isoformat(),
            "settlementDateTo": end.isoformat(),
            "fuelType": "WIND",
        })
        for r in data:
            if r.get("fuelType") == "WIND":
                rows[iso(parse_ts(r["startTime"]))] = float(r["generation"])
        day = end + timedelta(days=1)
    return sorted([k, v] for k, v in rows.items())


def fetch_forecasts(client: httpx.Client, first_publish: datetime, last_publish: datetime,
                    max_horizon_h: int = config.MAX_HORIZON_H, step_hours: int = 24) -> list[list]:
    """WINDFOR -> [[startTime, publishTime, generation_MW], ...].

    Keeps only forecasts published 0..max_horizon_h before the target time; longer horizons are
    irrelevant for day-ahead decisions and would make the dataset ~7x bigger.
    """
    seen: dict[tuple[str, str], float] = {}
    cur = first_publish
    while cur < last_publish:
        nxt = min(cur + timedelta(hours=step_hours), last_publish)
        data = _get_json(client, "/datasets/WINDFOR/stream", {
            "publishDateTimeFrom": iso(cur),
            "publishDateTimeTo": iso(nxt),
        })
        for r in data:
            target, publish = parse_ts(r["startTime"]), parse_ts(r["publishTime"])
            horizon_h = (target - publish).total_seconds() / 3600
            if 0 <= horizon_h <= max_horizon_h and r.get("generation") is not None:
                seen[(iso(target), iso(publish))] = float(r["generation"])
        cur = nxt
    return sorted([t, p, g] for (t, p), g in seen.items())


def january_2026_window():
    """Returns (actual_first_day, actual_last_day, publish_from, publish_to)."""
    publish_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    publish_to = datetime(2026, 2, 1, tzinfo=timezone.utc)
    return config.DECISION_FIRST, config.DELIVERY_LAST, publish_from, publish_to
