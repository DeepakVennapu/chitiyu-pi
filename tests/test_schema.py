import pytest


def test_all_tables_exist(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    expected = {
        "entities","facts","fields","relationships","events",
        "tasks","recipes","meals","meal_recipes","health_metrics",
        "journal_entries","pending_state","notification_events"
    }
    assert expected.issubset(tables)


def test_user_id_defaults_to_1(conn):
    conn.execute("INSERT INTO tasks(title) VALUES ('test')")
    conn.commit()
    row = conn.execute("SELECT user_id FROM tasks WHERE title='test'").fetchone()
    assert row["user_id"] == 1


def test_health_metrics_unique_per_user_date(conn):
    conn.execute("INSERT INTO health_metrics(date, steps) VALUES ('2026-08-01', 5000)")
    conn.commit()
    with pytest.raises(Exception):
        conn.execute("INSERT INTO health_metrics(date, steps) VALUES ('2026-08-01', 6000)")
        conn.commit()
