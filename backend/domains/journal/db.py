import sqlite3


def upsert_entry(conn: sqlite3.Connection, user_id: int, date: str,
                 raw_text: str, summary: str | None = None,
                 retro_json: str | None = None) -> None:
    conn.execute(
        """INSERT INTO journal_entries(user_id, date, raw_text, summary, retro_json)
           VALUES (?,?,?,?,?)
           ON CONFLICT(user_id, date) DO UPDATE SET
             raw_text=excluded.raw_text,
             summary=excluded.summary,
             retro_json=excluded.retro_json""",
        (user_id, date, raw_text, summary, retro_json)
    )
    conn.commit()


def get_entry(conn: sqlite3.Connection, user_id: int, date: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM journal_entries WHERE user_id=? AND date=?", (user_id, date)
    ).fetchone()
    return dict(row) if row else None


def get_recent(conn: sqlite3.Connection, user_id: int, limit: int = 7) -> list:
    return conn.execute(
        "SELECT * FROM journal_entries WHERE user_id=? ORDER BY date DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
