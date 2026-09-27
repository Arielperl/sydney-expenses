"""Request/response schemas for the future payments API (INACTIVE).

Requests forbid unknown fields, so a client sending ``card_number``, ``cvv``
or any other unexpected key gets a validation error rather than having the
value silently dropped (and possibly logged by a proxy on the way). Responses
never include idempotency fingerprints, provider secrets or audit internals.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

from app.payments.currency import MAX_AMOUNT_MINOR, CurrencyError, normalize_currency
from app.payments.sensitive_data import contains_card_like_number

Reference = Annotated[StrictStr, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:\-]+$")]
IdempotencyKey = Annotated[StrictStr, Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:\-]+$")]
AmountMinor = Annotated[StrictInt, Field(gt=0, le=MAX_AMOUNT_MINOR)]


def _no_card_data(value: str | None) -> str | None:
    if value is not None and contains_card_like_number(value):
        raise ValueError("Card numbers are never accepted")
    return value


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreatePaymentIntentRequest(_Request):
    external_reference: Reference
    provider: Annotated[StrictStr, Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_]+$")]
    amount_minor: AmountMinor
    currency: Annotated[StrictStr, Field(min_length=3, max_length=3)]
    description: Annotated[StrictStr, Field(min_length=1, max_length=255)]
    customer_reference: Reference | None = None
    expires_at: datetime | None = None

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        try:
            return normalize_currency(value)
        except CurrencyError as error:
            raise ValueError(str(error)) from error

    @field_validator("description", "customer_reference")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return _no_card_data(value)


class CreateRefundRequest(_Request):
    amount_minor: AmountMinor | None = None  # omitted = refund everything still refundable
    reason: Annotated[StrictStr, Field(min_length=1, max_length=255)] | None = None

    @field_validator("reason")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return _no_card_data(value)


class PaymentIntentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_reference: str
    provider: str
    provider_payment_id: str | None
    amount_minor: int
    currency: str
    captured_minor: int
    refunded_minor: int
    description: str
    customer_reference: str | None
    status: str
    checkout_url: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaymentRefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payment_intent_id: str
    amount_minor: int
    currency: str
    reason: str | None
    status: str
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
