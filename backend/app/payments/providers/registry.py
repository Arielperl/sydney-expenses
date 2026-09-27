"""Which provider adapters may be used, per environment.

There are no real adapters yet, so ``build_default_registry`` returns an
empty registry. Test doubles must be registered explicitly and are refused
outright when the environment is production (fail closed).
"""

from app.payments.providers.base import PaymentProviderAdapter


class UnknownProviderError(Exception):
    pass


class ProviderNotAllowedError(Exception):
    pass


class PaymentProviderRegistry:
    def __init__(self, environment: str):
        if environment not in ("development", "production"):
            raise ValueError("Unknown environment")
        self._environment = environment
        self._adapters: dict[str, PaymentProviderAdapter] = {}

    def register(self, adapter: PaymentProviderAdapter) -> None:
        if not isinstance(adapter, PaymentProviderAdapter):
            raise TypeError("Adapter does not implement PaymentProviderAdapter")
        if getattr(adapter, "test_only", True) and self._environment == "production":
            raise ProviderNotAllowedError(f"{adapter.name} is a test-only provider and cannot be used in production")
        if adapter.name in self._adapters:
            raise ValueError(f"Provider {adapter.name} is already registered")
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> PaymentProviderAdapter:
        adapter = self._adapters.get(name)
        if adapter is None:
            raise UnknownProviderError(f"Payment provider {name!r} is not available")
        # Re-checked on every lookup, in case the environment was misconfigured after registration.
        if adapter.test_only and self._environment == "production":
            raise ProviderNotAllowedError(f"{name} cannot be used in production")
        return adapter

    def names(self) -> list[str]:
        return sorted(self._adapters)


def build_default_registry(environment: str) -> PaymentProviderRegistry:
    """No real provider has been integrated. See docs/payments-foundation.md."""
    return PaymentProviderRegistry(environment)
