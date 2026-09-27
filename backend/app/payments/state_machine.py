"""The payment and refund state machines.

Every status change in this module goes through ``transition()``. Nothing
assigns ``status`` directly, and the database has a CHECK constraint so an
out-of-vocabulary value can never be stored.

Payment lifecycle (arrows are the only allowed moves)::

    created ──► pending ◄──► requires_action
       │           │               │
       │           ▼               ▼
       ├──────► authorized ──► captured ──► partially_refunded ──► refunded
       │                                            └──────────────────┘ (more partial refunds stay here)
       └──► failed / cancelled / expired   (terminal; reachable from any pre-capture state)

``pending`` and ``requires_action`` are the same stage (a customer may be
asked for 3-D Secure and then return to processing), so moving between them
is lateral, not backward. Everything else only moves forward. ``failed``,
``cancelled``, ``expired`` and ``refunded`` are terminal.

Receiving the status a payment already has is an idempotent no-op, which is
what makes duplicate provider events harmless.
"""

import enum


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    PENDING = "pending"
    REQUIRES_ACTION = "requires_action"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


_PRE_CAPTURE_EXITS = {PaymentStatus.FAILED, PaymentStatus.CANCELLED, PaymentStatus.EXPIRED}

PAYMENT_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.CREATED: frozenset({
        PaymentStatus.PENDING, PaymentStatus.REQUIRES_ACTION, PaymentStatus.AUTHORIZED,
        PaymentStatus.CAPTURED, *_PRE_CAPTURE_EXITS,
    }),
    PaymentStatus.PENDING: frozenset({
        PaymentStatus.REQUIRES_ACTION, PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED, *_PRE_CAPTURE_EXITS,
    }),
    PaymentStatus.REQUIRES_ACTION: frozenset({
        PaymentStatus.PENDING, PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED, *_PRE_CAPTURE_EXITS,
    }),
    # An authorization can be captured, voided (cancelled), declined at capture, or lapse.
    PaymentStatus.AUTHORIZED: frozenset({PaymentStatus.CAPTURED, *_PRE_CAPTURE_EXITS}),
    PaymentStatus.CAPTURED: frozenset({PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED}),
    PaymentStatus.PARTIALLY_REFUNDED: frozenset({PaymentStatus.REFUNDED}),
    PaymentStatus.FAILED: frozenset(),
    PaymentStatus.CANCELLED: frozenset(),
    PaymentStatus.EXPIRED: frozenset(),
    PaymentStatus.REFUNDED: frozenset(),
}

TERMINAL_PAYMENT_STATUSES = frozenset(status for status, targets in PAYMENT_TRANSITIONS.items() if not targets)
CANCELLABLE_STATUSES = frozenset({
    PaymentStatus.CREATED, PaymentStatus.PENDING, PaymentStatus.REQUIRES_ACTION, PaymentStatus.AUTHORIZED,
})
REFUNDABLE_STATUSES = frozenset({PaymentStatus.CAPTURED, PaymentStatus.PARTIALLY_REFUNDED})
# Statuses that still "occupy" an external_reference: a new intent for the same
# reference would risk charging the customer twice.
OCCUPYING_STATUSES = frozenset(PaymentStatus) - {PaymentStatus.FAILED, PaymentStatus.CANCELLED, PaymentStatus.EXPIRED}

REFUND_TRANSITIONS: dict[RefundStatus, frozenset[RefundStatus]] = {
    RefundStatus.PENDING: frozenset({RefundStatus.SUCCEEDED, RefundStatus.FAILED}),
    RefundStatus.SUCCEEDED: frozenset(),
    RefundStatus.FAILED: frozenset(),
}


class InvalidTransitionError(Exception):
    def __init__(self, current: enum.Enum, target: enum.Enum):
        super().__init__(f"Transition {current.value} -> {target.value} is not allowed")
        self.current = current
        self.target = target


def check_payment_transition(current: PaymentStatus, target: PaymentStatus) -> bool:
    """True if the status changes, False for an idempotent repeat; raises if not allowed."""
    if current == target:
        return False
    if target not in PAYMENT_TRANSITIONS[current]:
        raise InvalidTransitionError(current, target)
    return True


def check_refund_transition(current: RefundStatus, target: RefundStatus) -> bool:
    if current == target:
        return False
    if target not in REFUND_TRANSITIONS[current]:
        raise InvalidTransitionError(current, target)
    return True
