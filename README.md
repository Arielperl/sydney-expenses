# Receiptly

Receiptly is a local-first, AI-ready receipt and expense manager with a provider-independent extraction interface and a deterministic mock provider. Upload a receipt image, review the extracted details in an editable, bilingual (Hebrew/English) confirmation form, and save the confirmed expense — or just add an expense manually. Built as a portfolio project demonstrating a clean, modular full-stack architecture.

**Note on naming:** the GitHub repository is `sydney-expenses` (its original working name); the product itself is **Receiptly**, and the backend service identifies itself as **Receiptly API**. These are intentionally distinct — the repo name is not being renamed.

**Note on AI:** receipt extraction supports three interchangeable providers behind the same `ReceiptExtractor` interface: `MockReceiptExtractor` (default — deterministic, synthetic, needs nothing), `LocalReceiptExtractor` (real Vision extraction that runs entirely on your machine via Tesseract OCR + a local Ollama model — no API key, no external network call, no per-request cost), and `OpenAIReceiptExtractor` (real Vision extraction via the OpenAI Responses API). Mock mode is what the automated test suite and the default local setup use. The local provider has been run for real against a live local Ollama + gemma3:12b + Tesseract stack in this environment (see "Verification performed"); the OpenAI provider has been verified with **mocked** responses only — no OpenAI API key was available here, so its real-world accuracy is not yet claimed. See "Receipt extraction: mock vs. local vs. real AI mode" below.

## Status

**Hardened MVP with two pluggable real-AI extraction providers and provider-independent receipt image storage.** The complete flow — manual expense entry, receipt upload, extraction (mock, local, or OpenAI), confirmation, image storage (local disk or private Supabase Storage), and dashboard reporting — runs end-to-end, in Hebrew (default) or English, with decimal-safe money handling and a real image-validated upload pipeline.

## Tech stack

**Frontend:** React, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Hook Form, Zod, Recharts, React Router, i18next / react-i18next, lucide-react

**Backend:** Python, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, SQLite or PostgreSQL (including Supabase), psycopg, Pillow, pytesseract (Tesseract OCR), Ollama (local LLM runtime, via its HTTP API), OpenAI Python SDK, pytest

**Frontend testing:** Vitest, React Testing Library, user-event, jsdom, MSW

## Project structure

```
receiptly/  (repository: sydney-expenses)
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
│   │   ├── api/routes/   REST endpoints
│   │   ├── models/       SQLAlchemy ORM models (Expense, ReceiptUpload)
│   │   ├── schemas/       Pydantic request/response models (Decimal money)
│   │   ├── services/extraction/  ReceiptExtractor interface, mock + local (Ollama/Tesseract) + OpenAI providers, plus preprocessing/OCR-selection/receipt_parser/merge for local mode
│   │   ├── services/storage/     ReceiptStorage interface, local-disk + Supabase Storage providers
│   │   ├── services/      Business logic (uploads, dashboard, receipt lifecycle)
│   │   ├── repositories/  Database access layer
│   │   └── database.py
│   ├── alembic/          Database migrations (the sole source of schema truth)
│   ├── scripts/          cleanup_uploads.py — expires stale pending uploads
│   ├── evaluation/        Manual accuracy-evaluation CLI (see its own README)
│   ├── tests/            pytest suite
│   └── uploads/          Locally stored receipt images when STORAGE_PROVIDER=local (gitignored)
├── .env.example
└── .gitignore
```

## How it works

1. Upload a receipt image (or skip straight to a manual entry).
2. The backend streams the upload to disk in bounded chunks (rejecting it immediately if it exceeds the configured size limit) and verifies the actual image bytes with Pillow — a spoofed content type or corrupted file is rejected regardless of what the browser claimed. The original filename is never trusted; the stored filename is always server-generated from the verified format.
3. The upload is tracked as a `ReceiptUpload` row (`pending` → `confirmed`/`expired`/`failed`), not just a bare file. The configured extractor (mock, local, or OpenAI) derives structured data from the image (business name, amount, VAT, category, date, a quality score) and never invents a value it isn't confident about; missing or contradictory fields (e.g. VAT greater than the total) are left blank with a warning code instead (translated on the frontend).
4. The extracted data pre-fills an editable, translated confirmation form. Nothing is saved until you review and confirm it.
5. Confirming atomically claims the pending upload and creates the expense in one transaction — attempting to confirm the same upload twice returns a clear conflict instead of creating a duplicate expense.
6. The expense appears immediately in the expense list and dashboard.

The extraction logic sits behind a `ReceiptExtractor` interface ([base.py](backend/app/services/extraction/base.py)), so a real Vision AI provider can be swapped in later without touching any route or form code.

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

1. Install and start Ollama, then pull a vision-capable model (tested with `gemma3:12b`, ~8 GB on disk):
   ```bash
   brew install ollama        # or see ollama.com for other platforms
   ollama serve                # leave running in its own terminal, or run as a background service
   ollama pull gemma3:12b
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
   OLLAMA_RECEIPT_MODEL=gemma3:12b
   OLLAMA_TIMEOUT_SECONDS=120   # a 12B local model on a laptop is much slower than a hosted API
   OLLAMA_MAX_RETRIES=2
   TESSERACT_LANGUAGES=heb+eng
   ```
4. Restart the backend. The Upload Receipt page shows "Local extraction active — your data stays on this computer" whenever the backend reports `local` mode.

**Resource cost, not API cost:** there's no per-request bill, but a 12B model resident in memory uses several GB of RAM and meaningfully more CPU/GPU and electricity than the mock provider while it's generating — expect real wall-clock latency (tens of seconds per receipt on a laptop) rather than an instant response.

**If Ollama isn't running or the model isn't pulled**, extraction fails gracefully per receipt — upload and manual entry still work. The Upload Receipt page also proactively checks reachability (via `GET /api/system/capabilities`) and shows a specific "Ollama isn't running" message before you even try uploading, rather than waiting for a failed request.

**If Tesseract fails** (missing binary, missing language data, or any OCR error), extraction continues using the image alone — the vision model can often still read the receipt without OCR assistance — with a warning noting OCR was unavailable.

#### Preprocessing, deterministic parsing, and the merge policy

A real, narrow (330×736px) Hebrew receipt photo uploaded through the app exposed a serious accuracy problem: confidence displayed as 0%, the total showed as 0 instead of ~60.50 ILS, VAT was missing, and the date silently defaulted to today's date instead of staying blank. Diagnosing it end-to-end (original image → OCR output → model prompt → sanitizer → frontend form) found several compounding root causes, each now fixed:

1. **Preprocessing scaled off the wrong dimension.** The old code picked a target size from `max(width, height)` — for a typical receipt photo, that's the *height*, which is already large, so the *width* (the dimension that actually determines how many pixels each character stroke gets) barely grew. The 330px-wide receipt above only reached ~359px wide. [`image_preprocessing.py`](backend/app/services/extraction/image_preprocessing.py) now scales primarily off the width, targeting ~1400px for narrow receipts, with EXIF orientation correction and hard caps on both max dimension (4000px) and total pixel count (15M px) so an unusually large upload can't be upscaled further or consume unbounded memory. Three variants are generated (`enhanced`: grayscale + autocontrast + mild sharpen; `denoised`: adds a light median filter; `threshold`: Otsu binarization) — binarization in particular is offered only as one candidate, never the default, since it can destroy thin Hebrew strokes.
2. **A single OCR pass was trusted blindly.** [`ocr_selection.py`](backend/app/services/extraction/ocr_selection.py) now runs a small, bounded matrix of (preprocessing variant, Tesseract page-segmentation mode) combinations — 5 total, never more — and scores each by a documented heuristic (known Hebrew/English receipt keywords, money-shaped number patterns, a noise penalty) to pick the best single text to send to the model. Only the winning text is ever included in the prompt, so the model never sees the same receipt lines repeated across several OCR attempts.
3. **The vision model was trusted to reliably read obvious, structured values, and it wasn't — even when the correct text was sitting in the OCR output in plain sight.** [`receipt_parser.py`](backend/app/services/extraction/receipt_parser.py) now deterministically extracts receipt number, date, total, VAT, and currency candidates from the OCR text via regex, each tagged with a confidence tier (high/medium/low) and internal-only evidence (never exposed via the API or logged). It understands common Hebrew label variants (`סה"כ לתשלום`, `סה"כ`, `שולם`, `מע"מ` — including the trailing מ Tesseract frequently drops), decimal commas, currency symbols, and explicitly excludes item-price lines (detected by shape: a small quantity digit alongside two money-shaped amounts, not a fixed column layout) and change/cash-tendered lines from ever being read as the total. When OCR only weakly labels the true total line (common on a noisy photo), a same-value amount repeated elsewhere in the receipt is used as a lower-confidence fallback rather than nothing at all. The same OCR text is parsed multiple times across the bounded OCR attempts and cross-checked — a value two or more independent attempts agree on is upgraded a confidence tier, which recovered the correct date on the real receipt above even though the single best-scoring OCR attempt alone had misread one digit.
4. **[`merge.py`](backend/app/services/extraction/merge.py) combines the two.** A confident parser candidate fills a gap the model left null (flagged with a `*_from_ocr` warning); a genuine disagreement between the model and a confident parser match is never resolved silently — the more trustworthy source wins, but a `*_conflicting_sources` warning is always raised so the user is prompted to double-check it. A low-confidence parser guess (an unlabeled repeated number, a shaky merchant-name match) is never used to fill a model's null — "never invent a value" holds for the weakest evidence tier too. The parser's own high/medium-confidence candidates are also fed back into the model's prompt as explicit hints ("verify this against the image; report what the image actually shows if it disagrees"), and the vision call now includes both the original photo and the best-enhanced image, since a second, contrast-boosted view measurably helps the model reason about categories/context even on a hard photo.

**Honest result on the real receipt that exposed this bug:** receipt number (9999), total (60.50 ILS), VAT (9.22 ILS), and date (2013-09-30) are now all correctly extracted — all four were wrong or missing before this fix. Business name stayed blank, correctly: the photo's text there was never legible enough for either the model or the parser to read with any real confidence, and "extract only if sufficiently clear" means blank is the honest answer here, not a guess. This is one real receipt's result, not a general accuracy claim — a second, synthetic, higher-resolution Hebrew receipt (rendered via PIL, a different content/layout entirely) was also run through the full pipeline as an overfitting check: it correctly recovered the date via the same cross-attempt agreement mechanism, and correctly left the total/VAT blank rather than confidently reporting a wrong number when a font-rendering quirk in that particular synthetic image made those specific digits genuinely illegible to OCR — the safety property ("never confidently wrong") held in both cases, but real accuracy on Hebrew receipts in general has only ever been measured against this one real photo.

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
- The local provider has now been run against one real, photographed Hebrew receipt (see "Preprocessing, deterministic parsing, and the merge policy" above) — receipt number, total, VAT, and date all came back correct. That is one data point, not a general Hebrew-receipt accuracy claim; a synthetic, PIL-rendered receipt was also run as an overfitting check (PIL doesn't apply Hebrew bidi text shaping, and this particular font/rendering combination made some digits illegible even to Tesseract), and the pipeline correctly left the unreadable fields blank rather than guessing. A real, field-labeled accuracy evaluation across many real receipts (see "What's next") is still the only way to make a general accuracy claim.
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
- **Upload receipt** — drop an image, review the extracted fields (mock, local, or OpenAI, shown by the mode badge), confirm and save. The receipt image is stored locally or in Supabase Storage depending on `STORAGE_PROVIDER`, transparently to this flow.
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

## Security and reliability notes

- The server verifies the actual image bytes with Pillow — a JPEG/PNG/WebP claim in the request is never trusted on its own; a spoofed content type or corrupted file is rejected.
- Uploads are streamed to disk in bounded chunks and rejected as soon as they exceed the configured limit (default 10 MB via `MAX_UPLOAD_SIZE_BYTES`) — an oversized file is never fully buffered in memory, and any partial file is deleted.
- Stored filenames are always server-generated from the verified image format — the original filename/extension is discarded, which also rules out path traversal.
- Money (`amount`, `vat_amount`) is stored as SQL `Numeric(12, 2)` and handled as Python `Decimal` throughout — dashboard aggregation never uses binary floating-point arithmetic.
- Receipt uploads are tracked through an explicit lifecycle (`pending` → `confirmed`/`expired`/`failed`); confirmation is atomic, so replaying a confirmation request can never create a duplicate expense.
- Deleting an expense best-effort removes its receipt image (local file or Supabase object); a deletion failure is logged and never corrupts the database state or blocks the expense deletion itself.
- API responses never include the server's absolute file path or a permanent storage URL — only a relative `/uploads/...` path (local provider) or a freshly generated, time-limited signed URL (Supabase provider), regenerated on every response and never persisted.
- In `supabase` mode, the bucket is always private; the app never calls `get_public_url`, and `SUPABASE_SECRET_KEY` is read only by the backend process — it is never sent to the frontend, logged, or included in any API response or error message (verified in tests, including with a deliberately failing fake client whose error message contains the fake secret).
- Only a verified, already-uploaded file inside the configured uploads directory is ever sent to any extraction provider (local or OpenAI) — the client cannot supply an arbitrary filesystem path.
- CORS is restricted to the configured frontend origin (`http://localhost:5173` by default).
- No secrets are hardcoded; all configuration is read from environment variables via `.env` (see `.env.example`). The OpenAI API key is never logged, printed, or included in any API response.
- `/api/system/capabilities` reports only the provider name, mode (`mock`/`local`/`openai`, `demo`/`local`/`ai`), a `real_ai_enabled` boolean, and — in `local` mode only — non-sensitive `ollama_available`/`tesseract_available` booleans (computed with a 1-second-bounded local reachability check). Never a key, and never a filesystem path.
- Structured logs (provider, success/failure, duration, upload id, error category, missing fields) never include image bytes, base64 data, OCR/receipt text, card numbers, or full provider responses — verified explicitly in tests for the local provider (which is the one handling raw OCR text).

## What's next

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
