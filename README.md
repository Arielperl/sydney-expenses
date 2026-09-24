# Sydney Revenue Manager

Sydney (**מנהל הכנסות מבית Sydney**) is an AI-ready sales and revenue management product for Israeli small businesses. Sales can be recorded manually, imported from a CSV export, or ingested automatically from a connected Grow or Cardcom account, and appear immediately on the dashboard and sales list, remaining isolated to the authenticated business. The app tracks whether a receipt/tax document has been attached, and an AI assistant answers questions about revenue, VAT, fees, refunds, individual transactions, customers, services, payment methods, averages, and period comparisons using only that business's data.

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
2. If that provider is Grow or Cardcom, its own customer document is linked automatically once the provider delivers it (see "Automatic provider documents" below) — the sale shows **"waiting for provider document"**, never a false "issued," until it actually arrives. Without a document-capable provider connected, issuance remains pending until a real invoicing provider exists. Production never creates a synthetic document number or claims that a legal document was issued.
3. The business owner's day-to-day job narrows to the **Exception Center**: sales whose document genuinely needs attention (a generation failure, or an automatic document that never arrived within a reasonable time — never a normal, still-waiting sale), sales needing a historical document, and legacy sales whose VAT treatment needs review — not manually re-entering every sale.
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

The goal of this feature is that a human should not need to type in every sale by hand: a payment provider or POS system sends a webhook the moment a customer pays, and the app's job narrows to handling actionable document and VAT-review exceptions rather than data entry.

**What's real today:**
- **Development-only simulator** ([`app/services/demo_simulator.py`](backend/app/services/demo_simulator.py)) — retained as an internal testing utility. Its API is blocked in production and it has no route, navigation item, reset control, or bundle in the public frontend.
- **CSV import** ([`app/services/ingestion/csv_import.py`](backend/app/services/ingestion/csv_import.py)) — upload a sales-export CSV, preview the parsed rows and any validation errors, then confirm to create sales. One documented format: `date,customer,service,amount,currency` with a header row. A sample file with fictional data is at [`backend/samples/sales-sample.csv`](backend/samples/sales-sample.csv).
- **Grow connection** ([`app/services/ingestion/grow_provider.py`](backend/app/services/ingestion/grow_provider.py)) — a real, production payment integration. See "Grow connection (account-level webhook)" above for the full details.
- **Cardcom connection** ([`app/services/ingestion/cardcom_provider.py`](backend/app/services/ingestion/cardcom_provider.py)) — a real, production payment integration, completely separate from Grow (its own adapter, its own connection type, its own credentials, its own status mapping). See "Cardcom connection (per-terminal webhook + server-to-server verification)" below for the full details.
- **Payment webhook foundation** ([`app/api/routes/webhooks.py`](backend/app/api/routes/webhooks.py)) — HMAC verification (demo-pay), source-IP verification (Grow), or server-to-server verification plus source-IP defense-in-depth (Cardcom); timestamp checks, body limits, tenant routing, and database-level idempotency are implemented for all of them. `demo-pay` remains a development/test-only payload adapter, blocked from creation and ingestion in production; `grow` and `cardcom` are the production-allowed providers.
- **Document issuance boundary** ([`app/services/documents/`](backend/app/services/documents/)) — production defaults to `DOCUMENT_PROVIDER=disabled`. `MockDocumentProvider` is available only for development/tests, and production configuration explicitly rejects it.
- **Exception Center** (`/exceptions`) and **Data Import** (`/imports`) — real production pages. Data Import currently exposes the working CSV flow only.

**Development adapters are not product features:** `demo-pay`, the simulator, and `MockDocumentProvider` remain test tools in source code. None is exposed or accepted by the production application. No real invoicing/tax-receipt provider is connected yet.

**Only completed payments count as revenue.** A `pending` or `failed` sale contributes nothing to any revenue total; a `refunded` sale contributes nothing; a `partially_refunded` sale contributes only its remaining (post-refund) net amount. See `Sale.revenue_contribution()` in [`app/models/sale.py`](backend/app/models/sale.py) — every dashboard stat and every assistant tool routes through this one method, so the "what counts as revenue" rule is defined in exactly one place.

**Explicit non-goals for this phase** (extension points exist, nothing here claims they already work): Grow's paid platform API (payment collection, PaymentLinks, `ApproveTransaction`), Cardcom's `LowProfile/Create` checkout-page creation and token-only/suspended-deal operations, refund/cancellation ingestion for any provider, provider OAuth, a real invoicing or tax-receipt provider, team invitations, and role-management UI. Authentication, verified accounts, private business workspaces, stored roles, tenant isolation, and the Grow and Cardcom webhook connections are implemented.

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

### Grow connection (account-level webhook)

A real, production integration with [Grow](https://developers.grow.business/) — specifically the **passive, account-level webhook** Grow offers, confirmed directly by Grow's own representative. This deliberately does **not** implement Grow's paid platform API (`CreatePaymentProcess`/`notifyUrl`, `ApproveTransaction`, payment collection, or PaymentLinks) — only the webhook Grow already sends automatically whenever a transaction completes on a connected terminal/account.

**How a business owner connects Grow:**

1. Open **Data Import** (`/imports`) and, in the **Grow connection** panel, add a connection — give it a name (e.g. the terminal's name, so one business can connect multiple tills/terminals each with its own connection).
2. Copy the connection's unique webhook URL (the **copy webhook URL** button).
3. Paste that URL into the corresponding webhook field in your Grow account's own settings for that terminal/account (per-terminal webhook configuration is supported directly by Grow — see Grow's own webhook docs).
4. The connection shows **"waiting for first transaction"** until Grow actually sends one — it is never described as verified or active before that happens.

Only the business **owner** can create, enable/disable, delete, or rotate a Grow connection (managers and viewers can see nothing beyond what the rest of the product already shows them). There is no signing secret to see or configure for Grow — Grow has no signing capability at all, and `webhookKey` (which does appear in Grow's payloads) is confirmed by Grow to not be a secret and is never treated as one, never displayed, and never logged.

**Supported Grow event types:** one-time regular transactions and installment-plan transactions from Grow's account-level "Regular Payment Webhook Format via API" (`paymentType` `"רגיל"`/`"תשלומים"`). Grow's documentation publishes no distinct payload example for a POS-device or mobile-app transaction specifically — both are assumed, per this integration's documented scope, to use this same account-level shape until a real transaction from either proves otherwise (see `app/services/ingestion/grow_provider.py`'s module docstring). A standing-order/recurring-payment webhook (`"הוראת קבע"`) is a structurally different Grow format this integration does not support, and is rejected — never silently accepted as a one-time sale.

**What Grow does not send, confirmed directly by Grow:** refund and cancellation events are never sent through this webhook — record those manually on the sale, the same as any other refund in this app. Grow also does not retry a failed webhook delivery even once, and there is no webhook-only sandbox to test against before going live.

**Because Grow never retries:** every inbound delivery is durably recorded (a `webhook_events` row: received → processed/duplicate/failed) *before* Sale creation is attempted, so a delivery is never silently lost even if something fails partway through. A delivery that fails after being durably received (e.g. a transient database error) stays visible in the connection's activity view with a safe **"try again"** action; a delivery that was simply malformed or represents an unsupported transaction type is not retryable (there is nothing safe to retry it with — see the module docstring on `app/models/webhook_event.py`) and should instead be re-entered via **CSV import**, which remains the general-purpose fallback for any transaction Grow ever misses.

**Source verification:** Grow has no signing capability, so the connecting request's source IP is the only application-layer defense, enforced in production via `GROW_WEBHOOK_ALLOWED_IPS` (see `.env.example` and `app/core/client_ip.py` for exactly which header is trusted and why, verified against Vercel's own documentation during implementation). The connection's own unique, unguessable URL is an additional possession barrier, but is explicitly **not** described anywhere in this codebase as cryptographic authentication — it is a URL, not a signature.

**Automatic customer documents (Grow's "Invoice creation" webhook):** Grow can also automatically generate the customer's tax invoice/receipt and notify this app of it — a *separate* webhook delivery, documented verbatim at [developers.grow.business/docs/webhooks](https://developers.grow.business/docs/webhooks):

```json
{"transactionCode": "ABCD1234", "invoiceNumber": "20", "invoiceUrl": "https://secure.meshulam.co.il"}
```

Both webhooks are sent to the **same connection URL** — the adapter discriminates by validated shape (`invoiceNumber`/`invoiceUrl` present → invoice event; never parsed as a payment) and never assumes delivery order: if the invoice arrives after its payment, the document is attached immediately; if it arrives first, it's durably queued (`provider_document_events` table) and linked the moment the matching payment sale is created. Duplicate invoice deliveries are idempotent by `(connection_id, transactionCode)` and never create a second row. **To enable this, ask Grow support to turn on both the relevant transaction webhook *and* "Invoice creation" for the same connection URL** — with only the transaction webhook enabled, sales are still recorded automatically, but no document is attached automatically. See "Automatic provider documents" below for the full status model.

**No synthetic documents:** the invoice URL is only ever a validated HTTPS link to Grow's own hosted document — the backend never fetches it (SSRF-safe), and the frontend renders it as a plain external link (`target="_blank" rel="noopener noreferrer"`), never as an inline image. Production keeps `DOCUMENT_PROVIDER=disabled` — this app never generates a document of its own — and never invents a `DEMO-*` reference for a Grow sale.

**Verification status:** payment ingestion has been structurally verified against Grow's own published payload examples (used verbatim as test fixtures — see `backend/tests/fixtures/grow_payloads.py`) and a full automated test suite, but is **not** considered live-verified until a real Grow account sends it a real transaction. The invoice-webhook document sync described above is newly implemented and structurally tested (both delivery orders, duplicates, cross-business/cross-connection correlation, invalid URLs) but has **not** received a real Grow invoice webhook — do not treat it as live-verified until one arrives. See the deployment notes for the exact remaining step.

### Cardcom connection (per-terminal webhook + server-to-server verification)

A real, production integration with [Cardcom](https://cardcom.solutions/) — the account's standard **LowProfile** webhook, confirmed directly against Cardcom's own documentation ([JSON API](https://cardcomapi.zendesk.com/hc/he/articles/25264402497426), [webhooks](https://support.cardcom.solutions/hc/he/articles/27875111757970), [API reference](https://cardcomapi.zendesk.com/hc/he/articles/26985443818514)). This is a **completely separate integration from Grow** — its own adapter ([`app/services/ingestion/cardcom_provider.py`](backend/app/services/ingestion/cardcom_provider.py)), its own connection type, its own encrypted credential storage, and its own status mapping. Nothing about the Grow integration was changed or weakened to add this.

**Why Cardcom is architecturally different from Grow:** Grow has no signing capability at all, so its connecting source IP is the *only* application-layer defense. Cardcom's own documentation instead mandates that a webhook payload is never trusted directly — the receiver must call Cardcom's own `LowProfile/GetLpResult` API server-to-server and treat **that response**, not the webhook body, as the source of truth. That server-to-server call is this integration's real authentication; the source-IP allowlist and the connection's own unguessable URL are defense-in-depth on top of it, not a substitute for it.

**How a business owner connects a Cardcom terminal:**

1. Open **Data Import** (`/imports`) and, in the **Cardcom connection** panel, add a connection — give it a name, the terminal number, and that terminal's API name and API password (from your Cardcom account's terminal settings). One business can connect multiple terminals, each with its own connection.
2. Cardcom's API name/password are encrypted at rest (`CARDCOM_CREDENTIAL_ENCRYPTION_KEY`, a dedicated Fernet key — never reused from any other secret) in a dedicated `cardcom_credentials` table, never stored in plaintext, never sent to the frontend again after the connection is created, and never logged.
3. Copy the connection's unique webhook URL (the **copy webhook URL** button) and paste it into that terminal's webhook field in Cardcom's own dashboard.
4. The connection shows **"waiting for first transaction"** until Cardcom actually sends one and it verifies successfully — it is never described as verified or active before that happens.

Only the business **owner** can create, enable/disable, delete, or rotate a Cardcom connection. There is no signing secret shown for Cardcom either — Cardcom's own documentation does not define a webhook signature scheme, so none is invented; the server-to-server verification call is the real trust boundary, not a secret in the payload.

**Supported operations:** `ChargeOnly`, `ChargeAndCreateToken`, and `Do3DSAndSubmit` — the LowProfile operations that represent an actual charge attempt. `CreateTokenOnly` (no charge occurred) and `SuspendedDeal` are explicitly not treated as sales. `CoinId` `1` → ILS, `2` → USD.

**Declined payments:** confirmed directly by Cardcom's representative, Cardcom *can* send a webhook notification for a declined transaction. The adapter supports a verified decline response as a failed sale, visible in the connection activity and sales history, and **never** counted as revenue. A decline does not by itself create an Exception Center task because there is no owner action defined for it. A live test-account decline also confirmed that Cardcom may call the identifier `LowProfileCode` (including as a URL query parameter), so the receiver accepts both that name and API v11's `LowProfileId`, case-insensitively, before making the authoritative server-to-server check. In that live test, however, `GetLpResult` returned only nonzero top-level code `60000004`, with no transaction details from which a trusted amount could be built. The delivery therefore remains a visible verification failure and creates no sale; the exact declined-result retrieval contract must be confirmed with Cardcom before this path can be called complete. Whether Cardcom sends decline notifications is controlled by the terminal's own **"always report a transaction"** setting in Cardcom's dashboard.

**What Cardcom does not send an ingestible event for, in this integration:** refunds and cancellations are **not** implemented — Cardcom's documentation does not define an exact, unambiguous format for them that this integration could rely on, so none is guessed at. Record refunds manually on the sale, exactly as with any other provider. This is stated here and in the connection panel's own UI copy, not left implicit.

**Because Cardcom retries** (Cardcom redelivers an unacknowledged webhook up to 7 times over roughly 25 hours), every inbound delivery is durably recorded (a `webhook_events` row) as the very first action, before any verification call or Sale creation is attempted, and the endpoint always returns a prompt 2xx once the delivery is durably received — so a slow verification call can never turn into a Cardcom retry storm, and database-level idempotency (`UNIQUE(business_id, source_provider, external_id)`) makes any actual redelivery safe regardless. A delivery whose verification failed for a transient reason (e.g. a network error calling Cardcom) stays visible with a safe **"try again"** action that re-runs verification from scratch; a delivery that was rejected outright (wrong content type, malformed payload, source IP not on the allowlist, verification permanently failed) is recorded with status **rejected** and is not retryable — re-enter it via **CSV import** if it represents a real missed transaction.

**Source verification:** in production, the connecting request's source IP must be on `CARDCOM_WEBHOOK_ALLOWED_IPS` (see `.env.example` for the current official ranges — verify against Cardcom's own support docs before deploying, as Cardcom may update them) or the request is rejected before any verification call is even attempted; production refuses to start if this is unset. This is enforced in addition to, never instead of, the `GetLpResult` server-to-server verification.

**Automatic customer documents (`DocumentInfo`):** unlike Grow, Cardcom's document details arrive bundled in the *same* authenticated `GetLpResult` response used to verify the payment — no separate webhook, no ordering problem. A verified successful transaction whose response includes `DocumentInfo` (`ResponseCode == 0`) — or, per Cardcom's documented fallback, the duplicate fields on `TranzactionInfo` — has its `DocumentNumber`/`DocumentType` recorded and the sale marked issued immediately. Missing `DocumentInfo` on an otherwise-verified success is normal (Cardcom may still be generating it) and never blocks recording the sale — it's marked as automatically waiting instead (see below). A declined transaction never expects a document at all. **`DocumentUrl` is never read, stored, or shown** — Cardcom's own documentation marks that field "לא עובד" (doesn't work), in both places it appears in the response; this is a confirmed platform limitation, not an oversight, and there is currently no way to show a clickable Cardcom document link.

**No synthetic documents:** production keeps `DOCUMENT_PROVIDER=disabled` — this app never generates a document of its own — and never invents a `DEMO-*` reference for a Cardcom payment.

**Verification status:** successful Cardcom payment ingestion is live-verified end to end against Cardcom's test account: the provider callback reached production, `GetLpResult` verified it, and the resulting sale appeared in the product with the correct ILS amount and VAT. Callback retries, deletion of an ingested sale, and the alternate `LowProfileCode` callback name have also been observed live. The declined-payment callback reaches production and is durably recorded, but its `GetLpResult` behavior remains the documented limitation above. The automated suite covers both callback names and transports, successful and synthetic documented decline-result shapes, malformed payloads, IP allowlisting, verification failure/reprocessing, and duplicate delivery — now including `DocumentInfo` present/absent and the declined/no-document-expected case. The `DocumentInfo` path itself has **not** been confirmed against a real Cardcom test transaction that actually generates a document — Cardcom's test account must produce one to live-verify it.

### Automatic provider documents

The product goal: an owner should not need to upload a receipt after every sale. When Grow or Cardcom already generates the customer's tax invoice/receipt, this app links it automatically — manual upload (**Import historical document**, `/import-document?saleId=...`) remains only a fallback, for historical sales, cash/other sales with no provider integration, or the rare case where an automatic document genuinely never arrives.

**This app never generates a legal tax document itself.** It only receives and links a document Grow or Cardcom already produced. The `DocumentProvider` boundary (`app/services/documents/`) is a separate, still-mock-only extension point reserved for a future *licensed* invoicing integration — production keeps `DOCUMENT_PROVIDER=disabled`, and the two systems are wired to never collide: a sale already tracked by a real provider's document sync is never touched by the generic (mock) issuance path.

`Sale.document_status` distinguishes five states — see `app/models/sale.py`'s `DocumentStatus` docstring:

| Status | Meaning |
|---|---|
| `waiting_automatic` | A Grow/Cardcom sale whose provider document is expected but hasn't arrived yet — the normal state for a fresh sale. **Never** immediately shown in the Exception Center. |
| `issued` | A document is linked — automatically (provider) or via manual attachment. |
| `failed` | A genuine problem: the generic (mock) issuance attempt failed, **or** a `waiting_automatic` sale has sat unmatched past `DOCUMENT_MATCH_GRACE_PERIOD_HOURS` (default 24h, see `.env.example`) — a deterministic, query-time rule (`app/services/exception_center.py`), never an in-memory timer or background job, since the backend runs on Vercel serverless. |
| `pending` | No automatic document path at all (manual/CSV entry, or a provider with no document integration) — unchanged, pre-existing meaning. |
| `not_required` | No document is ever expected — e.g. a declined/failed transaction. |

Both the Exception Center and the Dashboard's "needs attention" count apply the exact same grace-period rule, so they can never disagree; the AI Assistant's "sales missing a document" tool applies it too.

**Why the grace period, and why 24 hours:** Grow's invoice webhook and Cardcom's document generation can both complete slightly after the payment itself — flagging a `waiting_automatic` sale the instant it's created would turn ordinary automatic operation into daily manual work, exactly what this feature exists to avoid. 24 hours comfortably covers a realistic delivery delay while still surfacing a genuine miss within one business day.

Every provider-document field is scoped by business *and* by the specific integration connection (never just by transaction id) — a Grow `transactionCode` can never be matched to a different business's sale, or to a different connection of the same business, even if the code happens to collide.

### CSV import format

Header row required, exactly these five columns:
```
date,customer,service,amount,currency
2026-09-01,Demo Fictional Customer,Consulting session,184.90,ILS
```
`date` is `YYYY-MM-DD`; `amount` must be a positive number; `currency` a 3-letter code. UTF-8 and UTF-8-with-BOM are both accepted transparently. Re-importing the same file is safe — a stable id is derived from the file's hash plus row number, so repeat rows are skipped as duplicates (reported in the confirmation summary) rather than re-created.

## Refunds and the Exception Center

Refunds are recorded explicitly via `POST /api/sales/{id}/refund` (no real payment provider sends a refund webhook in this demo) — omit `amount` for a full refund, or supply it for a partial one. A refund can never exceed a sale's net amount (`409` if it would), and refunding an already-fully-refunded sale again is a safe no-op, not a double deduction.

The **Exception Center** (`/exceptions`) replaces what used to be a receipt-to-expense reconciliation inbox — there's no more matching to review, because a sale's document is either issued automatically or imported explicitly onto a named sale. It shows one deduplicated list of actionable sales, filterable by reason:
- Successful sales whose document is still `pending` and needs an already-issued document attached.
- Sales whose document generation `failed`, or whose automatic provider document has not arrived after the grace period. Fresh sales waiting for a provider document are not tasks.
- Legacy sales marked `tax_treatment_needs_review`, where the VAT treatment needs a human decision.

An already-recorded full or partial refund does not create a permanent task, and a missing customer contact is normal for many provider transactions. The task count therefore reflects unique sales that currently need an action, even when a sale has more than one reason.

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

The assistant has a constrained general analytics layer in addition to the focused totals tools:

- `query_sales` filters and ranks individual transactions by date, gross amount, actual net revenue, VAT, processing fee, or refunded amount. It supports customer, service, payment-method, status, date, and currency filters and returns at most 20 rows per currency.
- `analyze_sales` calculates totals, averages, counts, and rankings grouped by customer, service, payment method, status, day, week, or month. This lets it answer new combinations of questions without adding one hard-coded function for every possible sentence.
- `compare_sales_periods` compares two explicit inclusive date ranges and calculates the percentage change in backend code rather than asking the language model to perform financial arithmetic.

Individual-sale questions and grouped questions are deliberately routed differently. For example, “איזו עסקה עשתה הכי הרבה כסף?” uses `query_sales` and ranks actual sale rows by gross amount; “איזה לקוח הכניס הכי הרבה?” uses `analyze_sales` grouped by customer. Every monetary ranking stays separate per currency because the system has no exchange-rate source and must never pretend that numeric amounts in ILS, USD, and EUR are directly comparable. Every question about current business data performs a fresh tool call even if the conversation history contains an older answer.

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
- **Exception Center** — one deduplicated list for pending or failed documents and sales needing a VAT decision, with filters and direct links to the appropriate action.
- **Import historical document** (secondary, reached from a sale's own row) — attach a photo of a previously issued receipt/invoice to that specific sale.
- **Data Import** — the Grow/Cardcom connection panels selected for this business during onboarding, plus CSV sales-export import with preview and explicit confirmation. Adding or removing a payment provider later is a platform-admin/support action and is enforced by the API as well as the UI. Removing a provider immediately disables its active webhook connections while retaining sales history and connection records for audit and possible later reactivation.
- **Platform administration** (`/admin`, DB-backed admin role only) — cross-business overview, payment-provider enablement, and exact-name-confirmed business deletion. The role is stored in `app_accounts.system_role`; frontend state or a matching email address cannot grant access.
- **Language switcher** (top right) — toggle between עברית and English at any time.
- Old routes (`/expenses`, `/add-expense`, `/upload-receipt`, `/reconciliation`) redirect to their new equivalents, so old bookmarks/links don't break.

## Verification performed

- `pytest` (backend, 575 tests) — including DB-backed platform-admin authorization, cross-business admin operations, per-business payment-provider approval and safe removal, business isolation, development-only integration gates, signed (demo-pay), source-IP-verified (Grow), and server-to-server-verified (Cardcom) webhook routing, the Grow and Cardcom payload adapters against each provider's own published examples, both Cardcom `LowProfileId` and `LowProfileCode` callback forms (body and query string), the durable webhook-event inbox (received/processed/duplicate/failed/rejected) and safe provider-aware reprocessing, encrypted Cardcom credential storage, persisted assistant conversations, general sales analytics and ranking, sale validation, VAT calculation, ingestion idempotency, CSV/document import, dashboard math, exception handling, security controls, and the complete Alembic migration chain. All passing.
- `npm test` (frontend, 157 tests), `tsc -b`, `oxlint`, `npm run build` — all passing. Coverage includes authentication and provider selection during onboarding, provider-filtered imports, platform-admin provider management, the Grow connection panel and the separate Cardcom connection panel (owner/manager/viewer visibility, copy/rotate/delete, activity including rejected events, safe reprocessing, absence of demo/test wording), persisted assistant conversations, CSV import, sales, Sale Details, dashboard, exception center, and historical-document import. `oxlint` currently reports pre-existing, non-blocking React warnings (none introduced by this work) and no errors.
- `npm audit --omit=dev` and `pip-audit` — both report no known vulnerabilities as of this change.
- **Grow integration is structurally verified** (Grow's own published payload examples as test fixtures, full automated suite, production-config fail-fast checks) but **not live-verified** — no real Grow account has sent it a real transaction. See "Grow connection" above for what remains.
- **Cardcom successful-payment ingestion is live-verified** against Cardcom's test account, including its production webhook, server-to-server verification, ILS/VAT mapping, display, idempotency, and deletion. Decline delivery is also live-confirmed, but Cardcom's test `GetLpResult` returned code `60000004` without trusted transaction details; that provider contract still needs Cardcom's confirmation before declined attempts can reliably become failed-sale records. See "Cardcom connection" above.
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

- **Add a third real payment/POS integration.** Grow and Cardcom are both implemented (see "Grow connection" and "Cardcom connection" above) as real providers through the `WEBHOOK_PROVIDERS` registry ([`app/services/ingestion/webhook_provider.py`](backend/app/services/ingestion/webhook_provider.py)), each with its own dedicated adapter rather than being forced into another provider's payload shape, since a real provider's authentication model and payload fields are its own. The durable webhook-event inbox, connection management, and `Sale`-creation logic are all provider-agnostic already and should not need to change for a third one.
- **Cardcom refund/cancellation ingestion**, if Cardcom's documentation later confirms an exact, unambiguous webhook format for it — not implemented today because no such confirmed format was available; see "Cardcom connection" above.
- **Add a real invoicing/tax-receipt provider — for this app's own document generation.** Grow and Cardcom's own customer documents are now received and linked automatically (see "Automatic provider documents" above); this item is a separate capability, for the case where *this app itself* would need to generate a document (e.g. a cash sale with no provider). `DocumentProvider` ([`app/services/documents/base.py`](backend/app/services/documents/base.py)) is the intended extension point — a real provider (e.g. an Israeli-compliant e-invoicing service) means implementing that interface and selecting it via configuration; `sale_service.finalize_new_sale` never changes. No such provider exists yet, and `MockDocumentProvider` never claims to be one.
- **A Grow/Cardcom `DocumentUrl`/invoice link expiring or a provider changing its shape** is not specially detected — the URL is stored and shown as-is (Grow) or never stored at all (Cardcom, per its own documented `DocumentUrl` limitation).
- **An owner-visible list of unmatched provider-document events with no sale yet** (a Grow invoice webhook that arrives for a transaction whose payment never comes) is durably stored (`provider_document_events`) but not currently surfaced anywhere in the UI — a real gap, not a silent one; see "Automatic provider documents" above.
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
