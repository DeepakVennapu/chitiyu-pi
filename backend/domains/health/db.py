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


def delete_recipe(conn: sqlite3.Connection, user_id: int, recipe_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM recipes WHERE id=? AND user_id=?", (recipe_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


def log_meal_from_recipe(conn: sqlite3.Connection, user_id: int, recipe_id: int,
                         logged_at: str | None = None) -> dict | None:
    """Fetch recipe and insert a meal row. Returns the meal dict or None if recipe not found."""
    row = conn.execute(
        "SELECT * FROM recipes WHERE id=? AND user_id=?", (recipe_id, user_id)
    ).fetchone()
    if not row:
        return None
    recipe = dict(row)
    ts = _to_local_ts(logged_at) if logged_at else _local_now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO meals(user_id, description, calories, protein, fat, carbs, source, recipe_id, logged_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (user_id, recipe["name"], recipe["calories"], recipe["protein"],
         recipe.get("fat"), recipe.get("carbs"), "recipe", recipe_id, ts)
    )
    conn.commit()
    return recipe


def upsert_weight_log(conn: sqlite3.Connection, user_id: int, date: str,
                      recorded_at: str, weight_kg: float,
                      bodyfat_pct: float | None, muscle_kg: float | None,
                      bmi: float | None, source: str = "renpho") -> None:
    conn.execute(
        """INSERT INTO weight_logs(user_id, date, recorded_at, weight_kg, bodyfat_pct, muscle_kg, bmi, source)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(user_id, date) DO UPDATE SET
               recorded_at=excluded.recorded_at,
               weight_kg=excluded.weight_kg,
               bodyfat_pct=excluded.bodyfat_pct,
               muscle_kg=excluded.muscle_kg,
               bmi=excluded.bmi,
               source=excluded.source""",
        (user_id, date, recorded_at, weight_kg, bodyfat_pct, muscle_kg, bmi, source)
    )
    conn.commit()


def get_weight_logs(conn: sqlite3.Connection, user_id: int, days: int = 7) -> list:
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = conn.execute(
        "SELECT * FROM weight_logs WHERE user_id=? AND date>=? ORDER BY date ASC",
        (user_id, cutoff)
    ).fetchall()
    return [dict(r) for r in rows]


def get_latest_weight(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM weight_logs WHERE user_id=? ORDER BY date DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    return dict(row) if row else None


def insert_ingredient(conn: sqlite3.Connection, name: str,
                      calories_per_100g: float, protein_per_100g: float,
                      fat_per_100g: float, carbs_per_100g: float,
                      category: str = "other") -> int:
    cur = conn.execute(
        """INSERT INTO ingredients(name, name_lower, calories_per_100g, protein_per_100g,
                                   fat_per_100g, carbs_per_100g, category)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(name_lower) DO UPDATE SET
               calories_per_100g=excluded.calories_per_100g,
               protein_per_100g=excluded.protein_per_100g,
               fat_per_100g=excluded.fat_per_100g,
               carbs_per_100g=excluded.carbs_per_100g,
               category=excluded.category""",
        (name, name.lower(), calories_per_100g, protein_per_100g,
         fat_per_100g, carbs_per_100g, category)
    )
    conn.commit()
    return cur.lastrowid


def search_ingredient(conn: sqlite3.Connection, query: str) -> dict | None:
    q = query.lower().strip()
    # Exact match first
    row = conn.execute(
        "SELECT * FROM ingredients WHERE name_lower=?", (q,)
    ).fetchone()
    if row:
        return dict(row)
    # Partial: all words in query must appear in name
    words = q.split()
    like_clause = " AND ".join("name_lower LIKE ?" for _ in words)
    params = [f"%{w}%" for w in words]
    row = conn.execute(
        f"SELECT * FROM ingredients WHERE {like_clause} LIMIT 1", params
    ).fetchone()
    return dict(row) if row else None


def update_recipe_serving(conn: sqlite3.Connection, recipe_id: int,
                           serving_grams: int, serving_label: str) -> None:
    conn.execute(
        "UPDATE recipes SET serving_grams=?, serving_label=? WHERE id=?",
        (serving_grams, serving_label, recipe_id)
    )
    conn.commit()
