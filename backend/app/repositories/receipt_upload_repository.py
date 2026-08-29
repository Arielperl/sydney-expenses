from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus


class ReceiptUploadRepository:
    def __init__(self, db: Session):
        self._db = db

    def create_pending(self, stored_filename: str) -> ReceiptUpload:
        upload = ReceiptUpload(stored_filename=stored_filename, status=ReceiptUploadStatus.PENDING)
        self._db.add(upload)
        self._db.commit()
        self._db.refresh(upload)
        return upload

    def get(self, upload_id: str) -> ReceiptUpload | None:
        return self._db.get(ReceiptUpload, upload_id)

    def list_pending_older_than(self, cutoff: datetime) -> list[ReceiptUpload]:
        stmt = select(ReceiptUpload).where(
            ReceiptUpload.status == ReceiptUploadStatus.PENDING,
            ReceiptUpload.created_at < cutoff,
        )
        return list(self._db.scalars(stmt).all())
