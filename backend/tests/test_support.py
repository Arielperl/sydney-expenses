import pytest

from app.api.routes import auth
from app.core.config import get_settings
from app.database import SessionLocal
from app.models.business import AppAccount, Business, BusinessMember, BusinessPaymentProvider
from app.models.integration_connection import IntegrationConnection
from app.models.support_request import SupportMessage, SupportRequest


@pytest.fixture
def support_setup(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["http://localhost:5174"])
    with SessionLocal() as db:
        db.add_all([Business(id="one", name="One"), Business(id="two", name="Two")])
        db.flush()
        db.add_all([
            BusinessMember(business_id="one", user_id="owner-one", role="owner"),
            BusinessMember(business_id="two", user_id="owner-two", role="owner"),
            AppAccount(user_id="owner-one", email="one@example.com", system_role="user"),
            AppAccount(user_id="owner-two", email="two@example.com", system_role="user"),
            AppAccount(user_id="staff", email="support@example.com", system_role="support"),
            AppAccount(user_id="legacy-admin", email="old@example.com", system_role="admin"),
            AppAccount(user_id="root-admin", email="root@example.com", system_role="superadmin"),
        ])
        db.commit()

    async def fake_auth(method, path, payload=None, token=None):
        return {"id": token, "email": {"staff": "support@example.com", "legacy-admin": "old@example.com", "root-admin": "root@example.com"}.get(token, f"{token}@example.com"), "email_confirmed_at": "yes", "user_metadata": {}}
    monkeypatch.setattr(auth, "auth_request", fake_auth)


def test_owner_can_create_request_and_other_business_cannot_read_it(client, support_setup):
    client.cookies.set("sydney_access", "owner-one")
    response = client.post("/api/support/requests", json={"subject": "Cardcom connection", "message": "Please connect our terminal to the dashboard.", "provider": "cardcom"}, headers={"origin": "http://localhost:5174"})
    assert response.status_code == 201
    assert response.json()["business_id"] == "one"
    listed = client.get("/api/support/requests")
    assert len(listed.json()) == 1
    assert "no-store" in listed.headers["cache-control"]
    client.cookies.set("sydney_access", "owner-two")
    assert client.get("/api/support/requests").json() == []


def test_staff_sees_all_requests_and_changes_status(client, support_setup):
    with SessionLocal() as db:
        db.add(SupportRequest(id="ticket-1", business_id="two", requester_user_id="owner-two", subject="Need Grow", message="Please connect our Grow account"))
        db.commit()
    client.cookies.set("sydney_access", "staff")
    response = client.get("/api/support/staff/requests")
    assert response.status_code == 200
    assert response.json()[0]["business_name"] == "Two"
    changed = client.patch("/api/support/staff/requests/ticket-1", json={"status": "resolved"}, headers={"origin": "http://localhost:5174"})
    assert changed.status_code == 200
    assert changed.json()["status"] == "resolved"


def test_customer_and_staff_can_exchange_messages_without_cross_business_access(client, support_setup):
    headers = {"origin": "http://localhost:5174"}
    with SessionLocal() as db:
        db.add(SupportRequest(
            id="thread-1",
            business_id="one",
            requester_user_id="owner-one",
            subject="Connection help",
            message="Please help us connect our payment provider.",
            status="resolved",
        ))
        db.commit()

    client.cookies.set("sydney_access", "owner-one")
    customer_reply = client.post(
        "/api/support/requests/thread-1/messages",
        json={"body": "Here are the missing business details."},
        headers=headers,
    )
    assert customer_reply.status_code == 201
    assert customer_reply.json()["author_type"] == "customer"
    assert len(client.get("/api/support/requests/thread-1/messages").json()) == 2
    assert client.get("/api/support/requests").json()[0]["status"] == "open"

    client.cookies.set("sydney_access", "owner-two")
    assert client.get("/api/support/requests/thread-1/messages").status_code == 404
    assert client.post(
        "/api/support/requests/thread-1/messages",
        json={"body": "I should not be able to reply."},
        headers=headers,
    ).status_code == 404

    client.cookies.set("sydney_access", "staff")
    staff_reply = client.post(
        "/api/support/staff/requests/thread-1/messages",
        json={"body": "Thanks, the connection is now ready."},
        headers=headers,
    )
    assert staff_reply.status_code == 201
    assert staff_reply.json()["author_type"] == "staff"
    messages = client.get("/api/support/staff/requests/thread-1/messages").json()
    assert [message["author_type"] for message in messages] == ["customer", "customer", "staff"]
    with SessionLocal() as db:
        assert db.query(SupportMessage).filter_by(request_id="thread-1").count() == 2


def test_support_role_is_required_for_cross_business_operations(client, support_setup):
    for identity in ("owner-one",):
        client.cookies.set("sydney_access", identity)
        assert client.get("/api/support/staff/requests").status_code == 403
        assert client.get("/api/support/staff/businesses").status_code == 403
        assert client.post("/api/support/staff/businesses/two/payment-providers/grow", headers={"origin": "http://localhost:5174"}).status_code == 403
    assert client.get("/api/admin/businesses").status_code in (403, 404)


def test_only_superadmin_can_manage_accounts(client, support_setup, monkeypatch):
    from app.api.routes import admin
    called = []

    async def fake_delete(user_id):
        called.append(user_id)

    monkeypatch.setattr(admin, "delete_auth_identity", fake_delete)
    client.cookies.set("sydney_access", "staff")
    assert client.get("/api/support/staff/users").status_code == 403
    assert client.delete("/api/support/staff/users/owner-two", headers={"origin": "http://localhost:5174"}).status_code == 403
    client.cookies.set("sydney_access", "legacy-admin")
    assert client.get("/api/support/staff/users").status_code == 403
    client.cookies.set("sydney_access", "root-admin")
    assert client.get("/api/support/staff/users").status_code == 200
    assert client.delete("/api/support/staff/users/owner-two", headers={"origin": "http://localhost:5174"}).status_code == 409
    assert called == []
    assert client.delete("/api/support/staff/users/staff", headers={"origin": "http://localhost:5174"}).status_code == 204
    assert called == ["staff"]
    with SessionLocal() as db:
        assert db.get(AppAccount, "staff").disabled_at is not None
        assert db.get(AppAccount, "staff").email.endswith("@invalid.local")


def test_superadmin_creates_account_and_changes_its_role(client, support_setup, monkeypatch):
    from app.api.routes import admin

    async def fake_create(email, password, name):
        assert email == "new-support@support.sydneyexpenses.com"
        assert password == "temporary-pass-123"
        return {"id": "new-staff"}

    monkeypatch.setattr(admin, "create_auth_identity", fake_create)
    client.cookies.set("sydney_access", "root-admin")
    headers = {"origin": "http://localhost:5174"}
    created = client.post(
        "/api/support/staff/users",
        json={
            "email": "new-support@support",
            "password": "temporary-pass-123",
            "name": "New Support",
            "system_role": "support",
        },
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["email"] == "new-support@support"
    assert created.json()["system_role"] == "support"
    changed = client.patch(
        "/api/support/staff/users/new-staff/role",
        json={"system_role": "admin"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["system_role"] == "admin"
    with SessionLocal() as db:
        assert db.get(AppAccount, "new-staff").system_role == "admin"
        assert db.get(AppAccount, "new-staff").email == "new-support@support"


def test_staff_login_name_is_rejected_for_regular_user(client, support_setup):
    client.cookies.set("sydney_access", "root-admin")
    response = client.post(
        "/api/support/staff/users",
        json={
            "email": "customer@support",
            "password": "temporary-pass-123",
            "name": "Customer",
            "system_role": "user",
        },
        headers={"origin": "http://localhost:5174"},
    )
    assert response.status_code == 422


def test_superadmin_role_cannot_be_changed_or_deleted(client, support_setup, monkeypatch):
    from app.api.routes import admin

    async def fake_delete(user_id):
        raise AssertionError(f"must not delete {user_id}")

    monkeypatch.setattr(admin, "delete_auth_identity", fake_delete)
    client.cookies.set("sydney_access", "root-admin")
    headers = {"origin": "http://localhost:5174"}
    assert client.patch("/api/support/staff/users/root-admin/role", json={"system_role": "admin"}, headers=headers).status_code == 403
    assert client.delete("/api/support/staff/users/root-admin", headers=headers).status_code == 409


def test_staff_adds_and_removes_provider_disabling_connections(client, support_setup):
    client.cookies.set("sydney_access", "staff")
    added = client.post("/api/support/staff/businesses/two/payment-providers/cardcom", headers={"origin": "http://localhost:5174"})
    assert added.status_code == 201
    with SessionLocal() as db:
        db.add(IntegrationConnection(id="connection", business_id="two", provider="cardcom", name="Terminal", secret_salt="test", url_token="long-token-enough-for-test", enabled=True))
        db.commit()
    removed = client.delete("/api/support/staff/businesses/two/payment-providers/cardcom", headers={"origin": "http://localhost:5174"})
    assert removed.status_code == 200
    assert removed.json()["disabled_connections"] == 1
    with SessionLocal() as db:
        assert db.get(BusinessPaymentProvider, ("two", "cardcom")) is None
        assert db.get(IntegrationConnection, "connection").enabled is False
