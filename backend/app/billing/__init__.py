"""Sydney's own SaaS subscription billing: plans, trials, subscriptions,
entitlements and usage.

This is a different domain from ``app.payments`` (a business collecting money
from *its* customers) and from the sales/connection ingestion code. It has its
own tables, webhook endpoint (``/api/billing/webhooks/...``), provider
configuration (``BILLING_*`` settings) and authorization rules.

No real billing provider is integrated yet. The trial, plan selection,
entitlement limits and administration work without one; checkout, renewals
and charging require a provider adapter (see docs/subscription-billing.md).
"""
