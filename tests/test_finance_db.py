import pytest
from domains.finance.db import (
    insert_account, get_account_by_name, list_accounts,
    insert_transaction, list_transactions, delete_transaction, get_monthly_spend,
    get_category_spend_this_month,
    upsert_budget, list_budgets, get_budget,
    insert_net_worth, get_latest_net_worth, list_net_worth_snapshots,
    insert_savings_goal, update_savings_goal_progress, list_savings_goals,
    get_savings_goal,
)


# ── Accounts ────────────────────────────────────────────────────────────────────

def test_insert_and_get_account(conn, user_id):
    aid = insert_account(conn, user_id, "Chase Checking", "checking")
    assert aid > 0
    acct = get_account_by_name(conn, user_id, "Chase Checking")
    assert acct is not None
    assert acct["name"] == "Chase Checking"
    assert acct["type"] == "checking"


def test_insert_account_idempotent(conn, user_id):
    aid1 = insert_account(conn, user_id, "Chase Checking", "checking")
    aid2 = insert_account(conn, user_id, "Chase Checking", "checking")
    assert aid1 == aid2


def test_list_accounts(conn, user_id):
    insert_account(conn, user_id, "Amex Credit", "credit")
    insert_account(conn, user_id, "Schwab Investment", "investment")
    accounts = list_accounts(conn, user_id)
    names = {a["name"] for a in accounts}
    assert "Amex Credit" in names
    assert "Schwab Investment" in names


def test_account_user_isolation(conn):
    insert_account(conn, 1, "User1 Account", "checking")
    acct = get_account_by_name(conn, 2, "User1 Account")
    assert acct is None


# ── Transactions ───────────────────────────────────────────────────────────────

def test_insert_and_list_transaction(conn, user_id):
    tid = insert_transaction(conn, user_id, "2026-08-01", -45.00, "groceries",
                             "Whole Foods", "manual")
    assert tid > 0
    txns = list_transactions(conn, user_id)
    assert len(txns) == 1
    assert txns[0]["description"] == "Whole Foods"
    assert txns[0]["amount"] == -45.00


def test_list_transactions_filter_by_date(conn, user_id):
    insert_transaction(conn, user_id, "2026-07-15", -20.00, "dining", "Pizza Hut", "manual")
    insert_transaction(conn, user_id, "2026-08-01", -45.00, "groceries", "Whole Foods", "manual")
    txns = list_transactions(conn, user_id, date_from="2026-08-01")
    assert len(txns) == 1
    assert txns[0]["date"] == "2026-08-01"


def test_list_transactions_filter_by_category(conn, user_id):
    insert_transaction(conn, user_id, "2026-08-01", -45.00, "groceries", "Whole Foods", "manual")
    insert_transaction(conn, user_id, "2026-08-02", -30.00, "dining", "Chick-fil-A", "manual")
    txns = list_transactions(conn, user_id, category="dining")
    assert len(txns) == 1
    assert txns[0]["description"] == "Chick-fil-A"


def test_get_monthly_spend(conn, user_id):
    insert_transaction(conn, user_id, "2026-08-01", -45.00, "groceries", "Whole Foods", "manual")
    insert_transaction(conn, user_id, "2026-08-05", -60.00, "groceries", "Trader Joe's", "manual")
    insert_transaction(conn, user_id, "2026-08-10", -30.00, "dining", "Chipotle", "manual")
    # Positive (income) should be excluded
    insert_transaction(conn, user_id, "2026-08-15", 2000.00, "income", "Paycheck", "manual")
    spend = get_monthly_spend(conn, user_id, 2026, 8)
    assert spend["groceries"] == pytest.approx(105.00)
    assert spend["dining"] == pytest.approx(30.00)
    assert "income" not in spend


def test_transaction_user_isolation(conn):
    insert_transaction(conn, 1, "2026-08-01", -45.00, "groceries", "Whole Foods", "manual")
    txns = list_transactions(conn, 2)
    assert txns == []


def test_delete_transaction(conn, user_id):
    tid = insert_transaction(conn, user_id, "2026-08-07", -50.0, "food", "lunch", "manual")
    assert delete_transaction(conn, user_id, tid) is True
    rows = list_transactions(conn, user_id)
    assert all(r["id"] != tid for r in rows)


def test_delete_transaction_wrong_user(conn):
    tid = insert_transaction(conn, 1, "2026-08-07", -50.0, "food", "lunch", "manual")
    assert delete_transaction(conn, 2, tid) is False  # wrong user_id


# ── Budgets ────────────────────────────────────────────────────────────────────

def test_upsert_budget_creates(conn, user_id):
    bid = upsert_budget(conn, user_id, "groceries", 500.00)
    assert bid > 0
    budget = get_budget(conn, user_id, "groceries")
    assert budget is not None
    assert budget["amount"] == pytest.approx(500.00)


def test_upsert_budget_updates(conn, user_id):
    upsert_budget(conn, user_id, "groceries", 500.00)
    upsert_budget(conn, user_id, "groceries", 600.00)
    budget = get_budget(conn, user_id, "groceries")
    assert budget["amount"] == pytest.approx(600.00)


def test_list_budgets(conn, user_id):
    upsert_budget(conn, user_id, "groceries", 500.00)
    upsert_budget(conn, user_id, "dining", 200.00)
    budgets = list_budgets(conn, user_id)
    categories = {b["category"] for b in budgets}
    assert "groceries" in categories
    assert "dining" in categories


# ── Net Worth ──────────────────────────────────────────────────────────────────

def test_insert_and_get_net_worth(conn, user_id):
    assets = {"checking": 5000, "savings": 20000}
    liabilities = {"credit_card": 1500}
    nwid = insert_net_worth(conn, user_id, "2026-08-01", assets, liabilities, 23500.0)
    assert nwid > 0
    latest = get_latest_net_worth(conn, user_id)
    assert latest is not None
    assert latest["total"] == pytest.approx(23500.0)
    assert latest["assets_json"]["checking"] == 5000


def test_net_worth_upserts_on_same_date(conn, user_id):
    insert_net_worth(conn, user_id, "2026-08-01", {"checking": 5000}, {}, 5000.0)
    insert_net_worth(conn, user_id, "2026-08-01", {"checking": 6000}, {}, 6000.0)
    latest = get_latest_net_worth(conn, user_id)
    assert latest["total"] == pytest.approx(6000.0)


def test_get_latest_net_worth_returns_most_recent(conn, user_id):
    insert_net_worth(conn, user_id, "2026-06-01", {"checking": 5000}, {}, 5000.0)
    insert_net_worth(conn, user_id, "2026-08-01", {"checking": 7000}, {}, 7000.0)
    latest = get_latest_net_worth(conn, user_id)
    assert latest["snapshot_date"] == "2026-08-01"


def test_net_worth_returns_none_when_empty(conn, user_id):
    assert get_latest_net_worth(conn, user_id) is None


# ── Savings Goals ──────────────────────────────────────────────────────────────

def test_insert_and_list_savings_goal(conn, user_id):
    gid = insert_savings_goal(conn, user_id, "Emergency Fund", 10000.00, "2026-12-31")
    assert gid > 0
    goals = list_savings_goals(conn, user_id)
    assert len(goals) == 1
    assert goals[0]["name"] == "Emergency Fund"
    assert goals[0]["target_amount"] == pytest.approx(10000.00)
    assert goals[0]["current_amount"] == pytest.approx(0.0)


def test_update_savings_goal_progress(conn, user_id):
    gid = insert_savings_goal(conn, user_id, "Vacation", 3000.00)
    ok = update_savings_goal_progress(conn, user_id, gid, 1200.00)
    assert ok is True
    goals = list_savings_goals(conn, user_id)
    assert goals[0]["current_amount"] == pytest.approx(1200.00)


def test_update_savings_goal_wrong_user(conn):
    gid = insert_savings_goal(conn, 1, "Vacation", 3000.00)
    ok = update_savings_goal_progress(conn, 2, gid, 1200.00)
    assert ok is False


def test_get_savings_goal(conn, user_id):
    gid = insert_savings_goal(conn, user_id, "House Down Payment", 50000.00, "2028-12-31")
    goal = get_savings_goal(conn, user_id, gid)
    assert goal is not None
    assert goal["name"] == "House Down Payment"
    assert goal["target_amount"] == pytest.approx(50000.00)


def test_list_net_worth_snapshots(conn, user_id):
    insert_net_worth(conn, user_id, "2026-06-01", {"checking": 5000}, {"credit": 500}, 4500.0)
    insert_net_worth(conn, user_id, "2026-07-01", {"checking": 6000}, {"credit": 600}, 5400.0)
    insert_net_worth(conn, user_id, "2026-08-01", {"checking": 7000}, {"credit": 700}, 6300.0)
    snapshots = list_net_worth_snapshots(conn, user_id, limit=12)
    assert len(snapshots) == 3
    # Should be ordered by date DESC
    assert snapshots[0]["snapshot_date"] == "2026-08-01"
    assert snapshots[2]["snapshot_date"] == "2026-06-01"
