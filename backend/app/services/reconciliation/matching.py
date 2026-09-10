"""Deterministic, offline transaction-to-receipt matching.

No AI model participates in a matching decision, and no financial data is
sent to any external service here — every signal is computed from fields
already on `Expense` and `ExtractedReceiptData`.
"""

import difflib
import enum
import re
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expense import DocumentStatus, Expense, ExpenseCategory
from app.models.receipt_upload import ReceiptUpload
from app.schemas.receipt import ExtractedReceiptData

HIGH_MATCH_THRESHOLD = 0.85
MEDIUM_MATCH_THRESHOLD = 0.55
MATCH_MARGIN = 0.15

_AMOUNT_EXACT_TOLERANCE = Decimal("0.01")
_AMOUNT_CLOSE_TOLERANCE = Decimal("1.00")
_MERCHANT_SIMILAR_THRESHOLD = 0.6
_CONFLICT_DATE_DAYS = 3


@dataclass
class MatchScore:
    expense_id: str
    score: float
    reasons: list[str] = field(default_factory=list)
    has_conflict: bool = False


class MatchDecision(str, enum.Enum):
    AUTO_MATCH = "auto_match"
    NEEDS_REVIEW = "needs_review"
    SUGGESTED = "suggested"
    NO_MATCH = "no_match"


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[^\w\s]", "", name.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def score_candidate(expense: Expense, extracted: ExtractedReceiptData) -> MatchScore:
    reasons: list[str] = []
    score = 0.0
    amount_conflict = False
    date_conflict_range = False

    currency_matches = extracted.currency is not None and expense.currency.upper() == extracted.currency.upper()
    if currency_matches:
        reasons.append("same_currency")
    else:
        reasons.append("currency_mismatch")

    if currency_matches and extracted.total is not None:
        diff = abs(expense.amount - extracted.total)
        if diff <= _AMOUNT_EXACT_TOLERANCE:
            score += 0.5
            reasons.append("same_amount")
        elif diff <= _AMOUNT_CLOSE_TOLERANCE:
            score += 0.25
            reasons.append("amount_close")
        else:
            reasons.append("amount_mismatch")
            amount_conflict = True
    elif extracted.total is not None:
        # Currency differs — the raw numbers aren't comparable, so no amount credit,
        # but a matching number is still worth flagging as a possible conflict signal.
        if abs(expense.amount - extracted.total) <= _AMOUNT_EXACT_TOLERANCE:
            amount_conflict = False
        else:
            amount_conflict = True

    if extracted.date is not None:
        days = abs((expense.expense_date - extracted.date).days)
        if days == 0:
            score += 0.25
            reasons.append("date_same_day")
        elif days <= _CONFLICT_DATE_DAYS:
            score += 0.15
            reasons.append("date_within_3_days")
            date_conflict_range = True
        else:
            reasons.append("date_far")
        if days == 0:
            date_conflict_range = True

    merchant_ratio = 0.0
    if expense.business_name and extracted.business_name:
        merchant_ratio = difflib.SequenceMatcher(
            None, _normalize_name(expense.business_name), _normalize_name(extracted.business_name)
        ).ratio()
        score += 0.2 * merchant_ratio
        reasons.append("merchant_similar" if merchant_ratio >= _MERCHANT_SIMILAR_THRESHOLD else "merchant_different")

    if expense.receipt_number and extracted.receipt_number:
        if expense.receipt_number.strip().casefold() == extracted.receipt_number.strip().casefold():
            score += 0.15
            reasons.append("receipt_number_match")

    has_conflict = (
        not currency_matches or amount_conflict
    ) and merchant_ratio >= _MERCHANT_SIMILAR_THRESHOLD and date_conflict_range

    return MatchScore(
        expense_id=expense.id,
        score=min(score, 1.0),
        reasons=reasons,
        has_conflict=has_conflict,
    )


def extracted_from_snapshot(upload: ReceiptUpload) -> ExtractedReceiptData:
    """Reconstructs the `ExtractedReceiptData` shape from a `ReceiptUpload`'s
    persisted extraction snapshot, so rematching and eligible-expense scoring
    can reuse `score_candidate`/`find_candidates` without ever touching the
    original image or a fresh extraction call."""
    return ExtractedReceiptData(
        business_name=upload.extracted_business_name,
        receipt_number=upload.extracted_receipt_number,
        date=upload.extracted_date,
        total=upload.extracted_total,
        vat=upload.extracted_vat,
        currency=upload.extracted_currency or "ILS",
        category=upload.extracted_category or ExpenseCategory.OTHER,
        confidence=upload.extraction_confidence or 0.0,
        warnings=upload.extraction_warnings or [],
    )


def find_candidates(db: Session, extracted: ExtractedReceiptData) -> list[MatchScore]:
    """Scores every document_status='missing' expense against the extracted
    receipt data and returns the results sorted best-first."""
    expenses = db.scalars(select(Expense).where(Expense.document_status == DocumentStatus.MISSING)).all()
    scored = [score_candidate(expense, extracted) for expense in expenses]
    scored.sort(key=lambda match: match.score, reverse=True)
    return scored


def decide(candidates: list[MatchScore]) -> tuple[MatchDecision, MatchScore | None]:
    if not candidates:
        return MatchDecision.NO_MATCH, None

    best = candidates[0]

    if best.has_conflict:
        return MatchDecision.NEEDS_REVIEW, best

    if best.score >= HIGH_MATCH_THRESHOLD:
        second = candidates[1] if len(candidates) > 1 else None
        if second is None or (best.score - second.score) >= MATCH_MARGIN:
            return MatchDecision.AUTO_MATCH, best
        return MatchDecision.SUGGESTED, best

    if best.score >= MEDIUM_MATCH_THRESHOLD:
        return MatchDecision.SUGGESTED, best

    return MatchDecision.NO_MATCH, None
