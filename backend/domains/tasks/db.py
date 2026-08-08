import sqlite3
from datetime import datetime, timezone


def insert_task(conn: sqlite3.Connection, user_id: int, title: str,
                due_at: str | None = None, priority: int = 0) -> int:
    cur = conn.execute(
        "INSERT INTO tasks(user_id, title, due_at, priority) VALUES (?,?,?,?)",
        (user_id, title, due_at, priority)
    )
    conn.commit()
    return cur.lastrowid


def get_pending_tasks(conn: sqlite3.Connection, user_id: int) -> list:
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL "
        "ORDER BY priority DESC, due_at ASC NULLS LAST",
        (user_id,)
    ).fetchall()


def get_overdue_tasks(conn: sqlite3.Connection, user_id: int) -> list:
    now = datetime.now(timezone.utc).isoformat()
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL AND due_at < ? "
        "ORDER BY priority DESC, due_at ASC NULLS LAST",
        (user_id, now)
    ).fetchall()


def get_today_tasks(conn: sqlite3.Connection, user_id: int) -> list:
    today = datetime.now(timezone.utc).date().isoformat()
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL "
        "AND date(due_at) = ? "
        "ORDER BY priority DESC, due_at ASC NULLS LAST",
        (user_id, today)
    ).fetchall()


def get_tasks_by_date(conn: sqlite3.Connection, user_id: int, date_iso: str) -> list:
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL "
        "AND date(due_at) = ? "
        "ORDER BY priority DESC, due_at ASC NULLS LAST",
        (user_id, date_iso)
    ).fetchall()


def get_dates_summary(conn: sqlite3.Connection, user_id: int,
                      start_iso: str, end_iso: str) -> dict[str, int]:
    rows = conn.execute(
        "SELECT date(due_at) as d, MAX(priority) as max_p "
        "FROM tasks "
        "WHERE user_id=? AND completed_at IS NULL "
        "AND date(due_at) BETWEEN ? AND ? "
        "GROUP BY date(due_at)",
        (user_id, start_iso, end_iso)
    ).fetchall()
    return {row["d"]: row["max_p"] for row in rows}


def complete_task(conn: sqlite3.Connection, user_id: int, task_id: int) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "UPDATE tasks SET completed_at=? WHERE id=? AND user_id=? AND completed_at IS NULL",
        (now, task_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


def delete_task(conn: sqlite3.Connection, user_id: int, task_id: int) -> bool:
    cur = conn.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id))
    conn.commit()
    return cur.rowcount > 0
