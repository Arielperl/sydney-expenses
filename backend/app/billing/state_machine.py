"""Subscription state machine.

    (plan chosen)
         │
         ├──── trial available ──► trialing ──(paid at trial end)──► active ◄──┐
         │                            │   │                         │   ▲     │
         │                            │   └──(charge failed)──► past_due ┘     │
         │                            │                          │  │         │
         │                  (no payment method at trial end)     │  │ (dunning exhausted)
         │                            ▼                          │  ▼         │
         └── trial already used ──► expired ──(checkout paid)────┼► canceled ─┘ (checkout paid)
                                                                 │
                            active ──(period ends after cancel / provider cancels)──► canceled

* ``expired``  — the trial ended without a paid subscription (or no trial was
  available). Resubscribing moves it to ``active``.
* ``canceled`` — a paid subscription ended. Resubscribing moves it to ``active``.
* ``past_due`` — a charge failed; the provider retries. Access continues for a
  short grace period (see ``access.py``).

``SYSTEM`` transitions (time-based sweeps) and ``PROVIDER`` transitions
(verified webhooks) use ``TRANSITIONS``. Superadmin overrides may additionally
use ``OVERRIDE_TRANSITIONS`` — always audited with a reason.
"""

import enum


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


S = SubscriptionStatus

TRANSITIONS: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    S.TRIALING: frozenset({S.ACTIVE, S.PAST_DUE, S.EXPIRED, S.CANCELED}),
    S.ACTIVE: frozenset({S.PAST_DUE, S.CANCELED}),
    S.PAST_DUE: frozenset({S.ACTIVE, S.CANCELED}),
    S.EXPIRED: frozenset({S.ACTIVE}),
    S.CANCELED: frozenset({S.ACTIVE}),
}

# Extra moves only a superadmin override may make (e.g. extending an expired
# trial, granting complimentary access). Never reachable from webhooks.
OVERRIDE_TRANSITIONS: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    S.TRIALING: frozenset(),
    S.ACTIVE: frozenset(),
    S.PAST_DUE: frozenset(),
    S.EXPIRED: frozenset({S.TRIALING}),
    S.CANCELED: frozenset({S.TRIALING}),
}

ACCESS_STATUSES = frozenset({S.TRIALING, S.ACTIVE, S.PAST_DUE})


class InvalidSubscriptionTransition(Exception):
    def __init__(self, current: SubscriptionStatus, target: SubscriptionStatus):
        super().__init__(f"Subscription cannot move from {current.value} to {target.value}")
        self.current = current
        self.target = target


def check_transition(current: SubscriptionStatus, target: SubscriptionStatus, *, override: bool = False) -> bool:
    """True if the status changes, False for a repeat; raises when not allowed."""
    if current == target:
        return False
    allowed = TRANSITIONS[current] | (OVERRIDE_TRANSITIONS[current] if override else frozenset())
    if target not in allowed:
        raise InvalidSubscriptionTransition(current, target)
    return True
