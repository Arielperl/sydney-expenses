from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.expense import ExpenseCategory
from app.schemas.validators import (
    validate_business_name,
    validate_currency_code,
    validate_expense_date_reasonable,
    validate_finite_decimal,
    validate_vat_not_exceeding_amount,
)


class ExtractedReceiptData(BaseModel):
    """Provider-independent structured result returned by a ReceiptExtractor."""

    business_name: str | None = None
    receipt_number: str | None = None
    date: date_type | None = None
    total: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    vat: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str = "ILS"
    category: ExpenseCategory = ExpenseCategory.OTHER
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def validate_date_reasonable(cls, value: date_type | None) -> date_type | None:
        if value is None:
            return value
        if value > date_type.today():
            raise ValueError("extracted date must not be in the future")
        return value


class ReceiptUploadResponse(BaseModel):
    upload_id: str
    receipt_image_url: str
    extraction_succeeded: bool
    extracted_data: ExtractedReceiptData | None = None
    error_message: str | None = None


class ReceiptConfirmRequest(BaseModel):
    upload_id: str
    business_name: str = Field(min_length=1, max_length=255)
    receipt_number: str | None = Field(default=None, max_length=100)
    amount: Decimal = Field(ge=0, decimal_places=2)
    vat_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str = Field(default="ILS", min_length=3, max_length=3)
    category: ExpenseCategory = ExpenseCategory.OTHER
    expense_date: date_type
    payment_method: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("business_name")
    @classmethod
    def _validate_business_name(cls, value: str) -> str:
        return validate_business_name(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)

    @field_validator("amount", "vat_amount")
    @classmethod
    def _validate_finite(cls, value: Decimal | None) -> Decimal | None:
        return validate_finite_decimal(value)

    @field_validator("expense_date")
    @classmethod
    def validate_expense_date(cls, value: date_type) -> date_type:
        return validate_expense_date_reasonable(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _validate_vat_within_amount(self) -> "ReceiptConfirmRequest":
        validate_vat_not_exceeding_amount(self.amount, self.vat_amount)
        return self
