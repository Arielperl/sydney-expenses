"""Tamper-evident confirmation for rows returned by CSV preview."""

import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Sequence

from app.core.config import Settings
from app.schemas.imports import CsvPreviewRow

_EPHEMERAL_DEVELOPMENT_SECRET = secrets.token_bytes(32)


def _secret(settings: Settings) -> bytes:
    configured = settings.csv_preview_signing_secret
    return configured.encode("utf-8") if configured else _EPHEMERAL_DEVELOPMENT_SECRET


def _canonical_payload(
    business_id: str,
    file_hash: str,
    filename: str | None,
    rows: Sequence[CsvPreviewRow],
    expires_at: int,
) -> bytes:
    payload = {
        "business_id": business_id,
        "file_hash": file_hash,
        "filename": filename,
        "expires_at": expires_at,
        "rows": [row.model_dump(mode="json") for row in rows],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_csv_preview(
    settings: Settings,
    business_id: str,
    file_hash: str,
    filename: str | None,
    rows: Sequence[CsvPreviewRow],
    expires_at: int,
) -> str:
    return hmac.new(
        _secret(settings),
        _canonical_payload(business_id, file_hash, filename, rows, expires_at),
        hashlib.sha256,
    ).hexdigest()


def verify_csv_preview(
    settings: Settings,
    business_id: str,
    file_hash: str,
    filename: str | None,
    rows: Sequence[CsvPreviewRow],
    expires_at: int,
    signature: str,
) -> bool:
    if expires_at < int(time.time()):
        return False
    expected = sign_csv_preview(settings, business_id, file_hash, filename, rows, expires_at)
    return hmac.compare_digest(expected, signature)
