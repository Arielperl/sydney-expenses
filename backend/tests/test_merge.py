from datetime import date
from decimal import Decimal

from app.services.extraction.merge import (
    drop_resolved_not_confident_warnings,
    merge_field,
    merge_receipt_fields,
)
from app.services.extraction.receipt_parser import ParsedField, ParsedReceiptCandidates


def test_model_value_used_as_is_when_parser_found_nothing():
    result = merge_field("total", Decimal("10.00"), None)
    assert result.value == Decimal("10.00")
    assert result.warnings == ()


def test_parser_fills_gap_when_model_returns_null_high_confidence():
    candidate = ParsedField(Decimal("60.50"), "high", "evidence")
    result = merge_field("total", None, candidate)
    assert result.value == Decimal("60.50")
    assert result.warnings == ("total_from_ocr",)


def test_parser_fills_gap_when_model_returns_null_medium_confidence():
    candidate = ParsedField(Decimal("60.50"), "medium", "evidence")
    result = merge_field("total", None, candidate)
    assert result.value == Decimal("60.50")
    assert result.warnings == ("total_from_ocr",)


def test_low_confidence_parser_candidate_never_fills_a_gap():
    candidate = ParsedField("Some Shaky Guess", "low", "evidence")
    result = merge_field("business_name", None, candidate)
    assert result.value is None
    assert result.warnings == ()


def test_agreement_between_model_and_parser_is_silent():
    candidate = ParsedField(Decimal("60.50"), "high", "evidence")
    result = merge_field("total", Decimal("60.50"), candidate)
    assert result.value == Decimal("60.50")
    assert result.warnings == ()


def test_conflict_with_high_confidence_parser_prefers_parser_and_warns():
    candidate = ParsedField(Decimal("60.50"), "high", "evidence")
    result = merge_field("total", Decimal("99.00"), candidate)
    assert result.value == Decimal("60.50")
    assert result.warnings == ("total_conflicting_sources",)


def test_conflict_with_low_confidence_parser_prefers_model_and_still_warns():
    candidate = ParsedField(Decimal("1.00"), "low", "evidence")
    result = merge_field("total", Decimal("99.00"), candidate)
    assert result.value == Decimal("99.00")
    assert result.warnings == ("total_conflicting_sources",)


def test_date_conflict_uses_confidence_tier():
    candidate = ParsedField(date(2024, 1, 1), "high", "evidence")
    result = merge_field("date", date(2024, 2, 2), candidate)
    assert result.value == date(2024, 1, 1)
    assert result.warnings == ("date_conflicting_sources",)


def test_business_name_agreement_is_case_and_whitespace_insensitive():
    candidate = ParsedField("shufersal", "high", "evidence")
    result = merge_field("business_name", "  Shufersal  ", candidate)
    assert result.warnings == ()


def test_merge_receipt_fields_never_leaks_evidence():
    candidates = ParsedReceiptCandidates(
        total=ParsedField(Decimal("60.50"), "high", "some raw receipt line with personal data"),
    )
    merged = merge_receipt_fields(
        business_name=None,
        receipt_number=None,
        date=None,
        total=None,
        vat=None,
        currency=None,
        candidates=candidates,
    )
    assert "some raw receipt line" not in str(merged)


def test_drop_resolved_not_confident_warnings_removes_stale_code():
    candidates = ParsedReceiptCandidates(total=ParsedField(Decimal("60.50"), "high", "evidence"))
    merged = merge_receipt_fields(
        business_name=None,
        receipt_number=None,
        date=None,
        total=None,  # model said null...
        vat=None,
        currency=None,
        candidates=candidates,  # ...but the parser recovered it
    )
    warnings = drop_resolved_not_confident_warnings(
        ["total_not_confident", "vat_amount_not_confident"], merged
    )
    assert "total_not_confident" not in warnings
    assert "vat_amount_not_confident" in warnings  # vat is genuinely still null


def test_drop_resolved_not_confident_warnings_keeps_warning_for_still_null_field():
    merged = merge_receipt_fields(
        business_name=None,
        receipt_number=None,
        date=None,
        total=None,
        vat=None,
        currency=None,
        candidates=ParsedReceiptCandidates(),
    )
    warnings = drop_resolved_not_confident_warnings(["total_not_confident"], merged)
    assert warnings == ["total_not_confident"]
