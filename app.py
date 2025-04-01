import pandas as pd
from flask import Flask, request, jsonify

app = Flask(__name__)

###############################################################################
# 1) Category Mapping
###############################################################################
# This maps raw category strings (e.g. "milk & dairy") to our standard keys.
CATEGORY_MAP = {
    "seasonal & local fruits/vegetables": "fruit_veg",
    "milk & dairy": "dairy",
    "meat/fish/eggs/pulses": "protein",
    "grains": "cereal",
    "oil": "oil"
    # anything else => skip
}

###############################################################################
# 2) The 5-4-3-2-1 Meal Requirements
###############################################################################
MEALS = {
    "BreakfastPlan": {
        "fruit_veg": 1,
        "cereal": 1,
        "dairy": 1,
        "protein": 0,
        "oil": 0
    },
    "LunchPlan": {
        "fruit_veg": 2,
        "cereal": 1,
        "dairy": 0,
        "protein": 1,
        "oil": 1
    },
    "DinnerPlan": {
        "fruit_veg": 2,
        "cereal": 2,
        "dairy": 1,
        "protein": 0,
        "oil": 2
    }
}

MEAL_ORDER = ["BreakfastPlan", "LunchPlan", "DinnerPlan"]

###############################################################################
# 3) Load Food Reference from "DATA SET FOOD CATEGORY.xlsx"
###############################################################################
def load_food_reference():
    """
    Reads 'data/DATA SET FOOD CATEGORY.xlsx'.
    Must have columns:
      item_name, item_category, servings_per_unit
    Returns a dict:
      ref_map[item_name_lower] = {
         "raw_category": ...,
         "servings_per_unit": ...
      }
    """
    path = "data/DATA SET FOOD CATEGORY.xlsx"
    try:
        df = pd.read_excel(path)
    except FileNotFoundError:
        raise Exception(f"Cannot find '{path}'.")
    except ValueError:
        raise Exception(f"Error reading '{path}'—check sheet name, columns, etc.")

    needed_cols = ["item_name","item_category","servings_per_unit"]
    for c in needed_cols:
        if c not in df.columns:
            raise Exception(f"Column '{c}' missing in '{path}'.")

    df["servings_per_unit"] = pd.to_numeric(df["servings_per_unit"], errors="coerce").fillna(1)

    ref_map = {}
    for _, row in df.iterrows():
        name = str(row["item_name"]).strip().lower()
        raw_cat = str(row["item_category"]).strip().lower()
        su = float(row["servings_per_unit"])
        ref_map[name] = {
            "raw_category": raw_cat,
            "servings_per_unit": su
        }
    return ref_map

###############################################################################
# 4) Senior Box
###############################################################################
def get_cycle_month(month: int) -> int:
    return ((month - 1) % 3) + 1

def load_senior_box_data_and_list(cycle_month=1, ref_map=None):
    """
    Reads the relevant sheet from 'data/senior_box.xlsx'.
    Expects columns:
      item_name, quantity
    Then uses ref_map (from DATA SET FOOD CATEGORY.xlsx) to find category & su.
    'servings_available' = quantity * su
    Returns:
      box_original: raw data records
      box_item_list: processed list => { item_name, category, servings_available }
    """
    if cycle_month == 1:
        sheet_name = "Senior Box First Month"
    elif cycle_month == 2:
        sheet_name = "Senior Box Second Month"
    else:
        sheet_name = "Senior Box Third Month"

    path = "data/senior_box.xlsx"
    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except FileNotFoundError:
        raise Exception(f"Cannot find '{path}'.")
    except ValueError:
        raise Exception(f"Worksheet '{sheet_name}' not found in '{path}'.")

    box_original = df.to_dict(orient="records")

    if "item_name" not in df.columns or "quantity" not in df.columns:
        raise Exception(f"'item_name' or 'quantity' missing in sheet '{sheet_name}' of '{path}'.")

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

    box_list = []
    for _, row in df.iterrows():
        item_n = str(row["item_name"]).strip().lower()
        qty = float(row["quantity"])

        # lookup in reference
        if item_n not in ref_map:
            print(f"Skipping senior box item '{row['item_name']}' (not found in reference).")
            continue

        raw_cat = ref_map[item_n]["raw_category"]
        su = ref_map[item_n]["servings_per_unit"]
        mapped_cat = CATEGORY_MAP.get(raw_cat, None)
        if mapped_cat is None:
            print(f"Skipping box item '{row['item_name']}', raw cat '{raw_cat}' not recognized.")
            continue

        total_serv = qty * su
        box_list.append({
            "item_name": row["item_name"],
            "category": mapped_cat,
            "servings_available": total_serv
        })

    return box_original, box_list

###############################################################################
# 5) Main Inventory
###############################################################################
def load_main_inventory_items(ref_map=None):
    """
    'data/excel_file.xlsx' => sheet "Inventory" must have columns:
      item_name, quantity_in_stock
    We'll look up item_category & servings_per_unit in ref_map.
    Then total_serv = quantity_in_stock * su.
    """
    path = "data/excel_file.xlsx"
    sheet_name = "Inventory"
    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except FileNotFoundError:
        raise Exception(f"Cannot find '{path}'.")
    except ValueError:
        raise Exception(f"Worksheet '{sheet_name}' not found in '{path}'.")

    needed_cols = ["item_name","quantity_in_stock"]
    for c in needed_cols:
        if c not in df.columns:
            raise Exception(f"Column '{c}' missing in '{sheet_name}' of '{path}'.")

    df["quantity_in_stock"] = pd.to_numeric(df["quantity_in_stock"], errors="coerce").fillna(0)

    main_list = []
    for _, row in df.iterrows():
        item_n = str(row["item_name"]).strip().lower()
        qty_in_stock = float(row["quantity_in_stock"])

        # lookup item_name in reference
        if item_n not in ref_map:
            print(f"Skipping main item '{row['item_name']}' (not found in reference).")
            continue

        raw_cat = ref_map[item_n]["raw_category"]
        su = ref_map[item_n]["servings_per_unit"]
        mapped_cat = CATEGORY_MAP.get(raw_cat, None)
        if mapped_cat is None:
            print(f"Skipping main item '{row['item_name']}', raw cat '{raw_cat}' not recognized.")
            continue

        total_serv = qty_in_stock * su
        main_list.append({
            "item_name": row["item_name"],
            "category": mapped_cat,
            "servings_available": total_serv
        })
    return main_list

###############################################################################
# 6) Allocation Logic
###############################################################################
def allocate_category(box_list, main_list, category, needed):
    used_details = []
    needed_left = needed

    # Box first
    for item in box_list:
        if item["category"] == category and needed_left > 0:
            if item["servings_available"] >= needed_left:
                used_details.append({
                    "item_name": item["item_name"],
                    "category": category,
                    "servings_used": needed_left,
                    "from": "box"
                })
                item["servings_available"] -= needed_left
                needed_left = 0
                break
            else:
                if item["servings_available"] > 0:
                    used_details.append({
                        "item_name": item["item_name"],
                        "category": category,
                        "servings_used": item["servings_available"],
                        "from": "box"
                    })
                    needed_left -= item["servings_available"]
                    item["servings_available"] = 0

    # Then main
    if needed_left > 0:
        for item in main_list:
            if item["category"] == category and needed_left > 0:
                if item["servings_available"] >= needed_left:
                    used_details.append({
                        "item_name": item["item_name"],
                        "category": category,
                        "servings_used": needed_left,
                        "from": "main"
                    })
                    item["servings_available"] -= needed_left
                    needed_left = 0
                    break
                else:
                    if item["servings_available"] > 0:
                        used_details.append({
                            "item_name": item["item_name"],
                            "category": category,
                            "servings_used": item["servings_available"],
                            "from": "main"
                        })
                        needed_left -= item["servings_available"]
                        item["servings_available"] = 0

    shortage_flag = (needed_left > 0)
    return used_details, needed_left, shortage_flag

def allocate_meal(box_list, main_list, meal_plan):
    used_items = []
    shortage_any = False
    for cat, needed in meal_plan.items():
        if needed <= 0:
            continue
        cat_used, leftover, short = allocate_category(box_list, main_list, cat, needed)
        used_items.extend(cat_used)
        if short:
            shortage_any = True
    return used_items, shortage_any

###############################################################################
# 7) Summaries
###############################################################################
def summarize_day_usage(day_meals):
    from collections import defaultdict

    box_usage_map = defaultdict(float)
    main_usage_map = defaultdict(float)

    for meal in day_meals:
        for used in meal["used_items"]:
            key = (used["item_name"], used["category"])
            if used["from"] == "box":
                box_usage_map[key] += used["servings_used"]
            else:
                main_usage_map[key] += used["servings_used"]

    def map_to_list(usage_map):
        arr = []
        for (item_n, cat), total_used in usage_map.items():
            arr.append({
                "item_name": item_n,
                "category": cat,
                "servings_used": total_used
            })
        return arr

    day_box_usage = map_to_list(box_usage_map)
    day_main_usage = map_to_list(main_usage_map)
    return day_box_usage, day_main_usage

###############################################################################
# 8) Generate Plan
###############################################################################
def generate_monthly_plan(month=1):
    import copy

    # 1) Load reference
    ref_map = load_food_reference()

    # 2) Decide cycle
    cyc = get_cycle_month(month)

    # 3) Load box
    box_original, box_list = load_senior_box_data_and_list(cyc, ref_map)

    # 4) Load main
    main_list = load_main_inventory_items(ref_map)

    day_plans = []
    day_shortages = []

    for day_num in range(1, 31):
        backup_box = copy.deepcopy(box_list)
        backup_main = copy.deepcopy(main_list)

        day_meals = []
        shortage_for_day = False

        for meal_key in MEAL_ORDER:
            meal_req = MEALS[meal_key]
            used_items, shortage_any = allocate_meal(box_list, main_list, meal_req)
            day_meals.append({
                "meal_time": meal_key.replace("Plan",""),
                "meal_plan_requirements": meal_req,
                "used_items": used_items
            })
            if shortage_any:
                shortage_for_day = True
                break

        if shortage_for_day:
            box_list = backup_box
            main_list = backup_main
            day_shortages.append({
                "day_number": day_num,
                "shortages": [
                    "Not enough box+main inventory to fulfill 5-4-3-2-1 plan"
                ]
            })
            day_meals = []
        else:
            day_box_usage, day_main_usage = summarize_day_usage(day_meals)

        day_info = {
            "day_number": day_num,
            "meals": day_meals
        }
        if not shortage_for_day:
            day_info["day_box_usage"] = day_box_usage
            day_info["day_main_usage"] = day_main_usage

        day_plans.append(day_info)

    all_shortages = []
    if day_shortages:
        all_shortages.append({
            "type": "meal_plan_shortage",
            "details": day_shortages
        })

    return {
        "month_requested": month,
        "cycle_month": cyc,
        "senior_box_items_for_month": box_original,
        "final_daily_plan": day_plans,
        "all_shortages": all_shortages
    }


###############################################################################
# 9) Flask Routes
###############################################################################
app = Flask(__name__)

@app.route("/api/generate_monthly_plan", methods=["POST"])
def generate_monthly_plan_endpoint():
    data = request.get_json()
    month_num = data.get("month", 1)
    try:
        plan_result = generate_monthly_plan(month_num)
        return jsonify(plan_result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "Server running. Use POST /api/generate_monthly_plan with {'month':4}."

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)