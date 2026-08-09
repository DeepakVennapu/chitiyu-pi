# backend/domains/finance/router.py
import json
from typing import Any
from utils.local_time import today_local

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from auth import verify_api_key
from config import DB_PATH
from db.connection import get_connection
from db.schema import initialize_schema
from domains.finance.db import (
    compute_net_worth_from_balances,
    delete_transaction,
    get_account_by_name,
    get_discretionary_total,
    get_latest_balances,
    get_latest_net_worth,
    get_next_milestone,
    insert_account,
    insert_net_worth,
    insert_savings_goal,
    insert_transaction,
    list_accounts,
    list_balance_history,
    list_budgets,
    list_milestone_periods,
    list_milestones,
    list_net_worth_snapshots,
    list_savings_goals,
    list_transactions,
    update_milestone_actual,
    update_savings_goal_progress,
    upsert_account_balance,
    upsert_budget,
    upsert_milestone,
    get_monthly_spend,
    get_budget,
)
from domains.finance.formatter import format_budget_summary

router = APIRouter(prefix="/finance", tags=["finance"],
                   dependencies=[Depends(verify_api_key)])

EXCLUDED_FROM_TOTAL = {"income", "savings"}


def _conn():
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


# ── Pydantic models ────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    user_id: int = 1
    name: str
    type: str
    currency: str = "USD"


class BalanceEntry(BaseModel):
    account_id: int
    balance: float
    note: str | None = None


class BulkBalanceUpdate(BaseModel):
    user_id: int = 1
    date: str | None = None   # ISO YYYY-MM-DD; defaults to today
    balances: list[BalanceEntry]


class MilestoneCreate(BaseModel):
    user_id: int = 1
    period_label: str          # e.g. "2026-H2", "2027-H1"
    target_date: str           # ISO YYYY-MM-DD
    expected_net_worth: float
    actual_net_worth: float | None = None
    note: str | None = None


class MilestoneActualUpdate(BaseModel):
    actual_net_worth: float


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
    budget_type: str = "discretionary"


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


# ── Accounts ──────────────────────────────────────────────────────────────────

@router.get("/accounts")
def get_accounts(user_id: int = 1):
    conn = _conn()
    try:
        return {"accounts": list_accounts(conn, user_id)}
    finally:
        conn.close()


@router.post("/accounts")
def create_account(body: AccountCreate):
    conn = _conn()
    try:
        aid = insert_account(conn, body.user_id, body.name, body.type, body.currency)
        return {"id": aid, "name": body.name, "type": body.type, "currency": body.currency}
    finally:
        conn.close()


# ── Account Balances ──────────────────────────────────────────────────────────

@router.get("/balances/latest")
def get_latest_account_balances(user_id: int = 1):
    conn = _conn()
    try:
        rows = get_latest_balances(conn, user_id)
        net_worth = compute_net_worth_from_balances(conn, user_id)
        return {"balances": rows, "computed_net_worth": net_worth}
    finally:
        conn.close()


@router.get("/balances/history")
def get_balance_history(user_id: int = 1, account_id: int | None = None, limit: int = 60):
    conn = _conn()
    try:
        return {"history": list_balance_history(conn, user_id, account_id, limit)}
    finally:
        conn.close()


@router.post("/balances")
def update_balances(body: BulkBalanceUpdate):
    """Bulk-upsert balances for multiple accounts on a single date."""
    from datetime import date as _date
    conn = _conn()
    try:
        date = body.date or _date.today().isoformat()
        results = []
        for entry in body.balances:
            bid = upsert_account_balance(
                conn, body.user_id, entry.account_id, date, entry.balance, entry.note
            )
            results.append({"id": bid, "account_id": entry.account_id,
                            "date": date, "balance": entry.balance})
        net_worth = compute_net_worth_from_balances(conn, body.user_id)
        # Auto-snapshot net worth so existing net_worth history still works
        if net_worth is not None:
            insert_net_worth(conn, body.user_id, date, {}, {}, net_worth)
        return {"updated": results, "computed_net_worth": net_worth}
    finally:
        conn.close()


# ── Financial Milestones ──────────────────────────────────────────────────────

@router.get("/milestones")
def get_milestones(user_id: int = 1, period_label: str | None = None):
    conn = _conn()
    try:
        periods = list_milestone_periods(conn, user_id)
        milestones = list_milestones(conn, user_id, period_label)
        return {"periods": periods, "milestones": milestones}
    finally:
        conn.close()


@router.post("/milestones")
def create_milestone(body: MilestoneCreate):
    conn = _conn()
    try:
        mid = upsert_milestone(
            conn, body.user_id, body.period_label, body.target_date,
            body.expected_net_worth, body.actual_net_worth, body.note
        )
        return {"id": mid, "period_label": body.period_label,
                "target_date": body.target_date,
                "expected_net_worth": body.expected_net_worth}
    finally:
        conn.close()


@router.patch("/milestones/{target_date}")
def patch_milestone_actual(target_date: str, body: MilestoneActualUpdate, user_id: int = 1):
    conn = _conn()
    try:
        ok = update_milestone_actual(conn, user_id, target_date, body.actual_net_worth)
        if not ok:
            raise HTTPException(404, "Milestone not found")
        return {"target_date": target_date, "actual_net_worth": body.actual_net_worth}
    finally:
        conn.close()


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
                     date_to: str | None = None, category: str | None = None,
                     limit: int = 50):
    conn = _conn()
    try:
        txns = list_transactions(conn, user_id, date_from=date_from,
                                 date_to=date_to, category=category, limit=limit)
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
        disc_spent, disc_budget = get_discretionary_total(conn, user_id, year, month)
        next_ms = get_next_milestone(conn, user_id)

        budget_map: dict[str, dict] = {b["category"]: b for b in budgets}

        by_type: dict[str, list] = {
            "fixed": [], "recurring": [], "discretionary": [], "envelope": []
        }

        all_cats = sorted(set(list(spend.keys()) + list(budget_map.keys())))
        categories = []
        for cat in all_cats:
            spent_val = spend.get(cat, 0.0)
            b = budget_map.get(cat)
            limit = b["amount"] if b else None
            btype = b["budget_type"] if b else "discretionary"
            period = b["period"] if b else "monthly"
            is_excluded = cat.lower() in EXCLUDED_FROM_TOTAL
            entry = {
                "category": cat,
                "spent": round(spent_val, 2),
                "budget": round(limit, 2) if limit is not None else None,
                "budget_type": btype,
                "period": period,
                "over_budget": limit is not None and spent_val > limit and not is_excluded,
                "is_excluded": is_excluded,
            }
            categories.append(entry)
            if btype in by_type and not is_excluded:
                by_type[btype].append(entry)

        total_spent = sum(v for k, v in spend.items() if k.lower() not in EXCLUDED_FROM_TOTAL)
        total_budget = sum(
            b["amount"] for b in budgets
            if b["category"].lower() not in EXCLUDED_FROM_TOTAL
            and b["budget_type"] != "envelope"
            and b["period"] == "monthly"
        ) or None

        return {
            "year": year,
            "month": month,
            "total_spent": round(total_spent, 2),
            "total_budget": round(total_budget, 2) if total_budget else None,
            "discretionary_spent": disc_spent,
            "discretionary_budget": disc_budget,
            "next_milestone": next_ms,
            "categories": categories,
            "by_type": by_type,
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
        body.category = body.category.lower().strip()
        bid = upsert_budget(conn, body.user_id, body.category,
                            body.amount, body.period, body.budget_type)
        return {"id": bid, "category": body.category,
                "amount": body.amount, "period": body.period,
                "budget_type": body.budget_type}
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
        date = body.snapshot_date or today_local()
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
