import json
import pytest
from orchestrator.insights_store import store_insights, get_latest_insights


def test_store_and_retrieve(conn, user_id):
    cards = json.dumps([{"title": "Test card", "body": "body text"}])
    store_insights(conn, user_id, "today", cards)
    result = get_latest_insights(conn, user_id, "today")
    assert result is not None
    assert result["scope"] == "today"
    assert result["cards_json"] == cards


def test_upsert_replaces_previous(conn, user_id):
    store_insights(conn, user_id, "today", json.dumps([{"title": "old"}]))
    store_insights(conn, user_id, "today", json.dumps([{"title": "new"}]))
    result = get_latest_insights(conn, user_id, "today")
    assert json.loads(result["cards_json"])[0]["title"] == "new"


def test_week_scope_independent(conn, user_id):
    store_insights(conn, user_id, "today", json.dumps([{"title": "today card"}]))
    store_insights(conn, user_id, "week", json.dumps([{"title": "week card"}]))
    today = get_latest_insights(conn, user_id, "today")
    week = get_latest_insights(conn, user_id, "week")
    assert json.loads(today["cards_json"])[0]["title"] == "today card"
    assert json.loads(week["cards_json"])[0]["title"] == "week card"


def test_returns_none_when_no_insights(conn, user_id):
    assert get_latest_insights(conn, user_id, "today") is None
    assert get_latest_insights(conn, user_id, "week") is None
