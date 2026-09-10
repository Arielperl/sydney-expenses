# Reconciliation-First Flow — Implementation Plan

> Implements `docs/superpowers/specs/2026-09-10-reconciliation-first-flow-design.md`.
> Executed inline, task by task, commit after each task's tests pass.

## Global constraints

Same as the ingestion/reconciliation plan: `Decimal` for money, SQLAlchemy
only, no secret in source, per-test SQLite reset + fake clients, keep
`.claude/launch.json` out of every commit, `CLAUDE.md` verification gate
before each commit.

---

## Backend

### B1 — Persist the extraction snapshot (migration + model)

Files: `backend/app/models/receipt_upload.py` (add `DISCARDED` to
`ReceiptUploadStatus`; add the 9 snapshot columns), new
`backend/alembic/versions/<new>.py` (additive: 9 nullable columns on
`receipt_uploads`; no data backfill needed — old rows just have `NULL`
snapshots, which is correct since nothing was extracted-and-lost for them
under the *old* code path... actually it was lost, so old rows legitimately
have no recoverable snapshot — `NULL` is the honest value).

Verify: `alembic upgrade head` fresh DB + a DB carried from before this
migration (insert a pre-migration `receipt_uploads` row, upgrade, confirm
the new columns exist and are `NULL` on it, nothing else changed).

### B2 — Populate the snapshot at upload time

Files: `backend/app/repositories/receipt_upload_repository.py` (new method
`save_extraction(upload_id, extracted: ExtractedReceiptData) -> None`),
`backend/app/api/routes/receipts.py` (call it right after extraction
succeeds, before the matching branches).

Test: `test_receipt_upload.py` or a new assertion — upload succeeds, then
directly query the `ReceiptUpload` row and confirm the snapshot columns
match `extracted_data`.

### B3 — Targeted attach: extend `POST /receipts/upload` + new attach executor

Files: `backend/app/schemas/receipt.py` (upload takes optional
`expense_id: str | None` form field; extend `ReceiptUploadResponse` with
`attached_to_expense_id: str | None` and `conflict: ConflictInfo | None`
where `ConflictInfo` has `expense` (business_name/amount/currency/
expense_date) + `reasons`), new `backend/app/schemas/reconciliation.py`
addition (`AttachRequest{upload_id, expense_id}`), extend
`backend/app/services/reconciliation/workflow.py` with:

```python
def attach_to_expense(db: Session, upload_id: str, expense_id: str) -> Expense:
    """Unconditionally attaches (used both to confirm past a conflict and
    for manual selection) — still safe under concurrency via the same
    conditional-UPDATE pattern. Raises ExpenseNotEligibleError /
    ReceiptNotAvailableError (new, small exceptions) on a failed guard."""

def targeted_match(db: Session, upload: ReceiptUpload, expense: Expense, extracted: ExtractedReceiptData) -> TargetedMatchResult:
    """score_candidate(expense, extracted); no conflict -> calls
    attach_to_expense and returns attached=True; conflict -> returns
    attached=False + reasons, touches nothing."""
```

`backend/app/api/routes/receipts.py`: when `expense_id` is provided, look
up the expense (404 if missing or not `missing` status — "not eligible"),
call `targeted_match` instead of `apply_match_result`, shape the response
accordingly. `backend/app/api/routes/reconciliation.py`: new
`POST /reconciliation/attach`.

Tests: no-conflict targeted upload attaches immediately; conflicting
targeted upload does not attach and reports the conflict; confirming via
`/reconciliation/attach` after a conflict succeeds; attach on a
non-`missing` expense → 409; attach with a non-`pending` upload → 409;
concurrent attach attempts on the same expense → only one succeeds.

### B4 — Fix approval to use the persisted snapshot

Files: `backend/app/schemas/reconciliation.py` (`ApproveMatchRequest`
removed — approve takes no body), `backend/app/services/reconciliation/workflow.py`
(`approve_suggested_match` drops its `vat_amount`/`receipt_number`/`category`
params, loads them from `db.get(ReceiptUpload, expense.suggested_receipt_upload_id)`'s
snapshot columns instead; additionally guards `ReceiptUpload.status='pending'`
in the same conditional-update chain — approval fails cleanly if the
receipt was discarded/expired concurrently), `backend/app/api/routes/reconciliation.py`
(drop the request body param).

Tests: approve with **no client-supplied fields** still fills
vat/receipt_number/category correctly from the persisted snapshot; approve
after the linked upload was independently discarded fails with a clear
error instead of attaching a gone file.

### B5 — Real unassigned-document inbox + rematch/eligible/discard

Files: `backend/app/schemas/reconciliation.py` (new
`UnassignedDocumentRead`), `backend/app/services/reconciliation/workflow.py`
(`build_inbox`'s `documents_without_transactions` query rewritten per the
spec's `NOT IN (...)` condition, returns `ReceiptUpload` rows now, not
`Expense`; new `rematch_document`, `list_eligible_expenses`,
`discard_document`), `backend/app/api/routes/reconciliation.py` (3 new
routes: `POST .../rematch`, `GET .../eligible-expenses`,
`POST .../discard`), `backend/app/services/reconciliation/matching.py`
(small helper `extracted_from_snapshot(upload: ReceiptUpload) -> ExtractedReceiptData`
used by both rematch and eligible-expenses).

Tests: unassigned list only shows truly-unassigned pending uploads (not
ones with an active suggestion, not confirmed/expired/discarded ones);
rematch creates a suggestion when a candidate now qualifies; rematch is a
no-op when nothing matches; eligible-expenses lists only `missing` expenses
with a conflict preview per row; discard clears a dangling suggestion
pointer if one exists, deletes the stored file, is idempotent, and a
discarded upload can never be approved/attached afterward; a rejected
suggestion's upload reappears in the unassigned list with its snapshot
intact (the concrete regression test for "must not leave the rejected
receipt as an invisible pending upload").

### B6 — Preview URL safety for the new inbox section

Verify `resolve_receipt_image_url` (existing, reused) is called for every
unassigned-document row exactly as it already is for `Expense` rows — local
provider returns a `/uploads/...` relative path, Supabase returns a
freshly-generated signed URL, never a filesystem path or a permanent
private URL. Add one test asserting this explicitly for the new endpoint
(both providers, reusing the existing fake-Supabase-client test pattern).

---

## Frontend

### F1 — Navigation

Files: `frontend/src/components/Layout.tsx` (`NAV_ITEMS` drops
`uploadReceipt`/`addExpense`), `frontend/src/components/__tests__/Layout.test.tsx`
(update to assert the 5-item primary nav; confirm `/upload-receipt` and
`/add-expense` routes still resolve — `App.tsx` is unchanged).

### F2 — Secondary entry points

Files: `frontend/src/pages/ExpensesPage.tsx` ("Add expense manually" link),
`frontend/src/pages/ReconciliationInboxPage.tsx` ("Upload unassigned
document" link + "Attach receipt" link per missing-document row, using
`?expenseId=`), both locale files (`nav.*` cleanup not needed — keys stay,
just unused in nav — plus new `expenses.addExpenseManually`,
`reconciliation.attachReceipt`, `reconciliation.uploadUnassignedDocument`).

### F3 — Targeted upload page (`?expenseId=`)

Files: `frontend/src/pages/UploadReceiptPage.tsx` (reads `useSearchParams`,
fetches `getExpense(expenseId)` when present, shows a summary card before
the dropzone; upload call includes `expense_id`; branches on the new
response shape — `attached_to_expense_id` set → success; `conflict` set →
side-by-side conflict view with an explicit confirm button calling the new
`attachMatch` service function), `frontend/src/services/receiptService.ts`
(upload signature gains optional `expenseId`), `frontend/src/services/reconciliationService.ts`
(`attachMatch(uploadId, expenseId)`), `frontend/src/types/receipt.ts` (new
response fields), i18n additions for the conflict view.

Tests: fetches and displays the target expense; no-conflict targeted
upload shows a direct success state (no blank confirm form); a conflicting
upload shows both sides and requires the explicit confirm click before
attaching.

### F4 — Unassigned documents section + suggested-match receipt side

Files: `frontend/src/pages/ReconciliationInboxPage.tsx` (new "Unassigned
documents" section rendering `UnassignedDocumentRead[]`), new
`frontend/src/components/UnassignedDocumentCard.tsx` (preview, extracted
fields, the 4 actions), new `frontend/src/components/ManualMatchDialog.tsx`
(fetches eligible expenses, shows conflict preview, confirms via
`attachMatch`), `frontend/src/components/MatchSuggestionCard.tsx` (extended
to show the receipt side — preview + extracted total/currency/date/vat/
receipt_number — not just the transaction side), `frontend/src/services/reconciliationService.ts`
(`getUnassignedDocuments` folded into the existing inbox call — type change
only —, `rematchDocument`, `listEligibleExpenses`, `discardDocument`,
`approveMatch` drops its request-body params to match B4), `frontend/src/types/reconciliation.ts`
(new types), both locale files.

Tests: an unassigned document renders with its preview/extracted fields
and all 4 actions; **rejecting a suggested match makes its receipt
reappear in the unassigned-documents section without a page reload**
(the frontend regression test matching B5's backend one); discard requires
confirmation; manual match picker shows only eligible expenses and a
conflict warning where relevant; create-expense-from-document pre-fills
the existing `ExpenseForm` from the snapshot.

---

## Documentation

Update `README.md` (the target flow, that a transaction ≠ a receipt, the
extension-boundary explanation) and both spec/plan docs' own self-consistency
(no separate edit needed — they're written to already match what's about to
be built).

## Final

Run full backend (`pytest`) + frontend (`lint && tsc -b && test && build`);
verify `alembic upgrade head` fresh + carried-forward; fix any regression;
commit per task; push; final report per the task's required format.
