"""A persisted, append-only timeline of what actually happened to a sale —
the factual basis for Sale Details' history. Events are written exactly
once, transactionally with the state change they describe (see
app/services/sale_service.py) — never backfilled or invented for a sale
that predates this model. A sale created before `SaleEvent` existed simply
has fewer events than one created after; its timeline is honest about that
gap rather than inventing history to fill it (see the migration that
introduced this table).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SaleEventType(str, enum.Enum):
    SALE_RECEIVED = "sale_received"  # ingested automatically: webhook or demo simulator
    SALE_CREATED_MANUALLY = "sale_created_manually"
    SALE_IMPORTED_FROM_CSV = "sale_imported_from_csv"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_FAILED = "payment_failed"
    DOCUMENT_ISSUANCE_ATTEMPTED = "document_issuance_attempted"
    DOCUMENT_ISSUED = "document_issued"
    DOCUMENT_ISSUANCE_FAILED = "document_issuance_failed"
    REFUND_PARTIAL = "refund_partial"
    REFUND_FULL = "refund_full"
    SALE_DETAILS_EDITED = "sale_details_edited"


class SaleEventSource(str, enum.Enum):
    MANUAL = "manual"
    WEBHOOK = "webhook"
    CSV = "csv"
    DEMO = "demo"
    SYSTEM = "system"


class SaleEvent(Base):
    __tablename__ = "sale_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sale_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[SaleEventType] = mapped_column(Enum(SaleEventType, native_enum=False), nullable=False)
    source: Mapped[SaleEventSource] = mapped_column(Enum(SaleEventSource, native_enum=False), nullable=False)
    # Plain UTC audit timestamp — "when this event was recorded", not a
    # business-calendar field (see app.domain.business_time). Always "now"
    # at the moment the triggering state change is committed.
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    # Small, safe, structured facts about the event (e.g. {"amount": "50.00",
    # "currency": "ILS"} for a refund) — never a secret, a full webhook body,
    # or free-form customer-supplied text. Column name kept as `event_metadata`
    # to avoid colliding with SQLAlchemy's own reserved `Base.metadata`.
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
