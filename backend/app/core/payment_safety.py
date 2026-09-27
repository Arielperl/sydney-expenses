"""Card-data and URL safety helpers shared by Sydney's payment-related code.

Used by subscription billing (``app.billing``) and by the inactive customer
payment foundation (``app.payments``), so neither has to import the other.

* ``contains_card_like_number`` — rejects free text holding anything shaped
  like a card number (13–19 digits, spaces/dashes allowed, Luhn-valid).
* ``safe_error_message`` — an exception message that is safe to persist.
* ``validate_checkout_url`` — only plain ``https`` URLs on hosts a provider
  adapter declared; the backend never fetches them, so there is no SSRF path.
"""


import re

# Field names that must never appear in any request schema of this module.
FORBIDDEN_FIELD_NAMES = frozenset({
    "card", "card_number", "cardnumber", "pan", "cc", "cc_number", "number",
    "cvv", "cvc", "cvv2", "cvc2", "security_code", "expiry", "exp_month", "exp_year",
    "expiration", "track", "track1", "track2", "magstripe", "pin",
    "iban", "account_number", "routing_number", "bank_account", "password",
})

_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def _luhn_valid(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def contains_card_like_number(text: str | None) -> bool:
    if not text:
        return False
    for match in _CANDIDATE.finditer(text):
        digits = re.sub(r"[ -]", "", match.group(0))
        if 13 <= len(digits) <= 19 and _luhn_valid(digits):
            return True
    return False


def safe_error_message(error: BaseException, limit: int = 300) -> str:
    """A diagnostic that is safe to persist: the exception type plus a
    truncated message with anything card-shaped masked."""
    message = f"{type(error).__name__}: {error}"
    message = _CANDIDATE.sub(lambda m: "[redacted]" if _luhn_valid(re.sub(r"[ -]", "", m.group(0))) else m.group(0), message)
    return message[:limit]


class UntrustedUrlError(ValueError):
    pass


MAX_URL_LENGTH = 2048


def validate_checkout_url(url: str, allowed_hosts: frozenset[str], error_cls: type[Exception] = UntrustedUrlError) -> str:
    from urllib.parse import urlsplit

    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        raise error_cls("Checkout URL is missing or too long")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url):
        raise error_cls("Checkout URL contains whitespace or control characters")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise error_cls("Checkout URL is malformed") from error
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        raise error_cls("Checkout URL must be plain https")
    if host not in {allowed.lower() for allowed in allowed_hosts}:
        raise error_cls("Checkout URL host is not trusted for this provider")
    return url
