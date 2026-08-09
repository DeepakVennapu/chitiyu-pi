# backend/domains/finance/tools.py
import json
import re
import sqlite3
from utils.local_time import local_now, today_local

from config import DISPATCH_MODEL
from domains.finance.db import (
    get_budget,
    get_category_spend_this_month,
    get_latest_net_worth,
    get_monthly_spend,
    insert_net_worth,
    insert_savings_goal,
    insert_transaction,
    list_budgets,
    list_savings_goals,
    list_transactions,
    update_savings_goal_progress,
    upsert_budget,
)
from domains.finance.formatter import (
    format_budget_summary,
    format_goals,
    format_net_worth,
    format_transaction_log,
)
from orchestrator.dispatcher import post_event
from orchestrator.llm import call_claude

_PARSE_EXPENSE_PROMPT = """\
Parse this expense description into structured fields. Return JSON only:
{{"date": "<YYYY-MM-DD or today's date {today}>", "amount": <negative float for expense, positive for income>, \
"category": "<one of: groceries, dining, gas, transport, health, clothing, entertainment, \
utilities, rent, subscriptions, travel, shopping, savings, income, other>", \
"description": "<clean merchant or description name>"}}
Context (if any): {context}
Input: {text}"""


def parse_transaction_input(text: str, context: str = "") -> dict | None:
    """Parse NL expense text via Haiku. Returns structured dict or None on parse failure."""
    today = today_local()
    prompt = _PARSE_EXPENSE_PROMPT.format(today=today, context=context, text=text)
    raw = call_claude(prompt, model=DISPATCH_MODEL, timeout=20)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _fire_budget_event(conn: sqlite3.Connection, user_id: int,
                       category: str, amount: float) -> None:
    """Fire budget_exceeded event if this expense pushes the category over its budget."""
    if amount >= 0:
        return
    budget = get_budget(conn, user_id, category, period="monthly")
    if not budget:
        return
    spent_this_month = get_category_spend_this_month(conn, user_id, category)
    if spent_this_month > budget["amount"]:
        overage = spent_this_month - budget["amount"]
        post_event(
            conn, user_id, "finance", "budget_exceeded",
            {
                "category": category,
                "spent": round(spent_this_month, 2),
                "budget": round(budget["amount"], 2),
                "overage": round(overage, 2),
                "text": (
                    f"Budget alert: {category} is ${spent_this_month:.0f} this month "
                    f"vs ${budget['amount']:.0f} budget "
                    f"(${overage:.0f} over)."
                ),
            }
        )


def add_transaction(conn: sqlite3.Connection, user_id: int,
                    text: str, context: str = "") -> str:
    """Telegram/orchestrator path — parses NL text, inserts, returns human-readable string."""
    today = today_local()
    data = parse_transaction_input(text, context)
    if not data:
        return "Couldn't parse that expense. Try: 'spent $45 at Whole Foods on groceries'."

    amount = float(data.get("amount", 0))
    category = str(data.get("category", "other")).lower()
    description = str(data.get("description", text))
    date = str(data.get("date", today))

    insert_transaction(conn, user_id, date, amount, category, description, source="manual")
    _fire_budget_event(conn, user_id, category, amount)
    result = format_transaction_log(description, amount, category, date)

    # Trigger async insight regeneration — non-blocking
    try:
        from orchestrator.insights import trigger_insights_async
        trigger_insights_async(user_id, scope="today")
    except Exception:
        pass  # Never let insight trigger block the transaction response

    return result


def add_transaction_structured(conn: sqlite3.Connection, user_id: int,
                               text: str, context: str = "") -> dict | None:
    """App/REST path — parses NL text, inserts, returns the inserted row as a dict.
    Returns None if the text cannot be parsed (caller raises HTTP 422)."""
    today = today_local()
    data = parse_transaction_input(text, context)
    if not data:
        return None

    amount = float(data.get("amount", 0))
    category = str(data.get("category", "other")).lower()
    description = str(data.get("description", text))
    date = str(data.get("date", today))

    tid = insert_transaction(conn, user_id, date, amount, category, description, source="manual")
    _fire_budget_event(conn, user_id, category, amount)
    return {
        "id": tid,
        "date": date,
        "amount": amount,
        "category": category,
        "description": description,
        "source": "manual",
    }


def list_transactions_tool(conn: sqlite3.Connection, user_id: int,
                           date_from: str | None = None,
                           date_to: str | None = None,
                           category: str | None = None) -> str:
    txns = list_transactions(conn, user_id, date_from=date_from,
                             date_to=date_to, category=category)
    if not txns:
        return "No transactions found for those filters."
    lines = []
    for t in txns[:20]:  # Cap at 20 for readability
        sign = "-" if t["amount"] < 0 else "+"
        lines.append(
            f"{t['date']} — {t['description']}: {sign}${abs(t['amount']):.2f} [{t['category']}]"
        )
    suffix = f"\n(Showing {min(len(txns), 20)} of {len(txns)} transactions)" if len(txns) > 20 else ""
    return "Transactions:\n" + "\n".join(lines) + suffix


def get_budget_summary(conn: sqlite3.Connection, user_id: int,
                       year: int | None = None, month: int | None = None) -> str:
    today = local_now().date()
    y = year if year is not None else today.year
    m = month if month is not None else today.month
    spend = get_monthly_spend(conn, user_id, y, m)
    budgets = list_budgets(conn, user_id)
    return format_budget_summary(spend, budgets, y, m)


def add_budget(conn: sqlite3.Connection, user_id: int, category: str,
               amount: float, period: str = "monthly") -> str:
    upsert_budget(conn, user_id, category, amount, period)
    return f"Budget set: ${amount:.0f}/{period} for {category}."


def get_net_worth(conn: sqlite3.Connection, user_id: int) -> str:
    snapshot = get_latest_net_worth(conn, user_id)
    return format_net_worth(snapshot)


def add_net_worth_snapshot(conn: sqlite3.Connection, user_id: int,
                           snapshot_date: str | None = None,
                           assets_json: dict | None = None,
                           liabilities_json: dict | None = None,
                           total: float | None = None) -> str:
    date = snapshot_date or today_local()
    assets = assets_json or {}
    liabilities = liabilities_json or {}
    if total is None:
        total = sum(assets.values()) - sum(liabilities.values())
    insert_net_worth(conn, user_id, date, assets, liabilities, total)
    return f"Net worth snapshot recorded for {date}: ${total:,.0f}"


def get_savings_goals_tool(conn: sqlite3.Connection, user_id: int) -> str:
    goals = list_savings_goals(conn, user_id)
    return format_goals(goals)


def add_savings_goal(conn: sqlite3.Connection, user_id: int, name: str,
                     target_amount: float, target_date: str | None = None) -> str:
    insert_savings_goal(conn, user_id, name, target_amount, target_date)
    due = f" by {target_date}" if target_date else ""
    return f"Savings goal created: '{name}' — ${target_amount:,.0f}{due}"
