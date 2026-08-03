# backend/domains/finance/formatter.py

def format_transaction_log(description: str, amount: float, category: str, date: str) -> str:
    sign = "-" if amount < 0 else "+"
    return f"Logged: {description} — {sign}${abs(amount):.2f} ({category}) on {date}"


def format_budget_summary(spend: dict[str, float], budgets: list, year: int, month: int) -> str:
    import calendar
    month_name = calendar.month_name[month]
    budget_map = {b["category"]: b["amount"] for b in budgets}
    all_categories = sorted(set(list(spend.keys()) + list(budget_map.keys())))

    if not all_categories:
        return f"{month_name} {year}: No transactions or budgets recorded."

    lines = [f"{month_name} {year} — Spending vs Budget:"]
    for cat in all_categories:
        spent = spend.get(cat, 0.0)
        limit = budget_map.get(cat)
        if limit is not None:
            pct = int(spent / limit * 100)
            over = " ⚠️ OVER" if spent > limit else ""
            lines.append(f"  {cat}: ${spent:.0f} / ${limit:.0f} ({pct}%){over}")
        else:
            lines.append(f"  {cat}: ${spent:.0f} (no budget set)")

    total_spent = sum(spend.values())
    total_budgeted = sum(budget_map.values())
    lines.append(f"\nTotal: ${total_spent:.0f} spent / ${total_budgeted:.0f} budgeted")
    return "\n".join(lines)


def format_net_worth(snapshot: dict | None) -> str:
    if snapshot is None:
        return "No net worth snapshots recorded yet. Use 'record net worth' to add one."
    assets = snapshot.get("assets_json", {})
    liabilities = snapshot.get("liabilities_json", {})
    total = snapshot.get("total", 0.0)
    date = snapshot.get("snapshot_date", "unknown date")
    lines = [f"Net Worth as of {date}: ${total:,.0f}"]
    if assets:
        lines.append("  Assets:")
        for k, v in assets.items():
            lines.append(f"    {k}: ${v:,.0f}")
    if liabilities:
        lines.append("  Liabilities:")
        for k, v in liabilities.items():
            lines.append(f"    {k}: ${v:,.0f}")
    lines.append("Note: Investment values are manual snapshots. Live sync is Phase 2.")
    return "\n".join(lines)


def format_goals(goals: list) -> str:
    if not goals:
        return "No savings goals set. Use 'add a savings goal' to create one."
    lines = ["Savings Goals:"]
    for g in goals:
        pct = int(g["current_amount"] / g["target_amount"] * 100) if g["target_amount"] else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        due = f" (by {g['target_date']})" if g.get("target_date") else ""
        lines.append(
            f"  {g['name']}: ${g['current_amount']:,.0f} / ${g['target_amount']:,.0f} "
            f"[{bar}] {pct}%{due}"
        )
    return "\n".join(lines)
