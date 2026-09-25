from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.admin import get_support_db, _require_support
from app.core.rate_limit import RateLimiter
from app.database import get_db
from app.models.business import AppAccount, Business
from app.models.support_request import SupportMessage, SupportRequest

router = APIRouter(prefix="/support", tags=["support"])
_requests_by_user = RateLimiter(max_requests=10, window_seconds=3600)
_messages_by_user = RateLimiter(max_requests=60, window_seconds=3600)


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
    updated_at: datetime


class SupportMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=5000)


class SupportMessageRead(BaseModel):
    id: str
    author_type: Literal["customer", "staff"]
    author_name: str | None
    body: str
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
        status=row.status, created_at=row.created_at, updated_at=row.updated_at,
    )


def _author_name(db: Session, user_id: str, author_type: str) -> str:
    account = db.get(AppAccount, user_id)
    if author_type == "staff":
        return account.display_name.strip() if account and account.display_name.strip() else "צוות התמיכה"
    if account:
        return account.display_name.strip() or account.email
    return "בעל העסק"


def _messages(row: SupportRequest, db: Session) -> list[SupportMessageRead]:
    result = [SupportMessageRead(
        id=f"initial-{row.id}",
        author_type="customer",
        author_name=_author_name(db, row.requester_user_id, "customer"),
        body=row.message,
        created_at=row.created_at,
    )]
    replies = db.scalars(
        select(SupportMessage)
        .where(SupportMessage.request_id == row.id)
        .order_by(SupportMessage.created_at, SupportMessage.id)
    ).all()
    result.extend(SupportMessageRead(
        id=message.id,
        author_type=message.author_type,
        author_name=_author_name(db, message.author_user_id, message.author_type),
        body=message.body,
        created_at=message.created_at,
    ) for message in replies)
    return result


def _own_request(request_id: str, db: Session) -> SupportRequest:
    row = db.get(SupportRequest, request_id)
    if row is None:
        raise HTTPException(404, "הפנייה לא נמצאה")
    return row


def _add_message(
    row: SupportRequest,
    payload: SupportMessageCreate,
    user_id: str,
    author_type: Literal["customer", "staff"],
    db: Session,
) -> SupportMessageRead:
    body = payload.body.strip()
    if not body:
        raise HTTPException(422, "לא ניתן לשלוח הודעה ריקה")
    message = SupportMessage(
        business_id=row.business_id,
        request_id=row.id,
        author_user_id=user_id,
        author_type=author_type,
        body=body,
    )
    row.status = "open"
    row.updated_at = datetime.utcnow()
    db.add(message)
    db.commit()
    db.refresh(message)
    return SupportMessageRead(
        id=message.id,
        author_type=message.author_type,
        author_name=_author_name(db, message.author_user_id, message.author_type),
        body=message.body,
        created_at=message.created_at,
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
def own_requests(request: Request, response: Response, db: Session = Depends(get_db)) -> list[SupportRequestRead]:
    response.headers["Cache-Control"] = "private, no-store"
    rows = db.scalars(select(SupportRequest).order_by(SupportRequest.updated_at.desc()).limit(100)).all()
    return [_read(row, db) for row in rows]


@router.get("/requests/{request_id}/messages", response_model=list[SupportMessageRead])
def own_messages(request_id: str, response: Response, db: Session = Depends(get_db)) -> list[SupportMessageRead]:
    response.headers["Cache-Control"] = "private, no-store"
    return _messages(_own_request(request_id, db), db)


@router.post("/requests/{request_id}/messages", response_model=SupportMessageRead, status_code=201)
def create_own_message(
    request_id: str,
    payload: SupportMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> SupportMessageRead:
    user = request.state.user
    if user["role"] not in ("owner", "manager"):
        raise HTTPException(403, "נדרשת הרשאת בעלים או מנהל")
    _messages_by_user.check(f"support-message:{user['id']}")
    return _add_message(_own_request(request_id, db), payload, user["id"], "customer", db)


@router.get("/staff/requests", response_model=list[SupportRequestRead])
def staff_requests(request: Request, response: Response, db: Session = Depends(get_support_db)) -> list[SupportRequestRead]:
    response.headers["Cache-Control"] = "private, no-store"
    _require_support(request, db)
    rows = db.scalars(select(SupportRequest).order_by(SupportRequest.updated_at.desc()).limit(500)).all()
    return [_read(row, db, staff=True) for row in rows]


@router.get("/staff/requests/{request_id}/messages", response_model=list[SupportMessageRead])
def staff_messages(
    request_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_support_db),
) -> list[SupportMessageRead]:
    response.headers["Cache-Control"] = "private, no-store"
    _require_support(request, db)
    row = db.get(SupportRequest, request_id)
    if row is None:
        raise HTTPException(404, "הפנייה לא נמצאה")
    return _messages(row, db)


@router.post("/staff/requests/{request_id}/messages", response_model=SupportMessageRead, status_code=201)
def create_staff_message(
    request_id: str,
    payload: SupportMessageCreate,
    request: Request,
    db: Session = Depends(get_support_db),
) -> SupportMessageRead:
    account = _require_support(request, db)
    _messages_by_user.check(f"support-message:{account.user_id}")
    row = db.get(SupportRequest, request_id)
    if row is None:
        raise HTTPException(404, "הפנייה לא נמצאה")
    return _add_message(row, payload, account.user_id, "staff", db)


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
