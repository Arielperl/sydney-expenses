import json
import time

import pytest

from app.api.routes import auth
from app.core.config import get_settings
from app.database import SessionLocal
from app.models.business import Business, BusinessMember
from app.models.integration_connection import IntegrationConnection
from app.models.sale import Sale
from app.services.ingestion.webhook_security import compute_signature


def _event(external_id: str = "pos-txn-1") -> dict:
    return {
        "event_id": f"event-{external_id}",
        "provider": "demo-pay",
        "external_transaction_id": external_id,
        "occurred_at": "2026-09-10T09:00:00+00:00",
        "customer_name": "POS Customer",
        "customer_email": "pos@example.com",
        "service_name": "Store purchase",
        "gross_amount": "118.00",
        "vat_amount": "18.00",
        "processing_fee": "3.00",
        "net_amount": "97.00",
        "currency": "ILS",
        "payment_method": "card",
        "status": "succeeded",
    }


def _headers(body: bytes, secret: str) -> dict:
    timestamp = str(int(time.time()))
    return {"X-Timestamp": timestamp, "X-Signature": compute_signature(secret, timestamp, body)}


@pytest.fixture
def secured_businesses(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["http://localhost:5174"])
    monkeypatch.setattr(settings, "connection_signing_secret", "test-master-key-with-at-least-32-characters")
    with SessionLocal() as db:
        db.add_all([Business(id="business-a", name="Business A"), Business(id="business-b", name="Business B")])
        db.flush()
        db.add_all([
            BusinessMember(business_id="business-a", user_id="owner-a", role="owner"),
            BusinessMember(business_id="business-b", user_id="viewer-b", role="viewer"),
        ])
        db.commit()

    async def fake_auth(method, path, payload=None, token=None):
        return {
            "id": token,
            "email": f"{token}@example.com",
            "email_confirmed_at": "yes",
            "user_metadata": {},
        }

    monkeypatch.setattr(auth, "auth_request", fake_auth)


def _create(client, name: str = "Main till"):
    return client.post(
        "/api/connections",
        json={"name": name, "provider": "demo-pay"},
        headers={"origin": "http://localhost:5174"},
    )


def test_owner_creates_business_connection_and_secret_is_only_returned_once(client, secured_businesses):
    client.cookies.set("sydney_access", "owner-a")
    created = _create(client)
    assert created.status_code == 201
    assert len(created.json()["signing_secret"]) >= 40
    assert created.json()["webhook_path"].endswith(created.json()["id"])

    listed = client.get("/api/connections")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "signing_secret" not in listed.json()[0]

    with SessionLocal() as db:
        connection = db.get(IntegrationConnection, created.json()["id"])
        assert connection.business_id == "business-a"
        assert "secret" not in connection.__table__.columns


def test_viewer_cannot_manage_connections_and_business_lists_are_isolated(client, secured_businesses):
    client.cookies.set("sydney_access", "owner-a")
    assert _create(client).status_code == 201

    client.cookies.set("sydney_access", "viewer-b")
    assert client.get("/api/connections").json() == []
    assert _create(client).status_code == 403


def test_connection_webhook_routes_sale_to_owner_business(client, secured_businesses):
    client.cookies.set("sydney_access", "owner-a")
    connection = _create(client).json()
    body = json.dumps(_event()).encode()

    response = client.post(connection["webhook_path"], content=body, headers=_headers(body, connection["signing_secret"]))
    assert response.status_code == 201

    with SessionLocal() as db:
        sale = db.get(Sale, response.json()["sale_id"])
        assert sale.business_id == "business-a"
        assert sale.source_provider == f"demo-pay:{connection['id']}"
        assert db.get(IntegrationConnection, connection["id"]).last_event_at is not None


def test_rotating_secret_invalidates_old_secret(client, secured_businesses):
    client.cookies.set("sydney_access", "owner-a")
    connection = _create(client).json()
    rotated = client.post(
        f"/api/connections/{connection['id']}/rotate-secret",
        headers={"origin": "http://localhost:5174"},
    )
    assert rotated.status_code == 200
    assert rotated.json()["signing_secret"] != connection["signing_secret"]

    body = json.dumps(_event("rotated-txn")).encode()
    assert client.post(connection["webhook_path"], content=body, headers=_headers(body, connection["signing_secret"])).status_code == 401
    assert client.post(connection["webhook_path"], content=body, headers=_headers(body, rotated.json()["signing_secret"])).status_code == 201


def test_disabled_and_unknown_connections_reject_events(client, secured_businesses):
    client.cookies.set("sydney_access", "owner-a")
    connection = _create(client).json()
    disabled = client.patch(
        f"/api/connections/{connection['id']}",
        json={"enabled": False},
        headers={"origin": "http://localhost:5174"},
    )
    assert disabled.status_code == 200
    body = json.dumps(_event()).encode()
    assert client.post(connection["webhook_path"], content=body, headers=_headers(body, connection["signing_secret"])).status_code == 404
    assert client.post("/api/webhooks/connections/00000000-0000-4000-8000-000000000099", content=body, headers=_headers(body, connection["signing_secret"])).status_code == 404


def test_demo_connections_are_not_available_in_production(client, secured_businesses, monkeypatch):
    # demo-pay stays development/test-only in production: hidden from the
    # connections list, rejected on creation, and its webhook URL rejects
    # events — but the /api/connections routes themselves are NOT blocked
    # wholesale in production anymore, since a business's real Grow
    # connections must be manageable there. See test_grow_connections.py.
    client.cookies.set("sydney_access", "owner-a")
    connection = _create(client).json()
    settings = get_settings()
    monkeypatch.setattr(settings, "app_environment", "production")

    listed = client.get("/api/connections")
    assert listed.status_code == 200
    assert connection["id"] not in [row["id"] for row in listed.json()]

    assert _create(client, "Another till").status_code == 422

    body = json.dumps(_event("production-demo-txn")).encode()
    response = client.post(
        connection["webhook_path"],
        content=body,
        headers=_headers(body, connection["signing_secret"]),
    )
    assert response.status_code == 404
