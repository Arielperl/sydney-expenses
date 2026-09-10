from datetime import date
from decimal import Decimal

from app.models.expense import DocumentStatus, Expense, ExpenseCategory, ExpenseSource
from app.schemas.receipt import ExtractedReceiptData
from app.services.reconciliation.matching import (
    HIGH_MATCH_THRESHOLD,
    MATCH_MARGIN,
    MEDIUM_MATCH_THRESHOLD,
    MatchDecision,
    decide,
    find_candidates,
    score_candidate,
)


def _expense(**overrides) -> Expense:
    defaults = dict(
        business_name="Shufersal",
        amount=Decimal("184.90"),
        currency="ILS",
        category=ExpenseCategory.GROCERIES,
        expense_date=date(2026, 9, 1),
        source=ExpenseSource.WEBHOOK,
        document_status=DocumentStatus.MISSING,
    )
    defaults.update(overrides)
    return Expense(**defaults)


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


class TestScoreCandidate:
    def test_identical_amount_currency_date_merchant_scores_high(self):
        result = score_candidate(_expense(), _extracted())
        assert result.score >= HIGH_MATCH_THRESHOLD
        assert "same_amount" in result.reasons
        assert "same_currency" in result.reasons
        assert "date_same_day" in result.reasons
        assert "merchant_similar" in result.reasons
        assert result.has_conflict is False

    def test_currency_mismatch_caps_score_despite_other_signals_matching(self):
        result = score_candidate(_expense(), _extracted(currency="USD"))
        assert result.score < MEDIUM_MATCH_THRESHOLD
        assert "currency_mismatch" in result.reasons

    def test_date_far_apart_scores_low_on_date_component(self):
        close = score_candidate(_expense(), _extracted(date=date(2026, 9, 1)))
        far = score_candidate(_expense(), _extracted(date=date(2026, 8, 1)))
        assert far.score < close.score
        assert "date_far" in far.reasons

    def test_receipt_number_match_adds_bonus(self):
        without = score_candidate(
            _expense(receipt_number="R-100"), _extracted(receipt_number=None)
        )
        with_match = score_candidate(
            _expense(receipt_number="R-100"), _extracted(receipt_number="R-100")
        )
        assert with_match.score > without.score
        assert "receipt_number_match" in with_match.reasons

    def test_strong_merchant_and_date_with_amount_conflict_flags_conflict(self):
        result = score_candidate(_expense(), _extracted(total=Decimal("500.00")))
        assert result.has_conflict is True

    def test_score_never_exceeds_one(self):
        result = score_candidate(
            _expense(receipt_number="R-1"), _extracted(receipt_number="R-1")
        )
        assert result.score <= 1.0


class TestDecide:
    def test_high_score_with_margin_is_auto_match(self):
        candidates = [
            score_candidate(_expense(), _extracted()),
        ]
        decision, best = decide(candidates)
        assert decision == MatchDecision.AUTO_MATCH
        assert best is candidates[0]

    def test_high_score_but_close_second_candidate_is_suggested_not_auto(self):
        best = score_candidate(_expense(), _extracted())
        near_tie = score_candidate(
            _expense(business_name="Shufersal Express"), _extracted()
        )
        ordered = sorted([best, near_tie], key=lambda c: c.score, reverse=True)
        assert ordered[0].score - ordered[1].score < MATCH_MARGIN
        decision, _ = decide(ordered)
        assert decision != MatchDecision.AUTO_MATCH

    def test_medium_score_is_suggested(self):
        result = score_candidate(
            _expense(business_name="Super Shuk"), _extracted(date=date(2026, 9, 3))
        )
        assert MEDIUM_MATCH_THRESHOLD <= result.score < HIGH_MATCH_THRESHOLD
        decision, best = decide([result])
        assert decision == MatchDecision.SUGGESTED
        assert best is result

    def test_conflict_is_needs_review(self):
        result = score_candidate(_expense(), _extracted(total=Decimal("500.00")))
        decision, best = decide([result])
        assert decision == MatchDecision.NEEDS_REVIEW
        assert best is result

    def test_low_score_is_no_match(self):
        result = score_candidate(
            _expense(business_name="Totally Different Store", amount=Decimal("9.99")),
            _extracted(currency="USD", date=date(2020, 1, 1)),
        )
        decision, best = decide([result])
        assert decision == MatchDecision.NO_MATCH
        assert best is None

    def test_empty_candidate_list_is_no_match(self):
        decision, best = decide([])
        assert decision == MatchDecision.NO_MATCH
        assert best is None


class TestFindCandidates:
    def test_only_missing_document_status_expenses_are_candidates(self, db_session):
        missing = _expense(document_status=DocumentStatus.MISSING)
        attached = _expense(document_status=DocumentStatus.ATTACHED, business_name="Already Matched")
        db_session.add_all([missing, attached])
        db_session.commit()

        candidates = find_candidates(db_session, _extracted())

        ids = {c.expense_id for c in candidates}
        assert missing.id in ids
        assert attached.id not in ids

    def test_candidates_sorted_descending_by_score(self, db_session):
        good = _expense(business_name="Shufersal")
        bad = _expense(business_name="Totally Different Store", amount=Decimal("1.00"))
        db_session.add_all([good, bad])
        db_session.commit()

        candidates = find_candidates(db_session, _extracted())

        assert candidates[0].expense_id == good.id
        assert candidates[0].score >= candidates[-1].score
