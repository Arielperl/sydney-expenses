# Security model and production checklist

## Controls implemented in the application

- Supabase sessions stay in `HttpOnly`, `SameSite=Lax`, production-only `Secure` cookies.
- State-changing browser requests require an exact allowed `Origin`.
- Every protected request resolves a verified membership and a `business_id`.
- Tenant-scoped SQLAlchemy sessions filter reads, updates and deletes, enforce ownership on writes, and reject raw SQL and bulk ORM inserts.
- Viewer accounts cannot mutate business data.
- Webhooks require a fresh timestamp and constant-time HMAC verification, enforce a streamed body limit, validate bounded fields and monetary consistency, and rely on a business-scoped database uniqueness constraint for idempotency.
- CSV confirmation is HMAC-signed over the business, file hash, filename, exact rows and expiration time.
- Uploaded images use random server names, streamed byte limits, real image decoding, an explicit pixel limit and private storage or authenticated local delivery.
- Production disables API documentation and the demo simulator, validates HTTPS origins and Supabase configuration, rejects unexpected Host headers and sends baseline security headers.
- Authentication and paid AI endpoints have bounded, thread-safe in-process rate limits.

## Required production configuration

Set `APP_ENVIRONMENT=production`, keep `AUTH_REQUIRED=true`, and configure:

- `SUPABASE_URL` and a rotated `SUPABASE_SECRET_KEY`.
- `CORS_ALLOWED_ORIGINS` with only the exact HTTPS frontend origin(s).
- `ALLOWED_HOSTS` with only the public API hostname(s), never `*`.
- `CSV_PREVIEW_SIGNING_SECRET` with an independent cryptographically random value of at least 32 characters.
- A strong, independent `WEBHOOK_SIGNING_SECRET` when webhook ingestion is enabled.
- A private Supabase Storage bucket and a short signed-URL lifetime when using Supabase Storage.

Terminate TLS at a trusted proxy and configure its maximum request size, connection/time limits and trusted forwarded-header sources. Serve the React application with its own CSP; backend response headers do not configure the separate frontend host.

## Controls required before horizontal scaling

The current limiter is effective for one Uvicorn process. Multiple workers or instances require a shared Redis-backed limiter at the application or gateway layer. Configure the proxy so the application receives a trustworthy client address; never trust arbitrary forwarded headers from the public internet.

The backend database credential currently has privileged access and can bypass PostgreSQL RLS. ORM tenant guards are therefore the active isolation boundary. Before a public multi-instance deployment, create a least-privilege application database role and enforce tenant-aware database policies or an equivalent server-side connection policy. Test restoration from managed database, Auth and Storage backups.

Rotate any credential that appears in terminal output or a chat transcript, even when the file containing it is ignored by Git. Never place server secrets in a `VITE_*` variable.
