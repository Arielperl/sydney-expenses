"""Integration tests for the Cardcom connection lifecycle and webhook
ingestion: connection management (owner-only, business-isolated, encrypted
credentials), server-to-server verification (mocked — no real Cardcom call),
success/decline/non-charging handling, IP allowlisting, durable inbox,
duplicate delivery, and safe reprocessing."""

import json

import pytest

from app.api.routes import auth
from app.core.config import get_settings
from app.database import SessionLocal
from app.models.business import Business, BusinessMember
from app.models.cardcom_credential import CardcomCredential
from app.models.sale import Sale, SaleStatus
from app.services.ingestion.cardcom_provider import CardcomVerificationError
from tests.fixtures.cardcom_payloads import (
    CARDCOM_GET_LP_RESULT_CALL_FAILED,
    CARDCOM_GET_LP_RESULT_DECLINED,
    CARDCOM_GET_LP_RESULT_SUCCESS,
    CARDCOM_GET_LP_RESULT_TOKEN_ONLY,
    CARDCOM_RAW_WEBHOOK_FORM,
    CARDCOM_RAW_WEBHOOK_JSON,
)

CARDCOM_IP = "82.80.227.17"  # inside Cardcom's published 82.80.227.17/29 range
TEST_ENCRYPTION_KEY = "o8x1XJl4biNjdwxZjFAo44GqRGTX7C5gOaTx0fT6nlY="


@pytest.fixture
def secured_businesses(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["http://localhost:5174"])
    monkeypatch.setattr(settings, "connection_signing_secret", "test-master-key-with-at-least-32-characters")
    monkeypatch.setattr(settings, "cardcom_webhook_allowed_ips", ["82.80.227.17/29", "82.80.222.124/29"])
    monkeypatch.setattr(settings, "cardcom_credential_encryption_key", TEST_ENCRYPTION_KEY)
    with SessionLocal() as db:
        db.add_all([Business(id="business-a", name="Business A"), Business(id="business-b", name="Business B")])
        db.flush()
        db.add_all(
            [
                BusinessMember(business_id="business-a", user_id="owner-a", role="owner"),
                BusinessMember(business_id="business-a", user_id="manager-a", role="manager"),
                BusinessMember(business_id="business-a", user_id="viewer-a", role="viewer"),
                BusinessMember(business_id="business-b", user_id="owner-b", role="owner"),
            ]
        )
        db.commit()

    async def fake_auth(method, path, payload=None, token=None):
        return {"id": token, "email": f"{token}@example.com", "email_confirmed_at": "yes", "user_metadata": {}}

    monkeypatch.setattr(auth, "auth_request", fake_auth)


def _create_cardcom_connection(client, name: str = "מסוף חנות"):
    return client.post(
        "/api/connections",
        json={
            "name": name,
            "provider": "cardcom",
            "cardcom_terminal_number": "1000",
            "cardcom_api_name": "CardTest1994",
            "cardcom_api_password": "super-secret-password",
        },
        headers={"origin": "http://localhost:5174"},
    )


def _mock_verification(monkeypatch, result: dict | Exception):
    def fake_get_lowprofile_result(self, credentials, low_profile_id):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(
        "app.services.ingestion.cardcom_provider.CardcomVerificationClient.get_lowprofile_result",
        fake_get_lowprofile_result,
    )


def _post_cardcom_event(client, webhook_path: str, *, ip: str = CARDCOM_IP, form: bool = False):
    if form:
        return client.post(
            webhook_path,
            content=CARDCOM_RAW_WEBHOOK_FORM.encode(),
            headers={"content-type": "application/x-www-form-urlencoded", "x-forwarded-for": ip},
        )
    return client.post(
        webhook_path,
        content=json.dumps(CARDCOM_RAW_WEBHOOK_JSON).encode(),
        headers={"content-type": "application/json", "x-forwarded-for": ip},
    )


class TestConnectionManagement:
    def test_owner_creates_a_cardcom_connection_with_encrypted_credentials(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        response = _create_cardcom_connection(client)
        assert response.status_code == 201
        body = response.json()
        assert body["provider"] == "cardcom"
        assert body["signing_secret"] is None  # Cardcom defines no separate signing secret
        assert body["cardcom_terminal_number"] == "1000"
        assert "cardcom_api_name" not in body
        assert "cardcom_api_password" not in body
        assert "api_password" not in json.dumps(body)
        assert "super-secret-password" not in json.dumps(body)

        with SessionLocal() as db:
            credential = db.get(CardcomCredential, body["id"])
            assert credential is not None
            assert credential.terminal_number == "1000"
            assert "super-secret-password" not in credential.encrypted_credentials
            assert "CardTest1994" not in credential.encrypted_credentials

    def test_create_requires_terminal_number_and_api_name(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        response = client.post(
            "/api/connections",
            json={"name": "x", "provider": "cardcom"},
            headers={"origin": "http://localhost:5174"},
        )
        assert response.status_code == 422

    def test_manager_and_viewer_cannot_create_cardcom_connections(self, client, secured_businesses):
        client.cookies.set("sydney_access", "manager-a")
        assert _create_cardcom_connection(client).status_code == 403
        client.cookies.set("sydney_access", "viewer-a")
        assert _create_cardcom_connection(client).status_code == 403

    def test_connections_are_isolated_by_business(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        _create_cardcom_connection(client)
        client.cookies.set("sydney_access", "owner-b")
        assert client.get("/api/connections").json() == []

    def test_delete_connection_also_removes_credentials(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        assert client.delete(f"/api/connections/{connection['id']}", headers={"origin": "http://localhost:5174"}).status_code == 204
        with SessionLocal() as db:
            assert db.get(CardcomCredential, connection["id"]) is None

    def test_rotate_url_invalidates_the_previous_url(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        old_path = connection["webhook_path"]
        rotated = client.post(f"/api/connections/{connection['id']}/rotate-url", headers={"origin": "http://localhost:5174"})
        assert rotated.status_code == 200
        new_path = rotated.json()["webhook_path"]
        assert new_path != old_path

        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        assert _post_cardcom_event(client, old_path).status_code == 404
        assert _post_cardcom_event(client, new_path).status_code == 201

    def test_rotate_secret_is_rejected_for_cardcom(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        response = client.post(f"/api/connections/{connection['id']}/rotate-secret", headers={"origin": "http://localhost:5174"})
        assert response.status_code == 422

    def test_disabled_connection_rejects_events(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        client.patch(f"/api/connections/{connection['id']}", json={"enabled": False}, headers={"origin": "http://localhost:5174"})
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        assert _post_cardcom_event(client, connection["webhook_path"]).status_code == 404


class TestCardcomWebhookIngestion:
    def test_successful_transaction_creates_a_revenue_sale(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)

        response = _post_cardcom_event(client, connection["webhook_path"])
        assert response.status_code == 201
        sale_id = response.json()["sale_id"]

        with SessionLocal() as db:
            sale = db.get(Sale, sale_id)
            assert sale.business_id == "business-a"
            assert sale.status == SaleStatus.SUCCEEDED
            assert sale.source_provider == f"cardcom:{connection['id']}"
            assert sale.external_id == "209413394"
            assert sale.revenue_contribution() > 0

    def test_form_encoded_delivery_is_also_accepted(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        response = _post_cardcom_event(client, connection["webhook_path"], form=True)
        assert response.status_code == 201

    def test_declined_transaction_becomes_a_failed_sale_never_revenue(self, client, secured_businesses, monkeypatch, db_session):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_DECLINED)

        response = _post_cardcom_event(client, connection["webhook_path"])
        assert response.status_code == 201  # durably processed — a real, verified outcome
        sale_id = response.json()["sale_id"]

        with SessionLocal() as db:
            sale = db.get(Sale, sale_id)
            assert sale.status == SaleStatus.FAILED
            assert sale.revenue_contribution() == 0

        # Visible via the sales list, filterable, same as any other failed sale.
        client.cookies.set("sydney_access", "owner-a")
        listed = client.get("/api/sales", params={"status": "failed"}).json()
        assert any(row["id"] == sale_id for row in listed)

    def test_non_charging_operation_never_creates_a_sale(self, client, secured_businesses, monkeypatch, db_session):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_TOKEN_ONLY)

        response = _post_cardcom_event(client, connection["webhook_path"])
        assert response.status_code == 200
        assert response.json()["sale_id"] is None
        with SessionLocal() as db:
            assert db.query(Sale).filter(Sale.source_provider == f"cardcom:{connection['id']}").count() == 0

    def test_duplicate_delivery_returns_success_without_a_second_sale(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        first = _post_cardcom_event(client, connection["webhook_path"])
        second = _post_cardcom_event(client, connection["webhook_path"])
        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["sale_id"] == second.json()["sale_id"]
        with SessionLocal() as db:
            assert db.query(Sale).filter(Sale.external_id == "209413394").count() == 1

    def test_malformed_json_body_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        response = client.post(
            connection["webhook_path"],
            content=b"{not valid json",
            headers={"content-type": "application/json", "x-forwarded-for": CARDCOM_IP},
        )
        assert response.status_code == 422

    def test_missing_low_profile_id_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        response = client.post(
            connection["webhook_path"],
            content=json.dumps({"TerminalNumber": 1000}).encode(),
            headers={"content-type": "application/json", "x-forwarded-for": CARDCOM_IP},
        )
        assert response.status_code == 422

    def test_unsupported_content_type_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        response = client.post(
            connection["webhook_path"],
            content=b"whatever",
            headers={"content-type": "text/plain", "x-forwarded-for": CARDCOM_IP},
        )
        assert response.status_code == 415

    def test_sale_is_correctly_scoped_to_the_owning_business(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        response = _post_cardcom_event(client, connection["webhook_path"])
        sale_id = response.json()["sale_id"]

        client.cookies.set("sydney_access", "owner-b")
        assert client.get(f"/api/sales/{sale_id}").status_code == 404


class TestCardcomSourceIpEnforcement:
    def test_ip_allowlist_is_not_enforced_in_development(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        response = _post_cardcom_event(client, connection["webhook_path"], ip="198.51.100.7")
        assert response.status_code == 201

    def test_disallowed_ip_is_rejected_in_production(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        settings = get_settings()
        monkeypatch.setattr(settings, "app_environment", "production")
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        response = _post_cardcom_event(client, connection["webhook_path"], ip="203.0.113.55")
        assert response.status_code == 403
        with SessionLocal() as db:
            assert db.query(Sale).filter(Sale.source_provider == f"cardcom:{connection['id']}").count() == 0

    def test_allowed_ip_within_cardcoms_published_subnet_is_accepted_in_production(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        settings = get_settings()
        monkeypatch.setattr(settings, "app_environment", "production")
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        # .20 is inside 82.80.227.17/29 (the network containing .17-.23) even
        # though it isn't the exact address Cardcom's docs printed.
        response = _post_cardcom_event(client, connection["webhook_path"], ip="82.80.227.20")
        assert response.status_code == 201


class TestDurableInboxAndReprocessing:
    def test_every_delivery_is_recorded_in_the_activity_log(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        _post_cardcom_event(client, connection["webhook_path"])
        _post_cardcom_event(client, connection["webhook_path"])  # duplicate

        events = client.get(f"/api/connections/{connection['id']}/events").json()
        assert events["counts"]["processed"] == 1
        assert events["counts"]["duplicate"] == 1

    def test_ip_rejection_is_durably_logged_as_rejected(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        settings = get_settings()
        monkeypatch.setattr(settings, "app_environment", "production")
        _post_cardcom_event(client, connection["webhook_path"], ip="203.0.113.55")

        events = client.get(f"/api/connections/{connection['id']}/events").json()
        assert events["counts"]["rejected"] == 1
        rejected = next(e for e in events["events"] if e["status"] == "rejected")
        assert rejected["failure_category"] == "ip_not_allowed"
        assert rejected["can_reprocess"] is False

    def test_verification_failure_is_reprocessable_and_reprocess_succeeds(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()

        _mock_verification(monkeypatch, CardcomVerificationError("simulated network error"))
        response = _post_cardcom_event(client, connection["webhook_path"])
        assert response.status_code == 202
        event_id = response.json()["event_id"]

        events = client.get(f"/api/connections/{connection['id']}/events").json()["events"]
        failed = next(e for e in events if e["id"] == event_id)
        assert failed["status"] == "failed"
        assert failed["failure_category"] == "verification_failed"
        assert failed["can_reprocess"] is True
        # A safe, human-readable diagnostic is expected — what must never
        # appear is any credential or raw payload data.
        assert "super-secret-password" not in json.dumps(failed)
        assert "CardTest1994" not in json.dumps(failed)

        # Cardcom's own server recovers — a reprocess now succeeds.
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_SUCCESS)
        reprocessed = client.post(
            f"/api/connections/{connection['id']}/events/{event_id}/reprocess", headers={"origin": "http://localhost:5174"}
        )
        assert reprocessed.status_code == 200
        assert reprocessed.json()["status"] == "processed"
        assert reprocessed.json()["sale_id"] is not None

        with SessionLocal() as db:
            assert db.query(Sale).filter(Sale.external_id == "209413394").count() == 1

    def test_non_charging_operation_failure_is_not_reprocessable(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CARDCOM_GET_LP_RESULT_TOKEN_ONLY)
        response = _post_cardcom_event(client, connection["webhook_path"])
        assert response.status_code == 200

        events = client.get(f"/api/connections/{connection['id']}/events").json()["events"]
        failed = next(e for e in events if e["status"] == "failed")
        assert failed["can_reprocess"] is False
        reprocess_response = client.post(
            f"/api/connections/{connection['id']}/events/{failed['id']}/reprocess", headers={"origin": "http://localhost:5174"}
        )
        assert reprocess_response.status_code == 422

    def test_reprocess_is_owner_only(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_cardcom_connection(client).json()
        _mock_verification(monkeypatch, CardcomVerificationError("simulated"))
        response = _post_cardcom_event(client, connection["webhook_path"])
        event_id = response.json()["event_id"]

        client.cookies.set("sydney_access", "viewer-a")
        assert client.post(
            f"/api/connections/{connection['id']}/events/{event_id}/reprocess", headers={"origin": "http://localhost:5174"}
        ).status_code == 403
