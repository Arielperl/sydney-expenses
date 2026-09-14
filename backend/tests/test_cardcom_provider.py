"""Unit tests for the Cardcom adapter — both halves: reading `LowProfileId`
out of an untrusted raw delivery, and building a `PaymentEvent` from an
already-verified `GetLpResult` response. Fixtures come from Cardcom's own
published example (tests/fixtures/cardcom_payloads.py)."""

from decimal import Decimal

import pytest

from app.models.sale import SaleStatus
from app.services.ingestion.cardcom_provider import (
    CardcomPayloadError,
    CardcomUnsupportedOperationError,
    CardcomVerificationError,
    extract_low_profile_id,
    parse_lowprofile_result,
)
from tests.fixtures.cardcom_payloads import (
    CARDCOM_GET_LP_RESULT_CALL_FAILED,
    CARDCOM_GET_LP_RESULT_DECLINED,
    CARDCOM_GET_LP_RESULT_SUCCESS,
    CARDCOM_GET_LP_RESULT_TOKEN_ONLY,
    CARDCOM_RAW_WEBHOOK_FORM,
    CARDCOM_RAW_WEBHOOK_CODE_JSON,
    CARDCOM_RAW_WEBHOOK_JSON,
)


class TestExtractLowProfileId:
    def test_extracts_from_json_shaped_dict(self):
        assert extract_low_profile_id(CARDCOM_RAW_WEBHOOK_JSON) == "8c92820a-2f6f-4120-a699-ab1969b2f78b"

    def test_extracts_from_form_decoded_dict(self):
        from urllib.parse import parse_qsl

        payload = dict(parse_qsl(CARDCOM_RAW_WEBHOOK_FORM))
        assert extract_low_profile_id(payload) == "8c92820a-2f6f-4120-a699-ab1969b2f78b"

    def test_extracts_callback_low_profile_code_case_insensitively(self):
        assert extract_low_profile_id(CARDCOM_RAW_WEBHOOK_CODE_JSON) == "declined-lp-id-0001"
        assert extract_low_profile_id({"lowprofilecode": "lower-case-code"}) == "lower-case-code"

    def test_missing_low_profile_id_is_rejected(self):
        with pytest.raises(CardcomPayloadError):
            extract_low_profile_id({"TerminalNumber": 1000})

    def test_blank_low_profile_id_is_rejected(self):
        with pytest.raises(CardcomPayloadError):
            extract_low_profile_id({"LowProfileId": "   "})


class TestParseLowProfileResult:
    def test_parses_the_official_success_example(self):
        event = parse_lowprofile_result(CARDCOM_GET_LP_RESULT_SUCCESS)
        assert event.provider == "cardcom"
        assert event.status == SaleStatus.SUCCEEDED
        assert event.external_transaction_id == "209413394"
        assert event.gross_amount == Decimal("10.5")
        assert event.currency == "ILS"
        assert event.customer_name == "Card Owner"
        assert event.customer_email == "testsite@test.co.il"
        assert event.payment_method == "card"
        assert event.processing_fee is None
        assert event.occurred_at.isoformat() == "2025-05-06T10:48:21"

    def test_vat_is_computed_under_standard_israeli_vat(self):
        event = parse_lowprofile_result(CARDCOM_GET_LP_RESULT_SUCCESS)
        assert event.net_amount == event.gross_amount - event.vat_amount
        assert event.vat_rate == Decimal("0.18")

    def test_declined_transaction_becomes_a_failed_status_not_an_exception(self):
        event = parse_lowprofile_result(CARDCOM_GET_LP_RESULT_DECLINED)
        assert event.status == SaleStatus.FAILED
        assert event.gross_amount == Decimal("250.0")  # the attempted amount, preserved

    def test_declined_transaction_still_has_a_usable_external_id(self):
        # No TranzactionId for a declined attempt — falls back to LowProfileId.
        event = parse_lowprofile_result(CARDCOM_GET_LP_RESULT_DECLINED)
        assert event.external_transaction_id == "lpid:declined-lp-id-0001"

    def test_non_charging_operation_is_rejected_not_silently_ignored(self):
        with pytest.raises(CardcomUnsupportedOperationError):
            parse_lowprofile_result(CARDCOM_GET_LP_RESULT_TOKEN_ONLY)

    def test_failed_verification_call_itself_is_rejected(self):
        with pytest.raises(CardcomVerificationError):
            parse_lowprofile_result(CARDCOM_GET_LP_RESULT_CALL_FAILED)

    def test_missing_tranzaction_info_is_rejected(self):
        payload = {"ResponseCode": 0, "Operation": "ChargeOnly", "LowProfileId": "x"}
        with pytest.raises(CardcomVerificationError):
            parse_lowprofile_result(payload)

    def test_not_a_dict_is_rejected(self):
        with pytest.raises(CardcomVerificationError):
            parse_lowprofile_result("not a dict")  # type: ignore[arg-type]


class TestNeverStoresCardDataOrCredentials:
    def test_card_brand_and_last4_never_appear_on_the_returned_event(self):
        import dataclasses

        event = parse_lowprofile_result(CARDCOM_GET_LP_RESULT_SUCCESS)
        values = {str(value) for value in dataclasses.asdict(event).values()}
        assert "Visa" not in values
        assert event.payment_method == "card"
