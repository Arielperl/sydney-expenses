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
- **Net revenue** / "revenue after refunds": `net_amount - refunded_amount`
  (floored at zero), where `net_amount = gross_amount - vat_amount -
  processing_fee` was already computed at sale-creation time. This is what
  every "revenue" figure on the dashboard and in the assistant means — see
  `Sale.revenue_contribution()`, the one place this is computed. It is
  **never called "profit"**: profit would require the business's own
  expenses, which this app does not track.
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
  partially refunded) for the period — never a narrower or wider set than
  the sale count they're reported alongside, so these cards can never show
  a nonzero net revenue next to a zero sale count.
- **Currency**: every monetary total on this page is grouped *by the
  transaction currency of the sales it's built from* (see
  app.domain.demo_business — this business's own reporting currency is ILS,
  but a sale can be charged in ILS, USD, or EUR, and currency is never the
  same thing as tax jurisdiction). ILS, USD, and EUR amounts are never added
  together into one number; each total is a list of one {currency, amount}
  entry per currency actually present — a single-currency dataset naturally
  produces a one-element list. There is no live exchange-rate conversion in
  this phase: a future implementation adding one has a documented extension
  point (`Sale.currency` plus this per-currency grouping), not a rewrite.
- **Reporting period**: every "this month" / "previous month" figure uses
  calendar-month boundaries computed from the server's local date (there is
  currently no per-business timezone setting — see "What's next"). A sale's
  period is always its *original occurrence* (`occurred_at`), including for
  refunds: a refund reduces the revenue of the month the sale happened in,
  not the month the refund itself was recorded, because `Sale` does not yet
  persist a separate refund timestamp — a documented limitation, not a
  silent assumption.
"""

from calendar import monthrange
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.demo_business import DEMO_REPORTING_CURRENCY
from app.models.sale import DocumentStatus, Sale, SaleStatus
from app.schemas.dashboard import CurrencyAmount, DashboardStats, RevenueTrendPoint, TopService
from app.schemas.sale import sale_to_read

TWO_PLACES = Decimal("0.01")
TREND_MONTHS = 6


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    last_day = monthrange(year, month)[1]
    start = datetime(year, month, 1)
    end = datetime(year, month, last_day, 23, 59, 59, 999999)
    return start, end


def _previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _shift_months_back(year: int, month: int, count: int) -> tuple[int, int]:
    for _ in range(count):
        year, month = _previous_month(year, month)
    return year, month


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


def _percentage_change_by_currency(
    current: dict[str, Decimal], previous: dict[str, Decimal]
) -> dict[str, float | None]:
    """A zero previous-period baseline can never produce an honest
    percentage for that currency (any nonzero current value would be a
    mathematically undefined/infinite "increase") — reported as `None`
    (no comparison), never a fabricated 100%."""
    result: dict[str, float | None] = {}
    for currency in sorted(set(current) | set(previous), key=_currency_sort_key):
        prev_amount = previous.get(currency, Decimal("0"))
        curr_amount = current.get(currency, Decimal("0"))
        if prev_amount > 0:
            ratio = (curr_amount - prev_amount) / prev_amount * Decimal(100)
            result[currency] = float(ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        else:
            result[currency] = None
    return result


def build_dashboard_stats(db: Session, today: date | None = None) -> DashboardStats:
    today = today or date.today()
    current_start, current_end = _month_bounds(today.year, today.month)
    prev_year, prev_month = _previous_month(today.year, today.month)
    prev_start, prev_end = _month_bounds(prev_year, prev_month)

    net_revenue_this_month = _net_revenue_by_currency(db, current_start, current_end)
    net_revenue_previous_month = _net_revenue_by_currency(db, prev_start, prev_end)
    percentage_change = _percentage_change_by_currency(net_revenue_this_month, net_revenue_previous_month)

    # Gross revenue / VAT collected / processing fees / successful count all
    # share the exact same "successful" set as net revenue above (succeeded
    # + partially refunded) — this is what keeps these cards from ever
    # showing a nonzero net revenue next to a zero sale count.
    successful_this_month = _succeeded_or_partially_refunded_sales(db, current_start, current_end)
    gross_revenue_by_currency = _sum_by_currency(successful_this_month, lambda s: s.gross_amount)
    vat_collected_by_currency = _sum_by_currency(successful_this_month, lambda s: s.vat_amount or Decimal("0"))
    processing_fees_by_currency = _sum_by_currency(
        successful_this_month, lambda s: s.processing_fee or Decimal("0")
    )
    successful_sales_count = len(successful_this_month)

    counts_by_currency: dict[str, int] = {}
    for sale in successful_this_month:
        counts_by_currency[sale.currency] = counts_by_currency.get(sale.currency, 0) + 1
    average_transaction_value_by_currency = {
        currency: _round_money(gross_revenue_by_currency[currency] / count)
        for currency, count in counts_by_currency.items()
    }

    service_totals: dict[tuple[str, str], Decimal] = {}
    service_counts: dict[tuple[str, str], int] = {}
    for sale in successful_this_month:
        key = (sale.service_name, sale.currency)
        service_totals[key] = service_totals.get(key, Decimal("0")) + sale.gross_amount
        service_counts[key] = service_counts.get(key, 0) + 1
    top_services = [
        TopService(service_name=name, currency=currency, total=_round_money(total), count=service_counts[(name, currency)])
        for (name, currency), total in service_totals.items()
    ]
    top_services.sort(key=lambda item: item.total, reverse=True)

    # Two passes: first collect each month's per-currency revenue, then fill
    # every month with a zero point for any currency that appears in ANY of
    # the six months — so a trend LINE stays continuous (six connected
    # points) for a currency that had at least one sale in the window,
    # rather than the line jumping straight from month to month with gaps.
    # A currency that never appears in the whole window gets no line at all
    # (there's nothing to draw), and currencies are still never combined.
    months: list[tuple[date, dict[str, Decimal]]] = []
    currencies_in_window: set[str] = set()
    for offset in range(TREND_MONTHS - 1, -1, -1):
        year, month = _shift_months_back(today.year, today.month, offset)
        start, end = _month_bounds(year, month)
        by_currency = _net_revenue_by_currency(db, start, end)
        months.append((date(year, month, 1), by_currency))
        currencies_in_window.update(by_currency)

    revenue_trend: list[RevenueTrendPoint] = []
    for period_start, by_currency in months:
        for currency in sorted(currencies_in_window, key=_currency_sort_key):
            total = by_currency.get(currency, Decimal("0.00"))
            revenue_trend.append(RevenueTrendPoint(period_start=period_start, currency=currency, total=total))

    recent = db.scalars(select(Sale).order_by(Sale.occurred_at.desc(), Sale.created_at.desc()).limit(5)).all()
    recent_sales = [sale_to_read(sale) for sale in recent]

    pending_documents = list(
        db.scalars(
            select(Sale).where(
                Sale.status == SaleStatus.SUCCEEDED, Sale.document_status == DocumentStatus.PENDING
            )
        ).all()
    )
    pending_documents_count = len(pending_documents)
    pending_documents_total_by_currency = _sum_by_currency(pending_documents, lambda s: s.net_amount)

    document_failures_count = db.scalar(
        select(func.count(Sale.id)).where(Sale.document_status == DocumentStatus.FAILED)
    ) or 0

    failed_payments_count = db.scalar(
        select(func.count(Sale.id)).where(
            Sale.status == SaleStatus.FAILED,
            Sale.occurred_at >= current_start,
            Sale.occurred_at <= current_end,
        )
    ) or 0

    refunded_sales = list(
        db.scalars(
            select(Sale).where(Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]))
        ).all()
    )
    refunds_count = len(refunded_sales)
    refunds_total_by_currency = _sum_by_currency(refunded_sales, lambda s: s.refunded_amount or Decimal("0"))

    return DashboardStats(
        net_revenue_this_month=_as_currency_amounts(net_revenue_this_month),
        net_revenue_previous_month=_as_currency_amounts(net_revenue_previous_month),
        percentage_change=percentage_change,
        successful_sales_count=successful_sales_count,
        average_transaction_value=_as_currency_amounts(average_transaction_value_by_currency),
        gross_revenue=_as_currency_amounts(gross_revenue_by_currency),
        vat_collected=_as_currency_amounts(vat_collected_by_currency),
        processing_fees=_as_currency_amounts(processing_fees_by_currency),
        recent_sales=recent_sales,
        top_services=top_services,
        revenue_trend=revenue_trend,
        pending_documents_count=pending_documents_count,
        pending_documents_total=_as_currency_amounts(pending_documents_total_by_currency),
        document_failures_count=document_failures_count,
        failed_payments_count=failed_payments_count,
        refunds_count=refunds_count,
        refunds_total=_as_currency_amounts(refunds_total_by_currency),
    )
