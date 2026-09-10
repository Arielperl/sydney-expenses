from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.expense import ExpenseCategory
from app.schemas.expense import ExpenseRead


class ReconciliationInboxResponse(BaseModel):
    missing_documents: list[ExpenseRead]
    suggested_matches: list[ExpenseRead]
    documents_without_transactions: list[ExpenseRead]
    needs_review: list[ExpenseRead]
    recently_completed: list[ExpenseRead]


class ApproveMatchRequest(BaseModel):
    """Optional document-derived fields the frontend already has from the
    original upload's extraction result — used only to fill gaps the
    transaction itself doesn't have. Never re-sends amount/currency/date."""

    vat_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    receipt_number: str | None = Field(default=None, max_length=100)
    category: ExpenseCategory | None = None


class MatchDecisionResponse(BaseModel):
    expense: ExpenseRead
