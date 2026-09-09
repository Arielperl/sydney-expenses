# AI Assistant Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only chat page where a business owner asks natural-language questions about their expense/sales data and gets a natural-language answer, backed by OpenAI tool-calling over five fixed, read-only SQLAlchemy query functions.

**Architecture:** FastAPI route (`POST /api/assistant/chat`) → an orchestrator service that runs a bounded (max 5 rounds) OpenAI `chat.completions` tool-calling loop → tool calls dispatch to plain Python functions that query the `Expense` table via SQLAlchemy ORM (no raw SQL, no write path) → final natural-language reply returned to a new React chat page. Conversation history lives only in frontend state (no new DB table).

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, `openai` Python SDK 3.6.0 (`chat.completions.create` with `tools=`), React, TanStack Query, react-i18next, Tailwind CSS.

## Global Constraints

- No tool function may write/update/delete data — read-only `select()` queries only.
- No raw SQL anywhere in this feature.
- Model: `gpt-4o-mini` (new `openai_assistant_model` setting, independent of `openai_receipt_model`).
- Conversation history: frontend React state only, not persisted server-side.
- Full backend `pytest` and frontend `lint`/`tsc -b`/`test`/`build` must pass before any task is considered done.
- Follow existing patterns exactly: `app/api/routes/*.py` + `app/schemas/*.py` + `app/services/*` layering (see `dashboard.py`/`dashboard_service.py`/`schemas/dashboard.py` as the template); frontend `services/*.ts` + `types/*.ts` + `pages/*.tsx` + i18n JSON in both `he`/`en`.
- Never log receipt/expense content beyond what the rest of the codebase already logs (safe metadata only).

---

### Task 1: Assistant tools (pure, read-only query functions)

**Files:**
- Create: `backend/app/services/assistant/__init__.py`
- Create: `backend/app/services/assistant/tools.py`
- Test: `backend/tests/test_assistant_tools.py`

**Interfaces:**
- Produces: `TOOL_FUNCTIONS: dict[str, Callable]` (name → function), `TOOL_DEFINITIONS: list[dict]` (OpenAI tool-calling JSON schemas), and the five functions themselves — `get_total_revenue(db, start_date=None, end_date=None, category=None) -> dict`, `get_category_breakdown(db, start_date=None, end_date=None) -> dict`, `get_top_merchants(db, limit=5, start_date=None, end_date=None) -> dict`, `get_revenue_trend(db, period="month", start_date=None, end_date=None) -> dict`, `list_recent_expenses(db, limit=10, category=None) -> dict`. Every function takes a `sqlalchemy.orm.Session` as its first positional argument and returns a JSON-serializable `dict` — either the real result, or `{"error": "<message>"}` on invalid input (never raises for a bad argument value, since that dict is what gets handed back to the model as a tool result).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_assistant_tools.py`:

```python
from datetime import date
from decimal import Decimal

from app.models.expense import Expense, ExpenseCategory, ExtractionStatus
from app.services.assistant.tools import (
    get_category_breakdown,
    get_revenue_trend,
    get_top_merchants,
    get_total_revenue,
    list_recent_expenses,
)


def _add_expense(db_session, **overrides):
    defaults = dict(
        business_name="Shufersal",
        amount=Decimal("100.00"),
        currency="ILS",
        category=ExpenseCategory.GROCERIES,
        expense_date=date(2026, 3, 15),
        extraction_status=ExtractionStatus.MANUAL,
    )
    defaults.update(overrides)
    expense = Expense(**defaults)
    db_session.add(expense)
    db_session.commit()
    return expense


# --- get_total_revenue -------------------------------------------------


def test_get_total_revenue_empty_db(db_session):
    result = get_total_revenue(db_session)
    assert result == {"total": "0.00", "count": 0}


def test_get_total_revenue_sums_all_by_default(db_session):
    _add_expense(db_session, amount=Decimal("100.00"))
    _add_expense(db_session, amount=Decimal("50.50"))
    result = get_total_revenue(db_session)
    assert result == {"total": "150.50", "count": 2}


def test_get_total_revenue_filters_by_date_range(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 3, 10))
    _add_expense(db_session, amount=Decimal("50.00"), expense_date=date(2026, 4, 1))
    result = get_total_revenue(db_session, start_date="2026-03-01", end_date="2026-03-31")
    assert result == {"total": "100.00", "count": 1}


def test_get_total_revenue_filters_by_category(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), category=ExpenseCategory.GROCERIES)
    _add_expense(db_session, amount=Decimal("40.00"), category=ExpenseCategory.DINING)
    result = get_total_revenue(db_session, category="dining")
    assert result == {"total": "40.00", "count": 1}


def test_get_total_revenue_invalid_category_returns_error_not_raise(db_session):
    result = get_total_revenue(db_session, category="not-a-real-category")
    assert "error" in result


def test_get_total_revenue_invalid_date_returns_error_not_raise(db_session):
    result = get_total_revenue(db_session, start_date="not-a-date")
    assert "error" in result


# --- get_category_breakdown ---------------------------------------------


def test_get_category_breakdown_sorted_descending(db_session):
    _add_expense(db_session, amount=Decimal("50.00"), category=ExpenseCategory.DINING)
    _add_expense(db_session, amount=Decimal("100.00"), category=ExpenseCategory.GROCERIES)
    _add_expense(db_session, amount=Decimal("30.00"), category=ExpenseCategory.GROCERIES)
    result = get_category_breakdown(db_session)
    assert result["categories"] == [
        {"category": "groceries", "total": "130.00", "count": 2},
        {"category": "dining", "total": "50.00", "count": 1},
    ]


# --- get_top_merchants ---------------------------------------------------


def test_get_top_merchants_sorted_and_limited(db_session):
    _add_expense(db_session, business_name="A", amount=Decimal("10.00"))
    _add_expense(db_session, business_name="B", amount=Decimal("100.00"))
    _add_expense(db_session, business_name="B", amount=Decimal("50.00"))
    result = get_top_merchants(db_session, limit=1)
    assert result == {"merchants": [{"business_name": "B", "total": "150.00", "count": 2}]}


# --- get_revenue_trend -----------------------------------------------------


def test_get_revenue_trend_groups_by_month(db_session):
    _add_expense(db_session, amount=Decimal("100.00"), expense_date=date(2026, 3, 5))
    _add_expense(db_session, amount=Decimal("20.00"), expense_date=date(2026, 3, 20))
    _add_expense(db_session, amount=Decimal("40.00"), expense_date=date(2026, 4, 1))
    result = get_revenue_trend(db_session, period="month")
    assert result["trend"] == [
        {"period_start": "2026-03-01", "total": "120.00", "count": 2},
        {"period_start": "2026-04-01", "total": "40.00", "count": 1},
    ]


def test_get_revenue_trend_invalid_period_returns_error(db_session):
    result = get_revenue_trend(db_session, period="year")
    assert "error" in result


# --- list_recent_expenses -------------------------------------------------


def test_list_recent_expenses_orders_newest_first(db_session):
    _add_expense(db_session, business_name="Old", expense_date=date(2026, 1, 1))
    _add_expense(db_session, business_name="New", expense_date=date(2026, 3, 1))
    result = list_recent_expenses(db_session, limit=10)
    assert [e["business_name"] for e in result["expenses"]] == ["New", "Old"]


def test_list_recent_expenses_filters_by_category(db_session):
    _add_expense(db_session, business_name="Groc", category=ExpenseCategory.GROCERIES)
    _add_expense(db_session, business_name="Din", category=ExpenseCategory.DINING)
    result = list_recent_expenses(db_session, category="dining")
    assert [e["business_name"] for e in result["expenses"]] == ["Din"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_assistant_tools.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.services.assistant'`)

- [ ] **Step 3: Create the package and implement tools.py**

Create `backend/app/services/assistant/__init__.py` (empty file).

Create `backend/app/services/assistant/tools.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_assistant_tools.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/assistant/__init__.py backend/app/services/assistant/tools.py backend/tests/test_assistant_tools.py
git commit -m "Add read-only assistant query tools (revenue, categories, merchants, trend, recent)"
```

---

### Task 2: Assistant orchestrator (bounded OpenAI tool-calling loop)

**Files:**
- Create: `backend/app/services/assistant/exceptions.py`
- Create: `backend/app/services/assistant/orchestrator.py`
- Modify: `backend/app/core/config.py` (add `openai_assistant_model` setting)
- Test: `backend/tests/test_assistant_orchestrator.py`

**Interfaces:**
- Consumes: `TOOL_FUNCTIONS`, `TOOL_DEFINITIONS` from `app.services.assistant.tools` (Task 1).
- Produces: `answer_question(settings: Settings, db: Session, message: str, history: list[dict[str, str]], client: OpenAI | None = None) -> str`, `AssistantConfigError`, `AssistantProviderError` (both subclass `AssistantError`) — used by the route in Task 3.

- [ ] **Step 1: Add the new setting**

In `backend/app/core/config.py`, find the existing OpenAI settings block:

```python
    openai_api_key: str | None = None
    openai_receipt_model: str | None = None
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2
```

Replace with:

```python
    openai_api_key: str | None = None
    openai_receipt_model: str | None = None
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2
    # Separate from openai_receipt_model: the assistant chat is a text/tool-calling
    # task, never vision, so it always uses the cheaper mini model regardless of
    # which (possibly more expensive) model OPENAI_RECEIPT_MODEL is set to.
    openai_assistant_model: str = "gpt-4o-mini"
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_assistant_orchestrator.py`:

```python
import json

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, AuthenticationError

from app.core.config import get_settings
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError
from app.services.assistant.orchestrator import answer_question

# Both APITimeoutError and APIConnectionError require a real httpx.Request
# object (not None) — matches the exact pattern already used in
# test_openai_extractor.py for the same exception types.
_FAKE_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


class _FakeFunctionCall:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _FakeFunctionCall(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeCompletion:
    def __init__(self, message):
        self.choices = [_FakeChoice(message)]


class _FakeCompletions:
    """Stands in for `client.chat.completions`. `behaviors` is a queue of either
    a _FakeMessage (wrapped into a completion) or an exception — consumed one
    per call, so a test can script an exact multi-round conversation."""

    def __init__(self, behaviors):
        self._behaviors = list(behaviors)
        self.call_count = 0
        self.last_messages = None

    def create(self, model, messages, tools=None, timeout=None):
        self.call_count += 1
        self.last_messages = messages
        behavior = self._behaviors.pop(0)
        if isinstance(behavior, BaseException):
            raise behavior
        return _FakeCompletion(behavior)


class _FakeChat:
    def __init__(self, behaviors):
        self.completions = _FakeCompletions(behaviors)


class _FakeOpenAIClient:
    def __init__(self, behaviors):
        self.chat = _FakeChat(behaviors)


def _settings_with_openai(**overrides):
    return get_settings().model_copy(
        update={"openai_api_key": "sk-test-not-real", "openai_assistant_model": "gpt-test-model", **overrides}
    )


def test_answers_directly_when_no_tool_call_needed(db_session):
    client = _FakeOpenAIClient([_FakeMessage(content="Hello! How can I help?")])
    reply = answer_question(_settings_with_openai(), db_session, "hi", [], client=client)
    assert reply == "Hello! How can I help?"
    assert client.chat.completions.call_count == 1


def test_runs_a_tool_and_uses_its_result(db_session):
    from datetime import date
    from decimal import Decimal

    from app.models.expense import Expense, ExpenseCategory, ExtractionStatus

    db_session.add(
        Expense(
            business_name="Shufersal",
            amount=Decimal("100.00"),
            currency="ILS",
            category=ExpenseCategory.GROCERIES,
            expense_date=date(2026, 3, 15),
            extraction_status=ExtractionStatus.MANUAL,
        )
    )
    db_session.commit()

    client = _FakeOpenAIClient(
        [
            _FakeMessage(tool_calls=[_FakeToolCall("call_1", "get_total_revenue", "{}")]),
            _FakeMessage(content="You made 100.00 ILS total."),
        ]
    )
    reply = answer_question(_settings_with_openai(), db_session, "how much total?", [], client=client)
    assert reply == "You made 100.00 ILS total."
    assert client.chat.completions.call_count == 2
    # The tool result fed back to the model must reflect the real DB query.
    tool_message = client.chat.completions.last_messages[-1]
    assert tool_message["role"] == "tool"
    assert json.loads(tool_message["content"]) == {"total": "100.00", "count": 1}


def test_unknown_tool_name_returns_error_result_not_crash(db_session):
    client = _FakeOpenAIClient(
        [
            _FakeMessage(tool_calls=[_FakeToolCall("call_1", "delete_everything", "{}")]),
            _FakeMessage(content="I can't do that."),
        ]
    )
    reply = answer_question(_settings_with_openai(), db_session, "delete stuff", [], client=client)
    assert reply == "I can't do that."
    tool_message = client.chat.completions.last_messages[-1]
    assert "error" in json.loads(tool_message["content"])


def test_stops_after_max_tool_rounds(db_session):
    # 5 tool-call rounds (the cap) + 1 final forced text-only call.
    behaviors = [_FakeMessage(tool_calls=[_FakeToolCall("call_1", "get_total_revenue", "{}")]) for _ in range(5)]
    behaviors.append(_FakeMessage(content="Here's what I found so far."))
    client = _FakeOpenAIClient(behaviors)
    reply = answer_question(_settings_with_openai(), db_session, "keep asking", [], client=client)
    assert reply == "Here's what I found so far."
    assert client.chat.completions.call_count == 6


def test_missing_api_key_raises_config_error(db_session):
    with pytest.raises(AssistantConfigError):
        answer_question(_settings_with_openai(openai_api_key=""), db_session, "hi", [])


def test_timeout_raises_provider_error(db_session):
    client = _FakeOpenAIClient([APITimeoutError(_FAKE_REQUEST)])
    with pytest.raises(AssistantProviderError):
        answer_question(_settings_with_openai(), db_session, "hi", [], client=client)


def test_connection_error_raises_provider_error(db_session):
    client = _FakeOpenAIClient([APIConnectionError(request=_FAKE_REQUEST)])
    with pytest.raises(AssistantProviderError):
        answer_question(_settings_with_openai(), db_session, "hi", [], client=client)


def test_auth_error_raises_provider_error(db_session):
    response = httpx.Response(401, request=_FAKE_REQUEST)
    client = _FakeOpenAIClient([AuthenticationError("bad key", response=response, body=None)])
    with pytest.raises(AssistantProviderError):
        answer_question(_settings_with_openai(), db_session, "hi", [], client=client)


def test_conversation_history_is_forwarded(db_session):
    client = _FakeOpenAIClient([_FakeMessage(content="ok")])
    history = [{"role": "user", "content": "earlier question"}, {"role": "assistant", "content": "earlier answer"}]
    answer_question(_settings_with_openai(), db_session, "follow up", history, client=client)
    sent = client.chat.completions.last_messages
    contents = [m["content"] for m in sent if isinstance(m, dict) and m.get("content")]
    assert "earlier question" in contents
    assert "earlier answer" in contents
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_assistant_orchestrator.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.services.assistant.exceptions'`)

- [ ] **Step 4: Implement exceptions.py and orchestrator.py**

Create `backend/app/services/assistant/exceptions.py`:

```python
class AssistantError(Exception):
    """Base class for AI-assistant chat errors."""


class AssistantConfigError(AssistantError):
    """Raised when required assistant configuration (e.g. OPENAI_API_KEY) is missing."""


class AssistantProviderError(AssistantError):
    """Raised when the OpenAI call itself fails (timeout, connection, rate limit, auth, etc.)."""
```

Create `backend/app/services/assistant/orchestrator.py`:

```python
"""Runs a bounded OpenAI tool-calling conversation turn over the read-only
assistant tools (see tools.py). The model never sees the database schema or
writes any query itself — it only ever picks from the fixed TOOL_DEFINITIONS
list, and every tool call is dispatched through TOOL_FUNCTIONS, the same
lookup table the model's own tool definitions were generated from."""

import json
import logging

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError
from app.services.assistant.tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a helpful assistant for a small business owner using Receiptly, an "
    "expense/sales tracking app. Answer questions about their sales/expense data "
    "using only the provided tools — never invent a number. If a tool returns no "
    "data for the question asked, say so honestly rather than guessing. Reply in "
    "the same language the user asked in (Hebrew or English). Keep answers concise "
    "and conversational, formatted for a chat bubble, not a report."
)

_MAX_TOOL_ROUNDS = 5

_TRANSIENT_TIMEOUT_ERRORS = (APITimeoutError,)
_TRANSIENT_RETRYABLE_ERRORS = (APIConnectionError, RateLimitError, InternalServerError)
_NON_TRANSIENT_ERRORS = (BadRequestError, AuthenticationError, PermissionDeniedError, NotFoundError)


def answer_question(
    settings: Settings,
    db: Session,
    message: str,
    history: list[dict[str, str]],
    client: OpenAI | None = None,
) -> str:
    if not settings.openai_api_key:
        raise AssistantConfigError("OPENAI_API_KEY is not configured.")
    if client is None:
        client = OpenAI(api_key=settings.openai_api_key, max_retries=0)

    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    for _round in range(_MAX_TOOL_ROUNDS):
        message_out = _create_completion(client, settings, messages, with_tools=True)

        if not message_out.tool_calls:
            return message_out.content or ""

        messages.append(_assistant_message_dict(message_out))
        for tool_call in message_out.tool_calls:
            result = _run_tool(db, tool_call.function.name, tool_call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})

    # Hard cap reached: ask once more without tools, forcing a text answer
    # from whatever's already been gathered, rather than looping forever.
    final = _create_completion(client, settings, messages, with_tools=False)
    return final.content or "לא הצלחתי למצוא תשובה מלאה לשאלה הזו."


def _assistant_message_dict(message) -> dict:
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
        if message.tool_calls
        else None,
    }


def _create_completion(client: OpenAI, settings: Settings, messages: list[dict], *, with_tools: bool):
    try:
        response = client.chat.completions.create(
            model=settings.openai_assistant_model,
            messages=messages,
            tools=TOOL_DEFINITIONS if with_tools else None,
            timeout=settings.openai_timeout_seconds,
        )
        return response.choices[0].message
    except _TRANSIENT_TIMEOUT_ERRORS as exc:
        raise AssistantProviderError("Assistant request timed out.") from exc
    except _TRANSIENT_RETRYABLE_ERRORS as exc:
        raise AssistantProviderError(f"Assistant provider failed: {type(exc).__name__}") from exc
    except _NON_TRANSIENT_ERRORS as exc:
        raise AssistantProviderError(f"Assistant provider error: {type(exc).__name__}") from exc


def _run_tool(db: Session, name: str, arguments_json: str) -> dict:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"unknown tool: {name}"}
    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return {"error": "invalid tool arguments"}
    try:
        return func(db, **kwargs)
    except Exception as exc:  # noqa: BLE001 - a tool error must reach the model as data, not crash the request
        logger.info("assistant_tool_error tool=%s error_category=%s", name, type(exc).__name__)
        return {"error": f"tool failed: {type(exc).__name__}"}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_assistant_orchestrator.py -v`
Expected: PASS (9 tests)

- [ ] **Step 6: Run the full backend suite to confirm no regressions**

Run: `pytest -q`
Expected: all tests pass (242 existing + new ones)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/assistant/exceptions.py backend/app/services/assistant/orchestrator.py backend/app/core/config.py backend/tests/test_assistant_orchestrator.py
git commit -m "Add bounded OpenAI tool-calling orchestrator for the assistant chat"
```

---

### Task 3: Schemas, route, and router wiring

**Files:**
- Create: `backend/app/schemas/assistant.py`
- Create: `backend/app/api/routes/assistant.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_assistant_route.py`

**Interfaces:**
- Consumes: `answer_question` from `app.services.assistant.orchestrator` (Task 2).
- Produces: `POST /api/assistant/chat` — request body `{"message": str, "history": [{"role": str, "content": str}]}`, response `{"reply": str}`, `503` on any assistant failure.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_assistant_route.py`:

```python
from unittest.mock import patch

from app.core.config import get_settings
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError

CHAT_URL = "/api/assistant/chat"


def test_chat_returns_reply(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", return_value="You sold 100 ILS this month.") as mocked:
            response = client.post(CHAT_URL, json={"message": "how much this month?", "history": []})
        assert response.status_code == 200
        assert response.json() == {"reply": "You sold 100 ILS this month."}
        mocked.assert_called_once()
    finally:
        get_settings.cache_clear()


def test_chat_forwards_history(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", return_value="ok") as mocked:
            client.post(
                CHAT_URL,
                json={
                    "message": "follow up",
                    "history": [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "answer"}],
                },
            )
        _settings, _db, _message, history = mocked.call_args[0]
        assert history == [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "answer"}]
    finally:
        get_settings.cache_clear()


def test_chat_missing_config_returns_503(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", side_effect=AssistantConfigError("no key")):
            response = client.post(CHAT_URL, json={"message": "hi", "history": []})
        assert response.status_code == 503
    finally:
        get_settings.cache_clear()


def test_chat_provider_error_returns_503(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    try:
        with patch("app.api.routes.assistant.answer_question", side_effect=AssistantProviderError("timed out")):
            response = client.post(CHAT_URL, json={"message": "hi", "history": []})
        assert response.status_code == 503
        # The raw provider exception text must never leak to the client.
        assert "timed out" not in response.text
    finally:
        get_settings.cache_clear()


def test_chat_empty_message_is_rejected(client):
    response = client.post(CHAT_URL, json={"message": "", "history": []})
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_assistant_route.py -v`
Expected: FAIL (404 — route doesn't exist yet)

- [ ] **Step 3: Implement the schema, route, and wire it into the router**

Create `backend/app/schemas/assistant.py`:

```python
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
```

Create `backend/app/api/routes/assistant.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.schemas.assistant import ChatRequest, ChatResponse
from app.services.assistant.exceptions import AssistantConfigError, AssistantProviderError
from app.services.assistant.orchestrator import answer_question

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    settings = get_settings()
    history = [{"role": m.role, "content": m.content} for m in payload.history]
    try:
        reply = answer_question(settings, db, payload.message, history)
    except (AssistantConfigError, AssistantProviderError) as exc:
        raise HTTPException(
            status_code=503, detail="Could not get an answer right now. Please try again."
        ) from exc
    return ChatResponse(reply=reply)
```

In `backend/app/api/router.py`, replace:

```python
from app.api.routes import dashboard, expenses, health, receipts, system

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(expenses.router)
api_router.include_router(receipts.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
```

with:

```python
from app.api.routes import assistant, dashboard, expenses, health, receipts, system

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(expenses.router)
api_router.include_router(receipts.router)
api_router.include_router(dashboard.router)
api_router.include_router(system.router)
api_router.include_router(assistant.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_assistant_route.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full backend suite**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/assistant.py backend/app/api/routes/assistant.py backend/app/api/router.py backend/tests/test_assistant_route.py
git commit -m "Add POST /api/assistant/chat route"
```

---

### Task 4: Frontend types, service, and i18n strings

**Files:**
- Create: `frontend/src/types/assistant.ts`
- Create: `frontend/src/services/assistantService.ts`
- Modify: `frontend/src/i18n/locales/he/translation.json`
- Modify: `frontend/src/i18n/locales/en/translation.json`

**Interfaces:**
- Produces: `ChatMessage` type (`{role: 'user' | 'assistant'; content: string}`), `sendChatMessage(message: string, history: ChatMessage[]): Promise<string>` — used by `AssistantPage` in Task 5.

No test in this task — this is plain types/config with no independent behavior; it's exercised through `AssistantPage.test.tsx` in Task 5 (matching how `dashboardService.ts` has no test of its own, only via `DashboardPage.test.tsx`).

- [ ] **Step 1: Create the type file**

Create `frontend/src/types/assistant.ts`:

```typescript
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
```

- [ ] **Step 2: Create the service file**

Create `frontend/src/services/assistantService.ts`:

```typescript
import { apiClient, toApiError } from './apiClient'
import type { ChatMessage } from '../types/assistant'

export async function sendChatMessage(message: string, history: ChatMessage[]): Promise<string> {
  try {
    const response = await apiClient.post<{ reply: string }>('/assistant/chat', { message, history })
    return response.data.reply
  } catch (error) {
    throw toApiError(error)
  }
}
```

- [ ] **Step 3: Add i18n strings**

In `frontend/src/i18n/locales/he/translation.json`, in the `"nav"` object, add `"assistant"` after `"uploadReceipt"`:

```json
    "uploadReceipt": "העלאת קבלה",
    "assistant": "עוזר AI",
```

Add a new top-level `"assistant"` section (place it alphabetically near `"dashboard"` or at the end of the file, matching the file's existing style — insert as a sibling of the other top-level sections such as `"dashboard"`, `"expenses"`, etc.):

```json
  "assistant": {
    "title": "עוזר AI",
    "subtitle": "שאל שאלות על הנתונים העסקיים שלך",
    "inputPlaceholder": "שאל שאלה...",
    "send": "שלח",
    "emptyTitle": "שאל אותי משהו על העסק שלך",
    "exampleQuestion1": "כמה מכרתי החודש?",
    "exampleQuestion2": "מי הלקוח הכי גדול שלי?",
    "exampleQuestion3": "איך המכירות משתנות לפי חודש?",
    "errorMessage": "לא הצלחתי לענות כרגע, נסה שוב."
  },
```

In `frontend/src/i18n/locales/en/translation.json`, in the `"nav"` object, add `"assistant"` after `"uploadReceipt"`:

```json
    "uploadReceipt": "Upload receipt",
    "assistant": "AI Assistant",
```

Add the matching `"assistant"` section:

```json
  "assistant": {
    "title": "AI Assistant",
    "subtitle": "Ask questions about your business data",
    "inputPlaceholder": "Ask a question...",
    "send": "Send",
    "emptyTitle": "Ask me something about your business",
    "exampleQuestion1": "How much did I sell this month?",
    "exampleQuestion2": "Who is my biggest customer?",
    "exampleQuestion3": "How do sales trend by month?",
    "errorMessage": "Couldn't get an answer right now, please try again."
  },
```

- [ ] **Step 4: Verify the JSON files are still valid**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/he/translation.json')); JSON.parse(require('fs').readFileSync('src/i18n/locales/en/translation.json')); console.log('valid')"`
Expected: `valid`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/assistant.ts frontend/src/services/assistantService.ts frontend/src/i18n/locales/he/translation.json frontend/src/i18n/locales/en/translation.json
git commit -m "Add assistant chat types, API client, and translations"
```

---

### Task 5: AssistantPage, route, and nav link

**Files:**
- Create: `frontend/src/pages/AssistantPage.tsx`
- Create: `frontend/src/pages/__tests__/AssistantPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

**Interfaces:**
- Consumes: `sendChatMessage` from `app/services/assistantService.ts`, `ChatMessage` type (Task 4).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/__tests__/AssistantPage.test.tsx`:

```typescript
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import userEvent from '@testing-library/user-event'

import { AssistantPage } from '../AssistantPage'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const CHAT_URL = 'http://localhost:8000/api/assistant/chat'

describe('AssistantPage', () => {
  it('shows example questions in the empty state', () => {
    renderWithProviders(<AssistantPage />)
    expect(screen.getByText('כמה מכרתי החודש?')).toBeInTheDocument()
  })

  it('sends a message and shows the reply', async () => {
    server.use(
      http.post(CHAT_URL, () => HttpResponse.json({ reply: 'מכרת 100 ש"ח החודש.' })),
    )
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.type(screen.getByPlaceholderText('שאל שאלה...'), 'כמה מכרתי?')
    await user.click(screen.getByRole('button', { name: 'שלח' }))

    expect(screen.getByText('כמה מכרתי?')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('מכרת 100 ש"ח החודש.')).toBeInTheDocument()
    })
  })

  it('shows an error message when the request fails', async () => {
    server.use(http.post(CHAT_URL, () => HttpResponse.json({ detail: 'unavailable' }, { status: 503 })))
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.type(screen.getByPlaceholderText('שאל שאלה...'), 'שאלה')
    await user.click(screen.getByRole('button', { name: 'שלח' }))

    await waitFor(() => {
      expect(screen.getByText('לא הצלחתי לענות כרגע, נסה שוב.')).toBeInTheDocument()
    })
  })

  it('clicking an example question sends it', async () => {
    server.use(http.post(CHAT_URL, () => HttpResponse.json({ reply: 'תשובה' })))
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.click(screen.getByText('כמה מכרתי החודש?'))

    await waitFor(() => {
      expect(screen.getByText('תשובה')).toBeInTheDocument()
    })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/__tests__/AssistantPage.test.tsx`
Expected: FAIL (module not found — `AssistantPage` doesn't exist yet)

- [ ] **Step 3: Implement AssistantPage.tsx**

Create `frontend/src/pages/AssistantPage.tsx`:

```typescript
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { sendChatMessage } from '../services/assistantService'
import { toApiError } from '../services/apiClient'
import type { ChatMessage } from '../types/assistant'

export function AssistantPage() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const exampleQuestions = [
    t('assistant.exampleQuestion1'),
    t('assistant.exampleQuestion2'),
    t('assistant.exampleQuestion3'),
  ]

  async function send(question: string) {
    const trimmed = question.trim()
    if (!trimmed || isSending) return

    const history = messages
    const userMessage: ChatMessage = { role: 'user', content: trimmed }
    setMessages([...history, userMessage])
    setInput('')
    setError(null)
    setIsSending(true)
    try {
      const reply = await sendChatMessage(trimmed, history)
      setMessages([...history, userMessage, { role: 'assistant', content: reply }])
    } catch (err) {
      setError(toApiError(err).message || t('assistant.errorMessage'))
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="mx-auto flex h-[70vh] max-w-2xl flex-col">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t('assistant.title')}</h1>
        <p className="mt-1 text-sm text-slate-500">{t('assistant.subtitle')}</p>
      </div>

      <div className="mt-6 flex-1 space-y-3 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm font-medium text-slate-700">{t('assistant.emptyTitle')}</p>
            <div className="flex flex-wrap justify-center gap-2">
              {exampleQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => send(question)}
                  className="rounded-full border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div key={index} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <p
                className={
                  msg.role === 'user'
                    ? 'max-w-[80%] rounded-lg bg-brand-600 px-3 py-2 text-sm text-white'
                    : 'max-w-[80%] rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-900'
                }
              >
                {msg.content}
              </p>
            </div>
          ))
        )}
        {error && <p className="text-sm text-danger-700">{error}</p>}
      </div>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          send(input)
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={t('assistant.inputPlaceholder')}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={isSending}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {t('assistant.send')}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Wire the route and nav link**

In `frontend/src/App.tsx`, replace:

```typescript
import { Layout } from './components/Layout'
import { AddExpensePage } from './pages/AddExpensePage'
import { DashboardPage } from './pages/DashboardPage'
import { ExpensesPage } from './pages/ExpensesPage'
import { UploadReceiptPage } from './pages/UploadReceiptPage'
```

with:

```typescript
import { Layout } from './components/Layout'
import { AddExpensePage } from './pages/AddExpensePage'
import { AssistantPage } from './pages/AssistantPage'
import { DashboardPage } from './pages/DashboardPage'
import { ExpensesPage } from './pages/ExpensesPage'
import { UploadReceiptPage } from './pages/UploadReceiptPage'
```

and replace:

```typescript
          <Route path="upload-receipt" element={<UploadReceiptPage />} />
```

with:

```typescript
          <Route path="upload-receipt" element={<UploadReceiptPage />} />
          <Route path="assistant" element={<AssistantPage />} />
```

In `frontend/src/components/Layout.tsx`, replace:

```typescript
const NAV_ITEMS = [
  { to: '/', key: 'dashboard', end: true },
  { to: '/expenses', key: 'expenses', end: false },
  { to: '/add-expense', key: 'addExpense', end: false },
  { to: '/upload-receipt', key: 'uploadReceipt', end: false },
] as const
```

with:

```typescript
const NAV_ITEMS = [
  { to: '/', key: 'dashboard', end: true },
  { to: '/expenses', key: 'expenses', end: false },
  { to: '/add-expense', key: 'addExpense', end: false },
  { to: '/upload-receipt', key: 'uploadReceipt', end: false },
  { to: '/assistant', key: 'assistant', end: false },
] as const
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run src/pages/__tests__/AssistantPage.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the full frontend suite**

Run: `npm run lint && npx tsc -b && npm test && npm run build`
Expected: all clean/passing

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/AssistantPage.tsx frontend/src/pages/__tests__/AssistantPage.test.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "Add AI Assistant chat page, route, and nav link"
```

---

### Task 6: Full verification and live check

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: all tests pass, no real OpenAI call made (all tests use a fake client or mock `answer_question`)

- [ ] **Step 2: Run the full frontend suite**

Run: `cd frontend && npm run lint && npx tsc -b && npm test && npm run build`
Expected: all clean/passing

- [ ] **Step 3: Live check in the browser**

Start both dev servers, open the app, click "עוזר AI" / "AI Assistant" in the nav, click one of the example questions, confirm a real reply comes back from the real `gpt-4o-mini` call (this does make one real, billed OpenAI request — negligible cost, consistent with the rest of this session's live verifications). Check both Hebrew and English (via the language switcher) render the page correctly, RTL and LTR.

- [ ] **Step 4: Final commit if the live check surfaced any fix**

If the live check finds a real bug, fix it, re-run the relevant test file, and commit the fix separately with a clear message — do not silently patch without a matching test update.
