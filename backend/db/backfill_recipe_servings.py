# Run: python backend/db/backfill_recipe_servings.py
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.schema import initialize_schema
from domains.health.db import search_ingredient, update_recipe_serving
from config import DB_PATH

MANUAL_OVERRIDES = {
    # recipe name substring → (serving_grams, serving_label)
    "chicken drumstick": (None, "2 drumsticks"),
    "cashew brittle": (30, "~30g"),
    "bellam kaju": (30, "~30g"),
    "peanuts": (28, "1 oz"),
    "kachori": (60, "1 piece"),
    "filter coffee": (240, "1 cup"),
    "homemade curd": (150, "small bowl"),
    "chocolate": (30, "~30g"),
    "trail mix": (43, "1 serving"),
    "walnuts": (14, "0.5 oz"),
    "paneer": (100, "100g"),
    "moong dal": (200, "1 bowl"),
    "quinoa": (100, "100g"),
    "tomato paneer": (200, "1 bowl"),
}

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
initialize_schema(conn)

recipes = conn.execute("SELECT id, name FROM recipes WHERE serving_grams IS NULL").fetchall()
updated = 0
for r in recipes:
    name_lower = r["name"].lower()
    # Check manual overrides first
    for key, (grams, label) in MANUAL_OVERRIDES.items():
        if key in name_lower:
            update_recipe_serving(conn, r["id"], grams, label)
            print(f"  override: {r['name']} → {label}")
            updated += 1
            break
    else:
        # Try ingredient DB fuzzy match
        ing = search_ingredient(conn, name_lower)
        if ing:
            update_recipe_serving(conn, r["id"], 100, "100g")
            print(f"  matched: {r['name']} → 100g ({ing['name']})")
            updated += 1

conn.close()
print(f"Updated {updated} / {len(recipes)} recipes")
