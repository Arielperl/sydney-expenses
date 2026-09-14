# Business isolation — first release

New verified users create one Israeli business. Existing records are assigned by migration `b731b9a0c112` to business `00000000-0000-4000-8000-000000000001`. Membership is based on verified Supabase user IDs, never an email allowlist or a client-supplied owner ID. One business per user is enforced for this release.

## Database and rollout

The configured database is already PostgreSQL. Alembic upgrades must be run before restarting the updated backend. The migration preserves records and historical amounts, changes provider/external-ID uniqueness to include business ID, and enables RLS on application tables on PostgreSQL. There are no public API policies: browser-facing Supabase roles must not query these tables directly. The current backend connection uses a privileged database role; all request queries must therefore use the tenant-scoped `get_db` dependency.

An application-table snapshot (schema SQL, JSON records, baseline counts/totals) was stored outside Git under `~/.codex/backups/sydney-expenses/20260913-004804/`. It is not a full Supabase project/Auth/Storage backup. The installed pg_dump 16 cannot dump PostgreSQL 17. For deployment, configure full managed backups and verify a restoration separately.

Assign the preserved business to an existing verified user's Supabase UUID via an explicit administrative operation. Do not auto-claim it by email on login. The local rollout already assigned Ariel's verified UUID. New installations require their own verified owner assignment; an unclaimed legacy business remains inaccessible.

Downgrade is deliberately refused: removing business isolation from multi-business data is unsafe. Restore a verified pre-migration backup if rollback is required.

## Authorization

- Auth user views resolve database membership. The previous email allowlist has been removed.
- `get_db` creates a fresh tenant-scoped session; reads, aggregates, bulk deletes/updates, and ORM writes use central guards in `app/core/tenant.py`.
- `/uploads/` checks that the requested path belongs to a sale in the authenticated business.
- Owners/managers may mutate business records; viewers may read and ask the assistant but cannot mutate records.
- The assistant uses the same scoped session as sales and dashboards.
- Supabase signed document links remain bearer URLs until expiry; do not share them across businesses.

## Current boundaries / next steps

- Self-service setup currently supports Israel, ILS reporting, and Jerusalem time only. Existing per-sale tax treatments and rate snapshots remain intact. International tax rules, arbitrary reporting currencies and timezones are not yet implemented.
- Team invitation, role management UI, and multiple businesses per user are not yet available. Role enforcement and membership storage are implemented.
- Every business can create independent signed endpoints under `/api/webhooks/connections/{connection_id}`. Connection secrets are derived from a server-side master key, shown only at creation/rotation, and never stored in the database or returned by list APIs. Disabling a connection rejects new events; rotation immediately invalidates the previous secret. The legacy `/api/webhooks/payments` endpoint remains for compatibility and is assigned exclusively to the preserved business.
- `demo-pay` is still a fictional provider payload. A real POS integration requires a provider adapter and, where applicable, the provider's OAuth/API credential flow. No production deployment or automatic refund webhook was introduced.
- Customers/services are currently fields on a sale; they inherit its business ownership. There are no independent customer/service tables yet.
