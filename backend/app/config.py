"""Central configuration. Everything that is a business assumption lives here."""
import os
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

# Purchase decisions are made in January 2026 (one day before delivery).
DECISION_FIRST = date(2026, 1, 1)
DECISION_LAST = date(2026, 1, 31)
# Delivery day = decision day + 1  ->  2 Jan .. 1 Feb 2026
DELIVERY_FIRST = DECISION_FIRST + timedelta(days=1)
DELIVERY_LAST = DECISION_LAST + timedelta(days=1)

# Default time (UK local) on day D-1 by which the buy decision has to be made.
# Configurable from the UI because bidding deadlines differ per venue.
DEFAULT_CUTOFF = "09:00"

# Only forecasts published up to this many hours before the target are kept.
MAX_HORIZON_H = 48

ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1"

DEFAULT_SNAPSHOT = Path(__file__).resolve().parent.parent / "data" / "snapshot.json.gz"
SNAPSHOT_PATH = Path(os.getenv("WIND_SNAPSHOT_PATH", str(DEFAULT_SNAPSHOT)))
