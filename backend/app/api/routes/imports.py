import hashlib

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
    create_import_batch_and_expenses,
    find_batch_by_file_hash,
    parse_csv,
)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/csv/preview", response_model=CsvPreviewResponse)
async def preview_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CsvPreviewResponse:
    raw_bytes = await file.read()
    if len(raw_bytes) > settings.csv_max_file_size_bytes:
        raise HTTPException(status_code=413, detail="CSV file is too large")

    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        valid_rows, errors = parse_csv(raw_bytes, file_hash, max_rows=settings.csv_max_rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing_batch = find_batch_by_file_hash(db, file_hash)

    return CsvPreviewResponse(
        file_hash=file_hash,
        filename=file.filename,
        valid_rows=[CsvPreviewRow(**row.__dict__) for row in valid_rows],
        errors=[CsvRowError(row_number=e.row_number, message=e.message) for e in errors],
        is_repeat_file=existing_batch is not None,
    )


@router.post("/csv/confirm", response_model=CsvConfirmResponse, status_code=201)
def confirm_csv(
    payload: CsvConfirmRequest,
    db: Session = Depends(get_db),
) -> CsvConfirmResponse:
    rows = [
        ParsedCsvRow(
            row_number=row.row_number,
            expense_date=row.expense_date,
            description=row.description,
            merchant=row.merchant,
            amount=row.amount,
            currency=row.currency,
            external_id=row.external_id,
        )
        for row in payload.valid_rows
    ]
    batch = create_import_batch_and_expenses(db, payload.file_hash, payload.filename, rows)
    return CsvConfirmResponse(
        import_batch_id=batch.id,
        created_count=batch.created_count or 0,
        duplicate_count=batch.duplicate_count or 0,
        error_count=batch.error_row_count,
    )
