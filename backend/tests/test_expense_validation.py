from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.expense import ExpenseCreate, ExpenseUpdate


def _valid_payload(**overrides) -> dict:
    payload = {
        "business_name": "Shufersal",
        "amount": Decimal("100.00"),
        "expense_date": date.today(),
        "currency": "ILS",
    }
    payload.update(overrides)
    return payload


def test_valid_expense_passes():
    expense = ExpenseCreate(**_valid_payload())
    assert expense.business_name == "Shufersal"
    assert expense.amount == Decimal("100.00")


def test_negative_amount_rejected():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(amount=Decimal("-1")))


def test_negative_vat_rejected():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(vat_amount=Decimal("-5")))


def test_future_date_rejected():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(expense_date=date.today() + timedelta(days=1)))


def test_unreasonably_old_date_rejected():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(expense_date=date(1999, 12, 31)))


def test_blank_business_name_rejected():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(business_name="   "))


def test_business_name_is_trimmed():
    expense = ExpenseCreate(**_valid_payload(business_name="  Shufersal  "))
    assert expense.business_name == "Shufersal"


def test_zero_amount_is_allowed():
    expense = ExpenseCreate(**_valid_payload(amount=Decimal("0")))
    assert expense.amount == 0


def test_currency_lowercase_is_normalized_to_uppercase():
    expense = ExpenseCreate(**_valid_payload(currency="ils"))
    assert expense.currency == "ILS"


def test_currency_must_be_three_letters():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(currency="IL"))


def test_currency_must_be_alphabetic():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(currency="1LS"))


def test_vat_greater_than_amount_rejected():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(amount=Decimal("10.00"), vat_amount=Decimal("15.00")))


def test_vat_equal_to_amount_is_allowed():
    expense = ExpenseCreate(**_valid_payload(amount=Decimal("10.00"), vat_amount=Decimal("10.00")))
    assert expense.vat_amount == expense.amount


def test_non_finite_amount_rejected():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(amount=Decimal("NaN")))


def test_non_finite_vat_rejected():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(vat_amount=Decimal("Infinity")))


def test_amount_precision_is_limited_to_two_decimal_places():
    with pytest.raises(ValidationError):
        ExpenseCreate(**_valid_payload(amount=Decimal("10.999")))


def test_update_business_name_blank_rejected():
    with pytest.raises(ValidationError):
        ExpenseUpdate(business_name="   ")


def test_update_currency_normalized():
    update = ExpenseUpdate(currency="usd")
    assert update.currency == "USD"


def test_update_vat_greater_than_amount_rejected():
    with pytest.raises(ValidationError):
        ExpenseUpdate(amount=Decimal("5.00"), vat_amount=Decimal("6.00"))


def test_update_with_no_fields_is_allowed():
    update = ExpenseUpdate()
    assert update.business_name is None
