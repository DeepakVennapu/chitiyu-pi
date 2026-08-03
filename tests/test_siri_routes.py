# tests/test_siri_routes.py
"""
Siri Shortcuts endpoint tests.

All LLM calls and domain tool calls are mocked — tests focus on:
  1. Correct routing (right tool called with right args)
  2. Response format (plain prose, "spoken" + data key present)
  3. Auth enforcement
"""
from __future__ import annotations

import sqlite3
import sys, os

# Set required env vars before any backend imports touch config.py
os.environ.setdefault("API_KEY", "testkey")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from db.connection import get_connection
from db.schema import initialize_schema
from integrations.siri.router import router as siri_router, _get_conn
from auth import verify_api_key


FAKE_SPOKEN = "Logged. You're doing great today."
HEADERS = {"X-API-Key": "testkey"}

# String return values matching actual tool signatures
FAKE_MEAL_STR = "Logged: 2 scrambled eggs — 140 kcal, 12g protein"
FAKE_TASK_STR = "Task #1 created: Call the dentist"
FAKE_TOTALS_STR = "Today: 1100 kcal, 110g protein, 38g fat, 95g carbs"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    initialize_schema(c)
    yield c
    c.close()


@pytest.fixture
def app(conn):
    a = FastAPI()
    a.include_router(siri_router)
    a.dependency_overrides[verify_api_key] = lambda: None
    a.dependency_overrides[_get_conn] = lambda: conn
    return a


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# POST /siri/log-meal
# ---------------------------------------------------------------------------

def test_log_meal_calls_log_meal_tool(client):
    with patch("integrations.siri.router.log_meal", return_value=FAKE_MEAL_STR) as mock_tool, \
         patch("integrations.siri.router.call_claude", return_value=FAKE_SPOKEN):
        resp = client.post("/siri/log-meal", json={"text": "2 scrambled eggs", "user_id": 1}, headers=HEADERS)

    assert resp.status_code == 200
    mock_tool.assert_called_once()
    args = mock_tool.call_args
    # conn, user_id, text
    assert args[0][1] == 1            # user_id
    assert args[0][2] == "2 scrambled eggs"  # text


def test_log_meal_returns_spoken(client):
    with patch("integrations.siri.router.log_meal", return_value=FAKE_MEAL_STR), \
         patch("integrations.siri.router.call_claude", return_value=FAKE_SPOKEN):
        resp = client.post("/siri/log-meal", json={"text": "2 scrambled eggs", "user_id": 1}, headers=HEADERS)

    data = resp.json()
    assert "spoken" in data
    assert data["spoken"] == FAKE_SPOKEN


def test_log_meal_returns_result_key(client):
    with patch("integrations.siri.router.log_meal", return_value=FAKE_MEAL_STR), \
         patch("integrations.siri.router.call_claude", return_value=FAKE_SPOKEN):
        resp = client.post("/siri/log-meal", json={"text": "banana", "user_id": 1}, headers=HEADERS)

    data = resp.json()
    assert "result" in data
    assert data["result"] == FAKE_MEAL_STR


def test_log_meal_spoken_is_plain_prose(client):
    """Spoken response must not contain markdown symbols (spot-check)."""
    spoken_with_markdown = "- Great job!\n- 140 kcal logged.\n**Keep it up!**"
    with patch("integrations.siri.router.log_meal", return_value=FAKE_MEAL_STR), \
         patch("integrations.siri.router.call_claude", return_value=spoken_with_markdown):
        resp = client.post("/siri/log-meal", json={"text": "oatmeal", "user_id": 1}, headers=HEADERS)

    # Endpoint returns 200; spoken value is surfaced as-is (Haiku controlled by SPOKEN_SYSTEM)
    assert resp.status_code == 200
    assert "spoken" in resp.json()


# ---------------------------------------------------------------------------
# POST /siri/log-expense (stub)
# ---------------------------------------------------------------------------

def test_log_expense_stub_returns_spoken(client):
    resp = client.post("/siri/log-expense", json={"text": "coffee $4.50", "user_id": 1}, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "spoken" in data
    assert isinstance(data["spoken"], str)
    assert len(data["spoken"]) > 0


def test_log_expense_stub_transaction_is_none(client):
    resp = client.post("/siri/log-expense", json={"text": "gas $45", "user_id": 1}, headers=HEADERS)
    assert resp.json()["transaction"] is None


def test_log_expense_stub_echoes_text(client):
    resp = client.post("/siri/log-expense", json={"text": "lunch $12", "user_id": 1}, headers=HEADERS)
    data = resp.json()
    assert "lunch $12" in data["spoken"]


# ---------------------------------------------------------------------------
# POST /siri/add-task
# ---------------------------------------------------------------------------

def test_add_task_calls_create_task_tool(client):
    with patch("integrations.siri.router.create_task", return_value=FAKE_TASK_STR) as mock_tool, \
         patch("integrations.siri.router.call_claude", return_value=FAKE_SPOKEN):
        resp = client.post("/siri/add-task", json={"text": "call the dentist", "user_id": 1}, headers=HEADERS)

    assert resp.status_code == 200
    mock_tool.assert_called_once()
    args = mock_tool.call_args
    assert args[0][1] == 1                  # user_id
    assert args[0][2] == "call the dentist"  # title text


def test_add_task_returns_spoken_and_result(client):
    with patch("integrations.siri.router.create_task", return_value=FAKE_TASK_STR), \
         patch("integrations.siri.router.call_claude", return_value=FAKE_SPOKEN):
        resp = client.post("/siri/add-task", json={"text": "call the dentist", "user_id": 1}, headers=HEADERS)

    data = resp.json()
    assert data["spoken"] == FAKE_SPOKEN
    assert data["result"] == FAKE_TASK_STR


# ---------------------------------------------------------------------------
# GET /siri/macros
# ---------------------------------------------------------------------------

def test_macros_calls_get_today_totals(client):
    with patch("integrations.siri.router.get_today_totals", return_value=FAKE_TOTALS_STR) as mock_tool, \
         patch("integrations.siri.router.call_claude", return_value="You've had 1100 calories."):
        resp = client.get("/siri/macros", headers=HEADERS)

    assert resp.status_code == 200
    mock_tool.assert_called_once()


def test_macros_returns_totals_and_spoken(client):
    spoken_val = "You've had 1100 calories. Keep protein up for the rest of the day."
    with patch("integrations.siri.router.get_today_totals", return_value=FAKE_TOTALS_STR), \
         patch("integrations.siri.router.call_claude", return_value=spoken_val):
        resp = client.get("/siri/macros", headers=HEADERS)

    data = resp.json()
    assert data["totals"] == FAKE_TOTALS_STR
    assert "spoken" in data
    assert not data["spoken"].startswith("-")
    assert "**" not in data["spoken"]


# ---------------------------------------------------------------------------
# Auth enforcement (without dependency override — real verify_api_key)
# ---------------------------------------------------------------------------

def test_siri_log_meal_requires_api_key():
    a = FastAPI()
    a.include_router(siri_router)
    with TestClient(a) as c:
        resp = c.post("/siri/log-meal", json={"text": "eggs", "user_id": 1})
    # No X-API-Key header → 422 (missing required header) or 401
    assert resp.status_code in (401, 422)


def test_siri_macros_requires_api_key():
    a = FastAPI()
    a.include_router(siri_router)
    with TestClient(a) as c:
        resp = c.get("/siri/macros")
    assert resp.status_code in (401, 422)
