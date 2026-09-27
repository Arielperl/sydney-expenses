"""Service-level tests for the inactive payment foundation, against real
database sessions scoped exactly like request sessions (app.core.tenant).

They run on the suite's SQLite database, and additionally on PostgreSQL when
PAYMENTS_TEST_POSTGRES_URL points at a local, disposable database (real row
locks and enforced foreign keys). Never point that at a shared database: the
tables are dropped and recreated for every test."""

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.core import tenant  # noqa: F401 - registers the tenant guards, as get_db does
from app.database import Base, SessionLocal
from app.models.business import Business
from app.payments import service as service_module
from app.payments.errors import (
    ConcurrentUpdateError,
    DuplicateExternalReferenceError,
    IdempotencyConflictError,
    PaymentNotFoundError,
    PaymentStateError,
    PaymentValidationError,
    RefundLimitExceededError,
    UntrustedCheckoutUrlError,
)
from app.payments.models import (
    AuditImmutableError,
    PaymentAuditEvent,
    PaymentIntent,
    PaymentRefund,
    PaymentWebhookEvent,
    WebhookProcessingStatus,
)
from app.payments.permissions import PaymentActor, PaymentPermissionError
from app.payments.providers.base import (
    ProviderError,
    ProviderPaymentResult,
    ProviderPaymentState,
    WebhookVerificationError,
)
from app.payments.providers.fake import FakePaymentProvider
from app.payments.providers.registry import PaymentProviderRegistry
from app.payments.service import CreatePaymentIntentInput, PaymentService
from app.payments.state_machine import PaymentStatus, RefundStatus

A, B = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
SECRET = b"k" * 32
NOW = datetime(2026, 9, 26, 12, 0, 0)


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


BACKENDS = ["sqlite"] + (["postgresql"] if os.environ.get("PAYMENTS_TEST_POSTGRES_URL") else [])
CURRENT = {"factory": SessionLocal, "dialect": "sqlite"}


@pytest.fixture(params=BACKENDS, autouse=True)
def database(request):
    if request.param == "sqlite":
        CURRENT.update(factory=SessionLocal, dialect="sqlite")
        yield
        return
    url = os.environ["PAYMENTS_TEST_POSTGRES_URL"]
    assert "localhost" in url or "127.0.0.1" in url, "Only a local, disposable PostgreSQL may be used"
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    CURRENT.update(factory=sessionmaker(bind=engine, autoflush=False), dialect="postgresql")
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()
    CURRENT.update(factory=SessionLocal, dialect="sqlite")


def new_session():
    return CURRENT["factory"]()


@pytest.fixture
def world():
    with new_session() as db:
        db.add_all([Business(id=A, name="Alpha"), Business(id=B, name="Beta")])
        db.commit()
    provider = FakePaymentProvider(environment="development", webhook_secret=SECRET)
    registry = PaymentProviderRegistry("development")
    registry.register(provider)
    clock = Clock()
    sessions = []

    def make(business_id=A):
        db = new_session()
        db.info["business_id"] = business_id  # exactly what get_db does for a request
        sessions.append(db)
        return PaymentService(db, registry, clock=clock)

    yield {"provider": provider, "registry": registry, "clock": clock, "service": make}
    for db in sessions:
        db.close()


def owner(business_id=A, user="owner-a"):
    return PaymentActor(user_id=user, business_id=business_id, business_role="owner")


def intent_input(**overrides):
    values = {"external_reference": "order-1", "provider": "fake", "amount_minor": 10_000, "currency": "ILS",
              "description": "Laser treatment", "idempotency_key": "idem-key-0001"}
    values.update(overrides)
    return CreatePaymentIntentInput(**values)


def webhook(world, *, event_id, event_type, payment_id, business=A, **fields):
    ts = int(world["clock"].now.replace(tzinfo=timezone.utc).timestamp())
    body = json.dumps({"id": event_id, "type": event_type, "created": ts, "payment_id": payment_id, **fields}).encode()
    return world["service"](business).receive_webhook(business, "fake", world["provider"].sign(body, ts), body)


def captured_intent(world, *, amount=10_000, reference="order-1", key="idem-key-0001"):
    service = world["service"]()
    intent = service.create_payment_intent(owner(), intent_input(amount_minor=amount, external_reference=reference, idempotency_key=key))
    intent = service.request_checkout(owner(), intent.id)
    outcome = webhook(world, event_id=f"evt-cap-{intent.id}", event_type="payment.captured",
                      payment_id=intent.provider_payment_id, amount_minor=amount, currency="ILS")
    assert outcome.event.status == WebhookProcessingStatus.PROCESSED
    return world["service"]().get_payment(owner(), intent.id)


def rows(model, business_id=A, **filters):
    with new_session() as db:
        statement = select(model).where(model.business_id == business_id)
        for key, value in filters.items():
            statement = statement.where(getattr(model, key) == value)
        return list(db.scalars(statement))


# ------------------------------------------------------------------ creation
def test_create_payment_intent_records_status_and_audit(world):
    intent = world["service"]().create_payment_intent(owner(), intent_input())
    assert intent.status == PaymentStatus.CREATED and intent.amount_minor == 10_000 and intent.version == 1
    audit = rows(PaymentAuditEvent, payment_intent_id=intent.id)
    assert [(a.from_status, a.to_status, a.source.value, a.actor_user_id) for a in audit] == [(None, "created", "api", "owner-a")]


def test_idempotent_creation_returns_the_same_intent(world):
    first = world["service"]().create_payment_intent(owner(), intent_input())
    again = world["service"]().create_payment_intent(owner(), intent_input())
    assert again.id == first.id
    assert len(rows(PaymentIntent)) == 1 and len(rows(PaymentAuditEvent)) == 1


def test_reusing_an_idempotency_key_with_different_parameters_is_a_conflict(world):
    world["service"]().create_payment_intent(owner(), intent_input())
    with pytest.raises(IdempotencyConflictError):
        world["service"]().create_payment_intent(owner(), intent_input(amount_minor=20_000))


def test_idempotency_keys_are_scoped_per_business(world):
    a = world["service"](A).create_payment_intent(owner(A), intent_input())
    b = world["service"](B).create_payment_intent(owner(B, "owner-b"), intent_input())
    assert a.id != b.id


def test_concurrent_creation_with_one_key_creates_one_intent(world, monkeypatch):
    barrier = threading.Barrier(2, timeout=10)
    original = PaymentService._existing

    def racing_existing(self, model, business_id, key):
        found = original(self, model, business_id, key)
        if model is PaymentIntent and found is None and not getattr(threading.current_thread(), "passed", False):
            threading.current_thread().passed = True
            barrier.wait()  # both requests have now checked and found nothing
        return found

    monkeypatch.setattr(PaymentService, "_existing", racing_existing)
    results, failures = [], []

    def run():
        try:
            results.append(world["service"]().create_payment_intent(owner(), intent_input()).id)
        except Exception as error:  # pragma: no cover - reported below
            failures.append(error)

    threads = [threading.Thread(target=run) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not failures and len(set(results)) == 1 and len(rows(PaymentIntent)) == 1


def test_a_second_live_intent_for_the_same_reference_is_blocked(world):
    first = world["service"]().create_payment_intent(owner(), intent_input())
    with pytest.raises(DuplicateExternalReferenceError):
        world["service"]().create_payment_intent(owner(), intent_input(idempotency_key="idem-key-0002"))
    world["service"]().cancel_payment(owner(), first.id)
    retry = world["service"]().create_payment_intent(owner(), intent_input(idempotency_key="idem-key-0003"))
    assert retry.id != first.id


@pytest.mark.parametrize("override", [
    {"amount_minor": 0}, {"amount_minor": True}, {"amount_minor": 12.5}, {"currency": "ZZZ"},
    {"description": "card 4242 4242 4242 4242"}, {"customer_reference": "4111111111111111"},
    {"external_reference": "bad ref"}, {"idempotency_key": "short"}, {"provider": "grow"},
    {"expires_at": NOW - timedelta(minutes=1)}, {"expires_at": NOW + timedelta(days=31)},
])
def test_service_validates_inputs_itself(world, override):
    with pytest.raises((PaymentValidationError, Exception)) as error:
        world["service"]().create_payment_intent(owner(), intent_input(**override))
    assert not rows(PaymentIntent)
    assert error.type.__name__ in {"PaymentValidationError", "UnknownProviderError"}


# --------------------------------------------------------- tenant isolation
def test_other_businesses_cannot_see_or_act_on_a_payment(world):
    intent = captured_intent(world)
    other = owner(B, "owner-b")
    service_b = world["service"](B)
    for call in (
        lambda: service_b.get_payment(other, intent.id),
        lambda: service_b.cancel_payment(other, intent.id),
        lambda: service_b.create_refund(other, intent.id, idempotency_key="refund-key-1"),
        lambda: service_b.audit_trail(other, intent.id),
    ):
        with pytest.raises(PaymentNotFoundError):
            call()
    assert service_b.list_payment_intents(other) == []
    assert [p.id for p in world["service"](A).list_payment_intents(owner())] == [intent.id]


def test_a_session_scoped_to_one_business_refuses_another_businesses_actor(world):
    with pytest.raises(PaymentPermissionError):
        world["service"](A).list_payment_intents(owner(B, "owner-b"))


def test_webhook_for_another_businesses_payment_is_not_applied(world):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    outcome = webhook(world, business=B, event_id="evt-x", event_type="payment.captured", payment_id=intent.provider_payment_id)
    assert outcome.event.status == WebhookProcessingStatus.IGNORED
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.PENDING


# ------------------------------------------------------------- permissions
@pytest.mark.parametrize("role,system_role,can_create,can_cancel,can_refund,can_view", [
    ("owner", "user", True, True, True, True),
    ("manager", "user", True, False, False, True),
    ("viewer", "user", False, False, False, True),
    (None, "support", False, False, False, False),
    (None, "admin", False, False, False, False),
    (None, "superadmin", False, False, False, False),
])
def test_role_permissions_are_enforced_by_the_service(world, role, system_role, can_create, can_cancel, can_refund, can_view):
    intent = captured_intent(world)
    actor = PaymentActor(user_id="someone", business_id=A, business_role=role, system_role=system_role)
    service = world["service"]()
    outcomes = {}
    for name, call in {
        "create": lambda: service.create_payment_intent(actor, intent_input(external_reference="order-2", idempotency_key="idem-key-0009")),
        "cancel": lambda: service.cancel_payment(actor, intent.id),
        "refund": lambda: service.create_refund(actor, intent.id, idempotency_key="refund-key-1", amount_minor=100),
        "view": lambda: service.get_payment(actor, intent.id),
    }.items():
        try:
            call()
            outcomes[name] = True
        except PaymentPermissionError:
            outcomes[name] = False
        except (PaymentStateError, RefundLimitExceededError):
            outcomes[name] = True  # authorized, then refused for a business reason
    assert outcomes == {"create": can_create, "cancel": can_cancel, "refund": can_refund, "view": can_view}


def test_platform_admins_get_counts_only(world):
    captured_intent(world)
    service = world["service"]()
    admin = PaymentActor(user_id="adm", business_id="", business_role=None, system_role="superadmin")
    assert service.admin_status_counts(admin, A) == {"captured": 1}
    with pytest.raises(PaymentPermissionError):
        service.admin_status_counts(PaymentActor(user_id="s", business_id="", business_role=None, system_role="support"), A)


# ------------------------------------------------------------------ checkout
def test_checkout_moves_to_pending_with_a_trusted_url(world):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    assert intent.status == PaymentStatus.PENDING
    assert intent.checkout_url.startswith("https://checkout.fake-provider.test/")
    again = world["service"]().request_checkout(owner(), intent.id)
    assert again.provider_payment_id == intent.provider_payment_id


def test_synchronous_capture_records_the_captured_amount(world, monkeypatch):
    service = world["service"]()
    intent = service.create_payment_intent(owner(), intent_input())

    def capture_now(request):
        return ProviderPaymentResult(
            provider_payment_id="pay-sync-1",
            status=PaymentStatus.CAPTURED,
            captured_minor=request.amount_minor,
        )

    monkeypatch.setattr(world["provider"], "create_payment", capture_now)
    captured = service.request_checkout(owner(), intent.id)
    assert captured.status == PaymentStatus.CAPTURED
    assert captured.captured_minor == captured.amount_minor == 10_000


def test_synchronous_capture_without_an_amount_is_rejected(world, monkeypatch):
    service = world["service"]()
    intent = service.create_payment_intent(owner(), intent_input())
    monkeypatch.setattr(
        world["provider"],
        "create_payment",
        lambda _request: ProviderPaymentResult(provider_payment_id="pay-bad", status=PaymentStatus.CAPTURED),
    )
    with pytest.raises(PaymentValidationError):
        service.request_checkout(owner(), intent.id)
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.CREATED


def test_untrusted_checkout_url_is_rejected_and_rolled_back(world):
    service = world["service"]()
    intent = service.create_payment_intent(owner(), intent_input())
    world["provider"].checkout_url_override = "https://evil.example/phish"
    with pytest.raises(UntrustedCheckoutUrlError):
        service.request_checkout(owner(), intent.id)
    fresh = world["service"]().get_payment(owner(), intent.id)
    assert fresh.status == PaymentStatus.CREATED and fresh.checkout_url is None and fresh.provider_payment_id is None
    assert len(rows(PaymentAuditEvent, payment_intent_id=intent.id)) == 1


def test_provider_failure_during_checkout_leaves_nothing_behind(world):
    service = world["service"]()
    intent = service.create_payment_intent(owner(), intent_input())
    world["provider"].fail_next["create_payment"] = ProviderError("timeout", retryable=True)
    with pytest.raises(ProviderError):
        service.request_checkout(owner(), intent.id)
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.CREATED
    # The same intent id is the provider idempotency key, so retrying is safe.
    assert world["service"]().request_checkout(owner(), intent.id).status == PaymentStatus.PENDING


def test_cancel_is_rolled_back_when_the_provider_fails(world):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    world["provider"].fail_next["cancel_payment"] = ProviderError("provider down", retryable=True)
    with pytest.raises(ProviderError):
        service.cancel_payment(owner(), intent.id)
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.PENDING
    assert world["service"]().cancel_payment(owner(), intent.id).status == PaymentStatus.CANCELLED
    with pytest.raises(PaymentStateError):
        captured = captured_intent(world, reference="order-9", key="idem-key-0099")
        world["service"]().cancel_payment(owner(), captured.id)


def test_cancel_requires_provider_confirmation(world, monkeypatch):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    monkeypatch.setattr(
        world["provider"],
        "cancel_payment",
        lambda payment_id: ProviderPaymentState(payment_id, PaymentStatus.PENDING),
    )
    with pytest.raises(PaymentStateError, match="did not confirm"):
        service.cancel_payment(owner(), intent.id)
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.PENDING


# ------------------------------------------------------------------ webhooks
def test_verified_capture_event_updates_the_payment_through_the_state_machine(world):
    intent = captured_intent(world)
    assert intent.status == PaymentStatus.CAPTURED and intent.captured_minor == 10_000
    trail = [(a.from_status, a.to_status, a.source.value) for a in world["service"]().audit_trail(owner(), intent.id)]
    assert trail == [(None, "created", "api"), ("created", "pending", "api"), ("pending", "captured", "provider_event")]


def test_duplicate_webhook_delivery_is_idempotent(world):
    intent = captured_intent(world)
    outcome = webhook(world, event_id=f"evt-cap-{intent.id}", event_type="payment.captured",
                      payment_id=intent.provider_payment_id, amount_minor=10_000, currency="ILS")
    assert outcome.duplicate is True
    assert len(rows(PaymentWebhookEvent)) == 1
    assert len(rows(PaymentAuditEvent, payment_intent_id=intent.id)) == 3
    # A different event id carrying the same status is recorded but changes nothing.
    repeat = webhook(world, event_id="evt-cap-again", event_type="payment.captured",
                     payment_id=intent.provider_payment_id, amount_minor=10_000, currency="ILS")
    assert repeat.event.status == WebhookProcessingStatus.PROCESSED
    assert len(rows(PaymentAuditEvent, payment_intent_id=intent.id)) == 3


def test_redelivery_recovers_an_event_left_received_after_a_worker_stops(world, monkeypatch):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    original = PaymentService._process_inbox

    def stopped_after_durable_insert(self, inbox):
        raise RuntimeError("worker stopped")

    monkeypatch.setattr(PaymentService, "_process_inbox", stopped_after_durable_insert)
    with pytest.raises(RuntimeError, match="worker stopped"):
        webhook(world, event_id="evt-recover", event_type="payment.captured",
                payment_id=intent.provider_payment_id, amount_minor=10_000, currency="ILS")
    [stored] = rows(PaymentWebhookEvent)
    assert stored.status == WebhookProcessingStatus.RECEIVED

    monkeypatch.setattr(PaymentService, "_process_inbox", original)
    recovered = webhook(world, event_id="evt-recover", event_type="payment.captured",
                        payment_id=intent.provider_payment_id, amount_minor=10_000, currency="ILS")
    assert recovered.duplicate is True
    assert recovered.event.status == WebhookProcessingStatus.PROCESSED
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.CAPTURED


def test_repeated_capture_with_a_conflicting_amount_is_ignored(world):
    intent = captured_intent(world)
    outcome = webhook(world, event_id="evt-conflicting-capture", event_type="payment.captured",
                      payment_id=intent.provider_payment_id, amount_minor=9_000, currency="ILS")
    assert outcome.event.status == WebhookProcessingStatus.IGNORED
    assert "conflicts" in outcome.event.last_error
    assert world["service"]().get_payment(owner(), intent.id).captured_minor == 10_000


def test_oversized_provider_event_identifier_is_rejected_instead_of_truncated(world):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    with pytest.raises(WebhookVerificationError, match="invalid identifiers"):
        webhook(world, event_id="e" * 256, event_type="payment.captured",
                payment_id=intent.provider_payment_id, amount_minor=10_000, currency="ILS")
    assert rows(PaymentWebhookEvent) == []


def test_unverified_webhooks_are_rejected_and_never_stored(world, caplog):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    ts = int(NOW.replace(tzinfo=timezone.utc).timestamp())
    body = json.dumps({"id": "evt-forged", "type": "payment.captured", "created": ts, "payment_id": intent.provider_payment_id}).encode()
    forged = {"X-Fake-Signature": "0" * 64, "X-Fake-Timestamp": str(ts), "Authorization": "Bearer secret-token"}
    with caplog.at_level(logging.DEBUG, logger="app.payments"):
        with pytest.raises(WebhookVerificationError):
            world["service"]().receive_webhook(A, "fake", forged, body)
    assert rows(PaymentWebhookEvent) == []
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.PENDING
    logged = caplog.text
    assert "secret-token" not in logged and "0" * 64 not in logged and "evt-forged" not in logged


def test_replayed_old_delivery_is_rejected(world):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    ts = int((NOW - timedelta(hours=1)).replace(tzinfo=timezone.utc).timestamp())
    body = json.dumps({"id": "evt-old", "type": "payment.captured", "created": ts, "payment_id": intent.provider_payment_id}).encode()
    with pytest.raises(WebhookVerificationError):
        world["service"]().receive_webhook(A, "fake", world["provider"].sign(body, ts), body)


def test_out_of_order_events_are_recorded_but_do_not_move_status_backwards(world):
    intent = captured_intent(world)
    outcome = webhook(world, event_id="evt-late-pending", event_type="payment.pending", payment_id=intent.provider_payment_id)
    assert outcome.event.status == WebhookProcessingStatus.IGNORED
    assert "Out-of-order" in outcome.event.last_error
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.CAPTURED


@pytest.mark.parametrize("fields", [{"amount_minor": 99_999}, {"currency": "USD"}, {"amount_minor": 0}])
def test_capture_events_with_mismatched_money_are_not_applied(world, fields):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    outcome = webhook(world, event_id="evt-bad", event_type="payment.captured", payment_id=intent.provider_payment_id, **fields)
    assert outcome.event.status == WebhookProcessingStatus.IGNORED
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.PENDING


def test_inbox_stores_only_a_redacted_summary(world):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    webhook(world, event_id="evt-fail", event_type="payment.failed", payment_id=intent.provider_payment_id,
            failure_reason="card 4242424242424242 declined")
    [stored] = rows(PaymentWebhookEvent)
    assert "4242424242424242" not in json.dumps(stored.payload_summary)
    assert set(stored.payload_summary) == {"event_type", "occurred_at", "provider_payment_id", "amount_minor",
                                           "currency", "provider_refund_id", "failure_reason"}


def test_transient_processing_failure_is_recorded_and_retried(world, monkeypatch):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    original = PaymentService._apply_event
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("UPDATE payment_intents", {}, Exception("database is locked"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PaymentService, "_apply_event", flaky)
    outcome = webhook(world, event_id="evt-flaky", event_type="payment.captured", payment_id=intent.provider_payment_id)
    assert outcome.event.status == WebhookProcessingStatus.FAILED
    assert outcome.event.attempt_count == 1 and "OperationalError" in outcome.event.last_error
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.PENDING
    retried = world["service"]().retry_webhook_event(A, outcome.event.id)
    assert retried.status == WebhookProcessingStatus.PROCESSED and retried.attempt_count == 2
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.CAPTURED


def test_redelivery_of_a_failed_event_retries_it(world, monkeypatch):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    original = PaymentService._apply_event
    state = {"fail": True}

    def flaky(self, *args, **kwargs):
        if state.pop("fail", False):
            raise OperationalError("x", {}, Exception("locked"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PaymentService, "_apply_event", flaky)
    webhook(world, event_id="evt-r", event_type="payment.authorized", payment_id=intent.provider_payment_id)
    outcome = webhook(world, event_id="evt-r", event_type="payment.authorized", payment_id=intent.provider_payment_id)
    assert outcome.duplicate and outcome.event.status == WebhookProcessingStatus.PROCESSED
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.AUTHORIZED


# ------------------------------------------------------------------- refunds
def test_partial_then_full_refund(world):
    intent = captured_intent(world)
    first = world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", amount_minor=3_000, reason="Partial")
    assert first.status == RefundStatus.SUCCEEDED
    assert world["service"]().get_payment(owner(), intent.id).status == PaymentStatus.PARTIALLY_REFUNDED
    rest = world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-2")
    assert rest.amount_minor == 7_000
    final = world["service"]().get_payment(owner(), intent.id)
    assert final.status == PaymentStatus.REFUNDED and final.refunded_minor == 10_000 == final.refund_reserved_minor


def test_over_refund_is_prevented(world):
    intent = captured_intent(world)
    world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", amount_minor=6_000)
    with pytest.raises(RefundLimitExceededError):
        world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-2", amount_minor=4_001)
    with pytest.raises(RefundLimitExceededError):
        world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-3", amount_minor=20_000)
    assert world["service"]().get_payment(owner(), intent.id).refunded_minor == 6_000


def test_refund_requires_a_captured_payment(world):
    service = world["service"]()
    intent = service.request_checkout(owner(), service.create_payment_intent(owner(), intent_input()).id)
    with pytest.raises(PaymentStateError):
        world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1")


def test_refund_idempotency(world):
    intent = captured_intent(world)
    first = world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", amount_minor=1_000)
    again = world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", amount_minor=1_000)
    assert again.id == first.id and len(rows(PaymentRefund)) == 1
    with pytest.raises(IdempotencyConflictError):
        world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", amount_minor=2_000)
    assert [c for c in world["provider"].calls if c[0] == "refund_payment"] == [("refund_payment", first.id)]


def test_declined_refund_releases_its_reservation(world):
    intent = captured_intent(world)
    world["provider"].fail_next["refund_payment"] = ProviderError("refund declined", retryable=False)
    with pytest.raises(ProviderError):
        world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", amount_minor=5_000)
    [refund] = rows(PaymentRefund)
    assert refund.status == RefundStatus.FAILED and "declined" in refund.failure_reason
    fresh = world["service"]().get_payment(owner(), intent.id)
    assert fresh.refund_reserved_minor == 0 and fresh.status == PaymentStatus.CAPTURED


def test_commit_failure_after_provider_refund_is_recovered_without_a_second_refund(world, monkeypatch):
    intent = captured_intent(world)
    real_commit = PaymentService._commit
    state = {"fail": True}

    def failing_commit(self):
        if state.pop("fail", False):
            self.db.rollback()
            raise OperationalError("COMMIT", {}, Exception("connection lost"))
        return real_commit(self)

    monkeypatch.setattr(PaymentService, "_commit", failing_commit)
    with pytest.raises(OperationalError):
        world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", amount_minor=4_000)
    [pending] = rows(PaymentRefund)
    assert pending.status == RefundStatus.PENDING
    assert world["service"]().get_payment(owner(), intent.id).refund_reserved_minor == 4_000  # still reserved

    completed = world["service"]().retry_pending_refund(owner(), pending.id)
    assert completed.status == RefundStatus.SUCCEEDED
    refund_calls = [c for c in world["provider"].calls if c[0] == "refund_payment"]
    assert refund_calls == [("refund_payment", pending.id), ("refund_payment", pending.id)]  # same idempotency key
    assert world["service"]().get_payment(owner(), intent.id).refunded_minor == 4_000


def test_pending_refund_completed_by_a_provider_event(world):
    intent = captured_intent(world)
    world["provider"].refund_outcome = RefundStatus.PENDING
    refund = world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", amount_minor=2_500)
    assert refund.status == RefundStatus.PENDING
    outcome = webhook(world, event_id="evt-ref", event_type="refund.succeeded", payment_id=intent.provider_payment_id,
                      refund_id=refund.provider_refund_id)
    assert outcome.event.status == WebhookProcessingStatus.PROCESSED
    fresh = world["service"]().get_payment(owner(), intent.id)
    assert fresh.refunded_minor == 2_500 and fresh.status == PaymentStatus.PARTIALLY_REFUNDED
    late_failure = webhook(world, event_id="evt-ref-2", event_type="refund.failed", payment_id=intent.provider_payment_id,
                           refund_id=refund.provider_refund_id)
    assert late_failure.event.status == WebhookProcessingStatus.IGNORED


def test_concurrent_refunds_cannot_exceed_the_captured_amount(world, monkeypatch):
    intent = captured_intent(world)
    barrier = threading.Barrier(2, timeout=10)
    original = PaymentService._get_intent

    def racing_get(self, business_id, intent_id, *, lock):
        if lock and not getattr(threading.current_thread(), "passed", False):
            threading.current_thread().passed = True
            barrier.wait()  # both refunds start from the same, pre-refund state
        return original(self, business_id, intent_id, lock=lock)

    monkeypatch.setattr(PaymentService, "_get_intent", racing_get)
    results, errors = [], []

    def run(key):
        try:
            results.append(world["service"]().create_refund(owner(), intent.id, idempotency_key=key, amount_minor=7_000))
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=run, args=(f"refund-key-{i}",)) for i in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(results) == 1 and len(errors) == 1
    if CURRENT["dialect"] == "postgresql":
        # FOR UPDATE makes the second refund wait, then re-read the reserved amount.
        assert isinstance(errors[0], RefundLimitExceededError)
    else:
        # SQLite has no row locks: both read the same state, and the second writer's
        # transaction is rejected (stale version / colliding audit sequence), saving nothing.
        assert isinstance(errors[0], ConcurrentUpdateError)
    fresh = world["service"]().get_payment(owner(), intent.id)
    assert fresh.refunded_minor == 7_000 and fresh.refund_reserved_minor == 7_000


def test_database_constraints_forbid_over_refund_even_without_the_service(world):
    intent = captured_intent(world)
    with new_session() as db:
        with pytest.raises(IntegrityError):
            db.execute(update(PaymentIntent).where(PaymentIntent.id == intent.id).values(refund_reserved_minor=10_001))
            db.commit()


# --------------------------------------------------------------------- audit
def test_audit_events_are_immutable(world):
    intent = world["service"]().create_payment_intent(owner(), intent_input())
    with new_session() as db:
        event = db.scalar(select(PaymentAuditEvent).where(PaymentAuditEvent.payment_intent_id == intent.id))
        event.note = "rewritten"
        with pytest.raises(AuditImmutableError):
            db.commit()
        db.rollback()
        with pytest.raises(AuditImmutableError):
            db.delete(db.merge(event))
            db.commit()
        db.rollback()
        with pytest.raises(AuditImmutableError):
            db.execute(update(PaymentAuditEvent).values(note="x"))


def test_expiry_job_expires_only_due_open_payments(world):
    service = world["service"]()
    due = service.create_payment_intent(owner(), intent_input(expires_at=NOW + timedelta(hours=1)))
    later = service.create_payment_intent(owner(), intent_input(external_reference="order-2", idempotency_key="idem-key-0002",
                                                                expires_at=NOW + timedelta(days=2)))
    world["clock"].now = NOW + timedelta(hours=2)
    assert world["service"]().expire_due_payments(A) == 1
    assert world["service"]().get_payment(owner(), due.id).status == PaymentStatus.EXPIRED
    assert world["service"]().get_payment(owner(), later.id).status == PaymentStatus.CREATED


def test_no_raw_sql_bypass_in_a_business_scoped_session(world):
    service = world["service"]()
    with pytest.raises(ValueError):
        service.db.execute(text("SELECT * FROM payment_intents"))


def test_service_module_never_logs_payloads(world, caplog):
    with caplog.at_level(logging.DEBUG, logger="app.payments"):
        intent = captured_intent(world)
        world["service"]().create_refund(owner(), intent.id, idempotency_key="refund-key-1", reason="Customer asked")
    assert "Customer asked" not in caplog.text and SECRET.decode() not in caplog.text
    assert "Laser treatment" not in caplog.text
    assert service_module.logger.name == "app.payments"
