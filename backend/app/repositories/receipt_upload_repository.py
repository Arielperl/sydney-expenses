from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus
from app.schemas.receipt import ExtractedReceiptData


class ReceiptUploadRepository:
    def __init__(self, db: Session):
        self._db = db

    def create_pending(self, stored_filename: str, storage_provider: str) -> ReceiptUpload:
        upload = ReceiptUpload(
            stored_filename=stored_filename,
            storage_provider=storage_provider,
            status=ReceiptUploadStatus.PENDING,
        )
        self._db.add(upload)
        self._db.commit()
        self._db.refresh(upload)
        return upload

    def get(self, upload_id: str) -> ReceiptUpload | None:
        return self._db.get(ReceiptUpload, upload_id)

    def save_extraction(self, upload: ReceiptUpload, extracted: ExtractedReceiptData) -> None:
        """Persists a bounded snapshot of the extraction result — never the
        raw OCR text, image bytes, or full provider response — so a later
        approval never depends on the browser resending financial fields."""
        upload.extracted_business_name = extracted.business_name
        upload.extracted_receipt_number = extracted.receipt_number
        upload.extracted_date = extracted.date
        upload.extracted_total = extracted.total
        upload.extracted_vat = extracted.vat
        upload.extracted_currency = extracted.currency
        upload.extracted_category = extracted.category
        upload.extraction_confidence = extracted.confidence
        upload.extraction_warnings = extracted.warnings
        self._db.commit()
        self._db.refresh(upload)

    def list_pending_older_than(self, cutoff: datetime) -> list[ReceiptUpload]:
        stmt = select(ReceiptUpload).where(
            ReceiptUpload.status == ReceiptUploadStatus.PENDING,
            ReceiptUpload.created_at < cutoff,
        )
        return list(self._db.scalars(stmt).all())
