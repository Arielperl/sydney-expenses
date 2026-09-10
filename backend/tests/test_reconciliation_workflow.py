from datetime import date
from decimal import Decimal

import pytest

from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExpenseSource
from app.models.receipt_upload import ReceiptUpload, ReceiptUploadStatus
from app.repositories.receipt_upload_repository import ReceiptUploadRepository
from app.schemas.receipt import ExtractedReceiptData
from app.services.reconciliation.exceptions import (
    ExpenseNotEligibleError,
    ReceiptNotAvailableError,
    ReceiptNotFoundError,
)
from app.services.reconciliation.matching import MatchDecision
from app.services.reconciliation.workflow import (
    apply_match_result,
    approve_suggested_match,
    attach_to_expense,
    build_inbox,
    discard_document,
    list_eligible_expenses,
    reject_suggested_match,
    rematch_document,
    targeted_match,
)


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


def _pending_upload(db_session, **overrides) -> ReceiptUpload:
    defaults = dict(stored_filename="receipt-key.jpg", storage_provider="local", status=ReceiptUploadStatus.PENDING)
    defaults.update(overrides)
    upload = ReceiptUpload(**defaults)
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)
    return upload


def _extracted(**overrides) -> ExtractedReceiptData:
    defaults = dict(
        business_name="Shufersal",
        total=Decimal("184.90"),
        currency="ILS",
        date=date(2026, 9, 1),
        confidence=0.9,
    )
    defaults.update(overrides)
    return ExtractedReceiptData(**defaults)


class TestApplyMatchResult:
    def test_auto_match_attaches_receipt_and_confirms_upload(self, db_session):
        expense = _missing_expense(db_session)
        upload = _pending_upload(db_session)

        outcome = apply_match_result(db_session, upload, _extracted())

        assert outcome.decision == MatchDecision.AUTO_MATCH
        assert outcome.expense.id == expense.id
        assert outcome.expense.document_status == DocumentStatus.ATTACHED
        assert outcome.expense.receipt_image_path == "receipt-key.jpg"

        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.CONFIRMED
        assert upload.expense_id == expense.id

    def test_auto_match_never_overwrites_amount_or_currency(self, db_session):
        expense = _missing_expense(db_session, amount=Decimal("184.90"), currency="ILS")
        upload = _pending_upload(db_session)

        outcome = apply_match_result(db_session, upload, _extracted(total=Decimal("184.90")))

        assert outcome.expense.amount == Decimal("184.90")
        assert outcome.expense.currency == "ILS"

    def test_auto_match_fills_vat_and_receipt_number_gaps(self, db_session):
        _missing_expense(db_session, vat_amount=None, receipt_number=None)
        upload = _pending_upload(db_session)
        extracted = _extracted(vat=Decimal("26.85"), receipt_number="R-100")
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)

        outcome = apply_match_result(db_session, upload, extracted)

        assert outcome.expense.vat_amount == Decimal("26.85")
        assert outcome.expense.receipt_number == "R-100"

    def test_suggested_match_leaves_upload_pending(self, db_session):
        _missing_expense(db_session, business_name="Super Shuk")
        upload = _pending_upload(db_session)

        outcome = apply_match_result(db_session, upload, _extracted(date=date(2026, 9, 3)))

        assert outcome.decision == MatchDecision.SUGGESTED
        assert outcome.expense.document_status == DocumentStatus.SUGGESTED
        assert outcome.expense.suggested_receipt_upload_id == upload.id

        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.PENDING

    def test_no_match_leaves_expense_missing(self, db_session):
        _missing_expense(db_session, business_name="Totally Different Store")
        upload = _pending_upload(db_session)

        outcome = apply_match_result(
            db_session, upload, _extracted(currency="USD", date=date(2020, 1, 1))
        )

        assert outcome.decision == MatchDecision.NO_MATCH
        assert outcome.expense is None

    def test_no_candidates_is_no_match(self, db_session):
        upload = _pending_upload(db_session)

        outcome = apply_match_result(db_session, upload, _extracted())

        assert outcome.decision == MatchDecision.NO_MATCH


class TestApproveRejectSuggestedMatch:
    def test_approve_attaches_receipt_and_clears_suggestion(self, db_session):
        expense = _missing_expense(db_session, business_name="Super Shuk")
        upload = _pending_upload(db_session)
        extracted = _extracted(date=date(2026, 9, 3), receipt_number="R-200")
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)
        apply_match_result(db_session, upload, extracted)

        approved = approve_suggested_match(db_session, expense.id)

        assert approved.document_status == DocumentStatus.ATTACHED
        assert approved.receipt_image_path == "receipt-key.jpg"
        assert approved.receipt_number == "R-200"
        assert approved.suggested_receipt_upload_id is None

        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.CONFIRMED

    def test_approve_is_idempotent_on_repeat_call(self, db_session):
        expense = _missing_expense(db_session, business_name="Super Shuk")
        upload = _pending_upload(db_session)
        extracted = _extracted(date=date(2026, 9, 3))
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)
        apply_match_result(db_session, upload, extracted)

        first = approve_suggested_match(db_session, expense.id)
        second = approve_suggested_match(db_session, expense.id)

        assert first.document_status == DocumentStatus.ATTACHED
        assert second.document_status == DocumentStatus.ATTACHED
        assert second.id == first.id

    def test_approve_missing_expense_returns_none(self, db_session):
        assert approve_suggested_match(db_session, "does-not-exist") is None

    def test_approve_fails_cleanly_if_linked_upload_was_discarded(self, db_session):
        expense = _missing_expense(db_session, business_name="Super Shuk")
        upload = _pending_upload(db_session)
        extracted = _extracted(date=date(2026, 9, 3))
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)
        apply_match_result(db_session, upload, extracted)
        upload.status = ReceiptUploadStatus.DISCARDED
        db_session.commit()

        with pytest.raises(ReceiptNotAvailableError):
            approve_suggested_match(db_session, expense.id)

        db_session.refresh(expense)
        assert expense.document_status == DocumentStatus.SUGGESTED

    def test_reject_returns_expense_to_missing(self, db_session):
        expense = _missing_expense(db_session, business_name="Super Shuk")
        upload = _pending_upload(db_session)
        apply_match_result(db_session, upload, _extracted(date=date(2026, 9, 3)))

        rejected = reject_suggested_match(db_session, expense.id)

        assert rejected.document_status == DocumentStatus.MISSING
        assert rejected.reconciliation_confidence is None
        assert rejected.suggested_receipt_upload_id is None

        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.PENDING

    def test_reject_is_idempotent(self, db_session):
        expense = _missing_expense(db_session, business_name="Super Shuk")
        upload = _pending_upload(db_session)
        apply_match_result(db_session, upload, _extracted(date=date(2026, 9, 3)))

        reject_suggested_match(db_session, expense.id)
        second = reject_suggested_match(db_session, expense.id)

        assert second.document_status == DocumentStatus.MISSING


class TestBuildInbox:
    def test_sections_are_populated_correctly(self, db_session):
        missing = _missing_expense(
            db_session, external_id="tx-missing", business_name="Unrelated Store", amount=Decimal("999.99")
        )
        suggested_source = _missing_expense(
            db_session, external_id="tx-suggested", business_name="Super Shuk", amount=Decimal("184.00")
        )
        upload = _pending_upload(db_session)
        apply_match_result(db_session, upload, _extracted(business_name="Super Shuk"))

        unassigned_upload = _pending_upload(db_session, stored_filename="orphan.png")

        inbox = build_inbox(db_session)

        assert missing.id in {e.id for e in inbox.missing_documents}
        assert suggested_source.id in {e.id for e in inbox.suggested_matches}
        assert unassigned_upload.id in {u.id for u in inbox.documents_without_transactions}

    def test_unassigned_section_excludes_suggested_confirmed_and_discarded_uploads(self, db_session):
        expense = _missing_expense(db_session, business_name="Super Shuk")
        suggested_upload = _pending_upload(db_session, stored_filename="suggested.png")
        apply_match_result(db_session, suggested_upload, _extracted(business_name="Super Shuk"))

        confirmed_upload = _pending_upload(db_session, stored_filename="confirmed.png")
        confirmed_upload.status = ReceiptUploadStatus.CONFIRMED
        discarded_upload = _pending_upload(db_session, stored_filename="discarded.png")
        discarded_upload.status = ReceiptUploadStatus.DISCARDED
        db_session.commit()

        truly_unassigned = _pending_upload(db_session, stored_filename="unassigned.png")

        inbox = build_inbox(db_session)

        unassigned_ids = {u.id for u in inbox.documents_without_transactions}
        assert unassigned_ids == {truly_unassigned.id}
        assert suggested_upload.id not in unassigned_ids
        assert confirmed_upload.id not in unassigned_ids
        assert discarded_upload.id not in unassigned_ids


class TestAttachToExpense:
    def test_attaches_pending_upload_to_missing_expense(self, db_session):
        expense = _missing_expense(db_session)
        upload = _pending_upload(db_session)
        extracted = _extracted(vat=Decimal("26.85"), receipt_number="R-300")
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)

        attached = attach_to_expense(db_session, upload.id, expense.id)

        assert attached.document_status == DocumentStatus.ATTACHED
        assert attached.receipt_image_path == "receipt-key.jpg"
        assert attached.vat_amount == Decimal("26.85")
        assert attached.receipt_number == "R-300"

        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.CONFIRMED
        assert upload.expense_id == expense.id

    def test_only_one_of_two_concurrent_attach_attempts_succeeds(self, db_session):
        """Simulates two requests racing to attach different receipts to the
        same expense: both attempt the conditional claim, only the first's
        UPDATE affects a row, and the loser gets a clean ExpenseNotEligibleError
        instead of silently overwriting the winner's attachment."""
        expense = _missing_expense(db_session)
        first_upload = _pending_upload(db_session, stored_filename="first.jpg")
        second_upload = _pending_upload(db_session, stored_filename="second.jpg")

        first_result = attach_to_expense(db_session, first_upload.id, expense.id)
        assert first_result.document_status == DocumentStatus.ATTACHED

        with pytest.raises(ExpenseNotEligibleError):
            attach_to_expense(db_session, second_upload.id, expense.id)

        db_session.refresh(expense)
        db_session.refresh(first_upload)
        db_session.refresh(second_upload)
        assert expense.receipt_image_path == "first.jpg"
        assert first_upload.status == ReceiptUploadStatus.CONFIRMED
        assert second_upload.status == ReceiptUploadStatus.PENDING


class TestTargetedMatch:
    def test_no_conflict_attaches_immediately(self, db_session):
        expense = _missing_expense(db_session)
        upload = _pending_upload(db_session)
        extracted = _extracted()

        result = targeted_match(db_session, upload, expense, extracted)

        assert result.attached is True
        assert result.expense is not None
        assert result.expense.document_status == DocumentStatus.ATTACHED

    def test_conflict_does_not_attach(self, db_session):
        expense = _missing_expense(db_session, amount=Decimal("184.90"), expense_date=date(2026, 9, 1))
        upload = _pending_upload(db_session)
        extracted = _extracted(total=Decimal("684.90"), date=date(2026, 9, 1))

        result = targeted_match(db_session, upload, expense, extracted)

        assert result.attached is False
        assert result.expense is expense
        assert expense.document_status == DocumentStatus.MISSING

        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.PENDING


class TestRejectReappearsUnassigned:
    def test_rejecting_a_suggestion_makes_its_receipt_reappear_as_unassigned(self, db_session):
        """The concrete regression test for 'must not leave the rejected
        receipt as an invisible pending upload' — this is a structural
        consequence of clearing only the Expense-side pointer, not a
        separately implemented behavior."""
        expense = _missing_expense(db_session, business_name="Super Shuk")
        upload = _pending_upload(db_session)
        extracted = _extracted(date=date(2026, 9, 3))
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)
        apply_match_result(db_session, upload, extracted)

        before = build_inbox(db_session)
        assert upload.id not in {u.id for u in before.documents_without_transactions}

        reject_suggested_match(db_session, expense.id)

        after = build_inbox(db_session)
        assert upload.id in {u.id for u in after.documents_without_transactions}
        db_session.refresh(upload)
        assert upload.extracted_business_name == "Shufersal"


class TestRematchDocument:
    def test_rematch_creates_a_suggestion_when_a_candidate_now_qualifies(self, db_session):
        upload = _pending_upload(db_session)
        extracted = _extracted(business_name="Super Shuk")
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)

        outcome = rematch_document(db_session, upload.id)
        assert outcome.decision == MatchDecision.NO_MATCH

        expense = _missing_expense(db_session, business_name="Super Shuk")
        outcome = rematch_document(db_session, upload.id)

        assert outcome.decision != MatchDecision.NO_MATCH
        assert outcome.expense is not None
        assert outcome.expense.id == expense.id

    def test_rematch_is_a_no_op_when_nothing_matches(self, db_session):
        upload = _pending_upload(db_session)
        extracted = _extracted(business_name="Totally Unrelated")
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)

        outcome = rematch_document(db_session, upload.id)

        assert outcome.decision == MatchDecision.NO_MATCH
        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.PENDING

    def test_rematch_unknown_document_raises(self, db_session):

        with pytest.raises(ReceiptNotFoundError):
            rematch_document(db_session, "does-not-exist")

    def test_rematch_discarded_document_raises(self, db_session):
        upload = _pending_upload(db_session)
        upload.status = ReceiptUploadStatus.DISCARDED
        db_session.commit()

        with pytest.raises(ReceiptNotAvailableError):
            rematch_document(db_session, upload.id)


class TestListEligibleExpenses:
    def test_lists_only_missing_expenses_with_a_conflict_preview(self, db_session):

        matching = _missing_expense(db_session, business_name="Super Shuk", external_id="tx-a")
        conflicting = _missing_expense(
            db_session, business_name="Super Shuk", amount=Decimal("999.99"), external_id="tx-b"
        )
        not_missing = _missing_expense(
            db_session, business_name="Super Shuk", external_id="tx-c", document_status=DocumentStatus.ATTACHED
        )
        upload = _pending_upload(db_session)
        extracted = _extracted(business_name="Super Shuk", date=date(2026, 9, 1))
        ReceiptUploadRepository(db_session).save_extraction(upload, extracted)

        candidates = list_eligible_expenses(db_session, upload.id)
        candidate_ids = {c.expense_id for c in candidates}

        assert matching.id in candidate_ids
        assert conflicting.id in candidate_ids
        assert not_missing.id not in candidate_ids
        conflicting_candidate = next(c for c in candidates if c.expense_id == conflicting.id)
        assert conflicting_candidate.has_conflict is True


class TestDiscardDocument:
    def test_discard_marks_document_discarded(self, db_session):

        upload = _pending_upload(db_session)

        discard_document(db_session, upload.id)

        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.DISCARDED

    def test_discard_clears_a_dangling_suggestion_pointer(self, db_session):

        expense = _missing_expense(db_session, business_name="Super Shuk")
        upload = _pending_upload(db_session)
        apply_match_result(db_session, upload, _extracted(date=date(2026, 9, 3)))
        db_session.refresh(expense)
        assert expense.document_status == DocumentStatus.SUGGESTED

        discard_document(db_session, upload.id)

        db_session.refresh(expense)
        assert expense.document_status == DocumentStatus.MISSING
        assert expense.suggested_receipt_upload_id is None

    def test_discard_is_idempotent(self, db_session):

        upload = _pending_upload(db_session)

        discard_document(db_session, upload.id)
        discard_document(db_session, upload.id)

        db_session.refresh(upload)
        assert upload.status == ReceiptUploadStatus.DISCARDED

    def test_discarded_document_can_never_be_approved_or_attached(self, db_session):

        expense = _missing_expense(db_session)
        upload = _pending_upload(db_session)
        ReceiptUploadRepository(db_session).save_extraction(upload, _extracted())

        discard_document(db_session, upload.id)

        with pytest.raises(ReceiptNotAvailableError):
            attach_to_expense(db_session, upload.id, expense.id)

    def test_discard_unknown_document_raises(self, db_session):

        with pytest.raises(ReceiptNotFoundError):
            discard_document(db_session, "does-not-exist")
