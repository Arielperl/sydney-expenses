import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.business import BusinessOwned


class ProviderDocumentStatus(str, enum.Enum):
    """A provider document event's own lifecycle — separate from
    `Sale.document_status`, since this row can exist before any matching
    `Sale` does at all (Grow's invoice webhook may arrive before the
    payment webhook — see app/api/routes/webhooks.py)."""

    PENDING_MATCH = "pending_match"
    MATCHED = "matched"


class ProviderDocumentEvent(BusinessOwned, Base):
    """Durable record of one provider-supplied document (Grow's "Invoice
    creation" webhook today) that could not — or could not yet — be linked
    to a `Sale`. Written immediately on receipt, before any matching
    attempt, so an invoice event that arrives before its payment event is
    never lost: `try_match_pending_grow_document` (see
    app/api/routes/webhooks.py) consumes this row the moment the matching
    Sale is created.

    Deliberately minimal — no raw payload, no customer PII. `connection_id`
    plus `external_transaction_id` is the correlation key (matches
    `Sale.external_id`), scoped by business through `BusinessOwned` and by
    connection/provider through the unique constraint below, so a document
    can never be matched across businesses or across a different connection
    of the same provider."""

    __tablename__ = "provider_document_events"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "external_transaction_id", name="uq_provider_document_events_connection_txn"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)

    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Validated HTTPS URL only — see grow_provider.py's parse_grow_invoice_event.
    # Never fetched server-side (SSRF risk); only ever rendered as an
    # external link, never as an <img src>.
    document_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[ProviderDocumentStatus] = mapped_column(
        Enum(ProviderDocumentStatus, native_enum=False), nullable=False, default=ProviderDocumentStatus.PENDING_MATCH
    )
    matched_sale_id: Mapped[str | None] = mapped_column(ForeignKey("sales.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
