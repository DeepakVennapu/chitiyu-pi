import sqlite3
from utils.local_time import local_now as _local_now, today_local as _today_local, to_local_ts as _to_local_ts


def insert_meal(conn: sqlite3.Connection, user_id: int, description: str,
                calories: int, protein: float, fat: float | None, carbs: float | None,
                source: str = "text", recipe_id: int | None = None,
                logged_at: str | None = None) -> int:
    ts = _to_local_ts(logged_at) if logged_at else _local_now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO meals(user_id, description, calories, protein, fat, carbs, source, recipe_id, logged_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, description, calories, protein, fat, carbs, source, recipe_id, ts)
    )
    conn.commit()
    return cur.lastrowid


def get_meals_for_date(conn: sqlite3.Connection, user_id: int, date: str) -> list:
    return conn.execute(
        "SELECT * FROM meals WHERE user_id=? AND date(logged_at)=? ORDER BY logged_at",
        (user_id, date)
    ).fetchall()


def get_today_meals(conn: sqlite3.Connection, user_id: int) -> list:
    return get_meals_for_date(conn, user_id, _today_local())


def upsert_health_metrics(conn: sqlite3.Connection, user_id: int, date: str,
                           steps: int | None, sleep_deep_mins: int | None,
                           sleep_total_mins: int | None, resting_hr: int | None) -> None:
    # Insert row if missing, then patch only the non-null fields so partial syncs
    # (e.g. steps-only from Shortcuts) don't wipe data written by other sources.
    conn.execute(
        """INSERT INTO health_metrics(user_id, date, steps, sleep_deep_mins, sleep_total_mins, resting_hr)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(user_id, date) DO NOTHING""",
        (user_id, date, steps, sleep_deep_mins, sleep_total_mins, resting_hr)
    )
    updates = {}
    if steps is not None:
        updates["steps"] = steps
    if sleep_deep_mins is not None:
        updates["sleep_deep_mins"] = sleep_deep_mins
    if sleep_total_mins is not None:
        updates["sleep_total_mins"] = sleep_total_mins
    if resting_hr is not None:
        updates["resting_hr"] = resting_hr
    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(
            f"UPDATE health_metrics SET {set_clause} WHERE user_id=? AND date=?",
            (*updates.values(), user_id, date)
        )
    conn.commit()


def get_metrics_for_date(conn: sqlite3.Connection, user_id: int, date: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM health_metrics WHERE user_id=? AND date=?", (user_id, date)
    ).fetchone()
    return dict(row) if row else None


def insert_recipe(conn: sqlite3.Connection, user_id: int, name: str, calories: int,
                  protein: float, fat: float | None, carbs: float | None,
                  serving_unit: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO recipes(user_id, name, calories, protein, fat, carbs, serving_unit) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, name, calories, protein, fat, carbs, serving_unit)
    )
    conn.commit()
    return cur.lastrowid


def get_all_recipes(conn: sqlite3.Connection, user_id: int) -> list:
    return conn.execute(
        "SELECT * FROM recipes WHERE user_id=? ORDER BY name", (user_id,)
    ).fetchall()


def delete_meal(conn: sqlite3.Connection, user_id: int, meal_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM meals WHERE id=? AND user_id=?", (meal_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


def log_meal_from_recipe(conn: sqlite3.Connection, user_id: int, recipe_id: int) -> dict | None:
    """Fetch recipe and insert a meal row. Returns the meal dict or None if recipe not found."""
    row = conn.execute(
        "SELECT * FROM recipes WHERE id=? AND user_id=?", (recipe_id, user_id)
    ).fetchone()
    if not row:
        return None
    recipe = dict(row)
    conn.execute(
        "INSERT INTO meals(user_id, description, calories, protein, fat, carbs, source, recipe_id, logged_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, recipe["name"], recipe["calories"], recipe["protein"],
         recipe.get("fat"), recipe.get("carbs"), "recipe", recipe_id,
         _local_now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    return recipe
