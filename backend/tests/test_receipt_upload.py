import io
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.api.deps import get_upload_service
from app.core.config import get_settings
from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus
from app.services.receipt_lifecycle_service import cleanup_expired_uploads
from app.services.upload_service import UploadService
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
    upload_service = UploadService(settings)
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

    cleaned_count = cleanup_expired_uploads(db_session, upload_service, older_than_hours=24)

    assert cleaned_count == 1
    assert not orphan_path.exists()
    db_session.refresh(stale_upload)
    assert stale_upload.status == ReceiptUploadStatus.EXPIRED


def test_cleanup_does_not_touch_recent_pending_uploads(db_session):
    settings = get_settings()
    upload_service = UploadService(settings)
    uploads_dir = Path(settings.uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    recent_path = uploads_dir / "recent.png"
    recent_path.write_bytes(VALID_PNG_BYTES)

    recent_upload = ReceiptUpload(stored_filename="recent.png", status=ReceiptUploadStatus.PENDING)
    db_session.add(recent_upload)
    db_session.commit()

    cleaned_count = cleanup_expired_uploads(db_session, upload_service, older_than_hours=24)

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

    monkeypatch.setattr(UploadService, "delete", lambda self, filename: False)

    delete_response = client.delete(f"/api/expenses/{expense_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/expenses/{expense_id}").status_code == 404
