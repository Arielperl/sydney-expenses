from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.database import get_db
from app.models.sale import Sale, SaleSource, SaleStatus
from app.models.sale_event import SaleEvent, SaleEventSource, SaleEventType
from app.repositories.sale_repository import SaleRepository
from app.schemas.sale import RefundRequest, SaleCreate, SaleRead, SaleUpdate, sale_to_read
from app.schemas.sale_event import SaleEventRead
from app.services.sale_events import record_event
from app.services.sale_service import RefundExceedsNetAmountError, compute_net_amount, finalize_new_sale, record_refund
from app.services.tax.vat import calculate_vat, vat_rate_snapshot

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("", response_model=list[SaleRead])
def list_sales(
    search: str | None = Query(default=None),
    status: SaleStatus | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[SaleRead]:
    repository = SaleRepository(db)
    sales = repository.list(search=search, status=status, date_from=date_from, date_to=date_to)
    return [sale_to_read(s) for s in sales]


@router.get("/{sale_id}", response_model=SaleRead)
def get_sale(
    sale_id: str,
    db: Session = Depends(get_db),
) -> SaleRead:
    repository = SaleRepository(db)
    sale = repository.get(sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale_to_read(sale)


@router.post("", response_model=SaleRead, status_code=201)
def create_sale(
    payload: SaleCreate,
    db: Session = Depends(get_db),
) -> SaleRead:
    # The backend is authoritative for vat_amount: it is always computed
    # here from gross_amount + tax_treatment, never accepted from the
    # client (see SaleCreate — there is no vat_amount input field at all).
    vat_amount = calculate_vat(payload.gross_amount, payload.tax_treatment)
    net_amount = compute_net_amount(payload.gross_amount, vat_amount, payload.processing_fee)
    sale = Sale(
        **payload.model_dump(),
        vat_amount=vat_amount,
        vat_rate=vat_rate_snapshot(payload.tax_treatment),
        net_amount=net_amount,
        source=SaleSource.MANUAL,
        status=SaleStatus.SUCCEEDED,
    )
    created = finalize_new_sale(db, sale)
    return sale_to_read(created)


@router.put("/{sale_id}", response_model=SaleRead)
def update_sale(
    sale_id: str,
    payload: SaleUpdate,
    db: Session = Depends(get_db),
) -> SaleRead:
    repository = SaleRepository(db)
    sale = repository.get(sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    updates = payload.model_dump(exclude_unset=True)
    # vat_amount is recalculated (never accepted from the client — see
    # SaleUpdate) whenever the amount or the tax treatment changes, so it
    # can never drift out of sync with either.
    if any(field in updates for field in ("gross_amount", "tax_treatment", "processing_fee")):
        gross = updates.get("gross_amount", sale.gross_amount)
        tax_treatment = updates.get("tax_treatment", sale.tax_treatment)
        if tax_treatment is None:
            # A legacy sale whose tax treatment a data migration couldn't
            # safely infer (see the migration's docstring) — recomputing
            # VAT under an assumed treatment would be exactly the kind of
            # invented value that migration deliberately avoided.
            raise HTTPException(
                status_code=422,
                detail="This sale's tax treatment needs review — set tax_treatment explicitly before changing its amount.",
            )
        fee = updates.get("processing_fee", sale.processing_fee)
        vat = calculate_vat(gross, tax_treatment)
        updates["vat_amount"] = vat
        updates["vat_rate"] = vat_rate_snapshot(tax_treatment)
        updates["net_amount"] = compute_net_amount(gross, vat, fee)
        # A sale this update resolves the tax treatment for (or whose
        # amount changes while a treatment is already known) is no longer
        # ambiguous — clear any "needs review" flag a legacy-data migration
        # may have set.
        updates["tax_treatment_needs_review"] = False
    if updates:
        # Field names only — never the values themselves, which may include
        # customer contact details that shouldn't be duplicated into a log.
        record_event(
            db, sale.id, SaleEventType.SALE_DETAILS_EDITED, SaleEventSource.MANUAL,
            {"fields": sorted(updates.keys())},
        )
    updated = repository.update(sale, updates)
    return sale_to_read(updated)


@router.delete("/{sale_id}", status_code=204)
def delete_sale(
    sale_id: str,
    db: Session = Depends(get_db),
) -> None:
    repository = SaleRepository(db)
    sale = repository.get(sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    repository.delete(sale)


@router.get("/{sale_id}/events", response_model=list[SaleEventRead])
def list_sale_events(
    sale_id: str,
    db: Session = Depends(get_db),
) -> list[SaleEventRead]:
    """The sale's persisted timeline, oldest first. A sale created before
    events existed (or one whose creation predates this feature) may
    legitimately have none or only some events — the frontend must show
    that as "no earlier history available", never invent one."""
    repository = SaleRepository(db)
    sale = repository.get(sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    events = db.scalars(
        select(SaleEvent).where(SaleEvent.sale_id == sale_id).order_by(SaleEvent.created_at.asc())
    ).all()
    return [SaleEventRead.model_validate(e) for e in events]


@router.post("/{sale_id}/refund", response_model=SaleRead)
def refund_sale(
    sale_id: str,
    payload: RefundRequest,
    db: Session = Depends(get_db),
) -> SaleRead:
    repository = SaleRepository(db)
    sale = repository.get(sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    try:
        refunded = record_refund(db, sale, payload.amount)
    except RefundExceedsNetAmountError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return sale_to_read(refunded)
