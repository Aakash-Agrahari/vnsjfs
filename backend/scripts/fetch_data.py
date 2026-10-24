"""Download real Elexon data for January 2026 and save the snapshot the API serves.

Usage (from repo root):  python -m backend.scripts.fetch_data
"""
from datetime import datetime, timezone

import httpx

from backend.app import config
from backend.app.data import write_snapshot
from backend.app.elexon import fetch_actuals, fetch_forecasts, january_2026_window


def main() -> None:
    first_day, last_day, pub_from, pub_to = january_2026_window()
    with httpx.Client(headers={"Accept": "application/json"}) as client:
        print(f"Fetching FUELHH (WIND) {first_day} -> {last_day} ...")
        actuals = fetch_actuals(client, first_day, last_day)
        print(f"  {len(actuals)} half-hourly actuals")
        print(f"Fetching WINDFOR published {pub_from:%Y-%m-%d} -> {pub_to:%Y-%m-%d} (this takes a minute) ...")
        forecasts = fetch_forecasts(client, pub_from, pub_to)
        print(f"  {len(forecasts)} forecast rows kept (horizon 0-{config.MAX_HORIZON_H}h)")
    if not actuals or not forecasts:
        raise SystemExit("Elexon returned no data - check the endpoint parameters in backend/app/elexon.py")
    meta = {"source": "elexon", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "datasets": ["FUELHH", "WINDFOR"]}
    write_snapshot(config.SNAPSHOT_PATH, meta, actuals, forecasts)
    print(f"Saved snapshot -> {config.SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
