"""
Evening retrospective engine — 7-step flow from spec section 6.3.

Assembles full-day context from all domains, generates a structured
retrospective narrative via Sonnet, and stores the result via POST /journal/entry.
Triggered by scheduler at 10:00pm daily.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import date

import httpx

from config import POLISH_MODEL
from orchestrator.llm import call_claude
from domains.knowledge.search import semantic_search
from orchestrator.embedder import embed

logger = logging.getLogger(__name__)

_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

_RETRO_SYSTEM_PROMPT = """\
You are Chitiyu — a personal intelligence layer reviewing a full day's data.

User profile:
- Weight goal: 190 → 170 lbs, 10-week aggressive cut
- Calorie target: 1500 kcal | Protein: 150-160g | Fat: 40-50g | Carbs: 110-125g
- Step goal: 10,000/day | Deep sleep target: 60+ min
- Caffeine cutoff: 11am | Dinner cutoff: 6:30pm
- Finance: actively budgeting, tracking net worth

Write a daily retrospective with these sections:
1. WINS — what went well today (health, tasks, finance — specific numbers)
2. MISSES — what missed targets and why (specific, not generic)
3. PATTERNS — any cross-domain connections worth noting
4. TOMORROW — two or three concrete actions for tomorrow

Be direct and specific. Use the user's free-form note (if provided) to \
personalise the retrospective.

Return a JSON object with keys: "wins", "misses", "patterns", "tomorrow", "summary"
- wins/misses/patterns: arrays of strings
- tomorrow: array of action strings
- summary: one-paragraph plain-text overview (2-3 sentences)

Return ONLY the JSON object. No markdown fences, no explanation.\
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
        logger.warning("retro: GET %s failed: %s", path, exc)
        return None


def _post(path: str, body: dict) -> bool:
    try:
        resp = httpx.post(f"{_BASE_URL}{path}", json=body,
                          headers=_get_headers(), timeout=15)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("retro: POST %s failed: %s", path, exc)
        return False


def generate_retro(conn: sqlite3.Connection, user_id: int) -> dict:
    """
    Execute the 7-step retrospective flow.
    Returns {"raw": str, "retro_json": str, "date": str}.
    Raises on LLM failure.
    """
    today = date.today().isoformat()
    year, month = today[:4], today[5:7]

    # Step 1: Health summary
    health = _get(f"/health/summary/{today}")

    # Step 2: Finance summary
    finance = _get(f"/finance/summary/{year}/{month}")

    # Step 3: Tasks
    today_tasks = _get("/tasks/today")
    overdue_tasks = _get("/tasks/overdue")

    # Step 4: Knowledge context
    knowledge_facts: list[str] = []
    try:
        emb = embed("user goals and constraints")
        facts = semantic_search(conn, emb, user_id, top_n=5)
        knowledge_facts = [f["content"] for f in (facts or [])]
    except Exception as exc:
        logger.warning("retro: knowledge search failed: %s", exc)

    # Step 5: Journal entry (user's free-form reply, if any)
    journal = _get(f"/journal/{today}")

    # Step 6: Assemble context and call Sonnet
    sections: list[str] = [f"Date: {today}"]

    if health:
        sections.append(f"[HEALTH]\n{json.dumps(health, indent=2)}")
    if finance:
        sections.append(f"[FINANCE — {year}-{month}]\n{json.dumps(finance, indent=2)}")

    tasks_block: dict = {}
    if today_tasks:
        tasks_block["today"] = today_tasks
    if overdue_tasks:
        tasks_block["overdue"] = overdue_tasks
    if tasks_block:
        sections.append(f"[TASKS]\n{json.dumps(tasks_block, indent=2)}")

    if knowledge_facts:
        facts_text = "\n".join(f"- {f}" for f in knowledge_facts)
        sections.append(f"[KNOWLEDGE]\n{facts_text}")

    if journal and journal.get("raw_text"):
        sections.append(f"[USER NOTE]\n{journal['raw_text']}")

    context = "\n\n".join(sections)
    prompt = f"Here is today's complete data:\n\n{context}\n\nGenerate the retrospective."

    raw = call_claude(prompt, system_prompt=_RETRO_SYSTEM_PROMPT,
                      model=POLISH_MODEL, timeout=90)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[: cleaned.rfind("```")]
        cleaned = cleaned.strip()

    retro_data = json.loads(cleaned)
    retro_json = json.dumps(retro_data)

    # Step 7: Store via POST /journal/entry
    _post("/journal/entry", {
        "user_id": user_id,
        "date": today,
        "raw_text": retro_data.get("summary", ""),
        "retro_json": retro_json,
    })

    logger.info("retro: generated and stored for user=%d date=%s", user_id, today)
    return {"raw": raw, "retro_json": retro_json, "date": today}
