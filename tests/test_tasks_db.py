from domains.tasks.db import insert_task, get_pending_tasks, complete_task, get_overdue_tasks


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
