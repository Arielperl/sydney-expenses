import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database import get_db
from app.models.cardcom_credential import CardcomCredential
from app.models.integration_connection import IntegrationConnection
from app.models.webhook_event import WebhookEvent, WebhookEventFailureCategory, WebhookEventStatus
from app.schemas.connections import (
    ConnectionCreate,
    ConnectionEventCounts,
    ConnectionResponse,
    ConnectionSecretResponse,
    ConnectionUpdate,
)
from app.schemas.webhook_events import WebhookEventListResponse, WebhookEventRead
from app.services.connection_secrets import ConnectionSigningNotConfigured, derive_connection_secret, new_connection_salt
from app.services.credential_encryption import CredentialEncryptionNotConfigured, encrypt_credentials
from app.services.webhook_events import REPROCESSABLE_FAILURE_CATEGORIES, ReprocessNotAllowedError, reprocess_failed_event

router = APIRouter(prefix="/connections", tags=["connections"])

# Providers whose webhook URL is built from `url_token` (the URL itself is
# a credential/possession-barrier — see IntegrationConnection's docstring)
# rather than `id`. Cardcom is included even though its own server-to-server
# verification call is the real authentication — the unguessable URL is
# still explicit defense-in-depth (requirement: "a unique, unguessable
# webhook URL per connection"), never described as sufficient on its own.
URL_TOKEN_PROVIDERS = {"grow", "cardcom"}
# Providers allowed to be *created* in production. demo-pay stays a
# development/test-only fixture — never creatable, listed, or reachable via
# its webhook URL once APP_ENVIRONMENT=production (see webhooks.py for the
# webhook-ingestion side of this same rule).
PRODUCTION_ALLOWED_PROVIDERS = {"grow", "cardcom"}


def _require_owner(request: Request, settings: Settings) -> None:
    if settings.auth_required and getattr(request.state, "user", {}).get("role") != "owner":
        raise HTTPException(status_code=403, detail="רק בעל העסק יכול לנהל חיבורים")


def _visible_in_environment(provider: str, settings: Settings) -> bool:
    return settings.app_environment != "production" or provider in PRODUCTION_ALLOWED_PROVIDERS


def _require_visible(connection: IntegrationConnection, settings: Settings) -> None:
    if not _visible_in_environment(connection.provider, settings):
        raise HTTPException(status_code=404, detail="החיבור לא נמצא")


def _webhook_path(connection: IntegrationConnection) -> str:
    if connection.provider in URL_TOKEN_PROVIDERS and connection.url_token:
        return f"/api/webhooks/connections/{connection.url_token}"
    return f"/api/webhooks/connections/{connection.id}"


def _event_counts(db: Session, connection_id: str) -> ConnectionEventCounts:
    rows = db.execute(
        select(WebhookEvent.status, func.count())
        .where(WebhookEvent.connection_id == connection_id)
        .group_by(WebhookEvent.status)
    ).all()
    counts = {status.value: 0 for status in WebhookEventStatus}
    for status, count in rows:
        key = status.value if hasattr(status, "value") else status
        counts[key] = count
    return ConnectionEventCounts(**counts)


def _cardcom_terminal_number(db: Session, connection_id: str) -> str | None:
    credential = db.get(CardcomCredential, connection_id)
    return credential.terminal_number if credential else None


def _response(db: Session, connection: IntegrationConnection) -> ConnectionResponse:
    return ConnectionResponse(
        id=connection.id,
        provider=connection.provider,
        name=connection.name,
        enabled=connection.enabled,
        webhook_path=_webhook_path(connection),
        has_received_event=connection.last_event_at is not None,
        last_event_at=connection.last_event_at,
        created_at=connection.created_at,
        event_counts=_event_counts(db, connection.id),
        cardcom_terminal_number=_cardcom_terminal_number(db, connection.id) if connection.provider == "cardcom" else None,
    )


@router.get("", response_model=list[ConnectionResponse])
def list_connections(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> list[ConnectionResponse]:
    connections = db.scalars(select(IntegrationConnection).order_by(IntegrationConnection.created_at.desc())).all()
    return [_response(db, connection) for connection in connections if _visible_in_environment(connection.provider, settings)]


@router.post("", status_code=201, response_model=ConnectionSecretResponse)
def create_connection(
    payload: ConnectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionSecretResponse:
    _require_owner(request, settings)
    if not _visible_in_environment(payload.provider, settings):
        raise HTTPException(status_code=422, detail="ספק זה אינו זמין בסביבת הייצור")

    is_url_token_provider = payload.provider in URL_TOKEN_PROVIDERS
    connection = IntegrationConnection(
        provider=payload.provider,
        name=payload.name,
        secret_salt=new_connection_salt(),
        url_token=secrets.token_urlsafe(32) if is_url_token_provider else None,
    )
    db.add(connection)
    signing_secret: str | None = None
    try:
        db.flush()
        if payload.provider == "cardcom":
            # The owner's own real Cardcom terminal credentials — encrypted
            # at rest, never returned by this or any other response (see
            # app/services/credential_encryption.py and
            # app/models/cardcom_credential.py). Cardcom's documentation
            # defines no separate signing secret, so unlike demo-pay there
            # is nothing to show the owner here at all.
            encrypted = encrypt_credentials(
                settings,
                api_name=payload.cardcom_api_name,  # type: ignore[arg-type]
                api_password=payload.cardcom_api_password,
            )
            db.add(
                CardcomCredential(
                    connection_id=connection.id,
                    terminal_number=payload.cardcom_terminal_number,  # type: ignore[arg-type]
                    encrypted_credentials=encrypted,
                )
            )
        elif not is_url_token_provider:
            # Never displayed/requested for a URL-token provider like Grow —
            # it has no signing capability at all (see IntegrationConnection
            # and schemas/connections.py's ConnectionSecretResponse).
            signing_secret = derive_connection_secret(settings, connection.id, connection.secret_salt)
        db.commit()
        db.refresh(connection)
    except (ConnectionSigningNotConfigured, CredentialEncryptionNotConfigured) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="כבר קיים חיבור בשם הזה") from exc
    return ConnectionSecretResponse(**_response(db, connection).model_dump(), signing_secret=signing_secret)


@router.patch("/{connection_id}", response_model=ConnectionResponse)
def update_connection(
    connection_id: str,
    payload: ConnectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionResponse:
    _require_owner(request, settings)
    connection = db.get(IntegrationConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="החיבור לא נמצא")
    _require_visible(connection, settings)
    connection.enabled = payload.enabled
    db.commit()
    db.refresh(connection)
    return _response(db, connection)


@router.delete("/{connection_id}", status_code=204)
def delete_connection(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    _require_owner(request, settings)
    connection = db.get(IntegrationConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="החיבור לא נמצא")
    _require_visible(connection, settings)
    # Deleted explicitly, in application code, rather than relying on the
    # database's own ON DELETE CASCADE: SQLite (used in development and the
    # automated test suite) does not enforce foreign keys by default, so a
    # constraint that behaves correctly on the real production database
    # (PostgreSQL) could silently do nothing here — this way deleting a
    # connection's own activity log and stored credentials is correct on
    # every database this app runs on, not just production's.
    db.execute(delete(WebhookEvent).where(WebhookEvent.connection_id == connection_id))
    credential = db.get(CardcomCredential, connection_id)
    if credential is not None:
        db.delete(credential)
    db.delete(connection)
    db.commit()


@router.post("/{connection_id}/rotate-secret", response_model=ConnectionSecretResponse)
def rotate_connection_secret(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionSecretResponse:
    """demo-pay only — rotates the HMAC secret while keeping the same URL.
    Grow and Cardcom have no secret to rotate; see rotate_connection_url below."""
    _require_owner(request, settings)
    connection = db.get(IntegrationConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="החיבור לא נמצא")
    _require_visible(connection, settings)
    if connection.provider in URL_TOKEN_PROVIDERS:
        raise HTTPException(status_code=422, detail="לספק זה אין מפתח חתימה לסבב — יש לסבב את כתובת ה-Webhook")
    connection.secret_salt = new_connection_salt()
    try:
        signing_secret = derive_connection_secret(settings, connection.id, connection.secret_salt)
    except ConnectionSigningNotConfigured as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    db.refresh(connection)
    return ConnectionSecretResponse(**_response(db, connection).model_dump(), signing_secret=signing_secret)


@router.post("/{connection_id}/rotate-url", response_model=ConnectionResponse)
def rotate_connection_url(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionResponse:
    """Grow and Cardcom (any URL-token provider) — since there is no secret
    to rotate, "rotating" means issuing a new url_token and immediately
    invalidating the previous webhook URL. The connection's id, name,
    stored credentials (Cardcom), and activity history are all preserved."""
    _require_owner(request, settings)
    connection = db.get(IntegrationConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="החיבור לא נמצא")
    _require_visible(connection, settings)
    if connection.provider not in URL_TOKEN_PROVIDERS:
        raise HTTPException(status_code=422, detail="לספק זה יש מפתח חתימה לסבב, לא כתובת Webhook")
    connection.url_token = secrets.token_urlsafe(32)
    db.commit()
    db.refresh(connection)
    return _response(db, connection)


@router.get("/{connection_id}/events", response_model=WebhookEventListResponse)
def list_connection_events(
    connection_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebhookEventListResponse:
    _require_owner(request, settings)
    connection = db.get(IntegrationConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="החיבור לא נמצא")
    _require_visible(connection, settings)
    rows = db.scalars(
        select(WebhookEvent)
        .where(WebhookEvent.connection_id == connection_id)
        .order_by(WebhookEvent.received_at.desc())
        .limit(limit)
    ).all()
    events = [
        WebhookEventRead(
            id=row.id,
            status=row.status.value,
            received_at=row.received_at,
            processed_at=row.processed_at,
            failure_category=row.failure_category.value if row.failure_category else None,
            failure_message=row.failure_message,
            sale_id=row.sale_id,
            can_reprocess=(
                row.status == WebhookEventStatus.FAILED and row.failure_category in REPROCESSABLE_FAILURE_CATEGORIES
            ),
        )
        for row in rows
    ]
    return WebhookEventListResponse(events=events, counts=_event_counts(db, connection_id))


@router.post("/{connection_id}/events/{event_id}/reprocess", response_model=WebhookEventRead)
def reprocess_connection_event(
    connection_id: str,
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> WebhookEventRead:
    _require_owner(request, settings)
    connection = db.get(IntegrationConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="החיבור לא נמצא")
    _require_visible(connection, settings)
    event = db.get(WebhookEvent, event_id)
    if event is None or event.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="האירוע לא נמצא")
    try:
        reprocess_failed_event(db, event, connection=connection, settings=settings)
    except ReprocessNotAllowedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.refresh(event)
    return WebhookEventRead(
        id=event.id,
        status=event.status.value,
        received_at=event.received_at,
        processed_at=event.processed_at,
        failure_category=event.failure_category.value if event.failure_category else None,
        failure_message=event.failure_message,
        sale_id=event.sale_id,
        can_reprocess=False,
    )
