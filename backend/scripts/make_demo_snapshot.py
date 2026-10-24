"""Create a SYNTHETIC snapshot so the app can be explored without network access.

The UI shows a visible 'synthetic data' banner for this file. Never use it for real conclusions.
Usage (from repo root):  python -m backend.scripts.make_demo_snapshot
"""
import math
import random
from datetime import datetime, timedelta, timezone

from backend.app import config
from backend.app.data import iso, write_snapshot


def main(seed: int = 7) -> None:
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 2, tzinfo=timezone.utc)

    # "True" wind: slow weather regimes + daily wiggle, 1.5-17 GW
    actual: dict[datetime, float] = {}
    level, t = 8000.0, start
    while t < end:
        level += rnd.gauss(0, 120) - (level - 8500) * 0.01
        level = min(max(level, 1500), 16500)
        actual[t] = max(0.0, level + 600 * math.sin(t.hour / 24 * 2 * math.pi) + rnd.gauss(0, 150))
        t += timedelta(minutes=30)

    forecasts = []
    pub = start
    while pub < datetime(2026, 2, 1, tzinfo=timezone.utc):
        tgt = pub.replace(minute=0) + timedelta(hours=1)
        while (tgt - pub).total_seconds() / 3600 <= config.MAX_HORIZON_H:
            if tgt in actual:
                h = (tgt - pub).total_seconds() / 3600
                noise = rnd.gauss(0, 150 + 70 * h)  # error grows with horizon
                forecasts.append([iso(tgt), iso(pub), round(max(0.0, actual[tgt] * 1.01 + noise), 1)])
            tgt += timedelta(minutes=30)
        pub += timedelta(hours=1)

    actuals = [[iso(k), round(v, 1)] for k, v in sorted(actual.items())]
    meta = {"source": "synthetic", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    write_snapshot(config.SNAPSHOT_PATH, meta, actuals, forecasts)
    print(f"Wrote {len(actuals)} actuals, {len(forecasts)} forecasts -> {config.SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
