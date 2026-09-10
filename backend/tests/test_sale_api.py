from datetime import date, datetime
from decimal import Decimal

from app.models.sale import DocumentStatus, Sale, SaleSource, SaleStatus


def _sale_payload(**overrides) -> dict:
    payload = {
        "customer_name": "Demo Customer",
        "customer_contact": "demo@example.com",
        "service_name": "Consulting session",
        "gross_amount": "100.00",
        "vat_amount": "15.00",
        "processing_fee": "3.00",
        "currency": "ILS",
        "payment_method": "card",
        "occurred_at": datetime.combine(date.today(), datetime.min.time()).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_create_sale_manually_computes_net_amount_and_attempts_document(client, db_session):
    response = client.post("/api/sales", json=_sale_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "manual"
    assert body["status"] == "succeeded"
    assert body["gross_amount"] == "100.00"
    assert body["net_amount"] == "82.00"  # 100 - 15 - 3
    assert body["document_status"] == "issued"
    assert body["document_number"].startswith("DEMO-")

    sale = db_session.get(Sale, body["id"])
    assert sale.source == SaleSource.MANUAL


def test_create_sale_rejects_vat_exceeding_gross_amount(client):
    response = client.post("/api/sales", json=_sale_payload(gross_amount="10.00", vat_amount="20.00"))
    assert response.status_code == 422


def test_create_sale_requires_customer_and_service_name(client):
    response = client.post("/api/sales", json=_sale_payload(customer_name=""))
    assert response.status_code == 422


def test_list_sales_date_to_includes_the_whole_last_day(client):
    """Regression test: Sale.occurred_at is a full timestamp — a date_to
    filter built from a plain <input type="date"> (midnight) must still
    include a sale that happened later that same day."""
    late_today = datetime.combine(date.today(), datetime.min.time()).replace(hour=23, minute=0)
    client.post("/api/sales", json=_sale_payload(occurred_at=late_today.isoformat()))

    response = client.get("/api/sales", params={"date_to": date.today().isoformat()})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_sales_filters_by_search(client):
    client.post("/api/sales", json=_sale_payload(customer_name="Alice"))
    client.post("/api/sales", json=_sale_payload(customer_name="Bob"))

    response = client.get("/api/sales", params={"search": "Alice"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["customer_name"] == "Alice"


def test_get_sale_by_id(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    response = client.get(f"/api/sales/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_unknown_sale_returns_404(client):
    response = client.get("/api/sales/does-not-exist")
    assert response.status_code == 404


def test_update_sale_recomputes_net_amount(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    response = client.put(f"/api/sales/{created['id']}", json={"gross_amount": "200.00"})

    assert response.status_code == 200
    body = response.json()
    assert body["gross_amount"] == "200.00"
    assert body["net_amount"] == "182.00"  # 200 - 15 - 3 (vat/fee unchanged)


def test_delete_sale(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    response = client.delete(f"/api/sales/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/sales/{created['id']}").status_code == 404


def test_full_refund_via_api(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    response = client.post(f"/api/sales/{created['id']}/refund", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "refunded"
    assert body["refunded_amount"] == body["net_amount"]


def test_partial_refund_via_api(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    response = client.post(f"/api/sales/{created['id']}/refund", json={"amount": "10.00"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partially_refunded"
    assert body["refunded_amount"] == "10.00"


def test_refund_exceeding_net_amount_returns_409(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    response = client.post(f"/api/sales/{created['id']}/refund", json={"amount": "9999.00"})

    assert response.status_code == 409


def test_refunding_an_already_fully_refunded_sale_is_idempotent(client):
    created = client.post("/api/sales", json=_sale_payload()).json()
    client.post(f"/api/sales/{created['id']}/refund", json={})

    second = client.post(f"/api/sales/{created['id']}/refund", json={})

    assert second.status_code == 200
    assert second.json()["status"] == "refunded"


def test_pending_sale_never_attempts_document_generation(db_session):
    sale = Sale(
        customer_name="Demo Customer",
        service_name="Consulting",
        gross_amount=Decimal("100.00"),
        net_amount=Decimal("100.00"),
        currency="ILS",
        occurred_at=datetime(2026, 1, 1, 10, 0, 0),
        status=SaleStatus.PENDING,
        document_status=DocumentStatus.NOT_REQUIRED,
        source=SaleSource.MANUAL,
    )
    from app.services.sale_service import finalize_new_sale

    finalized = finalize_new_sale(db_session, sale)
    assert finalized.document_status == DocumentStatus.NOT_REQUIRED
    assert finalized.document_number is None
