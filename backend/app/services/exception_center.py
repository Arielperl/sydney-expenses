"""The exception center: the primary place a business owner's attention
should go, replacing the old expense-to-receipt reconciliation inbox. Sales
never need "matching" anymore — a sale's document is either generated
automatically (our own DocumentProvider, or a real payment/invoicing
provider like Grow/Cardcom) or imported explicitly — so these are the only
things that still need a human to look at them.

A sale waiting on an automatic provider document (`document_status=
waiting_automatic`) is deliberately NOT surfaced the moment it's created —
that's the normal, expected state for every fresh Grow/Cardcom sale until
the provider's own document arrives, and treating it as an exception would
turn ordinary automatic operation into daily manual work. It only becomes
an exception once it's sat unmatched for longer than
`settings.document_match_grace_period_hours` — a deterministic, query-time
cutoff (never an in-memory timer or background job, since the backend runs
on Vercel serverless)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.sale import DocumentStatus, Sale, SaleStatus

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

    grace_cutoff = datetime.utcnow() - timedelta(hours=get_settings().document_match_grace_period_hours)
    # A genuine document problem: our own generic issuance failed, OR a
    # provider-document sale has sat waiting past the grace period — but
    # never a fresh waiting_automatic sale still within it (see module
    # docstring).
    document_needs_attention = or_(
        Sale.document_status == DocumentStatus.FAILED,
        and_(Sale.document_status == DocumentStatus.WAITING_AUTOMATIC, Sale.occurred_at < grace_cutoff),
    )

    pending_documents = _query(
        Sale.status == SaleStatus.SUCCEEDED,
        Sale.document_status == DocumentStatus.PENDING,
    )
    document_failures = _query(document_needs_attention)
    refunds_needing_attention = _query(
        Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED])
    )
    incomplete_details = _query(Sale.customer_contact.is_(None))

    def _count(*conditions) -> int:
        return db.scalar(select(func.count(Sale.id)).where(*conditions)) or 0

    pending_documents_count = _count(
        Sale.status == SaleStatus.SUCCEEDED,
        Sale.document_status == DocumentStatus.PENDING,
    )
    document_failures_count = _count(document_needs_attention)
    refunds_needing_attention_count = _count(
        Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED])
    )
    incomplete_details_count = _count(Sale.customer_contact.is_(None))
    attention_count = db.scalar(
        select(func.count(Sale.id)).where(
            or_(
                and_(
                    Sale.status == SaleStatus.SUCCEEDED,
                    Sale.document_status == DocumentStatus.PENDING,
                ),
                document_needs_attention,
                Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]),
                Sale.customer_contact.is_(None),
            )
        )
    ) or 0

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
