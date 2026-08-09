import sys, os, json

# Set required env vars before any backend imports touch config.py
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

mock_sched = MagicMock()
mock_sched.start.return_value = None
mock_sched.shutdown.return_value = None

with patch("scheduler.build_scheduler", return_value=mock_sched):
    import main

import auth
auth.API_KEY = "test"


class _NoCloseConn:
    """Proxy that suppresses conn.close() so the shared in-memory test DB survives router requests."""
    def __init__(self, conn):
        self._conn = conn
    def close(self):
        pass
    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture
def client(conn):
    proxy = _NoCloseConn(conn)
    with patch("orchestrator.chat_router._conn", return_value=proxy):
        yield TestClient(main.app)


# ── Router-level tests (mock build_chat_response) ────────────────────────────

def test_chat_pure_query(client):
    """A question with no loggable data returns prose only, no domain previews."""
    with patch("orchestrator.chat.build_chat_response") as mock_build:
        mock_build.return_value = {
            "prose": "You have $460 discretionary left.",
            "domains": [],
            "actions": [{"label": "Log as task", "domain": "tasks", "prefill": "Check budget"}],
        }
        resp = client.post("/chat", json={"text": "Do I have budget for a watch?"},
                           headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["prose"] != ""
    assert data["domains"] == []


def test_chat_meal_only(client):
    with patch("orchestrator.chat.build_chat_response") as mock_build:
        mock_build.return_value = {
            "prose": "",
            "domains": [{"domain": "health", "preview": {"description": "chicken mozzarella", "calories": 680, "protein": 45.0, "fat": 22.0, "carbs": 30.0}, "extract": "chicken mozzarella"}],
            "actions": [],
        }
        resp = client.post("/chat", json={"text": "I had chicken mozzarella"},
                           headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert resp.json()["domains"][0]["domain"] == "health"


def test_chat_multi_domain(client):
    with patch("orchestrator.chat.build_chat_response") as mock_build:
        mock_build.return_value = {
            "prose": "",
            "domains": [
                {"domain": "health", "preview": {"description": "chicken mozzarella", "calories": 680, "protein": 45.0, "fat": 22.0, "carbs": 30.0}, "extract": "chicken mozzarella"},
                {"domain": "finance", "preview": {"description": "Cheesecake Factory", "amount": -50.0, "category": "dining", "date": "2026-08-08"}, "extract": "$50 at Cheesecake Factory"},
            ],
            "actions": [],
        }
        resp = client.post("/chat", json={"text": "I had chicken mozzarella at Cheesecake Factory, spent $50"},
                           headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert {d["domain"] for d in resp.json()["domains"]} == {"health", "finance"}


# ── Engine-level test (mock call_claude — verifies intent parsing) ────────────

def test_build_chat_response_meal(conn):
    """Verify build_chat_response correctly parses intent JSON and calls health parser."""
    from orchestrator.chat import build_chat_response
    intent_json = json.dumps({
        "prose": "",
        "health_extract": "chicken mozzarella",
        "finance_extract": None,
        "tasks_extract": None,
        "actions": [],
    })
    macro_json = json.dumps({"description": "chicken mozzarella", "calories": 680, "protein": 45.0, "fat": 22.0, "carbs": 30.0})
    with patch("orchestrator.chat.call_claude", return_value=intent_json), \
         patch("domains.health.tools.call_claude", return_value=macro_json):
        result = build_chat_response(conn, 1, "I had chicken mozzarella")
    assert len(result["domains"]) == 1
    assert result["domains"][0]["domain"] == "health"
    assert result["domains"][0]["preview"]["calories"] == 680


def test_build_chat_response_finance(conn):
    """Verify build_chat_response correctly parses finance intent and calls finance parser."""
    from orchestrator.chat import build_chat_response
    intent_json = json.dumps({
        "prose": "",
        "health_extract": None,
        "finance_extract": "$50 at Cheesecake Factory",
        "tasks_extract": None,
        "actions": [],
    })
    txn_json = json.dumps({"description": "Cheesecake Factory", "amount": -50.0, "category": "dining", "date": "2026-08-08"})
    with patch("orchestrator.chat.call_claude", return_value=intent_json), \
         patch("domains.finance.tools.call_claude", return_value=txn_json):
        result = build_chat_response(conn, 1, "Spent $50 at Cheesecake Factory")
    assert len(result["domains"]) == 1
    assert result["domains"][0]["domain"] == "finance"
    assert result["domains"][0]["preview"]["amount"] == -50.0


# ── Confirm-endpoint tests ────────────────────────────────────────────────────

def test_chat_confirm_health(client, conn):
    from domains.health.db import get_today_meals
    resp = client.post("/chat/confirm", json={
        "domain": "health",
        "preview": {"description": "eggs", "calories": 150, "protein": 12.0, "fat": 10.0, "carbs": 1.0},
        "user_id": 1,
    }, headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    meals = get_today_meals(conn, 1)
    assert len(meals) == 1
    assert meals[0]["description"] == "eggs"


def test_chat_confirm_tasks(client, conn):
    from domains.tasks.db import get_pending_tasks
    resp = client.post("/chat/confirm", json={
        "domain": "tasks",
        "preview": [
            {"title": "Buy chicken", "due_at": "2026-08-09T00:00:00", "priority": 0, "is_recurring": False},
            {"title": "Buy onions", "due_at": "2026-08-09T00:00:00", "priority": 0, "is_recurring": False},
        ],
        "user_id": 1,
    }, headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    assert len(get_pending_tasks(conn, 1)) == 2


def test_chat_confirm_finance(client, conn):
    from domains.finance.db import list_transactions
    resp = client.post("/chat/confirm", json={
        "domain": "finance",
        "preview": {"description": "Cheesecake Factory", "amount": -50.0, "category": "dining", "date": "2026-08-08"},
        "user_id": 1,
    }, headers={"X-API-Key": "test"})
    assert resp.status_code == 200
    txns = list_transactions(conn, 1)
    assert len(txns) == 1
    assert txns[0]["description"] == "Cheesecake Factory"
