import sqlite3
import json
import re
from domains.tasks.db import insert_task, get_pending_tasks, complete_task, insert_template
from domains.tasks.formatter import format_task_list
from utils.local_time import today_local
from orchestrator.llm import call_claude
from config import DISPATCH_MODEL


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


# ---------------------------------------------------------------------------
# Smart NL task parsing
# ---------------------------------------------------------------------------

_PARSE_TASKS_PROMPT = """\
Parse the user's input into one or more tasks. Return a JSON array only — no explanation.

Today's date: {today}

Rules:
- If the input lists items (e.g. "groceries: chicken, onions"), create one task per item.
- Resolve relative dates ("tomorrow", "next Monday", "in 3 days") against today's date.
- due_at: ISO datetime string "YYYY-MM-DDTHH:MM:SS" or null if no date mentioned.
- priority: 2 if urgent/ASAP/critical, 1 if high/important, else 0.
- recurrence: "daily", "weekly", "monthly", "yearly", or null.
- anchor_date: "YYYY-MM-DD" for the first occurrence when recurrence is not null, else null.
- If recurring, due_at should be null.

Return format (array of objects):
[{{"title": "...", "due_at": "...|null", "priority": 0|1|2, "recurrence": "...|null", "anchor_date": "...|null"}}]

Input: {text}"""


def parse_task_input(text: str, today: str | None = None) -> list[dict]:
    """Parse NL task input into a list of structured task dicts via Haiku."""
    today = today or today_local()
    raw = call_claude(
        _PARSE_TASKS_PROMPT.format(today=today, text=text),
        model=DISPATCH_MODEL,
        timeout=20,
    )
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:cleaned.rfind("```")]
        cleaned = cleaned.strip()
    m = re.search(r'\[.*\]', cleaned, re.DOTALL)
    if not m:
        return [{"title": text.strip(), "due_at": None, "priority": 0, "recurrence": None, "anchor_date": None}]
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return [{"title": text.strip(), "due_at": None, "priority": 0, "recurrence": None, "anchor_date": None}]


def create_tasks_from_input(conn, user_id: int, text: str) -> list[dict]:
    """Parse NL text and insert all resulting tasks/templates. Returns created task dicts."""
    parsed = parse_task_input(text)
    created = []
    for item in parsed:
        if item.get("recurrence") and item.get("anchor_date"):
            tid = insert_template(
                conn, user_id,
                title=item["title"],
                recurrence=item["recurrence"],
                anchor_date=item["anchor_date"],
                advance_days=1,
            )
            created.append({
                "id": tid,
                "title": item["title"],
                "due_at": None,
                "priority": item.get("priority", 0),
                "is_recurring": True,
            })
        else:
            task_id = insert_task(
                conn, user_id,
                title=item["title"],
                due_at=item.get("due_at"),
                priority=item.get("priority", 0),
            )
            created.append({
                "id": task_id,
                "title": item["title"],
                "due_at": item.get("due_at"),
                "priority": item.get("priority", 0),
                "is_recurring": False,
            })
    return created
