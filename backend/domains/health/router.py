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
    today = datetime.now(timezone.utc).date().isoformat()
    metrics = get_metrics_for_date(conn, user_id, today)
    conn.close()
    return {"meals": meals, "metrics": metrics,
            "summary": format_today_summary([dict(m) for m in (meals or [])], metrics)}


@router.post("/meals/preview")
def preview_meal(body: MealPreview):
    from domains.health.tools import parse_meal_macros
    data = parse_meal_macros(body.text, body.context)
    if data is None:
        raise HTTPException(422, "Couldn't parse that meal. Try: '2 eggs, toast, coffee'.")
    return data


@router.post("/meals/from-recipe")
def log_from_recipe(body: MealFromRecipe):
    conn = _conn()
    try:
        recipe = log_meal_from_recipe(conn, body.user_id, body.recipe_id)
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
    today = datetime.now(timezone.utc).date().isoformat()
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
                              body.protein, body.fat, body.carbs, body.serving_unit)
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
