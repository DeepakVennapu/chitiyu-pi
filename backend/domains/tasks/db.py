import sqlite3
from utils.local_time import local_now, today_local


def insert_task(conn: sqlite3.Connection, user_id: int, title: str, due_at: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO tasks(user_id, title, due_at) VALUES (?,?,?)",
        (user_id, title, due_at)
    )
    conn.commit()
    return cur.lastrowid


def get_pending_tasks(conn: sqlite3.Connection, user_id: int) -> list:
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL ORDER BY due_at ASC NULLS LAST",
        (user_id,)
    ).fetchall()


def get_overdue_tasks(conn: sqlite3.Connection, user_id: int) -> list:
    now = local_now().isoformat()
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL AND due_at < ?",
        (user_id, now)
    ).fetchall()


def get_today_tasks(conn: sqlite3.Connection, user_id: int) -> list:
    today = today_local()
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL "
        "AND date(due_at) = ?",
        (user_id, today)
    ).fetchall()


def get_tasks_by_date(conn: sqlite3.Connection, user_id: int, date_iso: str) -> list:
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL "
        "AND date(due_at) = ?",
        (user_id, date_iso)
    ).fetchall()


def complete_task(conn: sqlite3.Connection, user_id: int, task_id: int) -> bool:
    now = local_now().isoformat()
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
