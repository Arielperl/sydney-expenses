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
    # never leaves the machine; "openai" sends the receipt image to OpenAI.
    receipt_extractor_provider: Literal["mock", "openai"] = "mock"
    openai_api_key: str | None = None
    openai_receipt_model: str | None = None
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
