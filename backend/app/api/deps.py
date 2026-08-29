from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.extraction.base import ReceiptExtractor
from app.services.extraction.mock import MockReceiptExtractor
from app.services.upload_service import UploadService


@lru_cache
def get_upload_service() -> UploadService:
    return UploadService(get_settings())


@lru_cache
def get_receipt_extractor() -> ReceiptExtractor:
    return MockReceiptExtractor()


def get_settings_dep() -> Settings:
    return get_settings()
