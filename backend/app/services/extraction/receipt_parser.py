"""Deterministic, regex-based extraction of structured values from OCR text.

The vision model is not trusted to reliably read obvious, structurally
labeled values (a receipt number next to "מספר קבלה", a total next to
"לתשלום") — a low-resolution or noisy photo can make the model default to
null even when the correct value is sitting in the OCR text in plain sight.
This module extracts *candidates* deterministically instead, each carrying a
confidence tier ("high"/"medium"/"low") and a short evidence string (the
matched snippet) so a merge policy can combine them with the model's own
output. Evidence is for internal merge/debugging use only — it is never
included in any API response, so raw receipt text never leaks through it.

Nothing here is specific to any one receipt: every pattern is a general
Hebrew/English retail-receipt convention (see the module docstring items in
the project's task list), not a value copied from a specific real receipt.
"""

import re
from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Literal

Confidence = Literal["high", "medium", "low"]

# Bidi/RTL control characters Tesseract frequently emits around Hebrew text;
# stripping them keeps label matching and money parsing from silently failing.
_BIDI_MARKS_RE = re.compile("[‎‏‪-‮]")

_MONEY_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[.,]\d{2}))(?!\d)")

# A line of exactly three whitespace-separated numeric-looking tokens is the
# shape of an itemized "line-total  unit-price  quantity" row, never a total.
_ITEM_LINE_RE = re.compile(r"^[\d.,]+\s+[\d.,]+\s+\d+$")

_TOTAL_STRONG_LABEL_RE = re.compile(r'(?:סה"?כ\s*ל?תשלום|לתשלום)')
_TOTAL_WEAK_LABEL_RE = re.compile(r'(?:סה"?כ(?!\s*פריטים)|שולם|total)', re.IGNORECASE)
_TOTAL_ITEMS_COUNT_RE = re.compile(r'סה"?כ\s*פריטים')
_CHANGE_OR_CASH_RE = re.compile(r"(?:עודף|change|מזומן|cash)", re.IGNORECASE)

# The trailing מ is frequently dropped or merged away by OCR at typical
# receipt-photo resolutions (e.g. "מע"מ" reads back as just "מע""), so it is
# optional here; the money-amount-on-the-same-line requirement elsewhere in
# this module keeps a bare "מע" substring from matching unrelated text.
_VAT_LABEL_RE = re.compile(r'(?:מע"?מ?|vat)', re.IGNORECASE)

_DATE_RE = re.compile(r"\b([0-3]?\d)[./\-]([01]?\d)[./\-](\d{4}|\d{2})\b")

_RECEIPT_NUMBER_LABEL_RE = re.compile(r'(?:מספר\s*קבלה|קבלה\s*מספר|קבלה\s*#|receipt\s*(?:no|number|#))', re.IGNORECASE)
_STANDALONE_NUMBER_RE = re.compile(r"\b(\d{3,})\b")

_CURRENCY_SYMBOLS = {
    "₪": "ILS",
    'ש"ח': "ILS",
    "שח": "ILS",
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
}

# Non-name boilerplate lines that sometimes appear near the top/bottom of a
# receipt and must never be mistaken for a merchant name.
_NON_NAME_LINE_RE = re.compile(
    r"(תודה|להתראות|קבלה|לקוח|תאריך|מספר|עוסק|רחוב|טלפון|receipt|thank\s*you)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedField:
    value: object
    confidence: Confidence
    evidence: str


@dataclass(frozen=True)
class ParsedReceiptCandidates:
    business_name: ParsedField | None = None
    receipt_number: ParsedField | None = None
    date: ParsedField | None = None
    total: ParsedField | None = None
    vat: ParsedField | None = None
    currency: ParsedField | None = None


def _normalize(text: str) -> str:
    return _BIDI_MARKS_RE.sub("", text)


def _extract_money_amounts(line: str) -> list[Decimal]:
    amounts = []
    for match in _MONEY_RE.finditer(line.replace(",", ".") if _looks_like_decimal_comma(line) else line):
        try:
            amounts.append(Decimal(match.group(1)))
        except Exception:  # noqa: BLE001 - a malformed match is simply skipped
            continue
    return amounts


def _looks_like_decimal_comma(line: str) -> bool:
    """A comma immediately between two digit groups of length 1-3 and 2 is
    almost certainly a decimal separator (e.g. "60,50"), not a thousands
    separator — receipts in this domain never have four-digit-plus totals."""
    return bool(re.search(r"\d{1,3},\d{2}(?!\d)", line))


def _is_rate_like(value: Decimal) -> bool:
    """A round percentage-shaped value (e.g. 17.00, 18.00) in the typical VAT
    rate range — used to tell a VAT *rate* apart from a VAT *amount* when both
    appear on the same OCR line, without hardcoding one specific rate."""
    return Decimal("5") <= value <= Decimal("25") and value == value.to_integral_value()


_SMALL_QTY_RE = re.compile(r"(?<!\d)[1-9](?!\d)")


def _is_item_line(line: str) -> bool:
    """A line is treated as an itemized row — never a candidate for the final
    total — if it has the *shape* of one: a small quantity digit alongside at
    least two money-shaped amounts (line-total and unit-price). Matching by
    shape rather than an exact 3-token layout is deliberate: OCR frequently
    interleaves a garbled Hebrew item name between the numbers, or reorders
    tokens due to RTL confusion, so a strict positional pattern misses most
    real item lines."""
    if _ITEM_LINE_RE.match(line.strip()):
        return True
    amounts = _extract_money_amounts(line)
    return len(amounts) >= 2 and bool(_SMALL_QTY_RE.search(line))


def _find_total(lines: list[str]) -> ParsedField | None:
    candidate_lines = [line for line in lines if not _is_item_line(line) and not _TOTAL_ITEMS_COUNT_RE.search(line)]

    for line in candidate_lines:
        if _TOTAL_STRONG_LABEL_RE.search(line):
            amounts = _extract_money_amounts(line)
            if amounts:
                return ParsedField(amounts[-1], "high", line.strip())

    excluded_by_change_or_cash: list[Decimal] = []
    for line in candidate_lines:
        if _TOTAL_WEAK_LABEL_RE.search(line):
            amounts = _extract_money_amounts(line)
            if not amounts:
                continue
            if _CHANGE_OR_CASH_RE.search(line):
                excluded_by_change_or_cash.extend(amounts)
                continue
            return ParsedField(amounts[-1], "medium", line.strip())

    # A line labeled only "change"/"cash tendered" is excluded above by design
    # (task requirement) — but OCR at typical receipt-photo resolution is
    # unreliable specifically on short summary-section labels, so a label
    # read as "change" is itself not fully trustworthy. Record these purely
    # to make them available to the last-resort tier below; they are never
    # used at medium/high confidence.
    for line in candidate_lines:
        if _CHANGE_OR_CASH_RE.search(line) and not _TOTAL_WEAK_LABEL_RE.search(line):
            excluded_by_change_or_cash.extend(_extract_money_amounts(line))

    # Fallback: no usable label survived OCR at all (common on a noisy, narrow
    # photo). An amount that is printed more than once outside the itemized
    # lines is very likely the final total repeated in a payment summary —
    # never an individual item price, which only ever appears once per line.
    counts: dict[Decimal, int] = {}
    for line in candidate_lines:
        for amount in _extract_money_amounts(line):
            counts[amount] = counts.get(amount, 0) + 1
    repeated = [amount for amount, count in counts.items() if count >= 2]
    if repeated:
        return ParsedField(max(repeated), "low", "repeated amount across receipt")

    # Last resort: a change/cash-labeled amount is the only signal at all.
    # OCR's read of that specific label is treated as unreliable rather than
    # authoritative — surfaced at low confidence for the user to confirm,
    # rather than silently discarded and left blank.
    if excluded_by_change_or_cash:
        return ParsedField(max(excluded_by_change_or_cash), "low", "only found on an uncertain-label line")

    return None


def _find_vat(lines: list[str]) -> ParsedField | None:
    for line in lines:
        if not _VAT_LABEL_RE.search(line):
            continue
        amounts = _extract_money_amounts(line)
        if not amounts:
            continue
        if len(amounts) == 1:
            if _is_rate_like(amounts[0]):
                # Almost certainly just the VAT *rate* (e.g. "17.00%"), not the
                # amount — likely because OCR failed to also capture the real
                # amount on this line. Reporting the rate as if it were the
                # amount would be a confident-looking wrong number; better to
                # report nothing and let another line/the model try instead.
                continue
            return ParsedField(amounts[0], "medium", line.strip())
        non_rate = [a for a in amounts if not _is_rate_like(a)]
        if len(non_rate) == 1:
            return ParsedField(non_rate[0], "high", line.strip())
        return ParsedField(min(amounts), "medium", line.strip())
    return None


def _find_date(text: str) -> ParsedField | None:
    for match in _DATE_RE.finditer(text):
        day_str, month_str, year_str = match.groups()
        try:
            day, month, year = int(day_str), int(month_str), int(year_str)
        except ValueError:
            continue
        if year < 100:
            year += 2000 if year < 50 else 1900
        if year < 2000:
            continue
        try:
            candidate = date_type(year, month, day)
        except ValueError:
            continue
        if candidate > date_type.today():
            continue
        return ParsedField(candidate, "high", match.group(0))
    return None


def _find_receipt_number(lines: list[str]) -> ParsedField | None:
    for line in lines:
        if _RECEIPT_NUMBER_LABEL_RE.search(line):
            match = _STANDALONE_NUMBER_RE.search(line)
            if match:
                return ParsedField(match.group(1), "high", line.strip())
    return None


def _find_currency(text: str) -> ParsedField | None:
    lower = text.lower()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in lower or symbol in text:
            return ParsedField(code, "medium", symbol)
    return None


def _find_business_name(lines: list[str]) -> ParsedField | None:
    """Best-effort only, and deliberately conservative: a merchant name is far
    less structurally reliable to detect than a labeled amount or date, so
    this only returns a candidate when a short, letter-heavy, unlabeled line
    appears near the top of the receipt — otherwise it returns nothing rather
    than guessing, matching "extract only if sufficiently clear"."""
    for line in lines[:5]:
        stripped = line.strip()
        if not (2 <= len(stripped) <= 40):
            continue
        if _NON_NAME_LINE_RE.search(stripped):
            continue
        if any(ch.isdigit() for ch in stripped):
            continue
        letters = sum(1 for ch in stripped if ch.isalpha())
        if letters < max(2, len(stripped) * 0.6):
            continue
        return ParsedField(stripped, "low", stripped)
    return None


def parse_receipt_text(raw_text: str) -> ParsedReceiptCandidates:
    """Parses a single OCR text into deterministic field candidates."""
    text = _normalize(raw_text)
    lines = [line for line in text.splitlines() if line.strip()]

    return ParsedReceiptCandidates(
        business_name=_find_business_name(lines),
        receipt_number=_find_receipt_number(lines),
        date=_find_date(text),
        total=_find_total(lines),
        vat=_find_vat(lines),
        currency=_find_currency(text),
    )


_FIELDS = ("business_name", "receipt_number", "date", "total", "vat", "currency")


def parse_receipt_candidates(ocr_texts: list[str]) -> ParsedReceiptCandidates:
    """Parses several ranked OCR attempts (e.g. different Tesseract PSM modes
    on the same receipt) and merges them per field: a field found identically
    by two or more independent attempts is upgraded to "high" confidence
    (cross-validated); otherwise the first valid candidate found (in the
    given, presumably best-first, order) is kept as-is.

    This matters in practice — a narrow, noisy receipt photo can have
    different Tesseract configurations disagree on a single misread digit
    (e.g. one config misreads a day as invalid, another reads it correctly);
    since every candidate is independently validated (a date must be a real,
    non-future calendar date), scanning several attempts recovers a value
    that the single top-scoring attempt alone would have missed, without
    ever fabricating a value no attempt actually produced.
    """
    per_field: dict[str, list[ParsedField]] = {field: [] for field in _FIELDS}

    for ocr_text in ocr_texts:
        parsed = parse_receipt_text(ocr_text)
        for field in _FIELDS:
            candidate = getattr(parsed, field)
            if candidate is not None:
                per_field[field].append(candidate)

    tier_upgrade: dict[Confidence, Confidence] = {"low": "medium", "medium": "high", "high": "high"}

    merged: dict[str, ParsedField | None] = {}
    for field, candidates in per_field.items():
        merged[field] = None
        # Prefer the highest confidence tier seen by ANY attempt first — a
        # single well-labeled read must never be displaced by two low-tier
        # guesses that merely happen to agree (they are not independent
        # evidence; they usually come from the same underlying OCR noise).
        for tier in ("high", "medium", "low"):
            tier_candidates = [c for c in candidates if c.confidence == tier]
            if not tier_candidates:
                continue
            value_counts: dict[object, int] = {}
            for candidate in tier_candidates:
                value_counts[candidate.value] = value_counts.get(candidate.value, 0) + 1
            agreed_value = next((value for value, count in value_counts.items() if count >= 2), None)
            if agreed_value is not None:
                evidence = next(c.evidence for c in tier_candidates if c.value == agreed_value)
                merged[field] = ParsedField(agreed_value, tier_upgrade[tier], evidence)
            else:
                merged[field] = tier_candidates[0]
            break

    return ParsedReceiptCandidates(**merged)
