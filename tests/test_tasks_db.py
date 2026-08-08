from datetime import date, timedelta
from domains.tasks.db import (
    insert_task, get_pending_tasks, complete_task, get_overdue_tasks,
    get_tasks_by_date, get_dates_summary,
    insert_template, get_active_templates, spawn_instances_for_date,
    complete_instance, delete_instance
)


def test_insert_and_list(conn, user_id):
    insert_task(conn, user_id, "Buy milk")
    tasks = get_pending_tasks(conn, user_id)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Buy milk"


def test_complete_task(conn, user_id):
    tid = insert_task(conn, user_id, "Test task")
    assert complete_task(conn, user_id, tid) is True
    assert get_pending_tasks(conn, user_id) == []


def test_complete_wrong_user(conn):
    tid = insert_task(conn, 1, "Task")
    assert complete_task(conn, 2, tid) is False


def test_overdue(conn, user_id):
    insert_task(conn, user_id, "Old task", due_at="2020-01-01T00:00:00")
    overdue = get_overdue_tasks(conn, user_id)
    assert len(overdue) == 1


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
