import re
from datetime import date, datetime
from decimal import Decimal

from app.domain.business_time import business_date_of, business_today
from app.models.sale import PaymentMethod, SaleCurrency, TaxTreatment

MIN_REASONABLE_DATE = date(2000, 1, 1)
CURRENCY_CODE_PATTERN = re.compile(r"^[A-Za-z]{3}$")
_ALLOWED_PAYMENT_METHODS = {method.value for method in PaymentMethod}
_ALLOWED_TRANSACTION_CURRENCIES = {currency.value for currency in SaleCurrency}
_ALLOWED_TAX_TREATMENTS = {treatment.value for treatment in TaxTreatment}


def validate_required_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("value must not be blank")
    return stripped


def validate_currency_code(value: str) -> str:
    if not CURRENCY_CODE_PATTERN.match(value):
        raise ValueError("currency must be exactly 3 alphabetic characters")
    return value.upper()


def validate_date_reasonable(value: date | None) -> date | None:
    """Compares against `business_today()` — this demo business's own
    calendar date (Asia/Jerusalem) — never a bare UTC or OS-local "today".
    See app.domain.business_time for why that distinction matters."""
    if value is None:
        return value
    if value < MIN_REASONABLE_DATE:
        raise ValueError(f"date must not be earlier than {MIN_REASONABLE_DATE.isoformat()}")
    if value > business_today():
        raise ValueError("date must not be in the future")
    return value


def validate_transaction_datetime_reasonable(value: datetime | None) -> datetime | None:
    if value is None:
        return value
    validate_date_reasonable(business_date_of(value))
    return value


def validate_finite_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return value
    if not value.is_finite():
        raise ValueError("value must be a finite number")
    return value


def validate_transaction_currency(value: str) -> str:
    """Restricts `currency` to the closed set selectable through the sale
    create/update API (ILS/USD/EUR — see app.domain.demo_business) — never
    an arbitrary string. Webhook ingestion and CSV import use the more
    permissive `validate_currency_code` instead, since a real payment
    provider or bank export may legitimately use a currency this demo's
    manual-entry UI doesn't offer yet (the same reasoning `payment_method`
    already follows — see `validate_payment_method` below)."""
    normalized = validate_currency_code(value)
    if normalized not in _ALLOWED_TRANSACTION_CURRENCIES:
        allowed = ", ".join(sorted(_ALLOWED_TRANSACTION_CURRENCIES))
        raise ValueError(f"currency must be one of: {allowed}")
    return normalized


def validate_tax_treatment(value: str) -> str:
    if value not in _ALLOWED_TAX_TREATMENTS:
        allowed = ", ".join(sorted(_ALLOWED_TAX_TREATMENTS))
        raise ValueError(f"tax_treatment must be one of: {allowed}")
    return value


def validate_payment_method(value: str | None) -> str | None:
    """Restricts `payment_method` to the closed set a human can pick through
    the sale create/update API (`card`/`cash`/`other`) — never an arbitrary
    string. Webhook-ingested sales bypass this (see `PaymentMethod`'s own
    docstring) since a real payment provider's own method names shouldn't be
    rejected on ingestion."""
    if value is None:
        return value
    if value not in _ALLOWED_PAYMENT_METHODS:
        allowed = ", ".join(sorted(_ALLOWED_PAYMENT_METHODS))
        raise ValueError(f"payment_method must be one of: {allowed}")
    return value
