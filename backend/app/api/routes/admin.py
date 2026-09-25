from datetime import datetime
from typing import Literal

import httpx
from collections.abc import Generator
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.business import AppAccount, Business, BusinessMember, BusinessPaymentProvider
from app.models.integration_connection import IntegrationConnection
from app.models.sale import Sale
from app.core.config import get_settings
from app.core.staff_identity import is_regular_email, is_staff_login, staff_auth_email

router = APIRouter(prefix="/support/staff", tags=["support-staff"])


def get_support_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def _require_support(request: Request, db: Session) -> AppAccount:
    user = getattr(request.state, "user", None) or {}
    account = db.get(AppAccount, user.get("id")) if user.get("id") else None
    if account is None or account.system_role not in ("support", "admin", "superadmin") or account.disabled_at is not None:
        raise HTTPException(status_code=403, detail="נדרשת הרשאת תמיכה")
    return account


def _require_superadmin(request: Request, db: Session) -> AppAccount:
    account = _require_support(request, db)
    if account.system_role != "superadmin":
        raise HTTPException(status_code=403, detail="נדרשת הרשאת סופר אדמין")
    return account


async def delete_auth_identity(user_id: str) -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise HTTPException(503, "שירות ההתחברות אינו מוגדר")
    url = settings.supabase_url.rstrip("/") + f"/auth/v1/admin/users/{user_id}"
    headers = {"apikey": settings.supabase_secret_key, "Authorization": f"Bearer {settings.supabase_secret_key}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.delete(url, headers=headers)
    except httpx.RequestError:
        raise HTTPException(503, "מחיקת החשבון נכשלה בשירות ההתחברות")
    if response.status_code not in (200, 204):
        raise HTTPException(503, "מחיקת החשבון נכשלה בשירות ההתחברות")


async def create_auth_identity(email: str, password: str, name: str) -> dict:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise HTTPException(503, "שירות ההתחברות אינו מוגדר")
    url = settings.supabase_url.rstrip("/") + "/auth/v1/admin/users"
    headers = {"apikey": settings.supabase_secret_key, "Authorization": f"Bearer {settings.supabase_secret_key}"}
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": name},
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError:
        raise HTTPException(503, "יצירת החשבון נכשלה בשירות ההתחברות")
    if response.status_code >= 400:
        detail = "כתובת האימייל כבר קיימת" if response.status_code in (400, 422) else "יצירת החשבון נכשלה בשירות ההתחברות"
        raise HTTPException(409 if response.status_code in (400, 422) else 503, detail)
    return response.json()


class StaffUserRead(BaseModel):
    id: str
    email: str
    name: str
    system_role: str
    business_name: str | None


class StaffUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(default="", max_length=100)
    system_role: Literal["user", "support", "admin"]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_login(self):
        if is_staff_login(self.email):
            if self.system_role not in ("support", "admin"):
                raise ValueError("שם התחברות שמסתיים ב־@support מיועד לחשבון תמיכה או אדמין")
            return self
        if not is_regular_email(self.email):
            raise ValueError("הזינו שם התחברות כמו liad@support או כתובת אימייל תקינה")
        return self


class StaffRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system_role: Literal["user", "support", "admin"]


@router.get("/users", response_model=list[StaffUserRead])
def list_users(request: Request, db: Session = Depends(get_support_db)) -> list[StaffUserRead]:
    _require_superadmin(request, db)
    rows = db.scalars(select(AppAccount).where(AppAccount.disabled_at.is_(None)).order_by(AppAccount.created_at.desc())).all()
    result = []
    for account in rows:
        member = db.scalar(select(BusinessMember).where(BusinessMember.user_id == account.user_id))
        business = db.get(Business, member.business_id) if member else None
        result.append(StaffUserRead(id=account.user_id, email=account.email, name=account.display_name,
                                    system_role=account.system_role, business_name=business.name if business else None))
    return result


@router.post("/users", response_model=StaffUserRead, status_code=201)
async def create_user(payload: StaffUserCreate, request: Request, db: Session = Depends(get_support_db)) -> StaffUserRead:
    _require_superadmin(request, db)
    if db.scalar(select(AppAccount).where(func.lower(AppAccount.email) == payload.email)) is not None:
        raise HTTPException(409, "כתובת האימייל כבר קיימת")
    auth_email = staff_auth_email(payload.email) if is_staff_login(payload.email) else payload.email
    identity = await create_auth_identity(auth_email, payload.password, payload.name.strip())
    user_id = identity.get("id")
    if not user_id:
        raise HTTPException(503, "שירות ההתחברות החזיר תשובה לא תקינה")
    account = AppAccount(
        user_id=user_id,
        email=payload.email,
        display_name=payload.name.strip(),
        system_role=payload.system_role,
    )
    try:
        db.add(account)
        db.commit()
    except Exception:
        db.rollback()
        await delete_auth_identity(user_id)
        raise
    return StaffUserRead(
        id=account.user_id,
        email=account.email,
        name=account.display_name,
        system_role=account.system_role,
        business_name=None,
    )


@router.patch("/users/{user_id}/role", response_model=StaffUserRead)
def update_user_role(
    user_id: str,
    payload: StaffRoleUpdate,
    request: Request,
    db: Session = Depends(get_support_db),
) -> StaffUserRead:
    actor = _require_superadmin(request, db)
    target = db.get(AppAccount, user_id)
    if target is None or target.disabled_at is not None:
        raise HTTPException(404, "המשתמש לא נמצא")
    if target.user_id == actor.user_id or target.system_role == "superadmin":
        raise HTTPException(403, "לא ניתן לשנות את תפקיד הסופר אדמין")
    target.system_role = payload.system_role
    db.commit()
    member = db.scalar(select(BusinessMember).where(BusinessMember.user_id == target.user_id))
    business = db.get(Business, member.business_id) if member else None
    return StaffUserRead(
        id=target.user_id,
        email=target.email,
        name=target.display_name,
        system_role=target.system_role,
        business_name=business.name if business else None,
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, request: Request, db: Session = Depends(get_support_db)) -> None:
    admin = _require_superadmin(request, db)
    if user_id == admin.user_id:
        raise HTTPException(409, "לא ניתן למחוק את החשבון של עצמך")
    target = db.get(AppAccount, user_id)
    if target is None or target.disabled_at is not None:
        raise HTTPException(404, "המשתמש לא נמצא")
    if target.system_role == "superadmin":
        raise HTTPException(403, "לא ניתן למחוק סופר אדמין")
    member = db.scalar(select(BusinessMember).where(BusinessMember.user_id == user_id))
    if member and member.role == "owner":
        owners = db.scalar(select(func.count()).select_from(BusinessMember).where(
            BusinessMember.business_id == member.business_id, BusinessMember.role == "owner")) or 0
        if owners <= 1:
            raise HTTPException(409, "יש להעביר בעלות על העסק לפני מחיקת בעליו היחיד")
    await delete_auth_identity(user_id)
    if member:
        db.delete(member)
    target.email = f"deleted-{target.user_id}@invalid.local"
    target.display_name = ""
    target.system_role = "user"
    target.disabled_at = datetime.utcnow()
    db.commit()


class AdminBusinessRead(BaseModel):
    id: str
    name: str
    business_number: str | None
    created_at: datetime
    owner_emails: list[str]
    payment_providers: list[str]
    member_count: int
    sale_count: int
    connection_count: int


@router.get("/businesses", response_model=list[AdminBusinessRead])
def list_businesses(request: Request, db: Session = Depends(get_support_db)) -> list[AdminBusinessRead]:
    _require_support(request, db)
    businesses = db.scalars(select(Business).order_by(Business.created_at.desc())).all()
    result: list[AdminBusinessRead] = []
    for business in businesses:
        member_rows = db.execute(
            select(BusinessMember.user_id, BusinessMember.role).where(BusinessMember.business_id == business.id)
        ).all()
        owner_ids = [user_id for user_id, role in member_rows if role == "owner"]
        owner_emails = list(
            db.scalars(select(AppAccount.email).where(AppAccount.user_id.in_(owner_ids))).all()
        ) if owner_ids else []
        providers = list(
            db.scalars(
                select(BusinessPaymentProvider.provider)
                .where(BusinessPaymentProvider.business_id == business.id)
                .order_by(BusinessPaymentProvider.provider)
            ).all()
        )
        result.append(AdminBusinessRead(
            id=business.id,
            name=business.name,
            business_number=business.business_number,
            created_at=business.created_at,
            owner_emails=owner_emails,
            payment_providers=providers,
            member_count=len(member_rows),
            sale_count=db.scalar(select(func.count()).select_from(Sale).where(Sale.business_id == business.id)) or 0,
            connection_count=db.scalar(
                select(func.count()).select_from(IntegrationConnection).where(IntegrationConnection.business_id == business.id)
            ) or 0,
        ))
    return result


@router.post("/businesses/{business_id}/payment-providers/{provider}", status_code=201)
def add_payment_provider(
    business_id: str,
    provider: Literal["grow", "cardcom"],
    request: Request,
    db: Session = Depends(get_support_db),
) -> dict:
    admin = _require_support(request, db)
    if db.get(Business, business_id) is None:
        raise HTTPException(status_code=404, detail="העסק לא נמצא")
    existing = db.get(BusinessPaymentProvider, (business_id, provider))
    if existing is not None:
        return {"provider": provider, "created": False}
    db.add(BusinessPaymentProvider(
        business_id=business_id,
        provider=provider,
        added_by_user_id=admin.user_id,
    ))
    db.commit()
    return {"provider": provider, "created": True}


@router.delete("/businesses/{business_id}/payment-providers/{provider}")
def remove_payment_provider(
    business_id: str,
    provider: Literal["grow", "cardcom"],
    request: Request,
    db: Session = Depends(get_support_db),
) -> dict:
    _require_support(request, db)
    if db.get(Business, business_id) is None:
        raise HTTPException(status_code=404, detail="העסק לא נמצא")
    approved_provider = db.get(BusinessPaymentProvider, (business_id, provider))
    if approved_provider is None:
        return {"provider": provider, "removed": False, "disabled_connections": 0}

    connections = db.scalars(
        select(IntegrationConnection).where(
            IntegrationConnection.business_id == business_id,
            IntegrationConnection.provider == provider,
        )
    ).all()
    disabled_connections = 0
    for connection in connections:
        if connection.enabled:
            connection.enabled = False
            disabled_connections += 1

    db.delete(approved_provider)
    db.commit()
    return {
        "provider": provider,
        "removed": True,
        "disabled_connections": disabled_connections,
    }
