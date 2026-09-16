import json
import logging
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.client_ip import is_ip_allowed, resolve_client_ip
from app.core.config import Settings, get_settings
from app.database import SessionLocal, get_db
from app.models.cardcom_credential import CardcomCredential
from app.models.integration_connection import IntegrationConnection
from app.models.provider_document_event import ProviderDocumentEvent, ProviderDocumentStatus
from app.models.sale import Sale
from app.models.webhook_event import WebhookEventFailureCategory
from app.schemas.webhooks import WebhookIngestResponse
from app.services.credential_encryption import CredentialDecryptionError, CredentialEncryptionNotConfigured, decrypt_credentials
from app.services.ingestion.cardcom_provider import (
    CardcomCredentials,
    CardcomPayloadError,
    CardcomUnsupportedOperationError,
    CardcomVerificationClient,
    CardcomVerificationError,
    extract_low_profile_id,
    parse_lowprofile_result,
)
from app.services.ingestion.grow_provider import (
    GrowPayloadError,
    is_grow_invoice_payload,
    parse_grow_event,
    parse_grow_invoice_event,
)
from app.services.ingestion.webhook_provider import WebhookPayloadError, parse_webhook_event
from app.services.ingestion.webhook_security import is_timestamp_fresh, verify_signature
from app.services.connection_secrets import ConnectionSigningNotConfigured, derive_connection_secret
from app.services.sale_service import ingest_payment_event, link_provider_document, try_match_pending_provider_document
from app.services.webhook_events import (
    mark_processing_failed,
    mark_processed,
    mark_rejected,
    mark_validation_failed,
    mark_verification_failed,
    record_received,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# 1 MB is generous for a JSON payment payload and well above anything Grow's
# documented examples show, while still bounding an unauthenticated request
# body before it's ever read into memory.
GROW_MAX_BODY_BYTES = 1024 * 1024
# Cardcom's raw webhook delivery is smaller still — we only ever read
# LowProfileId out of it (see cardcom_provider.py's module docstring).
CARDCOM_MAX_BODY_BYTES = 256 * 1024


async def _read_verified_body(request: Request, settings: Settings, secret: str) -> bytes:
    """Read a bounded request body and verify its timestamped HMAC."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from exc
        if declared_length < 0:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header")
        if declared_length > settings.webhook_max_body_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > settings.webhook_max_body_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")
    raw_body = bytes(body)

    signature = request.headers.get("x-signature")
    timestamp = request.headers.get("x-timestamp")
    if not signature or not timestamp:
        logger.info("webhook_rejected reason=missing_signature_headers")
        raise HTTPException(status_code=401, detail="Missing signature headers")
    if len(signature) != 64 or any(character not in "0123456789abcdefABCDEF" for character in signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    if len(timestamp) > 24:
        raise HTTPException(status_code=401, detail="Request timestamp is stale")
    if not is_timestamp_fresh(timestamp, tolerance_seconds=settings.webhook_timestamp_tolerance_seconds):
        logger.info("webhook_rejected reason=stale_timestamp")
        raise HTTPException(status_code=401, detail="Request timestamp is stale")
    if not verify_signature(secret, timestamp, raw_body, signature):
        logger.info("webhook_rejected reason=invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    return raw_body


async def _read_unsigned_body(request: Request, max_bytes: int) -> bytes:
    """For Grow: no signature to verify at all (see grow_provider.py's
    module docstring) — still bounded and streamed the same way."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from exc
        if declared_length < 0 or declared_length > max_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")
    return bytes(body)


def _parse_body(raw_body: bytes):
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Request body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")
    try:
        return payload, parse_webhook_event(payload)
    except WebhookPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/payments", response_model=WebhookIngestResponse)
async def ingest_payment(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebhookIngestResponse:
    if settings.app_environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    if not settings.webhook_signing_secret:
        # Fail closed, not open: an unconfigured secret must never be treated
        # as "signature verification disabled".
        raise HTTPException(status_code=503, detail="Webhook ingestion is not configured")

    raw_body = await _read_verified_body(request, settings, settings.webhook_signing_secret)
    _, event = _parse_body(raw_body)

    sale, created = ingest_payment_event(db, event)
    logger.info(
        "webhook_ingested provider=%s created=%s event_id_hash=%s",
        event.provider,
        created,
        hashlib.sha256(event.event_id.encode("utf-8")).hexdigest()[:12],
    )
    response.status_code = 201 if created else 200
    return WebhookIngestResponse(created=created, sale_id=sale.id)


@dataclass
class _ConnectionLookup:
    """Plain values extracted while the lookup session is still open — the
    ORM object itself must never be returned past its session's `with`
    block (SQLAlchemy expires instance state on close, so touching an
    attribute afterward would either raise or silently re-open a session)."""

    id: str
    provider: str
    business_id: str
    enabled: bool
    secret_salt: str


def _resolve_connection(path_value: str) -> _ConnectionLookup | None:
    """Looked up either by `id` (demo-pay's stable webhook path) or by
    `url_token` (a URL-token provider like Grow — see
    IntegrationConnection's docstring). Tries a UUID-shaped id first purely
    as an optimization; either lookup is otherwise equally valid."""
    with SessionLocal() as lookup_db:
        try:
            normalized_id = str(uuid.UUID(path_value))
        except ValueError:
            normalized_id = None
        connection = None
        if normalized_id is not None:
            connection = lookup_db.get(IntegrationConnection, normalized_id)
        if connection is None:
            connection = lookup_db.scalar(
                select(IntegrationConnection).where(IntegrationConnection.url_token == path_value)
            )
        if connection is None:
            return None
        return _ConnectionLookup(
            id=connection.id,
            provider=connection.provider,
            business_id=connection.business_id,
            enabled=connection.enabled,
            secret_salt=connection.secret_salt,
        )


@router.post("/connections/{path_value}", response_model=WebhookIngestResponse)
async def ingest_connection_payment(
    path_value: str,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> WebhookIngestResponse:
    """Receive a signed (demo-pay) or unsigned (grow) event and route it to
    the connection's business. One response for missing/disabled/wrong-
    environment connections in every case below, so this endpoint can never
    be used to enumerate valid business connections."""
    connection = _resolve_connection(path_value)
    if connection is None or not connection.enabled:
        raise HTTPException(status_code=404, detail="Connection not found")

    provider = connection.provider
    business_id = connection.business_id
    connection_id = connection.id

    if settings.app_environment == "production" and provider == "demo-pay":
        raise HTTPException(status_code=404, detail="Connection not found")

    if provider == "grow":
        return await _ingest_grow_event(request, response, settings, connection_id=connection_id, business_id=business_id)

    if provider == "cardcom":
        return await _ingest_cardcom_event(request, response, settings, connection_id=connection_id, business_id=business_id)

    # demo-pay: existing HMAC-signed flow, unchanged.
    try:
        secret = derive_connection_secret(settings, connection.id, connection.secret_salt)
    except ConnectionSigningNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Webhook ingestion is not configured") from exc
    raw_body = await _read_verified_body(request, settings, secret)
    payload, event = _parse_body(raw_body)
    if payload.get("provider") != provider:
        raise HTTPException(status_code=422, detail="Webhook provider does not match this connection")

    with SessionLocal() as db:
        # Re-check after signature verification so a concurrent disable or
        # rotation takes effect before any sale is accepted.
        fresh = db.get(IntegrationConnection, connection_id)
        if fresh is None or not fresh.enabled or fresh.secret_salt != connection.secret_salt:
            raise HTTPException(status_code=404, detail="Connection not found")
        db.info["business_id"] = business_id
        # Namespacing the provider by connection prevents collisions if one
        # business connects two tills that reuse the same transaction IDs.
        event.provider = f"{provider}:{connection_id}"
        sale, created = ingest_payment_event(db, event)
        fresh.last_event_at = datetime.utcnow()
        db.commit()
        logger.info(
            "connection_webhook_ingested connection_id=%s provider=%s created=%s event_id_hash=%s",
            connection_id,
            f"{provider}:{connection_id}",
            created,
            hashlib.sha256(event.event_id.encode("utf-8")).hexdigest()[:12],
        )
        response.status_code = 201 if created else 200
        return WebhookIngestResponse(created=created, sale_id=sale.id)


async def _ingest_grow_event(
    request: Request, response: Response, settings: Settings, *, connection_id: str, business_id: str
) -> WebhookIngestResponse:
    """Grow has no signing capability at all — `webhookKey` is confirmed by
    Grow not to be a secret. The connecting source IP is the only
    application-layer defense; see app/core/client_ip.py and
    app/core/config.py's `grow_webhook_allowed_ips` (production refuses to
    start with this unset). Development never enforces it, so local testing
    doesn't need to spoof a Grow IP.
    """
    if settings.app_environment == "production":
        client_ip = resolve_client_ip(request)
        if not is_ip_allowed(client_ip, settings.grow_webhook_allowed_ips):
            logger.info("grow_webhook_rejected reason=ip_not_allowed")
            raise HTTPException(status_code=403, detail="Source not allowed")

    content_type = request.headers.get("content-type", "")
    if not content_type.split(";")[0].strip().lower() == "application/json":
        raise HTTPException(status_code=415, detail="Content-Type must be application/json")

    raw_body = await _read_unsigned_body(request, GROW_MAX_BODY_BYTES)
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Request body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")

    # Grow sends both the payment webhook and its separate "Invoice
    # creation" webhook to the same connection URL — discriminate by
    # validated shape (see is_grow_invoice_payload) and never try to parse
    # one as the other.
    if is_grow_invoice_payload(payload):
        return _ingest_grow_invoice_event(response, payload, connection_id=connection_id, business_id=business_id)

    # Best-effort id for the durable-receipt row, read defensively — a
    # malformed payload may not even have this field, and that's fine: the
    # row is still recorded, just without an id to log/display.
    provider_event_id = payload.get("transactionCode") if isinstance(payload.get("transactionCode"), str) else None

    with SessionLocal() as db:
        db.info["business_id"] = business_id
        connection = db.get(IntegrationConnection, connection_id)
        if connection is None or not connection.enabled:
            # A concurrent disable/delete since the outer lookup — still
            # respond identically to "not found" for the same reason as above.
            raise HTTPException(status_code=404, detail="Connection not found")

        webhook_event = record_received(db, connection=connection, provider_event_id=provider_event_id)

        try:
            payment_event = parse_grow_event(payload)
        except GrowPayloadError as exc:
            category = (
                WebhookEventFailureCategory.UNSUPPORTED_STATUS
                if "paymentType" in str(exc)
                else WebhookEventFailureCategory.VALIDATION
            )
            mark_validation_failed(db, webhook_event, category=category, message=str(exc))
            raise HTTPException(status_code=422, detail="Payload could not be processed") from exc

        payment_event.provider = f"grow:{connection_id}"
        try:
            sale, created = ingest_payment_event(db, payment_event)
        except Exception as exc:  # noqa: BLE001 - durably recorded, never crashes the request into an opaque 500
            # ingest_payment_event may leave the session mid-transaction on
            # an unexpected failure — roll back first so the durable-status
            # update below always applies cleanly, regardless of what state
            # the failed attempt left the session in.
            db.rollback()
            mark_processing_failed(db, webhook_event, payment_event=payment_event, error=exc)
            logger.warning("grow_webhook_processing_failed connection_id=%s error_category=%s", connection_id, type(exc).__name__)
            # Durably received, so still acknowledge — Grow does not retry,
            # and a 5xx would teach nothing since there is no redelivery.
            # The event is safely reprocessable from the owner's connection
            # activity view.
            response.status_code = 202
            return WebhookIngestResponse(created=False, sale_id=None, event_id=webhook_event.id)

        if created:
            # The invoice event for this same transaction may have already
            # arrived (Grow does not guarantee ordering between the two
            # webhooks) and been durably queued — link it now.
            try_match_pending_provider_document(db, sale=sale, connection_id=connection_id)

        mark_processed(db, webhook_event, payment_event=payment_event, created=created, sale_id=sale.id)
        connection.last_event_at = datetime.utcnow()
        db.commit()
        logger.info(
            "connection_webhook_ingested connection_id=%s provider=grow:%s created=%s event_id_hash=%s",
            connection_id,
            connection_id,
            created,
            hashlib.sha256(payment_event.external_transaction_id.encode("utf-8")).hexdigest()[:12],
        )
        response.status_code = 201 if created else 200
        return WebhookIngestResponse(created=created, sale_id=sale.id, event_id=webhook_event.id)


def _ingest_grow_invoice_event(
    response: Response, payload: dict, *, connection_id: str, business_id: str
) -> WebhookIngestResponse:
    """Grow's separate "Invoice creation" webhook — may arrive before or
    after the payment webhook for the same transaction (see
    _ingest_grow_event above), so both orderings are handled here:

    - If the matching Sale already exists, the document is attached
      immediately.
    - If it doesn't yet, a `ProviderDocumentEvent` row durably queues it
      (`pending_match`) — `try_match_pending_provider_document` consumes it
      the moment the payment webhook later creates the Sale.

    Idempotent by (connection_id, external_transaction_id) — a duplicate
    delivery for a transaction already recorded here is recognized before
    any write and never creates a second row or a second document-issued
    event."""
    with SessionLocal() as db:
        db.info["business_id"] = business_id
        connection = db.get(IntegrationConnection, connection_id)
        if connection is None or not connection.enabled:
            raise HTTPException(status_code=404, detail="Connection not found")

        try:
            invoice_event = parse_grow_invoice_event(payload)
        except GrowPayloadError as exc:
            provider_event_id = (
                payload.get("transactionCode") if isinstance(payload.get("transactionCode"), str) else None
            )
            webhook_event = record_received(db, connection=connection, provider_event_id=provider_event_id)
            mark_validation_failed(db, webhook_event, category=WebhookEventFailureCategory.VALIDATION, message=str(exc))
            raise HTTPException(status_code=422, detail="Payload could not be processed") from exc

        existing = db.scalar(
            select(ProviderDocumentEvent).where(
                ProviderDocumentEvent.connection_id == connection_id,
                ProviderDocumentEvent.external_transaction_id == invoice_event.transaction_code,
            )
        )
        if existing is not None:
            logger.info("grow_invoice_duplicate connection_id=%s", connection_id)
            response.status_code = 200
            return WebhookIngestResponse(created=False, sale_id=existing.matched_sale_id)

        # Scoped to this business (tenant-scoped session) and this exact
        # connection — a Grow transactionCode can never match a sale from a
        # different business or a different connection of the same provider.
        sale = db.scalar(
            select(Sale).where(
                Sale.source_provider == f"grow:{connection_id}",
                Sale.external_id == invoice_event.transaction_code,
            )
        )

        doc_event = ProviderDocumentEvent(
            connection_id=connection_id,
            provider="grow",
            external_transaction_id=invoice_event.transaction_code,
            document_number=invoice_event.invoice_number,
            document_url=invoice_event.invoice_url,
        )
        db.add(doc_event)
        connection.last_event_at = datetime.utcnow()

        if sale is not None:
            link_provider_document(db, sale=sale, document_event=doc_event)
            db.commit()
            logger.info("grow_invoice_matched connection_id=%s", connection_id)
            response.status_code = 200
            return WebhookIngestResponse(created=False, sale_id=sale.id)

        db.commit()
        logger.info("grow_invoice_queued connection_id=%s", connection_id)
        response.status_code = 202
        return WebhookIngestResponse(created=False, sale_id=None)


def _extract_cardcom_payload(raw_body: bytes, content_type: str) -> dict:
    """Cardcom's own documentation shows both JSON and form-encoded (Name To
    Value / APILevel 10) webhook formats across its different callback
    types — explicit handling for each, never a single assumed shape."""
    base_type = content_type.split(";")[0].strip().lower()
    if base_type == "application/json":
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="Request body is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")
        return payload
    if base_type == "application/x-www-form-urlencoded":
        try:
            text = raw_body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="Request body is not valid form data") from exc
        return dict(parse_qsl(text, keep_blank_values=True))
    raise HTTPException(status_code=415, detail="Content-Type must be application/json or application/x-www-form-urlencoded")


async def _ingest_cardcom_event(
    request: Request, response: Response, settings: Settings, *, connection_id: str, business_id: str
) -> WebhookIngestResponse:
    """Cardcom's own documentation explicitly forbids trusting the raw
    webhook delivery — every field this handler ultimately acts on comes
    from a separate, authenticated server-to-server call
    (`LowProfile/GetLpResult`), never the request body itself. See
    app/services/ingestion/cardcom_provider.py's module docstring.

    Cardcom also actively retries a delivery up to 7 times (over ~25 hours)
    whenever it doesn't receive HTTP 200 — every path below returns 200/201
    once a delivery is durably recorded, precisely so a single successfully
    *received* delivery never triggers a needless retry storm, while
    idempotency (the business-scoped `(source_provider, external_id)`
    uniqueness constraint) makes any redelivery Cardcom does send safe.
    """
    with SessionLocal() as db:
        db.info["business_id"] = business_id
        connection = db.get(IntegrationConnection, connection_id)
        if connection is None or not connection.enabled:
            raise HTTPException(status_code=404, detail="Connection not found")

        webhook_event = record_received(db, connection=connection, provider_event_id=None)

        if settings.app_environment == "production":
            client_ip = resolve_client_ip(request)
            if not is_ip_allowed(client_ip, settings.cardcom_webhook_allowed_ips):
                mark_rejected(db, webhook_event, category=WebhookEventFailureCategory.IP_NOT_ALLOWED, message="source IP not on the Cardcom allowlist")
                logger.info("cardcom_webhook_rejected reason=ip_not_allowed")
                raise HTTPException(status_code=403, detail="Source not allowed")

        content_type = request.headers.get("content-type", "")
        try:
            raw_body = await _read_unsigned_body(request, CARDCOM_MAX_BODY_BYTES)
            # Cardcom uses both body-based API v11 callbacks and legacy
            # Name-To-Value callbacks that put LowProfileCode in the query
            # string. Only this reference is consumed, and the financial
            # result is still fetched directly from Cardcom afterward.
            query_payload = dict(request.query_params)
            if raw_body:
                payload = {**query_payload, **_extract_cardcom_payload(raw_body, content_type)}
            else:
                payload = query_payload
            low_profile_id = extract_low_profile_id(payload)
        except HTTPException as exc:
            mark_rejected(db, webhook_event, category=WebhookEventFailureCategory.VALIDATION, message=str(exc.detail))
            raise
        except CardcomPayloadError as exc:
            mark_rejected(db, webhook_event, category=WebhookEventFailureCategory.VALIDATION, message=str(exc))
            raise HTTPException(status_code=422, detail="Payload could not be processed") from exc

        webhook_event.provider_event_id = low_profile_id
        db.commit()

        credential = db.get(CardcomCredential, connection_id)
        if credential is None:
            mark_verification_failed(db, webhook_event, low_profile_id=low_profile_id, message="no Cardcom credentials stored for this connection")
            logger.warning("cardcom_webhook_missing_credentials connection_id=%s", connection_id)
            response.status_code = 202
            return WebhookIngestResponse(created=False, sale_id=None, event_id=webhook_event.id)

        try:
            decrypted = decrypt_credentials(settings, credential.encrypted_credentials)
        except (CredentialEncryptionNotConfigured, CredentialDecryptionError) as exc:
            mark_verification_failed(db, webhook_event, low_profile_id=low_profile_id, message=type(exc).__name__)
            logger.error("cardcom_webhook_credential_error connection_id=%s error_category=%s", connection_id, type(exc).__name__)
            response.status_code = 202
            return WebhookIngestResponse(created=False, sale_id=None, event_id=webhook_event.id)

        client = CardcomVerificationClient(
            base_url=settings.cardcom_api_base_url, timeout_seconds=settings.cardcom_api_timeout_seconds
        )
        credentials = CardcomCredentials(
            terminal_number=credential.terminal_number, api_name=decrypted["api_name"], api_password=decrypted.get("api_password")
        )
        try:
            result = client.get_lowprofile_result(credentials, low_profile_id)
            payment_event = parse_lowprofile_result(result)
        except CardcomUnsupportedOperationError as exc:
            # A real, verified response, but for an operation that never
            # moves money (e.g. CreateTokenOnly) — out of scope, not
            # reprocessable, never a sale either way.
            mark_validation_failed(db, webhook_event, category=WebhookEventFailureCategory.UNSUPPORTED_STATUS, message=str(exc))
            response.status_code = 200
            return WebhookIngestResponse(created=False, sale_id=None, event_id=webhook_event.id)
        except CardcomVerificationError as exc:
            # Could not verify at all (network error, Cardcom-side error, or
            # a transaction not yet resolvable) — genuinely retryable.
            mark_verification_failed(db, webhook_event, low_profile_id=low_profile_id, message=str(exc))
            logger.warning("cardcom_webhook_verification_failed connection_id=%s error_category=%s", connection_id, type(exc).__name__)
            response.status_code = 202
            return WebhookIngestResponse(created=False, sale_id=None, event_id=webhook_event.id)

        payment_event.provider = f"cardcom:{connection_id}"
        try:
            sale, created = ingest_payment_event(db, payment_event)
        except Exception as exc:  # noqa: BLE001 - durably recorded, never crashes the request into an opaque 500
            db.rollback()
            mark_processing_failed(db, webhook_event, payment_event=payment_event, error=exc)
            logger.warning("cardcom_webhook_processing_failed connection_id=%s error_category=%s", connection_id, type(exc).__name__)
            response.status_code = 202
            return WebhookIngestResponse(created=False, sale_id=None, event_id=webhook_event.id)

        mark_processed(db, webhook_event, payment_event=payment_event, created=created, sale_id=sale.id)
        connection.last_event_at = datetime.utcnow()
        db.commit()
        logger.info(
            "connection_webhook_ingested connection_id=%s provider=cardcom:%s created=%s sale_status=%s event_id_hash=%s",
            connection_id,
            connection_id,
            created,
            payment_event.status.value,
            hashlib.sha256(payment_event.external_transaction_id.encode("utf-8")).hexdigest()[:12],
        )
        response.status_code = 201 if created else 200
        return WebhookIngestResponse(created=created, sale_id=sale.id, event_id=webhook_event.id)
