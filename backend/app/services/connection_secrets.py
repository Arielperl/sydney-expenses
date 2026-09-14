import base64
import hashlib
import hmac
import secrets

from app.core.config import Settings


class ConnectionSigningNotConfigured(RuntimeError):
    pass


def new_connection_salt() -> str:
    return secrets.token_hex(32)


def derive_connection_secret(settings: Settings, connection_id: str, salt: str) -> str:
    master = settings.connection_signing_secret or settings.webhook_signing_secret
    if not master:
        raise ConnectionSigningNotConfigured(
            "Connection signing is not configured. Set CONNECTION_SIGNING_SECRET."
        )
    message = f"sydney-connection-v1:{connection_id}:{salt}".encode()
    digest = hmac.new(master.encode(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
