from datetime import date
from decimal import Decimal

from app.core.config import get_settings
from app.models.expense import Expense, ExpenseCategory, ExtractionStatus
from app.services.dashboard_service import build_dashboard_stats
from app.services.upload_service import UploadService


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


def test_dashboard_empty_state(db_session):
    stats = build_dashboard_stats(db_session, UploadService(get_settings()), today=date(2026, 3, 20))
    assert stats.current_month_total == Decimal("0.00")
    assert stats.previous_month_total == Decimal("0.00")
    assert stats.percentage_change is None
    assert stats.totals_by_category == []
    assert stats.recent_expenses == []


def test_dashboard_current_and_previous_month_totals(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 3, 10))
    _add_expense(db_session, amount=Decimal("50.00"), expense_date=date(2026, 3, 20))
    _add_expense(db_session, amount=Decimal("80.00"), expense_date=date(2026, 2, 15))

    stats = build_dashboard_stats(db_session, UploadService(get_settings()), today=date(2026, 3, 25))

    assert stats.current_month_total == Decimal("150.00")
    assert stats.previous_month_total == Decimal("80.00")


def test_dashboard_decimal_precision_avoids_binary_float_error(db_session):
    """0.10 + 0.20 + 0.30 must sum to exactly 0.60, not float's 0.6000000000000001."""
    _add_expense(db_session, amount=Decimal("0.10"), expense_date=date(2026, 3, 1))
    _add_expense(db_session, amount=Decimal("0.20"), expense_date=date(2026, 3, 2))
    _add_expense(db_session, amount=Decimal("0.30"), expense_date=date(2026, 3, 3))

    stats = build_dashboard_stats(db_session, UploadService(get_settings()), today=date(2026, 3, 25))

    assert stats.current_month_total == Decimal("0.60")
    assert float(0.10) + float(0.20) + float(0.30) != 0.60  # sanity check: float would NOT be exact here


def test_dashboard_percentage_change_calculation(db_session):
    _add_expense(db_session, amount=Decimal("150.00"), expense_date=date(2026, 3, 10))
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 2, 10))

    stats = build_dashboard_stats(db_session, UploadService(get_settings()), today=date(2026, 3, 25))

    assert stats.percentage_change == 50.0


def test_dashboard_percentage_change_when_previous_month_had_no_spending(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 3, 10))

    stats = build_dashboard_stats(db_session, UploadService(get_settings()), today=date(2026, 3, 25))

    assert stats.percentage_change == 100.0


def test_dashboard_totals_by_category(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), category=ExpenseCategory.GROCERIES, expense_date=date(2026, 3, 5))
    _add_expense(db_session, amount=Decimal("40.00"), category=ExpenseCategory.DINING, expense_date=date(2026, 3, 6))
    _add_expense(db_session, amount=Decimal("60.00"), category=ExpenseCategory.GROCERIES, expense_date=date(2026, 3, 7))

    stats = build_dashboard_stats(db_session, UploadService(get_settings()), today=date(2026, 3, 25))

    by_category = {c.category: c.total for c in stats.totals_by_category}
    assert by_category["groceries"] == Decimal("160.00")
    assert by_category["dining"] == Decimal("40.00")


def test_dashboard_recent_expenses_limited_and_ordered(db_session):
    for day in range(1, 8):
        _add_expense(db_session, expense_date=date(2026, 3, day), business_name=f"Store {day}")

    stats = build_dashboard_stats(db_session, UploadService(get_settings()), today=date(2026, 3, 25))

    assert len(stats.recent_expenses) == 5
    assert stats.recent_expenses[0].business_name == "Store 7"


def test_dashboard_stats_api(client):
    client.post(
        "/api/expenses",
        json={
            "business_name": "Cofix",
            "amount": 42.0,
            "expense_date": date.today().isoformat(),
            "category": "dining",
            "currency": "ILS",
        },
    )
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["current_month_total"]) == Decimal("42.00")
    assert len(body["recent_expenses"]) == 1


def test_dashboard_stats_api_decimal_precision(client):
    for amount in ("0.10", "0.20", "0.30"):
        client.post(
            "/api/expenses",
            json={
                "business_name": "Precision Test",
                "amount": amount,
                "expense_date": date.today().isoformat(),
                "category": "other",
                "currency": "ILS",
            },
        )
    response = client.get("/api/dashboard/stats")
    assert Decimal(response.json()["current_month_total"]) == Decimal("0.60")
