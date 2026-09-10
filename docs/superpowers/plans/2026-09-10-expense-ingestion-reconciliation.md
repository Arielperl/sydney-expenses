# Automated Expense Ingestion & Reconciliation — Implementation Plan

> Implements the design in
> `docs/superpowers/specs/2026-09-10-expense-ingestion-reconciliation-design.md`.
> Executed inline, task by task, with a commit after each task's tests pass.

## Global constraints

- Money: `Decimal` everywhere new, `Numeric(12,2)` at the DB layer — never `float`.
- SQLAlchemy only, no raw SQL.
- New config vars go in `.env.example`, never a real secret in source.
- Every new DB-touching test uses `tests/conftest.py`'s per-test SQLite reset;
  every external-provider test uses a fake client — no real network calls.
- Keep `.claude/launch.json`'s existing uncommitted change out of every commit
  (`git add` specific paths, never `git add -A`).
- `CLAUDE.md` verification gate before each commit: backend
  `pytest` (+ `alembic upgrade head` on a fresh DB for the migration task, and
  on a DB seeded with pre-migration rows), frontend
  `npm run lint && npx tsc -b && npm test && npm run build`.

---

## Backend

### B1 — Migration + model changes

Files: `backend/app/models/expense.py` (extend), `backend/app/models/import_batch.py`
(new), `backend/app/models/__init__.py` (export), `backend/alembic/versions/<new>.py`,
`backend/alembic/env.py` (import new model module).

- Add `DocumentStatus(str, enum.Enum)`: `MISSING, SUGGESTED, ATTACHED, NEEDS_REVIEW, NOT_REQUIRED`.
- Add `ExpenseSource(str, enum.Enum)`: `MANUAL, RECEIPT_UPLOAD, CSV, WEBHOOK`.
- Add `ImportStatus(str, enum.Enum)`: `PENDING, COMPLETED, FAILED`.
- `Expense` gains the columns listed in the spec's table, plus a
  `UniqueConstraint('source_provider', 'external_id', name='uq_expenses_source_provider_external_id')`.
- New `ImportBatch` model per spec's table.
- Migration: create `import_batches`, add the new `expenses` columns via
  `batch_alter_table` (nullable or `server_default`-backed, matching migration
  `789ee45c9a55`'s style), add the unique constraint, then a data-migration
  step backfilling `document_status`/`source` as specified.
- Update `create_expense` (manual) to set `document_status=NOT_REQUIRED`;
  update `confirm_receipt_upload` to set `source=RECEIPT_UPLOAD`,
  `document_status=ATTACHED`.

Verify: `alembic upgrade head` on a brand-new temp SQLite DB; separately,
build a temp DB, run migrations *up to* `789ee45c9a55` only, insert a row
with the pre-feature schema shape, then upgrade to head and confirm the row
got sane defaults (`source='manual'` or `'receipt_upload'` per
`receipt_image_path`, `document_status` accordingly). `alembic downgrade -1`
then `upgrade head` again to confirm downgrade is well-formed.

### B2 — Schemas

Files: `backend/app/schemas/expense.py` (extend `ExpenseRead`), new
`backend/app/schemas/reconciliation.py`, new `backend/app/schemas/imports.py`,
new `backend/app/schemas/webhooks.py`.

- `ExpenseRead` gains: `source`, `external_id`, `source_provider`,
  `raw_description`, `occurred_at`, `document_status`,
  `reconciliation_confidence`, `reconciliation_reasons: list[str] | None`.
- `reconciliation.py`: `MatchCandidate` (expense_id, score, reasons,
  has_conflict), `ReconciliationInboxResponse` (5 lists of `ExpenseRead`,
  each capped/paginated per query params), `MatchDecisionResponse`
  (`ExpenseRead` + `status`).
- `imports.py`: `CsvRowError(row_number, message)`, `CsvPreviewRow` (parsed
  fields + computed `external_id`), `CsvPreviewResponse`,
  `CsvConfirmRequest` (echoes `file_hash`, `filename`, `valid_rows`),
  `CsvConfirmResponse`.
- `webhooks.py`: `WebhookTransactionPayload` (the fields from the spec),
  `WebhookIngestResponse{created: bool, expense_id: str}`.

### B3 — Reconciliation matching service (pure, unit-tested first)

Files: new `backend/app/services/reconciliation/__init__.py`, new
`backend/app/services/reconciliation/matching.py`, new
`backend/tests/test_reconciliation_matching.py`.

`matching.py` exports:
```python
HIGH_MATCH_THRESHOLD = 0.85
MEDIUM_MATCH_THRESHOLD = 0.55
MATCH_MARGIN = 0.15

@dataclass
class MatchScore:
    expense_id: str
    score: float
    reasons: list[str]
    has_conflict: bool

def score_candidate(expense: Expense, extracted: ExtractedReceiptData) -> MatchScore: ...
def find_candidates(db: Session, extracted: ExtractedReceiptData) -> list[MatchScore]:
    """Queries document_status='missing' expenses, scores each, returns sorted desc by score."""

class MatchDecision(str, Enum):
    AUTO_MATCH = "auto_match"
    NEEDS_REVIEW = "needs_review"
    SUGGESTED = "suggested"
    NO_MATCH = "no_match"

def decide(candidates: list[MatchScore]) -> tuple[MatchDecision, MatchScore | None]: ...
```
Write tests first for `score_candidate` (same amount/currency/date/merchant →
high score; currency mismatch caps score even with everything else matching;
date 10 days apart scores low on that component; receipt-number match adds
the bonus) and `decide` (high score + margin → AUTO_MATCH; high score but
close second candidate → SUGGESTED, not AUTO_MATCH; medium → SUGGESTED;
strong merchant+date but amount conflict → NEEDS_REVIEW; low → NO_MATCH;
empty candidate list → NO_MATCH/None). Then implement to pass.

### B4 — Reconciliation workflow service + routes

Files: new `backend/app/services/reconciliation/workflow.py`, new
`backend/app/api/routes/reconciliation.py`, wire into
`backend/app/api/routes/receipts.py` and `backend/app/api/router.py`, new
`backend/tests/test_reconciliation_workflow.py`, new
`backend/tests/test_reconciliation_route.py`.

`workflow.py`:
```python
def apply_match_result(db: Session, upload: ReceiptUpload, extracted: ExtractedReceiptData) -> ReceiptUploadResponse:
    """Called from POST /receipts/upload after extraction succeeds.
    Runs find_candidates + decide; on AUTO_MATCH attaches now (updates the
    matched Expense's document fields without overwriting amount/currency/
    occurred_at, marks the ReceiptUpload confirmed); on SUGGESTED/NEEDS_REVIEW
    sets the candidate Expense's document_status/confidence/reasons/
    suggested_receipt_upload_id and leaves the ReceiptUpload pending; on
    NO_MATCH does nothing (existing behavior)."""

def approve_suggested_match(db: Session, expense_id: str) -> Expense:
    """Atomic conditional UPDATE ... WHERE document_status IN
    ('suggested','needs_review') RETURNING *; 0 rows affected -> re-read and
    return current state (idempotent, not an error)."""

def reject_suggested_match(db: Session, expense_id: str) -> Expense:
    """Same idempotent pattern, clears back to missing."""

def build_inbox(db: Session, limit: int = 20) -> ReconciliationInboxResponse:
    """The 5 bounded queries from the spec."""
```

`reconciliation.py` routes:
- `GET /reconciliation/inbox?limit=` → `ReconciliationInboxResponse`
- `POST /reconciliation/matches/{expense_id}/approve` → `MatchDecisionResponse`
- `POST /reconciliation/matches/{expense_id}/reject` → `MatchDecisionResponse`

Extend `receipts.py`'s upload handler to call `apply_match_result` after a
successful extraction and merge its outcome into `ReceiptUploadResponse`
(new optional fields: `auto_matched: bool`, `matched_expense:
ExpenseRead | None`, `match_reasons: list[str] | None`,
`suggested_match: MatchCandidateRead | None`). No-match path is byte-for-byte
the existing response shape (additive fields only, all optional/None).

Tests: high-confidence auto-match end-to-end through `/receipts/upload`;
suggested match then approve then reject; two concurrent approve calls on the
same suggested expense (only one succeeds in creating the attach side effect,
both return 200 with the same final state); amount/currency conflict →
needs_review; inbox query shapes with seeded data in each of the 5 states.

### B5 — Webhook ingestion

Files: new `backend/app/services/ingestion/__init__.py`, new
`backend/app/services/ingestion/webhook_provider.py`, new
`backend/app/api/routes/webhooks.py`, wire into `router.py`, extend
`backend/app/core/config.py` (`webhook_signing_secret: str | None`,
`webhook_timestamp_tolerance_seconds: float = 300.0`,
`webhook_max_body_bytes: int = 65536`), extend `.env.example`, new
`backend/scripts/demo_webhook_request.py`, new
`backend/tests/test_webhook_ingestion.py`.

`webhook_provider.py`:
```python
@dataclass
class TransactionEvent:
    event_id: str
    provider: str
    external_transaction_id: str
    occurred_at: datetime
    merchant_name: str
    amount: Decimal
    currency: str
    payment_method: str | None
    description: str | None

def parse_demo_provider_event(payload: dict) -> TransactionEvent: ...

WEBHOOK_PROVIDERS: dict[str, Callable[[dict], TransactionEvent]] = {"demo-bank": parse_demo_provider_event}
```

`routes/webhooks.py`:
```python
@router.post("/transactions", status_code=200)
async def ingest_transaction(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> WebhookIngestResponse:
    raw_body = await request.body()
    # size check, signature check (X-Signature/X-Timestamp), timestamp skew check
    # parse JSON, look up WEBHOOK_PROVIDERS[payload["provider"]], build TransactionEvent
    # idempotent insert via (source_provider, external_id) lookup + IntegrityError handling
```
401 on bad/missing signature, 401 on stale timestamp, 413 on oversized body,
422 on malformed/unknown-provider payload.

`demo_webhook_request.py`: builds one sample event (ILS 184.90, fictional
merchant), signs with `os.environ.get("WEBHOOK_SIGNING_SECRET",
"demo-secret-change-me")`, POSTs to `http://localhost:8000/api/webhooks/transactions`
via `httpx`. Docstring/comment makes clear this is a local dev placeholder,
never a real secret.

Tests: valid signature → 201 created; invalid signature → 401; stale
timestamp → 401; oversized body → 413; malformed payload → 422; same
`event_id`/`external_transaction_id` delivered twice → second call returns
`created: false`, no second `Expense` row; two concurrent identical requests
(via two DB sessions/threads or a forced `IntegrityError` simulation) → only
one `Expense` row exists after both complete, both responses are 200/201
with correct `created` flags; response/log assertions confirm the secret and
signature never appear in any error body or captured log line.

### B6 — CSV import

Files: new `backend/app/services/ingestion/csv_import.py`, new
`backend/app/api/routes/imports.py`, wire into `router.py`, extend
`config.py` (`csv_max_file_size_bytes`, `csv_max_rows`), new
`backend/samples/expenses-sample.csv` (fictional data, documented format),
new `backend/tests/test_csv_import.py`.

`csv_import.py`:
```python
@dataclass
class ParsedCsvRow:
    row_number: int
    expense_date: date
    description: str
    merchant: str
    amount: Decimal
    currency: str
    external_id: str  # f"csv:{file_hash}:{row_number}"

def parse_csv(raw_bytes: bytes, file_hash: str, *, max_rows: int) -> tuple[list[ParsedCsvRow], list[CsvRowError]]: ...
def create_import_batch_and_expenses(db: Session, file_hash: str, filename: str, rows: list[ParsedCsvRow]) -> ImportBatch:
    """One ImportBatch row, then one Expense per row inside a per-row
    session.begin_nested() savepoint so an IntegrityError (duplicate
    external_id) only skips that row, not the whole batch. Returns the
    batch with created_count/duplicate_count/status set."""
```

`routes/imports.py`:
- `POST /imports/csv/preview` (multipart) → `CsvPreviewResponse`
- `POST /imports/csv/confirm` (JSON body `CsvConfirmRequest`) → `CsvConfirmResponse`

Tests: valid file → correct row count/parsed fields; UTF-8 BOM file parses
identically to plain UTF-8; a file with one malformed row → that row in
`errors`, the rest in `valid_rows`; oversized file → 413; row-count-over-limit
→ 413 or a clear validation error; confirming the same file twice → second
confirm's `duplicate_count` equals the row count, `created_count` is 0, no
new `Expense` rows.

### B7 — Dashboard stats

Files: extend `backend/app/schemas/dashboard.py`, extend
`backend/app/services/dashboard_service.py`, extend
`backend/tests/test_dashboard.py`.

`DashboardStats` gains: `missing_documents_count: int`,
`missing_documents_total: Decimal`, `matches_awaiting_confirmation_count: int`,
`document_attachment_rate: float | None` (per the spec's denominator rule —
`None` when the denominator is 0, so the frontend can render "—" instead of
a misleading 0%).

Tests: each new field's math against seeded expenses in each `document_status`.

### B8 — AI assistant corrections

Files: `backend/app/services/assistant/tools.py`,
`backend/app/services/assistant/orchestrator.py`, update
`backend/tests/test_assistant_tools.py`, `backend/tests/test_assistant_orchestrator.py`.

- Rename `get_total_revenue`→`get_total_expenses`,
  `get_revenue_trend`→`get_expense_trend` (function name, `TOOL_DEFINITIONS`
  entry name/description, `TOOL_FUNCTIONS` key) — behavior unchanged.
- Add `get_missing_documents_summary`, `get_match_rate`,
  `get_pending_suggestions_summary` per the spec's signatures, following the
  exact existing pattern (`(db: Session, ...) -> dict`, `{"error": ...}` on
  bad input, added to both `TOOL_FUNCTIONS` and `TOOL_DEFINITIONS`).
- Rewrite `_SYSTEM_PROMPT` to say "expense tracking app" / never "sales".

Tests: the 3 new tools directly against a seeded DB session (mirroring the
existing 5 tools' test style); orchestrator test updated to reference the
renamed tool names where it asserts on tool-call dispatch.

---

## Frontend

### F1 — Types, schemas, services

Files: extend `frontend/src/types/expense.ts` (add `source`,
`document_status`, etc. to `Expense`), new
`frontend/src/types/reconciliation.ts`, new `frontend/src/types/imports.ts`,
new `frontend/src/services/reconciliationService.ts`, new
`frontend/src/services/importService.ts`.

Mirrors the backend schemas 1:1 (same field names, camelCase kept as-is
since the existing `Expense` type already uses snake_case matching the API
directly — continue that convention, no transformation layer). Services
follow the existing thin-wrapper-over-`apiClient` + `toApiError` pattern
exactly (see `expenseService.ts`).

### F2 — Nav + i18n scaffolding

Files: `frontend/src/components/Layout.tsx` (add 2 `NAV_ITEMS` entries —
`Inbox` icon for `/reconciliation`, `PlugZap` icon for `/imports`, both from
`lucide-react`), `frontend/src/App.tsx` (2 new routes), both locale JSON
files (new `reconciliation.*` and `imports.*` namespaces, plus `nav.reconciliation`/
`nav.imports` keys).

### F3 — Reconciliation Inbox page

Files: new `frontend/src/pages/ReconciliationInboxPage.tsx`, new
`frontend/src/components/MatchSuggestionCard.tsx` (approve/reject buttons +
reason chips), new `frontend/src/components/DocumentStatusBadge.tsx`, new
`frontend/src/pages/__tests__/ReconciliationInboxPage.test.tsx`.

Five sections per the spec, each using the existing `EmptyState`/
`LoadingState`/`ErrorState` components for its own loading/empty/error state
(not one big page-level state — each section can be independently empty).
`useMutation` for approve/reject, invalidating `['reconciliation-inbox']` and
`['dashboard-stats']` on success (matching the existing invalidation
convention).

### F4 — Imports & Connections page

Files: new `frontend/src/pages/ImportsPage.tsx`, new
`frontend/src/components/CsvImportWizard.tsx` (local state machine: idle →
uploading → previewed → confirming → summary), new
`frontend/src/pages/__tests__/ImportsPage.test.tsx`.

Preview step shows valid-row count + an errors table; confirm step posts
back the previewed rows; summary shows created/duplicate/error counts. A
static "Webhook demo connection" panel: honest copy (not a live connection),
the exact local curl/script command, and — since there is no user-facing way
to *run* a Python script from the browser — a plainly formatted code block,
not a fake "connect" button.

### F5 — Expense list badges + receipt upload match handling

Files: `frontend/src/components/ExpenseList.tsx` (add source +
document-status badges per row, reusing `DocumentStatusBadge`),
`frontend/src/pages/UploadReceiptPage.tsx` (branch on the extended
`ReceiptUploadResponse`: `auto_matched` → show which expense + why;
`suggested_match` → approve/reject inline instead of the blank confirm form;
neither → existing confirm-form behavior, unchanged).

### F6 — Dashboard updates

Files: `frontend/src/pages/DashboardPage.tsx` (2 new `StatCard`s: missing
documents, matches awaiting confirmation; attachment-rate shown as a
percentage badge near the category chart), `frontend/src/types/dashboard.ts`
(extend `DashboardStats`).

### F7 — Assistant copy fixes

Files: both locale JSON files (`assistant.exampleQuestion1/2/3` reworded to
expense framing), `frontend/src/pages/__tests__/AssistantPage.test.tsx`
(update the pinned Hebrew strings/mocked reply to match).

---

## Final

- Update `README.md`: automated-vs-manual capability list, the demo
  end-to-end scenario (ILS 184.90) from the spec, CSV import instructions,
  webhook local-test instructions, reconciliation explanation, and an
  explicit "still needs a real banking/PSP provider" list.
- Run full backend (`pytest`) and frontend
  (`lint && tsc -b && test && build`) suites; fix any regression.
- Re-verify `alembic upgrade head` on both a fresh DB and a DB carried
  forward from before this migration.
- Commit in the same task-by-task increments used during implementation
  (already true if each task above ends with its own commit); push to
  `origin main` per `CLAUDE.md`.
- Final report: capabilities added, verification results, commit list, push
  status, and what still needs a real banking provider.
