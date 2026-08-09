# Tasks Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the Tasks tab with calendar styling fixes, date indicators, priority labels, and recurring task templates.

**Architecture:** Backend gains two new tables (`task_templates`, `task_instances`) and a dates-summary endpoint; existing `tasks` table priority column is exposed in the UI. Frontend CalendarPicker and DayStrip gain dot indicators; Add Task sheet gains priority picker and recurrence options. Recurring instances are spawned on-demand when a date is loaded.

**Tech Stack:** FastAPI + SQLite (backend), Expo React Native + TypeScript (frontend), pytest (tests)

## Global Constraints

- Backend lives at `~/deep-workspace/chitiyu-pi/backend/`
- Frontend lives at `~/deep-workspace/chitiyu-pi/app/`
- Tests live at `~/deep-workspace/chitiyu-pi/tests/`
- SQLite schema is initialized via `initialize_schema()` in `backend/db/schema.py` — all DDL goes there using `CREATE TABLE IF NOT EXISTS`
- Run backend tests from repo root: `cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/<file> -v`
- Priority integers: 0=normal, 1=high, 2=urgent
- Recurrence values: `'none'`, `'daily'`, `'weekly'`, `'monthly'`, `'yearly'`
- Default advance_days per recurrence: daily=1, weekly=1, monthly=7, yearly=30; "show in advance" overrides to 365
- All dates are `YYYY-MM-DD` strings; all datetimes are ISO8601 UTC strings
- Do not use `conn.close()` in tests — the `conn` fixture handles teardown

---

## File Map

**Backend — new/modified:**
- `backend/db/schema.py` — add `task_templates` and `task_instances` tables
- `backend/domains/tasks/db.py` — add template CRUD, instance spawn logic, dates-summary query, priority sort
- `backend/domains/tasks/router.py` — add `POST /tasks/templates`, `GET /tasks/dates-summary`, wire priority into `POST /tasks/`

**Backend — tests:**
- `tests/test_tasks_db.py` — extend with template, instance, priority, dates-summary tests
- `tests/test_tasks_router.py` — new file, router-level tests for new endpoints

**Frontend — modified:**
- `app/lib/api.ts` — update `Task` interface (priority as int), add `addTask` priority param, add `getTasksDatesSummary`, add `createTaskTemplate`
- `app/components/TaskRow.tsx` — add priority dot prefix
- `app/app/(tabs)/tasks.tsx` — add priority picker + recurrence UI in Add Task sheet, fetch dates-summary, pass dot data to DayStrip and CalendarPicker
- `app/app/(tabs)/tasks.tsx` (CalendarPicker) — replace today ring with dot below number; add task-indicator dot
- `app/app/(tabs)/tasks.tsx` (DayStrip) — add task-indicator dot below day number; fix today styling

---

### Task 1: Schema — add task_templates and task_instances tables

**Files:**
- Modify: `backend/db/schema.py`
- Test: `tests/test_schema.py` (extend existing)

**Interfaces:**
- Produces: `task_templates(id, user_id, title, recurrence, anchor_date, advance_days, created_at)` and `task_instances(id, template_id, user_id, due_date, completed_at, deleted_at, created_at)` tables available to all subsequent tasks

- [ ] **Step 1: Write the failing test**

Add to `tests/test_schema.py`:

```python
def test_task_templates_table_exists(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='task_templates'"
    ).fetchone()
    assert row is not None

def test_task_instances_table_exists(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='task_instances'"
    ).fetchone()
    assert row is not None
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_schema.py::test_task_templates_table_exists tests/test_schema.py::test_task_instances_table_exists -v
```

Expected: FAIL — tables don't exist yet.

- [ ] **Step 3: Add tables to schema**

In `backend/db/schema.py`, inside the `executescript` string, after the existing `tasks` table block, add:

```sql
CREATE TABLE IF NOT EXISTS task_templates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL DEFAULT 1,
    title        TEXT NOT NULL,
    recurrence   TEXT NOT NULL DEFAULT 'none' CHECK(recurrence IN ('none','daily','weekly','monthly','yearly')),
    anchor_date  TEXT NOT NULL,
    advance_days INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS task_instances (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id  INTEGER NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL DEFAULT 1,
    due_date     TEXT NOT NULL,
    completed_at TEXT,
    deleted_at   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(template_id, due_date)
);
CREATE INDEX IF NOT EXISTS idx_task_instances_user_due
    ON task_instances(user_id, due_date);
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_schema.py::test_task_templates_table_exists tests/test_schema.py::test_task_instances_table_exists -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/schema.py tests/test_schema.py
git commit -m "feat(tasks): add task_templates and task_instances schema"
```

---

### Task 2: Backend DB — priority sort + dates-summary query

**Files:**
- Modify: `backend/domains/tasks/db.py`
- Test: `tests/test_tasks_db.py`

**Interfaces:**
- Consumes: existing `tasks` table with `priority INTEGER NOT NULL DEFAULT 0`
- Produces:
  - All `get_*_tasks` functions return rows sorted `priority DESC, due_at ASC NULLS LAST`
  - `get_dates_summary(conn, user_id, start_iso, end_iso) -> dict[str, int]` — returns `{"YYYY-MM-DD": max_priority}` for dates with pending tasks in range

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tasks_db.py`:

```python
from domains.tasks.db import insert_task, get_pending_tasks, complete_task, get_overdue_tasks, get_tasks_by_date, get_dates_summary


def test_priority_sort(conn, user_id):
    insert_task(conn, user_id, "Normal task", due_at="2026-08-10T00:00:00", priority=0)
    insert_task(conn, user_id, "Urgent task", due_at="2026-08-10T00:00:00", priority=2)
    insert_task(conn, user_id, "High task",   due_at="2026-08-10T00:00:00", priority=1)
    tasks = get_tasks_by_date(conn, user_id, "2026-08-10")
    assert [t["priority"] for t in tasks] == [2, 1, 0]


def test_dates_summary_empty(conn, user_id):
    result = get_dates_summary(conn, user_id, "2026-08-01", "2026-08-31")
    assert result == {}


def test_dates_summary_max_priority(conn, user_id):
    insert_task(conn, user_id, "Normal", due_at="2026-08-10T00:00:00", priority=0)
    insert_task(conn, user_id, "High",   due_at="2026-08-10T00:00:00", priority=1)
    insert_task(conn, user_id, "Other",  due_at="2026-08-15T00:00:00", priority=2)
    result = get_dates_summary(conn, user_id, "2026-08-01", "2026-08-31")
    assert result == {"2026-08-10": 1, "2026-08-15": 2}


def test_dates_summary_excludes_completed(conn, user_id):
    tid = insert_task(conn, user_id, "Done", due_at="2026-08-10T00:00:00", priority=1)
    complete_task(conn, user_id, tid)
    result = get_dates_summary(conn, user_id, "2026-08-01", "2026-08-31")
    assert result == {}
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_tasks_db.py::test_priority_sort tests/test_tasks_db.py::test_dates_summary_empty tests/test_tasks_db.py::test_dates_summary_max_priority tests/test_tasks_db.py::test_dates_summary_excludes_completed -v
```

Expected: FAIL

- [ ] **Step 3: Update `insert_task` signature and add `get_dates_summary`**

Replace `backend/domains/tasks/db.py` with:

```python
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
```

- [ ] **Step 4: Run to verify they pass**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_tasks_db.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/domains/tasks/db.py tests/test_tasks_db.py
git commit -m "feat(tasks): priority sort + dates-summary query"
```

---

### Task 3: Backend DB — recurring template CRUD and instance spawn

**Files:**
- Modify: `backend/domains/tasks/db.py`
- Test: `tests/test_tasks_db.py`

**Interfaces:**
- Consumes: `task_templates` and `task_instances` tables from Task 1
- Produces:
  - `insert_template(conn, user_id, title, recurrence, anchor_date, advance_days) -> int`
  - `get_active_templates(conn, user_id) -> list`
  - `spawn_instances_for_date(conn, user_id, date_iso: str) -> list[dict]` — creates missing instances for templates that fire on `date_iso` and are within their advance window; returns list of instance dicts with shape `{id, template_id, title, due_date, completed_at, priority=0, tags=[], is_recurring=True}`
  - `complete_instance(conn, user_id, instance_id) -> bool`
  - `delete_instance(conn, user_id, instance_id) -> bool`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tasks_db.py`:

```python
from datetime import date, timedelta
from domains.tasks.db import (
    insert_task, get_pending_tasks, complete_task, get_overdue_tasks,
    get_tasks_by_date, get_dates_summary,
    insert_template, get_active_templates, spawn_instances_for_date,
    complete_instance, delete_instance
)


def test_insert_template(conn, user_id):
    tid = insert_template(conn, user_id, "Call mom", "weekly", "2026-08-11", advance_days=1)
    assert isinstance(tid, int) and tid > 0


def test_get_active_templates(conn, user_id):
    insert_template(conn, user_id, "Call mom", "weekly", "2026-08-11", advance_days=1)
    templates = get_active_templates(conn, user_id)
    assert len(templates) == 1
    assert templates[0]["title"] == "Call mom"


def test_spawn_daily_instance(conn, user_id):
    today = date.today().isoformat()
    insert_template(conn, user_id, "Take vitamins", "daily", today, advance_days=1)
    instances = spawn_instances_for_date(conn, user_id, today)
    assert len(instances) == 1
    assert instances[0]["due_date"] == today
    assert instances[0]["is_recurring"] is True


def test_spawn_is_idempotent(conn, user_id):
    today = date.today().isoformat()
    insert_template(conn, user_id, "Take vitamins", "daily", today, advance_days=1)
    spawn_instances_for_date(conn, user_id, today)
    instances = spawn_instances_for_date(conn, user_id, today)
    assert len(instances) == 1


def test_spawn_outside_advance_window(conn, user_id):
    far_future = (date.today() + timedelta(days=10)).isoformat()
    insert_template(conn, user_id, "Take vitamins", "daily", far_future, advance_days=1)
    instances = spawn_instances_for_date(conn, user_id, far_future)
    assert instances == []


def test_spawn_yearly_on_matching_date(conn, user_id):
    insert_template(conn, user_id, "Birthday wish", "yearly", "2026-08-20", advance_days=30)
    instances = spawn_instances_for_date(conn, user_id, "2027-08-20")
    assert len(instances) == 1
    assert instances[0]["due_date"] == "2027-08-20"


def test_spawn_weekly_on_non_matching_day(conn, user_id):
    insert_template(conn, user_id, "Call mom", "weekly", "2026-08-11", advance_days=1)
    instances = spawn_instances_for_date(conn, user_id, "2026-08-12")
    assert instances == []


def test_complete_instance(conn, user_id):
    today = date.today().isoformat()
    insert_template(conn, user_id, "Take vitamins", "daily", today, advance_days=1)
    instances = spawn_instances_for_date(conn, user_id, today)
    iid = instances[0]["id"]
    assert complete_instance(conn, user_id, iid) is True
    instances2 = spawn_instances_for_date(conn, user_id, today)
    assert instances2[0]["completed_at"] is not None


def test_delete_instance(conn, user_id):
    today = date.today().isoformat()
    insert_template(conn, user_id, "Take vitamins", "daily", today, advance_days=1)
    instances = spawn_instances_for_date(conn, user_id, today)
    iid = instances[0]["id"]
    assert delete_instance(conn, user_id, iid) is True
    instances2 = spawn_instances_for_date(conn, user_id, today)
    assert instances2 == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_tasks_db.py -k "template or instance or spawn or yearly or weekly" -v
```

Expected: FAIL — functions not defined yet

- [ ] **Step 3: Implement template and instance functions**

Append to `backend/domains/tasks/db.py` (do not replace existing functions):

```python
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
    target = date_type.fromisoformat(date_iso)
    templates = get_active_templates(conn, user_id)
    result = []
    for t in templates:
        t = dict(t)
        if not _template_fires_on(t["recurrence"], t["anchor_date"], date_iso):
            continue
        advance = t["advance_days"]
        if today < target - timedelta(days=advance):
            continue
        conn.execute(
            "INSERT OR IGNORE INTO task_instances(template_id, user_id, due_date) VALUES (?,?,?)",
            (t["id"], user_id, date_iso)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM task_instances WHERE template_id=? AND user_id=? AND due_date=? "
            "AND deleted_at IS NULL",
            (t["id"], user_id, date_iso)
        ).fetchone()
        if row:
            result.append({
                "id": row["id"],
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
```

- [ ] **Step 4: Run all tasks DB tests**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_tasks_db.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/domains/tasks/db.py tests/test_tasks_db.py
git commit -m "feat(tasks): recurring template CRUD and instance spawn logic"
```

---

### Task 4: Backend Router — expose priority, dates-summary, and template endpoints

**Files:**
- Modify: `backend/domains/tasks/router.py`
- Create: `tests/test_tasks_router.py`

**Interfaces:**
- Consumes: `insert_task(priority=)`, `get_dates_summary`, `insert_template`, `spawn_instances_for_date`, `complete_instance`, `delete_instance` from Task 2+3
- Produces:
  - `POST /tasks/` now accepts `priority: int = 0`
  - `GET /tasks/today` and `GET /tasks/by-date` now also return spawned recurring instances merged with regular tasks
  - `GET /tasks/dates-summary?start=YYYY-MM-DD&end=YYYY-MM-DD` → `{"2026-08-10": 1}`
  - `POST /tasks/templates` → `{id, title, recurrence, anchor_date, advance_days}`
  - `PATCH /tasks/instances/{instance_id}/complete` → `{ok: true}`
  - `DELETE /tasks/instances/{instance_id}` → `{ok: true}`

- [ ] **Step 1: Write failing router tests**

Create `tests/test_tasks_router.py`:

```python
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app
from db.connection import get_connection
from db.schema import initialize_schema
from config import DB_PATH
import domains.tasks.router as tasks_router


@pytest.fixture(autouse=True)
def clean_db():
    conn = get_connection(DB_PATH)
    initialize_schema(conn)
    conn.execute("DELETE FROM task_instances")
    conn.execute("DELETE FROM task_templates")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    conn.close()


@pytest.fixture
def client():
    return TestClient(app, headers={"X-API-Key": "test"})


def test_create_task_with_priority(client):
    r = client.post("/tasks/", json={"title": "Urgent thing", "priority": 2})
    assert r.status_code == 200
    assert r.json()["priority"] == 2


def test_dates_summary_empty(client):
    r = client.get("/tasks/dates-summary?start=2026-08-01&end=2026-08-31")
    assert r.status_code == 200
    assert r.json() == {}


def test_dates_summary_with_task(client):
    client.post("/tasks/", json={"title": "Thing", "due_at": "2026-08-10T00:00:00", "priority": 1})
    r = client.get("/tasks/dates-summary?start=2026-08-01&end=2026-08-31")
    assert r.json() == {"2026-08-10": 1}


def test_create_template(client):
    r = client.post("/tasks/templates", json={
        "title": "Call mom", "recurrence": "weekly",
        "anchor_date": "2026-08-11", "advance_days": 1
    })
    assert r.status_code == 200
    assert r.json()["recurrence"] == "weekly"


def test_complete_instance(client):
    from datetime import date
    today = date.today().isoformat()
    client.post("/tasks/templates", json={
        "title": "Take vitamins", "recurrence": "daily",
        "anchor_date": today, "advance_days": 1
    })
    tasks = client.get(f"/tasks/by-date?date={today}").json()
    recurring = [t for t in tasks if t.get("is_recurring")]
    assert len(recurring) == 1
    iid = recurring[0]["id"]
    r = client.patch(f"/tasks/instances/{iid}/complete")
    assert r.json()["ok"] is True
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_tasks_router.py -v
```

Expected: FAIL

- [ ] **Step 3: Update router**

Replace `backend/domains/tasks/router.py` with:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import verify_api_key
from db.connection import get_connection
from db.schema import initialize_schema
from config import DB_PATH
from domains.tasks.db import (
    insert_task, get_pending_tasks, get_overdue_tasks,
    get_today_tasks, get_tasks_by_date, complete_task, delete_task,
    get_dates_summary, insert_template, get_active_templates,
    spawn_instances_for_date, complete_instance, delete_instance
)

router = APIRouter(prefix="/tasks", tags=["tasks"],
                   dependencies=[Depends(verify_api_key)])


def _conn():
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


class TaskCreate(BaseModel):
    user_id: int = 1
    title: str
    due_at: str | None = None
    priority: int = 0


class TemplateCreate(BaseModel):
    user_id: int = 1
    title: str
    recurrence: str
    anchor_date: str
    advance_days: int | None = None


@router.post("/")
def create(body: TaskCreate):
    conn = _conn()
    task_id = insert_task(conn, body.user_id, body.title, body.due_at, body.priority)
    conn.close()
    return {"id": task_id, "title": body.title, "due_at": body.due_at,
            "completed_at": None, "priority": body.priority, "tags": [],
            "is_recurring": False}


@router.get("/")
def list_all(user_id: int = 1):
    conn = _conn()
    tasks = [dict(t) for t in get_pending_tasks(conn, user_id)]
    conn.close()
    return tasks


@router.get("/overdue")
def overdue(user_id: int = 1):
    conn = _conn()
    tasks = [dict(t) for t in get_overdue_tasks(conn, user_id)]
    conn.close()
    return tasks


@router.get("/today")
def today(user_id: int = 1):
    from datetime import date
    today_iso = date.today().isoformat()
    conn = _conn()
    tasks = [dict(t) for t in get_today_tasks(conn, user_id)]
    instances = spawn_instances_for_date(conn, user_id, today_iso)
    conn.close()
    return tasks + instances


@router.get("/by-date")
def by_date(date: str, user_id: int = 1):
    conn = _conn()
    tasks = [dict(t) for t in get_tasks_by_date(conn, user_id, date)]
    instances = spawn_instances_for_date(conn, user_id, date)
    conn.close()
    return tasks + instances


@router.get("/dates-summary")
def dates_summary(start: str, end: str, user_id: int = 1):
    conn = _conn()
    result = get_dates_summary(conn, user_id, start, end)
    conn.close()
    return result


@router.post("/templates")
def create_template(body: TemplateCreate):
    default_advance = {"daily": 1, "weekly": 1, "monthly": 7, "yearly": 30}
    advance = body.advance_days if body.advance_days is not None else default_advance.get(body.recurrence, 1)
    conn = _conn()
    tid = insert_template(conn, body.user_id, body.title, body.recurrence, body.anchor_date, advance)
    conn.close()
    return {"id": tid, "title": body.title, "recurrence": body.recurrence,
            "anchor_date": body.anchor_date, "advance_days": advance}


@router.patch("/{task_id}/complete")
def complete(task_id: int, user_id: int = 1):
    conn = _conn()
    ok = complete_task(conn, user_id, task_id)
    conn.close()
    if not ok:
        raise HTTPException(404, "Task not found or already complete")
    return {"ok": True}


@router.delete("/{task_id}")
def delete(task_id: int, user_id: int = 1):
    conn = _conn()
    ok = delete_task(conn, user_id, task_id)
    conn.close()
    if not ok:
        raise HTTPException(404, "Task not found")
    return {"ok": True}


@router.patch("/instances/{instance_id}/complete")
def complete_inst(instance_id: int, user_id: int = 1):
    conn = _conn()
    ok = complete_instance(conn, user_id, instance_id)
    conn.close()
    if not ok:
        raise HTTPException(404, "Instance not found or already complete")
    return {"ok": True}


@router.delete("/instances/{instance_id}")
def delete_inst(instance_id: int, user_id: int = 1):
    conn = _conn()
    ok = delete_instance(conn, user_id, instance_id)
    conn.close()
    if not ok:
        raise HTTPException(404, "Instance not found")
    return {"ok": True}
```

- [ ] **Step 4: Run router tests**

```bash
cd ~/deep-workspace/chitiyu-pi && python -m pytest tests/test_tasks_router.py tests/test_tasks_db.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/domains/tasks/router.py tests/test_tasks_router.py
git commit -m "feat(tasks): expose priority, dates-summary, template and instance endpoints"
```

---

### Task 5: Frontend API — update types and add new calls

**Files:**
- Modify: `app/lib/api.ts`

**Interfaces:**
- Produces:
  - `Task.priority: number` (was `string | null`)
  - `Task.is_recurring?: boolean`
  - `addTask(title, due_at?, priority?)` — adds `priority` param
  - `getTasksDatesSummary(start, end): Promise<Record<string, number>>` — calls `GET /tasks/dates-summary`
  - `createTaskTemplate(title, recurrence, anchor_date, advance_days?): Promise<{id, title, recurrence, anchor_date, advance_days}>`
  - `completeInstance(id): Promise<{ok: boolean}>`
  - `deleteInstance(id): Promise<{ok: boolean}>`

- [ ] **Step 1: Update `app/lib/api.ts`**

Find the Tasks section (around line 284) and replace it with:

```typescript
// ─── Tasks ────────────────────────────────────────────────────────────────────

export interface Task {
  id: number;
  title: string;
  due_at: string | null;
  completed_at: string | null;
  priority: number;
  tags: string[];
  is_recurring?: boolean;
}

export interface TaskTemplate {
  id: number;
  title: string;
  recurrence: "daily" | "weekly" | "monthly" | "yearly";
  anchor_date: string;
  advance_days: number;
}

export const getTasksOverdue = () =>
  request<Task[]>("GET", "/tasks/overdue");

export const getTasksToday = () =>
  request<Task[]>("GET", "/tasks/today");

export const addTask = (title: string, due_at?: string, priority: number = 0) =>
  request<Task>("POST", "/tasks/", { title, priority, ...(due_at ? { due_at } : {}) });

export const getTasksByDate = (date: string) =>
  request<Task[]>("GET", `/tasks/by-date?date=${encodeURIComponent(date)}`);

export const completeTask = (id: number) =>
  request<{ ok: boolean }>("PATCH", `/tasks/${id}/complete`, {});

export const deleteTask = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/tasks/${id}`);

export const getTasksDatesSummary = (start: string, end: string) =>
  request<Record<string, number>>("GET", `/tasks/dates-summary?start=${start}&end=${end}`);

export const createTaskTemplate = (
  title: string,
  recurrence: TaskTemplate["recurrence"],
  anchor_date: string,
  advance_days?: number
) =>
  request<TaskTemplate>("POST", "/tasks/templates", {
    title, recurrence, anchor_date, ...(advance_days !== undefined ? { advance_days } : {})
  });

export const completeInstance = (id: number) =>
  request<{ ok: boolean }>("PATCH", `/tasks/instances/${id}/complete`, {});

export const deleteInstance = (id: number) =>
  request<{ ok: boolean }>("DELETE", `/tasks/instances/${id}`);
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd ~/deep-workspace/chitiyu-pi/app && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors in `lib/api.ts`

- [ ] **Step 3: Commit**

```bash
git add app/lib/api.ts
git commit -m "feat(tasks): update API types — priority int, is_recurring, template and instance calls"
```

---

### Task 6: Frontend — TaskRow priority dot

**Files:**
- Modify: `app/components/TaskRow.tsx`

**Interfaces:**
- Consumes: `Task.priority: number` from Task 5
- Produces: colored dot before task title — no dot for priority=0, yellow `●` for priority=1, red `●` for priority=2

- [ ] **Step 1: Update TaskRow**

Replace `app/components/TaskRow.tsx` with:

```typescript
import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import type { Task } from "../lib/api";
import { useTheme } from "../lib/theme";
import { SwipeableRow } from "./SwipeableRow";

interface Props {
  task: Task;
  onComplete: (id: number) => void;
  onDelete: (id: number) => void;
}

const PRIORITY_COLORS: Record<number, string | null> = {
  0: null,
  1: "#FF9F0A",
  2: "#FF453A",
};

export function TaskRow({ task, onComplete, onDelete }: Props) {
  const { colors } = useTheme();
  const dotColor = PRIORITY_COLORS[task.priority] ?? null;

  return (
    <SwipeableRow
      confirmTitle="Delete task?"
      confirmMessage={task.title}
      onDelete={() => onDelete(task.id)}
      backgroundColor={colors.card}
    >
      <View style={[styles.row, { borderBottomColor: colors.border }]}>
        <TouchableOpacity
          style={styles.checkbox}
          onPress={() => onComplete(task.id)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <View style={[styles.checkCircle, { borderColor: colors.checkCircle }]} />
        </TouchableOpacity>
        <View style={styles.info}>
          <View style={styles.titleRow}>
            {dotColor && (
              <View style={[styles.priorityDot, { backgroundColor: dotColor }]} />
            )}
            <Text style={[styles.title, { color: colors.text }]}>{task.title}</Text>
          </View>
          {task.due_at && (
            <Text style={[styles.due, { color: colors.textSecondary }]}>
              Due {new Date(task.due_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </Text>
          )}
        </View>
      </View>
    </SwipeableRow>
  );
}

const styles = StyleSheet.create({
  row: {
    flex: 1, flexDirection: "row", alignItems: "center",
    paddingVertical: 12, paddingHorizontal: 4, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  checkbox: { marginRight: 12 },
  checkCircle: { width: 22, height: 22, borderRadius: 11, borderWidth: 2 },
  info: { flex: 1 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  priorityDot: { width: 8, height: 8, borderRadius: 4 },
  title: { fontSize: 15, flex: 1 },
  due: { fontSize: 12, marginTop: 2 },
});
```

- [ ] **Step 2: TypeScript check**

```bash
cd ~/deep-workspace/chitiyu-pi/app && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add app/components/TaskRow.tsx
git commit -m "feat(tasks): priority dot in TaskRow"
```

---

### Task 7: Frontend — tasks.tsx full update (calendar styling, date dots, priority picker, recurrence UI)

This is the largest task. It touches the main screen file in four areas: CalendarPicker styling, DayStrip dots, Add Task sheet (priority + recurrence), and complete/delete routing for recurring instances.

**Files:**
- Modify: `app/app/(tabs)/tasks.tsx`

**Interfaces:**
- Consumes:
  - `getTasksDatesSummary(start, end): Promise<Record<string, number>>` from Task 5
  - `createTaskTemplate(title, recurrence, anchor_date, advance_days?)` from Task 5
  - `completeInstance(id)`, `deleteInstance(id)` from Task 5
  - `addTask(title, due_at?, priority?)` from Task 5
  - `Task.is_recurring?: boolean` from Task 5
- Produces: fully updated tasks screen

- [ ] **Step 1: Replace `tasks.tsx` with the full updated version**

Replace the entire contents of `app/app/(tabs)/tasks.tsx` with:

```typescript
import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Modal,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
  FlatList,
} from "react-native";
import { TaskRow } from "../../components/TaskRow";
import {
  getTasksOverdue,
  getTasksToday,
  getTasksByDate,
  addTask,
  completeTask,
  deleteTask,
  completeInstance,
  deleteInstance,
  createTaskTemplate,
  getTasksDatesSummary,
  type Task,
} from "../../lib/api";
import { useTheme } from "../../lib/theme";

// ─── helpers ─────────────────────────────────────────────────────────────────

function toISO(d: Date) {
  return d.toISOString().slice(0, 10);
}

function addDays(d: Date, n: number) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function formatMonthYear(d: Date) {
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function formatDayLabel(d: Date) {
  return d.toLocaleDateString("en-US", { weekday: "short" });
}

function daysInMonth(d: Date): Date[] {
  const year = d.getFullYear();
  const month = d.getMonth();
  const count = new Date(year, month + 1, 0).getDate();
  return Array.from({ length: count }, (_, i) => new Date(year, month, i + 1));
}

// Priority dot color: 0=none, 1=yellow, 2=red
const INDICATOR_COLORS: Record<number, string> = {
  1: "#FF9F0A",
  2: "#FF453A",
};

// ─── CalendarPicker ──────────────────────────────────────────────────────────

interface CalendarPickerProps {
  selected: string;
  onSelect: (iso: string) => void;
  datesSummary?: Record<string, number>;
}

function CalendarPicker({ selected, onSelect, datesSummary = {} }: CalendarPickerProps) {
  const { colors } = useTheme();
  const today = toISO(new Date());
  const [viewDate, setViewDate] = useState(() => new Date(selected || today));
  const days = daysInMonth(viewDate);
  const firstDow = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1).getDay();
  const blanks = Array.from({ length: firstDow });

  return (
    <View style={calStyles.root}>
      <View style={calStyles.header}>
        <TouchableOpacity onPress={() => setViewDate((d) => addDays(new Date(d.getFullYear(), d.getMonth(), 1), -1))}>
          <Text style={[calStyles.navBtn, { color: colors.accent }]}>‹</Text>
        </TouchableOpacity>
        <Text style={[calStyles.monthLabel, { color: colors.text }]}>{formatMonthYear(viewDate)}</Text>
        <TouchableOpacity onPress={() => setViewDate((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1))}>
          <Text style={[calStyles.navBtn, { color: colors.accent }]}>›</Text>
        </TouchableOpacity>
      </View>
      <View style={calStyles.dowRow}>
        {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((d) => (
          <Text key={d} style={[calStyles.dowLabel, { color: colors.textTertiary }]}>{d}</Text>
        ))}
      </View>
      <View style={calStyles.grid}>
        {blanks.map((_, i) => <View key={`b${i}`} style={calStyles.cell} />)}
        {days.map((d) => {
          const iso = toISO(d);
          const isSelected = iso === selected;
          const isToday = iso === today;
          const maxPriority = datesSummary[iso];
          const indicatorColor = maxPriority !== undefined ? (INDICATOR_COLORS[maxPriority] ?? colors.textTertiary) : null;
          return (
            <TouchableOpacity
              key={iso}
              style={[
                calStyles.cell,
                isSelected && { backgroundColor: colors.accent, borderRadius: 16 },
              ]}
              onPress={() => onSelect(iso)}
            >
              <Text style={[
                calStyles.dayNum,
                { color: isSelected ? "#fff" : isToday ? colors.accent : colors.text },
                isToday && !isSelected && { fontWeight: "700" },
              ]}>{d.getDate()}</Text>
              {indicatorColor ? (
                <View style={[calStyles.dot, { backgroundColor: indicatorColor }]} />
              ) : (
                <View style={calStyles.dotPlaceholder} />
              )}
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const calStyles = StyleSheet.create({
  root: { marginBottom: 4 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  navBtn: { fontSize: 24, paddingHorizontal: 8 },
  monthLabel: { fontSize: 15, fontWeight: "600" },
  dowRow: { flexDirection: "row" },
  dowLabel: { flex: 1, textAlign: "center", fontSize: 11, marginBottom: 4 },
  grid: { flexDirection: "row", flexWrap: "wrap" },
  cell: { width: "14.28%", aspectRatio: 1, alignItems: "center", justifyContent: "center" },
  dayNum: { fontSize: 14 },
  dot: { width: 5, height: 5, borderRadius: 3, marginTop: 2 },
  dotPlaceholder: { width: 5, height: 5, marginTop: 2 },
});

// ─── DayStrip ────────────────────────────────────────────────────────────────

interface DayStripProps {
  selected: string;
  onSelect: (iso: string) => void;
  onOpenCalendar: () => void;
  datesSummary: Record<string, number>;
}

function DayStrip({ selected, onSelect, onOpenCalendar, datesSummary }: DayStripProps) {
  const { colors } = useTheme();
  const today = new Date();
  const days = Array.from({ length: 14 }, (_, i) => addDays(today, i));
  const flatRef = useRef<FlatList>(null);
  const todayISO = toISO(new Date());

  useEffect(() => {
    const idx = days.findIndex((d) => toISO(d) === selected);
    if (idx >= 0) flatRef.current?.scrollToIndex({ index: idx, animated: true, viewPosition: 0.5 });
  }, [selected]);

  return (
    <View style={stripStyles.row}>
      <FlatList
        ref={flatRef}
        horizontal
        showsHorizontalScrollIndicator={false}
        data={days}
        keyExtractor={(d) => toISO(d)}
        contentContainerStyle={{ paddingHorizontal: 4 }}
        renderItem={({ item: d }) => {
          const iso = toISO(d);
          const isSelected = iso === selected;
          const isToday = iso === todayISO;
          const maxPriority = datesSummary[iso];
          const dotColor = maxPriority !== undefined ? (INDICATOR_COLORS[maxPriority] ?? "#8E8E93") : null;
          return (
            <TouchableOpacity
              style={[
                stripStyles.dayBtn,
                { backgroundColor: isSelected ? colors.accent : colors.card },
              ]}
              onPress={() => onSelect(iso)}
            >
              <Text style={[stripStyles.dowText, { color: isSelected ? "#fff" : isToday ? colors.accent : colors.textSecondary, fontWeight: isToday && !isSelected ? "700" : "400" }]}>
                {formatDayLabel(d)}
              </Text>
              <Text style={[stripStyles.numText, { color: isSelected ? "#fff" : isToday ? colors.accent : colors.text }]}>
                {d.getDate()}
              </Text>
              {dotColor ? (
                <View style={[stripStyles.dot, { backgroundColor: isSelected ? "rgba(255,255,255,0.7)" : dotColor }]} />
              ) : (
                <View style={stripStyles.dotPlaceholder} />
              )}
            </TouchableOpacity>
          );
        }}
      />
      <TouchableOpacity style={[stripStyles.calBtn, { backgroundColor: colors.card }]} onPress={onOpenCalendar}>
        <Text style={{ color: colors.accent, fontSize: 18 }}>📅</Text>
      </TouchableOpacity>
    </View>
  );
}

const stripStyles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", marginBottom: 16, gap: 6 },
  dayBtn: { borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8, alignItems: "center", marginRight: 6, minWidth: 46 },
  dowText: { fontSize: 11 },
  numText: { fontSize: 16, fontWeight: "600", marginTop: 2 },
  dot: { width: 5, height: 5, borderRadius: 3, marginTop: 3 },
  dotPlaceholder: { width: 5, height: 5, marginTop: 3 },
  calBtn: { borderRadius: 10, padding: 8 },
});

// ─── Priority picker ─────────────────────────────────────────────────────────

interface PriorityPickerProps {
  value: number;
  onChange: (v: number) => void;
}

const PRIORITY_OPTIONS = [
  { value: 0, label: "Normal", color: null },
  { value: 1, label: "High", color: "#FF9F0A" },
  { value: 2, label: "Urgent", color: "#FF453A" },
];

function PriorityPicker({ value, onChange }: PriorityPickerProps) {
  const { colors } = useTheme();
  return (
    <View style={priorityStyles.row}>
      {PRIORITY_OPTIONS.map((opt) => {
        const isSelected = opt.value === value;
        return (
          <TouchableOpacity
            key={opt.value}
            style={[
              priorityStyles.option,
              { backgroundColor: isSelected ? (opt.color ?? colors.accent) : colors.cardElevated },
            ]}
            onPress={() => onChange(opt.value)}
          >
            {opt.color && <View style={[priorityStyles.dot, { backgroundColor: isSelected ? "#fff" : opt.color }]} />}
            <Text style={{ color: isSelected ? "#fff" : colors.textSecondary, fontSize: 13, fontWeight: "500" }}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const priorityStyles = StyleSheet.create({
  row: { flexDirection: "row", gap: 8, marginBottom: 12 },
  option: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 5, borderRadius: 10, paddingVertical: 10 },
  dot: { width: 7, height: 7, borderRadius: 4 },
});

// ─── Recurrence picker ───────────────────────────────────────────────────────

type Recurrence = "none" | "daily" | "weekly" | "monthly" | "yearly";
const RECURRENCE_OPTIONS: { value: Recurrence; label: string }[] = [
  { value: "none", label: "None" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "yearly", label: "Yearly" },
];

interface RecurrencePickerProps {
  value: Recurrence;
  onChange: (v: Recurrence) => void;
}

function RecurrencePicker({ value, onChange }: RecurrencePickerProps) {
  const { colors } = useTheme();
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
      <View style={{ flexDirection: "row", gap: 8 }}>
        {RECURRENCE_OPTIONS.map((opt) => {
          const isSelected = opt.value === value;
          return (
            <TouchableOpacity
              key={opt.value}
              style={[
                recStyles.chip,
                { backgroundColor: isSelected ? colors.accent : colors.cardElevated },
              ]}
              onPress={() => onChange(opt.value)}
            >
              <Text style={{ color: isSelected ? "#fff" : colors.textSecondary, fontSize: 13, fontWeight: "500" }}>
                {opt.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </ScrollView>
  );
}

const recStyles = StyleSheet.create({
  chip: { borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8 },
});

// ─── Main screen ─────────────────────────────────────────────────────────────

export default function TasksScreen() {
  const { colors } = useTheme();
  const todayISO = toISO(new Date());
  const [selectedDate, setSelectedDate] = useState<string>(todayISO);
  const [calendarVisible, setCalendarVisible] = useState(false);
  const [overdue, setOverdue] = useState<Task[]>([]);
  const [dateTasks, setDateTasks] = useState<Task[]>([]);
  const [datesSummary, setDatesSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [taskInput, setTaskInput] = useState("");
  const [dueDate, setDueDate] = useState<string>("");
  const [showDueDatePicker, setShowDueDatePicker] = useState(false);
  const [priority, setPriority] = useState<number>(0);
  const [recurrence, setRecurrence] = useState<Recurrence>("none");
  const [showInAdvance, setShowInAdvance] = useState(false);
  const [adding, setAdding] = useState(false);

  const isToday = selectedDate === todayISO;

  const loadSummary = useCallback(async () => {
    const start = todayISO;
    const end = toISO(addDays(new Date(), 30));
    try {
      const summary = await getTasksDatesSummary(start, end);
      setDatesSummary(summary);
    } catch {
      // non-fatal
    }
  }, [todayISO]);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      if (isToday) {
        const [overdueData, todayData] = await Promise.all([
          getTasksOverdue(),
          getTasksToday(),
        ]);
        setOverdue(overdueData);
        setDateTasks(todayData);
      } else {
        const [overdueData, dateData] = await Promise.all([
          getTasksOverdue(),
          getTasksByDate(selectedDate),
        ]);
        setOverdue(overdueData);
        setDateTasks(dateData);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to load tasks");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedDate, isToday]);

  useEffect(() => { loadData(); loadSummary(); }, [loadData]);

  const handleRefresh = () => { setRefreshing(true); loadData(); loadSummary(); };

  const openSheet = () => {
    setDueDate(selectedDate);
    setPriority(0);
    setRecurrence("none");
    setShowInAdvance(false);
    setShowDueDatePicker(false);
    setSheetVisible(true);
  };

  const handleAddTask = async () => {
    if (!taskInput.trim()) return;
    setAdding(true);
    try {
      if (recurrence !== "none") {
        const advance = showInAdvance ? 365 : undefined;
        await createTaskTemplate(taskInput.trim(), recurrence, dueDate || todayISO, advance);
        await loadData();
      } else {
        const task = await addTask(taskInput.trim(), dueDate || undefined, priority);
        if (!dueDate || dueDate === selectedDate) {
          setDateTasks((prev) => {
            const updated = [...prev, task];
            return updated.sort((a, b) => b.priority - a.priority);
          });
        }
      }
      setTaskInput("");
      setDueDate(selectedDate);
      setSheetVisible(false);
      loadSummary();
    } finally {
      setAdding(false);
    }
  };

  const handleComplete = async (id: number) => {
    const task = [...overdue, ...dateTasks].find((t) => t.id === id);
    if (task?.is_recurring) {
      await completeInstance(id);
    } else {
      await completeTask(id);
    }
    setOverdue((prev) => prev.filter((t) => t.id !== id));
    setDateTasks((prev) => prev.filter((t) => t.id !== id));
    loadSummary();
  };

  const handleDelete = async (id: number) => {
    const task = [...overdue, ...dateTasks].find((t) => t.id === id);
    if (task?.is_recurring) {
      await deleteInstance(id);
    } else {
      await deleteTask(id);
    }
    setOverdue((prev) => prev.filter((t) => t.id !== id));
    setDateTasks((prev) => prev.filter((t) => t.id !== id));
    loadSummary();
  };

  const handleSelectDate = (iso: string) => {
    setSelectedDate(iso);
    setCalendarVisible(false);
  };

  const selectedLabel = selectedDate === todayISO
    ? "Today"
    : new Date(selectedDate + "T00:00:00").toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.center}>
          <Text style={{ color: colors.accentRed, fontSize: 15, textAlign: "center", padding: 20 }}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        <DayStrip
          selected={selectedDate}
          onSelect={setSelectedDate}
          onOpenCalendar={() => setCalendarVisible(true)}
          datesSummary={datesSummary}
        />

        <TouchableOpacity
          style={[styles.primaryButton, { backgroundColor: colors.accent }]}
          onPress={openSheet}
        >
          <Text style={styles.primaryButtonText}>+ Add Task</Text>
        </TouchableOpacity>

        {isToday && overdue.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeaderRow}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Overdue</Text>
              <View style={[styles.badge, { backgroundColor: colors.accentRed }]}>
                <Text style={styles.badgeText}>{overdue.length}</Text>
              </View>
            </View>
            <View style={[styles.overdueContainer, { backgroundColor: colors.overdueStripe, borderLeftColor: colors.accentRed }]}>
              {overdue.map((task) => (
                <TaskRow key={task.id} task={task} onComplete={handleComplete} onDelete={handleDelete} />
              ))}
            </View>
          </View>
        )}

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>{selectedLabel}</Text>
          {dateTasks.length === 0 && (
            <Text style={{ color: colors.textSecondary, fontSize: 14 }}>No tasks for this day.</Text>
          )}
          {dateTasks.map((task) => (
            <TaskRow key={task.id} task={task} onComplete={handleComplete} onDelete={handleDelete} />
          ))}
        </View>
      </ScrollView>

      {/* Add Task Sheet */}
      <Modal
        visible={sheetVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setSheetVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={styles.modalOverlay}
        >
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Add Task</Text>
            <TextInput
              style={[styles.textInput, { backgroundColor: colors.cardElevated, color: colors.text }]}
              value={taskInput}
              onChangeText={setTaskInput}
              placeholder="e.g. Call doctor about blood work"
              placeholderTextColor={colors.textTertiary}
              autoFocus
              onSubmitEditing={handleAddTask}
              returnKeyType="done"
            />

            {/* Priority */}
            <Text style={[styles.fieldLabel, { color: colors.textSecondary }]}>Priority</Text>
            <PriorityPicker value={priority} onChange={setPriority} />

            {/* Due date */}
            <TouchableOpacity
              style={[styles.dueDateRow, { backgroundColor: colors.cardElevated }]}
              onPress={() => setShowDueDatePicker((v) => !v)}
            >
              <Text style={{ color: colors.textSecondary, fontSize: 14 }}>Due date</Text>
              <Text style={{ color: dueDate ? colors.accent : colors.textTertiary, fontSize: 14, fontWeight: "500" }}>
                {dueDate
                  ? new Date(dueDate + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
                  : "Optional"}
              </Text>
            </TouchableOpacity>

            {showDueDatePicker && (
              <View style={[styles.calendarBox, { backgroundColor: colors.cardElevated }]}>
                <CalendarPicker
                  selected={dueDate || toISO(new Date())}
                  onSelect={(iso) => { setDueDate(iso); setShowDueDatePicker(false); }}
                />
                {dueDate ? (
                  <TouchableOpacity onPress={() => setDueDate("")} style={styles.clearDueBtn}>
                    <Text style={{ color: colors.accentRed, fontSize: 13 }}>Clear date</Text>
                  </TouchableOpacity>
                ) : null}
              </View>
            )}

            {/* Repeat */}
            <Text style={[styles.fieldLabel, { color: colors.textSecondary }]}>Repeat</Text>
            <RecurrencePicker value={recurrence} onChange={setRecurrence} />

            {recurrence !== "none" && (
              <TouchableOpacity
                style={[styles.advanceRow, { backgroundColor: colors.cardElevated }]}
                onPress={() => setShowInAdvance((v) => !v)}
              >
                <Text style={{ color: colors.textSecondary, fontSize: 14 }}>Show in advance</Text>
                <View style={[styles.toggle, { backgroundColor: showInAdvance ? colors.accent : colors.borderSubtle }]}>
                  <View style={[styles.toggleThumb, { transform: [{ translateX: showInAdvance ? 18 : 2 }] }]} />
                </View>
              </TouchableOpacity>
            )}

            <TouchableOpacity
              style={[styles.submitButton, { backgroundColor: colors.accent }, adding && styles.buttonDisabled]}
              onPress={handleAddTask}
              disabled={adding}
            >
              {adding ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>Add Task</Text>}
            </TouchableOpacity>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setSheetVisible(false)}>
              <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Full calendar modal */}
      <Modal
        visible={calendarVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setCalendarVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalSheet, { backgroundColor: colors.card }]}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Pick a Day</Text>
            <CalendarPicker selected={selectedDate} onSelect={handleSelectDate} datesSummary={datesSummary} />
            <TouchableOpacity style={styles.cancelButton} onPress={() => setCalendarVisible(false)}>
              <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  primaryButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 24 },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  section: { marginBottom: 28 },
  sectionHeaderRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10 },
  sectionTitle: { fontSize: 15, fontWeight: "600" },
  badge: { borderRadius: 10, paddingHorizontal: 7, paddingVertical: 1 },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "700" },
  overdueContainer: { borderRadius: 12, overflow: "hidden", borderLeftWidth: 3 },
  modalOverlay: { flex: 1, backgroundColor: "#00000088", justifyContent: "flex-end" },
  modalSheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 24, paddingBottom: 40 },
  modalTitle: { fontSize: 17, fontWeight: "600", marginBottom: 16 },
  textInput: { borderRadius: 10, padding: 14, fontSize: 15, marginBottom: 12 },
  fieldLabel: { fontSize: 12, fontWeight: "600", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 },
  dueDateRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 12,
  },
  calendarBox: { borderRadius: 12, padding: 12, marginBottom: 12 },
  clearDueBtn: { alignItems: "center", paddingTop: 4 },
  advanceRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 12,
  },
  toggle: { width: 42, height: 24, borderRadius: 12, justifyContent: "center" },
  toggleThumb: { width: 20, height: 20, borderRadius: 10, backgroundColor: "#fff" },
  submitButton: { borderRadius: 12, paddingVertical: 14, alignItems: "center", marginBottom: 10 },
  buttonDisabled: { opacity: 0.6 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  cancelButton: { alignItems: "center", paddingVertical: 10 },
  cancelText: { fontSize: 15 },
});
```

- [ ] **Step 2: TypeScript check**

```bash
cd ~/deep-workspace/chitiyu-pi/app && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add app/app/(tabs)/tasks.tsx
git commit -m "feat(tasks): calendar dots, priority picker, recurrence UI, today styling fix"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Item 1 (calendar styling): today ring replaced with bold text + dot-based indicators; no conflicting ring
- ✅ Item 2 (date indicators): `get_dates_summary` + `getTasksDatesSummary` + dots in DayStrip and CalendarPicker; color reflects max priority
- ✅ Item 3 (priority): `insert_task` accepts priority, sort is priority DESC, TaskRow shows dot, Add Task sheet has PriorityPicker
- ✅ Item 4 (recurring): schema, template CRUD, spawn-on-demand, complete/delete instance routing, Add Task sheet recurrence + advance toggle
- ✅ Advance visibility: default per recurrence type in router; "show in advance" toggle sets 365

**Placeholder scan:** No TBDs, all code blocks present, all function names consistent across tasks.

**Type consistency:**
- `Task.priority: number` used in Task 5 (api.ts), Task 6 (TaskRow), Task 7 (tasks.tsx) ✅
- `spawn_instances_for_date` returns dicts with `is_recurring: True` ✅ matched by `Task.is_recurring?: boolean` in api.ts ✅
- `completeInstance`/`deleteInstance` called in Task 7 handleComplete/handleDelete with `task.is_recurring` guard ✅
- `insert_task` signature `(conn, user_id, title, due_at, priority)` consistent across Task 2 db.py and Task 4 router.py ✅
