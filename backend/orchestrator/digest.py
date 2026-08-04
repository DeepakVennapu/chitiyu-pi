"""
Morning digest builder — two parts:
  Part 1: Python-templated numbers block (zero LLM)
  Part 2: Sonnet 3-4 sentence forward-looking paragraph

Called by scheduler._morning_digest() at 8am daily.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import date, timedelta

import httpx

from config import POLISH_MODEL
from orchestrator.llm import call_claude

logger = logging.getLogger(__name__)

_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

_DIGEST_SHAPE_SYSTEM_PROMPT = """\
You are Chitiyu giving a brief morning briefing. Write 3-4 sentences that:
- Acknowledge the most important number from yesterday (sleep, steps, calories, or spending)
- Name the biggest challenge or opportunity for today based on the data
- Give one specific, actionable focus for today

Tone: direct, energising, specific. No filler phrases like "Let's make today great!"\
"""


def _get_headers() -> dict[str, str]:
    try:
        from config import API_KEY
        return {"X-API-Key": API_KEY}
    except Exception:
        return {}


def _get(path: str) -> dict | list | None:
    try:
        resp = httpx.get(f"{_BASE_URL}{path}", headers=_get_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("digest: GET %s failed: %s", path, exc)
        return None


def _build_numbers_block(yesterday_health: dict | None,
                         today_meals: dict | None,
                         today_tasks: list | None,
                         overdue_tasks: list | None,
                         finance_summary: dict | None) -> str:
    """Build the pure-Python numbers block — zero LLM."""
    # Health metrics yesterday
    deep_mins = "-"
    total_mins = "-"
    resting_hr = "-"
    steps = 0
    if yesterday_health:
        metrics = yesterday_health.get("metrics") or {}
        deep_mins = metrics.get("sleep_deep_mins", "-")
        total_mins = metrics.get("sleep_total_mins", "-")
        resting_hr = metrics.get("resting_hr", "-")
        steps = metrics.get("steps") or 0

    # Today's running macros
    cals = protein = fat = carbs = 0
    if today_meals:
        totals = today_meals.get("totals") or {}
        cals = totals.get("calories", 0) or 0
        protein = totals.get("protein", 0) or 0
        fat = totals.get("fat", 0) or 0
        carbs = totals.get("carbs", 0) or 0

    today_count = len(today_tasks) if today_tasks else 0
    overdue_count = len(overdue_tasks) if overdue_tasks else 0

    # Finance — GET /finance/summary/{year}/{month} returns {total_spent, total_budget, categories}
    month_spend = 0.0
    month_budget = 0.0
    if finance_summary:
        month_spend = finance_summary.get("total_spent", 0.0) or 0.0
        month_budget = finance_summary.get("total_budget", 0.0) or 0.0

    steps_fmt = f"{steps:,}" if isinstance(steps, int) else str(steps)

    return (
        f"Good morning, Deep ☀️\n\n"
        f"📊 Yesterday\n"
        f"  Sleep:  {deep_mins}min deep / {total_mins}min total | HR: {resting_hr} bpm\n"
        f"  Steps:  {steps_fmt} / 10,000\n\n"
        f"🍽️ Today so far\n"
        f"  Cal:     {cals} / 1500 kcal\n"
        f"  Protein: {protein}g / 155g\n"
        f"  Fat:     {fat}g / 45g\n"
        f"  Carbs:   {carbs}g / 117g\n\n"
        f"✅ Tasks\n"
        f"  Overdue: {overdue_count}  |  Due today: {today_count}\n\n"
        f"💰 Month spend: ${month_spend:.2f} / ${month_budget:.2f} budget"
    )


def build_morning_digest(conn: sqlite3.Connection, user_id: int) -> str:
    """
    Build the full morning digest message.
    Part 1: templated numbers (zero LLM).
    Part 2: Sonnet 3-4 sentence forward-looking paragraph.
    Returns combined string ready for Telegram.
    """
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    year, month = today[:4], today[5:7]

    yesterday_health = _get(f"/health/summary/{yesterday}")
    today_meals = _get("/health/meals/today")
    today_tasks = _get("/tasks/today")
    overdue_tasks = _get("/tasks/overdue")
    finance_summary = _get(f"/finance/summary/{year}/{month}")

    numbers_block = _build_numbers_block(
        yesterday_health, today_meals, today_tasks, overdue_tasks, finance_summary
    )

    # Part 2: Sonnet shape paragraph
    shape_paragraph = ""
    try:
        context_parts = [numbers_block]
        if overdue_tasks:
            context_parts.append(
                f"Overdue tasks: {json.dumps([t.get('title', '') for t in overdue_tasks])}"
            )
        context = "\n\n".join(context_parts)
        prompt = (
            f"Today's date: {today}\n\n"
            f"Morning data:\n{context}\n\n"
            f"Write the 3-4 sentence forward-looking paragraph."
        )
        shape_paragraph = call_claude(
            prompt, system_prompt=_DIGEST_SHAPE_SYSTEM_PROMPT,
            model=POLISH_MODEL, timeout=60
        ).strip()
    except Exception as exc:
        logger.error("digest: Sonnet shape paragraph failed: %s", exc)
        shape_paragraph = ""  # Digest sends without paragraph rather than failing entirely

    if shape_paragraph:
        return f"{numbers_block}\n\n{shape_paragraph}"
    return numbers_block
