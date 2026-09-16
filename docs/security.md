# Security model and production checklist

## Controls implemented in the application

- Supabase sessions stay in `HttpOnly`, `SameSite=Lax`, production-only `Secure` cookies.
- State-changing browser requests require an exact allowed `Origin`.
- Every protected request resolves a verified membership and a `business_id`.
- Tenant-scoped SQLAlchemy sessions filter reads, updates and deletes, enforce ownership on writes, and reject raw SQL and bulk ORM inserts.
- Viewer accounts cannot mutate business data.
- Webhooks require a fresh timestamp and constant-time HMAC verification (demo-pay, development/test-only in production), enforce a streamed body limit, validate bounded fields and monetary consistency, and rely on a business-scoped database uniqueness constraint for idempotency.
- Grow's account-level webhook has no signing capability at all (Grow-confirmed) — production instead enforces Grow's published source-IP allowlist (`GROW_WEBHOOK_ALLOWED_IPS`, refuses to start if unset/invalid), the connection's own unguessable URL, and a bounded body/content-type check. Every delivery is durably recorded (a `webhook_events` inbox row) before Sale creation, since Grow never retries a failed delivery; a delivery that fails after durable receipt can be safely reprocessed by the business owner, and one that was never safely parseable is not retried automatically (the owner re-enters it via CSV import instead).
- Cardcom's webhook is never trusted on its own — per Cardcom's own documentation, the receiver must call Cardcom's `LowProfile/GetLpResult` API server-to-server with that connection's own (encrypted-at-rest, Fernet) API name/password and treat only that response as authoritative; an event is never marked verified unless that call actually succeeded. Production additionally enforces `CARDCOM_WEBHOOK_ALLOWED_IPS` (refuses to start if unset/invalid) as defense-in-depth, not a substitute for the server-to-server check. Every delivery is durably recorded (a `webhook_events` inbox row, `received` status) before the verification call is made, since Cardcom retries an unacknowledged delivery up to 7 times over ~25 hours and the endpoint must still return a prompt 2xx once durably received. A rejected delivery (bad content type, malformed payload, IP not allowed, or verification that failed outright) is recorded as `rejected`, distinct from a `failed` Sale-creation error, and is not retried automatically; a delivery whose verification failed for a transient reason (e.g. a network error) can be safely reprocessed by the business owner, which re-runs the `GetLpResult` call from scratch. Cardcom credentials are decrypted only in-process for that call and are never logged, returned by any API response, or present in the frontend.
- **Provider-supplied documents (Grow's "Invoice creation" webhook, Cardcom's `DocumentInfo`)** never trust a URL beyond validating scheme (HTTPS only) and length before storing it — the backend never fetches a provider document URL itself (no SSRF surface), and the frontend only ever renders it as a plain external link (`target="_blank" rel="noopener noreferrer"`), never as a fetched/embedded resource. Cardcom's own `DocumentUrl` field is documented as broken and is never read, stored, or shown at all, for either provider's response shape it appears in. A Grow invoice event durably queues in `provider_document_events` (its own `connection_id`-scoped table, same `BusinessOwned`/RLS isolation as every other tenant-scoped table) before any matching is attempted, and correlates to a sale only by `(connection_id, external_transaction_id)` — never by transaction id alone — so a document can never cross a business or a different connection of the same provider, even on an id collision. Idempotent by the same key: a duplicate invoice delivery is recognized before any write and never creates a second row.
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
- `GROW_WEBHOOK_ALLOWED_IPS` set to Grow's current published IP list (production refuses to start otherwise — this is the only application-layer defense for Grow, which has no signing capability).
- `CARDCOM_WEBHOOK_ALLOWED_IPS` set to Cardcom's current published IP ranges, and a dedicated `CARDCOM_CREDENTIAL_ENCRYPTION_KEY` (Fernet key, never reused from any other secret) used to encrypt each connection's Cardcom API name/password at rest (production refuses to start if either is unset or invalid).
- A private Supabase Storage bucket and a short signed-URL lifetime when using Supabase Storage.

Terminate TLS at a trusted proxy and configure its maximum request size, connection/time limits and trusted forwarded-header sources. Serve the React application with its own CSP; backend response headers do not configure the separate frontend host.

## Controls required before horizontal scaling

The current limiter is effective for one Uvicorn process. Multiple workers or instances require a shared Redis-backed limiter at the application or gateway layer. Configure the proxy so the application receives a trustworthy client address; never trust arbitrary forwarded headers from the public internet.

Grow's and Cardcom's source-IP checks both rely on the same shared helper (`app/core/client_ip.py`) and the same Vercel guarantee: `X-Forwarded-For`/`X-Vercel-Forwarded-For` are overwritten by Vercel's edge network itself, not forwarded from the client, "to prevent IP spoofing" (verified against Vercel's request-headers documentation during implementation). This guarantee does **not** hold if this project's Vercel account ever enables the Enterprise "Trusted Proxy" feature, which explicitly allows a custom `X-Forwarded-For` to pass through unmodified — if that is ever enabled, both the Grow and Cardcom IP allowlists must be re-verified or enforced at the Vercel Firewall/WAF layer instead. For Cardcom this is defense-in-depth on top of its own server-to-server verification, not the sole check as it is for Grow; a failure of this trust boundary alone cannot forge a Cardcom event, since `GetLpResult` would still have to succeed. Configuring an equivalent IP-allowlist rule at the Vercel Firewall (Project → Firewall → Custom Rules, scoped to `/api/webhooks/connections/*`) as defense-in-depth alongside the application-level check has not been done as part of this change and remains a manual dashboard step.

The backend database credential currently has privileged access and can bypass PostgreSQL RLS. ORM tenant guards are therefore the active isolation boundary. Before a public multi-instance deployment, create a least-privilege application database role and enforce tenant-aware database policies or an equivalent server-side connection policy. Test restoration from managed database, Auth and Storage backups.

Rotate any credential that appears in terminal output or a chat transcript, even when the file containing it is ignored by Git. Never place server secrets in a `VITE_*` variable.
