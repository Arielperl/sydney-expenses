from decimal import Decimal

from app.models.sale import TaxTreatment
from app.services.tax.vat import calculate_vat, vat_amount_is_consistent, vat_rate_snapshot


def test_standard_vat_on_118_is_18():
    """The textbook example: a VAT-inclusive charge of 118.00 at the 18%
    Israeli standard rate has an 18.00 VAT component (never 118 * 0.18 =
    21.24, which would double-count VAT on an already-inclusive amount)."""
    assert calculate_vat(Decimal("118.00"), TaxTreatment.STANDARD) == Decimal("18.00")


def test_standard_vat_revenue_before_vat_is_100():
    gross = Decimal("118.00")
    vat = calculate_vat(gross, TaxTreatment.STANDARD)
    assert gross - vat == Decimal("100.00")


def test_zero_rate_and_exempt_always_produce_zero_vat():
    for treatment in (TaxTreatment.ZERO_RATE, TaxTreatment.EXEMPT):
        assert calculate_vat(Decimal("500.00"), treatment) == Decimal("0.00")


def test_currency_is_irrelevant_to_the_calculation():
    """calculate_vat takes only an amount and a treatment — there is no
    currency parameter at all, because currency must never change the tax
    rate (see app.domain.demo_business)."""
    assert calculate_vat(Decimal("118.00"), TaxTreatment.STANDARD) == Decimal("18.00")


def test_decimal_rounding_uses_round_half_up_to_two_places():
    # 10.00 * 18/118 = 1.5254237... -> rounds to 1.53 (ROUND_HALF_UP)
    assert calculate_vat(Decimal("10.00"), TaxTreatment.STANDARD) == Decimal("1.53")
    # 1.00 * 18/118 = 0.15254... -> rounds to 0.15
    assert calculate_vat(Decimal("1.00"), TaxTreatment.STANDARD) == Decimal("0.15")


def test_vat_rate_snapshot_standard_is_the_configured_rate():
    assert vat_rate_snapshot(TaxTreatment.STANDARD) == Decimal("0.18")


def test_vat_rate_snapshot_zero_rate_and_exempt_are_zero():
    assert vat_rate_snapshot(TaxTreatment.ZERO_RATE) == Decimal("0.00")
    assert vat_rate_snapshot(TaxTreatment.EXEMPT) == Decimal("0.00")


def test_vat_amount_is_consistent_accepts_exact_match():
    assert vat_amount_is_consistent(Decimal("118.00"), TaxTreatment.STANDARD, Decimal("18.00")) is True


def test_vat_amount_is_consistent_accepts_one_cent_rounding_tolerance():
    assert vat_amount_is_consistent(Decimal("118.00"), TaxTreatment.STANDARD, Decimal("18.01")) is True
    assert vat_amount_is_consistent(Decimal("118.00"), TaxTreatment.STANDARD, Decimal("17.99")) is True


def test_vat_amount_is_consistent_rejects_a_mismatched_value():
    assert vat_amount_is_consistent(Decimal("118.00"), TaxTreatment.STANDARD, Decimal("99.00")) is False


def test_vat_amount_is_consistent_rejects_nonzero_vat_for_exempt():
    assert vat_amount_is_consistent(Decimal("100.00"), TaxTreatment.EXEMPT, Decimal("18.00")) is False
