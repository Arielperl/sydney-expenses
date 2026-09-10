from datetime import date as date_type, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.expense import ExpenseRead
from app.models.expense import ExpenseCategory


class UnassignedDocumentRead(BaseModel):
    """A real, persisted `ReceiptUpload` with no expense pointing at it —
    never a derived `Expense` row. Exposes only the bounded extraction
    snapshot and a fresh preview URL, never a filesystem path or raw OCR
    output."""

    id: str
    received_at: datetime
    preview_url: str | None
    extracted_business_name: str | None
    extracted_total: Decimal | None
    extracted_vat: Decimal | None
    extracted_currency: str | None
    extracted_date: date_type | None
    extracted_receipt_number: str | None
    extracted_category: ExpenseCategory | None
    extraction_confidence: float | None
    extraction_warnings: list[str]


class SuggestedMatchRead(BaseModel):
    """A suggested/needs-review match shown with both sides — the
    transaction (`expense`) and the candidate receipt (`document`, using the
    same shape as an unassigned document) — so the reviewer never has to
    approve blind."""

    expense: ExpenseRead
    document: UnassignedDocumentRead | None


class ReconciliationInboxResponse(BaseModel):
    missing_documents: list[ExpenseRead]
    suggested_matches: list[SuggestedMatchRead]
    documents_without_transactions: list[UnassignedDocumentRead]
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


class EligibleExpenseRead(BaseModel):
    """One `missing`-document expense as a candidate for manual matching,
    with the same score/conflict preview the automated matcher would use —
    so a manual pick can still warn about a mismatch before attaching."""

    expense: ExpenseRead
    score: float
    reasons: list[str]
    has_conflict: bool


class RematchResponse(BaseModel):
    """Result of re-running matching for one unassigned document. `expense`
    is null when nothing currently qualifies — a safe no-op, not an error."""

    decision: str
    expense: ExpenseRead | None
    reasons: list[str]
