from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.expense import Expense, ExpenseCategory, ExtractionStatus
from app.schemas.validators import (
    validate_business_name,
    validate_currency_code,
    validate_expense_date_reasonable,
    validate_finite_decimal,
    validate_vat_not_exceeding_amount,
)


class ExpenseBase(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    receipt_number: str | None = Field(default=None, max_length=100)
    amount: Decimal = Field(ge=0, decimal_places=2)
    vat_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str = Field(default="ILS", min_length=3, max_length=3)
    category: ExpenseCategory = ExpenseCategory.OTHER
    expense_date: date
    payment_method: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)

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
    def _validate_expense_date(cls, value: date) -> date:
        return validate_expense_date_reasonable(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def _validate_vat_within_amount(self) -> "ExpenseBase":
        validate_vat_not_exceeding_amount(self.amount, self.vat_amount)
        return self


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    receipt_number: str | None = Field(default=None, max_length=100)
    amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    vat_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category: ExpenseCategory | None = None
    expense_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("business_name")
    @classmethod
    def _validate_business_name(cls, value: str | None) -> str | None:
        return None if value is None else validate_business_name(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        return None if value is None else validate_currency_code(value)

    @field_validator("amount", "vat_amount")
    @classmethod
    def _validate_finite(cls, value: Decimal | None) -> Decimal | None:
        return validate_finite_decimal(value)

    @field_validator("expense_date")
    @classmethod
    def _validate_expense_date(cls, value: date | None) -> date | None:
        return validate_expense_date_reasonable(value)

    @model_validator(mode="after")
    def _validate_vat_within_amount(self) -> "ExpenseUpdate":
        validate_vat_not_exceeding_amount(self.amount, self.vat_amount)
        return self


class ExpenseRead(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    receipt_image_url: str | None = None
    extraction_confidence: float | None = None
    extraction_status: ExtractionStatus
    created_at: datetime
    updated_at: datetime


def expense_to_read(expense: Expense, receipt_image_url: str | None) -> ExpenseRead:
    return ExpenseRead(
        id=expense.id,
        business_name=expense.business_name,
        receipt_number=expense.receipt_number,
        amount=expense.amount,
        vat_amount=expense.vat_amount,
        currency=expense.currency,
        category=expense.category,
        expense_date=expense.expense_date,
        payment_method=expense.payment_method,
        notes=expense.notes,
        receipt_image_url=receipt_image_url,
        extraction_confidence=expense.extraction_confidence,
        extraction_status=expense.extraction_status,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )
