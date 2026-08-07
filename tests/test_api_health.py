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


def test_delete_meal(monkeypatch):
    monkeypatch.setenv("API_KEY", "testkey")
    import importlib, config, auth
    importlib.reload(config)
    monkeypatch.setattr(auth, "API_KEY", "testkey")
    # First log a meal to get an id — mock LLM to avoid a real Claude call
    fake_response = '{"description": "banana", "calories": 89, "protein": 1.1, "fat": 0.3, "carbs": 23.0}'
    with patch("domains.health.tools.call_claude", return_value=fake_response):
        r = client.post("/health/meals", json={"text": "1 banana"}, headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    # Get today's meals to find the id
    r2 = client.get("/health/meals/today", headers={"x-api-key": "testkey"})
    assert r2.status_code == 200
    meals = r2.json()["meals"]
    assert len(meals) > 0
    meal_id = meals[-1]["id"]
    # Delete it
    r3 = client.delete(f"/health/meals/{meal_id}", headers={"x-api-key": "testkey"})
    assert r3.status_code == 200
    assert r3.json()["ok"] is True
    # Verify gone
    r4 = client.get("/health/meals/today", headers={"x-api-key": "testkey"})
    ids = [m["id"] for m in r4.json()["meals"]]
    assert meal_id not in ids


def test_delete_meal_not_found(monkeypatch):
    monkeypatch.setenv("API_KEY", "testkey")
    import importlib, config, auth
    importlib.reload(config)
    monkeypatch.setattr(auth, "API_KEY", "testkey")
    r = client.delete("/health/meals/99999", headers={"x-api-key": "testkey"})
    assert r.status_code == 404


_FAKE_MACRO_JSON = '{"description": "oatmeal with berries", "calories": 320, "protein": 8.0, "fat": 6.0, "carbs": 58.0}'


def test_preview_meal(monkeypatch):
    monkeypatch.setenv("API_KEY", "testkey")
    import importlib, config, auth
    importlib.reload(config)
    monkeypatch.setattr(auth, "API_KEY", "testkey")
    with patch("domains.health.tools.call_claude", return_value=_FAKE_MACRO_JSON):
        r = client.post("/health/meals/preview",
                        json={"text": "oatmeal with berries"},
                        headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    data = r.json()
    assert "calories" in data
    assert "protein" in data
    assert isinstance(data["calories"], (int, float))


def test_preview_meal_returns_no_db_row(monkeypatch):
    monkeypatch.setenv("API_KEY", "testkey")
    import importlib, config, auth
    importlib.reload(config)
    monkeypatch.setattr(auth, "API_KEY", "testkey")
    before = client.get("/health/meals/today", headers={"x-api-key": "testkey"}).json()["meals"]
    with patch("domains.health.tools.call_claude", return_value=_FAKE_MACRO_JSON):
        client.post("/health/meals/preview",
                    json={"text": "oatmeal"},
                    headers={"x-api-key": "testkey"})
    after = client.get("/health/meals/today", headers={"x-api-key": "testkey"}).json()["meals"]
    assert len(before) == len(after)  # preview must not insert


def test_log_from_recipe(monkeypatch):
    monkeypatch.setenv("API_KEY", "testkey")
    import importlib, config, auth
    importlib.reload(config)
    monkeypatch.setattr(auth, "API_KEY", "testkey")
    # Create a recipe first
    r = client.post("/health/recipes",
                    json={"name": "Test Oats", "calories": 300, "protein": 10.0, "fat": 5.0, "carbs": 50.0},
                    headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    recipe_id = r.json()["id"]
    # Log from it
    r2 = client.post("/health/meals/from-recipe",
                     json={"recipe_id": recipe_id},
                     headers={"x-api-key": "testkey"})
    assert r2.status_code == 200
    assert "Test Oats" in r2.json()["result"]
    # Verify it showed up in today's meals
    meals = client.get("/health/meals/today", headers={"x-api-key": "testkey"}).json()["meals"]
    assert any(m["description"] == "Test Oats" for m in meals)


def test_log_from_recipe_not_found(monkeypatch):
    monkeypatch.setenv("API_KEY", "testkey")
    import importlib, config, auth
    importlib.reload(config)
    monkeypatch.setattr(auth, "API_KEY", "testkey")
    r = client.post("/health/meals/from-recipe",
                    json={"recipe_id": 99999},
                    headers={"x-api-key": "testkey"})
    assert r.status_code == 404
