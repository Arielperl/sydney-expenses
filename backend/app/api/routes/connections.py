from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database import get_db
from app.models.integration_connection import IntegrationConnection
from app.schemas.connections import ConnectionCreate, ConnectionResponse, ConnectionSecretResponse, ConnectionUpdate
from app.services.connection_secrets import ConnectionSigningNotConfigured, derive_connection_secret, new_connection_salt

router = APIRouter(prefix="/connections", tags=["connections"])


def _require_owner(request: Request, settings: Settings) -> None:
    if settings.auth_required and getattr(request.state, "user", {}).get("role") != "owner":
        raise HTTPException(status_code=403, detail="רק בעל העסק יכול לנהל חיבורים")


def _response(connection: IntegrationConnection) -> ConnectionResponse:
    return ConnectionResponse(
        id=connection.id,
        provider=connection.provider,
        name=connection.name,
        enabled=connection.enabled,
        webhook_path=f"/api/webhooks/connections/{connection.id}",
        last_event_at=connection.last_event_at,
        created_at=connection.created_at,
    )


@router.get("", response_model=list[ConnectionResponse])
def list_connections(db: Session = Depends(get_db)) -> list[ConnectionResponse]:
    connections = db.scalars(select(IntegrationConnection).order_by(IntegrationConnection.created_at.desc())).all()
    return [_response(connection) for connection in connections]


@router.post("", status_code=201, response_model=ConnectionSecretResponse)
def create_connection(
    payload: ConnectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionSecretResponse:
    _require_owner(request, settings)
    connection = IntegrationConnection(provider=payload.provider, name=payload.name, secret_salt=new_connection_salt())
    db.add(connection)
    try:
        db.flush()
        signing_secret = derive_connection_secret(settings, connection.id, connection.secret_salt)
        db.commit()
        db.refresh(connection)
    except ConnectionSigningNotConfigured as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="כבר קיים חיבור בשם הזה") from exc
    return ConnectionSecretResponse(**_response(connection).model_dump(), signing_secret=signing_secret)


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
    connection.enabled = payload.enabled
    db.commit()
    db.refresh(connection)
    return _response(connection)


@router.post("/{connection_id}/rotate-secret", response_model=ConnectionSecretResponse)
def rotate_connection_secret(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectionSecretResponse:
    _require_owner(request, settings)
    connection = db.get(IntegrationConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="החיבור לא נמצא")
    connection.secret_salt = new_connection_salt()
    try:
        signing_secret = derive_connection_secret(settings, connection.id, connection.secret_salt)
    except ConnectionSigningNotConfigured as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    db.refresh(connection)
    return ConnectionSecretResponse(**_response(connection).model_dump(), signing_secret=signing_secret)
