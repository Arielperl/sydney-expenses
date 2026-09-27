"""Currencies and minor-unit amounts.

Amounts are integers in the currency's smallest unit (agorot, cents), never
floats. Only a deliberate allowlist of ISO 4217 codes is accepted; each code
carries its official minor-unit exponent so conversions never guess. Add a
currency here only after confirming its exponent in ISO 4217 and that the
target provider supports it.
"""

from decimal import Decimal

# ISO 4217 alphabetic code -> number of minor-unit digits.
SUPPORTED_CURRENCIES: dict[str, int] = {
    "ILS": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CHF": 2,
    "CAD": 2,
    "AUD": 2,
    "JPY": 0,
    "JOD": 3,
}

# 10^12 minor units: far above any plausible single payment, far below
# BIGINT overflow. Providers impose their own (lower) limits.
MAX_AMOUNT_MINOR = 1_000_000_000_000


class CurrencyError(ValueError):
    pass


def normalize_currency(code: str) -> str:
    if not isinstance(code, str) or len(code) != 3 or not code.isascii() or not code.isalpha():
        raise CurrencyError("Currency must be a three-letter ISO 4217 code")
    upper = code.upper()
    if upper not in SUPPORTED_CURRENCIES:
        raise CurrencyError(f"Unsupported currency: {upper}")
    return upper


def validate_amount_minor(amount: int) -> int:
    # bool is a subclass of int; True must never mean "1 agora".
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise CurrencyError("Amount must be an integer number of minor units")
    if amount <= 0:
        raise CurrencyError("Amount must be positive")
    if amount > MAX_AMOUNT_MINOR:
        raise CurrencyError("Amount exceeds the maximum allowed")
    return amount


def to_major_units(amount_minor: int, currency: str) -> Decimal:
    """For display and for a future Sale bridge only — never for arithmetic on stored amounts."""
    exponent = SUPPORTED_CURRENCIES[normalize_currency(currency)]
    return Decimal(amount_minor).scaleb(-exponent)
