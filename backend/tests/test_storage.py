import io
from pathlib import Path

import pytest
from storage3.exceptions import StorageApiError

from app.core.config import StorageConfigurationError, get_settings, validate_storage_settings
from app.services.storage import build_storage
from app.services.storage.exceptions import (
    StorageAuthenticationError,
    StorageConfigError,
    StorageNotFoundError,
    StorageUnavailableError,
    StorageUploadError,
)
from app.services.storage.local_storage import LocalReceiptStorage
from app.services.storage import supabase_storage as supabase_storage_module
from app.services.storage.supabase_storage import SupabaseReceiptStorage
from tests.conftest import VALID_PNG_BYTES

_FAKE_SECRET = "sb_secret_totally_fake_value_never_real"  # noqa: S105 - test-only placeholder


def _write_temp_png(tmp_path) -> Path:
    path = tmp_path / "staged.png"
    path.write_bytes(VALID_PNG_BYTES)
    return path


# ---------------------------------------------------------------------------
# LocalReceiptStorage
# ---------------------------------------------------------------------------


def test_local_storage_store_and_get_viewable_url(tmp_path):
    settings = get_settings().model_copy(update={"uploads_dir": str(tmp_path / "uploads")})
    storage = LocalReceiptStorage(settings)
    temp_path = _write_temp_png(tmp_path)

    object_key = storage.store(temp_path, "PNG")

    assert object_key.endswith(".png")
    assert (Path(settings.uploads_dir) / object_key).exists()
    assert storage.get_viewable_url(object_key) == f"/uploads/{object_key}"
    assert storage.get_viewable_url(None) is None


def test_local_storage_store_produces_random_names(tmp_path):
    settings = get_settings().model_copy(update={"uploads_dir": str(tmp_path / "uploads")})
    storage = LocalReceiptStorage(settings)
    key1 = storage.store(_write_temp_png(tmp_path), "PNG")
    key2 = storage.store(_write_temp_png(tmp_path), "PNG")
    assert key1 != key2


def test_local_storage_delete(tmp_path):
    settings = get_settings().model_copy(update={"uploads_dir": str(tmp_path / "uploads")})
    storage = LocalReceiptStorage(settings)
    object_key = storage.store(_write_temp_png(tmp_path), "PNG")

    assert storage.delete(object_key) is True
    assert storage.delete(object_key) is False  # already gone
    assert storage.delete("../../etc/passwd") is False
    assert storage.delete("") is False


def test_local_storage_rejects_unsupported_format(tmp_path):
    settings = get_settings().model_copy(update={"uploads_dir": str(tmp_path / "uploads")})
    storage = LocalReceiptStorage(settings)
    with pytest.raises(StorageUploadError):
        storage.store(_write_temp_png(tmp_path), "GIF")


# ---------------------------------------------------------------------------
# SupabaseReceiptStorage (always against a fake client, never real credentials)
# ---------------------------------------------------------------------------


class _FakeBucketProxy:
    def __init__(self):
        self.uploaded: list[tuple[str, bytes, dict]] = []
        self.removed: list[list[str]] = []
        self.upload_error: Exception | None = None
        self.signed_url_error: Exception | None = None
        self.signed_url_response: dict = {"signedURL": "https://example.supabase.co/signed?token=abc"}
        self.remove_error: Exception | None = None

    def upload(self, path, file_bytes, file_options=None):
        if self.upload_error is not None:
            raise self.upload_error
        self.uploaded.append((path, file_bytes, file_options or {}))
        return {"path": path}

    def create_signed_url(self, path, expires_in, options=None):
        if self.signed_url_error is not None:
            raise self.signed_url_error
        return self.signed_url_response

    def remove(self, paths):
        if self.remove_error is not None:
            raise self.remove_error
        self.removed.append(paths)


class _FakeStorage:
    def __init__(self, bucket: _FakeBucketProxy):
        self._bucket = bucket

    def from_(self, bucket_id):
        return self._bucket


class _FakeSupabaseClient:
    def __init__(self, bucket: _FakeBucketProxy):
        self.storage = _FakeStorage(bucket)


def _supabase_settings(**overrides):
    return get_settings().model_copy(
        update={
            "storage_provider": "supabase",
            "supabase_url": "https://fake-project.supabase.co",
            "supabase_secret_key": _FAKE_SECRET,
            "supabase_storage_bucket": "receipts",
            "supabase_signed_url_ttl_seconds": 3600,
            **overrides,
        }
    )


def _build_supabase_storage(monkeypatch, bucket: _FakeBucketProxy, **settings_overrides) -> SupabaseReceiptStorage:
    monkeypatch.setattr(supabase_storage_module, "create_client", lambda url, key: _FakeSupabaseClient(bucket))
    return SupabaseReceiptStorage(_supabase_settings(**settings_overrides))


def test_supabase_storage_requires_config():
    settings = get_settings().model_copy(
        update={
            "storage_provider": "supabase",
            "supabase_url": None,
            "supabase_secret_key": None,
            "supabase_storage_bucket": None,
        }
    )
    with pytest.raises(StorageConfigError):
        SupabaseReceiptStorage(settings)


def test_supabase_storage_store_uploads_with_content_type(monkeypatch, tmp_path):
    bucket = _FakeBucketProxy()
    storage = _build_supabase_storage(monkeypatch, bucket)

    object_key = storage.store(_write_temp_png(tmp_path), "PNG")

    assert object_key.endswith(".png")
    assert len(bucket.uploaded) == 1
    path, file_bytes, options = bucket.uploaded[0]
    assert path == object_key
    assert file_bytes == VALID_PNG_BYTES
    assert options["content-type"] == "image/png"


def test_supabase_storage_store_produces_random_names(monkeypatch, tmp_path):
    bucket = _FakeBucketProxy()
    storage = _build_supabase_storage(monkeypatch, bucket)
    key1 = storage.store(_write_temp_png(tmp_path), "PNG")
    key2 = storage.store(_write_temp_png(tmp_path), "PNG")
    assert key1 != key2


def test_supabase_storage_get_viewable_url_returns_signed_url(monkeypatch, tmp_path):
    bucket = _FakeBucketProxy()
    bucket.signed_url_response = {"signedURL": "https://fake-project.supabase.co/object/sign/receipts/x?token=y"}
    storage = _build_supabase_storage(monkeypatch, bucket)

    url = storage.get_viewable_url("some-object-key.png")

    assert url == bucket.signed_url_response["signedURL"]
    assert storage.get_viewable_url(None) is None


def test_supabase_storage_get_viewable_url_failure_returns_none_not_raise(monkeypatch, tmp_path, caplog):
    bucket = _FakeBucketProxy()
    bucket.signed_url_error = StorageApiError("not found", "not_found", 404)
    storage = _build_supabase_storage(monkeypatch, bucket)

    with caplog.at_level("WARNING"):
        url = storage.get_viewable_url("missing-key.png")

    assert url is None
    assert _FAKE_SECRET not in caplog.text


def test_supabase_storage_delete(monkeypatch, tmp_path):
    bucket = _FakeBucketProxy()
    storage = _build_supabase_storage(monkeypatch, bucket)

    assert storage.delete("some-key.png") is True
    assert bucket.removed == [["some-key.png"]]
    assert storage.delete("") is False


def test_supabase_storage_delete_failure_returns_false_not_raise(monkeypatch, caplog):
    bucket = _FakeBucketProxy()
    bucket.remove_error = StorageApiError("boom", "internal", 500)
    storage = _build_supabase_storage(monkeypatch, bucket)

    with caplog.at_level("WARNING"):
        result = storage.delete("some-key.png")

    assert result is False
    assert _FAKE_SECRET not in caplog.text


@pytest.mark.parametrize(
    "status, expected_exception",
    [
        (401, StorageAuthenticationError),
        (403, StorageAuthenticationError),
        (404, StorageNotFoundError),
        (500, StorageUnavailableError),
        (503, StorageUnavailableError),
        (400, StorageUploadError),
    ],
)
def test_supabase_storage_upload_translates_errors(monkeypatch, tmp_path, status, expected_exception):
    bucket = _FakeBucketProxy()
    bucket.upload_error = StorageApiError("failure", "some_code", status)
    storage = _build_supabase_storage(monkeypatch, bucket)

    with pytest.raises(expected_exception) as exc_info:
        storage.store(_write_temp_png(tmp_path), "PNG")

    assert _FAKE_SECRET not in str(exc_info.value)


def test_supabase_storage_upload_never_leaks_secret_on_failure(monkeypatch, tmp_path):
    bucket = _FakeBucketProxy()
    bucket.upload_error = StorageApiError(f"secret={_FAKE_SECRET}", "leaked", 500)
    storage = _build_supabase_storage(monkeypatch, bucket)

    with pytest.raises(StorageUnavailableError) as exc_info:
        storage.store(_write_temp_png(tmp_path), "PNG")

    # The translated exception's own message never includes the raw provider error text.
    assert _FAKE_SECRET not in str(exc_info.value)


# ---------------------------------------------------------------------------
# build_storage factory
# ---------------------------------------------------------------------------


def test_build_storage_returns_local_by_default():
    storage = build_storage("local", get_settings())
    assert isinstance(storage, LocalReceiptStorage)


def test_build_storage_unknown_provider_raises():
    with pytest.raises(StorageConfigError):
        build_storage("dropbox", get_settings())


# ---------------------------------------------------------------------------
# Startup configuration validation
# ---------------------------------------------------------------------------


def test_validate_storage_settings_passes_for_local():
    settings = get_settings().model_copy(update={"storage_provider": "local"})
    validate_storage_settings(settings)  # must not raise


def test_validate_storage_settings_fails_fast_when_supabase_config_missing():
    settings = get_settings().model_copy(
        update={
            "storage_provider": "supabase",
            "supabase_url": None,
            "supabase_secret_key": None,
            "supabase_storage_bucket": None,
        }
    )
    with pytest.raises(StorageConfigurationError) as exc_info:
        validate_storage_settings(settings)
    message = str(exc_info.value)
    assert "SUPABASE_URL" in message
    assert "SUPABASE_SECRET_KEY" in message
    assert "SUPABASE_STORAGE_BUCKET" in message


def test_validate_storage_settings_passes_when_supabase_fully_configured():
    settings = get_settings().model_copy(
        update={
            "storage_provider": "supabase",
            "supabase_url": "https://fake-project.supabase.co",
            "supabase_secret_key": _FAKE_SECRET,
            "supabase_storage_bucket": "receipts",
        }
    )
    validate_storage_settings(settings)  # must not raise
