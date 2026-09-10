"""Reconciliation workflow: applying a match result from a fresh receipt
upload, and approving/rejecting a suggested match. Every state transition
uses an atomic conditional UPDATE (`WHERE document_status == <expected>`)
instead of a select-then-update, so two concurrent requests can never both
claim the same expense — the loser's UPDATE simply affects 0 rows and is
treated as a safe no-op / fallback, never an error.
"""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExpenseSource, ExtractionStatus
from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus
from app.schemas.receipt import ExtractedReceiptData
from app.services.reconciliation.exceptions import (
    ExpenseNotEligibleError,
    ExpenseNotFoundError,
    ReceiptNotAvailableError,
    ReceiptNotFoundError,
)
from app.services.reconciliation.matching import (
    MatchDecision,
    MatchScore,
    decide,
    extracted_from_snapshot,
    find_candidates,
    score_candidate,
)
from app.services.storage import StorageError, build_storage

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
    documents_without_transactions: list[ReceiptUpload]
    needs_review: list[Expense]
    recently_completed: list[Expense]


def _fill_document_gaps_from_upload(expense: Expense, upload: ReceiptUpload) -> None:
    """Fills document-derived fields from the upload's persisted extraction
    snapshot — never the request body — only where the expense doesn't
    already have a value. Never overwrites amount/currency/occurred_at/
    expense_date, which always come from the financial source, not the
    receipt."""
    if expense.vat_amount is None and upload.extracted_vat is not None:
        expense.vat_amount = upload.extracted_vat
    if not expense.receipt_number and upload.extracted_receipt_number:
        expense.receipt_number = upload.extracted_receipt_number
    if (
        expense.category == ExpenseCategory.OTHER
        and upload.extracted_category is not None
        and upload.extracted_category != ExpenseCategory.OTHER
    ):
        expense.category = upload.extracted_category
    if upload.extraction_confidence is not None:
        expense.extraction_confidence = upload.extraction_confidence
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
        _fill_document_gaps_from_upload(expense, upload)
        db.execute(
            update(ReceiptUpload)
            .where(ReceiptUpload.id == upload.id, ReceiptUpload.status == ReceiptUploadStatus.PENDING)
            .values(status=ReceiptUploadStatus.CONFIRMED, confirmed_at=datetime.utcnow(), expense_id=expense.id)
        )

    db.commit()
    db.refresh(expense)
    return MatchOutcome(decision=decision, expense=expense, reasons=best.reasons)


@dataclass
class TargetedMatchResult:
    attached: bool
    expense: Expense | None = None
    reasons: list[str] = field(default_factory=list)


def attach_to_expense(db: Session, upload_id: str, expense_id: str) -> Expense:
    """Unconditionally attaches a pending upload to a missing-document
    expense — used both to confirm past a shown conflict and for manual
    match selection. The backend re-validates both sides itself; it never
    trusts an id only because the client supplied it. Concurrency-safe via
    the same conditional-UPDATE pattern as every other transition here."""
    upload = db.get(ReceiptUpload, upload_id)
    if upload is None:
        raise ReceiptNotFoundError()
    if upload.status != ReceiptUploadStatus.PENDING:
        raise ReceiptNotAvailableError()

    expense = db.get(Expense, expense_id)
    if expense is None:
        raise ExpenseNotFoundError()

    claim = db.execute(
        update(Expense)
        .where(Expense.id == expense_id, Expense.document_status == DocumentStatus.MISSING)
        .values(document_status=DocumentStatus.ATTACHED, suggested_receipt_upload_id=None)
    )
    if claim.rowcount == 0:
        raise ExpenseNotEligibleError()

    receipt_claim = db.execute(
        update(ReceiptUpload)
        .where(ReceiptUpload.id == upload_id, ReceiptUpload.status == ReceiptUploadStatus.PENDING)
        .values(status=ReceiptUploadStatus.CONFIRMED, confirmed_at=datetime.utcnow(), expense_id=expense_id)
    )
    if receipt_claim.rowcount == 0:
        # Someone else claimed this exact receipt in the moment between our
        # read and our write — undo the expense-side claim we just made so
        # it doesn't get stranded in a half-attached state.
        db.rollback()
        raise ReceiptNotAvailableError()

    db.refresh(expense)
    expense.receipt_image_path = upload.stored_filename
    expense.storage_provider = upload.storage_provider
    _fill_document_gaps_from_upload(expense, upload)
    db.commit()
    db.refresh(expense)
    return expense


def targeted_match(
    db: Session, upload: ReceiptUpload, expense: Expense, extracted: ExtractedReceiptData
) -> TargetedMatchResult:
    """Compares one freshly-extracted receipt with exactly one expense the
    user already chose (via ?expenseId=). No conflict -> attaches
    immediately. A conflict -> attaches nothing and reports why, requiring
    an explicit confirm (attach_to_expense) from the user."""
    match = score_candidate(expense, extracted)
    if match.has_conflict:
        return TargetedMatchResult(attached=False, expense=expense, reasons=match.reasons)

    attached_expense = attach_to_expense(db, upload.id, expense.id)
    return TargetedMatchResult(attached=True, expense=attached_expense, reasons=match.reasons)


def approve_suggested_match(db: Session, expense_id: str) -> Expense | None:
    """Approves a suggested/needs-review match using the receipt's
    *persisted* extraction snapshot — the client only identifies which
    match to approve, it is never the source of truth for VAT/receipt
    number/category. Idempotent: calling this again after it already
    succeeded just returns the current (already attached) state. Raises
    ReceiptNotAvailableError (never silently attaches nothing) if the
    linked upload was discarded/expired out from under the suggestion."""
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

    upload = (
        db.get(ReceiptUpload, expense.suggested_receipt_upload_id) if expense.suggested_receipt_upload_id else None
    )
    if upload is None or upload.status != ReceiptUploadStatus.PENDING:
        db.rollback()
        raise ReceiptNotAvailableError()

    receipt_claim = db.execute(
        update(ReceiptUpload)
        .where(ReceiptUpload.id == upload.id, ReceiptUpload.status == ReceiptUploadStatus.PENDING)
        .values(status=ReceiptUploadStatus.CONFIRMED, confirmed_at=datetime.utcnow(), expense_id=expense.id)
    )
    if receipt_claim.rowcount == 0:
        db.rollback()
        raise ReceiptNotAvailableError()

    db.refresh(expense)
    expense.receipt_image_path = upload.stored_filename
    expense.storage_provider = upload.storage_provider
    _fill_document_gaps_from_upload(expense, upload)
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
    suggested_upload_ids = select(Expense.suggested_receipt_upload_id).where(
        Expense.suggested_receipt_upload_id.isnot(None)
    )
    documents_without_transactions = list(
        db.scalars(
            select(ReceiptUpload)
            .where(
                ReceiptUpload.status == ReceiptUploadStatus.PENDING,
                ReceiptUpload.id.not_in(suggested_upload_ids),
            )
            .order_by(ReceiptUpload.created_at.desc())
            .limit(limit)
        ).all()
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


def rematch_document(db: Session, upload_id: str) -> MatchOutcome:
    """Re-runs matching for an unassigned document against the current pool
    of `missing` expenses, using its persisted extraction snapshot rather
    than re-extracting. A no-op (NO_MATCH, no side effects) when nothing
    qualifies — the document simply stays unassigned."""
    upload = db.get(ReceiptUpload, upload_id)
    if upload is None:
        raise ReceiptNotFoundError()
    if upload.status != ReceiptUploadStatus.PENDING:
        raise ReceiptNotAvailableError()

    extracted = extracted_from_snapshot(upload)
    return apply_match_result(db, upload, extracted)


def list_eligible_expenses(db: Session, upload_id: str) -> list[MatchScore]:
    """Scores every `missing`-document expense against this document's
    persisted snapshot, best-first, so a manual match picker can show a
    conflict warning before the user commits to an attach."""
    upload = db.get(ReceiptUpload, upload_id)
    if upload is None:
        raise ReceiptNotFoundError()

    extracted = extracted_from_snapshot(upload)
    return find_candidates(db, extracted)


def discard_document(db: Session, upload_id: str, settings: Settings | None = None) -> None:
    """Discards a pending, unassigned document: conditionally marks it
    discarded (never a select-then-update), clears any dangling suggestion
    pointer left on an expense, and best-effort deletes the stored file —
    mirroring the non-blocking storage-cleanup pattern used for expired
    uploads. Idempotent: discarding an already-discarded upload is a no-op,
    not an error."""
    upload = db.get(ReceiptUpload, upload_id)
    if upload is None:
        raise ReceiptNotFoundError()
    if upload.status == ReceiptUploadStatus.DISCARDED:
        return
    if upload.status != ReceiptUploadStatus.PENDING:
        raise ReceiptNotAvailableError()

    db.execute(
        update(Expense)
        .where(Expense.suggested_receipt_upload_id == upload_id)
        .values(
            document_status=DocumentStatus.MISSING,
            reconciliation_confidence=None,
            reconciliation_reasons=None,
            suggested_receipt_upload_id=None,
        )
    )
    claim = db.execute(
        update(ReceiptUpload)
        .where(ReceiptUpload.id == upload_id, ReceiptUpload.status == ReceiptUploadStatus.PENDING)
        .values(status=ReceiptUploadStatus.DISCARDED)
    )
    if claim.rowcount == 0:
        db.rollback()
        return
    db.commit()

    settings = settings or get_settings()
    try:
        storage = build_storage(upload.storage_provider or "local", settings)
        storage.delete(upload.stored_filename)
    except StorageError:
        pass
