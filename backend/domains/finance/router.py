# backend/domains/finance/router.py
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from auth import verify_api_key
from config import DB_PATH
from db.connection import get_connection
from db.schema import initialize_schema
from domains.finance.db import (
    delete_transaction,
    get_latest_net_worth,
    insert_net_worth,
    insert_savings_goal,
    insert_transaction,
    list_budgets,
    list_net_worth_snapshots,
    list_savings_goals,
    list_transactions,
    update_savings_goal_progress,
    upsert_budget,
    get_monthly_spend,
    get_budget,
)
from domains.finance.formatter import format_budget_summary

router = APIRouter(prefix="/finance", tags=["finance"],
                   dependencies=[Depends(verify_api_key)])


def _conn():
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


# ── Pydantic models ────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    user_id: int = 1
    text: str | None = None          # NL input (Telegram / orchestrator path)
    date: str | None = None          # ISO YYYY-MM-DD (direct / CSV path)
    amount: float | None = None
    category: str | None = None
    description: str | None = None
    account: str | None = None
    source: str = "manual"
    context: str = ""


class BudgetCreate(BaseModel):
    user_id: int = 1
    category: str
    amount: float
    period: str = "monthly"


class NetWorthCreate(BaseModel):
    user_id: int = 1
    snapshot_date: str | None = None
    assets_json: dict[str, Any] = {}
    liabilities_json: dict[str, Any] = {}
    total: float | None = None


class GoalCreate(BaseModel):
    user_id: int = 1
    name: str
    target_amount: float
    target_date: str | None = None


class GoalProgressUpdate(BaseModel):
    current_amount: float


# ── Transactions ───────────────────────────────────────────────────────────────

@router.post("/transactions")
def log_transaction(body: TransactionCreate):
    conn = _conn()
    try:
        if body.text:
            # NL path — Haiku parses the text, inserts, returns the row dict for the app
            from domains.finance.tools import add_transaction_structured
            tx = add_transaction_structured(conn, body.user_id, body.text, context=body.context)
            if tx is None:
                raise HTTPException(422, "Couldn't parse that expense. "
                                         "Try: 'spent $45 at Whole Foods on groceries'.")
            # Override LLM-derived category if the user explicitly provided one
            if body.category is not None:
                conn.execute("UPDATE transactions SET category=? WHERE id=?",
                             (body.category, tx["id"]))
                conn.commit()
                tx["category"] = body.category
            return tx
        # Structured path — all fields provided directly
        if body.date is None or body.amount is None or body.description is None:
            raise HTTPException(422, "Provide either 'text' for NL parsing or "
                                     "'date', 'amount', and 'description' for direct entry.")
        tid = insert_transaction(
            conn, body.user_id,
            body.date, body.amount,
            body.category or "other",
            body.description, body.source
        )
        return {
            "id": tid, "date": body.date, "amount": body.amount,
            "category": body.category or "other",
            "description": body.description,
            "source": body.source,
        }
    finally:
        conn.close()


@router.get("/transactions")
def get_transactions(user_id: int = 1, date_from: str | None = None,
                     date_to: str | None = None, category: str | None = None):
    conn = _conn()
    try:
        txns = list_transactions(conn, user_id, date_from=date_from,
                                 date_to=date_to, category=category)
        return {"transactions": txns}
    finally:
        conn.close()


@router.delete("/transactions/{tx_id}")
def delete_transaction_endpoint(tx_id: int, user_id: int = 1):
    conn = _conn()
    ok = delete_transaction(conn, user_id, tx_id)
    conn.close()
    if not ok:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}


# ── CSV import ─────────────────────────────────────────────────────────────────

@router.post("/import/csv")
async def import_csv(file: UploadFile = File(...),
                     user_id: int = 1, transform: str | None = None):
    """
    Import a CSV file. Accepts:
    - Canonical format (date, amount, description, category, account) directly.
    - Bank format when `transform` query param names a transforms/ file
      (e.g. transform=chase or transform=apple-card).
    """
    from domains.finance.csv_import import import_csv_file
    contents = await file.read()
    conn = _conn()
    try:
        count, errors = import_csv_file(conn, user_id, contents.decode("utf-8"),
                                        transform_name=transform)
        return {"imported": count, "errors": errors}
    except Exception as e:
        raise HTTPException(400, f"CSV import failed: {e}")
    finally:
        conn.close()


# ── Budget summary ─────────────────────────────────────────────────────────────

@router.get("/summary/{year}/{month}")
def budget_summary(year: int, month: int, user_id: int = 1):
    if not (1 <= month <= 12):
        raise HTTPException(400, "month must be 1–12")
    conn = _conn()
    try:
        spend = get_monthly_spend(conn, user_id, year, month)
        budgets = list_budgets(conn, user_id)
        budget_map = {b["category"]: b["amount"] for b in budgets}

        total_spent = sum(spend.values())
        total_budget = sum(budget_map.values()) if budget_map else None

        categories = []
        all_cats = sorted(set(list(spend.keys()) + list(budget_map.keys())))
        for cat in all_cats:
            spent = spend.get(cat, 0.0)
            limit = budget_map.get(cat)
            categories.append({
                "category": cat,
                "spent": round(spent, 2),
                "budget": round(limit, 2) if limit is not None else None,
                "over_budget": limit is not None and spent > limit,
            })

        return {
            "year": year,
            "month": month,
            "total_spent": round(total_spent, 2),
            "total_budget": round(total_budget, 2) if total_budget is not None else None,
            "categories": categories,
        }
    finally:
        conn.close()


# ── Budgets ────────────────────────────────────────────────────────────────────

@router.get("/budgets")
def get_budgets(user_id: int = 1):
    conn = _conn()
    try:
        return list_budgets(conn, user_id)
    finally:
        conn.close()


@router.post("/budgets")
def create_budget(body: BudgetCreate):
    conn = _conn()
    try:
        from domains.finance.db import upsert_budget
        bid = upsert_budget(conn, body.user_id, body.category, body.amount, body.period)
        return {"id": bid, "category": body.category,
                "amount": body.amount, "period": body.period}
    finally:
        conn.close()


# ── Net Worth ──────────────────────────────────────────────────────────────────

@router.get("/networth")
def get_networth(user_id: int = 1):
    conn = _conn()
    try:
        latest = get_latest_net_worth(conn, user_id)
        if latest is None:
            raise HTTPException(404, "No net worth snapshots recorded yet.")
        return latest
    finally:
        conn.close()


@router.post("/networth")
def record_networth(body: NetWorthCreate):
    conn = _conn()
    try:
        date = body.snapshot_date or datetime.now(timezone.utc).date().isoformat()
        total = body.total
        if total is None:
            total = sum(body.assets_json.values()) - sum(body.liabilities_json.values())
        nwid = insert_net_worth(conn, body.user_id, date,
                                body.assets_json, body.liabilities_json, total)
        return {"id": nwid, "snapshot_date": date, "total": total}
    finally:
        conn.close()


# ── Savings Goals ──────────────────────────────────────────────────────────────

@router.get("/goals")
def get_goals(user_id: int = 1):
    conn = _conn()
    try:
        return {"goals": list_savings_goals(conn, user_id)}
    finally:
        conn.close()


@router.post("/goals")
def create_goal(body: GoalCreate):
    conn = _conn()
    try:
        gid = insert_savings_goal(conn, body.user_id, body.name,
                                  body.target_amount, body.target_date)
        return {"id": gid, "name": body.name,
                "target_amount": body.target_amount, "target_date": body.target_date}
    finally:
        conn.close()


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalProgressUpdate, user_id: int = 1):
    conn = _conn()
    try:
        ok = update_savings_goal_progress(conn, user_id, goal_id, body.current_amount)
        if not ok:
            raise HTTPException(404, "Savings goal not found")
        return {"id": goal_id, "current_amount": body.current_amount}
    finally:
        conn.close()
