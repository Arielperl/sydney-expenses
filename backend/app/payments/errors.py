"""Domain errors. Messages are safe to show to an authorized caller and to log."""

from app.payments.permissions import PaymentPermissionError  # noqa: F401 - re-exported
from app.payments.providers.base import ProviderError, WebhookVerificationError  # noqa: F401 - re-exported
from app.payments.state_machine import InvalidTransitionError  # noqa: F401 - re-exported


class PaymentError(Exception):
    pass


class PaymentValidationError(PaymentError, ValueError):
    pass


class PaymentNotFoundError(PaymentError):
    pass


class IdempotencyConflictError(PaymentError):
    """The idempotency key was already used with different parameters."""


class DuplicateExternalReferenceError(PaymentError):
    """Another live payment intent already exists for this external reference."""


class PaymentStateError(PaymentError):
    """The operation is not possible in the payment's current status."""


class RefundLimitExceededError(PaymentError):
    pass


class ConcurrentUpdateError(PaymentError):
    """Another operation changed the payment first; re-read and retry."""


class UntrustedCheckoutUrlError(PaymentError):
    pass
