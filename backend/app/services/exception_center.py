"""Build the business owner's action queue.

Document attachment is a sales-management capability, not an operational
exception. A missing, delayed, or failed provider document must therefore
never add a task or increase the badge in "Needs attention". The queue is
reserved for sale data that genuinely requires an owner decision.

The legacy document fields remain in the response as empty values so older
clients can upgrade without breaking; they are intentionally no longer part
of the queue's behaviour.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sale import Sale

DEFAULT_SECTION_LIMIT = 20


@dataclass
class ExceptionCenter:
    attention_count: int
    pending_documents_count: int
    document_failures_count: int
    refunds_needing_attention_count: int
    incomplete_details_count: int
    pending_documents: list[Sale]
    document_failures: list[Sale]
    refunds_needing_attention: list[Sale]
    incomplete_details: list[Sale]


def build_exception_center(db: Session, *, limit: int = DEFAULT_SECTION_LIMIT) -> ExceptionCenter:
    def _query(*conditions) -> list[Sale]:
        stmt = select(Sale).where(*conditions).order_by(Sale.occurred_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    pending_documents: list[Sale] = []
    document_failures: list[Sale] = []
    # A recorded refund is already reflected in revenue. Without a separate
    # unresolved refund workflow, its status alone must not create a task.
    refunds_needing_attention: list[Sale] = []
    # A missing contact address is normal for many provider transactions. The
    # only incomplete field that currently requires a decision by the owner
    # is a legacy tax treatment that could not be inferred safely.
    tax_review_needed = Sale.tax_treatment_needs_review.is_(True)
    incomplete_details = _query(tax_review_needed)

    def _count(*conditions) -> int:
        return db.scalar(select(func.count(Sale.id)).where(*conditions)) or 0

    pending_documents_count = 0
    document_failures_count = 0
    refunds_needing_attention_count = 0  # Retained in the response for existing clients.
    incomplete_details_count = _count(tax_review_needed)
    attention_count = incomplete_details_count

    return ExceptionCenter(
        attention_count=attention_count,
        pending_documents_count=pending_documents_count,
        document_failures_count=document_failures_count,
        refunds_needing_attention_count=refunds_needing_attention_count,
        incomplete_details_count=incomplete_details_count,
        pending_documents=pending_documents,
        document_failures=document_failures,
        refunds_needing_attention=refunds_needing_attention,
        incomplete_details=incomplete_details,
    )
