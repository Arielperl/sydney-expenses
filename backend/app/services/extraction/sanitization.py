"""Business-rule sanitization shared by every real (non-mocked) extraction provider.

Keeping this in one place means OpenAI and local (Ollama) extraction can never
silently diverge on what counts as a valid total, a trustworthy VAT figure, or a
well-formed currency code — the model's raw output is never trusted as-is.
"""

from datetime import date as date_type
from decimal import ROUND_HALF_UP, Decimal

from app.models.expense import ExpenseCategory
from app.schemas.receipt import ExtractedReceiptData
from app.schemas.validators import validate_currency_code

# Every warning code the frontend i18n files translate. Anything else the model
# (or, in principle, a future provider) emits is normalized to a generic fallback
# code rather than shown to the user as raw, possibly-untranslated text — a local,
# quantized model is not fully constrained to a fixed vocabulary the way a strict
# hosted structured-output schema is, and has been observed to emit free-text
# explanations here instead of one of these codes.
KNOWN_WARNING_CODES = {
    "business_name_not_confident",
    "receipt_number_not_confident",
    "date_not_confident",
    "total_not_confident",
    "vat_amount_not_confident",
    "category_not_confident",
    "ocr_unavailable",
    "business_name_from_ocr",
    "receipt_number_from_ocr",
    "date_from_ocr",
    "total_from_ocr",
    "vat_from_ocr",
    "currency_from_ocr",
    "business_name_conflicting_sources",
    "receipt_number_conflicting_sources",
    "date_conflicting_sources",
    "total_conflicting_sources",
    "vat_conflicting_sources",
    "currency_conflicting_sources",
    "extraction_incomplete",
}

FALLBACK_WARNING_CODE = "extraction_incomplete"


def normalize_warnings(warnings: list[str]) -> list[str]:
    """Maps any warning not in `KNOWN_WARNING_CODES` to a safe generic fallback
    code (never raw, possibly-untranslated model text) and deduplicates while
    preserving order."""
    normalized: list[str] = []
    for warning in warnings:
        code = warning if warning in KNOWN_WARNING_CODES else FALLBACK_WARNING_CODE
        if code not in normalized:
            normalized.append(code)
    return normalized


def to_decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    # Convert via str(), never straight from the float, so binary floating-point
    # noise from the model's JSON number never leaks into the stored amount.
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_quality_score(
    business_name: str | None,
    total: Decimal | None,
    currency: str | None,
    category: ExpenseCategory | None,
    warnings: list[str],
) -> float:
    """A documented heuristic, not a calibrated probability: no provider's
    self-reported confidence is trusted. Scores field completeness (business name,
    total, currency, category present) minus a penalty per warning raised.

    This is a *completeness/quality* signal — how much of the receipt was
    successfully read and how many caveats were raised along the way — never a
    statistically calibrated probability that the extracted values are correct.
    A high score means "most fields were found with few caveats", not "this is
    N% likely to be accurate"."""
    important_fields = [business_name, total, currency, category]
    completeness = sum(1 for field in important_fields if field) / len(important_fields)
    penalty = min(len(warnings) * 0.15, 0.6)
    return round(max(0.0, min(1.0, completeness - penalty)), 2)


def sanitize_extracted_fields(
    *,
    business_name: str | None,
    receipt_number: str | None,
    date_str: str | None,
    total_raw: float | None,
    vat_raw: float | None,
    currency_raw: str | None,
    category: ExpenseCategory,
    warnings: list[str],
) -> ExtractedReceiptData:
    warnings = list(warnings)

    parsed_date: date_type | None = None
    if date_str:
        try:
            parsed_date = date_type.fromisoformat(date_str)
            if parsed_date > date_type.today():
                parsed_date = None
                warnings.append("date_not_confident")
        except ValueError:
            warnings.append("date_not_confident")

    total = to_decimal(total_raw)
    vat = to_decimal(vat_raw)

    if vat is not None and total is not None and vat > total:
        # The model contradicted itself (VAT can't exceed the total); discard
        # rather than surface a nonsensical number for the user to review.
        vat = None
        if "vat_amount_not_confident" not in warnings:
            warnings.append("vat_amount_not_confident")

    try:
        currency = validate_currency_code(currency_raw) if currency_raw else "ILS"
    except ValueError:
        currency = "ILS"

    if not business_name and "business_name_not_confident" not in warnings:
        warnings.append("business_name_not_confident")
    if total is None and "total_not_confident" not in warnings:
        warnings.append("total_not_confident")
    if not receipt_number and "receipt_number_not_confident" not in warnings:
        warnings.append("receipt_number_not_confident")
    if vat is None and "vat_amount_not_confident" not in warnings:
        warnings.append("vat_amount_not_confident")

    warnings = normalize_warnings(warnings)
    quality_score = compute_quality_score(business_name, total, currency, category, warnings)

    return ExtractedReceiptData(
        business_name=business_name,
        receipt_number=receipt_number,
        date=parsed_date,
        total=total,
        vat=vat,
        currency=currency,
        category=category,
        confidence=quality_score,
        warnings=warnings,
    )
