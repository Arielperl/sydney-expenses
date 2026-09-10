import re
from datetime import date, datetime, timezone
from decimal import Decimal

MIN_REASONABLE_DATE = date(2000, 1, 1)
CURRENCY_CODE_PATTERN = re.compile(r"^[A-Za-z]{3}$")


def validate_required_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("value must not be blank")
    return stripped


def validate_currency_code(value: str) -> str:
    if not CURRENCY_CODE_PATTERN.match(value):
        raise ValueError("currency must be exactly 3 alphabetic characters")
    return value.upper()


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def validate_date_reasonable(value: date | None) -> date | None:
    if value is None:
        return value
    if value < MIN_REASONABLE_DATE:
        raise ValueError(f"date must not be earlier than {MIN_REASONABLE_DATE.isoformat()}")
    if value > _today_utc():
        raise ValueError("date must not be in the future")
    return value


def validate_transaction_datetime_reasonable(value: datetime | None) -> datetime | None:
    if value is None:
        return value
    value_date = value.date() if value.tzinfo is None else value.astimezone(timezone.utc).date()
    validate_date_reasonable(value_date)
    return value


def validate_finite_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return value
    if not value.is_finite():
        raise ValueError("value must be a finite number")
    return value


def validate_vat_not_exceeding_amount(amount: Decimal | None, vat_amount: Decimal | None) -> None:
    if amount is not None and vat_amount is not None and vat_amount > amount:
        raise ValueError("vat_amount must not be greater than the gross amount")
