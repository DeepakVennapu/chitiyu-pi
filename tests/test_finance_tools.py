# tests/test_finance_tools.py
import json
import pytest
from unittest.mock import patch

from domains.finance.db import (
    insert_transaction,
    upsert_budget,
    get_category_spend_this_month,
)
from domains.finance.tools import (
    add_budget,
    add_net_worth_snapshot,
    add_savings_goal,
    add_transaction,
    add_transaction_structured,
    get_budget_summary,
    get_net_worth,
    get_savings_goals_tool,
    list_transactions_tool,
)
from domains.finance.formatter import (
    format_budget_summary,
    format_goals,
    format_net_worth,
    format_transaction_log,
)


# ── Formatter unit tests (no DB, no LLM) ──────────────────────────────────────

def test_format_transaction_log_expense():
    result = format_transaction_log("Whole Foods", -45.00, "groceries", "2026-08-01")
    assert "-$45.00" in result
    assert "groceries" in result
    assert "Whole Foods" in result


def test_format_transaction_log_income():
    result = format_transaction_log("Paycheck", 2000.00, "income", "2026-08-01")
    assert "+$2000.00" in result


def test_format_budget_summary_over_budget():
    spend = {"groceries": 550.0, "dining": 80.0}
    budgets = [
        {"category": "groceries", "amount": 500.0},
        {"category": "dining", "amount": 200.0},
    ]
    result = format_budget_summary(spend, budgets, 2026, 8)
    assert "OVER" in result
    assert "groceries" in result
    assert "dining" in result


def test_format_budget_summary_no_data():
    result = format_budget_summary({}, [], 2026, 8)
    assert "No transactions" in result


def test_format_net_worth_with_data():
    snapshot = {
        "snapshot_date": "2026-08-01",
        "assets_json": {"checking": 5000, "savings": 20000},
        "liabilities_json": {"credit_card": 1500},
        "total": 23500.0,
    }
    result = format_net_worth(snapshot)
    assert "$23,500" in result
    assert "2026-08-01" in result
    assert "Phase 2" in result  # MVP limitation note


def test_format_net_worth_none():
    result = format_net_worth(None)
    assert "No net worth" in result


def test_format_goals_with_data():
    goals = [
        {"name": "Emergency Fund", "target_amount": 10000.0,
         "current_amount": 4000.0, "target_date": "2026-12-31"},
    ]
    result = format_goals(goals)
    assert "Emergency Fund" in result
    assert "40%" in result


def test_format_goals_empty():
    result = format_goals([])
    assert "No savings goals" in result


# ── Tools that don't call LLM ─────────────────────────────────────────────────

def test_add_budget_tool(conn, user_id):
    result = add_budget(conn, user_id, "groceries", 500.0)
    assert "500" in result
    assert "groceries" in result


def test_get_budget_summary_tool(conn, user_id):
    upsert_budget(conn, user_id, "groceries", 500.0)
    insert_transaction(conn, user_id, "2026-08-01", -200.0, "groceries", "Trader Joe's", "manual")
    # Pass year/month explicitly — get_monthly_spend uses SQL strftime, no datetime.now needed
    result = get_budget_summary(conn, user_id, year=2026, month=8)
    assert "groceries" in result


def test_get_net_worth_tool_empty(conn, user_id):
    result = get_net_worth(conn, user_id)
    assert "No net worth" in result


def test_add_net_worth_snapshot_tool(conn, user_id):
    result = add_net_worth_snapshot(
        conn, user_id,
        snapshot_date="2026-08-01",
        assets_json={"checking": 5000, "savings": 20000},
        liabilities_json={"credit_card": 1500},
        total=23500.0
    )
    assert "23,500" in result
    assert "2026-08-01" in result


def test_add_savings_goal_tool(conn, user_id):
    result = add_savings_goal(conn, user_id, "House Down Payment", 50000.0, "2028-06-01")
    assert "House Down Payment" in result
    assert "50,000" in result


def test_get_savings_goals_tool_empty(conn, user_id):
    result = get_savings_goals_tool(conn, user_id)
    assert "No savings goals" in result


def test_get_savings_goals_tool_with_goals(conn, user_id):
    from domains.finance.db import insert_savings_goal
    insert_savings_goal(conn, user_id, "Emergency Fund", 10000.0)
    result = get_savings_goals_tool(conn, user_id)
    assert "Emergency Fund" in result


def test_list_transactions_tool_empty(conn, user_id):
    result = list_transactions_tool(conn, user_id)
    assert "No transactions" in result


def test_list_transactions_tool_with_data(conn, user_id):
    insert_transaction(conn, user_id, "2026-08-01", -45.0, "groceries", "Whole Foods", "manual")
    result = list_transactions_tool(conn, user_id)
    assert "Whole Foods" in result
    assert "$45.00" in result


# ── add_transaction with mocked LLM ──────────────────────────────────────────

def test_add_transaction_no_budget(conn, user_id):
    mock_response = json.dumps({
        "date": "2026-08-01", "amount": -45.0,
        "category": "groceries", "description": "Whole Foods"
    })
    with patch("domains.finance.tools.call_claude", return_value=mock_response):
        result = add_transaction(conn, user_id, "spent $45 at Whole Foods")
    assert "Whole Foods" in result
    assert "$45.00" in result


def test_add_transaction_fires_budget_exceeded_event(conn, user_id):
    # Use today's date so get_category_spend_this_month's month filter matches
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()

    upsert_budget(conn, user_id, "groceries", 100.0)
    insert_transaction(conn, user_id, today, -110.0, "groceries", "Costco", "manual")

    mock_response = json.dumps({
        "date": today, "amount": -40.0,
        "category": "groceries", "description": "Trader Joe's"
    })

    with patch("domains.finance.tools.call_claude", return_value=mock_response):
        add_transaction(conn, user_id, "spent $40 at Trader Joe's")

    events = conn.execute(
        "SELECT * FROM notification_events WHERE event_type='budget_exceeded'"
    ).fetchall()
    assert len(events) == 1
    payload = json.loads(events[0]["payload_json"])
    assert payload["category"] == "groceries"
    assert payload["overage"] > 0


def test_add_transaction_no_budget_exceeded_event_when_under(conn, user_id):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()

    upsert_budget(conn, user_id, "groceries", 500.0)
    mock_response = json.dumps({
        "date": today, "amount": -45.0,
        "category": "groceries", "description": "Whole Foods"
    })
    with patch("domains.finance.tools.call_claude", return_value=mock_response):
        add_transaction(conn, user_id, "spent $45 at Whole Foods")

    events = conn.execute(
        "SELECT * FROM notification_events WHERE event_type='budget_exceeded'"
    ).fetchall()
    assert len(events) == 0


def test_add_transaction_parse_failure(conn, user_id):
    with patch("domains.finance.tools.call_claude", return_value="not json at all"):
        result = add_transaction(conn, user_id, "xyz")
    assert "Couldn't parse" in result


# ── add_transaction_structured (REST/app path) ────────────────────────────────

def test_add_transaction_structured_returns_dict(conn, user_id):
    mock_response = json.dumps({
        "date": "2026-08-01", "amount": -45.0,
        "category": "groceries", "description": "Whole Foods"
    })
    with patch("domains.finance.tools.call_claude", return_value=mock_response):
        result = add_transaction_structured(conn, user_id, "spent $45 at Whole Foods")
    assert isinstance(result, dict)
    assert result["id"] > 0
    assert result["amount"] == pytest.approx(-45.0)
    assert result["category"] == "groceries"
    assert result["description"] == "Whole Foods"
    assert result["source"] == "manual"


def test_add_transaction_structured_returns_none_on_parse_failure(conn, user_id):
    with patch("domains.finance.tools.call_claude", return_value="not json"):
        result = add_transaction_structured(conn, user_id, "xyz")
    assert result is None
