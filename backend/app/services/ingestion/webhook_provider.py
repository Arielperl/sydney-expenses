"""Provider-specific webhook payload parsing.

`WEBHOOK_PROVIDERS` is the extension point for a real bank/PSP integration
later: adding a real provider means writing one more `dict -> TransactionEvent`
function and registering it here — the signature verification, idempotency,
and Expense-creation logic in app/api/routes/webhooks.py never change.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable


class WebhookPayloadError(ValueError):
    """The payload is malformed or from an unrecognized provider."""


@dataclass
class TransactionEvent:
    event_id: str
    provider: str
    external_transaction_id: str
    occurred_at: datetime
    merchant_name: str
    amount: Decimal
    currency: str
    payment_method: str | None = None
    description: str | None = None


def _require_str(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise WebhookPayloadError(f"'{field}' is required and must be a non-empty string")
    return value


def parse_demo_provider_event(payload: dict) -> TransactionEvent:
    event_id = _require_str(payload, "event_id")
    external_transaction_id = _require_str(payload, "external_transaction_id")
    merchant_name = _require_str(payload, "merchant_name")
    currency = _require_str(payload, "currency")

    occurred_at_raw = payload.get("occurred_at")
    if not isinstance(occurred_at_raw, str):
        raise WebhookPayloadError("'occurred_at' is required and must be an ISO-8601 string")
    try:
        occurred_at = datetime.fromisoformat(occurred_at_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WebhookPayloadError(f"'occurred_at' is not a valid ISO-8601 timestamp: {exc}") from exc

    amount_raw = payload.get("amount")
    if amount_raw is None:
        raise WebhookPayloadError("'amount' is required")
    try:
        amount = Decimal(str(amount_raw))
    except InvalidOperation as exc:
        raise WebhookPayloadError(f"'amount' is not a valid number: {exc}") from exc
    if amount <= 0:
        raise WebhookPayloadError("'amount' must be positive")

    payment_method = payload.get("payment_method")
    if payment_method is not None and not isinstance(payment_method, str):
        raise WebhookPayloadError("'payment_method' must be a string when present")

    description = payload.get("description")
    if description is not None and not isinstance(description, str):
        raise WebhookPayloadError("'description' must be a string when present")

    return TransactionEvent(
        event_id=event_id,
        provider="demo-bank",
        external_transaction_id=external_transaction_id,
        occurred_at=occurred_at,
        merchant_name=merchant_name,
        amount=amount,
        currency=currency.upper(),
        payment_method=payment_method,
        description=description,
    )


WEBHOOK_PROVIDERS: dict[str, Callable[[dict], TransactionEvent]] = {
    "demo-bank": parse_demo_provider_event,
}


def parse_webhook_event(payload: dict) -> TransactionEvent:
    provider = payload.get("provider")
    if not isinstance(provider, str) or provider not in WEBHOOK_PROVIDERS:
        known = ", ".join(sorted(WEBHOOK_PROVIDERS))
        raise WebhookPayloadError(f"unknown or missing 'provider' (known providers: {known})")
    return WEBHOOK_PROVIDERS[provider](payload)
