import json
import sqlite3
from datetime import datetime, timezone


# ── Accounts ──────────────────────────────────────────────────────────────────

def insert_account(conn: sqlite3.Connection, user_id: int, name: str,
                   acct_type: str, currency: str = "USD") -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO accounts(user_id, name, type, currency) VALUES (?,?,?,?)",
        (user_id, name, acct_type, currency)
    )
    conn.commit()
    if cur.lastrowid and cur.lastrowid > 0:
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM accounts WHERE user_id=? AND name=?", (user_id, name)
    ).fetchone()
    return row["id"]


def get_account_by_name(conn: sqlite3.Connection, user_id: int, name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM accounts WHERE user_id=? AND name=? COLLATE NOCASE", (user_id, name)
    ).fetchone()
    return dict(row) if row else None


def list_accounts(conn: sqlite3.Connection, user_id: int) -> list:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM accounts WHERE user_id=? ORDER BY name", (user_id,)
    ).fetchall()]


# ── Transactions ───────────────────────────────────────────────────────────────

def insert_transaction(conn: sqlite3.Connection, user_id: int, date: str,
                       amount: float, category: str, description: str,
                       source: str = "manual",
                       account_id: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO transactions(user_id, account_id, date, amount, category, description, source) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, account_id, date, amount, category, description, source)
    )
    conn.commit()
    return cur.lastrowid


def list_transactions(conn: sqlite3.Connection, user_id: int,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      category: str | None = None) -> list:
    query = "SELECT * FROM transactions WHERE user_id=?"
    params: list = [user_id]
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY date DESC, id DESC"
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_monthly_spend(conn: sqlite3.Connection, user_id: int,
                      year: int, month: int) -> dict[str, float]:
    """Returns {category: total_spent} for the given month (negative amounts only = expenses)."""
    month_str = f"{year:04d}-{month:02d}"
    rows = conn.execute(
        """SELECT category, SUM(amount) as total
           FROM transactions
           WHERE user_id=? AND strftime('%Y-%m', date)=? AND amount < 0
           GROUP BY category""",
        (user_id, month_str)
    ).fetchall()
    # Return absolute spend values (positive numbers represent money spent)
    return {r["category"]: abs(r["total"]) for r in rows}


def get_category_spend_this_month(conn: sqlite3.Connection, user_id: int, category: str) -> float:
    """Returns total absolute spend for category in the current calendar month."""
    today = datetime.now(timezone.utc).date()
    month_str = f"{today.year:04d}-{today.month:02d}"
    row = conn.execute(
        """SELECT COALESCE(SUM(amount), 0) as total
           FROM transactions
           WHERE user_id=? AND category=? AND strftime('%Y-%m', date)=? AND amount < 0""",
        (user_id, category, month_str)
    ).fetchone()
    return abs(row["total"])


# ── Budgets ────────────────────────────────────────────────────────────────────

def upsert_budget(conn: sqlite3.Connection, user_id: int, category: str,
                  amount: float, period: str = "monthly") -> int:
    from datetime import date
    conn.execute(
        """INSERT INTO budgets(user_id, category, amount, period, start_date)
           VALUES (?,?,?,?,?)
           ON CONFLICT(user_id, category, period) DO UPDATE SET
             amount=excluded.amount,
             start_date=excluded.start_date""",
        (user_id, category, amount, period, date.today().isoformat())
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM budgets WHERE user_id=? AND category=? AND period=?",
        (user_id, category, period)
    ).fetchone()
    return row["id"]


def list_budgets(conn: sqlite3.Connection, user_id: int) -> list:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM budgets WHERE user_id=? ORDER BY category", (user_id,)
    ).fetchall()]


def get_budget(conn: sqlite3.Connection, user_id: int, category: str,
               period: str = "monthly") -> dict | None:
    row = conn.execute(
        "SELECT * FROM budgets WHERE user_id=? AND category=? AND period=?",
        (user_id, category, period)
    ).fetchone()
    return dict(row) if row else None


# ── Net Worth ──────────────────────────────────────────────────────────────────

def insert_net_worth(conn: sqlite3.Connection, user_id: int, snapshot_date: str,
                     assets_json: dict, liabilities_json: dict, total: float) -> int:
    cur = conn.execute(
        """INSERT INTO net_worth(user_id, snapshot_date, assets_json, liabilities_json, total)
           VALUES (?,?,?,?,?)
           ON CONFLICT(user_id, snapshot_date) DO UPDATE SET
             assets_json=excluded.assets_json,
             liabilities_json=excluded.liabilities_json,
             total=excluded.total""",
        (user_id, snapshot_date,
         json.dumps(assets_json), json.dumps(liabilities_json), total)
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM net_worth WHERE user_id=? AND snapshot_date=?",
        (user_id, snapshot_date)
    ).fetchone()
    return row["id"]


def get_latest_net_worth(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM net_worth WHERE user_id=? ORDER BY snapshot_date DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["assets_json"] = json.loads(d["assets_json"])
    d["liabilities_json"] = json.loads(d["liabilities_json"])
    return d


def list_net_worth_snapshots(conn: sqlite3.Connection, user_id: int, limit: int = 12) -> list:
    rows = conn.execute(
        "SELECT * FROM net_worth WHERE user_id=? ORDER BY snapshot_date DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["assets_json"] = json.loads(d["assets_json"])
        d["liabilities_json"] = json.loads(d["liabilities_json"])
        result.append(d)
    return result


# ── Savings Goals ──────────────────────────────────────────────────────────────

def insert_savings_goal(conn: sqlite3.Connection, user_id: int, name: str,
                        target_amount: float, target_date: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO savings_goals(user_id, name, target_amount, target_date) VALUES (?,?,?,?)",
        (user_id, name, target_amount, target_date)
    )
    conn.commit()
    return cur.lastrowid


def update_savings_goal_progress(conn: sqlite3.Connection, user_id: int,
                                  goal_id: int, current_amount: float) -> bool:
    cur = conn.execute(
        "UPDATE savings_goals SET current_amount=? WHERE id=? AND user_id=?",
        (current_amount, goal_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


def list_savings_goals(conn: sqlite3.Connection, user_id: int) -> list:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM savings_goals WHERE user_id=? ORDER BY target_date ASC NULLS LAST, name",
        (user_id,)
    ).fetchall()]


def get_savings_goal(conn: sqlite3.Connection, user_id: int, goal_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM savings_goals WHERE id=? AND user_id=?", (goal_id, user_id)
    ).fetchone()
    return dict(row) if row else None
