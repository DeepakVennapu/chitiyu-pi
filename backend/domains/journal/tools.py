import sqlite3
from datetime import datetime, timezone
from orchestrator.llm import call_claude
from domains.journal.db import upsert_entry
from config import POLISH_MODEL

_SUMMARIZE = """\
Summarize this journal entry in 2-3 concise sentences. Keep key facts and emotions.
Entry: {text}"""


def save_journal_entry(conn: sqlite3.Connection, user_id: int, text: str) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        summary = call_claude(_SUMMARIZE.format(text=text), model=POLISH_MODEL, timeout=30)
    except Exception:
        summary = text[:200]
    upsert_entry(conn, user_id, today, text, summary)
    return "Journal entry saved for today."
