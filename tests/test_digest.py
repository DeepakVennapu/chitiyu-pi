from unittest.mock import patch

import pytest

from orchestrator.digest import build_morning_digest, _build_numbers_block


# --- Unit tests for the numbers block (zero LLM) ---

def test_numbers_block_all_none():
    """Should not raise when all domain fetches return None."""
    block = _build_numbers_block(None, None, None, None, None)
    assert "Good morning" in block
    assert "Sleep:" in block
    assert "Cal:" in block
    assert "Overdue: 0" in block


def test_numbers_block_with_data():
    yesterday_health = {"metrics": {
        "sleep_deep_mins": 55, "sleep_total_mins": 420, "resting_hr": 62, "steps": 9800
    }}
    today_meals = {"totals": {"calories": 720, "protein": 85, "fat": 22, "carbs": 60}}
    today_tasks = [{"id": 1, "title": "Call doctor"}, {"id": 2, "title": "Buy groceries"}]
    overdue_tasks = [{"id": 3, "title": "File taxes"}]
    finance = {"total_spent": 1230.50, "total_budget": 2000.00}

    block = _build_numbers_block(yesterday_health, today_meals, today_tasks, overdue_tasks, finance)

    assert "55min deep" in block
    assert "420min total" in block
    assert "9,800" in block
    assert "720 / 1500 kcal" in block
    assert "85g / 155g" in block
    assert "Overdue: 1" in block
    assert "Due today: 2" in block
    assert "$1230.50" in block
    assert "$2000.00" in block


def test_numbers_block_steps_formatting():
    """Steps should be comma-formatted."""
    health = {"metrics": {"steps": 10500, "sleep_deep_mins": 60,
                          "sleep_total_mins": 450, "resting_hr": 60}}
    block = _build_numbers_block(health, None, None, None, None)
    assert "10,500" in block


# --- Integration tests for build_morning_digest ---

def _make_digest_patches(shape_text="Stay focused on protein today. You're 30g short."):
    return [
        patch("orchestrator.digest.call_claude", return_value=shape_text),
        patch("orchestrator.digest._get", return_value=None),  # all domain fetches → None
    ]


def test_build_morning_digest_returns_string(conn, user_id):
    ps = _make_digest_patches()
    with ps[0], ps[1]:
        result = build_morning_digest(conn, user_id)
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_morning_digest_includes_numbers_and_paragraph(conn, user_id):
    shape = "Protein is the priority today. You're 40g short with two meals to go. Hit 155g."
    ps = _make_digest_patches(shape_text=shape)
    with ps[0], ps[1]:
        result = build_morning_digest(conn, user_id)
    assert "Good morning" in result
    assert "Sleep:" in result
    assert "Protein is the priority" in result


def test_build_morning_digest_succeeds_if_sonnet_fails(conn, user_id):
    """Digest must deliver the numbers block even if Sonnet call fails."""
    with patch("orchestrator.digest.call_claude", side_effect=RuntimeError("LLM down")), \
         patch("orchestrator.digest._get", return_value=None):
        result = build_morning_digest(conn, user_id)
    assert "Good morning" in result
    assert "Sleep:" in result
