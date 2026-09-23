import pytest

from app.api.routes import auth
from app.core.config import get_settings
from app.database import SessionLocal
from app.models.business import AppAccount, Business, BusinessMember, BusinessPaymentProvider
from app.models.integration_connection import IntegrationConnection


@pytest.fixture
def admin_businesses(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["http://localhost:5174"])
    with SessionLocal() as db:
        db.add_all([
            Business(id="admin-business", name="Admin Business"),
            Business(id="customer-business", name="Customer Business"),
        ])
        db.flush()
        db.add_all([
            BusinessMember(business_id="admin-business", user_id="admin-user", role="owner"),
            BusinessMember(business_id="customer-business", user_id="customer-user", role="owner"),
            AppAccount(user_id="admin-user", email="arielperl999@gmail.com", display_name="Ariel", system_role="admin"),
            AppAccount(user_id="customer-user", email="customer@example.com", display_name="Customer", system_role="user"),
        ])
        db.commit()

    async def fake_auth(method, path, payload=None, token=None):
        email = "arielperl999@gmail.com" if token == "admin-user" else f"{token}@example.com"
        return {"id": token, "email": email, "email_confirmed_at": "yes", "user_metadata": {}}

    monkeypatch.setattr(auth, "auth_request", fake_auth)


def test_admin_role_is_database_backed_and_can_list_all_businesses(client, admin_businesses):
    client.cookies.set("sydney_access", "admin-user")
    session = client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["system_role"] == "admin"

    response = client.get("/api/admin/businesses")
    assert response.status_code == 200
    assert {business["id"] for business in response.json()} == {"admin-business", "customer-business"}


def test_email_alone_never_grants_admin_access(client, admin_businesses, monkeypatch):
    with SessionLocal() as db:
        db.get(AppAccount, "admin-user").email = "admin-record@example.com"
        db.get(AppAccount, "customer-user").email = "arielperl999@gmail.com"
        db.commit()

    async def same_email_without_admin_role(method, path, payload=None, token=None):
        return {"id": "customer-user", "email": "arielperl999@gmail.com", "email_confirmed_at": "yes", "user_metadata": {}}

    monkeypatch.setattr(auth, "auth_request", same_email_without_admin_role)
    client.cookies.set("sydney_access", "customer-user")
    assert client.get("/api/admin/businesses").status_code == 403


def test_admin_can_add_provider_and_connection_gate_uses_it(client, admin_businesses):
    client.cookies.set("sydney_access", "customer-user")
    blocked = client.post(
        "/api/connections",
        json={"name": "Grow", "provider": "grow"},
        headers={"origin": "http://localhost:5174"},
    )
    assert blocked.status_code == 403

    client.cookies.set("sydney_access", "admin-user")
    added = client.post(
        "/api/admin/businesses/customer-business/payment-providers/grow",
        headers={"origin": "http://localhost:5174"},
    )
    assert added.status_code == 201
    with SessionLocal() as db:
        assert db.get(BusinessPaymentProvider, ("customer-business", "grow")) is not None


def test_admin_can_remove_provider_and_existing_connections_are_disabled(client, admin_businesses):
    with SessionLocal() as db:
        db.add(BusinessPaymentProvider(
            business_id="customer-business",
            provider="cardcom",
            added_by_user_id="admin-user",
        ))
        db.add(IntegrationConnection(
            id="cardcom-connection",
            business_id="customer-business",
            provider="cardcom",
            name="Main terminal",
            secret_salt="test-salt",
            url_token="cardcom-url-token-long-enough",
            enabled=True,
        ))
        db.commit()

    client.cookies.set("sydney_access", "admin-user")
    response = client.delete(
        "/api/admin/businesses/customer-business/payment-providers/cardcom",
        headers={"origin": "http://localhost:5174"},
    )
    assert response.status_code == 200
    assert response.json() == {"provider": "cardcom", "removed": True, "disabled_connections": 1}
    with SessionLocal() as db:
        assert db.get(BusinessPaymentProvider, ("customer-business", "cardcom")) is None
        assert db.get(IntegrationConnection, "cardcom-connection").enabled is False


def test_non_admin_cannot_remove_provider(client, admin_businesses):
    client.cookies.set("sydney_access", "customer-user")
    response = client.delete(
        "/api/admin/businesses/customer-business/payment-providers/grow",
        headers={"origin": "http://localhost:5174"},
    )
    assert response.status_code == 403


def test_admin_delete_requires_exact_name_and_protects_active_business(client, admin_businesses):
    client.cookies.set("sydney_access", "admin-user")
    headers = {"origin": "http://localhost:5174"}
    assert client.request("DELETE", "/api/admin/businesses/customer-business", json={"confirm_name": "wrong"}, headers=headers).status_code == 422
    assert client.request("DELETE", "/api/admin/businesses/admin-business", json={"confirm_name": "Admin Business"}, headers=headers).status_code == 409
    deleted = client.request("DELETE", "/api/admin/businesses/customer-business", json={"confirm_name": "Customer Business"}, headers=headers)
    assert deleted.status_code == 204
    with SessionLocal() as db:
        assert db.get(Business, "customer-business") is None
