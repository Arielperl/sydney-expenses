from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.assistant_conversation import AssistantConversation, AssistantMessage
from app.models.business import AppAccount, Business, BusinessMember, BusinessPaymentProvider
from app.models.cardcom_credential import CardcomCredential
from app.models.import_batch import ImportBatch
from app.models.integration_connection import IntegrationConnection
from app.models.provider_document_event import ProviderDocumentEvent
from app.models.sale import Sale
from app.models.sale_event import SaleEvent
from app.models.webhook_event import WebhookEvent

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request, db: Session) -> AppAccount:
    user = getattr(request.state, "user", None) or {}
    account = db.get(AppAccount, user.get("id")) if user.get("id") else None
    if account is None or account.system_role != "admin":
        raise HTTPException(status_code=403, detail="נדרשת הרשאת מנהל מערכת")
    # Only after the DB role has been verified may this request leave the
    # normal tenant scope and inspect/manage other businesses.
    db.info.pop("business_id", None)
    return account


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


class DeleteBusinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_name: str


@router.get("/businesses", response_model=list[AdminBusinessRead])
def list_businesses(request: Request, db: Session = Depends(get_db)) -> list[AdminBusinessRead]:
    _require_admin(request, db)
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
    db: Session = Depends(get_db),
) -> dict:
    admin = _require_admin(request, db)
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


@router.delete("/businesses/{business_id}", status_code=204)
def delete_business(
    business_id: str,
    payload: DeleteBusinessRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    _require_admin(request, db)
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="העסק לא נמצא")
    if business_id == request.state.user.get("business_id"):
        raise HTTPException(status_code=409, detail="לא ניתן למחוק את העסק הפעיל של חשבון המנהל")
    if payload.confirm_name.strip() != business.name:
        raise HTTPException(status_code=422, detail="שם העסק לאימות אינו תואם")

    # Explicit ordering keeps deletion correct in SQLite tests as well as in
    # PostgreSQL, even where a legacy foreign key lacks ON DELETE CASCADE.
    for model in (
        AssistantMessage,
        SaleEvent,
        WebhookEvent,
        ProviderDocumentEvent,
        CardcomCredential,
        AssistantConversation,
        Sale,
        ImportBatch,
        IntegrationConnection,
        BusinessPaymentProvider,
        BusinessMember,
    ):
        db.execute(delete(model).where(model.business_id == business_id))
    db.delete(business)
    db.commit()
