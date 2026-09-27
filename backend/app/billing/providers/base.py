"""The contract for the provider that charges businesses for their Sydney
subscription. Separate from ``app.payments.providers`` (a business's own
customer payments): different credentials, endpoints and data.

Adapters must:

* use hosted checkout only — card data never touches Sydney;
* pass Sydney's ``subscription_id`` to the provider as metadata and return it
  on every event, and use the given idempotency key for provider calls;
* verify every webhook (signature + freshness, constant-time comparison)
  before returning a ``BillingEvent``;
* report amounts *excluding VAT* in ``amount_excluding_vat_minor`` so they can
  be checked against the plan price;
* never claim a successful charge except through a verified ``invoice.paid``
  event — ``create_checkout_session`` only returns a URL;
* declare the exact checkout hosts (``allowed_checkout_hosts``);
* raise ``BillingProviderError`` with messages free of secrets and payloads.
"""

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


class BillingEventType(str, enum.Enum):
    CHECKOUT_COMPLETED = "checkout.completed"          # payment method added / subscription created at the provider
    INVOICE_PAID = "invoice.paid"                      # a period was successfully charged
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"  # a charge failed; the provider may retry
    SUBSCRIPTION_CANCELED = "subscription.canceled"    # the provider ended the subscription
    SUBSCRIPTION_UPDATED = "subscription.updated"      # plan / interval / cancel flag changed at the provider


@dataclass(frozen=True)
class CheckoutRequest:
    subscription_id: str
    business_id: str
    plan_code: str
    interval: str
    provider_price_ref: str | None
    # Set while a trial is still running: the provider must not charge before this.
    trial_ends_at: datetime | None
    customer_ref: str | None
    success_url: str
    cancel_url: str
    idempotency_key: str


@dataclass(frozen=True)
class CheckoutSession:
    provider_session_ref: str
    checkout_url: str
    expires_at: datetime | None = None


@dataclass(frozen=True)
class BillingEvent:
    provider_event_id: str
    event_type: BillingEventType
    occurred_at: datetime
    subscription_id: str | None = None
    provider_customer_ref: str | None = None
    provider_subscription_ref: str | None = None
    provider_session_ref: str | None = None
    plan_code: str | None = None
    interval: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    amount_excluding_vat_minor: int | None = None
    currency: str | None = None
    cancel_at_period_end: bool | None = None
    failure_reason: str | None = None


class BillingProviderError(Exception):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class BillingWebhookVerificationError(Exception):
    pass


@runtime_checkable
class BillingProviderAdapter(Protocol):
    name: str
    test_only: bool
    allowed_checkout_hosts: frozenset[str]

    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession: ...

    def set_cancel_at_period_end(self, provider_subscription_ref: str, cancel: bool) -> None: ...

    def change_plan(self, provider_subscription_ref: str, *, plan_code: str, interval: str,
                    provider_price_ref: str | None, at_period_end: bool) -> None: ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes, received_at: datetime) -> BillingEvent: ...
