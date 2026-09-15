from pydantic import BaseModel

from app.schemas.sale import SaleRead


class ExceptionCenterResponse(BaseModel):
    attention_count: int
    pending_documents: list[SaleRead]
    document_failures: list[SaleRead]
    refunds_needing_attention: list[SaleRead]
    incomplete_details: list[SaleRead]
