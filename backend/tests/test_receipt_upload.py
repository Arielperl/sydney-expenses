import io
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.api.deps import get_receipt_storage, get_upload_service
from app.core.config import get_settings
from app.main import app
from app.models.expense import Expense, ExpenseCategory
from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus
from app.services.receipt_lifecycle_service import cleanup_expired_uploads, delete_expense_and_cleanup_receipt
from app.services.storage.base import ReceiptStorage
from app.services.storage.exceptions import StorageUploadError
from app.services.storage.local_storage import LocalReceiptStorage
from tests.conftest import VALID_PNG_BYTES


def _confirm_payload(upload_id: str, **overrides) -> dict:
    payload = {
        "upload_id": upload_id,
        "business_name": "Shufersal",
        "amount": 100.0,
        "expense_date": "2026-01-01",
        "category": "groceries",
        "currency": "ILS",
    }
    payload.update(overrides)
    return payload


def test_upload_accepts_valid_png(client):
    response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["extraction_succeeded"] is True
    assert body["receipt_image_url"].startswith("/uploads/")
    assert body["extracted_data"]["confidence"] > 0
    assert body["upload_id"]


def test_upload_rejects_unsupported_content_type(client):
    response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert response.status_code == 422


def test_upload_rejects_spoofed_content_type(client):
    """A text file claiming to be image/png must still be rejected by real image verification."""
    response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(b"this is not actually an image"), "image/png")},
    )
    assert response.status_code == 422


def test_upload_rejects_corrupted_image_data(client):
    truncated = VALID_PNG_BYTES[:20]
    response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(truncated), "image/png")},
    )
    assert response.status_code == 422


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "10")
    get_settings.cache_clear()
    get_upload_service.cache_clear()
    try:
        response = client.post(
            "/api/receipts/upload",
            files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        )
        assert response.status_code == 422
    finally:
        get_settings.cache_clear()
        get_upload_service.cache_clear()


def test_oversized_upload_leaves_no_partial_file(client, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "10")
    get_settings.cache_clear()
    get_upload_service.cache_clear()
    try:
        client.post(
            "/api/receipts/upload",
            files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        )
        uploads_dir = Path(os.environ["UPLOADS_DIR"])
        leftover = [p for p in uploads_dir.iterdir() if p.name.startswith(".tmp-")]
        assert leftover == []
    finally:
        get_settings.cache_clear()
        get_upload_service.cache_clear()


def test_uploaded_filename_is_not_the_original(client):
    response = client.post(
        "/api/receipts/upload",
        files={"file": ("../../etc/passwd.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "passwd" not in body["upload_id"]
    assert ".." not in body["upload_id"]
    assert "passwd" not in body["receipt_image_url"]


def test_confirm_receipt_creates_expense(client):
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]

    confirm_response = client.post("/api/receipts/confirm", json=_confirm_payload(upload_id))
    assert confirm_response.status_code == 201
    body = confirm_response.json()
    assert body["extraction_status"] == "confirmed"
    assert body["receipt_image_url"] == upload_response.json()["receipt_image_url"]
    assert Decimal(body["amount"]) == Decimal("100.00")


def test_confirm_receipt_with_unknown_upload_id_returns_404(client):
    response = client.post("/api/receipts/confirm", json=_confirm_payload("nonexistent-id"))
    assert response.status_code == 404


def test_duplicate_confirmation_returns_conflict_and_creates_no_duplicate(client):
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]

    first = client.post("/api/receipts/confirm", json=_confirm_payload(upload_id))
    assert first.status_code == 201

    second = client.post("/api/receipts/confirm", json=_confirm_payload(upload_id))
    assert second.status_code == 409

    all_expenses = client.get("/api/expenses").json()
    assert len(all_expenses) == 1


def test_confirm_expired_upload_returns_gone(client, db_session):
    upload = ReceiptUpload(stored_filename="ghost.png", status=ReceiptUploadStatus.EXPIRED)
    db_session.add(upload)
    db_session.commit()

    response = client.post("/api/receipts/confirm", json=_confirm_payload(upload.id))
    assert response.status_code == 410


def test_cleanup_expired_uploads_removes_orphan_file_and_marks_expired(db_session):
    settings = get_settings()
    uploads_dir = Path(settings.uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    orphan_path = uploads_dir / "orphan.png"
    orphan_path.write_bytes(VALID_PNG_BYTES)

    stale_upload = ReceiptUpload(
        stored_filename="orphan.png",
        status=ReceiptUploadStatus.PENDING,
        created_at=datetime.utcnow() - timedelta(hours=48),
    )
    db_session.add(stale_upload)
    db_session.commit()

    cleaned_count = cleanup_expired_uploads(db_session, settings, older_than_hours=24)

    assert cleaned_count == 1
    assert not orphan_path.exists()
    db_session.refresh(stale_upload)
    assert stale_upload.status == ReceiptUploadStatus.EXPIRED


def test_cleanup_does_not_touch_recent_pending_uploads(db_session):
    settings = get_settings()
    uploads_dir = Path(settings.uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    recent_path = uploads_dir / "recent.png"
    recent_path.write_bytes(VALID_PNG_BYTES)

    recent_upload = ReceiptUpload(stored_filename="recent.png", status=ReceiptUploadStatus.PENDING)
    db_session.add(recent_upload)
    db_session.commit()

    cleaned_count = cleanup_expired_uploads(db_session, settings, older_than_hours=24)

    assert cleaned_count == 0
    assert recent_path.exists()
    db_session.refresh(recent_upload)
    assert recent_upload.status == ReceiptUploadStatus.PENDING


def test_deleting_expense_removes_receipt_image_file(client):
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]
    stored_filename = upload_response.json()["receipt_image_url"].removeprefix("/uploads/")

    confirm_response = client.post("/api/receipts/confirm", json=_confirm_payload(upload_id))
    expense_id = confirm_response.json()["id"]

    uploads_dir = Path(get_settings().uploads_dir)
    assert (uploads_dir / stored_filename).exists()

    delete_response = client.delete(f"/api/expenses/{expense_id}")
    assert delete_response.status_code == 204
    assert not (uploads_dir / stored_filename).exists()


def test_deleting_expense_succeeds_even_if_file_deletion_fails(client, monkeypatch):
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]
    confirm_response = client.post("/api/receipts/confirm", json=_confirm_payload(upload_id))
    expense_id = confirm_response.json()["id"]

    monkeypatch.setattr(LocalReceiptStorage, "delete", lambda self, object_key: False)

    delete_response = client.delete(f"/api/expenses/{expense_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/expenses/{expense_id}").status_code == 404


def test_upload_leaves_no_temp_file_after_success(client):
    response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert response.status_code == 200
    uploads_dir = Path(os.environ["UPLOADS_DIR"])
    leftover = [p for p in uploads_dir.iterdir() if p.name.startswith(".tmp-")]
    assert leftover == []


class _StoreCallRecordingStorage(ReceiptStorage):
    provider = "local"

    def __init__(self):
        self.store_called = False

    def store(self, local_path, verified_format):
        self.store_called = True
        raise AssertionError("store() must never be called for an image that failed validation")

    def get_viewable_url(self, object_key):
        return None

    def delete(self, object_key):
        return False


def test_upload_never_calls_storage_for_invalid_image(client):
    """Requirement: invalid/spoofed images must be rejected before any storage call."""
    fake_storage = _StoreCallRecordingStorage()
    app.dependency_overrides[get_receipt_storage] = lambda: fake_storage
    try:
        response = client.post(
            "/api/receipts/upload",
            files={"file": ("receipt.png", io.BytesIO(b"this is not actually an image"), "image/png")},
        )
        assert response.status_code == 422
        assert fake_storage.store_called is False
    finally:
        app.dependency_overrides.pop(get_receipt_storage, None)


def test_upload_returns_503_and_no_pending_row_when_storage_fails(client, db_session):
    class _FailingStorage(ReceiptStorage):
        provider = "local"

        def store(self, local_path, verified_format):
            raise StorageUploadError("simulated storage outage")

        def get_viewable_url(self, object_key):
            return None

        def delete(self, object_key):
            return False

    app.dependency_overrides[get_receipt_storage] = lambda: _FailingStorage()
    try:
        response = client.post(
            "/api/receipts/upload",
            files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        )
        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_receipt_storage, None)

    assert db_session.query(ReceiptUpload).count() == 0


def test_delete_expense_cleanup_is_non_blocking_when_storage_raises(db_session, monkeypatch):
    expense = Expense(
        business_name="Shufersal",
        amount=Decimal("10.00"),
        currency="ILS",
        category=ExpenseCategory.GROCERIES,
        expense_date=datetime.utcnow().date(),
        receipt_image_path="some-object-key.png",
        storage_provider="supabase",
    )
    db_session.add(expense)
    db_session.commit()
    expense_id = expense.id

    import app.services.receipt_lifecycle_service as lifecycle_module

    class _RaisingStorage:
        def delete(self, object_key):
            from app.services.storage.exceptions import StorageUnavailableError

            raise StorageUnavailableError("simulated Supabase outage")

    monkeypatch.setattr(lifecycle_module, "build_storage", lambda provider, settings: _RaisingStorage())

    result = delete_expense_and_cleanup_receipt(db_session, get_settings(), expense)

    assert result is False
    assert db_session.get(Expense, expense_id) is None


def test_receipt_upload_row_backfills_local_storage_provider_by_default(db_session):
    upload = ReceiptUpload(stored_filename="legacy.png", status=ReceiptUploadStatus.PENDING)
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    assert upload.storage_provider == "local"


def test_expense_backfills_local_storage_provider_by_default(db_session):
    expense = Expense(
        business_name="Legacy Store",
        amount=Decimal("5.00"),
        currency="ILS",
        category=ExpenseCategory.OTHER,
        expense_date=datetime.utcnow().date(),
        receipt_image_path="legacy.png",
    )
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)
    assert expense.storage_provider == "local"
