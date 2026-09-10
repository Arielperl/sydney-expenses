# Sydney Transaction Management

Sydney (סידני — ניהול עסקאות) is a local-first, AI-ready transaction and expense manager with a provider-independent extraction interface and a deterministic mock provider. Transactions arrive automatically (CSV import or a signed demo webhook) and the app tracks which ones are missing a receipt; a receipt can be matched to a transaction automatically, attached directly from the transaction, or — as a fallback — uploaded and reviewed in an editable, bilingual (Hebrew/English) confirmation form, or added manually. Built as a portfolio project demonstrating a clean, modular full-stack architecture.

**Note on naming:** the GitHub repository is `sydney-expenses` (its original working name); the product itself is **Sydney Transaction Management** (סידני — ניהול עסקאות), shortened to **Sydney** (סידני) in the UI, and the backend service identifies itself as **Sydney Transaction Management API**. These are intentionally distinct — the repo name is not being renamed.

**Note on AI:** receipt extraction supports three interchangeable providers behind the same `ReceiptExtractor` interface: `MockReceiptExtractor` (default — deterministic, synthetic, needs nothing), `LocalReceiptExtractor` (real Vision extraction that runs entirely on your machine via Tesseract OCR + a local Ollama model — no API key, no external network call, no per-request cost), and `OpenAIReceiptExtractor` (real Vision extraction via the OpenAI Responses API). Mock mode is what the automated test suite and the default local setup use. The local provider has been run for real against a live local Ollama + Tesseract stack in this environment, A/B-tested across two vision models (`gemma3:12b`, the current default, and `qwen3-vl:8b` — see "Local mode" below); the OpenAI provider has been verified with **mocked** responses only — no OpenAI API key was available here, so its real-world accuracy is not yet claimed. See "Receipt extraction: mock vs. local vs. real AI mode" below.

## Status

**Hardened MVP with two pluggable real-AI extraction providers, provider-independent receipt image storage, and automated expense ingestion with transaction-to-receipt reconciliation as the primary flow.** Expenses arrive automatically — via a signed demo webhook or a CSV bank-statement import — and are automatically matched against uploaded receipts by an explainable, deterministic scoring algorithm (no AI model makes the matching decision); a receipt can also be attached directly to a specific transaction, or uploaded/entered manually as a fallback. The complete flow runs end-to-end, in Hebrew (default) or English, with decimal-safe money handling and a real image-validated upload pipeline. See "Automated ingestion & reconciliation" below for what's real, what's a demo, and what still needs a real banking/email/POS provider.

## Tech stack

**Frontend:** React, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Hook Form, Zod, Recharts, React Router, i18next / react-i18next, lucide-react

**Backend:** Python, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, SQLite or PostgreSQL (including Supabase), psycopg, Pillow, pytesseract (Tesseract OCR), Ollama (local LLM runtime, via its HTTP API), OpenAI Python SDK, pytest

**Frontend testing:** Vitest, React Testing Library, user-event, jsdom, MSW

## Project structure

```
sydney/  (repository: sydney-expenses)
├── frontend/           React + Vite + TypeScript SPA
│   └── src/
│       ├── components/  Reusable UI (forms, tables, charts, states, language switcher)
│       ├── pages/        Route-level views
│       ├── services/     API client + typed service functions
│       ├── schemas/       Zod validation schemas
│       ├── types/         Shared TypeScript types
│       ├── i18n/          i18next setup + locales/{he,en}/translation.json
│       └── test/          Vitest setup, MSW mock server, test utilities
├── backend/            FastAPI application
│   ├── app/
│   │   ├── api/routes/   REST endpoints (expenses, receipts, dashboard, assistant, reconciliation, webhooks, imports)
│   │   ├── models/       SQLAlchemy ORM models (Expense, ReceiptUpload, ImportBatch)
│   │   ├── schemas/       Pydantic request/response models (Decimal money)
│   │   ├── services/extraction/  ReceiptExtractor interface, mock + local (Ollama/Tesseract) + OpenAI providers, plus preprocessing/OCR-selection/receipt_parser/merge for local mode
│   │   ├── services/storage/     ReceiptStorage interface, local-disk + Supabase Storage providers
│   │   ├── services/reconciliation/  Deterministic transaction-to-receipt matching + the approve/reject/inbox workflow
│   │   ├── services/ingestion/       Webhook signature verification + provider parsing, CSV parsing/import
│   │   ├── services/      Business logic (uploads, dashboard, receipt lifecycle)
│   │   ├── repositories/  Database access layer
│   │   └── database.py
│   ├── alembic/          Database migrations (the sole source of schema truth)
│   ├── scripts/          cleanup_uploads.py — expires stale pending uploads; demo_webhook_request.py — sends one signed demo transaction
│   ├── samples/          expenses-sample.csv — fictional CSV import sample
│   ├── evaluation/        Manual accuracy-evaluation CLI (see its own README)
│   ├── tests/            pytest suite
│   └── uploads/          Locally stored receipt images when STORAGE_PROVIDER=local (gitignored)
├── .env.example
└── .gitignore
```

## How it works

A **transaction** and a **receipt** are two different records that the app's job is to connect, not one and the same thing:

- An `Expense` row represents the *transaction* — the financial fact that money moved. It normally arrives automatically (CSV import or webhook) and starts out with `document_status='missing'`.
- A `ReceiptUpload` row represents a *document* — an uploaded receipt image and what was extracted from it. It exists independently of any transaction until it's attached to one.

The target flow is: **automatic transaction → missing document → automatic or manual document attachment → reconciliation**.

1. A transaction arrives automatically (CSV import or the demo webhook) and appears in the Reconciliation Inbox with a "missing document" status. This is the normal case — most transactions should never need a human to type them in.
2. If a receipt is uploaded independently (via **Upload unassigned document** in the Reconciliation Inbox), the system tries to match it against transactions that are missing a document, using a deterministic scoring function — never an AI model for the matching decision itself.
3. If no matching document ever arrives, the user can attach one directly from the transaction — an **Attach receipt** action next to every missing-document row, which pre-fills the target transaction so the upload page can compare the extracted receipt specifically against it, not just find "the best match anywhere."
4. The user's day-to-day job narrows to handling exceptions: missing documents, uncertain (suggested) matches, and conflicts — not manually re-typing every transaction from a paper receipt.

Uploading a receipt without a known transaction (or filling in every field by hand via **Add expense manually**) still works — it's the fallback and reconciliation path, not the primary workflow. The backend streams every upload to disk in bounded chunks (rejecting it immediately if it exceeds the configured size limit) and verifies the actual image bytes with Pillow — a spoofed content type or corrupted file is rejected regardless of what the browser claimed. The original filename is never trusted; the stored filename is always server-generated from the verified format. Every upload is tracked as a `ReceiptUpload` row (`pending` → `confirmed`/`expired`/`discarded`), and its extraction result (business name, amount, VAT, category, date, receipt number, a quality score, warning codes) is persisted on that row immediately — not just returned once in an HTTP response and then lost — so approving a suggested match later never depends on the browser resending financial fields it shouldn't own.

The extraction logic sits behind a `ReceiptExtractor` interface ([base.py](backend/app/services/extraction/base.py)), so a real Vision AI provider can be swapped in later without touching any route or form code.

## Automated ingestion & reconciliation

The goal of this feature is to flip the traditional expense-tracking model around: instead of a human always initiating an expense, a transaction can arrive automatically from a financial source and the user's job narrows to handling exceptions. `Expense` stays the single central record — an ingested transaction becomes an `Expense` row directly (`document_status='missing'`) rather than living in a separate staging table, so every existing list/dashboard/assistant query keeps working unchanged.

**What's real today:**
- **CSV import** ([`app/services/ingestion/csv_import.py`](backend/app/services/ingestion/csv_import.py)) — upload a bank/credit-card statement CSV, preview the parsed rows and any validation errors, then confirm to create expenses. One documented format: `date,description,merchant,amount,currency` with a header row. A sample file with fictional data is at [`backend/samples/expenses-sample.csv`](backend/samples/expenses-sample.csv).
- **Webhook ingestion** ([`app/api/routes/webhooks.py`](backend/app/api/routes/webhooks.py)) — `POST /api/webhooks/transactions` is a real, working, HMAC-signed endpoint. It's genuinely secure (signature + timestamp + body-size checks, idempotent by `(provider, external_transaction_id)` at the database level) — what's *not* real is the sender: only a `demo-bank` payload shape is registered in `WEBHOOK_PROVIDERS`, fed by a local script, not an actual bank or payment processor.
- **Reconciliation matching** ([`app/services/reconciliation/matching.py`](backend/app/services/reconciliation/matching.py)) — a deterministic, explainable scoring function (amount/currency, date proximity, merchant-name similarity, receipt-number match), never an AI model, decides auto-match / suggested / needs-review / no-match. Runs automatically after every receipt upload against transactions still missing a document, and can be re-run on demand for any still-unassigned document ("Find matches again").
- **Reconciliation Inbox** (`/reconciliation` in the app) and **Imports & Connections** (`/imports`) — real, working pages, not mockups. The inbox shows transactions missing a document, suggested matches (with both the transaction and the candidate receipt shown side by side), a **real, persisted list of unassigned documents** (not a UI illusion — see below), and recently completed matches.

**What's a demo, explicitly:** the webhook provider (`demo-bank`) is a stand-in for what a real bank/PSP integration would send — there is no live bank connection, no OAuth, and no real financial institution involved anywhere in this feature. Likewise, **receipt documents do not currently arrive automatically from email, a bank, or a POS system** — every document in the app got there either via CSV/webhook-driven transaction data or a manual upload. The Imports & Connections page says so explicitly in the UI, not just here.

**Explicit non-goals for this phase** (extension points exist, nothing here claims they already work): real bank OAuth or a live banking connection, automatic email or POS receipt ingestion, user authentication, organizations/roles. The document-ingestion boundary — `ReceiptUploadRepository.save_extraction()` plus the `ReceiptUpload` state machine below — is deliberately generic enough that a future email or POS connector could create pending `ReceiptUpload` rows the same way a manual upload does today, without changing the matching, approval, or inbox code at all. No such connector exists yet, and none is faked.

### The reconciliation state machine

Two fields own two different lifecycles, and a third is just a pointer between them — not a third source of truth:

- **`Expense.document_status`** owns the *transaction's* lifecycle: `missing` → `suggested`/`needs_review` → `attached` (or `not_required` for expenses that were never ingestion-tracked, e.g. ones added manually before this feature existed).
- **`ReceiptUpload.status`** owns the *document's* lifecycle: `pending` → `confirmed` (attached to an expense) / `expired` (never claimed in time) / `discarded` (explicitly discarded by a user).
- **`Expense.suggested_receipt_upload_id`** is a pointer, not duplicated state. "Unassigned" is a *computed* condition — a `pending` upload that no expense currently points at — not a separately stored flag. This is why rejecting a suggested match doesn't need any change to the `ReceiptUpload` row at all: clearing the one pointer field is enough for that same still-pending, still-fully-extracted upload to reappear in the unassigned-documents list on its own.

Every transition uses an atomic conditional `UPDATE ... WHERE <expected current state>` rather than a select-then-update, so two concurrent requests (two uploads racing to claim the same expense, two approvals of the same suggestion, an approval racing a discard) can never both succeed — the loser's `UPDATE` affects zero rows and is handled as a clean conflict, never a silent overwrite or a 500.

### Try it end-to-end (fictional demo scenario)

1. Start the backend with a webhook secret set (see below), and send one demo transaction for **ILS 184.90**:
   ```bash
   cd backend && source .venv/bin/activate
   export WEBHOOK_SIGNING_SECRET=demo-secret-change-me
   python -m scripts.demo_webhook_request
   ```
2. Open the app → **Reconciliation Inbox** (`/reconciliation`). The ILS 184.90 transaction appears under "Transactions missing documents" — it arrived automatically, no manual entry.
3. Either upload a receipt independently via **Upload unassigned document**, or click **Attach receipt** on that transaction's row to go straight to a targeted upload for it — any receipt whose extracted total is close to 184.90 works; the mock extractor's deterministic output for a given image can be discovered by re-uploading the same file.
4. Depending on how the receipt was uploaded:
   - **Targeted (via Attach receipt):** no conflict → attaches immediately; a conflict (mismatched amount/currency/date/merchant) → shows both sides and requires an explicit confirm before attaching, never a silent overwrite.
   - **Untargeted (via Upload unassigned document):** a high-confidence match attaches automatically; a medium-confidence match becomes a **suggested match** in the inbox, shown with both the transaction and the receipt side by side, that you approve or reject; a low-confidence result stays in the inbox as an unassigned document, with **Find matches again**, **Choose transaction manually**, **Create expense from document**, and **Discard** actions available on it.
5. Back in the Reconciliation Inbox and on the Dashboard, the transaction has moved out of "missing documents" and the document-attachment-rate stat has updated.

### Webhook signing (for real, not a simplification)

`POST /api/webhooks/transactions` requires `X-Signature` (hex HMAC-SHA256) and `X-Timestamp` headers. The signature is computed over `"{timestamp}.{raw request body}"` using a secret from `WEBHOOK_SIGNING_SECRET` — verification uses `hmac.compare_digest`, a stale timestamp (`WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS`, default 300s) is rejected, and the body is size-capped (`WEBHOOK_MAX_BODY_BYTES`, default 64KB) before it's even parsed. The payload, signature, and secret are never written to a log line. Delivering the same `external_transaction_id` twice never creates a second expense — idempotency is enforced by a database `UNIQUE(source_provider, external_id)` constraint, not just an application-level check, so it's safe under concurrent delivery too.

```bash
curl -X POST http://localhost:8000/api/webhooks/transactions \
  -H "Content-Type: application/json" \
  -H "X-Signature: <computed HMAC>" \
  -H "X-Timestamp: <unix seconds>" \
  -d '{"event_id":"evt-1","provider":"demo-bank","external_transaction_id":"txn-1","occurred_at":"2026-09-10T09:00:00+00:00","merchant_name":"Demo Café","amount":"184.90","currency":"ILS"}'
```
Computing the signature by hand is fiddly — use [`backend/scripts/demo_webhook_request.py`](backend/scripts/demo_webhook_request.py), which builds and signs this exact request for you.

### CSV import format

Header row required, exactly these five columns:
```
date,description,merchant,amount,currency
2026-09-01,Weekly groceries,Demo Fictional Supermarket,184.90,ILS
```
`date` is `YYYY-MM-DD`; `amount` must be a positive number; `currency` a 3-letter code. UTF-8 and UTF-8-with-BOM are both accepted transparently. Re-importing the same file is safe — a stable id is derived from the file's hash plus row number, so repeat rows are skipped as duplicates (reported in the confirmation summary) rather than re-created; this is separate from — and does not assume — "same merchant/amount/date" being a duplicate, which is not always true for legitimate transactions.

## Internationalization

- Hebrew is the default language on first load (no saved preference); English is available via the language switcher in the header.
- The selected language persists in `localStorage` (`receiptly-language`).
- `<html lang>` and `<html dir>` update automatically — Hebrew renders RTL, English renders LTR.
- All user-facing strings (navigation, forms, validation, errors, empty states, dashboard, categories, receipt warnings) live in `frontend/src/i18n/locales/{he,en}/translation.json` — none are hardcoded in components.
- Currency and dates are formatted with `Intl.NumberFormat` / `Intl.DateTimeFormat` for the active locale (e.g. `he-IL` renders ILS naturally as `184.90 ₪`).

## Receipt extraction: mock vs. local vs. real AI mode

Controlled by one environment variable, `RECEIPT_EXTRACTOR_PROVIDER`:

| | `mock` (default) | `local` | `openai` |
|---|---|---|---|
| Needs an API key | No | No | Yes (`OPENAI_API_KEY`) |
| Sends data externally | Never | Never — everything runs on this machine | Yes — the receipt image is sent to OpenAI |
| What it costs | Free | Free per request — but uses local RAM, disk, CPU/GPU, and electricity while running | Billed per request by OpenAI |
| Determinism | Same image → same result | Model output, not deterministic | Model output, not deterministic |
| Needs installed first | Nothing | Ollama + a pulled model, Tesseract + `heb`/`eng` language data | Nothing (just the key) |
| Used by the automated test suite | Yes | Yes (via a fake HTTP client + mocked OCR — never calls a real model) | Yes (via a fake client) |

**Mock mode** needs nothing beyond the default setup. It's a deterministic, offline stand-in that lets the whole upload → review → confirm → save pipeline be exercised (and tested) without any external dependency or cost.

### Local mode (Tesseract + Ollama — fully offline, free per request)

Runs two things locally for each receipt: Tesseract OCR (`heb+eng`) reads the text, and a local vision-capable Ollama model reads the image itself plus that OCR text (offered only as an untrusted hint the model can override) and returns strict JSON matching the same schema as every other provider. Nothing ever leaves your machine.

**Setup:**

1. Install and start Ollama, then pull a vision-capable model. Two have been evaluated end-to-end (see "Local model choice: gemma3:12b vs. qwen3-vl:8b" below); `gemma3:12b` is the current default:
   ```bash
   brew install ollama        # or see ollama.com for other platforms
   ollama serve                # leave running in its own terminal, or run as a background service
   ollama pull gemma3:12b      # default — ~9 GB on disk
   ollama pull qwen3-vl:8b     # optional alternative — ~6-8 GB on disk, same measured accuracy, slower
   ```
2. Install Tesseract with Hebrew and English language data:
   ```bash
   brew install tesseract tesseract-lang   # tesseract-lang includes heb + eng and many others
   tesseract --list-langs                  # confirm "heb" and "eng" are listed
   ```
3. In `backend/.env`:
   ```bash
   RECEIPT_EXTRACTOR_PROVIDER=local
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_RECEIPT_MODEL=gemma3:12b   # or qwen3-vl:8b — see model-choice section below
   OLLAMA_TIMEOUT_SECONDS=120        # a local vision model on a laptop is much slower than a hosted API
   OLLAMA_MAX_RETRIES=2
   OLLAMA_NUM_CTX=16384         # context window for a full request; a tall receipt + full prompt needs >8192
   OLLAMA_NUM_PREDICT=2048      # max output tokens for a full request; too small truncates JSON before it closes
   OLLAMA_NUM_CTX_FAST=8192     # smaller budget used once every factual field is already OCR-resolved
   OLLAMA_NUM_PREDICT_FAST=1024
   OLLAMA_TEMPERATURE=0.0       # deterministic sampling — see "Local model choice" below
   OLLAMA_SEED=42
   TESSERACT_LANGUAGES=heb+eng
   ```
4. Restart the backend. The Upload Receipt page shows "Local extraction active — your data stays on this computer" whenever the backend reports `local` mode.

**Resource cost, not API cost:** there's no per-request bill, but an 8-12B model resident in memory uses several GB of RAM and meaningfully more CPU/GPU and electricity than the mock provider while it's generating — expect real wall-clock latency (single-digit seconds to a couple of minutes per receipt depending on model warm-up and how much the deterministic parser already resolved, see the model-choice section for measured numbers) rather than an instant response. `OLLAMA_NUM_CTX=16384` in particular increases the memory Ollama reserves for the model's context window while it's loaded; lower it if you're RAM-constrained and your receipts are small. Only one model needs to be loaded at a time — run `ollama stop <model-name>` (e.g. `ollama stop gemma3:12b`) to free its memory when you're done, and `ollama ps` to see what's currently loaded.

**If Ollama isn't running or the model isn't pulled**, extraction fails gracefully per receipt — upload and manual entry still work. The Upload Receipt page also proactively checks reachability (via `GET /api/system/capabilities`) and shows a specific "Ollama isn't running" message before you even try uploading, rather than waiting for a failed request.

**If Tesseract fails** (missing binary, missing language data, or any OCR error), extraction continues using the image alone — the vision model can often still read the receipt without OCR assistance — with a warning noting OCR was unavailable.

#### Preprocessing, spatial OCR, deterministic parsing, and the merge policy

An evidence-driven accuracy pass, run against a private set of 4 real, varied Hebrew receipt photos (never committed — see "Evaluating real accuracy" below), found and fixed several compounding root causes of poor extraction:

1. **A narrow receipt photographed on a large white background was cropped, deskewed, and perspective-corrected before any OCR or model call.** [`document_geometry.py`](backend/app/services/extraction/document_geometry.py) detects the document region via Otsu thresholding + morphological closing + contour analysis, working at a capped resolution (max 1600px on the long edge) so cost stays bounded regardless of upload size. It crops to the union of all significant contours (a single-largest-contour approach was tried first and rejected — it catastrophically over-cropped real photos where receipt text forms several disconnected blobs rather than one solid rectangle); perspective correction only triggers when one contour clearly dominates the union and forms a clean convex quadrilateral, otherwise the image is just deskewed via a minimum-area rotated rectangle. Every step falls back to the original, uncropped image on low confidence or any failure — this step can only help, never break, an upload.
2. **[`image_preprocessing.py`](backend/app/services/extraction/image_preprocessing.py) then scales the cropped image** primarily off width (targeting ~1400px), with EXIF orientation correction and hard caps on both max dimension (4000px) and total pixel count (15M px), and generates four variants: `enhanced` (grayscale + autocontrast + mild sharpen), `illumination_normalized` (CLAHE — recovers a severely faded or unevenly lit receipt), `adaptive_threshold` (local, not global, binarization — survives uneven lighting across a single photo far better than the old global-Otsu threshold it replaces), and `denoised` (light median filter).
3. **OCR moved from flat text to spatial data.** [`ocr_selection.py`](backend/app/services/extraction/ocr_selection.py) now calls `pytesseract.image_to_data` across a bounded matrix of (variant, page-segmentation mode) combinations, keeping each word's bounding box, confidence, and block/paragraph/line grouping — not just a flat string. Flat text (reconstructed in visual reading order from the same word boxes) is kept only as a secondary signal; full OCR output is never logged.
4. **[`receipt_parser.py`](backend/app/services/extraction/receipt_parser.py) was rewritten to reason spatially, not just textually.** It finds Hebrew/English label words (`סה"כ לתשלום`, `סה"כ`, `שולם`, `מע"מ`/`סכום מע"מ`, `תאריך`, `חשבונית מס`/`קבלה`, handling common OCR-dropped-diacritic variants) and associates each with the nearest money-shaped or date-shaped word by position, not by scanning line text with regex. This directly fixed the flat-text failure mode where a taxable-subtotal amount sitting next to the true VAT amount on the same line was picked as VAT instead: a **competing-label disambiguation** step now only accepts a candidate value for a label when it is unambiguously closer to that label than to any other recognized label on the same line, rather than just picking the nearest number. VAT candidates are validated (must be ≥0 and ≤ the total; a value matching Israel's standard VAT-inclusive ratio is used only as supporting evidence, never as a hard rule) and receipt-number punctuation (hyphens, slashes) is preserved instead of stripped.
5. **[`merge.py`](backend/app/services/extraction/merge.py) keeps vision-model and OCR/parser evidence explicitly separate**, never blending them into one unlabeled number: agreement between the two sources raises confidence, a confident parser candidate fills a gap the model left null (flagged `*_from_ocr`), a genuine disagreement is never resolved silently — the more trustworthy source wins but a `*_conflicting_sources` warning always fires — and a weak/unlabeled OCR guess never overrides a clear vision-model reading. Merchant name is read from the receipt's header region plus the vision model; category is inferred from merchant name and context only when there's enough evidence, with an explicit `category_from_merchant_name` fallback (never allowed to influence total/VAT/date) when the model itself doesn't return one confidently.
6. **A later determinism/latency pass made the pipeline deterministic-first.** `local_extractor.py` now checks, per extraction, which factual fields (`receipt_number`/`date`/`total`/`vat`/`currency`) the parser resolved with *high* confidence and drops exactly those fields from the vision model's own JSON-schema request — the model is asked only for the fields still unresolved plus the two fields it always owns (`business_name`, `category`), so a stochastic model answer can never even be offered as a conflicting value for a field the parser already confidently settled (verified structurally, not just by policy — see `test_high_confidence_ocr_value_excludes_field_from_model_request_and_cannot_be_overwritten`). The request itself got smaller too: exactly one image is sent — the cropped/enhanced version when document cropping was confident, the original photo only as a fallback when it wasn't (never both); the OCR text sent to the model is a bounded summary (header lines + every labeled line + a capped number of item lines — see `ocr_selection.build_ocr_summary`), not the full flat text; and a smaller `OLLAMA_NUM_CTX_FAST`/`OLLAMA_NUM_PREDICT_FAST` budget applies once the schema itself is small. Sampling is now explicit and deterministic (`OLLAMA_TEMPERATURE=0.0`, `OLLAMA_SEED=42`) rather than left at each model's own Ollama default, which was a real, measured source of run-to-run field-level variance on an identical input. This work also found and fixed a genuine bug along the way: `OcrLine.text` orders words by pixel (left-to-right) position, not Hebrew reading order, so a multi-word Hebrew label could appear with its words in the *opposite* order from how a person reads them — `receipt_parser.py`'s label matching now checks for co-occurrence of a label's component words in either order, at a deliberately capped confidence tier so a still-uncertain association never blocks the vision model from being asked to verify it.

See [`backend/tests/test_document_geometry.py`](backend/tests/test_document_geometry.py), [`test_ocr_selection.py`](backend/tests/test_ocr_selection.py), and [`test_receipt_parser.py`](backend/tests/test_receipt_parser.py) for synthetic-fixture regression coverage of each of these (no real receipt image is ever used in an automated test).

### Local model choice: gemma3:12b vs. qwen3-vl:8b

Both models were evaluated with the exact same pipeline above, against the same private 4-receipt manifest, using [`backend/evaluation/evaluate_receipts.py --model <name>`](backend/evaluation/README.md):

| Field-level accuracy | gemma3:12b (pre-determinism-pass) | gemma3:12b (current) | qwen3-vl:8b (current) |
|---|---|---|---|
| receipt_number | 0–67% (run-to-run variance) | 67% (2/3) | 67% (2/3) |
| date | 75% | 75% | 75% |
| total | 75–100% (varied by run) | 100% | 100% |
| vat | 75% | 75% | 75% |
| currency | 100% | 100% | 100% |
| category | 50% | 50% (1/2) | 50% (1/2) |
| exact-match (every field correct) | 0/4 | 1/4 | 1/4 |
| avg. latency per receipt | ~13–34s (high variance) | ~30s | ~62s |

**gemma3:12b is the current default** (`OLLAMA_RECEIPT_MODEL=gemma3:12b`). Under the deterministic-first pipeline, the two models now produce *identical* measured field-level accuracy — expected, since most factual fields are resolved by the OCR/spatial parser for both models alike, and the vision model's remaining role (business_name/category, plus any factual field the parser didn't confidently resolve) turned out equally reliable for both on this manifest. With accuracy equal, gemma3:12b's materially lower latency (~2x faster on average here) makes it the better default; `qwen3-vl:8b` remains fully supported — set `OLLAMA_RECEIPT_MODEL=qwen3-vl:8b` to use it. This is a genuine reversal from an earlier round of this work, when qwen3-vl:8b measured meaningfully more accurate before the pipeline became deterministic-first — recorded here rather than silently dropped, since a past recommendation turning out incomplete is itself useful information.

**Plastelina, verified three consecutive times with identical settings (`gemma3:12b`, `temperature=0`, `seed=42`):** `receipt_number`, `date`, `total`, `vat`, and `currency` came back correct and *byte-for-byte identical* across all three runs — not just similar, but the exact same values and the exact same warning list every time. Latency: 134.67s in the pre-pass baseline measurement → 79–103s cold (first call after `ollama stop`, includes model load time) → 11–16s warm (a model already resident in memory from a preceding call, the realistic case for a session uploading more than one receipt). `category` alone came back `other` (not the expected `shopping`) in all three runs, consistently — a merchant name alone often isn't enough to confidently infer category, and this was already inherently the harder, more judgment-based field of the two the vision model retains.

**Read this table honestly, not as a general accuracy claim:** n=4 real receipts is a small, private evaluation set, not a representative sample. Neither model has been deleted; both remain pulled and available (`ollama list`) so the model can be switched without a fresh multi-GB download.

**Honest result on the real receipt that originally exposed the narrow-photo-on-white-canvas bug (from an earlier round of this work):** receipt number (9999), total (60.50 ILS), VAT (9.22 ILS), and date (2013-09-30) were all correctly extracted after that specific fix — all four had been wrong or missing before it. Business name stayed blank, correctly: the photo's text there was never legible enough for either the model or the parser to read with any real confidence, and "extract only if sufficiently clear" means blank is the honest answer, not a guess.

**Frontend safety fixes**, independent of the extraction accuracy work above:
- An unknown `total`/`date` from the API now leaves the amount/date fields genuinely **empty** — never `0` or today's date. Both fields are required, so an empty value now correctly blocks saving until the user fills it in (a `z.coerce.number()` bug meant an empty string was previously silently coerced to `0`, a valid amount — fixed by rejecting an empty value before coercion).
- Warnings are deduplicated and grouped by what they actually mean — "filled in from OCR text" (informational), "two sources disagreed" (worth a second look), or "couldn't be determined" — instead of one flat, noisy list, and every warning code is translated in both languages; an unrecognized code (a local model isn't as strictly constrained to a fixed vocabulary as a hosted structured-output API, and has been observed to write a full free-text explanation into a warning instead of a code) is normalized server-side to a generic, translated fallback rather than ever shown as raw text.
- If almost nothing could be extracted (quality score under 15%), the review screen shows a clear "we couldn't identify enough details" message instead of a quality badge reading "0%" next to a nearly empty form — the form itself still renders underneath for manual entry, exactly as the existing "automatic extraction failed" state already did.
- The quality/confidence score is explicitly documented (in a tooltip on the badge, and here) as a **completeness/quality heuristic** — how many fields were found and how many caveats were raised — never a calibrated probability that the values are correct.

### Real AI mode (OpenAI)

Uses the OpenAI [Responses API](https://platform.openai.com/docs/guides/structured-outputs) with strict Structured Outputs (a Pydantic schema, not free-form JSON parsing) and `store=False` (the request is not retained server-side for multi-turn use). To enable it:

1. Get an API key from your OpenAI account and pick a vision-capable model.
2. In `backend/.env` (never commit this file — it's gitignored):
   ```bash
   RECEIPT_EXTRACTOR_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   OPENAI_RECEIPT_MODEL=gpt-...        # any current vision-capable model
   OPENAI_TIMEOUT_SECONDS=30           # optional, defaults shown
   OPENAI_MAX_RETRIES=2                # optional; only transient failures are retried
   ```
3. Restart the backend. The Upload Receipt page shows "AI extraction active".

**If the key or model is missing** while `openai` mode is selected, extraction fails gracefully per receipt (a clear, non-sensitive error) — upload and manual entry still work; the app never crashes on misconfiguration. The same graceful-degradation behavior applies to `local` mode.

The mode badge is fed by `GET /api/system/capabilities` — a safe endpoint that returns only the provider name, mode, a `real_ai_enabled` boolean, and (in `local` mode only) non-sensitive `ollama_available`/`tesseract_available` booleans. Never a key, never a filesystem path.

**Privacy implications:** in `openai` mode, the verified receipt image is base64-encoded and sent to OpenAI's API for that single request (`store=False`, not used for multi-turn state) — review OpenAI's own data-handling terms before enabling it if your receipts contain sensitive personal data. In `local` mode, the image and its OCR text never leave the machine at all. Neither mode ever writes image bytes, extracted receipt text, or an API key to the application's own logs — only safe metadata (provider, success/failure, duration, upload id, error category).

**Quality score, not "AI confidence":** no provider's self-reported confidence is trusted as a calibrated probability. Every real provider instead computes a **quality score** — a documented heuristic based on how many important fields were found and how many warnings were raised — shown in the UI as "extraction quality", never "confidence".

**Evaluating real accuracy:** `backend/evaluation/` has a small CLI to measure field-level extraction accuracy against your own manually labeled receipts, for any of the three providers (`--provider mock|local|openai`). See [`backend/evaluation/README.md`](backend/evaluation/README.md) for setup and exact commands. It defaults to mock/dry-run (free, no network) and supports a `--max-files` cap. Real receipts and labels are gitignored and must never be committed.

**Current limitations:**
- No live OpenAI request has been run in this environment (no API key available here) — the OpenAI provider is verified only against mocked client responses in the test suite. Treat it as implemented-and-unit-tested, not yet field-verified.
- The local provider has now been run against a private, manually labeled set of 4 real, varied Hebrew receipt photos, A/B-tested across both installed models (see "Local model choice" above) — field-level accuracy under the current deterministic-first pipeline is identical for both models: 100% on total/currency, 75% on date/vat, 67% on receipt_number, 50% on category. That is still a small, private sample (n=4), not a general Hebrew-receipt accuracy claim — a larger, more representative labeled set (see "What's next") is still the only way to make a general accuracy claim. A synthetic, PIL-rendered receipt was also run as an overfitting check (PIL doesn't apply Hebrew bidi text shaping, and this particular font/rendering combination made some digits illegible even to Tesseract), and the pipeline correctly left the unreadable fields blank rather than guessing.
- The quality score is a heuristic (documented as such in the UI tooltip and above), not a calibrated accuracy measure.
- No per-provider rate limiting or cost cap beyond `OPENAI_MAX_RETRIES`/`OLLAMA_MAX_RETRIES`/`--max-files` in the evaluation tool.
- The deterministic parser's Hebrew label matching (`receipt_parser.py`) covers common label variants observed in practice, not an exhaustive list — an unusual receipt layout or an OCR misread outside the patterns it knows will simply fall back to the model's own reading (or `null`), never a crash.
- Sending two images (the original photo plus the enhanced variant) to the local model roughly doubles the base64 payload size for that request; on constrained hardware this is a real, if modest, additional memory/latency cost during the vision call, on top of the already-substantial RAM a 12B model resident in memory requires.

**Troubleshooting:**
- *"Automatic extraction failed" every time in `openai` mode* → check `OPENAI_API_KEY` and `OPENAI_RECEIPT_MODEL` are set in `backend/.env` and the backend was restarted after editing it.
- *"Automatic extraction failed" every time in `local` mode, or the "Ollama isn't running" banner* → run `ollama serve` (or confirm the background service is running), then `ollama list` to confirm the model in `OLLAMA_RECEIPT_MODEL` is actually pulled (`ollama pull gemma3:12b` if not). Check `curl http://localhost:11434/api/version` responds.
- *Missing Tesseract, or "ocr_unavailable" warnings every time in `local` mode* → confirm `tesseract --version` works and `tesseract --list-langs` lists both `heb` and `eng`; extraction still works without OCR (it falls back to the image alone), just with reduced accuracy.
- *Badge stuck on "Demo mode" after switching provider* → the backend wasn't restarted, or `RECEIPT_EXTRACTOR_PROVIDER` isn't actually set in the environment the backend process reads from.
- *Timeouts* → raise `OPENAI_TIMEOUT_SECONDS` / `OLLAMA_TIMEOUT_SECONDS` (a local 12B model is much slower than a hosted API — 120s is a reasonable starting point); transient failures (timeouts, connection errors, rate limits, 5xx) are retried up to `OPENAI_MAX_RETRIES`/`OLLAMA_MAX_RETRIES` times with backoff, non-transient errors (bad request, auth) are not retried.

## Receipt image storage: local vs. Supabase

Persisting the verified receipt image is behind the same kind of provider-independent interface as extraction — a `ReceiptStorage` abstraction ([base.py](backend/app/services/storage/base.py)) with two implementations, selected via `STORAGE_PROVIDER`:

- **`local`** (default) — writes the verified image to `UPLOADS_DIR` on disk, served back by the API's own `/uploads/...` route. Needs no external credentials; this is what the automated test suite and a fresh clone use.
- **`supabase`** — uploads the verified image to a **private** Supabase Storage bucket. The bucket must already exist with public access disabled (`SUPABASE_STORAGE_BUCKET`, default `receipts`); this app does not create or configure the bucket for you.

**How images move through the app, regardless of provider:** an upload is first streamed to a local temp file and verified with Pillow exactly as before — nothing provider-specific happens yet. That same local temp file is then (a) handed to the configured storage provider to persist permanently, and (b) handed to the configured extraction provider for OCR/vision analysis. Extraction always reads the local temp file directly, even when the storage provider is `supabase` — this is what lets `local` extraction mode (Tesseract/Ollama) keep working unmodified no matter which storage backend is configured. The temp file is deleted in a `finally` block once both steps are done, whether they succeeded or failed.

**Private bucket, signed URLs only:** the Supabase provider never calls `get_public_url` and the bucket is never made public. Only a stable **object key** (a random, server-generated name, never the original filename) is persisted in the database — never a URL, and never the service key. Every time the API returns a receipt image URL to the frontend (on upload, confirm, list, or get), it generates a **fresh, time-limited signed URL** on the spot via `create_signed_url` (TTL configured by `SUPABASE_SIGNED_URL_TTL_SECONDS`, default 1 hour); a signed URL is never cached or persisted, so it can't go stale in the database even though it does expire in the browser. If a signed URL happens to expire before the user views it (e.g. a long-open browser tab), the frontend's receipt-image view (`ReceiptImage` component) catches the `<img>` load failure and shows a plain-text fallback instead of a broken-image icon — the underlying data is never lost, only that one preview.

**Storage provider is recorded per record, not read from current config:** both `Expense` and `ReceiptUpload` store their own `storage_provider` column, set at the time they were created. This means a receipt uploaded while `STORAGE_PROVIDER=local` keeps resolving through local disk even after the app is reconfigured to `supabase`, and vice versa — switching providers is never destructive to existing data. Pre-existing rows (from before this column existed) are backfilled to `local` by the Alembic migration.

**Failure handling:** if the Supabase upload itself fails (network, auth, bucket misconfigured), `POST /api/receipts/upload` returns a clear `503` and no `ReceiptUpload` row is created — the user can still add the expense manually (no receipt), which never touches storage. If generating a signed URL fails for an existing record, the API returns `null` for that image URL rather than an error — the expense itself is unaffected. Deleting an expense **always** deletes the database row first and only then best-effort deletes the underlying storage object (local file or Supabase object); a storage-delete failure is logged as a warning and never blocks or reverts the database deletion — this matches the pre-existing local-only behavior and means a Supabase outage can never prevent a user from deleting an expense.

**Enabling Supabase Storage:**

1. In your Supabase project, create a **private** Storage bucket (public access disabled). Optionally set a max file size (10 MB matches this app's own upload limit) and restrict allowed MIME types to `image/jpeg`, `image/png`, `image/webp`.
2. In `backend/.env` (never commit this file):
   ```bash
   STORAGE_PROVIDER=supabase
   SUPABASE_URL=https://your-project-ref.supabase.co
   SUPABASE_SECRET_KEY=...        # the service/secret key — never the anon/public key
   SUPABASE_STORAGE_BUCKET=receipts
   SUPABASE_SIGNED_URL_TTL_SECONDS=3600   # optional, default shown
   ```
   **Security warning:** `SUPABASE_SECRET_KEY` bypasses Row Level Security and can read/write the entire project's storage (and database, if reused elsewhere) — treat it exactly like a database superuser password. It is never logged, printed, sent to the frontend, or included in any API response; only the backend process ever reads it.
3. Restart the backend. If `STORAGE_PROVIDER=supabase` but any of the three required variables above is missing, the app **fails fast at startup** with a clear error rather than silently falling back to local disk or degrading at request time.
4. Run the Alembic migration (`alembic upgrade head`) against whichever database you're using — the new `storage_provider` column applies to both SQLite and Postgres.

**Real end-to-end smoke test:** because mocked tests can't catch a real bucket misconfiguration, this project's own verification included a real (non-mocked) run against a live Supabase Storage bucket, using the actual `backend/.env` credentials: confirmed the bucket exists and is private, uploaded a synthetic test image, verified the object exists in the bucket, generated a signed URL and fetched it back (byte-for-byte match), deleted the object, and confirmed it was gone — leaving zero objects and zero database rows behind. To rerun this yourself, write a small script that constructs `SupabaseReceiptStorage(get_settings())` directly and exercises `store()` / `get_viewable_url()` / `delete()` against your own bucket; do not add such a script to the committed test suite, since it requires real credentials and network access.

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the environment template (optional — sensible defaults are built in):

```bash
cp ../.env.example .env
```

Apply database migrations — **required**, the app no longer creates tables automatically on startup; Alembic is the sole source of schema truth:

```bash
alembic upgrade head
```

Run the backend tests:

```bash
pytest
```

Start the API server:

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

Optionally, expire stale pending receipt uploads (older than `PENDING_UPLOAD_EXPIRY_HOURS`, default 24h) and clean up their orphaned files — safe to run manually or on a daily cron:

```bash
python -m scripts.cleanup_uploads
```

### 2. Frontend

In a new terminal:

```bash
cd frontend
npm install
```

Optionally copy the environment template (defaults to `http://localhost:8000` if omitted):

```bash
cp .env.example .env
```

Start the dev server:

```bash
npm run dev
```

The app is now available at `http://localhost:5173`.

## Running everything

With both servers running (backend on :8000, frontend on :5173), open `http://localhost:5173` and:

- **Dashboard** — monthly total, comparison to last month, category breakdown chart, recent expenses, empty states.
- **Expenses** — search, filter by category/date, edit, delete.
- **Add expense** — manual entry with validation.
- **Upload receipt** — drop an image, review the extracted fields (mock, local, or OpenAI, shown by the mode badge), confirm and save. The receipt image is stored locally or in Supabase Storage depending on `STORAGE_PROVIDER`, transparently to this flow. If a matching transaction is already waiting, the upload auto-attaches or offers a suggested match instead of a blank confirm form — see "Automated ingestion & reconciliation" above.
- **Reconciliation Inbox** — transactions missing documents, suggested matches to approve/reject, receipts without a matching transaction, cases needing review, and recently completed matches.
- **Imports & Connections** — CSV bank-statement import (preview → confirm), and the webhook demo connection status/instructions.
- **Language switcher** (top right) — toggle between עברית and English at any time.
- **View receipt** (Expenses list) — appears only for expenses that have a receipt image; opens it in a modal via a freshly generated URL. Gracefully falls back to a text message if the image fails to load (e.g. an expired signed URL).

## Verification performed

- `pytest` (backend, 202 tests) — expense validation (including currency normalization, VAT-vs-amount, non-finite rejection), CRUD API, decimal-precision dashboard math (e.g. `0.10 + 0.20 + 0.30 == 0.60` exactly), mock extraction, **OpenAI extractor tests against a fake/mocked client** and **local (Ollama/Tesseract) extractor tests against a fake HTTP client and mocked OCR** (provider selection for all three modes, missing-key/missing-model config errors with no key leakage, valid-response mapping, nullable/partial fields, invalid category/date/currency/VAT-vs-total handling, bounded timeout and transient-error retries, non-transient errors not retried, malformed output, Hebrew/English OCR text reaching the model prompt, Tesseract-failure image-only fallback, extraction failure still allows manual entry, no expense saved during extraction itself, sensitive OCR content never appearing in logs), real image-format verification (spoofed content type / corrupted file rejection), streamed oversized-upload rejection with no partial file left behind, `/system/capabilities` reporting for all three modes, and the full receipt-upload lifecycle (duplicate confirmation, missing/expired upload, orphan cleanup, expense deletion with safe file-cleanup-failure handling). All passing. **No real OpenAI API call and no real Ollama/Tesseract call was made in any automated test** — every local- and OpenAI-provider test injects a fake HTTP client and/or mocked OCR function.
- A fresh temporary SQLite database built entirely via `alembic upgrade head` (no `create_all` involved), and an application import/startup check in mock mode, a safe missing-key check in `openai` mode, and a safe Ollama-unreachable check in `local` mode (pointed at a port nothing listens on) — all degrade to a clear extraction failure with manual entry still available, never a crash.
- The evaluation CLI (`evaluation/evaluate_receipts.py`) run in `--dry-run` mode against a real generated test image (mock provider, no network).
- **A real local smoke test was performed** — genuinely running Ollama 0.33.2 + `gemma3:12b` + Tesseract 5.5.3 (`heb`+`eng`) on this machine, with no OpenAI key configured and no OpenAI code path reachable:
  - Verified via direct API calls that Ollama's `/api/generate` supports both the `format` JSON-schema parameter (structured output) and image input (`images` field) with `gemma3:12b` before writing any integration code against it.
  - Ran `evaluation.evaluate_receipts --provider local` against a real, generated, non-sensitive Hebrew/English test receipt image — completed in ~17s with real local inference, produced valid structured output and a field-level accuracy report (low accuracy on this specific image, expected — see "Current limitations": PIL doesn't shape Hebrew text, so the rendered receipt itself has reversed Hebrew word order). Notably, the model correctly returned `null` rather than guessing on the fields it couldn't confidently read, exactly the required safe behavior.
  - Ran the same image through the actual running FastAPI app end-to-end in `local` mode (`RECEIPT_EXTRACTOR_PROVIDER=local`): `POST /api/receipts/upload` → real local extraction → reviewed/corrected the low-confidence fields → `POST /api/receipts/confirm` → expense saved (HTTP 201) → appeared via `GET /api/expenses`. `GET /api/system/capabilities` correctly reported `ollama_available: true` and `tesseract_available: true`. The server log was grepped for any OpenAI reference — none found, confirming no external network call occurred.
- `npm test` (Vitest + RTL + MSW, frontend, 40 tests) — Hebrew-default/English-switch/persistence, the globe-icon language switcher (open/select/checkmark/Escape/outside-click/arrow-keys), manual expense validation, upload loading/failure states, extracted-data confirmation (full and partial), duplicate-confirmation conflict handling, provider-failure manual fallback, mock/local/AI-mode badge labels in both languages, the Ollama-unavailable warning banner, expense edit/delete, dashboard empty/populated states, and Israel-timezone-safe local date handling. All passing.
- `tsc -b`, `oxlint`, `npm run build` — all clean.
- Alembic migrations and create/read/update/delete operations were verified against a live Supabase PostgreSQL database; local development still defaults to SQLite when `DATABASE_URL` is not configured.
- Manual end-to-end verification in-browser (mock mode for the UI walkthrough): Hebrew RTL layout, switch to English/LTR, manual add, receipt upload → extraction → confirm → save, duplicate-confirmation attempt, edit, delete with image cleanup, dashboard totals/percentage-change/category chart, and mobile viewport in both languages. The local-mode UI (badge, Ollama-unavailable banner) was verified live against the real local stack described above.
- **Not performed:** a live request to the real OpenAI API. The `openai` provider is verified end-to-end against a scripted fake client, not against the real service — do not treat it as field-verified until you've run it with a real key.
- **Receipt storage (`local` and `supabase` providers)**, added alongside the existing extraction/upload work above:
  - New `pytest` coverage (included in the 141 total): local storage store/random-names/delete/traversal-rejection, Supabase storage store/random-names/signed-URL-generation/delete against a fake Supabase client (never real credentials), every `StorageApiError` status code correctly translated to the right typed exception, the secret key never appearing in any exception message or log, `build_storage`/config-validation behavior, an invalid image never reaching a storage call at all, a `503` (and no DB row created) when storage itself fails, non-blocking expense-deletion cleanup when storage raises, and pre-existing records without an explicit `storage_provider` correctly backfilling to `local`.
  - `alembic upgrade head` run successfully against **both** a fresh temporary SQLite database and the live Supabase PostgreSQL database (adding the new `storage_provider` column to `expenses` and `receipt_uploads`); downgrade/re-upgrade also verified on SQLite.
  - **A real, non-mocked smoke test against the live Supabase Storage bucket** using the actual `backend/.env` credentials (never printed or logged): confirmed the bucket exists and is private, uploaded a synthetic test image, verified the object in the bucket, generated a signed URL and fetched it back with a byte-for-byte match, deleted the object, and confirmed removal — see "Real end-to-end smoke test" above.
  - A real HTTP-level end-to-end run against the actual running backend (`STORAGE_PROVIDER=supabase`, live Supabase Postgres): upload → signed-URL image → confirm → view → delete, all via real requests, no mocks.
  - Live browser verification: uploaded a real (synthetic, non-personal) receipt image through the actual UI, reviewed and confirmed it, opened it via the new "View receipt" action in both Hebrew/RTL and English/LTR, confirmed the image renders from a genuine Supabase signed URL, then forced the `<img>` to a broken URL and confirmed the graceful text fallback (no broken-image icon, no crash) renders correctly in both languages; also checked the mobile-width expense list layout.
  - Confirmed no test data was left behind: zero rows in `expenses`/`receipt_uploads` and zero objects in the Supabase bucket after all of the above.
  - `npm test`/`tsc -b`/`oxlint`/`npm run build` all re-run and passing with the new `ReceiptImage` component and "View receipt" action included.
- **Extraction accuracy fix (preprocessing, deterministic parser, merge policy, frontend safety)**, diagnosed from a real, uploaded, narrow (330×736px) Hebrew receipt that had extracted with 0% confidence, an empty merchant name, a total/VAT of 0/blank, and a date silently defaulted to today:
  - New `pytest` coverage (included in the 202 total, ~61 new tests): width-based upscaling targeting 1200–1600px, max-dimension/max-pixel bounds on both narrow and abnormally large images, the bounded 5-config OCR scoring matrix (a single bad config never aborts the others), Hebrew receipt-number/date/total/VAT extraction against hand-authored synthetic OCR text covering common label variants and OCR-truncated labels (e.g. `מע"‎` missing its trailing מ), rejection of item-price and change/cash lines as the total, decimal-comma handling, the cross-OCR-attempt merge recovering a valid date even when the single best-scoring attempt misread a digit, every merge-policy branch (parser fills a null, a low-confidence guess never does, agreement is silent, disagreement is flagged and resolved by confidence tier), warning-code normalization of unrecognized/free-text model output and deduplication, and a full-pipeline test confirming no OCR text, image bytes, or secrets ever reach a log line.
  - **Re-ran the real uploaded receipt end-to-end after the fix**, both via a direct extractor call and via a real HTTP round-trip against the live running backend (private Supabase Storage, live Supabase Postgres): receipt number `9999`, total `60.50` ILS, VAT `9.22` ILS, and date `2013-09-30` were all extracted correctly — every one of the four fields that were wrong before is now right. Business name correctly stayed blank (genuinely illegible in the source photo). Confidence rose from 0% to 30%, honestly reflecting the fields that were and weren't recovered.
  - **A second, higher-resolution synthetic Hebrew receipt** (different content and layout, PIL-rendered) was run through the same pipeline as an overfitting check: it correctly recovered the date via the cross-attempt agreement mechanism, and correctly returned `null` rather than a wrong number for total/VAT when a font-rendering quirk in that specific image made those digits illegible even to Tesseract — the important property (never confidently wrong) held on both receipts, even though the two behaved differently.
  - Live-verified the frontend fix directly in the browser against the real running local pipeline: uploading a receipt with no readable total/date renders the amount and date fields genuinely **empty** (not `0`/today), and the confirmation form's "Date is required"/"Amount must be a number" validation errors correctly block submission until filled in. This also caught and fixed a real bug in the process — `z.coerce.number()` silently treats an empty string as `0` (`Number('') === 0` in JavaScript), which would have let an unknown amount silently save as a zero-amount expense; the schema now explicitly rejects an empty amount instead.
  - `npm test` (frontend, 52 tests), `tsc -b`, `oxlint`, `npm run build` all re-run and passing with the new warning-grouping, insufficient-extraction state, and schema fix included.
  - Confirmed via direct database/Storage queries that no test data was left behind by this round's real-receipt testing, and that the original user-uploaded pending receipt used for diagnosis was left completely untouched (never confirmed, deleted, or modified) — only the fresh copy created by this round's own re-test lifecycle was cleaned up.
- **Not fully performed this round:** interactive, visual (screenshot/click) browser verification of the frontend fixes in Hebrew RTL / English LTR / mobile viewports specifically for this round's changes — the browser automation pane became unresponsive to visual interaction partway through this session (confirmed via `document.hidden` staying `true` even after explicitly re-focusing the tab), which is an environment/tooling issue, not an application one. In its place: the same behavior was verified via direct DOM/JS state inspection against the real running app (confirming actual input values and validation error text), a real end-to-end HTTP round-trip against the live server, and the full automated frontend test suite (which exercises the identical code paths via React Testing Library, unaffected by the pane issue). The equivalent RTL/LTR/mobile browser checks for the Storage feature (a prior round) and the general Hebrew/English/responsive layout (unchanged this round) remain valid.
- **Reconciliation-first product flow** (persisted extraction snapshot, targeted attach, a real unassigned-document inbox, and the simplified nav):
  - `pytest` (backend, 359 tests, all passing) — the persisted extraction snapshot (`ReceiptUploadRepository.save_extraction`) populated at upload time and consumed by matching/approval instead of trusting client-supplied fields; targeted attach (`?expense_id=` on `POST /receipts/upload`) attaching immediately on no conflict, reporting a conflict without attaching otherwise, and the explicit-confirm `POST /reconciliation/attach` completing it afterward; server-side re-validation of an arbitrary client-supplied expense/upload id (404/409, never trusted); the real `documents_without_transactions` query (real pending, unpointed-to `ReceiptUpload` rows, excluding suggested/confirmed/discarded ones); rejecting a suggested match making its receipt reappear as unassigned with its snapshot intact, as a structural consequence of clearing one pointer field, not separately implemented behavior; rematch/eligible-expenses/discard for unassigned documents (discard clearing a dangling suggestion pointer, best-effort deleting the stored file, idempotent, and permanently blocking any later approve/attach of that upload); concurrent-claim races (two attach attempts on the same expense, an approval racing a discard) resolved cleanly via conditional `UPDATE`s, never a silent double-attach; and local/Supabase preview-URL safety for the new inbox section, reusing the existing `resolve_receipt_image_url`.
  - `npm test` (frontend, 88 tests, all passing), `tsc -b`, `oxlint`, `npm run build` — all clean. New/updated coverage: the 5-item primary nav with Upload Receipt/Add Expense removed (routes still resolve); the "Add expense manually"/"Upload unassigned document"/"Attach receipt" secondary entry points; the targeted-upload page fetching and displaying the target expense, a direct success state with no conflict, and a conflict requiring an explicit confirm click before attaching; suggested-match cards showing both the transaction and the receipt side by side; an unassigned document rendering its preview/extracted fields and all four actions; discard requiring confirmation; the manual-match picker showing only eligible expenses with a conflict warning; and the concrete regression test that rejecting a suggested match makes its receipt reappear in the unassigned-documents section without a page reload.
  - `alembic upgrade head` verified on a fresh temporary SQLite database (all 5 migrations, clean from scratch) and separately on a temporary SQLite database seeded with a pre-existing `receipt_uploads` row at the prior revision — the migration is purely additive (9 nullable columns), and the pre-existing row survived untouched with the new columns correctly `NULL`.
  - The actual live Supabase Postgres dev database (which had been left at the prior migration) was upgraded to head and verified end-to-end in the browser: the reconciliation inbox rendered its real, persisted unassigned-document rows (leftover pending uploads already in that database) with correct previews/extracted fields/timestamps and all four actions, the manual-match dialog opened and correctly showed its empty state (no `missing`-status expenses currently exist in that database), the "Add expense manually" link and the fallback `/upload-receipt`/`/add-expense` routes all resolved correctly, and the dashboard/expenses pages rendered without error against the live data.

## Security and reliability notes

- The server verifies the actual image bytes with Pillow — a JPEG/PNG/WebP claim in the request is never trusted on its own; a spoofed content type or corrupted file is rejected.
- Uploads are streamed to disk in bounded chunks and rejected as soon as they exceed the configured limit (default 10 MB via `MAX_UPLOAD_SIZE_BYTES`) — an oversized file is never fully buffered in memory, and any partial file is deleted.
- Stored filenames are always server-generated from the verified image format — the original filename/extension is discarded, which also rules out path traversal.
- Money (`amount`, `vat_amount`) is stored as SQL `Numeric(12, 2)` and handled as Python `Decimal` throughout — dashboard aggregation never uses binary floating-point arithmetic.
- Receipt uploads are tracked through an explicit lifecycle (`pending` → `confirmed`/`expired`/`discarded`/`failed`); every transition (confirm, attach, approve, discard) uses an atomic conditional `UPDATE`, so replaying a confirmation request, a double-approval, or a concurrent attach race can never create a duplicate expense or leave a document half-attached.
- Deleting an expense best-effort removes its receipt image (local file or Supabase object); a deletion failure is logged and never corrupts the database state or blocks the expense deletion itself.
- API responses never include the server's absolute file path or a permanent storage URL — only a relative `/uploads/...` path (local provider) or a freshly generated, time-limited signed URL (Supabase provider), regenerated on every response and never persisted.
- In `supabase` mode, the bucket is always private; the app never calls `get_public_url`, and `SUPABASE_SECRET_KEY` is read only by the backend process — it is never sent to the frontend, logged, or included in any API response or error message (verified in tests, including with a deliberately failing fake client whose error message contains the fake secret).
- Only a verified, already-uploaded file inside the configured uploads directory is ever sent to any extraction provider (local or OpenAI) — the client cannot supply an arbitrary filesystem path.
- CORS is restricted to the configured frontend origin (`http://localhost:5173` by default).
- No secrets are hardcoded; all configuration is read from environment variables via `.env` (see `.env.example`). The OpenAI API key is never logged, printed, or included in any API response.
- `/api/system/capabilities` reports only the provider name, mode (`mock`/`local`/`openai`, `demo`/`local`/`ai`), a `real_ai_enabled` boolean, and — in `local` mode only — non-sensitive `ollama_available`/`tesseract_available` booleans (computed with a 1-second-bounded local reachability check). Never a key, and never a filesystem path.
- Structured logs (provider, success/failure, duration, upload id, error category, missing fields) never include image bytes, base64 data, OCR/receipt text, card numbers, or full provider responses — verified explicitly in tests for the local provider (which is the one handling raw OCR text).

## What's next

- **Replace the demo webhook provider with a real bank/PSP integration.** The `WEBHOOK_PROVIDERS` registry ([`app/services/ingestion/webhook_provider.py`](backend/app/services/ingestion/webhook_provider.py)) is the intended extension point — a real provider means writing one more payload-parsing function and registering it there; the signature verification, idempotency, and Expense-creation logic never change. This also implies real OAuth/credential management, which does not exist yet.
- **Add a real email or POS document-ingestion connector.** No receipt currently arrives in the app on its own — every `ReceiptUpload` row today is created by a manual upload. `ReceiptUploadRepository.save_extraction()` plus the `pending`/`confirmed`/`expired`/`discarded` state machine is deliberately generic enough that a future connector (e.g. a forwarding-email inbox, or a POS integration) could create pending `ReceiptUpload` rows and let the existing matching/approval/inbox code pick them up unchanged — but no such connector exists yet, and none is faked in the UI or docs.
- Run a real, field-labeled accuracy evaluation of both the local and OpenAI providers against a representative set of real (not synthetic) photographed receipts, and record actual numbers here — including a same-receipt-set comparison between the two.
- Add authentication if the app moves beyond single-user local use — this also applies to Supabase Storage: the bucket is accessed only via the service key from the backend, so there is currently no per-user access control on receipt images, matching the app's existing single-user model.
- Code-split the frontend bundle (currently a single ~270 KB gzipped chunk, flagged by the Vite build but not a functional issue at this scale).
- **Remaining storage/deployment gaps:** this app does not create or configure the Supabase bucket itself (do that once, manually, before setting `STORAGE_PROVIDER=supabase`); there's no automated retry/backoff around Supabase Storage calls the way there is for the OpenAI/Ollama extractors (a transient network blip surfaces as an immediate `503` rather than being retried); and there's no background job to catch and clean up an object that finishes uploading to Supabase but whose `ReceiptUpload` row fails to commit afterward (an extremely narrow window, and no such case has been observed, but it isn't explicitly reconciled).

## Commands reference

```bash
# Backend
cd backend && source .venv/bin/activate
pytest                                  # run tests
uvicorn app.main:app --reload --port 8000   # run server
alembic revision --autogenerate -m "..."    # create a new migration
alembic upgrade head                        # apply migrations
python -m scripts.cleanup_uploads           # expire stale pending uploads
python -m scripts.demo_webhook_request      # send one signed demo transaction (needs WEBHOOK_SIGNING_SECRET)
python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --provider local --max-files 5   # evaluate accuracy (local)
python -m evaluation.evaluate_receipts --manifest evaluation/manifest.json --dry-run   # evaluate extraction accuracy (free)

# Frontend
cd frontend
npm run dev       # dev server
npm test          # run Vitest suite once
npm run test:watch  # Vitest in watch mode
npm run build     # type-check + production build
npm run lint      # lint
```
