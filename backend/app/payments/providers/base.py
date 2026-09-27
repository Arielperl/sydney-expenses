"""The contract every future provider adapter must implement.

Adapters translate between a provider's API/webhooks and the normalized
types below. Provider-specific payloads, field names and secrets stay inside
the adapter; the domain model and service only ever see these types.

An adapter must:

* never accept or return card data (hosted checkout / tokenization only);
* use the ``intent_id`` / ``refund_id`` it is given as the provider-side
  idempotency key, so a retried call cannot create a second charge/refund;
* verify every webhook cryptographically (or via an authenticated
  server-to-server lookup) before returning a ``VerifiedProviderEvent``,
  using constant-time comparison and a freshness window where the provider
  signs a timestamp;
* declare the exact hosts its checkout URLs may point to
  (``allowed_checkout_hosts``); the service rejects anything else;
* raise ``ProviderError`` (``retryable=True`` only for genuinely transient
  failures) and never include secrets or payloads in exception messages.
"""

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.payments.state_machine import PaymentStatus, RefundStatus


class ProviderEventType(str, enum.Enum):
    PAYMENT_PENDING = "payment.pending"
    PAYMENT_REQUIRES_ACTION = "payment.requires_action"
    PAYMENT_AUTHORIZED = "payment.authorized"
    PAYMENT_CAPTURED = "payment.captured"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_CANCELLED = "payment.cancelled"
    PAYMENT_EXPIRED = "payment.expired"
    REFUND_SUCCEEDED = "refund.succeeded"
    REFUND_FAILED = "refund.failed"


EVENT_TARGET_STATUS: dict[ProviderEventType, PaymentStatus] = {
    ProviderEventType.PAYMENT_PENDING: PaymentStatus.PENDING,
    ProviderEventType.PAYMENT_REQUIRES_ACTION: PaymentStatus.REQUIRES_ACTION,
    ProviderEventType.PAYMENT_AUTHORIZED: PaymentStatus.AUTHORIZED,
    ProviderEventType.PAYMENT_CAPTURED: PaymentStatus.CAPTURED,
    ProviderEventType.PAYMENT_FAILED: PaymentStatus.FAILED,
    ProviderEventType.PAYMENT_CANCELLED: PaymentStatus.CANCELLED,
    ProviderEventType.PAYMENT_EXPIRED: PaymentStatus.EXPIRED,
}


@dataclass(frozen=True)
class ProviderCreatePaymentRequest:
    intent_id: str  # also the provider-side idempotency key
    amount_minor: int
    currency: str
    description: str
    external_reference: str


@dataclass(frozen=True)
class ProviderPaymentResult:
    provider_payment_id: str
    status: PaymentStatus
    # Required when create_payment reports an immediate capture. Zero for
    # every pre-capture result. This keeps a synchronously captured payment
    # from being persisted with captured_minor=0.
    captured_minor: int = 0
    checkout_url: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ProviderPaymentState:
    provider_payment_id: str
    status: PaymentStatus
    captured_minor: int = 0


@dataclass(frozen=True)
class ProviderRefundRequest:
    refund_id: str  # also the provider-side idempotency key
    provider_payment_id: str
    amount_minor: int
    currency: str
    reason: str | None


@dataclass(frozen=True)
class ProviderRefundResult:
    provider_refund_id: str
    status: RefundStatus
    failure_reason: str | None = None


@dataclass(frozen=True)
class VerifiedProviderEvent:
    """Only an adapter's ``verify_webhook`` may construct one of these."""

    provider_event_id: str
    event_type: ProviderEventType
    occurred_at: datetime
    provider_payment_id: str
    amount_minor: int | None = None
    currency: str | None = None
    provider_refund_id: str | None = None
    failure_reason: str | None = None


class ProviderError(Exception):
    """A provider call failed. Messages must be safe to store (no secrets/payloads)."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class WebhookVerificationError(Exception):
    """The delivery could not be proven to come from the provider (or is stale/replayed)."""


@runtime_checkable
class PaymentProviderAdapter(Protocol):
    name: str
    #: True only for test doubles; the registry refuses these in production.
    test_only: bool
    allowed_checkout_hosts: frozenset[str]

    def create_payment(self, request: ProviderCreatePaymentRequest) -> ProviderPaymentResult: ...

    def get_payment(self, provider_payment_id: str) -> ProviderPaymentState: ...

    def cancel_payment(self, provider_payment_id: str) -> ProviderPaymentState: ...

    def refund_payment(self, request: ProviderRefundRequest) -> ProviderRefundResult: ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes, received_at: datetime) -> VerifiedProviderEvent: ...
