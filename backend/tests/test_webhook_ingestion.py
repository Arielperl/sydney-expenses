import json
import time

import pytest

from app.core.config import get_settings
from app.models.sale import Sale
from app.services.ingestion.webhook_security import compute_signature

WEBHOOK_URL = "/api/webhooks/payments"
SECRET = "test-webhook-secret"


def _event(**overrides) -> dict:
    payload = {
        "event_id": "evt-1",
        "provider": "demo-pay",
        "external_transaction_id": "txn-1",
        "occurred_at": "2026-09-10T09:00:00+00:00",
        "customer_name": "Demo Customer",
        "customer_email": "demo@example.com",
        "service_name": "Consulting session",
        "gross_amount": "184.90",
        "vat_amount": "27.72",
        "processing_fee": "5.55",
        "net_amount": "151.63",
        "currency": "ILS",
        "payment_method": "card",
        "status": "succeeded",
        "description": "Demo payment",
    }
    payload.update(overrides)
    return payload


def _signed_headers(raw_body: bytes, *, timestamp: str | None = None, secret: str = SECRET) -> dict:
    ts = timestamp or str(int(time.time()))
    return {"X-Signature": compute_signature(secret, ts, raw_body), "X-Timestamp": ts}


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SIGNING_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_valid_signature_creates_sale(client, db_session):
    body = json.dumps(_event()).encode("utf-8")

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert response.status_code == 201
    data = response.json()
    assert data["created"] is True

    sale = db_session.get(Sale, data["sale_id"])
    assert sale is not None
    assert sale.customer_name == "Demo Customer"
    assert sale.service_name == "Consulting session"
    assert sale.source.value == "webhook"
    assert sale.status.value == "succeeded"
    assert sale.external_id == "txn-1"
    assert sale.gross_amount == sale.vat_amount + sale.processing_fee + sale.net_amount


def test_only_succeeded_payments_count_as_revenue(client, db_session):
    body = json.dumps(_event(external_transaction_id="txn-pending", event_id="evt-pending", status="pending")).encode(
        "utf-8"
    )

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))
    assert response.status_code == 201

    dashboard = client.get("/api/dashboard/stats").json()
    assert dashboard["net_revenue_this_month"] == "0.00"


def test_repeated_delivery_is_idempotent(client, db_session):
    body = json.dumps(_event()).encode("utf-8")

    first = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))
    second = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["sale_id"] == first.json()["sale_id"]

    count = db_session.query(Sale).filter(Sale.external_id == "txn-1").count()
    assert count == 1


def test_invalid_signature_is_rejected(client):
    body = json.dumps(_event()).encode("utf-8")
    timestamp = str(int(time.time()))

    response = client.post(
        WEBHOOK_URL, content=body, headers={"X-Signature": "not-the-real-signature", "X-Timestamp": timestamp}
    )

    assert response.status_code == 401


def test_stale_timestamp_is_rejected(client):
    body = json.dumps(_event()).encode("utf-8")
    old_timestamp = str(int(time.time()) - 3600)

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body, timestamp=old_timestamp))

    assert response.status_code == 401


def test_oversized_body_is_rejected(client):
    big_description = "x" * (70 * 1024)
    body = json.dumps(_event(description=big_description)).encode("utf-8")

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert response.status_code == 413


def test_malformed_payload_is_rejected(client):
    body = json.dumps({"provider": "demo-pay"}).encode("utf-8")

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert response.status_code == 422


def test_unknown_provider_is_rejected(client):
    body = json.dumps(_event(provider="unknown-provider")).encode("utf-8")

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert response.status_code == 422


def test_secret_and_signature_never_appear_in_response_body(client):
    body = json.dumps(_event()).encode("utf-8")

    response = client.post(
        WEBHOOK_URL, content=body, headers={"X-Signature": "wrong", "X-Timestamp": str(int(time.time()))}
    )

    assert SECRET not in response.text
    assert "wrong" not in response.text


def test_concurrent_duplicate_delivery_creates_only_one_sale(client, db_session):
    """Simulates two workers racing to ingest the same payment: both attempt
    the insert, the DB unique constraint lets only one through, and the
    loser's IntegrityError is handled as 'already exists', not a 500."""
    from app.services.ingestion.webhook_provider import parse_webhook_event
    from app.services.sale_service import ingest_payment_event

    event = parse_webhook_event(_event(external_transaction_id="txn-concurrent", event_id="evt-concurrent"))

    first_sale, first_created = ingest_payment_event(db_session, event)
    second_sale, second_created = ingest_payment_event(db_session, event)

    assert first_created is True
    assert second_created is False
    assert first_sale.id == second_sale.id
    count = db_session.query(Sale).filter(Sale.external_id == "txn-concurrent").count()
    assert count == 1


def test_refund_reduces_revenue_totals(client):
    body = json.dumps(_event(external_transaction_id="txn-refund", event_id="evt-refund")).encode("utf-8")
    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))
    sale_id = response.json()["sale_id"]

    before = client.get("/api/dashboard/stats").json()
    assert before["net_revenue_this_month"] != "0.00"

    refund_response = client.post(f"/api/sales/{sale_id}/refund", json={})
    assert refund_response.status_code == 200
    assert refund_response.json()["status"] == "refunded"

    after = client.get("/api/dashboard/stats").json()
    assert after["net_revenue_this_month"] == "0.00"


def test_partial_refund_reduces_net_amount_correctly(client):
    body = json.dumps(_event(external_transaction_id="txn-partial-refund", event_id="evt-partial-refund")).encode(
        "utf-8"
    )
    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))
    sale_id = response.json()["sale_id"]

    refund_response = client.post(f"/api/sales/{sale_id}/refund", json={"amount": "50.00"})
    assert refund_response.status_code == 200
    body = refund_response.json()
    assert body["status"] == "partially_refunded"
    assert body["refunded_amount"] == "50.00"
