"""
Seed the ingredients table with ~150 curated raw foods.
Values are per 100g. Run: python backend/db/seed_ingredients.py
Idempotent — safe to re-run.
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.schema import initialize_schema
from domains.health.db import insert_ingredient
from config import DB_PATH

INGREDIENTS = [
    # (name, kcal/100g, protein, fat, carbs, category)
    # ── Proteins: Meat & Poultry ───────────────────────────────────
    ("Chicken breast cooked", 165, 31.0, 3.6, 0.0, "protein"),
    ("Chicken thigh cooked", 209, 26.0, 10.9, 0.0, "protein"),
    ("Chicken drumstick cooked", 172, 28.3, 5.7, 0.0, "protein"),
    ("Ground beef 80/20 cooked", 254, 26.1, 17.4, 0.0, "protein"),
    ("Ground beef 90/10 cooked", 218, 28.0, 11.5, 0.0, "protein"),
    ("Beef steak cooked", 271, 26.6, 17.7, 0.0, "protein"),
    ("Pork tenderloin cooked", 166, 28.0, 5.0, 0.0, "protein"),
    ("Bacon cooked", 541, 37.0, 42.0, 1.4, "protein"),
    ("Turkey breast cooked", 135, 30.0, 1.0, 0.0, "protein"),
    ("Lamb leg cooked", 218, 28.3, 11.1, 0.0, "protein"),
    # ── Proteins: Fish & Seafood ───────────────────────────────────
    ("Salmon cooked", 208, 20.4, 13.4, 0.0, "protein"),
    ("Tuna canned in water", 109, 25.5, 0.5, 0.0, "protein"),
    ("Shrimp cooked", 99, 24.0, 0.3, 0.0, "protein"),
    ("Tilapia cooked", 128, 26.2, 2.7, 0.0, "protein"),
    ("Cod cooked", 105, 23.0, 0.9, 0.0, "protein"),
    ("Sardines in oil", 208, 24.6, 11.5, 0.0, "protein"),
    # ── Proteins: Eggs & Dairy ────────────────────────────────────
    ("Whole egg", 155, 13.0, 11.0, 1.1, "protein"),
    ("Egg white", 52, 11.0, 0.2, 0.7, "protein"),
    ("Egg yolk", 322, 15.9, 26.5, 3.6, "protein"),
    ("Whole milk", 61, 3.2, 3.3, 4.8, "dairy"),
    ("Skim milk", 34, 3.4, 0.1, 5.0, "dairy"),
    ("Greek yogurt plain", 59, 10.0, 0.4, 3.6, "dairy"),
    ("Full fat yogurt", 61, 3.5, 3.3, 4.7, "dairy"),
    ("Cheddar cheese", 403, 25.0, 33.1, 1.3, "dairy"),
    ("Mozzarella cheese", 280, 28.0, 17.0, 3.1, "dairy"),
    ("Cottage cheese", 98, 11.1, 4.3, 3.4, "dairy"),
    ("Butter", 717, 0.9, 81.1, 0.1, "fat"),
    ("Cream cheese", 342, 6.2, 34.4, 4.1, "dairy"),
    ("Paneer", 265, 18.3, 20.8, 1.2, "dairy"),
    ("Homemade curd", 98, 11.0, 4.5, 3.4, "dairy"),
    # ── Proteins: Legumes ─────────────────────────────────────────
    ("Black beans cooked", 132, 8.9, 0.5, 23.7, "legume"),
    ("Chickpeas cooked", 164, 8.9, 2.6, 27.4, "legume"),
    ("Lentils cooked", 116, 9.0, 0.4, 20.1, "legume"),
    ("Moong dal cooked", 105, 7.0, 0.4, 19.2, "legume"),
    ("Toor dal cooked", 112, 7.3, 0.4, 20.6, "legume"),
    ("Urad dal cooked", 127, 9.0, 0.5, 22.6, "legume"),
    ("Kidney beans cooked", 127, 8.7, 0.5, 22.8, "legume"),
    ("Tofu firm", 76, 8.1, 4.8, 1.9, "protein"),
    ("Edamame", 121, 11.9, 5.2, 8.9, "legume"),
    ("Peanut butter", 588, 25.0, 50.0, 20.0, "fat"),
    ("Hummus", 166, 7.9, 9.6, 14.3, "legume"),
    # ── Grains & Starches ─────────────────────────────────────────
    ("Oats dry", 389, 17.0, 7.0, 66.0, "grain"),
    ("Rolled oats cooked", 71, 2.5, 1.5, 12.0, "grain"),
    ("White rice cooked", 130, 2.7, 0.3, 28.7, "grain"),
    ("Brown rice cooked", 216, 4.5, 1.8, 45.0, "grain"),
    ("White bread", 265, 9.0, 3.2, 49.0, "grain"),
    ("Whole wheat bread", 247, 13.0, 3.4, 41.0, "grain"),
    ("Pasta cooked", 131, 5.0, 1.1, 25.0, "grain"),
    ("Whole wheat pasta cooked", 124, 5.3, 0.5, 26.5, "grain"),
    ("Quinoa cooked", 120, 4.4, 1.9, 21.3, "grain"),
    ("Corn tortilla", 218, 5.7, 2.5, 46.0, "grain"),
    ("Flour tortilla", 312, 8.0, 8.0, 51.0, "grain"),
    ("All purpose flour", 364, 10.3, 1.0, 76.3, "grain"),
    ("Whole wheat flour", 340, 13.7, 2.5, 72.0, "grain"),
    ("Cornmeal", 362, 8.1, 3.6, 76.9, "grain"),
    ("Roti whole wheat", 297, 8.5, 1.5, 63.0, "grain"),
    ("Chapati", 297, 8.5, 1.5, 63.0, "grain"),
    ("Naan", 310, 9.0, 7.0, 53.0, "grain"),
    ("Poha", 333, 6.4, 0.3, 76.9, "grain"),
    ("Upma", 109, 2.8, 3.0, 17.8, "grain"),
    ("Idli", 58, 2.0, 0.4, 11.5, "grain"),
    ("Dosa", 168, 3.4, 5.1, 27.5, "grain"),
    ("Basmati rice cooked", 121, 3.5, 0.4, 25.2, "grain"),
    # ── Vegetables ────────────────────────────────────────────────
    ("Broccoli raw", 34, 2.8, 0.4, 6.6, "vegetable"),
    ("Spinach raw", 23, 2.9, 0.4, 3.6, "vegetable"),
    ("Kale raw", 49, 4.3, 0.9, 8.8, "vegetable"),
    ("Carrot raw", 41, 0.9, 0.2, 9.6, "vegetable"),
    ("Bell pepper raw", 31, 1.0, 0.3, 6.0, "vegetable"),
    ("Onion raw", 40, 1.1, 0.1, 9.3, "vegetable"),
    ("Tomato raw", 18, 0.9, 0.2, 3.9, "vegetable"),
    ("Cucumber raw", 15, 0.7, 0.1, 3.6, "vegetable"),
    ("Zucchini raw", 17, 1.2, 0.3, 3.1, "vegetable"),
    ("Sweet potato cooked", 90, 2.0, 0.1, 20.7, "vegetable"),
    ("White potato cooked", 87, 1.9, 0.1, 20.1, "vegetable"),
    ("Cauliflower raw", 25, 1.9, 0.3, 5.0, "vegetable"),
    ("Green beans raw", 31, 1.8, 0.2, 7.1, "vegetable"),
    ("Peas cooked", 84, 5.4, 0.4, 15.6, "vegetable"),
    ("Corn cooked", 96, 3.4, 1.5, 21.0, "vegetable"),
    ("Asparagus raw", 20, 2.2, 0.1, 3.9, "vegetable"),
    ("Mushroom raw", 22, 3.1, 0.3, 3.3, "vegetable"),
    ("Eggplant raw", 25, 1.0, 0.2, 5.9, "vegetable"),
    ("Lettuce romaine raw", 17, 1.2, 0.3, 3.3, "vegetable"),
    ("Celery raw", 16, 0.7, 0.2, 3.0, "vegetable"),
    ("Cabbage raw", 25, 1.3, 0.1, 5.8, "vegetable"),
    ("Beets cooked", 44, 1.7, 0.2, 10.0, "vegetable"),
    ("Okra raw", 33, 1.9, 0.2, 7.5, "vegetable"),
    ("Bitter gourd", 17, 1.0, 0.2, 3.7, "vegetable"),
    # ── Fruits ────────────────────────────────────────────────────
    ("Banana", 89, 1.1, 0.3, 23.0, "fruit"),
    ("Apple", 52, 0.3, 0.2, 14.0, "fruit"),
    ("Orange", 47, 0.9, 0.1, 11.8, "fruit"),
    ("Strawberry", 32, 0.7, 0.3, 7.7, "fruit"),
    ("Blueberry", 57, 0.7, 0.3, 14.5, "fruit"),
    ("Mango", 60, 0.8, 0.4, 15.0, "fruit"),
    ("Grapes", 69, 0.7, 0.2, 18.1, "fruit"),
    ("Watermelon", 30, 0.6, 0.2, 7.6, "fruit"),
    ("Pineapple", 50, 0.5, 0.1, 13.1, "fruit"),
    ("Avocado", 160, 2.0, 14.7, 8.5, "fruit"),
    ("Coconut fresh", 354, 3.3, 33.5, 15.2, "fruit"),
    ("Papaya", 43, 0.5, 0.3, 11.0, "fruit"),
    ("Pomegranate", 83, 1.7, 1.2, 18.7, "fruit"),
    ("Guava", 68, 2.6, 1.0, 14.3, "fruit"),
    ("Dates", 282, 2.5, 0.4, 75.0, "fruit"),
    # ── Nuts & Seeds ──────────────────────────────────────────────
    ("Almonds", 579, 21.2, 49.9, 21.6, "fat"),
    ("Walnuts", 654, 15.2, 65.2, 13.7, "fat"),
    ("Cashews", 553, 18.2, 43.9, 30.2, "fat"),
    ("Pistachios", 562, 20.2, 45.3, 27.2, "fat"),
    ("Peanuts", 567, 25.8, 49.2, 16.1, "protein"),
    ("Sunflower seeds", 584, 20.8, 51.5, 20.0, "fat"),
    ("Pumpkin seeds", 559, 30.2, 49.1, 10.7, "fat"),
    ("Flaxseeds", 534, 18.3, 42.2, 28.9, "fat"),
    ("Chia seeds", 486, 16.5, 30.7, 42.1, "fat"),
    ("Sesame seeds", 573, 17.7, 49.7, 23.5, "fat"),
    ("Coconut milk", 197, 2.3, 21.3, 2.8, "fat"),
    ("Kaju (cashew nuts)", 553, 18.2, 43.9, 30.2, "fat"),
    # ── Oils & Fats ───────────────────────────────────────────────
    ("Olive oil", 884, 0.0, 100.0, 0.0, "fat"),
    ("Coconut oil", 862, 0.0, 100.0, 0.0, "fat"),
    ("Vegetable oil", 884, 0.0, 100.0, 0.0, "fat"),
    ("Ghee", 900, 0.0, 99.5, 0.0, "fat"),
    ("Mustard oil", 884, 0.0, 100.0, 0.0, "fat"),
    # ── Condiments & Sauces ───────────────────────────────────────
    ("Ketchup", 112, 1.4, 0.1, 26.0, "condiment"),
    ("Mayonnaise", 680, 0.9, 74.9, 0.6, "condiment"),
    ("Mustard yellow", 66, 4.4, 4.0, 5.8, "condiment"),
    ("Soy sauce", 53, 5.6, 0.1, 4.9, "condiment"),
    ("Hot sauce", 11, 0.5, 0.3, 1.8, "condiment"),
    ("Honey", 304, 0.3, 0.0, 82.4, "condiment"),
    ("Maple syrup", 260, 0.0, 0.1, 67.0, "condiment"),
    ("Sugar white", 387, 0.0, 0.0, 100.0, "condiment"),
    ("Sugar brown", 380, 0.1, 0.0, 98.1, "condiment"),
    ("Salt", 0, 0.0, 0.0, 0.0, "condiment"),
    ("Tomato sauce", 29, 1.5, 0.4, 6.1, "condiment"),
    ("Chutney mint", 60, 2.0, 1.0, 10.0, "condiment"),
    ("Sambar", 55, 2.8, 1.0, 8.5, "condiment"),
    # ── Beverages ─────────────────────────────────────────────────
    ("Whole milk 1 cup", 149, 8.0, 8.0, 11.7, "beverage"),
    ("Orange juice", 45, 0.7, 0.2, 10.4, "beverage"),
    ("Coffee black", 2, 0.3, 0.0, 0.0, "beverage"),
    ("Coffee with milk and sugar", 27, 0.8, 0.8, 3.6, "beverage"),
    ("Filter coffee", 37, 1.5, 1.5, 4.5, "beverage"),
    ("Green tea", 1, 0.0, 0.0, 0.0, "beverage"),
    ("Protein shake whey", 400, 80.0, 7.0, 10.0, "protein"),
    # ── Snacks & Common Indian Foods ──────────────────────────────
    ("Samosa fried", 262, 5.0, 14.5, 29.0, "snack"),
    ("Pakora", 250, 7.0, 13.0, 28.0, "snack"),
    ("Khichdi", 130, 5.0, 3.5, 21.0, "grain"),
    ("Biryani chicken", 200, 12.0, 8.0, 21.0, "grain"),
    ("Dal tadka", 120, 7.0, 4.0, 15.0, "legume"),
    ("Dal fry", 135, 7.5, 5.5, 15.5, "legume"),
    ("Palak paneer", 180, 8.0, 12.0, 8.0, "protein"),
    ("Butter chicken", 170, 15.0, 10.0, 5.0, "protein"),
    ("Rajma cooked", 143, 8.7, 0.7, 26.0, "legume"),
    ("Chole masala", 164, 8.9, 2.6, 27.4, "legume"),
    ("Raita", 62, 3.5, 2.5, 6.0, "dairy"),
    ("Pickle mango", 88, 1.0, 6.0, 9.0, "condiment"),
    ("Papad roasted", 357, 23.0, 1.0, 60.0, "snack"),
    ("Dhokla", 160, 5.0, 3.0, 29.0, "snack"),
    ("Poha cooked", 110, 2.5, 2.5, 20.0, "grain"),
    ("Upma cooked", 109, 2.8, 3.0, 17.8, "grain"),
    ("Pongal", 130, 4.0, 4.5, 19.5, "grain"),
    ("Halwa sooji", 280, 4.5, 12.0, 39.0, "snack"),
    ("Ladoo besan", 450, 8.0, 22.0, 57.0, "snack"),
    ("Kaju katli", 480, 9.0, 24.0, 61.0, "snack"),
    ("Trail mix", 462, 13.0, 30.0, 43.0, "snack"),
    ("Granola bar", 471, 9.2, 21.2, 64.0, "snack"),
    ("Dark chocolate 70%", 598, 7.8, 42.6, 45.9, "snack"),
    ("Milk chocolate", 535, 7.7, 29.7, 59.4, "snack"),
    ("Chips potato", 536, 7.0, 35.0, 53.0, "snack"),
    ("Popcorn plain", 375, 11.0, 4.3, 74.0, "snack"),
    ("Rice cakes plain", 387, 8.2, 3.5, 81.5, "snack"),
]


def seed(db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    initialize_schema(conn)
    count = 0
    for row in INGREDIENTS:
        name, kcal, pro, fat, carbs, cat = row
        insert_ingredient(conn, name, kcal, pro, fat, carbs, cat)
        count += 1
    conn.close()
    return count


if __name__ == "__main__":
    n = seed()
    print(f"Seeded {n} ingredients into {DB_PATH}")
