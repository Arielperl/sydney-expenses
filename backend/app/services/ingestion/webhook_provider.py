"""Provider-specific webhook payload parsing.

`WEBHOOK_PROVIDERS` is the extension point for a real payment provider or
POS system later: adding a real provider means writing one more
`dict -> PaymentEvent` function and registering it here — the signature
verification, idempotency, and Sale-creation logic in
app/api/routes/webhooks.py never change.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable

from app.models.sale import SaleStatus
from app.services.sale_service import PaymentEvent, compute_net_amount


class WebhookPayloadError(ValueError):
    """The payload is malformed or from an unrecognized provider."""


_STATUS_MAP = {
    "succeeded": SaleStatus.SUCCEEDED,
    "pending": SaleStatus.PENDING,
    "failed": SaleStatus.FAILED,
    "refunded": SaleStatus.REFUNDED,
    "partially_refunded": SaleStatus.PARTIALLY_REFUNDED,
}


def _require_str(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise WebhookPayloadError(f"'{field}' is required and must be a non-empty string")
    return value


def _optional_str(payload: dict, field: str) -> str | None:
    value = payload.get(field)
    if value is not None and not isinstance(value, str):
        raise WebhookPayloadError(f"'{field}' must be a string when present")
    return value


def _require_decimal(payload: dict, field: str, *, allow_zero: bool = False) -> Decimal:
    raw = payload.get(field)
    if raw is None:
        raise WebhookPayloadError(f"'{field}' is required")
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise WebhookPayloadError(f"'{field}' is not a valid number: {exc}") from exc
    if allow_zero:
        if value < 0:
            raise WebhookPayloadError(f"'{field}' must not be negative")
    elif value <= 0:
        raise WebhookPayloadError(f"'{field}' must be positive")
    return value


def _optional_decimal(payload: dict, field: str) -> Decimal | None:
    raw = payload.get(field)
    if raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise WebhookPayloadError(f"'{field}' is not a valid number: {exc}") from exc
    if value < 0:
        raise WebhookPayloadError(f"'{field}' must not be negative")
    return value


def parse_demo_pay_event(payload: dict) -> PaymentEvent:
    event_id = _require_str(payload, "event_id")
    external_transaction_id = _require_str(payload, "external_transaction_id")
    customer_name = _require_str(payload, "customer_name")
    service_name = _require_str(payload, "service_name")
    currency = _require_str(payload, "currency")

    occurred_at_raw = payload.get("occurred_at")
    if not isinstance(occurred_at_raw, str):
        raise WebhookPayloadError("'occurred_at' is required and must be an ISO-8601 string")
    try:
        occurred_at = datetime.fromisoformat(occurred_at_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WebhookPayloadError(f"'occurred_at' is not a valid ISO-8601 timestamp: {exc}") from exc

    gross_amount = _require_decimal(payload, "gross_amount")
    vat_amount = _optional_decimal(payload, "vat_amount")
    processing_fee = _optional_decimal(payload, "processing_fee")
    net_amount = _optional_decimal(payload, "net_amount")
    if net_amount is None:
        net_amount = compute_net_amount(gross_amount, vat_amount, processing_fee)

    status_raw = payload.get("status")
    if not isinstance(status_raw, str) or status_raw not in _STATUS_MAP:
        raise WebhookPayloadError(f"'status' must be one of: {', '.join(_STATUS_MAP)}")
    status = _STATUS_MAP[status_raw]

    return PaymentEvent(
        event_id=event_id,
        provider="demo-pay",
        external_transaction_id=external_transaction_id,
        occurred_at=occurred_at,
        customer_name=customer_name,
        customer_email=_optional_str(payload, "customer_email"),
        service_name=service_name,
        gross_amount=gross_amount,
        vat_amount=vat_amount,
        processing_fee=processing_fee,
        net_amount=net_amount,
        currency=currency.upper(),
        payment_method=_optional_str(payload, "payment_method"),
        status=status,
        description=_optional_str(payload, "description"),
    )


WEBHOOK_PROVIDERS: dict[str, Callable[[dict], PaymentEvent]] = {
    "demo-pay": parse_demo_pay_event,
}


def parse_webhook_event(payload: dict) -> PaymentEvent:
    provider = payload.get("provider")
    if not isinstance(provider, str) or provider not in WEBHOOK_PROVIDERS:
        known = ", ".join(sorted(WEBHOOK_PROVIDERS))
        raise WebhookPayloadError(f"unknown or missing 'provider' (known providers: {known})")
    return WEBHOOK_PROVIDERS[provider](payload)
