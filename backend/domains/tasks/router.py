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


def _with_uid(task: dict) -> dict:
    return {**task, "uid": f"t:{task['id']}"}


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
    from domains.tasks.tools import create_tasks_from_input
    conn = _conn()
    created = create_tasks_from_input(conn, body.user_id, body.title)
    conn.close()
    # Return first created task shape for backwards compat with app's addTask() call
    if not created:
        raise HTTPException(422, "Could not parse task input")
    first = created[0]
    return {**first, "uid": f"t:{first['id']}", "tags": [], "completed_at": None}


@router.get("/")
def list_all(user_id: int = 1):
    conn = _conn()
    tasks = [_with_uid(dict(t)) for t in get_pending_tasks(conn, user_id)]
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
    tasks = [_with_uid(dict(t)) for t in get_today_tasks(conn, user_id)]
    instances = spawn_instances_for_date(conn, user_id, today_iso)
    conn.close()
    return tasks + instances


@router.get("/by-date")
def by_date(date: str, user_id: int = 1):
    conn = _conn()
    tasks = [_with_uid(dict(t)) for t in get_tasks_by_date(conn, user_id, date)]
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


# Instance routes MUST come before /{task_id} routes to avoid path param collision
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
