import io
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExpenseSource
from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus
from app.services.extraction.mock import MockReceiptExtractor
from tests.conftest import VALID_PNG_BYTES


def _extracted_for_valid_png():
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        tmp.write(VALID_PNG_BYTES)
        tmp.flush()
        return MockReceiptExtractor().extract(tmp.name)


def _missing_expense(db_session, **overrides) -> Expense:
    defaults = dict(
        business_name="Shufersal",
        amount=Decimal("184.90"),
        currency="ILS",
        category=ExpenseCategory.OTHER,
        expense_date=date(2026, 9, 1),
        source=ExpenseSource.WEBHOOK,
        source_provider="demo-bank",
        external_id="tx-1",
        document_status=DocumentStatus.MISSING,
    )
    defaults.update(overrides)
    expense = Expense(**defaults)
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)
    return expense


def test_receipt_upload_auto_matches_a_waiting_expense(client, db_session):
    # Derive exactly what the deterministic mock extractor will produce for
    # this fixed image content, then seed a missing-document expense with
    # those exact values so the real /receipts/upload call auto-matches it.
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        tmp.write(VALID_PNG_BYTES)
        tmp.flush()
        extracted = MockReceiptExtractor().extract(tmp.name)

    expense = _missing_expense(
        db_session,
        business_name=extracted.business_name,
        amount=extracted.total,
        currency=extracted.currency,
        expense_date=extracted.date,
        receipt_number=extracted.receipt_number,
        external_id="tx-auto-match",
    )

    response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["auto_matched"] is True
    assert body["matched_expense_id"] == expense.id
    assert len(body["match_reasons"]) > 0


def test_reconciliation_inbox_lists_missing_documents(client, db_session):
    expense = _missing_expense(db_session)

    response = client.get("/api/reconciliation/inbox")

    assert response.status_code == 200
    body = response.json()
    ids = {e["id"] for e in body["missing_documents"]}
    assert expense.id in ids


def test_inbox_suggested_matches_show_both_transaction_and_receipt(client, db_session):
    extracted = _extracted_for_valid_png()
    expense = _missing_expense(
        db_session,
        business_name="Totally Unrelated Store Name",
        amount=extracted.total,
        currency=extracted.currency,
        expense_date=extracted.date,
        external_id="tx-suggested-pair",
    )
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]
    assert upload_response.json()["suggested_match"] is not None

    response = client.get("/api/reconciliation/inbox")

    assert response.status_code == 200
    match = next(m for m in response.json()["suggested_matches"] if m["expense"]["id"] == expense.id)
    assert match["document"] is not None
    assert match["document"]["id"] == upload_id
    assert match["document"]["extracted_business_name"] == extracted.business_name
    assert match["document"]["preview_url"] is not None


def test_approve_match_endpoint(client, db_session):
    from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus

    upload = ReceiptUpload(
        stored_filename="receipt-key.jpg",
        storage_provider="local",
        status=ReceiptUploadStatus.PENDING,
        extracted_vat=Decimal("10.00"),
        extracted_receipt_number="R-1",
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    expense = _missing_expense(
        db_session,
        document_status=DocumentStatus.SUGGESTED,
        reconciliation_confidence=0.7,
        suggested_receipt_upload_id=upload.id,
        vat_amount=None,
        receipt_number=None,
    )

    response = client.post(f"/api/reconciliation/matches/{expense.id}/approve")

    assert response.status_code == 200
    body = response.json()["expense"]
    assert body["document_status"] == "attached"
    assert body["vat_amount"] == "10.00"
    assert body["receipt_number"] == "R-1"


def test_reject_match_endpoint(client, db_session):
    expense = _missing_expense(db_session, document_status=DocumentStatus.SUGGESTED, reconciliation_confidence=0.7)

    response = client.post(f"/api/reconciliation/matches/{expense.id}/reject")

    assert response.status_code == 200
    assert response.json()["expense"]["document_status"] == "missing"


def test_approve_match_unknown_expense_returns_404(client):
    response = client.post("/api/reconciliation/matches/does-not-exist/approve")

    assert response.status_code == 404


def test_targeted_upload_attaches_immediately_when_no_conflict(client, db_session):
    extracted = _extracted_for_valid_png()
    expense = _missing_expense(
        db_session,
        business_name=extracted.business_name,
        amount=extracted.total,
        currency=extracted.currency,
        expense_date=extracted.date,
        external_id="tx-targeted-no-conflict",
    )

    response = client.post(
        "/api/receipts/upload",
        data={"expense_id": expense.id},
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attached_to_expense_id"] == expense.id
    assert body["conflict"] is None

    db_session.refresh(expense)
    assert expense.document_status == DocumentStatus.ATTACHED


def test_targeted_upload_reports_conflict_without_attaching(client, db_session):
    extracted = _extracted_for_valid_png()
    expense = _missing_expense(
        db_session,
        business_name=extracted.business_name,
        amount=extracted.total + Decimal("500.00"),
        currency=extracted.currency,
        expense_date=extracted.date,
        external_id="tx-targeted-conflict",
    )

    response = client.post(
        "/api/receipts/upload",
        data={"expense_id": expense.id},
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attached_to_expense_id"] is None
    assert body["conflict"] is not None
    assert body["conflict"]["expense_id"] == expense.id

    db_session.refresh(expense)
    assert expense.document_status == DocumentStatus.MISSING


def test_confirming_attach_after_conflict_succeeds(client, db_session):
    extracted = _extracted_for_valid_png()
    expense = _missing_expense(
        db_session,
        business_name=extracted.business_name,
        amount=extracted.total + Decimal("500.00"),
        currency=extracted.currency,
        expense_date=extracted.date,
        external_id="tx-confirm-past-conflict",
    )

    upload_response = client.post(
        "/api/receipts/upload",
        data={"expense_id": expense.id},
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]

    attach_response = client.post(
        "/api/reconciliation/attach", json={"upload_id": upload_id, "expense_id": expense.id}
    )

    assert attach_response.status_code == 200
    assert attach_response.json()["expense"]["document_status"] == "attached"


def test_attach_on_non_missing_expense_returns_409(client, db_session):
    expense = _missing_expense(db_session, document_status=DocumentStatus.ATTACHED)
    upload = ReceiptUpload(stored_filename="receipt-key.jpg", storage_provider="local", status=ReceiptUploadStatus.PENDING)
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)

    response = client.post("/api/reconciliation/attach", json={"upload_id": upload.id, "expense_id": expense.id})

    assert response.status_code == 409


def test_attach_with_unavailable_upload_returns_409(client, db_session):
    expense = _missing_expense(db_session)
    upload = ReceiptUpload(stored_filename="receipt-key.jpg", storage_provider="local", status=ReceiptUploadStatus.CONFIRMED)
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)

    response = client.post("/api/reconciliation/attach", json={"upload_id": upload.id, "expense_id": expense.id})

    assert response.status_code == 409


def test_inbox_lists_real_unassigned_receipt_uploads(client, db_session):
    upload = ReceiptUpload(
        stored_filename="orphan.png",
        storage_provider="local",
        status=ReceiptUploadStatus.PENDING,
        extracted_business_name="Cofix",
        extracted_total=Decimal("42.50"),
        extracted_currency="ILS",
        extracted_date=date(2026, 9, 1),
        extraction_confidence=0.8,
        extraction_warnings=["vat_amount_not_confident"],
    )
    db_session.add(upload)
    db_session.commit()

    response = client.get("/api/reconciliation/inbox")

    assert response.status_code == 200
    docs = response.json()["documents_without_transactions"]
    match = next(d for d in docs if d["id"] == upload.id)
    assert match["extracted_business_name"] == "Cofix"
    assert match["extracted_total"] == "42.50"
    assert match["extraction_warnings"] == ["vat_amount_not_confident"]
    assert match["preview_url"] == "/uploads/orphan.png"


def test_unassigned_document_preview_url_uses_signed_supabase_url(client, db_session, monkeypatch):
    import app.services.storage as storage_module

    class _FakeSupabaseStorage:
        provider = "supabase"

        def get_viewable_url(self, object_key):
            return f"https://fake-project.supabase.co/object/sign/receipts/{object_key}?token=fake"

    monkeypatch.setattr(storage_module, "get_storage_for_provider", lambda provider: _FakeSupabaseStorage())

    upload = ReceiptUpload(stored_filename="orphan-key.png", storage_provider="supabase", status=ReceiptUploadStatus.PENDING)
    db_session.add(upload)
    db_session.commit()

    response = client.get("/api/reconciliation/inbox")

    docs = response.json()["documents_without_transactions"]
    match = next(d for d in docs if d["id"] == upload.id)
    assert match["preview_url"].startswith("https://fake-project.supabase.co/object/sign/")
    assert "orphan-key.png" not in match["preview_url"].split("token=")[0].split("/receipts/")[0]


def test_inbox_excludes_a_pending_upload_that_has_an_active_suggestion(client, db_session):
    extracted = _extracted_for_valid_png()
    expense = _missing_expense(
        db_session,
        business_name="Totally Unrelated Store Name",
        amount=extracted.total,
        currency=extracted.currency,
        expense_date=extracted.date,
        external_id="tx-inbox-suggestion",
    )
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]
    assert upload_response.json()["suggested_match"] is not None
    db_session.refresh(expense)
    assert expense.document_status == DocumentStatus.SUGGESTED

    response = client.get("/api/reconciliation/inbox")

    doc_ids = {d["id"] for d in response.json()["documents_without_transactions"]}
    assert upload_id not in doc_ids


def test_rematch_document_endpoint(client, db_session):
    extracted = _extracted_for_valid_png()
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]

    expense = _missing_expense(
        db_session,
        business_name=extracted.business_name,
        amount=extracted.total,
        currency=extracted.currency,
        expense_date=extracted.date,
        external_id="tx-rematch",
    )

    response = client.post(f"/api/reconciliation/documents/{upload_id}/rematch")

    assert response.status_code == 200
    body = response.json()
    assert body["expense"]["id"] == expense.id


def test_rematch_unknown_document_returns_404(client):
    response = client.post("/api/reconciliation/documents/does-not-exist/rematch")
    assert response.status_code == 404


def test_eligible_expenses_endpoint_lists_only_missing_expenses(client, db_session):
    extracted = _extracted_for_valid_png()
    matching = _missing_expense(
        db_session, business_name=extracted.business_name, external_id="tx-eligible-a"
    )
    _missing_expense(
        db_session,
        business_name=extracted.business_name,
        external_id="tx-eligible-b",
        document_status=DocumentStatus.ATTACHED,
    )
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]

    response = client.get(f"/api/reconciliation/documents/{upload_id}/eligible-expenses")

    assert response.status_code == 200
    body = response.json()
    expense_ids = {c["expense"]["id"] for c in body}
    assert matching.id in expense_ids


def test_discard_document_endpoint(client, db_session):
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]

    response = client.post(f"/api/reconciliation/documents/{upload_id}/discard")

    assert response.status_code == 204
    db_session.refresh(db_session.get(ReceiptUpload, upload_id))
    assert db_session.get(ReceiptUpload, upload_id).status == ReceiptUploadStatus.DISCARDED

    inbox_response = client.get("/api/reconciliation/inbox")
    doc_ids = {d["id"] for d in inbox_response.json()["documents_without_transactions"]}
    assert upload_id not in doc_ids


def test_discard_document_endpoint_unknown_returns_404(client):
    response = client.post("/api/reconciliation/documents/does-not-exist/discard")
    assert response.status_code == 404


def test_discard_document_endpoint_is_idempotent(client, db_session):
    upload_response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    upload_id = upload_response.json()["upload_id"]

    first = client.post(f"/api/reconciliation/documents/{upload_id}/discard")
    second = client.post(f"/api/reconciliation/documents/{upload_id}/discard")

    assert first.status_code == 204
    assert second.status_code == 204
