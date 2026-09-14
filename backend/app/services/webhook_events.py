"""The durable webhook-event inbox: recording a delivery before/around Sale
creation, and safely reprocessing one that failed after being durably
received. See app/models/webhook_event.py for why this exists at all
(Grow never retries a failed delivery; Cardcom does retry, but its own
webhook payload is never trusted without a separate verification call that
can itself fail transiently — see app/services/ingestion/cardcom_provider.py).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.cardcom_credential import CardcomCredential
from app.models.integration_connection import IntegrationConnection
from app.models.sale import SaleStatus, TaxTreatment
from app.models.webhook_event import WebhookEvent, WebhookEventFailureCategory, WebhookEventStatus
from app.services.credential_encryption import CredentialDecryptionError, CredentialEncryptionNotConfigured, decrypt_credentials
from app.services.ingestion.cardcom_provider import (
    CardcomCredentials,
    CardcomUnsupportedOperationError,
    CardcomVerificationClient,
    CardcomVerificationError,
    parse_lowprofile_result,
)
from app.services.sale_service import PaymentEvent, ingest_payment_event

# A FAILED event is safely reprocessable only when the original attempt got
# far enough to leave us something trustworthy to retry: Grow's
# already-validated/normalized fields (PROCESSING_ERROR), or Cardcom's own
# LowProfileId to re-verify (VERIFICATION_FAILED). VALIDATION and
# UNSUPPORTED_STATUS are never reprocessable — see WebhookEvent's docstring.
REPROCESSABLE_FAILURE_CATEGORIES = {
    WebhookEventFailureCategory.PROCESSING_ERROR,
    WebhookEventFailureCategory.VERIFICATION_FAILED,
}


class ReprocessNotAllowedError(Exception):
    pass


def record_received(db: Session, *, connection: IntegrationConnection, provider_event_id: str | None) -> WebhookEvent:
    """Step 1: durable receipt, before any Sale is attempted. Committed
    immediately so it survives even if the process is interrupted before
    Sale creation completes."""
    event = WebhookEvent(
        connection_id=connection.id,
        provider=connection.provider,
        provider_event_id=provider_event_id,
        received_at=datetime.utcnow(),
        status=WebhookEventStatus.RECEIVED,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def mark_rejected(
    db: Session, event: WebhookEvent, *, category: WebhookEventFailureCategory, message: str
) -> WebhookEvent:
    """A delivery refused at the gate (disallowed source IP, malformed body)
    — never reached real processing at all. Distinct from `FAILED`, which
    means processing was genuinely attempted."""
    event.status = WebhookEventStatus.REJECTED
    event.failure_category = category
    event.failure_message = message
    event.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    return event


def mark_validation_failed(
    db: Session, event: WebhookEvent, *, category: WebhookEventFailureCategory, message: str
) -> WebhookEvent:
    """A payload that failed before/without ever producing a normalized,
    storable event — not retryable (see class docstring on WebhookEvent);
    the owner re-enters it via CSV import instead."""
    event.status = WebhookEventStatus.FAILED
    event.failure_category = category
    event.failure_message = message
    event.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    return event


def mark_verification_failed(db: Session, event: WebhookEvent, *, low_profile_id: str, message: str) -> WebhookEvent:
    """Cardcom's own GetLpResult verification call failed (network error,
    Cardcom-side error, or a transaction not yet resolvable) — genuinely
    retryable by calling GetLpResult again later. `low_profile_id` is stored
    in `normalized_external_transaction_id` purely as the key to retry
    with — it is not itself a verified/trusted value."""
    event.status = WebhookEventStatus.FAILED
    event.failure_category = WebhookEventFailureCategory.VERIFICATION_FAILED
    event.failure_message = message
    event.processed_at = datetime.utcnow()
    event.normalized_external_transaction_id = low_profile_id
    db.commit()
    db.refresh(event)
    return event


def mark_processed(db: Session, event: WebhookEvent, *, payment_event: PaymentEvent, created: bool, sale_id: str) -> WebhookEvent:
    event.status = WebhookEventStatus.PROCESSED if created else WebhookEventStatus.DUPLICATE
    event.sale_id = sale_id
    event.processed_at = datetime.utcnow()
    event.provider_event_id = payment_event.external_transaction_id
    _store_normalized_fields(event, payment_event)
    db.commit()
    db.refresh(event)
    return event


def mark_processing_failed(db: Session, event: WebhookEvent, *, payment_event: PaymentEvent, error: Exception) -> WebhookEvent:
    """The payload WAS successfully validated/normalized (so it's safe to
    retry later), but something failed while actually creating the Sale —
    e.g. a transient database error. The normalized fields are stored so
    `/reprocess` can replay exactly this same event."""
    event.status = WebhookEventStatus.FAILED
    event.failure_category = WebhookEventFailureCategory.PROCESSING_ERROR
    event.failure_message = f"{type(error).__name__} during sale creation"
    event.processed_at = datetime.utcnow()
    event.provider_event_id = payment_event.external_transaction_id
    _store_normalized_fields(event, payment_event)
    db.commit()
    db.refresh(event)
    return event


def _store_normalized_fields(event: WebhookEvent, payment_event: PaymentEvent) -> None:
    event.normalized_customer_name = payment_event.customer_name
    event.normalized_customer_contact = payment_event.customer_email
    event.normalized_service_name = payment_event.service_name
    event.normalized_description = payment_event.description
    event.normalized_gross_amount = payment_event.gross_amount
    event.normalized_vat_amount = payment_event.vat_amount
    event.normalized_tax_treatment = payment_event.tax_treatment.value if payment_event.tax_treatment else None
    event.normalized_currency = payment_event.currency
    event.normalized_occurred_at = payment_event.occurred_at
    event.normalized_external_transaction_id = payment_event.external_transaction_id


def _replay_normalized_event(db: Session, event: WebhookEvent, *, connection: IntegrationConnection):
    """Grow (and any future normalized-replay provider): re-attempts Sale
    creation using exactly the fields already validated and normalized the
    first time — never re-parses the original payload (never retained at
    all) and never recomputes VAT, so this can only reproduce the same
    sale, not a drifted one."""
    if not event.normalized_gross_amount or not event.normalized_occurred_at or not event.normalized_external_transaction_id:
        raise ReprocessNotAllowedError("לא נשמרו נתונים מספיקים לניסיון חוזר עבור אירוע זה")

    payment_event = PaymentEvent(
        event_id=event.normalized_external_transaction_id,
        provider=connection.provider,
        external_transaction_id=event.normalized_external_transaction_id,
        occurred_at=event.normalized_occurred_at,
        customer_name=event.normalized_customer_name or "",
        customer_email=event.normalized_customer_contact,
        service_name=event.normalized_service_name or "",
        gross_amount=event.normalized_gross_amount,
        vat_amount=event.normalized_vat_amount,
        processing_fee=None,
        net_amount=None,
        currency=event.normalized_currency or "ILS",
        payment_method="card",
        status=SaleStatus.SUCCEEDED,
        tax_treatment=TaxTreatment(event.normalized_tax_treatment) if event.normalized_tax_treatment else TaxTreatment.STANDARD,
        vat_rate=None,
        description=event.normalized_description,
    )
    payment_event.provider = f"{connection.provider}:{connection.id}"
    sale, created = ingest_payment_event(db, payment_event)
    mark_processed(db, event, payment_event=payment_event, created=created, sale_id=sale.id)
    return sale


def _reverify_cardcom_event(db: Session, event: WebhookEvent, *, connection: IntegrationConnection, settings: Settings):
    """Cardcom: re-runs the *entire* server-to-server verification, since a
    `verification_failed` event never had a trustworthy result to replay in
    the first place — only the raw `LowProfileId` to look up again."""
    low_profile_id = event.normalized_external_transaction_id
    if not low_profile_id:
        raise ReprocessNotAllowedError("לא נשמר מזהה עסקה לניסיון אימות חוזר")

    credential = db.get(CardcomCredential, connection.id)
    if credential is None:
        raise ReprocessNotAllowedError("לא נמצאו פרטי התחברות ל-Cardcom עבור חיבור זה")
    try:
        decrypted = decrypt_credentials(settings, credential.encrypted_credentials)
    except (CredentialEncryptionNotConfigured, CredentialDecryptionError) as exc:
        raise ReprocessNotAllowedError(str(exc)) from exc

    client = CardcomVerificationClient(base_url=settings.cardcom_api_base_url, timeout_seconds=settings.cardcom_api_timeout_seconds)
    credentials = CardcomCredentials(
        terminal_number=credential.terminal_number, api_name=decrypted["api_name"], api_password=decrypted.get("api_password")
    )
    try:
        result = client.get_lowprofile_result(credentials, low_profile_id)
        payment_event = parse_lowprofile_result(result)
    except CardcomUnsupportedOperationError as exc:
        mark_validation_failed(db, event, category=WebhookEventFailureCategory.UNSUPPORTED_STATUS, message=str(exc))
        raise ReprocessNotAllowedError(str(exc)) from exc
    except CardcomVerificationError as exc:
        mark_verification_failed(db, event, low_profile_id=low_profile_id, message=str(exc))
        raise ReprocessNotAllowedError(str(exc)) from exc

    payment_event.provider = f"cardcom:{connection.id}"
    sale, created = ingest_payment_event(db, payment_event)
    mark_processed(db, event, payment_event=payment_event, created=created, sale_id=sale.id)
    return sale


def reprocess_failed_event(db: Session, event: WebhookEvent, *, connection: IntegrationConnection, settings: Settings):
    """Dispatches to the right reprocessing strategy for `connection.provider`
    — see `_replay_normalized_event` (Grow: replay already-verified data) vs
    `_reverify_cardcom_event` (Cardcom: nothing was ever verified, so
    re-verify from scratch)."""
    if event.status != WebhookEventStatus.FAILED or event.failure_category not in REPROCESSABLE_FAILURE_CATEGORIES:
        raise ReprocessNotAllowedError("רק אירועים שנכשלו בעיבוד לאחר קליטה תקינה ניתנים לניסיון חוזר")

    if connection.provider == "cardcom":
        return _reverify_cardcom_event(db, event, connection=connection, settings=settings)
    return _replay_normalized_event(db, event, connection=connection)
