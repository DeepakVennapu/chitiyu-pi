from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import verify_api_key
from db.connection import get_connection
from db.schema import initialize_schema
from config import DB_PATH
from domains.health.db import (get_today_meals, get_meals_for_date, get_metrics_for_date,
                               upsert_health_metrics, insert_recipe, get_all_recipes, delete_meal,
                               log_meal_from_recipe)
from domains.health.formatter import format_today_summary
from datetime import datetime, timezone
from domains.health.db import _today_local

router = APIRouter(prefix="/health", tags=["health"],
                   dependencies=[Depends(verify_api_key)])


def _conn():
    c = get_connection(DB_PATH)
    initialize_schema(c)
    return c


class MealLog(BaseModel):
    user_id: int = 1
    text: str
    context: str = ""


class RecipeCreate(BaseModel):
    user_id: int = 1
    name: str
    calories: int
    protein: float
    fat: float | None = None
    carbs: float | None = None
    serving_unit: str | None = None
    serving_grams: int | None = None
    serving_label: str | None = None


class HealthSync(BaseModel):
    user_id: int = 1
    date: str
    steps: int | None = None
    sleep_deep_mins: int | None = None
    sleep_total_mins: int | None = None
    resting_hr: int | None = None


class MealPreview(BaseModel):
    user_id: int = 1
    text: str
    context: str = ""


class MealFromRecipe(BaseModel):
    user_id: int = 1
    recipe_id: int
    logged_at: str | None = None
    multiplier: float = 1.0


class MealLogParsed(BaseModel):
    user_id: int = 1
    description: str
    calories: int
    protein: float
    fat: float | None = None
    carbs: float | None = None
    logged_at: str | None = None  # ISO 8601 — if omitted, defaults to now


@router.post("/meals")
def log_meal_endpoint(body: MealLog):
    from domains.health.tools import log_meal
    conn = _conn()
    result = log_meal(conn, body.user_id, body.text, body.context)
    conn.close()
    return {"result": result}


@router.get("/meals/today")
def meals_today(user_id: int = 1):
    conn = _conn()
    meals = [dict(m) for m in get_today_meals(conn, user_id)]
    today = _today_local()
    metrics = get_metrics_for_date(conn, user_id, today)
    conn.close()
    return {"meals": meals, "metrics": metrics,
            "summary": format_today_summary([dict(m) for m in (meals or [])], metrics)}


@router.post("/meals/preview")
def preview_meal(body: MealPreview):
    from domains.health.tools import parse_meal_macros
    conn = _conn()
    try:
        data = parse_meal_macros(body.text, body.context, conn=conn)
    finally:
        conn.close()
    if data is None:
        raise HTTPException(422, "Couldn't parse that meal. Try: '2 eggs, toast, coffee'.")
    return data


@router.post("/meals/from-recipe")
def log_from_recipe(body: MealFromRecipe):
    conn = _conn()
    try:
        recipe = log_meal_from_recipe(conn, body.user_id, body.recipe_id,
                                      body.logged_at, body.multiplier)
    finally:
        conn.close()
    if recipe is None:
        raise HTTPException(404, "Recipe not found")
    try:
        from orchestrator.insights import trigger_insights_async
        trigger_insights_async(body.user_id, scope="today")
    except Exception:
        pass
    return {"result": f"Logged {recipe['name']} — {recipe['calories']} kcal"}


@router.post("/meals/log-parsed")
def log_meal_parsed(body: MealLogParsed):
    from domains.health.db import insert_meal
    from domains.health.formatter import format_meal_confirmation
    conn = _conn()
    insert_meal(conn, body.user_id, body.description, body.calories,
                body.protein, body.fat, body.carbs, logged_at=body.logged_at)
    conn.close()
    try:
        from orchestrator.insights import trigger_insights_async
        trigger_insights_async(body.user_id, scope="today")
    except Exception:
        pass
    return {"result": format_meal_confirmation(body.description, body.calories, body.protein)}


@router.get("/meals/{date}")
def meals_for_date(date: str, user_id: int = 1):
    conn = _conn()
    meals = [dict(m) for m in get_meals_for_date(conn, user_id, date)]
    conn.close()
    return meals


@router.post("/sync")
def health_sync(body: HealthSync):
    conn = _conn()
    upsert_health_metrics(conn, body.user_id, body.date, body.steps,
                          body.sleep_deep_mins, body.sleep_total_mins, body.resting_hr)
    conn.close()
    return {"ok": True, "date": body.date}


@router.get("/metrics/today")
def metrics_today(user_id: int = 1):
    today = _today_local()
    conn = _conn()
    m = get_metrics_for_date(conn, user_id, today)
    conn.close()
    return m or {}


@router.get("/metrics/{date}")
def metrics_for_date(date: str, user_id: int = 1):
    conn = _conn()
    m = get_metrics_for_date(conn, user_id, date)
    conn.close()
    return m or {}


@router.get("/recipes")
def list_recipes(user_id: int = 1):
    conn = _conn()
    recipes = [dict(r) for r in get_all_recipes(conn, user_id)]
    conn.close()
    return recipes


@router.post("/recipes")
def create_recipe(body: RecipeCreate):
    conn = _conn()
    recipe_id = insert_recipe(conn, body.user_id, body.name, body.calories,
                              body.protein, body.fat, body.carbs, body.serving_unit,
                              body.serving_grams, body.serving_label)
    conn.close()
    return {"id": recipe_id, "name": body.name}


@router.delete("/meals/{meal_id}")
def delete_meal_endpoint(meal_id: int, user_id: int = 1):
    conn = _conn()
    ok = delete_meal(conn, user_id, meal_id)
    conn.close()
    if not ok:
        raise HTTPException(404, "Meal not found")
    return {"ok": True}


@router.get("/summary/{date}")
def summary(date: str, user_id: int = 1):
    conn = _conn()
    meals = [dict(m) for m in get_meals_for_date(conn, user_id, date)]
    metrics = get_metrics_for_date(conn, user_id, date)
    conn.close()
    return {"date": date, "meals": meals, "metrics": metrics,
            "summary": format_today_summary(meals, metrics)}


@router.get("/insights-context")
def health_insights_context(user_id: int = 1, days: int = 7):
    """Aggregated health trends for the insights engine."""
    from datetime import date, timedelta
    conn = _conn()
    try:
        today = date.today()
        dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

        daily = []
        for d in dates:
            meals = [dict(m) for m in get_meals_for_date(conn, user_id, d)]
            metrics = get_metrics_for_date(conn, user_id, d)
            kcal = sum(m["calories"] for m in meals)
            protein = sum(m["protein"] for m in meals)
            daily.append({
                "date": d,
                "meals_logged": len(meals),
                "kcal": kcal,
                "protein": round(protein, 1),
                "steps": metrics["steps"] if metrics else None,
                "sleep_total_mins": metrics["sleep_total_mins"] if metrics else None,
                "sleep_deep_mins": metrics["sleep_deep_mins"] if metrics else None,
                "resting_hr": metrics["resting_hr"] if metrics else None,
            })

        days_with_meals = [d for d in daily if d["meals_logged"] > 0]
        days_with_metrics = [d for d in daily if d["steps"] is not None]

        def avg(vals):
            v = [x for x in vals if x is not None]
            return round(sum(v) / len(v), 1) if v else None

        targets = {
            "kcal": 1500,
            "protein_g": 150,
            "steps": 10000,
            "sleep_deep_mins": 60,
        }

        hit_kcal = sum(1 for d in days_with_meals if 0 < d["kcal"] <= targets["kcal"])
        hit_protein = sum(1 for d in days_with_meals if d["protein"] >= targets["protein_g"])
        hit_steps = sum(1 for d in days_with_metrics if (d["steps"] or 0) >= targets["steps"])
        hit_deep = sum(1 for d in days_with_metrics
                       if (d["sleep_deep_mins"] or 0) >= targets["sleep_deep_mins"])

        return {
            "as_of": today.isoformat(),
            "window_days": days,
            "targets": targets,
            "averages": {
                "kcal": avg([d["kcal"] for d in days_with_meals]),
                "protein_g": avg([d["protein"] for d in days_with_meals]),
                "steps": avg([d["steps"] for d in days_with_metrics]),
                "sleep_total_mins": avg([d["sleep_total_mins"] for d in days_with_metrics]),
                "sleep_deep_mins": avg([d["sleep_deep_mins"] for d in days_with_metrics]),
                "resting_hr": avg([d["resting_hr"] for d in days_with_metrics]),
            },
            "target_hit_rate": {
                "kcal_on_target": f"{hit_kcal}/{len(days_with_meals)} days",
                "protein_on_target": f"{hit_protein}/{len(days_with_meals)} days",
                "steps_on_target": f"{hit_steps}/{len(days_with_metrics)} days",
                "deep_sleep_on_target": f"{hit_deep}/{len(days_with_metrics)} days",
            },
            "daily": daily,
        }
    finally:
        conn.close()
