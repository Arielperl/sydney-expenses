"""CSV sales-export import.

One documented format only for v1 — ambiguous column-guessing is explicitly
out of scope. Header row required:
date,customer,service,amount,currency
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch, ImportStatus
from app.models.sale import DocumentStatus, Sale, SaleSource, SaleStatus, TaxTreatment
from app.models.sale_event import SaleEventSource, SaleEventType
from app.schemas.validators import validate_date_reasonable, validate_currency_code, validate_required_text
from app.services.sale_events import record_event
from app.services.sale_service import attempt_document_generation
from app.services.tax.vat import calculate_vat, vat_rate_snapshot

REQUIRED_COLUMNS = ["date", "customer", "service", "amount", "currency"]


@dataclass
class CsvRowErrorInfo:
    row_number: int
    message: str


@dataclass
class ParsedCsvRow:
    row_number: int
    sale_date: date
    service: str
    customer: str
    amount: Decimal
    currency: str
    external_id: str


def _parse_row(row_number: int, raw_row: dict[str, str], file_hash: str) -> ParsedCsvRow:
    date_raw = (raw_row.get("date") or "").strip()
    try:
        sale_date = datetime.strptime(date_raw, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"'date' must be in YYYY-MM-DD format, got '{date_raw}'") from exc
    validate_date_reasonable(sale_date)

    customer = validate_required_text(raw_row.get("customer") or "")
    service = validate_required_text(raw_row.get("service") or "")

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
        sale_date=sale_date,
        service=service,
        customer=customer,
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


def create_import_batch_and_sales(
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
        # This documented CSV format has no VAT/tax-treatment column of its
        # own (v1, see the module docstring) — every imported row is a
        # single all-inclusive `amount`, so it's treated as an ordinary
        # standard-VAT sale under the business's own Israeli tax
        # configuration, the same as a manually entered one with no
        # treatment chosen.
        vat_amount = calculate_vat(row.amount, TaxTreatment.STANDARD)
        sale = Sale(
            customer_name=row.customer,
            service_name=row.service,
            gross_amount=row.amount,
            vat_amount=vat_amount,
            tax_treatment=TaxTreatment.STANDARD,
            vat_rate=vat_rate_snapshot(TaxTreatment.STANDARD),
            net_amount=row.amount - vat_amount,
            currency=row.currency,
            source=SaleSource.CSV,
            source_provider="csv",
            external_id=row.external_id,
            occurred_at=datetime.combine(row.sale_date, datetime.min.time()),
            status=SaleStatus.SUCCEEDED,
            document_status=DocumentStatus.PENDING,
            import_batch_id=batch.id,
        )
        savepoint = db.begin_nested()
        try:
            db.add(sale)
            savepoint.commit()
            created_count += 1
        except IntegrityError:
            savepoint.rollback()
            duplicate_count += 1
            continue
        record_event(db, sale.id, SaleEventType.SALE_IMPORTED_FROM_CSV, SaleEventSource.CSV)
        record_event(db, sale.id, SaleEventType.PAYMENT_SUCCEEDED, SaleEventSource.CSV)
        db.commit()
        attempt_document_generation(db, sale)

    batch.created_count = created_count
    batch.duplicate_count = duplicate_count
    batch.status = ImportStatus.COMPLETED
    db.commit()
    db.refresh(batch)
    return batch
