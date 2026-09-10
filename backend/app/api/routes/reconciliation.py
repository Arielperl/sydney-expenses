from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import resolve_receipt_image_url
from app.database import get_db
from app.models.expense import Expense
from app.models.receipt_upload import ReceiptUpload
from app.schemas.expense import expense_to_read
from app.schemas.reconciliation import (
    AttachRequest,
    EligibleExpenseRead,
    MatchDecisionResponse,
    ReconciliationInboxResponse,
    RematchResponse,
    UnassignedDocumentRead,
)
from app.services.reconciliation.exceptions import (
    ExpenseNotEligibleError,
    ExpenseNotFoundError,
    ReceiptNotAvailableError,
    ReceiptNotFoundError,
)
from app.services.reconciliation.workflow import (
    approve_suggested_match,
    attach_to_expense,
    build_inbox,
    discard_document,
    list_eligible_expenses,
    reject_suggested_match,
    rematch_document,
)

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


def _to_unassigned_document_read(upload: ReceiptUpload) -> UnassignedDocumentRead:
    return UnassignedDocumentRead(
        id=upload.id,
        received_at=upload.created_at,
        preview_url=resolve_receipt_image_url(upload.storage_provider, upload.stored_filename),
        extracted_business_name=upload.extracted_business_name,
        extracted_total=upload.extracted_total,
        extracted_currency=upload.extracted_currency,
        extracted_date=upload.extracted_date,
        extraction_confidence=upload.extraction_confidence,
        extraction_warnings=upload.extraction_warnings or [],
    )


@router.post("/attach", response_model=MatchDecisionResponse)
def attach_match(
    payload: AttachRequest,
    db: Session = Depends(get_db),
) -> MatchDecisionResponse:
    try:
        expense = attach_to_expense(db, payload.upload_id, payload.expense_id)
    except (ExpenseNotFoundError, ReceiptNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Expense or document not found") from exc
    except ExpenseNotEligibleError as exc:
        raise HTTPException(status_code=409, detail="This expense already has a document, or none is expected") from exc
    except ReceiptNotAvailableError as exc:
        raise HTTPException(status_code=409, detail="This document is no longer available") from exc

    image_url = resolve_receipt_image_url(expense.storage_provider, expense.receipt_image_path)
    return MatchDecisionResponse(expense=expense_to_read(expense, image_url))


@router.get("/inbox", response_model=ReconciliationInboxResponse)
def get_inbox(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ReconciliationInboxResponse:
    inbox = build_inbox(db, limit=limit)

    def _to_read(expense):
        return expense_to_read(expense, resolve_receipt_image_url(expense.storage_provider, expense.receipt_image_path))

    return ReconciliationInboxResponse(
        missing_documents=[_to_read(e) for e in inbox.missing_documents],
        suggested_matches=[_to_read(e) for e in inbox.suggested_matches],
        documents_without_transactions=[_to_unassigned_document_read(u) for u in inbox.documents_without_transactions],
        needs_review=[_to_read(e) for e in inbox.needs_review],
        recently_completed=[_to_read(e) for e in inbox.recently_completed],
    )


@router.post("/matches/{expense_id}/approve", response_model=MatchDecisionResponse)
def approve_match(
    expense_id: str,
    db: Session = Depends(get_db),
) -> MatchDecisionResponse:
    try:
        expense = approve_suggested_match(db, expense_id)
    except ReceiptNotAvailableError as exc:
        raise HTTPException(
            status_code=409, detail="The suggested document is no longer available (discarded or expired)"
        ) from exc
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    image_url = resolve_receipt_image_url(expense.storage_provider, expense.receipt_image_path)
    return MatchDecisionResponse(expense=expense_to_read(expense, image_url))


@router.post("/matches/{expense_id}/reject", response_model=MatchDecisionResponse)
def reject_match(
    expense_id: str,
    db: Session = Depends(get_db),
) -> MatchDecisionResponse:
    expense = reject_suggested_match(db, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    image_url = resolve_receipt_image_url(expense.storage_provider, expense.receipt_image_path)
    return MatchDecisionResponse(expense=expense_to_read(expense, image_url))


@router.post("/documents/{upload_id}/rematch", response_model=RematchResponse)
def rematch(
    upload_id: str,
    db: Session = Depends(get_db),
) -> RematchResponse:
    try:
        outcome = rematch_document(db, upload_id)
    except ReceiptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except ReceiptNotAvailableError as exc:
        raise HTTPException(status_code=409, detail="This document is no longer available") from exc

    expense_read = None
    if outcome.expense is not None:
        image_url = resolve_receipt_image_url(outcome.expense.storage_provider, outcome.expense.receipt_image_path)
        expense_read = expense_to_read(outcome.expense, image_url)
    return RematchResponse(decision=outcome.decision.value, expense=expense_read, reasons=outcome.reasons)


@router.get("/documents/{upload_id}/eligible-expenses", response_model=list[EligibleExpenseRead])
def eligible_expenses(
    upload_id: str,
    db: Session = Depends(get_db),
) -> list[EligibleExpenseRead]:
    try:
        candidates = list_eligible_expenses(db, upload_id)
    except ReceiptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    results = []
    for candidate in candidates:
        expense = db.get(Expense, candidate.expense_id)
        if expense is None:
            continue
        image_url = resolve_receipt_image_url(expense.storage_provider, expense.receipt_image_path)
        results.append(
            EligibleExpenseRead(
                expense=expense_to_read(expense, image_url),
                score=candidate.score,
                reasons=candidate.reasons,
                has_conflict=candidate.has_conflict,
            )
        )
    return results


@router.post("/documents/{upload_id}/discard", status_code=204)
def discard(
    upload_id: str,
    db: Session = Depends(get_db),
) -> None:
    try:
        discard_document(db, upload_id)
    except ReceiptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except ReceiptNotAvailableError as exc:
        raise HTTPException(status_code=409, detail="This document is no longer available") from exc
