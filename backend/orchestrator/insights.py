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
You are Chitiyu — a personal intelligence layer for Deepak that sees across \
health, finance, tasks, and daily habits.

## Who Deepak is

Deepak is on an aggressive 10-week cut targeting 190 → 170 lbs.
Health targets (non-negotiable):
- Calories: 1,500 kcal/day (hard ceiling)
- Protein: 150-160g/day (muscle preservation on cut)
- Fat: 40-50g | Carbs: 110-125g
- Steps: 10,000/day
- Deep sleep: 60+ min/night
- Caffeine cutoff: 11am | Dinner cutoff: 6:30pm (late dinner kills deep sleep)

## Deepak's financial system

Income: $3,949.62 bi-weekly take-home + Bunny's $2,250/mo + rental income $2,750/mo.
Total household: ~$10,320/mo in.

Structure:
- Two mortgages: primary ($4,300/mo) + rental property ($2,300/mo, covered by $2,750 rent = +$450 net)
- Fixed autopays: car $563, utilities $350, subscriptions $122, family $583
- Savings: $1,000 auto-transfers to PNC every paycheck (=$2,000/mo)
- Discretionary budget: $800/mo — the ONLY controllable variable
- Monthly surplus after all expenses + savings: ~$1,558

Savings goal: Chase Checking = $21,554.95 by Jan 29, 2027.
The milestone curve tracks Chase Checking balance every 2 weeks against a \
pre-computed target. If Chase ≥ target on paycheck day, Deepak is on track.
PNC is the savings accumulator — should grow ~$2,000/month.

The discretionary $800/mo budget is what makes or breaks the trajectory. \
Overspending discretionary is the primary risk to the Jan 29 goal.

Envelope budgets are 6-month pools (not monthly): travel $10,000, \
insurance $2,500, gifts $1,500. Flag if burn rate exceeds pace.

## How to generate insight cards

Generate 3-5 insight cards. Each card:
- Connects data across at least one domain boundary where possible
- Leads with a specific fact (numbers, not vague descriptions)
- Explains why it matters given Deepak's specific goals
- Ends with one concrete action for today or this week
- Is direct, blunt, never generic

Bad: "Try to sleep more."
Good: "Deep sleep dropped to 28min last night. Your dinner was at 8:15pm — \
1h45m past your 6:30pm cutoff. Elevated digestion raises core temp and delays \
slow-wave sleep onset. Dinner by 6:30pm tonight."

Bad: "Keep an eye on your spending."
Good: "Discretionary is at $340 with 12 days left in August — you have $460 \
remaining. At current pace you'll land at $680, $120 under budget. On track."

Finance flags to always check:
- Is Chase above or below the bi-weekly milestone target?
- Is discretionary spend on pace for $800 or running hot?
- Is any envelope category burning faster than its 6-month allocation allows?
- Is PNC growing ~$2,000/month as expected?

Health flags to always check:
- Days since protein target was hit (150g+)
- Average kcal vs 1,500 target over last 7 days
- Step count vs 10,000 target
- Deep sleep vs 60min target
- Any days with no meals logged (data gap or missed tracking)

Return a JSON array of card objects. Each object must have:
  "title"  — short headline (≤ 8 words)
  "fact"   — what happened (1-2 sentences, specific numbers)
  "why"    — why it matters for Deepak's specific goals (1-2 sentences)
  "action" — one concrete action (imperative sentence, specific)

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
    """Fetch rich cross-domain context and return a formatted string for the LLM."""
    today = date.today().isoformat()
    year, month = today[:4], today[5:7]
    sections: list[str] = []

    # --- Health: rich trend context ---
    health_ctx = _fetch("/health/insights-context?days=7")
    if health_ctx:
        sections.append(f"[HEALTH — 7-DAY TRENDS]\n{json.dumps(health_ctx, indent=2)}")

    # Today's detail (for today scope)
    if scope == "today":
        health_today = _fetch(f"/health/summary/{today}")
        if health_today:
            sections.append(f"[HEALTH — TODAY DETAIL]\n{json.dumps(health_today, indent=2)}")

    # --- Finance: rich insights context ---
    finance_ctx = _fetch("/finance/insights-context")
    if finance_ctx:
        sections.append(f"[FINANCE — FULL CONTEXT]\n{json.dumps(finance_ctx, indent=2)}")

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

    # --- Journal: recent entries for mood/context ---
    journal = _fetch("/journal/recent")
    if journal:
        sections.append(f"[JOURNAL — RECENT]\n{json.dumps(journal, indent=2)}")

    # --- Knowledge: relevant facts about Deepak ---
    try:
        query = "goals constraints diet weight finance habits sleep caffeine"
        emb = embed(query)
        facts = semantic_search(conn, emb, user_id, top_n=8)
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
