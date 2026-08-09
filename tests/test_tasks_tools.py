import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import pytest
from unittest.mock import patch
from domains.tasks.tools import parse_task_input, create_tasks_from_input


def test_parse_single_task_no_date():
    payload = [{"title": "Call dentist", "due_at": None, "priority": 0, "recurrence": None, "anchor_date": None}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        result = parse_task_input("Call dentist", today="2026-08-08")
    assert len(result) == 1
    assert result[0]["title"] == "Call dentist"
    assert result[0]["due_at"] is None
    assert result[0]["priority"] == 0


def test_parse_multiple_subtasks():
    payload = [
        {"title": "Buy chicken", "due_at": "2026-08-09T00:00:00", "priority": 0, "recurrence": None, "anchor_date": None},
        {"title": "Buy coriander", "due_at": "2026-08-09T00:00:00", "priority": 0, "recurrence": None, "anchor_date": None},
        {"title": "Buy onions", "due_at": "2026-08-09T00:00:00", "priority": 0, "recurrence": None, "anchor_date": None},
    ]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        result = parse_task_input("Buy groceries: chicken, coriander, onions tomorrow", today="2026-08-08")
    assert len(result) == 3
    assert result[0]["due_at"] == "2026-08-09T00:00:00"


def test_parse_urgency_priority():
    payload = [{"title": "Fix prod bug", "due_at": None, "priority": 2, "recurrence": None, "anchor_date": None}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        result = parse_task_input("URGENT: fix prod bug", today="2026-08-08")
    assert result[0]["priority"] == 2


def test_parse_recurring_weekly():
    payload = [{"title": "Call mom", "due_at": None, "priority": 0, "recurrence": "weekly", "anchor_date": "2026-08-11"}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        result = parse_task_input("Call mom every Monday", today="2026-08-08")
    assert result[0]["recurrence"] == "weekly"
    assert result[0]["anchor_date"] == "2026-08-11"


def test_create_tasks_from_input_one_off(conn, user_id):
    payload = [{"title": "Buy milk", "due_at": "2026-08-09T00:00:00", "priority": 0, "recurrence": None, "anchor_date": None}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        created = create_tasks_from_input(conn, user_id, "Buy milk tomorrow")
    assert len(created) == 1
    assert created[0]["title"] == "Buy milk"
    assert created[0]["is_recurring"] is False


def test_create_tasks_from_input_recurring(conn, user_id):
    payload = [{"title": "Call mom", "due_at": None, "priority": 0, "recurrence": "weekly", "anchor_date": "2026-08-11"}]
    with patch("domains.tasks.tools.call_claude", return_value=json.dumps(payload)):
        created = create_tasks_from_input(conn, user_id, "Call mom every Monday")
    assert len(created) == 1
    assert created[0]["is_recurring"] is True
