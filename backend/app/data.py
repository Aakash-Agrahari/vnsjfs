"""In-memory data store built from the JSON snapshot."""
from __future__ import annotations

import gzip
import json
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from . import config


def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (with Z or offset) to an aware UTC datetime."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class DataStore:
    meta: dict = field(default_factory=dict)
    actuals: dict[datetime, float] = field(default_factory=dict)
    # target time -> (sorted publish times, generation aligned with publish times)
    forecasts: dict[datetime, tuple[list[datetime], list[float]]] = field(default_factory=dict)

    def targets(self) -> list[datetime]:
        return sorted(self.forecasts.keys())

    def latest_forecast(self, target: datetime, published_at_or_before: datetime):
        """Latest forecast for `target` published at or before the given time.

        Returns (publish_time, mw) or None when no forecast existed yet.
        """
        entry = self.forecasts.get(target)
        if not entry:
            return None
        publishes, values = entry
        idx = bisect_right(publishes, published_at_or_before) - 1
        if idx < 0:
            return None
        return publishes[idx], values[idx]


def build_store(meta: dict, actuals: list, forecasts: list) -> DataStore:
    store = DataStore(meta=meta)
    for ts, mw in actuals:
        store.actuals[parse_ts(ts)] = float(mw)
    grouped: dict[datetime, list[tuple[datetime, float]]] = {}
    for target, publish, mw in forecasts:
        grouped.setdefault(parse_ts(target), []).append((parse_ts(publish), float(mw)))
    for target, rows in grouped.items():
        rows.sort(key=lambda r: r[0])
        store.forecasts[target] = ([r[0] for r in rows], [r[1] for r in rows])
    return store


def write_snapshot(path: Path, meta: dict, actuals: list, forecasts: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "actuals": actuals, "forecasts": forecasts}
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))


def load_snapshot(path: Path) -> DataStore:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    return build_store(payload["meta"], payload["actuals"], payload["forecasts"])


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    path = config.SNAPSHOT_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"No data snapshot at {path}. Run `python -m backend.scripts.fetch_data` "
            "(real Elexon data) or `python -m backend.scripts.make_demo_snapshot` (synthetic)."
        )
    return load_snapshot(path)
