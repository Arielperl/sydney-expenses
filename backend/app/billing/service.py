"""Subscription billing service.

Rules that matter for money and access:

* One subscription row per business, ever (DB unique). The trial starts once;
  retrying onboarding returns the existing subscription.
* A trial is also claimed by the owner's identity (email, and business number
  when given). A new business created by the same person — after deleting
  their account, for example — gets no second trial.
* Nothing is charged here. A charge exists only when a *verified* provider
  webhook says so (``invoice.paid``), and its amount must match the plan price.
* Every change writes an append-only ``SubscriptionEvent``; superadmin
  overrides must carry a reason (DB CHECK).
* Only business owners manage their subscription; members can view it.
"""

import hashlib
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.billing.access import billing_month, effective_status, usage_anchor
from app.billing.models import (
    BillingCheckoutSession,
    BillingTrialClaim,
    BillingUsageCounter,
    BillingWebhookEvent,
    BusinessSubscription,
    SubscriptionEvent,
    SubscriptionPlan,
    SubscriptionPlanPrice,
)
from app.billing.plans import INTERVALS, TRIAL_DAYS
from app.billing.providers.base import (
    BillingEvent,
    BillingEventType,
    BillingProviderAdapter,
    BillingWebhookVerificationError,
    CheckoutRequest,
)
from app.billing.state_machine import InvalidSubscriptionTransition, SubscriptionStatus as S, check_transition
from app.core.payment_safety import contains_card_like_number, safe_error_message, validate_checkout_url
from app.models.business import Business, BusinessMember
from app.models.integration_connection import IntegrationConnection

logger = logging.getLogger("app.billing")

IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:\-]{8,128}$")
MAX_WEBHOOK_ATTEMPTS = 10


# ------------------------------------------------------------------- errors
class BillingError(Exception):
    status_code = 400


class BillingPermissionError(BillingError):
    status_code = 403


class BillingNotFoundError(BillingError):
    status_code = 404


class BillingConflictError(BillingError):
    status_code = 409


class BillingValidationError(BillingError):
    status_code = 422


class PlanLimitError(BillingError):
    status_code = 409

    def __init__(self, message: str, *, limit: str, allowed: int, current: int):
        super().__init__(message)
        self.limit, self.allowed, self.current = limit, allowed, current


class QuotaExceededError(BillingError):
    status_code = 429


class BillingUnavailable(BillingError):
    status_code = 503


class BillingProviderResponseError(BillingError):
    """The provider answered with something Sydney will not use (e.g. an untrusted checkout URL)."""

    status_code = 502


# -------------------------------------------------------------------- actors
@dataclass(frozen=True)
class BillingActor:
    user_id: str
    business_id: str | None
    business_role: str | None
    system_role: str = "user"
    email: str | None = None

    @classmethod
    def from_request_user(cls, user: dict) -> "BillingActor":
        return cls(user_id=user["id"], business_id=user.get("business_id"), business_role=user.get("role"),
                   system_role=user.get("system_role") or "user", email=user.get("email"))


def _require_member(actor: BillingActor) -> str:
    if actor.system_role == "support" or not actor.business_id or actor.business_role not in ("owner", "manager", "viewer"):
        raise BillingPermissionError("אין הרשאה לצפות במנוי")
    return actor.business_id


def _require_owner(actor: BillingActor) -> str:
    business_id = _require_member(actor)
    if actor.business_role != "owner":
        raise BillingPermissionError("רק בעלי העסק יכולים לנהל את המנוי")
    return business_id


def _require_platform(actor: BillingActor, *, superadmin: bool) -> None:
    allowed = {"superadmin"} if superadmin else {"support", "admin", "superadmin"}
    if actor.system_role not in allowed:
        raise BillingPermissionError("אין הרשאה לפעולה זו")


def identity_hash(kind: str, value: str) -> str:
    normalized = re.sub(r"\s+", "", value).lower() if kind == "email" else re.sub(r"\D", "", value)
    return hashlib.sha256(f"sydney-trial:{kind}:{normalized}".encode()).hexdigest()


def plan_catalog(db: Session) -> list[dict]:
    plans = db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.active.is_(True)).order_by(SubscriptionPlan.sort_order)).all()
    prices = db.scalars(select(SubscriptionPlanPrice).where(SubscriptionPlanPrice.active.is_(True))).all()
    by_plan: dict[str, dict[str, int]] = {}
    for price in prices:
        by_plan.setdefault(price.plan_code, {})[price.interval] = price.amount_minor
    return [
        {
            "code": plan.code, "name": plan.name, "tagline": plan.tagline, "recommended": plan.recommended,
            "prices": by_plan.get(plan.code, {}), "max_connections": plan.max_connections,
            "max_members": plan.max_members, "ai_questions_per_month": plan.ai_questions_per_month,
            "features": list(plan.features),
        }
        for plan in plans
    ]


def _iso(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat(timespec="seconds") + "Z"


class SubscriptionService:
    def __init__(self, db: Session, *, provider: BillingProviderAdapter | None = None,
                 clock: Callable[[], datetime] = datetime.utcnow, frontend_origin: str = "http://localhost:5173"):
        self.db = db
        self.provider = provider
        self.clock = clock
        self.frontend_origin = frontend_origin.rstrip("/")

    # --------------------------------------------------------------- helpers
    def _plan(self, code: str) -> SubscriptionPlan:
        plan = self.db.get(SubscriptionPlan, code) if isinstance(code, str) else None
        if plan is None or not plan.active:
            raise BillingValidationError("מסלול לא קיים")
        return plan

    def _price(self, plan_code: str, interval: str) -> SubscriptionPlanPrice:
        if interval not in INTERVALS:
            raise BillingValidationError("מחזור חיוב לא תקין")
        price = self.db.scalar(select(SubscriptionPlanPrice).where(
            SubscriptionPlanPrice.plan_code == plan_code, SubscriptionPlanPrice.interval == interval,
            SubscriptionPlanPrice.active.is_(True)))
        if price is None:
            raise BillingValidationError("מחיר לא קיים למסלול ולמחזור שנבחרו")
        return price

    def subscription_for(self, business_id: str, *, lock: bool = False) -> BusinessSubscription | None:
        statement = select(BusinessSubscription).where(BusinessSubscription.business_id == business_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(statement)

    def _require_subscription(self, business_id: str, *, lock: bool = False) -> BusinessSubscription:
        sub = self.subscription_for(business_id, lock=lock)
        if sub is None:
            raise BillingNotFoundError("לעסק עדיין אין מנוי")
        return sub

    def _event(self, sub: BusinessSubscription, event_type: str, *, source: str, actor_user_id: str | None = None,
               from_status: S | None = None, to_status: S | None = None, from_plan: str | None = None,
               to_plan: str | None = None, reason: str | None = None, details: dict | None = None) -> None:
        stored = self.db.scalar(select(func.max(SubscriptionEvent.sequence)).where(SubscriptionEvent.subscription_id == sub.id)) or 0
        pending = sum(1 for obj in self.db.new if isinstance(obj, SubscriptionEvent) and obj.subscription_id == sub.id)
        self.db.add(SubscriptionEvent(
            business_id=sub.business_id, subscription_id=sub.id, sequence=stored + pending + 1, event_type=event_type,
            from_status=from_status.value if from_status else None, to_status=to_status.value if to_status else None,
            from_plan=from_plan, to_plan=to_plan, source=source, actor_user_id=actor_user_id, reason=reason,
            details=details or {}, created_at=self.clock(),
        ))

    def _move(self, sub: BusinessSubscription, target: S, *, source: str, event_type: str, override: bool = False,
              **event) -> bool:
        current = S(sub.status)
        if not check_transition(current, target, override=override):
            return False
        sub.status = target
        sub.updated_at = self.clock()
        self._event(sub, event_type, source=source, from_status=current, to_status=target, **event)
        logger.info("subscription %s: %s -> %s (%s)", sub.id, current.value, target.value, source)
        return True

    def _commit(self) -> None:
        try:
            self.db.commit()
        except (StaleDataError, IntegrityError) as error:
            self.db.rollback()
            raise BillingConflictError("המנוי עודכן במקביל. נסו שוב.") from error
        except Exception:
            self.db.rollback()
            raise

    def _count(self, model, business_id: str) -> int:
        return self.db.scalar(select(func.count()).select_from(model).where(model.business_id == business_id)) or 0

    # ------------------------------------------------------ time-based sync
    def sync_time_based_status(self, sub: BusinessSubscription) -> bool:
        """Persist what time has already decided (trial/period ended). Idempotent."""
        target = effective_status(sub, self.clock())
        current = S(sub.status)
        if target == current:
            return False
        note = {"trial_ends_at": _iso(sub.trial_ends_at), "current_period_end": _iso(sub.current_period_end)}
        changed = self._move(sub, target, source="system", event_type="lapsed", details=note)
        if changed and target in (S.EXPIRED, S.CANCELED):
            sub.ended_at = sub.ended_at or self.clock()
            if sub.pending_plan_code:
                sub.pending_plan_code = None
        return changed

    def sweep(self) -> int:
        """For a scheduled job: persist lapsed trials/periods for every business."""
        changed = 0
        for sub in self.db.scalars(select(BusinessSubscription).where(
                BusinessSubscription.status.in_([S.TRIALING, S.ACTIVE, S.PAST_DUE])).with_for_update()).all():
            changed += int(self.sync_time_based_status(sub))
        self._commit()
        return changed

    # ------------------------------------------------------------------ view
    def overview(self, actor: BillingActor) -> dict:
        from app.billing.access import days_remaining, evaluate_access

        business_id = _require_member(actor)
        sub = self.subscription_for(business_id, lock=True)
        if sub is not None and self.sync_time_based_status(sub):
            self._commit()
            sub = self.subscription_for(business_id)
        else:
            self.db.rollback()
            sub = self.subscription_for(business_id)
        now = self.clock()
        business = self.db.get(Business, business_id)
        plans = plan_catalog(self.db)
        result = {
            "business_timezone": business.timezone if business else "Asia/Jerusalem",
            "can_manage": actor.business_role == "owner",
            "billing_available": self.provider is not None,
            "trial_days": TRIAL_DAYS,
            "plans": plans,
            "subscription": None,
            "access": {"allowed": False, "reason": "plan_required"},
            "usage": None,
        }
        if sub is None:
            return result
        plan = self._plan(sub.plan_code)
        decision = evaluate_access(sub, now)
        window_start, window_end = billing_month(usage_anchor(sub), now)
        ai_used = self.db.scalar(select(BillingUsageCounter.used).where(
            BillingUsageCounter.business_id == business_id, BillingUsageCounter.metric == "ai_questions",
            BillingUsageCounter.period_start == window_start)) or 0
        open_checkout = self.db.scalar(select(BillingCheckoutSession).where(
            BillingCheckoutSession.business_id == business_id, BillingCheckoutSession.status == "open"
        ).order_by(BillingCheckoutSession.created_at.desc()))
        result["subscription"] = {
            "plan_code": sub.plan_code, "billing_interval": sub.billing_interval, "status": S(sub.status).value,
            "trial_started_at": _iso(sub.trial_started_at), "trial_ends_at": _iso(sub.trial_ends_at),
            "trial_days_remaining": days_remaining(sub.trial_ends_at, now) if S(sub.status) == S.TRIALING else None,
            "current_period_start": _iso(sub.current_period_start), "current_period_end": _iso(sub.current_period_end),
            "cancel_at_period_end": sub.cancel_at_period_end, "canceled_at": _iso(sub.canceled_at),
            "ended_at": _iso(sub.ended_at), "pending_plan_code": sub.pending_plan_code,
            "payment_method_on_file": sub.payment_method_on_file,
            "checkout_pending": open_checkout is not None,
        }
        result["access"] = {"allowed": decision.allowed, "reason": decision.reason}
        result["usage"] = {
            "ai_questions": {"used": ai_used, "limit": plan.ai_questions_per_month,
                             "period_start": _iso(window_start), "period_end": _iso(window_end)},
            "connections": {"used": self._count(IntegrationConnection, business_id), "limit": plan.max_connections},
            "members": {"used": self._count(BusinessMember, business_id), "limit": plan.max_members},
        }
        return result

    # ----------------------------------------------------------------- trial
    def start_trial(self, actor: BillingActor, plan_code: str, interval: str = "month") -> BusinessSubscription:
        business_id = _require_owner(actor)
        plan = self._plan(plan_code)
        self._price(plan.code, interval)
        existing = self.subscription_for(business_id)
        if existing is not None:
            return existing  # onboarding retried: never a second trial
        self._check_capacity(business_id, plan)
        business = self.db.get(Business, business_id)
        identities = []
        if actor.email:
            identities.append(("email", identity_hash("email", actor.email)))
        if business and business.business_number and re.sub(r"\D", "", business.business_number):
            identities.append(("business_number", identity_hash("business_number", business.business_number)))
        claimed = bool(identities) and self.db.scalar(
            select(func.count()).select_from(BillingTrialClaim).where(
                BillingTrialClaim.identity_hash.in_([h for _, h in identities]),
                BillingTrialClaim.business_id != business_id)) > 0
        now = self.clock()
        sub = BusinessSubscription(
            business_id=business_id, plan_code=plan.code, billing_interval=interval, created_by_user_id=actor.user_id,
            created_at=now, updated_at=now,
        )
        if claimed:
            sub.status = S.EXPIRED
        else:
            sub.status = S.TRIALING
            sub.trial_started_at = now
            sub.trial_ends_at = now + timedelta(days=TRIAL_DAYS)
            for kind, value in identities:
                self.db.add(BillingTrialClaim(identity_hash=value, identity_kind=kind, business_id=business_id, created_at=now))
        self.db.add(sub)
        try:
            self.db.flush()
        except IntegrityError:
            # A concurrent request for this business (or with the same identity) won the race.
            self.db.rollback()
            existing = self.subscription_for(business_id)
            if existing is not None:
                return existing
            raise BillingConflictError("בחירת המסלול נכשלה. נסו שוב.") from None
        if claimed:
            self._event(sub, "trial_unavailable", source="owner", actor_user_id=actor.user_id, to_status=S.EXPIRED,
                        to_plan=plan.code, details={"reason": "trial_already_used"})
        else:
            self._event(sub, "trial_started", source="owner", actor_user_id=actor.user_id, to_status=S.TRIALING,
                        to_plan=plan.code, details={"trial_ends_at": _iso(sub.trial_ends_at), "interval": interval})
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.subscription_for(business_id)
            if existing is not None:
                return existing
            raise
        return sub

    # ------------------------------------------------------------- plan change
    def _check_capacity(self, business_id: str, plan: SubscriptionPlan) -> None:
        connections = self._count(IntegrationConnection, business_id)
        if connections > plan.max_connections:
            raise PlanLimitError(f"במסלול {plan.name} אפשר עד {plan.max_connections} חיבורי מכירות. כרגע יש {connections}.",
                                 limit="connections", allowed=plan.max_connections, current=connections)
        members = self._count(BusinessMember, business_id)
        if members > plan.max_members:
            raise PlanLimitError(f"במסלול {plan.name} אפשר עד {plan.max_members} משתמשים. כרגע יש {members}.",
                                 limit="members", allowed=plan.max_members, current=members)

    def change_plan(self, actor: BillingActor, plan_code: str, interval: str) -> BusinessSubscription:
        business_id = _require_owner(actor)
        plan = self._plan(plan_code)
        price = self._price(plan.code, interval)
        sub = self._require_subscription(business_id, lock=True)
        self.sync_time_based_status(sub)
        if sub.plan_code == plan.code and sub.billing_interval == interval and not sub.pending_plan_code:
            self.db.rollback()
            return sub
        self._check_capacity(business_id, plan)
        status = S(sub.status)
        previous = sub.plan_code
        if status in (S.ACTIVE, S.PAST_DUE) and sub.provider_subscription_ref:
            if self.provider is None:
                self.db.rollback()
                raise BillingUnavailable("שינוי מסלול בתשלום אינו זמין כרגע")
            current_price = self._price(sub.plan_code, sub.billing_interval).amount_minor
            upgrade = interval == sub.billing_interval and price.amount_minor > current_price
            # Upgrades apply now at the provider (which prorates); everything else at period end.
            self.provider.change_plan(sub.provider_subscription_ref, plan_code=plan.code, interval=interval,
                                      provider_price_ref=price.provider_price_ref, at_period_end=not upgrade)
            if upgrade:
                self._event(sub, "plan_change_requested", source="owner", actor_user_id=actor.user_id,
                            from_plan=previous, to_plan=plan.code, details={"interval": interval})
            else:
                sub.pending_plan_code = plan.code
                self._event(sub, "plan_change_scheduled", source="owner", actor_user_id=actor.user_id,
                            from_plan=previous, to_plan=plan.code,
                            details={"interval": interval, "effective_at": _iso(sub.current_period_end)})
        else:
            # Trial or no paid subscription: nothing to charge, apply immediately.
            sub.plan_code = plan.code
            sub.billing_interval = interval
            sub.pending_plan_code = None
            sub.updated_at = self.clock()
            self._event(sub, "plan_changed", source="owner", actor_user_id=actor.user_id, from_plan=previous,
                        to_plan=plan.code, details={"interval": interval})
        self._commit()
        return sub

    # --------------------------------------------------------------- checkout
    def create_checkout(self, actor: BillingActor, plan_code: str, interval: str, idempotency_key: str) -> BillingCheckoutSession:
        business_id = _require_owner(actor)
        if not isinstance(idempotency_key, str) or not IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            raise BillingValidationError("מפתח בקשה לא תקין")
        if self.provider is None:
            raise BillingUnavailable("תשלום מקוון עדיין אינו זמין. אפשר להמשיך בתקופת הניסיון.")
        plan = self._plan(plan_code)
        price = self._price(plan.code, interval)
        existing = self.db.scalar(select(BillingCheckoutSession).where(
            BillingCheckoutSession.business_id == business_id, BillingCheckoutSession.idempotency_key == idempotency_key))
        if existing is not None:
            if existing.plan_code != plan.code or existing.interval != interval:
                raise BillingConflictError("מפתח הבקשה כבר שימש לבחירה אחרת")
            return existing
        sub = self._require_subscription(business_id, lock=True)
        self.sync_time_based_status(sub)
        status = S(sub.status)
        if status == S.ACTIVE and sub.payment_method_on_file and not sub.cancel_at_period_end:
            self.db.rollback()
            raise BillingConflictError("המנוי כבר פעיל")
        self._check_capacity(business_id, plan)
        now = self.clock()
        trial_end = sub.trial_ends_at if status == S.TRIALING and sub.trial_ends_at and sub.trial_ends_at > now else None
        request = CheckoutRequest(
            subscription_id=sub.id, business_id=business_id, plan_code=plan.code, interval=interval,
            provider_price_ref=price.provider_price_ref, trial_ends_at=trial_end, customer_ref=sub.provider_customer_ref,
            success_url=f"{self.frontend_origin}/billing?checkout=success",
            cancel_url=f"{self.frontend_origin}/billing?checkout=canceled",
            idempotency_key=f"{sub.id}:{idempotency_key}",
        )
        try:
            session = self.provider.create_checkout_session(request)
            url = validate_checkout_url(session.checkout_url, self.provider.allowed_checkout_hosts, BillingProviderResponseError)
        except Exception:
            self.db.rollback()
            raise
        # Older open sessions are superseded, so there is only ever one live checkout.
        for stale in self.db.scalars(select(BillingCheckoutSession).where(
                BillingCheckoutSession.business_id == business_id, BillingCheckoutSession.status == "open")).all():
            stale.status = "canceled"
        record = BillingCheckoutSession(
            business_id=business_id, subscription_id=sub.id, provider=self.provider.name,
            provider_session_ref=session.provider_session_ref, plan_code=plan.code, interval=interval, status="open",
            checkout_url=url, idempotency_key=idempotency_key, created_by_user_id=actor.user_id,
            expires_at=session.expires_at, created_at=now, updated_at=now,
        )
        self.db.add(record)
        self._event(sub, "checkout_started", source="owner", actor_user_id=actor.user_id, to_plan=plan.code,
                    details={"interval": interval, "during_trial": trial_end is not None})
        self._commit()
        return record

    # ------------------------------------------------------------ cancellation
    def set_cancel_at_period_end(self, actor: BillingActor, cancel: bool) -> BusinessSubscription:
        business_id = _require_owner(actor)
        sub = self._require_subscription(business_id, lock=True)
        self.sync_time_based_status(sub)
        status = S(sub.status)
        if status not in (S.TRIALING, S.ACTIVE, S.PAST_DUE):
            self.db.rollback()
            raise BillingConflictError("אין חידוש פעיל לבטל" if cancel else "המנוי כבר הסתיים")
        if sub.cancel_at_period_end == cancel:
            self.db.rollback()
            return sub
        if sub.provider_subscription_ref:
            if self.provider is None:
                self.db.rollback()
                raise BillingUnavailable("ניהול החידוש אינו זמין כרגע")
            try:
                self.provider.set_cancel_at_period_end(sub.provider_subscription_ref, cancel)
            except Exception:
                self.db.rollback()
                raise
        sub.cancel_at_period_end = cancel
        sub.canceled_at = self.clock() if cancel else None
        sub.updated_at = self.clock()
        effective = sub.trial_ends_at if status == S.TRIALING else sub.current_period_end
        self._event(sub, "cancel_scheduled" if cancel else "cancel_reverted", source="owner", actor_user_id=actor.user_id,
                    details={"effective_at": _iso(effective)})
        self._commit()
        return sub

    # ----------------------------------------------------------- entitlements
    def plan_for_business(self, business_id: str) -> SubscriptionPlan | None:
        sub = self.subscription_for(business_id)
        return self.db.get(SubscriptionPlan, sub.plan_code) if sub else None

    def ensure_connection_capacity(self, business_id: str) -> None:
        plan = self.plan_for_business(business_id)
        if plan is None:
            return  # no plan chosen yet: gating (when enforced) decides access
        current = self._count(IntegrationConnection, business_id)
        if current >= plan.max_connections:
            raise PlanLimitError(
                f"במסלול {plan.name} אפשר עד {plan.max_connections} חיבורי מכירות. כדי להוסיף חיבור, שדרגו את המסלול.",
                limit="connections", allowed=plan.max_connections, current=current)

    def ensure_member_capacity(self, business_id: str) -> None:
        plan = self.plan_for_business(business_id)
        if plan is None:
            return
        current = self._count(BusinessMember, business_id)
        if current >= plan.max_members:
            raise PlanLimitError(f"במסלול {plan.name} אפשר עד {plan.max_members} משתמשים.",
                                 limit="members", allowed=plan.max_members, current=current)

    def reserve_ai_question(self, business_id: str) -> str | None:
        """Atomically count one assistant question against this billing month.

        Returns the counter id (to release on failure), or None when the
        business has no plan yet. Commits immediately and independently.
        """
        sub = self.subscription_for(business_id)
        if sub is None:
            return None
        plan = self._plan(sub.plan_code)
        start, end = billing_month(usage_anchor(sub), self.clock())
        counter_id = self.db.scalar(select(BillingUsageCounter.id).where(
            BillingUsageCounter.business_id == business_id, BillingUsageCounter.metric == "ai_questions",
            BillingUsageCounter.period_start == start))
        if counter_id is None:
            counter = BillingUsageCounter(business_id=business_id, metric="ai_questions", period_start=start,
                                          period_end=end, used=0, updated_at=self.clock())
            self.db.add(counter)
            try:
                self.db.commit()
                counter_id = counter.id
            except IntegrityError:
                self.db.rollback()
                counter_id = self.db.scalar(select(BillingUsageCounter.id).where(
                    BillingUsageCounter.business_id == business_id, BillingUsageCounter.metric == "ai_questions",
                    BillingUsageCounter.period_start == start))
        result = self.db.execute(
            update(BillingUsageCounter)
            .where(BillingUsageCounter.id == counter_id, BillingUsageCounter.used < plan.ai_questions_per_month)
            .values(used=BillingUsageCounter.used + 1, updated_at=self.clock())
        )
        self.db.commit()
        if result.rowcount != 1:
            raise QuotaExceededError(
                f"הגעתם למכסת {plan.ai_questions_per_month:,} השאלות לעוזר בחודש החיוב הנוכחי. המכסה מתחדשת בתחילת החודש הבא.")
        return counter_id

    def release_ai_question(self, counter_id: str | None) -> None:
        if not counter_id:
            return
        self.db.execute(update(BillingUsageCounter).where(BillingUsageCounter.id == counter_id, BillingUsageCounter.used > 0)
                        .values(used=BillingUsageCounter.used - 1))
        self.db.commit()

    # ---------------------------------------------------------------- webhooks
    def receive_webhook(self, provider_name: str, headers: Mapping[str, str], body: bytes) -> BillingWebhookEvent:
        if self.provider is None or provider_name != self.provider.name:
            raise BillingNotFoundError("Unknown billing provider")
        now = self.clock()
        try:
            event = self.provider.verify_webhook(headers, body, now)
        except BillingWebhookVerificationError:
            logger.warning("rejected unverified billing webhook from %s", provider_name)
            raise
        if not event.provider_event_id:
            raise BillingWebhookVerificationError("Missing event id")
        inbox = BillingWebhookEvent(provider=provider_name, provider_event_id=event.provider_event_id[:255],
                                    event_type=event.event_type.value, payload_summary=_summary(event),
                                    status="received", attempt_count=0, received_at=now)
        self.db.add(inbox)
        try:
            self.db.commit()  # durable before processing
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(select(BillingWebhookEvent).where(
                BillingWebhookEvent.provider == provider_name,
                BillingWebhookEvent.provider_event_id == event.provider_event_id[:255]))
            if existing is None:
                raise
            if existing.status == "failed" and existing.attempt_count < MAX_WEBHOOK_ATTEMPTS:
                return self._process(existing, event)
            return existing
        return self._process(inbox, event)

    def _process(self, inbox: BillingWebhookEvent, event: BillingEvent) -> BillingWebhookEvent:
        inbox_id, attempts = inbox.id, inbox.attempt_count + 1
        try:
            status, note, sub = self._apply(event, inbox_id)
            inbox.status, inbox.last_error, inbox.attempt_count, inbox.processed_at = status, note, attempts, self.clock()
            if sub is not None:
                inbox.business_id, inbox.subscription_id = sub.business_id, sub.id
            self._commit()
            return inbox
        except Exception as error:
            self.db.rollback()
            failed = self.db.get(BillingWebhookEvent, inbox_id)
            failed.status, failed.attempt_count = "failed", attempts
            failed.last_error = safe_error_message(error, 500)
            self.db.commit()
            logger.warning("billing webhook %s failed (attempt %s): %s", inbox_id, attempts, type(error).__name__)
            return failed

    def _resolve(self, event: BillingEvent) -> BusinessSubscription | None:
        sub = None
        if event.subscription_id:
            sub = self.db.scalar(select(BusinessSubscription).where(BusinessSubscription.id == event.subscription_id)
                                 .with_for_update().execution_options(populate_existing=True))
        elif event.provider_subscription_ref:
            sub = self.db.scalar(select(BusinessSubscription).where(
                BusinessSubscription.provider == self.provider.name,
                BusinessSubscription.provider_subscription_ref == event.provider_subscription_ref,
            ).with_for_update().execution_options(populate_existing=True))
        if sub is not None and sub.provider_subscription_ref and event.provider_subscription_ref \
                and sub.provider_subscription_ref != event.provider_subscription_ref:
            return None  # an event for a different provider subscription must never touch this one
        return sub

    def _apply(self, event: BillingEvent, inbox_id: str) -> tuple[str, str | None, BusinessSubscription | None]:
        sub = self._resolve(event)
        if sub is None:
            return "ignored", "No matching subscription", None
        details = {"webhook_event_id": inbox_id}
        kind = event.event_type
        try:
            if kind == BillingEventType.CHECKOUT_COMPLETED:
                sub.provider = self.provider.name
                sub.provider_customer_ref = sub.provider_customer_ref or event.provider_customer_ref
                sub.provider_subscription_ref = sub.provider_subscription_ref or event.provider_subscription_ref
                sub.payment_method_on_file = True
                session = None
                if event.provider_session_ref:
                    session = self.db.scalar(select(BillingCheckoutSession).where(
                        BillingCheckoutSession.provider == self.provider.name,
                        BillingCheckoutSession.provider_session_ref == event.provider_session_ref,
                        BillingCheckoutSession.subscription_id == sub.id))
                if session is not None:
                    session.status = "completed"
                    if S(sub.status) != S.ACTIVE:
                        sub.plan_code, sub.billing_interval = session.plan_code, session.interval
                if sub.cancel_at_period_end and S(sub.status) == S.TRIALING:
                    sub.cancel_at_period_end, sub.canceled_at = False, None
                self._event(sub, "payment_method_added", source="provider", details=details)
                return "processed", None, sub

            if kind == BillingEventType.INVOICE_PAID:
                plan_code = event.plan_code or sub.plan_code
                interval = event.interval or sub.billing_interval
                price = self._price(self._plan(plan_code).code, interval)
                if event.currency != "ILS" or event.amount_excluding_vat_minor != price.amount_minor:
                    return "ignored", "Charged amount does not match the plan price", sub
                if not (event.period_start and event.period_end and event.period_end > event.period_start):
                    return "ignored", "Invalid billing period", sub
                if sub.current_period_start == event.period_start and S(sub.status) == S.ACTIVE:
                    return "processed", None, sub  # same period reported again
                previous_plan = sub.plan_code
                self._move(sub, S.ACTIVE, source="provider", event_type="activated", details=details)
                sub.plan_code, sub.billing_interval = plan_code, interval
                sub.current_period_start, sub.current_period_end = event.period_start, event.period_end
                sub.payment_method_on_file, sub.ended_at = True, None
                if sub.pending_plan_code == plan_code:
                    sub.pending_plan_code = None
                self._event(sub, "invoice_paid", source="provider", from_plan=previous_plan, to_plan=plan_code,
                            details={**details, "period_start": _iso(event.period_start), "period_end": _iso(event.period_end),
                                     "amount_excluding_vat_minor": event.amount_excluding_vat_minor, "interval": interval})
                return "processed", None, sub

            if kind == BillingEventType.INVOICE_PAYMENT_FAILED:
                self._move(sub, S.PAST_DUE, source="provider", event_type="payment_failed",
                           details={**details, "reason": _safe_text(event.failure_reason)})
                return "processed", None, sub

            if kind == BillingEventType.SUBSCRIPTION_CANCELED:
                target = S.EXPIRED if S(sub.status) == S.TRIALING else S.CANCELED
                self._move(sub, target, source="provider", event_type="ended", details=details)
                sub.ended_at = event.occurred_at
                sub.cancel_at_period_end = False
                sub.pending_plan_code = None
                return "processed", None, sub

            if kind == BillingEventType.SUBSCRIPTION_UPDATED:
                if event.cancel_at_period_end is not None:
                    sub.cancel_at_period_end = bool(event.cancel_at_period_end)
                if event.plan_code and event.plan_code != sub.plan_code:
                    plan = self._plan(event.plan_code)
                    previous = sub.plan_code
                    sub.plan_code = plan.code
                    if event.interval in INTERVALS:
                        sub.billing_interval = event.interval
                    if sub.pending_plan_code == plan.code:
                        sub.pending_plan_code = None
                    self._event(sub, "plan_changed", source="provider", from_plan=previous, to_plan=plan.code, details=details)
                return "processed", None, sub
        except InvalidSubscriptionTransition as error:
            return "ignored", f"Out-of-order event: {error}", sub
        except BillingValidationError as error:
            return "ignored", str(error), sub
        return "ignored", "Unsupported event", sub

    # ------------------------------------------------------------------ admin
    def admin_list(self, actor: BillingActor) -> list[dict]:
        _require_platform(actor, superadmin=False)
        now = self.clock()
        rows = self.db.execute(
            select(Business, BusinessSubscription).outerjoin(BusinessSubscription, BusinessSubscription.business_id == Business.id)
            .order_by(Business.created_at.desc())
        ).all()
        from app.billing.access import evaluate_access

        return [{
            "business_id": business.id, "business_name": business.name,
            "plan_code": sub.plan_code if sub else None,
            "status": S(sub.status).value if sub else None,
            "effective_status": effective_status(sub, now).value if sub else None,
            "trial_ends_at": _iso(sub.trial_ends_at) if sub else None,
            "current_period_end": _iso(sub.current_period_end) if sub else None,
            "cancel_at_period_end": sub.cancel_at_period_end if sub else False,
            "payment_method_on_file": sub.payment_method_on_file if sub else False,
            "access_allowed": evaluate_access(sub, now).allowed,
        } for business, sub in rows]

    def admin_events(self, actor: BillingActor, business_id: str) -> list[SubscriptionEvent]:
        _require_platform(actor, superadmin=False)
        sub = self._require_subscription(business_id)
        return list(self.db.scalars(select(SubscriptionEvent).where(SubscriptionEvent.subscription_id == sub.id)
                                    .order_by(SubscriptionEvent.sequence)))

    def admin_override(self, actor: BillingActor, business_id: str, *, action: str, reason: str,
                       days: int | None = None, plan_code: str | None = None, until: datetime | None = None) -> BusinessSubscription:
        _require_platform(actor, superadmin=True)
        reason = (reason or "").strip()
        if not 5 <= len(reason) <= 500 or contains_card_like_number(reason):
            raise BillingValidationError("יש לציין סיבה (5–500 תווים) לכל פעולת ניהול")
        sub = self._require_subscription(business_id, lock=True)
        self.sync_time_based_status(sub)
        now = self.clock()
        audit = {"source": "admin", "actor_user_id": actor.user_id, "reason": reason}
        if action == "extend_trial":
            if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 90:
                raise BillingValidationError("אפשר להאריך ב־1 עד 90 ימים")
            if sub.trial_started_at is None or S(sub.status) not in (S.TRIALING, S.EXPIRED):
                raise BillingConflictError("אפשר להאריך רק תקופת ניסיון")
            previous_end = sub.trial_ends_at
            sub.trial_ends_at = max(sub.trial_ends_at or now, now) + timedelta(days=days)
            sub.cancel_at_period_end, sub.ended_at = False, None
            if S(sub.status) == S.EXPIRED:
                self._move(sub, S.TRIALING, override=True, event_type="status_overridden", **audit)
            self._event(sub, "trial_extended", details={"days": days, "from": _iso(previous_end), "to": _iso(sub.trial_ends_at)}, **audit)
        elif action == "change_plan":
            plan = self._plan(plan_code or "")
            previous = sub.plan_code
            sub.plan_code, sub.pending_plan_code = plan.code, None
            self._event(sub, "plan_overridden", from_plan=previous, to_plan=plan.code,
                        details={"provider_not_updated": bool(sub.provider_subscription_ref)}, **audit)
        elif action == "grant_access":
            if until is None or until.tzinfo is not None or not now < until <= now + timedelta(days=366):
                raise BillingValidationError("תאריך הסיום חייב להיות בעתיד ועד שנה קדימה")
            if S(sub.status) != S.ACTIVE:
                self._move(sub, S.ACTIVE, event_type="status_overridden", **audit)
            sub.current_period_start, sub.current_period_end = now, until
            # Complimentary access never renews by itself.
            sub.cancel_at_period_end, sub.ended_at = True, None
            self._event(sub, "access_granted", details={"until": _iso(until)}, **audit)
        elif action == "end_now":
            target = S.EXPIRED if S(sub.status) == S.TRIALING else S.CANCELED
            self._move(sub, target, event_type="status_overridden", **audit)
            sub.ended_at, sub.cancel_at_period_end = now, False
        else:
            raise BillingValidationError("פעולה לא מוכרת")
        sub.updated_at = now
        self._commit()
        logger.info("subscription %s override %s by %s", sub.id, action, actor.user_id)
        return sub


def _safe_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value)[:255]
    return "[redacted]" if contains_card_like_number(value) else value


def _summary(event: BillingEvent) -> dict:
    return {
        "event_type": event.event_type.value, "occurred_at": _iso(event.occurred_at),
        "subscription_id": (event.subscription_id or "")[:64] or None,
        "plan_code": (event.plan_code or "")[:32] or None, "interval": (event.interval or "")[:8] or None,
        "period_start": _iso(event.period_start), "period_end": _iso(event.period_end),
        "amount_excluding_vat_minor": event.amount_excluding_vat_minor if isinstance(event.amount_excluding_vat_minor, int) else None,
        "currency": (event.currency or "")[:3] or None, "failure_reason": _safe_text(event.failure_reason),
    }
