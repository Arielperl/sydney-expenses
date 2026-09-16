from datetime import datetime
from decimal import Decimal

from app.models.sale import DocumentStatus, Sale, SaleStatus
from app.services.assistant.tools import (
    analyze_sales,
    compare_sales_periods,
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
    query_sales,
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
    assert result == {"net_revenue_by_currency": []}


def test_get_total_revenue_sums_net_by_default(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"))
    _add_sale(db_session, net_amount=Decimal("50.50"))
    result = get_total_revenue(db_session)
    assert result == {"net_revenue_by_currency": [{"currency": "ILS", "net_revenue": "150.50", "count": 2}]}


def test_get_total_revenue_excludes_pending_and_failed(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), status=SaleStatus.SUCCEEDED)
    _add_sale(db_session, net_amount=Decimal("50.00"), status=SaleStatus.PENDING)
    _add_sale(db_session, net_amount=Decimal("40.00"), status=SaleStatus.FAILED)
    result = get_total_revenue(db_session)
    assert result == {"net_revenue_by_currency": [{"currency": "ILS", "net_revenue": "100.00", "count": 1}]}


def test_get_total_revenue_excludes_fully_refunded_and_reduces_partial(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), status=SaleStatus.REFUNDED, refunded_amount=Decimal("100.00"))
    _add_sale(
        db_session,
        net_amount=Decimal("100.00"),
        status=SaleStatus.PARTIALLY_REFUNDED,
        refunded_amount=Decimal("40.00"),
    )
    result = get_total_revenue(db_session)
    assert result == {"net_revenue_by_currency": [{"currency": "ILS", "net_revenue": "60.00", "count": 1}]}


def test_get_total_revenue_filters_by_date_range(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 10, 9))
    _add_sale(db_session, net_amount=Decimal("50.00"), occurred_at=datetime(2026, 4, 1, 9))
    result = get_total_revenue(db_session, start_date="2026-03-01", end_date="2026-03-31")
    assert result == {"net_revenue_by_currency": [{"currency": "ILS", "net_revenue": "100.00", "count": 1}]}


def test_get_total_revenue_invalid_date_returns_error_not_raise(db_session):
    result = get_total_revenue(db_session, start_date="not-a-date")
    assert "error" in result


def test_get_total_revenue_end_date_includes_sales_later_that_same_day(db_session):
    """Regression test: Sale.occurred_at is a full timestamp, not a date —
    an end_date filter must include the whole day, not just up to midnight."""
    _add_sale(db_session, net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 10, 21, 30))
    result = get_total_revenue(db_session, start_date="2026-03-01", end_date="2026-03-10")
    assert result == {"net_revenue_by_currency": [{"currency": "ILS", "net_revenue": "100.00", "count": 1}]}


def test_get_total_revenue_never_combines_different_currencies(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), currency="ILS")
    _add_sale(db_session, net_amount=Decimal("30.00"), currency="USD")
    result = get_total_revenue(db_session)
    assert result == {
        "net_revenue_by_currency": [
            {"currency": "ILS", "net_revenue": "100.00", "count": 1},
            {"currency": "USD", "net_revenue": "30.00", "count": 1},
        ]
    }


# --- get_gross_revenue / get_vat_collected / get_processing_fees --------


def test_get_gross_revenue_excludes_vat_and_fees(db_session):
    _add_sale(db_session, gross_amount=Decimal("100.00"), vat_amount=Decimal("15.00"), processing_fee=Decimal("3.00"))
    result = get_gross_revenue(db_session)
    assert result == {"gross_revenue_by_currency": [{"currency": "ILS", "gross_revenue": "100.00", "count": 1}]}


def test_get_vat_collected(db_session):
    _add_sale(db_session, vat_amount=Decimal("15.00"))
    _add_sale(db_session, vat_amount=Decimal("7.50"))
    result = get_vat_collected(db_session)
    assert result == {"vat_collected_by_currency": [{"currency": "ILS", "vat_collected": "22.50", "count": 2}]}


def test_get_processing_fees(db_session):
    _add_sale(db_session, processing_fee=Decimal("3.00"))
    _add_sale(db_session, processing_fee=Decimal("1.50"))
    result = get_processing_fees(db_session)
    assert result == {"processing_fees_by_currency": [{"currency": "ILS", "processing_fees": "4.50", "count": 2}]}


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

    assert get_gross_revenue(db_session) == {"gross_revenue_by_currency": [{"currency": "ILS", "gross_revenue": "100.00", "count": 1}]}
    assert get_vat_collected(db_session) == {"vat_collected_by_currency": [{"currency": "ILS", "vat_collected": "15.00", "count": 1}]}
    assert get_processing_fees(db_session) == {"processing_fees_by_currency": [{"currency": "ILS", "processing_fees": "3.00", "count": 1}]}


def test_get_gross_revenue_never_combines_different_currencies(db_session):
    _add_sale(db_session, gross_amount=Decimal("100.00"), currency="ILS")
    _add_sale(db_session, gross_amount=Decimal("40.00"), currency="EUR")
    result = get_gross_revenue(db_session)
    assert result == {
        "gross_revenue_by_currency": [
            {"currency": "EUR", "gross_revenue": "40.00", "count": 1},
            {"currency": "ILS", "gross_revenue": "100.00", "count": 1},
        ]
    }


# --- get_top_services ---------------------------------------------------


def test_get_top_services_sorted_and_limited(db_session):
    _add_sale(db_session, service_name="A", net_amount=Decimal("10.00"))
    _add_sale(db_session, service_name="B", net_amount=Decimal("100.00"))
    _add_sale(db_session, service_name="B", net_amount=Decimal("50.00"))
    result = get_top_services(db_session, limit=1)
    assert result == {"services": [{"service_name": "B", "currency": "ILS", "total": "150.00", "count": 2}]}


def test_get_top_services_kept_separate_per_currency(db_session):
    _add_sale(db_session, service_name="Consulting", currency="ILS", net_amount=Decimal("100.00"))
    _add_sale(db_session, service_name="Consulting", currency="USD", net_amount=Decimal("30.00"))
    result = get_top_services(db_session, limit=5)
    rows = {(r["service_name"], r["currency"]): r["total"] for r in result["services"]}
    assert rows[("Consulting", "ILS")] == "100.00"
    assert rows[("Consulting", "USD")] == "30.00"


# --- get_revenue_trend -----------------------------------------------------


def test_get_revenue_trend_groups_by_month(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), occurred_at=datetime(2026, 3, 5, 9))
    _add_sale(db_session, net_amount=Decimal("20.00"), occurred_at=datetime(2026, 3, 20, 9))
    _add_sale(db_session, net_amount=Decimal("40.00"), occurred_at=datetime(2026, 4, 1, 9))
    result = get_revenue_trend(db_session, period="month")
    assert result["trend"] == [
        {"period_start": "2026-03-01", "currency": "ILS", "total": "120.00", "count": 2},
        {"period_start": "2026-04-01", "currency": "ILS", "total": "40.00", "count": 1},
    ]


def test_get_revenue_trend_invalid_period_returns_error(db_session):
    result = get_revenue_trend(db_session, period="year")
    assert "error" in result


def test_get_revenue_trend_separates_currencies_within_same_period(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), currency="ILS", occurred_at=datetime(2026, 3, 5, 9))
    _add_sale(db_session, net_amount=Decimal("30.00"), currency="USD", occurred_at=datetime(2026, 3, 20, 9))
    result = get_revenue_trend(db_session, period="month")
    assert result["trend"] == [
        {"period_start": "2026-03-01", "currency": "ILS", "total": "100.00", "count": 1},
        {"period_start": "2026-03-01", "currency": "USD", "total": "30.00", "count": 1},
    ]


# --- get_recent_customers ------------------------------------------------


def test_get_recent_customers_orders_newest_first(db_session):
    _add_sale(db_session, customer_name="Old", occurred_at=datetime(2026, 1, 1, 9))
    _add_sale(db_session, customer_name="New", occurred_at=datetime(2026, 3, 1, 9))
    result = get_recent_customers(db_session, limit=10)
    assert [c["customer_name"] for c in result["customers"]] == ["New", "Old"]


def test_get_recent_customers_includes_currency_per_row(db_session):
    _add_sale(db_session, customer_name="Dana", currency="USD", gross_amount=Decimal("30.00"))
    result = get_recent_customers(db_session, limit=10)
    assert result["customers"][0]["currency"] == "USD"
    assert result["customers"][0]["amount"] == "30.00"


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
    assert result["total_by_currency"] == [{"currency": "ILS", "total": "200.00", "count": 2}]
    assert all("currency" in row for row in result["sales"])


def test_get_pending_documents_summary_empty(db_session):
    result = get_pending_documents_summary(db_session)
    assert result["count"] == 0
    assert result["total_by_currency"] == []


# --- get_refunds_summary ---------------------------------------------------


def test_get_refunds_summary(db_session):
    _add_sale(db_session, status=SaleStatus.REFUNDED, refunded_amount=Decimal("100.00"))
    _add_sale(db_session, status=SaleStatus.PARTIALLY_REFUNDED, refunded_amount=Decimal("40.00"))
    _add_sale(db_session, status=SaleStatus.SUCCEEDED)

    result = get_refunds_summary(db_session)

    assert result == {"count": 2, "refunds_by_currency": [{"currency": "ILS", "total_refunded": "140.00", "count": 2}]}


def test_get_refunds_summary_separates_currencies(db_session):
    _add_sale(db_session, status=SaleStatus.REFUNDED, refunded_amount=Decimal("100.00"), currency="ILS")
    _add_sale(db_session, status=SaleStatus.REFUNDED, refunded_amount=Decimal("20.00"), currency="USD")

    result = get_refunds_summary(db_session)

    assert result["count"] == 2
    by_currency = {row["currency"]: row["total_refunded"] for row in result["refunds_by_currency"]}
    assert by_currency == {"ILS": "100.00", "USD": "20.00"}


# --- general analytics ----------------------------------------------------


def test_query_sales_returns_the_largest_individual_sale_not_top_service(db_session):
    _add_sale(db_session, customer_name="Small", service_name="Repeated", gross_amount=Decimal("800.00"))
    _add_sale(db_session, customer_name="Also Small", service_name="Repeated", gross_amount=Decimal("900.00"))
    _add_sale(db_session, customer_name="Largest", service_name="One-off", gross_amount=Decimal("1500.00"))

    result = query_sales(db_session, sort_by="gross_amount", sort_order="desc", limit=1)

    assert result["sales_by_currency"][0]["sales"][0]["customer_name"] == "Largest"
    assert result["sales_by_currency"][0]["sales"][0]["gross_amount"] == "1500.00"


def test_query_sales_can_rank_by_actual_net_after_partial_refund(db_session):
    _add_sale(db_session, customer_name="Gross Winner", gross_amount=Decimal("1500.00"), net_amount=Decimal("1200.00"))
    _add_sale(
        db_session,
        customer_name="Refunded",
        gross_amount=Decimal("2000.00"),
        net_amount=Decimal("1800.00"),
        status=SaleStatus.PARTIALLY_REFUNDED,
        refunded_amount=Decimal("1000.00"),
    )

    result = query_sales(db_session, sort_by="net_revenue", sort_order="desc", limit=1)

    assert result["sales_by_currency"][0]["sales"][0]["customer_name"] == "Gross Winner"
    assert result["sales_by_currency"][0]["sales"][0]["net_revenue"] == "1200.00"


def test_query_sales_never_ranks_different_currencies_against_each_other(db_session):
    _add_sale(db_session, customer_name="Shekel", currency="ILS", gross_amount=Decimal("1500.00"))
    _add_sale(db_session, customer_name="Dollar", currency="USD", gross_amount=Decimal("500.00"))

    result = query_sales(db_session, sort_by="gross_amount", limit=1)

    assert [(group["currency"], group["sales"][0]["customer_name"]) for group in result["sales_by_currency"]] == [
        ("ILS", "Shekel"),
        ("USD", "Dollar"),
    ]


def test_query_sales_supports_future_combinations_of_filters(db_session):
    _add_sale(
        db_session,
        customer_name="Dana Cohen",
        service_name="Consulting",
        payment_method="cash",
        gross_amount=Decimal("300.00"),
        occurred_at=datetime(2026, 3, 10, 12),
    )
    _add_sale(
        db_session,
        customer_name="Dana Cohen",
        service_name="Workshop",
        payment_method="card",
        gross_amount=Decimal("700.00"),
        occurred_at=datetime(2026, 4, 10, 12),
    )

    result = query_sales(
        db_session,
        customer_query="dana",
        service_query="consult",
        payment_method="cash",
        start_date="2026-03-01",
        end_date="2026-03-31",
        sort_by="gross_amount",
    )

    assert [row["gross_amount"] for row in result["sales_by_currency"][0]["sales"]] == ["300.00"]


def test_analyze_sales_answers_top_customer_and_average_ticket(db_session):
    _add_sale(db_session, customer_name="Dana", gross_amount=Decimal("100.00"), net_amount=Decimal("80.00"))
    _add_sale(db_session, customer_name="Dana", gross_amount=Decimal("300.00"), net_amount=Decimal("240.00"))
    _add_sale(db_session, customer_name="Ariel", gross_amount=Decimal("350.00"), net_amount=Decimal("280.00"))

    top_customer = analyze_sales(db_session, metric="net_revenue", group_by="customer", limit=1)
    average = analyze_sales(db_session, metric="average_gross_amount", group_by="none")

    assert top_customer["results"] == [{"group": "Dana", "currency": "ILS", "value": "320.00", "count": 2}]
    assert average["results"] == [{"group": "all", "currency": "ILS", "value": "250.00", "count": 3}]


def test_analyze_sales_handles_novel_payment_method_and_day_questions(db_session):
    _add_sale(db_session, payment_method="cash", occurred_at=datetime(2026, 3, 10, 9), net_amount=Decimal("100.00"))
    _add_sale(db_session, payment_method="cash", occurred_at=datetime(2026, 3, 10, 13), net_amount=Decimal("50.00"))
    _add_sale(db_session, payment_method="card", occurred_at=datetime(2026, 3, 11, 9), net_amount=Decimal("120.00"))

    by_method = analyze_sales(db_session, metric="sale_count", group_by="payment_method")
    by_day = analyze_sales(db_session, metric="net_revenue", group_by="day", limit=1)

    assert by_method["results"] == [{"group": "cash", "value": 2}, {"group": "card", "value": 1}]
    assert by_day["results"] == [{"group": "2026-03-10", "currency": "ILS", "value": "150.00", "count": 2}]


def test_compare_sales_periods_calculates_change_in_backend(db_session):
    _add_sale(db_session, net_amount=Decimal("100.00"), occurred_at=datetime(2026, 2, 10, 9))
    _add_sale(db_session, net_amount=Decimal("150.00"), occurred_at=datetime(2026, 3, 10, 9))

    result = compare_sales_periods(
        db_session,
        first_start_date="2026-02-01",
        first_end_date="2026-02-28",
        second_start_date="2026-03-01",
        second_end_date="2026-03-31",
    )

    assert result["periods_by_currency"] == [
        {"currency": "ILS", "first": "100.00", "second": "150.00", "change_percent": "50.00"}
    ]


def test_general_analytics_rejects_unbounded_or_unknown_arguments(db_session):
    assert "error" in query_sales(db_session, sort_by="raw_sql")
    assert "error" in query_sales(db_session, limit=1000)
    assert "error" in analyze_sales(db_session, group_by="credit_card_number")
    assert "error" in compare_sales_periods(
        db_session,
        first_start_date="bad-date",
        first_end_date="2026-01-31",
        second_start_date="2026-02-01",
        second_end_date="2026-02-28",
    )
