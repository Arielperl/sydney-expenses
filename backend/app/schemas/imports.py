from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.validators import validate_currency_code, validate_date_reasonable, validate_required_text

# Mirrors the default `csv_max_rows` setting (see app/core/config.py). A
# hardcoded ceiling here — independent of whatever `/csv/preview` was called
# with — because `/csv/confirm`'s `valid_rows` is client-supplied and must
# never be trusted to self-report a safe size.
MAX_CONFIRM_ROWS = 2000


class CsvRowError(BaseModel):
    row_number: int
    message: str


class CsvPreviewRow(BaseModel):
    """Used both as a `/csv/preview` response row (always server-constructed,
    already valid) and as a `/csv/confirm` request row (client-supplied, and
    therefore the part of this API that must never trust its input at face
    value — see `create_import_batch_and_sales`, which builds a `Sale`
    directly from these fields). The constraints below mirror exactly what
    `_parse_row` already enforces during preview, so a round-tripped
    server-generated row always validates, but a tampered confirm payload
    (negative amount, non-ISO currency, out-of-range date, forged
    external_id) is rejected before it ever reaches the database."""

    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(ge=1)
    sale_date: date_type
    customer: str = Field(min_length=1, max_length=255)
    service: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    external_id: str = Field(min_length=1, max_length=300)

    @field_validator("customer", "service")
    @classmethod
    def _validate_required_text(cls, value: str) -> str:
        return validate_required_text(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)

    @field_validator("sale_date")
    @classmethod
    def _validate_sale_date(cls, value: date_type) -> date_type:
        return validate_date_reasonable(value)  # type: ignore[return-value]


class CsvPreviewResponse(BaseModel):
    file_hash: str
    filename: str | None = Field(default=None, max_length=255)
    valid_rows: list[CsvPreviewRow]
    errors: list[CsvRowError]
    is_repeat_file: bool
    preview_signature: str
    preview_expires_at: int


class CsvConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_hash: str = Field(min_length=1, max_length=128)
    filename: str | None = Field(default=None, max_length=255)
    valid_rows: list[CsvPreviewRow] = Field(max_length=MAX_CONFIRM_ROWS)
    preview_signature: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    preview_expires_at: int = Field(gt=0)

    @model_validator(mode="after")
    def _validate_external_ids_match_file_hash(self) -> "CsvConfirmRequest":
        # `external_id` is always `csv:{file_hash}:{row_number}` when it comes
        # from `/csv/preview` (see `_parse_row`) — this rejects a confirm
        # payload whose rows were retargeted at a different file_hash or
        # row_number than the ones actually declared.
        expected = {f"csv:{self.file_hash}:{row.row_number}" for row in self.valid_rows}
        actual = {row.external_id for row in self.valid_rows}
        if actual - expected:
            raise ValueError("valid_rows contains an external_id inconsistent with file_hash/row_number")
        return self


class CsvConfirmResponse(BaseModel):
    import_batch_id: str
    created_count: int
    duplicate_count: int
    error_count: int
