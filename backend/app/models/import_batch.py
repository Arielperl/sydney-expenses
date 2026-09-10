import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportBatch(Base):
    """Tracks one CSV import attempt: which file, how many rows validated vs.
    errored, and (once confirmed) how many expenses were created vs. skipped
    as duplicates. `file_hash` lets the import flow recognize a re-uploaded
    file without treating same-amount/same-day rows as automatically
    duplicate — the real duplicate guard is the per-row external_id unique
    constraint on Expense.
    """

    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus, native_enum=False), nullable=False, default=ImportStatus.PENDING
    )
    valid_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
