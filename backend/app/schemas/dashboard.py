from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.sale import SaleRead


class CurrencyAmount(BaseModel):
    """One currency's worth of a total that must never be summed with a
    different currency's — see dashboard_service.py's module docstring."""

    currency: str
    amount: Decimal


class TopService(BaseModel):
    service_name: str
    currency: str
    total: Decimal
    count: int


class RevenueTrendPoint(BaseModel):
    period_start: date_type
    currency: str
    total: Decimal


class DashboardStats(BaseModel):
    # Every monetary total below is a *list* of per-currency amounts, never
    # a single number — a dataset with only ILS sales naturally produces a
    # one-element list (the frontend renders that exactly like a plain
    # figure); a dataset spanning ILS/USD/EUR produces one element per
    # currency, each clearly labeled, never added together. See
    # dashboard_service.py's module docstring for why.
    net_revenue_this_month: list[CurrencyAmount]
    net_revenue_previous_month: list[CurrencyAmount]
    # Keyed by currency: a currency with no revenue in the previous period
    # has no honest percentage to report for that currency (see
    # dashboard_service.py) — absent from this dict, or present with `None`.
    percentage_change: dict[str, float | None]
    successful_sales_count: int
    average_transaction_value: list[CurrencyAmount]
    gross_revenue: list[CurrencyAmount]
    vat_collected: list[CurrencyAmount]
    processing_fees: list[CurrencyAmount]
    recent_sales: list[SaleRead]
    top_services: list[TopService]
    revenue_trend: list[RevenueTrendPoint]
    pending_documents_count: int
    pending_documents_total: list[CurrencyAmount]
    document_failures_count: int
    failed_payments_count: int
    refunds_count: int
    refunds_total: list[CurrencyAmount]
