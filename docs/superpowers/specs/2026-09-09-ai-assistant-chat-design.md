# AI Assistant Chat — Design Spec

**Date:** 2026-09-09
**Status:** Approved for implementation

## Goal

Let a business owner ask natural-language questions about the expense/sales
records already stored in Receiptly's database (e.g. "how much did I sell
this month?", "who's my biggest customer?", "how's revenue trending?") and
get a natural-language answer, without writing any filters or reports by
hand.

## Explicitly out of scope for this round

- **Item/product-level questions** ("what's my best-selling item"). The
  `Expense` model has no line-item table — extraction currently captures only
  a receipt's total, not its individual products/quantities. Adding that is a
  separate, larger project (new table, extraction-prompt changes, review-form
  UI) and is not part of this spec.
- **Persisted conversation history.** Chat history lives only in frontend
  React state for this round; it resets on page reload. No new DB table for
  messages.
- **Any data-modifying action from chat.** The assistant can only read data,
  never create/update/delete an expense.

## Architecture

```
User message (Hebrew or English)
        │
        ▼
POST /api/assistant/chat  (FastAPI route)
        │
        ▼
AssistantService — a bounded tool-calling loop against OpenAI
        │
        ├─ sends: user message + conversation history + tool definitions
        ├─ OpenAI decides to call 0+ of the read-only tools below
        ├─ each tool call runs a plain SQLAlchemy query against the real DB
        ├─ tool results are fed back to the model
        └─ loop ends when the model returns a final text answer,
           or after a hard cap of tool-call rounds (5) is hit
        │
        ▼
Natural-language reply → JSON response → frontend chat UI
```

The model **never** writes or executes SQL itself, and never sees the raw
database schema — only the small set of typed tool functions below. This
makes the boundary between "what the AI can influence" and "what actually
touches the database" a fixed, auditable set of Python functions, not
anything the model's own output controls.

## Tools (read-only, SQLAlchemy ORM only — no raw SQL)

Implemented in `app/services/assistant/tools.py`, one plain function each,
each independently unit-testable against a seeded test database:

| Tool | Parameters | Returns |
|---|---|---|
| `get_total_revenue` | `start_date?, end_date?, category?` | total amount (sum), count of matching expenses |
| `get_category_breakdown` | `start_date?, end_date?` | list of `{category, total, count}`, sorted by total desc |
| `get_top_merchants` | `limit=5, start_date?, end_date?` | list of `{business_name, total, count}`, sorted by total desc |
| `get_revenue_trend` | `period="month"\|"week", start_date?, end_date?` | list of `{period_start, total, count}` |
| `list_recent_expenses` | `limit=10, category?` | list of `{business_name, amount, category, expense_date}` |

All date parameters are ISO date strings, optional (omitted = no filter on
that bound). All tools filter out nothing else — the assistant answers over
the same data the Dashboard/Expenses pages already show.

## Model orchestration

- Model: `gpt-4o-mini` via `OPENAI_API_KEY` (already configured) — this is a
  text/tool-calling task, not vision, so the cheaper model is the right
  default; no new billing setup needed.
- Uses OpenAI's native tool-calling (function calling), not a hand-rolled
  prompt-parsing scheme.
- Loop cap: 5 tool-call rounds per user message, then force a final answer
  from whatever's been gathered — prevents a runaway loop from one confused
  or adversarial question ballooning cost or hanging.
- If the model has genuinely insufficient data to answer (e.g. asks about a
  date range with zero expenses), it's instructed to say so plainly rather
  than invent a number — the same "never guess" principle the receipt
  extraction pipeline already follows.

## API contract

`POST /api/assistant/chat`

Request:
```json
{
  "message": "כמה מכרתי החודש?",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

Response:
```json
{
  "reply": "החודש מכרת בסה\"כ 4,320 ₪ מתוך 18 קבלות."
}
```

`history` is passed in by the frontend from its own React state each call —
the backend is stateless between requests (no server-side session/thread).

## Error handling

- OpenAI request fails (timeout/rate-limit/auth) → the route returns HTTP
  `503` with a safe, generic JSON `{"detail": "..."}` body (never the raw
  provider exception text); frontend shows "לא הצלחתי לענות כרגע, נסה שוב" —
  same pattern already used for receipt-extraction failures, never a raw
  crash.
- A tool function itself errors (e.g. bad DB state) → caught, logged safely
  (no data content in logs, matching the rest of the codebase), surfaced to
  the model as a tool error so it can tell the user something went wrong
  rather than silently returning nothing.

## Frontend

- New page, new nav item **"עוזר AI" / "AI Assistant"**, alongside the
  existing Dashboard / Expenses / Add Expense / Upload Receipt items.
- Simple chat UI: scrollable message list, text input, RTL/LTR aware like
  the rest of the app, both locales in `i18n/locales/{he,en}/translation.json`.
- Empty state shows 3-4 clickable example questions instead of a blank
  screen (mirrors the "realistic working state" principle used elsewhere).
- Conversation state: local React state only (see Explicitly out of scope).

## Testing plan

- **Backend:** unit tests per tool function against a seeded test DB (known
  inputs → known aggregates, e.g. "3 expenses totaling 300 in groceries" →
  `get_category_breakdown` returns `{groceries: 300, count: 3}`). Endpoint
  tests using a fake OpenAI client (same `_FakeResponse`-style pattern as
  `test_openai_extractor.py`) so the test suite never makes a real, billed
  API call.
- **Frontend:** component test for the chat page using MSW-mocked
  `/api/assistant/chat`, matching the existing test setup.
- Full backend `pytest` + frontend `lint`/`tsc -b`/`test`/`build` must all
  pass before this is considered done, per this repo's standard.

## Security notes

- No tool can modify data — enforced by only ever defining read-only tool
  functions, never exposing a write path to the model.
- No raw SQL is ever constructed from model output or user input — every
  query is a parameterized SQLAlchemy ORM call.
- The model is never shown the real database schema/table/column names,
  only the tool signatures above.
