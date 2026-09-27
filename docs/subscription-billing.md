# Sydney subscription billing

How Sydney charges *businesses* for Sydney itself. This is a separate domain
from the payments a business collects from its own customers
(`docs/payments-foundation.md`): separate tables (`subscription_*`,
`billing_*` vs `payment_*`), webhook endpoint (`/api/billing/webhooks/{provider}`
vs `/api/webhooks/...`), credentials and authorization.

## Status

- **No billing provider is connected.** `BILLING_PROVIDER=none` (the default)
  means checkout answers 503 and the UI shows "online payment is coming soon".
  Nothing can be charged, and no code path records a successful charge except a
  verified provider `invoice.paid` webhook whose amount (excluding VAT) and
  currency match the plan price.
- **Lockout is off by default.** `BILLING_ENFORCEMENT_ENABLED=false`: plan limits
  (connections, AI questions) apply, but an expired trial is shown as a banner,
  not a lock. Production refuses to start with enforcement on and no provider.
- `local_test` provider: tests and local development only. It is refused in
  production at startup and at construction, and needs a 32+ character secret.

## Architecture

| Layer | Module |
| --- | --- |
| Plan catalog (single source of truth) | `backend/app/billing/plans.py` → seeded by migration `d7e8f9a0b1c2`; a test keeps both in sync |
| State machine | `backend/app/billing/state_machine.py` |
| Time-based access (grace periods, reminders) | `backend/app/billing/access.py` |
| Domain service (trial, plan change, checkout, cancel, webhooks, entitlements, overrides) | `backend/app/billing/service.py` |
| Provider boundary | `backend/app/billing/providers/` (`base.py` protocol, `registry.py`, `local_test.py`) |
| HTTP | `backend/app/billing/routes.py` (`/api/billing/*`, `/api/support/staff/billing/*`) |
| Lockout | `backend/app/billing/gating.py` + `protect_workspace` in `app/main.py` (402 `subscription_required`) |
| Frontend | `services/billingService.ts`, `lib/billing.ts`, `components/billing/*`, `pages/PricingPage.tsx`, `pages/PlanSelectionStep.tsx`, `pages/BillingPage.tsx`, `pages/support-portal/SubscriptionsPanel.tsx` |

## States

```
    (plan chosen)
         │
         ├──── trial available ──► trialing ──(paid at trial end)──► active ◄──┐
         │                            │   │                         │   ▲     │
         │                            │   └──(charge failed)──► past_due ┘     │
         │                  (no payment method at trial end)     │  │ (dunning exhausted)
         │                            ▼                          │  ▼         │
         └── trial already used ──► expired ──(checkout paid)────┼► canceled ─┘ (checkout paid)
                            active ──(period ends after cancel / provider cancels)──► canceled
```

Superadmin overrides may additionally move `expired`/`canceled` → `trialing`.

Grace periods (`access.py`): 3 days to confirm the first charge after the trial
(only when a payment method is on file), 3 days for a renewal to confirm, 7 days
of `past_due` before access ends. Reminders start 7 days before the trial ends.

## Entitlements

| | Starter | Business | Pro | Enforced where |
| --- | --- | --- | --- | --- |
| Price / month (excl. VAT) | ₪69 | ₪119 | ₪249 | catalog |
| Price / year (excl. VAT) | ₪690 | ₪1,190 | ₪2,490 | catalog |
| Sales connections | 1 | 3 | 10 | `POST /api/connections` (403 with details) |
| AI questions / billing month | 300 | 1,500 | 5,000 | `POST /api/assistant/chat` (429), atomic reservation, released if no answer |
| Members | 1 | 5 | 15 | enforced centrally; **not advertised** (see below) |
All plans receive the same support treatment. Subscription tier never changes
the ordering or visibility of a support request.
| Dashboard, sales, CSV import, Needs Attention, support | ✓ | ✓ | ✓ | — |

Downgrades that would exceed a limit are refused with the reason.

## Trial rules

- 30 days, no card, one per business (`business_subscriptions.business_id` is unique).
- Claims on the owner's email and the business number (SHA-256 hashes in
  `billing_trial_claims`) stop a new trial after deleting and recreating a
  business, changing owners or retrying onboarding. A claimed identity gets an
  `expired` subscription with a `trial_unavailable` event.
- Dates are stored as naive UTC and shown in the business timezone.

## Migration of existing businesses

Migration `d7e8f9a0b1c2` is additive (8 new tables, no changes to existing
rows). Every existing business with at least one member, except the legacy
placeholder, gets a fresh 30-day trial from the migration time on Business
(or Pro if it already has more than 3 connections), an audit event
`trial_granted_on_migration`, and trial claims. With enforcement off nobody is
locked out either way.

## Known gaps before real billing

1. Choose a provider and implement its adapter (`BillingProviderAdapter`):
   hosted checkout, webhook signature verification, cancel/resume, plan change,
   price references. Until then checkout, cancel/resume of *paid* subscriptions
   and paid plan changes are unavailable (503).
2. Invoices/receipts, VAT invoices and a billing history list come from the
   provider; none are generated by Sydney.
3. Member invitations do not exist, so member limits are enforced but hidden
   (`MEMBER_INVITATIONS_AVAILABLE = False`); flip it when invitations ship.
4. Plan names, taglines and features are served in Hebrew; the English UI shows
   them as served.
5. Enable `BILLING_ENFORCEMENT_ENABLED` only after a provider is live.
