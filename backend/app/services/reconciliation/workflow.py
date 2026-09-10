"""Reconciliation workflow: applying a match result from a fresh receipt
upload, and approving/rejecting a suggested match. Every state transition
uses an atomic conditional UPDATE (`WHERE document_status == <expected>`)
instead of a select-then-update, so two concurrent requests can never both
claim the same expense — the loser's UPDATE simply affects 0 rows and is
treated as a safe no-op / fallback, never an error.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExpenseSource, ExtractionStatus
from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus
from app.schemas.receipt import ExtractedReceiptData
from app.services.reconciliation.matching import MatchDecision, decide, find_candidates

DEFAULT_INBOX_SECTION_LIMIT = 20
RECENTLY_COMPLETED_LIMIT = 10


@dataclass
class MatchOutcome:
    decision: MatchDecision
    expense: Expense | None = None
    reasons: list[str] = field(default_factory=list)


@dataclass
class ReconciliationInbox:
    missing_documents: list[Expense]
    suggested_matches: list[Expense]
    documents_without_transactions: list[Expense]
    needs_review: list[Expense]
    recently_completed: list[Expense]


def _fill_document_gaps(
    expense: Expense,
    *,
    vat_amount: Decimal | None,
    receipt_number: str | None,
    category: ExpenseCategory | None,
    extraction_confidence: float | None,
) -> None:
    """Fills document-derived fields only where the expense doesn't already
    have a value — never overwrites amount/currency/occurred_at/expense_date,
    which always come from the financial source, not the receipt."""
    if expense.vat_amount is None and vat_amount is not None:
        expense.vat_amount = vat_amount
    if not expense.receipt_number and receipt_number:
        expense.receipt_number = receipt_number
    if expense.category == ExpenseCategory.OTHER and category is not None and category != ExpenseCategory.OTHER:
        expense.category = category
    if extraction_confidence is not None:
        expense.extraction_confidence = extraction_confidence
    expense.extraction_status = ExtractionStatus.CONFIRMED


def apply_match_result(db: Session, upload: ReceiptUpload, extracted: ExtractedReceiptData) -> MatchOutcome:
    candidates = find_candidates(db, extracted)
    decision, best = decide(candidates)

    if decision == MatchDecision.NO_MATCH or best is None:
        return MatchOutcome(decision=MatchDecision.NO_MATCH)

    target_status = (
        DocumentStatus.ATTACHED if decision == MatchDecision.AUTO_MATCH else
        DocumentStatus.NEEDS_REVIEW if decision == MatchDecision.NEEDS_REVIEW else
        DocumentStatus.SUGGESTED
    )

    claim = db.execute(
        update(Expense)
        .where(Expense.id == best.expense_id, Expense.document_status == DocumentStatus.MISSING)
        .values(
            document_status=target_status,
            reconciliation_confidence=best.score,
            reconciliation_reasons=best.reasons,
            suggested_receipt_upload_id=upload.id,
        )
    )
    if claim.rowcount == 0:
        # Another concurrent upload already claimed this expense — fall back
        # to the safe default: this receipt is simply unmatched.
        return MatchOutcome(decision=MatchDecision.NO_MATCH)

    expense = db.get(Expense, best.expense_id)
    assert expense is not None  # guaranteed: rowcount == 1 means this row exists

    if decision == MatchDecision.AUTO_MATCH:
        expense.receipt_image_path = upload.stored_filename
        expense.storage_provider = upload.storage_provider
        _fill_document_gaps(
            expense,
            vat_amount=extracted.vat,
            receipt_number=extracted.receipt_number,
            category=extracted.category,
            extraction_confidence=extracted.confidence,
        )
        db.execute(
            update(ReceiptUpload)
            .where(ReceiptUpload.id == upload.id, ReceiptUpload.status == ReceiptUploadStatus.PENDING)
            .values(status=ReceiptUploadStatus.CONFIRMED, confirmed_at=datetime.utcnow(), expense_id=expense.id)
        )

    db.commit()
    db.refresh(expense)
    return MatchOutcome(decision=decision, expense=expense, reasons=best.reasons)


def approve_suggested_match(
    db: Session,
    expense_id: str,
    *,
    vat_amount: Decimal | None = None,
    receipt_number: str | None = None,
    category: ExpenseCategory | None = None,
) -> Expense | None:
    """Approves a suggested/needs-review match. Idempotent: calling this
    again after it already succeeded just returns the current (already
    attached) state rather than erroring."""
    claim = db.execute(
        update(Expense)
        .where(
            Expense.id == expense_id,
            Expense.document_status.in_([DocumentStatus.SUGGESTED, DocumentStatus.NEEDS_REVIEW]),
        )
        .values(document_status=DocumentStatus.ATTACHED)
    )
    expense = db.get(Expense, expense_id)
    if expense is None:
        return None
    if claim.rowcount == 0:
        db.commit()
        return expense

    if expense.suggested_receipt_upload_id:
        upload = db.get(ReceiptUpload, expense.suggested_receipt_upload_id)
        if upload is not None:
            expense.receipt_image_path = upload.stored_filename
            expense.storage_provider = upload.storage_provider
            db.execute(
                update(ReceiptUpload)
                .where(ReceiptUpload.id == upload.id, ReceiptUpload.status == ReceiptUploadStatus.PENDING)
                .values(status=ReceiptUploadStatus.CONFIRMED, confirmed_at=datetime.utcnow(), expense_id=expense.id)
            )
    _fill_document_gaps(
        expense,
        vat_amount=vat_amount,
        receipt_number=receipt_number,
        category=category,
        extraction_confidence=None,
    )
    expense.suggested_receipt_upload_id = None
    db.commit()
    db.refresh(expense)
    return expense


def reject_suggested_match(db: Session, expense_id: str) -> Expense | None:
    """Rejects a suggested/needs-review match, returning the expense to
    'missing'. Idempotent for the same reason as approve."""
    db.execute(
        update(Expense)
        .where(
            Expense.id == expense_id,
            Expense.document_status.in_([DocumentStatus.SUGGESTED, DocumentStatus.NEEDS_REVIEW]),
        )
        .values(
            document_status=DocumentStatus.MISSING,
            reconciliation_confidence=None,
            reconciliation_reasons=None,
            suggested_receipt_upload_id=None,
        )
    )
    expense = db.get(Expense, expense_id)
    db.commit()
    if expense is not None:
        db.refresh(expense)
    return expense


def build_inbox(db: Session, *, limit: int = DEFAULT_INBOX_SECTION_LIMIT) -> ReconciliationInbox:
    def _query(*conditions, order_desc_field, section_limit: int) -> list[Expense]:
        stmt = select(Expense).where(*conditions).order_by(order_desc_field.desc()).limit(section_limit)
        return list(db.scalars(stmt).all())

    missing_documents = _query(
        Expense.document_status == DocumentStatus.MISSING,
        order_desc_field=Expense.occurred_at,
        section_limit=limit,
    )
    suggested_matches = _query(
        Expense.document_status.in_([DocumentStatus.SUGGESTED, DocumentStatus.NEEDS_REVIEW]),
        order_desc_field=Expense.updated_at,
        section_limit=limit,
    )
    documents_without_transactions = _query(
        Expense.source == ExpenseSource.RECEIPT_UPLOAD,
        Expense.external_id.is_(None),
        order_desc_field=Expense.created_at,
        section_limit=limit,
    )
    needs_review = _query(
        Expense.document_status == DocumentStatus.NEEDS_REVIEW,
        order_desc_field=Expense.updated_at,
        section_limit=limit,
    )
    recently_completed = _query(
        Expense.document_status == DocumentStatus.ATTACHED,
        Expense.reconciliation_confidence.isnot(None),
        order_desc_field=Expense.updated_at,
        section_limit=RECENTLY_COMPLETED_LIMIT,
    )

    return ReconciliationInbox(
        missing_documents=missing_documents,
        suggested_matches=suggested_matches,
        documents_without_transactions=documents_without_transactions,
        needs_review=needs_review,
        recently_completed=recently_completed,
    )
