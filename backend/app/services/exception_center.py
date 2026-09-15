"""The exception center: the primary place a business owner's attention
should go, replacing the old expense-to-receipt reconciliation inbox. Sales
never need "matching" anymore — a sale's document is either generated
automatically at creation time or imported explicitly — so these are the
only things that still need a human to look at them."""

from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.sale import DocumentStatus, Sale, SaleStatus

DEFAULT_SECTION_LIMIT = 20


@dataclass
class ExceptionCenter:
    attention_count: int
    pending_documents: list[Sale]
    document_failures: list[Sale]
    refunds_needing_attention: list[Sale]
    incomplete_details: list[Sale]


def build_exception_center(db: Session, *, limit: int = DEFAULT_SECTION_LIMIT) -> ExceptionCenter:
    def _query(*conditions) -> list[Sale]:
        stmt = select(Sale).where(*conditions).order_by(Sale.occurred_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    pending_documents = _query(
        Sale.status == SaleStatus.SUCCEEDED,
        Sale.document_status == DocumentStatus.PENDING,
    )
    document_failures = _query(Sale.document_status == DocumentStatus.FAILED)
    refunds_needing_attention = _query(
        Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED])
    )
    incomplete_details = _query(Sale.customer_contact.is_(None))
    attention_count = db.scalar(
        select(func.count(Sale.id)).where(
            or_(
                and_(
                    Sale.status == SaleStatus.SUCCEEDED,
                    Sale.document_status == DocumentStatus.PENDING,
                ),
                Sale.document_status == DocumentStatus.FAILED,
                Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]),
                Sale.customer_contact.is_(None),
            )
        )
    ) or 0

    return ExceptionCenter(
        attention_count=attention_count,
        pending_documents=pending_documents,
        document_failures=document_failures,
        refunds_needing_attention=refunds_needing_attention,
        incomplete_details=incomplete_details,
    )
