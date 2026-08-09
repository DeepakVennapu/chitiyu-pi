import sys, os

# Set required env vars before any backend imports touch config.py
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from unittest.mock import patch, MagicMock

mock_sched = MagicMock()
mock_sched.start.return_value = None
mock_sched.shutdown.return_value = None

with patch("scheduler.build_scheduler", return_value=mock_sched):
    from main import app

from fastapi.testclient import TestClient
from db.connection import get_connection
from db.schema import initialize_schema
from config import DB_PATH
import domains.tasks.router as tasks_router
import auth


@pytest.fixture(autouse=True)
def clean_db():
    conn = get_connection(DB_PATH)
    initialize_schema(conn)
    conn.execute("DELETE FROM task_instances")
    conn.execute("DELETE FROM task_templates")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_KEY", "test")
    monkeypatch.setattr(auth, "API_KEY", "test")
    return TestClient(app, headers={"X-API-Key": "test"})


def test_create_task_with_priority(client):
    import json
    payload = [{"title": "Urgent thing", "due_at": None, "priority": 2, "recurrence": None, "anchor_date": None}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        r = client.post("/tasks/", json={"title": "Urgent thing", "priority": 2})
    assert r.status_code == 200
    assert r.json()["priority"] == 2


def test_dates_summary_empty(client):
    r = client.get("/tasks/dates-summary?start=2026-08-01&end=2026-08-31")
    assert r.status_code == 200
    assert r.json() == {}


def test_dates_summary_with_task(client):
    import json
    payload = [{"title": "Thing", "due_at": "2026-08-10T00:00:00", "priority": 1, "recurrence": None, "anchor_date": None}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        client.post("/tasks/", json={"title": "Thing", "due_at": "2026-08-10T00:00:00", "priority": 1})
    r = client.get("/tasks/dates-summary?start=2026-08-01&end=2026-08-31")
    assert r.json() == {"2026-08-10": 1}


def test_create_template(client):
    r = client.post("/tasks/templates", json={
        "title": "Call mom", "recurrence": "weekly",
        "anchor_date": "2026-08-11", "advance_days": 1
    })
    assert r.status_code == 200
    assert r.json()["recurrence"] == "weekly"


def test_complete_instance(client):
    from datetime import date
    today = date.today().isoformat()
    client.post("/tasks/templates", json={
        "title": "Take vitamins", "recurrence": "daily",
        "anchor_date": today, "advance_days": 1
    })
    tasks = client.get(f"/tasks/by-date?date={today}").json()
    recurring = [t for t in tasks if t.get("is_recurring")]
    assert len(recurring) == 1
    iid = recurring[0]["id"]
    r = client.patch(f"/tasks/instances/{iid}/complete")
    assert r.json()["ok"] is True
