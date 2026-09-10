"""Dashboard aggregates — the single source of truth for what each number on
the dashboard means. `app/services/assistant/tools.py` mirrors these exact
definitions so the dashboard and the AI assistant can never disagree for the
same period.

Metric definitions:
- **Gross amount** (`gross_amount`): what the customer paid for one sale,
  before anything is subtracted.
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
- **Reporting period**: every "this month" / "previous month" figure uses
  calendar-month boundaries computed from the server's local date (there is
  currently no per-business timezone setting — see "What's next"). A sale's
  period is always its *original occurrence* (`occurred_at`), including for
  refunds: a refund reduces the revenue of the month the sale happened in,
  not the month the refund itself was recorded, because `Sale` does not yet
  persist a separate refund timestamp — a documented limitation, not a
  silent assumption.
- **Currency**: every total on this page assumes a single operating
  currency. Sales in different currencies are summed together with no
  conversion — safe today because every sale in this app is created in the
  business's own default currency, but a real multi-currency deployment
  would need an explicit conversion policy before these sums stay
  meaningful (see "What's next").
"""

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sale import DocumentStatus, Sale, SaleStatus
from app.schemas.dashboard import DashboardStats, RevenueTrendPoint, TopService
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


def _net_revenue_between(db: Session, start: datetime, end: datetime) -> Decimal:
    sales = _succeeded_or_partially_refunded_sales(db, start, end)
    return _round_money(sum((s.revenue_contribution() for s in sales), Decimal("0")))


def build_dashboard_stats(db: Session, today: date | None = None) -> DashboardStats:
    today = today or date.today()
    current_start, current_end = _month_bounds(today.year, today.month)
    prev_year, prev_month = _previous_month(today.year, today.month)
    prev_start, prev_end = _month_bounds(prev_year, prev_month)

    net_revenue_this_month = _net_revenue_between(db, current_start, current_end)
    net_revenue_previous_month = _net_revenue_between(db, prev_start, prev_end)

    # A zero previous-month baseline can never produce an honest percentage
    # (any nonzero current value would be a mathematically undefined /
    # infinite "increase") — reported as no comparison at all, never a
    # fabricated 100%. The frontend shows "No comparison baseline" for this.
    if net_revenue_previous_month > 0:
        ratio = (net_revenue_this_month - net_revenue_previous_month) / net_revenue_previous_month * Decimal(100)
        percentage_change = float(ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    else:
        percentage_change = None

    # Gross revenue / VAT collected / processing fees / successful count all
    # share the exact same "successful" set as net revenue above (succeeded
    # + partially refunded) — this is what keeps these cards from ever
    # showing a nonzero net revenue next to a zero sale count.
    successful_this_month = _succeeded_or_partially_refunded_sales(db, current_start, current_end)
    gross_revenue = _round_money(sum((s.gross_amount for s in successful_this_month), Decimal("0")))
    vat_collected = _round_money(sum((s.vat_amount or Decimal("0") for s in successful_this_month), Decimal("0")))
    processing_fees = _round_money(
        sum((s.processing_fee or Decimal("0") for s in successful_this_month), Decimal("0"))
    )
    successful_sales_count = len(successful_this_month)
    average_transaction_value = (
        _round_money(gross_revenue / successful_sales_count) if successful_sales_count > 0 else None
    )

    service_totals: dict[str, Decimal] = {}
    service_counts: dict[str, int] = {}
    for sale in successful_this_month:
        service_totals[sale.service_name] = service_totals.get(sale.service_name, Decimal("0")) + sale.gross_amount
        service_counts[sale.service_name] = service_counts.get(sale.service_name, 0) + 1
    top_services = [
        TopService(service_name=name, total=_round_money(total), count=service_counts[name])
        for name, total in service_totals.items()
    ]
    top_services.sort(key=lambda item: item.total, reverse=True)

    revenue_trend: list[RevenueTrendPoint] = []
    for offset in range(TREND_MONTHS - 1, -1, -1):
        year, month = _shift_months_back(today.year, today.month, offset)
        start, end = _month_bounds(year, month)
        revenue_trend.append(RevenueTrendPoint(period_start=date(year, month, 1), total=_net_revenue_between(db, start, end)))

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
    pending_documents_total = _round_money(sum((s.net_amount for s in pending_documents), Decimal("0")))

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
    refunds_total = _round_money(sum((s.refunded_amount or Decimal("0") for s in refunded_sales), Decimal("0")))

    return DashboardStats(
        net_revenue_this_month=net_revenue_this_month,
        net_revenue_previous_month=net_revenue_previous_month,
        percentage_change=percentage_change,
        successful_sales_count=successful_sales_count,
        average_transaction_value=average_transaction_value,
        gross_revenue=gross_revenue,
        vat_collected=vat_collected,
        processing_fees=processing_fees,
        recent_sales=recent_sales,
        top_services=top_services,
        revenue_trend=revenue_trend,
        pending_documents_count=pending_documents_count,
        pending_documents_total=pending_documents_total,
        document_failures_count=document_failures_count,
        failed_payments_count=failed_payments_count,
        refunds_count=refunds_count,
        refunds_total=refunds_total,
    )
