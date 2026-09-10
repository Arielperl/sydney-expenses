# Automated Expense Ingestion & Reconciliation — Design Spec

## Problem

Sydney Transaction Management currently only learns about an expense when a human manually creates
one or uploads a receipt for OCR. The product goal is to flip this: expenses
should arrive automatically from a financial source, and the user's job
narrows to handling exceptions — a transaction with no document, a document
with no transaction, an uncertain match, conflicting data, or a duplicate/
failed import. Manual entry, manual upload, OCR, and human review must all
keep working unchanged as fallbacks.

## Domain language

Sydney Transaction Management is an **expense management** product, not a sales/revenue product.
User-facing copy and the AI assistant use *expense*, *merchant/vendor*,
*total expenses*, *spending trend* — never *revenue*, *sales*, *customer*.
This is a language-and-tool-naming fix (assistant tool names, example
questions, system prompt), not a database rename.

## Architecture decision: `Expense` stays the one record

Rather than introducing a separate "bank transaction" table that later merges
into `Expense`, an incoming webhook or CSV row **becomes an `Expense` row
directly**, with `document_status='missing'` until a receipt is attached.
This keeps `Expense` the single central record (per the constraint to not
break the existing app), and lets every existing list/dashboard/assistant
query keep working against one table. A `Transaction` staging table was
considered and rejected: it would duplicate the amount/currency/date/merchant
fields `Expense` already has, and every "attach a receipt" operation would
still end up copying those fields onto an `Expense` anyway.

## Data model changes (additive, one Alembic migration)

### `Expense` — new columns

| Column | Type | Notes |
|---|---|---|
| `source` | `Enum(manual, receipt_upload, csv, webhook)` NOT NULL, default `manual` | How the row was created |
| `external_id` | `String(255)` nullable | Source's own transaction id (webhook payload id, or `csv:<file_hash>:<row>` for CSV) |
| `source_provider` | `String(64)` nullable | `"csv"`, or the webhook provider name (e.g. `"demo-bank"`); `NULL` for manual/receipt_upload |
| `raw_description` | `Text` nullable | Verbatim description text from the source |
| `occurred_at` | `DateTime` nullable | Precise source timestamp, when the source supplies one |
| `document_status` | `Enum(missing, suggested, attached, needs_review, not_required)` NOT NULL, default `not_required` | Reconciliation state |
| `reconciliation_confidence` | `Float` nullable | 0–1 match score, set only when a match was scored |
| `reconciliation_reasons` | `JSON` nullable | Short list of reason codes, e.g. `["same_amount","date_same_day"]` — never the full extracted payload |
| `suggested_receipt_upload_id` | `String(36)` FK → `receipt_uploads.id`, `ON DELETE SET NULL`, nullable | The candidate receipt while `document_status='suggested'`/`'needs_review'` |
| `import_batch_id` | `String(36)` FK → `import_batches.id`, `ON DELETE SET NULL`, nullable | Traceability for CSV-sourced rows |

Constraint: `UNIQUE(source_provider, external_id)`. SQL treats every `NULL`
as distinct, so existing manual/receipt_upload rows (`external_id=NULL`)
never collide with each other or with this constraint. This is the
**database-level** duplicate guard: ingestion always attempts an `INSERT`
and treats a unique-violation as "already exists" (see Idempotency below),
which is race-safe under concurrent delivery — a `SELECT`-then-`INSERT`
check is not.

**Backfill for existing rows** (part of the same migration): 
`document_status = 'attached' WHERE receipt_image_path IS NOT NULL`, else
stays `'not_required'` (a pre-existing manual expense was never expected to
have a receipt — retroactively marking it `'missing'` would flood the new
Inbox with old data). `source = 'receipt_upload' WHERE receipt_image_path IS
NOT NULL`, else stays `'manual'`.

New manual/receipt-upload creations keep today's behavior:
`create_expense` (manual form) sets `document_status='not_required'`;
`confirm_receipt_upload` sets `source='receipt_upload'`,
`document_status='attached'`.

### `ImportBatch` — new table

| Column | Type |
|---|---|
| `id` | `String(36)` PK |
| `file_hash` | `String(64)` NOT NULL, indexed (SHA-256 of the uploaded bytes) |
| `filename` | `String(255)` nullable |
| `status` | `Enum(pending, completed, failed)` NOT NULL, default `pending` |
| `valid_row_count` | `Integer` NOT NULL |
| `error_row_count` | `Integer` NOT NULL |
| `created_count` | `Integer` nullable (set on confirm) |
| `duplicate_count` | `Integer` nullable (set on confirm) |
| `created_at` | `DateTime` NOT NULL |

Money stays `Decimal`/`Numeric(12,2)` everywhere new, matching the existing
`Expense.amount`/`vat_amount` convention — never `float`.

## Webhook ingestion

`POST /api/webhooks/transactions` — provider-agnostic endpoint; the JSON body
carries `provider`. A small `WEBHOOK_PROVIDERS` registry (one function per
provider: raw payload → canonical `TransactionEvent`) is the extension point
for a real bank/PSP later; only a `"demo-bank"` provider ships now.

Request headers: `X-Signature` (hex HMAC-SHA256), `X-Timestamp` (unix
seconds). Verification: `hmac.compare_digest(expected, provided)` where
`expected = HMAC_SHA256(secret, f"{timestamp}.{raw_body}")` — signed over the
**raw request bytes**, read once via `await request.body()` before any JSON
parsing, so signature verification can never be fooled by re-serialization.
Requests with `|now - timestamp| > WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS`
(default 300s) are rejected (replay protection). Body size is checked against
`WEBHOOK_MAX_BODY_BYTES` (default 64KB) before parsing. The secret comes from
`WEBHOOK_SIGNING_SECRET` in settings/`.env` — never hardcoded, added to
`.env.example` as a placeholder. Logs never include the payload, signature,
or secret — only `event_id`/`provider`/outcome.

Payload fields: `event_id`, `provider`, `external_transaction_id`,
`occurred_at`, `merchant_name`, `amount`, `currency`, optional
`payment_method`, optional `description`.

**Idempotency**: look up `Expense` by `(source_provider=provider,
external_id=external_transaction_id)`. If found, return `200` with
`{"created": false, "expense_id": ...}`. If not found, insert; on
`IntegrityError` (concurrent duplicate), re-query and return the same
`created: false` shape — never raise a 500 for a race that the unique
constraint already resolved correctly. A genuinely new row returns `201`
with `{"created": true, "expense_id": ...}`.

New `Expense` fields from a webhook: `source='webhook'`,
`source_provider=<provider>`, `external_id=<external_transaction_id>`,
`business_name=<merchant_name>`, `amount`, `currency`,
`occurred_at=<parsed timestamp>`, `expense_date=occurred_at.date()`,
`raw_description=<description>`, `payment_method`, `category='other'`
(unknown until reconciled or edited), `document_status='missing'`.

A demo script (`backend/scripts/demo_webhook_request.py`) builds a sample
event, signs it with a local-only placeholder secret read from the
environment, and posts it to `localhost:8000` — no real secret in source.

## CSV import

One documented format (header row required):
`date,description,merchant,amount,currency`. Ambiguous-column guessing is
explicitly out of scope for v1.

Two-step flow, mirroring the existing receipt upload/confirm shape but
without a server-side staging file (the frontend re-submits the *validated
rows*, not the raw file, at confirm time — avoiding a second file-storage
mechanism):

1. `POST /api/imports/csv/preview` — multipart upload. Parses with
   `csv.reader` over `io.TextIOWrapper(file, encoding="utf-8-sig")` (handles
   both plain UTF-8 and UTF-8 with BOM transparently). Enforces
   `CSV_MAX_FILE_SIZE_BYTES` and `CSV_MAX_ROWS`. Validates each row (date
   parses, amount is a positive `Decimal`, currency is a 3-letter code,
   merchant non-empty) and returns `{file_hash, valid_rows: [...], errors:
   [{row_number, message}], is_repeat_file: bool}`. Nothing is persisted yet.
   `is_repeat_file` (an existing `ImportBatch` with the same `file_hash`) is
   informational only — "same merchant/amount/date" is not necessarily a
   duplicate, so this never blocks, it only warns.
2. `POST /api/imports/csv/confirm` — takes back `{file_hash, filename,
   valid_rows}` (the same rows the preview returned, so nothing is
   re-parsed). Creates one `ImportBatch` row, then inserts one `Expense` per
   row with `source='csv'`, `source_provider='csv'`,
   `external_id=f"csv:{file_hash}:{row_number}"` (deterministic — reimporting
   the identical file reproduces the identical ids, so the unique constraint
   naturally rejects the repeats), `document_status='missing'`,
   `import_batch_id`. Each row insert is wrapped in a `session.begin_nested()`
   savepoint so one duplicate/failed row can't roll back the whole batch.
   Returns `{import_batch_id, created_count, duplicate_count, error_count}`.

A sample CSV with fictional data ships at `backend/evaluation/` or a new
`backend/samples/` directory, referenced by the README's demo walkthrough.

## Reconciliation matching

Pure, deterministic, offline — **no AI model participates in the matching
decision**, and no financial data is sent to an AI service as part of it.
Lives in `app/services/reconciliation/matching.py`, callable directly with a
DB session and an `ExtractedReceiptData`, with no HTTP dependency, so it's
unit-testable in isolation.

Score components (0.0–1.0 total):

- **Amount + currency** (up to 0.5): different currency, or amount differing
  by more than a small tolerance, is a **strong negative** — it caps the
  achievable score rather than being averaged away by other signals.
- **Date proximity** (up to 0.25): full points same-day, decaying linearly to
  0 by 7 days apart.
- **Merchant-name similarity** (up to 0.2): both names normalized
  (lowercase, strip punctuation/whitespace) and compared with
  `difflib.SequenceMatcher` — no new dependency needed.
- **Receipt number match** (+0.15 bonus, capped at 1.0): both sides have a
  receipt number and they're equal.

Candidates are every `Expense` with `document_status='missing'`. The
decision policy:

- **Auto-match**: best candidate's score ≥ `HIGH_MATCH_THRESHOLD` (0.85) *and*
  it beats the second-best by ≥ `MATCH_MARGIN` (0.15). The receipt is
  attached immediately — no user step.
- **Needs review**: best candidate has strong non-monetary signals (merchant
  similarity high, date within 1 day) but a currency or amount conflict —
  surfaced distinctly so the user sees *why* it wasn't auto-matched or
  quietly suggested.
- **Suggested**: score in `[MEDIUM_MATCH_THRESHOLD (0.55), HIGH_MATCH_THRESHOLD)`
  with no conflict — requires explicit user approval.
- **No match**: below `MEDIUM_MATCH_THRESHOLD` — the expense stays `missing`;
  today's manual-confirm flow is offered unchanged (this is the existing
  behavior, completely untouched when no candidate qualifies).

A matched receipt **fills gaps** (`vat_amount`, `receipt_number`, `category`
if the expense doesn't already have a confident value) and **never
overwrites** `amount`, `currency`, or `occurred_at`/`expense_date` that came
from the financial source — those are ground truth from the bank/CSV.

Reason codes stored in `reconciliation_reasons` (short, structured, not the
raw extracted payload): `same_amount`, `amount_close`, `amount_mismatch`,
`same_currency`, `currency_mismatch`, `date_same_day`, `date_within_3_days`,
`date_far`, `merchant_similar`, `merchant_different`,
`receipt_number_match`. The frontend maps each to a translated phrase.

### Where matching runs

`POST /receipts/upload` (existing endpoint, extended) — after extraction
succeeds, before returning the response, run matching against
`document_status='missing'` candidates:

- Auto-match → attach now (update the matched `Expense`'s document fields,
  mark the `ReceiptUpload` `confirmed` with `expense_id` set), respond with
  `auto_matched: true`, the matched expense, and the reasons.
- Suggested/needs-review → set the candidate `Expense`'s
  `document_status`/`reconciliation_confidence`/`reconciliation_reasons`/
  `suggested_receipt_upload_id`; the `ReceiptUpload` stays `pending`.
  Respond with `suggested_match: {...}`.
- No match → **unchanged existing behavior**: return `extracted_data` for the
  user to confirm via the existing form (which may still create a brand new
  expense, exactly as today).

### Approve / reject a suggestion

`POST /api/reconciliation/matches/{expense_id}/approve` and `.../reject`.
Both use the same atomic-conditional-update pattern the codebase already
uses in `confirm_receipt_upload` (`UPDATE ... WHERE document_status IN
('suggested','needs_review') RETURNING ...`) instead of
select-then-update, so two concurrent approvals on the same expense can't
both succeed, and a repeat call is idempotent (0 rows affected → re-read and
return current state, not an error). Approve: attaches the suggested
receipt (mirrors the auto-match attach step) and marks the `ReceiptUpload`
confirmed. Reject: clears `document_status` back to `missing` and clears the
suggestion fields; the `ReceiptUpload` stays `pending`, available for the
user to manually create a new expense from it via the existing confirm flow.

## Reconciliation Inbox

`GET /api/reconciliation/inbox` aggregates five sections, each a bounded,
paginatable query against `Expense`:

1. **Missing documents** — `document_status='missing'`.
2. **Suggested matches** — `document_status IN ('suggested','needs_review')`.
3. **Documents without transactions** — `source='receipt_upload' AND
   external_id IS NULL` (a receipt exists with no corroborating bank-side
   transaction).
4. **Cases requiring review** — `document_status='needs_review'` (also
   present in #2, but called out with its conflict reasons highlighted).
5. **Recently completed matches** — `document_status='attached' AND
   reconciliation_confidence IS NOT NULL`, most recent first, capped (10).

This is a dedicated workflow page, not a repeat of the Dashboard: every
section is either empty (nothing to do) or a concrete, actionable list.

## Imports & Connections page

CSV upload/preview/confirm (above), plus a status panel for the demo
webhook: explicitly labeled as a **provider interface and demo integration**
(not a live bank connection), with the exact `curl`/script command to send a
signed test event locally. Honesty here matters — the page must not imply a
real bank is connected.

## Dashboard additions

- Expenses missing documents: count + total value.
- Matches awaiting confirmation: count.
- Document attachment rate: `attached / (attached + missing + suggested +
  needs_review)` as a percentage (rows that are `not_required` are excluded
  from the denominator — they were never expected to have a document).
- Recent expenses already show `source`; the existing recent-expenses list
  gains a small source badge.

## AI Assistant corrections

Tool renames (behavior unchanged, name/framing only):
`get_total_revenue` → `get_total_expenses`, `get_revenue_trend` →
`get_expense_trend`. `get_top_merchants`/`get_category_breakdown`/
`list_recent_expenses` already use correct language and keep their names.
System prompt rewritten to describe an "expense tracking app" (not
"expense/sales"), business owner, never "sales".

Three new read-only tools, same safety pattern as the existing five (never
raise, return `{"error": ...}` on bad input, no write capability, no AI
model call as part of any matching decision):

- `get_missing_documents_summary(db) -> {"count": int, "total": str}`
- `get_match_rate(db) -> {"attached": int, "missing": int, "suggested": int, "rate": str}`
- `get_pending_suggestions_summary(db) -> {"count": int}`

Frontend example-question copy (`assistant.exampleQuestion1/2/3`, both
locales) changes from sales/customer framing to expense framing — e.g. "How
much did I spend this month?" / "Which merchant do I spend the most at?" /
"How does my spending trend by month?". The one test file that pins the old
Hebrew strings (`AssistantPage.test.tsx`) is updated alongside.

## Security & reliability checklist

- No secret in source; new vars only in `.env.example`.
- Webhook: HMAC + timestamp + body-size limit, raw-body signing, no payload/
  signature/secret in logs.
- CSV: file-size and row-count caps; per-field validation; per-row savepoint
  so one bad/duplicate row doesn't abort a batch.
- All new money handling: `Decimal`, never `float`.
- Idempotency enforced by DB unique constraint + `IntegrityError` handling,
  not just an application-level pre-check.
- SQLAlchemy throughout; no raw SQL.
- No financial data sent to an AI service as part of matching (matching is
  pure Python/SQL).
- All new automated tests run offline against fakes/mocks — no real webhook
  caller, no real OpenAI/Ollama/Supabase call.

## Explicitly out of scope (extension points only)

Real bank OAuth/live connections, authentication, organizations/roles, real
email ingestion. The `WEBHOOK_PROVIDERS` registry and the `ReceiptExtractor`/
`ReceiptStorage`-style provider abstraction are the seams a real integration
would plug into later; nothing here claims they already work.

## Testing

Backend: migration (fresh DB + upgrading a DB with existing pre-migration
rows), webhook (valid/invalid signature, stale timestamp, repeat delivery,
concurrent duplicate insert), CSV (valid file, UTF-8 BOM, malformed row,
oversized file, repeat import), matching (high-confidence, suggested,
no-match, two close candidates, amount/currency conflict, concurrent
approve-twice), dashboard stats, assistant tools (renamed + new). All via
the existing `tests/conftest.py` per-test SQLite reset fixture and fake
HTTP/OpenAI clients — no real network calls.

Frontend: CSV preview/confirm flow, every Inbox section state (empty,
populated), approve/reject a suggestion, source/document-status badges,
receipt upload leading to auto-match/suggestion/no-match, Hebrew+English
translations for all new copy. MSW handlers for every new endpoint;
`renderWithProviders` as today; assertions on behavior/text/roles, not CSS
classes (except where the existing suite's own precedent already does that
for a specific regression).
