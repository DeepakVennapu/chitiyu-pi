import sqlite3, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from db.schema import initialize_schema
from domains.health.db import insert_ingredient, search_ingredient, update_recipe_serving, insert_recipe

def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_schema(conn)
    return conn

def test_ingredients_table_exists():
    conn = make_conn()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ingredients'"
    ).fetchone()
    assert row is not None, "ingredients table missing"

def test_recipes_has_serving_columns():
    conn = make_conn()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(recipes)")}
    assert "serving_grams" in cols
    assert "serving_label" in cols

def test_insert_and_search_ingredient():
    conn = make_conn()
    insert_ingredient(conn, "Chicken breast", 165, 31.0, 3.6, 0.0, "protein")
    result = search_ingredient(conn, "chicken breast")
    assert result is not None
    assert result["name"] == "Chicken breast"
    assert result["calories_per_100g"] == 165

def test_search_ingredient_case_insensitive():
    conn = make_conn()
    insert_ingredient(conn, "Brown Rice", 216, 4.5, 1.8, 45.0, "grain")
    result = search_ingredient(conn, "brown rice")
    assert result is not None

def test_search_ingredient_partial_match():
    conn = make_conn()
    insert_ingredient(conn, "Greek yogurt plain", 59, 10.0, 0.4, 3.6, "dairy")
    result = search_ingredient(conn, "greek yogurt")
    assert result is not None

def test_search_ingredient_not_found():
    conn = make_conn()
    result = search_ingredient(conn, "zzznomatch")
    assert result is None

def test_update_recipe_serving():
    conn = make_conn()
    rid = insert_recipe(conn, 1, "Oats", 300, 10.0, 5.0, 50.0)
    update_recipe_serving(conn, rid, 80, "1 cup dry")
    row = conn.execute("SELECT serving_grams, serving_label FROM recipes WHERE id=?", (rid,)).fetchone()
    assert row["serving_grams"] == 80
    assert row["serving_label"] == "1 cup dry"


def test_seed_is_idempotent():
    conn = make_conn()
    # Can't use DB_PATH in tests — seed into in-memory conn by calling insert_ingredient directly
    insert_ingredient(conn, "Oats dry", 389, 17.0, 7.0, 66.0, "grain")
    # Run again — should not raise
    insert_ingredient(conn, "Oats dry", 389, 17.0, 7.0, 66.0, "grain")
    rows = conn.execute("SELECT count(*) as n FROM ingredients WHERE name_lower='oats dry'").fetchone()
    assert rows["n"] == 1
