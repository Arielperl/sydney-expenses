# Receiptly

Receiptly is a local-first, AI-ready receipt and expense manager with a provider-independent extraction interface and a deterministic mock provider. Upload a receipt image, review the extracted details in an editable, bilingual (Hebrew/English) confirmation form, and save the confirmed expense — or just add an expense manually. Built as a portfolio project demonstrating a clean, modular full-stack architecture.

**Note on naming:** the GitHub repository is `sydney-expenses` (its original working name); the product itself is **Receiptly**, and the backend service identifies itself as **Receiptly API**. These are intentionally distinct — the repo name is not being renamed.

**Note on AI:** receipt extraction supports three interchangeable providers behind the same `ReceiptExtractor` interface: `MockReceiptExtractor` (default — deterministic, synthetic, needs nothing), `LocalReceiptExtractor` (real Vision extraction that runs entirely on your machine via Tesseract OCR + a local Ollama model — no API key, no external network call, no per-request cost), and `OpenAIReceiptExtractor` (real Vision extraction via the OpenAI Responses API). Mock mode is what the automated test suite and the default local setup use. The local provider has been run for real against a live local Ollama + gemma3:12b + Tesseract stack in this environment (see "Verification performed"); the OpenAI provider has been verified with **mocked** responses only — no OpenAI API key was available here, so its real-world accuracy is not yet claimed. See "Receipt extraction: mock vs. local vs. real AI mode" below.

## Status

**Hardened MVP with two pluggable real-AI extraction providers.** The complete flow — manual expense entry, receipt upload, extraction (mock, local, or OpenAI), confirmation, storage, and dashboard reporting — runs end-to-end locally, in Hebrew (default) or English, with decimal-safe money handling and a real image-validated upload pipeline.

## Tech stack

**Frontend:** React, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Hook Form, Zod, Recharts, React Router, i18next / react-i18next, lucide-react

**Backend:** Python, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, SQLite, Pillow, pytesseract (Tesseract OCR), Ollama (local LLM runtime, via its HTTP API), OpenAI Python SDK, pytest

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
│   │   ├── services/extraction/  ReceiptExtractor interface, mock + local (Ollama/Tesseract) + OpenAI providers
│   │   ├── services/      Business logic (uploads, dashboard, receipt lifecycle)
│   │   ├── repositories/  Database access layer
│   │   └── database.py
│   ├── alembic/          Database migrations (the sole source of schema truth)
│   ├── scripts/          cleanup_uploads.py — expires stale pending uploads
│   ├── evaluation/        Manual accuracy-evaluation CLI (see its own README)
│   ├── tests/            pytest suite
│   └── uploads/          Locally stored receipt images (gitignored)
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
- The local provider *was* run for real in this environment (see "Verification performed") against a synthetic, PIL-rendered test receipt — PIL doesn't apply Hebrew bidi text shaping, so the Hebrew in that specific test image renders character-reversed and is not representative of a real photographed receipt. The model correctly returned `null` rather than guessing on the fields it couldn't confidently read from that garbled image — exactly the intended safe behavior — but no accuracy claim is made from this one synthetic run.
- The quality score is a heuristic, not a calibrated accuracy measure.
- No per-provider rate limiting or cost cap beyond `OPENAI_MAX_RETRIES`/`OLLAMA_MAX_RETRIES`/`--max-files` in the evaluation tool.
- A model-generated free-text warning (as opposed to one of our own fixed warning codes) is shown to the user as-is, in whatever language the model produced it — it isn't translated.

**Troubleshooting:**
- *"Automatic extraction failed" every time in `openai` mode* → check `OPENAI_API_KEY` and `OPENAI_RECEIPT_MODEL` are set in `backend/.env` and the backend was restarted after editing it.
- *"Automatic extraction failed" every time in `local` mode, or the "Ollama isn't running" banner* → run `ollama serve` (or confirm the background service is running), then `ollama list` to confirm the model in `OLLAMA_RECEIPT_MODEL` is actually pulled (`ollama pull gemma3:12b` if not). Check `curl http://localhost:11434/api/version` responds.
- *Missing Tesseract, or "ocr_unavailable" warnings every time in `local` mode* → confirm `tesseract --version` works and `tesseract --list-langs` lists both `heb` and `eng`; extraction still works without OCR (it falls back to the image alone), just with reduced accuracy.
- *Badge stuck on "Demo mode" after switching provider* → the backend wasn't restarted, or `RECEIPT_EXTRACTOR_PROVIDER` isn't actually set in the environment the backend process reads from.
- *Timeouts* → raise `OPENAI_TIMEOUT_SECONDS` / `OLLAMA_TIMEOUT_SECONDS` (a local 12B model is much slower than a hosted API — 120s is a reasonable starting point); transient failures (timeouts, connection errors, rate limits, 5xx) are retried up to `OPENAI_MAX_RETRIES`/`OLLAMA_MAX_RETRIES` times with backoff, non-transient errors (bad request, auth) are not retried.

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
- **Upload receipt** — drop an image, review the extracted fields (mock, local, or OpenAI, shown by the mode badge), confirm and save.
- **Language switcher** (top right) — toggle between עברית and English at any time.

## Verification performed

- `pytest` (backend, 112 tests) — expense validation (including currency normalization, VAT-vs-amount, non-finite rejection), CRUD API, decimal-precision dashboard math (e.g. `0.10 + 0.20 + 0.30 == 0.60` exactly), mock extraction, **OpenAI extractor tests against a fake/mocked client** and **local (Ollama/Tesseract) extractor tests against a fake HTTP client and mocked OCR** (provider selection for all three modes, missing-key/missing-model config errors with no key leakage, valid-response mapping, nullable/partial fields, invalid category/date/currency/VAT-vs-total handling, bounded timeout and transient-error retries, non-transient errors not retried, malformed output, Hebrew/English OCR text reaching the model prompt, Tesseract-failure image-only fallback, extraction failure still allows manual entry, no expense saved during extraction itself, sensitive OCR content never appearing in logs), real image-format verification (spoofed content type / corrupted file rejection), streamed oversized-upload rejection with no partial file left behind, `/system/capabilities` reporting for all three modes, and the full receipt-upload lifecycle (duplicate confirmation, missing/expired upload, orphan cleanup, expense deletion with safe file-cleanup-failure handling). All passing. **No real OpenAI API call and no real Ollama/Tesseract call was made in any automated test** — every local- and OpenAI-provider test injects a fake HTTP client and/or mocked OCR function.
- A fresh temporary SQLite database built entirely via `alembic upgrade head` (no `create_all` involved), and an application import/startup check in mock mode, a safe missing-key check in `openai` mode, and a safe Ollama-unreachable check in `local` mode (pointed at a port nothing listens on) — all degrade to a clear extraction failure with manual entry still available, never a crash.
- The evaluation CLI (`evaluation/evaluate_receipts.py`) run in `--dry-run` mode against a real generated test image (mock provider, no network).
- **A real local smoke test was performed** — genuinely running Ollama 0.33.2 + `gemma3:12b` + Tesseract 5.5.3 (`heb`+`eng`) on this machine, with no OpenAI key configured and no OpenAI code path reachable:
  - Verified via direct API calls that Ollama's `/api/generate` supports both the `format` JSON-schema parameter (structured output) and image input (`images` field) with `gemma3:12b` before writing any integration code against it.
  - Ran `evaluation.evaluate_receipts --provider local` against a real, generated, non-sensitive Hebrew/English test receipt image — completed in ~17s with real local inference, produced valid structured output and a field-level accuracy report (low accuracy on this specific image, expected — see "Current limitations": PIL doesn't shape Hebrew text, so the rendered receipt itself has reversed Hebrew word order). Notably, the model correctly returned `null` rather than guessing on the fields it couldn't confidently read, exactly the required safe behavior.
  - Ran the same image through the actual running FastAPI app end-to-end in `local` mode (`RECEIPT_EXTRACTOR_PROVIDER=local`): `POST /api/receipts/upload` → real local extraction → reviewed/corrected the low-confidence fields → `POST /api/receipts/confirm` → expense saved (HTTP 201) → appeared via `GET /api/expenses`. `GET /api/system/capabilities` correctly reported `ollama_available: true` and `tesseract_available: true`. The server log was grepped for any OpenAI reference — none found, confirming no external network call occurred.
- `npm test` (Vitest + RTL + MSW, frontend, 40 tests) — Hebrew-default/English-switch/persistence, the globe-icon language switcher (open/select/checkmark/Escape/outside-click/arrow-keys), manual expense validation, upload loading/failure states, extracted-data confirmation (full and partial), duplicate-confirmation conflict handling, provider-failure manual fallback, mock/local/AI-mode badge labels in both languages, the Ollama-unavailable warning banner, expense edit/delete, dashboard empty/populated states, and Israel-timezone-safe local date handling. All passing.
- `tsc -b`, `oxlint`, `npm run build` — all clean.
- Manual end-to-end verification in-browser (mock mode for the UI walkthrough): Hebrew RTL layout, switch to English/LTR, manual add, receipt upload → extraction → confirm → save, duplicate-confirmation attempt, edit, delete with image cleanup, dashboard totals/percentage-change/category chart, and mobile viewport in both languages. The local-mode UI (badge, Ollama-unavailable banner) was verified live against the real local stack described above.
- **Not performed:** a live request to the real OpenAI API. The `openai` provider is verified end-to-end against a scripted fake client, not against the real service — do not treat it as field-verified until you've run it with a real key.

## Security and reliability notes

- The server verifies the actual image bytes with Pillow — a JPEG/PNG/WebP claim in the request is never trusted on its own; a spoofed content type or corrupted file is rejected.
- Uploads are streamed to disk in bounded chunks and rejected as soon as they exceed the configured limit (default 10 MB via `MAX_UPLOAD_SIZE_BYTES`) — an oversized file is never fully buffered in memory, and any partial file is deleted.
- Stored filenames are always server-generated from the verified image format — the original filename/extension is discarded, which also rules out path traversal.
- Money (`amount`, `vat_amount`) is stored as SQL `Numeric(12, 2)` and handled as Python `Decimal` throughout — dashboard aggregation never uses binary floating-point arithmetic.
- Receipt uploads are tracked through an explicit lifecycle (`pending` → `confirmed`/`expired`/`failed`); confirmation is atomic, so replaying a confirmation request can never create a duplicate expense.
- Deleting an expense best-effort removes its receipt image; a file-deletion failure is logged and never corrupts the database state.
- API responses never include the server's absolute file path, only a relative `/uploads/...` URL.
- Only a verified, already-uploaded file inside the configured uploads directory is ever sent to any extraction provider (local or OpenAI) — the client cannot supply an arbitrary filesystem path.
- CORS is restricted to the configured frontend origin (`http://localhost:5173` by default).
- No secrets are hardcoded; all configuration is read from environment variables via `.env` (see `.env.example`). The OpenAI API key is never logged, printed, or included in any API response.
- `/api/system/capabilities` reports only the provider name, mode (`mock`/`local`/`openai`, `demo`/`local`/`ai`), a `real_ai_enabled` boolean, and — in `local` mode only — non-sensitive `ollama_available`/`tesseract_available` booleans (computed with a 1-second-bounded local reachability check). Never a key, and never a filesystem path.
- Structured logs (provider, success/failure, duration, upload id, error category, missing fields) never include image bytes, base64 data, OCR/receipt text, card numbers, or full provider responses — verified explicitly in tests for the local provider (which is the one handling raw OCR text).

## What's next

- Run a real, field-labeled accuracy evaluation of both the local and OpenAI providers against a representative set of real (not synthetic) photographed receipts, and record actual numbers here — including a same-receipt-set comparison between the two.
- Add authentication if the app moves beyond single-user local use.
- Swap SQLite for PostgreSQL and local disk storage for cloud storage when deploying beyond a single machine (the repository/service layering was written to make this a config change, not a rewrite).
- Code-split the frontend bundle (currently a single ~270 KB gzipped chunk, flagged by the Vite build but not a functional issue at this scale).

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
