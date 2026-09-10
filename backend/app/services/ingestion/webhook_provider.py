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

from app.models.sale import SaleStatus, TaxTreatment
from app.services.sale_service import PaymentEvent, compute_net_amount
from app.services.tax.vat import calculate_vat, vat_amount_is_consistent, vat_rate_snapshot


class WebhookPayloadError(ValueError):
    """The payload is malformed or from an unrecognized provider."""


_STATUS_MAP = {
    "succeeded": SaleStatus.SUCCEEDED,
    "pending": SaleStatus.PENDING,
    "failed": SaleStatus.FAILED,
    "refunded": SaleStatus.REFUNDED,
    "partially_refunded": SaleStatus.PARTIALLY_REFUNDED,
}

_TAX_TREATMENT_MAP = {treatment.value: treatment for treatment in TaxTreatment}


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

    tax_treatment_raw = payload.get("tax_treatment", TaxTreatment.STANDARD.value)
    if not isinstance(tax_treatment_raw, str) or tax_treatment_raw not in _TAX_TREATMENT_MAP:
        raise WebhookPayloadError(f"'tax_treatment' must be one of: {', '.join(_TAX_TREATMENT_MAP)}")
    tax_treatment = _TAX_TREATMENT_MAP[tax_treatment_raw]

    # This demo webhook always taxes under the business's own Israeli VAT
    # configuration (see app.domain.demo_business) — currency never
    # determines the tax rate, so a USD/EUR event is computed exactly like
    # an ILS one. If the provider didn't send a VAT amount at all, the
    # backend calculates it; if it did, that figure must agree with what our
    # own tax configuration computes (within rounding tolerance) — a
    # provider silently claiming a different VAT amount than the selected
    # tax treatment implies is inconsistent financial data, rejected rather
    # than accepted as-is.
    reported_vat_amount = _optional_decimal(payload, "vat_amount")
    if reported_vat_amount is None:
        vat_amount = calculate_vat(gross_amount, tax_treatment)
    else:
        if not vat_amount_is_consistent(gross_amount, tax_treatment, reported_vat_amount):
            expected = calculate_vat(gross_amount, tax_treatment)
            raise WebhookPayloadError(
                f"'vat_amount' {reported_vat_amount} is inconsistent with tax_treatment "
                f"{tax_treatment.value!r} for gross_amount {gross_amount} (expected {expected})"
            )
        vat_amount = reported_vat_amount

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
        tax_treatment=tax_treatment,
        vat_rate=vat_rate_snapshot(tax_treatment),
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
