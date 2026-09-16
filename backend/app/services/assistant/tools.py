"""Read-only query functions the AI assistant can call — never raw SQL, never
a write path. Each function takes the request's DB session plus the
JSON-serializable arguments the OpenAI tool-calling API sends, and returns a
plain, JSON-serializable dict: either the real result, or {"error": "..."}
for a bad argument (never raised — a raised exception would abort the whole
chat turn; an error dict instead becomes a tool result the model can react
to, e.g. by asking the user to clarify).

Every total here is *revenue*, computed via `Sale.revenue_contribution()`
(zero for pending/failed/fully-refunded sales, net-of-refund for a partial
refund) — never a raw sum of `gross_amount`, which would silently include
VAT, processing fees, and refunded money as if they were the business's own
revenue.

A "successful" sale, here and everywhere else in this file, means status
`succeeded` OR `partially_refunded` — the exact same definition
`app/services/dashboard_service.py` uses, and for the same reason: a partial
refund doesn't retroactively make the sale not have happened. Every one of
gross revenue / VAT collected / processing fees / sale count below shares
this one definition, so the dashboard and the assistant can never disagree
for the same period. See `dashboard_service.py`'s module docstring for the
full metric definitions (net vs. gross vs. profit, refund-by-original-date).

Currency safety: every monetary value this module returns is grouped by
`Sale.currency` and labeled with it explicitly — never a bare number with no
currency attached, and never a sum across different currencies. A tool
called over a single-currency dataset naturally returns a one-element
breakdown; a mixed-currency dataset returns one entry per currency. This
exists specifically so the language model never has to guess a currency
symbol (see the system prompt in orchestrator.py) — it can only ever display
the currency a tool actually returned.

TOOL_DEFINITIONS is the JSON-schema list handed to the model; TOOL_FUNCTIONS
maps each tool name to its implementation — the single source of truth the
orchestrator's tool-calling loop dispatches through, so a tool can never be
invoked under a name or shape the model wasn't actually given.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.sale import DocumentStatus, Sale, SaleStatus

_MONEY_PLACES = Decimal("0.01")


def _round_money(value: Decimal) -> str:
    return str(value.quantize(_MONEY_PLACES, rounding=ROUND_HALF_UP))


def _parse_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value!r} (expected YYYY-MM-DD)") from exc


def _end_of_day_exclusive(value: date) -> datetime:
    """`end_date` is a date-only boundary (e.g. 'this month' -> today's
    date), but `Sale.occurred_at` is a full timestamp — comparing it with
    `<=` against midnight on that date would silently exclude every sale
    that happened later the same day. Comparing with `<` against the start
    of the *next* day makes the whole end date inclusive, correctly."""
    return datetime.combine(value, datetime.min.time()) + timedelta(days=1)


def _filtered_sales(
    db: Session, start_date: str | None, end_date: str | None, *, only_succeeded: bool = True
) -> list[Sale]:
    stmt = select(Sale)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if start is not None:
        stmt = stmt.where(Sale.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(Sale.occurred_at < _end_of_day_exclusive(end))
    if only_succeeded:
        stmt = stmt.where(Sale.status.in_([SaleStatus.SUCCEEDED, SaleStatus.PARTIALLY_REFUNDED]))
    return list(db.scalars(stmt).all())


def _sum_by_currency(sales: list[Sale], value_fn, *, amount_key: str) -> list[dict]:
    """Groups `value_fn(sale)` by `sale.currency` and returns one row per
    currency actually present — `[{"currency": "ILS", amount_key: "150.00",
    "count": 2}, ...]`, sorted by currency code. An empty input returns an
    empty list, never a bare "0" with no currency to attach it to."""
    totals: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    for sale in sales:
        totals[sale.currency] = totals.get(sale.currency, Decimal("0")) + value_fn(sale)
        counts[sale.currency] = counts.get(sale.currency, 0) + 1
    return [
        {"currency": currency, amount_key: _round_money(totals[currency]), "count": counts[currency]}
        for currency in sorted(totals)
    ]


_ANALYTICS_STATUS_GROUPS = {
    "successful": {SaleStatus.SUCCEEDED, SaleStatus.PARTIALLY_REFUNDED},
    "pending": {SaleStatus.PENDING},
    "failed": {SaleStatus.FAILED},
    "refunded": {SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED},
}

_ROW_SORT_VALUE: dict[str, Callable[[Sale], Decimal | datetime]] = {
    "occurred_at": lambda sale: sale.occurred_at,
    "gross_amount": lambda sale: sale.gross_amount,
    "net_revenue": lambda sale: sale.revenue_contribution(),
    "vat_amount": lambda sale: sale.vat_amount or Decimal("0"),
    "processing_fee": lambda sale: sale.processing_fee or Decimal("0"),
    "refunded_amount": lambda sale: sale.refunded_amount or Decimal("0"),
}


def _analytics_sales(
    db: Session,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = "successful",
    customer_query: str | None = None,
    service_query: str | None = None,
    payment_method: str | None = None,
    currency: str | None = None,
) -> list[Sale]:
    """Shared, bounded filter language for the assistant's general-purpose
    analytics tools. It deliberately exposes domain filters rather than SQL:
    the model can ask useful new questions without ever constructing a query,
    naming a table, or escaping the request's business-scoped DB session."""
    if status not in {*_ANALYTICS_STATUS_GROUPS, "all"}:
        raise ValueError(f"invalid status: {status!r}")

    sales = _filtered_sales(db, start_date, end_date, only_succeeded=False)
    if status != "all":
        allowed_statuses = _ANALYTICS_STATUS_GROUPS[status]
        sales = [sale for sale in sales if sale.status in allowed_statuses]

    if customer_query:
        needle = customer_query.strip().casefold()
        sales = [sale for sale in sales if needle in sale.customer_name.casefold()]
    if service_query:
        needle = service_query.strip().casefold()
        sales = [sale for sale in sales if needle in sale.service_name.casefold()]
    if payment_method:
        wanted = payment_method.strip().casefold()
        sales = [sale for sale in sales if (sale.payment_method or "").casefold() == wanted]
    if currency:
        wanted_currency = currency.strip().upper()
        sales = [sale for sale in sales if sale.currency.upper() == wanted_currency]
    return sales


def _sale_row(sale: Sale) -> dict:
    return {
        "sale_id": sale.id,
        "customer_name": sale.customer_name,
        "service_name": sale.service_name,
        "occurred_at": sale.occurred_at.isoformat(),
        "status": sale.status.value,
        "payment_method": sale.payment_method,
        "currency": sale.currency,
        "gross_amount": _round_money(sale.gross_amount),
        "net_revenue": _round_money(sale.revenue_contribution()),
        "vat_amount": _round_money(sale.vat_amount or Decimal("0")),
        "processing_fee": _round_money(sale.processing_fee or Decimal("0")),
        "refunded_amount": _round_money(sale.refunded_amount or Decimal("0")),
    }


def query_sales(
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = "successful",
    customer_query: str | None = None,
    service_query: str | None = None,
    payment_method: str | None = None,
    currency: str | None = None,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
    limit: int = 10,
) -> dict:
    """Search and rank individual sales using a constrained query language.

    Results are partitioned by currency before ranking. This matters even for
    a seemingly simple question such as "largest sale": 1,500 ILS and 1,500
    USD cannot honestly compete for one global first place without an exchange
    rate, which this product intentionally does not guess.
    """
    if sort_by not in _ROW_SORT_VALUE:
        return {"error": f"invalid sort_by: {sort_by!r}"}
    if sort_order not in {"asc", "desc"}:
        return {"error": f"invalid sort_order: {sort_order!r}"}
    if not isinstance(limit, int) or not 1 <= limit <= 20:
        return {"error": "limit must be an integer between 1 and 20"}
    try:
        sales = _analytics_sales(
            db,
            start_date=start_date,
            end_date=end_date,
            status=status,
            customer_query=customer_query,
            service_query=service_query,
            payment_method=payment_method,
            currency=currency,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    grouped: dict[str, list[Sale]] = {}
    for sale in sales:
        grouped.setdefault(sale.currency, []).append(sale)

    reverse = sort_order == "desc"
    value_fn = _ROW_SORT_VALUE[sort_by]
    return {
        "sort_by": sort_by,
        "sort_order": sort_order,
        "sales_by_currency": [
            {
                "currency": currency_code,
                "sales": [
                    _sale_row(sale)
                    for sale in sorted(grouped[currency_code], key=value_fn, reverse=reverse)[:limit]
                ],
            }
            for currency_code in sorted(grouped)
        ],
    }


def _group_label(sale: Sale, group_by: str) -> str:
    if group_by == "customer":
        return sale.customer_name
    if group_by == "service":
        return sale.service_name
    if group_by == "payment_method":
        return sale.payment_method or "unknown"
    if group_by == "status":
        return sale.status.value
    if group_by == "day":
        return sale.occurred_at.date().isoformat()
    if group_by == "week":
        return _period_start(sale.occurred_at.date(), "week").isoformat()
    if group_by == "month":
        return _period_start(sale.occurred_at.date(), "month").isoformat()
    return "all"


def analyze_sales(
    db: Session,
    metric: str = "net_revenue",
    group_by: str = "none",
    start_date: str | None = None,
    end_date: str | None = None,
    status: str = "successful",
    customer_query: str | None = None,
    service_query: str | None = None,
    payment_method: str | None = None,
    currency: str | None = None,
    limit: int = 10,
) -> dict:
    """Aggregate sales by a safe, finite set of business dimensions.

    This is intentionally broad enough for questions the product team did not
    predict (top customer, average ticket, strongest weekday, payment-method
    mix) while remaining read-only and structurally incapable of arbitrary SQL.
    """
    valid_metrics = {
        "net_revenue",
        "gross_revenue",
        "vat_collected",
        "processing_fees",
        "refunded_amount",
        "average_net_revenue",
        "average_gross_amount",
        "sale_count",
    }
    valid_groups = {"none", "customer", "service", "payment_method", "status", "day", "week", "month"}
    if metric not in valid_metrics:
        return {"error": f"invalid metric: {metric!r}"}
    if group_by not in valid_groups:
        return {"error": f"invalid group_by: {group_by!r}"}
    if not isinstance(limit, int) or not 1 <= limit <= 50:
        return {"error": "limit must be an integer between 1 and 50"}
    effective_status = status
    if metric == "refunded_amount" and status == "successful":
        # A user asking for refunded money normally means all refunded and
        # partially-refunded sales. Requiring the model to remember an extra
        # status argument would make an otherwise valid question silently omit
        # full refunds.
        effective_status = "refunded"
    elif group_by == "status" and status == "successful":
        # A status breakdown is only meaningful across statuses unless the
        # caller deliberately supplied another explicit subset.
        effective_status = "all"

    try:
        sales = _analytics_sales(
            db,
            start_date=start_date,
            end_date=end_date,
            status=effective_status,
            customer_query=customer_query,
            service_query=service_query,
            payment_method=payment_method,
            currency=currency,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    if metric == "sale_count":
        counts: dict[str, int] = {}
        for sale in sales:
            label = _group_label(sale, group_by)
            counts[label] = counts.get(label, 0) + 1
        rows = [{"group": label, "value": value} for label, value in counts.items()]
        rows.sort(key=lambda row: (-row["value"], row["group"]))
        return {"metric": metric, "group_by": group_by, "results": rows[:limit]}

    value_functions: dict[str, Callable[[Sale], Decimal]] = {
        "net_revenue": lambda sale: sale.revenue_contribution(),
        "gross_revenue": lambda sale: sale.gross_amount,
        "vat_collected": lambda sale: sale.vat_amount or Decimal("0"),
        "processing_fees": lambda sale: sale.processing_fee or Decimal("0"),
        "refunded_amount": lambda sale: sale.refunded_amount or Decimal("0"),
        "average_net_revenue": lambda sale: sale.revenue_contribution(),
        "average_gross_amount": lambda sale: sale.gross_amount,
    }
    totals: dict[tuple[str, str], Decimal] = {}
    counts: dict[tuple[str, str], int] = {}
    value_fn = value_functions[metric]
    for sale in sales:
        key = (_group_label(sale, group_by), sale.currency)
        totals[key] = totals.get(key, Decimal("0")) + value_fn(sale)
        counts[key] = counts.get(key, 0) + 1

    is_average = metric.startswith("average_")
    rows = []
    for (label, currency_code), total in totals.items():
        count = counts[(label, currency_code)]
        value = total / count if is_average else total
        rows.append({"group": label, "currency": currency_code, "value": _round_money(value), "count": count})

    by_currency: dict[str, list[dict]] = {}
    for row in rows:
        by_currency.setdefault(row["currency"], []).append(row)
    limited: list[dict] = []
    for currency_code in sorted(by_currency):
        ranked = sorted(by_currency[currency_code], key=lambda row: (-Decimal(row["value"]), row["group"]))
        limited.extend(ranked[:limit])
    return {"metric": metric, "group_by": group_by, "results": limited}


def compare_sales_periods(
    db: Session,
    first_start_date: str,
    first_end_date: str,
    second_start_date: str,
    second_end_date: str,
    metric: str = "net_revenue",
    status: str = "successful",
    customer_query: str | None = None,
    service_query: str | None = None,
    payment_method: str | None = None,
    currency: str | None = None,
) -> dict:
    """Compare the same metric across two explicit inclusive date ranges.
    Percent change is computed here rather than by the language model, keeping
    arithmetic deterministic and making a zero baseline explicit."""
    metric_value: dict[str, Callable[[Sale], Decimal]] = {
        "net_revenue": lambda sale: sale.revenue_contribution(),
        "gross_revenue": lambda sale: sale.gross_amount,
        "vat_collected": lambda sale: sale.vat_amount or Decimal("0"),
        "processing_fees": lambda sale: sale.processing_fee or Decimal("0"),
        "refunded_amount": lambda sale: sale.refunded_amount or Decimal("0"),
    }
    if metric not in {*metric_value, "sale_count"}:
        return {"error": f"invalid metric: {metric!r}"}

    def period_sales(start_date: str, end_date: str) -> list[Sale]:
        effective_status = "refunded" if metric == "refunded_amount" and status == "successful" else status
        return _analytics_sales(
            db,
            start_date=start_date,
            end_date=end_date,
            status=effective_status,
            customer_query=customer_query,
            service_query=service_query,
            payment_method=payment_method,
            currency=currency,
        )

    try:
        first = period_sales(first_start_date, first_end_date)
        second = period_sales(second_start_date, second_end_date)
    except ValueError as exc:
        return {"error": str(exc)}

    if metric == "sale_count":
        first_value = Decimal(len(first))
        second_value = Decimal(len(second))
        change = None if first_value == 0 else _round_money((second_value - first_value) / first_value * 100)
        return {
            "metric": metric,
            "first": len(first),
            "second": len(second),
            "change_percent": change,
        }

    value_fn = metric_value[metric]
    first_totals = {row["currency"]: Decimal(row["value"]) for row in _analytics_totals(first, value_fn)}
    second_totals = {row["currency"]: Decimal(row["value"]) for row in _analytics_totals(second, value_fn)}
    rows = []
    for currency_code in sorted(set(first_totals) | set(second_totals)):
        first_value = first_totals.get(currency_code, Decimal("0"))
        second_value = second_totals.get(currency_code, Decimal("0"))
        change = None if first_value == 0 else _round_money((second_value - first_value) / first_value * 100)
        rows.append(
            {
                "currency": currency_code,
                "first": _round_money(first_value),
                "second": _round_money(second_value),
                "change_percent": change,
            }
        )
    return {"metric": metric, "periods_by_currency": rows}


def _analytics_totals(sales: list[Sale], value_fn: Callable[[Sale], Decimal]) -> list[dict]:
    totals: dict[str, Decimal] = {}
    for sale in sales:
        totals[sale.currency] = totals.get(sale.currency, Decimal("0")) + value_fn(sale)
    return [{"currency": code, "value": _round_money(totals[code])} for code in sorted(totals)]


def get_total_revenue(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Net revenue (gross minus VAT minus processing fees minus any
    refunded amount) — this is what "how much did I make" should answer,
    never the raw gross amount customers paid. Grouped by currency: never
    sum different currencies together."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"net_revenue_by_currency": _sum_by_currency(sales, lambda s: s.revenue_contribution(), amount_key="net_revenue")}


def get_gross_revenue(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Gross revenue: the total amount customers paid before VAT and
    processing fees are subtracted. Counts succeeded and partially-refunded
    sales (the same "successful" set as `get_total_revenue`) — a fully
    refunded sale is excluded, its revenue was fully reversed. Grouped by
    currency."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"gross_revenue_by_currency": _sum_by_currency(sales, lambda s: s.gross_amount, amount_key="gross_revenue")}


def get_vat_collected(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """VAT collected from customers on behalf of the tax authority — this is
    not the business's own revenue. Counts succeeded and partially-refunded
    sales, same as `get_gross_revenue`. Grouped by currency."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "vat_collected_by_currency": _sum_by_currency(
            sales, lambda s: s.vat_amount or Decimal("0"), amount_key="vat_collected"
        )
    }


def get_processing_fees(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Total payment-processing fees deducted by the payment provider.
    Counts succeeded and partially-refunded sales, same as
    `get_gross_revenue`. Grouped by currency."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "processing_fees_by_currency": _sum_by_currency(
            sales, lambda s: s.processing_fee or Decimal("0"), amount_key="processing_fees"
        )
    }


def get_top_services(
    db: Session, limit: int = 5, start_date: str | None = None, end_date: str | None = None
) -> dict:
    """Top services/products by net revenue, sorted descending within each
    currency — currencies are never combined into one ranking, since a
    larger number in one currency isn't necessarily worth more than a
    smaller number in another."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    totals: dict[tuple[str, str], Decimal] = {}
    counts: dict[tuple[str, str], int] = {}
    for sale in sales:
        key = (sale.service_name, sale.currency)
        totals[key] = totals.get(key, Decimal("0")) + sale.revenue_contribution()
        counts[key] = counts.get(key, 0) + 1
    rows = [
        {"service_name": name, "currency": currency, "total": _round_money(total), "count": counts[(name, currency)]}
        for (name, currency), total in totals.items()
    ]
    rows.sort(key=lambda row: (row["currency"], -Decimal(row["total"])))
    limit = max(0, limit)
    by_currency: dict[str, list[dict]] = {}
    for row in rows:
        by_currency.setdefault(row["currency"], [])
        if len(by_currency[row["currency"]]) < limit:
            by_currency[row["currency"]].append(row)
    limited = [row for currency in sorted(by_currency) for row in by_currency[currency]]
    return {"services": limited}


def get_recent_customers(db: Session, limit: int = 10) -> dict:
    """The most recent customers who bought something, most recent first.
    Each row carries its own sale's currency — never a bare amount."""
    stmt = select(Sale).where(
        Sale.status.in_([SaleStatus.SUCCEEDED, SaleStatus.PARTIALLY_REFUNDED])
    ).order_by(Sale.occurred_at.desc()).limit(max(0, limit))
    sales = db.scalars(stmt).all()
    return {
        "customers": [
            {
                "customer_name": s.customer_name,
                "service_name": s.service_name,
                "amount": _round_money(s.gross_amount),
                "currency": s.currency,
                "occurred_at": s.occurred_at.isoformat(),
            }
            for s in sales
        ]
    }


def _period_start(day: date, period: str) -> date:
    if period == "week":
        return date.fromordinal(day.toordinal() - day.weekday())
    return date(day.year, day.month, 1)


def get_revenue_trend(
    db: Session, period: str = "month", start_date: str | None = None, end_date: str | None = None
) -> dict:
    """Net revenue and sale count grouped by time period AND currency —
    a period spanning more than one currency produces multiple rows for
    that same period_start, one per currency, never a combined figure."""
    if period not in ("month", "week"):
        return {"error": f"invalid period: {period!r} (expected 'month' or 'week')"}
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    totals: dict[tuple[date, str], Decimal] = {}
    counts: dict[tuple[date, str], int] = {}
    for sale in sales:
        key = (_period_start(sale.occurred_at.date(), period), sale.currency)
        totals[key] = totals.get(key, Decimal("0")) + sale.revenue_contribution()
        counts[key] = counts.get(key, 0) + 1
    rows = [
        {"period_start": bucket.isoformat(), "currency": currency, "total": _round_money(total), "count": counts[(bucket, currency)]}
        for (bucket, currency), total in totals.items()
    ]
    rows.sort(key=lambda row: (row["period_start"], row["currency"]))
    return {"trend": rows}


def count_sales_in_period(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """How many sales occurred in the given period, regardless of status.
    A plain count, not a monetary value — no currency to attach."""
    try:
        start = _parse_date(start_date, "start_date")
        end = _parse_date(end_date, "end_date")
    except ValueError as exc:
        return {"error": str(exc)}
    stmt = select(Sale)
    if start is not None:
        stmt = stmt.where(Sale.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(Sale.occurred_at < _end_of_day_exclusive(end))
    sales = db.scalars(stmt).all()
    return {"count": len(sales)}


def get_pending_documents_summary(db: Session) -> dict:
    """Sales that succeeded but whose customer receipt/invoice is still
    pending or failed to generate. Each row and the summary total carry
    their own currency.

    A sale still waiting on an automatic provider document
    (`waiting_automatic`, e.g. a fresh Grow/Cardcom sale) is only included
    once it's past the same grace period the Exception Center uses — see
    app/services/exception_center.py — so the assistant's answer never
    disagrees with what the owner sees there."""
    grace_cutoff = datetime.utcnow() - timedelta(hours=get_settings().document_match_grace_period_hours)
    sales = list(
        db.scalars(
            select(Sale).where(
                Sale.status == SaleStatus.SUCCEEDED,
                or_(
                    Sale.document_status.in_([DocumentStatus.PENDING, DocumentStatus.FAILED]),
                    and_(Sale.document_status == DocumentStatus.WAITING_AUTOMATIC, Sale.occurred_at < grace_cutoff),
                ),
            )
        ).all()
    )
    return {
        "count": len(sales),
        "total_by_currency": _sum_by_currency(sales, lambda s: s.gross_amount, amount_key="total"),
        "sales": [
            {
                "customer_name": s.customer_name,
                "service_name": s.service_name,
                "amount": _round_money(s.gross_amount),
                "currency": s.currency,
            }
            for s in sales
        ],
    }


def get_refunds_summary(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Count and total refunded amount, grouped by currency."""
    try:
        start = _parse_date(start_date, "start_date")
        end = _parse_date(end_date, "end_date")
    except ValueError as exc:
        return {"error": str(exc)}
    stmt = select(Sale).where(Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED]))
    if start is not None:
        stmt = stmt.where(Sale.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(Sale.occurred_at < _end_of_day_exclusive(end))
    sales = db.scalars(stmt).all()
    return {
        "count": len(sales),
        "refunds_by_currency": _sum_by_currency(
            sales, lambda s: s.refunded_amount or Decimal("0"), amount_key="total_refunded"
        ),
    }


TOOL_FUNCTIONS = {
    "get_total_revenue": get_total_revenue,
    "get_gross_revenue": get_gross_revenue,
    "get_vat_collected": get_vat_collected,
    "get_processing_fees": get_processing_fees,
    "get_top_services": get_top_services,
    "get_recent_customers": get_recent_customers,
    "get_revenue_trend": get_revenue_trend,
    "count_sales_in_period": count_sales_in_period,
    "get_pending_documents_summary": get_pending_documents_summary,
    "get_refunds_summary": get_refunds_summary,
    "query_sales": query_sales,
    "analyze_sales": analyze_sales,
    "compare_sales_periods": compare_sales_periods,
}

_DATE_RANGE_PROPERTIES = {
    "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive lower bound. Omit for no lower bound."},
    "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive upper bound. Omit for no upper bound."},
}

_ANALYTICS_FILTER_PROPERTIES = {
    **_DATE_RANGE_PROPERTIES,
    "status": {
        "type": "string",
        "enum": ["successful", "pending", "failed", "refunded", "all"],
        "description": (
            "Sale lifecycle filter. Defaults to successful, which includes succeeded and partially-refunded "
            "sales but excludes fully-refunded, failed, and pending sales."
        ),
    },
    "customer_query": {"type": "string", "description": "Case-insensitive partial customer-name filter."},
    "service_query": {"type": "string", "description": "Case-insensitive partial service/product-name filter."},
    "payment_method": {
        "type": "string",
        "description": "Exact payment-method filter, such as card, cash, or other, when the user asks for one.",
    },
    "currency": {
        "type": "string",
        "description": "ISO currency filter such as ILS, USD, or EUR. Omit to return separate results per currency.",
    },
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_total_revenue",
            "description": (
                "Get net revenue (gross minus VAT minus processing fees minus any refunded amount) and count of "
                "successful sales in a date range, broken down by currency (net_revenue_by_currency: one row per "
                "currency actually present, e.g. ILS and USD separately — never a combined figure). This is the "
                "right tool for 'how much did I make/earn/net'. Always state which currency each number is in; "
                "never assume or guess a currency."
            ),
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_sales",
            "description": (
                "Search, filter, and rank INDIVIDUAL sale transactions. Use this for questions such as 'what was "
                "my largest/highest/smallest sale?', 'which single transaction made the most money?', 'show the "
                "three biggest cash sales', 'when did customer X buy?', or any question that needs actual sale "
                "rows rather than an aggregate. For 'largest sale/transaction/payment' default to "
                "sort_by=gross_amount, sort_order=desc, limit=1; use net_revenue only when the user explicitly "
                "asks what the business kept/netted. Results are ranked separately per currency and include the "
                "customer, service, date, gross, net, VAT, fees, refunds, and status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    **_ANALYTICS_FILTER_PROPERTIES,
                    "sort_by": {
                        "type": "string",
                        "enum": [
                            "occurred_at",
                            "gross_amount",
                            "net_revenue",
                            "vat_amount",
                            "processing_fee",
                            "refunded_amount",
                        ],
                        "description": "Field to rank individual sales by. Defaults to occurred_at.",
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Ascending or descending rank. Defaults to desc.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "description": "Maximum sale rows to return per currency. Defaults to 10.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_sales",
            "description": (
                "General read-only sales analytics for both expected and novel questions. Aggregate a metric and "
                "optionally rank it by customer, service, payment method, status, day, week, or month. Use for top "
                "customers, average transaction value, payment-method mix, strongest day/week/month, revenue by "
                "customer/service, VAT or fees breakdowns, and sale counts by category. Monetary results are "
                "always separated by currency. This analyzes groups; use query_sales when the user asks about an "
                "individual transaction."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    **_ANALYTICS_FILTER_PROPERTIES,
                    "metric": {
                        "type": "string",
                        "enum": [
                            "net_revenue",
                            "gross_revenue",
                            "vat_collected",
                            "processing_fees",
                            "refunded_amount",
                            "average_net_revenue",
                            "average_gross_amount",
                            "sale_count",
                        ],
                        "description": "Value to calculate. Defaults to net_revenue.",
                    },
                    "group_by": {
                        "type": "string",
                        "enum": ["none", "customer", "service", "payment_method", "status", "day", "week", "month"],
                        "description": "Dimension to aggregate and rank by. Defaults to none for one total per currency.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "description": "Maximum groups per currency (or total for sale_count). Defaults to 10.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_sales_periods",
            "description": (
                "Compare net/gross revenue, VAT, fees, refunds, or sale count between two explicit inclusive date "
                "ranges. Use for questions like 'did I improve this month?', 'compare this week with last week', "
                "or 'how much did card revenue change?'. Resolve relative periods using today's date from the "
                "system message. The tool computes the percentage change deterministically; a null percentage "
                "means the first period was zero, so no percentage can honestly be calculated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "first_start_date": {"type": "string", "description": "First period start, YYYY-MM-DD inclusive."},
                    "first_end_date": {"type": "string", "description": "First period end, YYYY-MM-DD inclusive."},
                    "second_start_date": {"type": "string", "description": "Second period start, YYYY-MM-DD inclusive."},
                    "second_end_date": {"type": "string", "description": "Second period end, YYYY-MM-DD inclusive."},
                    "metric": {
                        "type": "string",
                        "enum": [
                            "net_revenue",
                            "gross_revenue",
                            "vat_collected",
                            "processing_fees",
                            "refunded_amount",
                            "sale_count",
                        ],
                        "description": "Metric to compare. Defaults to net_revenue.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["successful", "pending", "failed", "refunded", "all"],
                        "description": "Optional lifecycle filter. Defaults to successful; refunded_amount defaults to refunded.",
                    },
                    "customer_query": {"type": "string", "description": "Optional partial customer-name filter."},
                    "service_query": {"type": "string", "description": "Optional partial service/product filter."},
                    "payment_method": {"type": "string", "description": "Optional exact payment-method filter."},
                    "currency": {"type": "string", "description": "Optional ISO currency filter."},
                },
                "required": ["first_start_date", "first_end_date", "second_start_date", "second_end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gross_revenue",
            "description": (
                "Get gross revenue — the total amount customers paid before VAT and processing fees are "
                "subtracted — for successful sales in a date range, broken down by currency "
                "(gross_revenue_by_currency). NOT the same as net revenue/profit."
            ),
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vat_collected",
            "description": (
                "Get total VAT collected from customers (held for the tax authority, not business revenue) in a "
                "date range, broken down by currency (vat_collected_by_currency)."
            ),
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_processing_fees",
            "description": (
                "Get total payment-processing fees deducted by the payment provider in a date range, broken down "
                "by currency (processing_fees_by_currency)."
            ),
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_services",
            "description": (
                "Get the top services/products by net revenue, sorted descending within each currency, optionally "
                "filtered by date range. Each row carries its own currency — never rank or combine amounts across "
                "different currencies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum services to return PER currency. Defaults to 5."},
                    **_DATE_RANGE_PROPERTIES,
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_customers",
            "description": (
                "List the most recent customers who completed a purchase, most recent first. Each row carries its "
                "own sale's currency — state it, never assume ILS or any other currency."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of customers to return. Defaults to 10."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue_trend",
            "description": (
                "Get net revenue and sale count grouped by time period (month or week) AND currency, sorted "
                "chronologically. A period with sales in more than one currency produces multiple rows for that "
                "period, one per currency — never a combined total."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["month", "week"], "description": "Grouping period. Defaults to 'month'."},
                    **_DATE_RANGE_PROPERTIES,
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_sales_in_period",
            "description": "Count how many sale transactions occurred in a date range, regardless of status.",
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_documents_summary",
            "description": (
                "Get the count and list of successful sales whose customer receipt/invoice is still pending or "
                "failed to generate, plus a total broken down by currency (total_by_currency). Each sale row "
                "carries its own currency."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refunds_summary",
            "description": (
                "Get the count and total amount of refunded/partially-refunded sales in a date range, broken down "
                "by currency (refunds_by_currency)."
            ),
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
]
