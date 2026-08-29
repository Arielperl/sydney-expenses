from decimal import Decimal

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, BadRequestError

_FAKE_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/responses")

from app.api.deps import get_receipt_extractor
from app.core.config import get_settings
from app.services.extraction.exceptions import (
    ReceiptExtractionConfigError,
    ReceiptExtractionParsingError,
    ReceiptExtractionProviderError,
    ReceiptExtractionTimeoutError,
)
from app.services.extraction.mock import MockReceiptExtractor
from app.services.extraction.openai_extractor import OpenAIReceiptExtractor, _RawReceiptExtraction


class _FakeParsedResponse:
    def __init__(self, output_parsed):
        self.output_parsed = output_parsed


class _FakeResponses:
    """Stands in for `client.responses`. `behaviors` is a queue of either an
    `_raw` instance to return (wrapped in a fake response) or an exception instance
    to raise — consumed one per call, so tests can script exact call sequences."""

    def __init__(self, behaviors):
        self._behaviors = list(behaviors)
        self.call_count = 0

    def parse(self, **kwargs):
        self.call_count += 1
        behavior = self._behaviors.pop(0)
        if isinstance(behavior, BaseException):
            raise behavior
        return _FakeParsedResponse(behavior)


class _FakeOpenAIClient:
    def __init__(self, behaviors):
        self.responses = _FakeResponses(behaviors)


def _settings_with_openai(**overrides):
    settings = get_settings().model_copy(
        update={
            "receipt_extractor_provider": "openai",
            "openai_api_key": "sk-test-not-real",
            "openai_receipt_model": "gpt-test-model",
            "openai_max_retries": 2,
            **overrides,
        }
    )
    return settings


def _raw(**overrides):
    defaults = dict(
        business_name="Shufersal",
        receipt_number="12345",
        date="2026-01-15",
        total=184.90,
        vat=26.65,
        currency="ILS",
        category="groceries",
        warnings=[],
    )
    defaults.update(overrides)
    return _RawReceiptExtraction(**defaults)


def _dummy_image(tmp_path):
    path = tmp_path / "receipt.png"
    path.write_bytes(b"fake-bytes")
    return str(path)


# --- Provider selection ---------------------------------------------------


def test_default_provider_is_mock():
    get_settings.cache_clear()
    get_receipt_extractor.cache_clear()
    try:
        extractor = get_receipt_extractor()
        assert isinstance(extractor, MockReceiptExtractor)
    finally:
        get_settings.cache_clear()
        get_receipt_extractor.cache_clear()


def test_openai_provider_selected_with_valid_config(monkeypatch):
    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("OPENAI_RECEIPT_MODEL", "gpt-test-model")
    get_settings.cache_clear()
    get_receipt_extractor.cache_clear()
    try:
        extractor = get_receipt_extractor()
        assert isinstance(extractor, OpenAIReceiptExtractor)
    finally:
        get_settings.cache_clear()
        get_receipt_extractor.cache_clear()


# --- Configuration errors --------------------------------------------------


def test_missing_api_key_raises_config_error(tmp_path):
    settings = _settings_with_openai(openai_api_key=None)
    extractor = OpenAIReceiptExtractor(settings)
    with pytest.raises(ReceiptExtractionConfigError):
        extractor.extract(_dummy_image(tmp_path))


def test_missing_model_raises_config_error(tmp_path):
    settings = _settings_with_openai(openai_receipt_model=None)
    extractor = OpenAIReceiptExtractor(settings)
    with pytest.raises(ReceiptExtractionConfigError):
        extractor.extract(_dummy_image(tmp_path))


def test_config_error_never_includes_the_key_value(tmp_path):
    settings = _settings_with_openai(openai_api_key=None)
    extractor = OpenAIReceiptExtractor(settings)
    with pytest.raises(ReceiptExtractionConfigError) as exc_info:
        extractor.extract(_dummy_image(tmp_path))
    assert "sk-" not in str(exc_info.value)


# --- Mapping a valid response ----------------------------------------------


def test_maps_a_valid_structured_response(tmp_path):
    client = _FakeOpenAIClient([_raw()])
    settings = _settings_with_openai()
    extractor = OpenAIReceiptExtractor(settings, client=client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name == "Shufersal"
    assert result.receipt_number == "12345"
    assert result.total == Decimal("184.90")
    assert result.vat == Decimal("26.65")
    assert result.currency == "ILS"
    assert result.category == "groceries"
    assert 0 <= result.confidence <= 1


def test_currency_is_normalized_to_uppercase(tmp_path):
    client = _FakeOpenAIClient([_raw(currency="ils")])
    extractor = OpenAIReceiptExtractor(_settings_with_openai(), client=client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.currency == "ILS"


# --- Nullable / partial fields ----------------------------------------------


def test_nullable_optional_fields_are_handled(tmp_path):
    client = _FakeOpenAIClient(
        [_raw(business_name=None, receipt_number=None, date=None, total=None, vat=None)]
    )
    extractor = OpenAIReceiptExtractor(_settings_with_openai(), client=client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name is None
    assert result.total is None
    assert result.vat is None
    assert "business_name_not_confident" in result.warnings
    assert "total_not_confident" in result.warnings


def test_invalid_date_is_discarded_with_warning(tmp_path):
    client = _FakeOpenAIClient([_raw(date="not-a-date")])
    extractor = OpenAIReceiptExtractor(_settings_with_openai(), client=client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.date is None
    assert "date_not_confident" in result.warnings


def test_future_date_is_discarded_with_warning(tmp_path):
    client = _FakeOpenAIClient([_raw(date="2999-01-01")])
    extractor = OpenAIReceiptExtractor(_settings_with_openai(), client=client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.date is None
    assert "date_not_confident" in result.warnings


def test_vat_greater_than_total_is_discarded(tmp_path):
    client = _FakeOpenAIClient([_raw(total=10.0, vat=50.0)])
    extractor = OpenAIReceiptExtractor(_settings_with_openai(), client=client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.vat is None
    assert "vat_amount_not_confident" in result.warnings


def test_invalid_currency_falls_back_to_ils(tmp_path):
    client = _FakeOpenAIClient([_raw(currency="1LS")])
    extractor = OpenAIReceiptExtractor(_settings_with_openai(), client=client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.currency == "ILS"


# --- Timeout / retry behavior ------------------------------------------------


def test_timeout_retries_then_raises_after_bound_exhausted(tmp_path, monkeypatch):
    monkeypatch.setattr(OpenAIReceiptExtractor, "_retry_backoff_base_seconds", 0)
    client = _FakeOpenAIClient(
        [APITimeoutError(_FAKE_REQUEST), APITimeoutError(_FAKE_REQUEST), APITimeoutError(_FAKE_REQUEST)]
    )
    settings = _settings_with_openai(openai_max_retries=2)
    extractor = OpenAIReceiptExtractor(settings, client=client)

    with pytest.raises(ReceiptExtractionTimeoutError):
        extractor.extract(_dummy_image(tmp_path))

    assert client.responses.call_count == 3  # initial attempt + 2 retries, then give up


def test_transient_connection_error_retries_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(OpenAIReceiptExtractor, "_retry_backoff_base_seconds", 0)
    client = _FakeOpenAIClient(
        [APIConnectionError(request=_FAKE_REQUEST), APIConnectionError(request=_FAKE_REQUEST), _raw()]
    )
    settings = _settings_with_openai(openai_max_retries=2)
    extractor = OpenAIReceiptExtractor(settings, client=client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name == "Shufersal"
    assert client.responses.call_count == 3


def test_non_transient_error_is_not_retried(tmp_path):
    fake_response = httpx.Response(400, request=_FAKE_REQUEST, json={"error": {"message": "bad request"}})
    client = _FakeOpenAIClient([BadRequestError("bad request", response=fake_response, body=None)])
    settings = _settings_with_openai(openai_max_retries=2)
    extractor = OpenAIReceiptExtractor(settings, client=client)

    with pytest.raises(ReceiptExtractionProviderError):
        extractor.extract(_dummy_image(tmp_path))

    assert client.responses.call_count == 1  # no retry for a non-transient error


def test_malformed_provider_output_raises_parsing_error(tmp_path):
    client = _FakeOpenAIClient([None])  # output_parsed is None
    extractor = OpenAIReceiptExtractor(_settings_with_openai(), client=client)
    with pytest.raises(ReceiptExtractionParsingError):
        extractor.extract(_dummy_image(tmp_path))


# --- Upload-route level behavior (extraction failure must not block the app) --


def test_upload_with_misconfigured_openai_provider_still_saves_the_file_and_allows_manual_entry(
    client, monkeypatch
):
    import io

    from app.api.deps import get_receipt_extractor as _get_receipt_extractor
    from tests.conftest import VALID_PNG_BYTES

    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    _get_receipt_extractor.cache_clear()
    try:
        response = client.post(
            "/api/receipts/upload",
            files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["extraction_succeeded"] is False
        assert body["receipt_image_url"].startswith("/uploads/")
        assert "sk-" not in (body["error_message"] or "")

        # Manual entry is still possible: confirm the same upload with hand-typed data.
        confirm_response = client.post(
            "/api/receipts/confirm",
            json={
                "upload_id": body["upload_id"],
                "business_name": "Manual Entry",
                "amount": 10,
                "currency": "ILS",
                "category": "other",
                "expense_date": "2026-01-01",
            },
        )
        assert confirm_response.status_code == 201
    finally:
        monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "mock")
        get_settings.cache_clear()
        _get_receipt_extractor.cache_clear()


def test_no_expense_is_saved_during_extraction_itself(client):
    import io

    from tests.conftest import VALID_PNG_BYTES

    response = client.post(
        "/api/receipts/upload",
        files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
    )
    assert response.status_code == 200
    all_expenses = client.get("/api/expenses").json()
    assert all_expenses == []


# --- /system/capabilities ----------------------------------------------------


def test_system_capabilities_reports_mock_by_default(client):
    response = client.get("/api/system/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["receipt_extraction_provider"] == "mock"
    assert body["receipt_extraction_mode"] == "demo"
    assert "key" not in str(body).lower()


def test_system_capabilities_reports_openai_when_selected(client, monkeypatch):
    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "openai")
    get_settings.cache_clear()
    try:
        response = client.get("/api/system/capabilities")
        assert response.json()["receipt_extraction_mode"] == "ai"
    finally:
        get_settings.cache_clear()
