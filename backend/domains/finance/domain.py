# backend/domains/finance/domain.py
import sqlite3

from domains.base import BaseDomain
from domains.finance.tools import (
    add_budget,
    add_net_worth_snapshot,
    add_savings_goal,
    add_transaction,
    get_budget_summary,
    get_net_worth,
    get_savings_goals_tool,
    list_transactions_tool,
)

_SYSTEM = """\
You are a personal finance assistant. Help the user track expenses, budgets, net worth, and savings goals.

Categories for expenses: groceries, dining, gas, transport, health, clothing, entertainment,
utilities, rent, subscriptions, travel, shopping, savings, income, other.

Available tools:
- add_transaction: log an expense or income (accepts natural language)
- list_transactions: list recent transactions
- get_budget_summary: show spending vs budgets for a month
- add_budget: set a monthly or weekly budget for a category
- get_net_worth: get latest net worth snapshot
- add_net_worth_snapshot: record new net worth (manual — no live sync until Phase 2)
- get_savings_goals: list savings goals with progress
- add_savings_goal: create a new savings goal

Respond with JSON to call a tool: {"tool": "name", "args": {...}}
If no tool is needed, reply in plain text.
When adding a transaction, prefer negative amounts for expenses and positive for income."""


class FinanceDomain(BaseDomain):
    name = "finance"

    @property
    def tools(self) -> dict:
        return {
            "add_transaction": add_transaction,
            "list_transactions": list_transactions_tool,
            "get_budget_summary": get_budget_summary,
            "add_budget": add_budget,
            "get_net_worth": get_net_worth,
            "add_net_worth_snapshot": add_net_worth_snapshot,
            "get_savings_goals": get_savings_goals_tool,
            "add_savings_goal": add_savings_goal,
        }

    def build_system_prompt(self) -> str:
        return _SYSTEM

    def inject_context(self, conn: sqlite3.Connection, user_id: int, message: str) -> str:
        from datetime import datetime, timezone
        from domains.finance.db import get_monthly_spend, list_budgets
        today = datetime.now(timezone.utc).date()
        try:
            spend = get_monthly_spend(conn, user_id, today.year, today.month)
            budgets = list_budgets(conn, user_id)
            if budgets:
                import calendar
                month_name = calendar.month_name[today.month]
                budget_map = {b["category"]: b["amount"] for b in budgets}
                lines = [f"{month_name} spend context:"]
                for cat, spent in spend.items():
                    limit = budget_map.get(cat)
                    if limit:
                        lines.append(f"  {cat}: ${spent:.0f} / ${limit:.0f}")
                    else:
                        lines.append(f"  {cat}: ${spent:.0f}")
                return "\n".join(lines)
        except Exception:
            pass
        return ""
