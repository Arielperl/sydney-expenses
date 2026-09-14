import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.business import BusinessOwned


class WebhookEventStatus(str, enum.Enum):
    """A provider like Grow (or Cardcom, which actively retries) needs a
    durable record of what happened to one delivery, independent of whether
    a `Sale` was ever created for it. See webhooks.py's
    `ingest_connection_payment` for how each status is reached.

    `PROCESSED` covers a Cardcom *decline* too — a decline that was
    correctly verified and recorded as a failed-status `Sale` is a
    successfully processed delivery, not a webhook-event-level failure.
    `REJECTED` is for a delivery refused at the gate, before any real
    processing was attempted (e.g. a disallowed source IP, or a malformed/
    wrong-content-type body) — distinct from `FAILED`, which means
    processing was genuinely attempted and hit a technical failure."""

    RECEIVED = "received"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    FAILED = "failed"
    REJECTED = "rejected"


class WebhookEventFailureCategory(str, enum.Enum):
    """Distinguishes a permanently-unprocessable delivery (bad/unsupported
    payload — never safely retryable, the owner should re-enter it via CSV
    import) from a transient failure after the payload was already validated
    and normalized (safely retryable — see `normalized_*` columns below and
    the `/reprocess` endpoint)."""

    VALIDATION = "validation"
    UNSUPPORTED_STATUS = "unsupported_status"
    PROCESSING_ERROR = "processing_error"
    # Cardcom-specific: the gate-level rejection reason (REJECTED status),
    # and a failed server-to-server verification call (FAILED status,
    # reprocessable by re-calling Cardcom's verification API — see
    # app/services/ingestion/cardcom_provider.py).
    IP_NOT_ALLOWED = "ip_not_allowed"
    VERIFICATION_FAILED = "verification_failed"


class WebhookEvent(BusinessOwned, Base):
    """A durable inbox row for one inbound connection-webhook delivery,
    written before any Sale is created. Exists specifically because Grow
    (and providers like it) never retry a failed delivery: without a durable
    record made *before* Sale creation is even attempted, a delivery that
    fails partway through would be lost with no trace and no way to safely
    reprocess it.

    Deliberately does not store the raw provider payload, card/token data, or
    full customer PII — see the module docstring in
    app/services/ingestion/grow_provider.py. When a payload was successfully
    validated and normalized but a later step failed (a transient
    `processing_error`), the `normalized_*` columns hold just enough of that
    already-validated data to retry Sale creation later; a `validation` or
    `unsupported_status` failure never populates them, because that payload
    was never safe/parseable in the first place and is not retryable — the
    owner re-enters it via CSV import instead.
    """

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    # Not always resolvable — a delivery that fails before the adapter can
    # even read a transaction identifier out of the payload leaves this null.
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    status: Mapped[WebhookEventStatus] = mapped_column(
        Enum(WebhookEventStatus, native_enum=False), nullable=False, default=WebhookEventStatus.RECEIVED
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sale_id: Mapped[str | None] = mapped_column(ForeignKey("sales.id"), nullable=True)

    failure_category: Mapped[WebhookEventFailureCategory | None] = mapped_column(
        Enum(WebhookEventFailureCategory, native_enum=False), nullable=True
    )
    # A short, safe diagnostic (e.g. "unsupported paymentType: הוראת קבע") —
    # never a raw payload, card number, email, phone, or webhookKey.
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Minimum normalized fields — see class docstring. Never card/token data.
    # Stored as an exact replay of what the adapter already validated and
    # computed (including VAT), not recomputed on reprocess — a reprocess
    # attempt must reproduce exactly the sale that would have been created
    # the first time, never a second, possibly-drifted calculation of it.
    normalized_customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_customer_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_service_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    normalized_vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    normalized_tax_treatment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    normalized_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    normalized_occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    normalized_external_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
