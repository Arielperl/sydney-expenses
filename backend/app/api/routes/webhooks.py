import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database import get_db
from app.schemas.webhooks import WebhookIngestResponse
from app.services.ingestion.transaction_ingest import ingest_transaction_event
from app.services.ingestion.webhook_provider import WebhookPayloadError, parse_webhook_event
from app.services.ingestion.webhook_security import is_timestamp_fresh, verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/transactions", response_model=WebhookIngestResponse)
async def ingest_transaction(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebhookIngestResponse:
    if not settings.webhook_signing_secret:
        # Fail closed, not open: an unconfigured secret must never be treated
        # as "signature verification disabled".
        raise HTTPException(status_code=503, detail="Webhook ingestion is not configured")

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > settings.webhook_max_body_bytes:
        raise HTTPException(status_code=413, detail="Request body too large")

    raw_body = await request.body()
    if len(raw_body) > settings.webhook_max_body_bytes:
        raise HTTPException(status_code=413, detail="Request body too large")

    signature = request.headers.get("x-signature")
    timestamp = request.headers.get("x-timestamp")
    if not signature or not timestamp:
        # Never log the payload/signature/secret — only that verification failed.
        logger.info("webhook_rejected reason=missing_signature_headers")
        raise HTTPException(status_code=401, detail="Missing signature headers")

    if not is_timestamp_fresh(timestamp, tolerance_seconds=settings.webhook_timestamp_tolerance_seconds):
        logger.info("webhook_rejected reason=stale_timestamp")
        raise HTTPException(status_code=401, detail="Request timestamp is stale")

    if not verify_signature(settings.webhook_signing_secret, timestamp, raw_body, signature):
        logger.info("webhook_rejected reason=invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Request body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")

    try:
        event = parse_webhook_event(payload)
    except WebhookPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    expense, created = ingest_transaction_event(db, event)
    logger.info(
        "webhook_ingested provider=%s created=%s event_id=%s",
        event.provider,
        created,
        event.event_id,
    )
    response.status_code = 201 if created else 200
    return WebhookIngestResponse(created=created, expense_id=expense.id)
