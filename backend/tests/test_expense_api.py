from datetime import date, timedelta
from decimal import Decimal


def _create_expense(client, **overrides):
    payload = {
        "business_name": "Shufersal",
        "amount": 120.5,
        "expense_date": date.today().isoformat(),
        "category": "groceries",
        "currency": "ILS",
    }
    payload.update(overrides)
    response = client.post("/api/expenses", json=payload)
    return response


def test_create_expense(client):
    response = _create_expense(client)
    assert response.status_code == 201
    body = response.json()
    assert body["business_name"] == "Shufersal"
    assert body["extraction_status"] == "manual"
    assert Decimal(body["amount"]) == Decimal("120.50")
    assert "id" in body
    assert "receipt_image_path" not in body


def test_create_expense_rejects_negative_amount(client):
    response = _create_expense(client, amount=-5)
    assert response.status_code == 422


def test_create_expense_rejects_vat_greater_than_amount(client):
    response = _create_expense(client, amount=10, vat_amount=15)
    assert response.status_code == 422


def test_create_expense_trims_business_name(client):
    response = _create_expense(client, business_name="  Cofix  ")
    assert response.status_code == 201
    assert response.json()["business_name"] == "Cofix"


def test_create_expense_normalizes_currency_case(client):
    response = _create_expense(client, currency="ils")
    assert response.status_code == 201
    assert response.json()["currency"] == "ILS"


def test_create_expense_rejects_blank_business_name(client):
    response = _create_expense(client, business_name="   ")
    assert response.status_code == 422


def test_list_expenses(client):
    _create_expense(client, business_name="Cofix")
    _create_expense(client, business_name="Rami Levy")
    response = client.get("/api/expenses")
    assert response.status_code == 200
    names = {item["business_name"] for item in response.json()}
    assert names == {"Cofix", "Rami Levy"}


def test_list_expenses_filters_by_search(client):
    _create_expense(client, business_name="Cofix")
    _create_expense(client, business_name="Rami Levy")
    response = client.get("/api/expenses", params={"search": "cofix"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["business_name"] == "Cofix"


def test_list_expenses_filters_by_category(client):
    _create_expense(client, category="groceries")
    _create_expense(client, category="dining")
    response = client.get("/api/expenses", params={"category": "dining"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["category"] == "dining"


def test_list_expenses_filters_by_date_range(client):
    today = date.today()
    _create_expense(client, expense_date=today.isoformat())
    _create_expense(client, expense_date=(today - timedelta(days=40)).isoformat())
    response = client.get(
        "/api/expenses",
        params={"date_from": (today - timedelta(days=5)).isoformat(), "date_to": today.isoformat()},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1


def test_get_expense_by_id(client):
    created = _create_expense(client).json()
    response = client.get(f"/api/expenses/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_expense_returns_404(client):
    response = client.get("/api/expenses/does-not-exist")
    assert response.status_code == 404


def test_update_expense(client):
    created = _create_expense(client).json()
    response = client.put(f"/api/expenses/{created['id']}", json={"amount": 999.99})
    assert response.status_code == 200
    assert Decimal(response.json()["amount"]) == Decimal("999.99")


def test_update_expense_rejects_vat_greater_than_amount(client):
    created = _create_expense(client).json()
    response = client.put(f"/api/expenses/{created['id']}", json={"amount": 10, "vat_amount": 20})
    assert response.status_code == 422


def test_update_missing_expense_returns_404(client):
    response = client.put("/api/expenses/does-not-exist", json={"amount": 10})
    assert response.status_code == 404


def test_delete_expense(client):
    created = _create_expense(client).json()
    response = client.delete(f"/api/expenses/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/expenses/{created['id']}").status_code == 404


def test_delete_missing_expense_returns_404(client):
    response = client.delete("/api/expenses/does-not-exist")
    assert response.status_code == 404


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
