"""Dashboard aggregates — the single source of truth for what each number on
the dashboard means. `app/services/assistant/tools.py` mirrors these exact
definitions so the dashboard and the AI assistant can never disagree for the
same period.

Metric definitions:
- **Gross amount** (`gross_amount`): what the customer paid for one sale,
  before anything is subtracted. Always in that sale's own transaction
  currency (see "Currency" below).
- **Refund amount** (`refunded_amount`): how much of a sale's *net* amount
  has been returned to the customer — zero/absent for a never-refunded sale,
  up to the full net amount for a fully refunded one.
- **Net revenue** ("revenue after refunds", `net_revenue_current_period` on
  the dashboard): `gross_amount - vat_amount - processing_fee -
  refunded_amount` (floored at zero) — see `Sale.revenue_contribution()`,
  the one place this is computed. This is **never called "profit" or
  "income"** in this app: profit would require the business's own expenses,
  which this app does not track — see the dashboard's own explanatory copy.
- **VAT** (`vat_amount`) / **processing fees** (`processing_fee`): held for
  the tax authority / kept by the payment provider respectively — neither is
  business revenue. A sale with these left `null` (unknown, e.g. a payment
  provider that didn't report a breakdown) is summed as contributing 0 to
  the VAT/fee *totals* below (the only way to aggregate an unknown value at
  all), but that sale's own gross amount is never reduced or reinterpreted
  because of it — an unknown VAT is not the same claim as a confirmed-zero
  VAT, and this distinction matters most at the single-sale level, visible
  on the sale itself, not just in an aggregate total.
- **Successful sale**: `status == 'succeeded'` OR `status ==
  'partially_refunded'` — a partial refund does not retroactively make the
  sale "unsuccessful", it succeeded and was later partly returned. A fully
  `refunded` sale is excluded from this count (and from gross/VAT/fees):
  its revenue was fully reversed. `pending`/`failed` sales never count.
- **Gross revenue / VAT collected / processing fees / average transaction
  value**: all computed over that exact same "successful" set (succeeded +
  partially refunded) for the *selected period* — never a narrower or wider
  set than the sale count they're reported alongside, so these cards can
  never show a nonzero net revenue next to a zero sale count.
- **Currency**: every monetary total on this page is grouped *by the
  transaction currency of the sales it's built from* (see
  app.domain.demo_business — this business's own reporting currency is ILS,
  but a sale can be charged in ILS, USD, or EUR, and currency is never the
  same thing as tax jurisdiction). ILS, USD, and EUR amounts are never added
  together into one number; each total is a list of one {currency, amount}
  entry per currency actually present — a single-currency dataset naturally
  produces a one-element list. There is no live exchange-rate conversion in
  this phase.
- **Reporting period**: the dashboard accepts a named period
  (this_month/previous_month/last_3_months/last_6_months/this_year) or an
  explicit custom date range — see `resolve_period` — always anchored to
  `app.domain.business_time`'s business-calendar "today" (Asia/Jerusalem),
  never the server process's own OS timezone or a bare UTC date. A sale's
  period is always its *original occurrence* (`occurred_at`), including for
  refunds: a refund reduces the revenue of the period the sale happened in,
  not the period the refund itself was recorded, because `Sale` does not
  yet persist a separate refund timestamp — a documented limitation, not a
  silent assumption. The "needs attention" counts
  (pending_documents_count/document_failures_count/failed_payments_count/
  refunds_needing_attention_count/incomplete_details_count) are the one
  exception: they describe current outstanding operational state, so they
  are deliberately NOT scoped to the selected period.
- **Comparison period**: "the immediately preceding period of the same
  kind" — the previous calendar month for `this_month`, the 3 calendar
  months before that for `last_3_months`, the same year-to-date range one
  year earlier for `this_year`, and (for `custom`) the immediately
  preceding range of the same number of days.
"""

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.business_time import business_today
from app.domain.demo_business import DEMO_REPORTING_CURRENCY
from app.models.sale import DocumentStatus, Sale, SaleStatus
from app.schemas.dashboard import (
    CurrencyAmount,
    DashboardPeriodInfo,
    DashboardPeriodName,
    DashboardStats,
    PeriodComparison,
    RevenueTrendPoint,
    TopService,
    TrendGranularity,
)
from app.schemas.sale import sale_to_read

TWO_PLACES = Decimal("0.01")
RECENT_SALES_LIMIT = 5


class InvalidDashboardPeriodError(ValueError):
    """Raised when `period='custom'` is requested without both
    `custom_start` and `custom_end`, or when `custom_end` precedes
    `custom_start`."""


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _safe_date(year: int, month: int, day: int) -> date:
    """Clamps `day` to the last valid day of `year`-`month` — used for the
    year-over-year comparison date, so Mar 1 "today" comparing against a
    non-leap previous year doesn't crash on Feb 29."""
    last_day = monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _to_datetime_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, datetime.min.time()), datetime(
        end.year, end.month, end.day, 23, 59, 59, 999999
    )


class _PeriodBounds:
    __slots__ = ("start", "end", "previous_start", "previous_end", "granularity")

    def __init__(self, start: date, end: date, previous_start: date, previous_end: date, granularity: TrendGranularity):
        self.start = start
        self.end = end
        self.previous_start = previous_start
        self.previous_end = previous_end
        self.granularity = granularity


def resolve_period(
    period: DashboardPeriodName,
    custom_start: date | None,
    custom_end: date | None,
    today: date,
) -> _PeriodBounds:
    if period == "this_month":
        start, end = _month_bounds(today.year, today.month)
        py, pm = _add_months(today.year, today.month, -1)
        prev_start, prev_end = _month_bounds(py, pm)
        return _PeriodBounds(start, end, prev_start, prev_end, "day")

    if period == "previous_month":
        py, pm = _add_months(today.year, today.month, -1)
        start, end = _month_bounds(py, pm)
        ppy, ppm = _add_months(py, pm, -1)
        prev_start, prev_end = _month_bounds(ppy, ppm)
        return _PeriodBounds(start, end, prev_start, prev_end, "day")

    if period in ("last_3_months", "last_6_months"):
        span = 3 if period == "last_3_months" else 6
        start_y, start_m = _add_months(today.year, today.month, -(span - 1))
        start = date(start_y, start_m, 1)
        end = date(today.year, today.month, monthrange(today.year, today.month)[1])
        prev_end_y, prev_end_m = _add_months(start_y, start_m, -1)
        prev_end = date(prev_end_y, prev_end_m, monthrange(prev_end_y, prev_end_m)[1])
        prev_start_y, prev_start_m = _add_months(start_y, start_m, -span)
        prev_start = date(prev_start_y, prev_start_m, 1)
        granularity: TrendGranularity = "week" if period == "last_3_months" else "month"
        return _PeriodBounds(start, end, prev_start, prev_end, granularity)

    if period == "this_year":
        start = date(today.year, 1, 1)
        end = today
        prev_start = date(today.year - 1, 1, 1)
        prev_end = _safe_date(today.year - 1, today.month, today.day)
        return _PeriodBounds(start, end, prev_start, prev_end, "month")

    if period == "custom":
        if custom_start is None or custom_end is None:
            raise InvalidDashboardPeriodError("custom_start and custom_end are both required when period=custom")
        if custom_end < custom_start:
            raise InvalidDashboardPeriodError("custom_end must not be before custom_start")
        span_days = (custom_end - custom_start).days + 1
        prev_end = custom_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span_days - 1)
        if span_days <= 31:
            granularity = "day"
        elif span_days <= 120:
            granularity = "week"
        else:
            granularity = "month"
        return _PeriodBounds(custom_start, custom_end, prev_start, prev_end, granularity)

    raise InvalidDashboardPeriodError(f"unknown period: {period!r}")  # pragma: no cover - Literal-guarded by FastAPI


def _trend_buckets(start: date, end: date, granularity: TrendGranularity) -> list[tuple[date, date]]:
    buckets: list[tuple[date, date]] = []
    if granularity == "day":
        current = start
        while current <= end:
            buckets.append((current, current))
            current += timedelta(days=1)
    elif granularity == "week":
        current = start
        while current <= end:
            bucket_end = min(current + timedelta(days=6), end)
            buckets.append((current, bucket_end))
            current = bucket_end + timedelta(days=1)
    else:  # month
        year, month = start.year, start.month
        while date(year, month, 1) <= end:
            month_start, month_end = _month_bounds(year, month)
            buckets.append((max(month_start, start), min(month_end, end)))
            year, month = _add_months(year, month, 1)
    return buckets


def _succeeded_or_partially_refunded_sales(db: Session, start: datetime, end: datetime) -> list[Sale]:
    stmt = select(Sale).where(
        Sale.occurred_at >= start,
        Sale.occurred_at <= end,
        Sale.status.in_([SaleStatus.SUCCEEDED, SaleStatus.PARTIALLY_REFUNDED]),
    )
    return list(db.scalars(stmt).all())


def _sum_by_currency(sales: list[Sale], value_fn) -> dict[str, Decimal]:
    """Sums `value_fn(sale)` per `sale.currency` — the one place every
    dashboard total groups by currency instead of summing across them."""
    totals: dict[str, Decimal] = {}
    for sale in sales:
        totals[sale.currency] = totals.get(sale.currency, Decimal("0")) + value_fn(sale)
    return {currency: _round_money(total) for currency, total in totals.items()}


def _currency_sort_key(currency: str) -> tuple[bool, str]:
    # The business's own reporting currency (ILS) sorts first when present;
    # everything else follows alphabetically — a stable, readable order, not
    # an implied priority for the underlying financial data.
    return (currency != DEMO_REPORTING_CURRENCY, currency)


def _as_currency_amounts(totals: dict[str, Decimal]) -> list[CurrencyAmount]:
    return [
        CurrencyAmount(currency=currency, amount=amount)
        for currency, amount in sorted(totals.items(), key=lambda item: _currency_sort_key(item[0]))
    ]


def _net_revenue_by_currency(db: Session, start: datetime, end: datetime) -> dict[str, Decimal]:
    sales = _succeeded_or_partially_refunded_sales(db, start, end)
    return _sum_by_currency(sales, lambda s: s.revenue_contribution())


def _comparison(current: dict[str, Decimal], previous: dict[str, Decimal]) -> list[PeriodComparison]:
    """A zero (or absent) previous-period baseline can never produce an
    honest percentage for that currency (any nonzero current value would be
    a mathematically undefined/infinite "increase") — reported as `None`
    for both percentage and amount, never a fabricated figure."""
    result: list[PeriodComparison] = []
    for currency in sorted(set(current) | set(previous), key=_currency_sort_key):
        prev_amount = previous.get(currency, Decimal("0"))
        curr_amount = current.get(currency, Decimal("0"))
        if prev_amount > 0:
            ratio = (curr_amount - prev_amount) / prev_amount * Decimal(100)
            result.append(
                PeriodComparison(
                    currency=currency,
                    percentage_change=float(ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                    amount_change=_round_money(curr_amount - prev_amount),
                )
            )
        else:
            result.append(PeriodComparison(currency=currency, percentage_change=None, amount_change=None))
    return result


def build_dashboard_stats(
    db: Session,
    *,
    period: DashboardPeriodName = "this_month",
    custom_start: date | None = None,
    custom_end: date | None = None,
    today: date | None = None,
) -> DashboardStats:
    # Never the server's OS timezone or a bare UTC date — see
    # app.domain.business_time for why that distinction matters here.
    today = today or business_today()
    bounds = resolve_period(period, custom_start, custom_end, today)
    current_start, current_end = _to_datetime_bounds(bounds.start, bounds.end)
    prev_start, prev_end = _to_datetime_bounds(bounds.previous_start, bounds.previous_end)

    net_revenue_current = _net_revenue_by_currency(db, current_start, current_end)
    net_revenue_previous = _net_revenue_by_currency(db, prev_start, prev_end)
    comparison = _comparison(net_revenue_current, net_revenue_previous)

    # Gross revenue / VAT collected / processing fees / successful count all
    # share the exact same "successful" set as net revenue above (succeeded
    # + partially refunded) — this is what keeps these cards from ever
    # showing a nonzero net revenue next to a zero sale count.
    successful_current = _succeeded_or_partially_refunded_sales(db, current_start, current_end)
    gross_revenue_by_currency = _sum_by_currency(successful_current, lambda s: s.gross_amount)
    vat_collected_by_currency = _sum_by_currency(successful_current, lambda s: s.vat_amount or Decimal("0"))
    processing_fees_by_currency = _sum_by_currency(
        successful_current, lambda s: s.processing_fee or Decimal("0")
    )
    successful_sales_count = len(successful_current)

    counts_by_currency: dict[str, int] = {}
    for sale in successful_current:
        counts_by_currency[sale.currency] = counts_by_currency.get(sale.currency, 0) + 1
    average_transaction_value_by_currency = {
        currency: _round_money(gross_revenue_by_currency[currency] / count)
        for currency, count in counts_by_currency.items()
    }

    service_totals: dict[tuple[str, str], Decimal] = {}
    service_counts: dict[tuple[str, str], int] = {}
    for sale in successful_current:
        key = (sale.service_name, sale.currency)
        service_totals[key] = service_totals.get(key, Decimal("0")) + sale.gross_amount
        service_counts[key] = service_counts.get(key, 0) + 1
    top_services = [
        TopService(
            service_name=name,
            currency=currency,
            total=_round_money(total),
            count=service_counts[(name, currency)],
            percentage_of_revenue=(
                float((total / gross_revenue_by_currency[currency] * 100).quantize(Decimal("0.1")))
                if gross_revenue_by_currency.get(currency)
                else 0.0
            ),
        )
        for (name, currency), total in service_totals.items()
    ]
    top_services.sort(key=lambda item: item.total, reverse=True)

    # Trend buckets cover the selected period at the resolved granularity.
    # Two passes, same reasoning as before: first collect each bucket's
    # per-currency totals, then fill every bucket with a zero point for any
    # currency that appears in ANY bucket in the window — so a trend LINE
    # stays continuous rather than jumping straight from bucket to bucket
    # with gaps. A currency that never appears in the whole window gets no
    # line at all, and currencies are still never combined.
    buckets = _trend_buckets(bounds.start, bounds.end, bounds.granularity)
    bucket_data: list[tuple[date, dict[str, Decimal], dict[str, Decimal]]] = []
    currencies_in_window: set[str] = set()
    for bucket_start, bucket_end in buckets:
        b_start, b_end = _to_datetime_bounds(bucket_start, bucket_end)
        bucket_sales = _succeeded_or_partially_refunded_sales(db, b_start, b_end)
        gross_by_currency = _sum_by_currency(bucket_sales, lambda s: s.gross_amount)
        net_by_currency = _sum_by_currency(bucket_sales, lambda s: s.revenue_contribution())
        bucket_data.append((bucket_start, gross_by_currency, net_by_currency))
        currencies_in_window.update(gross_by_currency)
        currencies_in_window.update(net_by_currency)

    revenue_trend: list[RevenueTrendPoint] = []
    for bucket_start, gross_by_currency, net_by_currency in bucket_data:
        for currency in sorted(currencies_in_window, key=_currency_sort_key):
            revenue_trend.append(
                RevenueTrendPoint(
                    period_start=bucket_start,
                    currency=currency,
                    gross_total=gross_by_currency.get(currency, Decimal("0.00")),
                    net_total=net_by_currency.get(currency, Decimal("0.00")),
                )
            )

    recent = db.scalars(
        select(Sale).order_by(Sale.occurred_at.desc(), Sale.created_at.desc()).limit(RECENT_SALES_LIMIT)
    ).all()
    recent_sales = [sale_to_read(sale) for sale in recent]

    refunded_current = list(
        db.scalars(
            select(Sale).where(
                Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]),
                Sale.occurred_at >= current_start,
                Sale.occurred_at <= current_end,
            )
        ).all()
    )
    refunds_total_by_currency = _sum_by_currency(refunded_current, lambda s: s.refunded_amount or Decimal("0"))

    # --- "Needs attention" — current operational state, not period-scoped ---
    pending_documents_count = db.scalar(
        select(func.count(Sale.id)).where(
            Sale.status == SaleStatus.SUCCEEDED, Sale.document_status == DocumentStatus.PENDING
        )
    ) or 0
    # Mirrors app/services/exception_center.py's grace-period rule exactly,
    # so this card's count never disagrees with the actual Exception Center.
    document_grace_cutoff = datetime.utcnow() - timedelta(hours=get_settings().document_match_grace_period_hours)
    document_failures_count = db.scalar(
        select(func.count(Sale.id)).where(
            or_(
                Sale.document_status == DocumentStatus.FAILED,
                and_(Sale.document_status == DocumentStatus.WAITING_AUTOMATIC, Sale.occurred_at < document_grace_cutoff),
            )
        )
    ) or 0
    failed_payments_count = db.scalar(
        select(func.count(Sale.id)).where(Sale.status == SaleStatus.FAILED)
    ) or 0
    refunds_needing_attention_count = db.scalar(
        select(func.count(Sale.id)).where(Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]))
    ) or 0
    incomplete_details_count = db.scalar(
        select(func.count(Sale.id)).where(Sale.customer_contact.is_(None))
    ) or 0

    return DashboardStats(
        period=DashboardPeriodInfo(
            period=period,
            start_date=bounds.start,
            end_date=bounds.end,
            previous_start_date=bounds.previous_start,
            previous_end_date=bounds.previous_end,
            trend_granularity=bounds.granularity,
        ),
        net_revenue_current_period=_as_currency_amounts(net_revenue_current),
        net_revenue_previous_period=_as_currency_amounts(net_revenue_previous),
        comparison=comparison,
        successful_sales_count=successful_sales_count,
        average_transaction_value=_as_currency_amounts(average_transaction_value_by_currency),
        gross_revenue=_as_currency_amounts(gross_revenue_by_currency),
        vat_collected=_as_currency_amounts(vat_collected_by_currency),
        processing_fees=_as_currency_amounts(processing_fees_by_currency),
        refunds_total=_as_currency_amounts(refunds_total_by_currency),
        recent_sales=recent_sales,
        top_services=top_services,
        revenue_trend=revenue_trend,
        pending_documents_count=pending_documents_count,
        document_failures_count=document_failures_count,
        failed_payments_count=failed_payments_count,
        refunds_needing_attention_count=refunds_needing_attention_count,
        incomplete_details_count=incomplete_details_count,
    )
