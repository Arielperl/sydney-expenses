from datetime import date
from decimal import Decimal

from app.services.extraction.ocr_selection import OcrLine, OcrWord
from app.services.extraction.receipt_parser import (
    parse_receipt_candidates,
    parse_receipt_lines,
)

# Every fixture below is a hand-authored, synthetic OCR-line layout loosely
# modeled on general Israeli retail receipt conventions — never copied from a
# real receipt. `make_lines` mimics real image_to_data() word boxes: each
# line's words get increasing left positions (visual left-to-right order) and
# consecutive top/bottom bands (visual top-to-bottom order).


def make_line(text: str, top: int = 0, height: int = 30) -> OcrLine:
    words = []
    left = 0
    for token in text.split(" "):
        width = len(token) * 12 + 8
        words.append(OcrWord(text=token, left=left, top=top, width=width, height=height, conf=90.0))
        left += width + 20
    return OcrLine(words=tuple(words), text=text, top=top, bottom=top + height, left=0, right=left)


def make_lines(*texts: str, line_height: int = 30, gap: int = 15) -> tuple[OcrLine, ...]:
    lines = []
    top = 0
    for text in texts:
        lines.append(make_line(text, top=top, height=line_height))
        top += line_height + gap
    return tuple(lines)


def test_extracts_receipt_number_next_to_hebrew_label():
    lines = make_lines("שופרסל דיל", "מספר קבלה 4821", 'סה"כ לתשלום 55.00')
    result = parse_receipt_lines(lines)
    assert result.receipt_number.value == "4821"
    assert result.receipt_number.confidence == "high"


def test_receipt_number_preserves_punctuation():
    """A hyphen genuinely printed as part of the identifier must survive —
    never silently stripped down to only the digits."""
    lines = make_lines("חשבונית מספר 12-165732", 'סה"כ לתשלום 690.00')
    result = parse_receipt_lines(lines)
    assert result.receipt_number.value == "12-165732"


def test_receipt_number_on_next_line_when_close():
    lines = make_lines("מספר קבלה", "3-379380", 'סה"כ לתשלום 435.90')
    result = parse_receipt_lines(lines)
    assert result.receipt_number.value == "3-379380"
    assert result.receipt_number.confidence == "medium"


def test_extracts_hebrew_date_dd_mm_yyyy():
    lines = make_lines("תאריך: 15/03/2024 - 12:30", "לתשלום 40.00")
    result = parse_receipt_lines(lines)
    assert result.date.value == date(2024, 3, 15)
    assert result.date.confidence == "high"


def test_rejects_future_date():
    lines = make_lines("תאריך: 15/03/2099", "לתשלום 40.00")
    result = parse_receipt_lines(lines)
    assert result.date is None


def test_rejects_invalid_calendar_date():
    lines = make_lines("תאריך: 32/13/2024", "לתשלום 40.00")
    result = parse_receipt_lines(lines)
    assert result.date is None


def test_date_prefers_the_labeled_date_over_an_unrelated_date_shaped_number():
    """A receipt can print more than one date-shaped number — e.g. a member/
    loyalty number formatted like a date, printed before the real, labeled
    purchase date. The תאריך-labeled one must win, not whichever the scan
    reaches first."""
    lines = make_lines("כרטיס לקוח 01/01/2020", "תאריך: 23/08/2026", 'סה"כ לתשלום 40.00')
    result = parse_receipt_lines(lines)
    assert result.date.value == date(2026, 8, 23)
    assert result.date.confidence == "high"


def test_extracts_total_with_strong_label():
    lines = make_lines("מצרך א 10.00", "מצרך ב 20.00", 'סה"כ לתשלום 30.00')
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("30.00")
    assert result.total.confidence == "high"


def test_extracts_total_with_weak_label():
    lines = make_lines("מצרך א 10.00", 'סה"כ 10.00')
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("10.00")
    assert result.total.confidence == "medium"


def test_total_value_on_next_line_when_close():
    """The label and its amount are sometimes printed on visually stacked
    lines rather than side by side — a narrow or faded receipt often does
    this, and flat text can't recover it without spatial position."""
    lines = make_lines('סה"כ לתשלום', "60.50")
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("60.50")


def test_total_on_far_next_line_is_not_associated():
    """A value several lines away (not vertically adjacent) must not be
    pulled in just because it's the next money-shaped number found."""
    label_line = make_line('סה"כ לתשלום', top=0, height=30)
    far_line = make_line("60.50", top=500, height=30)  # far below — not adjacent
    result = parse_receipt_lines((label_line, far_line))
    assert result.total is None or result.total.value != Decimal("60.50")


def test_does_not_confuse_item_count_line_with_total():
    lines = make_lines('סה"כ פריטים: 3', 'סה"כ לתשלום 45.00')
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("45.00")


def test_rejects_change_line_as_total_when_a_real_total_exists():
    lines = make_lines('סה"כ לתשלום 45.00', "עודף 5.00")
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("45.00")


def test_rejects_authorization_amount_as_total():
    lines = make_lines("אישור 123456 99.99", 'סה"כ לתשלום 45.00')
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("45.00")


def test_rejects_item_price_as_total():
    """Two clearly itemized rows (qty, unit price, line total) must never be
    mistaken for the final total, even without any explicit total label."""
    lines = make_lines("חלב 6.90 6.90 1", "לחם 12.00 12.00 1")
    result = parse_receipt_lines(lines)
    assert result.total is None


def test_repeated_non_item_amount_is_a_low_confidence_total_fallback():
    lines = make_lines("חלב 6.90 6.90 1", "X 60.50", "Y 60.50")
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("60.50")
    assert result.total.confidence == "low"


def test_uncertain_change_label_is_last_resort_when_nothing_else_found():
    lines = make_lines("עודף 60.50")
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("60.50")
    assert result.total.confidence == "low"


def test_extracts_vat_amount_distinct_from_rate():
    lines = make_lines('מע"מ 17.00 מע"מ 8.50')
    result = parse_receipt_lines(lines)
    assert result.vat.value == Decimal("8.50")
    assert result.vat.confidence == "high"


def test_extracts_vat_with_truncated_label():
    """Tesseract frequently drops the trailing מ of מע"מ at low resolution."""
    lines = make_lines('מע" 9.22')
    result = parse_receipt_lines(lines)
    assert result.vat.value == Decimal("9.22")


def test_vat_not_confused_with_taxable_subtotal_same_line():
    """The exact real failure mode this fixes: a taxable-subtotal amount
    (much larger than the VAT itself) printed on the same visual line as the
    VAT label/amount must never be picked as the VAT value — the word
    nearest the label wins, not an arbitrary min()/first amount."""
    lines = make_lines('סכום חייב 584.75 מע"מ 105.25', 'סה"כ לתשלום 690.00')
    result = parse_receipt_lines(lines)
    assert result.vat.value == Decimal("105.25")


def test_vat_not_confused_with_taxable_subtotal_separate_line():
    lines = make_lines("סכום עסקה חייב במעמ 584.75", 'מע"מ 105.25', 'סה"כ לתשלום 690.00')
    result = parse_receipt_lines(lines)
    assert result.vat.value == Decimal("105.25")


def test_vat_never_exceeds_total():
    """Even if the nearest number to a VAT label happens to be larger than
    the total (a clearly invalid VAT), a same-line value that does not
    exceed the total must be preferred if one exists."""
    lines = make_lines('מע"מ 690.00 חייב 105.25', 'סה"כ לתשלום 690.00')
    result = parse_receipt_lines(lines)
    assert result.vat is None or result.vat.value <= Decimal("690.00")


def test_vat_value_on_next_line_when_close():
    lines = make_lines('מע"מ', "25.51")
    result = parse_receipt_lines(lines)
    assert result.vat.value == Decimal("25.51")


def test_decimal_comma_is_normalized():
    lines = make_lines('סה"כ לתשלום 30,50')
    result = parse_receipt_lines(lines)
    assert result.total.value == Decimal("30.50")


def test_unknown_total_remains_none_not_zero():
    lines = make_lines("שופרסל דיל", "תודה ולהתראות")
    result = parse_receipt_lines(lines)
    assert result.total is None


def test_unknown_date_remains_none():
    lines = make_lines('סה"כ לתשלום 30.00')
    result = parse_receipt_lines(lines)
    assert result.date is None


def test_currency_symbol_detected_as_ils():
    lines = make_lines("לתשלום ₪30.00")
    result = parse_receipt_lines(lines)
    assert result.currency.value == "ILS"


def test_business_name_not_guessed_when_unclear():
    lines = make_lines("1234 5678 9012", "לתשלום 30.00")
    result = parse_receipt_lines(lines)
    assert result.business_name is None


def test_business_name_low_confidence_candidate_from_clean_header_line():
    lines = make_lines("שופרסל דיל", "לתשלום 30.00")
    result = parse_receipt_lines(lines)
    assert result.business_name is not None
    assert result.business_name.confidence == "low"


# --- Cross-attempt merge (parse_receipt_candidates) -------------------------


def test_merge_prefers_high_tier_over_repeated_low_tier_coincidence():
    """A single well-labeled total must win even if a completely different
    amount happens to repeat (coincidentally) across other OCR attempts."""
    attempts = [
        make_lines('סה"כ לתשלום 45.00'),
        make_lines("X 12.00", "Y 12.00"),  # 12.00 repeats but has no label at all
    ]
    result = parse_receipt_candidates(attempts)
    assert result.total.value == Decimal("45.00")
    assert result.total.confidence == "high"


def test_merge_upgrades_confidence_when_two_attempts_agree():
    attempts = [make_lines('סה"כ 30.00'), make_lines('סה"כ 30.00')]
    result = parse_receipt_candidates(attempts)
    assert result.total.value == Decimal("30.00")
    assert result.total.confidence == "high"  # medium -> high on agreement


def test_merge_recovers_valid_date_even_if_top_attempt_misreads_it():
    """Models a real observed OCR failure mode: one attempt misreads a digit
    (producing an invalid date, silently dropped), while another attempt on
    the same receipt reads it correctly."""
    attempts = [
        make_lines("תאריך: 80/09/2013"),  # invalid day, dropped
        make_lines("תאריך: 30/09/2013"),  # valid
    ]
    result = parse_receipt_candidates(attempts)
    assert result.date.value == date(2013, 9, 30)


def test_merge_handles_no_candidates_at_all():
    result = parse_receipt_candidates([make_lines("תודה ולהתראות"), make_lines("בברכה")])
    assert result.total is None
    assert result.date is None
    assert result.vat is None


# --- Merchant-name-based category fallback ----------------------------------


def test_infers_groceries_from_market_keyword():
    from app.models.expense import ExpenseCategory
    from app.services.extraction.receipt_parser import infer_category_from_merchant_name

    assert infer_category_from_merchant_name("מיני מרקט השכונה") == ExpenseCategory.GROCERIES


def test_infers_dining_from_cafe_keyword():
    from app.models.expense import ExpenseCategory
    from app.services.extraction.receipt_parser import infer_category_from_merchant_name

    assert infer_category_from_merchant_name("Cafe Nice") == ExpenseCategory.DINING


def test_no_category_inferred_when_merchant_name_unclear():
    from app.services.extraction.receipt_parser import infer_category_from_merchant_name

    assert infer_category_from_merchant_name("XYZ123") is None


def test_no_category_inferred_when_merchant_name_missing():
    from app.services.extraction.receipt_parser import infer_category_from_merchant_name

    assert infer_category_from_merchant_name(None) is None
    assert infer_category_from_merchant_name("") is None
