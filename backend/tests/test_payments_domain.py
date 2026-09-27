"""Pure-domain tests for the inactive payment foundation: state machine,
money/currency validation, card-data guards, provider registry, fake
provider, schemas and the guarantee that no route is registered."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.payments.currency import CurrencyError, normalize_currency, to_major_units, validate_amount_minor
from app.payments.permissions import PaymentAction, PaymentActor, is_allowed
from app.payments.providers.base import PaymentProviderAdapter, WebhookVerificationError
from app.payments.providers.fake import FakePaymentProvider
from app.payments.providers.registry import (
    PaymentProviderRegistry,
    ProviderNotAllowedError,
    UnknownProviderError,
    build_default_registry,
)
from app.payments.schemas import CreatePaymentIntentRequest, CreateRefundRequest
from app.payments.sensitive_data import FORBIDDEN_FIELD_NAMES, contains_card_like_number, safe_error_message
from app.payments.state_machine import (
    PAYMENT_TRANSITIONS,
    TERMINAL_PAYMENT_STATUSES,
    InvalidTransitionError,
    PaymentStatus as S,
    RefundStatus as R,
    check_payment_transition,
    check_refund_transition,
)
from app.payments.urls import validate_checkout_url
from app.payments.errors import UntrustedCheckoutUrlError

SECRET = b"s" * 32


# ------------------------------------------------------------- state machine
@pytest.mark.parametrize("current,target", [
    (S.CREATED, S.PENDING), (S.CREATED, S.CAPTURED), (S.PENDING, S.REQUIRES_ACTION), (S.REQUIRES_ACTION, S.PENDING),
    (S.PENDING, S.AUTHORIZED), (S.AUTHORIZED, S.CAPTURED), (S.AUTHORIZED, S.CANCELLED), (S.PENDING, S.EXPIRED),
    (S.CAPTURED, S.PARTIALLY_REFUNDED), (S.CAPTURED, S.REFUNDED), (S.PARTIALLY_REFUNDED, S.REFUNDED),
    (S.REQUIRES_ACTION, S.FAILED),
])
def test_allowed_transitions(current, target):
    assert check_payment_transition(current, target) is True


@pytest.mark.parametrize("current,target", [
    (S.CAPTURED, S.PENDING), (S.CAPTURED, S.AUTHORIZED), (S.CAPTURED, S.FAILED), (S.CAPTURED, S.CANCELLED),
    (S.AUTHORIZED, S.PENDING), (S.REFUNDED, S.CAPTURED), (S.REFUNDED, S.PARTIALLY_REFUNDED),
    (S.PARTIALLY_REFUNDED, S.CAPTURED), (S.FAILED, S.PENDING), (S.CANCELLED, S.CAPTURED), (S.EXPIRED, S.PENDING),
    (S.PENDING, S.CREATED), (S.CREATED, S.REFUNDED),
])
def test_backward_and_invalid_transitions_are_rejected(current, target):
    with pytest.raises(InvalidTransitionError):
        check_payment_transition(current, target)


def test_repeating_the_current_status_is_an_idempotent_no_op():
    for status in S:
        assert check_payment_transition(status, status) is False


def test_terminal_statuses_have_no_exits():
    assert TERMINAL_PAYMENT_STATUSES == {S.FAILED, S.CANCELLED, S.EXPIRED, S.REFUNDED}
    assert set(PAYMENT_TRANSITIONS) == set(S)


def test_refund_state_machine():
    assert check_refund_transition(R.PENDING, R.SUCCEEDED)
    assert check_refund_transition(R.PENDING, R.FAILED)
    assert check_refund_transition(R.SUCCEEDED, R.SUCCEEDED) is False
    for current, target in [(R.SUCCEEDED, R.FAILED), (R.FAILED, R.SUCCEEDED), (R.SUCCEEDED, R.PENDING)]:
        with pytest.raises(InvalidTransitionError):
            check_refund_transition(current, target)


# ------------------------------------------------------- currency and amounts
def test_currency_normalization_and_rejection():
    assert normalize_currency("ils") == "ILS"
    for bad in ["XXX", "US", "USDD", "12A", "", "ש״ח", None, 376]:
        with pytest.raises(CurrencyError):
            normalize_currency(bad)


@pytest.mark.parametrize("bad", [0, -1, 1_000_000_000_001, True, False, 10.5, "100", None])
def test_amounts_must_be_positive_bounded_integers(bad):
    with pytest.raises(CurrencyError):
        validate_amount_minor(bad)


def test_minor_units_follow_the_currency_exponent():
    assert str(to_major_units(1050, "ILS")) == "10.50"
    assert str(to_major_units(1050, "JPY")) == "1050"
    assert str(to_major_units(1050, "JOD")) == "1.050"


def _valid_request(**overrides):
    body = {"external_reference": "order-1", "provider": "fake", "amount_minor": 1000, "currency": "ils",
            "description": "Haircut"}
    body.update(overrides)
    return body


def test_schema_accepts_a_valid_request_and_normalizes_currency():
    assert CreatePaymentIntentRequest(**_valid_request()).currency == "ILS"


@pytest.mark.parametrize("override", [
    {"amount_minor": "1000"}, {"amount_minor": 10.0}, {"amount_minor": True}, {"amount_minor": 0},
    {"currency": "ZZZ"}, {"external_reference": "has space"}, {"external_reference": "x" * 65},
    {"description": ""}, {"description": "x" * 256}, {"provider": "Fake!"},
])
def test_schema_rejects_invalid_values(override):
    with pytest.raises(ValidationError):
        CreatePaymentIntentRequest(**_valid_request(**override))


# ------------------------------------------------------------ card data guards
@pytest.mark.parametrize("field", ["card_number", "cvv", "pan", "expiry", "track2", "iban"])
def test_schemas_reject_unknown_and_card_fields(field):
    with pytest.raises(ValidationError) as error:
        CreatePaymentIntentRequest(**_valid_request(**{field: "4242424242424242"}))
    assert "extra_forbidden" in str(error.value)
    with pytest.raises(ValidationError):
        CreateRefundRequest(**{field: "123"})


def test_no_request_schema_declares_a_sensitive_field():
    for schema in (CreatePaymentIntentRequest, CreateRefundRequest):
        assert not set(schema.model_fields) & FORBIDDEN_FIELD_NAMES


@pytest.mark.parametrize("text,expected", [
    ("4242 4242 4242 4242", True), ("pay 4111-1111-1111-1111 now", True), ("5555555555554444", True),
    ("4242424242424241", False), ("order 1234567", False), ("phone 0501234567", False), (None, False),
])
def test_card_number_detection(text, expected):
    assert contains_card_like_number(text) is expected


def test_free_text_containing_a_card_number_is_rejected():
    with pytest.raises(ValidationError):
        CreatePaymentIntentRequest(**_valid_request(description="card 4242 4242 4242 4242"))
    with pytest.raises(ValidationError):
        CreateRefundRequest(reason="refund to 4111111111111111")


def test_safe_error_message_masks_card_numbers():
    message = safe_error_message(RuntimeError("declined 4242424242424242 for order 55"))
    assert "4242424242424242" not in message and "[redacted]" in message and "order 55" in message


# ---------------------------------------------------------- checkout URL trust
@pytest.mark.parametrize("url", [
    "http://checkout.fake-provider.test/pay", "https://evil.test/pay", "https://checkout.fake-provider.test.evil.test/",
    "https://user:pass@checkout.fake-provider.test/", "https://checkout.fake-provider.test:8443/",
    "javascript:alert(1)", "https://checkout.fake-provider.test/\npay", "", "https://" + "a" * 2050,
])
def test_untrusted_checkout_urls_are_rejected(url):
    with pytest.raises(UntrustedCheckoutUrlError):
        validate_checkout_url(url, frozenset({"checkout.fake-provider.test"}))


def test_trusted_checkout_url_is_accepted():
    url = "https://CHECKOUT.fake-provider.test/pay/abc?x=1"
    assert validate_checkout_url(url, frozenset({"checkout.fake-provider.test"})) == url


# -------------------------------------------------------- providers / registry
def test_fake_provider_refuses_to_exist_in_production():
    with pytest.raises(RuntimeError):
        FakePaymentProvider(environment="production", webhook_secret=SECRET)


def test_fake_provider_requires_a_real_secret():
    with pytest.raises(ValueError):
        FakePaymentProvider(environment="development", webhook_secret=b"short")


def test_production_registry_rejects_test_only_adapters():
    provider = FakePaymentProvider(environment="development", webhook_secret=SECRET)
    registry = PaymentProviderRegistry("production")
    with pytest.raises(ProviderNotAllowedError):
        registry.register(provider)
    with pytest.raises(UnknownProviderError):
        registry.get("fake")


def test_default_registry_has_no_real_providers():
    assert build_default_registry("production").names() == []
    assert build_default_registry("development").names() == []


def test_fake_provider_implements_the_adapter_contract():
    assert isinstance(FakePaymentProvider(environment="development", webhook_secret=SECRET), PaymentProviderAdapter)


def test_fake_webhook_verification_rules():
    provider = FakePaymentProvider(environment="development", webhook_secret=SECRET)
    now = datetime(2026, 9, 26, 12, 0, 0)
    ts = int(now.replace(tzinfo=timezone.utc).timestamp())
    body = json.dumps({"id": "evt_1", "type": "payment.captured", "created": ts, "payment_id": "p1"}).encode()
    assert provider.verify_webhook(provider.sign(body, ts), body, now).provider_event_id == "evt_1"

    tampered = body.replace(b"p1", b"p2")
    with pytest.raises(WebhookVerificationError):
        provider.verify_webhook(provider.sign(body, ts), tampered, now)
    with pytest.raises(WebhookVerificationError):
        provider.verify_webhook({}, body, now)
    with pytest.raises(WebhookVerificationError):  # replayed outside the freshness window
        provider.verify_webhook(provider.sign(body, ts), body, now + timedelta(minutes=6))
    extra = json.dumps({"id": "e", "type": "payment.captured", "created": ts, "payment_id": "p", "card_number": "1"}).encode()
    with pytest.raises(WebhookVerificationError):
        provider.verify_webhook(provider.sign(extra, ts), extra, now)


# ----------------------------------------------------------------- permissions
@pytest.mark.parametrize("business_role,system_role,allowed", [
    ("owner", "user", {"view", "create", "cancel", "refund"}),
    ("manager", "user", {"view", "create"}),
    ("viewer", "user", {"view"}),
    (None, "support", set()),
    ("owner", "support", set()),
    (None, "admin", {"admin_view"}),
    (None, "superadmin", {"admin_view"}),
    ("owner", "superadmin", {"view", "create", "cancel", "refund", "admin_view"}),
    (None, "user", set()),
    ("unknown", "user", set()),
])
def test_permission_matrix(business_role, system_role, allowed):
    actor = PaymentActor(user_id="u", business_id="b", business_role=business_role, system_role=system_role)
    assert {action.value for action in PaymentAction if is_allowed(actor, action)} == allowed


# ---------------------------------------------------------- inactive routing
def test_payments_router_is_not_registered_on_the_application():
    from app.main import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any(path.startswith("/api/payments") for path in paths)
    backend = Path(__file__).resolve().parent.parent
    for source in ("app/main.py", "app/api/router.py", "app/models/__init__.py"):
        assert "payments" not in (backend / source).read_text() or "app.payments" not in (backend / source).read_text()
    assert "INTENTIONALLY INACTIVE" in (backend / "app/payments/router.py").read_text()
