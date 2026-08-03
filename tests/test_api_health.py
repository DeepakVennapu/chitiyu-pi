# tests/test_api_health.py
import sys, os

# Set required env vars before any backend imports touch config.py
os.environ.setdefault("API_KEY", "testkey")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from unittest.mock import patch, MagicMock

# Patch scheduler.build_scheduler before main.py is imported so the lifespan
# context manager never tries to start a real APScheduler.
mock_sched = MagicMock()
mock_sched.start.return_value = None
mock_sched.shutdown.return_value = None

with patch("scheduler.build_scheduler", return_value=mock_sched):
    from main import app

from fastapi.testclient import TestClient

client = TestClient(app)


def test_healthcheck():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_tasks_requires_api_key():
    r = client.get("/tasks/")
    assert r.status_code == 422  # missing header


def test_tasks_with_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "testkey")
    import importlib, config
    importlib.reload(config)
    # auth.py binds API_KEY at import time; patch it directly so verify_api_key
    # sees the reloaded value during this test.
    import auth
    monkeypatch.setattr(auth, "API_KEY", "testkey")
    r = client.get("/tasks/", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
