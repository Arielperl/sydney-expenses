import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

AMOUNT_PRECISION = 12
AMOUNT_SCALE = 2


class SaleSource(str, enum.Enum):
    MANUAL = "manual"
    CSV = "csv"
    WEBHOOK = "webhook"


class SaleStatus(str, enum.Enum):
    SUCCEEDED = "succeeded"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class DocumentStatus(str, enum.Enum):
    """Tracks the receipt/tax document issued *to the customer* for this
    sale — an outgoing document, never one received from a supplier."""

    PENDING = "pending"
    ISSUED = "issued"
    FAILED = "failed"
    NOT_REQUIRED = "not_required"


class Sale(Base):
    """A single customer sale/revenue transaction — the central domain
    record of the app. Money fields: `gross_amount` is what the customer
    paid, `vat_amount` is the portion of that collected on behalf of the
    tax authority (not real business revenue), `processing_fee` is what the
    payment provider kept, and `net_amount` = gross - vat - fee is the
    actual revenue the business nets from the sale."""

    __tablename__ = "sales"
    __table_args__ = (UniqueConstraint("source_provider", "external_id", name="uq_sales_source_provider_external_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[SaleSource] = mapped_column(Enum(SaleSource, native_enum=False), nullable=False, default=SaleSource.MANUAL)
    status: Mapped[SaleStatus] = mapped_column(
        Enum(SaleStatus, native_enum=False), nullable=False, default=SaleStatus.SUCCEEDED
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    gross_amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=False)
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=True)
    processing_fee: Mapped[Decimal | None] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=True)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=False)
    refunded_amount: Mapped[Decimal | None] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="ILS")
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    document_status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False), nullable=False, default=DocumentStatus.PENDING
    )
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_batch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def revenue_contribution(self) -> Decimal:
        """The amount of `net_amount` that actually counts toward revenue
        totals: zero for a pending/failed sale, the full net amount for a
        succeeded one, and net minus whatever was refunded otherwise."""
        if self.status in (SaleStatus.PENDING, SaleStatus.FAILED):
            return Decimal("0")
        if self.status == SaleStatus.REFUNDED:
            return Decimal("0")
        refunded = self.refunded_amount or Decimal("0")
        return max(self.net_amount - refunded, Decimal("0"))
