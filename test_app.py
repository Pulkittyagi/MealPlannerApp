import pytest
from app import app

# -------------------------------
# Test Case 1: Sufficient Inventory
# -------------------------------
def test_sufficient_inventory(monkeypatch):
    def dummy_generate_monthly_plan(month):
        return {
            "senior_box_items_for_month": ["itemA", "itemB"],
            "daily_usage": [{"day": i, "usage": 10} for i in range(1, 31)]
        }
    monkeypatch.setattr("app.generate_monthly_plan", dummy_generate_monthly_plan)
    
    client = app.test_client()
    response = client.post("/api/generate_monthly_plan", json={"month": 4})
    data = response.get_json()

    assert response.status_code == 200
    assert "senior_box_items_for_month" in data
    assert len(data["daily_usage"]) == 30
    for day in data["daily_usage"]:
        assert day["usage"] == 10

# -------------------------------
# Test Case 2: Shortage in Main Inventory
# -------------------------------
def test_shortage_in_main_inventory(monkeypatch):
    def dummy_generate_monthly_plan(month):
        return {
            "senior_box_items_for_month": ["itemA", "itemB"],
            "daily_usage": [
                {"day": i, "usage": 10 if i % 5 != 0 else 5}
                for i in range(1, 31)
            ]
        }
    monkeypatch.setattr("app.generate_monthly_plan", dummy_generate_monthly_plan)
    
    client = app.test_client()
    response = client.post("/api/generate_monthly_plan", json={"month": 4})
    data = response.get_json()

    assert response.status_code == 200
    shortage_days = [d for d in data["daily_usage"] if d["usage"] < 10]
    assert len(shortage_days) > 0
    for day in shortage_days:
        assert day["usage"] == 5

# -------------------------------
# Test Case 3: Shortage in Both Inventories
# -------------------------------
def test_shortage_in_both_inventories(monkeypatch):
    def dummy_generate_monthly_plan(month):
        return {
            "senior_box_items_for_month": [],  # Senior box is empty
            "daily_usage": [
                {"day": i, "usage": 0 if i % 7 == 0 else 10}
                for i in range(1, 31)
            ]
        }
    monkeypatch.setattr("app.generate_monthly_plan", dummy_generate_monthly_plan)
    
    client = app.test_client()
    response = client.post("/api/generate_monthly_plan", json={"month": 4})
    data = response.get_json()

    assert response.status_code == 200
    assert data["senior_box_items_for_month"] == []
    no_usage_days = [d for d in data["daily_usage"] if d["usage"] == 0]
    assert len(no_usage_days) > 0

# -------------------------------
# Test Case 4: Invalid Month Value
# -------------------------------
def test_invalid_month(monkeypatch):
    def dummy_generate_monthly_plan(month):
        if month < 1 or month > 12:
            raise ValueError("Invalid month number")
        return {"senior_box_items_for_month": [], "daily_usage": []}
    monkeypatch.setattr("app.generate_monthly_plan", dummy_generate_monthly_plan)
    
    client = app.test_client()
    response = client.post("/api/generate_monthly_plan", json={"month": 13})
    data = response.get_json()

    assert response.status_code == 500
    assert "Invalid month number" in data["error"]

# -------------------------------
# Test Case 5: Missing "month" Key in JSON
# -------------------------------
def test_missing_month_key(monkeypatch):
    def dummy_generate_monthly_plan(month):
        return {
            "senior_box_items_for_month": ["default_item"],
            "daily_usage": [{"day": i, "usage": 10} for i in range(1, 31)]
        }
    monkeypatch.setattr("app.generate_monthly_plan", dummy_generate_monthly_plan)
    
    client = app.test_client()
    response = client.post("/api/generate_monthly_plan", json={})
    data = response.get_json()

    assert response.status_code == 200
    assert data["senior_box_items_for_month"] == ["default_item"]
    assert len(data["daily_usage"]) == 30