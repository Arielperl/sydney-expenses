import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

AMOUNT_PRECISION = 12
AMOUNT_SCALE = 2


class ExpenseCategory(str, enum.Enum):
    GROCERIES = "groceries"
    DINING = "dining"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    HEALTH = "health"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    TRAVEL = "travel"
    HOUSING = "housing"
    OTHER = "other"


class ExtractionStatus(str, enum.Enum):
    MANUAL = "manual"
    PENDING = "pending"
    EXTRACTED = "extracted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class ExpenseSource(str, enum.Enum):
    MANUAL = "manual"
    RECEIPT_UPLOAD = "receipt_upload"
    CSV = "csv"
    WEBHOOK = "webhook"


class DocumentStatus(str, enum.Enum):
    MISSING = "missing"
    SUGGESTED = "suggested"
    ATTACHED = "attached"
    NEEDS_REVIEW = "needs_review"
    NOT_REQUIRED = "not_required"


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint("source_provider", "external_id", name="uq_expenses_source_provider_external_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=False)
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="ILS")
    category: Mapped[ExpenseCategory] = mapped_column(
        Enum(ExpenseCategory, native_enum=False), nullable=False, default=ExpenseCategory.OTHER
    )
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receipt_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_provider: Mapped[str | None] = mapped_column(String(32), nullable=True, server_default="local")
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, native_enum=False), nullable=False, default=ExtractionStatus.MANUAL
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # --- Ingestion / reconciliation ---
    source: Mapped[ExpenseSource] = mapped_column(
        Enum(ExpenseSource, native_enum=False), nullable=False, default=ExpenseSource.MANUAL
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    document_status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False), nullable=False, default=DocumentStatus.NOT_REQUIRED
    )
    reconciliation_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reconciliation_reasons: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    suggested_receipt_upload_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("receipt_uploads.id", ondelete="SET NULL", use_alter=True, name="fk_expenses_suggested_receipt_upload_id"),
        nullable=True
    )
    import_batch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
