"""
Insights API endpoints.
  POST /insights/generate — trigger background insight generation
  GET  /insights/latest   — fetch latest stored insight cards
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import verify_api_key
from db.connection import get_connection
from db.schema import initialize_schema
from config import DB_PATH

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insights", tags=["insights"])


def _get_conn():
    conn = get_connection(DB_PATH)
    initialize_schema(conn)
    return conn


class GenerateRequest(BaseModel):
    scope: str = "today"
    user_id: int = 1


@router.post("/generate", dependencies=[Depends(verify_api_key)])
def generate_insights_endpoint(req: GenerateRequest):
    """
    Trigger background insight generation. Returns immediately.
    App polls GET /insights/latest to see when new cards arrive.
    """
    if req.scope not in ("today", "week"):
        raise HTTPException(status_code=422, detail="scope must be 'today' or 'week'")

    try:
        from orchestrator.insights import trigger_insights_async
        trigger_insights_async(req.user_id, req.scope)
    except Exception as exc:
        logger.error("Failed to launch insight generation: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to start insight generation")

    return {"status": "generating", "scope": req.scope}


@router.get("/latest", dependencies=[Depends(verify_api_key)])
def get_latest_insights_endpoint(
    scope: str = Query("today", description="'today' or 'week'"),
    user_id: int = Query(1),
):
    """
    Return the latest stored insight cards for the given scope.
    404 if insights have never been generated.
    """
    if scope not in ("today", "week"):
        raise HTTPException(status_code=422, detail="scope must be 'today' or 'week'")

    conn = _get_conn()
    try:
        from orchestrator.insights_store import get_latest_insights as _get
        result = _get(conn, user_id, scope)
    except Exception as exc:
        logger.error("Failed to fetch insights: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch insights")
    finally:
        conn.close()

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No insights generated yet for scope='{scope}'. "
                   f"POST /insights/generate to trigger generation."
        )

    # Parse cards_json so the response is a proper JSON array, not a string
    try:
        result["cards"] = json.loads(result["cards_json"])
    except Exception:
        result["cards"] = []

    return result
