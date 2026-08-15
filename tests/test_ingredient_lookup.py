import sqlite3, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from db.schema import initialize_schema
from domains.health.db import insert_ingredient
from domains.health.ingredient_lookup import parse_quantity_text, lookup_meal_macros

def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize_schema(conn)
    return conn

def seed(conn):
    insert_ingredient(conn, "Oats", 389, 17.0, 7.0, 66.0, "grain")
    insert_ingredient(conn, "Whole egg", 155, 13.0, 11.0, 1.1, "protein")
    insert_ingredient(conn, "Peanut butter", 588, 25.0, 50.0, 20.0, "fat")
    insert_ingredient(conn, "Banana", 89, 1.1, 0.3, 23.0, "fruit")

def test_parse_grams_explicit():
    items = parse_quantity_text("200g oats")
    assert len(items) == 1
    assert items[0]["ingredient"] == "oats"
    assert items[0]["grams"] == 200

def test_parse_cup():
    items = parse_quantity_text("1 cup oats")
    assert items[0]["grams"] == 240

def test_parse_tbsp():
    items = parse_quantity_text("2 tbsp peanut butter")
    assert items[0]["grams"] == 30

def test_parse_multiple_items():
    items = parse_quantity_text("100g oats, 2 eggs, 1 tbsp peanut butter")
    assert len(items) == 3

def test_lookup_full_match():
    conn = make_conn()
    seed(conn)
    result = lookup_meal_macros(conn, "100g oats, 2 eggs")
    assert result is not None
    assert result["calories"] > 0
    assert result["coverage_pct"] == 100

def test_lookup_returns_none_on_low_coverage():
    conn = make_conn()
    # No ingredients seeded — nothing matches
    result = lookup_meal_macros(conn, "200g oats, 1 banana")
    assert result is None

def test_lookup_description_combined():
    conn = make_conn()
    seed(conn)
    result = lookup_meal_macros(conn, "100g oats, 1 banana")
    assert result is not None
    assert "oats" in result["description"].lower() or "banana" in result["description"].lower()
