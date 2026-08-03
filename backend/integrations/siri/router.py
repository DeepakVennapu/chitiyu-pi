# backend/integrations/siri/router.py
"""
Siri Shortcuts endpoints — thin wrappers on domain tools.

All responses are plain prose (≤2 sentences) suitable for Siri to read aloud.
No markdown, no bullet points, no parentheticals with numbers.

Note: domain tools (log_meal, create_task, get_today_totals) return strings,
not dicts. The string is passed directly to Haiku for a spoken confirmation.
"""
from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import verify_api_key
from config import DISPATCH_MODEL, DB_PATH
from db.connection import get_connection
from domains.health.tools import log_meal, get_today_totals
from domains.tasks.tools import create_task
from orchestrator.llm import call_claude

router = APIRouter(prefix="/siri", tags=["siri"])

SPOKEN_SYSTEM = (
    "You are Chitiyu, a personal intelligence assistant. "
    "Generate a single spoken confirmation of 1-2 sentences. "
    "Plain prose only — no markdown, no bullets, no numbers in parentheses. "
    "Be warm and direct. Do not repeat back the raw data verbatim."
)


class SiriRequest(BaseModel):
    text: str
    user_id: int = 1


def _get_conn():
    from db.schema import initialize_schema
    c = get_connection(DB_PATH)
    initialize_schema(c)
    try:
        yield c
    finally:
        c.close()


# ---------------------------------------------------------------------------
# POST /siri/log-meal
# ---------------------------------------------------------------------------

@router.post("/log-meal")
def siri_log_meal(
    req: SiriRequest,
    _: None = Depends(verify_api_key),
    conn: sqlite3.Connection = Depends(_get_conn),
) -> dict:
    """Dictate a meal — Haiku parses it, returns a spoken confirmation."""
    try:
        result_text = log_meal(conn, req.user_id, req.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    prompt = (
        f"The user said: '{req.text}'. "
        f"We logged: {result_text}. "
        "Generate a brief spoken confirmation."
    )
    spoken = call_claude(prompt, SPOKEN_SYSTEM, DISPATCH_MODEL, timeout=15.0)
    return {"spoken": spoken, "result": result_text}


# ---------------------------------------------------------------------------
# POST /siri/log-expense
# ---------------------------------------------------------------------------

@router.post("/log-expense")
def siri_log_expense(
    req: SiriRequest,
    _: None = Depends(verify_api_key),
    conn: sqlite3.Connection = Depends(_get_conn),
) -> dict:
    """
    Dictate an expense. Calls finance add_transaction when Plan 2 is live.
    Stub: acknowledges receipt and instructs user to confirm in the app.
    Replace the stub block with the real tool call after Plan 2 ships.
    """
    # --- Plan 2 stub: replace this block once finance tools exist ---
    # from domains.finance.tools import add_transaction
    # result_text = add_transaction(conn, req.user_id, req.text)
    # prompt = (
    #     f"The user said: '{req.text}'. "
    #     f"We logged the expense: {result_text}. "
    #     "Confirm it was logged and note whether this category is near its budget."
    # )
    # spoken = call_claude(prompt, SPOKEN_SYSTEM, DISPATCH_MODEL, timeout=15.0)
    # return {"spoken": spoken, "result": result_text}
    # --- end stub ---

    spoken = (
        f"Got it — I heard '{req.text}'. "
        "Finance logging isn't wired yet; open the app to confirm this expense."
    )
    return {"spoken": spoken, "transaction": None}


# ---------------------------------------------------------------------------
# POST /siri/add-task
# ---------------------------------------------------------------------------

@router.post("/add-task")
def siri_add_task(
    req: SiriRequest,
    _: None = Depends(verify_api_key),
    conn: sqlite3.Connection = Depends(_get_conn),
) -> dict:
    """Dictate a task — creates it and returns a spoken confirmation."""
    try:
        result_text = create_task(conn, req.user_id, req.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    prompt = (
        f"The user asked to add: '{req.text}'. "
        f"Result: {result_text}. "
        "Confirm task was added."
    )
    spoken = call_claude(prompt, SPOKEN_SYSTEM, DISPATCH_MODEL, timeout=15.0)
    return {"spoken": spoken, "result": result_text}


# ---------------------------------------------------------------------------
# GET /siri/macros
# ---------------------------------------------------------------------------

@router.get("/macros")
def siri_macros(
    user_id: int = 1,
    _: None = Depends(verify_api_key),
    conn: sqlite3.Connection = Depends(_get_conn),
) -> dict:
    """Return today's macro totals as a Siri-readable spoken summary."""
    try:
        totals_text = get_today_totals(conn, user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    prompt = (
        f"Today's nutrition summary: {totals_text}. "
        "Give a 1-2 sentence spoken version."
    )
    spoken = call_claude(prompt, SPOKEN_SYSTEM, DISPATCH_MODEL, timeout=15.0)
    return {"spoken": spoken, "totals": totals_text}
