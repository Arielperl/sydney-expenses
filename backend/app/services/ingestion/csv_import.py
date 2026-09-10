"""CSV bank/credit-card statement import.

One documented format only for v1 — ambiguous column-guessing is explicitly
out of scope. Header row required: date,description,merchant,amount,currency
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExpenseSource
from app.models.import_batch import ImportBatch, ImportStatus
from app.schemas.validators import validate_business_name, validate_currency_code, validate_expense_date_reasonable

REQUIRED_COLUMNS = ["date", "description", "merchant", "amount", "currency"]


@dataclass
class CsvRowErrorInfo:
    row_number: int
    message: str


@dataclass
class ParsedCsvRow:
    row_number: int
    expense_date: date
    description: str
    merchant: str
    amount: Decimal
    currency: str
    external_id: str


def _parse_row(row_number: int, raw_row: dict[str, str], file_hash: str) -> ParsedCsvRow:
    date_raw = (raw_row.get("date") or "").strip()
    try:
        expense_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"'date' must be in YYYY-MM-DD format, got '{date_raw}'") from exc
    validate_expense_date_reasonable(expense_date)

    merchant = validate_business_name(raw_row.get("merchant") or "")
    description = (raw_row.get("description") or "").strip()

    amount_raw = (raw_row.get("amount") or "").strip()
    try:
        amount = Decimal(amount_raw)
    except InvalidOperation as exc:
        raise ValueError(f"'amount' is not a valid number: '{amount_raw}'") from exc
    if amount <= 0:
        raise ValueError("'amount' must be positive")

    currency = validate_currency_code((raw_row.get("currency") or "").strip())

    return ParsedCsvRow(
        row_number=row_number,
        expense_date=expense_date,
        description=description,
        merchant=merchant,
        amount=amount,
        currency=currency,
        external_id=f"csv:{file_hash}:{row_number}",
    )


def parse_csv(raw_bytes: bytes, file_hash: str, *, max_rows: int) -> tuple[list[ParsedCsvRow], list[CsvRowErrorInfo]]:
    # utf-8-sig transparently strips a BOM if present, and behaves identically
    # to plain utf-8 when there isn't one.
    text = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None or [name.strip().lower() for name in reader.fieldnames] != REQUIRED_COLUMNS:
        raise ValueError(
            f"CSV header must be exactly: {','.join(REQUIRED_COLUMNS)} "
            f"(got: {','.join(reader.fieldnames or [])})"
        )

    valid_rows: list[ParsedCsvRow] = []
    errors: list[CsvRowErrorInfo] = []
    row_number = 0
    for raw_row in reader:
        row_number += 1
        if row_number > max_rows:
            errors.append(
                CsvRowErrorInfo(row_number=row_number, message=f"Row exceeds the {max_rows}-row import limit")
            )
            break
        try:
            valid_rows.append(_parse_row(row_number, raw_row, file_hash))
        except ValueError as exc:
            errors.append(CsvRowErrorInfo(row_number=row_number, message=str(exc)))

    return valid_rows, errors


def find_batch_by_file_hash(db: Session, file_hash: str) -> ImportBatch | None:
    return db.query(ImportBatch).filter(ImportBatch.file_hash == file_hash).first()


def create_import_batch_and_expenses(
    db: Session, file_hash: str, filename: str | None, rows: list[ParsedCsvRow]
) -> ImportBatch:
    batch = ImportBatch(
        file_hash=file_hash,
        filename=filename,
        status=ImportStatus.PENDING,
        valid_row_count=len(rows),
        error_row_count=0,
    )
    db.add(batch)
    db.flush()

    created_count = 0
    duplicate_count = 0
    for row in rows:
        expense = Expense(
            business_name=row.merchant,
            amount=row.amount,
            currency=row.currency,
            category=ExpenseCategory.OTHER,
            expense_date=row.expense_date,
            source=ExpenseSource.CSV,
            source_provider="csv",
            external_id=row.external_id,
            raw_description=row.description,
            occurred_at=datetime.combine(row.expense_date, datetime.min.time()),
            document_status=DocumentStatus.MISSING,
            import_batch_id=batch.id,
        )
        savepoint = db.begin_nested()
        try:
            db.add(expense)
            savepoint.commit()
            created_count += 1
        except IntegrityError:
            savepoint.rollback()
            duplicate_count += 1

    batch.created_count = created_count
    batch.duplicate_count = duplicate_count
    batch.status = ImportStatus.COMPLETED
    db.commit()
    db.refresh(batch)
    return batch
