"""Unit tests for the Grow account-level payload adapter, using Grow's own
published examples as fixtures (tests/fixtures/grow_payloads.py)."""

from decimal import Decimal

import pytest

from app.models.sale import SaleStatus, TaxTreatment
from app.services.ingestion.grow_provider import GrowPayloadError, parse_grow_event
from tests.fixtures.grow_payloads import (
    GROW_INSTALLMENTS_PAYMENT,
    GROW_PAYMENT_LINKS_EXCLUDED_FORMAT,
    GROW_RECURRING_PAYMENT_UNSUPPORTED,
    GROW_REGULAR_PAYMENT,
)


class TestRegularPayment:
    def test_parses_the_official_regular_payment_example(self):
        event = parse_grow_event(GROW_REGULAR_PAYMENT)
        assert event.provider == "grow"
        assert event.external_transaction_id == "ABCD1234"
        assert event.event_id == "ABCD1234"
        assert event.gross_amount == Decimal("2.00")
        assert event.currency == "ILS"
        assert event.status == SaleStatus.SUCCEEDED
        assert event.tax_treatment == TaxTreatment.STANDARD
        assert event.customer_name == "Full Name"
        assert event.customer_email == "test@test.com"  # prefers email over phone
        assert event.service_name == "Description"
        assert event.description == "Description"
        assert event.payment_method == "card"
        assert event.processing_fee is None

    def test_date_only_payload_becomes_business_local_midnight(self):
        event = parse_grow_event(GROW_REGULAR_PAYMENT)
        assert event.occurred_at.isoformat() == "2021-10-14T00:00:00"

    def test_non_zero_padded_date_is_parsed(self):
        event = parse_grow_event(GROW_INSTALLMENTS_PAYMENT)  # "28/3/22"
        assert event.occurred_at.isoformat() == "2022-03-28T00:00:00"

    def test_vat_is_computed_under_standard_israeli_vat(self):
        event = parse_grow_event(GROW_REGULAR_PAYMENT)
        assert event.vat_amount == Decimal("0.31")  # 2.00 * 18/118, rounded
        assert event.net_amount == event.gross_amount - event.vat_amount
        assert event.vat_rate == Decimal("0.18")

    def test_installments_payment_type_is_accepted_as_revenue(self):
        event = parse_grow_event(GROW_INSTALLMENTS_PAYMENT)
        assert event.status == SaleStatus.SUCCEEDED
        assert event.external_transaction_id == "ABCD1235"

    def test_prefers_email_falls_back_to_phone_when_no_email(self):
        payload = {**GROW_REGULAR_PAYMENT, "payerEmail": None}
        event = parse_grow_event(payload)
        assert event.customer_email == "0500000000"

    def test_missing_customer_name_falls_back_defensively(self):
        payload = {**GROW_REGULAR_PAYMENT}
        del payload["fullName"]
        event = parse_grow_event(payload)
        assert event.customer_name  # non-empty, never blank

    def test_missing_description_falls_back_to_a_generic_service_name(self):
        payload = {**GROW_REGULAR_PAYMENT}
        del payload["paymentDesc"]
        event = parse_grow_event(payload)
        assert event.service_name  # non-empty, never blank
        assert event.description is None


class TestRejectedAndUnsupportedPayloads:
    def test_recurring_payment_type_is_rejected_not_silently_accepted(self):
        with pytest.raises(GrowPayloadError, match="paymentType"):
            parse_grow_event(GROW_RECURRING_PAYMENT_UNSUPPORTED)

    def test_unknown_payment_type_is_rejected(self):
        payload = {**GROW_REGULAR_PAYMENT, "paymentType": "משהו אחר"}
        with pytest.raises(GrowPayloadError, match="paymentType"):
            parse_grow_event(payload)

    def test_payment_links_format_is_not_accepted_by_this_adapter(self):
        # Structurally different payload (transactionId/sum/statusCode) —
        # missing transactionCode/paymentSum/paymentType entirely.
        with pytest.raises(GrowPayloadError):
            parse_grow_event(GROW_PAYMENT_LINKS_EXCLUDED_FORMAT)

    def test_missing_transaction_code_is_rejected(self):
        payload = {**GROW_REGULAR_PAYMENT}
        del payload["transactionCode"]
        with pytest.raises(GrowPayloadError, match="transactionCode"):
            parse_grow_event(payload)

    def test_missing_payment_sum_is_rejected(self):
        payload = {**GROW_REGULAR_PAYMENT}
        del payload["paymentSum"]
        with pytest.raises(GrowPayloadError, match="paymentSum"):
            parse_grow_event(payload)

    def test_negative_payment_sum_is_rejected(self):
        payload = {**GROW_REGULAR_PAYMENT, "paymentSum": -5}
        with pytest.raises(GrowPayloadError):
            parse_grow_event(payload)

    def test_zero_payment_sum_is_rejected(self):
        payload = {**GROW_REGULAR_PAYMENT, "paymentSum": 0}
        with pytest.raises(GrowPayloadError):
            parse_grow_event(payload)

    def test_malformed_date_is_rejected(self):
        payload = {**GROW_REGULAR_PAYMENT, "paymentDate": "not-a-date"}
        with pytest.raises(GrowPayloadError, match="paymentDate"):
            parse_grow_event(payload)

    def test_impossible_calendar_date_is_rejected(self):
        payload = {**GROW_REGULAR_PAYMENT, "paymentDate": "31/2/22"}
        with pytest.raises(GrowPayloadError):
            parse_grow_event(payload)

    def test_far_future_date_is_rejected(self):
        payload = {**GROW_REGULAR_PAYMENT, "paymentDate": "1/1/99"}  # -> 2099
        with pytest.raises(GrowPayloadError):
            parse_grow_event(payload)


class TestNeverStoresCardDataOrWebhookKey:
    def test_card_fields_never_appear_anywhere_on_the_returned_event(self):
        import dataclasses

        event = parse_grow_event(GROW_REGULAR_PAYMENT)
        values = {str(value) for value in dataclasses.asdict(event).values()}
        # cardBrand/cardType from the fixture — distinct strings that can't
        # collide with a legitimate field like transactionCode.
        assert "Mastercard" not in values
        assert "Local" not in values
        assert event.payment_method == "card"  # fixed, generic value only — never the brand/suffix

    def test_webhook_key_value_never_appears_on_the_returned_event(self):
        import dataclasses

        event = parse_grow_event(GROW_REGULAR_PAYMENT)
        values = {str(value) for value in dataclasses.asdict(event).values()}
        assert GROW_REGULAR_PAYMENT["webhookKey"] not in values  # "ABC1234" — distinct from transactionCode "ABCD1234"
