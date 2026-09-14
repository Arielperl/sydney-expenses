"""Secondary feature: importing a previously issued document (a photo of an
old receipt/invoice) and attaching it directly to one specific sale.
Deliberately NOT part of the primary sales journey — there is no
auto-matching here, the caller always names the sale explicitly, mirroring
the old app's most defensible pattern (targeted attach) without any of the
suggested-match machinery that used to sit around it.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_receipt_extractor, get_receipt_storage, get_upload_service, resolve_receipt_image_url
from app.database import get_db
from app.models.sale import DocumentStatus, Sale
from app.repositories.sale_repository import SaleRepository
from app.schemas.receipt import DocumentImportResponse
from app.services.extraction.base import ReceiptExtractor
from app.services.storage.base import ReceiptStorage
from app.services.storage.exceptions import StorageError
from app.services.upload_service import FileTooLargeError, UnsupportedFileTypeError, UploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/import", response_model=DocumentImportResponse)
async def import_historical_document(
    sale_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service),
    storage: ReceiptStorage = Depends(get_receipt_storage),
    extractor: ReceiptExtractor = Depends(get_receipt_extractor),
) -> DocumentImportResponse:
    repository = SaleRepository(db)
    sale = repository.get(sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")

    try:
        temp_path, verified_format = await upload_service.stage(file)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        try:
            object_key = storage.store(temp_path, verified_format)
        except StorageError as exc:
            logger.warning(
                "document_import_storage_failed provider=%s error_category=%s", storage.provider, type(exc).__name__
            )
            raise HTTPException(
                status_code=503, detail="Could not store the document image right now."
            ) from exc

        document_url = resolve_receipt_image_url(storage.provider, object_key)

        try:
            extracted = extractor.extract(str(temp_path))
            extraction_succeeded = True
            error_message = None
        except Exception as exc:  # noqa: BLE001 - extraction provider failures are expected and handled here
            logger.info("document_import_extraction_failed sale_id=%s error_category=%s", sale.id, type(exc).__name__)
            extracted = None
            extraction_succeeded = False
            error_message = "Document extraction failed. The image was stored for manual review."

        sale.document_status = DocumentStatus.ISSUED
        sale.document_url = document_url
        if extracted is not None and extracted.receipt_number:
            sale.document_number = extracted.receipt_number
        db.commit()
        db.refresh(sale)

        return DocumentImportResponse(
            sale_id=sale.id,
            document_url=document_url or "",
            extraction_succeeded=extraction_succeeded,
            extracted_data=extracted,
            error_message=error_message,
            document_status=sale.document_status.value,
            document_number=sale.document_number,
        )
    finally:
        upload_service.cleanup(temp_path)
