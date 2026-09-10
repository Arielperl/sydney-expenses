from datetime import datetime
from decimal import Decimal

from app.models.sale import DocumentStatus, Sale, SaleStatus
from app.services.assistant.tools import (
    count_sales_in_period,
    get_gross_revenue,
    get_pending_documents_summary,
    get_processing_fees,
    get_recent_customers,
    get_refunds_summary,
    get_revenue_trend,
    get_top_services,
    get_total_revenue,
    get_vat_collected,
)


def _add_sale(db_session, **overrides):
    defaults = dict(
        customer_name="Demo Customer",
        service_name="Consulting",
        gross_amount=Decimal("100.00"),
        net_amount=Decimal("100.00"),
        currency="ILS",
        occurred_at=datetime(2026, 3, 15, 10, 0, 0),
        status=SaleStatus.SUCCEEDED,
        document_status=DocumentStatus.NOT_REQUIRED,
    )
    defaults.update(overrides)
    sale = Sale(**defaults)
    db_session.add(sale)
    db_session.commit()
    return sale


# --- get_total_revenue -------------------------------------------------


def test_get_total_revenue_empty_db(db_session):
    result = get_total_revenue(db_session)
    assert result == {"net_revenue": "0.00", "count": 0}


def test_get_total_revenue_sums_net_by_default(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"))
    _add_sale(db_session, net_amount=Decimal("50.50"))
    result = get_total_revenue(db_session)
    assert result == {"net_revenue": "150.50", "count": 2}


def test_get_total_revenue_excludes_pending_and_failed(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), status=SaleStatus.SUCCEEDED)
    _add_sale(db_session, net_amount=Decimal("50.00"), status=SaleStatus.PENDING)
    _add_sale(db_session, net_amount=Decimal("40.00"), status=SaleStatus.FAILED)
    result = get_total_revenue(db_session)
    assert result == {"net_revenue": "100.00", "count": 1}


def test_get_total_revenue_excludes_fully_refunded_and_reduces_partial(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), status=SaleStatus.REFUNDED, refunded_amount=Decimal("100.00"))
    _add_sale(
        db_session,
        net_amount=Decimal("100.00"),
        status=SaleStatus.PARTIALLY_REFUNDED,
        refunded_amount=Decimal("40.00"),
    )
    result = get_total_revenue(db_session)
    assert result == {"net_revenue": "60.00", "count": 1}


def test_get_total_revenue_filters_by_date_range(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 10, 9))
    _add_sale(db_session, net_amount=Decimal("50.00"), occurred_at=datetime(2026, 4, 1, 9))
    result = get_total_revenue(db_session, start_date="2026-03-01", end_date="2026-03-31")
    assert result == {"net_revenue": "100.00", "count": 1}


def test_get_total_revenue_invalid_date_returns_error_not_raise(db_session):
    result = get_total_revenue(db_session, start_date="not-a-date")
    assert "error" in result


def test_get_total_revenue_end_date_includes_sales_later_that_same_day(db_session):
    """Regression test: Sale.occurred_at is a full timestamp, not a date —
    an end_date filter must include the whole day, not just up to midnight."""
    _add_sale(db_session, net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 10, 21, 30))
    result = get_total_revenue(db_session, start_date="2026-03-01", end_date="2026-03-10")
    assert result == {"net_revenue": "100.00", "count": 1}


# --- get_gross_revenue / get_vat_collected / get_processing_fees --------


def test_get_gross_revenue_excludes_vat_and_fees(db_session):
    _add_sale(db_session, gross_amount=Decimal("100.00"), vat_amount=Decimal("15.00"), processing_fee=Decimal("3.00"))
    result = get_gross_revenue(db_session)
    assert result == {"gross_revenue": "100.00", "count": 1}


def test_get_vat_collected(db_session):
    _add_sale(db_session, vat_amount=Decimal("15.00"))
    _add_sale(db_session, vat_amount=Decimal("7.50"))
    result = get_vat_collected(db_session)
    assert result == {"vat_collected": "22.50"}


def test_get_processing_fees(db_session):
    _add_sale(db_session, processing_fee=Decimal("3.00"))
    _add_sale(db_session, processing_fee=Decimal("1.50"))
    result = get_processing_fees(db_session)
    assert result == {"processing_fees": "4.50"}


def test_gross_vat_and_fees_include_partially_refunded_sales(db_session):
    """A partially-refunded sale is still "successful" (same definition
    get_total_revenue already uses) — it must count here too, so the
    assistant and the dashboard can never disagree for the same period. A
    fully refunded sale still doesn't count: its revenue was fully
    reversed."""
    _add_sale(
        db_session,
        gross_amount=Decimal("100.00"),
        vat_amount=Decimal("15.00"),
        processing_fee=Decimal("3.00"),
        status=SaleStatus.PARTIALLY_REFUNDED,
        refunded_amount=Decimal("40.00"),
    )
    _add_sale(
        db_session,
        gross_amount=Decimal("50.00"),
        vat_amount=Decimal("7.50"),
        processing_fee=Decimal("1.50"),
        status=SaleStatus.REFUNDED,
        refunded_amount=Decimal("50.00"),
    )

    assert get_gross_revenue(db_session) == {"gross_revenue": "100.00", "count": 1}
    assert get_vat_collected(db_session) == {"vat_collected": "15.00"}
    assert get_processing_fees(db_session) == {"processing_fees": "3.00"}


# --- get_top_services ---------------------------------------------------


def test_get_top_services_sorted_and_limited(db_session):
    _add_sale(db_session, service_name="A", net_amount=Decimal("10.00"))
    _add_sale(db_session, service_name="B", net_amount=Decimal("100.00"))
    _add_sale(db_session, service_name="B", net_amount=Decimal("50.00"))
    result = get_top_services(db_session, limit=1)
    assert result == {"services": [{"service_name": "B", "total": "150.00", "count": 2}]}


# --- get_revenue_trend -----------------------------------------------------


def test_get_revenue_trend_groups_by_month(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 5, 9))
    _add_sale(db_session, net_amount=Decimal("20.00"), occurred_at=datetime(2026, 3, 20, 9))
    _add_sale(db_session, net_amount=Decimal("40.00"), occurred_at=datetime(2026, 4, 1, 9))
    result = get_revenue_trend(db_session, period="month")
    assert result["trend"] == [
        {"period_start": "2026-03-01", "total": "120.00", "count": 2},
        {"period_start": "2026-04-01", "total": "40.00", "count": 1},
    ]


def test_get_revenue_trend_invalid_period_returns_error(db_session):
    result = get_revenue_trend(db_session, period="year")
    assert "error" in result


# --- get_recent_customers ------------------------------------------------


def test_get_recent_customers_orders_newest_first(db_session):
    _add_sale(db_session, customer_name="Old", occurred_at=datetime(2026, 1, 1, 9))
    _add_sale(db_session, customer_name="New", occurred_at=datetime(2026, 3, 1, 9))
    result = get_recent_customers(db_session, limit=10)
    assert [c["customer_name"] for c in result["customers"]] == ["New", "Old"]


# --- count_sales_in_period -------------------------------------------------


def test_count_sales_in_period(db_session):
    _add_sale(db_session, occurred_at=datetime(2026, 3, 10, 9))
    _add_sale(db_session, occurred_at=datetime(2026, 3, 12, 9), status=SaleStatus.FAILED)
    result = count_sales_in_period(db_session, start_date="2026-03-01", end_date="2026-03-31")
    assert result == {"count": 2}


def test_count_sales_in_period_end_date_includes_the_whole_last_day(db_session):
    _add_sale(db_session, occurred_at=datetime(2026, 3, 12, 23, 45))
    result = count_sales_in_period(db_session, start_date="2026-03-01", end_date="2026-03-12")
    assert result == {"count": 1}


# --- get_pending_documents_summary -----------------------------------------


def test_get_pending_documents_summary_counts_pending_and_failed(db_session):
    _add_sale(db_session, document_status=DocumentStatus.PENDING)
    _add_sale(db_session, document_status=DocumentStatus.FAILED)
    _add_sale(db_session, document_status=DocumentStatus.ISSUED)

    result = get_pending_documents_summary(db_session)

    assert result["count"] == 2


def test_get_pending_documents_summary_empty(db_session):
    result = get_pending_documents_summary(db_session)
    assert result["count"] == 0


# --- get_refunds_summary ---------------------------------------------------


def test_get_refunds_summary(db_session):
    _add_sale(db_session, status=SaleStatus.REFUNDED, refunded_amount=Decimal("100.00"))
    _add_sale(db_session, status=SaleStatus.PARTIALLY_REFUNDED, refunded_amount=Decimal("40.00"))
    _add_sale(db_session, status=SaleStatus.SUCCEEDED)

    result = get_refunds_summary(db_session)

    assert result == {"count": 2, "total_refunded": "140.00"}
