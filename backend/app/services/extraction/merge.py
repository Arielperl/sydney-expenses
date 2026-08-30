"""Combines the vision model's output with deterministic parser candidates.

Policy, per field:

- If the parser found nothing, the model's value (if any) is used as-is —
  unchanged from previous behavior.
- If the model returned null but the parser found a candidate, the parser's
  value is used *provided* it is at least "medium" confidence — a "low"
  confidence guess (e.g. an unlabeled repeated number, a shaky merchant-name
  guess) is never used to fill a gap the model itself declined to fill,
  matching "never invent a value" for the weakest evidence tier. Using a
  medium/high-confidence parser value here is flagged with a `*_from_ocr`
  warning so the user knows this field came from deterministic text
  matching, not the vision model itself.
- If both the model and the parser produced a value and they agree, the
  value is used with no extra warning.
- If both produced a value and they *disagree*, this is a genuine conflict:
  it is never resolved silently. The higher-confidence source wins (a
  "high"-confidence, clearly labeled parser match outranks a vision-model
  guess on a low-resolution photo), but a `*_conflicting_sources` warning is
  always added so the user is prompted to double-check the field, per the
  "surfaced for user review" requirement.

Raw OCR evidence (the matched line/snippet) is deliberately never included in
the return value here — only the field-level scalar/warning codes are, so it
can never leak into an API response or a log line.
"""

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Generic, TypeVar

from app.services.extraction.receipt_parser import ParsedField, ParsedReceiptCandidates

T = TypeVar("T")


@dataclass(frozen=True)
class MergedField(Generic[T]):
    value: T | None
    warnings: tuple[str, ...] = ()


def _values_equal(a, b) -> bool:
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        try:
            return abs(Decimal(a) - Decimal(b)) <= Decimal("0.01")
        except Exception:  # noqa: BLE001 - non-comparable values are simply not equal
            return False
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().casefold() == b.strip().casefold()
    return a == b


def merge_field(
    field_name: str,
    model_value: T | None,
    parser_candidate: ParsedField | None,
) -> MergedField[T]:
    if parser_candidate is None:
        return MergedField(model_value)

    if model_value is None:
        if parser_candidate.confidence in ("high", "medium"):
            return MergedField(parser_candidate.value, (f"{field_name}_from_ocr",))
        return MergedField(None)

    if _values_equal(model_value, parser_candidate.value):
        return MergedField(model_value)

    warning = f"{field_name}_conflicting_sources"
    if parser_candidate.confidence == "high":
        return MergedField(parser_candidate.value, (warning,))
    return MergedField(model_value, (warning,))


@dataclass(frozen=True)
class MergedReceiptFields:
    business_name: MergedField[str]
    receipt_number: MergedField[str]
    date: MergedField[date_type]
    total: MergedField[Decimal]
    vat: MergedField[Decimal]
    currency: MergedField[str]


def merge_receipt_fields(
    *,
    business_name: str | None,
    receipt_number: str | None,
    date: date_type | None,
    total: Decimal | None,
    vat: Decimal | None,
    currency: str | None,
    candidates: ParsedReceiptCandidates,
) -> MergedReceiptFields:
    return MergedReceiptFields(
        business_name=merge_field("business_name", business_name, candidates.business_name),
        receipt_number=merge_field("receipt_number", receipt_number, candidates.receipt_number),
        date=merge_field("date", date, candidates.date),
        total=merge_field("total", total, candidates.total),
        vat=merge_field("vat", vat, candidates.vat),
        currency=merge_field("currency", currency, candidates.currency),
    )


# Maps each field to the "not confident" warning code the model may have
# emitted for it *before* the merge above possibly filled that field in from
# a deterministic parser candidate — see drop_resolved_not_confident_warnings.
_NOT_CONFIDENT_CODE_BY_FIELD = {
    "business_name": "business_name_not_confident",
    "receipt_number": "receipt_number_not_confident",
    "date": "date_not_confident",
    "total": "total_not_confident",
    "vat": "vat_amount_not_confident",
}


def drop_resolved_not_confident_warnings(warnings: list[str], merged: MergedReceiptFields) -> list[str]:
    """The model may legitimately warn "total_not_confident" while itself
    returning null for total — but if the merge above then filled that same
    field in (from a confident parser candidate, or because it agreed with a
    parser candidate), keeping that now-stale warning around would show the
    user a contradictory "not confident" caption on a field that has, in
    fact, been confidently filled in. Warnings for fields that are still
    genuinely null are untouched here — sanitize_extracted_fields adds those
    itself from the final merged value, so nothing is lost."""
    resolved = {
        "business_name": merged.business_name.value is not None,
        "receipt_number": merged.receipt_number.value is not None,
        "date": merged.date.value is not None,
        "total": merged.total.value is not None,
        "vat": merged.vat.value is not None,
    }
    stale_codes = {code for field, code in _NOT_CONFIDENT_CODE_BY_FIELD.items() if resolved[field]}
    return [w for w in warnings if w not in stale_codes]
