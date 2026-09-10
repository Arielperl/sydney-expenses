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


def _amount(currency_amounts, currency="ILS") -> Decimal:
    """Pulls out one currency's amount from a DashboardStats list-of-
    CurrencyAmount field — the shape every monetary dashboard total now
    uses. Returns 0.00 when that currency isn't present at all (nothing of
    that currency happened in the period), same as an absent total would
    mean."""
    for item in currency_amounts:
        if item.currency == currency:
            return item.amount
    return Decimal("0.00")


def _currencies(currency_amounts) -> set[str]:
    return {item.currency for item in currency_amounts}


def test_dashboard_empty_state(db_session):
    stats = build_dashboard_stats(db_session, today=date(2026, 3, 20))
    assert stats.net_revenue_this_month == []
    assert stats.net_revenue_previous_month == []
    assert stats.percentage_change == {}
    assert stats.top_services == []
    assert stats.recent_sales == []
    assert stats.successful_sales_count == 0
    assert stats.average_transaction_value == []
    assert stats.pending_documents_count == 0
    assert stats.pending_documents_total == []
    assert stats.document_failures_count == 0
    assert stats.failed_payments_count == 0
    assert stats.refunds_count == 0
    assert stats.revenue_trend == []


def test_dashboard_current_and_previous_month_revenue(db_session):
    _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 10, 9))
    _add_sale(db_session, gross_amount=Decimal("50.00"), net_amount=Decimal("50.00"), occurred_at=datetime(2026, 3, 20, 9))
    _add_sale(db_session, gross_amount=Decimal("80.00"), net_amount=Decimal("80.00"), occurred_at=datetime(2026, 2, 15, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert _amount(stats.net_revenue_this_month) == Decimal("150.00")
    assert _amount(stats.net_revenue_previous_month) == Decimal("80.00")


def test_dashboard_decimal_precision_avoids_binary_float_error(db_session):
    """0.10 + 0.20 + 0.30 must sum to exactly 0.60, not float's 0.6000000000000001."""
    for amount in ("0.10", "0.20", "0.30"):
        _add_sale(db_session, gross_amount=Decimal(amount), net_amount=Decimal(amount), occurred_at=datetime(2026, 3, 1, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert _amount(stats.net_revenue_this_month) == Decimal("0.60")
    assert float(0.10) + float(0.20) + float(0.30) != 0.60  # sanity check: float would NOT be exact here


def test_dashboard_percentage_change_calculation(db_session):
    _add_sale(db_session, gross_amount=Decimal("150.00"), net_amount=Decimal("150.00"), occurred_at=datetime(2026, 3, 10, 9))
    _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), occurred_at=datetime(2026, 2, 10, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.percentage_change == {"ILS": 50.0}


def test_dashboard_percentage_change_when_previous_month_had_no_revenue(db_session):
    """A zero previous-month baseline can't produce an honest percentage
    (any nonzero current value would be a mathematically undefined
    "increase") — this must report no comparison at all, never a fabricated
    100%."""
    _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 10, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.percentage_change == {"ILS": None}


def test_dashboard_top_services(db_session):
    _add_sale(db_session, service_name="Consulting", gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    _add_sale(db_session, service_name="Design", gross_amount=Decimal("40.00"), net_amount=Decimal("40.00"))
    _add_sale(db_session, service_name="Consulting", gross_amount=Decimal("60.00"), net_amount=Decimal("60.00"))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    by_service = {(s.service_name, s.currency): s.total for s in stats.top_services}
    assert by_service[("Consulting", "ILS")] == Decimal("160.00")
    assert by_service[("Design", "ILS")] == Decimal("40.00")


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

    assert _amount(stats.gross_revenue) == Decimal("150.00")
    assert _amount(stats.vat_collected) == Decimal("22.50")
    assert _amount(stats.processing_fees) == Decimal("4.50")
    assert stats.successful_sales_count == 2
    assert _amount(stats.average_transaction_value) == Decimal("75.00")


def test_dashboard_stats_api(client):
    client.post(
        "/api/sales",
        json={
            "customer_name": "Demo Customer",
            "service_name": "Consulting",
            "gross_amount": 42.0,
            "tax_treatment": "exempt",  # isolates this round-trip test from VAT math
            "occurred_at": datetime.combine(date.today(), datetime.min.time()).isoformat(),
            "currency": "ILS",
        },
    )
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    body = response.json()
    net_revenue = {row["currency"]: row["amount"] for row in body["net_revenue_this_month"]}
    assert Decimal(net_revenue["ILS"]) == Decimal("42.00")
    assert len(body["recent_sales"]) == 1


def test_pending_documents_count_and_total(db_session):
    _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), document_status=DocumentStatus.PENDING)
    _add_sale(db_session, gross_amount=Decimal("50.00"), net_amount=Decimal("50.00"), document_status=DocumentStatus.PENDING)
    _add_sale(db_session, gross_amount=Decimal("30.00"), net_amount=Decimal("30.00"), document_status=DocumentStatus.ISSUED)

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.pending_documents_count == 2
    assert _amount(stats.pending_documents_total) == Decimal("150.00")


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

    assert stats.net_revenue_this_month == []
    assert stats.refunds_count == 1
    assert _amount(stats.refunds_total) == Decimal("100.00")


def test_partial_refund_contributes_remaining_net_to_revenue(db_session):
    sale = _add_sale(db_session, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    sale.status = SaleStatus.PARTIALLY_REFUNDED
    sale.refunded_amount = Decimal("40.00")
    db_session.commit()

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert _amount(stats.net_revenue_this_month) == Decimal("60.00")


def test_partially_refunded_sale_counts_toward_gross_vat_fees_and_count(db_session):
    """A partially-refunded sale is still a successful sale — it must show up
    in gross_revenue/vat_collected/processing_fees/successful_sales_count,
    the same "successful" set net_revenue_this_month already uses. Before
    the fix, these cards used a SUCCEEDED-only scope while net revenue used
    SUCCEEDED-or-PARTIALLY_REFUNDED, so a partially-refunded sale could make
    net revenue nonzero while gross/count stayed at zero."""
    sale = _add_sale(
        db_session,
        gross_amount=Decimal("100.00"),
        vat_amount=Decimal("15.00"),
        processing_fee=Decimal("3.00"),
        net_amount=Decimal("82.00"),
    )
    sale.status = SaleStatus.PARTIALLY_REFUNDED
    sale.refunded_amount = Decimal("40.00")
    db_session.commit()

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert _amount(stats.gross_revenue) == Decimal("100.00")
    assert _amount(stats.vat_collected) == Decimal("15.00")
    assert _amount(stats.processing_fees) == Decimal("3.00")
    assert stats.successful_sales_count == 1
    assert _amount(stats.net_revenue_this_month) == Decimal("42.00")


def test_pending_and_failed_sales_never_count_as_revenue(db_session):
    _add_sale(db_session, status=SaleStatus.PENDING, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    _add_sale(db_session, status=SaleStatus.FAILED, gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert stats.net_revenue_this_month == []


def test_dashboard_stats_api_decimal_precision(client):
    for amount in ("0.10", "0.20", "0.30"):
        client.post(
            "/api/sales",
            json={
                "customer_name": "Precision Test",
                "service_name": "Consulting",
                "gross_amount": amount,
                "tax_treatment": "exempt",  # isolates this test from VAT math
                "occurred_at": datetime.combine(date.today(), datetime.min.time()).isoformat(),
                "currency": "ILS",
            },
        )
    response = client.get("/api/dashboard/stats")
    net_revenue = {row["currency"]: row["amount"] for row in response.json()["net_revenue_this_month"]}
    assert Decimal(net_revenue["ILS"]) == Decimal("0.60")


def test_dashboard_never_combines_different_currencies(db_session):
    """The core multi-currency requirement: an ILS sale and a USD sale in
    the same month must appear as two separate {currency, amount} entries,
    never summed into one number that mixes currencies."""
    _add_sale(db_session, currency="ILS", gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    _add_sale(db_session, currency="USD", gross_amount=Decimal("50.00"), net_amount=Decimal("50.00"))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    assert _amount(stats.net_revenue_this_month, "ILS") == Decimal("100.00")
    assert _amount(stats.net_revenue_this_month, "USD") == Decimal("50.00")
    assert _currencies(stats.net_revenue_this_month) == {"ILS", "USD"}
    assert stats.successful_sales_count == 2


def test_revenue_trend_fills_zero_for_a_currency_present_anywhere_in_the_window(db_session):
    """A currency that only had sales in one of the last six months still
    gets a point for every month (zero where it had none), so the trend
    line stays continuous — never combined with another currency, and
    never simply missing months."""
    _add_sale(db_session, currency="ILS", gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"), occurred_at=datetime(2026, 1, 10, 9))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    ils_points = [p for p in stats.revenue_trend if p.currency == "ILS"]
    assert len(ils_points) == 6
    assert {p.period_start for p in ils_points} == {
        date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)
    }
    by_month = {p.period_start: p.total for p in ils_points}
    assert by_month[date(2026, 1, 1)] == Decimal("100.00")
    assert by_month[date(2026, 3, 1)] == Decimal("0.00")


def test_dashboard_top_services_kept_separate_per_currency(db_session):
    _add_sale(db_session, service_name="Consulting", currency="ILS", gross_amount=Decimal("100.00"), net_amount=Decimal("100.00"))
    _add_sale(db_session, service_name="Consulting", currency="USD", gross_amount=Decimal("30.00"), net_amount=Decimal("30.00"))

    stats = build_dashboard_stats(db_session, today=date(2026, 3, 25))

    by_key = {(s.service_name, s.currency): s.total for s in stats.top_services}
    assert by_key[("Consulting", "ILS")] == Decimal("100.00")
    assert by_key[("Consulting", "USD")] == Decimal("30.00")
