from decimal import Decimal

from pydantic import BaseModel

from app.schemas.expense import ExpenseRead


class CategoryTotal(BaseModel):
    category: str
    total: Decimal


class DashboardStats(BaseModel):
    current_month_total: Decimal
    previous_month_total: Decimal
    percentage_change: float | None
    totals_by_category: list[CategoryTotal]
    recent_expenses: list[ExpenseRead]
