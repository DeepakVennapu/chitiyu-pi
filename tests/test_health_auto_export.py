# tests/test_health_auto_export.py
"""Tests for the Health Auto Export integration endpoint and partial-upsert fix."""
from __future__ import annotations

import sys, os

os.environ.setdefault("API_KEY", "testkey")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations.health_auto_export_router import router as hae_router, _get_conn
from auth import verify_api_key
from domains.health.db import upsert_health_metrics, get_metrics_for_date

HEADERS = {"X-API-Key": "testkey"}

HAE_PAYLOAD = {
    "data": {
        "metrics": [
            {
                "name": "step_count",
                "units": "count",
                "data": [
                    {"date": "2026-08-08 00:00:00 +0000", "qty": 8234},
                ],
            },
            {
                "name": "resting_heart_rate",
                "units": "bpm",
                "data": [
                    {"date": "2026-08-08 00:00:00 +0000", "qty": 58},
                    {"date": "2026-08-08 00:00:00 +0000", "qty": 62},
                ],
            },
            {
                "name": "sleep_analysis",
                "units": "hr",
                "data": [
                    {"date": "2026-08-08 00:00:00 +0000", "qty": 1.5, "value": "asleep_deep"},
                    {"date": "2026-08-08 00:00:00 +0000", "qty": 3.0, "value": "asleep_core"},
                    {"date": "2026-08-08 00:00:00 +0000", "qty": 1.0, "value": "asleep_rem"},
                ],
            },
        ]
    }
}


@pytest.fixture
def app(conn):
    a = FastAPI()
    a.include_router(hae_router)
    a.dependency_overrides[verify_api_key] = lambda: None
    a.dependency_overrides[_get_conn] = lambda: conn
    return a


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_hae_parses_steps(client, conn):
    resp = client.post("/integrations/health-auto-export", json=HAE_PAYLOAD, headers=HEADERS)
    assert resp.status_code == 200
    row = get_metrics_for_date(conn, 1, "2026-08-08")
    assert row is not None
    assert row["steps"] == 8234


def test_hae_averages_resting_hr(client, conn):
    client.post("/integrations/health-auto-export", json=HAE_PAYLOAD, headers=HEADERS)
    row = get_metrics_for_date(conn, 1, "2026-08-08")
    assert row["resting_hr"] == 60  # (58+62)/2 = 60


def test_hae_sums_sleep_total(client, conn):
    client.post("/integrations/health-auto-export", json=HAE_PAYLOAD, headers=HEADERS)
    row = get_metrics_for_date(conn, 1, "2026-08-08")
    # 1.5 + 3.0 + 1.0 = 5.5 hrs * 60 = 330 mins
    assert row["sleep_total_mins"] == 330


def test_hae_sums_deep_sleep(client, conn):
    client.post("/integrations/health-auto-export", json=HAE_PAYLOAD, headers=HEADERS)
    row = get_metrics_for_date(conn, 1, "2026-08-08")
    # Only asleep_deep: 1.5 hrs * 60 = 90 mins
    assert row["sleep_deep_mins"] == 90


def test_hae_returns_dates_synced(client):
    resp = client.post("/integrations/health-auto-export", json=HAE_PAYLOAD, headers=HEADERS)
    data = resp.json()
    assert data["ok"] is True
    assert data["dates_synced"] == 1
    assert "2026-08-08" in data["dates"]


def test_hae_handles_multi_day(client, conn):
    payload = {
        "data": {
            "metrics": [
                {
                    "name": "step_count",
                    "units": "count",
                    "data": [
                        {"date": "2026-08-07 00:00:00 +0000", "qty": 7000},
                        {"date": "2026-08-08 00:00:00 +0000", "qty": 9000},
                    ],
                }
            ]
        }
    }
    resp = client.post("/integrations/health-auto-export", json=payload, headers=HEADERS)
    assert resp.json()["dates_synced"] == 2
    assert get_metrics_for_date(conn, 1, "2026-08-07")["steps"] == 7000
    assert get_metrics_for_date(conn, 1, "2026-08-08")["steps"] == 9000


def test_hae_empty_payload(client):
    resp = client.post("/integrations/health-auto-export", json={"data": {"metrics": []}}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["dates_synced"] == 0


# ---------------------------------------------------------------------------
# Partial upsert fix: confirm that syncing steps doesn't wipe prior sleep data
# ---------------------------------------------------------------------------

def test_partial_upsert_preserves_other_fields(conn):
    """Steps-only sync must not clear sleep/HR written in a prior sync."""
    upsert_health_metrics(conn, 1, "2026-08-08", None, 55, 360, 62)
    upsert_health_metrics(conn, 1, "2026-08-08", 10000, None, None, None)

    row = get_metrics_for_date(conn, 1, "2026-08-08")
    assert row["steps"] == 10000
    assert row["sleep_deep_mins"] == 55
    assert row["sleep_total_mins"] == 360
    assert row["resting_hr"] == 62


def test_partial_upsert_overwrites_existing_field(conn):
    upsert_health_metrics(conn, 1, "2026-08-08", 8000, 50, 300, 65)
    upsert_health_metrics(conn, 1, "2026-08-08", 9500, None, None, None)

    row = get_metrics_for_date(conn, 1, "2026-08-08")
    assert row["steps"] == 9500
    assert row["resting_hr"] == 65  # unchanged
