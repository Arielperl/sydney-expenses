from datetime import date
from decimal import Decimal

from app.models.expense import Expense, ExpenseCategory, ExtractionStatus
from app.services.assistant.tools import (
    get_category_breakdown,
    get_revenue_trend,
    get_top_merchants,
    get_total_revenue,
    list_recent_expenses,
)


def _add_expense(db_session, **overrides):
    defaults = dict(
        business_name="Shufersal",
        amount=Decimal("100.00"),
        currency="ILS",
        category=ExpenseCategory.GROCERIES,
        expense_date=date(2026, 3, 15),
        extraction_status=ExtractionStatus.MANUAL,
    )
    defaults.update(overrides)
    expense = Expense(**defaults)
    db_session.add(expense)
    db_session.commit()
    return expense


# --- get_total_revenue -------------------------------------------------


def test_get_total_revenue_empty_db(db_session):
    result = get_total_revenue(db_session)
    assert result == {"total": "0.00", "count": 0}


def test_get_total_revenue_sums_all_by_default(db_session):
    _add_expense(db_session, amount=Decimal("100.00"))
    _add_expense(db_session, amount=Decimal("50.50"))
    result = get_total_revenue(db_session)
    assert result == {"total": "150.50", "count": 2}


def test_get_total_revenue_filters_by_date_range(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 3, 10))
    _add_expense(db_session, amount=Decimal("50.00"), expense_date=date(2026, 4, 1))
    result = get_total_revenue(db_session, start_date="2026-03-01", end_date="2026-03-31")
    assert result == {"total": "100.00", "count": 1}


def test_get_total_revenue_filters_by_category(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), category=ExpenseCategory.GROCERIES)
    _add_expense(db_session, amount=Decimal("40.00"), category=ExpenseCategory.DINING)
    result = get_total_revenue(db_session, category="dining")
    assert result == {"total": "40.00", "count": 1}


def test_get_total_revenue_invalid_category_returns_error_not_raise(db_session):
    result = get_total_revenue(db_session, category="not-a-real-category")
    assert "error" in result


def test_get_total_revenue_invalid_date_returns_error_not_raise(db_session):
    result = get_total_revenue(db_session, start_date="not-a-date")
    assert "error" in result


# --- get_category_breakdown ---------------------------------------------


def test_get_category_breakdown_sorted_descending(db_session):
    _add_expense(db_session, amount=Decimal("50.00"), category=ExpenseCategory.DINING)
    _add_expense(db_session, amount=Decimal("100.00"), category=ExpenseCategory.GROCERIES)
    _add_expense(db_session, amount=Decimal("30.00"), category=ExpenseCategory.GROCERIES)
    result = get_category_breakdown(db_session)
    assert result["categories"] == [
        {"category": "groceries", "total": "130.00", "count": 2},
        {"category": "dining", "total": "50.00", "count": 1},
    ]


# --- get_top_merchants ---------------------------------------------------


def test_get_top_merchants_sorted_and_limited(db_session):
    _add_expense(db_session, business_name="A", amount=Decimal("10.00"))
    _add_expense(db_session, business_name="B", amount=Decimal("100.00"))
    _add_expense(db_session, business_name="B", amount=Decimal("50.00"))
    result = get_top_merchants(db_session, limit=1)
    assert result == {"merchants": [{"business_name": "B", "total": "150.00", "count": 2}]}


# --- get_revenue_trend -----------------------------------------------------


def test_get_revenue_trend_groups_by_month(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 3, 5))
    _add_expense(db_session, amount=Decimal("20.00"), expense_date=date(2026, 3, 20))
    _add_expense(db_session, amount=Decimal("40.00"), expense_date=date(2026, 4, 1))
    result = get_revenue_trend(db_session, period="month")
    assert result["trend"] == [
        {"period_start": "2026-03-01", "total": "120.00", "count": 2},
        {"period_start": "2026-04-01", "total": "40.00", "count": 1},
    ]


def test_get_revenue_trend_invalid_period_returns_error(db_session):
    result = get_revenue_trend(db_session, period="year")
    assert "error" in result


# --- list_recent_expenses -------------------------------------------------


def test_list_recent_expenses_orders_newest_first(db_session):
    _add_expense(db_session, business_name="Old", expense_date=date(2026, 1, 1))
    _add_expense(db_session, business_name="New", expense_date=date(2026, 3, 1))
    result = list_recent_expenses(db_session, limit=10)
    assert [e["business_name"] for e in result["expenses"]] == ["New", "Old"]


def test_list_recent_expenses_filters_by_category(db_session):
    _add_expense(db_session, business_name="Groc", category=ExpenseCategory.GROCERIES)
    _add_expense(db_session, business_name="Din", category=ExpenseCategory.DINING)
    result = list_recent_expenses(db_session, category="dining")
    assert [e["business_name"] for e in result["expenses"]] == ["Din"]
