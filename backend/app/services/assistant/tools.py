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
full metric definitions (net vs. gross vs. profit, refund-by-original-date,
single-currency assumption).

TOOL_DEFINITIONS is the JSON-schema list handed to the model; TOOL_FUNCTIONS
maps each tool name to its implementation — the single source of truth the
orchestrator's tool-calling loop dispatches through, so a tool can never be
invoked under a name or shape the model wasn't actually given.
"""

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

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


def get_total_revenue(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Net revenue (gross minus VAT minus processing fees minus any
    refunded amount) — this is what "how much did I make" should answer,
    never the raw gross amount customers paid."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    total = sum((s.revenue_contribution() for s in sales), Decimal("0"))
    return {"net_revenue": _round_money(total), "count": len(sales)}


def get_gross_revenue(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Gross revenue: the total amount customers paid before VAT and
    processing fees are subtracted. Counts succeeded and partially-refunded
    sales (the same "successful" set as `get_total_revenue`) — a fully
    refunded sale is excluded, its revenue was fully reversed."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    total = sum((s.gross_amount for s in sales), Decimal("0"))
    return {"gross_revenue": _round_money(total), "count": len(sales)}


def get_vat_collected(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """VAT collected from customers on behalf of the tax authority — this is
    not the business's own revenue. Counts succeeded and partially-refunded
    sales, same as `get_gross_revenue`."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    total = sum((s.vat_amount or Decimal("0") for s in sales), Decimal("0"))
    return {"vat_collected": _round_money(total)}


def get_processing_fees(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Total payment-processing fees deducted by the payment provider.
    Counts succeeded and partially-refunded sales, same as
    `get_gross_revenue`."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    total = sum((s.processing_fee or Decimal("0") for s in sales), Decimal("0"))
    return {"processing_fees": _round_money(total)}


def get_top_services(
    db: Session, limit: int = 5, start_date: str | None = None, end_date: str | None = None
) -> dict:
    """Top services/products by net revenue, sorted descending."""
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    totals: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    for sale in sales:
        key = sale.service_name
        totals[key] = totals.get(key, Decimal("0")) + sale.revenue_contribution()
        counts[key] = counts.get(key, 0) + 1
    rows = [{"service_name": key, "total": _round_money(total), "count": counts[key]} for key, total in totals.items()]
    rows.sort(key=lambda row: Decimal(row["total"]), reverse=True)
    return {"services": rows[: max(0, limit)]}


def get_recent_customers(db: Session, limit: int = 10) -> dict:
    """The most recent customers who bought something, most recent first."""
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
    if period not in ("month", "week"):
        return {"error": f"invalid period: {period!r} (expected 'month' or 'week')"}
    try:
        sales = _filtered_sales(db, start_date, end_date)
    except ValueError as exc:
        return {"error": str(exc)}
    totals: dict[date, Decimal] = {}
    counts: dict[date, int] = {}
    for sale in sales:
        bucket = _period_start(sale.occurred_at.date(), period)
        totals[bucket] = totals.get(bucket, Decimal("0")) + sale.revenue_contribution()
        counts[bucket] = counts.get(bucket, 0) + 1
    rows = [
        {"period_start": bucket.isoformat(), "total": _round_money(total), "count": counts[bucket]}
        for bucket, total in totals.items()
    ]
    rows.sort(key=lambda row: row["period_start"])
    return {"trend": rows}


def count_sales_in_period(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    """How many sales occurred in the given period, regardless of status."""
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
    pending or failed to generate."""
    sales = list(
        db.scalars(
            select(Sale).where(
                Sale.status == SaleStatus.SUCCEEDED,
                Sale.document_status.in_([DocumentStatus.PENDING, DocumentStatus.FAILED]),
            )
        ).all()
    )
    return {
        "count": len(sales),
        "sales": [
            {"customer_name": s.customer_name, "service_name": s.service_name, "amount": _round_money(s.gross_amount)}
            for s in sales
        ],
    }


def get_refunds_summary(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
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
    total_refunded = sum((s.refunded_amount or Decimal("0") for s in sales), Decimal("0"))
    return {"count": len(sales), "total_refunded": _round_money(total_refunded)}


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
}

_DATE_RANGE_PROPERTIES = {
    "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive lower bound. Omit for no lower bound."},
    "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive upper bound. Omit for no upper bound."},
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_total_revenue",
            "description": (
                "Get net revenue (gross minus VAT minus processing fees minus any refunded amount) and count of "
                "successful sales in a date range. This is the right tool for 'how much did I make/earn/net'."
            ),
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gross_revenue",
            "description": (
                "Get gross revenue — the total amount customers paid before VAT and processing fees are "
                "subtracted — for successful sales in a date range. NOT the same as net revenue/profit."
            ),
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vat_collected",
            "description": "Get total VAT collected from customers (held for the tax authority, not business revenue) in a date range.",
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_processing_fees",
            "description": "Get total payment-processing fees deducted by the payment provider in a date range.",
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_services",
            "description": "Get the top services/products by net revenue, sorted descending, optionally filtered by date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of services to return. Defaults to 5."},
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
            "description": "List the most recent customers who completed a purchase, most recent first.",
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
            "description": "Get net revenue and sale count grouped by time period (month or week), sorted chronologically.",
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
            "description": "Get the count and list of successful sales whose customer receipt/invoice is still pending or failed to generate.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refunds_summary",
            "description": "Get the count and total amount of refunded/partially-refunded sales in a date range.",
            "parameters": {"type": "object", "properties": _DATE_RANGE_PROPERTIES, "required": []},
        },
    },
]
