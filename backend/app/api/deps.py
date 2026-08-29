from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.extraction.base import ReceiptExtractor
from app.services.extraction.mock import MockReceiptExtractor
from app.services.extraction.openai_extractor import OpenAIReceiptExtractor
from app.services.upload_service import UploadService


@lru_cache
def get_upload_service() -> UploadService:
    return UploadService(get_settings())


@lru_cache
def get_receipt_extractor() -> ReceiptExtractor:
    settings = get_settings()
    if settings.receipt_extractor_provider == "openai":
        return OpenAIReceiptExtractor(settings)
    return MockReceiptExtractor()


def get_settings_dep() -> Settings:
    return get_settings()
