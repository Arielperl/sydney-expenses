from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.business import Business, BusinessMember, BusinessPaymentProvider
from app.api.routes.auth import current_user

router = APIRouter(prefix="/businesses", tags=["businesses"])

class CreateBusiness(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    country_code: Literal["IL"] = "IL"
    currency: Literal["ILS"] = "ILS"
    timezone: Literal["Asia/Jerusalem"] = "Asia/Jerusalem"
    business_number: str | None = Field(default=None, max_length=30)
    payment_providers: list[Literal["grow", "cardcom"]] = Field(default_factory=list, max_length=2)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("יש להזין שם עסק")
        return value.strip()

    @field_validator("payment_providers")
    @classmethod
    def unique_providers(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("אין לבחור את אותה חברת סליקה יותר מפעם אחת")
        return value

@router.post("", status_code=201)
async def create_business(payload: CreateBusiness, request: Request):
    user = await current_user(request)
    if not user["email_verified"]:
        raise HTTPException(403, "יש לאמת את האימייל לפני יצירת עסק")
    with SessionLocal() as db:
        if db.scalar(select(BusinessMember).where(BusinessMember.user_id == user["id"])):
            raise HTTPException(409, "כבר קיים עסק לחשבון")
        business_data = payload.model_dump(exclude={"payment_providers"})
        business = Business(**business_data)
        db.add(business)
        db.flush()
        db.add(BusinessMember(business_id=business.id, user_id=user["id"], role="owner"))
        db.add_all([
            BusinessPaymentProvider(business_id=business.id, provider=provider, added_by_user_id=user["id"])
            for provider in payload.payment_providers
        ])
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "כבר קיים עסק לחשבון")
        return {"id": business.id, "name": business.name}


@router.get("/current/payment-providers")
async def get_payment_providers(request: Request):
    user = await current_user(request)
    if not user["has_workspace"]:
        raise HTTPException(404, "לא נמצא עסק")
    with SessionLocal() as db:
        providers = db.scalars(
            select(BusinessPaymentProvider.provider)
            .where(BusinessPaymentProvider.business_id == user["business_id"])
            .order_by(BusinessPaymentProvider.provider)
        ).all()
        return {"providers": list(providers)}

@router.get("/current")
async def get_business(request: Request):
    user = await current_user(request)
    if not user["has_workspace"]:
        raise HTTPException(404, "לא נמצא עסק")
    with SessionLocal() as db:
        b = db.get(Business, user["business_id"])
        return {"id": b.id, "name": b.name, "country_code": b.country_code,
                "currency": b.currency, "timezone": b.timezone,
                "business_number": b.business_number, "vat_rate": str(b.vat_rate), "role": user["role"]}
