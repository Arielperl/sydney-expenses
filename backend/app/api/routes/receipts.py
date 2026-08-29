from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_receipt_extractor, get_upload_service
from app.database import get_db
from app.repositories.receipt_upload_repository import ReceiptUploadRepository
from app.schemas.expense import ExpenseRead, expense_to_read
from app.schemas.receipt import ReceiptConfirmRequest, ReceiptUploadResponse
from app.services.extraction.base import ReceiptExtractor
from app.services.receipt_lifecycle_service import (
    ReceiptUploadAlreadyConfirmedError,
    ReceiptUploadNotAvailableError,
    ReceiptUploadNotFoundError,
    confirm_receipt_upload,
)
from app.services.upload_service import FileTooLargeError, UnsupportedFileTypeError, UploadService

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("/upload", response_model=ReceiptUploadResponse)
async def upload_receipt(
    file: UploadFile,
    db: Session = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service),
    extractor: ReceiptExtractor = Depends(get_receipt_extractor),
) -> ReceiptUploadResponse:
    try:
        stored_filename, stored_path = await upload_service.save(file)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    upload_repository = ReceiptUploadRepository(db)
    pending_upload = upload_repository.create_pending(stored_filename)
    image_url = upload_service.image_url(stored_filename)

    try:
        extracted = extractor.extract(stored_path)
    except Exception as exc:  # noqa: BLE001 - extraction provider failures are expected and handled here
        return ReceiptUploadResponse(
            upload_id=pending_upload.id,
            receipt_image_url=image_url,
            extraction_succeeded=False,
            extracted_data=None,
            error_message=f"Receipt extraction failed: {exc}",
        )

    return ReceiptUploadResponse(
        upload_id=pending_upload.id,
        receipt_image_url=image_url,
        extraction_succeeded=True,
        extracted_data=extracted,
    )


@router.post("/confirm", response_model=ExpenseRead, status_code=201)
def confirm_receipt(
    payload: ReceiptConfirmRequest,
    db: Session = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service),
) -> ExpenseRead:
    try:
        expense = confirm_receipt_upload(
            db,
            payload.upload_id,
            business_name=payload.business_name,
            receipt_number=payload.receipt_number,
            amount=payload.amount,
            vat_amount=payload.vat_amount,
            currency=payload.currency,
            category=payload.category,
            expense_date=payload.expense_date,
            payment_method=payload.payment_method,
            notes=payload.notes,
            extraction_confidence=payload.extraction_confidence,
        )
    except ReceiptUploadNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Uploaded receipt was not found") from exc
    except ReceiptUploadAlreadyConfirmedError as exc:
        raise HTTPException(status_code=409, detail="This receipt has already been confirmed") from exc
    except ReceiptUploadNotAvailableError as exc:
        raise HTTPException(
            status_code=410, detail="This receipt upload is no longer available, please upload it again"
        ) from exc

    return expense_to_read(expense, upload_service.image_url(expense.receipt_image_path))
