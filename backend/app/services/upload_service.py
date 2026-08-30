import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from app.core.config import Settings
from app.services.storage.formats import EXTENSION_BY_VERIFIED_FORMAT

CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MB


class UnsupportedFileTypeError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


class UploadService:
    """Validates an uploaded receipt image and stages it as a local temp file.

    The client-supplied content type and filename are never trusted: the file is
    streamed to disk in bounded chunks (rejecting it as soon as it exceeds the size
    limit) and then the actual image bytes are verified with Pillow.

    This service only produces a verified, local temp file — it never decides where
    the image is permanently stored. That decision belongs to a `ReceiptStorage`
    implementation (see app/services/storage/), which is what lets the same staged
    temp file be used both for the storage upload and for local OCR/vision receipt
    extraction, regardless of which storage provider is configured. Callers are
    responsible for deleting the returned temp file once they are done with it
    (typically in a `finally` block).
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._staging_dir = Path(settings.uploads_dir)
        self._staging_dir.mkdir(parents=True, exist_ok=True)

    async def stage(self, file: UploadFile) -> tuple[Path, str]:
        """Streams and verifies the upload, returning (temp_path, verified_format)."""
        temp_path = self._staging_dir / f".tmp-{uuid.uuid4().hex}"
        total_bytes = 0
        try:
            with temp_path.open("wb") as buffer:
                while True:
                    chunk = await file.read(CHUNK_SIZE_BYTES)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > self._settings.max_upload_size_bytes:
                        max_mb = self._settings.max_upload_size_bytes / (1024 * 1024)
                        raise FileTooLargeError(f"File exceeds the maximum allowed size of {max_mb:.0f} MB.")
                    buffer.write(chunk)

            if total_bytes == 0:
                raise UnsupportedFileTypeError("Uploaded file is empty.")

            verified_format = self._verify_image(temp_path)
            if verified_format not in EXTENSION_BY_VERIFIED_FORMAT:
                raise UnsupportedFileTypeError(
                    f"Unsupported image format '{verified_format}'. Allowed formats: JPEG, PNG, WEBP."
                )
            return temp_path, verified_format
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _verify_image(path: Path) -> str:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                return (image.format or "").upper()
        except Exception as exc:
            raise UnsupportedFileTypeError(
                "The uploaded file is not a valid JPEG, PNG, or WebP image."
            ) from exc

    @staticmethod
    def cleanup(temp_path: Path) -> None:
        temp_path.unlink(missing_ok=True)
