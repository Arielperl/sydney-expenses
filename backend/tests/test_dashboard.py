from datetime import date, datetime
from decimal import Decimal

from app.models.sale import DocumentStatus, Sale, SaleStatus
from app.services.dashboard_service import build_dashboard_stats


def _add_sale(db_session, **overrides):
    defaults = dict(
        customer_name="Demo Customer",
        service_name="Consulting session",
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


def test_dashboard_empty_state(db_session):
    stats = build_dashboard_stats(db_session, today=date(2026, 3, 20))
    assert stats.net_revenue_this_month == Decimal("0.00")
    assert stats.net_revenue_previous_month == Decimal("0.00")
    assert stats.percentage_change is None
    assert stats.top_services == []
    assert stats.recent_sales == []
    assert stats.successful_sales_count == 0
    assert stats.average_transaction_value is None
    assert stats.pending_documents_count == 0
    assert stats.pending_documents_total == Decimal("0.00")
    assert stats.document_failures_count == 0
    assert stats.failed_payments_count == 0
    assert stats.refunds_count == 0
    assert stats.revenue_trend[-1].period_start == date(2026, 3, 1)
    assert len(stats.revenue_trend) == 6


def test_dashboard_current_and_previous_month_revenue(db_session):
    _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 10, 9))
    _add_sale(db_session, gross_amount=Decimal("50.00"), net_amount=Decimal("50.00"), occurred_at=datetime(2026, 3, 20, 9))
    _add_sale(db_session, gross_amount=Decimal("80.00"), net_amount=Decimal("80.00"), occurred_at=datetime(2026, 2, 15, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.net_revenue_this_month == Decimal("150.00")
    assert stats.net_revenue_previous_month == Decimal("80.00")


def test_dashboard_decimal_precision_avoids_binary_float_error(db_session):
    """0.10 + 0.20 + 0.30 must sum to exactly 0.60, not float's 0.6000000000000001."""
    for amount in ("0.10", "0.20", "0.30"):
        _add_sale(db_session, gross_amount=Decimal(amount), net_amount=Decimal(amount), occurred_at=datetime(2026, 3, 1, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.net_revenue_this_month == Decimal("0.60")
    assert float(0.10) + float(0.20) + float(0.30) != 0.60  # sanity check: float would NOT be exact here


def test_dashboard_percentage_change_calculation(db_session):
    _add_sale(db_session, gross_amount=Decimal("150.00"), net_amount=Decimal("150.00"), occurred_at=datetime(2026, 3, 10, 9))
    _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), occurred_at=datetime(2026, 2, 10, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.percentage_change == 50.0


def test_dashboard_percentage_change_when_previous_month_had_no_revenue(db_session):
    _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 10, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.percentage_change == 100.0


def test_dashboard_top_services(db_session):
    _add_sale(db_session, service_name="Consulting", gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    _add_sale(db_session, service_name="Design", gross_amount=Decimal("40.00"), net_amount=Decimal("40.00"))
    _add_sale(db_session, service_name="Consulting", gross_amount=Decimal("60.00"), net_amount=Decimal("60.00"))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    by_service = {s.service_name: s.total for s in stats.top_services}
    assert by_service["Consulting"] == Decimal("160.00")
    assert by_service["Design"] == Decimal("40.00")


def test_dashboard_recent_sales_limited_and_ordered(db_session):
    for day in range(1, 8):
        _add_sale(db_session, occurred_at=datetime(2026, 3, day, 9), customer_name=f"Customer {day}")

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert len(stats.recent_sales) == 5
    assert stats.recent_sales[0].customer_name == "Customer 7"


def test_dashboard_gross_vat_fees_and_average(db_session):
    _add_sale(
        db_session,
        gross_amount=Decimal("100.00"),
        vat_amount=Decimal("15.00"),
        processing_fee=Decimal("3.00"),
        net_amount=Decimal("82.00"),
    )
    _add_sale(
        db_session,
        gross_amount=Decimal("50.00"),
        vat_amount=Decimal("7.50"),
        processing_fee=Decimal("1.50"),
        net_amount=Decimal("41.00"),
    )

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.gross_revenue == Decimal("150.00")
    assert stats.vat_collected == Decimal("22.50")
    assert stats.processing_fees == Decimal("4.50")
    assert stats.successful_sales_count == 2
    assert stats.average_transaction_value == Decimal("75.00")


def test_dashboard_stats_api(client):
    client.post(
        "/api/sales",
        json={
            "customer_name": "Demo Customer",
            "service_name": "Consulting",
            "gross_amount": 42.0,
            "occurred_at": datetime.combine(date.today(), datetime.min.time()).isoformat(),
            "currency": "ILS",
        },
    )
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["net_revenue_this_month"]) == Decimal("42.00")
    assert len(body["recent_sales"]) == 1


def test_pending_documents_count_and_total(db_session):
    _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), document_status=DocumentStatus.PENDING)
    _add_sale(db_session, gross_amount=Decimal("50.00"), net_amount=Decimal("50.00"), document_status=DocumentStatus.PENDING)
    _add_sale(db_session, gross_amount=Decimal("30.00"), net_amount=Decimal("30.00"), document_status=DocumentStatus.ISSUED)

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.pending_documents_count == 2
    assert stats.pending_documents_total == Decimal("150.00")


def test_document_failures_count(db_session):
    _add_sale(db_session, document_status=DocumentStatus.FAILED)
    _add_sale(db_session, document_status=DocumentStatus.ISSUED)

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.document_failures_count == 1


def test_failed_payments_count_this_month(db_session):
    _add_sale(db_session, status=SaleStatus.FAILED, occurred_at=datetime(2026, 3, 10, 9))
    _add_sale(db_session, status=SaleStatus.SUCCEEDED, occurred_at=datetime(2026, 3, 11, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.failed_payments_count == 1


def test_refunds_reduce_net_revenue_and_are_counted(db_session):
    sale = _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    sale.status = SaleStatus.REFUNDED
    sale.refunded_amount = Decimal("100.00")
    db_session.commit()

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.net_revenue_this_month == Decimal("0.00")
    assert stats.refunds_count == 1
    assert stats.refunds_total == Decimal("100.00")


def test_partial_refund_contributes_remaining_net_to_revenue(db_session):
    sale = _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    sale.status = SaleStatus.PARTIALLY_REFUNDED
    sale.refunded_amount = Decimal("40.00")
    db_session.commit()

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.net_revenue_this_month == Decimal("60.00")


def test_pending_and_failed_sales_never_count_as_revenue(db_session):
    _add_sale(db_session, status=SaleStatus.PENDING, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    _add_sale(db_session, status=SaleStatus.FAILED, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.net_revenue_this_month == Decimal("0.00")


def test_dashboard_stats_api_decimal_precision(client):
    for amount in ("0.10", "0.20", "0.30"):
        client.post(
            "/api/sales",
            json={
                "customer_name": "Precision Test",
                "service_name": "Consulting",
                "gross_amount": amount,
                "occurred_at": datetime.combine(date.today(), datetime.min.time()).isoformat(),
                "currency": "ILS",
            },
        )
    response = client.get("/api/dashboard/stats")
    assert Decimal(response.json()["net_revenue_this_month"]) == Decimal("0.60")
