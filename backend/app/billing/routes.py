"""HTTP routes for subscription billing.

* ``/api/billing/plans``              — public plan catalog (before login)
* ``/api/billing/*``                  — business members view, owners manage
* ``/api/billing/webhooks/{provider}`` — the billing provider's webhook; its own
  endpoint, separate from customer-sale webhooks (``/api/webhooks/...``)
* ``/api/support/staff/billing/*``    — support/admin view, superadmin overrides

Money-moving and trial-starting routes are rate limited per user on top of
the global protections in ``protect_workspace``.
"""

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr
from sqlalchemy.orm import Session

from app.billing.plans import MEMBER_INVITATIONS_AVAILABLE, TRIAL_DAYS
from app.billing.providers.base import BillingProviderError, BillingWebhookVerificationError
from app.billing.providers.registry import BillingUnavailableError, build_billing_provider
from app.billing.service import BillingActor, BillingError, PlanLimitError, SubscriptionService, plan_catalog
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.database import SessionLocal, get_db

router = APIRouter(prefix="/billing", tags=["billing"])
staff_router = APIRouter(prefix="/support/staff/billing", tags=["billing admin"])

_billing_changes_by_user = RateLimiter(max_requests=20, window_seconds=60)
_overrides_by_user = RateLimiter(max_requests=30, window_seconds=60)

Interval = Literal["month", "year"]
PlanCode = Annotated[StrictStr, Field(min_length=2, max_length=32, pattern=r"^[a-z0-9_]+$")]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanSelection(_Request):
    plan_code: PlanCode
    interval: Interval = "month"


class OverrideRequest(_Request):
    action: Literal["extend_trial", "change_plan", "grant_access", "end_now"]
    reason: Annotated[StrictStr, Field(min_length=5, max_length=500)]
    days: StrictInt | None = None
    plan_code: PlanCode | None = None
    until: datetime | None = None


def _unscoped_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _provider():
    try:
        return build_billing_provider(get_settings())
    except BillingUnavailableError:
        return None


def service_for(db: Session) -> SubscriptionService:
    settings = get_settings()
    return SubscriptionService(db, provider=_provider(), frontend_origin=settings.cors_allowed_origins[0])


def get_billing_service(db: Session = Depends(get_db)) -> SubscriptionService:
    return service_for(db)


def get_staff_billing_service(db: Session = Depends(_unscoped_db)) -> SubscriptionService:
    return service_for(db)


def _actor(request: Request) -> BillingActor:
    user = getattr(request.state, "user", None)
    if not user:
        if get_settings().auth_required:
            raise HTTPException(401, "נדרשת התחברות")
        # Development without auth: the legacy single business, acting as its owner.
        from app.models.business import LEGACY_BUSINESS_ID

        return BillingActor(user_id="local-dev", business_id=LEGACY_BUSINESS_ID, business_role="owner",
                            email="local-dev@example.com")
    return BillingActor.from_request_user(user)


def _call(operation):
    try:
        return operation()
    except PlanLimitError as error:
        raise HTTPException(error.status_code, {"message": str(error), "limit": error.limit,
                                                "allowed": error.allowed, "current": error.current}) from None
    except BillingError as error:
        raise HTTPException(error.status_code, str(error)) from None
    except BillingProviderError:
        raise HTTPException(502, "ספק החיוב אינו זמין כרגע. לא בוצע חיוב. נסו שוב בעוד מספר דקות.") from None


def _summary(sub) -> dict:
    return {"status": sub.status.value, "plan_code": sub.plan_code, "billing_interval": sub.billing_interval,
            "cancel_at_period_end": sub.cancel_at_period_end, "pending_plan_code": sub.pending_plan_code}


# ------------------------------------------------------------------ public
@router.get("/plans")
def list_plans(db: Session = Depends(_unscoped_db)) -> dict:
    return {
        "plans": plan_catalog(db), "trial_days": TRIAL_DAYS, "currency": "ILS", "vat_rate": "0.18",
        "prices_exclude_vat": True, "member_limits_available": MEMBER_INVITATIONS_AVAILABLE,
    }


# ------------------------------------------------------------------ owners
@router.get("/subscription")
def get_subscription(request: Request, service: SubscriptionService = Depends(get_billing_service)) -> dict:
    overview = _call(lambda: service.overview(_actor(request)))
    # The UI locks the product only when the server does; otherwise it informs.
    overview["enforcement_enabled"] = get_settings().billing_enforcement_enabled
    return overview


@router.post("/trial", status_code=201)
def start_trial(body: PlanSelection, request: Request, service: SubscriptionService = Depends(get_billing_service)) -> dict:
    actor = _actor(request)
    _billing_changes_by_user.check(f"trial:{actor.user_id}")
    return _summary(_call(lambda: service.start_trial(actor, body.plan_code, body.interval)))


@router.post("/plan")
def change_plan(body: PlanSelection, request: Request, service: SubscriptionService = Depends(get_billing_service)) -> dict:
    actor = _actor(request)
    _billing_changes_by_user.check(f"plan:{actor.user_id}")
    return _summary(_call(lambda: service.change_plan(actor, body.plan_code, body.interval)))


@router.post("/checkout", status_code=201)
def create_checkout(body: PlanSelection, request: Request,
                    idempotency_key: str = Header(..., alias="Idempotency-Key"),
                    service: SubscriptionService = Depends(get_billing_service)) -> dict:
    actor = _actor(request)
    _billing_changes_by_user.check(f"checkout:{actor.user_id}")
    session = _call(lambda: service.create_checkout(actor, body.plan_code, body.interval, idempotency_key))
    return {"checkout_url": session.checkout_url, "status": session.status}


@router.post("/cancel")
def cancel_renewal(request: Request, service: SubscriptionService = Depends(get_billing_service)) -> dict:
    actor = _actor(request)
    _billing_changes_by_user.check(f"cancel:{actor.user_id}")
    return _summary(_call(lambda: service.set_cancel_at_period_end(actor, True)))


@router.post("/resume")
def resume_renewal(request: Request, service: SubscriptionService = Depends(get_billing_service)) -> dict:
    actor = _actor(request)
    _billing_changes_by_user.check(f"resume:{actor.user_id}")
    return _summary(_call(lambda: service.set_cancel_at_period_end(actor, False)))


# ---------------------------------------------------------------- webhook
@router.post("/webhooks/{provider}")
async def billing_webhook(provider: str, request: Request, db: Session = Depends(_unscoped_db)) -> dict:
    body = await request.body()
    if len(body) > 64 * 1024:
        raise HTTPException(413, "Payload too large")
    service = service_for(db)
    try:
        event = service.receive_webhook(provider, dict(request.headers), body)
    except BillingWebhookVerificationError:
        raise HTTPException(400, "Invalid webhook") from None
    except BillingError as error:
        raise HTTPException(error.status_code, "Unknown webhook") from None
    # A recorded-but-failed event is still acknowledged: it is retried from the inbox.
    return {"received": True, "status": event.status}


# ------------------------------------------------------------------ staff
@staff_router.get("/subscriptions")
def staff_subscriptions(request: Request, service: SubscriptionService = Depends(get_staff_billing_service)) -> list[dict]:
    return _call(lambda: service.admin_list(_actor(request)))


@staff_router.get("/subscriptions/{business_id}/events")
def staff_subscription_events(business_id: str, request: Request,
                              service: SubscriptionService = Depends(get_staff_billing_service)) -> list[dict]:
    events = _call(lambda: service.admin_events(_actor(request), business_id))
    return [{
        "sequence": e.sequence, "event_type": e.event_type, "from_status": e.from_status, "to_status": e.to_status,
        "from_plan": e.from_plan, "to_plan": e.to_plan, "source": e.source, "actor_user_id": e.actor_user_id,
        "reason": e.reason, "details": e.details, "created_at": e.created_at.isoformat(timespec="seconds") + "Z",
    } for e in events]


@staff_router.post("/subscriptions/{business_id}/overrides")
def staff_override(business_id: str, body: OverrideRequest, request: Request,
                   service: SubscriptionService = Depends(get_staff_billing_service)) -> dict:
    actor = _actor(request)
    _overrides_by_user.check(f"override:{actor.user_id}")
    until = body.until.astimezone(timezone.utc).replace(tzinfo=None) if body.until and body.until.tzinfo else body.until
    return _summary(_call(lambda: service.admin_override(
        actor, business_id, action=body.action, reason=body.reason, days=body.days, plan_code=body.plan_code, until=until)))
