import sqlite3
from domains.base import BaseDomain
from domains.health.tools import log_meal, get_today_meals_tool, get_today_totals, log_health_sync
from domains.health.db import get_today_meals
from domains.health.formatter import TARGETS

_SYSTEM = f"""\
You are a health and nutrition assistant. User targets: {TARGETS['calories']} kcal/day,
{TARGETS['protein']}g protein, {TARGETS['fat']}g fat, {TARGETS['carbs']}g carbs.
Step goal: 10,000/day. Deep sleep target: 60+ min. Dinner cutoff: 6:30pm. Caffeine cutoff: 11am.
Available tools: log_meal, get_today_meals, get_today_totals, log_health_sync
Respond with JSON to call a tool: {{"tool": "name", "args": {{...}}}}
If no tool is needed, reply in plain text."""


class HealthDomain(BaseDomain):
    name = "health"

    @property
    def tools(self) -> dict:
        return {
            "log_meal": log_meal,
            "get_today_meals": get_today_meals_tool,
            "get_today_totals": get_today_totals,
            "log_health_sync": log_health_sync,
        }

    def build_system_prompt(self) -> str:
        return _SYSTEM

    def inject_context(self, conn: sqlite3.Connection, user_id: int, message: str) -> str:
        from datetime import datetime, timezone
        from domains.health.formatter import TARGETS
        meals = get_today_meals(conn, user_id)
        total_cal = sum(m["calories"] or 0 for m in meals)
        total_pro = sum(m["protein"] or 0 for m in meals)
        return (f"Today so far: {total_cal}/{TARGETS['calories']} kcal, "
                f"{total_pro:.0f}/{TARGETS['protein']}g protein, {len(meals)} meals logged.")
