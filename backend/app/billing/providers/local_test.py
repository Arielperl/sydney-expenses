"""LOCAL TEST BILLING PROVIDER — for tests and local development only.

It never contacts a network, never charges anything and refuses to be
constructed in production. Its checkout URLs point at the reserved
``.invalid`` domain, so they can never resolve to a real payment page. Its
signature scheme (HMAC-SHA256 over ``"<timestamp>.<body>"``) exists only to
exercise the verification path and describes no real provider.
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from app.billing.providers.base import (
    BillingEvent,
    BillingEventType,
    BillingProviderError,
    BillingWebhookVerificationError,
    CheckoutRequest,
    CheckoutSession,
)

SIGNATURE_HEADER = "x-local-test-billing-signature"
TIMESTAMP_HEADER = "x-local-test-billing-timestamp"
MAX_BODY_BYTES = 16_384
_FIELDS = {
    "id", "type", "created", "subscription_id", "customer", "subscription", "session", "plan", "interval",
    "period_start", "period_end", "amount_excluding_vat", "currency", "cancel_at_period_end", "failure_reason",
}


def _ts(value) -> datetime | None:
    return None if value is None else datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)


class LocalTestBillingProvider:
    name = "local_test_billing"
    test_only = True
    allowed_checkout_hosts = frozenset({"checkout.local-test-billing.invalid"})

    def __init__(self, *, environment: str, webhook_secret: bytes, tolerance: timedelta = timedelta(minutes=5)):
        if environment == "production":
            raise RuntimeError("LocalTestBillingProvider is disabled in production")
        if len(webhook_secret) < 32:
            raise ValueError("webhook_secret must be at least 32 bytes")
        self._secret = webhook_secret
        self._tolerance = tolerance
        self.fail_next: dict[str, BillingProviderError] = {}
        self.calls: list[tuple] = []

    def _maybe_fail(self, operation: str) -> None:
        error = self.fail_next.pop(operation, None)
        if error is not None:
            raise error

    def sign(self, body: bytes, timestamp: int) -> dict[str, str]:
        mac = hmac.new(self._secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
        return {SIGNATURE_HEADER: mac, TIMESTAMP_HEADER: str(timestamp)}

    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession:
        self.calls.append(("create_checkout_session", request.idempotency_key, request.plan_code, request.interval,
                           request.trial_ends_at))
        self._maybe_fail("create_checkout_session")
        ref = "lt_cs_" + hashlib.sha256(request.idempotency_key.encode()).hexdigest()[:20]
        return CheckoutSession(provider_session_ref=ref, checkout_url=f"https://checkout.local-test-billing.invalid/session/{ref}")

    def set_cancel_at_period_end(self, provider_subscription_ref: str, cancel: bool) -> None:
        self.calls.append(("set_cancel_at_period_end", provider_subscription_ref, cancel))
        self._maybe_fail("set_cancel_at_period_end")

    def change_plan(self, provider_subscription_ref: str, *, plan_code: str, interval: str,
                    provider_price_ref: str | None, at_period_end: bool) -> None:
        self.calls.append(("change_plan", provider_subscription_ref, plan_code, interval, at_period_end))
        self._maybe_fail("change_plan")

    def verify_webhook(self, headers: Mapping[str, str], body: bytes, received_at: datetime) -> BillingEvent:
        lowered = {key.lower(): value for key, value in headers.items()}
        signature, timestamp_raw = lowered.get(SIGNATURE_HEADER), lowered.get(TIMESTAMP_HEADER)
        if not signature or not timestamp_raw or len(body) > MAX_BODY_BYTES:
            raise BillingWebhookVerificationError("Missing signature or oversized body")
        try:
            timestamp = int(timestamp_raw)
        except ValueError as error:
            raise BillingWebhookVerificationError("Malformed timestamp") from error
        if abs(received_at - _ts(timestamp)) > self._tolerance:
            raise BillingWebhookVerificationError("Stale or future-dated delivery")
        if not hmac.compare_digest(self.sign(body, timestamp)[SIGNATURE_HEADER].encode(), signature.encode()):
            raise BillingWebhookVerificationError("Signature mismatch")
        try:
            payload = json.loads(body)
        except ValueError as error:
            raise BillingWebhookVerificationError("Body is not JSON") from error
        if not isinstance(payload, dict) or set(payload) - _FIELDS:
            raise BillingWebhookVerificationError("Unexpected event shape")
        try:
            amount = payload.get("amount_excluding_vat")
            if amount is not None and (isinstance(amount, bool) or not isinstance(amount, int)):
                raise ValueError("amount must be an integer")
            return BillingEvent(
                provider_event_id=str(payload["id"]),
                event_type=BillingEventType(payload["type"]),
                occurred_at=_ts(payload["created"]),
                subscription_id=payload.get("subscription_id"),
                provider_customer_ref=payload.get("customer"),
                provider_subscription_ref=payload.get("subscription"),
                provider_session_ref=payload.get("session"),
                plan_code=payload.get("plan"),
                interval=payload.get("interval"),
                period_start=_ts(payload.get("period_start")),
                period_end=_ts(payload.get("period_end")),
                amount_excluding_vat_minor=amount,
                currency=payload.get("currency"),
                cancel_at_period_end=payload.get("cancel_at_period_end"),
                failure_reason=payload.get("failure_reason"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise BillingWebhookVerificationError("Event is missing required fields") from error
