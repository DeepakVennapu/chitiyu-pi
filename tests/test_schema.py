import pytest


def test_all_tables_exist(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    expected = {
        "entities","facts","fields","relationships","events",
        "tasks","recipes","meals","meal_recipes","health_metrics",
        "journal_entries","pending_state","notification_events",
        "accounts","transactions","budgets","net_worth","savings_goals","insights"
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


def test_finance_tables_exist(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    finance_tables = {"accounts", "transactions", "budgets", "net_worth", "savings_goals"}
    assert finance_tables.issubset(tables)


def test_transactions_index_exists(conn):
    indexes = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )}
    assert "idx_transactions_user_date" in indexes
    assert "idx_transactions_user_category" in indexes


def test_budget_unique_per_user_category_period(conn):
    conn.execute("INSERT INTO budgets(user_id, category, amount, period) VALUES (1,'groceries',500,'monthly')")
    conn.commit()
    with pytest.raises(Exception):
        conn.execute("INSERT INTO budgets(user_id, category, amount, period) VALUES (1,'groceries',600,'monthly')")
        conn.commit()


def test_net_worth_unique_per_user_date(conn):
    conn.execute("INSERT INTO net_worth(user_id, snapshot_date, total) VALUES (1,'2026-08-01',50000)")
    conn.commit()
    with pytest.raises(Exception):
        conn.execute("INSERT INTO net_worth(user_id, snapshot_date, total) VALUES (1,'2026-08-01',55000)")
        conn.commit()


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


def test_weight_logs_table_exists(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(weight_logs)").fetchall()}
    assert {"id", "user_id", "date", "recorded_at", "weight_kg", "bodyfat_pct", "muscle_kg", "bmi", "source"} <= cols


def test_weight_logs_unique_user_date(conn):
    conn.execute(
        "INSERT INTO weight_logs(user_id, date, recorded_at, weight_kg, source) VALUES (?,?,?,?,?)",
        (1, "2026-08-15", "2026-08-15 07:00:00", 84.6, "renpho")
    )
    conn.commit()
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO weight_logs(user_id, date, recorded_at, weight_kg, source) VALUES (?,?,?,?,?)",
            (1, "2026-08-15", "2026-08-15 08:00:00", 84.7, "renpho")
        )
        conn.commit()
