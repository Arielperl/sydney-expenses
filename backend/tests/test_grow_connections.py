"""Integration tests for the Grow connection lifecycle and webhook
ingestion: connection management (owner-only, business-isolated), IP
allowlisting, durable inbox persistence, idempotency, unsupported payloads,
URL rotation, and safe reprocessing."""

import json
from datetime import datetime

import pytest

from app.api.routes import auth
from app.core.config import get_settings
from app.database import SessionLocal
from app.models.business import Business, BusinessMember, BusinessPaymentProvider
from app.models.integration_connection import IntegrationConnection
from app.models.provider_document_event import ProviderDocumentEvent, ProviderDocumentStatus
from app.models.sale import DocumentStatus, Sale
from app.models.sale_event import SaleEvent, SaleEventType
from app.models.webhook_event import WebhookEvent, WebhookEventStatus
from tests.fixtures.grow_payloads import (
    GROW_INSTALLMENTS_PAYMENT,
    GROW_INVOICE_EVENT,
    GROW_RECURRING_PAYMENT_UNSUPPORTED,
    GROW_REGULAR_PAYMENT,
)

GROW_IP = "3.123.194.128"  # a real address from Grow's published allowlist


@pytest.fixture
def secured_businesses(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "cors_allowed_origins", ["http://localhost:5174"])
    monkeypatch.setattr(settings, "connection_signing_secret", "test-master-key-with-at-least-32-characters")
    monkeypatch.setattr(settings, "grow_webhook_allowed_ips", [GROW_IP])
    with SessionLocal() as db:
        db.add_all([Business(id="business-a", name="Business A"), Business(id="business-b", name="Business B")])
        db.flush()
        db.add_all(
            [
                BusinessMember(business_id="business-a", user_id="owner-a", role="owner"),
                BusinessMember(business_id="business-a", user_id="manager-a", role="manager"),
                BusinessMember(business_id="business-a", user_id="viewer-a", role="viewer"),
                BusinessMember(business_id="business-b", user_id="owner-b", role="owner"),
                BusinessPaymentProvider(business_id="business-a", provider="grow", added_by_user_id="owner-a"),
                BusinessPaymentProvider(business_id="business-b", provider="grow", added_by_user_id="owner-b"),
            ]
        )
        db.commit()

    async def fake_auth(method, path, payload=None, token=None):
        return {"id": token, "email": f"{token}@example.com", "email_confirmed_at": "yes", "user_metadata": {}}

    monkeypatch.setattr(auth, "auth_request", fake_auth)


def _create_grow_connection(client, name: str = "קופה ראשית"):
    return client.post(
        "/api/connections",
        json={"name": name, "provider": "grow"},
        headers={"origin": "http://localhost:5174"},
    )


def _post_grow_event(client, webhook_path: str, payload: dict, *, ip: str = GROW_IP):
    return client.post(
        webhook_path,
        content=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "x-forwarded-for": ip},
    )


class TestConnectionManagement:
    def test_owner_creates_a_grow_connection_with_no_signing_secret(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        response = _create_grow_connection(client)
        assert response.status_code == 201
        body = response.json()
        assert body["provider"] == "grow"
        assert body["signing_secret"] is None  # Grow has no signing capability — never issued
        assert body["webhook_path"].startswith("/api/webhooks/connections/")
        assert body["has_received_event"] is False
        assert body["event_counts"] == {"received": 0, "processed": 0, "duplicate": 0, "failed": 0, "rejected": 0}

    def test_url_token_is_not_the_connection_id(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        body = _create_grow_connection(client).json()
        token = body["webhook_path"].rsplit("/", 1)[-1]
        assert token != body["id"]

    def test_manager_cannot_create_or_delete_connections(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        client.cookies.set("sydney_access", "manager-a")
        assert _create_grow_connection(client, "Another").status_code == 403
        assert client.delete(f"/api/connections/{connection['id']}", headers={"origin": "http://localhost:5174"}).status_code == 403

    def test_viewer_cannot_manage_connections(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        client.cookies.set("sydney_access", "viewer-a")
        assert _create_grow_connection(client, "Another").status_code == 403
        assert client.patch(
            f"/api/connections/{connection['id']}", json={"enabled": False}, headers={"origin": "http://localhost:5174"}
        ).status_code == 403
        assert client.delete(f"/api/connections/{connection['id']}", headers={"origin": "http://localhost:5174"}).status_code == 403

    def test_connections_are_isolated_by_business(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        _create_grow_connection(client)

        client.cookies.set("sydney_access", "owner-b")
        assert client.get("/api/connections").json() == []

    def test_delete_connection(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        assert client.delete(f"/api/connections/{connection['id']}", headers={"origin": "http://localhost:5174"}).status_code == 204
        assert client.get("/api/connections").json() == []

    def test_rotate_url_issues_a_new_token_and_invalidates_the_old_one(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        old_path = connection["webhook_path"]

        rotated = client.post(f"/api/connections/{connection['id']}/rotate-url", headers={"origin": "http://localhost:5174"})
        assert rotated.status_code == 200
        new_path = rotated.json()["webhook_path"]
        assert new_path != old_path

        assert _post_grow_event(client, old_path, GROW_REGULAR_PAYMENT).status_code == 404
        response = _post_grow_event(client, new_path, GROW_REGULAR_PAYMENT)
        assert response.status_code == 201

    def test_rotate_secret_is_rejected_for_a_grow_connection(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        response = client.post(f"/api/connections/{connection['id']}/rotate-secret", headers={"origin": "http://localhost:5174"})
        assert response.status_code == 422

    def test_disabled_connection_rejects_events(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        client.patch(f"/api/connections/{connection['id']}", json={"enabled": False}, headers={"origin": "http://localhost:5174"})
        assert _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT).status_code == 404


class TestGrowWebhookIngestion:
    def test_successful_event_creates_a_sale_correctly_attributed_to_grow(self, client, secured_businesses, db_session):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        response = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        assert response.status_code == 201
        sale_id = response.json()["sale_id"]

        with SessionLocal() as db:
            sale = db.get(Sale, sale_id)
            assert sale.business_id == "business-a"
            assert sale.source_provider == f"grow:{connection['id']}"
            assert sale.external_id == "ABCD1234"
            # Document issuance here goes through the exact same shared
            # sale_service.finalize_new_sale path every other sale source
            # already uses — this test environment's DOCUMENT_PROVIDER=mock
            # (see conftest.py) issues a document the same way it would for
            # a demo-pay or CSV sale; nothing Grow-specific happens here.
            # The real "no synthetic document" guarantee is a PRODUCTION
            # config fact (DOCUMENT_PROVIDER=disabled — see
            # test_security_hardening.py), verified next.

    def test_production_config_never_issues_a_document_for_a_grow_sale(self):
        # DOCUMENT_PROVIDER=disabled is enforced production-wide by
        # validate_auth_settings (see test_security_hardening.py) — a Grow
        # sale gets no special exemption or synthetic document number in
        # production, the same as every other sale source.
        from app.core.config import InsecureProductionConfigurationError, Settings, validate_auth_settings

        settings = Settings(
            app_environment="production",
            auth_required=True,
            supabase_url="https://project.supabase.co",
            supabase_secret_key="sb_secret_x",
            cors_allowed_origins=["https://app.example.com"],
            allowed_hosts=["api.example.com"],
            csv_preview_signing_secret="test-only-secret-with-at-least-32-characters",
            connection_signing_secret="test-only-connection-key-at-least-32-characters",
            receipt_extractor_provider="openai",
            grow_webhook_allowed_ips=[GROW_IP],
            document_provider="mock",
        )
        with pytest.raises(InsecureProductionConfigurationError, match="DOCUMENT_PROVIDER"):
            validate_auth_settings(settings)

    def test_connection_last_event_at_and_has_received_event_update(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        listed = client.get("/api/connections").json()
        assert listed[0]["has_received_event"] is True
        assert listed[0]["last_event_at"] is not None

    def test_duplicate_delivery_returns_success_without_a_second_sale(self, client, secured_businesses, db_session):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        first = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        second = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["sale_id"] == second.json()["sale_id"]
        with SessionLocal() as db:
            count = db.query(Sale).filter(Sale.external_id == "ABCD1234").count()
            assert count == 1

    def test_installments_transaction_is_accepted(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        response = _post_grow_event(client, connection["webhook_path"], GROW_INSTALLMENTS_PAYMENT)
        assert response.status_code == 201

    def test_recurring_payment_type_is_rejected_and_never_creates_a_sale(self, client, secured_businesses, db_session):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        response = _post_grow_event(client, connection["webhook_path"], GROW_RECURRING_PAYMENT_UNSUPPORTED)
        assert response.status_code == 422
        with SessionLocal() as db:
            assert db.query(Sale).filter(Sale.external_id == "ABCD9999").count() == 0

    def test_malformed_json_body_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        response = client.post(
            connection["webhook_path"],
            content=b"{not valid json",
            headers={"content-type": "application/json", "x-forwarded-for": GROW_IP},
        )
        assert response.status_code == 422

    def test_non_json_content_type_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        response = client.post(
            connection["webhook_path"],
            content=json.dumps(GROW_REGULAR_PAYMENT).encode(),
            headers={"content-type": "text/plain", "x-forwarded-for": GROW_IP},
        )
        assert response.status_code == 415

    def test_oversized_body_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        huge_payload = {**GROW_REGULAR_PAYMENT, "paymentDesc": "x" * (2 * 1024 * 1024)}
        response = client.post(
            connection["webhook_path"],
            content=json.dumps(huge_payload).encode(),
            headers={"content-type": "application/json", "x-forwarded-for": GROW_IP},
        )
        assert response.status_code == 413

    def test_unknown_connection_returns_404(self, client, secured_businesses):
        import secrets

        guessed_token = secrets.token_urlsafe(32)  # realistically-shaped, but never issued
        response = client.post(
            f"/api/webhooks/connections/{guessed_token}",
            content=json.dumps(GROW_REGULAR_PAYMENT).encode(),
            headers={"content-type": "application/json", "x-forwarded-for": GROW_IP},
        )
        assert response.status_code == 404

    def test_sale_is_correctly_scoped_to_the_owning_business(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        response = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        sale_id = response.json()["sale_id"]

        client.cookies.set("sydney_access", "owner-b")
        assert client.get(f"/api/sales/{sale_id}").status_code == 404


class TestGrowSourceIpEnforcement:
    def test_ip_allowlist_is_not_enforced_in_development(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        response = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT, ip="198.51.100.7")
        assert response.status_code == 201

    def test_allowed_ip_is_accepted_in_production(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        settings = get_settings()
        monkeypatch.setattr(settings, "app_environment", "production")
        response = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT, ip=GROW_IP)
        assert response.status_code == 201

    def test_non_grow_ip_is_rejected_in_production(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        settings = get_settings()
        monkeypatch.setattr(settings, "app_environment", "production")
        response = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT, ip="203.0.113.55")
        assert response.status_code == 403
        with SessionLocal() as db:
            assert db.query(Sale).filter(Sale.external_id == "ABCD1234").count() == 0

    def test_x_vercel_forwarded_for_is_preferred_over_x_forwarded_for(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        settings = get_settings()
        monkeypatch.setattr(settings, "app_environment", "production")
        response = client.post(
            connection["webhook_path"],
            content=json.dumps(GROW_REGULAR_PAYMENT).encode(),
            headers={
                "content-type": "application/json",
                "x-forwarded-for": "203.0.113.55",  # would be rejected on its own
                "x-vercel-forwarded-for": GROW_IP,  # the trustworthy one — must win
            },
        )
        assert response.status_code == 201


class TestDurableInboxAndReprocessing:
    def test_every_delivery_is_recorded_in_the_activity_log(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)  # duplicate
        _post_grow_event(client, connection["webhook_path"], GROW_RECURRING_PAYMENT_UNSUPPORTED)  # failed/validation

        # Every terminal status is reached — "received" itself is transient
        # (see record_received): a row only stays "received" if processing
        # was interrupted before reaching a terminal status, which none of
        # these three deliveries were.
        events = client.get(f"/api/connections/{connection['id']}/events").json()
        assert events["counts"] == {"received": 0, "processed": 1, "duplicate": 1, "failed": 1, "rejected": 0}
        assert len(events["events"]) == 3
        statuses = {event["status"] for event in events["events"]}
        assert statuses == {"processed", "duplicate", "failed"}

    def test_failure_message_never_contains_customer_pii(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        _post_grow_event(client, connection["webhook_path"], GROW_RECURRING_PAYMENT_UNSUPPORTED)
        events = client.get(f"/api/connections/{connection['id']}/events").json()["events"]
        failed = next(e for e in events if e["status"] == "failed")
        assert "test@test.com" not in (failed["failure_message"] or "")
        assert "0500000000" not in (failed["failure_message"] or "")

    def test_validation_failure_is_not_reprocessable(self, client, secured_businesses, db_session):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        _post_grow_event(client, connection["webhook_path"], GROW_RECURRING_PAYMENT_UNSUPPORTED)
        events = client.get(f"/api/connections/{connection['id']}/events").json()["events"]
        failed = next(e for e in events if e["status"] == "failed")
        assert failed["can_reprocess"] is False
        response = client.post(
            f"/api/connections/{connection['id']}/events/{failed['id']}/reprocess",
            headers={"origin": "http://localhost:5174"},
        )
        assert response.status_code == 422

    def test_processing_failure_can_be_safely_reprocessed(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        import app.api.routes.webhooks as webhooks_module

        original = webhooks_module.ingest_payment_event
        call_count = {"n": 0}

        def flaky(db, event, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated transient database error")
            return original(db, event, **kwargs)

        monkeypatch.setattr(webhooks_module, "ingest_payment_event", flaky)

        first = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        assert first.status_code == 202
        event_id = first.json()["event_id"]

        events = client.get(f"/api/connections/{connection['id']}/events").json()["events"]
        failed = next(e for e in events if e["id"] == event_id)
        assert failed["status"] == "failed"
        assert failed["can_reprocess"] is True

        reprocessed = client.post(
            f"/api/connections/{connection['id']}/events/{event_id}/reprocess",
            headers={"origin": "http://localhost:5174"},
        )
        assert reprocessed.status_code == 200
        assert reprocessed.json()["status"] == "processed"
        assert reprocessed.json()["sale_id"] is not None

        with SessionLocal() as db:
            assert db.query(Sale).filter(Sale.external_id == "ABCD1234").count() == 1

    def test_reprocessing_a_processing_failure_twice_does_not_duplicate_the_sale(self, client, secured_businesses, monkeypatch):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        import app.api.routes.webhooks as webhooks_module

        original = webhooks_module.ingest_payment_event
        call_count = {"n": 0}

        def flaky(db, event, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated transient database error")
            return original(db, event, **kwargs)

        monkeypatch.setattr(webhooks_module, "ingest_payment_event", flaky)
        first = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        event_id = first.json()["event_id"]

        client.post(f"/api/connections/{connection['id']}/events/{event_id}/reprocess", headers={"origin": "http://localhost:5174"})
        second_attempt = client.post(
            f"/api/connections/{connection['id']}/events/{event_id}/reprocess", headers={"origin": "http://localhost:5174"}
        )
        assert second_attempt.status_code == 422  # no longer a processing_error once already reprocessed
        with SessionLocal() as db:
            assert db.query(Sale).filter(Sale.external_id == "ABCD1234").count() == 1

    def test_events_and_reprocess_are_owner_only(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        client.cookies.set("sydney_access", "viewer-a")
        assert client.get(f"/api/connections/{connection['id']}/events").status_code == 403
        assert client.post(
            f"/api/connections/{connection['id']}/events/any-id/reprocess", headers={"origin": "http://localhost:5174"}
        ).status_code == 403


class TestInvoiceDocumentSync:
    """Grow's separate "Invoice creation" webhook — may arrive before or
    after the payment webhook for the same transaction. See
    app/api/routes/webhooks.py's _ingest_grow_invoice_event and
    app/services/sale_service.py's try_match_pending_provider_document."""

    def test_payment_then_invoice_links_the_document(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        payment = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        assert payment.status_code == 201
        sale_id = payment.json()["sale_id"]
        with SessionLocal() as db:
            sale = db.get(Sale, sale_id)
            assert sale.document_status == DocumentStatus.WAITING_AUTOMATIC

        invoice = _post_grow_event(client, connection["webhook_path"], GROW_INVOICE_EVENT)
        assert invoice.status_code == 200
        assert invoice.json()["sale_id"] == sale_id

        with SessionLocal() as db:
            sale = db.get(Sale, sale_id)
            assert sale.document_status == DocumentStatus.ISSUED
            assert sale.document_number == "20"
            assert sale.document_url == "https://secure.meshulam.co.il"
            events = db.query(ProviderDocumentEvent).filter(
                ProviderDocumentEvent.external_transaction_id == "ABCD1234"
            ).all()
            assert len(events) == 1
            assert events[0].status == ProviderDocumentStatus.MATCHED
            assert events[0].matched_sale_id == sale_id

    def test_invoice_then_payment_links_the_document_once_the_sale_exists(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        invoice = _post_grow_event(client, connection["webhook_path"], GROW_INVOICE_EVENT)
        assert invoice.status_code == 202
        assert invoice.json()["sale_id"] is None
        with SessionLocal() as db:
            pending = db.query(ProviderDocumentEvent).filter(
                ProviderDocumentEvent.external_transaction_id == "ABCD1234"
            ).one()
            assert pending.status == ProviderDocumentStatus.PENDING_MATCH

        payment = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        assert payment.status_code == 201
        sale_id = payment.json()["sale_id"]

        with SessionLocal() as db:
            sale = db.get(Sale, sale_id)
            assert sale.document_status == DocumentStatus.ISSUED
            assert sale.document_number == "20"
            assert sale.document_url == "https://secure.meshulam.co.il"
            pending = db.query(ProviderDocumentEvent).filter(
                ProviderDocumentEvent.external_transaction_id == "ABCD1234"
            ).one()
            assert pending.status == ProviderDocumentStatus.MATCHED
            assert pending.matched_sale_id == sale_id

    def test_no_sale_is_created_from_an_invoice_webhook_alone(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        response = _post_grow_event(client, connection["webhook_path"], GROW_INVOICE_EVENT)
        assert response.status_code == 202
        with SessionLocal() as db:
            assert db.query(Sale).count() == 0

    def test_duplicate_invoice_webhook_does_not_create_a_second_row_or_event(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()

        _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        first = _post_grow_event(client, connection["webhook_path"], GROW_INVOICE_EVENT)
        assert first.status_code == 200
        second = _post_grow_event(client, connection["webhook_path"], GROW_INVOICE_EVENT)
        assert second.status_code == 200

        with SessionLocal() as db:
            events = db.query(ProviderDocumentEvent).filter(
                ProviderDocumentEvent.external_transaction_id == "ABCD1234"
            ).all()
            assert len(events) == 1
            sale = db.query(Sale).filter(Sale.external_id == "ABCD1234").one()
            saved_events = db.query(SaleEvent).filter(
                SaleEvent.sale_id == sale.id, SaleEvent.event_type == SaleEventType.DOCUMENT_ISSUED
            ).all()
            assert len(saved_events) == 1

    def test_invoice_cannot_be_matched_to_another_businesss_sale(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection_a = _create_grow_connection(client).json()
        _post_grow_event(client, connection_a["webhook_path"], GROW_REGULAR_PAYMENT)

        client.cookies.set("sydney_access", "owner-b")
        connection_b = _create_grow_connection(client).json()
        # Same transactionCode, but a different business's own connection —
        # must queue as pending, never reach across to business-a's sale.
        invoice = _post_grow_event(client, connection_b["webhook_path"], GROW_INVOICE_EVENT)
        assert invoice.status_code == 202
        assert invoice.json()["sale_id"] is None

        with SessionLocal() as db:
            db.info["business_id"] = "business-a"
            sale = db.query(Sale).filter(Sale.external_id == "ABCD1234").one()
            assert sale.document_status == DocumentStatus.WAITING_AUTOMATIC

    def test_invoice_cannot_be_matched_to_another_connections_sale(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection_1 = _create_grow_connection(client, name="קופה 1").json()
        connection_2 = _create_grow_connection(client, name="קופה 2").json()

        _post_grow_event(client, connection_1["webhook_path"], GROW_REGULAR_PAYMENT)
        # Same transactionCode, but a different connection of the SAME
        # business — must not attach to connection_1's sale.
        invoice = _post_grow_event(client, connection_2["webhook_path"], GROW_INVOICE_EVENT)
        assert invoice.status_code == 202
        assert invoice.json()["sale_id"] is None

        with SessionLocal() as db:
            sale = db.query(Sale).filter(Sale.external_id == "ABCD1234").one()
            assert sale.document_status == DocumentStatus.WAITING_AUTOMATIC

    def test_missing_invoice_url_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        payload = {"transactionCode": "ABCD1234", "invoiceNumber": "20"}
        response = _post_grow_event(client, connection["webhook_path"], payload)
        assert response.status_code == 422
        with SessionLocal() as db:
            assert db.query(ProviderDocumentEvent).count() == 0

    def test_non_https_invoice_url_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        payload = {**GROW_INVOICE_EVENT, "invoiceUrl": "http://secure.meshulam.co.il"}
        response = _post_grow_event(client, connection["webhook_path"], payload)
        assert response.status_code == 422
        with SessionLocal() as db:
            assert db.query(ProviderDocumentEvent).count() == 0

    def test_oversized_invoice_url_is_rejected(self, client, secured_businesses):
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        payload = {**GROW_INVOICE_EVENT, "invoiceUrl": "https://secure.meshulam.co.il/" + ("a" * 3000)}
        response = _post_grow_event(client, connection["webhook_path"], payload)
        assert response.status_code == 422
        with SessionLocal() as db:
            assert db.query(ProviderDocumentEvent).count() == 0

    def test_fresh_waiting_automatic_sale_is_not_in_the_exception_center(self, client, secured_businesses):
        # A recent paymentDate — GROW_REGULAR_PAYMENT's fixed 2021 date is
        # already (correctly) past any reasonable grace period, so this
        # test needs its own recent one.
        today = datetime.utcnow()
        recent_payload = {**GROW_REGULAR_PAYMENT, "paymentDate": today.strftime("%-d/%-m/%y")}
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        _post_grow_event(client, connection["webhook_path"], recent_payload)

        response = client.get("/api/exceptions")
        assert response.status_code == 200
        body = response.json()
        assert body["attention_count"] == 0
        assert body["document_failures"] == []
        assert body["pending_documents"] == []

    def test_waiting_automatic_sale_past_the_grace_period_is_surfaced(self, client, secured_businesses):
        # GROW_REGULAR_PAYMENT's fixed 2021 paymentDate is already years
        # past the grace period — no manipulation needed.
        client.cookies.set("sydney_access", "owner-a")
        connection = _create_grow_connection(client).json()
        payment = _post_grow_event(client, connection["webhook_path"], GROW_REGULAR_PAYMENT)
        sale_id = payment.json()["sale_id"]

        response = client.get("/api/exceptions")
        assert response.status_code == 200
        body = response.json()
        assert body["attention_count"] == 1
        assert [s["id"] for s in body["document_failures"]] == [sale_id]
