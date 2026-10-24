import os
import tempfile
from pathlib import Path

import pytest

os.environ["WIND_SNAPSHOT_PATH"] = str(Path(tempfile.gettempdir()) / "wind_test_snapshot.json.gz")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import config  # noqa: E402
from backend.scripts.make_demo_snapshot import main as make_demo  # noqa: E402


@pytest.fixture(scope="module")
def client():
    make_demo()
    from backend.app.main import app
    return TestClient(app)


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta(client):
    body = client.get("/api/meta").json()
    assert body["delivery_first"] == "2026-01-02" and body["delivery_last"] == "2026-02-01"


def test_forecast_day(client):
    r = client.get("/api/forecast", params={"delivery_date": "2026-01-15", "cutoff": "09:00"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == 48
    assert body["decision_time"] == "2026-01-14T09:00:00Z"
    assert all(p["published"] <= body["decision_time"] for p in body["points"] if p["published"])


def test_forecast_rejects_out_of_scope_date(client):
    assert client.get("/api/forecast", params={"delivery_date": "2026-03-01"}).status_code == 422


def test_forecast_rejects_bad_cutoff(client):
    assert client.get("/api/forecast", params={"delivery_date": "2026-01-15", "cutoff": "9am"}).status_code == 422


def test_accuracy_modes(client):
    for mode in ("dayahead", "horizon"):
        r = client.get("/api/accuracy", params={"start": "2026-01-02", "end": "2026-01-31", "mode": mode, "horizon": 12})
        assert r.status_code == 200 and r.json()["metrics"]["n"] > 1000


def test_error_grows_with_horizon(client):
    prof = client.get("/api/horizon-profile", params={"start": "2026-01-05", "end": "2026-01-31"}).json()["profile"]
    assert prof[-1]["mae_mw"] > prof[0]["mae_mw"]
