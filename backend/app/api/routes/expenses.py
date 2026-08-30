from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_settings_dep, resolve_receipt_image_url
from app.core.config import Settings
from app.database import get_db
from app.models.expense import Expense, ExpenseCategory, ExtractionStatus
from app.repositories.expense_repository import ExpenseRepository
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate, expense_to_read
from app.services.receipt_lifecycle_service import delete_expense_and_cleanup_receipt

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseRead])
def list_expenses(
    search: str | None = Query(default=None),
    category: ExpenseCategory | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ExpenseRead]:
    repository = ExpenseRepository(db)
    expenses = repository.list(search=search, category=category, date_from=date_from, date_to=date_to)
    return [
        expense_to_read(e, resolve_receipt_image_url(e.storage_provider, e.receipt_image_path)) for e in expenses
    ]


@router.get("/{expense_id}", response_model=ExpenseRead)
def get_expense(
    expense_id: str,
    db: Session = Depends(get_db),
) -> ExpenseRead:
    repository = ExpenseRepository(db)
    expense = repository.get(expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    image_url = resolve_receipt_image_url(expense.storage_provider, expense.receipt_image_path)
    return expense_to_read(expense, image_url)


@router.post("", response_model=ExpenseRead, status_code=201)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
) -> ExpenseRead:
    repository = ExpenseRepository(db)
    expense = Expense(**payload.model_dump(), extraction_status=ExtractionStatus.MANUAL)
    created = repository.create(expense)
    image_url = resolve_receipt_image_url(created.storage_provider, created.receipt_image_path)
    return expense_to_read(created, image_url)


@router.put("/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: str,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
) -> ExpenseRead:
    repository = ExpenseRepository(db)
    expense = repository.get(expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    updates = payload.model_dump(exclude_unset=True)
    updated = repository.update(expense, updates)
    image_url = resolve_receipt_image_url(updated.storage_provider, updated.receipt_image_path)
    return expense_to_read(updated, image_url)


@router.delete("/{expense_id}", status_code=204)
def delete_expense(
    expense_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    repository = ExpenseRepository(db)
    expense = repository.get(expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    delete_expense_and_cleanup_receipt(db, settings, expense)
