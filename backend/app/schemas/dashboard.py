from datetime import date as date_type
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.sale import SaleRead

DashboardPeriodName = Literal[
    "this_month", "previous_month", "last_3_months", "last_6_months", "this_year", "custom"
]
TrendGranularity = Literal["day", "week", "month"]


class CurrencyAmount(BaseModel):
    """One currency's worth of a total that must never be summed with a
    different currency's — see dashboard_service.py's module docstring."""

    currency: str
    amount: Decimal


class PeriodComparison(BaseModel):
    """How the current period's net revenue compares to the immediately
    preceding equivalent period, for one currency. `percentage_change` and
    `amount_change` are always both present or both null together — null
    exactly when the previous period had no revenue in this currency at
    all, since a percentage against a zero baseline is mathematically
    undefined, never fabricated as 0% or 100%."""

    currency: str
    percentage_change: float | None
    amount_change: Decimal | None


class DashboardPeriodInfo(BaseModel):
    """Echoes back the resolved period so the frontend never has to
    recompute date arithmetic itself to render a period label."""

    period: DashboardPeriodName
    start_date: date_type
    end_date: date_type
    previous_start_date: date_type
    previous_end_date: date_type
    trend_granularity: TrendGranularity


class TopService(BaseModel):
    service_name: str
    currency: str
    total: Decimal
    count: int
    # Share of this currency's own total gross revenue for the period —
    # never computed against a different currency's total, and never
    # implies the currencies were combined to get a "whole".
    percentage_of_revenue: float


class RevenueTrendPoint(BaseModel):
    period_start: date_type
    currency: str
    gross_total: Decimal
    net_total: Decimal


class DashboardStats(BaseModel):
    period: DashboardPeriodInfo

    # Every monetary total below is a *list* of per-currency amounts, never
    # a single number — a dataset with only ILS sales naturally produces a
    # one-element list (the frontend renders that exactly like a plain
    # figure); a dataset spanning ILS/USD/EUR produces one element per
    # currency, each clearly labeled, never added together. See
    # dashboard_service.py's module docstring for why.
    net_revenue_current_period: list[CurrencyAmount]
    net_revenue_previous_period: list[CurrencyAmount]
    comparison: list[PeriodComparison]

    successful_sales_count: int
    average_transaction_value: list[CurrencyAmount]
    gross_revenue: list[CurrencyAmount]
    vat_collected: list[CurrencyAmount]
    processing_fees: list[CurrencyAmount]
    # Refunds recorded against a sale that *occurred* in the selected
    # period (a refund's own timestamp isn't tracked yet — see the
    # module docstring) — this is the period-scoped financial-reporting
    # figure, distinct from `refunds_needing_attention_count` below.
    refunds_total: list[CurrencyAmount]

    recent_sales: list[SaleRead]
    top_services: list[TopService]
    revenue_trend: list[RevenueTrendPoint]

    # Operational "needs attention" counts — deliberately NOT scoped to the
    # selected reporting period: these describe the business's current
    # outstanding state (a document still pending, a payment that failed),
    # not a historical report, so they stay the same regardless of which
    # period is selected for the financial metrics above.
    pending_documents_count: int
    document_failures_count: int
    failed_payments_count: int
    refunds_needing_attention_count: int
    incomplete_details_count: int
