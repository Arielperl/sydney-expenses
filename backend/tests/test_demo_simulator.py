from decimal import Decimal

from app.core.config import get_settings
from app.models.sale import Sale, SaleSource, SaleStatus


def _simulate(client, **overrides) -> dict:
    payload = {
        "customer_name": "דנה כהן",
        "service_name": "ייעוץ עסקי",
        "gross_amount": "118.00",
        "currency": "ILS",
        "payment_method": "card",
        "tax_treatment": "standard",
        "scenario": "succeeded",
    }
    payload.update(overrides)
    return client.post("/api/demo/simulate", json=payload)


def test_simulating_a_successful_card_purchase_creates_a_labeled_demo_sale(client, db_session):
    response = _simulate(client, scenario="succeeded", payment_method="card")
    assert response.status_code == 201, response.text
    body = response.json()

    sale = db_session.get(Sale, body["sale"]["id"])
    assert sale.source == SaleSource.DEMO
    assert sale.source_provider == "demo-simulator"
    assert sale.status == SaleStatus.SUCCEEDED
    assert sale.payment_method == "card"
    assert sale.vat_amount == Decimal("18.00")  # 118 * 18/118, same Israeli formula as any other sale


def test_simulating_pending_and_failed_payments(client):
    pending = _simulate(client, scenario="pending").json()
    assert pending["sale"]["status"] == "pending"

    failed = _simulate(client, scenario="failed").json()
    assert failed["sale"]["status"] == "failed"


def test_simulating_a_sale_whose_document_fails(client, db_session):
    response = _simulate(client, scenario="succeeded_document_failed")
    sale_id = response.json()["sale"]["id"]

    sale = db_session.get(Sale, sale_id)
    assert sale.document_status.value == "failed"

    events = client.get(f"/api/sales/{sale_id}/events").json()
    assert any(e["event_type"] == "document_issuance_failed" for e in events)


def test_simulating_a_partial_refund(client):
    response = _simulate(client, scenario="succeeded_partial_refund", gross_amount="200.00")
    body = response.json()
    assert body["sale"]["status"] == "partially_refunded"
    assert Decimal(body["sale"]["refunded_amount"]) > 0
    assert Decimal(body["sale"]["refunded_amount"]) < Decimal(body["sale"]["net_amount"])


def test_simulating_a_full_refund(client):
    response = _simulate(client, scenario="succeeded_full_refund")
    body = response.json()
    assert body["sale"]["status"] == "refunded"
    assert body["sale"]["refunded_amount"] == body["sale"]["net_amount"]


def test_simulating_usd_and_eur_sales_use_the_same_israeli_vat_rate(client):
    for currency in ("USD", "EUR"):
        body = _simulate(client, currency=currency, gross_amount="118.00").json()
        assert body["sale"]["currency"] == currency
        assert body["sale"]["vat_amount"] == "18.00"


def test_simulate_rejects_invalid_scenario(client):
    response = _simulate(client, scenario="not-a-real-scenario")
    assert response.status_code == 422


def test_reset_preview_counts_only_demo_sales(client):
    client.post(
        "/api/sales",
        json={
            "customer_name": "Manual Sale",
            "service_name": "Consulting",
            "gross_amount": "10.00",
            "currency": "ILS",
            "occurred_at": "2026-01-01T00:00:00",
        },
    )
    _simulate(client)
    _simulate(client)

    preview = client.get("/api/demo/reset-preview").json()
    assert preview["demo_sales_count"] == 2


def test_reset_deletes_only_demo_sales_and_their_events(client, db_session):
    manual = client.post(
        "/api/sales",
        json={
            "customer_name": "Manual Sale",
            "service_name": "Consulting",
            "gross_amount": "10.00",
            "currency": "ILS",
            "occurred_at": "2026-01-01T00:00:00",
        },
    ).json()
    _simulate(client)
    _simulate(client)

    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    body = response.json()
    assert body["deleted_sales_count"] == 2
    assert body["deleted_events_count"] > 0

    remaining = client.get("/api/sales").json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == manual["id"]
    assert db_session.query(Sale).filter(Sale.source == SaleSource.DEMO).count() == 0


def test_reset_with_no_demo_sales_reports_zero(client):
    response = client.post("/api/demo/reset")
    assert response.json() == {"deleted_sales_count": 0, "deleted_events_count": 0}


def test_demo_endpoints_are_disabled_in_production(client, monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        assert _simulate(client).status_code == 403
        assert client.get("/api/demo/reset-preview").status_code == 403
        assert client.post("/api/demo/reset").status_code == 403
        assert client.get("/api/demo/scenarios").status_code == 403
    finally:
        get_settings.cache_clear()


def test_system_capabilities_reports_demo_simulator_enabled(client, monkeypatch):
    assert client.get("/api/system/capabilities").json()["demo_simulator_enabled"] is True

    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        assert client.get("/api/system/capabilities").json()["demo_simulator_enabled"] is False
    finally:
        get_settings.cache_clear()
