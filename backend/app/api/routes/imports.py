import hashlib
import time

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database import get_db
from app.schemas.imports import (
    CsvConfirmRequest,
    CsvConfirmResponse,
    CsvPreviewResponse,
    CsvPreviewRow,
    CsvRowError,
)
from app.services.ingestion.csv_import import (
    ParsedCsvRow,
    create_import_batch_and_sales,
    find_batch_by_file_hash,
    parse_csv,
)
from app.services.ingestion.csv_preview_security import sign_csv_preview, verify_csv_preview

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/csv/preview", response_model=CsvPreviewResponse)
async def preview_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CsvPreviewResponse:
    raw_buffer = bytearray()
    while True:
        chunk = await file.read(min(64 * 1024, settings.csv_max_file_size_bytes + 1))
        if not chunk:
            break
        raw_buffer.extend(chunk)
        if len(raw_buffer) > settings.csv_max_file_size_bytes:
            raise HTTPException(status_code=413, detail="CSV file is too large")
    raw_bytes = bytes(raw_buffer)

    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        valid_rows, errors = parse_csv(raw_bytes, file_hash, max_rows=settings.csv_max_rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing_batch = find_batch_by_file_hash(db, file_hash)

    preview_rows = [CsvPreviewRow(**row.__dict__) for row in valid_rows]
    expires_at = int(time.time()) + settings.csv_preview_ttl_seconds
    filename = file.filename.replace("\\", "/").rsplit("/", 1)[-1] if file.filename else None
    filename = "".join(character for character in filename if character.isprintable())[:255] if filename else None
    return CsvPreviewResponse(
        file_hash=file_hash,
        filename=filename,
        valid_rows=preview_rows,
        errors=[CsvRowError(row_number=e.row_number, message=e.message) for e in errors],
        is_repeat_file=existing_batch is not None,
        preview_signature=sign_csv_preview(
            settings, db.info["business_id"], file_hash, filename, preview_rows, expires_at
        ),
        preview_expires_at=expires_at,
    )


@router.post("/csv/confirm", response_model=CsvConfirmResponse, status_code=201)
def confirm_csv(
    payload: CsvConfirmRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CsvConfirmResponse:
    if not verify_csv_preview(
        settings,
        db.info["business_id"],
        payload.file_hash,
        payload.filename,
        payload.valid_rows,
        payload.preview_expires_at,
        payload.preview_signature,
    ):
        raise HTTPException(status_code=422, detail="CSV preview confirmation is invalid or was modified")
    rows = [
        ParsedCsvRow(
            row_number=row.row_number,
            sale_date=row.sale_date,
            customer=row.customer,
            service=row.service,
            amount=row.amount,
            currency=row.currency,
            external_id=row.external_id,
        )
        for row in payload.valid_rows
    ]
    batch = create_import_batch_and_sales(db, payload.file_hash, payload.filename, rows)
    return CsvConfirmResponse(
        import_batch_id=batch.id,
        created_count=batch.created_count or 0,
        duplicate_count=batch.duplicate_count or 0,
        error_count=batch.error_row_count,
    )
