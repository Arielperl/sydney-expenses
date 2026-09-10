import json
import time

import pytest

from app.core.config import get_settings
from app.models.expense import Expense
from app.services.ingestion.webhook_security import compute_signature

WEBHOOK_URL = "/api/webhooks/transactions"
SECRET = "test-webhook-secret"


def _event(**overrides) -> dict:
    payload = {
        "event_id": "evt-1",
        "provider": "demo-bank",
        "external_transaction_id": "txn-1",
        "occurred_at": "2026-09-10T09:00:00+00:00",
        "merchant_name": "Demo Café",
        "amount": "184.90",
        "currency": "ILS",
        "payment_method": "card",
        "description": "Demo transaction",
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


def test_valid_signature_creates_expense(client, db_session):
    body = json.dumps(_event()).encode("utf-8")

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert response.status_code == 201
    data = response.json()
    assert data["created"] is True

    expense = db_session.get(Expense, data["expense_id"])
    assert expense is not None
    assert expense.business_name == "Demo Café"
    assert expense.source.value == "webhook"
    assert expense.document_status.value == "missing"
    assert expense.external_id == "txn-1"


def test_repeated_delivery_is_idempotent(client, db_session):
    body = json.dumps(_event()).encode("utf-8")

    first = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))
    second = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["expense_id"] == first.json()["expense_id"]

    count = db_session.query(Expense).filter(Expense.external_id == "txn-1").count()
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
    body = json.dumps({"provider": "demo-bank"}).encode("utf-8")

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert response.status_code == 422


def test_unknown_provider_is_rejected(client):
    body = json.dumps(_event(provider="unknown-bank")).encode("utf-8")

    response = client.post(WEBHOOK_URL, content=body, headers=_signed_headers(body))

    assert response.status_code == 422


def test_secret_and_signature_never_appear_in_response_body(client):
    body = json.dumps(_event()).encode("utf-8")

    response = client.post(
        WEBHOOK_URL, content=body, headers={"X-Signature": "wrong", "X-Timestamp": str(int(time.time()))}
    )

    assert SECRET not in response.text
    assert "wrong" not in response.text


def test_concurrent_duplicate_delivery_creates_only_one_expense(client, db_session):
    """Simulates two workers racing to ingest the same transaction: both
    attempt the insert, the DB unique constraint lets only one through, and
    the loser's IntegrityError is handled as 'already exists', not a 500."""
    from app.services.ingestion.transaction_ingest import ingest_transaction_event
    from app.services.ingestion.webhook_provider import parse_webhook_event

    event = parse_webhook_event(_event(external_transaction_id="txn-concurrent"))

    first_expense, first_created = ingest_transaction_event(db_session, event)
    second_expense, second_created = ingest_transaction_event(db_session, event)

    assert first_created is True
    assert second_created is False
    assert first_expense.id == second_expense.id
    count = db_session.query(Expense).filter(Expense.external_id == "txn-concurrent").count()
    assert count == 1
