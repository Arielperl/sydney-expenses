from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.admin import get_support_db, _require_support
from app.core.rate_limit import RateLimiter
from app.database import get_db
from app.models.business import AppAccount, Business
from app.models.support_request import SupportRequest

router = APIRouter(prefix="/support", tags=["support"])
_requests_by_user = RateLimiter(max_requests=10, window_seconds=3600)


class SupportRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=10, max_length=5000)
    provider: str | None = Field(default=None, max_length=80)


class SupportRequestRead(BaseModel):
    id: str
    business_id: str
    business_name: str | None = None
    requester_email: str | None = None
    subject: str
    message: str
    provider: str | None
    status: Literal["open", "resolved"]
    created_at: datetime


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["open", "resolved"]


def _read(row: SupportRequest, db: Session, *, staff: bool = False) -> SupportRequestRead:
    business = db.get(Business, row.business_id) if staff else None
    account = db.get(AppAccount, row.requester_user_id) if staff else None
    return SupportRequestRead(
        id=row.id, business_id=row.business_id,
        business_name=business.name if business else None,
        requester_email=account.email if account else None,
        subject=row.subject, message=row.message, provider=row.provider,
        status=row.status, created_at=row.created_at,
    )


@router.post("/requests", response_model=SupportRequestRead, status_code=201)
def create_request(payload: SupportRequestCreate, request: Request, db: Session = Depends(get_db)) -> SupportRequestRead:
    user = request.state.user
    if user["role"] not in ("owner", "manager"):
        raise HTTPException(403, "נדרשת הרשאת בעלים או מנהל")
    _requests_by_user.check(f"support-request:{user['id']}")
    subject, message = payload.subject.strip(), payload.message.strip()
    if len(subject) < 3 or len(message) < 10:
        raise HTTPException(422, "נא למלא נושא ותיאור מפורט")
    row = SupportRequest(
        business_id=user["business_id"], requester_user_id=user["id"],
        subject=subject, message=message, provider=payload.provider.strip() if payload.provider else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _read(row, db)


@router.get("/requests", response_model=list[SupportRequestRead])
def own_requests(request: Request, db: Session = Depends(get_db)) -> list[SupportRequestRead]:
    rows = db.scalars(select(SupportRequest).order_by(SupportRequest.created_at.desc()).limit(100)).all()
    return [_read(row, db) for row in rows]


@router.get("/staff/requests", response_model=list[SupportRequestRead])
def staff_requests(request: Request, db: Session = Depends(get_support_db)) -> list[SupportRequestRead]:
    _require_support(request, db)
    rows = db.scalars(select(SupportRequest).order_by(SupportRequest.created_at.desc()).limit(500)).all()
    return [_read(row, db, staff=True) for row in rows]


@router.patch("/staff/requests/{request_id}", response_model=SupportRequestRead)
def update_request(request_id: str, payload: StatusUpdate, request: Request, db: Session = Depends(get_support_db)) -> SupportRequestRead:
    _require_support(request, db)
    row = db.get(SupportRequest, request_id)
    if row is None:
        raise HTTPException(404, "הפנייה לא נמצאה")
    row.status = payload.status
    db.commit()
    db.refresh(row)
    return _read(row, db, staff=True)
