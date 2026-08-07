import sqlite3
from datetime import datetime, timezone


def insert_meal(conn: sqlite3.Connection, user_id: int, description: str,
                calories: int, protein: float, fat: float | None, carbs: float | None,
                source: str = "text", recipe_id: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO meals(user_id, description, calories, protein, fat, carbs, source, recipe_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (user_id, description, calories, protein, fat, carbs, source, recipe_id)
    )
    conn.commit()
    return cur.lastrowid


def get_meals_for_date(conn: sqlite3.Connection, user_id: int, date: str) -> list:
    return conn.execute(
        "SELECT * FROM meals WHERE user_id=? AND date(logged_at)=? ORDER BY logged_at",
        (user_id, date)
    ).fetchall()


def get_today_meals(conn: sqlite3.Connection, user_id: int) -> list:
    today = datetime.now(timezone.utc).date().isoformat()
    return get_meals_for_date(conn, user_id, today)


def upsert_health_metrics(conn: sqlite3.Connection, user_id: int, date: str,
                           steps: int | None, sleep_deep_mins: int | None,
                           sleep_total_mins: int | None, resting_hr: int | None) -> None:
    conn.execute(
        """INSERT INTO health_metrics(user_id, date, steps, sleep_deep_mins, sleep_total_mins, resting_hr)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(user_id, date) DO UPDATE SET
             steps=excluded.steps,
             sleep_deep_mins=excluded.sleep_deep_mins,
             sleep_total_mins=excluded.sleep_total_mins,
             resting_hr=excluded.resting_hr""",
        (user_id, date, steps, sleep_deep_mins, sleep_total_mins, resting_hr)
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
    from datetime import datetime, timezone
    conn.execute(
        "INSERT INTO meals(user_id, description, calories, protein, fat, carbs, source, recipe_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (user_id, recipe["name"], recipe["calories"], recipe["protein"],
         recipe.get("fat"), recipe.get("carbs"), "recipe", recipe_id)
    )
    conn.commit()
    return recipe
