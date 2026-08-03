import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from domains.health.router import router as health_router
from auth import verify_api_key


SYNC_PAYLOAD = {
    "date": "2026-08-02",
    "steps": 11240,
    "sleep_deep_mins": 52,
    "sleep_total_mins": 432,
    "resting_hr": 64,
}


class _NoCloseConn:
    """Thin proxy around sqlite3.Connection that suppresses close() calls.

    The health router calls conn.close() after every request, which would destroy
    the shared in-memory test database.  This wrapper delegates everything to the
    real connection but turns close() into a no-op so the connection stays alive
    across multiple requests within a single test.
    """

    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass  # no-op — let the conftest fixture handle cleanup

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
    # Wrap conn so that router calls to conn.close() are suppressed.
    # The conftest fixture still owns the real connection and closes it on teardown.
    proxy = _NoCloseConn(conn)

    with patch("domains.health.router.get_connection", return_value=proxy), \
         patch("domains.health.router.initialize_schema", return_value=None):
        with TestClient(app) as c:
            yield c, conn


def test_health_sync_writes_row(client):
    c, conn = client
    resp = c.post("/health/sync", json=SYNC_PAYLOAD, headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    row = conn.execute(
        "SELECT * FROM health_metrics WHERE date = '2026-08-02'"
    ).fetchone()
    assert row is not None
    assert row["steps"] == 11240
    assert row["sleep_deep_mins"] == 52
    assert row["sleep_total_mins"] == 432
    assert row["resting_hr"] == 64


def test_health_sync_upserts_same_date(client):
    c, conn = client
    c.post("/health/sync", json=SYNC_PAYLOAD, headers={"X-API-Key": "test"})

    updated = {**SYNC_PAYLOAD, "steps": 12500, "resting_hr": 60}
    resp = c.post("/health/sync", json=updated, headers={"X-API-Key": "test"})
    assert resp.status_code == 200

    rows = conn.execute(
        "SELECT * FROM health_metrics WHERE date = '2026-08-02'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["steps"] == 12500
    assert rows[0]["resting_hr"] == 60


def test_health_sync_partial_payload(client):
    """Fields other than date are optional — partial sync should succeed."""
    c, _ = client
    resp = c.post(
        "/health/sync",
        json={"date": "2026-08-03", "steps": 8000},
        headers={"X-API-Key": "test"},
    )
    assert resp.status_code == 200


def test_health_sync_requires_api_key(app):
    """Without the dependency override for auth, a missing API key should return 401."""
    # Build a fresh app WITHOUT the verify_api_key override
    strict_app = FastAPI()
    strict_app.include_router(health_router)
    # Patch DB so it doesn't try to open a real file if auth somehow passes
    with patch("domains.health.router.get_connection"), \
         patch("domains.health.router.initialize_schema"):
        with TestClient(strict_app, raise_server_exceptions=False) as c:
            resp = c.post("/health/sync", json=SYNC_PAYLOAD)
    assert resp.status_code == 422  # Header missing → FastAPI 422 Unprocessable Entity
