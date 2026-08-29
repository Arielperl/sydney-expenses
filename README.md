# Receiptly

Receiptly is a local-first, AI-ready receipt and expense manager with a provider-independent extraction interface and a deterministic mock provider. Upload a receipt image, review the extracted details in an editable, bilingual (Hebrew/English) confirmation form, and save the confirmed expense — or just add an expense manually. Built as a portfolio project demonstrating a clean, modular full-stack architecture.

**Note on naming:** the GitHub repository is `sydney-expenses` (its original working name); the product itself is **Receiptly**, and the backend service identifies itself as **Receiptly API**. These are intentionally distinct — the repo name is not being renamed.

**Note on AI:** receipt data extraction currently uses a `MockReceiptExtractor` — it does not call any real Vision/AI provider. It produces deterministic, clearly-synthetic data from the image bytes so the full upload → review → confirm → save pipeline works end-to-end without an API key. Connecting a real Vision provider behind the existing `ReceiptExtractor` interface is the next planned milestone.

## Status

**Hardened MVP.** The complete flow — manual expense entry, receipt upload, mock extraction, confirmation, storage, and dashboard reporting — runs end-to-end locally, in Hebrew (default) or English, with decimal-safe money handling and a real image-validated upload pipeline.

## Tech stack

**Frontend:** React, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Hook Form, Zod, Recharts, React Router, i18next / react-i18next

**Backend:** Python, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, SQLite, Pillow, pytest

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
│   │   ├── services/      Business logic (extraction, uploads, dashboard, receipt lifecycle)
│   │   ├── repositories/  Database access layer
│   │   └── database.py
│   ├── alembic/          Database migrations (the sole source of schema truth)
│   ├── scripts/          cleanup_uploads.py — expires stale pending uploads
│   ├── tests/            pytest suite
│   └── uploads/          Locally stored receipt images (gitignored)
├── .env.example
└── .gitignore
```

## How it works

1. Upload a receipt image (or skip straight to a manual entry).
2. The backend streams the upload to disk in bounded chunks (rejecting it immediately if it exceeds the configured size limit) and verifies the actual image bytes with Pillow — a spoofed content type or corrupted file is rejected regardless of what the browser claimed. The original filename is never trusted; the stored filename is always server-generated from the verified format.
3. The upload is tracked as a `ReceiptUpload` row (`pending` → `confirmed`/`expired`/`failed`), not just a bare file. A `MockReceiptExtractor` derives plausible structured data from the image bytes (business name, amount, VAT, category, date, confidence score) — deterministic per file, and it never invents a value it isn't confident about; missing fields are left blank with a warning code instead (translated on the frontend).
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
- **Upload receipt** — drop an image, review the mock-extracted fields, confirm and save.
- **Language switcher** (top right) — toggle between עברית and English at any time.

## Verification performed

- `pytest` (backend) — expense validation (including currency normalization, VAT-vs-amount, non-finite rejection), CRUD API, decimal-precision dashboard math (e.g. `0.10 + 0.20 + 0.30 == 0.60` exactly), mock extraction, real image-format verification (spoofed content type / corrupted file rejection), streamed oversized-upload rejection with no partial file left behind, and the full receipt-upload lifecycle (duplicate confirmation, missing/expired upload, orphan cleanup, expense deletion with safe file-cleanup-failure handling). All passing.
- A fresh temporary SQLite database built entirely via `alembic upgrade head` (no `create_all` involved), and an application import/startup check.
- `npm test` (Vitest + RTL + MSW, frontend) — Hebrew-default/English-switch/persistence, manual expense validation, upload loading/failure states, extracted-data confirmation, duplicate-confirmation conflict handling, expense edit/delete, dashboard empty/populated states, and Israel-timezone-safe local date handling. All passing.
- `tsc -b`, `oxlint`, `npm run build` — all clean.
- Manual end-to-end verification in-browser: Hebrew RTL layout, switch to English/LTR, manual add, receipt upload → mock extraction → confirm → save, duplicate-confirmation attempt, edit, delete with image cleanup, dashboard totals/percentage-change/category chart, and mobile viewport in both languages.

## Security and reliability notes

- The server verifies the actual image bytes with Pillow — a JPEG/PNG/WebP claim in the request is never trusted on its own; a spoofed content type or corrupted file is rejected.
- Uploads are streamed to disk in bounded chunks and rejected as soon as they exceed the configured limit (default 10 MB via `MAX_UPLOAD_SIZE_BYTES`) — an oversized file is never fully buffered in memory, and any partial file is deleted.
- Stored filenames are always server-generated from the verified image format — the original filename/extension is discarded, which also rules out path traversal.
- Money (`amount`, `vat_amount`) is stored as SQL `Numeric(12, 2)` and handled as Python `Decimal` throughout — dashboard aggregation never uses binary floating-point arithmetic.
- Receipt uploads are tracked through an explicit lifecycle (`pending` → `confirmed`/`expired`/`failed`); confirmation is atomic, so replaying a confirmation request can never create a duplicate expense.
- Deleting an expense best-effort removes its receipt image; a file-deletion failure is logged and never corrupts the database state.
- API responses never include the server's absolute file path, only a relative `/uploads/...` URL.
- CORS is restricted to the configured frontend origin (`http://localhost:5173` by default).
- No secrets are hardcoded; all configuration is read from environment variables via `.env` (see `.env.example`).

## What's next

- Connect a real Vision AI provider behind the existing `ReceiptExtractor` interface — the next planned milestone.
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

# Frontend
cd frontend
npm run dev       # dev server
npm test          # run Vitest suite once
npm run test:watch  # Vitest in watch mode
npm run build     # type-check + production build
npm run lint      # lint
```
