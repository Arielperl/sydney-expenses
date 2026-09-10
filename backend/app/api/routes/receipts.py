import logging
import time

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_receipt_extractor, get_receipt_storage, get_upload_service, resolve_receipt_image_url
from app.core.config import get_settings
from app.database import get_db
from app.models.expense import DocumentStatus, Expense
from app.repositories.receipt_upload_repository import ReceiptUploadRepository
from app.schemas.expense import ExpenseRead, expense_to_read
from app.schemas.receipt import ExtractedReceiptData, MatchCandidateRead, ReceiptConfirmRequest, ReceiptUploadResponse
from app.services.extraction.base import ReceiptExtractor
from app.services.receipt_lifecycle_service import (
    ReceiptUploadAlreadyConfirmedError,
    ReceiptUploadNotAvailableError,
    ReceiptUploadNotFoundError,
    confirm_receipt_upload,
)
from app.services.reconciliation.exceptions import ExpenseNotEligibleError, ReceiptNotAvailableError
from app.services.reconciliation.matching import MatchDecision
from app.services.reconciliation.workflow import apply_match_result, targeted_match
from app.services.storage.base import ReceiptStorage
from app.services.storage.exceptions import StorageError
from app.services.upload_service import FileTooLargeError, UnsupportedFileTypeError, UploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _missing_required_fields(extracted: ExtractedReceiptData) -> list[str]:
    missing = []
    if not extracted.business_name:
        missing.append("business_name")
    if extracted.total is None:
        missing.append("total")
    return missing


@router.post("/upload", response_model=ReceiptUploadResponse)
async def upload_receipt(
    file: UploadFile,
    expense_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
    upload_service: UploadService = Depends(get_upload_service),
    storage: ReceiptStorage = Depends(get_receipt_storage),
    extractor: ReceiptExtractor = Depends(get_receipt_extractor),
) -> ReceiptUploadResponse:
    target_expense: Expense | None = None
    if expense_id is not None:
        target_expense = db.get(Expense, expense_id)
        if target_expense is None:
            raise HTTPException(status_code=404, detail="Expense not found")
        if target_expense.document_status != DocumentStatus.MISSING:
            raise HTTPException(status_code=409, detail="This expense already has a document, or none is expected")

    try:
        temp_path, verified_format = await upload_service.stage(file)
    except (UnsupportedFileTypeError, FileTooLargeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        # Extraction always runs against the local temp file, regardless of which
        # storage provider is configured — this is what lets local Tesseract/Ollama
        # extraction work even when receipts are ultimately stored in Supabase.
        try:
            object_key = storage.store(temp_path, verified_format)
        except StorageError as exc:
            logger.warning(
                "receipt_storage_upload_failed provider=%s error_category=%s", storage.provider, type(exc).__name__
            )
            raise HTTPException(
                status_code=503,
                detail="Could not store the receipt image right now. You can still add this expense manually.",
            ) from exc

        upload_repository = ReceiptUploadRepository(db)
        pending_upload = upload_repository.create_pending(object_key, storage_provider=storage.provider)
        image_url = resolve_receipt_image_url(storage.provider, object_key)
        extractor_provider = get_settings().receipt_extractor_provider

        started_at = time.perf_counter()
        try:
            extracted = extractor.extract(str(temp_path))
        except Exception as exc:  # noqa: BLE001 - extraction provider failures are expected and handled here
            duration_ms = (time.perf_counter() - started_at) * 1000
            # Structured, safe metadata only — never the image, extracted text, or a key.
            logger.info(
                "receipt_extraction result=failure provider=%s duration_ms=%.1f upload_id=%s error_category=%s",
                extractor_provider,
                duration_ms,
                pending_upload.id,
                type(exc).__name__,
            )
            return ReceiptUploadResponse(
                upload_id=pending_upload.id,
                receipt_image_url=image_url,
                extraction_succeeded=False,
                extracted_data=None,
                error_message=f"Receipt extraction failed: {exc}",
            )

        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "receipt_extraction result=success provider=%s duration_ms=%.1f upload_id=%s missing_fields=%s",
            extractor_provider,
            duration_ms,
            pending_upload.id,
            ",".join(_missing_required_fields(extracted)) or "none",
        )

        upload_repository.save_extraction(pending_upload, extracted)

        if target_expense is not None:
            try:
                result = targeted_match(db, pending_upload, target_expense, extracted)
            except ExpenseNotEligibleError as exc:
                raise HTTPException(
                    status_code=409, detail="This expense was matched to another document in the meantime"
                ) from exc
            except ReceiptNotAvailableError as exc:
                raise HTTPException(status_code=409, detail="This upload is no longer available") from exc
            if result.attached and result.expense is not None:
                return ReceiptUploadResponse(
                    upload_id=pending_upload.id,
                    receipt_image_url=image_url,
                    extraction_succeeded=True,
                    extracted_data=extracted,
                    attached_to_expense_id=result.expense.id,
                    match_reasons=result.reasons,
                )
            return ReceiptUploadResponse(
                upload_id=pending_upload.id,
                receipt_image_url=image_url,
                extraction_succeeded=True,
                extracted_data=extracted,
                conflict=MatchCandidateRead(
                    expense_id=target_expense.id,
                    business_name=target_expense.business_name,
                    amount=target_expense.amount,
                    currency=target_expense.currency,
                    expense_date=target_expense.expense_date,
                    score=0.0,
                    reasons=result.reasons,
                ),
            )

        match_outcome = apply_match_result(db, pending_upload, extracted)
        logger.info(
            "receipt_reconciliation decision=%s upload_id=%s expense_id=%s",
            match_outcome.decision.value,
            pending_upload.id,
            match_outcome.expense.id if match_outcome.expense else "none",
        )

        if match_outcome.decision == MatchDecision.AUTO_MATCH and match_outcome.expense is not None:
            return ReceiptUploadResponse(
                upload_id=pending_upload.id,
                receipt_image_url=image_url,
                extraction_succeeded=True,
                extracted_data=extracted,
                auto_matched=True,
                matched_expense_id=match_outcome.expense.id,
                match_reasons=match_outcome.reasons,
            )

        if (
            match_outcome.decision in (MatchDecision.SUGGESTED, MatchDecision.NEEDS_REVIEW)
            and match_outcome.expense is not None
        ):
            return ReceiptUploadResponse(
                upload_id=pending_upload.id,
                receipt_image_url=image_url,
                extraction_succeeded=True,
                extracted_data=extracted,
                suggested_match=MatchCandidateRead(
                    expense_id=match_outcome.expense.id,
                    business_name=match_outcome.expense.business_name,
                    amount=match_outcome.expense.amount,
                    currency=match_outcome.expense.currency,
                    expense_date=match_outcome.expense.expense_date,
                    score=match_outcome.expense.reconciliation_confidence or 0.0,
                    reasons=match_outcome.reasons,
                ),
            )

        return ReceiptUploadResponse(
            upload_id=pending_upload.id,
            receipt_image_url=image_url,
            extraction_succeeded=True,
            extracted_data=extracted,
        )
    finally:
        upload_service.cleanup(temp_path)


@router.post("/confirm", response_model=ExpenseRead, status_code=201)
def confirm_receipt(
    payload: ReceiptConfirmRequest,
    db: Session = Depends(get_db),
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

    image_url = resolve_receipt_image_url(expense.storage_provider, expense.receipt_image_path)
    return expense_to_read(expense, image_url)
