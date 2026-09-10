# Reconciliation-First Flow — Design Spec

## Problem

The automated-ingestion work made webhook/CSV transactions and reconciliation
real, but the product's *navigation and default path* still center on manual
receipt upload — the old primary workflow. This demotes manual upload/entry
to what they should be: fallback and reconciliation actions, not the front
door. It also fixes three real correctness gaps found while building this:
extracted receipt data is discarded after the initial response instead of
persisted, "documents without transactions" is derived from the wrong table,
and match approval trusts the browser to resend financial fields it
shouldn't own.

## Target flow

`automatic transaction (webhook/CSV) → appears with document_status='missing'
→ automatic match on next receipt upload, or manual "Attach receipt" →
reconciliation (approve/reject/attach/discard)`. A financial transaction and
a tax receipt are different records — ingesting the transaction never
implies the receipt image exists yet. Manual expense entry and manual
receipt upload remain fully functional, reachable via secondary actions and
existing routes, never removed.

## Navigation

Primary sidebar (`Layout.tsx`): Dashboard, Expenses, Reconciliation Inbox,
Imports & Connections, AI Assistant. "Upload receipt" and "Add expense" are
removed from `NAV_ITEMS` but their routes (`/upload-receipt`,
`/add-expense`) stay mounted unchanged — direct links, tests, and the new
scoped-attach flow all still use `/upload-receipt`. Secondary entry points:
"הוספת הוצאה ידנית" / "Add expense manually" (button on the Expenses page,
linking to `/add-expense`), "העלאת מסמך ללא שיוך" / "Upload unassigned
document" (Reconciliation Inbox, linking to plain `/upload-receipt`),
"צרפו קבלה" / "Attach receipt" (next to every `document_status='missing'`
row, linking to `/upload-receipt?expenseId=<id>`).

## One coherent state machine

Two entities, each owning its own status, related but not duplicated:

**`ReceiptUpload.status`**: `pending → confirmed | expired | discarded`
(new: `discarded`). `pending` means "this document doesn't have a home yet"
— which includes a document with no candidate, *and* one whose suggestion
was just rejected (rejection never changes `ReceiptUpload` at all — see
below). All three non-`pending` states are terminal: an already-confirmed,
expired, or discarded upload can never be approved, rejected, re-attached,
or re-discarded.

**`Expense.document_status`**: unchanged enum
(`missing/suggested/attached/needs_review/not_required`).
`suggested_receipt_upload_id` is the *only* place "this expense has a
pending candidate" is recorded — not a second copy of state, a pointer.

**The relationship is the state, not a new field.** A `ReceiptUpload` is
"unassigned" (belongs in the Inbox's unassigned-documents section) exactly
when `status='pending'` **and** no `Expense.suggested_receipt_upload_id`
points at it — a computed condition (`NOT EXISTS`), not a stored flag. This
is why rejecting a suggestion needs no change to `ReceiptUpload` at all:
clearing the `Expense` side's pointer is sufficient to make the same
still-`pending` row reappear as unassigned, with its extraction snapshot
intact. This directly satisfies "do not leave a rejected receipt as an
invisible pending upload."

**Every transition already required, or now needs, an atomic conditional
`UPDATE ... WHERE <expected state>`** — never select-then-update — so two
concurrent requests can only ever have one winner, and the loser gets a
clean 404/409, never a corrupted double-claim:

| Transition | Guard |
|---|---|
| Expense `missing → suggested/needs_review/attached` (upload-time match, targeted attach) | `WHERE document_status='missing'` |
| Expense `suggested/needs_review → attached` (approve) | `WHERE document_status IN (suggested, needs_review)` |
| Expense `suggested/needs_review → missing` (reject) | same guard |
| ReceiptUpload `pending → confirmed` (any attach path) | `WHERE status='pending'` |
| ReceiptUpload `pending → discarded` | `WHERE status='pending'` |

Approval additionally re-checks the linked `ReceiptUpload.status='pending'`
before finalizing (a real gap in the prior version — approval never verified
the receipt hadn't expired/been discarded out from under it) — if that
guard fails, approval fails cleanly (409) instead of attaching a
discarded/expired document.

## Persisting the extraction snapshot

New nullable columns on `ReceiptUpload` (additive migration): `extracted_business_name`,
`extracted_receipt_number`, `extracted_date`, `extracted_total`/`extracted_vat`
(`Numeric(12,2)`/`Decimal`, never float), `extracted_currency`,
`extracted_category`, `extraction_confidence`, `extraction_warnings` (bounded
`JSON` list of short warning codes — never raw OCR text, image bytes, or a
full provider response). Populated once, right after extraction succeeds in
`POST /receipts/upload`, regardless of which path (general match, targeted
attach, or no match) the upload takes afterward.

Approval (`POST /reconciliation/matches/{expense_id}/approve`) **no longer
accepts `vat_amount`/`receipt_number`/`category` in the request body** — it
loads the persisted snapshot from the expense's `suggested_receipt_upload_id`
and gap-fills from that. The browser identifies *which* match to approve; it
is never the source of truth for what the receipt actually said.

## Targeted attach (`?expenseId=`)

`UploadReceiptPage` fetches `GET /expenses/{id}` when `expenseId` is present
and shows merchant/amount/currency/date/source up top before any upload
happens. `POST /receipts/upload` gains an optional `expense_id` field: when
present, extraction is compared with *only* that expense
(`matching.score_candidate`, reusing the exact scoring already used for
general matching) instead of running general `find_candidates`. No conflict
→ attach immediately in the same request (conditional updates as above). A
conflict (amount/currency/date/merchant) → **nothing is attached**; the
response carries the extracted data plus a conflict description, and the
page shows both sides side-by-side requiring an explicit confirm, which
calls `POST /reconciliation/attach {upload_id, expense_id}` — a small,
unconditional-once-confirmed executor endpoint, reused by "choose
transaction manually" too. The backend re-validates the expense is still
`missing` and the upload still `pending` at that point regardless of what
the first response said (never trusts client-supplied state across two
requests).

## Reconciliation Inbox contract fix

`documents_without_transactions` changes from `list[ExpenseRead]` (wrong —
it was reading `Expense` rows created *by* a receipt upload, not actual
pending documents) to `list[UnassignedDocumentRead]`: `upload_id`,
`received_at`, `preview_url` (via the existing `resolve_receipt_image_url`
— never a raw path), and the persisted extraction snapshot fields. Query:
`ReceiptUpload.status='pending' AND id NOT IN (SELECT suggested_receipt_upload_id
FROM expenses WHERE suggested_receipt_upload_id IS NOT NULL)`.

Suggested-match cards now show **both sides** — the transaction (unchanged)
and the receipt (preview + extracted fields, now available because they're
persisted) — plus score and translated reasons.

## New unassigned-document actions

- **Find matches again** — `POST /reconciliation/documents/{upload_id}/rematch`:
  reconstructs an `ExtractedReceiptData` from the persisted snapshot, reruns
  `find_candidates`/`decide` exactly like upload-time matching. A no-match
  result is a no-op — the document stays unassigned, not an error.
- **Choose transaction manually** — `GET /reconciliation/documents/{upload_id}/eligible-expenses`
  lists `missing` expenses with a per-candidate conflict preview (same
  `score_candidate` call), then the same `POST /reconciliation/attach` executes it.
- **Create expense from document** — reuses the existing `POST /receipts/confirm`
  flow unchanged (it already creates a brand-new expense from a pending
  upload); the frontend just pre-fills the form from the persisted snapshot.
- **Discard document** — `POST /reconciliation/documents/{upload_id}/discard`:
  conditional `pending → discarded`, defensively clears any expense
  currently pointing at it as a suggestion (so discarding never leaves a
  dangling pointer regardless of which UI path triggered it), then
  best-effort deletes the stored file via the existing `ReceiptStorage`
  interface — same non-blocking, log-and-continue pattern as
  `delete_expense_and_cleanup_receipt`. Requires explicit confirmation in
  the UI (a destructive, irreversible action).

## Explicit extension boundary (not implemented)

`app/services/ingestion/` already separates *how a document/transaction
arrives* from *what happens once it does*. A future email or POS/document
connector's only new work would be producing a file plus calling the same
staging → extraction → snapshot-persist → matching pipeline `POST
/receipts/upload` already runs — no fake email connection is added here, and
the README/UI say plainly that receipts do not yet arrive automatically from
any source.

## Non-goals / unchanged

CSV/webhook ingestion, all three extraction providers, local/Supabase
storage, the AI assistant, dashboard, i18n, themes, and all existing data
are unaffected — this is a workflow and API-contract fix layered on top of
the existing ingestion/reconciliation system, not a rewrite of it.
