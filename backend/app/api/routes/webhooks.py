import json
import logging
import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database import SessionLocal, get_db
from app.models.integration_connection import IntegrationConnection
from app.schemas.webhooks import WebhookIngestResponse
from app.services.ingestion.webhook_provider import WebhookPayloadError, parse_webhook_event
from app.services.ingestion.webhook_security import is_timestamp_fresh, verify_signature
from app.services.connection_secrets import ConnectionSigningNotConfigured, derive_connection_secret
from app.services.sale_service import ingest_payment_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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


@router.post("/connections/{connection_id}", response_model=WebhookIngestResponse)
async def ingest_connection_payment(
    connection_id: str,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> WebhookIngestResponse:
    """Receive a signed event and route it to the connection's business."""
    try:
        normalized_id = str(uuid.UUID(connection_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc

    with SessionLocal() as lookup_db:
        connection = lookup_db.get(IntegrationConnection, normalized_id)
        if connection is None or not connection.enabled:
            # Use one response for missing and disabled endpoints so callers
            # cannot use this API to enumerate valid business connections.
            raise HTTPException(status_code=404, detail="Connection not found")
        try:
            secret = derive_connection_secret(settings, connection.id, connection.secret_salt)
        except ConnectionSigningNotConfigured as exc:
            raise HTTPException(status_code=503, detail="Webhook ingestion is not configured") from exc
        business_id = connection.business_id
        expected_salt = connection.secret_salt
        provider = connection.provider

    raw_body = await _read_verified_body(request, settings, secret)
    payload, event = _parse_body(raw_body)
    if payload.get("provider") != provider:
        raise HTTPException(status_code=422, detail="Webhook provider does not match this connection")

    with SessionLocal() as db:
        # Re-check after signature verification so a concurrent disable or
        # rotation takes effect before any sale is accepted.
        connection = db.get(IntegrationConnection, normalized_id)
        if connection is None or not connection.enabled or connection.secret_salt != expected_salt:
            raise HTTPException(status_code=404, detail="Connection not found")
        db.info["business_id"] = business_id
        # Namespacing the provider by connection prevents collisions if one
        # business connects two tills that reuse the same transaction IDs.
        event.provider = f"{provider}:{connection.id}"
        sale, created = ingest_payment_event(db, event)
        connection.last_event_at = datetime.utcnow()
        db.commit()
        logger.info(
            "connection_webhook_ingested connection_id=%s provider=%s created=%s event_id_hash=%s",
            connection.id,
            connection.provider,
            created,
            hashlib.sha256(event.event_id.encode("utf-8")).hexdigest()[:12],
        )
        response.status_code = 201 if created else 200
        return WebhookIngestResponse(created=created, sale_id=sale.id)
