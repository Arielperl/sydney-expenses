"""Time-aware access decisions and billing-month windows.

Access is decided from the stored subscription *and the current time*, so an
expired trial is blocked immediately even if no background job has persisted
the ``expired`` status yet. Short grace periods only cover the gap where a
provider is expected to report an outcome.
"""

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.billing.models import BusinessSubscription
from app.billing.state_machine import SubscriptionStatus as S

PAYMENT_PROCESSING_GRACE = timedelta(days=3)  # trial over, payment method on file, first charge not yet reported
RENEWAL_GRACE = timedelta(days=3)             # paid period over, renewal not yet reported
PAST_DUE_GRACE = timedelta(days=7)            # a failed charge being retried by the provider
REMINDER_DAYS = 7


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str


def effective_status(sub: BusinessSubscription, now: datetime) -> S:
    """The status the subscription has *given the time*, before a sweep persists it."""
    status = S(sub.status)
    if status == S.TRIALING and sub.trial_ends_at and now >= sub.trial_ends_at:
        if sub.cancel_at_period_end or not sub.payment_method_on_file:
            return S.EXPIRED
        if now >= sub.trial_ends_at + PAYMENT_PROCESSING_GRACE:
            return S.EXPIRED
    if status == S.ACTIVE and sub.current_period_end and now >= sub.current_period_end:
        if sub.cancel_at_period_end or now >= sub.current_period_end + RENEWAL_GRACE:
            return S.CANCELED
    if status == S.PAST_DUE and sub.current_period_end and now >= sub.current_period_end + PAST_DUE_GRACE:
        return S.CANCELED
    return status


def evaluate_access(sub: BusinessSubscription | None, now: datetime) -> AccessDecision:
    if sub is None:
        return AccessDecision(False, "plan_required")
    status = effective_status(sub, now)
    if status == S.TRIALING:
        waiting = sub.trial_ends_at is not None and now >= sub.trial_ends_at
        return AccessDecision(True, "payment_processing" if waiting else "trialing")
    if status == S.ACTIVE:
        waiting = sub.current_period_end is not None and now >= sub.current_period_end
        return AccessDecision(True, "renewal_processing" if waiting else "active")
    if status == S.PAST_DUE:
        return AccessDecision(True, "past_due")
    if status == S.EXPIRED:
        return AccessDecision(False, "trial_expired" if sub.trial_started_at else "subscription_required")
    return AccessDecision(False, "canceled")


def add_months(moment: datetime, months: int) -> datetime:
    total = moment.month - 1 + months
    year, month = moment.year + total // 12, total % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def billing_month(anchor: datetime, now: datetime) -> tuple[datetime, datetime]:
    """The monthly window, anchored at ``anchor``, that contains ``now``.

    AI quotas are per billing *month* on annual plans too, so this is always a
    calendar-month step from the period (or trial) start.
    """
    if now < anchor:
        return anchor, add_months(anchor, 1)
    months = (now.year - anchor.year) * 12 + (now.month - anchor.month)
    start = add_months(anchor, months)
    if start > now:
        months -= 1
        start = add_months(anchor, months)
    end = add_months(anchor, months + 1)
    return start, end


def usage_anchor(sub: BusinessSubscription) -> datetime:
    status = S(sub.status)
    if status in (S.ACTIVE, S.PAST_DUE) and sub.current_period_start:
        return sub.current_period_start
    return sub.trial_started_at or sub.current_period_start or sub.created_at


def days_remaining(end: datetime | None, now: datetime) -> int | None:
    if end is None:
        return None
    seconds = (end - now).total_seconds()
    if seconds <= 0:
        return 0
    return int((seconds + 86_399) // 86_400)  # a partial day counts as a day
