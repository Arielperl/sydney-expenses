import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseCategory, ExtractionStatus
from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus
from app.repositories.receipt_upload_repository import ReceiptUploadRepository
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)


class ReceiptUploadNotFoundError(Exception):
    pass


class ReceiptUploadAlreadyConfirmedError(Exception):
    pass


class ReceiptUploadNotAvailableError(Exception):
    def __init__(self, status: ReceiptUploadStatus):
        self.status = status
        super().__init__(f"Receipt upload is not available (status={status.value})")


def confirm_receipt_upload(
    db: Session,
    upload_id: str,
    *,
    business_name: str,
    receipt_number: str | None,
    amount: Decimal,
    vat_amount: Decimal | None,
    currency: str,
    category: ExpenseCategory,
    expense_date,
    payment_method: str | None,
    notes: str | None,
    extraction_confidence: float | None,
) -> Expense:
    """Atomically claims a pending upload and creates its expense.

    Uses a conditional UPDATE (status='pending' -> 'confirmed') so that two concurrent
    confirmation attempts for the same upload can never both succeed, which is what
    actually prevents a duplicate expense — not just an application-level status check.
    """
    repository = ReceiptUploadRepository(db)

    claim_result = db.execute(
        update(ReceiptUpload)
        .where(ReceiptUpload.id == upload_id, ReceiptUpload.status == ReceiptUploadStatus.PENDING)
        .values(status=ReceiptUploadStatus.CONFIRMED, confirmed_at=datetime.utcnow())
    )

    if claim_result.rowcount == 0:
        existing = repository.get(upload_id)
        if existing is None:
            raise ReceiptUploadNotFoundError()
        if existing.status == ReceiptUploadStatus.CONFIRMED:
            raise ReceiptUploadAlreadyConfirmedError()
        raise ReceiptUploadNotAvailableError(existing.status)

    try:
        claimed_upload = repository.get(upload_id)
        assert claimed_upload is not None  # guaranteed: rowcount == 1 means this row exists
        expense = Expense(
            business_name=business_name,
            receipt_number=receipt_number,
            amount=amount,
            vat_amount=vat_amount,
            currency=currency,
            category=category,
            expense_date=expense_date,
            payment_method=payment_method,
            notes=notes,
            receipt_image_path=claimed_upload.stored_filename,
            extraction_confidence=extraction_confidence,
            extraction_status=ExtractionStatus.CONFIRMED,
        )
        db.add(expense)
        db.flush()
        db.execute(update(ReceiptUpload).where(ReceiptUpload.id == upload_id).values(expense_id=expense.id))
        db.commit()
        db.refresh(expense)
        return expense
    except Exception:
        db.rollback()
        raise


def delete_expense_and_cleanup_receipt(db: Session, upload_service: UploadService, expense: Expense) -> bool:
    """Deletes an expense and best-effort removes its receipt image.

    The database delete always commits first; a failure to remove the underlying
    file never leaves the database in an inconsistent state — it only leaves an
    orphaned file on disk, which the cleanup job will not touch (it only targets
    pending uploads), but which is harmless and can be cleared manually.
    """
    receipt_filename = expense.receipt_image_path
    db.execute(update(ReceiptUpload).where(ReceiptUpload.expense_id == expense.id).values(expense_id=None))
    db.delete(expense)
    db.commit()

    if not receipt_filename:
        return True

    deleted = upload_service.delete(receipt_filename)
    if not deleted:
        logger.warning("Failed to delete receipt image file '%s' for a removed expense.", receipt_filename)
    return deleted


def cleanup_expired_uploads(db: Session, upload_service: UploadService, older_than_hours: int) -> int:
    """Marks stale pending uploads as expired and removes their orphaned files.

    Only ever deletes files resolved through UploadService.resolve_path, which
    guarantees the path stays inside the configured uploads directory.
    """
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    repository = ReceiptUploadRepository(db)
    stale_uploads = repository.list_pending_older_than(cutoff)

    for upload in stale_uploads:
        upload_service.delete(upload.stored_filename)
        upload.status = ReceiptUploadStatus.EXPIRED

    db.commit()
    return len(stale_uploads)
