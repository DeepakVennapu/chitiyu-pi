# backend/orchestrator/chat.py
"""
Global chat engine — parses multi-domain intent from a single message.

build_chat_response() is the main entry point. It:
1. Calls Haiku once to detect which domains have loggable data and extract any prose answer
2. For each detected domain, calls the domain-specific parser to build a preview
3. Returns ChatResponse dict: prose + domain previews + suggested task actions
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any

from config import DISPATCH_MODEL
from orchestrator.llm import call_claude
from utils.local_time import today_local

logger = logging.getLogger(__name__)

_INTENT_SYSTEM = """\
You are a personal intelligence assistant. Analyze the user's message and determine:
1. Which domains have loggable data (health=meal/nutrition, finance=expense/income, tasks=task/reminder)
2. A prose response if the message is a question or needs an answer
3. Suggested "log as task" actions for recommendations you make

Return JSON only:
{{
  "prose": "<conversational answer or empty string>",
  "health_extract": "<meal description fragment or null>",
  "finance_extract": "<expense description fragment or null>",
  "tasks_extract": "<task description fragment or null>",
  "actions": [
    {{"label": "<button label>", "domain": "tasks", "prefill": "<pre-fill text>"}}
  ]
}}

Today: {today}

Rules:
- health_extract: only if the message describes eating/drinking something
- finance_extract: only if the message describes spending money or income
- tasks_extract: only if the message describes a task, reminder, or to-do
- prose: always answer questions; for pure logs with no question, use empty string
- actions: only when you make a recommendation that could become a task
- For knowledge graph queries (who is X, what does X like), answer in prose using provided context"""


def _extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:cleaned.rfind("```")]
        cleaned = cleaned.strip()
    m = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return {}


def build_chat_response(
    conn: sqlite3.Connection,
    user_id: int,
    text: str,
    knowledge_context: str = "",
) -> dict[str, Any]:
    """
    Parse a free-text message. Returns:
    {"prose": str, "domains": [{"domain", "preview", "extract"}], "actions": [...]}
    """
    today = today_local()
    context_block = f"Context from memory:\n{knowledge_context}\n\n" if knowledge_context else ""
    intent_prompt = f"{context_block}User message: {text}"

    raw = call_claude(
        intent_prompt,
        system_prompt=_INTENT_SYSTEM.format(today=today),
        model=DISPATCH_MODEL,
        timeout=30,
    )
    intent = _extract_json(raw)

    domains: list[dict] = []

    health_extract = intent.get("health_extract")
    if health_extract:
        try:
            from domains.health.tools import parse_meal_macros
            preview = parse_meal_macros(health_extract)
            if preview:
                domains.append({"domain": "health", "preview": preview, "extract": health_extract})
        except Exception as exc:
            logger.warning("chat: health parse failed: %s", exc)

    finance_extract = intent.get("finance_extract")
    if finance_extract:
        try:
            from domains.finance.tools import parse_transaction_input
            preview = parse_transaction_input(finance_extract)
            if preview:
                domains.append({"domain": "finance", "preview": preview, "extract": finance_extract})
        except Exception as exc:
            logger.warning("chat: finance parse failed: %s", exc)

    tasks_extract = intent.get("tasks_extract")
    if tasks_extract:
        try:
            from domains.tasks.tools import parse_task_input
            parsed_tasks = parse_task_input(tasks_extract, today=today)
            if parsed_tasks:
                tasks_with_flag = [
                    {**t, "is_recurring": bool(t.get("recurrence"))}
                    for t in parsed_tasks
                ]
                domains.append({"domain": "tasks", "preview": tasks_with_flag, "extract": tasks_extract})
        except Exception as exc:
            logger.warning("chat: tasks parse failed: %s", exc)

    return {
        "prose": intent.get("prose", ""),
        "domains": domains,
        "actions": intent.get("actions", []),
    }
