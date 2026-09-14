"""Grow account-level (passive, webhook-only) payload adapter.

Scope, confirmed directly by Grow's own representative — this adapter
implements ONLY the passive account-level webhook, never the paid platform
API: no `CreatePaymentProcess`/`notifyUrl` flow, no `ApproveTransaction`, no
payment collection or PaymentLinks. Those use a structurally different
payload (`transactionId`, `sum`, `statusCode` — see the "Regular Payment
Webhook Format via PaymentLinks" example in Grow's docs) that this adapter
deliberately never parses.

Fixtures for this adapter come verbatim from Grow's own published examples
at https://developers.grow.business/docs/webhooks ("Regular Payment Webhook
Format via API" — see tests/fixtures/grow_payloads.py). Grow's documentation
publishes no distinct payload example for POS-device or mobile-app
transactions; per this integration's scope, both are assumed to use this
same account-level webhook shape until a real transaction from either proves
otherwise — this is a documented assumption, not a verified fact (see
README's Grow section).

Decisions isolated to this adapter, each because Grow's account-level
payload doesn't send the field at all:
- **No `currency` field** → every Grow sale is recorded in ILS. Grow is an
  Israeli PSP and every published example is an Israeli transaction; this
  is a real assumption, confined to this one adapter, not a platform-wide
  default.
- **No VAT/tax-treatment field** → VAT is computed by this app's own
  existing Israeli VAT rules (`app.services.tax.vat`) under `standard`
  treatment, the same default CSV import already uses for a source with no
  tax column of its own.
- **No processing-fee field** → `processing_fee` is always `None`. Never
  invented.
- **No transaction-status field on this webhook type at all** — per Grow's
  own confirmation, this webhook is sent only when a transaction is
  performed, and refunds/cancellations are never sent through it. The one
  signal this adapter validates is `paymentType`: `"רגיל"` (regular) and
  `"תשלומים"` (installments) both represent a completed, revenue-producing
  transaction and are accepted; `"הוראת קבע"` (standing order / recurring)
  belongs to a different, separate Grow webhook format
  ("Recurring Payment Webhook Format") with different renewal/failure
  semantics this integration does not support, and is rejected — see
  `GrowPayloadError` below — rather than silently accepted as a one-time
  sale. Any other/unrecognized value is rejected the same way. Nothing here
  ever creates a `Sale` for an unsupported or unrecognized status.

PII/security, applied here, not left to the caller:
- `webhookKey` is read only to be discarded — Grow itself confirmed it is
  not a secret, and it must never be treated as one, stored, or logged.
- Card fields (`cardSuffix`, `cardBrand`, `cardType`) are never read into
  the returned event at all — never stored, not even the last-4 digits.
  `payment_method` is set to a fixed, generic `"card"` instead.
- `fullName`/`payerPhone`/`payerEmail` map to `customer_name`/
  `customer_contact` — the same customer fields every other ingestion path
  already stores — never logged in plaintext by the caller (see
  app/api/routes/webhooks.py, which only ever logs a hash of the external
  transaction id).
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models.sale import SaleSource, SaleStatus, TaxTreatment
from app.models.sale_event import SaleEventSource
from app.schemas.validators import validate_transaction_datetime_reasonable
from app.services.sale_service import PaymentEvent
from app.services.tax.vat import calculate_vat, vat_rate_snapshot

GROW_CURRENCY = "ILS"

# "רגיל" (regular) and "תשלומים" (installments) both represent a completed
# one-time transaction under the account-level webhook this adapter
# supports. "הוראת קבע" (standing order/recurring) is a different Grow
# webhook format with its own renewal/failure semantics and is intentionally
# excluded — see module docstring.
_SUPPORTED_PAYMENT_TYPES = {"רגיל", "תשלומים"}

MAX_MONEY = Decimal("9999999999.99")


class GrowPayloadError(ValueError):
    """The payload is malformed, or represents a Grow transaction type this
    account-level adapter does not (or must not) accept as revenue."""


def _clean_string(value, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise GrowPayloadError(f"'{field}' is required and must be a string")
    value = value.strip()
    if not value:
        raise GrowPayloadError(f"'{field}' is required and must be a non-empty string")
    if len(value) > max_length:
        raise GrowPayloadError(f"'{field}' must contain at most {max_length} characters")
    if any(ord(character) < 32 for character in value):
        raise GrowPayloadError(f"'{field}' contains invalid control characters")
    return value


def _optional_string(payload: dict, field: str, max_length: int) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > max_length or any(ord(character) < 32 for character in value):
        return None
    return value


def _parse_payment_sum(raw) -> Decimal:
    if raw is None:
        raise GrowPayloadError("'paymentSum' is required")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise GrowPayloadError(f"'paymentSum' is not a valid number: {exc}") from exc
    if not value.is_finite() or value <= 0 or value > MAX_MONEY:
        raise GrowPayloadError("'paymentSum' must be a positive, finite monetary value")
    # Grow's examples show at most 2 decimal places; anything finer isn't a
    # real ILS amount and is rejected rather than silently rounded.
    if value.as_tuple().exponent < -2:
        raise GrowPayloadError("'paymentSum' must have at most 2 decimal places")
    return value


def _parse_payment_date(raw) -> datetime:
    """Grow sends a date only (`D/M/YY` or `DD/MM/YY`, e.g. "14/10/21" or
    "28/3/22") — no time of day. Stored as business-local midnight on that
    date, the same convention the CSV importer already uses for a date-only
    source (see app.services.ingestion.csv_import). A naive datetime built
    this way is already business-local wall-clock time per the naive-
    timestamp convention (app.domain.business_time) — no timezone
    conversion is applied or needed."""
    if not isinstance(raw, str) or not raw.strip():
        raise GrowPayloadError("'paymentDate' is required and must be a string")
    parts = raw.strip().split("/")
    if len(parts) != 3:
        raise GrowPayloadError(f"'paymentDate' is not in D/M/YY format: {raw!r}")
    try:
        day, month, year_2digit = (int(part) for part in parts)
    except ValueError as exc:
        raise GrowPayloadError(f"'paymentDate' is not in D/M/YY format: {raw!r}") from exc
    # Grow's own examples span 2021-2024; every real delivery is 20xx.
    year = 2000 + year_2digit
    try:
        occurred_at = datetime(year, month, day)
    except ValueError as exc:
        raise GrowPayloadError(f"'paymentDate' is not a valid calendar date: {raw!r}") from exc
    try:
        validate_transaction_datetime_reasonable(occurred_at)
    except ValueError as exc:
        raise GrowPayloadError(str(exc)) from exc
    return occurred_at


def parse_grow_event(payload: dict) -> PaymentEvent:
    payload.get("webhookKey")  # read-and-discard: confirmed by Grow to not be a secret; never stored or logged

    transaction_code = _clean_string(payload.get("transactionCode"), "transactionCode", 255)

    payment_type = payload.get("paymentType")
    if not isinstance(payment_type, str) or payment_type.strip() not in _SUPPORTED_PAYMENT_TYPES:
        raise GrowPayloadError(
            f"unsupported or missing 'paymentType': {payment_type!r} "
            f"(supported: {', '.join(sorted(_SUPPORTED_PAYMENT_TYPES))})"
        )

    gross_amount = _parse_payment_sum(payload.get("paymentSum"))
    occurred_at = _parse_payment_date(payload.get("paymentDate"))

    # Grow's account-level webhook has no product/service field at all —
    # only a free-text transaction description. Used defensively as the
    # sale's service name too, since Sale.service_name cannot be blank.
    payment_desc = _optional_string(payload, "paymentDesc", 2000)
    service_name = payment_desc or "עסקת Grow"
    customer_name = _optional_string(payload, "fullName", 255) or "לקוח Grow"
    customer_email = _optional_string(payload, "payerEmail", 255)
    customer_phone = _optional_string(payload, "payerPhone", 50)
    customer_contact = customer_email or customer_phone

    tax_treatment = TaxTreatment.STANDARD
    vat_amount = calculate_vat(gross_amount, tax_treatment)
    net_amount = gross_amount - vat_amount

    return PaymentEvent(
        event_id=transaction_code,
        provider="grow",
        external_transaction_id=transaction_code,
        occurred_at=occurred_at,
        customer_name=customer_name,
        customer_email=customer_contact,
        service_name=service_name,
        gross_amount=gross_amount,
        vat_amount=vat_amount,
        processing_fee=None,
        net_amount=net_amount,
        currency=GROW_CURRENCY,
        # A fixed, generic value — never the card brand/suffix Grow sends.
        payment_method="card",
        status=SaleStatus.SUCCEEDED,
        tax_treatment=tax_treatment,
        vat_rate=vat_rate_snapshot(tax_treatment),
        description=payment_desc,
        sale_source=SaleSource.WEBHOOK,
        event_source=SaleEventSource.WEBHOOK,
    )
