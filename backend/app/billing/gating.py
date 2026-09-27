"""Request gating when ``BILLING_ENFORCEMENT_ENABLED`` is on.

Blocked businesses keep: authentication, billing, support tickets and their
business details — so they can always see why, pay, or ask for help. Their
data is never deleted or modified; normal product routes just answer 402 until
the subscription is active again.
"""

from datetime import datetime

from sqlalchemy import select

from app.billing.access import AccessDecision, evaluate_access
from app.billing.models import BusinessSubscription

EXEMPT_PREFIXES = (
    "/api/auth/",
    "/api/billing/",
    "/api/support/requests",
    "/api/businesses/current",
    "/api/health",
)


def is_exempt(path: str) -> bool:
    return path.startswith(EXEMPT_PREFIXES)


def access_for_business(business_id: str, now: datetime | None = None) -> AccessDecision:
    from app.database import SessionLocal

    with SessionLocal() as db:
        db.info["business_id"] = business_id
        sub = db.scalar(select(BusinessSubscription).where(BusinessSubscription.business_id == business_id))
        return evaluate_access(sub, now or datetime.utcnow())
