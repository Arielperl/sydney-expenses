import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from app.core.config import Settings

CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MB

_EXTENSION_BY_VERIFIED_FORMAT = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


class UnsupportedFileTypeError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


class UploadService:
    """Validates and persists uploaded receipt images to the local uploads directory.

    The client-supplied content type and filename are never trusted: the file is
    streamed to disk in bounded chunks (rejecting it as soon as it exceeds the size
    limit) and then the actual image bytes are verified with Pillow. The stored
    filename is always server-generated from the verified format, which also rules
    out path traversal.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._uploads_dir = Path(settings.uploads_dir)
        self._uploads_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, file: UploadFile) -> tuple[str, str]:
        temp_path = self._uploads_dir / f".tmp-{uuid.uuid4().hex}"
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
            extension = _EXTENSION_BY_VERIFIED_FORMAT.get(verified_format)
            if extension is None:
                raise UnsupportedFileTypeError(
                    f"Unsupported image format '{verified_format}'. Allowed formats: JPEG, PNG, WEBP."
                )

            final_filename = f"{uuid.uuid4().hex}{extension}"
            final_path = self._uploads_dir / final_filename
            temp_path.rename(final_path)
            return final_filename, str(final_path)
        except (FileTooLargeError, UnsupportedFileTypeError):
            temp_path.unlink(missing_ok=True)
            raise
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

    def resolve_path(self, filename: str) -> Path | None:
        """Resolves a stored filename to its path, rejecting any attempt at traversal."""
        if not filename or "/" in filename or "\\" in filename:
            return None
        candidate = (self._uploads_dir / filename).resolve()
        if candidate.parent != self._uploads_dir.resolve():
            return None
        if not candidate.exists():
            return None
        return candidate

    def delete(self, filename: str) -> bool:
        """Best-effort deletion of a stored file. Returns True if deletion succeeded."""
        path = self.resolve_path(filename)
        if path is None:
            return False
        try:
            path.unlink()
            return True
        except OSError:
            return False

    def image_url(self, filename: str | None) -> str | None:
        if not filename:
            return None
        return f"/uploads/{filename}"
