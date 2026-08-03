TARGETS = {"calories": 1500, "protein": 155, "fat": 45, "carbs": 117}


def _pct(val, target):
    return f"{int(val/target*100)}%" if target else "—"


def format_today_summary(meals: list, metrics: dict | None) -> str:
    totals = {"calories": 0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for m in meals:
        totals["calories"] += m["calories"] or 0
        totals["protein"] += m["protein"] or 0
        totals["fat"] += m["fat"] or 0
        totals["carbs"] += m["carbs"] or 0
    lines = [
        f"Calories: {totals['calories']}/{TARGETS['calories']} kcal ({_pct(totals['calories'], TARGETS['calories'])})",
        f"Protein:  {totals['protein']:.0f}/{TARGETS['protein']}g",
        f"Fat:      {totals['fat']:.0f}/{TARGETS['fat']}g",
        f"Carbs:    {totals['carbs']:.0f}/{TARGETS['carbs']}g",
    ]
    if meals:
        lines.append(f"\nMeals logged ({len(meals)}):")
        for m in meals:
            lines.append(f"  {m['logged_at'][11:16]} — {m['description']} ({m['calories']} kcal)")
    if metrics:
        lines.append(f"\nSteps: {metrics.get('steps','—')} / 10,000")
        lines.append(f"Deep sleep: {metrics.get('sleep_deep_mins','—')} min / 60 target")
        lines.append(f"Resting HR: {metrics.get('resting_hr','—')} bpm")
    return "\n".join(lines)


def format_meal_confirmation(description: str, calories: int, protein: float) -> str:
    return f"Logged: {description} — {calories} kcal, {protein:.0f}g protein"
