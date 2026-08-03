from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import verify_api_key
from db.connection import get_connection
from db.schema import initialize_schema
from config import DB_PATH
from domains.journal.db import upsert_entry, get_entry, get_recent

router = APIRouter(prefix="/journal", tags=["journal"],
                   dependencies=[Depends(verify_api_key)])


def _conn():
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


class EntryCreate(BaseModel):
    user_id: int = 1
    raw_text: str
    summary: str | None = None
    retro_json: str | None = None


@router.post("/entry")
def save(body: EntryCreate):
    from datetime import datetime, timezone
    conn = _conn()
    date = datetime.now(timezone.utc).date().isoformat()
    upsert_entry(conn, body.user_id, date, body.raw_text, body.summary, body.retro_json)
    conn.close()
    return {"ok": True, "date": date}


@router.get("/recent")
def recent(user_id: int = 1):
    conn = _conn()
    entries = [dict(e) for e in get_recent(conn, user_id)]
    conn.close()
    return entries


@router.get("/{date}")
def get(date: str, user_id: int = 1):
    conn = _conn()
    entry = get_entry(conn, user_id, date)
    conn.close()
    if not entry:
        raise HTTPException(404, "No entry for this date")
    return entry
