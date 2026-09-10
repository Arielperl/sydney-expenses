from datetime import date
from decimal import Decimal

from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExtractionStatus
from app.services.assistant.tools import (
    get_category_breakdown,
    get_expense_trend,
    get_match_rate,
    get_missing_documents_summary,
    get_pending_suggestions_summary,
    get_top_merchants,
    get_total_expenses,
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


# --- get_total_expenses -------------------------------------------------


def test_get_total_expenses_empty_db(db_session):
    result = get_total_expenses(db_session)
    assert result == {"total": "0.00", "count": 0}


def test_get_total_expenses_sums_all_by_default(db_session):
    _add_expense(db_session, amount=Decimal("100.00"))
    _add_expense(db_session, amount=Decimal("50.50"))
    result = get_total_expenses(db_session)
    assert result == {"total": "150.50", "count": 2}


def test_get_total_expenses_filters_by_date_range(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 3, 10))
    _add_expense(db_session, amount=Decimal("50.00"), expense_date=date(2026, 4, 1))
    result = get_total_expenses(db_session, start_date="2026-03-01", end_date="2026-03-31")
    assert result == {"total": "100.00", "count": 1}


def test_get_total_expenses_filters_by_category(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), category=ExpenseCategory.GROCERIES)
    _add_expense(db_session, amount=Decimal("40.00"), category=ExpenseCategory.DINING)
    result = get_total_expenses(db_session, category="dining")
    assert result == {"total": "40.00", "count": 1}


def test_get_total_expenses_invalid_category_returns_error_not_raise(db_session):
    result = get_total_expenses(db_session, category="not-a-real-category")
    assert "error" in result


def test_get_total_expenses_invalid_date_returns_error_not_raise(db_session):
    result = get_total_expenses(db_session, start_date="not-a-date")
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


# --- get_expense_trend -----------------------------------------------------


def test_get_expense_trend_groups_by_month(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 3, 5))
    _add_expense(db_session, amount=Decimal("20.00"), expense_date=date(2026, 3, 20))
    _add_expense(db_session, amount=Decimal("40.00"), expense_date=date(2026, 4, 1))
    result = get_expense_trend(db_session, period="month")
    assert result["trend"] == [
        {"period_start": "2026-03-01", "total": "120.00", "count": 2},
        {"period_start": "2026-04-01", "total": "40.00", "count": 1},
    ]


def test_get_expense_trend_invalid_period_returns_error(db_session):
    result = get_expense_trend(db_session, period="year")
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


# --- get_missing_documents_summary -----------------------------------------


def test_get_missing_documents_summary_counts_and_sums(db_session):
    _add_expense(db_session, amount=Decimal("50.00"), document_status=DocumentStatus.MISSING)
    _add_expense(db_session, amount=Decimal("30.00"), document_status=DocumentStatus.MISSING)
    _add_expense(db_session, amount=Decimal("10.00"), document_status=DocumentStatus.ATTACHED)

    result = get_missing_documents_summary(db_session)

    assert result == {"count": 2, "total": "80.00"}


def test_get_missing_documents_summary_empty(db_session):
    result = get_missing_documents_summary(db_session)
    assert result == {"count": 0, "total": "0.00"}


# --- get_match_rate ---------------------------------------------------------


def test_get_match_rate_computes_percentage(db_session):
    _add_expense(db_session, document_status=DocumentStatus.ATTACHED)
    _add_expense(db_session, document_status=DocumentStatus.ATTACHED)
    _add_expense(db_session, document_status=DocumentStatus.ATTACHED)
    _add_expense(db_session, document_status=DocumentStatus.MISSING)

    result = get_match_rate(db_session)

    assert result["attached"] == 3
    assert result["missing"] == 1
    assert result["suggested"] == 0
    assert result["rate"] == "75.00"


def test_get_match_rate_empty_db_has_no_rate(db_session):
    result = get_match_rate(db_session)
    assert result["rate"] is None


# --- get_pending_suggestions_summary ----------------------------------------


def test_get_pending_suggestions_summary_counts_suggested_and_needs_review(db_session):
    _add_expense(db_session, document_status=DocumentStatus.SUGGESTED)
    _add_expense(db_session, document_status=DocumentStatus.NEEDS_REVIEW)
    _add_expense(db_session, document_status=DocumentStatus.MISSING)

    result = get_pending_suggestions_summary(db_session)

    assert result == {"count": 2}
