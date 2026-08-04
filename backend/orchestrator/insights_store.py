"""
Thin persistence layer for insight cards.
One row per (user_id, scope) — always the most recent generation.
"""
import sqlite3
from datetime import datetime, timezone


def store_insights(conn: sqlite3.Connection, user_id: int, scope: str, cards_json: str) -> None:
    """Upsert insight cards for the given scope."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO insights (user_id, scope, cards_json, generated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, scope) DO UPDATE SET
            cards_json   = excluded.cards_json,
            generated_at = excluded.generated_at
        """,
        (user_id, scope, cards_json, now),
    )
    conn.commit()


def get_latest_insights(conn: sqlite3.Connection, user_id: int, scope: str) -> dict | None:
    """Return the latest insight record for (user_id, scope), or None if not yet generated."""
    row = conn.execute(
        "SELECT scope, cards_json, generated_at FROM insights WHERE user_id = ? AND scope = ?",
        (user_id, scope),
    ).fetchone()
    if row is None:
        return None
    return {
        "scope": row["scope"],
        "cards_json": row["cards_json"],
        "generated_at": row["generated_at"],
    }
