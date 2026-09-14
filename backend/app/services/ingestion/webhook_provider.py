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

from app.domain.business_time import normalize_to_naive_business_datetime
from app.models.sale import SaleStatus, TaxTreatment
from app.services.ingestion.grow_provider import parse_grow_event
from app.services.sale_service import PaymentEvent, compute_net_amount
from app.services.tax.vat import calculate_vat, vat_amount_is_consistent, vat_rate_snapshot
from app.schemas.validators import validate_currency_code, validate_transaction_datetime_reasonable


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


MAX_MONEY = Decimal("9999999999.99")


def _clean_string(value: str, field: str, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise WebhookPayloadError(f"'{field}' is required and must be a non-empty string")
    if len(value) > max_length:
        raise WebhookPayloadError(f"'{field}' must contain at most {max_length} characters")
    if any(ord(character) < 32 for character in value):
        raise WebhookPayloadError(f"'{field}' contains invalid control characters")
    return value


def _require_str(payload: dict, field: str, max_length: int) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise WebhookPayloadError(f"'{field}' is required and must be a non-empty string")
    return _clean_string(value, field, max_length)


def _optional_str(payload: dict, field: str, max_length: int) -> str | None:
    value = payload.get(field)
    if value is not None and not isinstance(value, str):
        raise WebhookPayloadError(f"'{field}' must be a string when present")
    return None if value is None else _clean_string(value, field, max_length)


def _require_decimal(payload: dict, field: str, *, allow_zero: bool = False) -> Decimal:
    raw = payload.get(field)
    if raw is None:
        raise WebhookPayloadError(f"'{field}' is required")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise WebhookPayloadError(f"'{field}' is not a valid number: {exc}") from exc
    if not value.is_finite() or abs(value) > MAX_MONEY or value.as_tuple().exponent < -2:
        raise WebhookPayloadError(f"'{field}' must be a finite monetary value with at most 2 decimals")
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
    except (InvalidOperation, ValueError) as exc:
        raise WebhookPayloadError(f"'{field}' is not a valid number: {exc}") from exc
    if not value.is_finite() or value > MAX_MONEY or value.as_tuple().exponent < -2:
        raise WebhookPayloadError(f"'{field}' must be a finite monetary value with at most 2 decimals")
    if value < 0:
        raise WebhookPayloadError(f"'{field}' must not be negative")
    return value


def parse_demo_pay_event(payload: dict) -> PaymentEvent:
    event_id = _require_str(payload, "event_id", 255)
    external_transaction_id = _require_str(payload, "external_transaction_id", 255)
    customer_name = _require_str(payload, "customer_name", 255)
    service_name = _require_str(payload, "service_name", 255)
    currency = _require_str(payload, "currency", 3)
    try:
        currency = validate_currency_code(currency)
    except ValueError as exc:
        raise WebhookPayloadError(str(exc)) from exc

    occurred_at_raw = payload.get("occurred_at")
    if not isinstance(occurred_at_raw, str):
        raise WebhookPayloadError("'occurred_at' is required and must be an ISO-8601 string")
    try:
        occurred_at = datetime.fromisoformat(occurred_at_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WebhookPayloadError(f"'occurred_at' is not a valid ISO-8601 timestamp: {exc}") from exc
    # Normalized to naive business-local (Asia/Jerusalem) wall-clock time
    # exactly once, here at the ingestion boundary — see
    # app.domain.business_time for why: a provider may legitimately send an
    # aware timestamp with any UTC offset, but every `Sale.occurred_at`
    # value this app stores and later compares (dashboard boundaries, sale-
    # date validation) is naive business-local, so ingestion is where that
    # gets reconciled, once, rather than at every later read.
    occurred_at = normalize_to_naive_business_datetime(occurred_at)
    try:
        validate_transaction_datetime_reasonable(occurred_at)
    except ValueError as exc:
        raise WebhookPayloadError(str(exc)) from exc

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
    expected_net = compute_net_amount(gross_amount, vat_amount, processing_fee)
    if expected_net < 0 or abs(net_amount - expected_net) > Decimal("0.01"):
        raise WebhookPayloadError("'net_amount' is inconsistent with gross amount, VAT, and processing fee")

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
        customer_email=_optional_str(payload, "customer_email", 255),
        service_name=service_name,
        gross_amount=gross_amount,
        vat_amount=vat_amount,
        processing_fee=processing_fee,
        net_amount=net_amount,
        currency=currency.upper(),
        payment_method=_optional_str(payload, "payment_method", 50),
        status=status,
        tax_treatment=tax_treatment,
        vat_rate=vat_rate_snapshot(tax_treatment),
        description=_optional_str(payload, "description", 2000),
    )


WEBHOOK_PROVIDERS: dict[str, Callable[[dict], PaymentEvent]] = {
    "demo-pay": parse_demo_pay_event,
    # Grow's account-level payload has no self-describing "provider" field
    # (unlike demo-pay), so this registry entry is reached only by the
    # connection-based route selecting it via `connection.provider` — see
    # app/api/routes/webhooks.py — never by `parse_webhook_event`'s
    # payload-sniffing dispatch below, which Grow payloads never match.
    "grow": parse_grow_event,
}


def parse_webhook_event(payload: dict) -> PaymentEvent:
    provider = payload.get("provider")
    if not isinstance(provider, str) or provider not in WEBHOOK_PROVIDERS:
        known = ", ".join(sorted(WEBHOOK_PROVIDERS))
        raise WebhookPayloadError(f"unknown or missing 'provider' (known providers: {known})")
    return WEBHOOK_PROVIDERS[provider](payload)
