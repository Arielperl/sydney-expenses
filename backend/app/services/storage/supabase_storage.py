import logging
import uuid
from pathlib import Path

from supabase import create_client
from storage3.exceptions import StorageApiError

from app.core.config import Settings
from app.services.storage.base import ReceiptStorage
from app.services.storage.exceptions import (
    SignedUrlError,
    StorageAuthenticationError,
    StorageConfigError,
    StorageDeleteError,
    StorageNotFoundError,
    StorageUnavailableError,
    StorageUploadError,
)
from app.services.storage.formats import (
    CONTENT_TYPE_BY_VERIFIED_FORMAT,
    EXTENSION_BY_VERIFIED_FORMAT,
)

logger = logging.getLogger(__name__)


class SupabaseReceiptStorage(ReceiptStorage):
    """Stores receipt images in a private Supabase Storage bucket.

    The bucket is never made public. The frontend never receives a permanent
    URL or the service key — only a freshly generated, time-limited signed URL
    per response, and only the stable object key is ever persisted in the
    database (see get_viewable_url())."""

    provider = "supabase"

    def __init__(self, settings: Settings):
        if not settings.supabase_url or not settings.supabase_secret_key or not settings.supabase_storage_bucket:
            raise StorageConfigError(
                "STORAGE_PROVIDER=supabase requires SUPABASE_URL, SUPABASE_SECRET_KEY, "
                "and SUPABASE_STORAGE_BUCKET to be set."
            )
        self._client = create_client(settings.supabase_url, settings.supabase_secret_key)
        self._bucket_id = settings.supabase_storage_bucket
        self._signed_url_ttl_seconds = settings.supabase_signed_url_ttl_seconds

    @property
    def _bucket(self):
        return self._client.storage.from_(self._bucket_id)

    def store(self, local_path: Path, verified_format: str) -> str:
        extension = EXTENSION_BY_VERIFIED_FORMAT.get(verified_format)
        content_type = CONTENT_TYPE_BY_VERIFIED_FORMAT.get(verified_format)
        if extension is None or content_type is None:
            raise StorageUploadError(f"Unsupported verified image format '{verified_format}'.")
        object_key = f"{uuid.uuid4().hex}{extension}"
        try:
            with open(local_path, "rb") as fh:
                self._bucket.upload(
                    object_key,
                    fh.read(),
                    file_options={"content-type": content_type, "upsert": "false"},
                )
        except StorageApiError as exc:
            raise self._translate(exc, f"Could not upload the receipt image (status {exc.status}).")
        except OSError as exc:
            raise StorageUploadError("Could not read the staged receipt image for upload.") from exc
        return object_key

    def get_viewable_url(self, object_key: str) -> str | None:
        if not object_key:
            return None
        try:
            response = self._bucket.create_signed_url(object_key, self._signed_url_ttl_seconds)
        except StorageApiError as exc:
            logger.warning("supabase_signed_url_failed status=%s code=%s", exc.status, exc.code)
            return None
        return response.get("signedURL") or response.get("signedUrl")

    def delete(self, object_key: str) -> bool:
        if not object_key:
            return False
        try:
            self._bucket.remove([object_key])
            return True
        except StorageApiError as exc:
            logger.warning("supabase_delete_failed status=%s code=%s", exc.status, exc.code)
            return False

    @staticmethod
    def _translate(exc: StorageApiError, message: str) -> StorageUploadError:
        try:
            status = int(exc.status)
        except (TypeError, ValueError):
            status = None
        if status in (401, 403):
            return StorageAuthenticationError(message)
        if status == 404:
            return StorageNotFoundError(message)
        if status is None or status >= 500:
            return StorageUnavailableError(message)
        return StorageUploadError(message)
