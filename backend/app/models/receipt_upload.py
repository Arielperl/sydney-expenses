import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.expense import AMOUNT_PRECISION, AMOUNT_SCALE, ExpenseCategory


class ReceiptUploadStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    EXPIRED = "expired"
    DISCARDED = "discarded"


class ReceiptUpload(Base):
    """Tracks the lifecycle of an uploaded receipt image from upload to confirmation.

    The public id is an opaque identifier handed to the client; it never exposes the
    underlying stored filename or filesystem path.
    """

    __tablename__ = "receipt_uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False, server_default="local")
    status: Mapped[ReceiptUploadStatus] = mapped_column(
        Enum(ReceiptUploadStatus, native_enum=False), nullable=False, default=ReceiptUploadStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expense_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True
    )

    # --- Persisted extraction snapshot ---
    # Bounded, structured fields only — never raw OCR text, image bytes, or a
    # full provider response. Populated once, right after extraction
    # succeeds, so approving a suggestion later never depends on the browser
    # resending financial fields it shouldn't own.
    extracted_business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extracted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    extracted_total: Mapped[Decimal | None] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=True)
    extracted_vat: Mapped[Decimal | None] = mapped_column(Numeric(AMOUNT_PRECISION, AMOUNT_SCALE), nullable=True)
    extracted_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    extracted_category: Mapped[ExpenseCategory | None] = mapped_column(
        Enum(ExpenseCategory, native_enum=False), nullable=True
    )
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
