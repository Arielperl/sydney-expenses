"""Subscription billing tables. All timestamps are naive UTC.

Business-owned tables use ``BusinessOwned`` so the request tenant guards in
``app.core.tenant`` apply. The plan catalog, the provider-level webhook inbox
and trial claims are deliberately global: plans are shared, a billing webhook
arrives before its business is known, and a trial claim must be checked across
every business (that is how a second trial is refused).

No column holds card numbers, CVV, bank details or provider secrets. The
provider references are opaque identifiers only.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base
from app.models.business import BusinessOwned
from app.billing.state_machine import SubscriptionStatus


def _uuid() -> str:
    return str(uuid.uuid4())


def _in(column: str, values) -> str:
    return f"{column} in ({', '.join(repr(value) for value in values)})"


STATUS_VALUES = [status.value for status in SubscriptionStatus]
EVENT_SOURCES = ("owner", "provider", "system", "admin")
WEBHOOK_STATUSES = ("received", "processed", "ignored", "failed")
CHECKOUT_STATUSES = ("open", "completed", "expired", "canceled")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        CheckConstraint("max_connections >= 0", name="ck_subscription_plans_connections"),
        CheckConstraint("max_members >= 1", name="ck_subscription_plans_members"),
        CheckConstraint("ai_questions_per_month >= 0", name="ck_subscription_plans_ai"),
    )

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    tagline: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_connections: Mapped[int] = mapped_column(Integer, nullable=False)
    max_members: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_questions_per_month: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    features: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class SubscriptionPlanPrice(Base):
    __tablename__ = "subscription_plan_prices"
    __table_args__ = (
        UniqueConstraint("plan_code", "interval", "currency", name="uq_subscription_plan_prices_plan_interval"),
        CheckConstraint("interval in ('month', 'year')", name="ck_subscription_plan_prices_interval"),
        CheckConstraint("amount_minor > 0", name="ck_subscription_plan_prices_amount"),
        CheckConstraint("currency = 'ILS'", name="ck_subscription_plan_prices_currency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plan_code: Mapped[str] = mapped_column(ForeignKey("subscription_plans.code"), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)  # excluding VAT
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="ILS")
    # The billing provider's own price identifier, once a provider exists.
    provider_price_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BusinessSubscription(BusinessOwned, Base):
    __tablename__ = "business_subscriptions"
    __table_args__ = (
        # One subscription per business, ever: a business can never get a second trial.
        UniqueConstraint("business_id", name="uq_business_subscriptions_business"),
        UniqueConstraint("provider", "provider_subscription_ref", name="uq_business_subscriptions_provider_ref"),
        CheckConstraint(_in("status", STATUS_VALUES), name="ck_business_subscriptions_status"),
        CheckConstraint("billing_interval in ('month', 'year')", name="ck_business_subscriptions_interval"),
        CheckConstraint(
            "(trial_started_at IS NULL AND trial_ends_at IS NULL) OR "
            "(trial_started_at IS NOT NULL AND trial_ends_at IS NOT NULL AND trial_ends_at > trial_started_at)",
            name="ck_business_subscriptions_trial_window",
        ),
        CheckConstraint("status <> 'trialing' OR trial_ends_at IS NOT NULL", name="ck_business_subscriptions_trialing_has_end"),
        CheckConstraint(
            "current_period_start IS NULL OR current_period_end IS NULL OR current_period_end > current_period_start",
            name="ck_business_subscriptions_period_window",
        ),
        CheckConstraint("version >= 1", name="ck_business_subscriptions_version"),
        Index("ix_business_subscriptions_status_trial_end", "status", "trial_ends_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plan_code: Mapped[str] = mapped_column(ForeignKey("subscription_plans.code"), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(8), nullable=False, default="month")
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False, values_callable=lambda e: [m.value for m in e], length=16),
        nullable=False,
    )
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # A downgrade scheduled for the end of the paid period.
    pending_plan_code: Mapped[str | None] = mapped_column(ForeignKey("subscription_plans.code"), nullable=True)
    payment_method_on_file: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_customer_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_subscription_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": version}


class SubscriptionEvent(BusinessOwned, Base):
    """Append-only history: ORM guard below + database triggers from the migration."""

    __tablename__ = "subscription_events"
    __table_args__ = (
        UniqueConstraint("subscription_id", "sequence", name="uq_subscription_events_sequence"),
        CheckConstraint(_in("source", EVENT_SOURCES), name="ck_subscription_events_source"),
        CheckConstraint("sequence >= 1", name="ck_subscription_events_sequence"),
        CheckConstraint("source <> 'admin' OR (actor_user_id IS NOT NULL AND reason IS NOT NULL)", name="ck_subscription_events_admin_reason"),
        Index("ix_subscription_events_subscription_created", "subscription_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("business_subscriptions.id", ondelete="RESTRICT"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    from_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    subscription: Mapped[BusinessSubscription] = relationship(lazy="raise")


class BillingCheckoutSession(BusinessOwned, Base):
    __tablename__ = "billing_checkout_sessions"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_billing_checkout_sessions_idempotency"),
        UniqueConstraint("provider", "provider_session_ref", name="uq_billing_checkout_sessions_provider_ref"),
        CheckConstraint(_in("status", CHECKOUT_STATUSES), name="ck_billing_checkout_sessions_status"),
        CheckConstraint("interval in ('month', 'year')", name="ck_billing_checkout_sessions_interval"),
        CheckConstraint("checkout_url IS NULL OR checkout_url LIKE 'https://%'", name="ck_billing_checkout_sessions_https"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("business_subscriptions.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_session_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("subscription_plans.code"), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    checkout_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscription: Mapped[BusinessSubscription] = relationship(lazy="raise")


class BillingWebhookEvent(Base):
    """Durable inbox for *verified* billing-provider deliveries. Unverified ones are never stored."""

    __tablename__ = "billing_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_billing_webhook_events_provider_event"),
        CheckConstraint(_in("status", WEBHOOK_STATUSES), name="ck_billing_webhook_events_status"),
        CheckConstraint("attempt_count >= 0", name="ck_billing_webhook_events_attempts"),
        Index("ix_billing_webhook_events_status", "status", "received_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id"), nullable=True, index=True)
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("business_subscriptions.id", ondelete="RESTRICT"), nullable=True)
    payload_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # whitelisted, never the raw body
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="received")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BillingUsageCounter(BusinessOwned, Base):
    """Metered usage per business, metric and billing month."""

    __tablename__ = "billing_usage_counters"
    __table_args__ = (
        UniqueConstraint("business_id", "metric", "period_start", name="uq_billing_usage_counters_period"),
        CheckConstraint("metric in ('ai_questions')", name="ck_billing_usage_counters_metric"),
        CheckConstraint("used >= 0", name="ck_billing_usage_counters_used"),
        CheckConstraint("period_end > period_start", name="ck_billing_usage_counters_window"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class BillingTrialClaim(Base):
    """Who has already used a free trial, independent of any one business.

    ``identity_hash`` is SHA-256 over a normalized identity ("email:" or
    "business_number:"). It survives account deletion, owner changes and
    retried onboarding, which is what stops a second trial.
    """

    __tablename__ = "billing_trial_claims"
    __table_args__ = (UniqueConstraint("identity_hash", name="uq_billing_trial_claims_identity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    identity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class SubscriptionAuditImmutableError(Exception):
    pass


@event.listens_for(Session, "before_flush")
def _forbid_subscription_event_mutation(session, flush_context, instances):
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, SubscriptionEvent) and (obj in session.deleted or session.is_modified(obj)):
            raise SubscriptionAuditImmutableError("Subscription events are append-only")


@event.listens_for(Session, "do_orm_execute")
def _forbid_subscription_event_bulk_mutation(state):
    if (state.is_update or state.is_delete) and any(
        getattr(mapper, "class_", None) is SubscriptionEvent for mapper in state.all_mappers
    ):
        raise SubscriptionAuditImmutableError("Subscription events are append-only")
