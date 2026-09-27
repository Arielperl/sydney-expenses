"""A deterministic, in-memory provider for tests. NEVER usable in production.

It never talks to a network, never sees card data, and refuses to be
constructed when the environment is production. Its webhook signature scheme
(HMAC-SHA256 over ``"<timestamp>.<body>"`` with a freshness window) exists to
exercise the verification path; it does not describe any real provider.
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from app.payments.providers.base import (
    ProviderCreatePaymentRequest,
    ProviderError,
    ProviderEventType,
    ProviderPaymentResult,
    ProviderPaymentState,
    ProviderRefundRequest,
    ProviderRefundResult,
    VerifiedProviderEvent,
    WebhookVerificationError,
)
from app.payments.state_machine import PaymentStatus, RefundStatus

SIGNATURE_HEADER = "x-fake-signature"
TIMESTAMP_HEADER = "x-fake-timestamp"
MAX_WEBHOOK_BYTES = 16_384
_EVENT_FIELDS = {
    "id", "type", "created", "payment_id", "amount_minor", "currency", "refund_id", "failure_reason",
}


class FakePaymentProvider:
    name = "fake"
    test_only = True
    allowed_checkout_hosts = frozenset({"checkout.fake-provider.test"})

    def __init__(self, *, environment: str, webhook_secret: bytes, tolerance: timedelta = timedelta(minutes=5)):
        if environment == "production":
            raise RuntimeError("FakePaymentProvider is disabled in production")
        if len(webhook_secret) < 32:
            raise ValueError("webhook_secret must be at least 32 bytes")
        self._secret = webhook_secret
        self._tolerance = tolerance
        self.fail_next: dict[str, ProviderError] = {}
        self.refund_outcome: RefundStatus = RefundStatus.SUCCEEDED
        self.checkout_url_override: str | None = None
        self.calls: list[tuple[str, str]] = []

    # -- test controls -------------------------------------------------
    def _maybe_fail(self, operation: str) -> None:
        error = self.fail_next.pop(operation, None)
        if error is not None:
            raise error

    @staticmethod
    def payment_id_for(intent_id: str) -> str:
        return "fake_pay_" + hashlib.sha256(intent_id.encode()).hexdigest()[:24]

    def sign(self, body: bytes, timestamp: int) -> dict[str, str]:
        mac = hmac.new(self._secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
        return {SIGNATURE_HEADER: mac, TIMESTAMP_HEADER: str(timestamp)}

    # -- adapter contract ------------------------------------------------
    def create_payment(self, request: ProviderCreatePaymentRequest) -> ProviderPaymentResult:
        self.calls.append(("create_payment", request.intent_id))
        self._maybe_fail("create_payment")
        payment_id = self.payment_id_for(request.intent_id)
        return ProviderPaymentResult(
            provider_payment_id=payment_id,
            status=PaymentStatus.PENDING,
            checkout_url=self.checkout_url_override or f"https://checkout.fake-provider.test/pay/{payment_id}",
            expires_at=None,
        )

    def get_payment(self, provider_payment_id: str) -> ProviderPaymentState:
        self.calls.append(("get_payment", provider_payment_id))
        self._maybe_fail("get_payment")
        return ProviderPaymentState(provider_payment_id=provider_payment_id, status=PaymentStatus.PENDING)

    def cancel_payment(self, provider_payment_id: str) -> ProviderPaymentState:
        self.calls.append(("cancel_payment", provider_payment_id))
        self._maybe_fail("cancel_payment")
        return ProviderPaymentState(provider_payment_id=provider_payment_id, status=PaymentStatus.CANCELLED)

    def refund_payment(self, request: ProviderRefundRequest) -> ProviderRefundResult:
        self.calls.append(("refund_payment", request.refund_id))
        self._maybe_fail("refund_payment")
        return ProviderRefundResult(
            provider_refund_id="fake_ref_" + hashlib.sha256(request.refund_id.encode()).hexdigest()[:24],
            status=self.refund_outcome,
            failure_reason="declined by fake provider" if self.refund_outcome == RefundStatus.FAILED else None,
        )

    def verify_webhook(self, headers: Mapping[str, str], body: bytes, received_at: datetime) -> VerifiedProviderEvent:
        lowered = {key.lower(): value for key, value in headers.items()}
        signature = lowered.get(SIGNATURE_HEADER)
        timestamp_raw = lowered.get(TIMESTAMP_HEADER)
        if not signature or not timestamp_raw or len(body) > MAX_WEBHOOK_BYTES:
            raise WebhookVerificationError("Missing signature or oversized body")
        try:
            timestamp = int(timestamp_raw)
        except ValueError as error:
            raise WebhookVerificationError("Malformed timestamp") from error
        signed_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
        if abs(received_at - signed_at) > self._tolerance:
            raise WebhookVerificationError("Stale or future-dated delivery")
        expected = self.sign(body, timestamp)[SIGNATURE_HEADER]
        if not hmac.compare_digest(expected.encode(), signature.encode()):
            raise WebhookVerificationError("Signature mismatch")
        try:
            payload = json.loads(body)
        except ValueError as error:
            raise WebhookVerificationError("Body is not JSON") from error
        if not isinstance(payload, dict) or set(payload) - _EVENT_FIELDS:
            raise WebhookVerificationError("Unexpected event shape")
        try:
            return VerifiedProviderEvent(
                provider_event_id=str(payload["id"]),
                event_type=ProviderEventType(payload["type"]),
                occurred_at=datetime.fromtimestamp(int(payload["created"]), tz=timezone.utc).replace(tzinfo=None),
                provider_payment_id=str(payload["payment_id"]),
                amount_minor=payload.get("amount_minor"),
                currency=payload.get("currency"),
                provider_refund_id=payload.get("refund_id"),
                failure_reason=payload.get("failure_reason"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WebhookVerificationError("Event is missing required fields") from error
