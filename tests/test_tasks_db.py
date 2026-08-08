from domains.tasks.db import insert_task, get_pending_tasks, complete_task, get_overdue_tasks, get_tasks_by_date, get_dates_summary


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
