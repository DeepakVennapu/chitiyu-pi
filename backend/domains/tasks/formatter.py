from datetime import datetime
from utils.local_time import local_now


def _humanize(due_at: str | None) -> str:
    if not due_at:
        return "no due date"
    try:
        dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        today = local_now().date()
        delta = (dt.date() - today).days
        if delta < 0:
            return f"overdue by {-delta}d"
        if delta == 0:
            return "today"
        if delta == 1:
            return "tomorrow"
        return dt.strftime("%b %d")
    except Exception:
        return due_at[:10]


def format_task_list(tasks: list) -> str:
    if not tasks:
        return "No pending tasks. You're all caught up!"
    lines = []
    for t in tasks:
        due = _humanize(t["due_at"])
        lines.append(f"#{t['id']} {t['title']} — {due}")
    return "Tasks:\n" + "\n".join(lines)


def format_overdue_nudge(tasks: list) -> str:
    if not tasks:
        return ""
    lines = [f"• {t['title']}" for t in tasks]
    return f"Overdue tasks ({len(tasks)}):\n" + "\n".join(lines)
