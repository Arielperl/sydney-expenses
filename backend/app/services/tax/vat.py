"""Israeli VAT calculation — the single place `vat_amount` is computed from
`gross_amount` and `tax_treatment`. `gross_amount` is always VAT-inclusive
(it's what the customer paid), so the VAT component is `gross * rate / (1 +
rate)`, never `gross * rate` — that would compute VAT as if it were being
added on top of an already-VAT-inclusive amount, over-counting it. For
gross=118.00 and rate=18%: 118 * 0.18 / 1.18 = 18.00 exactly (VAT), leaving
100.00 as revenue before VAT — not 118 * 0.18 = 21.24.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.domain.demo_business import DEMO_STANDARD_VAT_RATE
from app.models.sale import TaxTreatment

TWO_PLACES = Decimal("0.01")

# How far an externally-reported VAT amount (e.g. from a webhook payload) may
# differ from what this business's own tax configuration would have computed
# and still be trusted — covers ordinary rounding differences between
# systems, never a systematic miscalculation.
VAT_AMOUNT_TOLERANCE = Decimal("0.01")

_ZERO_VAT_TREATMENTS = (TaxTreatment.ZERO_RATE, TaxTreatment.EXEMPT)


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_vat(
    gross_amount: Decimal,
    tax_treatment: TaxTreatment,
    vat_rate: Decimal = DEMO_STANDARD_VAT_RATE,
) -> Decimal:
    """The VAT portion of a VAT-inclusive `gross_amount` for the given tax
    treatment. Zero for `zero_rate` and `exempt`, regardless of amount."""
    if tax_treatment in _ZERO_VAT_TREATMENTS:
        return Decimal("0.00")
    vat = gross_amount * vat_rate / (Decimal("1") + vat_rate)
    return _round_money(vat)


def vat_rate_snapshot(tax_treatment: TaxTreatment, vat_rate: Decimal = DEMO_STANDARD_VAT_RATE) -> Decimal:
    """The rate to persist on `Sale.vat_rate` for a newly created/updated
    sale — a snapshot of the rate actually used, so a future change to
    `DEMO_STANDARD_VAT_RATE` can never change what a past sale is understood
    to have charged. `zero_rate` and `exempt` both snapshot 0; the
    distinction between them is preserved by `tax_treatment` itself, not by
    this rate."""
    if tax_treatment in _ZERO_VAT_TREATMENTS:
        return Decimal("0.00")
    return vat_rate


def vat_amount_is_consistent(
    gross_amount: Decimal,
    tax_treatment: TaxTreatment,
    reported_vat_amount: Decimal,
    vat_rate: Decimal = DEMO_STANDARD_VAT_RATE,
) -> bool:
    """Whether an externally-reported VAT amount is close enough to what
    this business's own tax configuration would have computed to be
    trusted — within `VAT_AMOUNT_TOLERANCE`, never an exact comparison."""
    expected = calculate_vat(gross_amount, tax_treatment, vat_rate)
    return abs(reported_vat_amount - expected) <= VAT_AMOUNT_TOLERANCE
