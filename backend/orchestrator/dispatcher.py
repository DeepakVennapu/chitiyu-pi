# backend/orchestrator/dispatcher.py
import json, logging, sqlite3
from utils.local_time import local_now

logger = logging.getLogger(__name__)


def post_event(conn: sqlite3.Connection, user_id: int, domain: str,
               event_type: str, payload: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO notification_events(user_id, domain, event_type, payload_json) VALUES (?,?,?,?)",
        (user_id, domain, event_type, json.dumps(payload or {}))
    )
    conn.commit()


async def dispatch_pending(conn: sqlite3.Connection, bot) -> None:
    rows = conn.execute(
        "SELECT * FROM notification_events WHERE delivered_at IS NULL ORDER BY created_at"
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
            text = payload.get("text", f"[{row['domain']}:{row['event_type']}]")
            await bot.send_message(chat_id=payload.get("chat_id", 0), text=text)
            conn.execute(
                "UPDATE notification_events SET delivered_at=? WHERE id=?",
                (local_now().isoformat(), row["id"])
            )
            conn.commit()
        except Exception as e:
            logger.warning("dispatch failed for event %s: %s", row["id"], e)
