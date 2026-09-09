"""Deterministic, regex-based extraction of structured values from spatial OCR
data (see ocr_selection.OcrLine/OcrWord).

The vision model is not trusted to reliably read obvious, structurally
labeled values (a receipt number next to "מספר קבלה", a total next to
"לתשלום") — a low-resolution, faded, or noisy photo can make the model
default to null even when the correct value is sitting in the OCR text in
plain sight. This module extracts *candidates* deterministically instead,
each carrying a confidence tier ("high"/"medium"/"low") and a short evidence
string (the matched snippet) so a merge policy can combine them with the
model's own output. Evidence is for internal merge/debugging use only — it is
never included in any API response, so raw receipt text never leaks through it.

Flat text alone loses *where* a label and a value sit relative to each other,
which is exactly what let a taxable-subtotal amount get picked up as VAT on a
real receipt where the true VAT figure sat elsewhere on the line (or on the
next line) than a naive "grab the nearest number in this line of text" pass
assumed. This version works word-by-word within each spatially-reconstructed
line: it finds the label word(s), then picks the *nearest* money-shaped word
to it — first on the same line, then, if none, on the very next line within a
tight vertical-proximity bound — rather than an arbitrary "first" or "last"
amount found anywhere on a line of joined text.

Nothing here is specific to any one receipt: every pattern is a general
Hebrew/English retail-receipt convention, not a value copied from a specific
real receipt.
"""

import re
from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Literal

from app.models.expense import ExpenseCategory
from app.services.extraction.ocr_selection import LINE_PROXIMITY_HEIGHT_MULTIPLE, OcrLine, OcrWord

Confidence = Literal["high", "medium", "low"]

# Bidi/RTL control characters Tesseract frequently emits around Hebrew text;
# stripping them keeps label matching and money parsing from silently failing.
_BIDI_MARKS_RE = re.compile("[‎‏‪-‮]")

# A whole money token, e.g. "60.50", "1,234.56"->"1234.56" after normalization,
# with optional currency symbol/word directly attached.
_MONEY_TOKEN_RE = re.compile(r"^\D{0,3}(\d{1,3}(?:[.,]\d{2}))\D{0,3}$")
_MONEY_ANYWHERE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[.,]\d{2}))(?!\d)")

# A line of exactly three whitespace-separated numeric-looking tokens is the
# shape of an itemized "line-total  unit-price  quantity" row, never a total.
_ITEM_LINE_RE = re.compile(r"^[\d.,]+\s+[\d.,]+\s+\d+$")
_SMALL_QTY_RE = re.compile(r"(?<!\d)[1-9](?!\d)")

_TOTAL_STRONG_LABEL_RE = re.compile(r'(?:סה"?כ\s*ל?תשלום|לתשלום)')
_TOTAL_WEAK_LABEL_RE = re.compile(r'(?:סה"?כ(?!\s*פריטים)|שולם|total)', re.IGNORECASE)
_TOTAL_ITEMS_COUNT_RE = re.compile(r'סה"?כ\s*פריטים')
_CHANGE_OR_CASH_RE = re.compile(r"(?:עודף|change|מזומן|cash)", re.IGNORECASE)
_AUTH_RE = re.compile(r"(?:אישור|authorization|auth\b)", re.IGNORECASE)
_DISCOUNT_RE = re.compile(r"(?:הנחה|discount)", re.IGNORECASE)

# The trailing מ is frequently dropped or merged away by OCR at typical
# receipt-photo resolutions (e.g. "מע"מ" reads back as just "מע""), so it is
# optional here; requiring a nearby money-shaped word elsewhere in this
# module keeps a bare "מע" substring from matching unrelated text.
# A negative lookbehind for a preceding Hebrew letter keeps this from matching
# "מעמ" as a mere substring buried inside a longer word — e.g. "במעמ" ("subject
# to VAT", a description embedded in a taxable-subtotal line) must never read
# as the VAT label itself, only a standalone "מע"מ"/"מעמ" token should.
_VAT_LABEL_RE = re.compile(r'(?<![א-ת])(?:סכום\s*מע"?מ?|מע"?מ?|vat)', re.IGNORECASE)
_SUBTOTAL_RE = re.compile(r"(?:חייב|subtotal|taxable)", re.IGNORECASE)

_DATE_RE = re.compile(r"\b([0-3]?\d)[./\-]([01]?\d)[./\-](\d{4}|\d{2})\b")
_DATE_LABEL_RE = re.compile(r"תאריך|date", re.IGNORECASE)

# A fixed left-to-right phrase — safe to trust at "high" confidence, since
# the words appearing in exactly this order is itself strong evidence they
# were read correctly and belong together, not two unrelated words that
# happen to share a line.
_RECEIPT_NUMBER_LABEL_ORDERED_RE = re.compile(
    r'(?:מספר\s*קבלה|קבלה\s*מספר|קבלה\s*מס\'?|קבלה\s*#|חשבונית\s*מס\'?|מספר\s*חשבונית'
    r'|receipt\s*(?:no|number|#)|invoice\s*(?:no|number|#))',
    re.IGNORECASE,
)
# "אסמכתא" (a standalone Hebrew term for a transaction reference number) is
# unambiguous on its own — no ordering concern since it is a single word.
_RECEIPT_NUMBER_ASMACHTA_RE = re.compile(r"(?<![א-ת])אסמכתא(?![א-ת])")
# A "document type" word alone (חשבונית/קבלה) is deliberately never enough on
# its own — that word alone is often just a section heading (e.g. "חשבונית
# מס" as a title) with no specific identifier reliably nearby; matching it
# caused a real regression where an unrelated nearby number (a phone/
# business-registration number) got picked up as the receipt number,
# overriding a vision-model read that was correct. A "number qualifier" word
# (מספר/מס'/#) must co-occur on the same line too.
_RECEIPT_NUMBER_DOC_WORD_RE = re.compile(r"(?<![א-ת])(?:חשבונית|קבלה)(?![א-ת])")
_RECEIPT_NUMBER_QUALIFIER_RE = re.compile(r"(?<![א-ת])(?:מספר|מס'?)(?![א-ת])|#")


def _has_strong_receipt_number_label(text: str) -> bool:
    return bool(_RECEIPT_NUMBER_LABEL_ORDERED_RE.search(text) or _RECEIPT_NUMBER_ASMACHTA_RE.search(text))


def _has_weak_receipt_number_label(text: str) -> bool:
    """A spatially-reconstructed OCR line orders words by pixel (left-to-
    right) position, not Hebrew reading order (see ocr_selection.OcrLine) —
    a compound label like "חשבונית מס' קבלה" can therefore appear on the
    line with its words in the *opposite* order from how a person reads
    them, or with an unrelated number also sharing the line. Presence of a
    document-type word (חשבונית/קבלה) together with a number-qualifier word
    (מספר/מס'/#) ANYWHERE on the line, in any order, recovers a real signal a
    fixed left-to-right phrase would miss entirely — but it is a strictly
    weaker (never "high") signal than the ordered match above, since it
    cannot itself confirm the two words are actually part of one label
    rather than two coincidentally co-occurring words; the vision model
    stays in the loop to verify a value found only this way."""
    return bool(_RECEIPT_NUMBER_DOC_WORD_RE.search(text)) and bool(_RECEIPT_NUMBER_QUALIFIER_RE.search(text))

# Digits with internal hyphens/slashes kept (e.g. "12-165732", "3/379380") —
# an invoice/receipt number's punctuation is visibly part of the identifier
# and must not be silently stripped down to only the digits. The bare-digit
# fallback requires 3+ digits: a 1-2 digit number next to a receipt-number
# label is far more likely to be unrelated noise (e.g. a page/copy number).
_RECEIPT_NUMBER_PUNCTUATED_RE = re.compile(r"\b(\d+(?:[-/]\d+)+)\b")
_RECEIPT_NUMBER_BARE_RE = re.compile(r"\b(\d{3,})\b")


def _extract_receipt_number_token(text: str) -> str | None:
    """A busy header line can carry more than one digit-shaped token (a
    receipt number alongside an unrelated business-registration/VAT-ID
    number, for instance) — a hyphenated/slashed token is preferred whenever
    one is present anywhere on the line, since a receipt/invoice number's
    punctuation is a much sharper identifying signal than a bare digit run,
    which many unrelated numbers on a receipt also happen to have."""
    punctuated = _RECEIPT_NUMBER_PUNCTUATED_RE.search(text)
    if punctuated:
        return punctuated.group(1)
    bare = _RECEIPT_NUMBER_BARE_RE.search(text)
    return bare.group(1) if bare else None


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
    r"(תודה|להתראות|קבלה|לקוח|תאריך|מספר|עוסק|רחוב|טלפון|חשבונית|receipt|invoice|thank\s*you)",
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


def _looks_like_decimal_comma(token: str) -> bool:
    """A comma immediately between two digit groups of length 1-3 and 2 is
    almost certainly a decimal separator (e.g. "60,50"), not a thousands
    separator — receipts in this domain never have four-digit-plus totals."""
    return bool(re.search(r"\d{1,3},\d{2}(?!\d)", token))


def _parse_money_word(raw_token: str) -> Decimal | None:
    token = _normalize(raw_token)
    normalized = token.replace(",", ".") if _looks_like_decimal_comma(token) else token
    match = _MONEY_TOKEN_RE.match(normalized)
    if not match:
        return None
    try:
        return Decimal(match.group(1))
    except Exception:  # noqa: BLE001 - a malformed match is simply skipped
        return None


def _extract_money_amounts(text: str) -> list[Decimal]:
    normalized = _normalize(text)
    normalized = normalized.replace(",", ".") if _looks_like_decimal_comma(normalized) else normalized
    amounts = []
    for match in _MONEY_ANYWHERE_RE.finditer(normalized):
        try:
            amounts.append(Decimal(match.group(1)))
        except Exception:  # noqa: BLE001
            continue
    return amounts


def _is_rate_like(value: Decimal) -> bool:
    """A round percentage-shaped value (e.g. 17.00, 18.00) in the typical VAT
    rate range — used to tell a VAT *rate* apart from a VAT *amount* when both
    appear near each other, without hardcoding one specific rate."""
    return Decimal("5") <= value <= Decimal("25") and value == value.to_integral_value()


def _is_item_line(text: str) -> bool:
    """A line is treated as an itemized row — never a candidate for the final
    total or VAT — if it has the *shape* of one: a small quantity digit
    alongside at least two money-shaped amounts (line-total and unit-price).
    Matching by shape rather than an exact 3-token layout is deliberate: OCR
    frequently interleaves a garbled Hebrew item name between the numbers, or
    reorders tokens due to RTL confusion, so a strict positional pattern
    misses most real item lines."""
    stripped = text.strip()
    if _ITEM_LINE_RE.match(stripped):
        return True
    amounts = _extract_money_amounts(stripped)
    return len(amounts) >= 2 and bool(_SMALL_QTY_RE.search(stripped))


def _find_label_word_index(words: tuple[OcrWord, ...], label_re: re.Pattern) -> int | None:
    """Locates the label within a line's words — checking each word alone
    first, then adjacent 2-word windows, since OCR sometimes splits a Hebrew
    label like סה"כ across two word boxes."""
    for i, word in enumerate(words):
        if label_re.search(_normalize(word.text)):
            return i
    for i in range(len(words) - 1):
        joined = _normalize(words[i].text) + _normalize(words[i + 1].text)
        if label_re.search(joined):
            return i + 1
    return None


def _nearest_money_word(words: tuple[OcrWord, ...], anchor_index: int, exclude_rate_like: bool = False) -> Decimal | None:
    """Among all money-shaped words on this line, picks the one closest (by
    word position) to the label's own position — a receipt's amount almost
    always sits immediately next to its label, not several unrelated tokens
    away, so nearest-wins is a much sharper signal than "first" or "last"
    amount found anywhere in the line's flat text."""
    best_distance = None
    best_value = None
    for i, word in enumerate(words):
        value = _parse_money_word(word.text)
        if value is None:
            continue
        if exclude_rate_like and _is_rate_like(value):
            continue
        distance = abs(i - anchor_index)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_value = value
    return best_value


def _label_value_on_line_or_next(
    lines: tuple[OcrLine, ...],
    line_index: int,
    label_re: re.Pattern,
    *,
    exclude_rate_like: bool = False,
) -> tuple[Decimal, str] | None:
    """Finds `label_re` within this line and returns the nearest money-shaped
    value — first among this line's own words, then, only if this line has
    none, from the very next line provided it sits close enough vertically
    (label and value are sometimes printed on visually stacked lines rather
    than side by side, especially on a narrow or faded receipt)."""
    line = lines[line_index]
    label_index = _find_label_word_index(line.words, label_re)
    if label_index is None:
        return None

    value = _nearest_money_word(line.words, label_index, exclude_rate_like)
    if value is not None:
        return value, line.text

    if line_index + 1 < len(lines):
        next_line = lines[line_index + 1]
        gap = next_line.top - line.bottom
        if gap <= line.height * LINE_PROXIMITY_HEIGHT_MULTIPLE and not _is_item_line(next_line.text):
            amounts = [a for a in _extract_money_amounts(next_line.text) if not (exclude_rate_like and _is_rate_like(a))]
            if amounts:
                return amounts[0], next_line.text

    return None


def _find_total(lines: tuple[OcrLine, ...]) -> ParsedField | None:
    candidate_indexes = [
        i for i, line in enumerate(lines) if not _is_item_line(line.text) and not _TOTAL_ITEMS_COUNT_RE.search(line.text)
    ]

    for i in candidate_indexes:
        if _TOTAL_STRONG_LABEL_RE.search(lines[i].text):
            found = _label_value_on_line_or_next(lines, i, _TOTAL_STRONG_LABEL_RE)
            if found:
                return ParsedField(found[0], "high", found[1])

    excluded_by_change_or_cash: list[Decimal] = []
    for i in candidate_indexes:
        text = lines[i].text
        if _TOTAL_WEAK_LABEL_RE.search(text):
            if _CHANGE_OR_CASH_RE.search(text) or _AUTH_RE.search(text) or _DISCOUNT_RE.search(text):
                excluded_by_change_or_cash.extend(_extract_money_amounts(text))
                continue
            found = _label_value_on_line_or_next(lines, i, _TOTAL_WEAK_LABEL_RE)
            if found:
                return ParsedField(found[0], "medium", found[1])

    # A line labeled only "change"/"cash tendered"/"authorization"/"discount"
    # is excluded above by design — but OCR at typical receipt-photo
    # resolution is unreliable specifically on short summary-section labels,
    # so a label read as "change" is itself not fully trustworthy. Record
    # these purely to make them available to the last-resort tier below;
    # they are never used at medium/high confidence.
    for i in candidate_indexes:
        text = lines[i].text
        if (_CHANGE_OR_CASH_RE.search(text) or _AUTH_RE.search(text)) and not _TOTAL_WEAK_LABEL_RE.search(text):
            excluded_by_change_or_cash.extend(_extract_money_amounts(text))

    # Fallback: no usable label survived OCR at all (common on a noisy,
    # narrow, or faded photo). An amount printed more than once outside the
    # itemized lines is very likely the final total repeated in a payment
    # summary — never an individual item price, which only ever appears once.
    counts: dict[Decimal, int] = {}
    for i in candidate_indexes:
        for amount in _extract_money_amounts(lines[i].text):
            counts[amount] = counts.get(amount, 0) + 1
    repeated = [amount for amount, count in counts.items() if count >= 2]
    if repeated:
        return ParsedField(max(repeated), "low", "repeated amount across receipt")

    # Last resort: a change/cash/authorization-labeled amount is the only
    # signal at all. OCR's read of that specific label is treated as
    # unreliable rather than authoritative — surfaced at low confidence for
    # the user to confirm, rather than silently discarded and left blank.
    if excluded_by_change_or_cash:
        return ParsedField(max(excluded_by_change_or_cash), "low", "only found on an uncertain-label line")

    return None


_VAT_COMPETING_LABEL_RES = (_SUBTOTAL_RE, _TOTAL_STRONG_LABEL_RE, _TOTAL_WEAK_LABEL_RE, _CHANGE_OR_CASH_RE)


def _competing_label_indexes(words: tuple[OcrWord, ...], own_label_index: int) -> list[int]:
    """Finds every OTHER recognized label (subtotal, total, change, ...) on
    this line besides the VAT label itself — used to break a same-line
    nearest-word tie in favor of whichever number is unambiguously closer to
    the VAT label than to any competing label."""
    indexes = []
    for i, word in enumerate(words):
        if i == own_label_index:
            continue
        normalized = _normalize(word.text)
        if any(pattern.search(normalized) for pattern in _VAT_COMPETING_LABEL_RES):
            indexes.append(i)
    return indexes


def _find_vat(lines: tuple[OcrLine, ...], total: Decimal | None) -> ParsedField | None:
    for i, line in enumerate(lines):
        if not _VAT_LABEL_RE.search(line.text):
            continue

        label_index = _find_label_word_index(line.words, _VAT_LABEL_RE)
        if label_index is None:
            continue

        candidates = [
            (idx, value)
            for idx, value in ((j, _parse_money_word(w.text)) for j, w in enumerate(line.words))
            if value is not None
        ]
        if not candidates:
            # Label found but no money on this line at all (common when a
            # faded/narrow photo drops the amount from the same visual row) —
            # try the next line, same as the total's label/value logic.
            found = _label_value_on_line_or_next(lines, i, _VAT_LABEL_RE, exclude_rate_like=True)
            if found:
                return ParsedField(found[0], "medium", found[1])
            continue

        non_rate = [(idx, v) for idx, v in candidates if not _is_rate_like(v)]
        if len(non_rate) == 1:
            confidence: Confidence = "high"
            value = non_rate[0][1]
        elif len(non_rate) > 1:
            # Two or more non-rate numbers on the VAT line — most often a
            # taxable subtotal printed right next to the VAT amount (the
            # exact real failure mode this fixes). Prefer whichever value is
            # *unambiguously* closer to the VAT label than to any other
            # recognized label (subtotal/total/change) also on this line —
            # this correctly tells a subtotal-adjacent amount apart from the
            # VAT-adjacent one even when a plain nearest-word distance ties.
            competing = _competing_label_indexes(line.words, label_index)
            unambiguous = [
                (idx, v)
                for idx, v in non_rate
                if not competing or abs(idx - label_index) < min(abs(idx - c) for c in competing)
            ]
            pool = unambiguous or non_rate
            value = min(pool, key=lambda pair: abs(pair[0] - label_index))[1]
            confidence = "medium"
            if total is not None and value > total:
                # Never let a clearly-too-large pick through — fall back to
                # whichever non-rate candidate does not exceed the total,
                # since VAT can never exceed it.
                valid = [v for _, v in non_rate if v <= total]
                if not valid:
                    continue
                value = min(valid, key=lambda v: abs(v - value))
        else:
            # Only a rate-like number (e.g. "18.00") was found — almost
            # certainly just the VAT *rate*, not the amount. Reporting it as
            # if it were the amount would be a confident-looking wrong
            # number; better to try the next line or report nothing.
            found = _label_value_on_line_or_next(lines, i, _VAT_LABEL_RE, exclude_rate_like=True)
            if found:
                return ParsedField(found[0], "medium", found[1])
            continue

        return ParsedField(value, confidence, line.text)

    return None


def _valid_date_from_match(match: re.Match) -> date_type | None:
    day_str, month_str, year_str = match.groups()
    try:
        day, month, year = int(day_str), int(month_str), int(year_str)
    except ValueError:
        return None
    if year < 100:
        year += 2000 if year < 50 else 1900
    if year < 2000:
        return None
    try:
        candidate = date_type(year, month, day)
    except ValueError:
        return None
    if candidate > date_type.today():
        return None
    return candidate


def _find_date(lines: tuple[OcrLine, ...]) -> ParsedField | None:
    """Prefers a date immediately on a line carrying a "תאריך"/"date" label —
    anchored, so a receipt printing more than one date-shaped number (an
    expiry date, a loyalty/member number formatted like a date) doesn't fall
    back to whichever one the unanchored scan below happens to reach first.
    Only falls back to an unlabeled whole-text scan when no label is
    recognized at all (e.g. OCR dropped the label word itself)."""
    for line in lines:
        if not _DATE_LABEL_RE.search(_normalize(line.text)):
            continue
        for match in _DATE_RE.finditer(_normalize(line.text)):
            candidate = _valid_date_from_match(match)
            if candidate is not None:
                return ParsedField(candidate, "high", match.group(0))

    text = "\n".join(line.text for line in lines)
    for match in _DATE_RE.finditer(_normalize(text)):
        candidate = _valid_date_from_match(match)
        if candidate is not None:
            return ParsedField(candidate, "high", match.group(0))
    return None


def _label_spans_this_and_next_line(lines: tuple[OcrLine, ...], i: int) -> bool:
    """A multi-word label (e.g. "חשבונית מס'" / "קבלה") can itself be split
    across two OCR lines by Tesseract's own layout analysis on a real photo,
    not just the value being on the next line — checked as a fallback only
    when the label doesn't already match on this one line alone. Always a
    "weak" match (see _has_weak_receipt_number_label): splitting the search
    across two lines is itself less certain than a same-line match.

    Requires THIS line to itself carry at least one recognizable label
    fragment (a doc-type word or a number-qualifier word) before combining it
    with the next line's text — without this, an unrelated line (e.g. a
    merchant name) immediately before a line that already carries the *whole*
    label on its own would wrongly "discover" a cross-line match here, when
    the very next loop iteration would already find that same line's own
    complete, unambiguous match on its own."""
    if i + 1 >= len(lines):
        return False
    this_has_component = bool(
        _RECEIPT_NUMBER_DOC_WORD_RE.search(lines[i].text) or _RECEIPT_NUMBER_QUALIFIER_RE.search(lines[i].text)
    )
    if not this_has_component:
        return False
    next_line = lines[i + 1]
    gap = next_line.top - lines[i].bottom
    if gap > lines[i].height * LINE_PROXIMITY_HEIGHT_MULTIPLE:
        return False
    combined = f"{lines[i].text} {next_line.text}"
    return _has_strong_receipt_number_label(combined) or _has_weak_receipt_number_label(combined)


def _find_receipt_number(lines: tuple[OcrLine, ...]) -> ParsedField | None:
    for i, line in enumerate(lines):
        strong = _has_strong_receipt_number_label(line.text)
        weak = not strong and (_has_weak_receipt_number_label(line.text) or _label_spans_this_and_next_line(lines, i))
        if not strong and not weak:
            continue

        if strong:
            token = _extract_receipt_number_token(_normalize(line.text))
        else:
            # The order-agnostic "weak" label match cannot itself confirm the
            # label and the number are actually related, rather than two
            # words that merely happen to share a line with some other,
            # unrelated number (e.g. a business-registration ID also printed
            # near a "document type" heading) — real risk observed on an
            # actual receipt. Only a *punctuated* token (a receipt/invoice
            # number's hyphen/slash is a much sharper identifying signal — see
            # _extract_receipt_number_token) is trusted via this weaker path;
            # a bare digit run found only this way is not returned at all,
            # leaving the field to the vision model rather than risking a
            # confidently wrong value.
            match = _RECEIPT_NUMBER_PUNCTUATED_RE.search(_normalize(line.text))
            token = match.group(1) if match else None
        if token:
            return ParsedField(token, "high" if strong else "medium", line.text)

        if i + 1 < len(lines):
            next_line = lines[i + 1]
            gap = next_line.top - line.bottom
            if gap <= line.height * LINE_PROXIMITY_HEIGHT_MULTIPLE:
                if strong:
                    token = _extract_receipt_number_token(_normalize(next_line.text))
                else:
                    match = _RECEIPT_NUMBER_PUNCTUATED_RE.search(_normalize(next_line.text))
                    token = match.group(1) if match else None
                if token:
                    return ParsedField(token, "medium" if strong else "low", next_line.text)
    return None


def _find_currency(lines: tuple[OcrLine, ...]) -> ParsedField | None:
    """A literal currency symbol/code printed anywhere on the receipt (₪, $,
    €, ש"ח) is unambiguous — unlike an amount or a date, there is no
    competing candidate a currency mark could be confused with, so this is
    "high" confidence, not merely a fallback guess."""
    text = "\n".join(line.text for line in lines).lower()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return ParsedField(code, "high", symbol)
    return None


def _find_business_name(lines: tuple[OcrLine, ...]) -> ParsedField | None:
    """Best-effort only, and deliberately conservative: a merchant name is far
    less structurally reliable to detect than a labeled amount or date, so
    this only returns a candidate when a short, letter-heavy, unlabeled line
    appears near the top of the receipt (the prominent header region) —
    otherwise it returns nothing rather than guessing, matching "extract only
    if sufficiently clear"."""
    for line in lines[:5]:
        stripped = line.text.strip()
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


def parse_receipt_lines(ocr_lines: tuple[OcrLine, ...] | list[OcrLine]) -> ParsedReceiptCandidates:
    """Parses one OCR attempt's spatially-reconstructed lines into
    deterministic field candidates."""
    lines = tuple(ocr_lines)
    total = _find_total(lines)
    vat = _find_vat(lines, total.value if isinstance(total, ParsedField) else None)
    return ParsedReceiptCandidates(
        business_name=_find_business_name(lines),
        receipt_number=_find_receipt_number(lines),
        date=_find_date(lines),
        total=total,
        vat=vat,
        currency=_find_currency(lines),
    )


_FIELDS = ("business_name", "receipt_number", "date", "total", "vat", "currency")


def parse_receipt_candidates(ocr_candidates: list[tuple[OcrLine, ...]]) -> ParsedReceiptCandidates:
    """Parses several ranked OCR attempts (e.g. different Tesseract PSM modes
    on the same receipt) and merges them per field: a field found identically
    by two or more independent attempts is upgraded one confidence tier
    (cross-validated); otherwise the first valid candidate found (in the
    given, presumably best-first, order) is kept as-is.

    This matters in practice — a narrow, noisy, or faded receipt photo can
    have different Tesseract configurations disagree on a single misread
    digit (e.g. one config misreads a day as invalid, another reads it
    correctly); since every candidate is independently validated (a date must
    be a real, non-future calendar date), scanning several attempts recovers
    a value that the single top-scoring attempt alone would have missed,
    without ever fabricating a value no attempt actually produced.
    """
    per_field: dict[str, list[ParsedField]] = {field: [] for field in _FIELDS}

    for lines in ocr_candidates:
        parsed = parse_receipt_lines(lines)
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


# General Hebrew/English retail-category keywords — deliberately broad,
# common business-type words, never anything specific to one receipt/chain.
# Used only as a conservative fallback (see local_extractor.py) when the
# vision model itself was not confident enough to pick anything but "other".
_CATEGORY_KEYWORDS: tuple[tuple[ExpenseCategory, tuple[str, ...]], ...] = (
    (ExpenseCategory.GROCERIES, ("מרקט", "סופר", "מכולת", "קואופ", "market", "super", "grocery")),
    (ExpenseCategory.DINING, ("מסעדה", "קפה", "פיצה", "בורגר", "מאפי", "restaurant", "cafe", "coffee", "pizza")),
    (ExpenseCategory.TRANSPORT, ("דלק", "תחנת דלק", "מוניות", "taxi", "fuel", "gas station")),
    (ExpenseCategory.HEALTH, ("בית מרקחת", "פארם", "מרפאה", "pharmacy", "clinic")),
    (ExpenseCategory.SHOPPING, ("אופנה", "בגדים", "בוטיק", "fashion", "boutique", "clothing")),
    (ExpenseCategory.ENTERTAINMENT, ("קולנוע", "תיאטרון", "cinema", "theater")),
    (ExpenseCategory.TRAVEL, ("מלון", "hotel", "טיסות", "airlines")),
)


def infer_category_from_merchant_name(business_name: str | None) -> ExpenseCategory | None:
    """A conservative, generic keyword match — never a substitute for the
    vision model's own reading, only a fallback when it had nothing better
    than "other". Returns None (never a guess) when nothing matches."""
    if not business_name:
        return None
    normalized = _normalize(business_name).lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return category
    return None
