from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.business import Business, BusinessMember
from app.api.routes.auth import current_user

router = APIRouter(prefix="/businesses", tags=["businesses"])

class CreateBusiness(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    country_code: Literal["IL"] = "IL"
    currency: Literal["ILS"] = "ILS"
    timezone: Literal["Asia/Jerusalem"] = "Asia/Jerusalem"
    business_number: str | None = Field(default=None, max_length=30)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("יש להזין שם עסק")
        return value.strip()

@router.post("", status_code=201)
async def create_business(payload: CreateBusiness, request: Request):
    user = await current_user(request)
    if not user["email_verified"]:
        raise HTTPException(403, "יש לאמת את האימייל לפני יצירת עסק")
    with SessionLocal() as db:
        if db.scalar(select(BusinessMember).where(BusinessMember.user_id == user["id"])):
            raise HTTPException(409, "כבר קיים עסק לחשבון")
        business = Business(**payload.model_dump())
        db.add(business)
        db.flush()
        db.add(BusinessMember(business_id=business.id, user_id=user["id"], role="owner"))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "כבר קיים עסק לחשבון")
        return {"id": business.id, "name": business.name}

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
