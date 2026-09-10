from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.document_category import DocumentCategory


class ExtractedReceiptData(BaseModel):
    """Provider-independent structured result returned by a ReceiptExtractor
    when reading a document image — used only by the secondary "import a
    historical document" feature, never to create a sale from scratch."""

    business_name: str | None = None
    receipt_number: str | None = None
    date: date_type | None = None
    total: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    vat: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str = "ILS"
    category: DocumentCategory = DocumentCategory.OTHER
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def validate_date_reasonable(cls, value: date_type | None) -> date_type | None:
        if value is None:
            return value
        if value > date_type.today():
            raise ValueError("extracted date must not be in the future")
        return value


class DocumentImportResponse(BaseModel):
    """Result of importing a previously issued document image and attaching
    it to an existing sale — a secondary, explicit action, never automatic
    matching."""

    sale_id: str
    document_url: str
    extraction_succeeded: bool
    extracted_data: ExtractedReceiptData | None = None
    error_message: str | None = None
    document_status: str
    document_number: str | None = None
