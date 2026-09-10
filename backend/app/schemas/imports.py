from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel


class CsvRowError(BaseModel):
    row_number: int
    message: str


class CsvPreviewRow(BaseModel):
    row_number: int
    expense_date: date_type
    description: str
    merchant: str
    amount: Decimal
    currency: str
    external_id: str


class CsvPreviewResponse(BaseModel):
    file_hash: str
    filename: str | None = None
    valid_rows: list[CsvPreviewRow]
    errors: list[CsvRowError]
    is_repeat_file: bool


class CsvConfirmRequest(BaseModel):
    file_hash: str
    filename: str | None = None
    valid_rows: list[CsvPreviewRow]


class CsvConfirmResponse(BaseModel):
    import_batch_id: str
    created_count: int
    duplicate_count: int
    error_count: int
