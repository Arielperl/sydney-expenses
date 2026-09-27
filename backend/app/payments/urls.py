"""Checkout URL trust checks (shared implementation in app.core.payment_safety).

A checkout URL is only ever *returned* to the customer's browser; the backend
never fetches it, so there is no server-side request to forge. What remains
is open-redirect/phishing risk, handled by accepting only https URLs on the
exact hosts the adapter declared, with no embedded credentials or odd ports.
"""

from app.core import payment_safety
from app.payments.errors import UntrustedCheckoutUrlError

MAX_URL_LENGTH = payment_safety.MAX_URL_LENGTH


def validate_checkout_url(url: str, allowed_hosts: frozenset[str]) -> str:
    return payment_safety.validate_checkout_url(url, allowed_hosts, UntrustedCheckoutUrlError)
