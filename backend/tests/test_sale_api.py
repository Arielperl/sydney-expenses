from datetime import date, datetime
from decimal import Decimal

from app.models.sale import DocumentStatus, Sale, SaleSource, SaleStatus


def _sale_payload(**overrides) -> dict:
    payload = {
        "customer_name": "Demo Customer",
        "customer_contact": "demo@example.com",
        "service_name": "Consulting session",
        "gross_amount": "100.00",
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
    # tax_treatment defaults to "standard": vat = 100 * 18/118 = 15.25 (rounded),
    # net = 100 - 15.25 - 3 (processing fee).
    assert body["tax_treatment"] == "standard"
    assert body["vat_amount"] == "15.25"
    assert body["net_amount"] == "81.75"
    assert body["document_status"] == "issued"
    assert body["document_number"].startswith("DEMO-")

    sale = db_session.get(Sale, body["id"])
    assert sale.source == SaleSource.MANUAL


def test_create_sale_vat_is_backend_computed_never_client_supplied(client):
    """`vat_amount` isn't accepted as a create-request field at all — sending
    one is simply ignored, never trusted, because the backend is the sole
    source of truth for the calculation."""
    payload = _sale_payload(gross_amount="118.00")
    payload["vat_amount"] = "999.00"  # not a real field on SaleCreate

    response = client.post("/api/sales", json=payload)

    assert response.status_code == 201
    assert response.json()["vat_amount"] == "18.00"


def test_create_sale_rejects_invalid_tax_treatment(client):
    response = client.post("/api/sales", json=_sale_payload(tax_treatment="luxury_tax"))
    assert response.status_code == 422


def test_create_sale_zero_rate_and_exempt_produce_zero_vat(client):
    for treatment in ("zero_rate", "exempt"):
        response = client.post("/api/sales", json=_sale_payload(tax_treatment=treatment))
        assert response.status_code == 201
        body = response.json()
        assert body["vat_amount"] == "0.00"
        assert body["tax_treatment"] == treatment


def test_create_sale_currency_selection_does_not_change_vat_rate(client):
    """118.00 charged in ILS, USD, or EUR all produce the same 18.00 VAT
    under the Israeli standard tax profile — currency never determines the
    tax rate."""
    for currency in ("ILS", "USD", "EUR"):
        response = client.post("/api/sales", json=_sale_payload(gross_amount="118.00", currency=currency))
        assert response.status_code == 201
        body = response.json()
        assert body["vat_amount"] == "18.00"
        assert body["currency"] == currency


def test_create_sale_rejects_currency_outside_supported_set(client):
    response = client.post("/api/sales", json=_sale_payload(currency="GBP"))
    assert response.status_code == 422


def test_create_sale_requires_customer_and_service_name(client):
    response = client.post("/api/sales", json=_sale_payload(customer_name=""))
    assert response.status_code == 422


def test_create_sale_accepts_each_allowed_payment_method(client):
    for method in ("card", "cash", "other"):
        response = client.post("/api/sales", json=_sale_payload(payment_method=method))
        assert response.status_code == 201
        assert response.json()["payment_method"] == method


def test_create_sale_accepts_null_payment_method(client):
    response = client.post("/api/sales", json=_sale_payload(payment_method=None))
    assert response.status_code == 201
    assert response.json()["payment_method"] is None


def test_create_sale_rejects_arbitrary_payment_method_string(client):
    response = client.post("/api/sales", json=_sale_payload(payment_method="bitcoin"))
    assert response.status_code == 422


def test_update_sale_rejects_arbitrary_payment_method_string(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    response = client.put(f"/api/sales/{created['id']}", json={"payment_method": "bitcoin"})

    assert response.status_code == 422


def test_update_sale_accepts_a_valid_payment_method_change(client):
    created = client.post("/api/sales", json=_sale_payload(payment_method="card")).json()

    response = client.put(f"/api/sales/{created['id']}", json={"payment_method": "cash"})

    assert response.status_code == 200
    assert response.json()["payment_method"] == "cash"


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
    # tax_treatment stays "standard" (unchanged): vat = 200 * 18/118 = 30.51
    # (rounded), net = 200 - 30.51 - 3 (processing fee, unchanged).
    assert body["vat_amount"] == "30.51"
    assert body["net_amount"] == "166.49"


def test_update_sale_recomputes_vat_when_tax_treatment_changes(client):
    created = client.post("/api/sales", json=_sale_payload(gross_amount="118.00")).json()
    assert created["vat_amount"] == "18.00"

    response = client.put(f"/api/sales/{created['id']}", json={"tax_treatment": "exempt"})

    assert response.status_code == 200
    body = response.json()
    assert body["tax_treatment"] == "exempt"
    assert body["vat_amount"] == "0.00"


def test_update_sale_rejects_invalid_tax_treatment(client):
    created = client.post("/api/sales", json=_sale_payload()).json()

    response = client.put(f"/api/sales/{created['id']}", json={"tax_treatment": "luxury_tax"})

    assert response.status_code == 422


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
