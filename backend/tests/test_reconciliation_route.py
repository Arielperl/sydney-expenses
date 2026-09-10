import io
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExpenseSource
from app.services.extraction.mock import MockReceiptExtractor
from tests.conftest import VALID_PNG_BYTES


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


def test_approve_match_endpoint(client, db_session):
    expense = _missing_expense(db_session, document_status=DocumentStatus.SUGGESTED, reconciliation_confidence=0.7)

    response = client.post(f"/api/reconciliation/matches/{expense.id}/approve")

    assert response.status_code == 200
    assert response.json()["expense"]["document_status"] == "attached"


def test_reject_match_endpoint(client, db_session):
    expense = _missing_expense(db_session, document_status=DocumentStatus.SUGGESTED, reconciliation_confidence=0.7)

    response = client.post(f"/api/reconciliation/matches/{expense.id}/reject")

    assert response.status_code == 200
    assert response.json()["expense"]["document_status"] == "missing"


def test_approve_match_unknown_expense_returns_404(client):
    response = client.post("/api/reconciliation/matches/does-not-exist/approve")

    assert response.status_code == 404
