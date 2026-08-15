from domains.health.db import insert_meal, get_today_meals, upsert_health_metrics, get_metrics_for_date, upsert_weight_log, get_weight_logs, get_latest_weight


def test_insert_and_retrieve_meal(conn, user_id):
    insert_meal(conn, user_id, "2 eggs", 140, 12.0, 10.0, 0.0)
    meals = get_today_meals(conn, user_id)
    assert len(meals) == 1
    assert meals[0]["description"] == "2 eggs"
    assert meals[0]["calories"] == 140


def test_user_isolation_meals(conn):
    insert_meal(conn, 1, "eggs", 140, 12.0, 10.0, 0.0)
    assert get_today_meals(conn, 2) == []


def test_upsert_health_metrics(conn, user_id):
    upsert_health_metrics(conn, user_id, "2026-08-02", 8000, 45, 420, 62)
    m = get_metrics_for_date(conn, user_id, "2026-08-02")
    assert m["steps"] == 8000
    assert m["sleep_deep_mins"] == 45


def test_upsert_overwrites(conn, user_id):
    upsert_health_metrics(conn, user_id, "2026-08-02", 8000, 45, 420, 62)
    upsert_health_metrics(conn, user_id, "2026-08-02", 11000, 55, 450, 60)
    m = get_metrics_for_date(conn, user_id, "2026-08-02")
    assert m["steps"] == 11000


def test_upsert_weight_log_insert(conn, user_id):
    from datetime import date
    today = date.today().isoformat()
    upsert_weight_log(conn, user_id, today, f"{today} 07:00:00", 84.6, 16.1, 54.2, 28.3, "renpho")
    logs = get_weight_logs(conn, user_id, days=7)
    assert len(logs) == 1
    assert logs[0]["weight_kg"] == 84.6
    assert logs[0]["bodyfat_pct"] == 16.1
    assert logs[0]["source"] == "renpho"


def test_upsert_weight_log_update(conn, user_id):
    from datetime import date
    today = date.today().isoformat()
    upsert_weight_log(conn, user_id, today, f"{today} 07:00:00", 84.6, 16.1, 54.2, 28.3, "renpho")
    upsert_weight_log(conn, user_id, today, f"{today} 08:00:00", 84.3, 15.9, 54.4, 28.2, "renpho")
    logs = get_weight_logs(conn, user_id, days=7)
    assert len(logs) == 1
    assert logs[0]["weight_kg"] == 84.3  # updated


def test_get_weight_logs_window(conn, user_id):
    from datetime import date, timedelta
    today = date.today()
    d_old = (today - timedelta(days=10)).isoformat()  # outside 7-day window
    d_mid = (today - timedelta(days=3)).isoformat()
    d_today = today.isoformat()
    upsert_weight_log(conn, user_id, d_old, f"{d_old} 07:00:00", 86.0, 16.8, 53.8, 28.8, "renpho")
    upsert_weight_log(conn, user_id, d_mid, f"{d_mid} 07:00:00", 84.8, 16.3, 54.1, 28.4, "renpho")
    upsert_weight_log(conn, user_id, d_today, f"{d_today} 07:00:00", 84.6, 16.1, 54.2, 28.3, "renpho")
    logs = get_weight_logs(conn, user_id, days=7)
    assert len(logs) == 2  # d_old excluded; d_mid and d_today included
    dates = [r["date"] for r in logs]
    assert dates == sorted(dates)  # ascending
    assert d_old not in dates


def test_get_latest_weight(conn, user_id):
    from datetime import date, timedelta
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    today_str = today.isoformat()
    upsert_weight_log(conn, user_id, yesterday, f"{yesterday} 07:00:00", 84.8, 16.3, 54.1, 28.4, "renpho")
    upsert_weight_log(conn, user_id, today_str, f"{today_str} 07:00:00", 84.6, 16.1, 54.2, 28.3, "renpho")
    latest = get_latest_weight(conn, user_id)
    assert latest["date"] == today_str
    assert latest["weight_kg"] == 84.6


def test_get_latest_weight_none(conn, user_id):
    assert get_latest_weight(conn, user_id) is None
