import sqlite3
from domains.tasks.db import insert_task, get_pending_tasks, complete_task
from domains.tasks.formatter import format_task_list


def create_task(conn: sqlite3.Connection, user_id: int, title: str, due_at: str | None = None) -> str:
    task_id = insert_task(conn, user_id, title, due_at)
    due_msg = f" (due {due_at[:10]})" if due_at else ""
    return f"Task #{task_id} created: {title}{due_msg}"


def list_tasks(conn: sqlite3.Connection, user_id: int) -> str:
    tasks = get_pending_tasks(conn, user_id)
    return format_task_list(tasks)


def mark_task_done(conn: sqlite3.Connection, user_id: int, task_id: int) -> str:
    success = complete_task(conn, user_id, task_id)
    if success:
        return f"Task #{task_id} marked done."
    return f"Task #{task_id} not found or already complete."
