from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.exceptions import ExceptionCenterResponse
from app.schemas.sale import sale_to_read
from app.services.exception_center import build_exception_center

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


@router.get("", response_model=ExceptionCenterResponse)
def get_exception_center(
    limit: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ExceptionCenterResponse:
    center = build_exception_center(db, limit=limit)
    return ExceptionCenterResponse(
        attention_count=center.attention_count,
        pending_documents_count=center.pending_documents_count,
        document_failures_count=center.document_failures_count,
        refunds_needing_attention_count=center.refunds_needing_attention_count,
        incomplete_details_count=center.incomplete_details_count,
        pending_documents=[sale_to_read(s) for s in center.pending_documents],
        document_failures=[sale_to_read(s) for s in center.document_failures],
        refunds_needing_attention=[sale_to_read(s) for s in center.refunds_needing_attention],
        incomplete_details=[sale_to_read(s) for s in center.incomplete_details],
    )
