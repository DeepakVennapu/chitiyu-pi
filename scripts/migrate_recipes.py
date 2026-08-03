"""One-time: copy recipes from pi.db to chitiyu.db. Use --dry-run to preview without writing."""
import argparse
import sqlite3
import sys

SRC = "/Users/me/deep-workspace/personal-intelligence/data/pi.db"
DST = "/Users/me/deep-workspace/chitiyu-pi/chitiyu.db"

parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true", help="Preview only — don't write")
parser.add_argument("--src", default=SRC)
parser.add_argument("--dst", default=DST)
args = parser.parse_args()

src = sqlite3.connect(args.src)
src.row_factory = sqlite3.Row

rows = src.execute("SELECT * FROM recipes").fetchall()
if not rows:
    print("No recipes in pi.db — nothing to migrate.")
    sys.exit(0)

print(f"Found {len(rows)} recipes to migrate:")
for r in rows:
    print(f"  {r['name']} — {r['calories']} kcal, {r['protein_g']}g protein")

if args.dry_run:
    print("Dry run — no changes written.")
    src.close()
    sys.exit(0)

dst = sqlite3.connect(args.dst)
for r in rows:
    dst.execute(
        "INSERT OR IGNORE INTO recipes(user_id, name, calories, protein, fat, carbs, serving_unit) "
        "VALUES (?,?,?,?,?,?,?)",
        (1, r["name"], r["calories"], r["protein_g"], r["fat_g"], r["carbs_g"], r["serving_size"])
    )
dst.commit()
print(f"Migrated {len(rows)} recipes to {args.dst}.")
src.close()
dst.close()
