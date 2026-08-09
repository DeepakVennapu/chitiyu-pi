"""One-shot migration: add budget_type + updated period CHECK to budgets table,
then backfill known categories and seed envelope budgets."""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent.parent.parent / "chitiyu.db"

CATEGORY_TYPES = {
    # fixed — non-negotiable, same every month
    "mortgage":      ("fixed",        "monthly"),
    "car":           ("fixed",        "monthly"),
    "utilities":     ("fixed",        "monthly"),
    "subscriptions": ("fixed",        "monthly"),
    # recurring — planned, monthly
    "family":        ("recurring",    "monthly"),
    "savings":       ("recurring",    "monthly"),
    "income":        ("recurring",    "monthly"),
    # discretionary — daily decisions
    "groceries":     ("discretionary","monthly"),
    "dining":        ("discretionary","monthly"),
    "shopping":      ("discretionary","monthly"),
    "misc":          ("discretionary","monthly"),
    "fuel":          ("discretionary","monthly"),
    # envelope — 6-month pools
    "travel":        ("envelope",     "biannual"),
    "insurance":     ("envelope",     "biannual"),
    "gifts":         ("envelope",     "biannual"),
}

ENVELOPE_AMOUNTS = {
    "travel":    10000.00,
    "insurance":  2500.00,
    "gifts":      1500.00,
}


def run():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = [dict(r) for r in conn.execute("SELECT * FROM budgets").fetchall()]
    print(f"Migrating {len(rows)} existing budget rows...")

    conn.executescript("""
        PRAGMA foreign_keys=OFF;
        ALTER TABLE budgets RENAME TO budgets_old;
        CREATE TABLE budgets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL DEFAULT 1,
            category    TEXT NOT NULL,
            amount      REAL NOT NULL,
            period      TEXT NOT NULL DEFAULT 'monthly'
                        CHECK(period IN ('monthly','weekly','biannual','annual')),
            budget_type TEXT NOT NULL DEFAULT 'discretionary'
                        CHECK(budget_type IN ('fixed','recurring','discretionary','envelope')),
            start_date  TEXT NOT NULL DEFAULT (date('now')),
            UNIQUE(user_id, category, period)
        );
        PRAGMA foreign_keys=ON;
    """)

    for r in rows:
        cat = r["category"].lower().strip()
        btype, period = CATEGORY_TYPES.get(cat, ("discretionary", "monthly"))
        amount = ENVELOPE_AMOUNTS.get(cat, r["amount"]) if btype == "envelope" else r["amount"]
        conn.execute(
            """INSERT OR IGNORE INTO budgets(user_id, category, amount, period, budget_type, start_date)
               VALUES (?,?,?,?,?,?)""",
            (r["user_id"], cat, amount, period, btype, r.get("start_date", "2026-08-08"))
        )

    conn.commit()

    final = conn.execute(
        "SELECT category, amount, period, budget_type FROM budgets ORDER BY budget_type, category"
    ).fetchall()
    print(f"\nMigrated {len(final)} budget rows:")
    for r in final:
        print(f"  [{r['budget_type']:14s}] {r['category']:16s}  ${r['amount']:>9,.2f}  / {r['period']}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    run()
