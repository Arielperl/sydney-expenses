class ExpenseNotFoundError(Exception):
    pass


class ExpenseNotEligibleError(Exception):
    """The expense exists but isn't in a state a document can be attached to
    (already has one, or is a manual/not_required entry)."""


class ReceiptNotFoundError(Exception):
    pass


class ReceiptNotAvailableError(Exception):
    """The receipt upload exists but is no longer pending (already
    confirmed, expired, or discarded) — it can never be attached again."""
