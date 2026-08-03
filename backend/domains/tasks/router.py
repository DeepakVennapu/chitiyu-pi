from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import verify_api_key
from db.connection import get_connection
from db.schema import initialize_schema
from config import DB_PATH
from domains.tasks.db import (
    insert_task, get_pending_tasks, get_overdue_tasks,
    get_today_tasks, complete_task, delete_task
)
from domains.tasks.formatter import format_task_list

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


@router.post("/")
def create(body: TaskCreate):
    conn = _conn()
    from domains.tasks.db import insert_task
    task_id = insert_task(conn, body.user_id, body.title, body.due_at)
    conn.close()
    return {"id": task_id, "title": body.title, "due_at": body.due_at}


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
    conn = _conn()
    tasks = [dict(t) for t in get_today_tasks(conn, user_id)]
    conn.close()
    return tasks


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
