from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sale import Sale, SaleSource, SaleStatus
from app.repositories.sale_repository import SaleRepository
from app.schemas.sale import RefundRequest, SaleCreate, SaleRead, SaleUpdate, sale_to_read
from app.services.sale_service import RefundExceedsNetAmountError, compute_net_amount, finalize_new_sale, record_refund

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
    net_amount = compute_net_amount(payload.gross_amount, payload.vat_amount, payload.processing_fee)
    sale = Sale(
        **payload.model_dump(),
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
    if any(field in updates for field in ("gross_amount", "vat_amount", "processing_fee")):
        gross = updates.get("gross_amount", sale.gross_amount)
        vat = updates.get("vat_amount", sale.vat_amount)
        fee = updates.get("processing_fee", sale.processing_fee)
        updates["net_amount"] = compute_net_amount(gross, vat, fee)
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
