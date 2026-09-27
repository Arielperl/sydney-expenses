"""Resolves the configured billing provider, failing closed.

``BILLING_PROVIDER=none`` (the production default today) means there is no
way to charge: checkout returns "billing unavailable" instead of pretending.
"""

from app.billing.providers.base import BillingProviderAdapter
from app.core.config import Settings


class BillingUnavailableError(Exception):
    """No billing provider is configured; nothing can be charged."""


def build_billing_provider(settings: Settings) -> BillingProviderAdapter | None:
    if settings.billing_provider == "none":
        return None
    if settings.billing_provider == "local_test":
        if settings.app_environment == "production":
            raise BillingUnavailableError("The local test billing provider is never available in production")
        from app.billing.providers.local_test import LocalTestBillingProvider

        return LocalTestBillingProvider(
            environment=settings.app_environment,
            webhook_secret=(settings.billing_local_test_webhook_secret or "").encode(),
        )
    raise BillingUnavailableError("Unknown billing provider")


def require_billing_provider(settings: Settings) -> BillingProviderAdapter:
    provider = build_billing_provider(settings)
    if provider is None:
        raise BillingUnavailableError("Online payment is not available yet")
    if provider.test_only and settings.app_environment == "production":
        raise BillingUnavailableError("A test billing provider cannot be used in production")
    return provider
