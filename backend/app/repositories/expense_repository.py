from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseCategory


class ExpenseRepository:
    def __init__(self, db: Session):
        self._db = db

    def create(self, expense: Expense) -> Expense:
        self._db.add(expense)
        self._db.commit()
        self._db.refresh(expense)
        return expense

    def get(self, expense_id: str) -> Expense | None:
        return self._db.get(Expense, expense_id)

    def list(
        self,
        *,
        search: str | None = None,
        category: ExpenseCategory | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Expense]:
        stmt = select(Expense)
        if search:
            like_pattern = f"%{search.strip()}%"
            stmt = stmt.where(Expense.business_name.ilike(like_pattern))
        if category:
            stmt = stmt.where(Expense.category == category)
        if date_from:
            stmt = stmt.where(Expense.expense_date >= date_from)
        if date_to:
            stmt = stmt.where(Expense.expense_date <= date_to)
        stmt = stmt.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        return list(self._db.scalars(stmt).all())

    def update(self, expense: Expense, updates: dict) -> Expense:
        for field, value in updates.items():
            setattr(expense, field, value)
        self._db.commit()
        self._db.refresh(expense)
        return expense

    def delete(self, expense: Expense) -> None:
        self._db.delete(expense)
        self._db.commit()
