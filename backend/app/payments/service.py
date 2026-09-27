"""Transaction-safe payment orchestration (INACTIVE — see app/payments/__init__.py).

Every public method takes an explicit business scope: the actor's
``business_id`` for API operations, an explicit ``business_id`` for provider
webhooks. Each query filters on it, and a request-scoped session (see
``app.core.tenant``) enforces the same scope a second time.

Concurrency and money safety
----------------------------
* Status changes only go through the state machine, and every change writes
  an immutable ``PaymentAuditEvent`` in the same transaction.
* The intent row is locked (``SELECT ... FOR UPDATE`` on PostgreSQL) and
  versioned (optimistic ``version`` check on every UPDATE, which also covers
  SQLite), so racing writers fail with ``ConcurrentUpdateError`` instead of
  overwriting each other.
* Refunds are two-phase: the refund row and its amount reservation are
  committed *before* the provider is called, using the refund's id as the
  provider idempotency key. A crash or failed commit after the provider has
  refunded therefore leaves a pending refund that ``retry_pending_refund``
  can complete with the same key — never a second refund.
* Idempotency keys are unique per business at the database level (one
  constraint per operation table); reusing a key with different parameters
  is a conflict, not a replay.
"""

import hashlib
import json
import logging
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.payments.currency import CurrencyError, normalize_currency, validate_amount_minor
from app.payments.errors import (
    ConcurrentUpdateError,
    DuplicateExternalReferenceError,
    IdempotencyConflictError,
    PaymentNotFoundError,
    PaymentStateError,
    PaymentValidationError,
    RefundLimitExceededError,
)
from app.payments.models import (
    AuditSource,
    PaymentAuditEvent,
    PaymentIntent,
    PaymentRefund,
    PaymentWebhookEvent,
    WebhookProcessingStatus,
)
from app.payments.permissions import PaymentAction, PaymentActor, PaymentPermissionError, authorize
from app.payments.providers.base import (
    EVENT_TARGET_STATUS,
    ProviderCreatePaymentRequest,
    ProviderError,
    ProviderEventType,
    ProviderRefundRequest,
    VerifiedProviderEvent,
    WebhookVerificationError,
)
from app.payments.providers.registry import PaymentProviderRegistry
from app.payments.sensitive_data import contains_card_like_number, safe_error_message
from app.payments.state_machine import (
    CANCELLABLE_STATUSES,
    REFUNDABLE_STATUSES,
    InvalidTransitionError,
    PaymentStatus,
    RefundStatus,
    check_payment_transition,
    check_refund_transition,
)
from app.payments.urls import validate_checkout_url

logger = logging.getLogger("app.payments")

REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:\-]{8,128}$")
PROVIDER_NAME_PATTERN = re.compile(r"^[a-z0-9_]{2,40}$")
MAX_INTENT_LIFETIME = timedelta(days=30)
MAX_WEBHOOK_ATTEMPTS = 10
MAX_LIST_LIMIT = 100
MAX_PROVIDER_IDENTIFIER_LENGTH = 255


@dataclass(frozen=True)
class CreatePaymentIntentInput:
    external_reference: str
    provider: str
    amount_minor: int
    currency: str
    description: str
    idempotency_key: str
    customer_reference: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class WebhookOutcome:
    event: PaymentWebhookEvent
    duplicate: bool = False


def _fingerprint(params: dict) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()


def _clean_text(value: str | None, field: str, *, required: bool, max_length: int) -> str | None:
    if value is None or value == "":
        if required:
            raise PaymentValidationError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise PaymentValidationError(f"{field} must be text")
    value = value.strip()
    if not value or len(value) > max_length:
        raise PaymentValidationError(f"{field} must be 1-{max_length} characters")
    if any(ord(char) < 32 for char in value):
        raise PaymentValidationError(f"{field} contains control characters")
    if contains_card_like_number(value):
        raise PaymentValidationError(f"{field} looks like it contains a card number, which is never accepted")
    return value


def _provider_identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_PROVIDER_IDENTIFIER_LENGTH:
        raise PaymentValidationError(f"{field} is missing or too long")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise PaymentValidationError(f"{field} contains control characters")
    return value


class PaymentService:
    def __init__(self, db: Session, registry: PaymentProviderRegistry, *, clock: Callable[[], datetime] = datetime.utcnow):
        self.db = db
        self.registry = registry
        self.clock = clock

    # ------------------------------------------------------------------ scope
    def _scope(self, business_id: str) -> str:
        if not business_id:
            raise PaymentPermissionError("A business is required")
        session_business = self.db.info.get("business_id")
        if session_business and session_business != business_id:
            raise PaymentPermissionError("Session is scoped to a different business")
        return business_id

    def _authorized_scope(self, actor: PaymentActor, action: PaymentAction) -> str:
        authorize(actor, action)
        return self._scope(actor.business_id)

    def _get_intent(self, business_id: str, intent_id: str, *, lock: bool) -> PaymentIntent:
        statement = select(PaymentIntent).where(PaymentIntent.id == intent_id, PaymentIntent.business_id == business_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        intent = self.db.scalar(statement)
        if intent is None:
            raise PaymentNotFoundError("Payment not found")
        return intent

    def _commit(self) -> None:
        try:
            self.db.commit()
        except (StaleDataError, IntegrityError) as error:
            # A stale version or a colliding audit sequence both mean another
            # writer changed this payment first; nothing was saved.
            self.db.rollback()
            raise ConcurrentUpdateError("The payment was changed by another operation; please retry") from error
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------ transitions
    def _audit(self, *, business_id: str, intent_id: str, entity: str, from_status, to_status, source: AuditSource,
               actor_user_id: str | None = None, refund_id: str | None = None, webhook_event_id: str | None = None,
               note: str | None = None) -> None:
        stored = self.db.scalar(
            select(func.max(PaymentAuditEvent.sequence)).where(PaymentAuditEvent.payment_intent_id == intent_id)
        ) or 0
        unflushed = sum(
            1 for obj in self.db.new if isinstance(obj, PaymentAuditEvent) and obj.payment_intent_id == intent_id
        )
        self.db.add(PaymentAuditEvent(
            business_id=business_id, payment_intent_id=intent_id, refund_id=refund_id, webhook_event_id=webhook_event_id,
            sequence=stored + unflushed + 1,
            entity=entity, from_status=from_status.value if from_status else None, to_status=to_status.value,
            source=source, actor_user_id=actor_user_id, note=note, created_at=self.clock(),
        ))

    def _transition(self, intent: PaymentIntent, target: PaymentStatus, source: AuditSource, **audit) -> bool:
        current = PaymentStatus(intent.status)
        if not check_payment_transition(current, target):
            return False
        intent.status = target
        intent.updated_at = self.clock()
        self._audit(business_id=intent.business_id, intent_id=intent.id, entity="payment",
                    from_status=current, to_status=target, source=source, **audit)
        logger.info("payment %s: %s -> %s (%s)", intent.id, current.value, target.value, source.value)
        return True

    def _transition_refund(self, refund: PaymentRefund, target: RefundStatus, source: AuditSource, **audit) -> bool:
        current = RefundStatus(refund.status)
        if not check_refund_transition(current, target):
            return False
        refund.status = target
        refund.updated_at = self.clock()
        self._audit(business_id=refund.business_id, intent_id=refund.payment_intent_id, refund_id=refund.id,
                    entity="refund", from_status=current, to_status=target, source=source, **audit)
        logger.info("refund %s: %s -> %s (%s)", refund.id, current.value, target.value, source.value)
        return True

    def _complete_refund(self, refund: PaymentRefund, intent: PaymentIntent, source: AuditSource, **audit) -> None:
        if not self._transition_refund(refund, RefundStatus.SUCCEEDED, source, **audit):
            return
        intent.refunded_minor += refund.amount_minor
        target = PaymentStatus.REFUNDED if intent.refunded_minor == intent.captured_minor else PaymentStatus.PARTIALLY_REFUNDED
        self._transition(intent, target, source, refund_id=refund.id, **audit)

    def _fail_refund(
        self, refund: PaymentRefund, intent: PaymentIntent, reason: str | None, source: AuditSource, **audit
    ) -> None:
        if not self._transition_refund(refund, RefundStatus.FAILED, source, **audit):
            return
        refund.failure_reason = (reason or "Refund failed")[:255]
        intent.refund_reserved_minor -= refund.amount_minor

    # ---------------------------------------------------------- idempotency
    def _replay(self, existing, fingerprint: str):
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflictError("This idempotency key was already used with different parameters")
        return existing

    def _existing(self, model, business_id: str, key: str):
        return self.db.scalar(select(model).where(model.business_id == business_id, model.idempotency_key == key))

    # --------------------------------------------------------------- create
    def create_payment_intent(self, actor: PaymentActor, data: CreatePaymentIntentInput) -> PaymentIntent:
        business_id = self._authorized_scope(actor, PaymentAction.CREATE)
        external_reference = _clean_text(data.external_reference, "external_reference", required=True, max_length=64)
        if not REFERENCE_PATTERN.fullmatch(external_reference):
            raise PaymentValidationError("external_reference may only contain letters, digits and . _ : -")
        if not isinstance(data.idempotency_key, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(data.idempotency_key):
            raise PaymentValidationError("idempotency_key must be 8-128 characters of letters, digits and . _ : -")
        if not isinstance(data.provider, str) or not PROVIDER_NAME_PATTERN.fullmatch(data.provider):
            raise PaymentValidationError("Unknown provider")
        try:
            amount = validate_amount_minor(data.amount_minor)
            currency = normalize_currency(data.currency)
        except CurrencyError as error:
            raise PaymentValidationError(str(error)) from error
        description = _clean_text(data.description, "description", required=True, max_length=255)
        customer_reference = _clean_text(data.customer_reference, "customer_reference", required=False, max_length=64)
        if customer_reference is not None and not REFERENCE_PATTERN.fullmatch(customer_reference):
            raise PaymentValidationError("customer_reference may only contain letters, digits and . _ : -")
        now = self.clock()
        if data.expires_at is not None:
            if data.expires_at.tzinfo is not None:
                raise PaymentValidationError("expires_at must be naive UTC")
            if not now < data.expires_at <= now + MAX_INTENT_LIFETIME:
                raise PaymentValidationError("expires_at must be in the future and within 30 days")
        self.registry.get(data.provider)  # fail before writing anything if the provider is unavailable

        fingerprint = _fingerprint({
            "external_reference": external_reference, "provider": data.provider, "amount_minor": amount,
            "currency": currency, "description": description, "customer_reference": customer_reference,
            "expires_at": data.expires_at,
        })
        existing = self._existing(PaymentIntent, business_id, data.idempotency_key)
        if existing is not None:
            return self._replay(existing, fingerprint)

        intent = PaymentIntent(
            id=str(uuid.uuid4()), business_id=business_id, external_reference=external_reference,
            provider=data.provider, amount_minor=amount, currency=currency, description=description,
            customer_reference=customer_reference, idempotency_key=data.idempotency_key,
            request_fingerprint=fingerprint, status=PaymentStatus.CREATED, expires_at=data.expires_at,
            created_by_user_id=actor.user_id, created_at=now, updated_at=now,
        )
        self.db.add(intent)
        self._audit(business_id=business_id, intent_id=intent.id, entity="payment", from_status=None,
                    to_status=PaymentStatus.CREATED, source=AuditSource.API, actor_user_id=actor.user_id)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            existing = self._existing(PaymentIntent, business_id, data.idempotency_key)
            if existing is not None:  # a concurrent request with the same key won the race
                return self._replay(existing, fingerprint)
            raise DuplicateExternalReferenceError(
                "A live payment already exists for this external reference"
            ) from error
        logger.info("payment %s created for business %s", intent.id, business_id)
        return intent

    # -------------------------------------------------------------- checkout
    def request_checkout(self, actor: PaymentActor, intent_id: str) -> PaymentIntent:
        business_id = self._authorized_scope(actor, PaymentAction.CREATE)
        intent = self._get_intent(business_id, intent_id, lock=True)
        if intent.status != PaymentStatus.CREATED:
            if intent.provider_payment_id and intent.status in (PaymentStatus.PENDING, PaymentStatus.REQUIRES_ACTION):
                self.db.rollback()
                return intent  # already requested: idempotent
            self.db.rollback()
            raise PaymentStateError(f"Checkout cannot be requested for a payment that is {intent.status.value}")
        adapter = self.registry.get(intent.provider)
        try:
            # Keyed by intent.id, so a retry after any failure returns the same provider payment.
            result = adapter.create_payment(ProviderCreatePaymentRequest(
                intent_id=intent.id, amount_minor=intent.amount_minor, currency=intent.currency,
                description=intent.description, external_reference=intent.external_reference,
            ))
            checkout_url = None
            if result.checkout_url:
                checkout_url = validate_checkout_url(result.checkout_url, adapter.allowed_checkout_hosts)
            intent.provider_payment_id = _provider_identifier(result.provider_payment_id, "provider_payment_id")
            intent.checkout_url = checkout_url
            if result.expires_at is not None:
                if result.expires_at.tzinfo is not None:
                    raise PaymentValidationError("Provider expires_at must be naive UTC")
                intent.expires_at = result.expires_at
            if result.status == PaymentStatus.CAPTURED:
                try:
                    captured_minor = validate_amount_minor(result.captured_minor)
                except CurrencyError as error:
                    raise PaymentValidationError("A captured provider result must include a valid captured amount") from error
                if captured_minor > intent.amount_minor:
                    raise PaymentValidationError("Provider captured more than the requested amount")
                intent.captured_minor = captured_minor
            elif result.captured_minor != 0:
                raise PaymentValidationError("A pre-capture provider result cannot include a captured amount")
            self._transition(intent, result.status, AuditSource.API, actor_user_id=actor.user_id)
        except Exception:
            self.db.rollback()
            raise
        self._commit()
        return intent

    # ---------------------------------------------------------------- cancel
    def cancel_payment(self, actor: PaymentActor, intent_id: str) -> PaymentIntent:
        business_id = self._authorized_scope(actor, PaymentAction.CANCEL)
        intent = self._get_intent(business_id, intent_id, lock=True)
        if intent.status == PaymentStatus.CANCELLED:
            self.db.rollback()
            return intent
        if intent.status not in CANCELLABLE_STATUSES:
            self.db.rollback()
            raise PaymentStateError(f"A payment that is {intent.status.value} cannot be cancelled")
        try:
            if intent.provider_payment_id:
                result = self.registry.get(intent.provider).cancel_payment(intent.provider_payment_id)
                if result.provider_payment_id != intent.provider_payment_id:
                    raise PaymentStateError("Provider cancellation returned a different payment")
                if result.status != PaymentStatus.CANCELLED:
                    raise PaymentStateError(
                        f"Provider did not confirm cancellation (reported {result.status.value})"
                    )
            self._transition(intent, PaymentStatus.CANCELLED, AuditSource.API, actor_user_id=actor.user_id)
        except Exception:
            self.db.rollback()
            raise
        self._commit()
        return intent

    # --------------------------------------------------------------- refunds
    def create_refund(self, actor: PaymentActor, intent_id: str, *, idempotency_key: str,
                      amount_minor: int | None = None, reason: str | None = None) -> PaymentRefund:
        business_id = self._authorized_scope(actor, PaymentAction.REFUND)
        if not isinstance(idempotency_key, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key):
            raise PaymentValidationError("idempotency_key must be 8-128 characters of letters, digits and . _ : -")
        if amount_minor is not None:
            try:
                validate_amount_minor(amount_minor)
            except CurrencyError as error:
                raise PaymentValidationError(str(error)) from error
        reason = _clean_text(reason, "reason", required=False, max_length=255)
        fingerprint = _fingerprint({"intent_id": intent_id, "amount_minor": amount_minor, "reason": reason})
        existing = self._existing(PaymentRefund, business_id, idempotency_key)
        if existing is not None:
            return self._replay(existing, fingerprint)

        # Phase 1: validate against the locked, current intent and reserve the amount.
        intent = self._get_intent(business_id, intent_id, lock=True)
        if intent.status not in REFUNDABLE_STATUSES:
            self.db.rollback()
            raise PaymentStateError(f"A payment that is {intent.status.value} cannot be refunded")
        available = intent.captured_minor - intent.refund_reserved_minor
        amount = amount_minor if amount_minor is not None else available
        if amount <= 0 or amount > available:
            self.db.rollback()
            raise RefundLimitExceededError("The refund exceeds the amount still refundable")
        now = self.clock()
        refund = PaymentRefund(
            id=str(uuid.uuid4()), business_id=business_id, payment_intent_id=intent.id, amount_minor=amount,
            currency=intent.currency, reason=reason, idempotency_key=idempotency_key, request_fingerprint=fingerprint,
            status=RefundStatus.PENDING, created_by_user_id=actor.user_id, created_at=now, updated_at=now,
        )
        intent.refund_reserved_minor += amount
        self.db.add(refund)
        self._audit(business_id=business_id, intent_id=intent.id, refund_id=refund.id, entity="refund",
                    from_status=None, to_status=RefundStatus.PENDING, source=AuditSource.API, actor_user_id=actor.user_id)
        try:
            self.db.commit()
        except StaleDataError as error:
            self.db.rollback()
            raise ConcurrentUpdateError("The payment was changed by another operation; please retry") from error
        except IntegrityError as error:
            self.db.rollback()
            existing = self._existing(PaymentRefund, business_id, idempotency_key)
            if existing is not None:
                return self._replay(existing, fingerprint)
            # Only a concurrent writer can trip a constraint here (the amount was
            # checked against the locked row): the caller should re-read and retry.
            raise ConcurrentUpdateError("The payment was changed by another operation; please retry") from error

        # Phase 2: ask the provider, then record the outcome.
        return self._submit_refund(refund.id, business_id, actor.user_id)

    def retry_pending_refund(self, actor: PaymentActor, refund_id: str) -> PaymentRefund:
        business_id = self._authorized_scope(actor, PaymentAction.REFUND)
        return self._submit_refund(refund_id, business_id, actor.user_id)

    def _submit_refund(self, refund_id: str, business_id: str, actor_user_id: str | None) -> PaymentRefund:
        refund = self.db.scalar(
            select(PaymentRefund).where(PaymentRefund.id == refund_id, PaymentRefund.business_id == business_id)
        )
        if refund is None:
            raise PaymentNotFoundError("Refund not found")
        if refund.status != RefundStatus.PENDING:
            return refund
        intent = self._get_intent(business_id, refund.payment_intent_id, lock=True)
        adapter = self.registry.get(intent.provider)
        try:
            result = adapter.refund_payment(ProviderRefundRequest(
                refund_id=refund.id, provider_payment_id=intent.provider_payment_id or "", amount_minor=refund.amount_minor,
                currency=refund.currency, reason=refund.reason,
            ))
        except ProviderError as error:
            if error.retryable:
                self.db.rollback()  # stays pending with its reservation; safe to retry with the same refund id
                raise
            self._fail_refund(refund, intent, safe_error_message(error, 255), AuditSource.API, actor_user_id=actor_user_id)
            self._commit()
            raise
        refund.provider_refund_id = result.provider_refund_id
        if result.status == RefundStatus.SUCCEEDED:
            self._complete_refund(refund, intent, AuditSource.API, actor_user_id=actor_user_id)
        elif result.status == RefundStatus.FAILED:
            self._fail_refund(refund, intent, result.failure_reason, AuditSource.API, actor_user_id=actor_user_id)
        self._commit()  # a failure here leaves the refund pending; retry_pending_refund completes it
        return refund

    # ------------------------------------------------------------------ read
    def get_payment(self, actor: PaymentActor, intent_id: str) -> PaymentIntent:
        business_id = self._authorized_scope(actor, PaymentAction.VIEW)
        return self._get_intent(business_id, intent_id, lock=False)

    def list_payment_intents(self, actor: PaymentActor, *, status: PaymentStatus | None = None,
                             limit: int = 50, offset: int = 0) -> list[PaymentIntent]:
        business_id = self._authorized_scope(actor, PaymentAction.VIEW)
        if not 1 <= limit <= MAX_LIST_LIMIT or offset < 0:
            raise PaymentValidationError("Invalid pagination")
        statement = select(PaymentIntent).where(PaymentIntent.business_id == business_id)
        if status is not None:
            statement = statement.where(PaymentIntent.status == status)
        statement = statement.order_by(PaymentIntent.created_at.desc(), PaymentIntent.id).limit(limit).offset(offset)
        return list(self.db.scalars(statement))

    def admin_status_counts(self, actor: PaymentActor, business_id: str) -> dict[str, int]:
        """Platform-admin oversight: counts only. No references, provider ids, URLs or customer data."""
        authorize(actor, PaymentAction.ADMIN_VIEW)
        rows = self.db.execute(
            select(PaymentIntent.status, func.count())
            .where(PaymentIntent.business_id == business_id)
            .group_by(PaymentIntent.status)
        )
        return {PaymentStatus(status).value: count for status, count in rows}

    def audit_trail(self, actor: PaymentActor, intent_id: str) -> list[PaymentAuditEvent]:
        business_id = self._authorized_scope(actor, PaymentAction.VIEW)
        self._get_intent(business_id, intent_id, lock=False)
        return list(self.db.scalars(
            select(PaymentAuditEvent)
            .where(PaymentAuditEvent.business_id == business_id, PaymentAuditEvent.payment_intent_id == intent_id)
            .order_by(PaymentAuditEvent.sequence)
        ))

    # --------------------------------------------------------------- expiry
    def expire_due_payments(self, business_id: str) -> int:
        business_id = self._scope(business_id)
        now = self.clock()
        due = self.db.scalars(
            select(PaymentIntent).where(
                PaymentIntent.business_id == business_id,
                PaymentIntent.expires_at.is_not(None),
                PaymentIntent.expires_at <= now,
                PaymentIntent.status.in_([PaymentStatus.CREATED, PaymentStatus.PENDING, PaymentStatus.REQUIRES_ACTION]),
            ).with_for_update()
        ).all()
        for intent in due:
            self._transition(intent, PaymentStatus.EXPIRED, AuditSource.SYSTEM, note="expires_at reached")
        self._commit()
        return len(due)

    # -------------------------------------------------------------- webhooks
    def receive_webhook(self, business_id: str, provider: str, headers: Mapping[str, str], body: bytes) -> WebhookOutcome:
        """Verify, durably record, then apply one provider delivery.

        Unverified deliveries raise ``WebhookVerificationError`` and are never
        stored. A redelivery of an already-recorded event is a no-op, except
        that a previously *failed* event is retried.
        """
        business_id = self._scope(business_id)
        adapter = self.registry.get(provider)
        now = self.clock()
        try:
            event = adapter.verify_webhook(headers, body, now)
        except WebhookVerificationError:
            # Deliberately no headers, signature or body in the log.
            logger.warning("rejected unverified %s webhook for business %s", provider, business_id)
            raise
        try:
            provider_event_id = _provider_identifier(event.provider_event_id, "provider_event_id")
            _provider_identifier(event.provider_payment_id, "provider_payment_id")
        except PaymentValidationError as error:
            raise WebhookVerificationError("Verified event has invalid identifiers") from error
        inbox = PaymentWebhookEvent(
            business_id=business_id, provider=provider, provider_event_id=provider_event_id,
            event_type=event.event_type.value, payload_summary=_summarize(event), received_at=now,
            status=WebhookProcessingStatus.RECEIVED, attempt_count=0, created_at=now, updated_at=now,
        )
        self.db.add(inbox)
        try:
            self.db.commit()  # durable before any processing
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.business_id == business_id,
                PaymentWebhookEvent.provider == provider,
                PaymentWebhookEvent.provider_event_id == provider_event_id,
            ))
            if existing is None:
                raise
            if existing.status in (WebhookProcessingStatus.RECEIVED, WebhookProcessingStatus.FAILED) \
                    and existing.attempt_count < MAX_WEBHOOK_ATTEMPTS:
                return WebhookOutcome(self._process_inbox(existing), duplicate=True)
            return WebhookOutcome(existing, duplicate=True)
        return WebhookOutcome(self._process_inbox(inbox))

    def retry_webhook_event(self, business_id: str, event_id: str) -> PaymentWebhookEvent:
        business_id = self._scope(business_id)
        inbox = self.db.scalar(select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.id == event_id, PaymentWebhookEvent.business_id == business_id))
        if inbox is None:
            raise PaymentNotFoundError("Webhook event not found")
        if inbox.status not in (WebhookProcessingStatus.RECEIVED, WebhookProcessingStatus.FAILED):
            return inbox
        if inbox.attempt_count >= MAX_WEBHOOK_ATTEMPTS:
            raise PaymentStateError("Retry limit reached; this event needs manual review")
        return self._process_inbox(inbox)

    def _process_inbox(self, inbox: PaymentWebhookEvent) -> PaymentWebhookEvent:
        inbox_id, business_id = inbox.id, inbox.business_id
        attempts = inbox.attempt_count + 1
        event = _event_from_summary(inbox)
        try:
            status, note, intent_id = self._apply_event(business_id, inbox, event)
            inbox.status = status
            inbox.last_error = note
            inbox.payment_intent_id = intent_id
            inbox.attempt_count = attempts
            inbox.processed_at = self.clock()
            self._commit()
            return inbox
        except Exception as error:  # transient: record, keep retryable, never re-raise payload details
            self.db.rollback()
            failed = self.db.scalar(select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.id == inbox_id, PaymentWebhookEvent.business_id == business_id))
            failed.status = WebhookProcessingStatus.FAILED
            failed.attempt_count = attempts
            failed.last_error = safe_error_message(error, 500)
            self.db.commit()
            logger.warning("payment webhook %s failed (attempt %s): %s", inbox_id, attempts, type(error).__name__)
            return failed

    def _apply_event(self, business_id: str, inbox: PaymentWebhookEvent,
                     event: VerifiedProviderEvent) -> tuple[WebhookProcessingStatus, str | None, str | None]:
        intent = self.db.scalar(
            select(PaymentIntent).where(
                PaymentIntent.business_id == business_id,
                PaymentIntent.provider == inbox.provider,
                PaymentIntent.provider_payment_id == event.provider_payment_id,
            ).with_for_update().execution_options(populate_existing=True)
        )
        if intent is None:
            return WebhookProcessingStatus.IGNORED, "No payment of this business matches the event", None
        audit = {"webhook_event_id": inbox.id}

        if event.event_type in (ProviderEventType.REFUND_SUCCEEDED, ProviderEventType.REFUND_FAILED):
            refund = self.db.scalar(select(PaymentRefund).where(
                PaymentRefund.business_id == business_id,
                PaymentRefund.payment_intent_id == intent.id,
                PaymentRefund.provider_refund_id == event.provider_refund_id,
            )) if event.provider_refund_id else None
            if refund is None:
                # Refunds created outside Sydney are not adopted automatically.
                return WebhookProcessingStatus.IGNORED, "Refund was not initiated through Sydney", intent.id
            try:
                if event.event_type == ProviderEventType.REFUND_SUCCEEDED:
                    self._complete_refund(refund, intent, AuditSource.PROVIDER_EVENT, **audit)
                else:
                    self._fail_refund(refund, intent, event.failure_reason, AuditSource.PROVIDER_EVENT, **audit)
            except InvalidTransitionError as error:
                return WebhookProcessingStatus.IGNORED, f"Out-of-order refund event: {error}", intent.id
            return WebhookProcessingStatus.PROCESSED, None, intent.id

        target = EVENT_TARGET_STATUS[event.event_type]
        if event.currency is not None and event.currency != intent.currency:
            return WebhookProcessingStatus.IGNORED, "Event currency does not match the payment", intent.id
        if target == PaymentStatus.CAPTURED:
            captured = event.amount_minor if event.amount_minor is not None else intent.amount_minor
            if isinstance(captured, bool) or not isinstance(captured, int) or not 0 < captured <= intent.amount_minor:
                return WebhookProcessingStatus.IGNORED, "Captured amount is not valid for this payment", intent.id
            if intent.captured_minor and captured != intent.captured_minor:
                return WebhookProcessingStatus.IGNORED, "Captured amount conflicts with the recorded capture", intent.id
        try:
            changed = self._transition(intent, target, AuditSource.PROVIDER_EVENT, **audit)
        except InvalidTransitionError as error:
            return WebhookProcessingStatus.IGNORED, f"Out-of-order event: {error}", intent.id
        if changed and target == PaymentStatus.CAPTURED:
            intent.captured_minor = captured
        return WebhookProcessingStatus.PROCESSED, None, intent.id


def _summarize(event: VerifiedProviderEvent) -> dict:
    """The only event data that is stored: normalized, whitelisted, size-bounded."""
    def short(value, limit=255):
        return None if value is None else str(value)[:limit]
    amount = event.amount_minor if isinstance(event.amount_minor, int) and not isinstance(event.amount_minor, bool) else None
    failure = short(event.failure_reason)
    if failure and contains_card_like_number(failure):
        failure = "[redacted]"
    return {
        "event_type": event.event_type.value,
        "occurred_at": event.occurred_at.isoformat(),
        "provider_payment_id": short(event.provider_payment_id),
        "amount_minor": amount,
        "currency": short(event.currency, 3),
        "provider_refund_id": short(event.provider_refund_id),
        "failure_reason": failure,
    }


def _event_from_summary(inbox: PaymentWebhookEvent) -> VerifiedProviderEvent:
    summary = inbox.payload_summary
    return VerifiedProviderEvent(
        provider_event_id=inbox.provider_event_id,
        event_type=ProviderEventType(summary["event_type"]),
        occurred_at=datetime.fromisoformat(summary["occurred_at"]),
        provider_payment_id=summary["provider_payment_id"],
        amount_minor=summary.get("amount_minor"),
        currency=summary.get("currency"),
        provider_refund_id=summary.get("provider_refund_id"),
        failure_reason=summary.get("failure_reason"),
    )
