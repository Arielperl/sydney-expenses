from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.schemas.dashboard import CategoryTotal, DashboardStats
from app.schemas.expense import expense_to_read
from app.services.upload_service import UploadService

TWO_PLACES = Decimal("0.01")


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _amounts_between(db: Session, start: date, end: date) -> list[Decimal]:
    stmt = select(Expense.amount).where(Expense.expense_date >= start, Expense.expense_date <= end)
    return list(db.scalars(stmt).all())


def _sum_decimal(values: list[Decimal]) -> Decimal:
    return _round_money(sum(values, Decimal("0")))


def build_dashboard_stats(db: Session, upload_service: UploadService, today: date | None = None) -> DashboardStats:
    today = today or date.today()
    current_start, current_end = _month_bounds(today.year, today.month)
    prev_year, prev_month = _previous_month(today.year, today.month)
    prev_start, prev_end = _month_bounds(prev_year, prev_month)

    current_total = _sum_decimal(_amounts_between(db, current_start, current_end))
    previous_total = _sum_decimal(_amounts_between(db, prev_start, prev_end))

    if previous_total > 0:
        ratio = (current_total - previous_total) / previous_total * Decimal(100)
        percentage_change = float(ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    elif current_total > 0:
        percentage_change = 100.0
    else:
        percentage_change = None

    category_rows = db.execute(
        select(Expense.category, Expense.amount).where(
            Expense.expense_date >= current_start, Expense.expense_date <= current_end
        )
    ).all()
    totals_by_category_map: dict[str, Decimal] = {}
    for category, amount in category_rows:
        totals_by_category_map[category.value] = totals_by_category_map.get(category.value, Decimal("0")) + amount
    totals_by_category = [
        CategoryTotal(category=category, total=_round_money(total))
        for category, total in totals_by_category_map.items()
    ]
    totals_by_category.sort(key=lambda item: item.total, reverse=True)

    recent = db.scalars(
        select(Expense).order_by(Expense.expense_date.desc(), Expense.created_at.desc()).limit(5)
    ).all()
    recent_expenses = [
        expense_to_read(expense, upload_service.image_url(expense.receipt_image_path)) for expense in recent
    ]

    return DashboardStats(
        current_month_total=current_total,
        previous_month_total=previous_total,
        percentage_change=percentage_change,
        totals_by_category=totals_by_category,
        recent_expenses=recent_expenses,
    )
