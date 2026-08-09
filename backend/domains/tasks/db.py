import sqlite3
from datetime import datetime, timezone
from utils.local_time import local_now, today_local


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
    now = local_now().isoformat()
    return conn.execute(
        "SELECT * FROM tasks WHERE user_id=? AND completed_at IS NULL AND due_at < ? "
        "ORDER BY priority DESC, due_at ASC NULLS LAST",
        (user_id, now)
    ).fetchall()


def get_today_tasks(conn: sqlite3.Connection, user_id: int) -> list:
    today = today_local()
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
    result = {row["d"]: row["max_p"] for row in rows}

    # Merge recurring template dates (priority 0 unless tasks already have a higher priority)
    templates = get_active_templates(conn, user_id)
    start = date_type.fromisoformat(start_iso)
    end = date_type.fromisoformat(end_iso)
    current = start
    while current <= end:
        iso = current.isoformat()
        for t in templates:
            t = dict(t)
            if _template_fires_on(t["recurrence"], t["anchor_date"], iso):
                if iso not in result:
                    result[iso] = 0
        current += timedelta(days=1)

    return result


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


# ---------------------------------------------------------------------------
# Recurring template CRUD and instance spawn
# ---------------------------------------------------------------------------

from datetime import date as date_type, timedelta


def insert_template(conn: sqlite3.Connection, user_id: int, title: str,
                    recurrence: str, anchor_date: str, advance_days: int) -> int:
    cur = conn.execute(
        "INSERT INTO task_templates(user_id, title, recurrence, anchor_date, advance_days) "
        "VALUES (?,?,?,?,?)",
        (user_id, title, recurrence, anchor_date, advance_days)
    )
    conn.commit()
    return cur.lastrowid


def get_active_templates(conn: sqlite3.Connection, user_id: int) -> list:
    return conn.execute(
        "SELECT * FROM task_templates WHERE user_id=? ORDER BY created_at ASC",
        (user_id,)
    ).fetchall()


def _template_fires_on(recurrence: str, anchor_date: str, target_date: str) -> bool:
    anchor = date_type.fromisoformat(anchor_date)
    target = date_type.fromisoformat(target_date)
    if target < anchor:
        return False
    if recurrence == "daily":
        return True
    if recurrence == "weekly":
        return anchor.weekday() == target.weekday()
    if recurrence == "monthly":
        return anchor.day == target.day
    if recurrence == "yearly":
        return anchor.month == target.month and anchor.day == target.day
    return False


def spawn_instances_for_date(conn: sqlite3.Connection, user_id: int,
                              date_iso: str) -> list[dict]:
    today = date_type.today()
    templates = get_active_templates(conn, user_id)
    result = []
    for t in templates:
        t = dict(t)
        if not _template_fires_on(t["recurrence"], t["anchor_date"], date_iso):
            continue
        advance = t["advance_days"]
        anchor = date_type.fromisoformat(t["anchor_date"])
        if today < anchor - timedelta(days=advance):
            continue
        conn.execute(
            "INSERT OR IGNORE INTO task_instances(template_id, user_id, due_date) VALUES (?,?,?)",
            (t["id"], user_id, date_iso)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM task_instances WHERE template_id=? AND user_id=? AND due_date=? "
            "AND deleted_at IS NULL AND completed_at IS NULL",
            (t["id"], user_id, date_iso)
        ).fetchone()
        if row:
            result.append({
                "id": row["id"],
                "uid": f"i:{row['id']}",
                "template_id": t["id"],
                "title": t["title"],
                "due_date": date_iso,
                "due_at": date_iso + "T00:00:00",
                "completed_at": row["completed_at"],
                "priority": 0,
                "tags": [],
                "is_recurring": True,
            })
    return result


def complete_instance(conn: sqlite3.Connection, user_id: int, instance_id: int) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "UPDATE task_instances SET completed_at=? "
        "WHERE id=? AND user_id=? AND completed_at IS NULL",
        (now, instance_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


def delete_instance(conn: sqlite3.Connection, user_id: int, instance_id: int) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "UPDATE task_instances SET deleted_at=? WHERE id=? AND user_id=?",
        (now, instance_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0
