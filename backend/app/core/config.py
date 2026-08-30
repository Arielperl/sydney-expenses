from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Receiptly API"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'receiptly.db'}"
    uploads_dir: str = str(BACKEND_DIR / "uploads")
    max_upload_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    allowed_image_content_types: set[str] = {"image/jpeg", "image/png", "image/webp"}
    cors_allowed_origins: list[str] = ["http://localhost:5173"]
    default_currency: str = "ILS"
    pending_upload_expiry_hours: int = 24

    # Receipt extraction provider. "mock" (default) needs no external credentials and
    # never leaves the machine; "local" runs Tesseract OCR + a local Ollama model,
    # never leaving the machine either; "openai" sends the receipt image to OpenAI.
    receipt_extractor_provider: Literal["mock", "local", "openai"] = "mock"
    openai_api_key: str | None = None
    openai_receipt_model: str | None = None
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2

    ollama_base_url: str = "http://localhost:11434"
    ollama_receipt_model: str = "gemma3:12b"
    ollama_timeout_seconds: float = 120.0
    ollama_max_retries: int = 2
    tesseract_languages: str = "heb+eng"

    # Receipt image storage provider. "local" (default) writes to uploads_dir on
    # disk and needs no external credentials — the safe default for a fresh clone
    # and for the automated test suite. "supabase" stores images in a private
    # Supabase Storage bucket, served back to the frontend only via freshly
    # generated, time-limited signed URLs (never a permanent public URL).
    storage_provider: Literal["local", "supabase"] = "local"
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_storage_bucket: str | None = None
    supabase_signed_url_ttl_seconds: int = 3600


class StorageConfigurationError(RuntimeError):
    """Raised at startup when STORAGE_PROVIDER=supabase but required Supabase
    configuration is missing. Deliberately fails fast rather than silently
    falling back to local storage, so a misconfigured deployment never
    surprises an operator by writing receipts to an ephemeral local disk."""


def validate_storage_settings(settings: Settings) -> None:
    if settings.storage_provider != "supabase":
        return
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", settings.supabase_url),
            ("SUPABASE_SECRET_KEY", settings.supabase_secret_key),
            ("SUPABASE_STORAGE_BUCKET", settings.supabase_storage_bucket),
        )
        if not value
    ]
    if missing:
        raise StorageConfigurationError(
            "STORAGE_PROVIDER=supabase requires the following environment "
            f"variable(s) to be set: {', '.join(missing)}."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
