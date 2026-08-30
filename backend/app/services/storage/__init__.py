from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.storage.base import ReceiptStorage
from app.services.storage.exceptions import (
    SignedUrlError,
    StorageAuthenticationError,
    StorageConfigError,
    StorageDeleteError,
    StorageError,
    StorageNotFoundError,
    StorageUnavailableError,
    StorageUploadError,
)
from app.services.storage.local_storage import LocalReceiptStorage
from app.services.storage.supabase_storage import SupabaseReceiptStorage

_PROVIDERS = {
    LocalReceiptStorage.provider: LocalReceiptStorage,
    SupabaseReceiptStorage.provider: SupabaseReceiptStorage,
}


def build_storage(provider: str, settings: Settings) -> ReceiptStorage:
    """Builds the storage backend for a given provider name. `provider` should
    always come from either `settings.storage_provider` (for new uploads) or a
    persisted record's own `storage_provider` column (for existing records),
    never assumed — this is what lets old `local` records keep working
    correctly even after the app is reconfigured to use `supabase`."""
    try:
        storage_cls = _PROVIDERS[provider]
    except KeyError:
        raise StorageConfigError(f"Unknown storage provider '{provider}'.") from None
    return storage_cls(settings)


@lru_cache
def get_storage_for_provider(provider: str) -> ReceiptStorage:
    """Cached per provider name so a Supabase client (and its underlying HTTP
    connection pool) is built once, not on every request."""
    return build_storage(provider, get_settings())


def get_receipt_storage() -> ReceiptStorage:
    """The storage backend for *new* uploads — always the currently configured provider."""
    return get_storage_for_provider(get_settings().storage_provider)


def resolve_receipt_image_url(provider: str | None, object_key: str | None) -> str | None:
    """Resolves a persisted record's own storage provider (never necessarily the
    currently configured one) to a fresh viewable URL, so pre-existing `local`
    records keep working even after the app is reconfigured to use `supabase`,
    and vice versa."""
    if not object_key:
        return None
    storage = get_storage_for_provider(provider or "local")
    return storage.get_viewable_url(object_key)


__all__ = [
    "ReceiptStorage",
    "LocalReceiptStorage",
    "SupabaseReceiptStorage",
    "build_storage",
    "get_storage_for_provider",
    "get_receipt_storage",
    "resolve_receipt_image_url",
    "StorageError",
    "StorageConfigError",
    "StorageUnavailableError",
    "StorageAuthenticationError",
    "StorageNotFoundError",
    "StorageUploadError",
    "SignedUrlError",
    "StorageDeleteError",
]
