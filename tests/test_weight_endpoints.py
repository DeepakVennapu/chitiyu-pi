import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from domains.health.router import router as health_router
from auth import verify_api_key


class _NoCloseConn:
    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(health_router)
    test_app.dependency_overrides[verify_api_key] = lambda: None
    return test_app


@pytest.fixture
def client(app, conn):
    proxy = _NoCloseConn(conn)
    with patch("domains.health.router.get_connection", return_value=proxy), \
         patch("domains.health.router.initialize_schema", return_value=None):
        with TestClient(app) as c:
            yield c, conn


def test_weight_latest_empty(client):
    c, _ = client
    resp = c.get("/health/weight/latest")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_weight_latest_returns_data(client):
    c, conn = client
    from domains.health.db import upsert_weight_log
    from utils.local_time import today_local
    today = today_local()
    upsert_weight_log(conn, 1, today, f"{today} 07:00:00", 84.6, 16.1, 54.2, 28.3, "renpho")
    resp = c.get("/health/weight/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["weight_kg"] == 84.6
    assert abs(data["weight_lbs"] - 186.5) < 0.2
    assert data["bodyfat_pct"] == 16.1
    assert "date" in data


def test_weight_latest_returns_stale_reading(client):
    c, conn = client
    from domains.health.db import upsert_weight_log
    upsert_weight_log(conn, 1, "2026-08-10", "2026-08-10 07:00:00", 85.2, 16.5, 54.0, 28.6, "renpho")
    resp = c.get("/health/weight/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-08-10"
    assert data["weight_kg"] == 85.2


def test_weight_trend_empty(client):
    c, _ = client
    resp = c.get("/health/weight/trend?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert data["logs"] == []
    assert data["avg_weight_kg"] is None
    assert data["delta_kg"] is None


def test_weight_trend_returns_logs(client):
    c, conn = client
    from domains.health.db import upsert_weight_log
    from datetime import date, timedelta
    today = date.today()
    d1 = (today - timedelta(days=3)).isoformat()
    d2 = today.isoformat()
    upsert_weight_log(conn, 1, d1, f"{d1} 07:00:00", 85.0, 16.3, 54.0, 28.5, "renpho")
    upsert_weight_log(conn, 1, d2, f"{d2} 07:00:00", 84.6, 16.1, 54.2, 28.3, "renpho")
    resp = c.get("/health/weight/trend?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["logs"]) == 2
    assert all("weight_lbs" in log for log in data["logs"])
    assert data["avg_weight_kg"] is not None
    assert data["delta_kg"] == round(84.6 - 85.0, 1)
