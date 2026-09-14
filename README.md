# Sydney Revenue Manager

Sydney (**מנהל הכנסות מבית Sydney**) is an AI-ready sales and revenue management product for Israeli small businesses. Sales can be recorded manually or imported from a CSV export, appear immediately on the dashboard and sales list, and remain isolated to the authenticated business. The app tracks whether a receipt/tax document has been attached, and an AI assistant answers questions about revenue, VAT, fees, and refunds using only that business's data. Direct Grow/Cardcom ingestion is the next active integration milestone.

**Note on naming:** the GitHub repository is `sydney-expenses`, its original working name from before the domain model changed from expense tracking to sales and revenue management. The customer-facing product is **מנהל הכנסות מבית Sydney**. Some internal API and translation identifiers retain the earlier “Sydney Transaction Management” name and do not affect the product branding.

**Note on AI:** receipt/document image extraction (used only by the secondary "import a historical document" feature, described below) supports three interchangeable providers behind the same `ReceiptExtractor` interface: `MockReceiptExtractor` (default — deterministic, synthetic, needs nothing), `LocalReceiptExtractor` (real Vision extraction that runs entirely on your machine via Tesseract OCR + a local Ollama model — no API key, no external network call, no per-request cost), and `OpenAIReceiptExtractor` (real Vision extraction via the OpenAI Responses API). Mock mode is what the automated test suite and the default local setup use. See "Importing a historical document" below for what's been field-verified and what hasn't.

## Status

**A deployed sales/revenue workspace with CSV import, document tracking, an exception center, and an AI assistant that reasons correctly about gross vs. net revenue vs. profit.** The public production app contains no simulator, demo connection controls, reset action, or synthetic document issuance. The provider-neutral webhook and document adapter boundaries remain in the backend for the upcoming Grow/Cardcom and invoicing integrations.

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
│   │   ├── api/routes/   REST endpoints (auth, businesses, sales, dashboard, assistant, connections, webhooks, imports)
│   │   ├── models/       SQLAlchemy ORM models (businesses/members, sales/events, imports, connections, AI conversations)
│   │   ├── schemas/       Pydantic request/response models (Decimal money)
│   │   ├── services/extraction/  ReceiptExtractor interface, mock + local (Ollama/Tesseract) + OpenAI providers — used only by the secondary historical-document-import feature
│   │   ├── services/storage/     ReceiptStorage interface, local-disk + Supabase Storage providers
│   │   ├── services/documents/   DocumentProvider adapter boundary; issuance stays disabled until a real provider is connected
│   │   ├── services/exception_center.py  Sales that need a human's attention
│   │   ├── services/sale_service.py      Core sale lifecycle: create, attempt document issuance, refund
│   │   ├── services/ingestion/       Webhook signature verification + payment-provider parsing, CSV parsing/import
│   │   ├── services/      Business logic (uploads, dashboard)
│   │   ├── repositories/  Database access layer
│   │   └── database.py
│   ├── alembic/          Database migrations (the sole source of schema truth)
│   ├── scripts/          cleanup_uploads.py; demo_webhook_request.py — sends one signed demo customer payment
│   ├── samples/          sales-sample.csv — fictional CSV import sample
│   ├── evaluation/        Manual accuracy-evaluation CLI for the document-extraction pipeline (see its own README)
│   ├── tests/            pytest suite
│   └── uploads/          Locally stored document images when STORAGE_PROVIDER=local (gitignored)
├── .env.example
└── .gitignore
```

## How it works

A **sale** and a **document** are two different records that the app's job is to connect, not one and the same thing:

- A `Sale` row represents the *transaction* — a customer paying the business for a product or service. It normally arrives automatically (a payment webhook or a CSV sales import) with `document_status='pending'`.
- The receipt/invoice **issued to that customer** is tracked directly on the `Sale` row (`document_status`, `document_number`, `document_url`) — there's no separate "unassigned document" concept, because a document is either generated for a specific sale automatically, or explicitly imported onto one.

The target flow is: **a customer pays → a sale is created automatically → the sale and its document status appear immediately on the dashboard and sales list.**

1. A payment provider or POS system sends a webhook when a customer completes a purchase (in this demo, a signed local script stands in for that provider). Sydney creates a `Sale` row immediately — no manual entry.
2. Customer-document issuance remains pending until a real invoicing provider is connected. Production never creates a synthetic document number or claims that a legal document was issued.
3. The business owner's day-to-day job narrows to the **Exception Center**: sales whose document is still pending or failed to generate, refunds needing attention, and sales with incomplete customer/service details — not manually re-entering every sale.
4. If a real historical document needs to be attached to a sale (e.g. backfilling an old paper receipt), that's a secondary, explicit action — "Import historical document" — never the primary way sales get created.
5. The AI Assistant answers questions about revenue, VAT collected, processing fees, top services, and refunds — always from real data, and always correctly distinguishing gross revenue, net revenue, and profit (see "AI Assistant" below).

Adding a sale manually, via **Add sale manually**, still works — it's the fallback path for when no payment provider is connected, not the primary workflow.

## Israeli VAT and currency

Each verified account creates a private business workspace. The current release supports Israeli businesses, with country `IL`, reporting currency `ILS`, timezone `Asia/Jerusalem`, and standard VAT rate `18%`. Existing calculation defaults remain centralized in [`app/domain/demo_business.py`](backend/app/domain/demo_business.py), while ownership and business metadata are stored in the database. International tax logic is not implemented yet.

**Currency is not tax jurisdiction.** A sale can be charged in `ILS`, `USD`, or `EUR` (the closed set in the Sale form's currency select) while always being taxed under this business's Israeli VAT rules — switching a sale's currency never changes which tax rules apply, and this app implements no US sales-tax or EU-VAT logic of its own.

**VAT calculation.** Every sale has a `tax_treatment`: `standard` (ordinary 18% VAT, the default), `zero_rate` (VAT at 0%), or `exempt` (no VAT applies at all). `gross_amount` is always VAT-*inclusive* — what the customer actually paid — so for a `standard` sale, `vat_amount = gross_amount × 18 / 118`, never `gross_amount × 0.18` (that would incorrectly add VAT on top of an amount that already includes it). Example: gross `118.00` → VAT `18.00` → revenue before VAT `100.00`. `zero_rate` and `exempt` always compute `vat_amount = 0`. The calculation is backend-authoritative — see [`app/services/tax/vat.py`](backend/app/services/tax/vat.py) — the frontend form only ever *previews* it; `vat_amount` is not a field a client can set directly through the sale create/update API. Every sale also snapshots the VAT rate actually used onto `Sale.vat_rate`, so a future change to the business's standard rate can never rewrite a historical sale's VAT.

**Webhook and CSV ingestion.** The demo payment webhook accepts an optional `tax_treatment` (defaulting to `standard`) and computes `vat_amount` on the backend when the payload omits it; if the payload *does* send a `vat_amount`, it's validated against what the business's own tax configuration would compute for that treatment (within a one-cent rounding tolerance) and the request is rejected with `422` if it doesn't match — a provider silently claiming inconsistent financial data is never accepted as-is. CSV-imported sales (no VAT column in the documented v1 format) are treated as ordinary `standard`-VAT sales, the same default a manually entered sale gets.

**Multi-currency reporting.** The dashboard and the AI Assistant group every monetary total *by currency* and never add different currencies together — a dataset with only ILS sales shows ordinary single-figure cards; a dataset spanning ILS/USD/EUR shows a separate, clearly labeled figure per currency instead. There is no live exchange-rate conversion in this phase and none is invented; the reporting currency stays configured as ILS (see `app/domain/demo_business.py`) as the extension point for a future conversion feature.

## Automatic sale ingestion

The goal of this feature is that a human should not need to type in every sale by hand: a payment provider or POS system sends a webhook the moment a customer pays, and the app's job narrows to handling the exceptions (a document that failed to generate, a refund, incomplete details) rather than data entry.

**What's real today:**
- **Development-only simulator** ([`app/services/demo_simulator.py`](backend/app/services/demo_simulator.py)) — retained as an internal testing utility. Its API is blocked in production and it has no route, navigation item, reset control, or bundle in the public frontend.
- **CSV import** ([`app/services/ingestion/csv_import.py`](backend/app/services/ingestion/csv_import.py)) — upload a sales-export CSV, preview the parsed rows and any validation errors, then confirm to create sales. One documented format: `date,customer,service,amount,currency` with a header row. A sample file with fictional data is at [`backend/samples/sales-sample.csv`](backend/samples/sales-sample.csv).
- **Payment webhook foundation** ([`app/api/routes/webhooks.py`](backend/app/api/routes/webhooks.py)) — HMAC verification, timestamp checks, body limits, tenant routing, and database-level idempotency are implemented. The only current payload adapter is `demo-pay`, so connection management and demo ingestion are blocked in production until a real provider adapter is added.
- **Document issuance boundary** ([`app/services/documents/`](backend/app/services/documents/)) — production defaults to `DOCUMENT_PROVIDER=disabled`. `MockDocumentProvider` is available only for development/tests, and production configuration explicitly rejects it.
- **Exception Center** (`/exceptions`) and **Data Import** (`/imports`) — real production pages. Data Import currently exposes the working CSV flow only.

**Development adapters are not product features:** `demo-pay`, the simulator, and `MockDocumentProvider` remain test tools in source code. None is exposed or accepted by the production application. No real invoicing/tax-receipt provider is connected yet.

**Only completed payments count as revenue.** A `pending` or `failed` sale contributes nothing to any revenue total; a `refunded` sale contributes nothing; a `partially_refunded` sale contributes only its remaining (post-refund) net amount. See `Sale.revenue_contribution()` in [`app/models/sale.py`](backend/app/models/sale.py) — every dashboard stat and every assistant tool routes through this one method, so the "what counts as revenue" rule is defined in exactly one place.

**Explicit non-goals for this phase** (extension points exist, nothing here claims they already work): a live payment-provider/POS adapter, provider OAuth, a real invoicing or tax-receipt provider, team invitations, and role-management UI. Authentication, verified accounts, private business workspaces, stored roles, and tenant isolation are implemented.

### The sale and document lifecycle

- **`Sale.status`** owns the payment's own lifecycle: `succeeded` / `pending` / `failed` / `refunded` / `partially_refunded`.
- **`Sale.document_status`** owns the customer document's lifecycle, independently: `pending` → `issued` / `failed` / `not_required`.
- **`Sale.refunded_amount`** tracks how much of a sale's net amount has been refunded (partial or full) — the reason `revenue_contribution()` can compute the correct remaining revenue for a partially refunded sale without a separate ledger.

Every transition (creating a sale from a webhook, recording a refund) uses an atomic conditional operation or a database uniqueness constraint rather than a check-then-write, so two concurrent webhook deliveries of the same event, or a refund applied twice, can never silently corrupt a total.

### Try it end-to-end (fictional demo scenario)

**The easy way — no terminal, from the app itself:**

1. Open the app → **Local Demo Area** (`/demo`). Pick or type a Hebrew customer/service name, an amount, a currency, and a scenario (e.g. "Successful purchase"), then run it.
2. Open **Sales** — the new sale is there, clearly labeled as demo data, with its document already "issued." Click its name to open **Sale Details** — the full VAT/revenue breakdown and its real event timeline are both there.
3. Record a partial refund from Sale Details — the status, remaining-revenue figure, and timeline all update together.
4. Check the **Dashboard** — the revenue totals reflect it immediately. Ask the **AI Assistant** "כמה הכנסתי החודש?" / "How much revenue did I make this month?" — it reports the same figure, in the same currency.
5. When you're done, use **Reset demo data** on the Demo Area page — it deletes only what the simulator created, never your manual/CSV/webhook sales, and reports exactly how many rows were removed.

**The technical way — a real signed HTTP request, for developers:**

1. Start the backend with a webhook secret set (see below), and send one demo customer payment for **ILS 184.90**:
   ```bash
   cd backend && source .venv/bin/activate
   export WEBHOOK_SIGNING_SECRET=demo-secret-change-me
   python -m scripts.demo_webhook_request
   ```
2. Open the app → **Dashboard**. The sale appears immediately in "Recent sales" and in the revenue totals — no manual entry.
3. Check **Sales** (`/sales`) — the sale is there with its document already marked "issued" (the demo document provider ran automatically). Check **Exception Center** (`/exceptions`) — empty, since nothing needs attention yet.
4. Re-run the same script — the response now reports `created: false` with the same `sale_id`: delivering the same event twice never creates a duplicate sale.
5. Open the AI Assistant and ask "כמה הכנסתי החודש?" / "How much revenue did I make this month?" — it answers using the real sale you just created, correctly distinguishing gross from net revenue.

For the business-specific flow, open **Imports & Connections**, create a POS/payment connection, and copy the URL and one-time secret. Then run:

```bash
cd backend && source .venv/bin/activate
export DEMO_WEBHOOK_URL='http://localhost:8000/api/webhooks/connections/<connection-id>'
export DEMO_WEBHOOK_SECRET='<secret shown in the app>'
python -m scripts.demo_webhook_request
```

That endpoint identifies the business from the connection ID and verifies the request with that connection's own secret. The database stores only a random salt; the secret is derived from `CONNECTION_SIGNING_SECRET`, shown only when created or rotated, and never returned by the connection list API.

### Webhook signing (for real, not a simplification)

`POST /api/webhooks/payments` requires `X-Signature` (hex HMAC-SHA256) and `X-Timestamp` headers. The signature is computed over `"{timestamp}.{raw request body}"` using a secret from `WEBHOOK_SIGNING_SECRET` — verification uses `hmac.compare_digest`, a stale timestamp (`WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS`, default 300s) is rejected, and the body is size-capped (`WEBHOOK_MAX_BODY_BYTES`, default 64KB) before it's even parsed. The payload, signature, and secret are never written to a log line. Delivering the same `external_transaction_id` twice never creates a second sale — idempotency is enforced by a database `UNIQUE(source_provider, external_id)` constraint, not just an application-level check, so it's safe under concurrent delivery too.

```bash
curl -X POST http://localhost:8000/api/webhooks/payments \
  -H "Content-Type: application/json" \
  -H "X-Signature: <computed HMAC>" \
  -H "X-Timestamp: <unix seconds>" \
  -d '{"event_id":"evt-1","provider":"demo-pay","external_transaction_id":"txn-1","occurred_at":"2026-09-10T09:00:00+00:00","customer_name":"Demo Customer","customer_email":"demo@example.com","service_name":"Consulting session","gross_amount":"184.90","vat_amount":"28.21","processing_fee":"5.55","net_amount":"151.14","currency":"ILS","payment_method":"card","tax_treatment":"standard","status":"succeeded"}'
```
Computing the signature by hand is fiddly — use [`backend/scripts/demo_webhook_request.py`](backend/scripts/demo_webhook_request.py), which builds and signs this exact request for you.

### CSV import format

Header row required, exactly these five columns:
```
date,customer,service,amount,currency
2026-09-01,Demo Fictional Customer,Consulting session,184.90,ILS
```
`date` is `YYYY-MM-DD`; `amount` must be a positive number; `currency` a 3-letter code. UTF-8 and UTF-8-with-BOM are both accepted transparently. Re-importing the same file is safe — a stable id is derived from the file's hash plus row number, so repeat rows are skipped as duplicates (reported in the confirmation summary) rather than re-created.

## Refunds and the Exception Center

Refunds are recorded explicitly via `POST /api/sales/{id}/refund` (no real payment provider sends a refund webhook in this demo) — omit `amount` for a full refund, or supply it for a partial one. A refund can never exceed a sale's net amount (`409` if it would), and refunding an already-fully-refunded sale again is a safe no-op, not a double deduction.

The **Exception Center** (`/exceptions`) replaces what used to be a receipt-to-expense reconciliation inbox — there's no more matching to review, because a sale's document is either issued automatically or imported explicitly onto a named sale. It surfaces four things:
- Successful sales whose document is still `pending`
- Sales whose document generation `failed`
- Sales that are `refunded` or `partially_refunded`
- Sales missing a customer contact (email/phone) — the one genuinely optional customer field

## Importing a historical document (secondary feature)

Attaching a photo of a **previously issued** receipt or invoice to a specific sale — e.g. backfilling paper records — is an explicit, secondary action (`/import-document?saleId=...`, reached from a sale's own row or from the Exception Center), never part of the primary sales journey and never in the main navigation. It reuses the same hardened image-verification, extraction, and storage pipeline described below, but the extracted data only ever updates that one named sale's document fields — there is no auto-matching, no "suggested match" UI, and no unassigned-document inbox.

Controlled by one environment variable, `RECEIPT_EXTRACTOR_PROVIDER`:

| | `mock` (default) | `local` | `openai` |
|---|---|---|---|
| Needs an API key | No | No | Yes (`OPENAI_API_KEY`) |
| Sends data externally | Never | Never — everything runs on this machine | Yes — the document image is sent to OpenAI |
| What it costs | Free | Free per request — but uses local RAM, disk, CPU/GPU, and electricity while running | Billed per request by OpenAI |
| Determinism | Same image → same result | Model output, not deterministic | Model output, not deterministic |
| Needs installed first | Nothing | Ollama + a pulled model, Tesseract + `heb`/`eng` language data | Nothing (just the key) |
| Used by the automated test suite | Yes | Yes (via a fake HTTP client + mocked OCR — never calls a real model) | Yes (via a fake client) |

**Mock mode** needs nothing beyond the default setup. It's a deterministic, offline stand-in that lets the whole import → extract → attach pipeline be exercised (and tested) without any external dependency or cost.

### Local mode (Tesseract + Ollama — fully offline, free per request)

Runs two things locally for each document image: Tesseract OCR (`heb+eng`) reads the text, and a local vision-capable Ollama model reads the image itself plus that OCR text (offered only as an untrusted hint the model can override) and returns strict JSON matching the same schema as every other provider. Nothing ever leaves your machine.

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
   OLLAMA_NUM_CTX=16384         # context window for a full request; a tall document + full prompt needs >8192
   OLLAMA_NUM_PREDICT=2048      # max output tokens for a full request; too small truncates JSON before it closes
   OLLAMA_NUM_CTX_FAST=8192     # smaller budget used once every factual field is already OCR-resolved
   OLLAMA_NUM_PREDICT_FAST=1024
   OLLAMA_TEMPERATURE=0.0       # deterministic sampling — see "Local model choice" below
   OLLAMA_SEED=42
   TESSERACT_LANGUAGES=heb+eng
   ```
4. Restart the backend. The "Import historical document" page shows "Local extraction active — your data stays on this computer" whenever the backend reports `local` mode.

**Resource cost, not API cost:** there's no per-request bill, but an 8-12B model resident in memory uses several GB of RAM and meaningfully more CPU/GPU and electricity than the mock provider while it's generating — expect real wall-clock latency (single-digit seconds to a couple of minutes per document depending on model warm-up and how much the deterministic parser already resolved, see the model-choice section for measured numbers) rather than an instant response. Only one model needs to be loaded at a time — run `ollama stop <model-name>` to free its memory when you're done, and `ollama ps` to see what's currently loaded.

**If Ollama isn't running or the model isn't pulled**, extraction fails gracefully — the document image is still stored and attached to the sale (see "Importing a historical document" above), just without extracted fields. The import page also proactively checks reachability (via `GET /api/system/capabilities`) and shows a specific "Ollama isn't running" message before you even try importing, rather than waiting for a failed request.

**If Tesseract fails** (missing binary, missing language data, or any OCR error), extraction continues using the image alone — the vision model can often still read the document without OCR assistance — with a warning noting OCR was unavailable.

#### Preprocessing, spatial OCR, deterministic parsing, and the merge policy

An evidence-driven accuracy pass, run against a private set of 4 real, varied Hebrew receipt photos (never committed — see "Evaluating real accuracy" below), found and fixed several compounding root causes of poor extraction:

1. **A narrow document photographed on a large white background was cropped, deskewed, and perspective-corrected before any OCR or model call.** [`document_geometry.py`](backend/app/services/extraction/document_geometry.py) detects the document region via Otsu thresholding + morphological closing + contour analysis, working at a capped resolution (max 1600px on the long edge) so cost stays bounded regardless of upload size. It crops to the union of all significant contours (a single-largest-contour approach was tried first and rejected — it catastrophically over-cropped real photos where receipt text forms several disconnected blobs rather than one solid rectangle); perspective correction only triggers when one contour clearly dominates the union and forms a clean convex quadrilateral, otherwise the image is just deskewed via a minimum-area rotated rectangle. Every step falls back to the original, uncropped image on low confidence or any failure — this step can only help, never break, an import.
2. **[`image_preprocessing.py`](backend/app/services/extraction/image_preprocessing.py) then scales the cropped image** primarily off width (targeting ~1400px), with EXIF orientation correction and hard caps on both max dimension (4000px) and total pixel count (15M px), and generates four variants: `enhanced` (grayscale + autocontrast + mild sharpen), `illumination_normalized` (CLAHE — recovers a severely faded or unevenly lit document), `adaptive_threshold` (local, not global, binarization — survives uneven lighting across a single photo far better than the old global-Otsu threshold it replaces), and `denoised` (light median filter).
3. **OCR moved from flat text to spatial data.** [`ocr_selection.py`](backend/app/services/extraction/ocr_selection.py) now calls `pytesseract.image_to_data` across a bounded matrix of (variant, page-segmentation mode) combinations, keeping each word's bounding box, confidence, and block/paragraph/line grouping — not just a flat string. Flat text (reconstructed in visual reading order from the same word boxes) is kept only as a secondary signal; full OCR output is never logged.
4. **[`receipt_parser.py`](backend/app/services/extraction/receipt_parser.py) was rewritten to reason spatially, not just textually.** It finds Hebrew/English label words (`סה"כ לתשלום`, `סה"כ`, `שולם`, `מע"מ`/`סכום מע"מ`, `תאריך`, `חשבונית מס`/`קבלה`, handling common OCR-dropped-diacritic variants) and associates each with the nearest money-shaped or date-shaped word by position, not by scanning line text with regex. A **competing-label disambiguation** step only accepts a candidate value for a label when it is unambiguously closer to that label than to any other recognized label on the same line, rather than just picking the nearest number. VAT candidates are validated (must be ≥0 and ≤ the total; a value matching Israel's standard VAT-inclusive ratio is used only as supporting evidence, never as a hard rule) and document-number punctuation (hyphens, slashes) is preserved instead of stripped.
5. **[`merge.py`](backend/app/services/extraction/merge.py) keeps vision-model and OCR/parser evidence explicitly separate**, never blending them into one unlabeled number: agreement between the two sources raises confidence, a confident parser candidate fills a gap the model left null (flagged `*_from_ocr`), a genuine disagreement is never resolved silently — the more trustworthy source wins but a `*_conflicting_sources` warning always fires — and a weak/unlabeled OCR guess never overrides a clear vision-model reading. Business name is read from the document's header region plus the vision model; a document category is inferred from that name and context only when there's enough evidence, with an explicit `category_from_merchant_name` fallback (never allowed to influence total/VAT/date) when the model itself doesn't return one confidently.
6. **A later determinism/latency pass made the pipeline deterministic-first.** `local_extractor.py` now checks, per extraction, which factual fields (`receipt_number`/`date`/`total`/`vat`/`currency`) the parser resolved with *high* confidence and drops exactly those fields from the vision model's own JSON-schema request — the model is asked only for the fields still unresolved plus the two fields it always owns (`business_name`, `category`), so a stochastic model answer can never even be offered as a conflicting value for a field the parser already confidently settled. Sampling is explicit and deterministic (`OLLAMA_TEMPERATURE=0.0`, `OLLAMA_SEED=42`) rather than left at each model's own Ollama default.

See [`backend/tests/test_document_geometry.py`](backend/tests/test_document_geometry.py), [`test_ocr_selection.py`](backend/tests/test_ocr_selection.py), and [`test_receipt_parser.py`](backend/tests/test_receipt_parser.py) for synthetic-fixture regression coverage of each of these (no real document image is ever used in an automated test).

### Local model choice: gemma3:12b vs. qwen3-vl:8b

Both models were evaluated with the exact same pipeline above, against the same private 4-receipt manifest, using [`backend/evaluation/evaluate_receipts.py --model <name>`](backend/evaluation/README.md):

| Field-level accuracy | gemma3:12b | qwen3-vl:8b |
|---|---|---|
| receipt_number | 67% (2/3) | 67% (2/3) |
| date | 75% | 75% |
| total | 100% | 100% |
| vat | 75% | 75% |
| currency | 100% | 100% |
| category | 50% (1/2) | 50% (1/2) |
| exact-match (every field correct) | 1/4 | 1/4 |
| avg. latency per document | ~30s | ~62s |

**gemma3:12b is the current default** (`OLLAMA_RECEIPT_MODEL=gemma3:12b`). Under the deterministic-first pipeline, the two models produce identical measured field-level accuracy on this manifest; with accuracy equal, gemma3:12b's materially lower latency (~2x faster on average here) makes it the better default. `qwen3-vl:8b` remains fully supported — set `OLLAMA_RECEIPT_MODEL=qwen3-vl:8b` to use it.

**Read this table honestly, not as a general accuracy claim:** n=4 real receipts is a small, private evaluation set, not a representative sample.

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
3. Restart the backend.

**If the key or model is missing** while `openai` mode is selected, extraction fails gracefully (a clear, non-sensitive error) — the document is still stored and attached to the sale. The same graceful-degradation behavior applies to `local` mode.

The mode badge is fed by `GET /api/system/capabilities` — a safe endpoint that returns only the provider name, mode, a `real_ai_enabled` boolean, and (in `local` mode only) non-sensitive `ollama_available`/`tesseract_available` booleans. Never a key, never a filesystem path.

**Privacy implications:** in `openai` mode, the verified document image is base64-encoded and sent to OpenAI's API for that single request (`store=False`, not used for multi-turn state) — review OpenAI's own data-handling terms before enabling it if your documents contain sensitive personal data. In `local` mode, the image and its OCR text never leave the machine at all. Neither mode ever writes image bytes, extracted document text, or an API key to the application's own logs.

**Evaluating real accuracy:** `backend/evaluation/` has a small CLI to measure field-level extraction accuracy against your own manually labeled receipts, for any of the three providers (`--provider mock|local|openai`). See [`backend/evaluation/README.md`](backend/evaluation/README.md) for setup and exact commands.

**Current limitations:**
- No live OpenAI request has been run in this environment (no API key available here) — the OpenAI provider is verified only against mocked client responses in the test suite.
- The local provider has been run against a private, manually labeled set of 4 real, varied Hebrew receipt photos — field-level accuracy under the current deterministic-first pipeline: 100% on total/currency, 75% on date/vat, 67% on receipt_number, 50% on category. That is still a small, private sample (n=4), not a general accuracy claim.
- The quality score is a heuristic, not a calibrated accuracy measure.

**Troubleshooting:**
- *Extraction fails every time in `openai` mode* → check `OPENAI_API_KEY` and `OPENAI_RECEIPT_MODEL` are set in `backend/.env` and the backend was restarted after editing it.
- *Extraction fails every time in `local` mode, or the "Ollama isn't running" banner* → run `ollama serve` (or confirm the background service is running), then `ollama list` to confirm the model in `OLLAMA_RECEIPT_MODEL` is actually pulled.
- *"ocr_unavailable" warnings every time in `local` mode* → confirm `tesseract --version` works and `tesseract --list-langs` lists both `heb` and `eng`.
- *Badge stuck on "Demo mode" after switching provider* → the backend wasn't restarted, or `RECEIPT_EXTRACTOR_PROVIDER` isn't actually set in the environment the backend process reads from.

## Document image storage: local vs. Supabase

Persisting a verified document image (from the historical-document-import feature) is behind the same kind of provider-independent interface as extraction — a `ReceiptStorage` abstraction ([base.py](backend/app/services/storage/base.py)) with two implementations, selected via `STORAGE_PROVIDER`:

- **`local`** (default) — writes the verified image to `UPLOADS_DIR` on disk, served back by the API's own `/uploads/...` route. Needs no external credentials; this is what the automated test suite and a fresh clone use.
- **`supabase`** — uploads the verified image to a **private** Supabase Storage bucket. The bucket must already exist with public access disabled (`SUPABASE_STORAGE_BUCKET`, default `receipts`); this app does not create or configure the bucket for you.

**Private bucket, signed URLs only:** the Supabase provider never calls `get_public_url` and the bucket is never made public. Only a stable **object key** (a random, server-generated name, never the original filename) is persisted in the database — never a URL, and never the service key. Every time the API returns a document image URL to the frontend, it generates a **fresh, time-limited signed URL** on the spot via `create_signed_url` (TTL configured by `SUPABASE_SIGNED_URL_TTL_SECONDS`, default 1 hour). If a signed URL happens to expire before the user views it, the frontend's document-image view (`ReceiptImage` component) catches the `<img>` load failure and shows a plain-text fallback instead of a broken-image icon.

**Enabling Supabase Storage:**

1. In your Supabase project, create a **private** Storage bucket (public access disabled).
2. In `backend/.env` (never commit this file):
   ```bash
   STORAGE_PROVIDER=supabase
   SUPABASE_URL=https://your-project-ref.supabase.co
   SUPABASE_SECRET_KEY=...        # the service/secret key — never the anon/public key
   SUPABASE_STORAGE_BUCKET=receipts
   SUPABASE_SIGNED_URL_TTL_SECONDS=3600   # optional, default shown
   ```
   **Security warning:** `SUPABASE_SECRET_KEY` bypasses Row Level Security and can read/write the entire project's storage — treat it like a database superuser password. It is never logged, printed, sent to the frontend, or included in any API response.
3. Restart the backend. If `STORAGE_PROVIDER=supabase` but any required variable is missing, the app **fails fast at startup**.
4. Run the Alembic migration (`alembic upgrade head`) against whichever database you're using.

## Internationalization

- Hebrew is the default language on first load (no saved preference); English is available via the language switcher in the header.
- The selected language persists in `localStorage` (`receiptly-language`).
- `<html lang>` and `<html dir>` update automatically — Hebrew renders RTL, English renders LTR.

## AI Assistant

Answers questions about sales and revenue using a bounded OpenAI tool-calling loop over read-only query functions — never raw SQL, and the model never sees the database schema directly. Every number returned by a tool comes from `Sale.revenue_contribution()` or a direct field on `Sale`, so the assistant can never invent a figure or double-count a refunded sale.

**Financially precise by design:** the system prompt explicitly distinguishes gross revenue (what customers paid, before VAT and processing fees), net revenue (what the business actually keeps), and profit (which needs expense data this app doesn't track) — if asked "כמה הרווחתי?" ("how much did I profit?"), it answers with the gross or net revenue it actually has, names which one, and says plainly that true profit needs expense data too. It replies in whichever language the user asked in.

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

Optionally, expire stale pending document-import uploads and clean up their orphaned temp files — safe to run manually or on a daily cron:

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

- **Dashboard** — revenue this month vs. last month, successful sale count, average transaction value, gross revenue, VAT collected, processing fees, top services, a revenue trend chart, recent sales, and an exceptions overview.
- **Sales** — search, filter by status/date, edit, delete, view an attached document, import a historical document for a sale that's still missing one, or click a row to open its full **Sale Details** page.
- **Sale Details** (`/sales/:id`) — the complete picture for one sale: customer/service/description, origin (source, provider, external reference), the full VAT/currency breakdown (gross, tax treatment, VAT rate snapshot, VAT amount, revenue before VAT, processing fee, net revenue, refunded amount, remaining revenue), customer-document status, and a persisted, real (never invented) event timeline. Provider-originated facts (source, external reference) are always read-only; editing only ever changes the fields a human is actually allowed to correct.
- **Add sale** (fallback) — manual entry with validation.
- **Exception Center** — sales whose document is pending or failed, refunds needing attention, and sales with incomplete customer details.
- **Import historical document** (secondary, reached from a sale's own row) — attach a photo of a previously issued receipt/invoice to that specific sale.
- **Data Import** — CSV sales-export import with preview and explicit confirmation.
- **Language switcher** (top right) — toggle between עברית and English at any time.
- Old routes (`/expenses`, `/add-expense`, `/upload-receipt`, `/reconciliation`) redirect to their new equivalents, so old bookmarks/links don't break.

## Verification performed

- `pytest` (backend, 430 tests) — including business isolation, development-only integration gates, signed webhook routing, persisted assistant conversations, sale validation, VAT calculation, ingestion idempotency, CSV/document import, dashboard math, exception handling, security controls, and the complete Alembic migration chain. All passing.
- `npm test` (frontend, 100 tests), `tsc -b`, `oxlint`, `npm run build` — all passing. Coverage includes authentication, persisted assistant conversations, CSV import, sales, Sale Details, dashboard, exception center, and historical-document import. `oxlint` currently reports six non-blocking React warnings and no errors.
- `npm audit --omit=dev` and `pip-audit` — no known production dependency vulnerabilities reported on 14 September 2026.
- `alembic upgrade head` verified on a fresh temporary SQLite database (the entire migration chain, from the original `expenses` table through to `sale_events`) and separately as an incremental upgrade on the live development database carrying real prior data forward — this specifically caught and fixed a real bug (a data-backfill migration writing an enum value in the wrong case for how it's actually stored, which only surfaced on a genuine round-trip, not against the ORM-only test suite).
- Manual end-to-end verification in the browser: local demo simulator → a realistic sale appears on the dashboard and sales list within seconds, clearly labeled as demo data → Sale Details shows the correct VAT/revenue breakdown and a real, persisted timeline → recording a partial refund updates the status, the remaining-revenue figure, and the timeline together → the dashboard total updates → the AI assistant correctly reports the same revenue, in the same currency.

## Security and reliability notes

- The server verifies the actual image bytes with Pillow — a JPEG/PNG/WebP claim in the request is never trusted on its own; a spoofed content type or corrupted file is rejected.
- Uploads are streamed to disk in bounded chunks and rejected as soon as they exceed the configured limit (default 10 MB via `MAX_UPLOAD_SIZE_BYTES`) — an oversized file is never fully buffered in memory, and any partial file is deleted.
- Stored filenames are always server-generated from the verified image format — the original filename/extension is discarded, which also rules out path traversal.
- Money (`gross_amount`, `vat_amount`, `processing_fee`, `net_amount`, `refunded_amount`) is stored as SQL `Numeric(12, 2)` and handled as Python `Decimal` throughout — dashboard and assistant aggregation never uses binary floating-point arithmetic.
- Every sale-lifecycle transition (webhook ingestion, refund) uses an atomic conditional operation or a database uniqueness constraint, never a select-then-write, so a concurrent duplicate delivery or a double refund can never corrupt a total.
- API responses never include the server's absolute file path or a permanent storage URL — only a relative `/uploads/...` path (local provider) or a freshly generated, time-limited signed URL (Supabase provider).
- In `supabase` mode, the bucket is always private; the app never calls `get_public_url`, and `SUPABASE_SECRET_KEY` is read only by the backend process — never sent to the frontend, logged, or included in any API response or error message.
- Only a verified, already-uploaded file inside the configured uploads directory is ever sent to any extraction provider — the client cannot supply an arbitrary filesystem path.
- CORS is restricted to the configured frontend origin (`http://localhost:5173` by default).
- No secrets are hardcoded; all configuration is read from environment variables via `.env` (see `.env.example`). API keys are never logged, printed, or included in any API response.
- `/api/system/capabilities` reports only the provider name, mode, a `real_ai_enabled` boolean, and (in `local` mode only) non-sensitive reachability booleans. Never a key, and never a filesystem path.
- Structured logs never include image bytes, base64 data, OCR/document text, card numbers, webhook payloads/signatures/secrets, or full provider responses.
- Browser authentication uses HttpOnly cookies, mutating requests require an allowed `Origin`, verified accounts are mapped to database-backed business memberships, and request-scoped ORM guards apply `business_id` isolation to reads and writes.
- Production refuses to start with authentication disabled, missing Supabase credentials, localhost/non-HTTPS CORS origins, wildcard/local trusted hosts, missing/short connection and CSV-signing secrets, or the mock document provider enabled. Interactive API documentation is disabled in production and security headers are applied to all responses.

## What's next

- **Replace the demo payment webhook with a real PSP/POS integration.** The `WEBHOOK_PROVIDERS` registry ([`app/services/ingestion/webhook_provider.py`](backend/app/services/ingestion/webhook_provider.py)) is the intended extension point — a real provider means writing one more payload-parsing function and registering it there; the signature verification, idempotency, and `Sale`-creation logic never change. This also implies real OAuth/credential management, which does not exist yet.
- **Add a real invoicing/tax-receipt provider.** `DocumentProvider` ([`app/services/documents/base.py`](backend/app/services/documents/base.py)) is the intended extension point — a real provider (e.g. an Israeli-compliant e-invoicing service) means implementing that interface and selecting it via configuration; `sale_service.finalize_new_sale` never changes. No such provider exists yet, and `MockDocumentProvider` never claims to be one.
- Add password recovery, account/business settings, data export/deletion, team invitations, and role-management UI. The underlying business membership model and owner/manager/viewer enforcement already exist.
- Add database-aware health checks, centralized error monitoring, backup/restore procedures, and shared rate limiting before scaling beyond a single server. The frontend and API are already deployed behind HTTPS on Vercel, with Supabase and the API colocated in London.
- Run a real, field-labeled accuracy evaluation of both the local and OpenAI document-extraction providers against a representative set of real (not synthetic) photographed receipts.
- **Normalized `Customer` and `Service` entities.** Sales still carry customer/service as plain snapshot fields on `Sale` itself, not foreign keys to their own tables — the right design for "who's my most frequent customer" / "which service earns the most" questions, but not yet built. Adding them is additive (new tables + a nullable FK on `Sale`, backfilled conservatively only on an exact email/phone match) and doesn't require touching existing sale records' historical meaning.
- **A dedicated `Refund` model.** Refunds today are still a cumulative field on `Sale` (`refunded_amount`/`status`), not their own rows — sufficient for "how much is left on this sale" but not for "how much was refunded *in* a given period" versus "how much revenue occurred in that period," which need separate rows with their own timestamps to answer honestly. `SaleEvent` (added in this pass) already records *that* a refund happened, chronologically; a `Refund` table with its own amount/currency/reason/timestamp is the next step for period-accurate reporting.
- **Engineering quality follow-ups:** add a GitHub Actions workflow running the backend/frontend suites, lint, dependency audits, and production build on every push; add page-level error boundaries and browser-level end-to-end tests for signup, onboarding, and the primary sales flow.
- **Remaining storage/deployment gaps:** this app does not create or configure the Supabase bucket itself; there's no automated retry/backoff around Supabase Storage calls; and refund/gross-revenue reporting for a partially refunded sale doesn't proportionally re-derive VAT/fee splits (documented in `dashboard_service.py`) since no structured refund line-item exists to do that honestly yet.

## Commands reference

```bash
# Backend
cd backend && source .venv/bin/activate
pytest                                  # run tests
uvicorn app.main:app --reload --port 8000   # run server
alembic revision --autogenerate -m "..."    # create a new migration
alembic upgrade head                        # apply migrations
python -m scripts.cleanup_uploads           # expire stale pending uploads
python -m scripts.demo_webhook_request      # send one signed demo customer payment (needs WEBHOOK_SIGNING_SECRET)
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

## Public website and authentication

The public home is `/`, email sign-up is `/signup`, login is `/login`, and the
protected dashboard is `/app`. Existing sales/import/assistant URLs remain valid
and now require authentication. The Higgsfield background is stored locally at
`frontend/public/images/sydney-hero.png`.

Authentication uses the existing server-side `SUPABASE_URL` and
`SUPABASE_SECRET_KEY` through Supabase Auth (not the admin user-creation API).
The browser receives HttpOnly session cookies, never the secret key or refresh
token in JavaScript. All business APIs and local uploaded files require a verified
Supabase account with a database-backed business membership. After verification,
a new account creates a private Israeli business workspace. Every sale, import
and audit event is scoped to that business in the backend. Existing records were
preserved under the original business. Each business can now create its own
signed payment/POS endpoint from Imports & Connections.

The first release supports one business per user and three stored roles: owner,
manager and viewer. Owners and managers may change business data; viewers can
read reports and use the assistant. Team invitations and role-management UI are
not exposed yet. See `docs/business-isolation.md` for the rollout boundaries.

Assistant conversations are persisted in the database per user and business.
Users can create, reopen, rename automatically through the first prompt, and
delete conversations; switching pages or signing in again does not erase the
conversation history. Only a bounded recent message window is sent to the model.

In Supabase Authentication > URL Configuration, allow the actual frontend origin
plus `/login` as a redirect URL, e.g. `http://localhost:5174/login`, and set Site URL
to that frontend origin. Keep email confirmation enabled. After verifying the
email, return to `/login` and sign in with the registered password. The signup
request supplies the allowed frontend origin as its redirect target. No real
registration/verification emails are sent by automated tests.

`CORS_ALLOWED_ORIGINS` must list the exact frontend origin. Mutating browser API
calls also require a matching Origin header for CSRF protection. Keep the frontend
and API on the same site (localhost during development); production uses Secure
cookies when `APP_ENVIRONMENT=production`, and should use HTTPS with an API reverse
proxy or same-site subdomain. `AUTH_REQUIRED=false` is for isolated automated
tests only and must not be used for a public deployment. The `/api/webhooks/payments`
endpoint is a development-only HMAC integration and returns `404` in production.

Production startup also requires an explicit `ALLOWED_HOSTS` list and a dedicated
random `CSV_PREVIEW_SIGNING_SECRET` of at least 32 characters. CSV preview rows are
signed, bound to the current business and filename, and expire after 15 minutes;
the confirmation endpoint rejects altered, expired, unsigned, or cross-business
payloads. Configure request-body limits and TLS at the reverse proxy as well. See
[`docs/security.md`](docs/security.md) for the deployment controls that cannot be
enforced solely inside this repository.
