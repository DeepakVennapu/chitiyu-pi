"""
Cross-domain insight generation engine.

generate_insights()      — blocking: fetch context → Sonnet → store → fire event
trigger_insights_async() — non-blocking daemon thread wrapper
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import date, timedelta

import httpx

from config import POLISH_MODEL
from orchestrator.llm import call_claude
from orchestrator.insights_store import store_insights
from orchestrator.dispatcher import post_event
from domains.knowledge.search import semantic_search
from orchestrator.embedder import embed

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — verbatim from spec section 6.3
# ---------------------------------------------------------------------------
_INSIGHT_SYSTEM_PROMPT = """\
You are Chitiyu — a personal intelligence layer that sees across health, \
finance, tasks, and daily habits.

User profile:
- Weight goal: 190 → 170 lbs, 10-week aggressive cut
- Calorie target: 1500 kcal | Protein: 150-160g | Fat: 40-50g | Carbs: 110-125g
- Step goal: 10,000/day | Deep sleep target: 60+ min
- Caffeine cutoff: 11am | Dinner cutoff: 6:30pm
- Finance: actively budgeting, tracking net worth

Generate 3-5 insight cards. Each card:
- Connects data across at least one domain boundary where possible
- Leads with what happened (fact)
- Explains why it matters (implication)
- Ends with one concrete action for today or this week
- Is direct, specific, never generic

Bad: "Try to sleep more."
Good: "Deep sleep dropped to 28min last night. Your dinner was at 8:15pm — \
1h45m past your 6:30pm cutoff. Elevated digestion raises core temp and delays \
slow-wave sleep onset. Dinner by 6:30pm tonight."

Return a JSON array of card objects. Each object must have:
  "title"  — short headline (≤ 8 words)
  "fact"   — what happened (1-2 sentences)
  "why"    — why it matters (1-2 sentences)
  "action" — one concrete action (imperative sentence)

Return ONLY the JSON array. No markdown fences, no explanation.\
"""

_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
_HEADERS = {}  # auth header injected below — see _get_headers()


def _get_headers() -> dict[str, str]:
    try:
        from config import API_KEY
        return {"X-API-Key": API_KEY}
    except Exception:
        return {}


def _fetch(path: str) -> dict | list | None:
    """GET a local domain endpoint. Returns parsed JSON or None on error."""
    try:
        resp = httpx.get(f"{_BASE_URL}{path}", headers=_get_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("insights: fetch %s failed: %s", path, exc)
        return None


def _assemble_context(conn: sqlite3.Connection, user_id: int, scope: str) -> str:
    """Fetch data from all domains and return a formatted context string."""
    today = date.today().isoformat()
    year, month = today[:4], today[5:7]

    sections: list[str] = []

    # --- Health ---
    if scope == "today":
        health = _fetch(f"/health/summary/{today}")
        if health:
            sections.append(f"[HEALTH — TODAY]\n{json.dumps(health, indent=2)}")
    else:
        # week: last 7 days
        days = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        health_week = []
        for d in days:
            h = _fetch(f"/health/summary/{d}")
            if h:
                health_week.append(h)
        if health_week:
            sections.append(f"[HEALTH — LAST 7 DAYS]\n{json.dumps(health_week, indent=2)}")

    # --- Finance ---
    finance = _fetch(f"/finance/summary/{year}/{month}")
    if finance:
        sections.append(f"[FINANCE — {year}-{month}]\n{json.dumps(finance, indent=2)}")

    # --- Tasks ---
    today_tasks = _fetch("/tasks/today")
    overdue_tasks = _fetch("/tasks/overdue")
    tasks_block: dict = {}
    if today_tasks:
        tasks_block["today"] = today_tasks
    if overdue_tasks:
        tasks_block["overdue"] = overdue_tasks
    if tasks_block:
        sections.append(f"[TASKS]\n{json.dumps(tasks_block, indent=2)}")

    # --- Knowledge context ---
    try:
        query = "user goals and constraints diet weight finance habits"
        emb = embed(query)
        facts = semantic_search(conn, emb, user_id, top_n=5)
        if facts:
            facts_text = "\n".join(f"- {f['content']}" for f in facts)
            sections.append(f"[KNOWLEDGE — RELEVANT FACTS]\n{facts_text}")
    except Exception as exc:
        logger.warning("insights: knowledge search failed: %s", exc)

    if not sections:
        return "No data available yet."

    header = f"Scope: {scope} | Date: {today}"
    return f"{header}\n\n" + "\n\n".join(sections)


def generate_insights(conn: sqlite3.Connection, user_id: int, scope: str) -> list[dict]:
    """
    Fetch cross-domain context, call Sonnet, store result, fire insight_ready event.
    Returns the parsed list of card dicts.
    Raises on LLM failure — caller (thread) logs and swallows.
    """
    if scope not in ("today", "week"):
        raise ValueError(f"Invalid scope: {scope!r}. Must be 'today' or 'week'.")

    context = _assemble_context(conn, user_id, scope)
    prompt = f"Here is the user's data:\n\n{context}\n\nGenerate the insight cards."

    raw = call_claude(prompt, system_prompt=_INSIGHT_SYSTEM_PROMPT,
                      model=POLISH_MODEL, timeout=90)

    # Strip markdown fences if model wraps despite instructions
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

    cards = json.loads(cleaned)
    if not isinstance(cards, list):
        raise ValueError(f"Expected JSON array from Sonnet, got: {type(cards)}")

    cards_json = json.dumps(cards)
    store_insights(conn, user_id, scope, cards_json)

    post_event(conn, user_id=user_id, domain="orchestrator",
               event_type="insight_ready",
               payload={"scope": scope, "card_count": len(cards)})

    logger.info("insights: generated %d cards (scope=%s, user=%d)", len(cards), scope, user_id)
    return cards


def trigger_insights_async(user_id: int, scope: str = "today") -> None:
    """
    Fire-and-forget: launch generate_insights in a daemon thread.
    Opens its own DB connection — SQLite connections are not thread-safe.
    The calling request returns immediately. Failures are logged, not raised.
    """
    def _run() -> None:
        from db.connection import get_connection
        from db.schema import initialize_schema
        from config import DB_PATH
        try:
            conn = get_connection(DB_PATH)
            initialize_schema(conn)
            generate_insights(conn, user_id, scope)
            conn.close()
        except Exception as exc:
            logger.error("insights background task failed (scope=%s): %s", scope, exc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
