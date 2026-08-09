# backend/orchestrator/chat_router.py
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import verify_api_key
from config import DB_PATH
from db.connection import get_connection
from db.schema import initialize_schema
import orchestrator.chat as _chat_engine

router = APIRouter(prefix="/chat", tags=["chat"],
                   dependencies=[Depends(verify_api_key)])


def _conn() -> sqlite3.Connection:
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


class ChatRequest(BaseModel):
    text: str
    user_id: int = 1


class ConfirmRequest(BaseModel):
    domain: str   # "health" | "finance" | "tasks"
    preview: Any  # dict for health/finance, list[dict] for tasks
    user_id: int = 1


@router.post("")
def chat(body: ChatRequest):
    conn = _conn()
    try:
        knowledge_context = ""
        try:
            from orchestrator.embedder import embed
            from domains.knowledge.search import semantic_search
            emb = embed(body.text)
            facts = semantic_search(conn, emb, body.user_id, top_n=5)
            if facts:
                knowledge_context = "\n".join(f"• {f['content']}" for f in facts)
        except Exception:
            pass
        return _chat_engine.build_chat_response(conn, body.user_id, body.text, knowledge_context)
    finally:
        conn.close()


@router.post("/confirm")
def confirm(body: ConfirmRequest):
    conn = _conn()
    try:
        if body.domain == "health":
            p = body.preview
            from domains.health.db import insert_meal
            from domains.health.formatter import format_meal_confirmation
            insert_meal(conn, body.user_id, p["description"], p["calories"],
                        p["protein"], p.get("fat"), p.get("carbs"))
            result = format_meal_confirmation(p["description"], p["calories"], p["protein"])
            try:
                from orchestrator.insights import trigger_insights_async
                trigger_insights_async(body.user_id, scope="today")
            except Exception:
                pass
            return {"ok": True, "result": result}

        elif body.domain == "finance":
            p = body.preview
            from domains.finance.db import insert_transaction
            from domains.finance.tools import _fire_budget_event
            insert_transaction(conn, body.user_id, p["date"], float(p["amount"]),
                               p["category"], p["description"], source="manual")
            _fire_budget_event(conn, body.user_id, p["category"], float(p["amount"]))
            try:
                from orchestrator.insights import trigger_insights_async
                trigger_insights_async(body.user_id, scope="today")
            except Exception:
                pass
            return {"ok": True, "result": f"Logged {p['description']} — ${abs(p['amount']):.2f} [{p['category']}]"}

        elif body.domain == "tasks":
            from domains.tasks.db import insert_task, insert_template
            results = []
            for item in body.preview:
                if item.get("recurrence") and item.get("anchor_date"):
                    insert_template(conn, body.user_id, title=item["title"],
                                    recurrence=item["recurrence"], anchor_date=item["anchor_date"],
                                    advance_days=1)
                else:
                    insert_task(conn, body.user_id, title=item["title"],
                                due_at=item.get("due_at"), priority=item.get("priority", 0))
                results.append(item["title"])
            conn.commit()
            return {"ok": True, "result": f"Created {len(results)} task(s): {', '.join(results)}"}

        else:
            raise HTTPException(400, f"Unknown domain: {body.domain!r}")
    finally:
        conn.close()
