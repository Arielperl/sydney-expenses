from pydantic import BaseModel

from app.schemas.expense import ExpenseRead


class ReconciliationInboxResponse(BaseModel):
    missing_documents: list[ExpenseRead]
    suggested_matches: list[ExpenseRead]
    documents_without_transactions: list[ExpenseRead]
    needs_review: list[ExpenseRead]
    recently_completed: list[ExpenseRead]


class AttachRequest(BaseModel):
    """Executes an attach the user already decided on — confirming past a
    shown conflict, or a manually chosen transaction. The backend
    re-validates both sides regardless of what an earlier response said."""

    upload_id: str
    expense_id: str


class MatchDecisionResponse(BaseModel):
    expense: ExpenseRead
