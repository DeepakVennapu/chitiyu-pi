import re
import sqlite3
from domains.health.db import search_ingredient

_UNIT_GRAMS: dict[str, float] = {
    "g": 1, "gram": 1, "grams": 1,
    "kg": 1000,
    "oz": 28, "ounce": 28, "ounces": 28,
    "lb": 454, "pound": 454, "pounds": 454,
    "cup": 240, "cups": 240,
    "tbsp": 15, "tablespoon": 15, "tablespoons": 15,
    "tsp": 5, "teaspoon": 5, "teaspoons": 5,
    "slice": 30, "slices": 30,
    "piece": 100, "pieces": 100,
    "egg": 50, "eggs": 50,
    "handful": 30,
    "scoop": 35,
}

_QTY_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*'           # quantity number
    r'(' + '|'.join(sorted(_UNIT_GRAMS, key=len, reverse=True)) + r')?\s*'  # optional unit
    r'([a-zA-Z][a-zA-Z\s]{1,40})',  # ingredient name (2–40 chars)
    re.IGNORECASE
)


def parse_quantity_text(text: str) -> list[dict]:
    """Parse '200g oats, 2 eggs' → [{"ingredient": "oats", "grams": 200}, ...]"""
    results = []
    for part in re.split(r'[,;]+', text):
        part = part.strip()
        if not part:
            continue
        m = _QTY_RE.search(part)
        if not m:
            continue
        qty = float(m.group(1))
        unit = (m.group(2) or "").lower().strip()
        name = m.group(3).strip().lower()
        grams = qty * _UNIT_GRAMS.get(unit, 100)  # default 100g if no unit
        results.append({"ingredient": name, "grams": grams})
    return results


def lookup_meal_macros(conn: sqlite3.Connection, text: str) -> dict | None:
    """
    Try to resolve meal text entirely from the local ingredients table.
    Returns macro dict with coverage_pct, or None if coverage < 50%.
    """
    items = parse_quantity_text(text)
    if not items:
        return None

    matched, unmatched = [], []
    totals = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    names = []

    for item in items:
        name = item["ingredient"]
        ing = search_ingredient(conn, name)
        # Try singular form if plural search fails (e.g. "eggs" → "egg")
        if ing is None and name.endswith("s"):
            ing = search_ingredient(conn, name[:-1])
        if ing is None:
            unmatched.append(name)
            continue
        scale = item["grams"] / 100.0
        totals["calories"] += ing["calories_per_100g"] * scale
        totals["protein"]  += ing["protein_per_100g"] * scale
        totals["fat"]      += ing["fat_per_100g"] * scale
        totals["carbs"]    += ing["carbs_per_100g"] * scale
        names.append(ing["name"])
        matched.append(item)

    if not items:
        return None
    coverage = len(matched) / len(items) * 100
    if coverage < 50:
        return None

    description = ", ".join(names) if names else text
    return {
        "description": description,
        "calories": round(totals["calories"]),
        "protein": round(totals["protein"], 1),
        "fat": round(totals["fat"], 1),
        "carbs": round(totals["carbs"], 1),
        "coverage_pct": round(coverage),
    }
