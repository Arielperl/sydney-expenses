from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar


class ReceiptStorage(ABC):
    """Provider-independent persistence for a verified receipt image.

    A concrete implementation never decides *whether* an image is a valid
    receipt — that is the job of the upload-staging step (Pillow verification)
    that always runs first. This interface only decides *where* an already-
    verified image ends up: on local disk, or in a private Supabase Storage
    bucket.

    `store()` always takes a *local* file path — even the Supabase
    implementation reads bytes from a local temp file — which is what lets the
    local Tesseract/Ollama extraction step run against that same temp file
    regardless of which storage provider is configured (see upload_service.py
    and the /receipts/upload route for how the temp file's lifetime spans
    both the extraction call and the storage call before being cleaned up).
    """

    provider: ClassVar[str]

    @abstractmethod
    def store(self, local_path: Path, verified_format: str) -> str:
        """Persists the file at `local_path` (already Pillow-verified as
        `verified_format`, e.g. "JPEG") and returns a stable object key/reference
        to save in the database. Never derived from the original filename."""
        raise NotImplementedError

    @abstractmethod
    def get_viewable_url(self, object_key: str) -> str | None:
        """Returns a URL the frontend can load the image from right now. For a
        private provider this must be freshly generated and time-limited (a
        signed URL) — never a permanent public URL, and never persisted."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, object_key: str) -> bool:
        """Best-effort delete. Returns True only on confirmed deletion."""
        raise NotImplementedError
