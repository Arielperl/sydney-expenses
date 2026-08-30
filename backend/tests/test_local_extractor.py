import json
from decimal import Decimal

import httpx
import pytest

from app.api.deps import get_receipt_extractor
from app.core.config import get_settings
from app.services.extraction.exceptions import (
    ReceiptExtractionParsingError,
    ReceiptExtractionProviderError,
    ReceiptExtractionTimeoutError,
)
from app.services.extraction.local_extractor import LocalReceiptExtractor
from app.services.extraction.mock import MockReceiptExtractor


def _raw_json(**overrides) -> str:
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
    return json.dumps(defaults)


class _FakeResponse:
    def __init__(self, json_body=None, status_code=200, raw_text: str | None = None):
        self._json_body = json_body
        self.status_code = status_code
        self._raw_text = raw_text

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://localhost:11434/api/generate")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        if self._raw_text is not None:
            return {"response": self._raw_text}
        if self._json_body is None:
            raise ValueError("no body")
        return {"response": self._json_body}


class _FakeHttpClient:
    """Stands in for httpx.Client. `behaviors` is a queue of either a _FakeResponse
    to return or an exception instance to raise — consumed one per call."""

    def __init__(self, behaviors):
        self._behaviors = list(behaviors)
        self.call_count = 0
        self.last_payload = None

    def post(self, url, json=None):
        self.call_count += 1
        self.last_payload = json
        behavior = self._behaviors.pop(0)
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior


def _settings_with_local(**overrides):
    settings = get_settings().model_copy(
        update={
            "receipt_extractor_provider": "local",
            "ollama_max_retries": 2,
            **overrides,
        }
    )
    return settings


def _dummy_image(tmp_path):
    path = tmp_path / "receipt.png"
    path.write_bytes(b"fake-bytes")
    return str(path)


def _valid_image(tmp_path):
    from tests.conftest import VALID_PNG_BYTES

    path = tmp_path / "receipt.png"
    path.write_bytes(VALID_PNG_BYTES)
    return str(path)


def _extractor_with_no_ocr(settings, client):
    extractor = LocalReceiptExtractor(settings, http_client=client)
    extractor._run_ocr = lambda path: ("", None)  # bypass real Tesseract in unit tests
    return extractor


# --- Provider selection ---------------------------------------------------


def test_default_provider_is_mock():
    get_settings.cache_clear()
    get_receipt_extractor.cache_clear()
    try:
        assert isinstance(get_receipt_extractor(), MockReceiptExtractor)
    finally:
        get_settings.cache_clear()
        get_receipt_extractor.cache_clear()


def test_local_provider_selected_with_valid_config(monkeypatch):
    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "local")
    get_settings.cache_clear()
    get_receipt_extractor.cache_clear()
    try:
        assert isinstance(get_receipt_extractor(), LocalReceiptExtractor)
    finally:
        get_settings.cache_clear()
        get_receipt_extractor.cache_clear()


# --- Mapping a valid response ------------------------------------------------


def test_maps_a_valid_structured_response(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name == "Shufersal"
    assert result.total == Decimal("184.90")
    assert result.vat == Decimal("26.65")
    assert result.currency == "ILS"
    assert result.category == "groceries"
    assert 0 <= result.confidence <= 1


def test_uses_json_schema_format_and_includes_image(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)

    extractor.extract(_dummy_image(tmp_path))

    payload = client.last_payload
    assert payload["model"] == "gemma3:12b"
    assert payload["stream"] is False
    assert "properties" in payload["format"]  # a real JSON schema, not free-form
    assert len(payload["images"]) == 1


def test_currency_is_normalized_to_uppercase(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(currency="ils"))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.currency == "ILS"


# --- Nullable / partial / invalid fields -------------------------------------


def test_nullable_optional_fields_are_handled(tmp_path):
    client = _FakeHttpClient(
        [_FakeResponse(json_body=_raw_json(business_name=None, receipt_number=None, date=None, total=None, vat=None))]
    )
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name is None
    assert result.total is None
    assert "business_name_not_confident" in result.warnings
    assert "total_not_confident" in result.warnings


def test_invalid_date_is_discarded_with_warning(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(date="not-a-date"))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.date is None
    assert "date_not_confident" in result.warnings


def test_vat_greater_than_total_is_discarded(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(total=10.0, vat=50.0))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.vat is None
    assert "vat_amount_not_confident" in result.warnings


def test_invalid_currency_falls_back_to_ils(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(currency="1LS"))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.currency == "ILS"


def test_invalid_category_falls_back_to_other(tmp_path):
    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json(category="not-a-real-category"))])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    result = extractor.extract(_dummy_image(tmp_path))
    assert result.category == "other"


def test_malformed_json_output_raises_parsing_error(tmp_path):
    client = _FakeHttpClient([_FakeResponse(raw_text="this is not json")])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    with pytest.raises(ReceiptExtractionParsingError):
        extractor.extract(_dummy_image(tmp_path))


def test_empty_response_raises_parsing_error(tmp_path):
    client = _FakeHttpClient([_FakeResponse(raw_text="")])
    extractor = _extractor_with_no_ocr(_settings_with_local(), client)
    with pytest.raises(ReceiptExtractionParsingError):
        extractor.extract(_dummy_image(tmp_path))


# --- Ollama availability / timeout / retries ---------------------------------


def test_ollama_unavailable_raises_clear_provider_error(tmp_path, monkeypatch):
    monkeypatch.setattr(LocalReceiptExtractor, "_retry_backoff_base_seconds", 0)
    connect_error = httpx.ConnectError("Connection refused")
    client = _FakeHttpClient([connect_error, connect_error, connect_error])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_max_retries=2), client)

    with pytest.raises(ReceiptExtractionProviderError, match="Ollama"):
        extractor.extract(_dummy_image(tmp_path))

    assert client.call_count == 3  # initial attempt + 2 retries


def test_timeout_retries_then_raises_after_bound_exhausted(tmp_path, monkeypatch):
    monkeypatch.setattr(LocalReceiptExtractor, "_retry_backoff_base_seconds", 0)
    timeout = httpx.TimeoutException("timed out")
    client = _FakeHttpClient([timeout, timeout, timeout])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_max_retries=2), client)

    with pytest.raises(ReceiptExtractionTimeoutError):
        extractor.extract(_dummy_image(tmp_path))

    assert client.call_count == 3


def test_transient_5xx_retries_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(LocalReceiptExtractor, "_retry_backoff_base_seconds", 0)
    client = _FakeHttpClient(
        [_FakeResponse(status_code=503), _FakeResponse(status_code=503), _FakeResponse(json_body=_raw_json())]
    )
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_max_retries=2), client)

    result = extractor.extract(_dummy_image(tmp_path))

    assert result.business_name == "Shufersal"
    assert client.call_count == 3


def test_non_transient_error_is_not_retried(tmp_path):
    client = _FakeHttpClient([_FakeResponse(status_code=400)])
    extractor = _extractor_with_no_ocr(_settings_with_local(ollama_max_retries=2), client)

    with pytest.raises(ReceiptExtractionProviderError):
        extractor.extract(_dummy_image(tmp_path))

    assert client.call_count == 1


# --- OCR: Hebrew/English handling and Tesseract-failure fallback ------------


def test_hebrew_and_english_ocr_text_is_included_in_the_prompt(tmp_path, monkeypatch):
    import app.services.extraction.local_extractor as local_extractor_module

    class _FakePytesseract:
        @staticmethod
        def image_to_string(image, lang):
            assert lang == "heb+eng"
            return "שופרסל\nTOTAL: 42.50"

    monkeypatch.setattr(local_extractor_module, "pytesseract", _FakePytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    extractor.extract(_valid_image(tmp_path))

    assert "שופרסל" in client.last_payload["prompt"]
    assert "TOTAL: 42.50" in client.last_payload["prompt"]


def test_tesseract_failure_falls_back_to_image_only_extraction(tmp_path, monkeypatch):
    import app.services.extraction.local_extractor as local_extractor_module

    class _FailingPytesseract:
        @staticmethod
        def image_to_string(image, lang):
            raise RuntimeError("tesseract binary not found")

    monkeypatch.setattr(local_extractor_module, "pytesseract", _FailingPytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    result = extractor.extract(_valid_image(tmp_path))

    assert result.business_name == "Shufersal"  # extraction still succeeded via the image
    assert "ocr_unavailable" in result.warnings


def test_sensitive_ocr_content_is_not_logged(tmp_path, monkeypatch, caplog):
    import app.services.extraction.local_extractor as local_extractor_module

    secret_text = "שם פרטי: ישראל ישראלי מספר כרטיס 4111111111111111"

    class _FakePytesseract:
        @staticmethod
        def image_to_string(image, lang):
            raise RuntimeError(secret_text)  # simulate an error that could embed OCR text

    monkeypatch.setattr(local_extractor_module, "pytesseract", _FakePytesseract)

    client = _FakeHttpClient([_FakeResponse(json_body=_raw_json())])
    extractor = LocalReceiptExtractor(_settings_with_local(), http_client=client)

    with caplog.at_level("DEBUG"):
        extractor.extract(_valid_image(tmp_path))

    for record in caplog.records:
        assert secret_text not in record.getMessage()
        assert "fake-bytes" not in record.getMessage()  # the raw image bytes


# --- Upload-route level: extraction failure must not block manual entry -----


def test_upload_with_ollama_unreachable_still_saves_the_file_and_allows_manual_entry(client, monkeypatch):
    import io

    from app.api.deps import get_receipt_extractor as _get_receipt_extractor
    from tests.conftest import VALID_PNG_BYTES

    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "local")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:1")  # nothing listens here
    monkeypatch.setenv("OLLAMA_MAX_RETRIES", "0")
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


def test_no_expense_saved_during_local_extraction_itself(client, monkeypatch):
    import io

    from app.api.deps import get_receipt_extractor as _get_receipt_extractor
    from tests.conftest import VALID_PNG_BYTES

    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "local")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:1")
    monkeypatch.setenv("OLLAMA_MAX_RETRIES", "0")
    get_settings.cache_clear()
    _get_receipt_extractor.cache_clear()
    try:
        client.post(
            "/api/receipts/upload",
            files={"file": ("receipt.png", io.BytesIO(VALID_PNG_BYTES), "image/png")},
        )
        assert client.get("/api/expenses").json() == []
    finally:
        monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "mock")
        get_settings.cache_clear()
        _get_receipt_extractor.cache_clear()


# --- /system/capabilities for local mode -------------------------------------


def test_system_capabilities_reports_local_mode(client, monkeypatch):
    monkeypatch.setenv("RECEIPT_EXTRACTOR_PROVIDER", "local")
    get_settings.cache_clear()
    try:
        response = client.get("/api/system/capabilities")
        body = response.json()
        assert body["receipt_extraction_provider"] == "local"
        assert body["receipt_extraction_mode"] == "local"
        assert body["real_ai_enabled"] is True
        assert isinstance(body["tesseract_available"], bool)
        assert isinstance(body["ollama_available"], bool)
        assert "key" not in str(body).lower()
    finally:
        get_settings.cache_clear()
