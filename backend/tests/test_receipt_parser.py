from datetime import date
from decimal import Decimal

from app.services.extraction.receipt_parser import (
    ParsedField,
    parse_receipt_candidates,
    parse_receipt_text,
)

# Every fixture below is a hand-authored, synthetic OCR-text sample loosely
# modeled on general Israeli retail receipt conventions — never copied from a
# real receipt.


def test_extracts_receipt_number_next_to_hebrew_label():
    text = 'שופרסל דיל\nמספר קבלה: 4821\nסה"כ לתשלום 55.00'
    result = parse_receipt_text(text)
    assert result.receipt_number.value == "4821"
    assert result.receipt_number.confidence == "high"


def test_extracts_receipt_number_alternate_label_order():
    text = "קבלה מספר 7734\nלתשלום 20.00"
    result = parse_receipt_text(text)
    assert result.receipt_number.value == "7734"


def test_extracts_hebrew_date_dd_mm_yyyy():
    text = "תאריך: 15/03/2024 - 12:30\nלתשלום 40.00"
    result = parse_receipt_text(text)
    assert result.date.value == date(2024, 3, 15)
    assert result.date.confidence == "high"


def test_rejects_future_date():
    text = "תאריך: 15/03/2099\nלתשלום 40.00"
    result = parse_receipt_text(text)
    assert result.date is None


def test_rejects_invalid_calendar_date():
    text = "תאריך: 32/13/2024\nלתשלום 40.00"
    result = parse_receipt_text(text)
    assert result.date is None


def test_extracts_total_with_strong_label():
    text = "מצרך א 10.00\nמצרך ב 20.00\nסה\"כ לתשלום 30.00"
    result = parse_receipt_text(text)
    assert result.total.value == Decimal("30.00")
    assert result.total.confidence == "high"


def test_extracts_total_with_weak_label():
    text = "מצרך א 10.00\nסה\"כ 10.00"
    result = parse_receipt_text(text)
    assert result.total.value == Decimal("10.00")
    assert result.total.confidence == "medium"


def test_does_not_confuse_item_count_line_with_total():
    text = 'סה"כ פריטים: 3\nסה"כ לתשלום 45.00'
    result = parse_receipt_text(text)
    assert result.total.value == Decimal("45.00")


def test_rejects_change_line_as_total_when_a_real_total_exists():
    text = 'סה"כ לתשלום 45.00\nעודף 5.00'
    result = parse_receipt_text(text)
    assert result.total.value == Decimal("45.00")


def test_rejects_item_price_as_total():
    """Two clearly itemized rows (qty, unit price, line total) must never be
    mistaken for the final total, even without any explicit total label."""
    text = "חלב 6.90 6.90 1\nלחם 12.00 12.00 1"
    result = parse_receipt_text(text)
    # No usable label and no repeated non-item amount -> no confident total.
    assert result.total is None


def test_repeated_non_item_amount_is_a_low_confidence_total_fallback():
    text = "חלב 6.90 6.90 1\nX 60.50\nY 60.50"
    result = parse_receipt_text(text)
    assert result.total.value == Decimal("60.50")
    assert result.total.confidence == "low"


def test_uncertain_change_label_is_last_resort_when_nothing_else_found():
    """A narrow/noisy receipt photo can garble the true total label into
    something OCR reads as a change/cash label — treated as a low-confidence
    last resort, not silently discarded, since it's still real printed
    evidence, just of uncertain semantic meaning."""
    text = "עודף 60.50"
    result = parse_receipt_text(text)
    assert result.total.value == Decimal("60.50")
    assert result.total.confidence == "low"


def test_extracts_vat_amount_distinct_from_rate():
    text = 'מע"מ 17.00 מע"מ 8.50'
    result = parse_receipt_text(text)
    assert result.vat.value == Decimal("8.50")
    assert result.vat.confidence == "high"


def test_extracts_vat_with_truncated_label():
    """Tesseract frequently drops the trailing מ of מע"מ at low resolution."""
    text = 'מע" 9.22'
    result = parse_receipt_text(text)
    assert result.vat.value == Decimal("9.22")


def test_decimal_comma_is_normalized():
    text = 'סה"כ לתשלום 30,50'
    result = parse_receipt_text(text)
    assert result.total.value == Decimal("30.50")


def test_unknown_total_remains_none_not_zero():
    text = "שופרסל דיל\nתודה ולהתראות"
    result = parse_receipt_text(text)
    assert result.total is None


def test_unknown_date_remains_none():
    text = 'סה"כ לתשלום 30.00'
    result = parse_receipt_text(text)
    assert result.date is None


def test_currency_symbol_detected_as_ils():
    text = "לתשלום ₪30.00"
    result = parse_receipt_text(text)
    assert result.currency.value == "ILS"


def test_business_name_not_guessed_when_unclear():
    text = "1234 5678 9012\nלתשלום 30.00"
    result = parse_receipt_text(text)
    assert result.business_name is None


def test_business_name_low_confidence_candidate_from_clean_header_line():
    text = "שופרסל דיל\nלתשלום 30.00"
    result = parse_receipt_text(text)
    assert result.business_name is not None
    assert result.business_name.confidence == "low"


# --- Cross-attempt merge (parse_receipt_candidates) -------------------------


def test_merge_prefers_high_tier_over_repeated_low_tier_coincidence():
    """A single well-labeled total must win even if a completely different
    amount happens to repeat (coincidentally) across other OCR attempts."""
    texts = [
        'סה"כ לתשלום 45.00',
        "X 12.00\nY 12.00",  # 12.00 repeats but has no label at all
    ]
    result = parse_receipt_candidates(texts)
    assert result.total.value == Decimal("45.00")
    assert result.total.confidence == "high"


def test_merge_upgrades_confidence_when_two_attempts_agree():
    texts = ['סה"כ 30.00', 'סה"כ 30.00']
    result = parse_receipt_candidates(texts)
    assert result.total.value == Decimal("30.00")
    assert result.total.confidence == "high"  # medium -> high on agreement


def test_merge_recovers_valid_date_even_if_top_attempt_misreads_it():
    """Models a real observed OCR failure mode: one attempt misreads a digit
    (producing an invalid date, silently dropped), while another attempt on
    the same receipt reads it correctly."""
    texts = [
        "תאריך: 80/09/2013",  # invalid day, dropped
        "תאריך: 30/09/2013",  # valid
    ]
    result = parse_receipt_candidates(texts)
    assert result.date.value == date(2013, 9, 30)


def test_merge_handles_no_candidates_at_all():
    result = parse_receipt_candidates(["תודה ולהתראות", "בברכה"])
    assert result.total is None
    assert result.date is None
    assert result.vat is None
