import json
import sqlite3
from utils.local_time import local_now, today_local


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
                      category: str | None = None,
                      limit: int = 50) -> list:
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
    query += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def delete_transaction(conn: sqlite3.Connection, user_id: int, tx_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


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
    today = local_now().date()
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
                  amount: float, period: str = "monthly",
                  budget_type: str = "discretionary") -> int:
    from datetime import date
    category = category.lower().strip()
    conn.execute(
        """INSERT INTO budgets(user_id, category, amount, period, budget_type, start_date)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(user_id, category, period) DO UPDATE SET
             amount=excluded.amount,
             budget_type=excluded.budget_type,
             start_date=excluded.start_date""",
        (user_id, category, amount, period, budget_type, date.today().isoformat())
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM budgets WHERE user_id=? AND category=? AND period=?",
        (user_id, category, period)
    ).fetchone()
    return row["id"]


def get_discretionary_total(conn: sqlite3.Connection, user_id: int,
                             year: int, month: int) -> tuple[float, float]:
    """Returns (spent, budget) for discretionary categories only."""
    month_str = f"{year:04d}-{month:02d}"
    disc_cats = [r["category"] for r in conn.execute(
        "SELECT category FROM budgets WHERE user_id=? AND budget_type='discretionary'",
        (user_id,)
    ).fetchall()]
    if not disc_cats:
        return 0.0, 0.0
    placeholders = ",".join("?" * len(disc_cats))
    spent_row = conn.execute(
        f"""SELECT COALESCE(ABS(SUM(amount)), 0) as total
            FROM transactions
            WHERE user_id=? AND strftime('%Y-%m', date)=?
              AND amount < 0 AND category IN ({placeholders})""",
        [user_id, month_str] + disc_cats
    ).fetchone()
    budget_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM budgets WHERE user_id=? AND budget_type='discretionary'",
        (user_id,)
    ).fetchone()
    return round(spent_row["total"], 2), round(budget_row["total"], 2)


def get_envelope_spend(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    """Returns YTD spend for each envelope category vs its pool amount."""
    from datetime import date
    year = date.today().year
    envelopes = conn.execute(
        "SELECT category, amount, period FROM budgets WHERE user_id=? AND budget_type='envelope'",
        (user_id,)
    ).fetchall()
    result = []
    for e in envelopes:
        row = conn.execute(
            """SELECT COALESCE(ABS(SUM(amount)), 0) as spent
               FROM transactions
               WHERE user_id=? AND category=? AND amount < 0
                 AND strftime('%Y', date)=?""",
            (user_id, e["category"], str(year))
        ).fetchone()
        result.append({
            "category": e["category"],
            "pool": e["amount"],
            "period": e["period"],
            "spent_ytd": round(row["spent"], 2),
            "remaining": round(e["amount"] - row["spent"], 2),
        })
    return result


def get_next_milestone(conn: sqlite3.Connection, user_id: int) -> dict | None:
    """Returns the next upcoming milestone with the latest Chase checking balance."""
    from datetime import date
    today = date.today().isoformat()
    row = conn.execute(
        """SELECT * FROM financial_milestones
           WHERE user_id=? AND target_date >= ?
           ORDER BY target_date ASC LIMIT 1""",
        (user_id, today)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    # Chase Checking balance only — milestone targets were built against this account
    balance_row = conn.execute(
        """SELECT ab.balance FROM account_balances ab
           JOIN accounts a ON a.id = ab.account_id
           WHERE ab.user_id=? AND LOWER(a.name) LIKE '%chase%' AND a.type='checking'
           ORDER BY ab.date DESC LIMIT 1""",
        (user_id,)
    ).fetchone()
    d["current_balance"] = balance_row["balance"] if balance_row else None
    return d


def list_budgets(conn: sqlite3.Connection, user_id: int) -> list:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM budgets WHERE user_id=? ORDER BY category", (user_id,)
    ).fetchall()]


def get_budget(conn: sqlite3.Connection, user_id: int, category: str,
               period: str = "monthly") -> dict | None:
    category = category.lower().strip()
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


# ── Account Balances ───────────────────────────────────────────────────────────

def upsert_account_balance(conn: sqlite3.Connection, user_id: int,
                           account_id: int, date: str, balance: float,
                           note: str | None = None) -> int:
    conn.execute(
        """INSERT INTO account_balances(user_id, account_id, date, balance, note)
           VALUES (?,?,?,?,?)
           ON CONFLICT(account_id, date) DO UPDATE SET
             balance=excluded.balance,
             note=excluded.note""",
        (user_id, account_id, date, balance, note)
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM account_balances WHERE account_id=? AND date=?",
        (account_id, date)
    ).fetchone()
    return row["id"]


def get_latest_balances(conn: sqlite3.Connection, user_id: int) -> list:
    """Returns the most recent balance for each account."""
    return [dict(r) for r in conn.execute(
        """SELECT ab.*, a.name as account_name, a.type as account_type
           FROM account_balances ab
           JOIN accounts a ON a.id = ab.account_id
           WHERE ab.user_id=?
             AND ab.date = (
               SELECT MAX(ab2.date) FROM account_balances ab2
               WHERE ab2.account_id = ab.account_id
             )
           ORDER BY a.type, a.name""",
        (user_id,)
    ).fetchall()]


def list_balance_history(conn: sqlite3.Connection, user_id: int,
                         account_id: int | None = None, limit: int = 60) -> list:
    query = """SELECT ab.*, a.name as account_name, a.type as account_type
               FROM account_balances ab
               JOIN accounts a ON a.id = ab.account_id
               WHERE ab.user_id=?"""
    params: list = [user_id]
    if account_id:
        query += " AND ab.account_id=?"
        params.append(account_id)
    query += " ORDER BY ab.date DESC, ab.account_id LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def compute_net_worth_from_balances(conn: sqlite3.Connection, user_id: int) -> float | None:
    """Compute net worth from latest account balances.
    Credit accounts subtract from net worth; all others add."""
    rows = get_latest_balances(conn, user_id)
    if not rows:
        return None
    total = 0.0
    for r in rows:
        if r["account_type"] == "credit":
            total -= abs(r["balance"])
        else:
            total += r["balance"]
    return round(total, 2)


# ── Financial Milestones ───────────────────────────────────────────────────────

def upsert_milestone(conn: sqlite3.Connection, user_id: int, period_label: str,
                     target_date: str, expected_net_worth: float,
                     actual_net_worth: float | None = None,
                     note: str | None = None) -> int:
    conn.execute(
        """INSERT INTO financial_milestones
               (user_id, period_label, target_date, expected_net_worth, actual_net_worth, note)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(user_id, target_date) DO UPDATE SET
             period_label=excluded.period_label,
             expected_net_worth=excluded.expected_net_worth,
             actual_net_worth=COALESCE(excluded.actual_net_worth, actual_net_worth),
             note=COALESCE(excluded.note, note)""",
        (user_id, period_label, target_date, expected_net_worth, actual_net_worth, note)
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM financial_milestones WHERE user_id=? AND target_date=?",
        (user_id, target_date)
    ).fetchone()
    return row["id"]


def update_milestone_actual(conn: sqlite3.Connection, user_id: int,
                             target_date: str, actual_net_worth: float) -> bool:
    cur = conn.execute(
        "UPDATE financial_milestones SET actual_net_worth=? WHERE user_id=? AND target_date=?",
        (actual_net_worth, user_id, target_date)
    )
    conn.commit()
    return cur.rowcount > 0


def list_milestones(conn: sqlite3.Connection, user_id: int,
                    period_label: str | None = None) -> list:
    query = "SELECT * FROM financial_milestones WHERE user_id=?"
    params: list = [user_id]
    if period_label:
        query += " AND period_label=?"
        params.append(period_label)
    query += " ORDER BY target_date ASC"
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def list_milestone_periods(conn: sqlite3.Connection, user_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT period_label FROM financial_milestones WHERE user_id=? ORDER BY period_label",
        (user_id,)
    ).fetchall()
    return [r["period_label"] for r in rows]


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
