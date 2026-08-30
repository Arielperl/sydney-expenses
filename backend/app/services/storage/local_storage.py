import shutil
import uuid
from pathlib import Path

from app.core.config import Settings
from app.services.storage.base import ReceiptStorage
from app.services.storage.exceptions import StorageUploadError
from app.services.storage.formats import EXTENSION_BY_VERIFIED_FORMAT


class LocalReceiptStorage(ReceiptStorage):
    """Stores receipt images on local disk, served back via the app's own
    /uploads static mount. This is the safe default provider — it needs no
    external credentials and is what the automated test suite and a fresh
    clone use unless STORAGE_PROVIDER=supabase is explicitly set."""

    provider = "local"

    def __init__(self, settings: Settings):
        self._dir = Path(settings.uploads_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def store(self, local_path: Path, verified_format: str) -> str:
        extension = EXTENSION_BY_VERIFIED_FORMAT.get(verified_format)
        if extension is None:
            raise StorageUploadError(f"Unsupported verified image format '{verified_format}'.")
        object_key = f"{uuid.uuid4().hex}{extension}"
        try:
            shutil.copy(local_path, self._dir / object_key)
        except OSError as exc:
            raise StorageUploadError("Could not write the receipt image to local storage.") from exc
        return object_key

    def get_viewable_url(self, object_key: str) -> str | None:
        if not object_key:
            return None
        return f"/uploads/{object_key}"

    def delete(self, object_key: str) -> bool:
        path = self._resolve(object_key)
        if path is None:
            return False
        try:
            path.unlink()
            return True
        except OSError:
            return False

    def _resolve(self, object_key: str) -> Path | None:
        """Resolves an object key to a path, rejecting any attempt at traversal."""
        if not object_key or "/" in object_key or "\\" in object_key:
            return None
        candidate = (self._dir / object_key).resolve()
        if candidate.parent != self._dir.resolve():
            return None
        if not candidate.exists():
            return None
        return candidate
