from domains.health.db import insert_meal, get_today_meals, upsert_health_metrics, get_metrics_for_date


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
