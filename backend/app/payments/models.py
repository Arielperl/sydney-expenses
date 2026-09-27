"""ORM models for the (inactive) payment orchestration foundation.

All four tables are ``BusinessOwned``, so the request-scoped tenant guards in
``app.core.tenant`` filter every read and reject cross-business writes, on
top of the explicit ``business_id`` filters in the service layer.

Money invariants are enforced by the database, not just the service:
``0 <= refunded_minor <= refund_reserved_minor <= captured_minor <= amount_minor``.
A refund reserves its amount the moment it is created, so two refunds racing
each other can never together exceed what was captured.

No column holds card data, bank credentials, provider secrets or raw
provider payloads.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base
from app.models.business import BusinessOwned
from app.payments.state_machine import OCCUPYING_STATUSES, PaymentStatus, RefundStatus


def _values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def _in_list(column: str, values: list[str]) -> str:
    return f"{column} in ({', '.join(repr(value) for value in values)})"


class WebhookProcessingStatus(str, enum.Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    # Verified and recorded, but deliberately not applied: out-of-order/stale
    # (a backward transition), or it references no payment of this business.
    IGNORED = "ignored"
    # Processing hit a transient error; safe to retry.
    FAILED = "failed"


class AuditSource(str, enum.Enum):
    API = "api"
    PROVIDER_EVENT = "provider_event"
    SYSTEM = "system"


def _status_enum(enum_cls: type[enum.Enum]) -> Enum:
    return Enum(enum_cls, native_enum=False, values_callable=_values, validate_strings=True, length=32)


_OCCUPYING = sorted(status.value for status in OCCUPYING_STATUSES)


class PaymentIntent(BusinessOwned, Base):
    __tablename__ = "payment_intents"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_payment_intents_idempotency"),
        UniqueConstraint("business_id", "provider", "provider_payment_id", name="uq_payment_intents_provider_payment"),
        CheckConstraint(_in_list("status", _values(PaymentStatus)), name="ck_payment_intents_status"),
        CheckConstraint("amount_minor > 0 AND amount_minor <= 1000000000000", name="ck_payment_intents_amount"),
        CheckConstraint("length(currency) = 3 AND upper(currency) = currency", name="ck_payment_intents_currency"),
        CheckConstraint("captured_minor >= 0 AND captured_minor <= amount_minor", name="ck_payment_intents_captured"),
        CheckConstraint(
            "refund_reserved_minor >= 0 AND refund_reserved_minor <= captured_minor",
            name="ck_payment_intents_refund_reserved",
        ),
        CheckConstraint(
            "refunded_minor >= 0 AND refunded_minor <= refund_reserved_minor", name="ck_payment_intents_refunded"
        ),
        CheckConstraint(
            "checkout_url IS NULL OR checkout_url LIKE 'https://%'", name="ck_payment_intents_checkout_url_https"
        ),
        CheckConstraint("version >= 1", name="ck_payment_intents_version"),
        # One live intent per merchant reference: a second attempt for the same
        # order is only possible after the first failed, was cancelled or expired.
        Index(
            "uq_payment_intents_active_reference",
            "business_id",
            "external_reference",
            unique=True,
            sqlite_where=text(_in_list("status", _OCCUPYING)),
            postgresql_where=text(_in_list("status", _OCCUPYING)),
        ),
        Index("ix_payment_intents_business_created", "business_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    captured_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    refund_reserved_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    refunded_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # SHA-256 of the creation parameters: the same key with different parameters is a conflict, not a replay.
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(_status_enum(PaymentStatus), nullable=False, default=PaymentStatus.CREATED)
    checkout_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Optimistic concurrency: every UPDATE is "... WHERE version = <read version>", so
    # a writer working from a stale read fails instead of silently overwriting.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": version}


class PaymentRefund(BusinessOwned, Base):
    __tablename__ = "payment_refunds"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_payment_refunds_idempotency"),
        UniqueConstraint("business_id", "provider_refund_id", name="uq_payment_refunds_provider_refund"),
        CheckConstraint(_in_list("status", _values(RefundStatus)), name="ck_payment_refunds_status"),
        CheckConstraint("amount_minor > 0 AND amount_minor <= 1000000000000", name="ck_payment_refunds_amount"),
        CheckConstraint("length(currency) = 3 AND upper(currency) = currency", name="ck_payment_refunds_currency"),
        CheckConstraint("version >= 1", name="ck_payment_refunds_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_intent_id: Mapped[str] = mapped_column(
        ForeignKey("payment_intents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider_refund_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RefundStatus] = mapped_column(_status_enum(RefundStatus), nullable=False, default=RefundStatus.PENDING)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Many-to-one links exist so the unit of work always inserts parents before
    # children (plain FK columns alone do not order a flush); nothing loads them eagerly.
    payment_intent: Mapped["PaymentIntent"] = relationship(lazy="raise")

    __mapper_args__ = {"version_id_col": version}


class PaymentWebhookEvent(BusinessOwned, Base):
    """Durable inbox: a *verified* provider event is recorded here before it
    is applied. Unverified deliveries are rejected and never stored."""

    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint("business_id", "provider", "provider_event_id", name="uq_payment_webhook_events_provider_event"),
        CheckConstraint(_in_list("status", _values(WebhookProcessingStatus)), name="ck_payment_webhook_events_status"),
        CheckConstraint("attempt_count >= 0", name="ck_payment_webhook_events_attempts"),
        Index("ix_payment_webhook_events_status", "business_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # A whitelisted, normalized summary built by the service — never the raw body.
    payload_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payment_intent_id: Mapped[str | None] = mapped_column(ForeignKey("payment_intents.id", ondelete="RESTRICT"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    status: Mapped[WebhookProcessingStatus] = mapped_column(
        _status_enum(WebhookProcessingStatus), nullable=False, default=WebhookProcessingStatus.RECEIVED
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    payment_intent: Mapped["PaymentIntent | None"] = relationship(lazy="raise")


class PaymentAuditEvent(BusinessOwned, Base):
    """Append-only history of every payment and refund status change.

    Immutability is enforced three ways: an ORM guard below (updates/deletes
    of loaded rows), a guard against bulk UPDATE/DELETE statements, and
    database triggers created by the migration.
    """

    __tablename__ = "payment_audit_events"
    __table_args__ = (
        CheckConstraint(_in_list("source", _values(AuditSource)), name="ck_payment_audit_events_source"),
        CheckConstraint("entity in ('payment', 'refund')", name="ck_payment_audit_events_entity"),
        Index("ix_payment_audit_events_intent_created", "payment_intent_id", "created_at"),
        UniqueConstraint("payment_intent_id", "sequence", name="uq_payment_audit_events_sequence"),
        CheckConstraint("sequence >= 1", name="ck_payment_audit_events_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_intent_id: Mapped[str] = mapped_column(ForeignKey("payment_intents.id", ondelete="RESTRICT"), nullable=False)
    refund_id: Mapped[str | None] = mapped_column(ForeignKey("payment_refunds.id", ondelete="RESTRICT"), nullable=True)
    webhook_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("payment_webhook_events.id", ondelete="RESTRICT"), nullable=True
    )
    # Order of events for one payment. Every audit write happens while the intent row
    # is locked and its version bumped, so this per-intent counter cannot collide.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    entity: Mapped[str] = mapped_column(String(16), nullable=False)  # "payment" or "refund"
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[AuditSource] = mapped_column(_status_enum(AuditSource), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    payment_intent: Mapped["PaymentIntent"] = relationship(lazy="raise")
    refund: Mapped["PaymentRefund | None"] = relationship(lazy="raise")
    webhook_event: Mapped["PaymentWebhookEvent | None"] = relationship(lazy="raise")


class AuditImmutableError(Exception):
    pass


@event.listens_for(Session, "before_flush")
def _forbid_audit_mutation(session, flush_context, instances):
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, PaymentAuditEvent) and (obj in session.deleted or session.is_modified(obj)):
            raise AuditImmutableError("Payment audit events are append-only")


@event.listens_for(Session, "do_orm_execute")
def _forbid_audit_bulk_mutation(state):
    if (state.is_update or state.is_delete) and any(
        getattr(mapper, "class_", None) is PaymentAuditEvent for mapper in state.all_mappers
    ):
        raise AuditImmutableError("Payment audit events are append-only")
