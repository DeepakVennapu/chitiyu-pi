import sqlite3, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from db.schema import initialize_schema

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
