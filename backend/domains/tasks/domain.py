import sqlite3
from domains.base import BaseDomain
from domains.tasks.tools import create_task, list_tasks, mark_task_done
from domains.tasks.db import get_overdue_tasks
from domains.tasks.formatter import format_overdue_nudge

_SYSTEM = """\
You are a task management assistant. Help the user manage their to-do list.
Available tools: create_task, list_tasks, mark_task_done
Respond with JSON to call a tool: {"tool": "name", "args": {...}}
If no tool is needed, reply in plain text."""


class TasksDomain(BaseDomain):
    name = "tasks"

    @property
    def tools(self) -> dict:
        return {
            "create_task": create_task,
            "list_tasks": list_tasks,
            "mark_task_done": mark_task_done,
        }

    def build_system_prompt(self) -> str:
        return _SYSTEM

    def inject_context(self, conn: sqlite3.Connection, user_id: int, message: str) -> str:
        overdue = get_overdue_tasks(conn, user_id)
        if overdue:
            return f"Context: {len(overdue)} overdue tasks.\n{format_overdue_nudge(overdue)}"
        return ""
