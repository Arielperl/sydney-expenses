from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import resolve_receipt_image_url
from app.database import get_db
from app.schemas.expense import expense_to_read
from app.schemas.reconciliation import AttachRequest, MatchDecisionResponse, ReconciliationInboxResponse
from app.services.reconciliation.exceptions import (
    ExpenseNotEligibleError,
    ExpenseNotFoundError,
    ReceiptNotAvailableError,
    ReceiptNotFoundError,
)
from app.services.reconciliation.workflow import approve_suggested_match, attach_to_expense, build_inbox, reject_suggested_match

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


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
        documents_without_transactions=[_to_read(e) for e in inbox.documents_without_transactions],
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
