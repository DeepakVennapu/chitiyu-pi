import sqlite3
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from db.schema import initialize_schema


def _make_src_db(recipes: list[dict]) -> str:
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE recipes (
        id INTEGER PRIMARY KEY, name TEXT, calories INTEGER,
        protein_g REAL, fat_g REAL, carbs_g REAL, serving_size TEXT
    )""")
    for r in recipes:
        conn.execute("INSERT INTO recipes(name,calories,protein_g,fat_g,carbs_g,serving_size) "
                     "VALUES (?,?,?,?,?,?)",
                     (r["name"], r["calories"], r["protein_g"], r["fat_g"], r["carbs_g"], r.get("serving_size")))
    conn.commit()
    conn.close()
    return path


def test_dry_run_does_not_write():
    src = _make_src_db([{"name": "Oats", "calories": 300, "protein_g": 10.0, "fat_g": 5.0, "carbs_g": 55.0}])
    dst = tempfile.mktemp(suffix=".db")
    dst_conn = sqlite3.connect(dst)
    initialize_schema(dst_conn)
    dst_conn.close()
    import subprocess
    subprocess.run([sys.executable, "scripts/migrate_recipes.py",
                    "--src", src, "--dst", dst, "--dry-run"], check=True,
                   cwd=os.path.join(os.path.dirname(__file__), '..'))
    dst_conn = sqlite3.connect(dst)
    dst_conn.row_factory = sqlite3.Row
    rows = dst_conn.execute("SELECT * FROM recipes").fetchall()
    assert len(rows) == 0, "Dry run should not insert rows"
    dst_conn.close()


def test_migration_writes_recipes():
    src = _make_src_db([
        {"name": "Eggs", "calories": 140, "protein_g": 12.0, "fat_g": 10.0, "carbs_g": 0.0},
        {"name": "Oats", "calories": 300, "protein_g": 10.0, "fat_g": 5.0, "carbs_g": 55.0},
    ])
    dst = tempfile.mktemp(suffix=".db")
    dst_conn = sqlite3.connect(dst)
    initialize_schema(dst_conn)
    dst_conn.close()
    import subprocess
    subprocess.run([sys.executable, "scripts/migrate_recipes.py",
                    "--src", src, "--dst", dst], check=True,
                   cwd=os.path.join(os.path.dirname(__file__), '..'))
    dst_conn = sqlite3.connect(dst)
    dst_conn.row_factory = sqlite3.Row
    rows = dst_conn.execute("SELECT * FROM recipes WHERE user_id=1").fetchall()
    assert len(rows) == 2
    names = {r["name"] for r in rows}
    assert "Eggs" in names and "Oats" in names
    dst_conn.close()
