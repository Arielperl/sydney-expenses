"""Read-only query functions the AI assistant can call — never raw SQL, never
a write path. Each function takes the request's DB session plus the
JSON-serializable arguments the OpenAI tool-calling API sends, and returns a
plain, JSON-serializable dict: either the real result, or {"error": "..."}
for a bad argument (never raised — a raised exception would abort the whole
chat turn; an error dict instead becomes a tool result the model can react
to, e.g. by asking the user to clarify).

TOOL_DEFINITIONS is the JSON-schema list handed to the model; TOOL_FUNCTIONS
maps each tool name to its implementation — the single source of truth the
orchestrator's tool-calling loop dispatches through, so a tool can never be
invoked under a name or shape the model wasn't actually given.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseCategory

_MONEY_PLACES = Decimal("0.01")
_CATEGORY_VALUES = [c.value for c in ExpenseCategory]


def _round_money(value: Decimal) -> str:
    return str(value.quantize(_MONEY_PLACES, rounding=ROUND_HALF_UP))


def _parse_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value!r} (expected YYYY-MM-DD)") from exc


def _parse_category(value: str | None) -> ExpenseCategory | None:
    if not value:
        return None
    try:
        return ExpenseCategory(value)
    except ValueError as exc:
        raise ValueError(f"invalid category: {value!r} (expected one of: {', '.join(_CATEGORY_VALUES)})") from exc


def _filtered_expenses(db: Session, start_date: str | None, end_date: str | None, category: str | None) -> list[Expense]:
    stmt = select(Expense)
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    cat = _parse_category(category)
    if start is not None:
        stmt = stmt.where(Expense.expense_date >= start)
    if end is not None:
        stmt = stmt.where(Expense.expense_date <= end)
    if cat is not None:
        stmt = stmt.where(Expense.category == cat)
    return list(db.scalars(stmt).all())


def get_total_revenue(
    db: Session, start_date: str | None = None, end_date: str | None = None, category: str | None = None
) -> dict:
    try:
        expenses = _filtered_expenses(db, start_date, end_date, category)
    except ValueError as exc:
        return {"error": str(exc)}
    total = sum((e.amount for e in expenses), Decimal("0"))
    return {"total": _round_money(total), "count": len(expenses)}


def get_category_breakdown(db: Session, start_date: str | None = None, end_date: str | None = None) -> dict:
    try:
        expenses = _filtered_expenses(db, start_date, end_date, None)
    except ValueError as exc:
        return {"error": str(exc)}
    totals: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    for expense in expenses:
        key = expense.category.value
        totals[key] = totals.get(key, Decimal("0")) + expense.amount
        counts[key] = counts.get(key, 0) + 1
    rows = [{"category": key, "total": _round_money(total), "count": counts[key]} for key, total in totals.items()]
    rows.sort(key=lambda row: Decimal(row["total"]), reverse=True)
    return {"categories": rows}


def get_top_merchants(
    db: Session, limit: int = 5, start_date: str | None = None, end_date: str | None = None
) -> dict:
    try:
        expenses = _filtered_expenses(db, start_date, end_date, None)
    except ValueError as exc:
        return {"error": str(exc)}
    totals: dict[str, Decimal] = {}
    counts: dict[str, int] = {}
    for expense in expenses:
        key = expense.business_name
        totals[key] = totals.get(key, Decimal("0")) + expense.amount
        counts[key] = counts.get(key, 0) + 1
    rows = [
        {"business_name": key, "total": _round_money(total), "count": counts[key]} for key, total in totals.items()
    ]
    rows.sort(key=lambda row: Decimal(row["total"]), reverse=True)
    return {"merchants": rows[: max(0, limit)]}


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
        expenses = _filtered_expenses(db, start_date, end_date, None)
    except ValueError as exc:
        return {"error": str(exc)}
    totals: dict[date, Decimal] = {}
    counts: dict[date, int] = {}
    for expense in expenses:
        bucket = _period_start(expense.expense_date, period)
        totals[bucket] = totals.get(bucket, Decimal("0")) + expense.amount
        counts[bucket] = counts.get(bucket, 0) + 1
    rows = [
        {"period_start": bucket.isoformat(), "total": _round_money(total), "count": counts[bucket]}
        for bucket, total in totals.items()
    ]
    rows.sort(key=lambda row: row["period_start"])
    return {"trend": rows}


def list_recent_expenses(db: Session, limit: int = 10, category: str | None = None) -> dict:
    try:
        cat = _parse_category(category)
    except ValueError as exc:
        return {"error": str(exc)}
    stmt = select(Expense).order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    if cat is not None:
        stmt = stmt.where(Expense.category == cat)
    stmt = stmt.limit(max(0, limit))
    expenses = db.scalars(stmt).all()
    return {
        "expenses": [
            {
                "business_name": e.business_name,
                "amount": _round_money(e.amount),
                "category": e.category.value,
                "expense_date": e.expense_date.isoformat(),
            }
            for e in expenses
        ]
    }


TOOL_FUNCTIONS = {
    "get_total_revenue": get_total_revenue,
    "get_category_breakdown": get_category_breakdown,
    "get_top_merchants": get_top_merchants,
    "get_revenue_trend": get_revenue_trend,
    "list_recent_expenses": list_recent_expenses,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_total_revenue",
            "description": (
                "Get total revenue (sum of amounts) and count of matching expenses, "
                "optionally filtered by date range and/or category."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "ISO date YYYY-MM-DD, inclusive lower bound. Omit for no lower bound.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "ISO date YYYY-MM-DD, inclusive upper bound. Omit for no upper bound.",
                    },
                    "category": {"type": "string", "enum": _CATEGORY_VALUES, "description": "Optional category filter."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_breakdown",
            "description": (
                "Get total revenue and count broken down by category, sorted by total "
                "descending, optionally filtered by date range."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive lower bound."},
                    "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive upper bound."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_merchants",
            "description": (
                "Get the top customers/merchants by total revenue, sorted descending, "
                "optionally filtered by date range."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of merchants to return. Defaults to 5."},
                    "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive lower bound."},
                    "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive upper bound."},
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
                "Get total revenue and count grouped by time period (month or week), "
                "sorted chronologically, optionally filtered by date range."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["month", "week"],
                        "description": "Grouping period. Defaults to 'month'.",
                    },
                    "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive lower bound."},
                    "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD, inclusive upper bound."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_expenses",
            "description": "List the most recent individual expenses, optionally filtered by category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of expenses to return. Defaults to 10."},
                    "category": {"type": "string", "enum": _CATEGORY_VALUES, "description": "Optional category filter."},
                },
                "required": [],
            },
        },
    },
]
