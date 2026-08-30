import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReceiptUploadStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    EXPIRED = "expired"


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
