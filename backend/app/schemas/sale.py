from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.sale import DocumentStatus, Sale, SaleSource, SaleStatus
from app.schemas.validators import (
    validate_currency_code,
    validate_finite_decimal,
    validate_required_text,
    validate_transaction_datetime_reasonable,
    validate_vat_not_exceeding_amount,
)


class SaleBase(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    customer_contact: str | None = Field(default=None, max_length=255)
    service_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    gross_amount: Decimal = Field(ge=0, decimal_places=2)
    vat_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    processing_fee: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str = Field(default="ILS", min_length=3, max_length=3)
    payment_method: str | None = Field(default=None, max_length=50)
    occurred_at: datetime

    @field_validator("customer_name", "service_name")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        return validate_required_text(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)

    @field_validator("gross_amount", "vat_amount", "processing_fee")
    @classmethod
    def _validate_finite(cls, value: Decimal | None) -> Decimal | None:
        return validate_finite_decimal(value)

    @field_validator("occurred_at")
    @classmethod
    def _validate_occurred_at(cls, value: datetime) -> datetime:
        return validate_transaction_datetime_reasonable(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _validate_vat_within_amount(self) -> "SaleBase":
        validate_vat_not_exceeding_amount(self.gross_amount, self.vat_amount)
        return self


class SaleCreate(SaleBase):
    """Manual sale entry — the fallback path when no payment provider sent
    a webhook. Always recorded as a completed (`succeeded`) sale; `net_amount`
    is never accepted from the client, only computed server-side."""

    pass


class SaleUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_contact: str | None = Field(default=None, max_length=255)
    service_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    gross_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    vat_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    processing_fee: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    payment_method: str | None = Field(default=None, max_length=50)
    occurred_at: datetime | None = None

    @field_validator("customer_name", "service_name")
    @classmethod
    def _validate_required_text(cls, value: str | None) -> str | None:
        return None if value is None else validate_required_text(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        return None if value is None else validate_currency_code(value)

    @field_validator("gross_amount", "vat_amount", "processing_fee")
    @classmethod
    def _validate_finite(cls, value: Decimal | None) -> Decimal | None:
        return validate_finite_decimal(value)

    @field_validator("occurred_at")
    @classmethod
    def _validate_occurred_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else validate_transaction_datetime_reasonable(value)  # type: ignore[return-value]


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_id: str | None = None
    source_provider: str | None = None
    source: SaleSource
    status: SaleStatus
    occurred_at: datetime
    customer_name: str
    customer_contact: str | None = None
    service_name: str
    description: str | None = None
    gross_amount: Decimal
    vat_amount: Decimal | None = None
    processing_fee: Decimal | None = None
    net_amount: Decimal
    refunded_amount: Decimal | None = None
    currency: str
    payment_method: str | None = None
    document_status: DocumentStatus
    document_number: str | None = None
    document_url: str | None = None
    raw_description: str | None = None
    created_at: datetime
    updated_at: datetime


class RefundRequest(BaseModel):
    """A manual refund record — no real payment provider sends a refund
    webhook in this demo, so refunds are recorded explicitly. Omitting
    `amount` records a full refund."""

    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)

    @field_validator("amount")
    @classmethod
    def _validate_finite(cls, value: Decimal | None) -> Decimal | None:
        return validate_finite_decimal(value)


def sale_to_read(sale: Sale) -> SaleRead:
    return SaleRead.model_validate(sale)
